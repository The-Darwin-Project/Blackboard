// gemini-sidecar/server.js
// @ai-rules:
// 1. [Pattern]: Thin entrypoint -- all logic lives in modules. This file only wires them together.
// 2. [Pattern]: Mode selection via BRAIN_WS_URL env. If set: ws-client (reverse). If not: ws-server (legacy).
// 3. [Constraint]: HTTP server always runs (K8s health probes need /health regardless of WS mode).
// 4. [Pattern]: CLI settings init runs once at module load. Periodic CLI login refresh via setInterval.
// 5. [Pattern]: Ephemeral agents fetch event document from Brain HTTP API before WS connect.

const http = require('http');
const fs = require('fs');
const WebSocket = require('ws');

const { PORT, AGENT_CLI, EVENT_ID, EPHEMERAL, BRAIN_HTTP_URL } = require('./config');
const { initializeCLISettings } = require('./cli-setup');
const { handleRequest } = require('./http-handler');
const { setupWSServer } = require('./ws-server');
const { startWSClient } = require('./ws-client');
const {
  hasGitHubCredentials, hasGitLabCredentials, setupArgoCDMCP, setupCLILogins,
  GITLAB_HOST, CLI_LOGIN_INTERVAL_MS,
} = require('./credentials');

initializeCLISettings();

async function fetchEventDocument() {
  if (!EPHEMERAL || !EVENT_ID || !BRAIN_HTTP_URL) return;
  const url = `${BRAIN_HTTP_URL}/events/${EVENT_ID}/document`;
  try {
    const res = await fetch(url);
    if (!res.ok) {
      console.log(`[${new Date().toISOString()}] Event doc fetch failed: ${res.status} from ${url}`);
      return;
    }
    const content = await res.text();
    const eventsDir = '/data/workspace/events';
    fs.mkdirSync(eventsDir, { recursive: true });
    fs.writeFileSync(`${eventsDir}/event-${EVENT_ID}.md`, content);
    console.log(`[${new Date().toISOString()}] Event doc fetched: ${content.length} chars -> ${eventsDir}/event-${EVENT_ID}.md`);
  } catch (err) {
    console.log(`[${new Date().toISOString()}] Event doc fetch error: ${err.message}`);
  }
}

const server = http.createServer(handleRequest);
const BRAIN_WS_URL = process.env.BRAIN_WS_URL || '';

(async () => {
  await fetchEventDocument();

  if (BRAIN_WS_URL) {
    startWSClient(BRAIN_WS_URL);
  } else {
    const wss = new WebSocket.Server({ server, path: '/ws' });
    setupWSServer(wss);
    console.log(`[${new Date().toISOString()}] WS server mode: listening on /ws`);
  }
})();

server.listen(PORT, '0.0.0.0', () => {
  console.log(`[${new Date().toISOString()}] Agent sidecar (${AGENT_CLI}) listening on port ${PORT}`);
  console.log(`[${new Date().toISOString()}] Endpoints: GET /health, POST /execute, POST /callback${BRAIN_WS_URL ? '' : ', WS /ws'}`);
  console.log(`[${new Date().toISOString()}] GitHub App credentials: ${hasGitHubCredentials() ? 'available' : 'NOT FOUND'}`);
  console.log(`[${new Date().toISOString()}] GitLab credentials: ${hasGitLabCredentials() ? `available (${GITLAB_HOST})` : 'NOT FOUND'}`);
  console.log(`[${new Date().toISOString()}] ArgoCD credentials: ${fs.existsSync('/secrets/argocd/auth-token') ? 'available' : 'not configured'}`);
  console.log(`[${new Date().toISOString()}] Kargo credentials: ${fs.existsSync('/secrets/kargo/auth-token') ? 'available' : 'not configured'}`);

  setupArgoCDMCP().catch((err) => {
    console.log(`[${new Date().toISOString()}] Startup ArgoCD MCP setup failed: ${err.message}`);
  });
  setupCLILogins().catch((err) => {
    console.log(`[${new Date().toISOString()}] Startup CLI login failed: ${err.message}`);
  });

  setInterval(() => {
    setupCLILogins().catch((err) => {
      console.log(`[${new Date().toISOString()}] Periodic CLI login refresh failed: ${err.message}`);
    });
  }, CLI_LOGIN_INTERVAL_MS);
});

process.on('SIGTERM', () => {
  console.log(`[${new Date().toISOString()}] Received SIGTERM, shutting down...`);
  server.close(() => process.exit(0));
});
