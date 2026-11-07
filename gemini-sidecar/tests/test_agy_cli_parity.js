// gemini-sidecar/tests/test_agy_cli_parity.js
// @ai-rules:
// 1. [Constraint]: Pure unit tests for cli-executor.js and cli-setup.js agy CLI parity — uses node:test + node:assert/strict.
// 2. [Pattern]: Sets AGENT_CLI=agy, clears require.cache between tests, restores environment.
// 4. [Coverage]: VMER-2271 operational gate through the REAL validate-mutations.sh + merge-guard.js against a loopback
//    /proxy/approval stub (async spawn: spawnSync would block the in-process stub server).
// 3. [Coverage]: Validates buildCLICommand agy path, flag order, effort normalization, mode plan security,
//    conversation persistence, writeAgyMcpServer, and isAgySessionError recovery.

const { describe, it, afterEach } = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');
const fs = require('fs');
const os = require('os');
const http = require('http');
const { spawn, spawnSync } = require('child_process');

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

  it('normalizes suffixed model names e.g. gemini-3.8-pro-max into model and effort', () => {
    setEnv('AGENT_CLI', 'agy');
    const { buildCLICommand } = freshModules();
    const { args } = buildCLICommand('test task', { model: 'gemini-3.8-pro-max' });

    const modelIdx = args.indexOf('--model');
    assert.notEqual(modelIdx, -1);
    assert.equal(args[modelIdx + 1], 'gemini-3.8-pro');

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
    const { args } = buildCLICommand('test task', { model: 'gemini-3.8-pro', effort: 'medium' });

    const effortIdx = args.indexOf('--effort');
    assert.notEqual(effortIdx, -1);
    assert.equal(args[effortIdx + 1], 'medium');
  });

  it('routes EPHEMERAL_MODEL_EXPLORER for explorer role when model is omitted', () => {
    setEnv('AGENT_CLI', 'agy');
    setEnv('EPHEMERAL_MODEL_EXPLORER', 'gemini-3.8-flash');
    const { buildCLICommand } = freshModules();
    const { args } = buildCLICommand('explore repo', { role: 'explorer' });

    const modelIdx = args.indexOf('--model');
    assert.notEqual(modelIdx, -1);
    assert.equal(args[modelIdx + 1], 'gemini-3.8-flash');
  });
});

// =============================================================================
// 3. Security & Role Permissions (--mode plan vs --dangerously-skip-permissions)
// =============================================================================

