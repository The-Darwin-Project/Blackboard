// gemini-sidecar/credentials.js
// @ai-rules:
// 1. [Constraint]: Consolidates ALL authentication, credential setup, and CLI login logic.
// 2. [Pattern]: GitHub App multi-org: discoverAndGenerateTokens() discovers all installations,
//    generates per-org tokens, writes /tmp/gh-token-map.json (0o600). Fallback chain:
//    GITHUB_INSTALLATION_ID env → discovery API → file-mount → no auth.
// 3. [Pattern]: git-credential-darwin shell helper resolves per-org tokens from the map file.
//    gh-wrapper.sh does the same for `gh` CLI invocations.
// 4. [Pattern]: GitLab uses static PAT; ArgoCD session API for MCP JWT; Registry copies
//    dockerconfigjson to ~/.docker/config.json. Claude MCP -> ~/.claude.json; Gemini MCP -> ~/.gemini/settings.json.
// 5. [Gotcha]: findPrivateKeyPath/createAppJWT are internal — not exported; only public API exposed.
// 6. [Gotcha]: _lastCLILoginTime is module-scoped dedup — setupCLILogins skips ArgoCD/Kargo login if already done within 5 min.
// 7. [Gotcha]: setupArgoCDMCP sets NODE_TLS_REJECT_UNAUTHORIZED=0 globally when ARGOCD_INSECURE=true.
// 8. [Pattern]: Remote K8s clusters: setupRemoteK8sMCPs scans /secrets/remote-clusters/<name>/kubeconfig
//    and registers kubernetes-mcp-server (--read-only --toolsets core,config,tekton).
// 9. [Pattern]: Jenkins uses static user/api-token auth (GitLab PAT pattern). hasJenkinsCredentials()/
//    setupJenkinsMCP() are role-gated at the CALL SITE (server.js/ws-server.js/ws-client.js), not here --
//    the Secret is mounted for every ephemeral role, only sysadmin/developer register the MCP.
//    TLS insecure flag is scoped to mcpConfig.env only (no direct HTTPS fetch() from this sidecar to Jenkins).

const fs = require('fs');
const { spawn, execSync, execFileSync } = require('child_process');
const jwt = require('jsonwebtoken');
const { resolveCommand, writeClaudeMcpServer } = require('./cli-setup');

// --- GitHub App ---
const SECRETS_PATH = '/secrets/github';
const APP_ID_PATH = `${SECRETS_PATH}/app-id`;
const INSTALL_ID_PATH = `${SECRETS_PATH}/installation-id`;
const PRIVATE_KEY_PATTERN = /\.pem$/;

// --- GitLab ---
const GITLAB_SECRETS_PATH = '/secrets/gitlab';
const GITLAB_TOKEN_PATH = process.env.GITLAB_TOKEN_PATH || `${GITLAB_SECRETS_PATH}/token`;
const GITLAB_HOST = process.env.GITLAB_HOST || '';

// --- Container Registry ---
const REGISTRY_CONFIG_PATH = '/secrets/registry/.dockerconfigjson';
const DOCKER_DIR = `${process.env.HOME}/.docker`;
const DOCKER_CONFIG_PATH = `${DOCKER_DIR}/config.json`;

// --- CLI Logins ---
let _lastCLILoginTime = 0;
const CLI_LOGIN_INTERVAL_MS = 5 * 60 * 1000; // 5 min -- ArgoCD sessions can expire early

/**
 * Find the private key file in the secrets directory
 */
function findPrivateKeyPath() {
  if (!fs.existsSync(SECRETS_PATH)) {
    return null;
  }
  const files = fs.readdirSync(SECRETS_PATH);
  const pemFile = files.find(f => PRIVATE_KEY_PATTERN.test(f));
  return pemFile ? `${SECRETS_PATH}/${pemFile}` : null;
}

/**
 * Check if GitHub App credentials are available
 */
function hasGitHubCredentials() {
  return fs.existsSync(APP_ID_PATH) && findPrivateKeyPath() !== null;
}

/**
 * Create a short-lived App JWT for GitHub API authentication.
 * Reusable helper — both single-install and multi-org paths need this.
 * @returns {{jwtToken: string, appId: string}}
 */
function createAppJWT() {
  const privateKeyPath = findPrivateKeyPath();
  if (!privateKeyPath) {
    throw new Error('GitHub App private key not found in /secrets/github/');
  }
  const appId = fs.readFileSync(APP_ID_PATH, 'utf8').trim();
  const privateKey = fs.readFileSync(privateKeyPath, 'utf8');
  const now = Math.floor(Date.now() / 1000);
  const payload = { iat: now - 60, exp: now + 540, iss: appId };
  const jwtToken = jwt.sign(payload, privateKey, { algorithm: 'RS256' });
  return { jwtToken, appId };
}

/**
 * Generate GitHub App installation token (single installation — legacy path).
 * Mirrors logic from BlackBoard/src/utils/github_app.py
 * @returns {Promise<string>} Installation access token (valid 1 hour)
 */
