// gemini-sidecar/tests/test_agy_cli_parity.js
// @ai-rules:
// 1. [Constraint]: Pure unit tests for cli-executor.js and cli-setup.js agy CLI parity — uses node:test + node:assert/strict.
// 2. [Pattern]: Sets AGENT_CLI=agy, clears require.cache between tests, restores environment.
// 3. [Coverage]: Validates buildCLICommand agy path, flag order, effort normalization, mode plan security,
//    conversation persistence, settings.json non-mutation, writeAgyMcpServer, and isAgySessionError recovery.

const { describe, it, afterEach } = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');
const fs = require('fs');
const os = require('os');

const CONFIG_PATH = path.resolve(__dirname, '..', 'config.js');
const CLI_EXECUTOR_PATH = path.resolve(__dirname, '..', 'cli-executor.js');
const CLI_SETUP_PATH = path.resolve(__dirname, '..', 'cli-setup.js');

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

afterEach(() => {
  restoreEnv();
  delete require.cache[require.resolve(CONFIG_PATH)];
  delete require.cache[require.resolve(CLI_EXECUTOR_PATH)];
  delete require.cache[require.resolve(CLI_SETUP_PATH)];
});

// =============================================================================
// 1. agy buildCLICommand: basics, prompt positioning, and no --input-format
// =============================================================================

describe('agy buildCLICommand: basics and argument order', () => {
  it('returns binary "agy" and includes --output-format stream-json', () => {
    setEnv('AGENT_CLI', 'agy');
    const { buildCLICommand } = freshModules();
    const { binary, args } = buildCLICommand('inspect system state', {});
    assert.equal(binary, 'agy');

    const outFmtIdx = args.indexOf('--output-format');
    assert.notEqual(outFmtIdx, -1, '--output-format should be present');
    assert.equal(args[outFmtIdx + 1], 'stream-json');
  });

  it('strictly forbids --input-format (prevents conflict with -p prompt)', () => {
    setEnv('AGENT_CLI', 'agy');
    const { buildCLICommand } = freshModules();
    const { args } = buildCLICommand('do something', {});
    assert.equal(args.includes('--input-format'), false, '--input-format must NOT be present in args');
    assert.equal(args.some((arg) => typeof arg === 'string' && arg.includes('input-format')), false);
  });

  it('places -p and prompt at the very end of args', () => {
    setEnv('AGENT_CLI', 'agy');
    const { buildCLICommand } = freshModules();
    const promptText = 'verify production rollout status';
    const { args } = buildCLICommand(promptText, { autoApprove: true, effort: 'high' });

    assert.equal(args[args.length - 2], '-p', '-p must be second-to-last arg');
    assert.equal(args[args.length - 1], promptText, 'prompt text must be the last arg');
  });
});

// =============================================================================
// 2. Model & Effort Normalization
// =============================================================================