describe('agy buildCLICommand: autonomous execution permissions (no agent should be in plan mode)', () => {
  it('enforces --dangerously-skip-permissions and never --mode plan for code_reviewer role when autoApprove is true', () => {
    setEnv('AGENT_CLI', 'agy');
    const { buildCLICommand } = freshModules();
    const { args } = buildCLICommand('review code', { role: 'code_reviewer', autoApprove: true });

    assert.equal(args.includes('--dangerously-skip-permissions'), true);
    assert.equal(args.includes('--mode'), false);
  });

  it('enforces --dangerously-skip-permissions and never --mode plan for explorer role when autoApprove is true', () => {
    setEnv('AGENT_CLI', 'agy');
    const { buildCLICommand } = freshModules();
    const { args } = buildCLICommand('explore code', { role: 'explorer', autoApprove: true });

    assert.equal(args.includes('--dangerously-skip-permissions'), true);
    assert.equal(args.includes('--mode'), false);
  });

  it('enforces --dangerously-skip-permissions and never --mode plan for security_analyst role when autoApprove is true', () => {
    setEnv('AGENT_CLI', 'agy');
    const { buildCLICommand } = freshModules();
    const { args } = buildCLICommand('analyze vulns', { role: 'security_analyst', autoApprove: true });

    assert.equal(args.includes('--dangerously-skip-permissions'), true);
    assert.equal(args.includes('--mode'), false);
  });

  it('never sets --mode plan even if AGENT_PERMISSION_MODE was set when autoApprove is true', () => {
    setEnv('AGENT_CLI', 'agy');
    setEnv('AGENT_PERMISSION_MODE', 'plan');
    const { buildCLICommand } = freshModules();
    const { args } = buildCLICommand('develop fix', { role: 'developer', autoApprove: true });

    assert.equal(args.includes('--dangerously-skip-permissions'), true);
    assert.equal(args.includes('--mode'), false);
  });

  it('matches role regardless of casing (e.g. Code_Reviewer) without plan mode', () => {
    setEnv('AGENT_CLI', 'agy');
    const { buildCLICommand } = freshModules();
    const { args } = buildCLICommand('review code changes', { role: 'Code_Reviewer', autoApprove: true });

    assert.equal(args.includes('--dangerously-skip-permissions'), true);
    assert.equal(args.includes('--mode'), false);
  });

  it('enforces --dangerously-skip-permissions for mutating roles when autoApprove is true', () => {
    setEnv('AGENT_CLI', 'agy');
    setEnv('AGENT_PERMISSION_MODE', undefined);
    const { buildCLICommand } = freshModules();
    const { args } = buildCLICommand('apply fix', { role: 'developer', autoApprove: true });

    assert.equal(args.includes('--dangerously-skip-permissions'), true);
    assert.equal(args.includes('--mode'), false);
  });

  it('omits --dangerously-skip-permissions when autoApprove is false and never enters plan mode', () => {
    setEnv('AGENT_CLI', 'agy');
    setEnv('AGENT_PERMISSION_MODE', undefined);
    const { buildCLICommand } = freshModules();
    const { args } = buildCLICommand('apply fix', { role: 'developer', autoApprove: false });

    assert.equal(args.includes('--dangerously-skip-permissions'), false);
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

  it('executeCLIStreaming forwards conversationId to buildCLICommand', async (t) => {
    setEnv('AGENT_CLI', 'agy');
    const cp = require('child_process');
    const { EventEmitter } = require('events');
    const modules = freshModules();
    const { executeCLIStreaming } = modules;

    let capturedArgs = null;
    t.mock.method(cp, 'spawn', (cmd, args) => {
      capturedArgs = args;
      const child = new EventEmitter();
      child.stdout = new EventEmitter();
      child.stderr = new EventEmitter();
      setTimeout(() => {
        child.stdout.emit('data', Buffer.from(JSON.stringify({ event: 'result', result: { status: 'SUCCESS' } }) + '\n'));
        child.emit('close', 0);
      }, 10);
      return child;
    });

    const mockWs = { send: () => {} };
    await executeCLIStreaming(mockWs, 'evt-123', 'hello agy', { conversationId: 'conv-fwd-456' });

    assert.ok(capturedArgs, 'spawn must be called');
    const convIdx = capturedArgs.indexOf('--conversation');
    assert.notEqual(convIdx, -1, '--conversation must be passed to spawned CLI');
    assert.equal(capturedArgs[convIdx + 1], 'conv-fwd-456');
  });
});

// =============================================================================
// 5. Session Recovery: isAgySessionError (agy only, stderr only)
// =============================================================================

describe('isAgySessionError recovery logic', () => {
  it('matches conversation not found / corrupt / invalid in STDERR under agy', () => {
    setEnv('AGENT_CLI', 'agy');
    const { isAgySessionError } = freshModules();
    assert.equal(isAgySessionError(1, 'Warning: conversation not found'), true);
    assert.equal(isAgySessionError(1, 'Error: Conversation corrupt: invalid format'), true);
    assert.equal(isAgySessionError(1, 'conversation invalid'), true);
    assert.equal(isAgySessionError(0, ''), false);
    assert.equal(isAgySessionError(1, 'Rate limit 429 exceeded'), false);
  });

  it('ignores model output: a third `output` argument can no longer trigger a match', () => {
    setEnv('AGENT_CLI', 'agy');
    const { isAgySessionError } = freshModules();
    assert.equal(isAgySessionError(1, '', 'Error: Conversation corrupt: invalid format'), false);
  });

  it('is false outside agy', () => {
    setEnv('AGENT_CLI', 'claude');
    const { isAgySessionError } = freshModules();
    assert.equal(isAgySessionError(1, 'conversation not found'), false);
  });
});

// =============================================================================
// 7. MCP Configuration: writeAgyMcpServer (isolated HOME, gated on AGENT_CLI=agy)
// =============================================================================

function withTempHome(fn) {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'agy-home-'));
  setEnv('HOME', home);
  try {
    // cli-setup computes AGY_MCP_PATH from os.homedir() at load -- drop caches so it sees the temp HOME.
    delete require.cache[require.resolve(CONFIG_PATH)];
    delete require.cache[require.resolve(CLI_SETUP_PATH)];
    return fn(home, require(CLI_SETUP_PATH));
  } finally {
    fs.rmSync(home, { recursive: true, force: true });
  }
}

