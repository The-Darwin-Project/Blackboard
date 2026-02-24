// gemini-sidecar/credentials.js
// @ai-rules:
// 1. [Constraint]: Consolidates ALL authentication, credential setup, and CLI login logic.
// 2. [Pattern]: GitHub App JWT exchange for installation tokens; GitLab uses static PAT; ArgoCD session API for MCP JWT. Claude MCP -> ~/.claude.json (via writeClaudeMcpServer); Gemini MCP -> ~/.gemini/settings.json.
// 3. [Gotcha]: findPrivateKeyPath is internal — not exported; only public API exposed.
// 4. [Gotcha]: _lastCLILoginTime is module-scoped dedup — setupCLILogins skips ArgoCD/Kargo login if already done within 30 min.
// 5. [Gotcha]: setupArgoCDMCP sets NODE_TLS_REJECT_UNAUTHORIZED=0 globally when ARGOCD_INSECURE=true. Acceptable for internal clusters.

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
  return fs.existsSync(APP_ID_PATH) &&
         fs.existsSync(INSTALL_ID_PATH) &&
         findPrivateKeyPath() !== null;
}

/**
 * Generate GitHub App installation token
 * Mirrors logic from BlackBoard/src/utils/github_app.py
 * @returns {Promise<string>} Installation access token (valid 1 hour)
 */
async function generateInstallationToken() {
  const privateKeyPath = findPrivateKeyPath();
  if (!privateKeyPath) {
    throw new Error('GitHub App private key not found in /secrets/github/');
  }

  // Read credentials from mounted secrets
  const appId = fs.readFileSync(APP_ID_PATH, 'utf8').trim();
  const installId = fs.readFileSync(INSTALL_ID_PATH, 'utf8').trim();
  const privateKey = fs.readFileSync(privateKeyPath, 'utf8');

  console.log(`[${new Date().toISOString()}] Generating GitHub App token (app=${appId}, install=${installId})`);

  // Create JWT (same payload as Python: iat-60, exp+540, iss=appId)
  const now = Math.floor(Date.now() / 1000);
  const payload = { iat: now - 60, exp: now + 540, iss: appId };
  const jwtToken = jwt.sign(payload, privateKey, { algorithm: 'RS256' });

  // Exchange JWT for installation token
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

/**
 * Configure git credentials for GitHub operations
 * Agent CLI will handle clone/pull/push itself
 * @param {string} token - Installation access token
 * @param {string} workDir - Working directory for git operations
 */
function setupGitCredentials(token, workDir) {
  console.log(`[${new Date().toISOString()}] Configuring git credentials`);

  try {
    // Ensure work directory exists
    if (!fs.existsSync(workDir)) {
      fs.mkdirSync(workDir, { recursive: true });
    }

    // Configure git user globally (for any repo the agent clones)
    execSync(`git config --global user.name "${process.env.GIT_USER_NAME || 'Darwin Agent'}"`, { encoding: 'utf8' });
    execSync(`git config --global user.email "${process.env.GIT_USER_EMAIL || 'darwin-agent@darwin-project.io'}"`, { encoding: 'utf8' });

    // Mark work directory as safe (PVC mounted volumes need this)
    execSync(`git config --global --add safe.directory ${workDir}`, { encoding: 'utf8' });
    execSync(`git config --global --add safe.directory '*'`, { encoding: 'utf8' });  // Allow any subdir

    // Store credentials using host-specific helper (coexists with GitLab credentials)
    const credFile = `/tmp/git-creds-${Date.now()}`;
    execSync(`git config --global credential.https://github.com.helper 'store --file=${credFile}'`, { encoding: 'utf8' });
    fs.writeFileSync(credFile, `https://x-access-token:${token}@github.com\n`, { mode: 0o600 });

    console.log(`[${new Date().toISOString()}] Git credentials configured`);

  } catch (err) {
    console.error(`[${new Date().toISOString()}] Git config error:`, err.message);
    throw new Error(`Failed to configure git: ${err.message}`);
  }
}

/**
 * Configure GitHub MCP server + gh CLI auth with a fresh installation token.
 * Both Gemini CLI and Claude Code use the MCP server for structured GitHub interaction.
 * The gh CLI uses GH_TOKEN env var for direct commands.
 *
 * @param {string} token - GitHub App installation token
 */
function setupGitHubTooling(token) {
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

module.exports = {
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
  CLI_LOGIN_INTERVAL_MS,
};
