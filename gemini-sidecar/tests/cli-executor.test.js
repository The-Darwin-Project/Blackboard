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

// Scratch cwd for executor runs: executeCLI/executeCLIStreaming call prepareResultsDir(cwd) (which EMPTIES <cwd>/results) and watch it,
// so tests must never fall back to DEFAULT_WORK_DIR (e.g. /data/workspace on a squad pod).
const SCRATCH_CWD = fs.mkdtempSync(path.join(os.tmpdir(), 'cli-exec-scratch-'));
process.on('exit', () => { try { fs.rmSync(SCRATCH_CWD, { recursive: true, force: true }); } catch (_) {} });

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
                const deny = JSON.parse(fs.readFileSync(file, 'utf8')).permissions.deny;
                for (const rule of ['Bash(git push *)', 'Bash(git commit *)', 'Bash(kubectl apply *)']) assert.ok(deny.includes(rule), rule);
                for (const rule of ['Edit', 'Write', 'Bash(rm *)']) assert.equal(deny.includes(rule), false, `should not deny ${rule}`);
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

// =============================================================================
// 4-Layer Farley ATDD Executable Specification: Scenario T-6
// Claude Code Developer Deny Settings & Parameterized Validator
// =============================================================================

class ClaudeSettingsDriver {
    constructor(mod, baseDir) {
        this.mod = mod;
        this.baseDir = baseDir || path.resolve(__dirname, '..');
        this.claudeSettingsDir = path.resolve(this.baseDir, 'claude-settings');
    }

    buildCommand(options) {
        return this.mod.buildCLICommand('test prompt', options);
    }

    resolveSettingsFile(role, workStyle) {
        if (typeof this.mod.settingsFileForRole === 'function') {
            return this.mod.settingsFileForRole(role, workStyle);
        }
        return undefined;
    }

    getDeveloperSettingsPath() {
        return path.join(this.claudeSettingsDir, 'developer-permissions.json');
    }

    readDeveloperSettings() {
        const filePath = this.getDeveloperSettingsPath();
        if (!fs.existsSync(filePath)) {
            return null;
        }
        return JSON.parse(fs.readFileSync(filePath, 'utf8'));
    }
}

class ClaudeSettingsDSL {
    constructor(driver) {
        this.driver = driver;
    }

    givenDeveloperWorkStyle(workStyle) {
        return {
            agentCli: 'claude',
            role: 'developer',
            workStyle,
        };
    }

    whenBuildingCLICommand(options) {
        return this.driver.buildCommand(options);
    }

    thenDeveloperSettingsFileAttached(cmd) {
        const settingsIdx = cmd.args.indexOf('--settings');
        assert.notEqual(settingsIdx, -1, 'Expected --settings flag to be passed to claude CLI');
        const settingsPath = cmd.args[settingsIdx + 1];
        assert.ok(
            settingsPath.endsWith('developer-permissions.json'),
            `Expected settings path to end with 'developer-permissions.json', got: ${settingsPath}`
        );
    }

    thenNoSettingsFileAttached(cmd) {
        const settingsIdx = cmd.args.indexOf('--settings');
        assert.equal(settingsIdx, -1, `Expected no --settings flag for autonomous developer, got index: ${settingsIdx}`);
    }

    thenDeveloperPermissionsDenyTestsAndAllowGit() {
        const settings = this.driver.readDeveloperSettings();
        assert.ok(settings !== null, `Expected developer-permissions.json to exist at ${this.driver.getDeveloperSettingsPath()}`);
        const denyRules = settings?.permissions?.deny || [];
        assert.ok(Array.isArray(denyRules), 'Expected permissions.deny to be an array');

        // Must deny tests and specs
        const requiredDenies = ['Edit(**/tests/**)', 'Write(**/tests/**)'];
        for (const req of requiredDenies) {
            assert.ok(
                denyRules.includes(req),
                `Expected developer-permissions.json to include deny rule: ${req}`
            );
        }

        // Must NOT deny git commit, git push, or kubectl apply
        const bannedDenies = ['Bash(git commit *)', 'Bash(git push *)', 'Bash(kubectl apply *)'];
        for (const banned of bannedDenies) {
            assert.ok(
                !denyRules.includes(banned),
                `developer-permissions.json must NOT deny: ${banned}`
            );
        }
    }

    thenSettingsFileForRoleGatedCorrectly() {
        assert.equal(
            typeof this.driver.mod.settingsFileForRole,
            'function',
            'Expected settingsFileForRole to be exported from cli-executor.js'
        );
        const greenPath = this.driver.resolveSettingsFile('developer', 'atdd_green');
        assert.ok(
            greenPath && greenPath.endsWith('developer-permissions.json'),
            `Expected developer-permissions.json for ('developer', 'atdd_green'), got: ${greenPath}`
        );
        const autoPath = this.driver.resolveSettingsFile('developer', 'autonomous');
        assert.equal(
            autoPath,
            undefined,
            `Expected undefined for ('developer', 'autonomous'), got: ${autoPath}`
        );
    }
}

describe('Scenario T-6: Farley ATDD Developer Claude Deny Settings & Validator', () => {
    it('attaches developer-permissions.json when workStyle is atdd_green', () => {
        const { mod, restore } = freshExecutor({
            AGENT_CLI: 'claude',
            CLAUDE_SETTINGS_DIR: path.resolve(__dirname, '..', 'claude-settings'),
        });
        try {
            const driver = new ClaudeSettingsDriver(mod);
            const dsl = new ClaudeSettingsDSL(driver);

            const options = dsl.givenDeveloperWorkStyle('atdd_green');
            const cmd = dsl.whenBuildingCLICommand(options);
            dsl.thenDeveloperSettingsFileAttached(cmd);
        } finally {
            restore();
        }
    });

    it('attaches NO settings file for autonomous developer', () => {
        const { mod, restore } = freshExecutor({
            AGENT_CLI: 'claude',
            CLAUDE_SETTINGS_DIR: path.resolve(__dirname, '..', 'claude-settings'),
        });
        try {
            const driver = new ClaudeSettingsDriver(mod);
            const dsl = new ClaudeSettingsDSL(driver);

            const options = dsl.givenDeveloperWorkStyle('autonomous');
            const cmd = dsl.whenBuildingCLICommand(options);
            dsl.thenNoSettingsFileAttached(cmd);
        } finally {
            restore();
        }
    });

    it('verifies developer-permissions.json denies tests and permits git commit/push', () => {
        const { mod, restore } = freshExecutor({ AGENT_CLI: 'claude' });
        try {
            const driver = new ClaudeSettingsDriver(mod);
            const dsl = new ClaudeSettingsDSL(driver);

            dsl.thenDeveloperPermissionsDenyTestsAndAllowGit();
        } finally {
            restore();
        }
    });

    it('gates settingsFileForRole strictly on atdd_green workStyle', () => {
        const { mod, restore } = freshExecutor({ AGENT_CLI: 'claude' });
        try {
            const driver = new ClaudeSettingsDriver(mod);
            const dsl = new ClaudeSettingsDSL(driver);

            dsl.thenSettingsFileForRoleGatedCorrectly();
        } finally {
            restore();
        }
    });
});

/**
 * Farley ATDD 4-Layer Model for Sliding-Window Inactivity Watchdog (VMER-2321)
 * Layer 4: SUT - cli-executor.js (executeCLI / executeCLIStreaming)
 * Layer 3: Protocol Driver - InactivityWatchdogDriver
 * Layer 2: DSL - InactivityWatchdogDSL
 * Layer 1: Acceptance Scenarios - T-20 through T-24
 */
class InactivityWatchdogDriver {
    constructor(mod) {
        this.mod = mod;
        this.activityCount = 0;
        this.killedSignals = [];
    }

    createMockChild() {
        const child = new EventEmitter();
        child.stdout = new EventEmitter();
        child.stderr = new EventEmitter();
        child.killed = false;
        child.signals = [];
        child.kill = (sig = 'SIGTERM') => {
            child.killed = true;
            child.signals.push(sig);
            this.killedSignals.push(sig);
            setImmediate(() => {
                child.emit('close', null, sig);
            });
            return true;
        };
        return child;
    }

