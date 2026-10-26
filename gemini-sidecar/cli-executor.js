// gemini-sidecar/cli-executor.js
// @ai-rules:
// 1. [Pattern]: All shared state (_callbackResult, currentTask) accessed via state.js getters/setters -- NEVER direct variables.
// 2. [Pattern]: resolveResult() is the single result resolution function for BOTH executeCLI and executeCLIStreaming.
//    Priority: callback -> cachedFindings (fs.watch) -> disk findings -> retry prompt -> stdout tail.
// 3. [Pattern]: No agent should ever run in plan mode in autonomous sidecars. All agents execute with --dangerously-skip-permissions (when autoApprove !== false).
// 4. [Pattern]: AGENT_EFFORT_LEVEL -> --effort flag on Claude CLI and Antigravity CLI.
// 5. [Pattern]: Claude --mcp-config resolved lazily (fs.existsSync at call time) so it picks up ~/.claude.json even when created after module load.
// 6. [Gotcha]: requestFindings spawns a second CLI process -- keep timeout low (60s) and never reject.
// 7. [Gotcha]: fs.watch cachedFindings is captured by closure in spawn callbacks -- not in state.js.
// 8. [Pattern]: is400SessionError detects Claude thinking-block corruption on --resume. executeCLIStreaming retries once without session (_retryWithoutSession flag prevents loops).
// 9. [Pattern]: options.model/effort/role override env (AGENT_MODEL/AGENT_EFFORT_LEVEL/AGENT_ROLE) at the per-task level.
//    Stored on state.getCurrentTask() (model/role) so resolveResult -> requestFindings can read them without threading
//    extra params through the whole call chain -- mirrors the existing sessionId bridging pattern.
// 10. [Pattern]: ROLE_SETTINGS_FILE maps a role to a --settings JSON path (native Claude Code permissions.deny).
//     Read-only roles explorer/architect/security_analyst share readonly-role-permissions.json, and any other
//     read-only-looking role name falls back to it via settingsFileForRole. CLAUDE_SETTINGS_DIR overrides
//     /app/claude-settings (tests). Engine-enforced, independent of validate-reviewer-bash.sh -- add an entry
//     here (not a hardcoded role check) when a future role needs its own permission boundary.
// 11. [Pattern]: executeCLI and executeCLIStreaming share getRetryOptions() for the agy session retry and the
//     invalid-model fallback -- change the triggers THERE, never inline. Both are one-shot (flag-bounded), agy-only /
//     model-line-only, and match stderr only (stdout is model text and can mention these phrases).
// 12. [Gotcha]: agy uses ~/.gemini/config/hooks.json for PreToolUse (validate-mutations.sh) and Stop (require-results.sh) as defense-in-depth.
//     Claude uses --settings permissions.deny files (ROLE_SETTINGS_FILE) for engine-level read-only enforcement.

const cp = require('child_process');
const spawn = (...args) => cp.spawn(...args);
const fs = require('fs');
const path = require('path');
const os = require('os');
const { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS } = require('./config');
const state = require('./state');
const { parseStreamLine } = require('./stream-parser');
const { wsSend } = require('./ws-utils');
const { READ_ONLY_ROLES, isReadOnlyRoleName, isMutatingRoleName } = require('./roles');
const { setupGoogleAuthForAgy } = require('./credentials');
const { checkAndRecycleStorage } = require('./storage-recycler');

const CLAUDE_JSON_PATH = path.join(os.homedir(), '.claude.json');
function resolveEffectiveRole(role) {
    const raw = role || AGENT_ROLE || '';
    return String(raw).trim().toLowerCase().replace(/[^a-z0-9_-]/g, '');
}

function resolveModel(options, agentCli) {
  const effectiveRole = resolveEffectiveRole(options.role);
  if (options.model) return options.model;
  if (effectiveRole === 'explorer' && process.env.EPHEMERAL_MODEL_EXPLORER) {
    return process.env.EPHEMERAL_MODEL_EXPLORER;
  }
  return AGENT_MODEL || (agentCli === 'claude' ? 'claude-sonnet-5-5' : 'gemini-3.8-flash');
}

