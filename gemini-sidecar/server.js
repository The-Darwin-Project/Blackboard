// gemini-sidecar/server.js
// @ai-rules:
// 1. [Pattern]: Agent result delivery via sendResults/sendMessage -> POST /callback -> _callbackResult.
//    _callbackResult (module-level) stores the latest "result" type callback. "message" type forwards as WS progress only.
// 2. [Pattern]: resolveResult() is the single result resolution function used by BOTH executeCLI and executeCLIStreaming close handlers.
//    Priority: _callbackResult (callback) -> cachedFindings (fs.watch) -> disk findings -> retry prompt -> stdout tail.
// 3. [Pattern]: All WS result messages carry a `source` field: "callback" | "findings" | "stdout". Brain uses this for preference logic.
// 4. [Pattern]: AGENT_CLI env var routes spawn() to 'gemini' or 'claude' binary via buildCLICommand().
// 5. [Pattern]: buildCLICommand reads AGENT_PERMISSION_MODE env var. If set (e.g. "plan") -> --permission-mode <value>; else autoApprove -> --dangerously-skip-permissions. Currently no agents use plan mode (soft rules via CLAUDE.md instead).
// 6. [Pattern]: Claude session_id extracted from stream-json init event (type=system, subtype=init) and stored on currentTask.sessionId.
// 7. [Pattern]: Claude settings.json pre-created at startup (~/.claude/settings.json) to skip onboarding flow.
// 8. [Pattern]: Both Gemini and Claude use headless mode (-p + stream-json). Follow-ups via --resume <session_id>. No PTY.
// HTTP wrapper for Gemini/Claude Code CLIs with GitHub/GitLab authentication
// Exposes POST /execute, POST /callback endpoints for the brain container
// Handles dynamic repo cloning with fresh tokens per execution

const http = require('http');
const fs = require('fs');
const path = require('path');
const os = require('os');
const { spawn, execSync } = require('child_process');
const jwt = require('jsonwebtoken');
const WebSocket = require('ws');

const PORT = process.env.PORT || 9090;
const ROLE_TIMEOUTS = {
    architect: 600000,   // 10 min
    sysadmin: 300000,    // 5 min
    developer: 900000,   // 15 min
    qe: 600000,          // 10 min
    default: 300000,     // 5 min fallback
};
const TIMEOUT_MS = parseInt(process.env.TIMEOUT_MS) || ROLE_TIMEOUTS[process.env.AGENT_ROLE || 'default'] || ROLE_TIMEOUTS.default;
const FINDINGS_FRESHNESS_MS = 30000; // 30s -- findings.md older than this is stale
const DEFAULT_WORK_DIR = '/data/gitops';

// Agent callback result -- set by POST /callback when agent calls sendResults.
// Module-level so both the HTTP handler and the close handler can access it.
// Reset to null at the start of each new task.
let _callbackResult = null;

