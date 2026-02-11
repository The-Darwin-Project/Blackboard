// gemini-sidecar/server.js
// @ai-rules:
// 1. [Pattern]: executeCLI + executeCLIStreaming use fs.watch preemptive read for findings.md to avoid PVC flush race.
// 2. [Pattern]: readFindings() is fallback only -- watcher caches content on file creation; close handler uses cached value first.
// 3. [Constraint]: Watcher setup MUST happen AFTER prepareResultsDir() but BEFORE spawn() to avoid watching a non-existent dir.
// 4. [Gotcha]: fs.watch on Linux inotify fires 'rename' for file creation AND deletion -- existsSync guard prevents reading deleted files.
// 5. [Pattern]: AGENT_CLI env var routes spawn() to 'gemini' or 'claude' binary via buildCLICommand().
// HTTP wrapper for Gemini/Claude Code CLIs with GitHub App authentication
// Exposes POST /execute endpoint for the brain container
// Handles dynamic repo cloning with fresh tokens per execution

const http = require('http');
const fs = require('fs');
const { spawn, execSync } = require('child_process');
const jwt = require('jsonwebtoken');
const WebSocket = require('ws');

const PORT = process.env.PORT || 9090;
const TIMEOUT_MS = parseInt(process.env.TIMEOUT_MS) || 300000; // 5 minutes
const DEFAULT_WORK_DIR = '/data/gitops';

// CLI routing -- AGENT_CLI selects which binary to spawn (gemini or claude)
const AGENT_CLI = process.env.AGENT_CLI || 'gemini';
const AGENT_MODEL = process.env.AGENT_MODEL || process.env.GEMINI_MODEL || '';
// Agent role -- used to restrict tools (e.g., architect can't write code files)
const AGENT_ROLE = process.env.AGENT_ROLE || '';

/**
 * Parse a Claude stream-json line and extract displayable text.
 * Returns the text to display, or null if the line is not user-facing.
 *
 * Claude stream-json emits lines like:
 *   {"type":"content_block_delta","delta":{"type":"text_delta","text":"token"}}
 *   {"type":"assistant","message":{...,"content":[{"type":"text","text":"full"}]}}
 *   {"type":"result","result":"final text",...}
 */
function parseClaudeStreamLine(line) {
    try {
        const obj = JSON.parse(line);
        // content_block_delta -- incremental token
        if (obj.type === 'content_block_delta' && obj.delta?.text) {
            return obj.delta.text;
        }
        // assistant message -- summarized narration
        if (obj.type === 'assistant' && obj.message?.content) {
            const texts = obj.message.content
                .filter(c => c.type === 'text')
                .map(c => c.text);
            return texts.join('\n') || null;
        }
        // result -- final output
        if (obj.type === 'result' && obj.result) {
            return typeof obj.result === 'string' ? obj.result : JSON.stringify(obj.result);
        }
    } catch (e) {
        // Not JSON or unknown format -- return raw line for Gemini compatibility
        return line;
    }
    return null;
}

/**
 * Build CLI command based on AGENT_CLI env var.
 * Routes to 'gemini' or 'claude' binary with appropriate flags.
 */
function buildCLICommand(prompt, options = {}) {
    if (AGENT_CLI === 'claude') {
        const args = [];
        if (options.autoApprove) args.push('--dangerously-skip-permissions');
        args.push('--output-format', 'stream-json');  // Stream JSON events (tokens + tool calls)
        args.push('--verbose');
        // Architect: read-only tools only (no code modification)
        if (AGENT_ROLE === 'architect') {
            args.push('--tools', 'Read,Grep,Glob,Bash,Task');
            args.push('--disallowedTools', 'Edit,MultiEdit,Write');
        }
        args.push('-p', prompt);
        return { binary: 'claude', args };
    } else {
        const args = [];
        if (options.autoApprove) args.push('--yolo');
        // Architect: disable file modification tools (Gemini CLI uses --disallowedTools)
        if (AGENT_ROLE === 'architect') {
            args.push('--disallowedTools', 'EditFile,WriteFile,ReplaceInFile,CreateFile');
        }
        args.push('-p', prompt);
        return { binary: 'gemini', args };
    }
}

