// gemini-sidecar/ws-client.js
// @ai-rules:
// 1. [Pattern]: Sidecar connects TO Brain as WS client. Persistent connection with reconnect backoff.
// 2. [Pattern]: All outgoing messages include task_id for Queue correlation on Brain side.
// 3. [Pattern]: Per-task timeout timer resets on progress. SIGTERM/SIGKILL on expiry.
// 4. [Pattern]: Reconnect backoff: 1s, 2s, 4s, 8s, max 30s. Re-register after reconnect.
// 5. [Constraint]: state.setCurrentTask includes ws + taskId (fixes pre-existing bug from legacy mode).
// 6. [Pattern]: proactive_message from Brain -> pushInboundMessage. Messages during WS disconnect are lost.
// 7. [Pattern]: 429 retry loop wraps executeCLIStreaming. Conditions: failed + is429Error + no callback result. resetTimer before/after backoff wait.
// 8. [Pattern]: _activeWs tracks live WS connection. tryWake() resumes idle agents on teammate/proactive messages via handleTask with saved session context.
// 9. [Pattern]: Mode-based skill filtering: restoreAllSkills() (defensive) + filterSkillsByMode(mode) before CLI spawn; restoreAllSkills() in finally block.

const WebSocket = require('ws');
const os = require('os');
const { executeCLIStreaming, prepareResultsDir, is429Error } = require('./cli-executor');
const {
  hasGitHubCredentials, generateInstallationToken, setupGitCredentials, setupGitHubTooling,
  hasGitLabCredentials, readGitLabToken, setupGitLabCredentials, setupGitLabTooling,
  setupArgoCDMCP, setupCLILogins, GITLAB_HOST,
} = require('./credentials');
const state = require('./state');
const {
  DEFAULT_WORK_DIR, AGENT_CLI, AGENT_MODEL, AGENT_ROLE,
  CLI_429_MAX_RETRIES, CLI_429_INITIAL_DELAY_MS, CLI_429_BACKOFF_MULTIPLIER,
} = require('./config');
const { wsSend } = require('./ws-utils');
const { filterSkillsByMode, restoreAllSkills } = require('./cli-setup');

const BACKOFF_MIN = 1000;
const BACKOFF_MAX = 30000;
let _activeWs = null;
let _isWaking = false;

function killChild(child) {
  child.kill('SIGTERM');
  const t = setTimeout(() => { if (!child.killed) child.kill('SIGKILL'); }, 5000);
  child.on('exit', () => clearTimeout(t));
}

function sendMsg(ws, taskId, data) {
  wsSend(ws, { ...data, task_id: taskId });
}

function startWSClient(brainUrl) {
  const agentId = `${AGENT_ROLE}-${os.hostname()}`;
  let backoff = BACKOFF_MIN;
  let reconnectTimer = null;

  function connect() {
    const ws = new WebSocket(brainUrl);

    ws.on('open', () => {
      _activeWs = ws;
      console.log(`[${new Date().toISOString()}] Connected to Brain: ${brainUrl}`);
      if (backoff > BACKOFF_MIN) {
        console.warn(`[${new Date().toISOString()}] WS reconnected -- inbound messages during disconnect were lost`);
      }
      backoff = BACKOFF_MIN;
      wsSend(ws, {
        type: 'register', agent_id: agentId, role: AGENT_ROLE,
        capabilities: [], cli: AGENT_CLI, model: AGENT_MODEL,
      });
    });

    ws.on('message', async (raw) => {
      let msg;
      try { msg = JSON.parse(raw.toString()); } catch (e) { return; }
      if (msg.type === 'task') await handleTask(ws, msg);
      else if (msg.type === 'cancel') handleCancel(msg);
      else if (msg.type === 'ping') wsSend(ws, { type: 'pong' });
      else if (msg.type === 'huddle_reply') {
        // Brain replied to a HuddleSendMessage -- resolve the held HTTP response
        const pending = state.getPendingHuddleReply();
        if (pending) {
          clearTimeout(pending.timeout);
          pending.res.writeHead(200, { 'Content-Type': 'application/json' });
          pending.res.end(JSON.stringify({ reply: msg.content || '' }));
          state.clearPendingHuddleReply();
          console.log(`[${new Date().toISOString()}] Huddle reply delivered (${(msg.content || '').length} chars)`);
        }
      } else if (msg.type === 'proactive_message') {
        state.pushInboundMessage({
          from: msg.from || 'brain',
          content: msg.content || '',
        });
        console.log(`[${new Date().toISOString()}] Proactive message received (${(msg.content || '').length} chars)`);
        tryWake(msg.from || 'brain', msg.content || '');
      }
    });

    ws.on('close', () => {
      _activeWs = null;
      console.log(`[${new Date().toISOString()}] Disconnected from Brain`);
      cleanupActiveTask();
      scheduleReconnect();
    });

    ws.on('error', (err) => {
      _activeWs = null;
      console.error(`[${new Date().toISOString()}] WS error: ${err.message}`);
      cleanupActiveTask();
      scheduleReconnect();
    });
  }

  function scheduleReconnect() {
    if (reconnectTimer) return;
    console.log(`[${new Date().toISOString()}] Reconnecting in ${backoff}ms`);
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      backoff = Math.min(backoff * 2, BACKOFF_MAX);
      connect();
    }, backoff);
  }

  function cleanupActiveTask() {
    const task = state.getCurrentTask();
    if (!task?.child) return;
    console.log(`[${new Date().toISOString()}] Killing orphan for ${task.eventId} (disconnect)`);
    if (task.timer) clearTimeout(task.timer);
    killChild(task.child);
    state.clearCurrentTask();
  }

  connect();
}