describe('writeAgyMcpServer MCP configuration', () => {
  it('writes valid 0600 mcp_config.json under ~/.gemini/config when AGENT_CLI=agy', () => {
    setEnv('AGENT_CLI', 'agy');
    withTempHome((home, cliSetup) => {
      const testConfig = { command: 'node', args: ['/path/to/server.js'], env: { FOO: 'bar' } };
      cliSetup.writeAgyMcpServer('TestDarwinMCP', testConfig);

      const mcpPath = path.join(home, '.gemini', 'config', 'mcp_config.json');
      assert.equal(fs.existsSync(mcpPath), true, 'mcp_config.json must exist');
      const content = JSON.parse(fs.readFileSync(mcpPath, 'utf8'));
      assert.deepEqual(content.mcpServers.TestDarwinMCP, testConfig);
      assert.equal(fs.statSync(mcpPath).mode & 0o777, 0o600);
    });
  });

  it('preserves existing servers when adding another', () => {
    setEnv('AGENT_CLI', 'agy');
    withTempHome((home, cliSetup) => {
      cliSetup.writeAgyMcpServer('A', { command: 'a' });
      cliSetup.writeAgyMcpServer('B', { command: 'b' });
      const content = JSON.parse(fs.readFileSync(path.join(home, '.gemini', 'config', 'mcp_config.json'), 'utf8'));
      assert.deepEqual(Object.keys(content.mcpServers).sort(), ['A', 'B']);
    });
  });

  for (const cli of ['claude']) {
    it(`writes NOTHING (no plaintext credential file) when AGENT_CLI=${cli}`, () => {
      setEnv('AGENT_CLI', cli);
      withTempHome((home, cliSetup) => {
        cliSetup.writeAgyMcpServer('GitHub', { command: 'gh-mcp', env: { GITHUB_TOKEN: 'secret' } });
        assert.equal(fs.existsSync(path.join(home, '.gemini', 'config', 'mcp_config.json')), false);
        assert.equal(fs.existsSync(path.join(home, '.gemini', 'config')), false);
      });
    });
  }

  it('rejects prototype-polluting server names', () => {
    setEnv('AGENT_CLI', 'agy');
    withTempHome((home, cliSetup) => {
      cliSetup.writeAgyMcpServer('__proto__', { command: 'x' });
      assert.equal(fs.existsSync(path.join(home, '.gemini', 'config', 'mcp_config.json')), false);
    });
  });

  it('corrects a swapped or rogue fallback symlink in ~/.gemini/antigravity', () => {
    setEnv('AGENT_CLI', 'agy');
    withTempHome((home, cliSetup) => {
      const fallbackDir = path.join(home, '.gemini', 'antigravity');
      fs.mkdirSync(fallbackDir, { recursive: true });
      const fallbackLink = path.join(fallbackDir, 'mcp_config.json');
      const rogueTarget = path.join(home, 'rogue_mcp.json');
      fs.writeFileSync(rogueTarget, '{}');
      fs.symlinkSync(rogueTarget, fallbackLink);

      cliSetup.writeAgyMcpServer('SafeServer', { command: 'node' });

      assert.equal(fs.lstatSync(fallbackLink).isSymbolicLink(), true);
      const target = fs.readlinkSync(fallbackLink);
      assert.equal(target, path.join(home, '.gemini', 'config', 'mcp_config.json'));
    });
  });
});

describe('writeClaudeMcpServer MCP configuration', () => {
  it('writes valid 0600 .claude.json under HOME and tightens existing weaker permissions', () => {
    withTempHome((home, cliSetup) => {
      const claudePath = path.join(home, '.claude.json');
      fs.writeFileSync(claudePath, JSON.stringify({ mcpServers: { Existing: { command: 'prev' } } }), { mode: 0o644 });
      assert.equal(fs.statSync(claudePath).mode & 0o777, 0o644);

      cliSetup.writeClaudeMcpServer('TestClaudeMCP', { command: 'node', args: ['/path/to/server.js'] });

      assert.equal(fs.existsSync(claudePath), true);
      const content = JSON.parse(fs.readFileSync(claudePath, 'utf8'));
      assert.equal(content.mcpServers.Existing.command, 'prev');
      assert.equal(content.mcpServers.TestClaudeMCP.command, 'node');
      assert.equal(fs.statSync(claudePath).mode & 0o777, 0o600, '.claude.json must be 0600 mode');
    });
  });

  it('rejects prototype-polluting server names for Claude', () => {
    withTempHome((home, cliSetup) => {
      const claudePath = path.join(home, '.claude.json');
      cliSetup.writeClaudeMcpServer('__proto__', { command: 'x' });
      assert.equal(fs.existsSync(claudePath), false);
      cliSetup.writeClaudeMcpServer('constructor', { command: 'x' });
      assert.equal(fs.existsSync(claudePath), false);
    });
  });
});

// =============================================================================
// 8. resolveModel routing and role fallback
// =============================================================================

describe('resolveModel routing and role fallback', () => {
  it('picks up EPHEMERAL_MODEL_EXPLORER when process.env.AGENT_ROLE is explorer', () => {
    setEnv('AGENT_CLI', 'agy');
    setEnv('AGENT_ROLE', 'explorer');
    setEnv('EPHEMERAL_MODEL_EXPLORER', 'gemini-3.8-flash-explorer-custom');
    const { resolveModel } = freshModules();

    const selected = resolveModel({}, 'agy');
    assert.equal(selected, 'gemini-3.8-flash-explorer-custom');
  });

  it('picks up EPHEMERAL_MODEL_EXPLORER when options.role is Explorer (case-insensitive)', () => {
    setEnv('AGENT_CLI', 'agy');
    setEnv('AGENT_ROLE', undefined);
    setEnv('EPHEMERAL_MODEL_EXPLORER', 'gemini-3.8-flash-explorer-custom');
    const { resolveModel } = freshModules();

    const selected = resolveModel({ role: 'Explorer' }, 'agy');
    assert.equal(selected, 'gemini-3.8-flash-explorer-custom');
  });

  it('falls back to gemini-3.8-flash for agy when no AGENT_MODEL or role override is set', () => {
    setEnv('AGENT_CLI', 'agy');
    setEnv('AGENT_ROLE', undefined);
    setEnv('AGENT_MODEL', undefined);
    setEnv('EPHEMERAL_MODEL_EXPLORER', undefined);
    const { resolveModel } = freshModules();

    const selected = resolveModel({}, 'agy');
    assert.equal(selected, 'gemini-3.8-flash');
  });
});