    createWsProxy() {
        return {
            send: () => {},
            onActivity: () => {
                this.activityCount++;
            },
        };
    }
}

class InactivityWatchdogDSL {
    constructor(driver) {
        this.driver = driver;
    }

    givenActiveStreamingProcess(t, { chunkIntervalMs, chunkCount, finalOutput = '{"ok":true}' }) {
        let childInstance;
        t.mock.method(cp, 'spawn', (cmd, args, opts) => {
            childInstance = this.driver.createMockChild();
            childInstance.spawnOpts = opts;
            let count = 0;
            const timer = setInterval(() => {
                count++;
                if (count <= chunkCount) {
                    childInstance.stdout.emit('data', Buffer.from(`chunk-${count}\n`));
                } else {
                    clearInterval(timer);
                    childInstance.stdout.emit('data', Buffer.from(finalOutput));
                    childInstance.emit('close', 0, null);
                }
            }, chunkIntervalMs);
            return childInstance;
        });
        return () => childInstance;
    }

    givenSilentProcess(t) {
        let childInstance;
        t.mock.method(cp, 'spawn', (cmd, args, opts) => {
            childInstance = this.driver.createMockChild();
            childInstance.spawnOpts = opts;
            return childInstance;
        });
        return () => childInstance;
    }

    givenPartialOutputThenHang(t, partialText) {
        let childInstance;
        t.mock.method(cp, 'spawn', (cmd, args, opts) => {
            childInstance = this.driver.createMockChild();
            childInstance.spawnOpts = opts;
            setTimeout(() => {
                childInstance.stdout.emit('data', Buffer.from(partialText));
            }, 5);
            return childInstance;
        });
        return () => childInstance;
    }

    givenErroringProcess(t) {
        let childInstance;
        t.mock.method(cp, 'spawn', (cmd, args, opts) => {
            childInstance = this.driver.createMockChild();
            childInstance.spawnOpts = opts;
            setTimeout(() => {
                childInstance.emit('error', new Error('spawn ENOENT'));
            }, 5);
            return childInstance;
        });
        return () => childInstance;
    }

    async whenExecutingStreaming(wsProxy, options = {}) {
        return this.driver.mod.executeCLIStreaming(wsProxy, 'evt-watchdog-test', 'test prompt', { cwd: SCRATCH_CWD, ...options });
    }

    async whenExecuting(options = {}) {
        return this.driver.mod.executeCLI('test prompt', { cwd: SCRATCH_CWD, ...options });
    }

    thenProcessCompletedSuccessfully(result, getChild) {
        const child = getChild();
        assert.equal(result.status, 'success', `Expected status success, got: ${result.status}`);
        assert.equal(child.killed, false, 'Expected child process not to be killed');
        assert.equal(child.spawnOpts.timeout, undefined, 'Expected spawn options not to have static timeout');
    }

    thenProcessTimedOut(result, getChild) {
        const child = getChild();
        assert.equal(result.status, 'failed', `Expected status failed, got: ${result.status}`);
        assert.equal(result.timedOut, true, 'Expected result.timedOut to be true');
        assert.ok(child.killed, 'Expected child process to be killed by watchdog');
        assert.ok(child.signals.includes('SIGTERM'), `Expected SIGTERM signal, got: ${child.signals.join(',')}`);
    }

    thenTimeoutErrorMessageAndStaleStdoutSuppression(result) {
        assert.equal(result.status, 'failed');
        assert.equal(result.timedOut, true);
        assert.match(result.output, /Task execution timed out: no output received/i);
        // The stale progress text must NOT be promoted into `output` (ws-client forwards output to Brain as the result)...
        assert.doesNotMatch(result.output, /mutants had finished/, 'stale stdout leaked into result.output');
        // ...but the tail is preserved in `stdout` for diagnostics instead of being thrown away.
        assert.match(result.stdout, /only 9 of 123 mutants had finished/, `Expected stdout tail to be preserved, got: ${result.stdout}`);
    }

    thenActivityCallbackInvoked(minCount = 1) {
        assert.ok(
            this.driver.activityCount >= minCount,
            `Expected onActivity to be called >= ${minCount} times, got: ${this.driver.activityCount}`
        );
    }
}

describe('Scenario T-20..T-24: Farley ATDD Sliding-Window Inactivity Watchdog & Heartbeat', () => {
    it('T-20: Heartbeat keeps active streaming process alive past inactivity window', async (t) => {
        // Inactivity window 300ms; chunks every 60ms x5 (total ~360ms > window). Each gap (60ms) leaves 240ms of
        // scheduler/CI-load headroom, so only a watchdog that fails to reset on activity can time out.
        const { mod, restore } = freshExecutor({ AGENT_CLI: 'claude', TIMEOUT_MS: '300' });
        try {
            const driver = new InactivityWatchdogDriver(mod);
            const dsl = new InactivityWatchdogDSL(driver);
            const wsProxy = driver.createWsProxy();

            const getChild = dsl.givenActiveStreamingProcess(t, {
                chunkIntervalMs: 60,
                chunkCount: 5,
                finalOutput: '{"status":"ok"}',
            });

            const result = await dsl.whenExecutingStreaming(wsProxy);
            dsl.thenProcessCompletedSuccessfully(result, getChild);
        } finally {
            restore();
        }
    });

    it('T-21: Genuine inactivity triggers timeout, kills child with SIGTERM and reports failure', async (t) => {
        // Inactivity timeout: 20ms. Silent process hangs.
        const { mod, restore } = freshExecutor({ AGENT_CLI: 'claude', TIMEOUT_MS: '20' });
        try {
            const driver = new InactivityWatchdogDriver(mod);
            const dsl = new InactivityWatchdogDSL(driver);
            const wsProxy = driver.createWsProxy();

            const getChild = dsl.givenSilentProcess(t);
            const result = await dsl.whenExecutingStreaming(wsProxy);

            dsl.thenProcessTimedOut(result, getChild);
        } finally {
            restore();
        }
    });

    it('T-22: Stale stdout is not promoted to the result; explicit inactivity message returned, stdout tail kept for diagnostics', async (t) => {
        const { mod, restore } = freshExecutor({ AGENT_CLI: 'claude', TIMEOUT_MS: '20' });
        try {
            const driver = new InactivityWatchdogDriver(mod);
            const dsl = new InactivityWatchdogDSL(driver);
            const wsProxy = driver.createWsProxy();

            dsl.givenPartialOutputThenHang(t, 'Turn 1: only 9 of 123 mutants had finished');
            const result = await dsl.whenExecutingStreaming(wsProxy);

            dsl.thenTimeoutErrorMessageAndStaleStdoutSuppression(result);
        } finally {
            restore();
        }
    });

    it('T-23: Clean watchdog teardown on spawn error (no timer survives the rejection)', async (t) => {
        const { mod, restore } = freshExecutor({ AGENT_CLI: 'claude', TIMEOUT_MS: '50', MAX_TASK_WALL_MS: '80' });
        try {
            const driver = new InactivityWatchdogDriver(mod);
            const dsl = new InactivityWatchdogDSL(driver);
            const wsProxy = driver.createWsProxy();

            const getChild = dsl.givenErroringProcess(t);
            await assert.rejects(async () => {
                await dsl.whenExecutingStreaming(wsProxy);
            }, /spawn ENOENT/);

            // Both the 50ms inactivity timer and the 80ms wall timer would have fired inside this window had either survived.
            await new Promise((r) => setTimeout(r, 250));
            const child = getChild();
            assert.deepEqual(child.signals, [], `watchdog fired after spawn error: ${child.signals.join(',')}`);
            assert.equal(child.killed, false);
            assert.equal(child._timedOut, undefined, 'watchdog marked a dead spawn as timed out');
        } finally {
            restore();
        }
    });

    it('T-24: Dual-timer sync via wsProxy.onActivity on raw stdout data chunks', async (t) => {
        const { mod, restore } = freshExecutor({ AGENT_CLI: 'claude', TIMEOUT_MS: '100' });
        try {
            const driver = new InactivityWatchdogDriver(mod);
            const dsl = new InactivityWatchdogDSL(driver);
            const wsProxy = driver.createWsProxy();

            dsl.givenActiveStreamingProcess(t, {
                chunkIntervalMs: 5,
                chunkCount: 3,
                finalOutput: '{"done":true}',
            });

            await dsl.whenExecutingStreaming(wsProxy);
            dsl.thenActivityCallbackInvoked(3);
        } finally {
            restore();
        }
    });
});

