// gemini-sidecar/tests/test_work_style_isolation.js
// @ai-rules:
// 1. [Constraint]: Test-only file -- the ATDD work-style lock is TASK-scoped. A task rejected as busy (or any other
//    early-return) must never alter the running task's workStyle, and the process-global DARWIN_WORK_STYLE env var
//    must not be written by ws-client at all (it raced with the running task's hooks).
// 2. [Pattern]: Drives ws-client.handleTask with a fake ws + real state.js; no network, no CLI spawn (busy path returns first).
const { describe, it, afterEach } = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');
const fs = require('fs');

const WS_CLIENT_PATH = path.resolve(__dirname, '..', 'ws-client.js');
const STATE_PATH = path.resolve(__dirname, '..', 'state.js');

const savedStyle = process.env.DARWIN_WORK_STYLE;
afterEach(() => {
  if (savedStyle === undefined) delete process.env.DARWIN_WORK_STYLE; else process.env.DARWIN_WORK_STYLE = savedStyle;
  require(STATE_PATH).clearCurrentTask();
});

function fakeWs() {
  const WebSocket = require('ws');
  const sent = [];
  return { readyState: WebSocket.OPEN, send: (m) => sent.push(JSON.parse(m)), sent };
}

describe('work style isolation (H3/A1)', () => {
  it('a busy-rejected task does not alter the running task\'s atdd_green workStyle or the process env', async () => {
    delete process.env.DARWIN_WORK_STYLE;
    const state = require(STATE_PATH);
    const { handleTask } = require(WS_CLIENT_PATH);
    state.setCurrentTask({ eventId: 'evt-running', taskId: 't-1', role: 'developer', workStyle: 'atdd_green' });

    const ws = fakeWs();
    await handleTask(ws, { task_id: 't-2', event_id: 'evt-other', prompt: 'do things', role: 'developer', work_style: 'autonomous' });

    assert.equal(ws.sent.length, 1);
    assert.equal(ws.sent[0].type, 'busy');
    assert.equal(state.resolveWorkStyle(), 'atdd_green', 'running task lost its lock');
    assert.equal(state.getCurrentTask().workStyle, 'atdd_green');
    assert.equal(process.env.DARWIN_WORK_STYLE, undefined, 'ws-client must not write the process-global env');
  });

  it('a task rejected for a missing role never touches DARWIN_WORK_STYLE', async () => {
    process.env.DARWIN_WORK_STYLE = 'atdd_green';
    const { handleTask } = require(WS_CLIENT_PATH);
    const ws = fakeWs();
    await handleTask(ws, { task_id: 't-3', event_id: 'evt-x', prompt: 'p', role: '', work_style: 'autonomous' });
    assert.equal(ws.sent[0].type, 'error');
    assert.equal(process.env.DARWIN_WORK_STYLE, 'atdd_green');
  });

  it('ws-client passes the task workStyle to executeCLIStreaming options and never assigns the env var (source contract)', () => {
    const src = fs.readFileSync(WS_CLIENT_PATH, 'utf8');
    assert.doesNotMatch(src, /process\.env\.DARWIN_WORK_STYLE\s*=/);
    assert.match(src, /executeCLIStreaming\(wsProxy, eventId, prompt, \{[^}]*\bworkStyle\b[^}]*\}\)/s);
  });
});

describe('cli-executor reads options.workStyle end to end (A1)', () => {
  it('buildCLICommand attaches the developer deny settings from options.workStyle, ignoring a conflicting global env', () => {
    process.env.DARWIN_WORK_STYLE = 'autonomous';
    const prevCli = process.env.AGENT_CLI;
    process.env.AGENT_CLI = 'claude';
    try {
      delete require.cache[require.resolve('../config.js')];
      delete require.cache[require.resolve('../cli-executor.js')];
      const { buildCLICommand } = require('../cli-executor.js');
      const green = buildCLICommand('p', { role: 'developer', workStyle: 'atdd_green' });
      assert.ok(green.args.includes('--settings'), 'atdd_green developer must get --settings');
      const auto = buildCLICommand('p', { role: 'developer', workStyle: 'autonomous' });
      assert.ok(!auto.args.includes('--settings'));
    } finally {
      if (prevCli === undefined) delete process.env.AGENT_CLI; else process.env.AGENT_CLI = prevCli;
      delete require.cache[require.resolve('../config.js')];
      delete require.cache[require.resolve('../cli-executor.js')];
    }
  });

  it('executeCLIStreaming / executeCLI / requestFindings forward workStyle into buildCLICommand and the child env (source contract)', () => {
    const src = fs.readFileSync(path.resolve(__dirname, '..', 'cli-executor.js'), 'utf8');
    assert.equal((src.match(/workStyle: options\.workStyle/g) || []).length, 2, 'executeCLI + executeCLIStreaming');
    assert.match(src, /buildCLICommand\(prompt, \{ autoApprove, model, role, workStyle \}\)/);
    assert.equal((src.match(/env: spawnEnv\(/g) || []).length, 3);
    assert.doesNotMatch(src, /env: process\.env/);
  });
});
