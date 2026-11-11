// gemini-sidecar/tests/test_ws_client.js
// @ai-rules:
// 1. [Constraint]: ws-client.js reads config (EVENT_ID/EPHEMERAL/IDLE_TIMEOUT_MS/AGENT_ROLE/MAX_TASK_WALL_MS) at load time -- every test loads it via
//    freshClient() with the env it needs, and restores env + require.cache in `finally`. Never rely on ambient env.
// 2. [Pattern]: Heavy collaborators (cli-executor, credentials, cli-setup, event-transport, catalog-skills) are replaced through require.cache;
//    config, state and ws-utils stay REAL so timer/ownership logic is exercised against the true shared state.
// 3. [Pattern]: Timers use node:test mock timers (setTimeout only). Promise continuations still run, so `flush()` (setImmediate, unmocked) is used
//    between steps. Never tick with a real sleep.
// 4. [Gotcha]: signalIdleExit() writes a sentinel under /data/workspace (shared squad dir) and the idle callback calls process.exit --
//    both are mocked in every test that can reach them. A test must never touch the real sentinel dir or exit the runner.

const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');
const fs = require('fs');
const os = require('os');
const { EventEmitter } = require('events');

const ROOT = path.join(__dirname, '..');
const resolveMod = (f) => require.resolve(path.join(ROOT, f));
const STUBBED = ['cli-executor.js', 'credentials.js', 'cli-setup.js', 'event-transport.js', 'catalog-skills.js'];
const RELOADED = ['config.js', 'state.js', 'ws-utils.js', 'ws-client.js'];

const IDLE_MS = 1000;
const TASK_TIMEOUT_SEC = 10;
const GRACE_MS = 15000; // BACKSTOP_GRACE_MS
const BACKSTOP_MS = TASK_TIMEOUT_SEC * 1000 + GRACE_MS;

const flush = async () => { for (let i = 0; i < 5; i++) await new Promise((r) => setImmediate(r)); };

