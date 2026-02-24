// gemini-sidecar/cli-executor.js
// @ai-rules:
// 1. [Pattern]: All shared state (_callbackResult, currentTask) accessed via state.js getters/setters -- NEVER direct variables.
// 2. [Pattern]: resolveResult() is the single result resolution function for BOTH executeCLI and executeCLIStreaming.
//    Priority: callback -> cachedFindings (fs.watch) -> disk findings -> retry prompt -> stdout tail.
// 3. [Pattern]: buildCLICommand reads AGENT_PERMISSION_MODE from process.env (not config). If set -> --permission-mode; else autoApprove -> skip-permissions.
// 4. [Pattern]: Claude --mcp-config resolved lazily (fs.existsSync at call time) so it picks up ~/.claude.json even when created after module load.
// 5. [Gotcha]: requestFindings spawns a second CLI process -- keep timeout low (60s) and never reject.
// 6. [Gotcha]: fs.watch cachedFindings is captured by closure in spawn callbacks -- not in state.js.

const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');
const { AGENT_CLI, AGENT_MODEL, AGENT_ROLE, TIMEOUT_MS, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS } = require('./config');
const state = require('./state');
const { parseStreamLine } = require('./stream-parser');
const { wsSend } = require('./ws-utils');

const CLAUDE_JSON_PATH = path.join(os.homedir(), '.claude.json');

function buildCLICommand(prompt, options = {}) {
    const permissionMode = process.env.AGENT_PERMISSION_MODE || '';
    if (AGENT_CLI === 'claude') {
        const args = [];
        if (fs.existsSync(CLAUDE_JSON_PATH)) {
            args.push('--mcp-config', CLAUDE_JSON_PATH);
        }
        if (permissionMode === 'plan') {
            args.push('--permission-mode', 'plan');
        } else if (options.autoApprove) {
            args.push('--dangerously-skip-permissions');
        }
        args.push('--output-format', 'stream-json', '--verbose');
        args.push('--model', AGENT_MODEL || 'claude-opus-4-6');
        if (options.sessionId) {
            args.push('--resume', options.sessionId);
        }
        const thinkPrefix = AGENT_ROLE === 'architect' ? 'Think harder. ' : '';
        args.push('-p', thinkPrefix + prompt);
        return { binary: 'claude', args };
    }
    const args = [];
    if (options.autoApprove) args.push('--yolo');
    args.push('-o', 'stream-json');
    if (options.sessionId) {
        args.push('--resume', options.sessionId);
    }
    args.push('-p', prompt);
    return { binary: 'gemini', args };
}

function readFindings(workDir) {
    const findingsPath = `${workDir}/results/findings.md`;
    try {
        if (fs.existsSync(findingsPath)) {
            const stats = fs.statSync(findingsPath);
            const ageMs = Date.now() - stats.mtimeMs;
            if (ageMs > FINDINGS_FRESHNESS_MS) {
                console.log(`[${new Date().toISOString()}] findings.md is stale (${Math.round(ageMs/1000)}s old), ignoring`);
                return null;
            }
            const content = fs.readFileSync(findingsPath, 'utf8').trim();
            fs.unlinkSync(findingsPath);
            console.log(`[${new Date().toISOString()}] Read findings from ${findingsPath} (${content.length} chars)`);
            if (content.length > 0) return content;
            console.log(`[${new Date().toISOString()}] Findings file was empty`);
        }
    } catch (err) {
        console.log(`[${new Date().toISOString()}] Could not read findings file: ${err.message}`);
    }
    return null;
}

function stdoutFallback(effectiveOutput) {
    const MAX_FALLBACK_CHARS = 3000;
    if (effectiveOutput.length <= MAX_FALLBACK_CHARS) {
        console.log(`[${new Date().toISOString()}] No findings, using full stdout (${effectiveOutput.length} chars)`);
        return effectiveOutput;
    }
    const tail = effectiveOutput.slice(-MAX_FALLBACK_CHARS);
    console.log(`[${new Date().toISOString()}] No findings, using stdout tail (${MAX_FALLBACK_CHARS} of ${effectiveOutput.length} chars)`);
    return `[...truncated planning output...]\n\n${tail}`;
}

