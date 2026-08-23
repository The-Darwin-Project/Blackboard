// gemini-sidecar/tests/test_plan_step_role.js
// @ai-rules:
// 1. [Constraint]: Test-only file -- regression coverage for the plan_step actor-role fallback
//    (state.resolveRole: task.role, else AGENT_ROLE, else default) and the /proxy/plan-step
//    loopback-only auth guard added alongside it.
// 2. [Pattern]: Uses node:test + node:assert, mirrors tests/test_gemini_cli_parity.js's
//    setEnv/restoreEnv/freshModules pattern -- config.js snapshots AGENT_ROLE/BRAIN_HTTP_URL from
//    process.env at require time, and state.js/http-handler.js both require config.js, so all
//    three caches must be cleared together whenever those env vars change between test cases.
// 3. [Pattern]: The /proxy/plan-step tests spin up a real HTTP server backed by handleRequest plus
//    a fake "Brain" HTTP server, then issue a real loopback HTTP request -- this exercises
//    req.socket.remoteAddress as a genuine loopback value instead of mocking the request object,
//    and verifies the actual body forwarded to the Brain (the real regression surface).

const { describe, it, afterEach } = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');
const http = require('http');

const CONFIG_PATH = path.resolve(__dirname, '..', 'config.js');
const STATE_PATH = path.resolve(__dirname, '..', 'state.js');
const HTTP_HANDLER_PATH = path.resolve(__dirname, '..', 'http-handler.js');

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
function clearCache() {
  [CONFIG_PATH, STATE_PATH, HTTP_HANDLER_PATH].forEach((p) => delete require.cache[require.resolve(p)]);
}
function freshState() {
  clearCache();
  return require(STATE_PATH);
}
function freshHttpHandler() {
  clearCache();
  const handler = require(HTTP_HANDLER_PATH);
  // http-handler.js's own `const state = require('./state')` resolves to the same cache
  // entry we just populated above, so this returns the identical instance it's using.
  const state = require(STATE_PATH);
  return { handler, state };
}

afterEach(() => {
  restoreEnv();
  clearCache();
});

function httpRequest(port, reqPath, method, body) {
  return new Promise((resolve, reject) => {
    const data = body !== undefined ? JSON.stringify(body) : undefined;
    const headers = data ? { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(data) } : {};
    const req = http.request({ hostname: '127.0.0.1', port, path: reqPath, method, headers }, (res) => {
      let chunks = '';
      res.on('data', (c) => { chunks += c; });
      res.on('end', () => {
        let parsed;
        try { parsed = JSON.parse(chunks); } catch { parsed = chunks; }
        resolve({ status: res.statusCode, body: parsed });
      });
    });
    req.on('error', reject);
    if (data) req.write(data);
    req.end();
  });
}

function startFakeBrain(respondWith = {}) {
  return new Promise((resolve) => {
    let lastRequest = null;
    const server = http.createServer((req, res) => {
      let body = '';
      req.on('data', (c) => { body += c; });
      req.on('end', () => {
        lastRequest = { method: req.method, url: req.url, body: body ? JSON.parse(body) : null };
        res.writeHead(respondWith.status || 200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify(respondWith.body || { ok: true }));
      });
    });
    server.listen(0, '127.0.0.1', () => resolve({
      server,
      port: server.address().port,
      getLastRequest: () => lastRequest,
    }));
  });
}

function startAppServer(handleRequest) {
  return new Promise((resolve) => {
    const server = http.createServer((req, res) => { handleRequest(req, res).catch(() => {}); });
    server.listen(0, '127.0.0.1', () => resolve({ server, port: server.address().port }));
  });
}

// =============================================================================
// state.resolveRole -- task.role, else AGENT_ROLE, else default
// =============================================================================

