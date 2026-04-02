// gemini-sidecar/http-handler.js
// @ai-rules:
// 1. [Pattern]: HTTP routing for /health, /messages, /teammate-notes, /callback, /execute, /proxy/*. All state via state.js.
// 2. [Pattern]: /callback forwards sendResults/sendMessage/huddle_message/teammate_forward — task_id and event_id from state.getCurrentTask().
// 3. [Gotcha]: huddle_message holds HTTP response in pendingHuddleReply until huddle_reply WS message or 90s timeout.
// 4. [Gotcha]: /execute concurrency guard — rejects with 429 if state.getCurrentTask() already set.
// 5. [Pattern]: GET /messages drains _inboundMessages (Manager proactive). GET /teammate-notes drains _teammateMessages (peer reads).
// 6. [Pattern]: /proxy/* endpoints forward GET requests to Brain API at BRAIN_HTTP_URL || localhost:8000. Read-only, no auth.
// 7. [Gotcha]: /proxy/turns returns empty response if no active task (eventId is null).

const { executeCLI } = require('./cli-executor');
const { tryWake } = require('./ws-client');
const {
  hasGitHubCredentials,
  generateInstallationToken,
  setupGitCredentials,
  setupGitHubTooling,
  hasGitLabCredentials,
  readGitLabToken,
  setupGitLabCredentials,
  setupGitLabTooling,
  setupArgoCDMCP,
  setupCLILogins,
  GITLAB_HOST,
} = require('./credentials');
const state = require('./state');
const { AGENT_CLI, AGENT_MODEL, AGENT_ROLE, DEFAULT_WORK_DIR, PORT, BRAIN_HTTP_URL } = require('./config');
const { wsSend } = require('./ws-utils');
const fs = require('fs');
const http = require('http');

const BRAIN_BASE = BRAIN_HTTP_URL || 'http://localhost:8000';