/**
 * Unified result resolution for CLI close handlers.
 * Priority: callback -> cachedFindings -> disk findings -> retry -> stdout tail.
 */
async function resolveResult(opts) {
    const { callbackResult, cachedFindings, findingsPath, workDir, autoApprove, effectiveOutput } = opts;

    if (callbackResult && callbackResult.length > 0) {
        console.log(`[${new Date().toISOString()}] Using callback result (${callbackResult.length} chars)`);
        return { output: callbackResult, source: 'callback' };
    }

    if (cachedFindings && cachedFindings.content && cachedFindings.content.length > 0) {
        console.log(`[${new Date().toISOString()}] Using cached findings (${cachedFindings.content.length} chars)`);
        try { if (fs.existsSync(findingsPath)) fs.unlinkSync(findingsPath); } catch(e) {}
        return { output: cachedFindings.content, source: 'findings' };
    }

    if (fs.existsSync(findingsPath)) {
        try {
            const content = fs.readFileSync(findingsPath, 'utf8').trim();
            fs.unlinkSync(findingsPath);
            if (content.length > 0) {
                console.log(`[${new Date().toISOString()}] Read findings from disk (${content.length} chars)`);
                return { output: content, source: 'findings' };
            }
        } catch (err) {
            console.log(`[${new Date().toISOString()}] Could not read findings file: ${err.message}`);
        }
    }

    console.log(`[${new Date().toISOString()}] No findings, requesting report from agent`);
    const retryFindings = await requestFindings(workDir, autoApprove);
    if (retryFindings) {
        return { output: retryFindings, source: 'findings' };
    }

    return { output: stdoutFallback(effectiveOutput), source: 'stdout' };
}

async function requestFindings(workDir, autoApprove) {
    const prompt = 'You completed your task but did not write a completion report. '
        + 'Write a brief summary of what you did to ./results/findings.md now. '
        + 'Include: files changed, what was implemented or verified, and the outcome.';
    const { binary, args } = buildCLICommand(prompt, { autoApprove });
    return new Promise((resolve) => {
        const timeout = setTimeout(() => resolve(null), 60000);
        const child = spawn(binary, args, {
            env: { ...process.env, ...(AGENT_CLI === 'gemini' ? { GOOGLE_GENAI_USE_VERTEXAI: 'true' } : {}) },
            cwd: workDir,
            timeout: 60000,
            stdio: ['ignore', 'pipe', 'pipe'],
        });
        child.on('close', () => {
            clearTimeout(timeout);
            const findingsPath = `${workDir}/results/findings.md`;
            try {
                if (fs.existsSync(findingsPath)) {
                    const content = fs.readFileSync(findingsPath, 'utf8').trim();
                    fs.unlinkSync(findingsPath);
                    if (content.length > 0) { resolve(content); return; }
                }
            } catch (e) {
                console.log(`[${new Date().toISOString()}] Retry findings read failed: ${e.message}`);
            }
            resolve(null);
        });
        child.on('error', (err) => {
            console.log(`[${new Date().toISOString()}] Retry spawn error: ${err.message}`);
            clearTimeout(timeout);
            resolve(null);
        });
    });
}

function prepareResultsDir(workDir) {
    const resultsDir = `${workDir}/results`;
    try {
        if (fs.existsSync(resultsDir)) {
            const files = fs.readdirSync(resultsDir);
            for (const f of files) {
                fs.unlinkSync(`${resultsDir}/${f}`);
            }
        } else {
            fs.mkdirSync(resultsDir, { recursive: true });
        }
    } catch (err) {
        console.log(`[${new Date().toISOString()}] Results dir prep warning: ${err.message}`);
    }
}