// Per-role native permission files (Claude Code engine-enforced deny rules).
// Only roles listed here get --settings; all other roles are unaffected.
const CLAUDE_SETTINGS_DIR = process.env.CLAUDE_SETTINGS_DIR || path.join(__dirname, 'claude-settings');
const READONLY_SETTINGS_FILE = `${CLAUDE_SETTINGS_DIR}/readonly-role-permissions.json`;
const ROLE_SETTINGS_FILE = {
    code_reviewer: `${CLAUDE_SETTINGS_DIR}/code-reviewer-permissions.json`,
    // Read-only roles on the Claude path (the agy path enforces these via validate-mutations.sh).
    // Claude uses engine-enforced deny settings files to block perimeter mutations and credential reads.
    explorer: READONLY_SETTINGS_FILE,
    architect: READONLY_SETTINGS_FILE,
    security_analyst: READONLY_SETTINGS_FILE,
};

// Read-only role detection is shared (roles.js): name heuristics fail closed for unlisted read-only-looking roles.
// Any role that is not an explicitly allowed mutating role gets the read-only deny file (fail closed).
function settingsFileForRole(role) {
    if (ROLE_SETTINGS_FILE[role]) return ROLE_SETTINGS_FILE[role];
    if (!role || !isMutatingRoleName(role) || isReadOnlyRoleName(role)) {
        return READONLY_SETTINGS_FILE;
    }
    return undefined;
}

// Fallback model per CLI for the invalid-model retry (see getRetryOptions).
const FALLBACK_MODEL = {
    claude: 'claude-sonnet-5-5',
    agy: 'gemini-3.8-flash',
};

// Minimum load-bearing deny rules the settings-validity check requires (below) --
// a near-empty-but-shape-valid file would previously pass a bare "non-empty array" check
// while providing almost no real restriction. Checking for a representative sample across
// perimeter categories (git commit, git push, cluster mutations) catches wholesale content
// tampering/corruption without needing to enumerate every rule in the real file.
const REQUIRED_DENY_RULES = ['Bash(git commit *)', 'Bash(git push *)', 'Bash(kubectl apply *)'];

// agy rejects a model name that already carries an effort suffix alongside --effort, so
// peel any trailing "-low|medium|high|xhigh|max" off the model and let it win as the effort.
function splitModelEffortSuffix(model, effort) {
    let m;
    while ((m = model.match(/^(.+)-(low|medium|high|xhigh|max)$/))) {
        model = m[1];
        effort = m[2];
    }
    return { model, effort };
}