function proxyGet(brainPath) {
  return new Promise((resolve, reject) => {
    const url = new URL(brainPath, BRAIN_BASE);
    http.get(url.href, { timeout: 10000 }, (resp) => {
      let data = '';
      resp.on('data', c => data += c);
      resp.on('end', () => {
        try { resolve(JSON.parse(data)); }
        catch { resolve(data); }
      });
    }).on('error', reject).on('timeout', function() { this.destroy(); reject(new Error('Brain proxy timeout')); });
  });
}

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

  // =========================================================================
  // Claude Code HTTP hook endpoints — return 2xx ALWAYS
  // =========================================================================

  if (url.pathname === '/hooks/pre-tool-use' && req.method === 'POST') {
    try {
      const bbTurns = state.getBlackboardTurnsSince(state.getHookHighwater());
      const inbound = state.drainInboundMessages();
      const teammate = state.drainTeammateMessages();
      const parts = [];
      if (bbTurns.length > 0) {
        const summary = bbTurns.map(t => `[${t.actor || '?'}.${t.action || '?'}] ${(t.thoughts || t.result || '').slice(0, 120)}`).join('; ');
        parts.push(`Blackboard: ${bbTurns.length} new turn(s) — ${summary}`);
        const maxTurn = bbTurns.reduce((m, t) => Math.max(m, t.turn || 0), state.getHookHighwater());
        state.setHookHighwater(maxTurn);
      }
      if (inbound.length > 0) {
        parts.push(`Brain messages: ${inbound.map(m => m.content || '').join('; ')}`);
      }
      if (teammate.length > 0) {
        parts.push(`Teammate: ${teammate.map(m => `(${m.from}) ${m.content || ''}`).join('; ')}`);
      }
      res.writeHead(200, { 'Content-Type': 'application/json' });
      if (parts.length > 0) {
        const ctx = parts.join('\n');
        console.log(`[${new Date().toISOString()}] PreToolUse hook: injecting ${bbTurns.length} bb turns, ${inbound.length} brain msgs, ${teammate.length} teammate msgs`);
        res.end(JSON.stringify({ hookSpecificOutput: { hookEventName: 'PreToolUse', additionalContext: ctx } }));
      } else {
        res.end('{}');
      }
    } catch (err) {
      console.error(`[${new Date().toISOString()}] PreToolUse hook error: ${err.message}`);
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end('{}');
    }
    return;
  }

  if (url.pathname === '/hooks/stop' && req.method === 'POST') {
    try {
      const body = await parseBody(req).catch(() => ({}));
      if (body.stop_hook_active) {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end('{}');
        return;
      }
      const hasResults = !!state.getCallbackResult();
      const pendingInbound = state.peekInboundMessages();
      const pendingTeammate = state.peekTeammateMessages();
      if (!hasResults) {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ decision: 'block', reason: 'You must call team_send_results with your final findings before finishing. Summarize your work and deliver results now.' }));
        return;
      }
      if (pendingInbound.length > 0 || pendingTeammate.length > 0) {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ decision: 'block', reason: 'You have unread messages from the Brain or your teammate. Process them before finishing.' }));
        return;
      }
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end('{}');
    } catch (err) {
      console.error(`[${new Date().toISOString()}] Stop hook error: ${err.message}`);
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end('{}');
    }
    return;
  }

  if (url.pathname === '/hooks/session-start' && req.method === 'POST') {
    try {
      const task = state.getCurrentTask();
      const eid = task?.eventId || 'unknown';
      const role = AGENT_ROLE || 'unknown';
      let context = `Event ${eid} — you are ${role}.`;
      try {
        const data = await proxyGet(`/queue/${eid}/turns?role=${role}`);
        if (data.turns && data.turns.length > 0) {
          const last5 = data.turns.slice(-5);
          const summary = last5.map(t => `[${t.actor || '?'}.${t.action || '?'}] ${(t.thoughts || t.result || '').slice(0, 80)}`).join('; ');
          context += ` Status: ${data.event_status}. Last ${last5.length} turns: ${summary}`;
        }
      } catch { /* Brain unavailable — return minimal context */ }
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ hookSpecificOutput: { hookEventName: 'SessionStart', additionalContext: context } }));
    } catch (err) {
      console.error(`[${new Date().toISOString()}] SessionStart hook error: ${err.message}`);
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end('{}');
    }
    return;
  }

  // Inbound message inbox (Manager proactive messages, drained on read)
  if (url.pathname === '/messages' && req.method === 'GET') {
    const msgs = state.drainInboundMessages();
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(msgs));
    return;
  }

  // Teammate notes (forwarded by teammate; drained by this sidecar's GET — hook or team_read_teammate_notes)
  if (url.pathname === '/teammate-notes' && req.method === 'GET') {
    const msgs = state.drainTeammateMessages();
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(msgs));
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
              console.log(`[${new Date().toISOString()}] [${eid3}] Huddle reply timed out (90s)`);
            }
          }, 90000);
          state.setPendingHuddleReply({ res, timeout });
          return; // do NOT respond yet -- response sent when huddle_reply arrives
        }
        // No WS available -- respond immediately with error
        res.writeHead(503, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'No active task connection' }));
        return;
      } else if (callbackType === 'teammate_forward') {
        state.pushTeammateMessage({ from: body.from || 'unknown', content });
        console.log(`[${new Date().toISOString()}] Teammate message stored (${content.length} chars, from: ${body.from || 'unknown'})`);
        tryWake(body.from || 'unknown', content, body.event_id || '');
      } else if (callbackType === 'teammate_message') {
        const task = state.getCurrentTask();
        if (task?.ws) {
          wsSend(task.ws, {
            type: 'agent_teammate_message',
            task_id: task?.taskId || '',
            event_id: task?.eventId || '',
            content,
            from: AGENT_ROLE || 'unknown',
          });
          console.log(`[${new Date().toISOString()}] Teammate message mirrored to blackboard (${content.length} chars)`);
        }
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

      // Configure ArgoCD MCP server (session API -> JWT per-task)
      await setupArgoCDMCP();

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

  // =========================================================================
  // Blackboard local cache endpoints — read from WebSocket-fed state.js
  // =========================================================================

  if (url.pathname === '/blackboard/sync-highwater' && req.method === 'POST') {
    try {
      const body = await parseBody(req);
      const hw = parseInt(body.highwater || '0', 10);
      if (hw > state.getHookHighwater()) state.setHookHighwater(hw);
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ highwater: state.getHookHighwater() }));
    } catch {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ highwater: state.getHookHighwater() }));
    }
    return;
  }

  if (url.pathname === '/blackboard/turns' && req.method === 'GET') {
    const since = parseInt(url.searchParams.get('since') || '0', 10);
    const turns = state.getBlackboardTurnsSince(since);
    const { status, total } = state.getBlackboardStatus();
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ turns, total, event_status: status, since }));
    return;
  }

  if (url.pathname === '/blackboard/status' && req.method === 'GET') {
    const { status, total, highwater } = state.getBlackboardStatus();
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ event_status: status, total, highwater }));
    return;
  }

  // =========================================================================
  // Proxy endpoints — forward to Brain API (read-only)
  // =========================================================================

  if (url.pathname === '/proxy/turns' && req.method === 'GET') {
    const task = state.getCurrentTask();
    const eventId = task?.eventId;
    if (!eventId) {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ turns: [], total: 0, event_status: 'unknown', gap_from_turn: 0, role_last_seen_turn: 0 }));
      return;
    }
    try {
      const since = url.searchParams.get('since');
      let brainPath = `/queue/${eventId}/turns?role=${AGENT_ROLE || ''}`;
      if (since) brainPath += `&since=${since}`;
      const data = await proxyGet(brainPath);
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(data));
    } catch (err) {
      res.writeHead(502, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: `Brain proxy failed: ${err.message}` }));
    }
    return;
  }

  if (url.pathname === '/proxy/active-events' && req.method === 'GET') {
    try {
      const data = await proxyGet('/queue/active');
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(data));
    } catch (err) {
      res.writeHead(502, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: `Brain proxy failed: ${err.message}` }));
    }
    return;
  }

  if (url.pathname.startsWith('/proxy/journal') && req.method === 'GET') {
    try {
      const service = url.pathname.replace('/proxy/journal', '').replace(/^\//, '');
      const brainPath = service ? `/api/journal/${service}` : '/api/journal/';
      const data = await proxyGet(brainPath);
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(data));
    } catch (err) {
      res.writeHead(502, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: `Brain proxy failed: ${err.message}` }));
    }
    return;
  }

  if (url.pathname.startsWith('/proxy/service/') && req.method === 'GET') {
    try {
      const name = url.pathname.replace('/proxy/service/', '');
      const data = await proxyGet(`/topology/service/${name}`);
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(data));
    } catch (err) {
      res.writeHead(502, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: `Brain proxy failed: ${err.message}` }));
    }
    return;
  }

  if (url.pathname === '/proxy/topology/mermaid' && req.method === 'GET') {
    try {
      const data = await proxyGet('/topology/mermaid');
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(data));
    } catch (err) {
      res.writeHead(502, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: `Brain proxy failed: ${err.message}` }));
    }
    return;
  }

  // 404 for unknown routes
  res.writeHead(404, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify({ error: 'Not found' }));
}

module.exports = { handleRequest, parseBody };
