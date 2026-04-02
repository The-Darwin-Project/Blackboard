// gemini-sidecar/journal-mcp.js
// @ai-rules:
// 1. [Pattern]: MCP stdio server -- JSON-RPC 2.0 over stdin/stdout. Console.error for all logging (stdout reserved).
// 2. [Constraint]: No SDK. readline + process.stdout.write + http.request only. Zero npm deps.
// 3. [Pattern]: All tools proxy to Brain via sidecar /proxy/* endpoints. No local cache — journal is read-through.
'use strict';

const readline = require('readline');
const http = require('http');

const SIDECAR_PORT = parseInt(process.env.SIDECAR_PORT) || 9090;

const TOOLS = [
  {
    name: 'svc_get_journal',
    description: 'Get the ops journal for a specific service. Returns recent operational actions, deployments, and status changes.',
    inputSchema: { type: 'object', properties: { service_name: { type: 'string', description: 'Service name to look up' } }, required: ['service_name'] },
  },
  {
    name: 'svc_get_journal_all',
    description: 'Get recent ops journal entries across all services. Use for cross-service timing and pattern analysis.',
    inputSchema: { type: 'object', properties: {} },
  },
  {
    name: 'svc_get_service',
    description: 'Get service metadata: version, GitOps repo, replicas, CPU/memory/error metrics.',
    inputSchema: { type: 'object', properties: { service_name: { type: 'string', description: 'Service name to look up' } }, required: ['service_name'] },
  },
  {
    name: 'svc_get_topology',
    description: 'Get the system architecture diagram showing service dependencies (mermaid format).',
    inputSchema: { type: 'object', properties: {} },
  },
];

function httpGet(port, path) {
  return new Promise((resolve, reject) => {
    http.get(`http://127.0.0.1:${port}${path}`, { timeout: 10000 }, (res) => {
      let data = '';
      res.on('data', c => data += c);
      res.on('end', () => {
        try { resolve(JSON.parse(data)); }
        catch { resolve(data); }
      });
    }).on('error', reject).on('timeout', function() { this.destroy(); reject(new Error('timeout')); });
  });
}

function respond(id, result) {
  process.stdout.write(JSON.stringify({ jsonrpc: '2.0', id, result }) + '\n');
}

function respondError(id, code, message) {
  process.stdout.write(JSON.stringify({ jsonrpc: '2.0', id, error: { code, message } }) + '\n');
}

async function handleToolCall(name, args) {
  if (name === 'svc_get_journal') {
    return await httpGet(SIDECAR_PORT, `/proxy/journal/${encodeURIComponent(args.service_name)}`);
  }
  if (name === 'svc_get_journal_all') {
    return await httpGet(SIDECAR_PORT, '/proxy/journal');
  }
  if (name === 'svc_get_service') {
    return await httpGet(SIDECAR_PORT, `/proxy/service/${encodeURIComponent(args.service_name)}`);
  }
  if (name === 'svc_get_topology') {
    return await httpGet(SIDECAR_PORT, '/proxy/topology/mermaid');
  }
  return { error: `Unknown tool: ${name}` };
}

const rl = readline.createInterface({ input: process.stdin, terminal: false });
rl.on('line', async (line) => {
  let req;
  try { req = JSON.parse(line); } catch { return; }
  const { id, method, params } = req;

  if (method === 'initialize') {
    respond(id, {
      protocolVersion: '2024-11-05',
      capabilities: { tools: {} },
      serverInfo: { name: 'DarwinJournal', version: '1.0.0' },
    });
    return;
  }

  if (method === 'notifications/initialized') return;

  if (method === 'tools/list') {
    respond(id, { tools: TOOLS });
    return;
  }

  if (method === 'tools/call') {
    const { name, arguments: args } = params || {};
    try {
      const result = await handleToolCall(name, args || {});
      respond(id, { content: [{ type: 'text', text: JSON.stringify(result, null, 2) }] });
    } catch (err) {
      console.error(`[DarwinJournal] Tool ${name} error: ${err.message}`);
      respond(id, { content: [{ type: 'text', text: JSON.stringify({ error: err.message }) }] });
    }
    return;
  }

  respondError(id, -32601, `Method not found: ${method}`);
});

console.error('[DarwinJournal] MCP server started');