// =============================================================================
// 9. writeAgyHooks Hook Configuration
// =============================================================================

describe('writeAgyHooks Hook configuration', () => {
  it('writes valid 0600 hooks.json under ~/.gemini/config with PreToolUse and Stop hooks', () => {
    setEnv('AGENT_CLI', 'agy');
    withTempHome((home, cliSetup) => {
      cliSetup.writeAgyHooks();

      const hooksPath = path.join(home, '.gemini', 'config', 'hooks.json');
      assert.equal(fs.existsSync(hooksPath), true, 'hooks.json must exist');
      const content = JSON.parse(fs.readFileSync(hooksPath, 'utf8'));

      assert.equal(Array.isArray(content['validate-mutations']?.PreToolUse), true);
      assert.equal(content['validate-mutations'].PreToolUse[0].matcher, '*');
      assert.equal(content['validate-mutations'].PreToolUse[0].hooks[0].command, '/app/hooks/validate-mutations.sh');

      assert.equal(Array.isArray(content['require-results']?.Stop), true);
      assert.equal(content['require-results'].Stop[0].command, '/app/hooks/require-results.sh');

      assert.equal(Array.isArray(content['cluster-context']?.SessionStart), true);
      assert.equal(content['cluster-context'].SessionStart[0].matcher, '*');
      assert.equal(content['cluster-context'].SessionStart[0].hooks[0].command, '/app/hooks/cluster-context.sh');

      assert.equal(Array.isArray(content['team-inbox']?.SessionStart), true);
      assert.equal(content['team-inbox'].SessionStart[0].matcher, '*');
      assert.equal(content['team-inbox'].SessionStart[0].hooks[0].command, '/app/hooks/check-inbox.sh');

      assert.equal(Array.isArray(content['team-inbox']?.PostToolUse), true);
      assert.equal(content['team-inbox'].PostToolUse[0].matcher, '*');
      assert.equal(content['team-inbox'].PostToolUse[0].hooks[0].command, '/app/hooks/check-inbox.sh');

      assert.equal(fs.statSync(hooksPath).mode & 0o777, 0o600, 'hooks.json must be 0600 mode');
    });
  });

  it('preserves existing hooks when updating', () => {
    setEnv('AGENT_CLI', 'agy');
    withTempHome((home, cliSetup) => {
      const hooksPath = path.join(home, '.gemini', 'config', 'hooks.json');
      fs.mkdirSync(path.dirname(hooksPath), { recursive: true });
      fs.writeFileSync(hooksPath, JSON.stringify({ customHook: { PreToolUse: [] } }), { mode: 0o600 });

      cliSetup.writeAgyHooks();

      const content = JSON.parse(fs.readFileSync(hooksPath, 'utf8'));
      assert.notEqual(content.customHook, undefined);
      assert.notEqual(content['validate-mutations'], undefined);
      assert.notEqual(content['require-results'], undefined);
    });
  });

  for (const cli of ['claude']) {
    it(`does not write agy hooks.json when AGENT_CLI=${cli}`, () => {
      setEnv('AGENT_CLI', cli);
      withTempHome((home, cliSetup) => {
        cliSetup.writeAgyHooks();
        assert.equal(fs.existsSync(path.join(home, '.gemini', 'config', 'hooks.json')), false);
      });
    });
  }

  it('registerMCPsAndHooks registers hooks when cli === "agy"', () => {
    setEnv('AGENT_CLI', 'agy');
    withTempHome((home, cliSetup) => {
      cliSetup.registerMCPsAndHooks({}, 'agy');
      const hooksPath = path.join(home, '.gemini', 'config', 'hooks.json');
      assert.equal(fs.existsSync(hooksPath), true);
    });
  });
});

// =============================================================================
// 10. getRetryOptions model fallback and retry bounds
// =============================================================================