function deferred() {
  let resolve; let reject;
  const promise = new Promise((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}

function makeWs() {
  return { readyState: 1, sent: [], send(raw) { this.sent.push(JSON.parse(raw)); } };
}

function makeMsg(overrides = {}) {
  return { type: 'task', task_id: 't1', event_id: 'e1', prompt: 'do it', mode: 'implement', role: 'developer', cwd: os.tmpdir(), ...overrides };
}

/**
 * Loads ws-client with stubbed collaborators and an isolated env.
 * `executeCLIStreaming` receives (wsProxy, eventId, prompt, opts) exactly like the real one.
 */
function freshClient({ env = {}, executeCLIStreaming, ensureEventDocument } = {}) {
  const fullEnv = {
    EVENT_ID: undefined, AGENT_ROLE: 'developer', IDLE_TIMEOUT_MS: String(IDLE_MS),
    TASK_TIMEOUT_IMPLEMENT: String(TASK_TIMEOUT_SEC), TASK_TIMEOUT_DEFAULT: undefined,
    TIMEOUT_MS: undefined, MAX_TASK_WALL_MS: undefined, ...env,
  };
  const saved = {};
  for (const [k, v] of Object.entries(fullEnv)) {
    saved[k] = process.env[k];
    if (v === undefined) delete process.env[k]; else process.env[k] = v;
  }
  const clearCache = () => {
    for (const f of [...STUBBED, ...RELOADED]) delete require.cache[resolveMod(f)];
  };
  clearCache();

  const calls = { execute: [] };
  const noop = () => {};
  const asyncNoop = async () => {};
  const stubs = {
    'cli-executor.js': {
      executeCLIStreaming: async (...args) => {
        calls.execute.push(args);
        return executeCLIStreaming ? executeCLIStreaming(...args) : { status: 'success', output: 'ok' };
      },
      prepareResultsDir: noop,
      is429Error: (s) => /429/.test(s || ''),
    },
    'credentials.js': {
      hasGitHubCredentials: () => false, hasGitLabCredentials: () => false,
      hasJenkinsCredentials: () => false, hasGoogleServiceAccount: () => false,
      setupArgoCDMCP: asyncNoop, setupCLILogins: asyncNoop, setupJenkinsMCP: asyncNoop,
      setupRemoteK8sMCPs: noop, setupRegistryCredentials: noop, GITLAB_HOST: 'gitlab.test',
    },
    'cli-setup.js': {
      filterSkillsByRole: noop, filterSkillsByMode: noop, swapActiveRules: noop, restoreAllSkills: noop,
    },
    'event-transport.js': { ensureEventDocument: ensureEventDocument || asyncNoop },
    'catalog-skills.js': { startCatalogSync: noop },
  };
  for (const [f, exports] of Object.entries(stubs)) {
    const id = resolveMod(f);
    require.cache[id] = { id, filename: id, loaded: true, exports, children: [], paths: [] };
  }

  const mod = require(resolveMod('ws-client.js'));
  const state = require(resolveMod('state.js'));
  const config = require(resolveMod('config.js'));
  const restore = () => {
    state.clearCurrentTask();
    for (const [k, v] of Object.entries(saved)) {
      if (v === undefined) delete process.env[k]; else process.env[k] = v;
    }
    clearCache();
  };
  return { mod, state, config, calls, restore };
}

/** Common per-test harness: mock timers, silenced logs, neutralised process.exit + idle sentinel write. */
function harness(t) {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  t.mock.method(console, 'log', () => {});
  t.mock.method(console, 'warn', () => {});
  const exit = t.mock.method(process, 'exit', () => {});
  const writes = t.mock.method(fs, 'writeFileSync', () => {});
  return { exit, writes };
}

const errorsOf = (ws) => ws.sent.filter((m) => m.type === 'error');
const resultsOf = (ws) => ws.sent.filter((m) => m.type === 'result');

describe('computeBackstopMs', () => {
  it('is the inactivity window plus the grace buffer, and the grace exceeds the watchdog SIGTERM->SIGKILL escalation (10s)', () => {
    const { mod, restore } = freshClient();
    try {
      assert.equal(mod.BACKSTOP_GRACE_MS, GRACE_MS);
      assert.ok(mod.BACKSTOP_GRACE_MS > 10000, 'grace must outlast the watchdog kill escalation');
      assert.equal(mod.computeBackstopMs(10), 10000 + GRACE_MS);
      assert.equal(mod.computeBackstopMs(600), 600000 + GRACE_MS);
    } finally { restore(); }
  });

  it('caps at MAX_TASK_WALL_MS + grace so the backstop never outlives the hard wall-clock ceiling', () => {
    const { mod, config, restore } = freshClient({ env: { MAX_TASK_WALL_MS: '60000' } });
    try {
      assert.equal(config.MAX_TASK_WALL_MS, 60000);
      assert.equal(mod.computeBackstopMs(59), 59000 + GRACE_MS);
      assert.equal(mod.computeBackstopMs(3600), 60000 + GRACE_MS, 'window beyond the wall ceiling must be capped');
    } finally { restore(); }
  });

  it('never returns 0/NaN for a missing or invalid window (floors the window at 1s)', () => {
    const { mod, restore } = freshClient();
    try {
      for (const bad of [0, -5, NaN, undefined, null, 'abc']) {
        assert.equal(mod.computeBackstopMs(bad), 1000 + GRACE_MS, `input ${String(bad)}`);
      }
    } finally { restore(); }
  });
});

describe('ws-client ephemeral idle timer', () => {
  it('is suppressed for the whole task (setup + CLI run) and re-armed in finally once the task ends', async (t) => {
    const { exit, writes } = harness(t);
    const run = deferred();
    const { mod, restore } = freshClient({ env: { EVENT_ID: 'evt-1' }, executeCLIStreaming: () => run.promise });
    try {
      const ws = makeWs();
      mod.resetIdleTimer(); // idle timer armed before the task arrives
      t.mock.timers.tick(IDLE_MS / 2);

      const task = mod.handleTask(ws, makeMsg());
      await flush();

      // Task is in flight far longer than IDLE_TIMEOUT_MS (but below the backstop): the agent must NOT exit.
      t.mock.timers.tick(IDLE_MS * 5);
      assert.equal(exit.mock.callCount(), 0, 'ephemeral agent exited while a task was running');

      run.resolve({ status: 'success', output: 'done' });
      await task;
      assert.equal(resultsOf(ws).length, 1);

      // Re-armed in finally: exits only after a FULL idle window counted from task end.
      t.mock.timers.tick(IDLE_MS - 1);
      assert.equal(exit.mock.callCount(), 0, 'idle timer fired before a full window elapsed after the task');
      t.mock.timers.tick(1);
      assert.equal(exit.mock.callCount(), 1);
      assert.deepEqual(exit.mock.calls[0].arguments, [0]);
      // The sentinel write was intercepted (never touches the real shared dir) and targets this role.
      assert.ok(writes.mock.calls.some((c) => String(c.arguments[0]).endsWith('.idle-developer')));
    } finally { restore(); }
  });

  it('re-arms in finally even when task handling rejects (setup failure before the CLI run)', async (t) => {
    const { exit } = harness(t);
    const { mod, restore } = freshClient({
      env: { EVENT_ID: 'evt-1' },
      ensureEventDocument: async () => { throw new Error('event doc fetch exploded'); },
    });
    try {
      mod.resetIdleTimer();
      await assert.rejects(mod.handleTask(makeWs(), makeMsg()), /event doc fetch exploded/);
      t.mock.timers.tick(IDLE_MS - 1);
      assert.equal(exit.mock.callCount(), 0);
      t.mock.timers.tick(1);
      assert.equal(exit.mock.callCount(), 1, 'idle timer was not re-armed after a rejected task');
    } finally { restore(); }
  });

  it('timer callback refuses to exit mid-task: it re-arms instead (never process.exit while a task is active)', async (t) => {
    const { exit } = harness(t);
    const run = deferred();
    const { mod, restore } = freshClient({ env: { EVENT_ID: 'evt-1' }, executeCLIStreaming: () => run.promise });
    try {
      const ws = makeWs();
      const task = mod.handleTask(ws, makeMsg());
      await flush();

      mod.resetIdleTimer(); // something re-arms the timer mid-task
      t.mock.timers.tick(IDLE_MS);
      t.mock.timers.tick(IDLE_MS);
      assert.equal(exit.mock.callCount(), 0, 'idle callback exited the process during an active task');

      run.resolve({ status: 'success', output: 'done' });
      await task;
      t.mock.timers.tick(IDLE_MS);
      assert.equal(exit.mock.callCount(), 1, 'exit must resume once the task is over');
    } finally { restore(); }
  });

  it('is ref-counted: a busy-rejected second task does not re-arm the timer while the first is still running', async (t) => {
    const { exit } = harness(t);
    const run = deferred();
    const { mod, restore } = freshClient({ env: { EVENT_ID: 'evt-1' }, executeCLIStreaming: () => run.promise });
    try {
      const wsA = makeWs();
      const wsB = makeWs();
      const taskA = mod.handleTask(wsA, makeMsg({ task_id: 'A' }));
      await flush();

      await mod.handleTask(wsB, makeMsg({ task_id: 'B' })); // rejected: agent busy
      assert.equal(wsB.sent.filter((m) => m.type === 'busy').length, 1);

      t.mock.timers.tick(IDLE_MS * 5);
      assert.equal(exit.mock.callCount(), 0, "rejected task B's finally re-armed the idle timer under running task A");

      run.resolve({ status: 'success', output: 'done' });
      await taskA;
      t.mock.timers.tick(IDLE_MS);
      assert.equal(exit.mock.callCount(), 1);
    } finally { restore(); }
  });

  it('is a no-op for non-ephemeral (persistent) sidecars: no idle exit is ever armed', async (t) => {
    const { exit } = harness(t);
    const { mod, restore } = freshClient({ env: { EVENT_ID: undefined } });
    try {
      mod.resetIdleTimer();
      await mod.handleTask(makeWs(), makeMsg());
      t.mock.timers.tick(IDLE_MS * 100);
      assert.equal(exit.mock.callCount(), 0);
    } finally { restore(); }
  });
});

describe('ws-client per-task backstop timer', () => {
  it('fires only after window + grace (not at the bare window), kills the child, reports a retryable error, clears the task', async (t) => {
    harness(t);
    const run = deferred();
    const killed = [];
    const { mod, state, restore } = freshClient({ executeCLIStreaming: () => run.promise });
    try {
      const ws = makeWs();
      const task = mod.handleTask(ws, makeMsg());
      await flush();
      const child = new EventEmitter();
      Object.assign(child, { exitCode: null, signalCode: null, kill: (s) => { killed.push(s); } });
      state.getCurrentTask().child = child;

      t.mock.timers.tick(TASK_TIMEOUT_SEC * 1000); // the old behaviour fired here and raced the executor watchdog
      assert.equal(errorsOf(ws).length, 0, 'backstop fired at the bare inactivity window (no grace buffer)');
      t.mock.timers.tick(BACKSTOP_MS - TASK_TIMEOUT_SEC * 1000 - 1);
      assert.equal(errorsOf(ws).length, 0);
      t.mock.timers.tick(1);

      const errs = errorsOf(ws);
      assert.equal(errs.length, 1);
      assert.equal(errs[0].retryable, true);
      assert.equal(errs[0].task_id, 't1');
      assert.match(errs[0].error, new RegExp(`timed out after ${TASK_TIMEOUT_SEC}s`));
      assert.deepEqual(killed.slice(0, 1), ['SIGTERM']);
      assert.equal(state.getCurrentTask(), null);

      run.resolve({ status: 'failed', stderr: 'killed', stdout: '' });
      await task;
      assert.equal(resultsOf(ws).length, 0, 'a result must not be sent for a task the backstop already terminated');
    } finally { restore(); }
  });

  it('is re-armed by activity (onActivity and progress frames), each time a full window + grace', async (t) => {
    harness(t);
    const run = deferred();
    let proxy;
    const { mod, restore } = freshClient({ executeCLIStreaming: (p) => { proxy = p; return run.promise; } });
    try {
      const ws = makeWs();
      const task = mod.handleTask(ws, makeMsg());
      await flush();

      t.mock.timers.tick(BACKSTOP_MS - 1000);
      proxy.onActivity();
      t.mock.timers.tick(BACKSTOP_MS - 1);
      assert.equal(errorsOf(ws).length, 0, 'onActivity did not re-arm the backstop');

      proxy.send(JSON.stringify({ type: 'progress', message: 'still working' }));
      t.mock.timers.tick(BACKSTOP_MS - 1);
      assert.equal(errorsOf(ws).length, 0, 'a progress frame did not re-arm the backstop');
      assert.ok(ws.sent.some((m) => m.type === 'progress' && m.task_id === 't1'), 'progress must be forwarded with task_id');

      t.mock.timers.tick(1);
      assert.equal(errorsOf(ws).length, 1);

      run.resolve({ status: 'failed', stderr: '', stdout: '' });
      await task;
    } finally { restore(); }
  });

  it('is bound to its own taskId: stale activity from a previous task never arms or resets a timer on the current task', async (t) => {
    harness(t);
    const run = deferred();
    let staleProxy;
    const { mod, state, restore } = freshClient({ executeCLIStreaming: (p) => { staleProxy = p; return run.promise; } });
    try {
      const wsA = makeWs();
      const taskA = mod.handleTask(wsA, makeMsg({ task_id: 'A' }));
      await flush();
      t.mock.timers.tick(BACKSTOP_MS); // A's backstop fires and drops A
      assert.equal(errorsOf(wsA).length, 1);
      assert.equal(state.getCurrentTask(), null);

      // Task B becomes current (its own timer handling is not under test here).
      const wsB = makeWs();
      state.setCurrentTask({ eventId: 'e2', ws: wsB, taskId: 'B', child: null, role: 'developer' });

      staleProxy.onActivity(); // late chunk from A's still-dying child
      staleProxy.send(JSON.stringify({ type: 'progress', message: 'zombie output' }));
      assert.equal(state.getCurrentTask().timer, undefined, "stale activity attached a timer to task B");
      t.mock.timers.tick(BACKSTOP_MS * 10);
      assert.equal(errorsOf(wsB).length, 0, "stale activity leaked a backstop onto task B");
      assert.equal(state.getCurrentTask()?.taskId, 'B', 'task B was cleared by a timer from task A');

      run.resolve({ status: 'failed', stderr: '', stdout: '' });
      await taskA;
      assert.equal(state.getCurrentTask()?.taskId, 'B', "task A's teardown clobbered task B");
    } finally { restore(); }
  });

  it('is torn down when the task completes: no late timeout error after a successful result', async (t) => {
    harness(t);
    const { mod, state, restore } = freshClient();
    try {
      const ws = makeWs();
      await mod.handleTask(ws, makeMsg());
      assert.equal(resultsOf(ws).length, 1);
      assert.equal(state.getCurrentTask(), null);
      t.mock.timers.tick(BACKSTOP_MS * 10);
      assert.equal(errorsOf(ws).length, 0);
    } finally { restore(); }
  });

  it('honours TASK_TIMEOUT_DEFAULT for non-implement modes and ignores a non-positive env override', async (t) => {
    harness(t);
    const run = deferred();
    const { mod, restore } = freshClient({
      env: { TASK_TIMEOUT_DEFAULT: '20', TASK_TIMEOUT_IMPLEMENT: '-5' },
      executeCLIStreaming: () => run.promise,
    });
    try {
      const wsDefault = makeWs();
      const taskDefault = mod.handleTask(wsDefault, makeMsg({ mode: 'investigate' }));
      await flush();
      t.mock.timers.tick(20000 + GRACE_MS - 1);
      assert.equal(errorsOf(wsDefault).length, 0);
      t.mock.timers.tick(1);
      assert.match(errorsOf(wsDefault)[0].error, /timed out after 20s/);
      run.resolve({ status: 'failed', stderr: '', stdout: '' });
      await taskDefault;
    } finally { restore(); }
  });
});

describe('ws-client cancellation before CLI spawn', () => {
  it('does not spawn the CLI when the task is cancelled during the security_analyst pre-warm', async (t) => {
    harness(t);
    const { mod, state, calls, restore } = freshClient();
    try {
      const cp = require('child_process');
      let execCalls = 0;
      t.mock.method(cp, 'exec', (cmd, opts, cb) => {
        execCalls++;
        if (execCalls === 1) state.clearCurrentTask(); // Brain cancel / disconnect lands mid pre-warm
        setImmediate(() => cb(null));
        return new EventEmitter();
      });

      const ws = makeWs();
      await mod.handleTask(ws, makeMsg({ role: 'security_analyst' }));

      assert.equal(calls.execute.length, 0, 'CLI was spawned for a task that was cancelled during pre-warm (orphan)');
      assert.equal(resultsOf(ws).length, 0);
      assert.equal(errorsOf(ws).length, 0);
      assert.equal(state.getCurrentTask(), null);
    } finally { restore(); }
  });

  it('positive control: an uncancelled security_analyst task still spawns the CLI after pre-warm', async (t) => {
    harness(t);
    const { mod, calls, restore } = freshClient();
    try {
      t.mock.method(require('child_process'), 'exec', (cmd, opts, cb) => { setImmediate(() => cb(null)); return new EventEmitter(); });
      const ws = makeWs();
      await mod.handleTask(ws, makeMsg({ role: 'security_analyst' }));
      assert.equal(calls.execute.length, 1);
      assert.equal(resultsOf(ws).length, 1);
    } finally { restore(); }
  });

  it('does not retry when the task is cancelled during the 429 backoff wait', async (t) => {
    harness(t);
    const { mod, state, config, calls, restore } = freshClient({
      env: { TASK_TIMEOUT_IMPLEMENT: '600' }, // window must exceed the 60s backoff, else the backstop legitimately ends the task first
      executeCLIStreaming: async () => ({ status: 'failed', stderr: '429 Too Many Requests', stdout: '' }),
    });
    try {
      const ws = makeWs();
      const task = mod.handleTask(ws, makeMsg());
      await flush();
      assert.equal(calls.execute.length, 1);
      assert.ok(ws.sent.some((m) => m.type === 'progress' && /Rate limited \(429\)/.test(m.message)), 'expected the 429 retry notice');

      state.clearCurrentTask(); // cancelled while waiting out the backoff
      t.mock.timers.tick(config.CLI_429_INITIAL_DELAY_MS);
      await task;

      assert.equal(calls.execute.length, 1, 'CLI was re-spawned after the task was cancelled during the 429 wait');
      assert.equal(resultsOf(ws).length, 0);
    } finally { restore(); }
  });

  it('positive control: an uncancelled 429 still retries after the backoff and reports the recovered result', async (t) => {
    harness(t);
    let n = 0;
    const { mod, config, calls, restore } = freshClient({
      env: { TASK_TIMEOUT_IMPLEMENT: '600' },
      executeCLIStreaming: async () => (++n === 1
        ? { status: 'failed', stderr: '429 Too Many Requests', stdout: '' }
        : { status: 'success', output: 'recovered' }),
    });
    try {
      const ws = makeWs();
      const task = mod.handleTask(ws, makeMsg());
      await flush();
      t.mock.timers.tick(config.CLI_429_INITIAL_DELAY_MS);
      await task;
      assert.equal(calls.execute.length, 2);
      assert.equal(resultsOf(ws)[0].output, 'recovered');
    } finally { restore(); }
  });
});

// ---------------------------------------------------------------------------------------------------------------------
// Mutation-hardening: guards that are only observable through timer bookkeeping or a *different* current task.
// ---------------------------------------------------------------------------------------------------------------------

/** Counts every (mock) setTimeout created from now on. Call AFTER harness(t) enabled mock timers. */
function countTimers(t) {
  const orig = globalThis.setTimeout;
  const created = [];
  t.mock.method(globalThis, 'setTimeout', (...args) => { const h = orig(...args); created.push(h); return h; });
  return created;
}

describe('ws-client hardening: backstop sizing', () => {
  it('computeBackstopMs never exceeds the Node timer maximum, even when MAX_TASK_WALL_MS is already at it', () => {
    const { mod, config, restore } = freshClient({ env: { MAX_TASK_WALL_MS: '2147483647' } });
    try {
      assert.equal(mod.computeBackstopMs(10 ** 8), config.MAX_TIMER_MS);
    } finally { restore(); }
  });

  it('rejects non-positive TASK_TIMEOUT_IMPLEMENT / TASK_TIMEOUT_DEFAULT overrides and falls back to the role window', async (t) => {
    harness(t);
    for (const [env, mode] of [
      [{ TASK_TIMEOUT_IMPLEMENT: '-5', TASK_TIMEOUT_DEFAULT: undefined, MAX_TASK_WALL_MS: '600000' }, 'implement'],
      [{ TASK_TIMEOUT_IMPLEMENT: undefined, TASK_TIMEOUT_DEFAULT: '-5', MAX_TASK_WALL_MS: '600000' }, 'investigate'],
    ]) {
      const run = deferred();
      const { mod, restore } = freshClient({ env, executeCLIStreaming: () => run.promise });
      try {
        const ws = makeWs();
        const task = mod.handleTask(ws, makeMsg({ mode }));
        await flush();
        // A leaked "-5" would floor to a 1s window => backstop at 1s + grace = 16s.
        t.mock.timers.tick(GRACE_MS + 2000);
        assert.equal(errorsOf(ws).length, 0, `${mode}: negative timeout override was honoured`);
        run.resolve({ status: 'success', output: 'done' });
        await task;
      } finally { restore(); }
    }
  });
});

describe('ws-client hardening: idle timer bookkeeping', () => {
  it('handleTask cancels a pending idle timer on entry, and the callback refuses to exit during setup (before currentTask exists)', async (t) => {
    const { exit } = harness(t);
    const gate = deferred();
    const { mod, restore } = freshClient({ env: { EVENT_ID: 'evt-1' }, ensureEventDocument: () => gate.promise });
    try {
      const created = countTimers(t);
      mod.resetIdleTimer(); // armed before the task arrives
      const task = mod.handleTask(makeWs(), makeMsg());
      await flush(); // blocked in setup: _activeTasks === 1, state.getCurrentTask() === null
      const n = created.length;

      t.mock.timers.tick(IDLE_MS * 3);
      assert.equal(created.length, n, 'the idle timer armed before the task was not cancelled on handleTask entry');

      mod.resetIdleTimer(); // something re-arms it mid-setup
      t.mock.timers.tick(IDLE_MS * 3);
      assert.equal(exit.mock.callCount(), 0, 'idle callback exited while a task was in its setup phase');

      gate.resolve();
      await task;
    } finally { restore(); }
  });

  it('a busy-rejected second task neither arms nor re-arms an idle timer while the first task still runs', async (t) => {
    harness(t);
    const run = deferred();
    const { mod, restore } = freshClient({ env: { EVENT_ID: 'evt-1' }, executeCLIStreaming: () => run.promise });
    try {
      const taskA = mod.handleTask(makeWs(), makeMsg({ task_id: 'A' }));
      await flush();
      const created = countTimers(t);
      const n = created.length;
      await mod.handleTask(makeWs(), makeMsg({ task_id: 'B' })); // busy
      assert.equal(created.length, n, "busy-rejected task B armed an idle timer under running task A");
      run.resolve({ status: 'success', output: 'done' });
      await taskA;
    } finally { restore(); }
  });

  it('the idle timer is unref()d so it can never pin the process', async (t) => {
    harness(t);
    const { mod, restore } = freshClient({ env: { EVENT_ID: 'evt-1' } });
    try {
      const orig = globalThis.setTimeout;
      const unrefd = new Set();
      const created = [];
      t.mock.method(globalThis, 'setTimeout', (...args) => {
        const h = orig(...args);
        const realUnref = h.unref.bind(h);
        h.unref = () => { unrefd.add(h); return realUnref(); };
        created.push(h);
        return h;
      });
      mod.resetIdleTimer();
      assert.equal(created.length, 1);
      assert.ok(unrefd.has(created[0]), 'idle timer was not unref()d');
    } finally { restore(); }
  });
});

describe('ws-client hardening: a DIFFERENT task becoming current', () => {
  const otherTask = (ws, extra = {}) => ({ eventId: 'e2', ws, taskId: 'B', child: null, role: 'developer', ...extra });

  it("A's backstop firing after A was cancelled and B took over must not kill, error or clear B", async (t) => {
    harness(t);
    const run = deferred();
    const { mod, state, restore } = freshClient({ executeCLIStreaming: () => run.promise });
    try {
      const wsA = makeWs();
      const wsB = makeWs();
      const taskA = mod.handleTask(wsA, makeMsg({ task_id: 'A' }));
      await flush();
      state.clearCurrentTask(); // A cancelled; its runTask is still awaiting the executor
      const killed = [];
      state.setCurrentTask(otherTask(wsB, { child: { exitCode: null, signalCode: null, kill: (s) => killed.push(s) } }));

      t.mock.timers.tick(BACKSTOP_MS * 3); // A's backstop fires here
      assert.deepEqual(killed, [], "A's backstop killed B's child");
      assert.equal(errorsOf(wsA).length, 0);
      assert.equal(errorsOf(wsB).length, 0);
      assert.equal(state.getCurrentTask()?.taskId, 'B', "A's backstop cleared task B");

      run.resolve({ status: 'failed', stderr: '', stdout: '' });
      await taskA;
      assert.equal(state.getCurrentTask()?.taskId, 'B');
    } finally { restore(); }
  });

  it('does not spawn the CLI when another task became current during the pre-warm await', async (t) => {
    harness(t);
    const { mod, state, calls, restore } = freshClient();
    try {
      let n = 0;
      t.mock.method(require('child_process'), 'exec', (cmd, opts, cb) => {
        if (++n === 1) { state.clearCurrentTask(); state.setCurrentTask(otherTask(makeWs())); }
        setImmediate(() => cb(null));
        return new EventEmitter();
      });
      const ws = makeWs();
      await mod.handleTask(ws, makeMsg({ role: 'security_analyst' }));
      assert.equal(calls.execute.length, 0, 'CLI spawned for task A although task B is current');
      assert.equal(state.getCurrentTask()?.taskId, 'B');
      assert.equal(resultsOf(ws).length, 0);
    } finally { restore(); }
  });

  it('does not retry after the 429 wait when another task became current meanwhile', async (t) => {
    harness(t);
    const { mod, state, config, calls, restore } = freshClient({
      env: { TASK_TIMEOUT_IMPLEMENT: '600' },
      executeCLIStreaming: async () => ({ status: 'failed', stderr: '429 Too Many Requests', stdout: '' }),
    });
    try {
      const ws = makeWs();
      const task = mod.handleTask(ws, makeMsg());
      await flush();
      assert.equal(calls.execute.length, 1);
      state.clearCurrentTask();
      state.setCurrentTask(otherTask(makeWs()));
      t.mock.timers.tick(config.CLI_429_INITIAL_DELAY_MS);
      await task;
      assert.equal(calls.execute.length, 1, 'CLI re-spawned for task A although task B is current');
      assert.equal(state.getCurrentTask()?.taskId, 'B');
      assert.equal(resultsOf(ws).length, 0);
    } finally { restore(); }
  });
});