/** Controllable mock child: records signals; `onKill(sig, child)` decides how (or whether) it dies. */
function makeControlledChild({ onKill } = {}) {
    const child = new EventEmitter();
    child.stdout = new EventEmitter();
    child.stderr = new EventEmitter();
    child.exitCode = null;
    child.signalCode = null;
    child.signals = [];
    child.kill = (sig = 'SIGTERM') => {
        child.signals.push(sig);
        if (onKill) onKill(sig, child);
        return true;
    };
    return child;
}

/** Wait (real time, via setImmediate) until `cond()` is truthy -- for mock-timer tests where setTimeout is frozen. */
async function until(cond, label = 'condition') {
    for (let i = 0; i < 2000; i++) {
        if (cond()) return;
        await new Promise((r) => setImmediate(r));
    }
    assert.fail(`timed out waiting for ${label}`);
}

describe('createInactivityWatchdog (direct, mock timers)', () => {
    it('sliding reset(): activity re-arms the inactivity window; silence for a full window fires once', (t) => {
        t.mock.timers.enable({ apis: ['setTimeout'] });
        const { mod, restore } = freshExecutor({ AGENT_CLI: 'claude' });
        try {
            const child = makeControlledChild();
            const fired = [];
            const wd = mod.createInactivityWatchdog(child, 1000, (c, reason) => fired.push(reason), 1000000);

            t.mock.timers.tick(600);
            wd.reset();
            t.mock.timers.tick(600); // 1200ms since start, only 600ms since last activity
            assert.equal(child._timedOut, undefined, 'fired despite activity inside the window');
            wd.reset();
            t.mock.timers.tick(999);
            assert.deepEqual(child.signals, []);
            t.mock.timers.tick(1);
            assert.deepEqual(child.signals, ['SIGTERM']);
            assert.deepEqual(fired, ['inactivity']);
            assert.equal(child._timedOut, true);
            assert.equal(child._timeoutReason, 'inactivity');
            wd.clear();
        } finally {
            restore();
        }
    });

    it('escalates SIGTERM -> SIGKILL only after the kill grace period, and only if the child is still alive', (t) => {
        t.mock.timers.enable({ apis: ['setTimeout'] });
        const { mod, restore } = freshExecutor({ AGENT_CLI: 'claude' });
        try {
            const grace = mod.WATCHDOG_KILL_GRACE_MS;
            assert.equal(grace, 10000);

            // Stubborn child: ignores SIGTERM, stays alive.
            const stubborn = makeControlledChild();
            mod.createInactivityWatchdog(stubborn, 100, undefined, 1000000);
            t.mock.timers.tick(100);
            assert.deepEqual(stubborn.signals, ['SIGTERM']);
            t.mock.timers.tick(grace - 1);
            assert.deepEqual(stubborn.signals, ['SIGTERM'], 'SIGKILL sent before the grace period elapsed');
            t.mock.timers.tick(1);
            assert.deepEqual(stubborn.signals, ['SIGTERM', 'SIGKILL']);

            // Cooperative child: exits after SIGTERM, so no SIGKILL must follow.
            const polite = makeControlledChild({ onKill: (sig, c) => { c.exitCode = 0; } });
            mod.createInactivityWatchdog(polite, 100, undefined, 1000000);
            t.mock.timers.tick(100);
            t.mock.timers.tick(grace * 2);
            assert.deepEqual(polite.signals, ['SIGTERM']);
        } finally {
            restore();
        }
    });

    it('maxWallMs hard ceiling fires despite continuous reset() and is never extended', (t) => {
        t.mock.timers.enable({ apis: ['setTimeout'] });
        const { mod, restore } = freshExecutor({ AGENT_CLI: 'claude' });
        try {
            const child = makeControlledChild();
            const fired = [];
            const wd = mod.createInactivityWatchdog(child, 1000, (c, reason) => fired.push(reason), 3000);

            // Activity every 500ms keeps the inactivity window alive indefinitely...
            for (let i = 0; i < 5; i++) { // t = 500..2500
                t.mock.timers.tick(500);
                wd.reset();
            }
            t.mock.timers.tick(499); // t = 2999
            wd.reset();
            assert.deepEqual(child.signals, [], 'fired before the wall-clock ceiling');
            // ...but not past creation + maxWallMs (3000ms), however fresh the last activity was.
            t.mock.timers.tick(1);
            assert.deepEqual(child.signals, ['SIGTERM']);
            assert.deepEqual(fired, ['wall']);
            assert.equal(child._timeoutReason, 'wall');

            // Post-fire activity must not re-arm anything or fire a second time.
            wd.reset();
            t.mock.timers.tick(5000);
            assert.deepEqual(child.signals, ['SIGTERM']);
            wd.clear();
        } finally {
            restore();
        }
    });

    it('default maxWallMs is config MAX_TASK_WALL_MS (honours the env override)', (t) => {
        t.mock.timers.enable({ apis: ['setTimeout'] });
        const { mod, restore } = freshExecutor({ AGENT_CLI: 'claude', MAX_TASK_WALL_MS: '5000' });
        try {
            const child = makeControlledChild();
            const wd = mod.createInactivityWatchdog(child, 2000); // no explicit maxWallMs
            for (let i = 0; i < 9; i++) { t.mock.timers.tick(500); wd.reset(); }
            assert.deepEqual(child.signals, []);
            t.mock.timers.tick(500);
            assert.deepEqual(child.signals, ['SIGTERM']);
            assert.equal(child._timeoutReason, 'wall');
            wd.clear();
        } finally {
            restore();
        }
    });

    it('a disabled inactivity window (<=0) still enforces the wall ceiling; both disabled is a no-op', (t) => {
        t.mock.timers.enable({ apis: ['setTimeout'] });
        const { mod, restore } = freshExecutor({ AGENT_CLI: 'claude' });
        try {
            const wallOnly = makeControlledChild();
            const wd = mod.createInactivityWatchdog(wallOnly, 0, undefined, 400);
            wd.reset();
            t.mock.timers.tick(399);
            assert.deepEqual(wallOnly.signals, []);
            t.mock.timers.tick(1);
            assert.deepEqual(wallOnly.signals, ['SIGTERM']);
            wd.clear();

            const none = makeControlledChild();
            const noop = mod.createInactivityWatchdog(none, -5, undefined, NaN);
            noop.reset();
            t.mock.timers.tick(10 ** 9);
            noop.clear();
            assert.deepEqual(none.signals, []);
        } finally {
            restore();
        }
    });

    it('clear() stops both timers and a pending SIGKILL escalation; later reset() is a no-op', (t) => {
        t.mock.timers.enable({ apis: ['setTimeout'] });
        const { mod, restore } = freshExecutor({ AGENT_CLI: 'claude' });
        try {
            const idle = makeControlledChild();
            const wd = mod.createInactivityWatchdog(idle, 1000, undefined, 3000);
            t.mock.timers.tick(500);
            wd.clear();
            wd.reset();
            t.mock.timers.tick(10 ** 7);
            assert.deepEqual(idle.signals, [], 'timer survived clear()');

            const killed = makeControlledChild();
            const wd2 = mod.createInactivityWatchdog(killed, 100, undefined, 1000000);
            t.mock.timers.tick(100);
            assert.deepEqual(killed.signals, ['SIGTERM']);
            wd2.clear(); // e.g. 'close' arrived: pending SIGKILL must be cancelled
            t.mock.timers.tick(mod.WATCHDOG_KILL_GRACE_MS * 2);
            assert.deepEqual(killed.signals, ['SIGTERM']);
        } finally {
            restore();
        }
    });
});

