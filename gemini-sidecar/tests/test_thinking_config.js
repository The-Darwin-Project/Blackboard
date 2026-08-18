// gemini-sidecar/tests/test_thinking_config.js
// @ai-rules:
// 1. [Constraint]: Test-only file -- verifies writeThinkingConfig writes correct settings.json
//    with effort-mapped thinkingBudget before Gemini CLI spawn.
// 2. [Pattern]: Uses node:test + node:assert, same setEnv/restoreEnv/freshModules pattern
//    as test_gemini_cli_parity.js.
// 3. [Pattern]: Uses a real temp HOME dir per test to isolate settings.json writes.
//    GEMINI_SETTINGS_PATH is computed at require-time from os.homedir(), so HOME env
//    must be set BEFORE freshModules().
// 4. [Gotcha]: The .gemini/ directory must exist in the temp HOME -- writeThinkingConfig
//    creates the FILE, not the directory (Dockerfile handles that in production).

const { describe, it, afterEach, after } = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');
const fs = require('fs');
const os = require('os');

const CONFIG_PATH = path.resolve(__dirname, '..', 'config.js');
const CLI_EXECUTOR_PATH = path.resolve(__dirname, '..', 'cli-executor.js');

const savedEnv = {};
function setEnv(key, value) {
    if (!(key in savedEnv)) savedEnv[key] = process.env[key];
    if (value === undefined) delete process.env[key];
    else process.env[key] = value;
}

function restoreEnv() {
    for (const [key, val] of Object.entries(savedEnv)) {
        if (val === undefined) delete process.env[key];
        else process.env[key] = val;
    }
    Object.keys(savedEnv).forEach((k) => delete savedEnv[k]);
}

function freshModules() {
    delete require.cache[require.resolve(CONFIG_PATH)];
    delete require.cache[require.resolve(CLI_EXECUTOR_PATH)];
    return require(CLI_EXECUTOR_PATH);
}

const tmpHome = fs.mkdtempSync(path.join(os.tmpdir(), 'darwin-thinkingcfg-'));
const geminiDir = path.join(tmpHome, '.gemini');

afterEach(() => {
    restoreEnv();
    delete require.cache[require.resolve(CONFIG_PATH)];
    delete require.cache[require.resolve(CLI_EXECUTOR_PATH)];
    const settingsPath = path.join(geminiDir, 'settings.json');
    try { if (fs.existsSync(settingsPath)) fs.unlinkSync(settingsPath); } catch (_) {}
});

after(() => {
    try { fs.rmSync(tmpHome, { recursive: true, force: true }); } catch (_) {}
});

function setupHome() {
    if (!fs.existsSync(geminiDir)) fs.mkdirSync(geminiDir, { recursive: true });
    setEnv('HOME', tmpHome);
}

function readSettings() {
    return JSON.parse(fs.readFileSync(path.join(geminiDir, 'settings.json'), 'utf8'));
}

function getBudget(settings) {
    return settings.modelConfigs.overrides[0].modelConfig.generateContentConfig.thinkingConfig.thinkingBudget;
}

// =============================================================================
// writeThinkingConfig: effort → thinkingBudget mapping
// =============================================================================

