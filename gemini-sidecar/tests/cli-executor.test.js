// gemini-sidecar/tests/cli-executor.test.js
// @ai-rules:
// 1. [Constraint]: AGENT_CLI is read at config.js load time -- every test loads cli-executor via freshExecutor()
//    with the env it needs and restores env in `finally`. Never rely on the ambient AGENT_CLI.
// 2. [Constraint]: freshExecutor sandboxes HOME -- tests must not write ~/.gemini or ~/.claude.json of the real user.
// 3. [Gotcha]: a code-0 run whose stdout is not JSON triggers resolveResult -> requestFindings (an EXTRA spawn). Mocked
//    successes therefore emit JSON so spawn-call counts reflect only the retry logic under test.
// 4. [Pattern]: spawn is mocked through node:child_process (cli-executor wraps cp.spawn lazily for this).
const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const cp = require('node:child_process');
const EventEmitter = require('node:events');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const CONFIG_PATH = path.resolve(__dirname, '..', 'config.js');
const EXECUTOR_PATH = path.resolve(__dirname, '..', 'cli-executor.js');

/**
 * Load cli-executor with the given env; returns { mod, restore }.
 * HOME is pointed at a throwaway dir: the gemini path persists thinking config to
 * ~/.gemini/settings.json (path fixed at module load), which must never hit the real home.
 */
function freshExecutor(env = {}) {
    const fakeHome = fs.mkdtempSync(path.join(os.tmpdir(), 'cli-exec-home-'));
    env = { HOME: fakeHome, ...env };
    fs.mkdirSync(path.join(fakeHome, '.gemini'), { recursive: true });
    const saved = {};
    for (const [k, v] of Object.entries(env)) {
        saved[k] = process.env[k];
        if (v === undefined) delete process.env[k]; else process.env[k] = v;
    }
    delete require.cache[require.resolve(CONFIG_PATH)];
    delete require.cache[require.resolve(EXECUTOR_PATH)];
    let mod;
    const restore = () => {
        for (const [k, v] of Object.entries(saved)) {
            if (v === undefined) delete process.env[k]; else process.env[k] = v;
        }
        delete require.cache[require.resolve(CONFIG_PATH)];
        delete require.cache[require.resolve(EXECUTOR_PATH)];
        fs.rmSync(fakeHome, { recursive: true, force: true });
    };
    try {
        mod = require(EXECUTOR_PATH);
    } catch (err) {
        // config.js fails fast on an unsupported AGENT_CLI -- never leak the env/cache into later tests
        restore();
        throw err;
    }
    return { mod, restore };
}

/** Mock cp.spawn; `script(args, callIndex)` returns { code, stdout, stderr }. Returns the recorded arg lists. */
function mockSpawn(t, script) {
    const calls = [];
    t.mock.method(cp, 'spawn', (cmd, args) => {
        const idx = calls.length;
        calls.push(args);
        const { code = 0, signal, stdout = '', stderr = '' } = script(args, idx);
        const child = new EventEmitter();
        child.stdout = new EventEmitter();
        child.stderr = new EventEmitter();
        setTimeout(() => {
            if (stdout) child.stdout.emit('data', Buffer.from(stdout));
            if (stderr) child.stderr.emit('data', Buffer.from(stderr));
            child.emit('close', code, signal);
        }, 5);
        return child;
    });
    return calls;
}

const modelOf = (args) => args[args.indexOf('--model') + 1];

describe('CLI Executor', () => {
    it('T-14: resolves Explorer model from EPHEMERAL_MODEL_EXPLORER', () => {
        const { mod, restore } = freshExecutor({ AGENT_CLI: 'agy', EPHEMERAL_MODEL_EXPLORER: 'gemini-test-model' });
        try {
            const { args } = mod.buildCLICommand('prompt', { role: 'explorer' });
            assert.equal(modelOf(args), 'gemini-test-model');
        } finally {
            restore();
        }
    });
});

