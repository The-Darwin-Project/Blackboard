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
    const mod = require(EXECUTOR_PATH);
    const restore = () => {
        for (const [k, v] of Object.entries(saved)) {
            if (v === undefined) delete process.env[k]; else process.env[k] = v;
        }
        delete require.cache[require.resolve(CONFIG_PATH)];
        delete require.cache[require.resolve(EXECUTOR_PATH)];
        fs.rmSync(fakeHome, { recursive: true, force: true });
    };
    return { mod, restore };
}

/** Mock cp.spawn; `script(args, callIndex)` returns { code, stdout, stderr }. Returns the recorded arg lists. */
function mockSpawn(t, script) {
    const calls = [];
    t.mock.method(cp, 'spawn', (cmd, args) => {
        const idx = calls.length;
        calls.push(args);
        const { code = 0, stdout = '', stderr = '' } = script(args, idx);
        const child = new EventEmitter();
        child.stdout = new EventEmitter();
        child.stderr = new EventEmitter();
        setTimeout(() => {
            if (stdout) child.stdout.emit('data', Buffer.from(stdout));
            if (stderr) child.stderr.emit('data', Buffer.from(stderr));
            child.emit('close', code);
        }, 5);
        return child;
    });
    return calls;
}

const modelOf = (args) => args[args.indexOf('--model') + 1];

describe('CLI Executor', () => {
    it('T-14: resolves Explorer model from EPHEMERAL_MODEL_EXPLORER', () => {
        const { mod, restore } = freshExecutor({ EPHEMERAL_MODEL_EXPLORER: 'gemini-test-model' });
        try {
            const { args } = mod.buildCLICommand('prompt', { role: 'explorer' });
            assert.equal(modelOf(args), 'gemini-test-model');
        } finally {
            restore();
        }
    });
});

describe('invalid-model fallback (shared getRetryOptions)', () => {
    it('T-17: gemini falls back to gemini-2.5-flash exactly once', async (t) => {
        const { mod, restore } = freshExecutor({ AGENT_CLI: 'gemini', EPHEMERAL_MODEL_EXPLORER: 'invalid-model-that-fails' });
        try {
            const calls = mockSpawn(t, (args) => args.includes('invalid-model-that-fails')
                ? { code: 1, stderr: 'INVALID_ARGUMENT: model not found' }
                : { code: 0, stdout: '{"ok":true}' });
            const result = await mod.executeCLI('test', { role: 'explorer' });
            assert.equal(result.usedModel, 'gemini-2.5-flash');
            assert.equal(calls.length, 2);
        } finally {
            restore();
        }
    });

    it('is one-shot: a fallback that also fails is returned as failed, not retried again', async (t) => {
        const { mod, restore } = freshExecutor({ AGENT_CLI: 'gemini', AGENT_MODEL: 'gemini-x' });
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
            assert.equal(calls.length, 1, 'retrying claude-opus-4-6 with claude-opus-4-6 is pointless');
        } finally {
            restore();
        }
    });

    it('does not retry a bare INVALID_ARGUMENT that does not name the model (bad flag, MCP, context size)', async (t) => {
        const { mod, restore } = freshExecutor({ AGENT_CLI: 'gemini', AGENT_MODEL: 'gemini-x' });
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
        const { mod, restore } = freshExecutor({ AGENT_CLI: 'gemini', AGENT_MODEL: 'gemini-bad' });
        try {
            const calls = mockSpawn(t, (args) => modelOf(args) === 'gemini-bad'
                ? { code: 1, stderr: 'model gemini-bad not found' }
                : { code: 0, stdout: '{"ok":true}' });
            const ws = { readyState: 1, send() {} };
            const result = await mod.executeCLIStreaming(ws, 'evt-1', 'test', {});
            assert.equal(result.status, 'success');
            assert.deepEqual(calls.map(modelOf), ['gemini-bad', 'gemini-2.5-flash']);
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

    it('isAgySessionError is false for claude/gemini even on matching stderr', () => {
        for (const cli of ['claude', 'gemini']) {
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

describe('agy read-only roles (plan mode is the only enforcement layer)', () => {
    for (const role of ['architect', 'explorer', 'code_reviewer', 'reviewer', 'security_analyst']) {
        it(`${role}: --mode plan, never --dangerously-skip-permissions, even with autoApprove`, () => {
            const { mod, restore } = freshExecutor({ AGENT_CLI: 'agy', AGENT_PERMISSION_MODE: undefined });
            try {
                const { args } = mod.buildCLICommand('p', { role, autoApprove: true });
                assert.equal(args[args.indexOf('--mode') + 1], 'plan');
                assert.equal(args.includes('--dangerously-skip-permissions'), false);
            } finally {
                restore();
            }
        });
    }

    it('role is matched case-insensitively and via AGENT_ROLE env', () => {
        const { mod, restore } = freshExecutor({ AGENT_CLI: 'agy', AGENT_ROLE: 'Code_Reviewer', AGENT_PERMISSION_MODE: undefined });
        try {
            const { args } = mod.buildCLICommand('p', { autoApprove: true });
            assert.equal(args[args.indexOf('--mode') + 1], 'plan');
        } finally {
            restore();
        }
    });

    it('unnormalized role with whitespace or compound name falls back to --mode plan', () => {
        const { mod, restore } = freshExecutor({ AGENT_CLI: 'agy', AGENT_PERMISSION_MODE: undefined });
        try {
            for (const r of ['  code_reviewer \n', 'security-analyst', 'qa_reviewer_agent', 'ARCHITECT_LEAD']) {
                const { args } = mod.buildCLICommand('p', { role: r, autoApprove: true });
                assert.equal(args[args.indexOf('--mode') + 1], 'plan', `Role ${r} should get --mode plan`);
                assert.equal(args.includes('--dangerously-skip-permissions'), false, `Role ${r} must not get --dangerously-skip-permissions`);
            }
        } finally {
            restore();
        }
    });

    it('a mutating role still gets --dangerously-skip-permissions with autoApprove', () => {
        const { mod, restore } = freshExecutor({ AGENT_CLI: 'agy', AGENT_PERMISSION_MODE: undefined, AGENT_ROLE: undefined });
        try {
            const { args } = mod.buildCLICommand('p', { role: 'developer', autoApprove: true });
            assert.equal(args.includes('--dangerously-skip-permissions'), true);
            assert.equal(args.includes('--mode'), false);
        } finally {
            restore();
        }
    });

    it('an unrecognized future role fails closed to --mode plan even with autoApprove', () => {
        const { mod, restore } = freshExecutor({ AGENT_CLI: 'agy', AGENT_PERMISSION_MODE: undefined, AGENT_ROLE: undefined });
        try {
            for (const r of ['custom_worker', 'arbitrary_bot', 'assistant', 'unknown_agent']) {
                const { args } = mod.buildCLICommand('p', { role: r, autoApprove: true });
                assert.equal(args[args.indexOf('--mode') + 1], 'plan', `Role ${r} should fail-closed to --mode plan`);
                assert.equal(args.includes('--dangerously-skip-permissions'), false, `Role ${r} must not get --dangerously-skip-permissions`);
            }
        } finally {
            restore();
        }
    });
});
