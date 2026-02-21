// gemini-sidecar/server.js
// @ai-rules:
// 1. [Pattern]: Thin entrypoint -- all logic lives in modules. This file only wires them together.
// 2. [Pattern]: Mode selection via BRAIN_WS_URL env. If set: ws-client (reverse). If not: ws-server (legacy).
// 3. [Constraint]: HTTP server always runs (K8s health probes need /health regardless of WS mode).
// 4. [Pattern]: CLI settings init runs once at module load. Periodic CLI login refresh via setInterval.

const http = require('http');
const fs = require('fs');
const WebSocket = require('ws');

const { PORT, AGENT_CLI } = require('./config');
const { initializeCLISettings } = require('./cli-setup');
const { handleRequest } = require('./http-handler');
const { setupWSServer } = require('./ws-server');
const { startWSClient } = require('./ws-client');
const {
  hasGitHubCredentials, hasGitLabCredentials, setupCLILogins,
  GITLAB_HOST, CLI_LOGIN_INTERVAL_MS,
} = require('./credentials');

// Startup: initialize CLI settings (Gemini/Claude config, trusted folders, agent rules)
initializeCLISettings();

// HTTP server (always runs -- /health, /execute, /callback)
const server = http.createServer(handleRequest);

// WS mode selection
const BRAIN_WS_URL = process.env.BRAIN_WS_URL || '';

if (BRAIN_WS_URL) {
  // Reverse mode: sidecar connects TO Brain as WS client
  startWSClient(BRAIN_WS_URL);
} else {
  // Legacy mode: Brain connects TO sidecar as WS client
  const wss = new WebSocket.Server({ server, path: '/ws' });
  setupWSServer(wss);
  console.log(`[${new Date().toISOString()}] WS server mode: listening on /ws`);
}

// Start listening
server.listen(PORT, '0.0.0.0', () => {
  console.log(`[${new Date().toISOString()}] Agent sidecar (${AGENT_CLI}) listening on port ${PORT}`);
  console.log(`[${new Date().toISOString()}] Endpoints: GET /health, POST /execute, POST /callback${BRAIN_WS_URL ? '' : ', WS /ws'}`);
  console.log(`[${new Date().toISOString()}] GitHub App credentials: ${hasGitHubCredentials() ? 'available' : 'NOT FOUND'}`);
  console.log(`[${new Date().toISOString()}] GitLab credentials: ${hasGitLabCredentials() ? `available (${GITLAB_HOST})` : 'NOT FOUND'}`);
  console.log(`[${new Date().toISOString()}] ArgoCD credentials: ${fs.existsSync('/secrets/argocd/auth-token') ? 'available' : 'not configured'}`);
  console.log(`[${new Date().toISOString()}] Kargo credentials: ${fs.existsSync('/secrets/kargo/auth-token') ? 'available' : 'not configured'}`);

  // Warm up CLI logins at startup (pod ready before first task)
  setupCLILogins().catch((err) => {
    console.log(`[${new Date().toISOString()}] Startup CLI login failed: ${err.message}`);
  });

  // Periodic CLI login refresh -- keeps ArgoCD/Kargo sessions warm during idle
  setInterval(() => {
    setupCLILogins().catch((err) => {
      console.log(`[${new Date().toISOString()}] Periodic CLI login refresh failed: ${err.message}`);
    });
  }, CLI_LOGIN_INTERVAL_MS);
});

// Graceful shutdown
process.on('SIGTERM', () => {
  console.log(`[${new Date().toISOString()}] Received SIGTERM, shutting down...`);
  server.close(() => process.exit(0));
});