describe('invalid-model fallback (shared getRetryOptions)', () => {
    it('T-17: agy falls back to gemini-3.8-flash exactly once', async (t) => {
        const { mod, restore } = freshExecutor({ AGENT_CLI: 'agy', EPHEMERAL_MODEL_EXPLORER: 'invalid-model-that-fails' });
        try {
            const calls = mockSpawn(t, (args) => args.includes('invalid-model-that-fails')
                ? { code: 1, stderr: 'INVALID_ARGUMENT: model not found' }
                : { code: 0, stdout: '{"ok":true}' });
            const result = await mod.executeCLI('test', { role: 'explorer' });
            assert.equal(result.usedModel, 'gemini-3.8-flash');
            assert.equal(calls.length, 2);
        } finally {
            restore();
        }
    });

    it('is one-shot: a fallback that also fails is returned as failed, not retried again', async (t) => {
        const { mod, restore } = freshExecutor({ AGENT_CLI: 'agy', AGENT_MODEL: 'gemini-x' });
        try {
            const calls = mockSpawn(t, () => ({ code: 1, stderr: 'model not found' }));
            const result = await mod.executeCLI('test', {});
            assert.equal(result.status, 'failed');
            assert.equal(calls.length, 2);
        } finally {
            restore();
        }
    });

    it('does not retry when the fallback model is the model that just failed (claude on default)', async (t) => {
        const { mod, restore } = freshExecutor({ AGENT_CLI: 'claude', AGENT_MODEL: undefined, GEMINI_MODEL: undefined });
        try {
            const calls = mockSpawn(t, () => ({ code: 1, stderr: 'model not found' }));
            const result = await mod.executeCLI('test', {});
            assert.equal(result.status, 'failed');
            assert.equal(calls.length, 1, 'retrying claude-sonnet-5-5 with claude-sonnet-5-5 is pointless');
        } finally {
            restore();
        }
    });

    it('does not retry a bare INVALID_ARGUMENT that does not name the model (bad flag, MCP, context size)', async (t) => {
        const { mod, restore } = freshExecutor({ AGENT_CLI: 'agy', AGENT_MODEL: 'gemini-x' });
        try {
            const calls = mockSpawn(t, () => ({ code: 1, stderr: 'INVALID_ARGUMENT: effort level unsupported\nrequest too large' }));
            const result = await mod.executeCLI('test', {});
            assert.equal(result.status, 'failed');
            assert.equal(calls.length, 1);
        } finally {
            restore();
        }
    });

    it('executeCLIStreaming uses the same fallback logic', async (t) => {
        const { mod, restore } = freshExecutor({ AGENT_CLI: 'agy', AGENT_MODEL: 'gemini-bad' });
        try {
            const calls = mockSpawn(t, (args) => modelOf(args) === 'gemini-bad'
                ? { code: 1, stderr: 'model gemini-bad not found' }
                : { code: 0, stdout: '{"ok":true}' });
            const ws = { readyState: 1, send() {} };
            const result = await mod.executeCLIStreaming(ws, 'evt-1', 'test', {});
            assert.equal(result.status, 'success');
            assert.deepEqual(calls.map(modelOf), ['gemini-bad', 'gemini-3.8-flash']);
        } finally {
            restore();
        }
    });
});