function buildCLICommand(prompt, options = {}) {
    const agentCli = options.agentCli || AGENT_CLI;
    if (agentCli !== 'claude' && agentCli !== 'agy') {
        throw new Error(`Unsupported AGENT_CLI: ${agentCli}. Supported runtimes: 'claude', 'agy'`);
    }

    const effectiveRole = resolveEffectiveRole(options.role);

    if (agentCli === 'agy') {
        const args = [];
        const binary = AGY_CLI;

        // No agent runs in plan mode in autonomous sidecars.
        // Safety boundaries are enforced by PreToolUse hook (validate-mutations.sh).
        if (options.autoApprove !== false) {
            args.push('--dangerously-skip-permissions');
        }
        args.push('--output-format', 'stream-json');
        // NOTE: Never pass --input-format stream-json; it conflicts with command-line -p prompt!

        // Model & effort normalization to prevent CLI conflict errors
        let model = resolveModel(options, agentCli);
        let effort = options.effort || AGENT_EFFORT_LEVEL || process.env.AGENT_EFFORT_LEVEL || process.env.AGENT_EFFORT;

        ({ model, effort } = splitModelEffortSuffix(model, effort));
        effort = effort || 'high'; // agy requires explicit --effort for flash/pro models

        if (model) args.push('--model', model);
        if (effort) args.push('--effort', effort);
        if (options.conversationId || options.sessionId) {
            args.push('--conversation', options.conversationId || options.sessionId);
        }

        args.push('-p', prompt);
        return { binary, args };
    }

    if (agentCli === 'claude') {
        const args = [];
        if (fs.existsSync(CLAUDE_JSON_PATH)) {
            args.push('--mcp-config', CLAUDE_JSON_PATH);
        }
        const settingsFile = settingsFileForRole(effectiveRole);
        if (settingsFile) {
            // Fail CLOSED, not a quiet degrade to hook-only enforcement: a role in
            // ROLE_SETTINGS_FILE EXPECTS the engine-enforced permissions.deny layer to
            // exist and be valid. Losing it silently (missing image layer, bad COPY, wrong
            // path, truncated/corrupted file) means this role now runs with a weaker
            // security posture than its own design assumes, with nothing but a log line
            // to notice. Checking existence alone (fs.existsSync) only proves the file is
            // THERE, not that Claude Code can actually parse and apply it -- verify it's
            // valid JSON with the expected shape before trusting it.
            let settingsValid = false;
            try {
                const parsed = JSON.parse(fs.readFileSync(settingsFile, 'utf8'));
                const denyList = parsed && parsed.permissions && parsed.permissions.deny;
                settingsValid = Array.isArray(denyList) && REQUIRED_DENY_RULES.every((rule) => denyList.includes(rule));
            } catch (e) {
                settingsValid = false;
            }
            if (!settingsValid) {
                const msg = `Expected --settings file missing or invalid for role '${effectiveRole}': ${settingsFile} -- refusing to launch without the native permissions.deny layer`;
                console.error(`[${new Date().toISOString()}] CRITICAL: ${msg}`);
                throw new Error(msg);
            }
            args.push('--settings', settingsFile);
        }
        // No agent runs in plan mode in autonomous sidecars.
        // Read-only boundaries are enforced by --settings permissions.deny and hooks.
        if (options.autoApprove !== false) {
            args.push('--dangerously-skip-permissions');
        }
        args.push('--output-format', 'stream-json', '--verbose');
        const model = resolveModel(options, agentCli);
        args.push('--model', model);
        const effort = options.effort || AGENT_EFFORT_LEVEL;
        if (effort) {
            args.push('--effort', effort);
        }
        if (options.sessionId) {
            args.push('--resume', options.sessionId);
        }
        const ultrathinkPrefix = effectiveRole === 'architect' ? 'ultrathink ' : '';
        args.push('-p', ultrathinkPrefix + prompt);
        return { binary: 'claude', args };
    }
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
    const task = state.getCurrentTask();
    const model = task?.model || '';
    const role = task?.role || '';
    const retryFindings = await requestFindings(workDir, autoApprove, model, role);
    if (retryFindings) {
        return { output: retryFindings, source: 'findings' };
    }

    return { output: stdoutFallback(effectiveOutput), source: 'stdout' };
}