async function handleTask(ws, msg) {
  const taskId = msg.task_id;
  const eventId = msg.event_id || 'unknown';
  const prompt = msg.prompt;
  const workDir = msg.cwd || DEFAULT_WORK_DIR;
  const autoApprove = msg.autoApprove || false;
  const sessionId = msg.session_id || null;

  if (state.getCurrentTask()) {
    sendMsg(ws, taskId, { type: 'error', event_id: eventId, message: 'Agent busy, task rejected.' });
    return;
  }
  if (!prompt) {
    sendMsg(ws, taskId, { type: 'error', event_id: eventId, message: 'Missing prompt' });
    return;
  }

  state.resetCallbackResult();
  console.log(`[${new Date().toISOString()}] Task ${taskId}: ${eventId} (${prompt.length} chars, session: ${sessionId})`);

  if (hasGitHubCredentials()) {
    try {
      const token = await generateInstallationToken();
      setupGitCredentials(token, workDir);
      setupGitHubTooling(token);
      sendMsg(ws, taskId, { type: 'progress', event_id: eventId, message: 'GitHub credentials configured' });
    } catch (err) {
      sendMsg(ws, taskId, { type: 'progress', event_id: eventId, message: `GitHub creds failed: ${err.message}, continuing...` });
    }
  }
  if (hasGitLabCredentials()) {
    try {
      const glToken = readGitLabToken();
      setupGitLabCredentials(glToken, workDir);
      setupGitLabTooling(glToken);
      sendMsg(ws, taskId, { type: 'progress', event_id: eventId, message: `GitLab credentials configured (${GITLAB_HOST})` });
    } catch (err) {
      sendMsg(ws, taskId, { type: 'progress', event_id: eventId, message: `GitLab creds failed: ${err.message}, continuing...` });
    }
  }
  await setupArgoCDMCP();
  sendMsg(ws, taskId, { type: 'progress', event_id: eventId, message: 'ArgoCD MCP configured' });
  await setupCLILogins();

  const mode = msg.mode || '';
  const timeoutSec = mode.includes('implement')
    ? parseInt(process.env.TASK_TIMEOUT_IMPLEMENT) || 1800
    : parseInt(process.env.TASK_TIMEOUT_DEFAULT) || 600;

  function resetTimer() {
    const task = state.getCurrentTask();
    if (task?.timer) clearTimeout(task.timer);
    const timer = setTimeout(() => {
      const t = state.getCurrentTask();
      if (!t?.child || t.taskId !== taskId) return;
      console.log(`[${new Date().toISOString()}] Task ${taskId} timed out (${timeoutSec}s)`);
      killChild(t.child);
      sendMsg(ws, taskId, {
        type: 'error', event_id: eventId, retryable: true,
        error: `Task timed out after ${timeoutSec}s`,
      });
      state.clearCurrentTask();
    }, timeoutSec * 1000);
    if (task) task.timer = timer;
  }

  const wsProxy = {
    get readyState() { return ws.readyState; },
    send(raw) {
      try {
        const obj = JSON.parse(raw);
        obj.task_id = taskId;
        ws.send(JSON.stringify(obj));
        if (obj.type === 'progress') resetTimer();
      } catch (e) { ws.send(raw); }
    },
  };

  try {
    // Set full task state BEFORE execution so callbacks (sendResults, sendMessage)
    // can access ws + taskId immediately. executeCLIStreaming will overwrite the child field.
    state.setCurrentTask({ eventId, ws, taskId, cwd: workDir, child: null });
    resetTimer();

    restoreAllSkills();
    filterSkillsByMode(mode);

    let result;
    let retryDelay = CLI_429_INITIAL_DELAY_MS;
    let retriesTaken = 0;

    for (let attempt = 0; attempt <= CLI_429_MAX_RETRIES; attempt++) {
      if (attempt > 0) {
        resetTimer();
        console.log(`[429-RETRY] attempt ${attempt}/${CLI_429_MAX_RETRIES}, waiting ${retryDelay / 1000}s (event: ${eventId})`);
        sendMsg(ws, taskId, {
          type: 'progress', event_id: eventId,
          message: `Rate limited (429). Retrying in ${retryDelay / 1000}s... (attempt ${attempt + 1})`,
        });
        await new Promise(r => setTimeout(r, retryDelay));
        retryDelay *= CLI_429_BACKOFF_MULTIPLIER;

        prepareResultsDir(workDir);
        state.resetCallbackResult();
        resetTimer();
        retriesTaken = attempt;
      }

      try {
        result = await executeCLIStreaming(wsProxy, eventId, prompt, {
          autoApprove, cwd: workDir, sessionId,
        });
      } catch (spawnErr) {
        if (attempt < CLI_429_MAX_RETRIES) {
          console.log(`[429-RETRY] spawn error on attempt ${attempt + 1}, will retry: ${spawnErr.message}`);
          result = { status: 'failed', stderr: spawnErr.message, stdout: '' };
          continue;
        }
        throw spawnErr;
      }

      if (result.status !== 'failed') break;
      if (!is429Error(result.stderr)) break;
      if (state.getCallbackResult()) {
        result = { ...result, status: 'success', output: state.getCallbackResult(), source: 'callback' };
        break;
      }
    }

    if (result.status !== 'failed' && retriesTaken > 0) {
      console.log(`[429-RETRY] Recovered after ${retriesTaken} retries for ${eventId}`);
    }
    if (result.status === 'failed' && is429Error(result.stderr)) {
      console.log(`[429-RETRY] All retries exhausted for ${eventId}, returning failed result`);
    }

    const cur = state.getCurrentTask();
    if (cur?.timer) clearTimeout(cur.timer);
    if (cur?.taskId === taskId) {
      sendMsg(ws, taskId, {
        type: 'result', event_id: eventId, session_id: result.sessionId || null,
        status: result.status, output: result.output || result.stdout || '',
        source: result.source || 'stdout',
      });
      state.saveLastTaskContext({ sessionId: result.sessionId || null, eventId, cwd: workDir });
      state.clearCurrentTask();
    }
  } catch (err) {
    const cur = state.getCurrentTask();
    if (cur?.timer) clearTimeout(cur.timer);
    if (cur?.taskId === taskId) {
      sendMsg(ws, taskId, { type: 'error', event_id: eventId, message: err.message });
      state.saveLastTaskContext({ sessionId: cur?.sessionId || null, eventId, cwd: workDir });
      state.clearCurrentTask();
    }
  } finally {
    restoreAllSkills();
  }
}