describe('agy session retry (shared getRetryOptions)', () => {
    it('isAgySessionError: agy + stderr only', () => {
        const { mod, restore } = freshExecutor({ AGENT_CLI: 'agy' });
        try {
            assert.equal(mod.isAgySessionError(1, 'Warning: conversation not found'), true);
            assert.equal(mod.isAgySessionError(1, 'Conversation corrupt'), true);
            assert.equal(mod.isAgySessionError(1, 'conversation invalid'), true);
            assert.equal(mod.isAgySessionError(1, 'Rate limit 429 exceeded'), false);
            assert.equal(mod.isAgySessionError(1, 'conversation\nsome unrelated error not found'), false);
            assert.equal(mod.isAgySessionError(1, ''), false);
            // explicit CLI argument overrides the ambient one (predicate stays unit-testable)
            assert.equal(mod.isAgySessionError(1, 'conversation not found', 'claude'), false);
        } finally {
            restore();
        }
    });

    it('isAgySessionError is false for claude even on matching stderr', () => {
        for (const cli of ['claude']) {
            const { mod, restore } = freshExecutor({ AGENT_CLI: cli });
            try {
                assert.equal(mod.isAgySessionError(1, 'conversation not found'), false, cli);
            } finally {
                restore();
            }
        }
    });

    it('agy: stderr session error retries once without --conversation', async (t) => {
        const { mod, restore } = freshExecutor({ AGENT_CLI: 'agy', AGENT_MODEL: undefined });
        try {
            const calls = mockSpawn(t, (args) => args.includes('--conversation')
                ? { code: 1, stderr: 'error: conversation not found' }
                : { code: 0, stdout: '{"ok":true}' });
            const result = await mod.executeCLI('test', { conversationId: 'conv-1' });
            assert.equal(result.status, 'success');
            assert.equal(calls.length, 2);
            assert.equal(calls[0].includes('--conversation'), true);
            assert.equal(calls[1].includes('--conversation'), false);
        } finally {
            restore();
        }
    });

    it('agy: model text on stdout mentioning a missing conversation does NOT trigger a re-run', async (t) => {
        const { mod, restore } = freshExecutor({ AGENT_CLI: 'agy', AGENT_MODEL: undefined });
        try {
            const calls = mockSpawn(t, () => ({ code: 1, stdout: 'The conversation was not found in the tracker', stderr: 'tool crashed' }));
            const result = await mod.executeCLI('test', { conversationId: 'conv-1' });
            assert.equal(result.status, 'failed');
            assert.equal(calls.length, 1, 'a re-run could repeat mutating tool calls');
        } finally {
            restore();
        }
    });

    it('claude: stderr matching the agy phrases does NOT trigger the agy retry', async (t) => {
        const { mod, restore } = freshExecutor({ AGENT_CLI: 'claude', AGENT_MODEL: 'claude-sonnet-x' });
        try {
            const calls = mockSpawn(t, () => ({ code: 1, stderr: 'conversation not found' }));
            const result = await mod.executeCLI('test', { sessionId: 'sess-1' });
            assert.equal(result.status, 'failed');
            assert.equal(calls.length, 1);
        } finally {
            restore();
        }
    });
});

describe('claude read-only roles (engine-enforced permissions.deny, not plan mode)', () => {
    const SETTINGS_DIR = path.resolve(__dirname, '..', 'claude-settings');
    for (const role of ['explorer', 'architect', 'security_analyst', 'code_reviewer', 'qa_reviewer_agent', 'ARCHITECT_LEAD', 'security-analyst']) {
        it(`${role}: gets a --settings deny file and runs with --dangerously-skip-permissions (no plan mode)`, () => {
            const { mod, restore } = freshExecutor({ AGENT_CLI: 'claude', AGENT_PERMISSION_MODE: undefined, CLAUDE_SETTINGS_DIR: SETTINGS_DIR });
            try {
                const { args } = mod.buildCLICommand('p', { role, autoApprove: true });
                const file = args[args.indexOf('--settings') + 1];
                assert.ok(file && file.startsWith(SETTINGS_DIR), `expected --settings under ${SETTINGS_DIR}, got ${file}`);
                const deny = JSON.parse(fs.readFileSync(file, 'utf8')).permissions.deny;
                for (const rule of ['Edit', 'Write', 'Bash(git push *)', 'Bash(git commit *)', 'Bash(rm *)']) assert.ok(deny.includes(rule), rule);
                assert.equal(args.includes('--dangerously-skip-permissions'), true);
                assert.equal(args.includes('--permission-mode'), false);
            } finally {
                restore();
            }
        });
    }
    it('mutating roles (developer, sysadmin, qe) get no --settings file', () => {
        const { mod, restore } = freshExecutor({ AGENT_CLI: 'claude', AGENT_PERMISSION_MODE: undefined, CLAUDE_SETTINGS_DIR: SETTINGS_DIR });
        try {
            for (const role of ['developer', 'sysadmin', 'qe']) {
                assert.equal(mod.buildCLICommand('p', { role, autoApprove: true }).args.includes('--settings'), false, role);
            }
        } finally {
            restore();
        }
    });
    it('fails closed when the read-only settings file is missing', () => {
        const { mod, restore } = freshExecutor({ AGENT_CLI: 'claude', AGENT_PERMISSION_MODE: undefined, CLAUDE_SETTINGS_DIR: '/nonexistent-dir' });
        try {
            assert.throws(() => mod.buildCLICommand('p', { role: 'explorer', autoApprove: true }), /refusing to launch/);
        } finally {
            restore();
        }
    });
});

