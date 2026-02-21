// gemini-sidecar/http-handler.js
// @ai-rules:
// 1. [Pattern]: HTTP routing for /health, /callback, /execute. All state access via state.js getters/setters.
// 2. [Pattern]: /callback forwards sendResults/sendMessage/huddle_message — task_id and event_id from state.getCurrentTask().
// 3. [Gotcha]: huddle_message holds HTTP response in pendingHuddleReply until huddle_reply WS message or 45s timeout.
// 4. [Gotcha]: /execute concurrency guard — rejects with 429 if state.getCurrentTask() already set. Credentials setup before executeCLI.

const { executeCLI } = require('./cli-executor');
const {
  hasGitHubCredentials,
  generateInstallationToken,
  setupGitCredentials,
  setupGitHubTooling,
  hasGitLabCredentials,
  readGitLabToken,
  setupGitLabCredentials,
  setupGitLabTooling,
  setupCLILogins,
  GITLAB_HOST,
} = require('./credentials');
const state = require('./state');
const { AGENT_CLI, AGENT_MODEL, AGENT_ROLE, DEFAULT_WORK_DIR, PORT } = require('./config');
const { wsSend } = require('./ws-utils');
const fs = require('fs');

/**
 * Parse request body as JSON
 */
function parseBody(req) {
  return new Promise((resolve, reject) => {
    let body = '';
    req.on('data', chunk => body += chunk);
    req.on('end', () => {
      try {
        resolve(JSON.parse(body));
      } catch (e) {
        reject(new Error('Invalid JSON body'));
      }
    });
    req.on('error', reject);
  });
}

/**
 * HTTP request handler
 */
async function handleRequest(req, res) {
  const url = new URL(req.url, `http://localhost:${PORT}`);

  // Health check endpoint
  if (url.pathname === '/health' && req.method === 'GET') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      status: 'healthy',
      service: 'agent-sidecar',
      cliType: AGENT_CLI,
      cliModel: AGENT_MODEL,
      agentRole: AGENT_ROLE || 'default',
      toolRestrictions: AGENT_ROLE === 'architect' ? 'read-only (no file modification)' : 'full',
      hasGitHubCredentials: hasGitHubCredentials(),
      hasGitLabCredentials: hasGitLabCredentials(),
      hasArgocdCredentials: fs.existsSync('/secrets/argocd/auth-token'),
      hasKargoCredentials: fs.existsSync('/secrets/kargo/auth-token'),
      hasGitHubMCP: !!process.env.GH_TOKEN,
      hasGitLabMCP: !!process.env.GITLAB_TOKEN,
      gitlabHost: GITLAB_HOST,
    }));
    return;
  }

  // Agent callback endpoint (sendResults / sendMessage)
  if (url.pathname === '/callback' && req.method === 'POST') {
    try {
      const body = await parseBody(req);
      const callbackType = body.type || 'result';  // "result" or "message"
      const content = body.content || '';

      if (!content) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'content is required' }));
        return;
      }

      if (callbackType === 'result') {
        // sendResults: store as deliverable (last-write-wins)
        state.setCallbackResult(content);
        const task = state.getCurrentTask();
        const eid = task?.eventId || 'no-task';
        console.log(`[${new Date().toISOString()}] [${eid}] Callback result stored (${content.length} chars)`);
        // Forward as partial_result via WS if task is active
        if (task?.ws) {
          wsSend(task.ws, {
            type: 'partial_result',
            task_id: task?.taskId || '',
            event_id: eid,
            content,
          });
        }
      } else if (callbackType === 'huddle_message') {
        // HuddleSendMessage: forward to Manager, HOLD response until Manager replies
        const task = state.getCurrentTask();
        const eid3 = task?.eventId || 'no-task';
        console.log(`[${new Date().toISOString()}] [${eid3}] Huddle message forwarded (${content.length} chars), holding response...`);
        if (task?.ws) {
          wsSend(task.ws, {
            type: 'huddle_message',
            task_id: task?.taskId || '',
            event_id: eid3,
            content,
          });
          // Hold HTTP response -- Manager will reply via huddle_reply WS message
          const timeout = setTimeout(() => {
            if (state.getPendingHuddleReply()) {
              res.writeHead(408, { 'Content-Type': 'application/json' });
              res.end(JSON.stringify({ error: 'Manager reply timeout' }));
              state.clearPendingHuddleReply();
              console.log(`[${new Date().toISOString()}] [${eid3}] Huddle reply timed out (45s)`);
            }
          }, 45000);
          state.setPendingHuddleReply({ res, timeout });
          return; // do NOT respond yet -- response sent when huddle_reply arrives
        }
        // No WS available -- respond immediately with error
        res.writeHead(503, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'No active task connection' }));
        return;
      } else {
        // sendMessage: forward as progress note (do NOT overwrite deliverable)
        const task2 = state.getCurrentTask();
        const eid2 = task2?.eventId || 'no-task';
        console.log(`[${new Date().toISOString()}] [${eid2}] Callback message forwarded (${content.length} chars)`);
        if (task2?.ws) {
          wsSend(task2.ws, {
            type: 'progress',
            task_id: task2?.taskId || '',
            event_id: eid2,
            message: content,
            source: 'agent_message',
          });
        }
      }

      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ ok: true, type: callbackType }));
    } catch (err) {
      res.writeHead(400, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: err.message }));
    }
    return;
  }

  // Execute endpoint
  if (url.pathname === '/execute' && req.method === 'POST') {
    // Concurrency guard: reject if agent is already running a task
    if (state.getCurrentTask()) {
      res.writeHead(429, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'Agent busy', event_id: state.getCurrentTask()?.eventId || '' }));
      return;
    }

    try {
      const body = await parseBody(req);

      if (!body.prompt) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Missing required field: prompt' }));
        return;
      }

      const workDir = body.cwd || DEFAULT_WORK_DIR;
      state.resetCallbackResult(); // Reset stale callback from previous WS task

      // Setup git credentials + GitHub tooling if GitHub App is configured
      if (hasGitHubCredentials()) {
        try {
          const token = await generateInstallationToken();
          setupGitCredentials(token, workDir);
          setupGitHubTooling(token);
        } catch (err) {
          console.error(`[${new Date().toISOString()}] Git credential setup failed:`, err.message);
          console.log(`[${new Date().toISOString()}] Continuing without git credentials`);
        }
      }

      // Setup GitLab credentials + MCP tooling if token is available
      if (hasGitLabCredentials()) {
        try {
          const glToken = readGitLabToken();
          setupGitLabCredentials(glToken, workDir);
          setupGitLabTooling(glToken);
        } catch (err) {
          console.error(`[${new Date().toISOString()}] GitLab credential setup failed:`, err.message);
          console.log(`[${new Date().toISOString()}] Continuing without GitLab credentials`);
        }
      }

      // Login to ArgoCD/Kargo CLIs (awaited, with deduplication)
      await setupCLILogins();

      // Execute agent CLI
      const result = await executeCLI(body.prompt, {
        autoApprove: body.autoApprove || false,
        cwd: workDir,
      });

      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(result));

    } catch (err) {
      console.error(`[${new Date().toISOString()}] Error:`, err.message);
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({
        status: 'error',
        message: err.message
      }));
    }
    return;
  }

  // 404 for unknown routes
  res.writeHead(404, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify({ error: 'Not found' }));
}

module.exports = { handleRequest, parseBody };
