// gemini-sidecar/tests/test_gemini_cli_parity.js
// @ai-rules:
// 1. [Constraint]: Test-only file -- verifies Gemini CLI feature-parity fixes in cli-executor.js
//    (buildCLICommand Gemini path) and the explorer timeout bump in config.js (evt-f99032dc).
// 2. [Pattern]: Uses node:test + node:assert, mirrors tests/test_credentials_multiorg.js's
//    freshRequire/setEnv/restoreEnv pattern since config.js snapshots AGENT_CLI/AGENT_MODEL/
//    AGENT_ROLE/AGENT_EFFORT_LEVEL from process.env at require time.
// 3. [Gotcha]: cli-executor.js destructures config.js's exports at require time, so both modules'
//    require.cache entries must be cleared together whenever AGENT_CLI/AGENT_MODEL/AGENT_ROLE/
//    AGENT_EFFORT_LEVEL env vars change between test cases.

const { describe, it, afterEach } = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

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

afterEach(() => {
  restoreEnv();
  delete require.cache[require.resolve(CONFIG_PATH)];
  delete require.cache[require.resolve(CLI_EXECUTOR_PATH)];
});

// =============================================================================
// Gemini path -- effort/--thinking mapping (Finding 1)
// =============================================================================

describe('Gemini buildCLICommand: --thinking effort mapping', () => {
  const cases = [
    ['low', 'none'],
    ['medium', 'low'],
    ['high', 'medium'],
    ['max', 'high'],
  ];

  for (const [effort, expectedThinking] of cases) {
    it(`maps effort="${effort}" -> --thinking ${expectedThinking}`, () => {
      setEnv('AGENT_CLI', 'gemini');
      const { buildCLICommand } = freshModules();
      const { binary, args } = buildCLICommand('do the thing', { effort });
      assert.equal(binary, 'gemini');
      const idx = args.indexOf('--thinking');
      assert.notEqual(idx, -1, '--thinking flag should be present');
      assert.equal(args[idx + 1], expectedThinking);
    });
  }

  it('falls back to the raw effort string for an unrecognized value', () => {
    setEnv('AGENT_CLI', 'gemini');
    const { buildCLICommand } = freshModules();
    const { args } = buildCLICommand('do the thing', { effort: 'unknown-level' });
    const idx = args.indexOf('--thinking');
    assert.notEqual(idx, -1);
    assert.equal(args[idx + 1], 'unknown-level');
  });

  it('omits --thinking entirely when no effort is set (options nor env)', () => {
    setEnv('AGENT_CLI', 'gemini');
    setEnv('AGENT_EFFORT_LEVEL', undefined);
    const { buildCLICommand } = freshModules();
    const { args } = buildCLICommand('do the thing', {});
    assert.equal(args.includes('--thinking'), false);
  });

  it('options.effort takes priority over AGENT_EFFORT_LEVEL env', () => {
    setEnv('AGENT_CLI', 'gemini');
    setEnv('AGENT_EFFORT_LEVEL', 'low');
    const { buildCLICommand } = freshModules();
    const { args } = buildCLICommand('do the thing', { effort: 'max' });
    const idx = args.indexOf('--thinking');
    assert.equal(args[idx + 1], 'high');
  });

  it('falls back to AGENT_EFFORT_LEVEL env when options.effort is not set', () => {
    setEnv('AGENT_CLI', 'gemini');
    setEnv('AGENT_EFFORT_LEVEL', 'high');
    const { buildCLICommand } = freshModules();
    const { args } = buildCLICommand('do the thing', {});
    const idx = args.indexOf('--thinking');
    assert.equal(args[idx + 1], 'medium');
  });
});

// =============================================================================
// Gemini path -- --verbose flag (Finding 2)
// =============================================================================

describe('Gemini buildCLICommand: --verbose flag', () => {
  it('includes --verbose alongside -o stream-json', () => {
    setEnv('AGENT_CLI', 'gemini');
    const { buildCLICommand } = freshModules();
    const { args } = buildCLICommand('probe the repo', {});
    assert.equal(args.includes('--verbose'), true);
    const oIdx = args.indexOf('-o');
    assert.notEqual(oIdx, -1);
    assert.equal(args[oIdx + 1], 'stream-json');
  });
});

// =============================================================================
// Gemini path -- model fallback chain (Finding 4)
// =============================================================================

describe('Gemini buildCLICommand: model fallback', () => {
  it('uses options.model when provided', () => {
    setEnv('AGENT_CLI', 'gemini');
    setEnv('AGENT_MODEL', 'gemini-2.5-pro');
    const { buildCLICommand } = freshModules();
    const { args } = buildCLICommand('x', { model: 'gemini-explicit' });
    const idx = args.indexOf('--model');
    assert.equal(args[idx + 1], 'gemini-explicit');
  });

  it('falls back to AGENT_MODEL env when options.model is absent', () => {
    setEnv('AGENT_CLI', 'gemini');
    setEnv('AGENT_MODEL', 'gemini-2.5-pro');
    const { buildCLICommand } = freshModules();
    const { args } = buildCLICommand('x', {});
    const idx = args.indexOf('--model');
    assert.equal(args[idx + 1], 'gemini-2.5-pro');
  });

  it('falls back to the hardcoded gemini-3.7-flash default when both are empty', () => {
    setEnv('AGENT_CLI', 'gemini');
    setEnv('AGENT_MODEL', undefined);
    setEnv('GEMINI_MODEL', undefined);
    const { buildCLICommand } = freshModules();
    const { args } = buildCLICommand('x', {});
    const idx = args.indexOf('--model');
    assert.notEqual(idx, -1, '--model should always be present now that a hardcoded fallback exists');
    assert.equal(args[idx + 1], 'gemini-3.7-flash');
  });
});

