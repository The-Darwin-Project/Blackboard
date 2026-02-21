// gemini-sidecar/ws-server.js
// @ai-rules:
// 1. [Pattern]: Legacy WS server — clients connect TO sidecar. Message types: task, followup, cancel.
// 2. [Pattern]: All shared state via state.js. Concurrency guard — rejects task if getCurrentTask() already set.
// 3. [Pattern]: Credentials (GitHub, GitLab, ArgoCD, Kargo) set up per task before executeCLIStreaming.
// 4. [Gotcha]: On ws.close, kills orphaned child process (SIGTERM then SIGKILL after 5s) and clears currentTask.

const { executeCLIStreaming } = require('./cli-executor');
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
const { DEFAULT_WORK_DIR } = require('./config');
const { wsSend } = require('./ws-utils');

function setupWSServer(wss) {
  wss.on('connection', (ws) => {
    console.log(`[${new Date().toISOString()}] WebSocket client connected`);

    ws.on('message', async (data) => {
      let msg;
      try {
        msg = JSON.parse(data.toString());
      } catch (e) {
        ws.send(JSON.stringify({ type: 'error', message: 'Invalid JSON' }));
        return;
      }

      if (msg.type === 'task') {
        // Reject if already busy
        if (state.getCurrentTask()) {
          ws.send(JSON.stringify({
            type: 'busy',
            event_id: msg.event_id || '',
            message: 'Agent busy, task rejected. One task at a time.',
          }));
          return;
        }

        const eventId = msg.event_id || 'unknown';
        const prompt = msg.prompt;
        const workDir = msg.cwd || DEFAULT_WORK_DIR;
        const autoApprove = msg.autoApprove || false;
        const sessionId = msg.session_id || null;

        if (!prompt) {
          ws.send(JSON.stringify({ type: 'error', event_id: eventId, message: 'Missing prompt' }));
          return;
        }

        // Reset callback result for new task
        state.resetCallbackResult();
        console.log(`[${new Date().toISOString()}] WS task received: ${eventId} (prompt: ${prompt.length} chars, session: ${sessionId})`);

        // Setup git credentials + GitHub tooling
        if (hasGitHubCredentials()) {
          try {
            const token = await generateInstallationToken();
            setupGitCredentials(token, workDir);
            setupGitHubTooling(token);
            wsSend(ws, { type: 'progress', event_id: eventId, message: 'GitHub credentials configured' });
          } catch (err) {
            wsSend(ws, { type: 'progress', event_id: eventId, message: `GitHub credentials failed: ${err.message}, continuing...` });
          }
        }

        // Setup GitLab credentials + MCP tooling
        if (hasGitLabCredentials()) {
          try {
            const glToken = readGitLabToken();
            setupGitLabCredentials(glToken, workDir);
            setupGitLabTooling(glToken);
            wsSend(ws, { type: 'progress', event_id: eventId, message: `GitLab credentials configured (${GITLAB_HOST})` });
          } catch (err) {
            wsSend(ws, { type: 'progress', event_id: eventId, message: `GitLab credentials failed: ${err.message}, continuing...` });
          }
        }

        // Login to ArgoCD/Kargo CLIs (awaited, with deduplication)
        await setupCLILogins();

        // Execute agent CLI with streaming progress (headless mode for both Gemini + Claude).
        // Both CLIs use -p (headless) + -o stream-json. Session IDs from the init event
        // enable --resume for follow-ups. No PTY needed -- env vars handle auth in headless.
        try {
          const result = await executeCLIStreaming(ws, eventId, prompt, { autoApprove, cwd: workDir, sessionId });
          wsSend(ws, {
            type: 'result',
            event_id: eventId,
            session_id: result.sessionId || null,
            status: result.status,
            output: result.output || result.stdout || '',
            source: result.source || 'stdout',
          });
        } catch (err) {
          wsSend(ws, {
            type: 'error',
            event_id: eventId,
            message: err.message,
          });
        }
        state.clearCurrentTask();

      } else if (msg.type === 'followup') {
        // Forward follow-up message to an existing session via --resume.
        // Both Gemini and Claude CLIs support --resume <session_id>.
        const sessionId = msg.session_id || '';
        const followupMsg = msg.message || '';
        const eventId = msg.event_id || 'unknown';
        console.log(`[${new Date().toISOString()}] Followup for session ${sessionId} (event: ${eventId})`);

        if (sessionId) {
          try {
            const task = state.getCurrentTask();
            const result = await executeCLIStreaming(ws, eventId, followupMsg, {
              autoApprove: true,
              cwd: task?.cwd || DEFAULT_WORK_DIR,
              sessionId: sessionId,
            });
            wsSend(ws, {
              type: 'result',
              event_id: eventId,
              session_id: result.sessionId || sessionId,
              output: result.output || result.stdout || '',
              source: result.source || 'stdout',
            });
          } catch (err) {
            wsSend(ws, { type: 'error', event_id: eventId, message: err.message });
          }
          state.clearCurrentTask();
        } else {
          wsSend(ws, { type: 'error', event_id: eventId, message: 'No session_id for followup' });
        }

      } else if (msg.type === 'cancel') {
        const task = state.getCurrentTask();
        if (task && task.child) {
          console.log(`[${new Date().toISOString()}] Cancelling task: ${task.eventId}`);
          const child = task.child;
          child.kill('SIGTERM');
          const killTimer = setTimeout(() => {
            if (!child.killed) {
              console.log(`[${new Date().toISOString()}] SIGTERM timeout -- SIGKILL for ${task?.eventId || 'unknown'}`);
              child.kill('SIGKILL');
            }
          }, 5000);
          child.on('exit', () => clearTimeout(killTimer));
          state.clearCurrentTask();
        }
      }
    });

    ws.on('close', () => {
      console.log(`[${new Date().toISOString()}] WebSocket client disconnected`);
      const task = state.getCurrentTask();
      if (task && task.child) {
        // S5 probe: log whether the disconnecting client is the task owner
        console.log(`[${new Date().toISOString()}] Killing orphaned process for ${task.eventId} (disconnect-triggered, task was active)`);
        const child = task.child;
        child.kill('SIGTERM');
        const killTimer = setTimeout(() => {
          if (!child.killed) {
            console.log(`[${new Date().toISOString()}] SIGTERM timeout -- SIGKILL`);
            child.kill('SIGKILL');
          }
        }, 5000);
        child.on('exit', () => clearTimeout(killTimer));
        state.clearCurrentTask();
      }
    });

    ws.on('error', (err) => {
      console.error(`[${new Date().toISOString()}] WebSocket error:`, err.message);
    });
  });
}

module.exports = { setupWSServer };