async function requestFindings(workDir, autoApprove, model, role) {
    const prompt = 'You completed your task but did not write a completion report. '
        + 'Write a brief summary of what you did to ./results/findings.md now. '
        + 'Include: files changed, what was implemented or verified, and the outcome.';
    // buildCLICommand can now throw (fail-closed on a missing --settings file) -- this
    // function must never reject (ai-rule 6), so catch it here and resolve(null) the
    // same as any other retry failure, rather than let it surface as an unhandled
    // rejection through resolveResult's un-guarded `await requestFindings(...)` call.
    let binary, args;
    try {
        ({ binary, args } = buildCLICommand(prompt, { autoApprove, model, role }));
    } catch (e) {
        console.log(`[${new Date().toISOString()}] Retry findings buildCLICommand failed: ${e.message}`);
        return null;
    }
    return new Promise((resolve) => {
        const timeout = setTimeout(() => resolve(null), 60000);
        const child = spawn(binary, args, {
            env: process.env,
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
    const agentCli = options.agentCli || AGENT_CLI;
    if (agentCli === 'agy') {
        try {
            await setupGoogleAuthForAgy();
        } catch (err) {
            console.error(`[${new Date().toISOString()}] setupGoogleAuthForAgy failed before executeCLI: ${err.message}`);
        }
    }

    const storageRoot = process.env.DEFAULT_WORK_DIR || DEFAULT_WORK_DIR || '/data/gitops';
    try {
        await checkAndRecycleStorage(storageRoot, options.cwd);
    } catch (err) {
        console.warn(`[${new Date().toISOString()}] Storage check failed before executeCLI: ${err.message}`);
    }

    // buildCLICommand can throw (fail-closed on a missing/invalid --settings file --
    // see ROLE_SETTINGS_FILE above). No try/catch needed HERE: a synchronous throw
    // inside a `new Promise((resolve, reject) => {...})` executor is caught by the
    // Promise constructor itself per the ECMAScript spec and auto-rejects -- this is
    // guaranteed language behavior, not an assumption. Every real caller of
    // executeCLI (http-handler.js's /execute handler) already awaits it inside its
    // own try/catch, so a throw here degrades to a clean error response, never an
    // unhandled rejection. (Raised repeatedly in AI review across multiple rounds --
    // documenting the reasoning here rather than adding a redundant try/catch.)
    return new Promise((resolve, reject) => {
        const { binary, args } = buildCLICommand(prompt, {
            autoApprove: options.autoApprove,
            model: options.model,
            effort: options.effort,
            role: options.role,
            sessionId: options.sessionId,
            conversationId: options.conversationId,
        });

        console.log(`[${new Date().toISOString()}] Executing: ${AGENT_CLI} (prompt length: ${prompt.length})`);

        const workDir = options.cwd || DEFAULT_WORK_DIR;
        prepareResultsDir(workDir);
        const watch = watchResultsDir(workDir);

        const child = spawn(binary, args, {
            env: process.env,
            cwd: workDir,
            timeout: resolveTimeoutMs(options.role || AGENT_ROLE),
            stdio: ['ignore', 'pipe', 'pipe'],
        });

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
                if (parsed?.text) streamTextAccum += parsed.text;
                const task = state.getCurrentTask();
                if (parsed?.sessionId && task) task.sessionId = parsed.sessionId;
            }
        });

        child.stderr.on('data', (data) => { stderr += data.toString(); });

        child.on('close', (code, signal) => {
            watch.close();

            if (lineBuffer.trim()) {
                const parsed = parseStreamLine(lineBuffer);
                if (parsed?.text) streamTextAccum += parsed.text;
                const task = state.getCurrentTask();
                if (parsed?.sessionId && task) task.sessionId = parsed.sessionId;
            }

            const effectiveOutput = streamTextAccum || stdout;

            console.log(`[${new Date().toISOString()}] ${AGENT_CLI} exited with code ${code}`);
            console.log(`[${new Date().toISOString()}] stdout (${effectiveOutput.length} chars): ${effectiveOutput}`);
            if (stderr) {
                console.log(`[${new Date().toISOString()}] stderr: ${stderr}`);
            }

            const usedModel = resolveModel(options, AGENT_CLI);

            if (code === 0) {
                try {
                    const result = JSON.parse(effectiveOutput);
                    resolve({ status: 'success', exitCode: code, output: result, source: 'stdout', usedModel });
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
                    resolve({ status: 'success', exitCode: code, output, source, usedModel });
                }).catch((err) => {
                    console.error(`[${new Date().toISOString()}] resolveResult error: ${err.message}`);
                    resolve({ status: 'success', exitCode: code, output: stdoutFallback(effectiveOutput), source: 'stdout', usedModel });
                });
            } else {
                if (code === null && signal) {
                    console.warn(`[${new Date().toISOString()}] CLI process exited via signal ${signal} (possible timeout or SIGKILL)`);
                }
                const retry = getRetryOptions(options, code, stderr);
                if (retry) {
                    console.log(`[${new Date().toISOString()}] ${retry.reason}`);
                    executeCLI(prompt, retry.options).then(resolve).catch(reject);
                    return;
                }
                resolve({ status: 'failed', exitCode: code, stderr, stdout: effectiveOutput, source: 'stdout', usedModel });
            }
        });

        child.on('error', (err) => {
            console.error(`[${new Date().toISOString()}] Spawn error:`, err.message);
            reject(err);
        });
    });
}