function handleCancel(msg) {
  const task = state.getCurrentTask();
  if (!task?.child || task.taskId !== msg.task_id) return;
  console.log(`[${new Date().toISOString()}] Cancelling task ${msg.task_id}`);
  if (task.timer) clearTimeout(task.timer);
  killChild(task.child);
  sendMsg(task.ws, msg.task_id, {
    type: 'error', event_id: task.eventId,
    error: 'Cancelled by Brain', retryable: false,
  });
  state.clearCurrentTask();
}

function tryWake(from, content) {
  if (state.getCurrentTask()) return;
  const ctx = state.getLastTaskContext();
  if (!ctx) return;
  if (_isWaking) return;
  if (!_activeWs) return;

  _isWaking = true;
  const syntheticMsg = {
    type: 'task',
    task_id: `wake-${Date.now()}`,
    event_id: ctx.eventId,
    session_id: ctx.sessionId,
    prompt: 'You have a pending message from your teammate. Check your inbox and respond.',
    cwd: ctx.cwd,
    autoApprove: true,
    mode: 'implement',
  };
  console.log(`[${new Date().toISOString()}] Wake triggered: resuming session ${ctx.sessionId} for event ${ctx.eventId} (from: ${from})`);
  handleTask(_activeWs, syntheticMsg)
    .catch(err => console.error(`[${new Date().toISOString()}] Wake failed:`, err.message))
    .finally(() => { _isWaking = false; });
}

module.exports = { startWSClient, tryWake };