async function generateInstallationToken() {
  const { jwtToken, appId } = createAppJWT();
  const installId = (process.env.GITHUB_INSTALLATION_ID || fs.readFileSync(INSTALL_ID_PATH, 'utf8')).trim();

  console.log(`[${new Date().toISOString()}] Generating GitHub App token (app=${appId}, install=${installId})`);

  const url = `https://api.github.com/app/installations/${installId}/access_tokens`;
  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Accept': 'application/vnd.github+json',
      'Authorization': `Bearer ${jwtToken}`,
      'X-GitHub-Api-Version': '2022-11-28',
    },
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`GitHub token request failed: ${response.status} - ${error}`);
  }

  const data = await response.json();
  console.log(`[${new Date().toISOString()}] Got GitHub installation token (expires: ${data.expires_at})`);
  return data.token;
}

// --- Multi-Org GitHub Auth ---
const TOKEN_MAP_PATH = '/tmp/gh-token-map.json';

/**
 * Discover all installations for this GitHub App.
 * @returns {Promise<Array<{id: number, account: {login: string}}>>}
 */
async function discoverInstallations() {
  const { jwtToken, appId } = createAppJWT();
  console.log(`[${new Date().toISOString()}] Discovering GitHub App installations (app=${appId})`);

  const response = await fetch('https://api.github.com/app/installations', {
    headers: {
      'Accept': 'application/vnd.github+json',
      'Authorization': `Bearer ${jwtToken}`,
      'X-GitHub-Api-Version': '2022-11-28',
    },
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`GitHub installations discovery failed: ${response.status} - ${error}`);
  }

  const installations = await response.json();
  console.log(`[${new Date().toISOString()}] Discovered ${installations.length} installation(s): ${installations.map(i => i.account?.login || i.id).join(', ')}`);
  return installations;
}

/**
 * Generate access tokens for each installation. Accumulates partial successes.
 * @param {Array<{id: number, account: {login: string}}>} installations
 * @returns {Promise<Object<string, {token: string, installation_id: string, expires_at: string}>>}
 */
async function generateAllTokens(installations) {
  const { jwtToken } = createAppJWT();
  const tokenMap = {};

  for (const inst of installations) {
    const org = (inst.account?.login || '').toLowerCase();
    if (!org) continue;

    try {
      const url = `https://api.github.com/app/installations/${inst.id}/access_tokens`;
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Accept': 'application/vnd.github+json',
          'Authorization': `Bearer ${jwtToken}`,
          'X-GitHub-Api-Version': '2022-11-28',
        },
      });

      if (!response.ok) {
        const error = await response.text();
        console.warn(`[${new Date().toISOString()}] Token generation failed for ${org} (install=${inst.id}): ${response.status} - ${error}`);
        continue;
      }

      const data = await response.json();
      tokenMap[org] = {
        token: data.token,
        installation_id: String(inst.id),
        expires_at: data.expires_at,
      };
      console.log(`[${new Date().toISOString()}] Got token for ${org} (install=${inst.id}, expires: ${data.expires_at})`);
    } catch (err) {
      console.warn(`[${new Date().toISOString()}] Token generation error for ${org}: ${err.message}`);
    }
  }

  return tokenMap;
}

// Dedup lock: prevents concurrent discovery from 3 call sites (http-handler, ws-server, ws-client)
let _discoveryInFlight = null;

/**
 * Full multi-org discovery and token generation with fallback chain:
 * 1. GITHUB_INSTALLATION_ID env → single-token legacy path
 * 2. Discovery API → multi-org tokens (scoped by GITHUB_ALLOWED_ORGS if set)
 * 3. File-mount (INSTALL_ID_PATH) → single-token legacy path
 * 4. No auth (returns empty map, cleans stale map file)
 *
 * Always cleans pre-existing token map at entry to prevent stale inheritance.
 * Dedup: concurrent callers share a single in-flight discovery (no race on file).
 *
 * @returns {Promise<Object<string, {token: string, installation_id: string, expires_at: string}>>}
 */
async function discoverAndGenerateTokens() {
  if (_discoveryInFlight) return _discoveryInFlight;
  _discoveryInFlight = _discoverAndGenerateTokensInner();
  try { return await _discoveryInFlight; }
  finally { _discoveryInFlight = null; }
}

