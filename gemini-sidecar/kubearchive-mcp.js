// gemini-sidecar/kubearchive-mcp.js
// @ai-rules:
// 1. [Pattern]: MCP stdio server -- JSON-RPC 2.0 over stdin/stdout. Console.error for all logging (stdout reserved).
// 2. [Constraint]: No SDK. readline + process.stdout.write + https only. Zero npm deps.
// 3. [Pattern]: All tools call KubeArchive REST API directly (K8s-style paths, Bearer token auth).
// 4. [Gotcha]: /log endpoints return plain text, not JSON. httpsGet uses try-catch JSON.parse with raw string fallback.
// 5. [Constraint]: Read-only. No create/update/delete operations.
'use strict';

const readline = require('readline');
const https = require('https');

const KUBEARCHIVE_URL = process.env.KUBEARCHIVE_URL || '';
const KUBEARCHIVE_TOKEN = process.env.KUBEARCHIVE_TOKEN || '';

const TOOLS = [
  {
    name: 'ka_list_pipelineruns',
    description: 'List archived PipelineRuns in a namespace. Use when live cluster data is pruned (Konflux retains only 3 latest). Returns component, application, pipeline type, status, git-url.',
    inputSchema: {
      type: 'object',
      properties: {
        namespace: { type: 'string', description: 'Tenant namespace (e.g., v4-22-openshift-virtualization-tenant)' },
        limit: { type: 'number', description: 'Max results (default 10)' },
      },
      required: ['namespace'],
    },
  },
  {
    name: 'ka_get_pipelinerun',
    description: 'Get a specific archived PipelineRun by name. Returns params (git-url, revision, output-image), childReferences (TaskRun names), results (IMAGE_URL, IMAGE_DIGEST), and conditions.',
    inputSchema: {
      type: 'object',
      properties: {
        namespace: { type: 'string', description: 'Tenant namespace' },
        name: { type: 'string', description: 'PipelineRun name' },
      },
      required: ['namespace', 'name'],
    },
  },
  {
    name: 'ka_list_taskruns',
    description: 'List archived TaskRuns in a namespace. Returns step exit codes, pipelineRun reference, and podName.',
    inputSchema: {
      type: 'object',
      properties: {
        namespace: { type: 'string', description: 'Tenant namespace' },
        limit: { type: 'number', description: 'Max results (default 10)' },
      },
      required: ['namespace'],
    },
  },
  {
    name: 'ka_get_taskrun',
    description: 'Get a specific archived TaskRun by name. Returns steps (exitCode, reason), podName, and taskSpec (inline scripts).',
    inputSchema: {
      type: 'object',
      properties: {
        namespace: { type: 'string', description: 'Tenant namespace' },
        name: { type: 'string', description: 'TaskRun name' },
      },
      required: ['namespace', 'name'],
    },
  },
  {
    name: 'ka_get_log',
    description: 'Get archived pod step log. This is the key tool for diagnosing pruned pipeline failures -- returns the full execution log with phases, actions, exit codes, and failure messages. Get the podName from ka_get_taskrun status.podName, and use "step-{stepName}" as the container.',
    inputSchema: {
      type: 'object',
      properties: {
        namespace: { type: 'string', description: 'Tenant namespace' },
        pod: { type: 'string', description: 'Pod name (from TaskRun status.podName)' },
        container: { type: 'string', description: 'Container name (e.g., "step-update-bundle")' },
      },
      required: ['namespace', 'pod', 'container'],
    },
  },
];

function enc(s) { return encodeURIComponent(s || ''); }

function httpsGet(urlStr) {
  return new Promise((resolve, reject) => {
    const url = new URL(urlStr);
    const opts = {
      hostname: url.hostname, port: url.port || 443,
      path: url.pathname + url.search,
      headers: { 'Authorization': `Bearer ${KUBEARCHIVE_TOKEN}` },
      rejectUnauthorized: false,
      timeout: 30000,
    };
    https.get(opts, (res) => {
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
  const ns = enc(args.namespace);
  const limit = args.limit || 10;
  if (name === 'ka_list_pipelineruns')
    return await httpsGet(`${KUBEARCHIVE_URL}/apis/tekton.dev/v1/namespaces/${ns}/pipelineruns?limit=${limit}`);
  if (name === 'ka_get_pipelinerun')
    return await httpsGet(`${KUBEARCHIVE_URL}/apis/tekton.dev/v1/namespaces/${ns}/pipelineruns/${enc(args.name)}`);
  if (name === 'ka_list_taskruns')
    return await httpsGet(`${KUBEARCHIVE_URL}/apis/tekton.dev/v1/namespaces/${ns}/taskruns?limit=${limit}`);
  if (name === 'ka_get_taskrun')
    return await httpsGet(`${KUBEARCHIVE_URL}/apis/tekton.dev/v1/namespaces/${ns}/taskruns/${enc(args.name)}`);
  if (name === 'ka_get_log')
    return await httpsGet(`${KUBEARCHIVE_URL}/api/v1/namespaces/${ns}/pods/${enc(args.pod)}/log?container=${enc(args.container)}`);
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
      serverInfo: { name: 'DarwinKubeArchive', version: '1.0.0' },
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
      const text = typeof result === 'string' ? result : JSON.stringify(result, null, 2);
      respond(id, { content: [{ type: 'text', text }] });
    } catch (err) {
      console.error(`[DarwinKubeArchive] Tool ${name} error: ${err.message}`);
      respond(id, { content: [{ type: 'text', text: JSON.stringify({ error: err.message }) }] });
    }
    return;
  }

  respondError(id, -32601, `Method not found: ${method}`);
});

console.error('[DarwinKubeArchive] MCP server started');