async function executeCLIStreaming(ws, eventId, prompt, options = {}) {
    const agentCli = options.agentCli || AGENT_CLI;
    if (agentCli === 'agy') {
        try {
            await setupGoogleAuthForAgy();
        } catch (err) {
            console.error(`[${new Date().toISOString()}] setupGoogleAuthForAgy failed before executeCLIStreaming: ${err.message}`);
        }
    }

    const storageRoot = process.env.DEFAULT_WORK_DIR || DEFAULT_WORK_DIR || '/data/gitops';
    try {
        await checkAndRecycleStorage(storageRoot, options.cwd);
    } catch (err) {
        console.warn(`[${new Date().toISOString()}] Storage check failed before executeCLIStreaming: ${err.message}`);
    }

    // Same guarantee as executeCLI above: a buildCLICommand throw auto-rejects this
    // Promise via the executor-throw-to-reject spec behavior. Every real caller
    // (ws-server.js task/followup handlers, ws-client.js reconnect path) already
    // awaits this inside its own try/catch, converting a throw into a clean WS error
    // message -- never an unhandled rejection.
    return new Promise((resolve, reject) => {
        const { binary, args } = buildCLICommand(prompt, {
            autoApprove: options.autoApprove,
            sessionId: options.sessionId,
            conversationId: options.conversationId,
            model: options.model,
            effort: options.effort,
            role: options.role,
        });

        console.log(`[${new Date().toISOString()}] Streaming exec: ${AGENT_CLI} (prompt: ${prompt.length} chars)`);

        const workDir = options.cwd || DEFAULT_WORK_DIR;
        prepareResultsDir(workDir);
        const watch = watchResultsDir(workDir);

        const child = spawn(binary, args, {
            env: process.env,
            cwd: workDir,
            timeout: resolveTimeoutMs(options.role || AGENT_ROLE),
            stdio: ['ignore', 'pipe', 'pipe'],
        });

        // Only mutate the existing task object in place when it's the SAME logical call
        // (e.g. the is400SessionError retry-without-session recursion below, which shares
        // eventId with its parent invocation). Anything else finding a task already parked
        // here means a busy-guard was missed upstream (ws-server.js/ws-client.js) and two
        // calls genuinely overlapped -- clobbering that task's tracking in place would
        // silently corrupt its sessionId/cancel/kill bookkeeping. Replace it with a fresh
        // object instead, and log loudly so the missed guard is visible rather than a
        // silent cross-contamination.
        const existing = state.getCurrentTask();
        if (existing && existing.eventId === eventId) {
            existing.child = child;
            existing.model = options.model || '';
            existing.role = options.role || '';
            existing.sessionId = options.sessionId || options.conversationId || null;
        } else {
            if (existing) {
                console.error(`[${new Date().toISOString()}] WARNING: replacing in-flight task state for event ${existing.eventId} with unrelated task ${eventId} -- an upstream busy-guard was missed`);
            }
            state.setCurrentTask({ eventId, child, model: options.model || '', role: options.role || '', sessionId: options.sessionId || options.conversationId || null });
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

        child.on('close', (code, signal) => {
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
                if (code === null && signal) {
                    console.warn(`[${new Date().toISOString()}] [${eventId}] CLI process exited via signal ${signal} (possible timeout or SIGKILL)`);
                }
                if (options.sessionId && !options._retryWithoutSession && is400SessionError(effectiveOutput, stderr)) {
                    console.log(`[${new Date().toISOString()}] [${eventId}] 400 session error detected, retrying without --resume`);
                    executeCLIStreaming(ws, eventId, prompt, {
                        ...options,
                        sessionId: null,
                        conversationId: null,
                        _retryWithoutSession: true,
                    }).then(resolve).catch(reject);
                    return;
                }
                const retry = getRetryOptions(options, code, stderr);
                if (retry) {
                    console.log(`[${new Date().toISOString()}] [${eventId}] ${retry.reason}`);
                    executeCLIStreaming(ws, eventId, prompt, retry.options).then(resolve).catch(reject);
                    return;
                }
                resolve({ status: 'failed', sessionId: capturedSessionId, exitCode: code, stderr, stdout: effectiveOutput, source: 'stdout', usedModel: resolveModel(options, AGENT_CLI) });
            }
        });

        child.on('error', (err) => {
            console.error(`[${new Date().toISOString()}] Spawn error:`, err.message);
            reject(err);
        });
    });
}

