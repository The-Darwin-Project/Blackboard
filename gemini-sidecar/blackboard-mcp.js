// gemini-sidecar/blackboard-mcp.js
// @ai-rules:
// 1. [Pattern]: MCP stdio server -- JSON-RPC 2.0 over stdin/stdout. Console.error for all logging (stdout reserved).
// 2. [Constraint]: No SDK. readline + process.stdout.write + http.request only. Zero npm deps.
// 3. [Pattern]: bb_catch_up uses /proxy/turns (Brain round-trip) on first call, /blackboard/turns (local cache) after.
// 4. [Pattern]: Shared hookHighwater with PostToolUse hook via /blackboard/status endpoint.
'use strict';

const readline = require('readline');
const http = require('http');

const SIDECAR_PORT = parseInt(process.env.SIDECAR_PORT) || 9090;
let _highwater = 0;
let _coldStartDone = false;

const TOOLS = [
  {
    name: 'bb_catch_up',
    description: 'Get conversation turns you missed since your last involvement in this event. First call returns the full gap (role-based); subsequent calls return only new turns from the local cache. Call this FIRST when starting a task.',
    inputSchema: { type: 'object', properties: {} },
  },
  {
    name: 'bb_get_event_status',
    description: 'Get the current event status and turn count without fetching full turns.',
    inputSchema: { type: 'object', properties: {} },
  },
  {
    name: 'bb_get_active_events',
    description: 'List all active events in the system. Use to see if related events are being worked on.',
    inputSchema: { type: 'object', properties: {} },
  },
  {
    name: 'bb_update_plan_step',
    description: 'Mark a plan step as in_progress, completed, or blocked. Call this when you start or finish a step from the plan on the blackboard. The update is visible to the Brain, other agents, and the dashboard in real time.',
    inputSchema: {
      type: 'object',
      properties: {
        step_id: { type: 'string', description: 'Step ID from the plan (e.g., "1", "2")' },
        status: { type: 'string', enum: ['in_progress', 'completed', 'blocked'], description: 'New status for this step' },
        notes: { type: 'string', description: 'Optional: what was done or why blocked' },
      },
      required: ['step_id', 'status'],
    },
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

function httpPost(port, path, body) {
  return new Promise((resolve, reject) => {
    const data = JSON.stringify(body);
    const req = http.request({ hostname: '127.0.0.1', port, path, method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(data) },
      timeout: 5000 }, (res) => {
      let chunks = '';
      res.on('data', c => chunks += c);
      res.on('end', () => { try { resolve(JSON.parse(chunks)); } catch { resolve(chunks); } });
    });
    req.on('error', reject);
    req.on('timeout', () => { req.destroy(); reject(new Error('timeout')); });
    req.write(data);
    req.end();
  });
}

function syncHighwater() {
  httpPost(SIDECAR_PORT, '/blackboard/sync-highwater', { highwater: _highwater }).catch(() => {});
}

function respond(id, result) {
  process.stdout.write(JSON.stringify({ jsonrpc: '2.0', id, result }) + '\n');
}

function respondError(id, code, message) {
  process.stdout.write(JSON.stringify({ jsonrpc: '2.0', id, error: { code, message } }) + '\n');
}

async function handleToolCall(name, args) {
  if (name === 'bb_catch_up') {
    if (!_coldStartDone) {
      const data = await httpGet(SIDECAR_PORT, '/proxy/turns');
      _coldStartDone = true;
      const maxTurn = (data.turns || []).reduce((m, t) => Math.max(m, t.turn || 0), 0);
      if (maxTurn > _highwater) _highwater = maxTurn;
      syncHighwater();
      return data;
    }
    const data = await httpGet(SIDECAR_PORT, `/blackboard/turns?since=${_highwater}`);
    const maxTurn = (data.turns || []).reduce((m, t) => Math.max(m, t.turn || 0), _highwater);
    if (maxTurn > _highwater) _highwater = maxTurn;
    syncHighwater();
    return data;
  }
  if (name === 'bb_get_event_status') {
    return await httpGet(SIDECAR_PORT, '/blackboard/status');
  }
  if (name === 'bb_get_active_events') {
    return await httpGet(SIDECAR_PORT, '/proxy/active-events');
  }
  if (name === 'bb_update_plan_step') {
    return await httpPost(SIDECAR_PORT, '/proxy/plan-step', {
      step_id: args.step_id || '',
      status: args.status || 'completed',
      notes: args.notes || '',
    });
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
      serverInfo: { name: 'DarwinBlackboard', version: '1.0.0' },
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
      console.error(`[DarwinBlackboard] Tool ${name} error: ${err.message}`);
      respond(id, { content: [{ type: 'text', text: JSON.stringify({ error: err.message }) }] });
    }
    return;
  }

  respondError(id, -32601, `Method not found: ${method}`);
});

console.error('[DarwinBlackboard] MCP server started');