describe('writeThinkingConfig', () => {
    it('writes 8192 budget for effort=high', () => {
        setupHome();
        setEnv('AGENT_CLI', 'gemini');
        const { writeThinkingConfig } = freshModules();
        writeThinkingConfig('high', 'gemini-3.7-flash');
        const settings = readSettings();
        const override = settings.modelConfigs.overrides[0];
        assert.equal(override.match.model, 'gemini-3.7-flash');
        assert.equal(getBudget(settings), 8192);
        assert.equal(override.modelConfig.generateContentConfig.thinkingConfig.includeThoughts, false);
    });

    it('writes 16384 budget for effort=max', () => {
        setupHome();
        setEnv('AGENT_CLI', 'gemini');
        const { writeThinkingConfig } = freshModules();
        writeThinkingConfig('max', 'gemini-3.7-flash');
        assert.equal(getBudget(readSettings()), 16384);
    });

    it('writes 0 budget for effort=medium', () => {
        setupHome();
        setEnv('AGENT_CLI', 'gemini');
        const { writeThinkingConfig } = freshModules();
        writeThinkingConfig('medium', 'gemini-3.7-flash');
        assert.equal(getBudget(readSettings()), 0);
    });

    it('writes 0 budget for effort=low', () => {
        setupHome();
        setEnv('AGENT_CLI', 'gemini');
        const { writeThinkingConfig } = freshModules();
        writeThinkingConfig('low', 'gemini-3.7-flash');
        assert.equal(getBudget(readSettings()), 0);
    });

    it('writes 0 budget for effort=none (clears stale)', () => {
        setupHome();
        setEnv('AGENT_CLI', 'gemini');
        const { writeThinkingConfig } = freshModules();
        writeThinkingConfig('high', 'gemini-3.7-flash');
        assert.equal(getBudget(readSettings()), 8192, 'precondition: high sets 8192');
        writeThinkingConfig('none', 'gemini-3.7-flash');
        assert.equal(getBudget(readSettings()), 0, 'none overwrites stale high budget to 0');
    });

    it('defaults to 0 for unknown effort string', () => {
        setupHome();
        setEnv('AGENT_CLI', 'gemini');
        const { writeThinkingConfig } = freshModules();
        writeThinkingConfig('turbo', 'gemini-3.7-flash');
        assert.equal(getBudget(readSettings()), 0);
    });

    it('preserves existing auth/mcp keys in settings.json', () => {
        setupHome();
        setEnv('AGENT_CLI', 'gemini');
        const existingSettings = {
            auth: { token: 'vertex-token-123' },
            mcpServers: { local: { command: 'node', args: ['server.js'] } },
            hooks: { preToolUse: [{ name: 'validate-bash', command: './validate.sh' }] },
        };
        fs.writeFileSync(
            path.join(geminiDir, 'settings.json'),
            JSON.stringify(existingSettings, null, 2),
        );
        const { writeThinkingConfig } = freshModules();
        writeThinkingConfig('high', 'gemini-3.7-flash');
        const settings = readSettings();
        assert.equal(getBudget(settings), 8192);
        assert.deepStrictEqual(settings.auth, existingSettings.auth);
        assert.deepStrictEqual(settings.mcpServers, existingSettings.mcpServers);
        assert.deepStrictEqual(settings.hooks, existingSettings.hooks);
    });

    it('creates settings.json if it does not exist', () => {
        setupHome();
        setEnv('AGENT_CLI', 'gemini');
        const settingsPath = path.join(geminiDir, 'settings.json');
        assert.equal(fs.existsSync(settingsPath), false, 'precondition: no settings.json yet');
        const { writeThinkingConfig } = freshModules();
        writeThinkingConfig('high', 'gemini-3.7-flash');
        assert.equal(fs.existsSync(settingsPath), true, 'writeThinkingConfig created the file');
        assert.equal(getBudget(readSettings()), 8192);
    });
});

// =============================================================================
// buildCLICommand integration: architect role → effort mapping → settings.json
// =============================================================================

describe('writeThinkingConfig: buildCLICommand integration', () => {
    it('architect role with no effort gets high (8192)', () => {
        setupHome();
        setEnv('AGENT_CLI', 'gemini');
        setEnv('AGENT_EFFORT_LEVEL', undefined);
        const { buildCLICommand } = freshModules();
        buildCLICommand('review the sidecar', { role: 'architect' });
        assert.equal(getBudget(readSettings()), 8192);
    });

    it('options.effort takes priority over AGENT_EFFORT_LEVEL (budget verification)', () => {
        setupHome();
        setEnv('AGENT_CLI', 'gemini');
        setEnv('AGENT_EFFORT_LEVEL', 'low');
        const { buildCLICommand } = freshModules();
        buildCLICommand('do the thing', { effort: 'max' });
        assert.equal(getBudget(readSettings()), 16384);
    });

    it('falls back to AGENT_EFFORT_LEVEL env (budget verification)', () => {
        setupHome();
        setEnv('AGENT_CLI', 'gemini');
        setEnv('AGENT_EFFORT_LEVEL', 'high');
        const { buildCLICommand } = freshModules();
        buildCLICommand('do the thing', {});
        assert.equal(getBudget(readSettings()), 8192);
    });
});