describe('state.resolveRole', () => {
  it('prefers the current task role over AGENT_ROLE', () => {
    setEnv('AGENT_ROLE', '');
    const state = freshState();
    state.setCurrentTask({ eventId: 'evt-1', role: 'code_reviewer' });
    assert.equal(state.resolveRole('default'), 'code_reviewer');
  });

  it('falls back to AGENT_ROLE when there is no active task', () => {
    setEnv('AGENT_ROLE', 'developer');
    const state = freshState();
    state.setCurrentTask(null);
    assert.equal(state.resolveRole('default'), 'developer');
  });

  it('falls back to the default when neither task role nor AGENT_ROLE is set', () => {
    setEnv('AGENT_ROLE', '');
    const state = freshState();
    state.setCurrentTask(null);
    assert.equal(state.resolveRole('default'), 'default');
  });

  it('preserves an explicitly falsy task role instead of falling through to AGENT_ROLE (?? vs ||)', () => {
    setEnv('AGENT_ROLE', 'developer');
    const state = freshState();
    state.setCurrentTask({ eventId: 'evt-2', role: '' });
    assert.equal(state.resolveRole('default'), '');
  });

  it('accepts an explicit task argument, avoiding a redundant getCurrentTask() re-fetch', () => {
    setEnv('AGENT_ROLE', '');
    const state = freshState();
    state.setCurrentTask({ eventId: 'evt-3', role: 'from-current-task' });
    assert.equal(state.resolveRole('default', { role: 'from-explicit-arg' }), 'from-explicit-arg');
  });
});

// =============================================================================
// http-handler.isLoopbackAddress -- guards the mutating /proxy/plan-step route
// =============================================================================

describe('isLoopbackAddress', () => {
  it('accepts IPv4 and IPv6 loopback forms', () => {
    const { handler } = freshHttpHandler();
    assert.equal(handler.isLoopbackAddress('127.0.0.1'), true);
    assert.equal(handler.isLoopbackAddress('::1'), true);
    assert.equal(handler.isLoopbackAddress('::ffff:127.0.0.1'), true);
  });

  it('rejects non-loopback addresses', () => {
    const { handler } = freshHttpHandler();
    assert.equal(handler.isLoopbackAddress('10.0.0.5'), false);
    assert.equal(handler.isLoopbackAddress(undefined), false);
  });
});

// =============================================================================
// POST /proxy/plan-step -- end-to-end regression coverage
// =============================================================================

describe('POST /proxy/plan-step', () => {
  let apps = [];

  afterEach(async () => {
    await Promise.all(apps.map(({ server }) => new Promise((r) => server.close(r))));
    apps = [];
  });

  it('forwards the actor role from the current task, not the (empty, ephemeral) AGENT_ROLE env', async () => {
    setEnv('AGENT_ROLE', ''); // ephemeral agent -- exactly the scenario the original bug hit
    const brain = await startFakeBrain();
    setEnv('BRAIN_HTTP_URL', `http://127.0.0.1:${brain.port}`);
    const { handler, state } = freshHttpHandler();
    state.setCurrentTask({ eventId: 'evt-42', role: 'code_reviewer' });

    const app = await startAppServer(handler.handleRequest);
    apps.push(app);
    apps.push(brain);

    const res = await httpRequest(app.port, '/proxy/plan-step', 'POST', { step_id: '2', status: 'completed' });

    assert.equal(res.status, 200);
    const forwarded = brain.getLastRequest();
    assert.equal(forwarded.url, '/queue/evt-42/plan-step');
    assert.equal(forwarded.body.role, 'code_reviewer');
    assert.equal(forwarded.body.event_id, 'evt-42');
  });

  it('preserves an explicit empty task role instead of leaking AGENT_ROLE', async () => {
    setEnv('AGENT_ROLE', 'developer');
    const brain = await startFakeBrain();
    setEnv('BRAIN_HTTP_URL', `http://127.0.0.1:${brain.port}`);
    const { handler, state } = freshHttpHandler();
    state.setCurrentTask({ eventId: 'evt-43', role: '' });

    const app = await startAppServer(handler.handleRequest);
    apps.push(app);
    apps.push(brain);

    await httpRequest(app.port, '/proxy/plan-step', 'POST', { step_id: '1', status: 'blocked' });

    assert.equal(brain.getLastRequest().body.role, '');
  });

  it('falls back to AGENT_ROLE when the task has no role field at all', async () => {
    setEnv('AGENT_ROLE', 'architect');
    const brain = await startFakeBrain();
    setEnv('BRAIN_HTTP_URL', `http://127.0.0.1:${brain.port}`);
    const { handler, state } = freshHttpHandler();
    state.setCurrentTask({ eventId: 'evt-44' });

    const app = await startAppServer(handler.handleRequest);
    apps.push(app);
    apps.push(brain);

    await httpRequest(app.port, '/proxy/plan-step', 'POST', { step_id: '1', status: 'in_progress' });

    assert.equal(brain.getLastRequest().body.role, 'architect');
  });

  it('returns 400 with no active task, without contacting the Brain', async () => {
    const brain = await startFakeBrain();
    setEnv('BRAIN_HTTP_URL', `http://127.0.0.1:${brain.port}`);
    const { handler, state } = freshHttpHandler();
    state.setCurrentTask(null);

    const app = await startAppServer(handler.handleRequest);
    apps.push(app);
    apps.push(brain);

    const res = await httpRequest(app.port, '/proxy/plan-step', 'POST', { step_id: '1', status: 'completed' });

    assert.equal(res.status, 400);
    assert.equal(res.body.error, 'No active task');
    assert.equal(brain.getLastRequest(), null);
  });

  it('rejects a non-loopback caller with 403 before parsing the body or contacting the Brain', async () => {
    const brain = await startFakeBrain();
    setEnv('BRAIN_HTTP_URL', `http://127.0.0.1:${brain.port}`);
    const { handler, state } = freshHttpHandler();
    state.setCurrentTask({ eventId: 'evt-45', role: 'developer' });
    apps.push(brain);

    // Exercises the real handleRequest auth gate directly with a spoofed remoteAddress --
    // binding an actual server to a non-loopback interface isn't reliable in a sandboxed
    // test environment, so the request object is faked instead of the transport.
    let statusCode, headers, payload;
    const fakeReq = { url: '/proxy/plan-step', method: 'POST', socket: { remoteAddress: '10.0.0.5' } };
    const fakeRes = {
      writeHead: (code, h) => { statusCode = code; headers = h; },
      end: (body) => { payload = body; },
    };

    await handler.handleRequest(fakeReq, fakeRes);

    assert.equal(statusCode, 403);
    assert.equal(headers['Content-Type'], 'application/json');
    assert.equal(JSON.parse(payload).error, 'Forbidden: loopback-only endpoint');
    assert.equal(brain.getLastRequest(), null, 'a rejected caller must never reach the Brain');
  });
});