// GitHub App secret paths (mounted from K8s secret)
const SECRETS_PATH = '/secrets/github';
const APP_ID_PATH = `${SECRETS_PATH}/app-id`;
const INSTALL_ID_PATH = `${SECRETS_PATH}/installation-id`;
// Note: Private key filename may vary - we'll find it dynamically
const PRIVATE_KEY_PATTERN = /\.pem$/;

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
    
    // Store credentials using unique file per request (avoids stale state issues)
    const credFile = `/tmp/git-creds-${Date.now()}`;
    execSync(`git config --global credential.helper 'store --file=${credFile}'`, { encoding: 'utf8' });
    fs.writeFileSync(credFile, `https://x-access-token:${token}@github.com\n`, { mode: 0o600 });
    
    console.log(`[${new Date().toISOString()}] Git credentials configured`);
    
  } catch (err) {
    console.error(`[${new Date().toISOString()}] Git config error:`, err.message);
    throw new Error(`Failed to configure git: ${err.message}`);
  }
}

/**
 * Login to ArgoCD/Kargo CLIs in the background (non-blocking).
 * Spawns login processes that run concurrently with agent CLI execution.
 * The CLI sessions become available within ~2s; if the agent uses argocd/kargo
 * before login completes, the command fails gracefully (agent retries or
 * falls back to kubectl/oc).
 */