// =============================================================================
// Gemini path -- architect thinking-prefix (Finding 1, "Deep reasoning" row)
// =============================================================================

describe('Gemini buildCLICommand: architect thinking prefix', () => {
  it('prepends the reasoning prefix for role=architect', () => {
    setEnv('AGENT_CLI', 'gemini');
    const { buildCLICommand } = freshModules();
    const { args } = buildCLICommand('review the sidecar', { role: 'architect' });
    const promptIdx = args.indexOf('-p');
    assert.notEqual(promptIdx, -1);
    assert.equal(args[promptIdx + 1], 'Think step by step and reason deeply. review the sidecar');
  });

  it('does not add a prefix for non-architect roles', () => {
    setEnv('AGENT_CLI', 'gemini');
    const { buildCLICommand } = freshModules();
    const { args } = buildCLICommand('review the sidecar', { role: 'explorer' });
    const promptIdx = args.indexOf('-p');
    assert.equal(args[promptIdx + 1], 'review the sidecar');
  });

  it('falls back to AGENT_ROLE env for the prefix decision', () => {
    setEnv('AGENT_CLI', 'gemini');
    setEnv('AGENT_ROLE', 'architect');
    const { buildCLICommand } = freshModules();
    const { args } = buildCLICommand('review the sidecar', {});
    const promptIdx = args.indexOf('-p');
    assert.equal(args[promptIdx + 1], 'Think step by step and reason deeply. review the sidecar');
  });
});

// =============================================================================
// Gemini path -- other flags unaffected by the fix (regression coverage)
// =============================================================================

describe('Gemini buildCLICommand: unaffected flags still work', () => {
  it('still adds --yolo when autoApprove is set', () => {
    setEnv('AGENT_CLI', 'gemini');
    const { buildCLICommand } = freshModules();
    const { args } = buildCLICommand('x', { autoApprove: true });
    assert.equal(args[0], '--yolo');
  });

  it('still adds --resume when sessionId is set', () => {
    setEnv('AGENT_CLI', 'gemini');
    const { buildCLICommand } = freshModules();
    const { args } = buildCLICommand('x', { sessionId: 'sess-123' });
    const idx = args.indexOf('--resume');
    assert.notEqual(idx, -1);
    assert.equal(args[idx + 1], 'sess-123');
  });
});

// =============================================================================
// Claude path -- must remain unaffected by the Gemini-focused fix (regression)
// =============================================================================

describe('Claude buildCLICommand: unaffected by Gemini parity fix', () => {
  it('still uses --effort (not --thinking) and the claude-opus-4-6 fallback', () => {
    setEnv('AGENT_CLI', 'claude');
    setEnv('AGENT_MODEL', undefined);
    setEnv('GEMINI_MODEL', undefined);
    const { buildCLICommand } = freshModules();
    const { binary, args } = buildCLICommand('x', { effort: 'high' });
    assert.equal(binary, 'claude');
    assert.equal(args.includes('--thinking'), false);
    const effortIdx = args.indexOf('--effort');
    assert.notEqual(effortIdx, -1);
    assert.equal(args[effortIdx + 1], 'high');
    const modelIdx = args.indexOf('--model');
    assert.equal(args[modelIdx + 1], 'claude-opus-4-6');
  });

  it('still uses the ultrathink prefix for architect, not the Gemini prefix', () => {
    setEnv('AGENT_CLI', 'claude');
    const { buildCLICommand } = freshModules();
    const { args } = buildCLICommand('review', { role: 'architect' });
    const promptIdx = args.indexOf('-p');
    assert.equal(args[promptIdx + 1], 'ultrathink review');
  });
});

// =============================================================================
// config.js -- explorer timeout bump (Finding 3)
// =============================================================================

describe('resolveTimeoutMs: explorer timeout parity fix', () => {
  it('explorer resolves to 15 minutes (900000ms), not the old 10-minute value', () => {
    setEnv('TIMEOUT_MS', undefined);
    delete require.cache[require.resolve(CONFIG_PATH)];
    const { resolveTimeoutMs } = require(CONFIG_PATH);
    assert.equal(resolveTimeoutMs('explorer'), 900000);
  });

  it('other roles are untouched by the explorer-specific bump', () => {
    setEnv('TIMEOUT_MS', undefined);
    delete require.cache[require.resolve(CONFIG_PATH)];
    const { resolveTimeoutMs } = require(CONFIG_PATH);
    assert.equal(resolveTimeoutMs('developer'), 1800000);
    assert.equal(resolveTimeoutMs('code_reviewer'), 2700000);
  });

  it('an explicit TIMEOUT_MS env override still wins over the explorer ceiling', () => {
    setEnv('TIMEOUT_MS', '123000');
    delete require.cache[require.resolve(CONFIG_PATH)];
    const { resolveTimeoutMs } = require(CONFIG_PATH);
    assert.equal(resolveTimeoutMs('explorer'), 123000);
  });
});