describe('executeCLI / executeCLIStreaming watchdog integration', () => {
    const state = require('../state');
    const MODES = ['executeCLI', 'executeCLIStreaming'];
    const run = (mod, mode, options = {}) => (mode === 'executeCLI'
        ? mod.executeCLI('test prompt', { cwd: SCRATCH_CWD, ...options })
        : mod.executeCLIStreaming({ onActivity() {}, send() {} }, 'evt-wd-int', 'test prompt', { cwd: SCRATCH_CWD, ...options }));

    /** Child that emits whitespace chunks (valid JSON prefix) every `intervalMs` for `count` chunks, then JSON, then closes 0. */
    function activeJsonChild(t, { intervalMs, count }) {
        let child;
        t.mock.method(cp, 'spawn', () => {
            child = makeControlledChild({ onKill: (sig, c) => { clearInterval(c._iv); setImmediate(() => c.emit('close', null, sig)); } });
            let n = 0;
            child._iv = setInterval(() => {
                n++;
                if (n <= count) { child.stdout.emit('data', Buffer.from(' \n')); return; }
                clearInterval(child._iv);
                child.stdout.emit('data', Buffer.from('{"ok":true}'));
                child.emit('close', 0, null);
            }, intervalMs);
            return child;
        });
        return () => child;
    }

    for (const mode of MODES) {
        it(`${mode}: output activity resets the inactivity window (runs past the window without being killed)`, async (t) => {
            state.clearCurrentTask();
            const { mod, restore } = freshExecutor({ AGENT_CLI: 'claude', TIMEOUT_MS: '300' });
            try {
                let activity = 0;
                const getChild = activeJsonChild(t, { intervalMs: 60, count: 6 }); // ~420ms total > 300ms window
                const result = await run(mod, mode, { onActivity: () => { activity++; } });
                assert.equal(result.status, 'success');
                assert.deepEqual(getChild().signals, []);
                if (mode === 'executeCLI') assert.ok(activity >= 6, `onActivity called ${activity}x`);
            } finally {
                restore();
                state.clearCurrentTask();
            }
        });

        it(`${mode}: genuine silence times out with SIGTERM and a diagnostic result`, async (t) => {
            state.clearCurrentTask();
            const { mod, restore } = freshExecutor({ AGENT_CLI: 'claude', TIMEOUT_MS: '30' });
            try {
                let child;
                t.mock.method(cp, 'spawn', () => {
                    child = makeControlledChild({ onKill: (sig, c) => setImmediate(() => c.emit('close', null, sig)) });
                    return child;
                });
                const result = await run(mod, mode, {});
                assert.equal(result.status, 'failed');
                assert.equal(result.timedOut, true);
                assert.equal(result.timeoutReason, 'inactivity');
                assert.match(result.output, /no output received for 1 minutes/);
                assert.deepEqual(child.signals, ['SIGTERM']);
            } finally {
                restore();
                state.clearCurrentTask();
            }
        });

        it(`${mode}: wall-clock ceiling terminates a never-silent child`, async (t) => {
            state.clearCurrentTask();
            const { mod, restore } = freshExecutor({ AGENT_CLI: 'claude', TIMEOUT_MS: '400', MAX_TASK_WALL_MS: '200' });
            try {
                const getChild = activeJsonChild(t, { intervalMs: 20, count: 10000 }); // chatty for far longer than 200ms
                const started = Date.now();
                const result = await run(mod, mode, {});
                assert.equal(result.status, 'failed');
                assert.equal(result.timedOut, true);
                assert.equal(result.timeoutReason, 'wall');
                assert.match(result.output, /exceeded maximum wall-clock time of 1 minutes/);
                assert.deepEqual(getChild().signals, ['SIGTERM']);
                assert.ok(Date.now() - started < 3000, 'wall ceiling did not fire promptly');
            } finally {
                restore();
                state.clearCurrentTask();
            }
        });

        it(`${mode}: partial stdout tail and callback result are salvaged on timeout`, async (t) => {
            state.clearCurrentTask();
            const { mod, restore } = freshExecutor({ AGENT_CLI: 'claude', TIMEOUT_MS: '60' });
            try {
                t.mock.method(cp, 'spawn', () => {
                    const child = makeControlledChild({ onKill: (sig, c) => setImmediate(() => c.emit('close', null, sig)) });
                    setTimeout(() => {
                        state.setCallbackResult('FINAL REPORT via callback');
                        child.stdout.emit('data', Buffer.from('x'.repeat(5000) + 'TAIL-MARKER'));
                    }, 5);
                    return child;
                });
                const result = await run(mod, mode, {});
                assert.equal(result.timedOut, true);
                assert.match(result.output, /no output received/);
                assert.match(result.output, /FINAL REPORT via callback/);
                assert.equal(result.partialOutput, 'FINAL REPORT via callback');
                assert.equal(result.source, 'callback');
                assert.ok(result.stdout.endsWith('TAIL-MARKER'), 'stdout tail missing');
                assert.ok(result.stdout.length < 3200, `stdout tail not truncated (${result.stdout.length})`);
                assert.doesNotMatch(result.output, /xxxxx/, 'raw stdout leaked into result.output');
                assert.equal(state.getCallbackResult(), null, 'callback result not consumed');
            } finally {
                restore();
                state.clearCurrentTask();
                state.resetCallbackResult();
            }
        });

        it(`${mode}: cached findings.md is salvaged on timeout`, async (t) => {
            state.clearCurrentTask();
            const cwd = fs.mkdtempSync(path.join(os.tmpdir(), 'cli-exec-cwd-'));
            const { mod, restore } = freshExecutor({ AGENT_CLI: 'claude', TIMEOUT_MS: '250' });
            try {
                t.mock.method(cp, 'spawn', () => {
                    const child = makeControlledChild({ onKill: (sig, c) => setImmediate(() => c.emit('close', null, sig)) });
                    setTimeout(() => fs.writeFileSync(path.join(cwd, 'results', 'findings.md'), 'FINDINGS written before hang'), 10);
                    return child;
                });
                const result = await run(mod, mode, { cwd });
                assert.equal(result.timedOut, true);
                assert.match(result.output, /FINDINGS written before hang/);
                assert.equal(result.source, 'findings');
            } finally {
                restore();
                state.clearCurrentTask();
                fs.rmSync(cwd, { recursive: true, force: true });
            }
        });

        it(`${mode}: a child that exits 0 after the watchdog fired is a clean exit, not a failure`, async (t) => {
            state.clearCurrentTask();
            const { mod, restore } = freshExecutor({ AGENT_CLI: 'claude', TIMEOUT_MS: '30' });
            try {
                t.mock.method(cp, 'spawn', () => makeControlledChild({
                    onKill: (sig, c) => setImmediate(() => {
                        c.stdout.emit('data', Buffer.from('{"ok":true}'));
                        c.emit('close', 0, null); // finished on its own just as SIGTERM landed
                    }),
                }));
                const result = await run(mod, mode, {});
                assert.equal(result.status, 'success');
                assert.equal(result.timedOut, undefined);
            } finally {
                restore();
                state.clearCurrentTask();
            }
        });

        it(`${mode}: a post-timeout 'error' event does not cancel the pending SIGKILL escalation`, async (t) => {
            state.clearCurrentTask();
            t.mock.timers.enable({ apis: ['setTimeout'] });
            const { mod, restore } = freshExecutor({ AGENT_CLI: 'claude', TIMEOUT_MS: '100', MAX_TASK_WALL_MS: '100000' });
            try {
                let child;
                t.mock.method(cp, 'spawn', () => {
                    // Ignores SIGTERM; only dies on SIGKILL.
                    child = makeControlledChild({ onKill: (sig, c) => { if (sig === 'SIGKILL') setImmediate(() => c.emit('close', null, sig)); } });
                    return child;
                });
                const pending = run(mod, mode, {}).catch((e) => e);
                await until(() => child, 'spawn');
                t.mock.timers.tick(100); // inactivity fires
                assert.deepEqual(child.signals, ['SIGTERM']);
                child.emit('error', new Error('late spawn error'));
                t.mock.timers.tick(mod.WATCHDOG_KILL_GRACE_MS);
                assert.deepEqual(child.signals, ['SIGTERM', 'SIGKILL'], 'SIGKILL escalation was cancelled by the error handler');
                const outcome = await pending;
                assert.match(String(outcome.message || outcome.output), /late spawn error|timed out/);
            } finally {
                restore();
                state.clearCurrentTask();
            }
        });
    }
});