describe('autonomous sidecar permissions: no agent should ever be in plan mode', () => {
    for (const role of ['architect', 'explorer', 'code_reviewer', 'reviewer', 'security_analyst', 'developer', 'sysadmin']) {
        it(`${role} (agy): runs with --dangerously-skip-permissions and never --mode plan when autoApprove is true`, () => {
            const { mod, restore } = freshExecutor({ AGENT_CLI: 'agy', AGENT_PERMISSION_MODE: undefined });
            try {
                const { args } = mod.buildCLICommand('p', { role, autoApprove: true });
                assert.equal(args.includes('--dangerously-skip-permissions'), true);
                assert.equal(args.includes('--mode'), false);
            } finally {
                restore();
            }
        });

        it(`${role} (claude): runs with --dangerously-skip-permissions and never --permission-mode plan when autoApprove is true`, () => {
            const { mod, restore } = freshExecutor({ AGENT_CLI: 'claude', AGENT_PERMISSION_MODE: undefined });
            try {
                const { args } = mod.buildCLICommand('p', { role, autoApprove: true });
                assert.equal(args.includes('--dangerously-skip-permissions'), true);
                assert.equal(args.includes('--permission-mode'), false);
            } finally {
                restore();
            }
        });
    }

    it('role is matched case-insensitively and via AGENT_ROLE env without plan mode', () => {
        const { mod, restore } = freshExecutor({ AGENT_CLI: 'agy', AGENT_ROLE: 'Code_Reviewer', AGENT_PERMISSION_MODE: undefined });
        try {
            const { args } = mod.buildCLICommand('p', { autoApprove: true });
            assert.equal(args.includes('--dangerously-skip-permissions'), true);
            assert.equal(args.includes('--mode'), false);
        } finally {
            restore();
        }
    });

    it('omits --dangerously-skip-permissions when autoApprove is false and never enters plan mode', () => {
        const { mod, restore } = freshExecutor({ AGENT_CLI: 'agy', AGENT_PERMISSION_MODE: undefined });
        try {
            const { args } = mod.buildCLICommand('p', { role: 'developer', autoApprove: false });
            assert.equal(args.includes('--dangerously-skip-permissions'), false);
            assert.equal(args.includes('--mode'), false);
        } finally {
            restore();
        }
    });

    it('claude omits --dangerously-skip-permissions when autoApprove is false and never enters plan mode', () => {
        const { mod, restore } = freshExecutor({ AGENT_CLI: 'claude', AGENT_PERMISSION_MODE: undefined });
        try {
            const { args } = mod.buildCLICommand('p', { role: 'developer', autoApprove: false });
            assert.equal(args.includes('--dangerously-skip-permissions'), false);
            assert.equal(args.includes('--permission-mode'), false);
        } finally {
            restore();
        }
    });
});

describe('CLI Executor - Fail-fast CLI validation (T-6)', () => {
    it('config.js throws a descriptive error at load when AGENT_CLI is gemini', () => {
        assert.throws(
            () => freshExecutor({ AGENT_CLI: 'gemini' }),
            /Unsupported AGENT_CLI: gemini\. Supported runtimes: 'claude', 'agy'/
        );
    });

    it('config.js throws a descriptive error at load when AGENT_CLI is unsupported or unknown', () => {
        assert.throws(
            () => freshExecutor({ AGENT_CLI: 'unsupported-cli' }),
            /Unsupported AGENT_CLI: unsupported-cli\. Supported runtimes: 'claude', 'agy'/
        );
    });

    it('does not leak an invalid AGENT_CLI into the environment after a failed load', () => {
        const before = process.env.AGENT_CLI;
        assert.throws(() => freshExecutor({ AGENT_CLI: 'gemini' }));
        assert.equal(process.env.AGENT_CLI, before);
    });

    it('buildCLICommand still rejects an unsupported per-call agentCli override', () => {
        const { mod, restore } = freshExecutor({ AGENT_CLI: 'agy' });
        try {
            assert.throws(
                () => mod.buildCLICommand('test', { agentCli: 'gemini' }),
                /Unsupported AGENT_CLI: gemini/
            );
        } finally {
            restore();
        }
    });
});