describe('agy buildCLICommand: model and effort normalization', () => {
  it('defaults effort to "high" for bare flash models to prevent CLI crash', () => {
    setEnv('AGENT_CLI', 'agy');
    setEnv('AGENT_EFFORT_LEVEL', undefined);
    setEnv('AGENT_EFFORT', undefined);
    const { buildCLICommand } = freshModules();
    const { args } = buildCLICommand('test task', { model: 'gemini-3.7-flash' });

    const modelIdx = args.indexOf('--model');
    assert.notEqual(modelIdx, -1);
    assert.equal(args[modelIdx + 1], 'gemini-3.7-flash');

    const effortIdx = args.indexOf('--effort');
    assert.notEqual(effortIdx, -1, '--effort must be present');
    assert.equal(args[effortIdx + 1], 'high');
  });

  it('normalizes suffixed model names e.g. gemini-2.5-pro-max into model and effort', () => {
    setEnv('AGENT_CLI', 'agy');
    const { buildCLICommand } = freshModules();
    const { args } = buildCLICommand('test task', { model: 'gemini-2.5-pro-max' });

    const modelIdx = args.indexOf('--model');
    assert.notEqual(modelIdx, -1);
    assert.equal(args[modelIdx + 1], 'gemini-2.5-pro');

    const effortIdx = args.indexOf('--effort');
    assert.notEqual(effortIdx, -1);
    assert.equal(args[effortIdx + 1], 'max');
  });

  it('normalizes suffixed model names e.g. gemini-3.7-flash-low', () => {
    setEnv('AGENT_CLI', 'agy');
    const { buildCLICommand } = freshModules();
    const { args } = buildCLICommand('test task', { model: 'gemini-3.7-flash-low' });

    const modelIdx = args.indexOf('--model');
    assert.equal(args[modelIdx + 1], 'gemini-3.7-flash');

    const effortIdx = args.indexOf('--effort');
    assert.equal(args[effortIdx + 1], 'low');
  });

  it('respects explicit options.effort over default', () => {
    setEnv('AGENT_CLI', 'agy');
    const { buildCLICommand } = freshModules();
    const { args } = buildCLICommand('test task', { model: 'gemini-2.5-pro', effort: 'medium' });

    const effortIdx = args.indexOf('--effort');
    assert.notEqual(effortIdx, -1);
    assert.equal(args[effortIdx + 1], 'medium');
  });

  it('routes EPHEMERAL_MODEL_EXPLORER for explorer role when model is omitted', () => {
    setEnv('AGENT_CLI', 'agy');
    setEnv('EPHEMERAL_MODEL_EXPLORER', 'gemini-2.5-flash');
    const { buildCLICommand } = freshModules();
    const { args } = buildCLICommand('explore repo', { role: 'explorer' });

    const modelIdx = args.indexOf('--model');
    assert.notEqual(modelIdx, -1);
    assert.equal(args[modelIdx + 1], 'gemini-2.5-flash');
  });
});

// =============================================================================
// 3. Security & Role Permissions (--mode plan vs --dangerously-skip-permissions)
// =============================================================================

describe('agy buildCLICommand: role security & permissions', () => {
  it('enforces --mode plan for code_reviewer role even if autoApprove is true', () => {
    setEnv('AGENT_CLI', 'agy');
    const { buildCLICommand } = freshModules();
    const { args } = buildCLICommand('review code', { role: 'code_reviewer', autoApprove: true });

    assert.equal(args.includes('--mode'), true);
    assert.equal(args[args.indexOf('--mode') + 1], 'plan');
    assert.equal(args.includes('--dangerously-skip-permissions'), false);
  });

  it('enforces --mode plan for explorer role', () => {
    setEnv('AGENT_CLI', 'agy');
    const { buildCLICommand } = freshModules();
    const { args } = buildCLICommand('explore code', { role: 'explorer', autoApprove: true });

    assert.equal(args.includes('--mode'), true);
    assert.equal(args[args.indexOf('--mode') + 1], 'plan');
    assert.equal(args.includes('--dangerously-skip-permissions'), false);
  });

  it('enforces --mode plan for security_analyst role', () => {
    setEnv('AGENT_CLI', 'agy');
    const { buildCLICommand } = freshModules();
    const { args } = buildCLICommand('analyze vulns', { role: 'security_analyst', autoApprove: true });

    assert.equal(args.includes('--mode'), true);
    assert.equal(args[args.indexOf('--mode') + 1], 'plan');
    assert.equal(args.includes('--dangerously-skip-permissions'), false);
  });

  it('enforces --mode plan when AGENT_PERMISSION_MODE=plan', () => {
    setEnv('AGENT_CLI', 'agy');
    setEnv('AGENT_PERMISSION_MODE', 'plan');
    const { buildCLICommand } = freshModules();
    const { args } = buildCLICommand('develop fix', { role: 'developer', autoApprove: true });

    assert.equal(args.includes('--mode'), true);
    assert.equal(args[args.indexOf('--mode') + 1], 'plan');
    assert.equal(args.includes('--dangerously-skip-permissions'), false);
  });

  it('enforces --dangerously-skip-permissions for mutating roles when autoApprove is true', () => {
    setEnv('AGENT_CLI', 'agy');
    setEnv('AGENT_PERMISSION_MODE', undefined);
    const { buildCLICommand } = freshModules();
    const { args } = buildCLICommand('apply fix', { role: 'developer', autoApprove: true });

    assert.equal(args.includes('--dangerously-skip-permissions'), true);
    assert.equal(args.includes('--mode'), false);
  });
});

// =============================================================================
// 4. Conversation / Session Continuity
// =============================================================================

