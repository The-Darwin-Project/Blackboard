// gemini-sidecar/server.js
// HTTP wrapper for Gemini CLI - runs as sidecar container
// Exposes POST /execute endpoint for the brain container

const http = require('http');
const { spawn } = require('child_process');

const PORT = process.env.PORT || 9090;
const TIMEOUT_MS = parseInt(process.env.TIMEOUT_MS) || 300000; // 5 minutes

/**
 * Execute gemini CLI with given prompt and options
 */
async function executeGemini(prompt, options = {}) {
  return new Promise((resolve, reject) => {
    // Using -p/--prompt triggers non-interactive (headless) mode
    // No separate --non-interactive flag exists
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
      cwd: options.cwd || process.cwd(),
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
          // Try to parse JSON output
          const result = JSON.parse(stdout);
          resolve({ status: 'success', exitCode: code, output: result });
        } catch (e) {
          // Return raw output if not valid JSON
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
    res.end(JSON.stringify({ status: 'healthy', service: 'gemini-sidecar' }));
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
      
      const result = await executeGemini(body.prompt, {
        autoApprove: body.autoApprove || false,
        cwd: body.cwd || '/data/gitops',
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

server.listen(PORT, '0.0.0.0', () => {
  console.log(`[${new Date().toISOString()}] Gemini sidecar listening on port ${PORT}`);
  console.log(`[${new Date().toISOString()}] Endpoints: GET /health, POST /execute`);
});

// Graceful shutdown
process.on('SIGTERM', () => {
  console.log(`[${new Date().toISOString()}] Received SIGTERM, shutting down...`);
  server.close(() => process.exit(0));
});