describe('config timer validation', () => {
    it('TIMEOUT_MS / MAX_TASK_WALL_MS reject negative, NaN, junk and overflow values', () => {
        const cases = [
            ['-5', 1800000], ['NaN', 1800000], ['abc', 1800000], ['0', 1800000], ['', 1800000], ['1e3', 1800000], ['25abc', 1800000],
            ['2500', 2500], ['99999999999999', 2147483647],
        ];
        for (const [raw, expected] of cases) {
            const { mod, restore } = freshExecutor({ AGENT_CLI: 'claude', TIMEOUT_MS: raw });
            try {
                const cfg = require(CONFIG_PATH);
                assert.equal(cfg.resolveTimeoutMs('qe'), expected, `TIMEOUT_MS=${JSON.stringify(raw)}`);
            } finally {
                restore();
            }
        }
        for (const [raw, expected] of [[undefined, 3000000], ['-1', 3000000], ['NaN', 3000000], ['120000', 120000], ['9999999999999', 2147483647]]) {
            const { restore } = freshExecutor({ AGENT_CLI: 'claude', MAX_TASK_WALL_MS: raw });
            try {
                assert.equal(require(CONFIG_PATH).MAX_TASK_WALL_MS, expected, `MAX_TASK_WALL_MS=${raw}`);
            } finally {
                restore();
            }
        }
    });

    it('default wall ceiling is 50 minutes, above every role inactivity window', () => {
        const { restore } = freshExecutor({ AGENT_CLI: 'claude', MAX_TASK_WALL_MS: undefined, TIMEOUT_MS: undefined });
        try {
            const cfg = require(CONFIG_PATH);
            assert.equal(cfg.MAX_TASK_WALL_MS, 3000000);
            for (const [role, ms] of Object.entries(cfg.ROLE_TIMEOUTS)) {
                assert.ok(ms <= cfg.MAX_TASK_WALL_MS, `${role} inactivity window exceeds the wall ceiling`);
            }
        } finally {
            restore();
        }
    });
});