// =============================================================================
// The three sibling call sites this PR fixed alongside /proxy/plan-step --
// each previously read bare AGENT_ROLE with no task.role fallback.
// =============================================================================

describe('other resolveRole call sites fixed by this PR', () => {
  let apps = [];

  afterEach(async () => {
    await Promise.all(apps.map(({ server }) => new Promise((r) => server.close(r))));
    apps = [];
  });

  it('POST /hooks/session-start reports the task role, not the (empty, ephemeral) AGENT_ROLE env', async () => {
    setEnv('AGENT_ROLE', '');
    const { handler, state } = freshHttpHandler();
    state.setCurrentTask({ eventId: 'evt-46', role: 'security_analyst' });

    const app = await startAppServer(handler.handleRequest);
    apps.push(app);

    const res = await httpRequest(app.port, '/hooks/session-start', 'POST');

    assert.equal(res.status, 200);
    assert.match(res.body.hookSpecificOutput.additionalContext, /you are security_analyst\./);
  });

  it('GET /proxy/turns queries the Brain with the task role, not the (empty, ephemeral) AGENT_ROLE env', async () => {
    setEnv('AGENT_ROLE', '');
    const brain = await startFakeBrain({ body: { turns: [], total: 0 } });
    setEnv('BRAIN_HTTP_URL', `http://127.0.0.1:${brain.port}`);
    const { handler, state } = freshHttpHandler();
    state.setCurrentTask({ eventId: 'evt-47', role: 'explorer' });

    const app = await startAppServer(handler.handleRequest);
    apps.push(app);
    apps.push(brain);

    const res = await httpRequest(app.port, '/proxy/turns', 'GET');

    assert.equal(res.status, 200);
    assert.equal(brain.getLastRequest().url, '/queue/evt-47/turns?role=explorer');
  });

  it("POST /callback (teammate_message) mirrors the task role as 'from', not the (empty, ephemeral) AGENT_ROLE env", async () => {
    setEnv('AGENT_ROLE', '');
    const { handler, state } = freshHttpHandler();
    const WebSocket = require('ws');
    const sent = [];
    const fakeWs = { readyState: WebSocket.OPEN, send: (msg) => sent.push(JSON.parse(msg)) };
    state.setCurrentTask({ eventId: 'evt-48', taskId: 'task-1', role: 'architect', ws: fakeWs });

    const app = await startAppServer(handler.handleRequest);
    apps.push(app);

    const res = await httpRequest(app.port, '/callback', 'POST', { type: 'teammate_message', content: 'hello' });

    assert.equal(res.status, 200);
    assert.equal(sent.length, 1);
    assert.equal(sent[0].type, 'agent_teammate_message');
    assert.equal(sent[0].from, 'architect');
  });
});