// CLI routing -- AGENT_CLI selects which binary to spawn (gemini or claude)
const AGENT_CLI = process.env.AGENT_CLI || 'gemini';
const AGENT_MODEL = process.env.AGENT_MODEL || process.env.GEMINI_MODEL || '';
// GEMINI_INTERACTIVE removed -- both CLIs now use headless mode + session resume.
// Strip ANSI escape codes from PTY output (colors, cursor movements, etc.)
// PTY output is raw terminal data -- Brain/LLM needs clean text.
const ANSI_RE = /\x1b\[[0-9;]*[a-zA-Z]|\x1b\].*?\x07|\x1b[()][AB012]|\x1b\[[\?]?[0-9;]*[hlm]/g;
function stripAnsi(text) { return text.replace(ANSI_RE, ''); }
// Agent role -- used to restrict tools (e.g., architect can't write code files)
const AGENT_ROLE = process.env.AGENT_ROLE || '';

// Pre-create Claude settings to skip first-run onboarding
const claudeDir = path.join(os.homedir(), '.claude');
fs.mkdirSync(claudeDir, { recursive: true });
const claudeSettingsPath = path.join(claudeDir, 'settings.json');
if (!fs.existsSync(claudeSettingsPath)) {
  fs.writeFileSync(claudeSettingsPath, JSON.stringify({ theme: 'dark', hasCompletedOnboarding: true }));
  console.log('Claude settings.json created (skip onboarding)');
}

// Pre-create Gemini settings. Trust is disabled so the trust dialog never appears.
// Auth is handled by env vars in headless mode (no interactive wizard needed).
const geminiDir = path.join(os.homedir(), '.gemini');
fs.mkdirSync(geminiDir, { recursive: true });
const geminiSettingsPath = path.join(geminiDir, 'settings.json');
try {
  let geminiSettings = {};
  if (fs.existsSync(geminiSettingsPath)) {
    try { geminiSettings = JSON.parse(fs.readFileSync(geminiSettingsPath, 'utf8')); } catch { /* fresh start */ }
  }
  // Disable trust folder prompt (all agent working dirs are safe)
  geminiSettings.security = geminiSettings.security || {};
  geminiSettings.security.folderTrust = { enabled: false };
  // Preserve any existing MCP server configs
  geminiSettings.mcpServers = geminiSettings.mcpServers || {};
  fs.writeFileSync(geminiSettingsPath, JSON.stringify(geminiSettings, null, 2));
  console.log('Gemini settings.json created (trust disabled)');
} catch (err) {
  console.error(`Gemini settings.json error: ${err.message}`);
}
// Trusted folders: JSON object format (path -> trust level), not array.
// Even with trust disabled, an invalid file causes a warning on every run.
const trustedFoldersPath = path.join(geminiDir, 'trustedFolders.json');
try {
  const trustedFolders = {
    '/data/gitops': 'TRUST_FOLDER',
    '/data/gitops-architect': 'TRUST_FOLDER',
    '/data/gitops-sysadmin': 'TRUST_FOLDER',
    '/data/gitops-developer': 'TRUST_FOLDER',
    '/data/gitops-qe': 'TRUST_FOLDER',
  };
  fs.writeFileSync(trustedFoldersPath, JSON.stringify(trustedFolders, null, 2));
  console.log('Gemini trustedFolders.json created (object format)');
} catch (err) {
  console.error(`Gemini trustedFolders.json error: ${err.message}`);
}

/**
 * Unified stream-json line parser for both Gemini and Claude CLIs.
 * Returns { text, sessionId, toolCalls, done } or null if not user-facing.
 *
 * Gemini stream-json schema (probed 2026-02-13):
 *   {"type":"init","session_id":"...","model":"auto-gemini-2.5"}
 *   {"type":"message","role":"assistant","content":"...","delta":true}
 *   {"type":"result","status":"success","stats":{"tool_calls":0,...}}
 *
 * Claude stream-json schema:
 *   {"type":"system","subtype":"init","session_id":"..."}
 *   {"type":"content_block_delta","delta":{"type":"text_delta","text":"..."}}
 *   {"type":"assistant","message":{"content":[{"type":"text","text":"..."}]}}
 *   {"type":"result","result":"..."}
 */
function parseStreamLine(line) {
    try {
        const obj = JSON.parse(line);

        // --- Init events (both CLIs emit session_id) ---
        if (obj.type === 'init' || (obj.type === 'system' && obj.subtype === 'init')) {
            return { text: null, sessionId: obj.session_id || null, toolCalls: null, done: false };
        }

        // --- Gemini: assistant message ---
        if (obj.type === 'message' && obj.role === 'assistant' && obj.content) {
            return { text: obj.content, sessionId: null, toolCalls: null, done: false };
        }

        // --- Claude: content_block_delta (incremental token) ---
        if (obj.type === 'content_block_delta' && obj.delta?.text) {
            return { text: obj.delta.text, sessionId: null, toolCalls: null, done: false };
        }

        // --- Claude: assistant message (summarized) ---
        if (obj.type === 'assistant' && obj.message?.content) {
            const texts = obj.message.content
                .filter(c => c.type === 'text')
                .map(c => c.text);
            return { text: texts.join('\n') || null, sessionId: null, toolCalls: null, done: false };
        }

        // --- Result events (both CLIs) ---
        if (obj.type === 'result') {
            const toolCalls = obj.stats?.tool_calls ?? null;
            let text = null;
            if (obj.result) {
                text = typeof obj.result === 'string' ? obj.result : JSON.stringify(obj.result);
            }
            return { text, sessionId: null, toolCalls, done: true };
        }
    } catch (e) {
        // Not JSON -- return raw line as text
        return { text: line, sessionId: null, toolCalls: null, done: false };
    }
    return null;
}

// Backward compat wrapper -- existing code calls parseClaudeStreamLine()
function parseClaudeStreamLine(line) {
    const parsed = parseStreamLine(line);
    return parsed?.text || null;
}

/**
 * Build CLI command based on AGENT_CLI env var.
 * Routes to 'gemini' or 'claude' binary with appropriate flags.
 */
function buildCLICommand(prompt, options = {}) {
    const permissionMode = process.env.AGENT_PERMISSION_MODE || '';
    if (AGENT_CLI === 'claude') {
        const args = [];
        if (permissionMode === 'plan') {
            args.push('--permission-mode', 'plan');
        } else if (options.autoApprove) {
            args.push('--dangerously-skip-permissions');
        }
        args.push('--output-format', 'stream-json', '--verbose');
        args.push('--model', AGENT_MODEL || 'claude-opus-4-6');
        if (options.sessionId) {
            args.push('--resume', options.sessionId);
        }
        args.push('-p', prompt);
        return { binary: 'claude', args };
    } else {
        // Gemini path -- headless mode with stream-json (same pattern as Claude)
        // Auth handled by env vars (GOOGLE_GENAI_USE_VERTEXAI + GOOGLE_APPLICATION_CREDENTIALS)
        const args = [];
        if (options.autoApprove) args.push('--yolo');
        args.push('-o', 'stream-json');
        if (options.sessionId) {
            args.push('--resume', options.sessionId);
        }
        args.push('-p', prompt);
        return { binary: 'gemini', args };
    }
}

// NOTE: PTY/interactive mode (spawnInteractiveGemini) has been removed.
// Both Gemini and Claude now use headless mode (-p + -o stream-json) with
// session resume (--resume <session_id>) for follow-ups. This eliminates
// the TUI auth wizard, ANSI codes, and PTY complexity. Auth is handled
// entirely by env vars (GOOGLE_GENAI_USE_VERTEXAI + GOOGLE_APPLICATION_CREDENTIALS)
// per https://geminicli.com/docs/get-started/authentication/

// GitHub App secret paths (mounted from K8s secret)
const SECRETS_PATH = '/secrets/github';
const APP_ID_PATH = `${SECRETS_PATH}/app-id`;
const INSTALL_ID_PATH = `${SECRETS_PATH}/installation-id`;
// Note: Private key filename may vary - we'll find it dynamically
const PRIVATE_KEY_PATTERN = /\.pem$/;

// GitLab token secret paths (mounted from K8s secret)
const GITLAB_SECRETS_PATH = '/secrets/gitlab';
const GITLAB_TOKEN_PATH = process.env.GITLAB_TOKEN_PATH || `${GITLAB_SECRETS_PATH}/token`;
const GITLAB_HOST = process.env.GITLAB_HOST || '';

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
 * Login to ArgoCD/Kargo CLIs (awaitable, with deduplication).
 * Returns a Promise that resolves when both logins complete (or timeout after 10s).
 * Skips login if already logged in within the last 30 minutes.
 */
let _lastCLILoginTime = 0;
const CLI_LOGIN_INTERVAL_MS = 30 * 60 * 1000; // 30 min

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

    // 2. Configure GitHub MCP server for Gemini CLI
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
            command: 'github-mcp-server',
            args: ['stdio'],
            env: { GITHUB_PERSONAL_ACCESS_TOKEN: token },
        };
        fs.writeFileSync(geminiSettingsPath, JSON.stringify(settings, null, 2));
        console.log(`[${new Date().toISOString()}] GitHub MCP configured for Gemini CLI`);
    } catch (err) {
        console.error(`[${new Date().toISOString()}] GitHub MCP config (Gemini) failed: ${err.message}`);
    }

    // 3. Configure GitHub MCP server for Claude Code
    const claudeSettingsDir = `${process.env.HOME}/.claude`;
    const claudeSettingsPath = `${claudeSettingsDir}/settings.json`;
    try {
        fs.mkdirSync(claudeSettingsDir, { recursive: true });
        let claudeSettings = {};
        if (fs.existsSync(claudeSettingsPath)) {
            try { claudeSettings = JSON.parse(fs.readFileSync(claudeSettingsPath, 'utf8')); } catch { /* fresh start */ }
        }
        claudeSettings.mcpServers = claudeSettings.mcpServers || {};
        claudeSettings.mcpServers.GitHub = {
            command: 'github-mcp-server',
            args: ['stdio'],
            env: { GITHUB_PERSONAL_ACCESS_TOKEN: token },
        };
        fs.writeFileSync(claudeSettingsPath, JSON.stringify(claudeSettings, null, 2));
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
    execSync(`git config --global credential.https://${GITLAB_HOST}.helper 'store --file=${credFile}'`, { encoding: 'utf8' });
    console.log(`[${new Date().toISOString()}] GitLab git credentials configured for ${GITLAB_HOST}`);
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
    try { execSync('which glab', { stdio: 'ignore' }); hasGlab = true; } catch { /* not installed */ }

    if (!hasGlab) {
        console.log(`[${new Date().toISOString()}] glab not installed, skipping GitLab MCP config`);
        return;
    }

    // MCP config for both CLIs: use `glab mcp serve` (replaces deprecated @modelcontextprotocol/server-gitlab)
    // glab reads GITLAB_TOKEN and GITLAB_HOST from env -- no extra env vars needed in MCP config
    const mcpConfig = {
        command: 'glab',
        args: ['mcp', 'serve'],
        env: {
            GITLAB_TOKEN: token,
            GITLAB_HOST: GITLAB_HOST,
            NODE_TLS_REJECT_UNAUTHORIZED: '0',  // Internal GitLab with self-signed certs
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

    // 3. Configure GitLab MCP for Claude Code
    const claudeSettingsDir = `${process.env.HOME}/.claude`;
    const claudeSettingsPath = `${claudeSettingsDir}/settings.json`;
    try {
        fs.mkdirSync(claudeSettingsDir, { recursive: true });
        let claudeSettings = {};
        if (fs.existsSync(claudeSettingsPath)) {
            try { claudeSettings = JSON.parse(fs.readFileSync(claudeSettingsPath, 'utf8')); } catch { /* fresh start */ }
        }
        claudeSettings.mcpServers = claudeSettings.mcpServers || {};
        claudeSettings.mcpServers.GitLab = mcpConfig;
        fs.writeFileSync(claudeSettingsPath, JSON.stringify(claudeSettings, null, 2));
        console.log(`[${new Date().toISOString()}] GitLab MCP configured for Claude Code (glab mcp serve)`);
    } catch (err) {
        console.error(`[${new Date().toISOString()}] GitLab MCP config (Claude) failed: ${err.message}`);
    }

    console.log(`[${new Date().toISOString()}] glab CLI + GitLab MCP ready (${GITLAB_HOST})`);
}

/**
 * Safe WebSocket send - only sends if connection is open
 */
function wsSend(ws, data) {
  if (ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(data));
  }
}

/**
 * Read agent findings from the results folder with freshness check.
 * Agents write their deliverable to ./results/findings.md.
 * Returns null if file is missing, stale, or empty -- caller decides fallback.
 *
 * @param {string} workDir - Agent working directory
 * @returns {string|null} Extracted findings or null
 */
function readFindings(workDir) {
  const findingsPath = `${workDir}/results/findings.md`;
  try {
    if (fs.existsSync(findingsPath)) {
      const stats = fs.statSync(findingsPath);
      const ageMs = Date.now() - stats.mtimeMs;
      if (ageMs > FINDINGS_FRESHNESS_MS) {
        console.log(`[${new Date().toISOString()}] findings.md is stale (${Math.round(ageMs/1000)}s old), ignoring`);
        return null;
      }
      const content = fs.readFileSync(findingsPath, 'utf8').trim();
      fs.unlinkSync(findingsPath);
      console.log(`[${new Date().toISOString()}] Read findings from ${findingsPath} (${content.length} chars)`);
      if (content.length > 0) return content;
      console.log(`[${new Date().toISOString()}] Findings file was empty`);
    }
  } catch (err) {
    console.log(`[${new Date().toISOString()}] Could not read findings file: ${err.message}`);
  }
  return null;
}

/**
 * Fallback: extract the final meaningful segment from stdout when no findings file is available.
 * 
 * The full stream contains planning noise ("I will check...", "I will investigate...")
 * that the Brain already saw via progress messages. Sending it again as the result
 * pollutes the Brain's LLM context with duplicate chatter.
 * 
 * Strategy: return only the last ~3000 chars -- typically the agent's final summary,
 * not the early planning/investigation text.
 * 
 * @param {string} effectiveOutput - Full captured stdout (or Claude parsed text)
 * @returns {string} Tail segment of stdout (max ~3000 chars)
 */
function stdoutFallback(effectiveOutput) {
  const MAX_FALLBACK_CHARS = 3000;
  if (effectiveOutput.length <= MAX_FALLBACK_CHARS) {
    console.log(`[${new Date().toISOString()}] No findings, using full stdout (${effectiveOutput.length} chars)`);
    return effectiveOutput;
  }
  // Return tail -- the final output is more likely to contain the actual deliverable
  const tail = effectiveOutput.slice(-MAX_FALLBACK_CHARS);
  console.log(`[${new Date().toISOString()}] No findings, using stdout tail (${MAX_FALLBACK_CHARS} of ${effectiveOutput.length} chars)`);
  return `[...truncated planning output...]\n\n${tail}`;
}

/**
 * Unified result resolution for CLI close handlers.
 * Single function used by BOTH executeCLI and executeCLIStreaming.
 * 
 * Priority:
 *   1. _callbackResult (from sendResults)     -> source: "callback"
 *   2. cachedFindings (from fs.watch)          -> source: "findings"
 *   3. disk findings (readFindings)            -> source: "findings"
 *   4. retry (requestFindings)                 -> source: "findings"
 *   5. stdoutFallback (tail 3000 chars)        -> source: "stdout"
 * 
 * @param {object} opts
 * @param {string|null} opts.callbackResult - Captured _callbackResult at close time
 * @param {object|null} opts.cachedFindings - {content, timestamp} from fs.watch
 * @param {string} opts.findingsPath - Absolute path to findings.md
 * @param {string} opts.workDir - Agent working directory
 * @param {boolean} opts.autoApprove - For retry prompt
 * @param {string} opts.effectiveOutput - Full stream text (fallback)
 * @returns {Promise<{output: string, source: string}>}
 */
async function resolveResult(opts) {
  const { callbackResult, cachedFindings, findingsPath, workDir, autoApprove, effectiveOutput } = opts;

  // 1. Callback result (from sendResults script)
  if (callbackResult && callbackResult.length > 0) {
    console.log(`[${new Date().toISOString()}] Using callback result (${callbackResult.length} chars)`);
    return { output: callbackResult, source: 'callback' };
  }

  // 2. Cached findings from fs.watch (captured in real-time for this run)
  if (cachedFindings && cachedFindings.content && cachedFindings.content.length > 0) {
    console.log(`[${new Date().toISOString()}] Using cached findings (${cachedFindings.content.length} chars)`);
    try { if (fs.existsSync(findingsPath)) fs.unlinkSync(findingsPath); } catch(e) {}
    return { output: cachedFindings.content, source: 'findings' };
  }

  // 3. Read findings file from disk (no freshness -- cleaned at run start)
  if (fs.existsSync(findingsPath)) {
    try {
      const content = fs.readFileSync(findingsPath, 'utf8').trim();
      fs.unlinkSync(findingsPath);
      if (content.length > 0) {
        console.log(`[${new Date().toISOString()}] Read findings from disk (${content.length} chars)`);
        return { output: content, source: 'findings' };
      }
    } catch (err) {
      console.log(`[${new Date().toISOString()}] Could not read findings file: ${err.message}`);
    }
  }

  // 4. Retry: ask agent to write report
  console.log(`[${new Date().toISOString()}] No findings, requesting report from agent`);
  const retryFindings = await requestFindings(workDir, autoApprove);
  if (retryFindings) {
    return { output: retryFindings, source: 'findings' };
  }

  // 5. Final fallback: stdout tail
  return { output: stdoutFallback(effectiveOutput), source: 'stdout' };
}

/**
 * Retry: spawn agent CLI to write a findings report when none was produced.
 * Returns the report content or null on failure/timeout.
 * Never rejects -- resolve(null) on all error paths.
 *
 * @param {string} workDir - Agent working directory
 * @param {boolean} autoApprove - Pass --yolo / --dangerously-skip-permissions
 * @returns {Promise<string|null>}
 */
async function requestFindings(workDir, autoApprove) {
  const prompt = 'You completed your task but did not write a completion report. '
    + 'Write a brief summary of what you did to ./results/findings.md now. '
    + 'Include: files changed, what was implemented or verified, and the outcome.';
  const { binary, args } = buildCLICommand(prompt, { autoApprove });
  return new Promise((resolve) => {
    const timeout = setTimeout(() => resolve(null), 60000);
    const child = spawn(binary, args, {
      env: { ...process.env, ...(AGENT_CLI === 'gemini' ? { GOOGLE_GENAI_USE_VERTEXAI: 'true' } : {}) },
      cwd: workDir,
      timeout: 60000,
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    child.on('close', () => {
      clearTimeout(timeout);
      // Read findings -- no freshness check needed (just written)
      const findingsPath = `${workDir}/results/findings.md`;
      try {
        if (fs.existsSync(findingsPath)) {
          const content = fs.readFileSync(findingsPath, 'utf8').trim();
          fs.unlinkSync(findingsPath);
          if (content.length > 0) { resolve(content); return; }
        }
      } catch (e) {
        console.log(`[${new Date().toISOString()}] Retry findings read failed: ${e.message}`);
      }
      resolve(null);
    });
    child.on('error', (err) => {
      console.log(`[${new Date().toISOString()}] Retry spawn error: ${err.message}`);
      clearTimeout(timeout);
      resolve(null);
    });
  });
}

/**
 * Ensure results directory exists and is clean before a new task.
 * Handles stale files from crashed previous runs.
 */
function prepareResultsDir(workDir) {
  const resultsDir = `${workDir}/results`;
  try {
    if (fs.existsSync(resultsDir)) {
      // Clean stale files from previous runs
      const files = fs.readdirSync(resultsDir);
      for (const f of files) {
        fs.unlinkSync(`${resultsDir}/${f}`);
      }
    } else {
      fs.mkdirSync(resultsDir, { recursive: true });
    }
  } catch (err) {
    console.log(`[${new Date().toISOString()}] Results dir prep warning: ${err.message}`);
  }
}

/**
 * Execute agent CLI with given prompt and options
 */
async function executeCLI(prompt, options = {}) {
  return new Promise((resolve, reject) => {
    const { binary, args } = buildCLICommand(prompt, { autoApprove: options.autoApprove });
    
    console.log(`[${new Date().toISOString()}] Executing: ${AGENT_CLI} (prompt length: ${prompt.length})`);
    
    // Prepare results directory (clean stale files, ensure exists)
    prepareResultsDir(options.cwd || DEFAULT_WORK_DIR);

    // Watch for findings file (preemptive read to avoid race with PVC flush)
    const resultsDir = `${options.cwd || DEFAULT_WORK_DIR}/results`;
    const findingsPath = `${resultsDir}/findings.md`;
    let cachedFindings = null;  // { content: string, timestamp: number } | null
    let watcher = null;
    try {
      watcher = fs.watch(resultsDir, (eventType, filename) => {
        if (filename === 'findings.md' && (eventType === 'rename' || eventType === 'change')) {
          try {
            if (fs.existsSync(findingsPath)) {
              const raw = fs.readFileSync(findingsPath, 'utf8').trim();
              cachedFindings = { content: raw, timestamp: Date.now() };
              console.log(`[${new Date().toISOString()}] Preemptive read: findings.md (${raw.length} chars)`);
            }
          } catch (err) {
            console.log(`[${new Date().toISOString()}] Preemptive read failed: ${err.message}`);
          }
        }
      });
    } catch (err) {
      console.log(`[${new Date().toISOString()}] fs.watch setup failed: ${err.message}`);
    }

    const child = spawn(binary, args, {
      env: {
        ...process.env,
        ...(AGENT_CLI === 'gemini' ? { GOOGLE_GENAI_USE_VERTEXAI: 'true' } : {}),
      },
      cwd: options.cwd || DEFAULT_WORK_DIR,
      timeout: TIMEOUT_MS,
      stdio: ['ignore', 'pipe', 'pipe'],  // Close stdin -- Claude CLI blocks on open pipe
    });
    
    let stdout = '';
    let stderr = '';
    let streamTextAccum = '';  // Accumulate parsed text from stream-json (both CLIs)
    
    child.stdout.on('data', (data) => {
      const text = data.toString();
      stdout += text;
      // Unified stream-json parsing (both Gemini and Claude emit stream-json now)
      for (const line of text.split('\n')) {
        if (!line.trim()) continue;
        const parsed = parseStreamLine(line);
        if (parsed?.text) streamTextAccum += parsed.text;
        if (parsed?.sessionId && currentTask) currentTask.sessionId = parsed.sessionId;
      }
    });
    
    child.stderr.on('data', (data) => {
      stderr += data.toString();
    });
    
    child.on('close', (code) => {
      // Close the watcher
      if (watcher) { try { watcher.close(); } catch(e) {} }

      // Stream-json parsed output (both CLIs) takes precedence over raw stdout
      const effectiveOutput = streamTextAccum || stdout;

      console.log(`[${new Date().toISOString()}] ${AGENT_CLI} exited with code ${code}`);
      console.log(`[${new Date().toISOString()}] stdout (${effectiveOutput.length} chars): ${effectiveOutput}`);
      if (stderr) {
        console.log(`[${new Date().toISOString()}] stderr: ${stderr}`);
      }
      
      if (code === 0) {
        // Try JSON parse first (structured output)
        try {
          const result = JSON.parse(effectiveOutput);
          resolve({ status: 'success', exitCode: code, output: result, source: 'stdout' });
          return;
        } catch (e) {}

        // Unified result resolution (callback -> findings -> retry -> stdout)
        const capturedCallback = _callbackResult;
        _callbackResult = null;
        resolveResult({
          callbackResult: capturedCallback,
          cachedFindings,
          findingsPath,
          workDir: options.cwd || DEFAULT_WORK_DIR,
          autoApprove: options.autoApprove !== false,
          effectiveOutput,
        }).then(({ output, source }) => {
          resolve({ status: 'success', exitCode: code, output, source });
        }).catch((err) => {
          console.error(`[${new Date().toISOString()}] resolveResult error: ${err.message}`);
          resolve({ status: 'success', exitCode: code, output: stdoutFallback(effectiveOutput), source: 'stdout' });
        });
      } else {
        resolve({ status: 'failed', exitCode: code, stderr, stdout: effectiveOutput, source: 'stdout' });
      }
    });
    
    child.on('error', (err) => {
      console.error(`[${new Date().toISOString()}] Spawn error:`, err.message);
      reject(err);
    });
  });
}

/**
 * Execute agent CLI with streaming progress over WebSocket
 */
async function executeCLIStreaming(ws, eventId, prompt, options = {}) {
  return new Promise((resolve, reject) => {
    const { binary, args } = buildCLICommand(prompt, {
      autoApprove: options.autoApprove,
      sessionId: options.sessionId,
    });

    console.log(`[${new Date().toISOString()}] Streaming exec: ${AGENT_CLI} (prompt: ${prompt.length} chars)`);

    // Prepare results directory (clean stale files, ensure exists)
    prepareResultsDir(options.cwd || DEFAULT_WORK_DIR);

    // Watch for findings file (preemptive read to avoid race with PVC flush)
    const resultsDir = `${options.cwd || DEFAULT_WORK_DIR}/results`;
    const findingsPath = `${resultsDir}/findings.md`;
    let cachedFindings = null;  // { content: string, timestamp: number } | null
    let watcher = null;
    try {
      watcher = fs.watch(resultsDir, (eventType, filename) => {
        if (filename === 'findings.md' && (eventType === 'rename' || eventType === 'change')) {
          try {
            if (fs.existsSync(findingsPath)) {
              const raw = fs.readFileSync(findingsPath, 'utf8').trim();
              cachedFindings = { content: raw, timestamp: Date.now() };
              console.log(`[${new Date().toISOString()}] Preemptive read: findings.md (${raw.length} chars)`);
            }
          } catch (err) {
            console.log(`[${new Date().toISOString()}] Preemptive read failed: ${err.message}`);
          }
        }
      });
    } catch (err) {
      console.log(`[${new Date().toISOString()}] fs.watch setup failed: ${err.message}`);
    }

    const child = spawn(binary, args, {
      env: {
        ...process.env,
        ...(AGENT_CLI === 'gemini' ? { GOOGLE_GENAI_USE_VERTEXAI: 'true' } : {}),
      },
      cwd: options.cwd || DEFAULT_WORK_DIR,
      timeout: TIMEOUT_MS,
      stdio: ['ignore', 'pipe', 'pipe'],  // Close stdin -- Claude CLI blocks on open pipe
    });

    currentTask = { eventId, child };

    let stdout = '';
    let stderr = '';
    let lineBuffer = '';
    let streamTextAccum = '';  // Accumulate parsed text from stream-json (both CLIs)

    // Stream stdout line-by-line as progress (unified parser for both CLIs)
    child.stdout.on('data', (data) => {
      const text = data.toString();
      stdout += text;
      lineBuffer += text;

      // Flush complete lines
      const lines = lineBuffer.split('\n');
      lineBuffer = lines.pop(); // Keep incomplete line in buffer
      for (const line of lines) {
        if (!line.trim()) continue;
        const parsed = parseStreamLine(line);
        if (!parsed) continue;
        // Session ID extraction (both CLIs)
        if (parsed.sessionId && currentTask) {
          currentTask.sessionId = parsed.sessionId;
          console.log(`[${new Date().toISOString()}] [${eventId}] Session: ${parsed.sessionId}`);
        }
        // Displayable text -> progress + accumulate
        if (parsed.text) {
          streamTextAccum += parsed.text;
          console.log(`[${new Date().toISOString()}] [${eventId}] >> ${parsed.text}`);
          wsSend(ws, { type: 'progress', event_id: eventId, message: parsed.text });
        }
      }
    });

    child.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    child.on('close', (code) => {
      // Close the watcher
      if (watcher) { try { watcher.close(); } catch(e) {} }

      // Capture session ID before currentTask is cleared
      const capturedSessionId = currentTask?.sessionId || null;

      // Flush remaining buffer
      if (lineBuffer.trim()) {
        const parsed = parseStreamLine(lineBuffer);
        if (parsed?.text) {
          streamTextAccum += parsed.text;
          wsSend(ws, { type: 'progress', event_id: eventId, message: parsed.text });
        }
      }

      // Stream-json parsed output takes precedence over raw stdout
      const effectiveOutput = streamTextAccum || stdout;

      console.log(`[${new Date().toISOString()}] ${AGENT_CLI} exited code ${code} (${effectiveOutput.length} chars)`);
      if (effectiveOutput.length > 0) {
        console.log(`[${new Date().toISOString()}] ${AGENT_CLI} stdout: ${effectiveOutput}`);
      } else {
        console.log(`[${new Date().toISOString()}] WARNING: ${AGENT_CLI} produced EMPTY stdout`);
      }
      if (stderr) {
        console.log(`[${new Date().toISOString()}] ${AGENT_CLI} stderr: ${stderr}`);
      }

      if (code === 0) {
        // Try JSON parse first (structured output)
        try {
          const result = JSON.parse(effectiveOutput);
          resolve({ status: 'success', sessionId: capturedSessionId, output: result, source: 'stdout' });
          return;
        } catch (e) {}

        // Unified result resolution (callback -> findings -> retry -> stdout)
        const capturedCallback = _callbackResult;
        _callbackResult = null;
        resolveResult({
          callbackResult: capturedCallback,
          cachedFindings,
          findingsPath,
          workDir: options.cwd || DEFAULT_WORK_DIR,
          autoApprove: options.autoApprove !== false,
          effectiveOutput,
        }).then(({ output, source }) => {
          resolve({ status: 'success', sessionId: capturedSessionId, output, source });
        }).catch((err) => {
          console.error(`[${new Date().toISOString()}] resolveResult error: ${err.message}`);
          resolve({ status: 'success', sessionId: capturedSessionId, output: stdoutFallback(effectiveOutput), source: 'stdout' });
        });
      } else {
        resolve({ status: 'failed', sessionId: capturedSessionId, exitCode: code, stderr, stdout: effectiveOutput, source: 'stdout' });
      }
    });

    child.on('error', (err) => {
      console.error(`[${new Date().toISOString()}] Spawn error:`, err.message);
      reject(err);
    });
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
        _callbackResult = content;
        const eid = currentTask?.eventId || 'no-task';
        console.log(`[${new Date().toISOString()}] [${eid}] Callback result stored (${content.length} chars)`);
        // Forward as partial_result via WS if task is active
        if (currentTask?.ws) {
          wsSend(currentTask.ws, {
            type: 'partial_result',
            event_id: currentTask.eventId,
            content,
          });
        }
      } else {
        // sendMessage: forward as progress note (do NOT overwrite deliverable)
        const eid2 = currentTask?.eventId || 'no-task';
        console.log(`[${new Date().toISOString()}] [${eid2}] Callback message forwarded (${content.length} chars)`);
        if (currentTask?.ws) {
          wsSend(currentTask.ws, {
            type: 'progress',
            event_id: currentTask.eventId,
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
    if (currentTask) {
      res.writeHead(429, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'Agent busy', event_id: currentTask.eventId || '' }));
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
      _callbackResult = null; // Reset stale callback from previous WS task
      
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

// Create and start server
const server = http.createServer(handleRequest);

// WebSocket server on /ws path
const wss = new WebSocket.Server({ server, path: '/ws' });

// Track current execution state
let currentTask = null; // { eventId, child } or null

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
      if (currentTask) {
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

      if (!prompt) {
        ws.send(JSON.stringify({ type: 'error', event_id: eventId, message: 'Missing prompt' }));
        return;
      }

      // Reset callback result for new task
      _callbackResult = null;
      console.log(`[${new Date().toISOString()}] WS task received: ${eventId} (prompt: ${prompt.length} chars)`);

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
        const result = await executeCLIStreaming(ws, eventId, prompt, { autoApprove, cwd: workDir });
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
      currentTask = null;

    } else if (msg.type === 'followup') {
      // Forward follow-up message to an existing session via --resume.
      // Both Gemini and Claude CLIs support --resume <session_id>.
      const sessionId = msg.session_id || '';
      const followupMsg = msg.message || '';
      const eventId = msg.event_id || 'unknown';
      console.log(`[${new Date().toISOString()}] Followup for session ${sessionId} (event: ${eventId})`);

      if (sessionId) {
        try {
          const result = await executeCLIStreaming(ws, eventId, followupMsg, {
            autoApprove: true,
            cwd: currentTask?.cwd || DEFAULT_WORK_DIR,
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
        currentTask = null;
      } else {
        wsSend(ws, { type: 'error', event_id: eventId, message: 'No session_id for followup' });
      }

    } else if (msg.type === 'cancel') {
      if (currentTask && currentTask.child) {
        console.log(`[${new Date().toISOString()}] Cancelling task: ${currentTask.eventId}`);
        const child = currentTask.child;
        child.kill('SIGTERM');
        const killTimer = setTimeout(() => {
          if (!child.killed) {
            console.log(`[${new Date().toISOString()}] SIGTERM timeout -- SIGKILL for ${currentTask?.eventId || 'unknown'}`);
            child.kill('SIGKILL');
          }
        }, 5000);
        child.on('exit', () => clearTimeout(killTimer));
        currentTask = null;
      }
    }
  });

  ws.on('close', () => {
    console.log(`[${new Date().toISOString()}] WebSocket client disconnected`);
    if (currentTask && currentTask.child) {
      // S5 probe: log whether the disconnecting client is the task owner
      console.log(`[${new Date().toISOString()}] Killing orphaned process for ${currentTask.eventId} (disconnect-triggered, task was active)`);
      const child = currentTask.child;
      child.kill('SIGTERM');
      const killTimer = setTimeout(() => {
        if (!child.killed) {
          console.log(`[${new Date().toISOString()}] SIGTERM timeout -- SIGKILL`);
          child.kill('SIGKILL');
        }
      }, 5000);
      child.on('exit', () => clearTimeout(killTimer));
      currentTask = null;
    }
  });

  ws.on('error', (err) => {
    console.error(`[${new Date().toISOString()}] WebSocket error:`, err.message);
  });
});

server.listen(PORT, '0.0.0.0', () => {
  console.log(`[${new Date().toISOString()}] Agent sidecar (${AGENT_CLI}) listening on port ${PORT}`);
  console.log(`[${new Date().toISOString()}] Endpoints: GET /health, POST /execute, WS /ws`);
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