describe('CLI Executor - Timeout and Process Resolution (T-7)', () => {
    it('explorer resolves to 30 minutes (1800000ms), matching other roles', () => {
        const { restore } = freshExecutor({ TIMEOUT_MS: undefined });
        try {
            const { resolveTimeoutMs } = require(CONFIG_PATH);
            assert.equal(resolveTimeoutMs('explorer'), 1800000);
        } finally {
            restore();
        }
    });

    it('other roles are untouched by the explorer-specific bump', () => {
        const { restore } = freshExecutor({ TIMEOUT_MS: undefined });
        try {
            const { resolveTimeoutMs } = require(CONFIG_PATH);
            assert.equal(resolveTimeoutMs('developer'), 1800000);
            assert.equal(resolveTimeoutMs('code_reviewer'), 2700000);
        } finally {
            restore();
        }
    });

    it('an explicit TIMEOUT_MS env override still wins over the explorer ceiling', () => {
        const { restore } = freshExecutor({ TIMEOUT_MS: '123000' });
        try {
            const { resolveTimeoutMs } = require(CONFIG_PATH);
            assert.equal(resolveTimeoutMs('explorer'), 123000);
        } finally {
            restore();
        }
    });

    it('Claude buildCLICommand: still uses --effort (not prompt prefix) and the claude-sonnet-5-5 fallback', () => {
        const { mod, restore } = freshExecutor({
            AGENT_CLI: 'claude',
            AGENT_MODEL: undefined,
            GEMINI_MODEL: undefined,
        });
        try {
            const { binary, args } = mod.buildCLICommand('x', { effort: 'high' });
            assert.equal(binary, 'claude');
            assert.equal(args.includes('--thinking'), false);
            const effortIdx = args.indexOf('--effort');
            assert.notEqual(effortIdx, -1);
            assert.equal(args[effortIdx + 1], 'high');
            const modelIdx = args.indexOf('--model');
            assert.equal(args[modelIdx + 1], 'claude-sonnet-5-5');
        } finally {
            restore();
        }
    });

    it('Claude buildCLICommand: still uses the ultrathink prefix for architect, not the Gemini prefix', () => {
        const { mod, restore } = freshExecutor({ AGENT_CLI: 'claude', CLAUDE_SETTINGS_DIR: path.resolve(__dirname, '..', 'claude-settings') });
        try {
            const { args } = mod.buildCLICommand('review', { role: 'architect' });
            const promptIdx = args.indexOf('-p');
            assert.equal(args[promptIdx + 1], 'ultrathink review');
        } finally {
            restore();
        }
    });
});


describe('signal-terminated child (close(null, signal))', () => {
    // Regression: the close handlers referenced `signal` without declaring it, so a SIGKILL/timeout
    // (code === null) threw ReferenceError inside the event handler and the promise never settled.
    it('executeCLI resolves failed with exitCode null on close(null, SIGKILL)', async (t) => {
        const { mod, restore } = freshExecutor({ AGENT_CLI: 'agy', AGENT_MODEL: 'gemini-x' });
        try {
            const calls = mockSpawn(t, () => ({ code: null, signal: 'SIGKILL' }));
            const result = await Promise.race([
                mod.executeCLI('test', {}),
                new Promise((_, rej) => setTimeout(() => rej(new Error('executeCLI never settled')), 2000)),
            ]);
            assert.equal(result.status, 'failed');
            assert.equal(result.exitCode, null);
            assert.equal(calls.length, 1);
        } finally {
            restore();
        }
    });

    it('executeCLIStreaming resolves failed with exitCode null on close(null, SIGKILL)', async (t) => {
        const { mod, restore } = freshExecutor({ AGENT_CLI: 'agy', AGENT_MODEL: 'gemini-x' });
        try {
            const calls = mockSpawn(t, () => ({ code: null, signal: 'SIGKILL' }));
            const ws = { readyState: 1, send() {} };
            const result = await Promise.race([
                mod.executeCLIStreaming(ws, 'evt-sig', 'test', {}),
                new Promise((_, rej) => setTimeout(() => rej(new Error('executeCLIStreaming never settled')), 2000)),
            ]);
            assert.equal(result.status, 'failed');
            assert.equal(result.exitCode, null);
            assert.equal(calls.length, 1);
        } finally {
            restore();
        }
    });
});
