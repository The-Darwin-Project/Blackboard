// gemini-sidecar/tests/test_ws_server_work_style.js
// @ai-rules:
// 1. [Constraint]: Test-only. Legacy ws-server `task` path must register work_style in state during execution (R2-4).
// 2. [Pattern]: cli-executor + credentials are stubbed via require.cache; no network, no CLI spawn.
const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');
const EventEmitter = require('events');

const root = path.resolve(__dirname, '..');
const stub = (name, exports) => {
  const id = require.resolve(path.join(root, name));
  require.cache[id] = { id, filename: id, loaded: true, exports };
};
const noop = () => {};
const asyncNoop = async () => {};
let observed = null;
stub('credentials.js', {
  hasGitHubCredentials: () => false, discoverAndGenerateTokens: asyncNoop, setupGitCredentials: noop,
  setupGitHubTooling: noop, hasGitLabCredentials: () => false, readGitLabToken: noop, setupGitLabCredentials: noop,
  setupGitLabTooling: noop, setupArgoCDMCP: asyncNoop, setupCLILogins: asyncNoop, setupRegistryCredentials: noop,
  setupRemoteK8sMCPs: noop, GITLAB_HOST: 'x', hasJenkinsCredentials: () => false, setupJenkinsMCP: asyncNoop,
  hasGoogleServiceAccount: () => false, setupGoogleAuthForAgy: asyncNoop,
});
stub('event-transport.js', { ensureEventDocument: asyncNoop });
const state = require(path.join(root, 'state.js'));
stub('cli-executor.js', {
  executeCLIStreaming: async () => { observed = state.resolveWorkStyle(); return { status: 'ok', output: 'done' }; },
});
const { setupWSServer } = require(path.join(root, 'ws-server.js'));

describe('ws-server work style (R2-4)', () => {
  it('resolves atdd_green during the task and resets afterwards', async () => {
    delete process.env.DARWIN_WORK_STYLE;
    const wss = new EventEmitter();
    setupWSServer(wss);
    const ws = new EventEmitter();
    ws.readyState = 1;
    ws.send = noop;
    wss.emit('connection', ws);
    ws.emit('message', JSON.stringify({ type: 'task', event_id: 'e1', prompt: 'p', role: 'developer', work_style: 'atdd_green' }));
    for (let i = 0; i < 50 && state.getCurrentTask() !== null && observed === null; i++) await new Promise(r => setTimeout(r, 10));
    for (let i = 0; i < 50 && state.getCurrentTask(); i++) await new Promise(r => setTimeout(r, 10));
    assert.equal(observed, 'atdd_green');
    assert.equal(state.getCurrentTask(), null);
    assert.equal(state.resolveWorkStyle(), 'autonomous');
  });
});