async function _discoverAndGenerateTokensInner() {
  // Clean stale map from prior sessions before any fallback path runs.
  // Prevents HIGH-1: a no-auth task inheriting tokens from a previous session.
  try { fs.unlinkSync(TOKEN_MAP_PATH); } catch { /* not present — expected on first run */ }

  // Parse allowed-org scoping (empty = all orgs, backward compat)
  const allowedOrgs = (process.env.GITHUB_ALLOWED_ORGS || '')
    .split(',').map(o => o.toLowerCase().trim()).filter(Boolean);

  // Fallback 1: explicit single-installation env var → old behavior
  if (process.env.GITHUB_INSTALLATION_ID) {
    console.log(`[${new Date().toISOString()}] GITHUB_INSTALLATION_ID set — using single-install path`);
    const token = await generateInstallationToken();
    const installId = process.env.GITHUB_INSTALLATION_ID.trim();
    const map = { _default: { token, installation_id: installId, expires_at: '' } };
    fs.writeFileSync(TOKEN_MAP_PATH, JSON.stringify(map, null, 2), { mode: 0o600 });
    return map;
  }

  // Fallback 2: discovery API
  try {
    const installations = await discoverInstallations();
    if (installations.length > 0) {
      const fullTokenMap = await generateAllTokens(installations);
      if (Object.keys(fullTokenMap).length > 0) {
        // Scope token map to allowed orgs if configured (fixes CRITICAL cross-org confused-deputy)
        if (allowedOrgs.length > 0) {
          const scopedMap = {};
          for (const [org, entry] of Object.entries(fullTokenMap)) {
            if (allowedOrgs.includes(org)) {
              scopedMap[org] = entry;
            }
          }
          if (Object.keys(scopedMap).length === 0) {
            console.warn(`[${new Date().toISOString()}] No tokens match GITHUB_ALLOWED_ORGS=[${allowedOrgs.join(',')}]`);
          } else {
            fs.writeFileSync(TOKEN_MAP_PATH, JSON.stringify(scopedMap, null, 2), { mode: 0o600 });
            console.log(`[${new Date().toISOString()}] Token map scoped to ${Object.keys(scopedMap).length}/${Object.keys(fullTokenMap).length} orgs`);
          }
          return scopedMap;
        }
        // No org scoping — write full map to disk (single write-site, post-scoping)
        fs.writeFileSync(TOKEN_MAP_PATH, JSON.stringify(fullTokenMap, null, 2), { mode: 0o600 });
        console.log(`[${new Date().toISOString()}] Token map written (${Object.keys(fullTokenMap).length} orgs, unscoped) -> ${TOKEN_MAP_PATH}`);
        return fullTokenMap;
      }
    }
  } catch (err) {
    console.warn(`[${new Date().toISOString()}] Installation discovery failed: ${err.message}`);
  }

  // Fallback 3: file-mounted installation-id (backward compat)
  if (fs.existsSync(INSTALL_ID_PATH)) {
    console.log(`[${new Date().toISOString()}] Falling back to file-mounted installation-id`);
    try {
      const token = await generateInstallationToken();
      const installId = fs.readFileSync(INSTALL_ID_PATH, 'utf8').trim();
      const map = { _default: { token, installation_id: installId, expires_at: '' } };
      fs.writeFileSync(TOKEN_MAP_PATH, JSON.stringify(map, null, 2), { mode: 0o600 });
      return map;
    } catch (err) {
      console.warn(`[${new Date().toISOString()}] File-mount token generation failed: ${err.message}`);
    }
  }

  // Fallback 4: no auth — stale map already cleaned at function entry
  console.log(`[${new Date().toISOString()}] No GitHub installation tokens available`);
  return {};
}

/**
 * Configure git credentials for GitHub operations (multi-org aware).
 * Uses git-credential-darwin helper for per-org token resolution.
 * @param {Object} tokenMap - Multi-org token map from discoverAndGenerateTokens()
 * @param {string} workDir - Working directory for git operations
 */