// --- fs.watch helper (shared by both execution paths) ---
function watchResultsDir(workDir) {
    const resultsDir = `${workDir}/results`;
    const findingsPath = `${resultsDir}/findings.md`;
    let cachedFindings = null;
    let watcher = null;
    try {
        watcher = fs.watch(resultsDir, (eventType, filename) => {
            if (filename === 'findings.md' && (eventType === 'rename' || eventType === 'change')) {
                try {
                    if (fs.existsSync(findingsPath)) {
                        const raw = fs.readFileSync(findingsPath, 'utf8').trim();
                        cachedFindings = { content: raw, timestamp: Date.now() };
                        console.log(`[${new Date().toISOString()}] Preemptive read: findings.md (${raw.length} chars)`);
                    }
                } catch (err) {
                    console.log(`[${new Date().toISOString()}] Preemptive read failed: ${err.message}`);
                }
            }
        });
    } catch (err) {
        console.log(`[${new Date().toISOString()}] fs.watch setup failed: ${err.message}`);
    }
    return {
        get cachedFindings() { return cachedFindings; },
        findingsPath,
        close() { if (watcher) { try { watcher.close(); } catch(e) {} } },
    };
}

async function executeCLI(prompt, options = {}) {
    return new Promise((resolve, reject) => {
        const { binary, args } = buildCLICommand(prompt, { autoApprove: options.autoApprove });

        console.log(`[${new Date().toISOString()}] Executing: ${AGENT_CLI} (prompt length: ${prompt.length})`);

        const workDir = options.cwd || DEFAULT_WORK_DIR;
        prepareResultsDir(workDir);
        const watch = watchResultsDir(workDir);

        const child = spawn(binary, args, {
            env: {
                ...process.env,
                ...(AGENT_CLI === 'gemini' ? { GOOGLE_GENAI_USE_VERTEXAI: 'true' } : {}),
            },
            cwd: workDir,
            timeout: TIMEOUT_MS,
            stdio: ['ignore', 'pipe', 'pipe'],
        });

        let stdout = '';
        let stderr = '';
        let streamTextAccum = '';

        child.stdout.on('data', (data) => {
            const text = data.toString();
            stdout += text;
            for (const line of text.split('\n')) {
                if (!line.trim()) continue;
                const parsed = parseStreamLine(line);
                if (parsed?.text) streamTextAccum += parsed.text;
                const task = state.getCurrentTask();
                if (parsed?.sessionId && task) task.sessionId = parsed.sessionId;
            }
        });

        child.stderr.on('data', (data) => { stderr += data.toString(); });

        child.on('close', (code) => {
            watch.close();
            const effectiveOutput = streamTextAccum || stdout;

            console.log(`[${new Date().toISOString()}] ${AGENT_CLI} exited with code ${code}`);
            console.log(`[${new Date().toISOString()}] stdout (${effectiveOutput.length} chars): ${effectiveOutput}`);
            if (stderr) {
                console.log(`[${new Date().toISOString()}] stderr: ${stderr}`);
            }

            if (code === 0) {
                try {
                    const result = JSON.parse(effectiveOutput);
                    resolve({ status: 'success', exitCode: code, output: result, source: 'stdout' });
                    return;
                } catch (e) {}

                const capturedCallback = state.getCallbackResult();
                state.resetCallbackResult();
                resolveResult({
                    callbackResult: capturedCallback,
                    cachedFindings: watch.cachedFindings,
                    findingsPath: watch.findingsPath,
                    workDir,
                    autoApprove: options.autoApprove !== false,
                    effectiveOutput,
                }).then(({ output, source }) => {
                    resolve({ status: 'success', exitCode: code, output, source });
                }).catch((err) => {
                    console.error(`[${new Date().toISOString()}] resolveResult error: ${err.message}`);
                    resolve({ status: 'success', exitCode: code, output: stdoutFallback(effectiveOutput), source: 'stdout' });
                });
            } else {
                resolve({ status: 'failed', exitCode: code, stderr, stdout: effectiveOutput, source: 'stdout' });
            }
        });

        child.on('error', (err) => {
            console.error(`[${new Date().toISOString()}] Spawn error:`, err.message);
            reject(err);
        });
    });
}