describe('agy buildCLICommand: conversation session tracking', () => {
  it('adds --conversation flag when conversationId is provided', () => {
    setEnv('AGENT_CLI', 'agy');
    const { buildCLICommand } = freshModules();
    const { args } = buildCLICommand('continue discussion', { conversationId: 'conv-xyz-789' });

    const convIdx = args.indexOf('--conversation');
    assert.notEqual(convIdx, -1);
    assert.equal(args[convIdx + 1], 'conv-xyz-789');
  });

  it('adds --conversation flag when sessionId is provided', () => {
    setEnv('AGENT_CLI', 'agy');
    const { buildCLICommand } = freshModules();
    const { args } = buildCLICommand('continue discussion', { sessionId: 'sess-abc-123' });

    const convIdx = args.indexOf('--conversation');
    assert.notEqual(convIdx, -1);
    assert.equal(args[convIdx + 1], 'sess-abc-123');
  });
});

// =============================================================================
// 5. Zero settings.json Mutation under agy
// =============================================================================

describe('agy buildCLICommand: settings.json immutability', () => {
  it('never mutates settings.json when running with agy', () => {
    setEnv('AGENT_CLI', 'agy');
    const { buildCLICommand, GEMINI_SETTINGS_PATH } = freshModules();

    let initialMtime = null;
    let initialContent = null;
    if (fs.existsSync(GEMINI_SETTINGS_PATH)) {
      initialMtime = fs.statSync(GEMINI_SETTINGS_PATH).mtimeMs;
      initialContent = fs.readFileSync(GEMINI_SETTINGS_PATH, 'utf8');
    }

    buildCLICommand('do work with agy', { effort: 'high', model: 'gemini-3.7-flash' });

    if (fs.existsSync(GEMINI_SETTINGS_PATH)) {
      const currentMtime = fs.statSync(GEMINI_SETTINGS_PATH).mtimeMs;
      const currentContent = fs.readFileSync(GEMINI_SETTINGS_PATH, 'utf8');
      assert.equal(currentMtime, initialMtime, 'settings.json mtime should not change under agy');
      assert.equal(currentContent, initialContent, 'settings.json content should not change under agy');
    }
  });
});

// =============================================================================
// 6. Session Recovery: isAgySessionError
// =============================================================================

describe('isAgySessionError recovery logic', () => {
  it('matches conversation not found warnings in stderr and output', (t) => {
    const modules = freshModules();
    if (typeof modules.isAgySessionError !== 'function') {
      t.skip('isAgySessionError not yet exported from cli-executor.js by parallel executor');
      return;
    }
    const { isAgySessionError } = modules;
    assert.equal(isAgySessionError(1, 'Warning: conversation not found', ''), true);
    assert.equal(isAgySessionError(1, '', 'Error: Conversation corrupt: invalid format'), true);
    assert.equal(isAgySessionError(1, 'conversation invalid', ''), true);
    assert.equal(isAgySessionError(0, '', 'All clear'), false);
    assert.equal(isAgySessionError(1, 'Rate limit 429 exceeded', ''), false);
  });
});

// =============================================================================
// 7. MCP Configuration: writeAgyMcpServer
// =============================================================================

describe('writeAgyMcpServer MCP configuration', () => {
  it('writes valid mcp_config.json at ~/.gemini/config/mcp_config.json', (t) => {
    const cliSetup = require(CLI_SETUP_PATH);
    if (typeof cliSetup.writeAgyMcpServer !== 'function') {
      t.skip('writeAgyMcpServer not yet implemented in cli-setup.js by parallel executor');
      return;
    }

    const testServerName = 'TestDarwinMCP';
    const testConfig = { command: 'node', args: ['/path/to/server.js'], env: { FOO: 'bar' } };

    cliSetup.writeAgyMcpServer(testServerName, testConfig);

    const mcpPath = path.join(os.homedir(), '.gemini', 'config', 'mcp_config.json');
    assert.equal(fs.existsSync(mcpPath), true, 'mcp_config.json must exist');

    const content = JSON.parse(fs.readFileSync(mcpPath, 'utf8'));
    assert.notEqual(content.mcpServers, undefined);
    assert.deepEqual(content.mcpServers[testServerName], testConfig);

    const stats = fs.statSync(mcpPath);
    assert.ok((stats.mode & 0o600) === 0o600, 'mcp_config.json must be read/write by owner');
  });
});