describe('getRetryOptions retry bounding and model fallback', () => {
  it('returns null if _retryCount is >= 1 (bounded to 1 retry)', () => {
    const { getRetryOptions } = freshModules();
    const result = getRetryOptions(
      { _retriedModel: true, _retryCount: 1, role: 'explorer' },
      1,
      'Model not found: gemini-custom',
      'agy'
    );
    assert.equal(result, null);
  });

  it('falls back to claude-sonnet-5-5 under claude CLI even for explorer role', () => {
    const { getRetryOptions } = freshModules();
    const result = getRetryOptions(
      { role: 'explorer', model: 'invalid-model' },
      1,
      'Model not found: invalid-model',
      'claude'
    );
    assert.notEqual(result, null);
    assert.equal(result.options.model, 'claude-sonnet-5-5');
    assert.equal(result.options._retriedModel, true);
    assert.equal(result.options._retryCount, 1);
  });

  it('falls back to gemini-3.8-flash under agy CLI for explorer role', () => {
    const { getRetryOptions } = freshModules();
    const result = getRetryOptions(
      { role: 'explorer', model: 'invalid-model' },
      1,
      'Model not found: invalid-model',
      'agy'
    );
    assert.notEqual(result, null);
    assert.equal(result.options.model, 'gemini-3.8-flash');
    assert.equal(result.options._retriedModel, true);
    assert.equal(result.options._retryCount, 1);
  });
});

// =============================================================================
// 11. Antigravity PreToolUse and Stop hook protocol contract validation
// =============================================================================