function setupGitCredentials(tokenMap, workDir) {
  console.log(`[${new Date().toISOString()}] Configuring git credentials (multi-org)`);

  try {
    if (!fs.existsSync(workDir)) {
      fs.mkdirSync(workDir, { recursive: true });
    }

    // Core git identity
    execSync(`git config --global user.name "${process.env.GIT_USER_NAME || 'Darwin Agent'}"`, { encoding: 'utf8' });
    execSync(`git config --global user.email "${process.env.GIT_USER_EMAIL || 'darwin-agent@darwin-project.io'}"`, { encoding: 'utf8' });

    // Safe directories
    execSync(`git config --global --add safe.directory ${workDir}`, { encoding: 'utf8' });
    execSync(`git config --global --add safe.directory '*'`, { encoding: 'utf8' });

    // Enable per-path credential matching
    execSync('git config --global credential.https://github.com.useHttpPath true', { encoding: 'utf8' });

    // Clean stale per-org credential helpers from prior runs
    try {
      const existing = execSync('git config --global --get-regexp "^credential\\.https://github\\.com/.+\\.helper$"', { encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe'] });
      for (const line of existing.trim().split('\n')) {
        if (!line) continue;
        const key = line.split(/\s+/)[0];
        try { execSync(`git config --global --unset "${key}"`, { encoding: 'utf8', stdio: 'pipe' }); } catch { /* already gone */ }
      }
    } catch { /* no existing entries -- expected on first run */ }

    // Remove legacy flat credential helper (old single-token path)
    try { execSync('git config --global --unset credential.https://github.com.helper', { encoding: 'utf8', stdio: 'pipe' }); } catch { /* not set */ }

    // Register a single host-level credential helper. git-credential-darwin
    // already lowercases the org from the credential path itself, so a
    // per-org registration here is redundant and breaks for mixed-case org
    // names since git's credential URL matching is case-sensitive.
    if (Object.keys(tokenMap).length > 0) {
      execSync('git config --global credential.https://github.com.helper "!/app/git-credential-darwin"', { encoding: 'utf8' });
      console.log(`[${new Date().toISOString()}] Host-level credential helper registered (github.com)`);
    }

    console.log(`[${new Date().toISOString()}] Git credentials configured`);
  } catch (err) {
    console.error(`[${new Date().toISOString()}] Git config error:`, err.message);
    throw new Error(`Failed to configure git: ${err.message}`);
  }
}

/**
 * Configure GitHub MCP server + gh CLI auth with multi-org token map.
 * Selects primary token: GITHUB_TARGET_ORG → GITHUB_INSTALLATION_ID → _default → first available.
 * Both Gemini CLI and Claude Code use the MCP server for structured GitHub interaction.
 * The gh CLI uses GH_TOKEN env var; per-repo switching handled by gh-wrapper.sh.
 *
 * @param {Object} tokenMap - Multi-org token map from discoverAndGenerateTokens()
 */
function setupGitHubTooling(tokenMap) {
  let token = '';

  // Priority 1: task's target org (fixes HIGH-2 — org-agnostic primary token)
  const targetOrg = (process.env.GITHUB_TARGET_ORG || '').toLowerCase().trim();
  if (targetOrg && tokenMap[targetOrg]) {
    token = tokenMap[targetOrg].token;
    console.log(`[${new Date().toISOString()}] Primary token selected for target org: ${targetOrg}`);
  }

  // Priority 2: explicit GITHUB_INSTALLATION_ID (existing behavior, unchanged)
  if (!token) {
    const explicitId = (process.env.GITHUB_INSTALLATION_ID || '').trim();
    if (explicitId) {
      const entry = Object.values(tokenMap).find(e => e.installation_id === explicitId);
      if (entry) token = entry.token;
    }
  }

  // Priority 3: _default key (single-install backward compat)
  if (!token && tokenMap._default) {
    token = tokenMap._default.token;
  }

  // Priority 4: first available (last resort — preserves existing fallback)
  if (!token) {
    const entries = Object.values(tokenMap).filter(e => e.token);
    if (entries.length > 0) token = entries[0].token;
  }

  if (!token) {
    console.warn(`[${new Date().toISOString()}] No GitHub token available for MCP/gh CLI`);
    return;
  }

  // 1. Set GH_TOKEN for gh CLI (persists in process env for child processes)
  process.env.GH_TOKEN = token;

  // 2. Configure GitHub MCP server for both CLIs
  // Hoisted above try blocks: resolveCommand never throws (catches internally, falls back to relative name)
  const ghMcpBin = resolveCommand('github-mcp-server');
  const geminiSettingsDir = `${process.env.HOME}/.gemini`;
  const geminiSettingsPath = `${geminiSettingsDir}/settings.json`;
  try {
    fs.mkdirSync(geminiSettingsDir, { recursive: true });
    // Read existing settings (may have other config)
    let settings = {};
    if (fs.existsSync(geminiSettingsPath)) {
      try { settings = JSON.parse(fs.readFileSync(geminiSettingsPath, 'utf8')); } catch { /* fresh start */ }
    }
    // Add/update GitHub MCP server config (stdio transport -- CLI spawns server as child)
    settings.mcpServers = settings.mcpServers || {};
    settings.mcpServers.GitHub = {
      command: ghMcpBin,
      args: ['stdio'],
      env: { GITHUB_PERSONAL_ACCESS_TOKEN: token },
    };
    fs.writeFileSync(geminiSettingsPath, JSON.stringify(settings, null, 2));
    console.log(`[${new Date().toISOString()}] GitHub MCP configured for Gemini CLI`);
  } catch (err) {
    console.error(`[${new Date().toISOString()}] GitHub MCP config (Gemini) failed: ${err.message}`);
  }

  // 3. Configure GitHub MCP server for Claude Code (writes to ~/.claude.json)
  try {
    writeClaudeMcpServer('GitHub', {
      command: ghMcpBin, args: ['stdio'],
      env: { GITHUB_PERSONAL_ACCESS_TOKEN: token },
    });
    console.log(`[${new Date().toISOString()}] GitHub MCP configured for Claude Code`);
  } catch (err) {
    console.error(`[${new Date().toISOString()}] GitHub MCP config (Claude) failed: ${err.message}`);
  }

  console.log(`[${new Date().toISOString()}] gh CLI + GitHub MCP server ready`);
}

/**
 * Check if GitLab token credentials are available
 */
function hasGitLabCredentials() {
  return fs.existsSync(GITLAB_TOKEN_PATH) && !!GITLAB_HOST;
}

/**
 * Read GitLab token from mounted secret.
 * Unlike GitHub App (JWT exchange), GitLab uses a static PAT.
 * @returns {string} GitLab access token
 */
function readGitLabToken() {
  if (!fs.existsSync(GITLAB_TOKEN_PATH)) {
    throw new Error(`GitLab token not found at ${GITLAB_TOKEN_PATH}`);
  }
  return fs.readFileSync(GITLAB_TOKEN_PATH, 'utf8').trim();
}

/**
 * Configure git credentials for GitLab operations.
 * Appends GitLab credentials alongside existing GitHub credentials.
 * @param {string} token - GitLab access token (PAT)
 * @param {string} workDir - Working directory for git operations
 */
function setupGitLabCredentials(token, workDir) {
  console.log(`[${new Date().toISOString()}] Configuring GitLab git credentials (${GITLAB_HOST})`);
  try {
    // Ensure work directory exists
    if (!fs.existsSync(workDir)) {
      fs.mkdirSync(workDir, { recursive: true });
    }
    // Store credentials using host-specific helper (coexists with GitHub credentials)
    const credFile = `/tmp/git-creds-gitlab-${Date.now()}`;
    fs.writeFileSync(credFile, `https://darwin-agent:${token}@${GITLAB_HOST}\n`, { mode: 0o600 });
    execFileSync('git', ['config', '--global', `credential.https://${GITLAB_HOST}.helper`, `store --file=${credFile}`], { encoding: 'utf8' });
    execFileSync('git', ['config', '--global', `http.https://${GITLAB_HOST}.sslVerify`, 'false'], { encoding: 'utf8' });
    console.log(`[${new Date().toISOString()}] GitLab git credentials configured for ${GITLAB_HOST} (SSL verify disabled)`);
  } catch (err) {
    console.error(`[${new Date().toISOString()}] GitLab git config error:`, err.message);
    throw new Error(`Failed to configure GitLab git: ${err.message}`);
  }
}

/**
 * Configure GitLab MCP server + glab CLI auth with a token.
 * Both Gemini CLI and Claude Code use the MCP server for structured GitLab interaction.
 * The glab CLI uses GITLAB_TOKEN env var for direct commands.
 *
 * @param {string} token - GitLab access token (PAT)
 */
function setupGitLabTooling(token) {
  // 1. Set GITLAB_TOKEN for glab CLI (persists in process env for child processes)
  process.env.GITLAB_TOKEN = token;
  process.env.GITLAB_HOST = GITLAB_HOST;

  // Check if glab CLI exists (provides MCP server via `glab mcp serve`)
  let hasGlab = false;
  try { execFileSync('which', ['glab'], { stdio: 'ignore' }); hasGlab = true; } catch { /* not installed */ }

  if (!hasGlab) {
    console.log(`[${new Date().toISOString()}] glab not installed, skipping GitLab MCP config`);
    return;
  }

  // Configure glab to skip TLS verification for internal GitLab (self-signed certs).
  // Host-scoped: only affects this host, not gitlab.com or other instances.
  try {
    execFileSync('glab', ['config', 'set', 'skip_tls_verify', 'true', '--host', GITLAB_HOST], { encoding: 'utf8' });
    console.log(`[${new Date().toISOString()}] glab TLS verify disabled for ${GITLAB_HOST}`);
  } catch (err) {
    console.error(`[${new Date().toISOString()}] glab config set failed: ${err.message}`);
  }

  // MCP config for both CLIs: use `glab mcp serve` (replaces deprecated @modelcontextprotocol/server-gitlab)
  const mcpConfig = {
    command: resolveCommand('glab'),
    args: ['mcp', 'serve'],
    env: {
      GITLAB_TOKEN: token,
      GITLAB_HOST: GITLAB_HOST,
    },
  };

  // 2. Configure GitLab MCP for Gemini CLI
  const geminiSettingsDir = `${process.env.HOME}/.gemini`;
  const geminiSettingsPath = `${geminiSettingsDir}/settings.json`;
  try {
    fs.mkdirSync(geminiSettingsDir, { recursive: true });
    let settings = {};
    if (fs.existsSync(geminiSettingsPath)) {
      try { settings = JSON.parse(fs.readFileSync(geminiSettingsPath, 'utf8')); } catch { /* fresh start */ }
    }
    settings.mcpServers = settings.mcpServers || {};
    settings.mcpServers.GitLab = mcpConfig;
    fs.writeFileSync(geminiSettingsPath, JSON.stringify(settings, null, 2));
    console.log(`[${new Date().toISOString()}] GitLab MCP configured for Gemini CLI (glab mcp serve)`);
  } catch (err) {
    console.error(`[${new Date().toISOString()}] GitLab MCP config (Gemini) failed: ${err.message}`);
  }

  // 3. Configure GitLab MCP for Claude Code (writes to ~/.claude.json)
  try {
    writeClaudeMcpServer('GitLab', mcpConfig);
    console.log(`[${new Date().toISOString()}] GitLab MCP configured for Claude Code (glab mcp serve)`);
  } catch (err) {
    console.error(`[${new Date().toISOString()}] GitLab MCP config (Claude) failed: ${err.message}`);
  }

  console.log(`[${new Date().toISOString()}] glab CLI + GitLab MCP ready (${GITLAB_HOST})`);
}

/**
 * Configure ArgoCD MCP server for Gemini CLI and Claude Code.
 * Exchanges the existing ArgoCD password for a session JWT via the ArgoCD API,
 * then registers argocd-mcp as an MCP server in both CLI settings.
 * Architect gets read-only access; all other roles get full access.
 * Falls back silently to argocd CLI if session API is unreachable.
 */
async function setupArgoCDMCP() {
  const server = process.env.ARGOCD_SERVER;
  if (!server) return;

  const authTokenPath = '/secrets/argocd/auth-token';
  if (!fs.existsSync(authTokenPath)) return;
  const password = fs.readFileSync(authTokenPath, 'utf8').trim();
  if (!password) return;

  const insecure = process.env.ARGOCD_INSECURE === 'true';
  const baseUrl = `https://${server}`;
  const username = process.env.ARGOCD_USERNAME || 'admin';

  let sessionJwt;
  try {
    if (insecure) process.env.NODE_TLS_REJECT_UNAUTHORIZED = '0';
    const response = await fetch(`${baseUrl}/api/v1/session`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    if (!response.ok) throw new Error(`ArgoCD session API returned ${response.status}`);
    const data = await response.json();
    sessionJwt = data.token;
    if (!sessionJwt) throw new Error('ArgoCD session API returned no token');
  } catch (err) {
    console.log(`[${new Date().toISOString()}] ArgoCD MCP: session API failed (${err.message}), agents use argocd CLI fallback`);
    return;
  }

  const role = process.env.AGENT_ROLE || '';
  const readOnly = (role === 'architect');

  const mcpConfig = {
    command: resolveCommand('argocd-mcp'),
    args: ['stdio'],
    env: {
      ARGOCD_BASE_URL: baseUrl,
      ARGOCD_API_TOKEN: sessionJwt,
      ...(readOnly ? { MCP_READ_ONLY: 'true' } : {}),
      ...(insecure ? { NODE_TLS_REJECT_UNAUTHORIZED: '0' } : {}),
    },
  };

  const geminiSettingsPath = `${process.env.HOME}/.gemini/settings.json`;
  try {
    fs.mkdirSync(`${process.env.HOME}/.gemini`, { recursive: true });
    let settings = {};
    if (fs.existsSync(geminiSettingsPath)) {
      try { settings = JSON.parse(fs.readFileSync(geminiSettingsPath, 'utf8')); } catch { /* fresh */ }
    }
    settings.mcpServers = settings.mcpServers || {};
    settings.mcpServers.ArgoCD = mcpConfig;
    fs.writeFileSync(geminiSettingsPath, JSON.stringify(settings, null, 2));
    console.log(`[${new Date().toISOString()}] ArgoCD MCP configured for Gemini CLI${readOnly ? ' (read-only)' : ''}`);
  } catch (err) {
    console.error(`[${new Date().toISOString()}] ArgoCD MCP config (Gemini) failed: ${err.message}`);
  }

  // Configure ArgoCD MCP for Claude Code (writes to ~/.claude.json)
  try {
    writeClaudeMcpServer('ArgoCD', mcpConfig);
    console.log(`[${new Date().toISOString()}] ArgoCD MCP configured for Claude Code${readOnly ? ' (read-only)' : ''}`);
  } catch (err) {
    console.error(`[${new Date().toISOString()}] ArgoCD MCP config (Claude) failed: ${err.message}`);
  }
}

/**
 * Login to ArgoCD/Kargo CLIs (awaitable, with deduplication).
 * Returns a Promise that resolves when both logins complete (or timeout after 10s).
 * Skips login if already logged in within the last 30 minutes.
 */
async function setupCLILogins() {
  const now = Date.now();
  if (now - _lastCLILoginTime < CLI_LOGIN_INTERVAL_MS) {
    return; // Already logged in recently
  }

  const promises = [];

  // ArgoCD login
  const argoServer = process.env.ARGOCD_SERVER;
  const argoSecretPath = '/secrets/argocd/auth-token';
  if (argoServer && fs.existsSync(argoSecretPath)) {
    const password = fs.readFileSync(argoSecretPath, 'utf8').trim();
    const insecure = process.env.ARGOCD_INSECURE === 'true' ? '--insecure' : '';
    promises.push(new Promise((resolve) => {
      const child = spawn('argocd', ['login', argoServer, '--username', 'admin', '--password', password, insecure, '--grpc-web'].filter(Boolean),
        { stdio: 'pipe', timeout: 10000 });
      child.on('close', (code) => {
        if (code === 0) console.log(`[${new Date().toISOString()}] ArgoCD login successful (${argoServer})`);
        else console.log(`[${new Date().toISOString()}] ArgoCD login failed (exit ${code}), agents use kubectl/oc fallback`);
        resolve();
      });
      child.on('error', (err) => {
        console.log(`[${new Date().toISOString()}] ArgoCD login error: ${err.message}`);
        resolve();
      });
    }));
  }

  // Kargo login
  const kargoServer = process.env.KARGO_SERVER;
  const kargoSecretPath = '/secrets/kargo/auth-token';
  if (kargoServer && fs.existsSync(kargoSecretPath)) {
    const password = fs.readFileSync(kargoSecretPath, 'utf8').trim();
    const insecure = process.env.KARGO_INSECURE === 'true' ? '--insecure-skip-tls-verify' : '';
    promises.push(new Promise((resolve) => {
      const child = spawn('kargo', ['login', `https://${kargoServer}`, '--admin', '--password', password, insecure].filter(Boolean),
        { stdio: 'pipe', timeout: 10000 });
      child.on('close', (code) => {
        if (code === 0) console.log(`[${new Date().toISOString()}] Kargo login successful (${kargoServer})`);
        else console.log(`[${new Date().toISOString()}] Kargo login failed (exit ${code}), agents use kubectl/oc fallback`);
        resolve();
      });
      child.on('error', (err) => {
        console.log(`[${new Date().toISOString()}] Kargo login error: ${err.message}`);
        resolve();
      });
    }));
  }

  if (promises.length > 0) {
    await Promise.all(promises);
    _lastCLILoginTime = Date.now();
  }
}

// --- Remote K8s Clusters ---
const REMOTE_CLUSTERS_PATH = '/secrets/remote-clusters';

/**
 * Scan mounted remote cluster kubeconfigs and register a kubernetes-mcp-server
 * instance for each one. Each cluster appears as K8s_<name> in the CLI's MCP
 * tool list. All instances run in --read-only --toolsets core,config,tekton mode.
 */
function setupRemoteK8sMCPs() {
  if (!fs.existsSync(REMOTE_CLUSTERS_PATH)) return;

  let clusterDirs;
  try { clusterDirs = fs.readdirSync(REMOTE_CLUSTERS_PATH, { withFileTypes: true }); }
  catch { return; }

  const mcpBin = resolveCommand('kubernetes-mcp-server');
  const geminiSettingsPath = `${process.env.HOME}/.gemini/settings.json`;

  for (const entry of clusterDirs) {
    if (!entry.isDirectory()) continue;
    const name = entry.name;
    const kubeconfigPath = `${REMOTE_CLUSTERS_PATH}/${name}/kubeconfig`;
    if (!fs.existsSync(kubeconfigPath)) continue;

    const mcpName = `K8s_${name}`;
    const mcpConfig = {
      command: mcpBin,
      args: ['--kubeconfig', kubeconfigPath, '--read-only', '--toolsets', 'core,config,tekton'],
    };

    try {
      fs.mkdirSync(`${process.env.HOME}/.gemini`, { recursive: true });
      let settings = {};
      if (fs.existsSync(geminiSettingsPath)) {
        try { settings = JSON.parse(fs.readFileSync(geminiSettingsPath, 'utf8')); } catch { }
      }
      settings.mcpServers = settings.mcpServers || {};
      settings.mcpServers[mcpName] = mcpConfig;
      fs.writeFileSync(geminiSettingsPath, JSON.stringify(settings, null, 2));
    } catch (err) {
      console.error(`[${new Date().toISOString()}] ${mcpName} MCP config (Gemini) failed: ${err.message}`);
    }

    try {
      writeClaudeMcpServer(mcpName, mcpConfig);
    } catch (err) {
      console.error(`[${new Date().toISOString()}] ${mcpName} MCP config (Claude) failed: ${err.message}`);
    }

    const metaPath = `/config/remote-clusters/${name}.json`;
    let meta = {};
    try { meta = JSON.parse(fs.readFileSync(metaPath, 'utf8')); } catch { }

    console.log(`[${new Date().toISOString()}] ${mcpName} MCP configured (read-only, kubeconfig=${kubeconfigPath}, namespaces=${(meta.namespaces || []).length})`);

    if (meta.kubearchiveUrl) {
      let token = '';
      try {
        token = execFileSync('kubectl', [
          '--kubeconfig', kubeconfigPath,
          'config', 'view', '--raw', '--minify',
          '-o', 'jsonpath={.users[0].user.token}'
        ], { encoding: 'utf8', timeout: 5000 }).trim();
      } catch (err) {
        console.warn(`[${new Date().toISOString()}] KubeArchive token extraction failed for ${name}: ${err.message}`);
      }
      if (!token) {
        console.warn(`[${new Date().toISOString()}] KubeArchive skipped for ${name}: no static token in kubeconfig (exec-auth or empty)`);
      }

      if (token) {
        const kaMcpName = `KubeArchive_${name}`;
        const kaMcpConfig = {
          command: resolveCommand('node'),
          args: ['/app/kubearchive-mcp.js'],
          env: { KUBEARCHIVE_URL: meta.kubearchiveUrl, KUBEARCHIVE_TOKEN: token },
        };

        try {
          let kaSettings = {};
          if (fs.existsSync(geminiSettingsPath)) {
            try { kaSettings = JSON.parse(fs.readFileSync(geminiSettingsPath, 'utf8')); } catch { }
          }
          kaSettings.mcpServers = kaSettings.mcpServers || {};
          kaSettings.mcpServers[kaMcpName] = kaMcpConfig;
          fs.writeFileSync(geminiSettingsPath, JSON.stringify(kaSettings, null, 2));
        } catch (err) {
          console.error(`[${new Date().toISOString()}] ${kaMcpName} MCP config (Gemini) failed: ${err.message}`);
        }

        try {
          writeClaudeMcpServer(kaMcpName, kaMcpConfig);
        } catch (err) {
          console.error(`[${new Date().toISOString()}] ${kaMcpName} MCP config (Claude) failed: ${err.message}`);
        }

        console.log(`[${new Date().toISOString()}] ${kaMcpName} MCP configured (${meta.kubearchiveUrl})`);
      }
    }
  }
}

/**
 * Read cluster metadata from ConfigMap mount. Returns array of
 * { name, displayName, namespacePattern, namespaces } objects.
 */
function getRemoteClustersMeta() {
  const metaDir = '/config/remote-clusters';
  if (!fs.existsSync(metaDir)) return [];
  const result = [];
  try {
    for (const f of fs.readdirSync(metaDir)) {
      if (!f.endsWith('.json')) continue;
      try { result.push(JSON.parse(fs.readFileSync(`${metaDir}/${f}`, 'utf8'))); } catch { }
    }
  } catch { }
  return result;
}

/**
 * Check if container registry credentials are mounted.
 */
function hasRegistryCredentials() {
  return fs.existsSync(REGISTRY_CONFIG_PATH);
}

/**
 * Copy mounted dockerconfigjson to $HOME/.docker/config.json so skopeo,
 * podman, and crane can authenticate to private registries at task time.
 */
function setupRegistryCredentials() {
  if (!fs.existsSync(REGISTRY_CONFIG_PATH)) return;
  try {
    fs.mkdirSync(DOCKER_DIR, { recursive: true });
    fs.copyFileSync(REGISTRY_CONFIG_PATH, DOCKER_CONFIG_PATH);
    fs.chmodSync(DOCKER_CONFIG_PATH, 0o600);
    console.log(`[${new Date().toISOString()}] Registry credentials configured (${DOCKER_CONFIG_PATH})`);
  } catch (err) {
    console.error(`[${new Date().toISOString()}] Registry credentials setup failed: ${err.message}`);
  }
}

// --- Jenkins ---
const JENKINS_SECRETS_PATH = '/secrets/jenkins';
const JENKINS_USERNAME_PATH = `${JENKINS_SECRETS_PATH}/username`;
const JENKINS_API_TOKEN_PATH = `${JENKINS_SECRETS_PATH}/api-token`;

/**
 * Check if Jenkins credentials are mounted. The Secret is mounted for every
 * ephemeral role (shared TriggerTemplate), but only SysAdmin/Developer call
 * setupJenkinsMCP() -- see the per-file role gate at each call site.
 */
function hasJenkinsCredentials() {
  return fs.existsSync(JENKINS_USERNAME_PATH) && fs.existsSync(JENKINS_API_TOKEN_PATH) && !!process.env.JENKINS_URL;
}

/**
 * Configure the Jenkins MCP server (@kud/mcp-jenkins) for Gemini CLI and Claude Code.
 * Static user/API-token auth, same shape as GitLab's PAT (no session exchange).
 * MCP_JENKINS_ALLOW_TOOLS restricts the exposed tool surface to retrigger +
 * read-only status tools -- it scopes which TOOLS are exposed, not which JOBS
 * a retrigger can target; job-level scoping is enforced by agent rules (prose).
 */
async function setupJenkinsMCP() {
  if (!hasJenkinsCredentials()) return;

  let username, apiToken;
  try {
    username = fs.readFileSync(JENKINS_USERNAME_PATH, 'utf8').trim();
    apiToken = fs.readFileSync(JENKINS_API_TOKEN_PATH, 'utf8').trim();
  } catch (err) {
    console.error(`[${new Date().toISOString()}] Jenkins credential read failed: ${err.message}`);
    return;
  }
  // Strict equality: the string "false" is truthy in JS, so a naive
  // `if (process.env.JENKINS_INSECURE_TLS)` would treat "false" as enabled.
  const insecureTls = process.env.JENKINS_INSECURE_TLS === 'true';

  const mcpConfig = {
    command: resolveCommand('mcp-jenkins'),
    args: [],
    env: {
      MCP_JENKINS_URL: process.env.JENKINS_URL,
      MCP_JENKINS_USER: username,
      MCP_JENKINS_API_TOKEN: apiToken,
      MCP_JENKINS_ALLOW_TOOLS: 'jenkins_trigger_build,jenkins_get_build_status,jenkins_get_recent_builds',
    },
  };

  if (insecureTls) {
    // Scoped to the MCP child process env only, not global process.env --
    // unlike ArgoCD, this sidecar makes no direct HTTPS fetch() of its own to
    // Jenkins, so there is nothing else that needs the global override.
    mcpConfig.env.NODE_TLS_REJECT_UNAUTHORIZED = '0';
  }

  const geminiSettingsDir = `${process.env.HOME}/.gemini`;
  const geminiSettingsPath = `${geminiSettingsDir}/settings.json`;
  try {
    fs.mkdirSync(geminiSettingsDir, { recursive: true });
    let settings = {};
    if (fs.existsSync(geminiSettingsPath)) {
      try { settings = JSON.parse(fs.readFileSync(geminiSettingsPath, 'utf8')); } catch { /* fresh start */ }
    }
    settings.mcpServers = settings.mcpServers || {};
    settings.mcpServers.Jenkins = mcpConfig;
    fs.writeFileSync(geminiSettingsPath, JSON.stringify(settings, null, 2));
    console.log(`[${new Date().toISOString()}] Jenkins MCP configured for Gemini CLI`);
  } catch (err) {
    console.error(`[${new Date().toISOString()}] Jenkins MCP config (Gemini) failed: ${err.message}`);
  }

  try {
    writeClaudeMcpServer('Jenkins', mcpConfig);
    console.log(`[${new Date().toISOString()}] Jenkins MCP configured for Claude Code`);
  } catch (err) {
    console.error(`[${new Date().toISOString()}] Jenkins MCP config (Claude) failed: ${err.message}`);
  }
}

module.exports = {
  hasGitHubCredentials,
  generateInstallationToken,
  discoverAndGenerateTokens,
  setupGitCredentials,
  setupGitHubTooling,
  hasGitLabCredentials,
  readGitLabToken,
  setupGitLabCredentials,
  setupGitLabTooling,
  setupArgoCDMCP,
  setupCLILogins,
  setupRemoteK8sMCPs,
  getRemoteClustersMeta,
  setupRegistryCredentials,
  hasRegistryCredentials,
  hasJenkinsCredentials,
  setupJenkinsMCP,
  GITLAB_HOST,
  CLI_LOGIN_INTERVAL_MS,
};
