// gemini-sidecar/server.js
// HTTP wrapper for Gemini CLI with GitHub App authentication
// Exposes POST /execute endpoint for the brain container
// Handles dynamic repo cloning with fresh tokens per execution

const http = require('http');
const fs = require('fs');
const { spawn, execSync } = require('child_process');
const jwt = require('jsonwebtoken');

const PORT = process.env.PORT || 9090;
const TIMEOUT_MS = parseInt(process.env.TIMEOUT_MS) || 300000; // 5 minutes
const DEFAULT_WORK_DIR = '/data/gitops';

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
 * Gemini will handle clone/pull/push itself
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

    // Configure git user globally (for any repo Gemini clones)
    execSync('git config --global user.name "Darwin SysAdmin"', { encoding: 'utf8' });
    execSync('git config --global user.email "darwin-sysadmin@darwin-project.io"', { encoding: 'utf8' });
    
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
 * Execute gemini CLI with given prompt and options
 */
async function executeGemini(prompt, options = {}) {
  return new Promise((resolve, reject) => {
    // Using -p/--prompt triggers non-interactive (headless) mode
    const args = [];
    
    // Add auto-approve (yolo) flag if requested
    if (options.autoApprove) {
      args.push('--yolo');
    }
    
    // Add the prompt (this makes it non-interactive)
    args.push('-p', prompt);
    
    console.log(`[${new Date().toISOString()}] Executing: gemini ${args[0]} ${args.length > 2 ? '...' : ''} (prompt length: ${prompt.length})`);
    
    const child = spawn('gemini', args, {
      env: {
        ...process.env,
        GOOGLE_GENAI_USE_VERTEXAI: 'true',
      },
      cwd: options.cwd || DEFAULT_WORK_DIR,
      timeout: TIMEOUT_MS,
    });
    
    let stdout = '';
    let stderr = '';
    
    child.stdout.on('data', (data) => {
      stdout += data.toString();
    });
    
    child.stderr.on('data', (data) => {
      stderr += data.toString();
    });
    
    child.on('close', (code) => {
      console.log(`[${new Date().toISOString()}] Gemini exited with code ${code}`);
      console.log(`[${new Date().toISOString()}] stdout (${stdout.length} chars): ${stdout.slice(0, 500)}${stdout.length > 500 ? '...' : ''}`);
      if (stderr) {
        console.log(`[${new Date().toISOString()}] stderr: ${stderr.slice(0, 500)}${stderr.length > 500 ? '...' : ''}`);
      }
      
      if (code === 0) {
        try {
          const result = JSON.parse(stdout);
          resolve({ status: 'success', exitCode: code, output: result });
        } catch (e) {
          resolve({ status: 'success', exitCode: code, output: stdout, raw: true });
        }
      } else {
        resolve({ 
          status: 'failed', 
          exitCode: code, 
          stderr: stderr,
          stdout: stdout 
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
      service: 'gemini-sidecar',
      hasGitHubCredentials: hasGitHubCredentials(),
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
      // Gemini will handle clone/pull/push itself
      if (hasGitHubCredentials()) {
        try {
          const token = await generateInstallationToken();
          setupGitCredentials(token, workDir);
        } catch (err) {
          console.error(`[${new Date().toISOString()}] Git credential setup failed:`, err.message);
          // Continue anyway - Gemini might not need git for this operation
          console.log(`[${new Date().toISOString()}] Continuing without git credentials`);
        }
      }
      
      // Execute gemini CLI
      const result = await executeGemini(body.prompt, {
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
  
  // Investigate endpoint - Analyze pod issues using kubectl
  if (url.pathname === '/investigate' && req.method === 'POST') {
    try {
      const body = await parseBody(req);
      
      const { service, namespace = 'darwin', anomalyType } = body;
      
      if (!service || !anomalyType) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Missing required fields: service, anomalyType' }));
        return;
      }
      
      // Build investigation prompt for Gemini
      const prompt = buildInvestigationPrompt(service, namespace, anomalyType);
      
      console.log(`[${new Date().toISOString()}] Investigating ${service} (${anomalyType}) in ${namespace}`);
      
      // Execute gemini with investigation prompt
      const result = await executeGemini(prompt, { autoApprove: true });
      
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(result));
      
    } catch (err) {
      console.error(`[${new Date().toISOString()}] Investigation error:`, err.message);
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

/**
 * Build investigation prompt for Gemini to analyze pod issues
 */
function buildInvestigationPrompt(service, namespace, anomalyType) {
  return `You are a Kubernetes operations expert investigating a ${anomalyType.replace('_', ' ')} issue for service "${service}" in namespace "${namespace}".

=== INVESTIGATION STEPS ===

1. First, get recent events for the service:
   kubectl get events -n ${namespace} --field-selector involvedObject.name=${service} --sort-by='.lastTimestamp' | tail -20

2. If pods exist, get their status:
   kubectl get pods -n ${namespace} -l app=${service}

3. For each pod showing issues (CrashLoopBackOff, OOMKilled, Error), get logs:
   kubectl logs -n ${namespace} <pod-name> --tail=50
   
   If previous container exists:
   kubectl logs -n ${namespace} <pod-name> --previous --tail=50

4. Describe the problematic pod for more context:
   kubectl describe pod -n ${namespace} <pod-name>

=== ANALYSIS REQUIRED ===

Based on the above information, provide:
1. **Root Cause**: What is causing the ${anomalyType.replace('_', ' ')}?
2. **Evidence**: Specific log lines or events that support your conclusion
3. **Recommendation**: What action should be taken (scale, rollback, reconfig, etc.)

Be concise and actionable. Focus on the most likely cause based on the evidence.`;
}

// Create and start server
const server = http.createServer(handleRequest);

server.listen(PORT, '0.0.0.0', () => {
  console.log(`[${new Date().toISOString()}] Gemini sidecar listening on port ${PORT}`);
  console.log(`[${new Date().toISOString()}] Endpoints: GET /health, POST /execute, POST /investigate`);
  console.log(`[${new Date().toISOString()}] GitHub App credentials: ${hasGitHubCredentials() ? 'available' : 'NOT FOUND'}`);
});

// Graceful shutdown
process.on('SIGTERM', () => {
  console.log(`[${new Date().toISOString()}] Received SIGTERM, shutting down...`);
  server.close(() => process.exit(0));
});