function is429Error(stderr) {
    if (!stderr) return false;
    const lower = stderr.toLowerCase();
    return lower.includes('429') || lower.includes('resource_exhausted') || lower.includes('rate limit');
}

function is400SessionError(output, stderr) {
    const combined = ((output || '') + (stderr || '')).toLowerCase();
    if (combined.includes('no conversation found')) return true;
    return combined.includes('400') && (
        combined.includes('thinking') ||
        combined.includes('redacted_thinking') ||
        combined.includes('text content blocks must be non-empty') ||
        combined.includes('invalid_request_error')
    );
}

// agy only, stderr only: stdout carries the model's own text, so matching it would re-run
// (and repeat any mutating tool calls of) a task that merely *talked about* a missing
// conversation. Matches per-line to avoid spurious retries when unrelated lines combine.
// `agentCli` is a parameter so the predicate stays testable.
function isAgySessionError(exitCode, stderr, agentCli = AGENT_CLI) {
    if (agentCli !== 'agy') return false;
    return (stderr || '').toLowerCase().split('\n').some((line) =>
        line.includes('conversation') && (line.includes('not found') || line.includes('corrupt') || line.includes('invalid')));
}

// A model-selection failure names the model on the same stderr line as the error marker.
// Bare `invalid_argument` also covers bad --effort flags, MCP errors and oversized context,
// none of which a model swap can fix -- so require the line to mention the model.
function isInvalidModelError(stderr) {
    return (stderr || '').toLowerCase().split('\n').some((line) =>
        line.includes('model') && (line.includes('not found') || line.includes('invalid_argument') || line.includes('invalid model')));
}

// Shared by executeCLI and executeCLIStreaming: decide whether a failed run gets ONE retry
// and with which options. Returns { reason, options } or null. Both retries re-run the whole
// prompt, so each is bounded by its own flag and gated as narrowly as the evidence allows.
function getRetryOptions(options, exitCode, stderr, agentCli = AGENT_CLI) {
    const retryCount = options._retryCount || 0;
    if (retryCount >= 1) return null;

    if ((options.conversationId || options.sessionId) && !options._retryWithoutSession && isAgySessionError(exitCode, stderr, agentCli)) {
        return {
            reason: 'agy session error detected, retrying without --conversation',
            options: { ...options, conversationId: null, sessionId: null, _retryWithoutSession: true, _retryCount: retryCount + 1 },
        };
    }
    if (!options._retriedModel && isInvalidModelError(stderr)) {
        const effectiveRole = String(options.role || AGENT_ROLE || '').trim().toLowerCase();
        // Explorer falls back to flash on Gemini/Agy, or claude default on Claude CLI
        const fallbackModel = (effectiveRole === 'explorer' && agentCli !== 'claude')
            ? 'gemini-3.8-flash'
            : FALLBACK_MODEL[agentCli];
        // Retrying the model that just failed (e.g. claude already on the default) is pointless.
        if (fallbackModel && fallbackModel !== resolveModel(options, agentCli)) {
            return {
                reason: `Invalid model error, retrying with ${fallbackModel}`,
                options: { ...options, model: fallbackModel, _retriedModel: true, _retryCount: retryCount + 1 },
            };
        }
    }
    return null;
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
    is429Error,
    is400SessionError,
    isAgySessionError,
    isInvalidModelError,
    getRetryOptions,
    resolveModel,
};