async function executeCLIStreaming(ws, eventId, prompt, options = {}) {
    return new Promise((resolve, reject) => {
        const { binary, args } = buildCLICommand(prompt, {
            autoApprove: options.autoApprove,
            sessionId: options.sessionId,
        });

        console.log(`[${new Date().toISOString()}] Streaming exec: ${AGENT_CLI} (prompt: ${prompt.length} chars)`);

        const workDir = options.cwd || DEFAULT_WORK_DIR;
        prepareResultsDir(workDir);
        const watch = watchResultsDir(workDir);

        const child = spawn(binary, args, {
            env: {
                ...process.env,
                ...(AGENT_CLI === 'gemini' ? { GOOGLE_GENAI_USE_VERTEXAI: 'true' } : {}),
            },
            cwd: workDir,
            timeout: TIMEOUT_MS,
            stdio: ['ignore', 'pipe', 'pipe'],
        });

        const existing = state.getCurrentTask();
        if (existing) {
            existing.child = child;
            existing.eventId = eventId;
        } else {
            state.setCurrentTask({ eventId, child });
        }

        let stdout = '';
        let stderr = '';
        let lineBuffer = '';
        let streamTextAccum = '';

        child.stdout.on('data', (data) => {
            const text = data.toString();
            stdout += text;
            lineBuffer += text;

            const lines = lineBuffer.split('\n');
            lineBuffer = lines.pop();
            for (const line of lines) {
                if (!line.trim()) continue;
                const parsed = parseStreamLine(line);
                if (!parsed) continue;
                const task = state.getCurrentTask();
                if (parsed.sessionId && task) {
                    task.sessionId = parsed.sessionId;
                    console.log(`[${new Date().toISOString()}] [${eventId}] Session: ${parsed.sessionId}`);
                }
                if (parsed.text) {
                    streamTextAccum += parsed.text;
                    console.log(`[${new Date().toISOString()}] [${eventId}] >> ${parsed.text}`);
                    wsSend(ws, { type: 'progress', event_id: eventId, message: parsed.text });
                }
            }
        });

        child.stderr.on('data', (data) => { stderr += data.toString(); });

        child.on('close', (code) => {
            watch.close();
            const capturedSessionId = state.getCurrentTask()?.sessionId || null;

            if (lineBuffer.trim()) {
                const parsed = parseStreamLine(lineBuffer);
                if (parsed?.text) {
                    streamTextAccum += parsed.text;
                    wsSend(ws, { type: 'progress', event_id: eventId, message: parsed.text });
                }
            }

            const effectiveOutput = streamTextAccum || stdout;

            console.log(`[${new Date().toISOString()}] ${AGENT_CLI} exited code ${code} (${effectiveOutput.length} chars)`);
            if (effectiveOutput.length > 0) {
                console.log(`[${new Date().toISOString()}] ${AGENT_CLI} stdout: ${effectiveOutput}`);
            } else {
                console.log(`[${new Date().toISOString()}] WARNING: ${AGENT_CLI} produced EMPTY stdout`);
            }
            if (stderr) {
                console.log(`[${new Date().toISOString()}] ${AGENT_CLI} stderr: ${stderr}`);
            }

            if (code === 0) {
                try {
                    const result = JSON.parse(effectiveOutput);
                    resolve({ status: 'success', sessionId: capturedSessionId, output: result, source: 'stdout' });
                    return;
                } catch (e) {}

                const capturedCallback = state.getCallbackResult();
                state.resetCallbackResult();
                resolveResult({
                    callbackResult: capturedCallback,
                    cachedFindings: watch.cachedFindings,
                    findingsPath: watch.findingsPath,
                    workDir,
                    autoApprove: options.autoApprove !== false,
                    effectiveOutput,
                }).then(({ output, source }) => {
                    resolve({ status: 'success', sessionId: capturedSessionId, output, source });
                }).catch((err) => {
                    console.error(`[${new Date().toISOString()}] resolveResult error: ${err.message}`);
                    resolve({ status: 'success', sessionId: capturedSessionId, output: stdoutFallback(effectiveOutput), source: 'stdout' });
                });
            } else {
                resolve({ status: 'failed', sessionId: capturedSessionId, exitCode: code, stderr, stdout: effectiveOutput, source: 'stdout' });
            }
        });

        child.on('error', (err) => {
            console.error(`[${new Date().toISOString()}] Spawn error:`, err.message);
            reject(err);
        });
    });
}

module.exports = {
    buildCLICommand,
    executeCLI,
    executeCLIStreaming,
    resolveResult,
    readFindings,
    stdoutFallback,
    requestFindings,
    prepareResultsDir,
};