describe('ws-client: idle timer suppression, backstop grace, task binding', () => {
    const state = require('../state');
    const WS_CLIENT_PATH = path.resolve(__dirname, '..', 'ws-client.js');
    const MODULE_STUBS = {
        './cli-executor': (h) => ({ executeCLIStreaming: h.executeCLIStreaming, prepareResultsDir: () => {}, is429Error: () => false }),
        './credentials': () => ({
            hasGitHubCredentials: () => false, hasGitLabCredentials: () => false, hasJenkinsCredentials: () => false,
            hasGoogleServiceAccount: () => false, setupArgoCDMCP: async () => {}, setupCLILogins: async () => {},
            setupRemoteK8sMCPs: () => {}, setupRegistryCredentials: () => {}, GITLAB_HOST: 'gitlab.test',
        }),
        './cli-setup': () => ({ filterSkillsByRole() {}, filterSkillsByMode() {}, swapActiveRules() {}, restoreAllSkills() {} }),
        './event-transport': () => ({ ensureEventDocument: async () => {} }),
        './catalog-skills': () => ({ startCatalogSync() {} }),
    };

    /** Load ws-client with stubbed collaborators + env. `harness.executeCLIStreaming` is called by handleTask. */
    function freshWsClient(env, harness) {
        // Never inherit the host's ephemeral/role identity: EVENT_ID would arm a real 1h idle-exit timer after every handleTask.
        env = { EVENT_ID: undefined, AGENT_ROLE: undefined, IDLE_TIMEOUT_MS: undefined, ...env };
        const saved = {};
        for (const [k, v] of Object.entries(env)) {
            saved[k] = process.env[k];
            if (v === undefined) delete process.env[k]; else process.env[k] = v;
        }
        const stubbed = [];
        for (const [rel, factory] of Object.entries(MODULE_STUBS)) {
            const resolved = require.resolve(path.resolve(__dirname, '..', rel));
            stubbed.push(resolved);
            require.cache[resolved] = { id: resolved, filename: resolved, loaded: true, exports: factory(harness) };
        }
        delete require.cache[require.resolve(CONFIG_PATH)];
        delete require.cache[WS_CLIENT_PATH];
        const mod = require(WS_CLIENT_PATH);
        const restore = () => {
            mod.clearIdleTimer();
            for (const [k, v] of Object.entries(saved)) {
                if (v === undefined) delete process.env[k]; else process.env[k] = v;
            }
            for (const r of stubbed) delete require.cache[r];
            delete require.cache[WS_CLIENT_PATH];
            delete require.cache[require.resolve(CONFIG_PATH)];
            state.clearCurrentTask();
        };
        return { mod, restore };
    }

    /** Fake Brain socket: records sent messages. readyState 1 === ws.OPEN. */
    function fakeWs() {
        const sent = [];
        return { readyState: 1, sent, send(raw) { sent.push(JSON.parse(raw)); } };
    }

    /** executeCLIStreaming stub that blocks until released; records the wsProxy it was handed. */
    function blockingExecutor() {
        const h = { calls: 0, wsProxy: null, release: null };
        h.executeCLIStreaming = (wsProxy) => {
            h.calls++;
            h.wsProxy = wsProxy;
            return new Promise((resolve) => { h.release = (result) => resolve(result || { status: 'success', output: 'done', source: 'stdout' }); });
        };
        return h;
    }

    const task = (over = {}) => ({ type: 'task', task_id: 't-1', event_id: 'evt-1', prompt: 'do it', role: 'developer', cwd: os.tmpdir(), ...over });

    it('computeBackstopMs adds a grace beyond the watchdog window and caps at MAX_TASK_WALL_MS + grace', () => {
        const h = blockingExecutor();
        const { mod, restore } = freshWsClient({ MAX_TASK_WALL_MS: '60000' }, h);
        try {
            assert.equal(mod.BACKSTOP_GRACE_MS, 15000);
            assert.ok(mod.BACKSTOP_GRACE_MS > 10000, 'grace must exceed the watchdog SIGTERM->SIGKILL escalation (10s)');
            assert.equal(mod.computeBackstopMs(30), 30000 + 15000);
            assert.equal(mod.computeBackstopMs(10 ** 6), 60000 + 15000); // capped
            assert.ok(mod.computeBackstopMs(0) > 0);
        } finally {
            restore();
        }
    });

    it('backstop timer does NOT fire at the watchdog window; it fires only after the grace and clears the task', async (t) => {
        state.clearCurrentTask();
        t.mock.timers.enable({ apis: ['setTimeout'] });
        const h = blockingExecutor();
        const { mod, restore } = freshWsClient({ TASK_TIMEOUT_DEFAULT: '2', TASK_TIMEOUT_IMPLEMENT: '2', MAX_TASK_WALL_MS: '600000' }, h);
        try {
            const ws = fakeWs();
            const done = mod.handleTask(ws, task());
            await until(() => h.calls === 1, 'executeCLIStreaming call');

            t.mock.timers.tick(2000 + 14999); // window + just under grace: executor watchdog's turf
            assert.equal(ws.sent.filter((m) => m.type === 'error').length, 0, 'backstop raced the executor watchdog');
            assert.equal(state.getCurrentTask()?.taskId, 't-1');

            t.mock.timers.tick(1);
            const errors = ws.sent.filter((m) => m.type === 'error');
            assert.equal(errors.length, 1);
            assert.match(errors[0].error, /timed out after 2s/);
            assert.equal(state.getCurrentTask(), null);

            h.release({ status: 'failed', timedOut: true, output: 'late', source: 'stdout' });
            await done;
            assert.equal(ws.sent.filter((m) => m.type === 'result').length, 0, 'late result must not follow the backstop error');
        } finally {
            restore();
        }
    });

    it('activity resets the backstop (sliding), bound to the current taskId', async (t) => {
        state.clearCurrentTask();
        t.mock.timers.enable({ apis: ['setTimeout'] });
        const h = blockingExecutor();
        const { mod, restore } = freshWsClient({ TASK_TIMEOUT_DEFAULT: '2', TASK_TIMEOUT_IMPLEMENT: '2', MAX_TASK_WALL_MS: '600000' }, h);
        try {
            const ws = fakeWs();
            const done = mod.handleTask(ws, task());
            await until(() => h.calls === 1, 'executeCLIStreaming call');

            t.mock.timers.tick(10000);
            h.wsProxy.onActivity(); // re-arms a full 17s
            t.mock.timers.tick(16999);
            assert.equal(ws.sent.filter((m) => m.type === 'error').length, 0);
            assert.equal(state.getCurrentTask()?.taskId, 't-1');

            // Stale chunk from this (finished) task must not touch whatever task is current now.
            const staleProxy = h.wsProxy;
            state.clearCurrentTask();
            const other = { taskId: 'other', eventId: 'evt-2' };
            state.setCurrentTask(other);
            staleProxy.onActivity();
            staleProxy.send(JSON.stringify({ type: 'progress', message: 'stale' }));
            assert.equal(other.timer, undefined, 'stale chunk armed a timer on a different task');

            state.clearCurrentTask();
            h.release();
            await done;
        } finally {
            restore();
        }
    });

    it('a cancel during the pre-warm await aborts cleanly: no orphan CLI is spawned', async (t) => {
        state.clearCurrentTask();
        const h = blockingExecutor();
        const { mod, restore } = freshWsClient({}, h);
        try {
            // security_analyst runs the async vuln-DB pre-warm via child_process.exec -- the only await between
            // setCurrentTask(child: null) and the CLI spawn. Simulate handleCancel landing mid-await.
            t.mock.method(cp, 'exec', (cmd, opts, cb) => {
                state.clearCurrentTask();
                setImmediate(() => cb(null));
                return new EventEmitter();
            });
            const ws = fakeWs();
            await mod.handleTask(ws, task({ role: 'security_analyst', task_id: 't-cancel' }));
            assert.equal(h.calls, 0, 'CLI spawned for a cancelled task');
            assert.equal(ws.sent.filter((m) => m.type === 'result' || m.type === 'error').length, 0);
        } finally {
            restore();
        }
    });

    describe('ephemeral idle timer', () => {
        const EPHEMERAL_ENV = { EVENT_ID: 'evt-idle', IDLE_TIMEOUT_MS: '1000', AGENT_ROLE: 'developer', MAX_TASK_WALL_MS: '600000' };

        function neutralizeExit(t) {
            const exit = t.mock.method(process, 'exit', () => {});
            // signalIdleExit() writes sentinel files under /data/workspace -- never let a test touch the real squad pod's markers.
            const writes = t.mock.method(fs, 'writeFileSync', () => {});
            return { exit, writes };
        }

        it('is paused while a task runs (no exit mid-task) and re-armed when it finishes', async (t) => {
            state.clearCurrentTask();
            t.mock.timers.enable({ apis: ['setTimeout'] });
            const { exit, writes } = neutralizeExit(t);
            const h = blockingExecutor();
            const { mod, restore } = freshWsClient(EPHEMERAL_ENV, h);
            try {
                mod.resetIdleTimer(); // as on WS 'open'
                const ws = fakeWs();
                const done = mod.handleTask(ws, task());
                await until(() => h.calls === 1, 'executeCLIStreaming call');

                t.mock.timers.tick(1000 * 20); // 20 idle windows while the task is active
                assert.equal(exit.mock.callCount(), 0, 'idle timer exited the process mid-task');
                assert.equal(writes.mock.callCount(), 0, 'idle sentinel written mid-task');

                h.release();
                await done;
                t.mock.timers.tick(999);
                assert.equal(exit.mock.callCount(), 0);
                t.mock.timers.tick(1); // re-armed in finally -> fires after a full idle window
                assert.equal(exit.mock.callCount(), 1);
                assert.deepEqual(exit.mock.calls[0].arguments, [0]);
                assert.equal(writes.mock.callCount(), 1);
            } finally {
                restore();
            }
        });

        it('callback refuses to exit while a task is current and re-schedules instead (guard independent of handleTask)', (t) => {
            state.clearCurrentTask();
            t.mock.timers.enable({ apis: ['setTimeout'] });
            const { exit, writes } = neutralizeExit(t);
            const { mod, restore } = freshWsClient(EPHEMERAL_ENV, blockingExecutor());
            try {
                state.setCurrentTask({ taskId: 'busy', eventId: 'evt-idle' });
                mod.resetIdleTimer();
                t.mock.timers.tick(1000 * 5);
                assert.equal(exit.mock.callCount(), 0, 'exited with a task in flight');
                assert.equal(writes.mock.callCount(), 0);

                state.clearCurrentTask();
                t.mock.timers.tick(1000); // the re-scheduled timer now finds the agent idle
                assert.equal(exit.mock.callCount(), 1);
            } finally {
                mod.clearIdleTimer();
                restore();
            }
        });

        it('non-ephemeral agents never arm the idle timer', (t) => {
            state.clearCurrentTask();
            t.mock.timers.enable({ apis: ['setTimeout'] });
            const { exit } = neutralizeExit(t);
            const { mod, restore } = freshWsClient({ ...EPHEMERAL_ENV, EVENT_ID: undefined }, blockingExecutor());
            try {
                mod.resetIdleTimer();
                t.mock.timers.tick(1000 * 100);
                assert.equal(exit.mock.callCount(), 0);
            } finally {
                restore();
            }
        });
    });
});

// ---------------------------------------------------------------------------------------------------------------------
// Mutation-hardening: behaviours that single-point mutants of the watchdog / timeout-result / config parsing could break
// without tripping the scenario tests above (timer clamping, handle teardown, unref, salvage priority, tail boundary...).
// ---------------------------------------------------------------------------------------------------------------------

/** Wraps the (mock) global setTimeout/clearTimeout: records created handles, which were unref()'d, and every clearTimeout arg.
 *  Mock timers' own unref()/hasRef() are no-ops, so unref is observed by wrapping the method on each returned handle. */
function trackTimers(t) {
    const origSet = globalThis.setTimeout;
    const origClear = globalThis.clearTimeout;
    const created = [];
    const unrefd = new Set();
    const cleared = [];
    t.mock.method(globalThis, 'setTimeout', (...args) => {
        const h = origSet(...args);
        const realUnref = h.unref.bind(h);
        h.unref = () => { unrefd.add(h); return realUnref(); };
        created.push(h);
        return h;
    });
    t.mock.method(globalThis, 'clearTimeout', (h) => { cleared.push(h); return origClear(h); });
    return { created, unrefd, cleared };
}

