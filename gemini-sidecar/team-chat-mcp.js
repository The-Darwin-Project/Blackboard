// gemini-sidecar/team-chat-mcp.js
// @ai-rules:
// 1. [Pattern]: MCP stdio server -- JSON-RPC 2.0 over stdin/stdout. Console.error for all logging (stdout reserved).
// 2. [Constraint]: No SDK. readline + process.stdout.write + http.request only. Zero npm deps.
// 3. [Pattern]: Role-filtered tools via AGENT_ROLE env. dev/qe get all 6, architect/sysadmin get 3.
// 4. [Gotcha]: team_huddle blocks the stdio loop for up to 600s. MCP is request-response so this is safe.
// 5. [Pattern]: SIDECAR_PORT for own HTTP, PEER_PORT for sending to teammate. team_read_teammate_notes reads from SIDECAR_PORT (own inbox).
'use strict';

const readline = require('readline');
const http = require('http');

const ROLE = process.env.AGENT_ROLE || '';
const SIDECAR_PORT = parseInt(process.env.SIDECAR_PORT) || 9090;
const PEER_PORT = parseInt(process.env.PEER_PORT) || 0;
const IS_TEAM = ROLE === 'developer' || ROLE === 'qe';

const ALL_TOOLS = [
  { name: 'team_send_message', description: 'Send a progress update to the Brain (shown in event chat, does NOT overwrite deliverable)', inputSchema: { type: 'object', properties: { message: { type: 'string', description: 'Status update text' } }, required: ['message'] } },
  { name: 'team_send_results', description: 'Deliver your final report/findings to the Brain (overwrites previous deliverable)', inputSchema: { type: 'object', properties: { content: { type: 'string', description: 'Final report or findings' } }, required: ['content'] } },
  { name: 'team_check_messages', description: 'Check your inbox for pending messages from Manager or Brain. Returns and clears the queue.', inputSchema: { type: 'object', properties: {} } },
  { name: 'team_huddle', description: 'Send a message to your Manager and BLOCK until the Manager replies (up to 10 min). Use for status reports and questions in implement mode.', inputSchema: { type: 'object', properties: { message: { type: 'string', description: 'Question or status for Manager' } }, required: ['message'] }, teamOnly: true },
  { name: 'team_send_to_teammate', description: 'Send a direct message to your dev/QE teammate via their sidecar. Message is stored in their teammate queue.', inputSchema: { type: 'object', properties: { message: { type: 'string', description: 'Message for teammate' } }, required: ['message'] }, teamOnly: true },
  { name: 'team_read_teammate_notes', description: "Read and clear messages your teammate sent you. Drains the teammate's outbound queue for you.", inputSchema: { type: 'object', properties: {} }, teamOnly: true },
];

function getTools() {
  return ALL_TOOLS.filter(t => !t.teamOnly || IS_TEAM).map(({ teamOnly, ...t }) => t);
}

function httpPost(port, path, body, timeoutMs = 10000) {
  return new Promise((resolve, reject) => {
    const data = JSON.stringify(body);
    const req = http.request({ hostname: '127.0.0.1', port, path, method: 'POST', headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(data) }, timeout: timeoutMs }, (res) => {
      let chunks = '';
      res.on('data', c => chunks += c);
      res.on('end', () => {
        try { resolve({ status: res.statusCode, body: JSON.parse(chunks) }); }
        catch { resolve({ status: res.statusCode, body: chunks }); }
      });
    });
    req.on('error', e => reject(e));
    req.on('timeout', () => { req.destroy(); reject(new Error('HTTP request timeout')); });
    req.write(data);
    req.end();
  });
}

function httpGet(port, path) {
  return new Promise((resolve, reject) => {
    const req = http.request({ hostname: '127.0.0.1', port, path, method: 'GET', timeout: 5000 }, (res) => {
      let chunks = '';
      res.on('data', c => chunks += c);
      res.on('end', () => {
        try { resolve(JSON.parse(chunks)); }
        catch { resolve(chunks); }
      });
    });
    req.on('error', e => reject(e));
    req.on('timeout', () => { req.destroy(); reject(new Error('HTTP request timeout')); });
    req.end();
  });
}

async function handleToolCall(name, args) {
  console.error(`[TeamChat] ${name}(${JSON.stringify(args).slice(0, 80)})`);
  try {
    if (name === 'team_send_message') {
      const r = await httpPost(SIDECAR_PORT, '/callback', { type: 'message', content: args.message || '' });
      return r.status === 200 ? { sent: true } : { error: `HTTP ${r.status}` };
    }
    if (name === 'team_send_results') {
      const r = await httpPost(SIDECAR_PORT, '/callback', { type: 'result', content: args.content || '' });
      return r.status === 200 ? { sent: true } : { error: `HTTP ${r.status}` };
    }
    if (name === 'team_check_messages') {
      const msgs = await httpGet(SIDECAR_PORT, '/messages');
      return { messages: Array.isArray(msgs) ? msgs : [] };
    }
    if (name === 'team_huddle') {
      const r = await httpPost(SIDECAR_PORT, '/callback', { type: 'huddle_message', content: args.message || '' }, 610000);
      if (r.status === 200 && r.body?.reply !== undefined) return { reply: r.body.reply };
      return { error: r.body?.error || `HTTP ${r.status}` };
    }
    if (name === 'team_send_to_teammate') {
      if (!PEER_PORT) return { error: 'No peer sidecar configured (PEER_PORT not set)' };
      const r = await httpPost(PEER_PORT, '/callback', { type: 'teammate_forward', from: ROLE, content: args.message || '' });
      return r.status === 200 ? { sent: true } : { error: `HTTP ${r.status}` };
    }
    if (name === 'team_read_teammate_notes') {
      const notes = await httpGet(SIDECAR_PORT, '/teammate-notes');
      return { notes: Array.isArray(notes) ? notes : [] };
    }
    return { error: `Unknown tool: ${name}` };
  } catch (e) {
    return { error: e.message };
  }
}

function send(obj) {
  process.stdout.write(JSON.stringify(obj) + '\n');
}

const rl = readline.createInterface({ input: process.stdin, terminal: false });

rl.on('line', async (line) => {
  let req;
  try { req = JSON.parse(line); } catch (e) { console.error(`[TeamChat] Malformed JSON-RPC input: ${e.message}`); return; }
  const id = req.id;

  if (req.method === 'initialize') {
    send({ jsonrpc: '2.0', id, result: { protocolVersion: '2024-11-05', capabilities: { tools: {} }, serverInfo: { name: 'TeamChat', version: '1.0.0' } } });
  } else if (req.method === 'tools/list') {
    send({ jsonrpc: '2.0', id, result: { tools: getTools() } });
  } else if (req.method === 'tools/call') {
    const { name, arguments: args } = req.params || {};
    const result = await handleToolCall(name, args || {});
    send({ jsonrpc: '2.0', id, result: { content: [{ type: 'text', text: JSON.stringify(result) }] } });
  } else if (req.method === 'notifications/initialized') {
    // Client acknowledgment -- no response needed
  } else {
    send({ jsonrpc: '2.0', id, error: { code: -32601, message: `Method not found: ${req.method}` } });
  }
});

rl.on('close', () => process.exit(0));
console.error(`[TeamChat] MCP server started (role=${ROLE}, port=${SIDECAR_PORT}, peer=${PEER_PORT || 'none'})`);
