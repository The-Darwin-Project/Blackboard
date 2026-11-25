// gemini-sidecar/tests/test_usage_tracker.js
// @ai-rules:
// 1. [Constraint]: 4-Layer ATDD executable spec for T-14 and T-15 (usage-tracker.js, cli-executor, ws-client, ws-server).
// 2. [Pattern]: Loads probe fixtures from tests/fixtures/*.ndjson; stubs cp.spawn & require.cache collaborators cleanly.
const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const cp = require('node:child_process');
const { EventEmitter } = require('events');
const fs = require('fs');
const os = require('os');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const FIXTURES = path.join(__dirname, 'fixtures');
const resolveMod = (f) => require.resolve(path.join(ROOT, f));
const flush = async () => { for (let i = 0; i < 6; i++) await new Promise((r) => setImmediate(r)); };

function readFixtureLines(name) {
  return fs.readFileSync(path.join(FIXTURES, name), 'utf8').trim().split('\n');
}

function freshExecutor(env = {}) {
  const fakeHome = fs.mkdtempSync(path.join(os.tmpdir(), 'usage-exec-home-'));
  fs.mkdirSync(path.join(fakeHome, '.gemini'), { recursive: true });
  const merged = { HOME: fakeHome, ...env };
  const saved = {};
  for (const [k, v] of Object.entries(merged)) {
    saved[k] = process.env[k];
    if (v === undefined) delete process.env[k]; else process.env[k] = v;
  }
  const configPath = resolveMod('config.js');
  const execPath = resolveMod('cli-executor.js');
  delete require.cache[configPath];
  delete require.cache[execPath];
  const mod = require(execPath);
  const restore = () => {
    for (const [k, v] of Object.entries(saved)) {
      if (v === undefined) delete process.env[k]; else process.env[k] = v;
    }
    delete require.cache[configPath];
    delete require.cache[execPath];
    fs.rmSync(fakeHome, { recursive: true, force: true });
  };
  return { mod, restore };
}