describe('createInactivityWatchdog: timer hygiene (mutation-hardening)', () => {
    const MAX = 2147483647;

    it('limits above the Node timer maximum are clamped to it (not dropped, not overflowed)', (t) => {
        t.mock.timers.enable({ apis: ['setTimeout'] });
        const { mod, restore } = freshExecutor({ AGENT_CLI: 'claude' });
        try {
            const idle = makeControlledChild();
            mod.createInactivityWatchdog(idle, 10 ** 12, undefined, 0);
            t.mock.timers.tick(MAX - 1);
            assert.deepEqual(idle.signals, []);
            t.mock.timers.tick(1);
            assert.deepEqual(idle.signals, ['SIGTERM']);
            assert.equal(idle._timeoutReason, 'inactivity');

            const wall = makeControlledChild();
            mod.createInactivityWatchdog(wall, 0, undefined, 10 ** 12);
            t.mock.timers.tick(MAX - 1);
            assert.deepEqual(wall.signals, []);
            t.mock.timers.tick(1);
            assert.deepEqual(wall.signals, ['SIGTERM']);
            assert.equal(wall._timeoutReason, 'wall');
        } finally {
            restore();
        }
    });

    it('non-finite limits disable that limit: Infinity/Infinity arms no timer at all', (t) => {
        t.mock.timers.enable({ apis: ['setTimeout'] });
        const { mod, restore } = freshExecutor({ AGENT_CLI: 'claude' });
        try {
            const { created } = trackTimers(t);
            const child = makeControlledChild();
            const wd = mod.createInactivityWatchdog(child, Infinity, undefined, Infinity);
            wd.reset();
            t.mock.timers.tick(MAX);
            assert.equal(created.length, 0, 'an Infinity limit armed a timer');
            assert.deepEqual(child.signals, []);
            wd.clear();
        } finally {
            restore();
        }
    });

    it('an onTimeout callback that throws never prevents SIGTERM or the SIGKILL escalation', (t) => {
        t.mock.timers.enable({ apis: ['setTimeout'] });
        const { mod, restore } = freshExecutor({ AGENT_CLI: 'claude' });
        try {
            const child = makeControlledChild();
            mod.createInactivityWatchdog(child, 100, () => { throw new Error('boom'); }, 100000);
            t.mock.timers.tick(100);
            assert.deepEqual(child.signals, ['SIGTERM']);
            assert.equal(child._timedOut, true);
            t.mock.timers.tick(mod.WATCHDOG_KILL_GRACE_MS);
            assert.deepEqual(child.signals, ['SIGTERM', 'SIGKILL']);
        } finally {
            restore();
        }
    });

    it('SIGKILL escalation is skipped when the child already died by signal (signalCode set, exitCode still null)', (t) => {
        t.mock.timers.enable({ apis: ['setTimeout'] });
        const { mod, restore } = freshExecutor({ AGENT_CLI: 'claude' });
        try {
            const child = makeControlledChild({ onKill: (sig, c) => { c.signalCode = sig; } });
            mod.createInactivityWatchdog(child, 100, undefined, 100000);
            t.mock.timers.tick(100);
            t.mock.timers.tick(mod.WATCHDOG_KILL_GRACE_MS * 3);
            assert.deepEqual(child.signals, ['SIGTERM']);
        } finally {
            restore();
        }
    });

    it('every watchdog timer (inactivity, wall, SIGKILL escalation) is unref()d so it never pins the process', (t) => {
        t.mock.timers.enable({ apis: ['setTimeout'] });
        const { mod, restore } = freshExecutor({ AGENT_CLI: 'claude' });
        try {
            const { created, unrefd } = trackTimers(t);
            const child = makeControlledChild();
            mod.createInactivityWatchdog(child, 100, undefined, 1000);
            assert.equal(created.length, 2, 'expected the wall and inactivity timers');
            t.mock.timers.tick(100); // fires -> arms the SIGKILL escalation timer
            assert.equal(created.length, 3);
            for (const [i, h] of created.entries()) assert.ok(unrefd.has(h), `watchdog timer #${i} was not unref()d`);
        } finally {
            restore();
        }
    });

    it('after clear() or after firing, reset() arms nothing', (t) => {
        t.mock.timers.enable({ apis: ['setTimeout'] });
        const { mod, restore } = freshExecutor({ AGENT_CLI: 'claude' });
        try {
            const { created } = trackTimers(t);
            const cleared = mod.createInactivityWatchdog(makeControlledChild(), 1000, undefined, 3000);
            cleared.clear();
            let n = created.length;
            cleared.reset();
            assert.equal(created.length, n, 'reset() after clear() armed a timer');

            const fired = mod.createInactivityWatchdog(makeControlledChild(), 100, undefined, 100000);
            t.mock.timers.tick(100);
            n = created.length;
            fired.reset();
            assert.equal(created.length, n, 'reset() after the watchdog fired armed a timer');
        } finally {
            restore();
        }
    });

    it('clear() and firing release the sibling limit timers (no leaked handles)', (t) => {
        t.mock.timers.enable({ apis: ['setTimeout'] });
        const { mod, restore } = freshExecutor({ AGENT_CLI: 'claude' });
        try {
            const { created, cleared } = trackTimers(t);

            // clear(): both the wall and inactivity timers are cancelled.
            const a = mod.createInactivityWatchdog(makeControlledChild(), 1000, undefined, 3000);
            const [aWall, aIdle] = created.slice(-2);
            cleared.length = 0;
            a.clear();
            assert.ok(cleared.includes(aWall), 'clear() leaked the wall timer');
            assert.ok(cleared.includes(aIdle), 'clear() leaked the inactivity timer');

            // fires on inactivity: the pending wall timer is cancelled.
            const b = mod.createInactivityWatchdog(makeControlledChild(), 100, undefined, 5000);
            const bWall = created[created.length - 2];
            cleared.length = 0;
            t.mock.timers.tick(100);
            assert.ok(cleared.includes(bWall), 'inactivity fire leaked the wall timer');
            b.clear();

            // fires on the wall ceiling: the pending inactivity timer is cancelled.
            const c = mod.createInactivityWatchdog(makeControlledChild(), 1000, undefined, 500);
            const cIdle = created[created.length - 1];
            cleared.length = 0;
            t.mock.timers.tick(500);
            assert.ok(cleared.includes(cIdle), 'wall fire leaked the inactivity timer');
            c.clear();
        } finally {
            restore();
        }
    });
});

describe('buildTimeoutResult (direct, mutation-hardening)', () => {
    const state = require('../state');
    const build = (mod, over = {}) => mod.buildTimeoutResult({
        child: { _timeoutReason: 'inactivity' }, code: null, timeoutMs: 120000, stderr: 'err', effectiveOutput: '',
        watch: null, usedModel: 'm-1', ...over,
    });
    const withMod = (fn) => {
        state.resetCallbackResult();
        const { mod, restore } = freshExecutor({ AGENT_CLI: 'claude', MAX_TASK_WALL_MS: undefined });
        try { return fn(mod); } finally { restore(); state.resetCallbackResult(); }
    };

    it('wall diagnostic reports the wall ceiling in minutes (not the inactivity window); inactivity reports the window; min 1 minute', () => withMod((mod) => {
        assert.match(build(mod, { child: { _timeoutReason: 'wall' }, timeoutMs: 120000 }).output, /exceeded maximum wall-clock time of 50 minutes$/);
        assert.match(build(mod, { timeoutMs: 120000 }).output, /no output received for 2 minutes$/);
        assert.match(build(mod, { timeoutMs: 100 }).output, /no output received for 1 minutes$/, 'sub-minute window must report at least 1');
    }));

    it('defaults: timeoutReason falls back to inactivity, exitCode falls back to 143 only when code is null/undefined', () => withMod((mod) => {
        const r = build(mod, { child: {}, code: null });
        assert.equal(r.timeoutReason, 'inactivity');
        assert.equal(r.exitCode, 143);
        assert.equal(r.status, 'failed');
        assert.equal(r.timedOut, true);
        assert.equal(r.usedModel, 'm-1');
        assert.equal(r.stderr, 'err');
        assert.equal(build(mod, { code: 137 }).exitCode, 137);
        assert.equal(build(mod, { child: { _timeoutReason: 'wall' } }).timeoutReason, 'wall');
    }));

    it('nothing to salvage: output is the bare diagnostic, partialOutput is null and source is stdout', () => withMod((mod) => {
        const r = build(mod);
        assert.equal(r.output, 'Task execution timed out: no output received for 2 minutes');
        assert.strictEqual(r.partialOutput, null);
        assert.equal(r.source, 'stdout');
        assert.equal('sessionId' in r, false, 'sessionId must be absent when not supplied');
    }));

    it('salvage prefers the callback result over cached findings; falls back to findings; consumes the callback result', () => withMod((mod) => {
        const watch = { cachedFindings: { content: 'FINDINGS-TEXT' } };
        state.setCallbackResult('CALLBACK-TEXT');
        const both = build(mod, { watch });
        assert.equal(both.source, 'callback');
        assert.equal(both.partialOutput, 'CALLBACK-TEXT');
        assert.ok(both.output.startsWith('Task execution timed out'), 'diagnostic must lead the output');
        assert.match(both.output, /--- Partial result salvaged before timeout ---\nCALLBACK-TEXT$/);
        assert.doesNotMatch(both.output, /FINDINGS-TEXT/);
        assert.equal(state.getCallbackResult(), null);

        const findingsOnly = build(mod, { watch });
        assert.equal(findingsOnly.source, 'findings');
        assert.equal(findingsOnly.partialOutput, 'FINDINGS-TEXT');
        assert.match(findingsOnly.output, /FINDINGS-TEXT$/);

        const emptyFindings = build(mod, { watch: { cachedFindings: { content: '' } } });
        assert.equal(emptyFindings.source, 'stdout');
        assert.strictEqual(emptyFindings.partialOutput, null);
    }));

    it('stdout tail: untouched at exactly 3000 chars; above that only the LAST 3000 chars are kept behind a truncation marker', () => withMod((mod) => {
        const exact = 'a'.repeat(3000);
        assert.equal(build(mod, { effectiveOutput: exact }).stdout, exact);
        assert.equal(build(mod, { effectiveOutput: '' }).stdout, '');

        const over = 'H'.repeat(1) + 'b'.repeat(3000); // 3001 chars: the leading 'H' must be dropped
        const r = build(mod, { effectiveOutput: over });
        assert.equal(r.stdout, `[...truncated...]\n${'b'.repeat(3000)}`);
        assert.doesNotMatch(r.output, /bbbb/, 'stdout must not leak into output');
    }));

    it('sessionId is passed through when supplied (including null), omitted when undefined', () => withMod((mod) => {
        assert.equal(build(mod, { sessionId: 'sess-9' }).sessionId, 'sess-9');
        assert.strictEqual(build(mod, { sessionId: null }).sessionId, null);
    }));
});