function setupCLILoginsBackground() {
  // ArgoCD login (background)
  const argoServer = process.env.ARGOCD_SERVER;
  const argoSecretPath = '/secrets/argocd/auth-token';
  if (argoServer && fs.existsSync(argoSecretPath)) {
    const password = fs.readFileSync(argoSecretPath, 'utf8').trim();
    const insecure = process.env.ARGOCD_INSECURE === 'true' ? '--insecure' : '';
    const child = spawn('argocd', ['login', argoServer, '--username', 'admin', '--password', password, insecure, '--grpc-web'].filter(Boolean),
      { stdio: 'pipe', timeout: 10000 });
    child.on('close', (code) => {
      if (code === 0) console.log(`[${new Date().toISOString()}] ArgoCD login successful (${argoServer})`);
      else console.log(`[${new Date().toISOString()}] ArgoCD login failed (exit ${code}), agents use kubectl/oc fallback`);
    });
    child.on('error', (err) => {
      console.log(`[${new Date().toISOString()}] ArgoCD login error: ${err.message}`);
    });
  }

  // Kargo login (background)
  const kargoServer = process.env.KARGO_SERVER;
  const kargoSecretPath = '/secrets/kargo/auth-token';
  if (kargoServer && fs.existsSync(kargoSecretPath)) {
    const password = fs.readFileSync(kargoSecretPath, 'utf8').trim();
    const insecure = process.env.KARGO_INSECURE === 'true' ? '--insecure-skip-tls-verify' : '';
    const child = spawn('kargo', ['login', `https://${kargoServer}`, '--admin', '--password', password, insecure].filter(Boolean),
      { stdio: 'pipe', timeout: 10000 });
    child.on('close', (code) => {
      if (code === 0) console.log(`[${new Date().toISOString()}] Kargo login successful (${kargoServer})`);
      else console.log(`[${new Date().toISOString()}] Kargo login failed (exit ${code}), agents use kubectl/oc fallback`);
    });
    child.on('error', (err) => {
      console.log(`[${new Date().toISOString()}] Kargo login error: ${err.message}`);
    });
  }
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
 * Read agent findings from the results folder.
 * Agents write their deliverable to ./results/findings.md.
 * Falls back to stdout tail if no file found (LLM non-compliance).
 *
 * @param {string} workDir - Agent working directory
 * @param {string} stdout - Full captured stdout (for fallback)
 * @returns {string} Extracted findings or stdout tail
 */
function readFindings(workDir, stdout) {
  const resultsDir = `${workDir}/results`;
  const findingsPath = `${resultsDir}/findings.md`;

  try {
    if (fs.existsSync(findingsPath)) {
      const content = fs.readFileSync(findingsPath, 'utf8').trim();
      // Clean up after reading
      fs.unlinkSync(findingsPath);
      console.log(`[${new Date().toISOString()}] Read findings from ${findingsPath} (${content.length} chars)`);
      if (content.length > 0) {
        return content;
      }
      // Empty file = treat as non-compliance, fall through to fallback
      console.log(`[${new Date().toISOString()}] Findings file was empty, falling back to stdout tail`);
    }
  } catch (err) {
    console.log(`[${new Date().toISOString()}] Could not read findings file: ${err.message}`);
  }

  // Fallback: tail extraction (last 3000 chars of stdout)
  console.log(`[${new Date().toISOString()}] No findings file, using stdout tail (${stdout.length} chars)`);
  if (stdout.length > 3000) {
    return '(truncated thinking...)\n' + stdout.slice(-3000);
  }
  return stdout;
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
    let cachedFindings = null;
    let watcher = null;
    try {
      watcher = fs.watch(resultsDir, (eventType, filename) => {
        if (filename === 'findings.md' && (eventType === 'rename' || eventType === 'change')) {
          try {
            if (fs.existsSync(findingsPath)) {
              cachedFindings = fs.readFileSync(findingsPath, 'utf8').trim();
              console.log(`[${new Date().toISOString()}] Preemptive read: findings.md (${cachedFindings.length} chars)`);
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
    let claudeTextAccum = '';  // Accumulate parsed text from Claude stream-json
    
    child.stdout.on('data', (data) => {
      const text = data.toString();
      stdout += text;
      // Parse Claude stream-json lines to extract readable text
      if (AGENT_CLI === 'claude') {
        for (const line of text.split('\n')) {
          if (!line.trim()) continue;
          const parsed = parseClaudeStreamLine(line);
          if (parsed) claudeTextAccum += parsed;
        }
      }
    });
    
    child.stderr.on('data', (data) => {
      stderr += data.toString();
    });
    
    child.on('close', (code) => {
      // Close the watcher
      if (watcher) { try { watcher.close(); } catch(e) {} }

      // For Claude stream-json, the readable output is in claudeTextAccum, not raw stdout
      const effectiveOutput = (AGENT_CLI === 'claude' && claudeTextAccum) ? claudeTextAccum : stdout;

      console.log(`[${new Date().toISOString()}] ${AGENT_CLI} exited with code ${code}`);
      console.log(`[${new Date().toISOString()}] stdout (${effectiveOutput.length} chars): ${effectiveOutput.slice(0, 500)}${effectiveOutput.length > 500 ? '...' : ''}`);
      if (stderr) {
        console.log(`[${new Date().toISOString()}] stderr: ${stderr.slice(0, 500)}${stderr.length > 500 ? '...' : ''}`);
      }
      
      if (code === 0) {
        try {
          const result = JSON.parse(effectiveOutput);
          resolve({ status: 'success', exitCode: code, output: result });
        } catch (e) {
          // Use cached findings from watcher, or fall back to readFindings()
          // Note: readFindings() already deletes the file internally
          const findings = cachedFindings || readFindings(options.cwd || DEFAULT_WORK_DIR, effectiveOutput);
          // Clean up only if watcher cached (readFindings already deleted otherwise)
          if (cachedFindings) {
            try { if (fs.existsSync(findingsPath)) fs.unlinkSync(findingsPath); } catch(err) {}
          }
          resolve({ status: 'success', exitCode: code, output: findings, raw: true });
        }
      } else {
        resolve({ 
          status: 'failed', 
          exitCode: code, 
          stderr: stderr,
          stdout: effectiveOutput 
        });
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
    const { binary, args } = buildCLICommand(prompt, { autoApprove: options.autoApprove });

    console.log(`[${new Date().toISOString()}] Streaming exec: ${AGENT_CLI} (prompt: ${prompt.length} chars)`);

    // Prepare results directory (clean stale files, ensure exists)
    prepareResultsDir(options.cwd || DEFAULT_WORK_DIR);

    // Watch for findings file (preemptive read to avoid race with PVC flush)
    const resultsDir = `${options.cwd || DEFAULT_WORK_DIR}/results`;
    const findingsPath = `${resultsDir}/findings.md`;
    let cachedFindings = null;
    let watcher = null;
    try {
      watcher = fs.watch(resultsDir, (eventType, filename) => {
        if (filename === 'findings.md' && (eventType === 'rename' || eventType === 'change')) {
          try {
            if (fs.existsSync(findingsPath)) {
              cachedFindings = fs.readFileSync(findingsPath, 'utf8').trim();
              console.log(`[${new Date().toISOString()}] Preemptive read: findings.md (${cachedFindings.length} chars)`);
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
    let claudeTextAccum = '';  // Accumulate parsed text from Claude stream-json

    // Stream stdout line-by-line as progress
    child.stdout.on('data', (data) => {
      const text = data.toString();
      stdout += text;
      lineBuffer += text;

      // Flush complete lines
      const lines = lineBuffer.split('\n');
      lineBuffer = lines.pop(); // Keep incomplete line in buffer
      for (const line of lines) {
        if (!line.trim()) continue;
        if (AGENT_CLI === 'claude') {
          // Parse Claude stream-json -- extract displayable text
          const parsed = parseClaudeStreamLine(line);
          if (parsed) {
            claudeTextAccum += parsed;
            console.log(`[${new Date().toISOString()}] [${eventId}] >> ${parsed.slice(0, 200)}`);
            wsSend(ws, { type: 'progress', event_id: eventId, message: parsed });
          }
        } else {
          // Gemini -- raw text lines
          console.log(`[${new Date().toISOString()}] [${eventId}] >> ${line.slice(0, 200)}`);
          wsSend(ws, { type: 'progress', event_id: eventId, message: line });
        }
      }
    });

    child.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    child.on('close', (code) => {
      // Close the watcher
      if (watcher) { try { watcher.close(); } catch(e) {} }

      // Flush remaining buffer (parse for Claude, raw for Gemini)
      if (lineBuffer.trim()) {
        if (AGENT_CLI === 'claude') {
          const parsed = parseClaudeStreamLine(lineBuffer);
          if (parsed) {
            claudeTextAccum += parsed;
            wsSend(ws, { type: 'progress', event_id: eventId, message: parsed });
          }
        } else {
          wsSend(ws, { type: 'progress', event_id: eventId, message: lineBuffer });
        }
      }

      // For Claude stream-json, the readable output is in claudeTextAccum, not raw stdout
      const effectiveOutput = (AGENT_CLI === 'claude' && claudeTextAccum) ? claudeTextAccum : stdout;

      console.log(`[${new Date().toISOString()}] ${AGENT_CLI} exited code ${code} (${effectiveOutput.length} chars)`);
      if (effectiveOutput.length > 0) {
        console.log(`[${new Date().toISOString()}] ${AGENT_CLI} stdout: ${effectiveOutput.slice(0, 1000)}${effectiveOutput.length > 1000 ? '...' : ''}`);
      } else {
        console.log(`[${new Date().toISOString()}] WARNING: ${AGENT_CLI} produced EMPTY stdout`);
      }
      if (stderr) {
        console.log(`[${new Date().toISOString()}] ${AGENT_CLI} stderr: ${stderr.slice(0, 500)}`);
      }

      if (code === 0) {
        try {
          const result = JSON.parse(effectiveOutput);
          resolve({ status: 'success', output: result });
        } catch (e) {
          // Use cached findings from watcher, or fall back to readFindings()
          // Note: readFindings() already deletes the file internally
          const findings = cachedFindings || readFindings(options.cwd || DEFAULT_WORK_DIR, effectiveOutput);
          // Clean up only if watcher cached (readFindings already deleted otherwise)
          if (cachedFindings) {
            try { if (fs.existsSync(findingsPath)) fs.unlinkSync(findingsPath); } catch(err) {}
          }
          resolve({ status: 'success', output: findings, raw: true });
        }
      } else {
        resolve({ status: 'failed', exitCode: code, stderr, stdout });
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
      hasArgocdCredentials: fs.existsSync('/secrets/argocd/auth-token'),
      hasKargoCredentials: fs.existsSync('/secrets/kargo/auth-token'),
    }));
    return;
  }
  
  // Execute endpoint
  if (url.pathname === '/execute' && req.method === 'POST') {
    try {
      const body = await parseBody(req);
      
      if (!body.prompt) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Missing required field: prompt' }));
        return;
      }
      
      const workDir = body.cwd || DEFAULT_WORK_DIR;
      
      // Setup git credentials if GitHub App is configured
      // Agent CLI will handle clone/pull/push itself
      if (hasGitHubCredentials()) {
        try {
          const token = await generateInstallationToken();
          setupGitCredentials(token, workDir);
        } catch (err) {
          console.error(`[${new Date().toISOString()}] Git credential setup failed:`, err.message);
          // Continue anyway - agent might not need git for this operation
          console.log(`[${new Date().toISOString()}] Continuing without git credentials`);
        }
      }

      // Login to ArgoCD/Kargo CLIs in background (non-blocking)
      setupCLILoginsBackground();
      
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

      console.log(`[${new Date().toISOString()}] WS task received: ${eventId} (prompt: ${prompt.length} chars)`);

      // Setup git credentials
      if (hasGitHubCredentials()) {
        try {
          const token = await generateInstallationToken();
          setupGitCredentials(token, workDir);
          wsSend(ws, { type: 'progress', event_id: eventId, message: 'Git credentials configured' });
        } catch (err) {
          wsSend(ws, { type: 'progress', event_id: eventId, message: `Git credentials failed: ${err.message}, continuing...` });
        }
      }

      // Login to ArgoCD/Kargo CLIs in background (non-blocking, runs concurrent with agent CLI)
      setupCLILoginsBackground();

      // Execute agent CLI with streaming progress
      try {
        const result = await executeCLIStreaming(ws, eventId, prompt, { autoApprove, cwd: workDir });
        wsSend(ws, {
          type: 'result',
          event_id: eventId,
          status: result.status,
          output: result.output || result.stdout || '',
        });
      } catch (err) {
        wsSend(ws, {
          type: 'error',
          event_id: eventId,
          message: err.message,
        });
      }
      currentTask = null;

    } else if (msg.type === 'cancel') {
      if (currentTask && currentTask.child) {
        console.log(`[${new Date().toISOString()}] Cancelling task: ${currentTask.eventId}`);
        currentTask.child.kill('SIGTERM');
        currentTask = null;
      }
    }
  });

  ws.on('close', () => {
    console.log(`[${new Date().toISOString()}] WebSocket client disconnected`);
    // Kill running process on disconnect
    if (currentTask && currentTask.child) {
      console.log(`[${new Date().toISOString()}] Killing orphaned process for ${currentTask.eventId}`);
      currentTask.child.kill('SIGTERM');
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
  console.log(`[${new Date().toISOString()}] ArgoCD credentials: ${fs.existsSync('/secrets/argocd/auth-token') ? 'available' : 'not configured'}`);
  console.log(`[${new Date().toISOString()}] Kargo credentials: ${fs.existsSync('/secrets/kargo/auth-token') ? 'available' : 'not configured'}`);
});

// Graceful shutdown
process.on('SIGTERM', () => {
  console.log(`[${new Date().toISOString()}] Received SIGTERM, shutting down...`);
  server.close(() => process.exit(0));
});