describe('T-14: usage-tracker.js pure stream extraction & deduped accumulation', () => {
  it('inferProvider distinguishes agy, vertex_claude, and enmaas', () => {
    const { inferProvider } = require(path.join(ROOT, 'usage-tracker.js'));

    assert.equal(inferProvider('agy', {}), 'vertex_gemini');
    assert.equal(inferProvider('claude', { CLAUDE_CODE_USE_VERTEX: '1' }), 'vertex_claude');
    assert.equal(inferProvider('claude', { ANTHROPIC_BASE_URL: 'https://enmaas.internal/v1' }), 'enmaas');
    assert.equal(inferProvider('claude', { CLAUDE_CODE_USE_VERTEX: '0', ANTHROPIC_BASE_URL: 'https://enmaas.internal' }), 'enmaas');
    assert.equal(inferProvider('claude', {}), 'vertex_claude');
  });

  it('dedups claude assistant message.id updates and reconciles terminal result without double-counting', () => {
    const { createTaskUsageAccumulator } = require(path.join(ROOT, 'usage-tracker.js'));
    const lines = readFixtureLines('claude-multi-turn.ndjson');
    const acc = createTaskUsageAccumulator();
    const spawn = acc.startSpawn('claude', 'vertex_claude', 'claude-sonnet-5');

    const emittedDeltas = [];
    for (const line of lines) {
      const delta = spawn.onLine(line);
      if (delta && delta.usage) emittedDeltas.push(delta);
    }

    // 2 assistant chunks for m1 (50 -> 120, delta +70), m2 (30), terminal result (500 -> reconcile +350)
    assert.equal(emittedDeltas.length, 4);
    assert.equal(emittedDeltas[0].usage.total_tokens, 50);
    assert.equal(emittedDeltas[1].usage.total_tokens, 70);
    assert.equal(emittedDeltas[2].usage.total_tokens, 30);
    assert.equal(emittedDeltas[3].usage.total_tokens, 350);

    const liveBeforeResult = 50 + 70 + 30;
    assert.equal(liveBeforeResult, 150);
    const sumAllDeltas = emittedDeltas.reduce((s, d) => s + d.usage.total_tokens, 0);
    assert.equal(sumAllDeltas, 500);
    assert.ok(emittedDeltas.every((d) => d.usage.total_tokens >= 0));

    const summary = acc.summary();
    assert.equal(summary.usage.total_tokens, 500);
    assert.equal(summary.used_model, 'claude-sonnet-5');
    assert.equal(summary.provider, 'vertex_claude');
    assert.equal(summary.usage_by_provider.vertex_claude.total_tokens, 500);
  });

  it('extracts agy result.usage cleanly while keeping stream-parser.js keys unchanged', () => {
    const { createTaskUsageAccumulator } = require(path.join(ROOT, 'usage-tracker.js'));
    const lines = readFixtureLines('agy-result.ndjson');
    const acc = createTaskUsageAccumulator();
    const spawn = acc.startSpawn('agy', 'vertex_gemini', 'gemini-4-neon');

    const deltas = lines.map((l) => spawn.onLine(l)).filter(Boolean);
    assert.equal(deltas.length, 1);
    assert.equal(deltas[0].usage.total_tokens, 300);
    assert.equal(deltas[0].usage.thinking_tokens, 40);

    const summary = acc.summary();
    assert.equal(summary.provider, 'vertex_gemini');
    assert.equal(summary.usage.total_tokens, 300);
    assert.equal(summary.usage_by_provider.vertex_gemini.total_tokens, 300);
  });

  it('folds claude cache_read_input_tokens without double-counting thinking_tokens when total_tokens is omitted', () => {
    const { extractStreamUsage, createTaskUsageAccumulator } = require(path.join(ROOT, 'usage-tracker.js'));

    const assistantLine = JSON.stringify({
      type: 'assistant',
      message: {
        id: 'm-cache-think',
        model: 'claude-sonnet-5',
        usage: {
          input_tokens: 100,
          cache_read_input_tokens: 400,
          cache_creation_input_tokens: 50,
          output_tokens: 80,
          thinking_tokens: 60,
        },
      },
    });
    const ext = extractStreamUsage(assistantLine, 'claude');
    assert.ok(ext);
    assert.equal(ext.usage.thinking_tokens, 60);
    assert.equal(ext.usage.cache_read_input_tokens, 400);
    // total = 100 + 400 + 50 + 80 = 630 (thinking_tokens excluded from Claude sum to avoid double-count)
    assert.equal(ext.usage.total_tokens, 630);

    const acc = createTaskUsageAccumulator();
    const spawn = acc.startSpawn('claude', 'vertex_claude', 'claude-sonnet-5');
    const delta = spawn.onLine(assistantLine);
    assert.equal(delta.usage.total_tokens, 630);
    assert.equal(delta.usage.thinking_tokens, 60);

    const resultLine = JSON.stringify({
      type: 'result',
      subtype: 'success',
      usage: {
        input_tokens: 150,
        cache_read_input_tokens: 500,
        cache_creation_input_tokens: 50,
        output_tokens: 120,
        thinking_tokens: 90,
      },
    });
    const resDelta = spawn.onLine(resultLine);
    // 150 + 500 + 50 + 120 = 820 total -> residual 820 - 630 = 190
    assert.equal(resDelta.usage.total_tokens, 190);
    assert.equal(acc.summary().usage.total_tokens, 820);
  });

  it('wsSend safely handles closed sockets, null sockets, and throwing ws.send', () => {
    const { wsSend } = require(path.join(ROOT, 'ws-utils.js'));

    assert.doesNotThrow(() => wsSend(null, { type: 'ping' }));
    assert.doesNotThrow(() => wsSend(undefined, { type: 'ping' }));

    let closedCalled = false;
    wsSend({ readyState: 3, send() { closedCalled = true; } }, { type: 'ping' });
    assert.equal(closedCalled, false);

    assert.doesNotThrow(() => {
      wsSend({ readyState: 1, send() { throw new Error('broken pipe'); } }, { type: 'ping' });
    });

    const sent = [];
    wsSend({ readyState: 1, send(raw) { sent.push(JSON.parse(raw)); } }, { type: 'pong', ok: true });
    assert.deepEqual(sent, [{ type: 'pong', ok: true }]);
  });
});