describe('executeCLI / executeCLIStreaming timeout edge cases (mutation-hardening)', () => {
    const state = require('../state');
    const MODES = ['executeCLI', 'executeCLIStreaming'];
    const run = (mod, mode, options = {}) => (mode === 'executeCLI'
        ? mod.executeCLI('test prompt', { cwd: SCRATCH_CWD, ...options })
        : mod.executeCLIStreaming({ onActivity() {}, send() {} }, 'evt-wd-edge', 'test prompt', { cwd: SCRATCH_CWD, ...options }));

    for (const mode of MODES) {
        it(`${mode}: a timed-out child that exits non-zero without a signal is still a timeout failure`, async (t) => {
            state.clearCurrentTask();
            const { mod, restore } = freshExecutor({ AGENT_CLI: 'claude', TIMEOUT_MS: '30' });
            try {
                t.mock.method(cp, 'spawn', () => makeControlledChild({ onKill: (sig, c) => setImmediate(() => c.emit('close', 1, null)) }));
                const result = await run(mod, mode, {});
                assert.equal(result.timedOut, true);
                assert.equal(result.status, 'failed');
                assert.equal(result.exitCode, 1);
            } finally {
                restore();
                state.clearCurrentTask();
            }
        });

        it(`${mode}: close(0, signal) after the watchdog fired is NOT a clean exit (only code 0 AND no signal is)`, async (t) => {
            state.clearCurrentTask();
            const { mod, restore } = freshExecutor({ AGENT_CLI: 'claude', TIMEOUT_MS: '30' });
            try {
                t.mock.method(cp, 'spawn', () => makeControlledChild({ onKill: (sig, c) => setImmediate(() => c.emit('close', 0, sig)) }));
                const result = await run(mod, mode, {});
                assert.equal(result.timedOut, true);
                assert.equal(result.status, 'failed');
            } finally {
                restore();
                state.clearCurrentTask();
            }
        });

        it(`${mode}: stderr-only output also resets the inactivity window`, async (t) => {
            state.clearCurrentTask();
            const { mod, restore } = freshExecutor({ AGENT_CLI: 'claude', TIMEOUT_MS: '300' });
            try {
                let child;
                t.mock.method(cp, 'spawn', () => {
                    child = makeControlledChild({ onKill: (sig, c) => { clearInterval(c._iv); setImmediate(() => c.emit('close', null, sig)); } });
                    let n = 0;
                    child._iv = setInterval(() => {
                        n++;
                        if (n <= 6) { child.stderr.emit('data', Buffer.from('progress\n')); return; } // ~420ms total > 300ms window
                        clearInterval(child._iv);
                        child.stdout.emit('data', Buffer.from('{"ok":true}'));
                        child.emit('close', 0, null);
                    }, 60);
                    return child;
                });
                const result = await run(mod, mode, {});
                assert.equal(result.status, 'success');
                assert.deepEqual(child.signals, []);
            } finally {
                restore();
                state.clearCurrentTask();
            }
        });

        it(`${mode}: a spawn 'error' tears the watchdog down (nothing is signalled afterwards) and closes the results watcher`, async (t) => {
            state.clearCurrentTask();
            t.mock.timers.enable({ apis: ['setTimeout'] });
            const closeCalls = [];
            t.mock.method(fs, 'watch', () => ({ close: () => closeCalls.push(1) }));
            const { mod, restore } = freshExecutor({ AGENT_CLI: 'claude', TIMEOUT_MS: '100', MAX_TASK_WALL_MS: '1000' });
            try {
                let child;
                t.mock.method(cp, 'spawn', () => { child = makeControlledChild(); return child; });
                const pending = run(mod, mode, {}).catch((e) => e);
                await until(() => child, 'spawn');
                child.emit('error', new Error('spawn ENOENT'));
                const outcome = await pending;
                assert.match(String(outcome.message), /spawn ENOENT/);
                assert.ok(closeCalls.length >= 1, 'results watcher not closed on spawn error');
                t.mock.timers.tick(5000); // well past both the inactivity window and the wall ceiling
                assert.deepEqual(child.signals, [], 'watchdog survived a spawn error and signalled a dead child');
            } finally {
                restore();
                state.clearCurrentTask();
            }
        });

        it(`${mode}: a normal close tears the watchdog down (no late SIGTERM to a finished child)`, async (t) => {
            state.clearCurrentTask();
            t.mock.timers.enable({ apis: ['setTimeout'] });
            const { mod, restore } = freshExecutor({ AGENT_CLI: 'claude', TIMEOUT_MS: '100', MAX_TASK_WALL_MS: '1000' });
            try {
                let child;
                t.mock.method(cp, 'spawn', () => {
                    child = makeControlledChild();
                    setImmediate(() => { child.stdout.emit('data', Buffer.from('{"ok":true}')); child.emit('close', 0, null); });
                    return child;
                });
                const result = await run(mod, mode, {});
                assert.equal(result.status, 'success');
                t.mock.timers.tick(5000);
                assert.deepEqual(child.signals, [], 'watchdog fired on an already-closed child');
            } finally {
                restore();
                state.clearCurrentTask();
            }
        });
    }
});

describe('config timer validation: edge cases (mutation-hardening)', () => {
    it('strict parsing: whitespace trimmed, 0 rejected (disabling the wall ceiling), 1 accepted, unsafe integers fall back', () => {
        const wall = [['0', 3000000], [' 120000 ', 120000], ['1', 1], ['9'.repeat(30), 3000000]];
        for (const [raw, expected] of wall) {
            const { restore } = freshExecutor({ AGENT_CLI: 'claude', MAX_TASK_WALL_MS: raw });
            try {
                assert.equal(require(CONFIG_PATH).MAX_TASK_WALL_MS, expected, `MAX_TASK_WALL_MS=${JSON.stringify(raw)}`);
            } finally {
                restore();
            }
        }
        const idle = [[' 2500 ', 2500], ['1', 1], ['9'.repeat(30), 1800000]];
        for (const [raw, expected] of idle) {
            const { restore } = freshExecutor({ AGENT_CLI: 'claude', TIMEOUT_MS: raw });
            try {
                assert.equal(require(CONFIG_PATH).resolveTimeoutMs('qe'), expected, `TIMEOUT_MS=${JSON.stringify(raw)}`);
            } finally {
                restore();
            }
        }
    });
});