describe('Antigravity PreToolUse and Stop hook protocol contract validation', () => {
  const hooksDir = path.resolve(__dirname, '..', 'hooks');

  it('validate-mutations.sh emits decision: "deny" (not "block") for agy on prohibited tool calls', () => {
    const hookPath = path.join(hooksDir, 'validate-mutations.sh');
    const input = JSON.stringify({
      toolCall: {
        name: 'run_command',
        args: { CommandLine: 'git commit -m "prohibited commit"' }
      }
    });

    const res = spawnSync('bash', [hookPath], {
      input,
      env: { ...process.env, AGENT_ROLE: 'explorer', AGENT_CLI: 'agy' },
      encoding: 'utf8'
    });

    assert.equal(res.status, 0, 'hook script must exit 0');
    const payload = JSON.parse(res.stdout);
    // Antigravity PreToolUse contract: decision must be 'deny' | 'allow' | 'ask' | 'force_ask'
    assert.equal(payload.decision, 'deny', 'agy requires decision: "deny", never "block"');
    assert.notEqual(payload.decision, 'block', 'Gemini "block" string breaks agy parser');
    assert.ok(payload.reason && payload.reason.length > 0, 'reason string must be non-empty');
  });

  it('validate-mutations.sh emits decision: "deny" for unapproved merge attempts regardless of role', () => {
    const hookPath = path.join(hooksDir, 'validate-mutations.sh');
    const input = JSON.stringify({
      toolCall: {
        name: 'run_command',
        args: { CommandLine: 'git push origin main' }
      }
    });

    const res = spawnSync('bash', [hookPath], {
      input,
      env: { ...process.env, AGENT_ROLE: 'developer', AGENT_CLI: 'agy' },
      encoding: 'utf8'
    });

    assert.equal(res.status, 0);
    const payload = JSON.parse(res.stdout);
    assert.equal(payload.decision, 'deny', 'unapproved merge attempt must be denied');
    assert.ok(payload.reason.includes('Merge REFUSED'), 'reason must state merge refusal');
  });

  it('validate-mutations.sh emits decision: "deny" when role developer attempts operational mutation (kargo promote)', () => {
    const hookPath = path.join(hooksDir, 'validate-mutations.sh');
    const input = JSON.stringify({
      toolCall: {
        name: 'run_command',
        args: { CommandLine: 'kargo promote --project myproj --freight foo' }
      }
    });

    const res = spawnSync('bash', [hookPath], {
      input,
      env: { ...process.env, AGENT_ROLE: 'developer', AGENT_CLI: 'agy', DARWIN_WORK_STYLE: 'autonomous' },
      encoding: 'utf8'
    });

    assert.equal(res.status, 0);
    const payload = JSON.parse(res.stdout);
    assert.equal(payload.decision, 'deny', 'mutating operational action must be denied for non-sysadmin developer');
    assert.ok(
      payload.reason.includes("Role 'developer' is not authorized for operational mutations; sysadmin required."),
      `expected role restriction reason, got: ${payload.reason}`
    );
  });

  it('validate-mutations.sh emits decision: "deny" when role architect attempts kargo promote', () => {
    const hookPath = path.join(hooksDir, 'validate-mutations.sh');
    const input = JSON.stringify({
      toolCall: {
        name: 'run_command',
        args: { CommandLine: 'kargo promote --project myproj --freight foo' }
      }
    });

    const res = spawnSync('bash', [hookPath], {
      input,
      env: { ...process.env, AGENT_ROLE: 'architect', AGENT_CLI: 'agy', DARWIN_WORK_STYLE: 'autonomous' },
      encoding: 'utf8'
    });

    assert.equal(res.status, 0);
    const payload = JSON.parse(res.stdout);
    assert.equal(payload.decision, 'deny', 'kargo promote must be denied for read-only architect');
    assert.match(
      payload.reason,
      /Operational mutation REFUSED: Role 'architect' is not authorized for operational mutations; sysadmin required\./,
      `architect must be rejected by the operational role gate (not just any mutation block), got: ${payload.reason}`
    );
  });

  it('validate-mutations.sh fails closed with decision: "deny" when classifier returns unparseable field 3', () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'darwin-agy-parity-'));
    try {
      const mockHook = path.join(tmpDir, 'validate-mutations.sh');
      const hookPath = path.join(hooksDir, 'validate-mutations.sh');
      fs.copyFileSync(hookPath, mockHook);
      const mockClassifier = path.join(tmpDir, 'merge-guard.js');
      fs.writeFileSync(mockClassifier, '#!/usr/bin/env node\nprocess.stdout.write("OK|||view_file|||invalid_token|||1|||");\n', { mode: 0o755 });

      const input = JSON.stringify({
        toolCall: {
          name: 'view_file',
          args: { AbsolutePath: '/tmp/test' }
        }
      });

      const res = spawnSync('bash', [mockHook], {
        input,
        env: { ...process.env, AGENT_ROLE: 'developer', AGENT_CLI: 'agy', DARWIN_WORK_STYLE: 'autonomous' },
        encoding: 'utf8'
      });

      assert.equal(res.status, 0);
      const payload = JSON.parse(res.stdout);
      assert.equal(payload.decision, 'deny', 'unparseable classifier output must fail closed with decision: deny');
      assert.ok(
        payload.reason.includes('unparseable guard category from classifier'),
        `expected unparseable classifier reason, got: ${payload.reason}`
      );
    } finally {
      fs.rmSync(tmpDir, { recursive: true, force: true });
    }
  });

  it('require-results.sh emits decision: "continue" (not "block") for agy Stop hook when results missing', () => {
    const hookPath = path.join(hooksDir, 'require-results.sh');
    const testPort = '19090';
    const counterDir = `/tmp/.darwin-hooks-${process.getuid ? process.getuid() : 1001}`;
    const counterFile = path.join(counterDir, `require-results-${testPort}-default.count`);
    try { fs.rmSync(counterFile, { force: true }); } catch {}
    const input = JSON.stringify({
      type: 'Stop',
      messages: [{ content: 'just wrapping up' }]
    });

    try {
      const res = spawnSync('bash', [hookPath], {
        input,
        env: { ...process.env, AGENT_CLI: 'agy', SIDECAR_PORT: testPort },
        encoding: 'utf8'
      });

      assert.equal(res.status, 0);
      const payload = JSON.parse(res.stdout);
      // Antigravity Stop hook contract: decision must be 'continue' to keep agent running
      assert.equal(payload.decision, 'continue', 'agy Stop hook requires decision: "continue"');
      assert.notEqual(payload.decision, 'block', 'Gemini "block" string breaks agy parser');
    } finally {
      try { fs.rmSync(counterFile, { force: true }); } catch {}
    }
  });

  const hasAgy = Boolean(process.env.AGY_INTEGRATION_TEST) && (() => {
    try {
      const res = spawnSync('which', ['agy']);
      return res.status === 0;
    } catch {
      return false;
    }
  })();

  (hasAgy ? it : it.skip)('real agy binary enforces decision: deny and halts command execution under --dangerously-skip-permissions', () => {
    withTempHome((home, cliSetup) => {
      cliSetup.writeAgyHooks(hooksDir);
      const targetFile = path.join(home, 'should_never_be_created.txt');
      const env = {
        ...process.env,
        HOME: home,
        AGENT_ROLE: 'explorer',
        AGENT_CLI: 'agy'
      };
      const res = spawnSync('agy', ['--dangerously-skip-permissions', '-p', `run_command to create file with touch ${targetFile}`], {
        env,
        cwd: home,
        timeout: 15000,
        encoding: 'utf8'
      });
      assert.equal(fs.existsSync(targetFile), false, 'target file must NOT be created when hook returns decision: deny');
      assert.ok(
        (res.stdout || '').includes('tool call denied by pre-tool hook') ||
        (res.stdout || '').includes('denied') ||
        (res.stdout || '').includes('blocked'),
        'agy stdout should reflect hook denial'
      );
    });
  });
});


