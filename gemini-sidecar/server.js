// gemini-sidecar/server.js
// @ai-rules:
// 1. [Pattern]: Thin entrypoint -- all logic lives in modules. This file only wires them together.
// 2. [Pattern]: Mode selection via BRAIN_WS_URL env. If set: ws-client (reverse). If not: ws-server (legacy).
// 3. [Constraint]: HTTP server always runs (K8s health probes need /health regardless of WS mode).
// 4. [Pattern]: CLI settings init runs once at module load. Periodic CLI login refresh via setInterval.
// 5. [Pattern]: Ephemeral agents fetch event document from Brain HTTP API before WS connect.
// 6. [Pattern]: Storage recycler root comes ONLY from config.resolveStorageRoot() (no inline DEFAULT_WORK_DIR fallback chain).
//    The periodic sweep starts after listen; SIGTERM stops the timer, then drains any in-flight sweep (bounded by
//    SHUTDOWN_DRAIN_MS) via stopStorageRecycler() BEFORE server.close/exit so an fs.rm is never cut off mid-directory.

const http = require('http');
const fs = require('fs');
const WebSocket = require('ws');

const { PORT, AGENT_CLI, EVENT_ID, EPHEMERAL, BRAIN_HTTP_URL, resolveStorageRoot } = require('./config');
const { initializeCLISettings } = require('./cli-setup');
const { handleRequest } = require('./http-handler');
const { setupWSServer } = require('./ws-server');
const { startWSClient } = require('./ws-client');
const { stageEventDocument } = require('./event-transport');
const { startPeriodicRecycler, stopPeriodicRecycler, stopStorageRecycler } = require('./storage-recycler');
const {
  hasGitHubCredentials, hasGitLabCredentials, hasRegistryCredentials, setupArgoCDMCP,
  setupCLILogins, setupRegistryCredentials, setupRemoteK8sMCPs, GITLAB_HOST, CLI_LOGIN_INTERVAL_MS,
  hasJenkinsCredentials, setupJenkinsMCP, hasGoogleServiceAccount, setupGoogleAuthForAgy,
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
    await stageEventDocument(EVENT_ID, content);
    console.log(`[${new Date().toISOString()}] Event doc fetched: ${content.length} chars -> staged event-${EVENT_ID}.md`);
  } catch (err) {
    console.log(`[${new Date().toISOString()}] Event doc fetch error: ${err.message}`);
  }
}

const server = http.createServer(handleRequest);
const BRAIN_WS_URL = process.env.BRAIN_WS_URL || '';
let storageRecyclerTimer = null;

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
  console.log(`[${new Date().toISOString()}] Registry credentials: ${hasRegistryCredentials() ? 'available' : 'not configured'}`);
  console.log(`[${new Date().toISOString()}] Google Service Account: ${hasGoogleServiceAccount() ? 'available' : 'not configured'}`);

  setupRegistryCredentials();
  setupRemoteK8sMCPs();
  setupGoogleAuthForAgy().catch((err) => {
    console.log(`[${new Date().toISOString()}] Startup Google agy auth setup failed: ${err.message}`);
  });

  setupArgoCDMCP(process.env.AGENT_ROLE || '').catch((err) => {
    console.log(`[${new Date().toISOString()}] Startup ArgoCD MCP setup failed: ${err.message}`);
  });

  // Local sidecars only — AGENT_ROLE is set at container level (never empty for local).
  // Ephemeral pods have AGENT_ROLE="" at boot (role arrives per-task via WS message).
  // This gate intentionally no-ops for ephemeral — ws-client.js/ws-server.js per-task gates cover them.
  // Uses .catch() pattern (not await) — server.listen callback is not async.
  const agentRole = process.env.AGENT_ROLE || '';
  if (agentRole && hasJenkinsCredentials() && ['sysadmin', 'developer'].includes(agentRole)) {
    setupJenkinsMCP().catch((err) => {
      console.log(`[${new Date().toISOString()}] Startup Jenkins MCP setup failed: ${err.message}`);
    });
  }

  setupCLILogins().catch((err) => {
    console.log(`[${new Date().toISOString()}] Startup CLI login failed: ${err.message}`);
  });

  setInterval(() => {
    setupCLILogins().catch((err) => {
      console.log(`[${new Date().toISOString()}] Periodic CLI login refresh failed: ${err.message}`);
    });
  }, CLI_LOGIN_INTERVAL_MS);

  // Storage Recycler startup sweep and periodic loop (VMER-2100)
  const workDir = resolveStorageRoot();
  storageRecyclerTimer = startPeriodicRecycler(workDir);
  console.log(`[${new Date().toISOString()}] Storage Recycler initialized for ${workDir}`);
});

// Keep well under the K8s default 30s terminationGracePeriodSeconds.
const SHUTDOWN_DRAIN_MS = 10000;

process.on('SIGTERM', async () => {
  console.log(`[${new Date().toISOString()}] Received SIGTERM, shutting down...`);
  if (storageRecyclerTimer) {
    stopPeriodicRecycler(storageRecyclerTimer);
  }
  let drainTimer;
  try {
    await Promise.race([
      stopStorageRecycler(),
      new Promise((resolve) => { drainTimer = setTimeout(resolve, SHUTDOWN_DRAIN_MS); }),
    ]);
  } catch (err) {
    console.warn(`[${new Date().toISOString()}] Storage recycler drain failed: ${err.message}`);
  } finally {
    clearTimeout(drainTimer);
  }
  server.close(() => process.exit(0));
});