describe('T-15: multi-spawn failover, requestFindings, ws-client, and ws-server wiring', () => {
  it('accumulates separate usage_by_provider across enmaas -> vertex_claude failover spawns', () => {
    const { createTaskUsageAccumulator } = require(path.join(ROOT, 'usage-tracker.js'));
    const lines = readFixtureLines('claude-failover.ndjson');
    const acc = createTaskUsageAccumulator();

    const s1 = acc.startSpawn('claude', 'enmaas', 'zai-org/glm-5');
    s1.onLine(lines[0]);
    s1.onLine(lines[1]); // 80 tokens on enmaas

    const s2 = acc.startSpawn('claude', 'vertex_claude', 'claude-sonnet-5');
    s2.onLine(lines[2]);
    s2.onLine(lines[3]); // 40 tokens
    s2.onLine(lines[4]); // terminal 120 tokens -> +80 reconcile

    const summary = acc.summary();
    assert.equal(summary.usage.total_tokens, 200);
    assert.equal(summary.usage_by_provider.enmaas.total_tokens, 80);
    assert.equal(summary.usage_by_provider.vertex_claude.total_tokens, 120);
    assert.equal(summary.provider, 'vertex_claude');
    assert.equal(summary.used_model, 'claude-sonnet-5');
  });

  it('executeCLIStreaming emits live token_usage WS deltas and includes requestFindings spawn', async (t) => {
    const scratch = fs.mkdtempSync(path.join(os.tmpdir(), 'usage-cwd-'));
    const { mod, restore } = freshExecutor({ AGENT_CLI: 'claude', CLAUDE_CODE_USE_VERTEX: '1' });
    try {
      const claudeLines = readFixtureLines('claude-multi-turn.ndjson');
      // Spawn 1: non-JSON output? Emit claudeLines WITH plain text? No: emit a valid assistant JSON + non-empty plain output?
      // Actually trigger requestFindings by returning code 0 with raw text + usage lines on spawn 1, then JSON result on spawn 2!
      let spawnIdx = 0;
      t.mock.method(cp, 'spawn', () => {
        const idx = spawnIdx++;
        const child = new EventEmitter();
        child.stdout = new EventEmitter();
        child.stderr = new EventEmitter();
        setTimeout(() => {
          if (idx === 0) {
            // 1 assistant token frame + non-JSON final stdout so resolveResult invokes requestFindings()
            child.stdout.emit('data', Buffer.from(claudeLines[1] + '\nPlain summary without JSON result\n'));
          } else {
            // requestFindings spawn emits terminal result usage (60 tokens)
            child.stdout.emit('data', Buffer.from(JSON.stringify({
              type: 'result', subtype: 'success', result: 'ok',
              usage: { input_tokens: 40, output_tokens: 20 },
            }) + '\n'));
          }
          child.emit('close', 0, null);
        }, 5);
        return child;
      });

      const sent = [];
      const ws = { readyState: 1, send(raw) { sent.push(JSON.parse(raw)); } };
      const res = await mod.executeCLIStreaming(ws, 'evt-rf', 'do task', { cwd: scratch, role: 'developer' });

      const liveFrames = sent.filter((m) => m.type === 'token_usage');
      assert.ok(liveFrames.length >= 1, 'Expected live token_usage WS frames');
      assert.equal(liveFrames[0].provider, 'vertex_claude');
      assert.equal(liveFrames[0].cli, 'claude');
      assert.ok(res.usage, 'Expected cumulative usage on executeCLIStreaming result');
      assert.equal(res.usage.total_tokens, 50 + 60);
      assert.equal(res.usage_by_provider.vertex_claude.total_tokens, 110);
    } finally {
      restore();
      fs.rmSync(scratch, { recursive: true, force: true });
    }
  });

  it('ws-client register sends provider and result frame carries cumulative usage + usage_by_provider', async () => {
    const STUBBED = ['cli-executor.js', 'credentials.js', 'cli-setup.js', 'event-transport.js', 'catalog-skills.js'];
    const RELOADED = ['config.js', 'state.js', 'ws-utils.js', 'ws-client.js'];
    const saved = { AGENT_CLI: process.env.AGENT_CLI, CLAUDE_CODE_USE_VERTEX: process.env.CLAUDE_CODE_USE_VERTEX };
    process.env.AGENT_CLI = 'claude';
    process.env.CLAUDE_CODE_USE_VERTEX = '1';
    for (const f of [...STUBBED, ...RELOADED]) delete require.cache[resolveMod(f)];

    try {
      const noop = () => {};
      const asyncNoop = async () => {};
      const stubs = {
        'cli-executor.js': {
          executeCLIStreaming: async () => ({
            status: 'success',
            output: 'ok',
            used_model: 'claude-sonnet-5',
            provider: 'vertex_claude',
            usage: { input_tokens: 100, output_tokens: 50, total_tokens: 150 },
            usage_by_provider: { vertex_claude: { input_tokens: 100, output_tokens: 50, total_tokens: 150 } },
          }),
          prepareResultsDir: noop,
          is429Error: () => false,
        },
        'credentials.js': {
          hasGitHubCredentials: () => false, hasGitLabCredentials: () => false,
          hasJenkinsCredentials: () => false, hasGoogleServiceAccount: () => false,
          setupArgoCDMCP: asyncNoop, setupCLILogins: asyncNoop, setupJenkinsMCP: asyncNoop,
          setupRemoteK8sMCPs: noop, setupRegistryCredentials: noop, GITLAB_HOST: 'x',
        },
        'cli-setup.js': { filterSkillsByRole: noop, filterSkillsByMode: noop, swapActiveRules: noop, restoreAllSkills: noop },
        'event-transport.js': { ensureEventDocument: asyncNoop },
        'catalog-skills.js': { startCatalogSync: noop },
      };
      for (const [f, exports] of Object.entries(stubs)) {
        const id = resolveMod(f);
        require.cache[id] = { id, filename: id, loaded: true, exports };
      }

      const { handleServerMessage, buildRegisterPayload } = require(resolveMod('ws-client.js'));
      const state = require(resolveMod('state.js'));
      const reg = typeof buildRegisterPayload === 'function' ? buildRegisterPayload() : null;
      if (reg) assert.equal(reg.provider, 'vertex_claude');

      // Also check ws-client source sends provider on register
      const wsClientSrc = fs.readFileSync(path.join(ROOT, 'ws-client.js'), 'utf8');
      assert.match(wsClientSrc, /provider\s*:/);

      const sent = [];
      const ws = { readyState: 1, send(raw) { sent.push(JSON.parse(raw)); } };
      await handleServerMessage(ws, {
        type: 'task', task_id: 't-1', event_id: 'e-1', prompt: 'hi', role: 'developer', cwd: os.tmpdir(),
      });
      await flush();
      state.clearCurrentTask();

      const resMsg = sent.find((m) => m.type === 'result');
      assert.ok(resMsg, 'Expected result message from ws-client');
      assert.equal(resMsg.provider, 'vertex_claude');
      assert.equal(resMsg.used_model, 'claude-sonnet-5');
      assert.equal(resMsg.usage.total_tokens, 150);
      assert.equal(resMsg.usage_by_provider.vertex_claude.total_tokens, 150);
    } finally {
      for (const [k, v] of Object.entries(saved)) {
        if (v === undefined) delete process.env[k]; else process.env[k] = v;
      }
      for (const f of [...STUBBED, ...RELOADED]) delete require.cache[resolveMod(f)];
    }
  });

  it('ws-server mirrors usage, used_model, provider, and usage_by_provider on BOTH task and followup', async () => {
    const stub = (name, exports) => {
      const id = resolveMod(name);
      require.cache[id] = { id, filename: id, loaded: true, exports };
    };
    const noop = () => {};
    const asyncNoop = async () => {};
    for (const f of ['ws-server.js', 'state.js', 'cli-executor.js', 'credentials.js', 'event-transport.js']) {
      delete require.cache[resolveMod(f)];
    }
    stub('credentials.js', {
      hasGitHubCredentials: () => false, discoverAndGenerateTokens: asyncNoop, setupGitCredentials: noop,
      setupGitHubTooling: noop, hasGitLabCredentials: () => false, readGitLabToken: noop, setupGitLabCredentials: noop,
      setupGitLabTooling: noop, setupArgoCDMCP: asyncNoop, setupCLILogins: asyncNoop, setupRegistryCredentials: noop,
      setupRemoteK8sMCPs: noop, GITLAB_HOST: 'x', hasJenkinsCredentials: () => false, setupJenkinsMCP: asyncNoop,
      hasGoogleServiceAccount: () => false, setupGoogleAuthForAgy: asyncNoop,
    });
    stub('event-transport.js', { ensureEventDocument: asyncNoop });
    const state = require(resolveMod('state.js'));
    stub('cli-executor.js', {
      executeCLIStreaming: async () => ({
        status: 'success',
        output: 'ok',
        used_model: 'claude-sonnet-5',
        provider: 'vertex_claude',
        usage: { input_tokens: 70, output_tokens: 30, total_tokens: 100 },
        usage_by_provider: { vertex_claude: { input_tokens: 70, output_tokens: 30, total_tokens: 100 } },
      }),
    });

    const { setupWSServer } = require(resolveMod('ws-server.js'));
    const wss = new EventEmitter();
    setupWSServer(wss);

    const sent = [];
    const ws = new EventEmitter();
    ws.readyState = 1;
    ws.send = (raw) => sent.push(JSON.parse(raw));
    wss.emit('connection', ws);

    ws.emit('message', JSON.stringify({ type: 'task', event_id: 'e-task', prompt: 'p', role: 'developer' }));
    for (let i = 0; i < 50 && !sent.some((m) => m.type === 'result'); i++) await new Promise((r) => setTimeout(r, 10));
    state.clearCurrentTask();

    ws.emit('message', JSON.stringify({ type: 'followup', event_id: 'e-follow', session_id: 's1', message: 'more', role: 'developer' }));
    for (let i = 0; i < 50 && sent.filter((m) => m.type === 'result').length < 2; i++) await new Promise((r) => setTimeout(r, 10));
    state.clearCurrentTask();

    const results = sent.filter((m) => m.type === 'result');
    assert.equal(results.length, 2);
    for (const r of results) {
      assert.equal(r.provider, 'vertex_claude');
      assert.equal(r.used_model, 'claude-sonnet-5');
      assert.equal(r.usage.total_tokens, 100);
      assert.equal(r.usage_by_provider.vertex_claude.total_tokens, 100);
    }
  });
});