describe('VMER-2271: validate-mutations.sh operational gate (NEEDS_GUARD=2) against a loopback /proxy/approval', () => {
  const hookPath = path.resolve(__dirname, '..', 'hooks', 'validate-mutations.sh');
  const shInput = (CommandLine) => JSON.stringify({ toolCall: { name: 'run_command', args: { CommandLine } } });
  const mcpInput = (name) => JSON.stringify({ toolCall: { name, args: {} } });
  const OP_APPROVED = { approved: true, approved_mr_sha: null, approved_by: 'maintainer' };

  // Starts a stub Brain-side /proxy/approval. body === undefined => do not start one (proxy down: connection refused on port 1).
  function startApprovalStub(body) {
    if (body === undefined) return Promise.resolve({ port: 1, close: () => {} });
    return new Promise((resolve) => {
      const srv = http.createServer((req, res) => {
        if (req.url === '/proxy/approval') {
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(typeof body === 'string' ? body : JSON.stringify(body));
        } else { res.writeHead(404); res.end(); }
      });
      srv.listen(0, '127.0.0.1', () => resolve({ port: srv.address().port, close: () => srv.close() }));
    });
  }

  function runHook(input, { role, port, env = {} }) {
    return new Promise((resolve, reject) => {
      const child = spawn('bash', [hookPath], {
        env: { ...process.env, AGENT_ROLE: role, AGENT_CLI: 'agy', DARWIN_WORK_STYLE: 'autonomous', SIDECAR_PORT: String(port), ...env },
        stdio: ['pipe', 'pipe', 'ignore'],
      });
      let out = '';
      child.stdout.on('data', (c) => { out += c; });
      child.on('error', reject);
      child.on('close', (code) => { try { resolve({ code, payload: JSON.parse(out) }); } catch (e) { reject(new Error(`unparseable hook output: ${out}`)); } });
      child.stdin.end(input);
    });
  }

  async function withStub(body, fn) {
    const stub = await startApprovalStub(body);
    try { return await fn(stub.port); } finally { stub.close(); }
  }

  it('sysadmin + operational + approved:true => allow', async () => {
    await withStub(OP_APPROVED, async (port) => {
      const { code, payload } = await runHook(shInput('kubectl delete pod x'), { role: 'sysadmin', port });
      assert.equal(code, 0);
      assert.equal(payload.decision, 'allow');
    });
  });

  it('sysadmin + operational + approved:false => deny with operational wording', async () => {
    await withStub({ approved: false }, async (port) => {
      const { payload } = await runHook(shInput('kubectl delete pod x'), { role: 'sysadmin', port });
      assert.equal(payload.decision, 'deny');
      assert.match(payload.reason, /Operational mutation REFUSED/);
      assert.doesNotMatch(payload.reason, /^Merge REFUSED/);
    });
  });

  it('sysadmin + operational + proxy down => deny (fail closed)', async () => {
    await withStub(undefined, async (port) => {
      const { payload } = await runHook(shInput('kubectl delete pod x'), { role: 'sysadmin', port });
      assert.equal(payload.decision, 'deny');
      assert.match(payload.reason, /Operational mutation REFUSED/);
    });
  });

  it('truthy non-boolean `approved` ("false", "true", 1) and garbage bodies are denied', async () => {
    for (const body of [{ approved: 'false' }, { approved: 'true' }, { approved: 1 }, {}, 'not-json', '[]', 'null']) {
      await withStub(body, async (port) => {
        const { payload } = await runHook(shInput('kubectl delete pod x'), { role: 'sysadmin', port });
        assert.equal(payload.decision, 'deny', `body=${JSON.stringify(body)}`);
      });
    }
  });

  it('role gate runs before approval: developer/qe/architect denied even with a valid approval; Sysadmin (case) allowed', async () => {
    await withStub(OP_APPROVED, async (port) => {
      for (const role of ['developer', 'qe', 'architect', 'explorer', 'sysadmin2']) {
        const { payload } = await runHook(shInput('kubectl delete pod x'), { role, port });
        assert.equal(payload.decision, 'deny', role);
        assert.match(payload.reason, new RegExp(`Role '${role}' is not authorized for operational mutations; sysadmin required\\.`), role);
      }
      for (const role of ['Sysadmin', ' SYSADMIN ']) {
        const { payload } = await runHook(shInput('kubectl delete pod x'), { role, port });
        assert.equal(payload.decision, 'allow', `role ${JSON.stringify(role)} normalises to sysadmin`);
      }
    });
  });

  it('a hostile role (quote/backslash) is JSON-escaped in the deny and cannot break the document', async () => {
    await withStub(OP_APPROVED, async (port) => {
      const role = 'dev"x\\y';
      const { payload } = await runHook(shInput('kubectl delete pod x'), { role, port });
      assert.equal(payload.decision, 'deny');
      assert.ok(payload.reason.includes(role), `escaped role must round-trip, got: ${payload.reason}`);
    });
  });

  it('valued-flag, dynamic-verb and previously-unlisted verbs hit the operational gate', async () => {
    const cmds = ['kubectl -v 6 exec -it prodpod -- /bin/sh', 'kubectl --request-timeout 5s delete pod x', 'kubectl $VERB pod x',
      'kargo --config-path /x promote --stage s', 'kubectl label pod x a=b', 'oc adm drain n', 'argocd app rollback a 1', 'helm repo add x y'];
    await withStub({ approved: false }, async (port) => {
      for (const c of cmds) {
        const { payload } = await runHook(shInput(c), { role: 'sysadmin', port });
        assert.equal(payload.decision, 'deny', `unapproved: ${c}`);
        assert.match(payload.reason, /Operational mutation REFUSED/, c);
      }
    });
    await withStub(OP_APPROVED, async (port) => {
      for (const c of cmds) {
        const { payload } = await runHook(shInput(c), { role: 'sysadmin', port });
        assert.equal(payload.decision, 'allow', `approved: ${c}`);
      }
    });
  });

  it('read-only operational verbs are not guarded: allowed with an unapproved event and with the proxy down', async () => {
    const cmds = ['kubectl get pods -A', 'kubectl rollout status deploy/x', 'helm list', 'argocd app get a', 'kargo get stages'];
    for (const body of [{ approved: false }, undefined]) {
      await withStub(body, async (port) => {
        for (const c of cmds) {
          const { payload } = await runHook(shInput(c), { role: 'sysadmin', port });
          assert.equal(payload.decision, 'allow', c);
        }
      });
    }
  });

  it('MCP cluster writes: sysadmin approved allow / unapproved deny; developer role-denied; ArgoCD reads allowed for architect', async () => {
    await withStub(OP_APPROVED, async (port) => {
      assert.equal((await runHook(mcpInput('mcp__ArgoCD__sync_application'), { role: 'sysadmin', port })).payload.decision, 'allow');
      const dev = (await runHook(mcpInput('mcp__ArgoCD__sync_application'), { role: 'developer', port })).payload;
      assert.equal(dev.decision, 'deny');
      assert.match(dev.reason, /sysadmin required/);
    });
    await withStub({ approved: false }, async (port) => {
      const un = (await runHook(mcpInput('mcp__ArgoCD__sync_application'), { role: 'sysadmin', port })).payload;
      assert.equal(un.decision, 'deny');
      assert.match(un.reason, /Operational mutation REFUSED/);
      assert.equal((await runHook(mcpInput('mcp__ArgoCD__get_application'), { role: 'architect', port })).payload.decision, 'allow');
    });
  });

  it('sysadmin + git merge with an operational-only approval (approved_mr_sha=null) is denied: git_merge keeps the SHA binding', async () => {
    await withStub(OP_APPROVED, async (port) => {
      for (const c of ['git merge origin/main', 'gh pr merge 5', 'git push origin main', 'kubectl delete pod x && git merge origin/main',
        'find . -exec oc rsh x \\; -exec git merge origin/main \\;', 'find . -exec git merge origin/main \\; -exec oc rsh x \\;',
        'find . -exec oc rsh x \\; -exec gh pr merge 5 \\;']) {
        const { payload } = await runHook(shInput(c), { role: 'sysadmin', port });
        assert.equal(payload.decision, 'deny', c);
        assert.match(payload.reason, /Merge REFUSED/, c);
      }
    });
  });

  it('operational gate is budget-safe: an exhausted hook budget denies instead of falling through', async () => {
    await withStub(OP_APPROVED, async (port) => {
      const { payload } = await runHook(shInput('kubectl delete pod x'), { role: 'sysadmin', port, env: { HOOK_BUDGET_SEC: '0' } });
      assert.equal(payload.decision, 'deny');
      assert.match(payload.reason, /budget exhausted/);
    });
  });

  it('guard code outside 0/1/2 (e.g. 3 or "1|2") is denied as an unparseable category', () => {
    for (const code of ['3', '12', 'x', '']) {
      const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'darwin-agy-guardcode-'));
      try {
        fs.copyFileSync(hookPath, path.join(tmpDir, 'validate-mutations.sh'));
        fs.writeFileSync(path.join(tmpDir, 'merge-guard.js'), `process.stdout.write("OK|||view_file|||${code}|||1|||");\n`);
        const res = spawnSync('bash', [path.join(tmpDir, 'validate-mutations.sh')], {
          input: JSON.stringify({ toolCall: { name: 'view_file', args: {} } }),
          env: { ...process.env, AGENT_ROLE: 'developer', AGENT_CLI: 'agy', DARWIN_WORK_STYLE: 'autonomous', SIDECAR_PORT: '1' }, encoding: 'utf8',
        });
        const payload = JSON.parse(res.stdout);
        assert.equal(payload.decision, 'deny', `guard code ${JSON.stringify(code)}`);
      } finally { fs.rmSync(tmpDir, { recursive: true, force: true }); }
    }
  });

  it('a tool name containing ||| cannot shift the classifier fields into a fast allow', async () => {
    const { code, payload } = await runHook(JSON.stringify({ toolCall: { name: 'x|||0|||1|||y', args: {} } }), { role: 'developer', port: 1 });
    assert.equal(code, 0);
    assert.equal(payload.decision, 'deny');
  });
});
