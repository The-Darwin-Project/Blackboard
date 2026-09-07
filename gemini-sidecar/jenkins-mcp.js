// gemini-sidecar/jenkins-mcp.js
// @ai-rules:
// 1. [Pattern]: MCP stdio server -- JSON-RPC 2.0 over stdin/stdout. Console.error for all logging (stdout reserved).
// 2. [Constraint]: No SDK. readline + https only. Zero npm deps -- replaces @kud/mcp-jenkins.
// 3. [Pattern]: jenkins_trigger_build fetches the source build's parameters (explicit build or
//    lastFailedBuild) and forwards them on retrigger via buildWithParameters -- a parameterless
//    retrigger of a parameterized job silently queues nothing (Jenkins returns 200 with no Location).
// 4. [Gotcha]: Auth is HTTP Basic (user:api-token) -- no CSRF crumb needed with API-token Basic auth.
// 5. [Constraint]: Exposes exactly 3 tools (role gating + call sites in server.js/ws-*.js depend on
//    these names): jenkins_trigger_build, jenkins_get_build_status, jenkins_get_recent_builds.
'use strict';

const readline = require('readline');
const https = require('https');

const JENKINS_URL = (process.env.MCP_JENKINS_URL || '').replace(/\/+$/, '');
const JENKINS_USER = process.env.MCP_JENKINS_USER || '';
const JENKINS_API_TOKEN = process.env.MCP_JENKINS_API_TOKEN || '';
const INSECURE_TLS = process.env.MCP_JENKINS_INSECURE_TLS === 'true';

const AUTH_HEADER = 'Basic ' + Buffer.from(`${JENKINS_USER}:${JENKINS_API_TOKEN}`).toString('base64');

const TOOLS = [
  {
    name: 'jenkins_trigger_build',
    description: 'Retrigger a Jenkins job. Fetches parameters from the given source build (or the last failed build) and forwards them on retrigger, so a parameterized job actually queues a build instead of silently no-oping.',
    inputSchema: {
      type: 'object',
      properties: {
        job: { type: 'string', description: 'Job name or path (e.g. "folder/job-name")' },
        build: { type: 'string', description: 'Source build number to copy parameters from (defaults to lastFailedBuild)' },
        parameters: { type: 'object', description: 'Explicit parameter overrides -- take precedence over fetched values' },
      },
      required: ['job'],
    },
  },
  {
    name: 'jenkins_get_build_status',
    description: 'Get the status of a specific Jenkins build (result, building, parameters, url).',
    inputSchema: {
      type: 'object',
      properties: {
        job: { type: 'string', description: 'Job name or path' },
        build: { type: 'string', description: 'Build number (default "lastBuild")' },
      },
      required: ['job'],
    },
  },
  {
    name: 'jenkins_get_recent_builds',
    description: 'List recent builds for a Jenkins job.',
    inputSchema: {
      type: 'object',
      properties: {
        job: { type: 'string', description: 'Job name or path' },
        limit: { type: 'number', description: 'Max number of builds to return (default 10)' },
      },
      required: ['job'],
    },
  },
];

function jobPath(job) {
  return String(job || '')
    .split('/')
    .filter(Boolean)
    .map((seg) => {
      if (seg === '.' || seg === '..') throw new Error(`Invalid job path segment: "${seg}"`);
      return `job/${encodeURIComponent(seg)}`;
    })
    .join('/');
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function request(method, urlStr, { body, isForm } = {}) {
  return new Promise((resolve, reject) => {
    const url = new URL(urlStr);
    const headers = { Authorization: AUTH_HEADER };
    let payload;
    if (body !== undefined) {
      payload = isForm ? body : JSON.stringify(body);
      headers['Content-Type'] = isForm ? 'application/x-www-form-urlencoded' : 'application/json';
      headers['Content-Length'] = Buffer.byteLength(payload);
    }
    const opts = {
      hostname: url.hostname,
      port: url.port || 443,
      path: url.pathname + url.search,
      method,
      headers,
      rejectUnauthorized: !INSECURE_TLS,
      timeout: 30000,
    };
    const req = https.request(opts, (res) => {
      let data = '';
      res.on('data', (c) => { data += c; });
      res.on('end', () => {
        let parsed;
        try { parsed = JSON.parse(data); } catch { parsed = data; }
        resolve({ statusCode: res.statusCode, headers: res.headers, body: parsed });
      });
    });
    req.on('error', reject);
    req.on('timeout', function () { this.destroy(); reject(new Error('timeout')); });
    if (payload !== undefined) req.write(payload);
    req.end();
  });
}

async function httpsGetJson(urlStr, retries = 2) {
  let lastErr;
  for (let attempt = 0; attempt <= retries; attempt++) {
    let res;
    try {
      res = await request('GET', urlStr);
    } catch (err) {
      lastErr = err;
      if (attempt < retries) { await sleep(300 * (attempt + 1)); continue; }
      throw err;
    }
    if (res.statusCode >= 200 && res.statusCode < 300) return res.body;
    lastErr = new Error(`Jenkins returned HTTP ${res.statusCode} for ${urlStr}`);
    // Only retry transient server-side failures; a 4xx (e.g. 404) won't change on retry.
    if (res.statusCode >= 500 && attempt < retries) { await sleep(300 * (attempt + 1)); continue; }
    throw lastErr;
  }
  throw lastErr;
}

async function fetchBuildParameters(job, build) {
  const url = `${JENKINS_URL}/${jobPath(job)}/${encodeURIComponent(build)}/api/json?tree=number,result,actions[parameters[name,value]]`;
  const data = await httpsGetJson(url);
  const params = {};
  const actions = (data && data.actions) || [];
  for (const action of actions) {
    for (const p of (action && action.parameters) || []) {
      if (p && p.name !== undefined) params[p.name] = String(p.value);
    }
  }
  return params;
}

async function jenkinsTriggerBuild(args) {
  const { job } = args;
  const sourceBuild = args.build || 'lastFailedBuild';

  let fetched = {};
  try {
    fetched = await fetchBuildParameters(job, sourceBuild);
  } catch (err) {
    console.error(`[DarwinJenkins] Failed to fetch parameters from ${job}#${sourceBuild}: ${err.message}`);
  }

  // Caller-supplied overrides win over fetched values.
  const merged = { ...fetched, ...(args.parameters || {}) };
  const hasParams = Object.keys(merged).length > 0;

  const base = `${JENKINS_URL}/${jobPath(job)}`;
  let res;
  if (hasParams) {
    const form = Object.entries(merged)
      .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
      .join('&');
    res = await request('POST', `${base}/buildWithParameters`, { body: form, isForm: true });
  } else {
    res = await request('POST', `${base}/build`, { body: '', isForm: true });
  }

  // A 200 (dedup no-op) or a redirect to something other than a queue item
  // (e.g. an auth proxy bouncing to a login page) means nothing was actually
  // queued -- status code alone is not sufficient to declare success.
  const queueUrl = res.headers.location || null;
  const triggered = [200, 201, 302].includes(res.statusCode) && typeof queueUrl === 'string' && queueUrl.includes('/queue/');

  return {
    triggered,
    statusCode: res.statusCode,
    queueUrl,
    parametersUsed: merged,
    sourceBuild,
  };
}

async function jenkinsGetBuildStatus(args) {
  const build = args.build || 'lastBuild';
  const url = `${JENKINS_URL}/${jobPath(args.job)}/${encodeURIComponent(build)}/api/json?tree=number,result,building,url,actions[parameters[name,value]]`;
  return httpsGetJson(url);
}

async function jenkinsGetRecentBuilds(args) {
  const limit = args.limit || 10;
  const url = `${JENKINS_URL}/${jobPath(args.job)}/api/json?tree=builds[number,result,building,url]{0,${limit}}`;
  return httpsGetJson(url);
}

function respond(id, result) {
  process.stdout.write(JSON.stringify({ jsonrpc: '2.0', id, result }) + '\n');
}

function respondError(id, code, message) {
  process.stdout.write(JSON.stringify({ jsonrpc: '2.0', id, error: { code, message } }) + '\n');
}

async function handleToolCall(name, args) {
  if (name === 'jenkins_trigger_build') return await jenkinsTriggerBuild(args);
  if (name === 'jenkins_get_build_status') return await jenkinsGetBuildStatus(args);
  if (name === 'jenkins_get_recent_builds') return await jenkinsGetRecentBuilds(args);
  return { error: `Unknown tool: ${name}` };
}

// Guarded so this file can be require()'d by unit tests (to exercise
// jenkinsTriggerBuild's parameter-merge logic) without wiring up a live stdin
// listener. When invoked directly (`node jenkins-mcp.js`, as the Dockerfile does),
// require.main === module and the stdio JSON-RPC loop starts exactly as before.
if (require.main === module) {
  const rl = readline.createInterface({ input: process.stdin, terminal: false });
  rl.on('line', (line) => {
    handleLine(line).catch((err) => {
      console.error(`[DarwinJenkins] Unhandled error processing input line: ${err.message}`);
    });
  });

  async function handleLine(line) {
    let req;
    try { req = JSON.parse(line); } catch { return; }
    if (!req || typeof req !== 'object') return;
    const { id, method, params } = req;

    if (method === 'initialize') {
      respond(id, {
        protocolVersion: '2024-11-05',
        capabilities: { tools: {} },
        serverInfo: { name: 'DarwinJenkins', version: '1.0.0' },
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
        console.error(`[DarwinJenkins] Tool ${name} error: ${err.message}`);
        respond(id, { content: [{ type: 'text', text: JSON.stringify({ error: err.message }) }] });
      }
      return;
    }

    respondError(id, -32601, `Method not found: ${method}`);
  }

  console.error('[DarwinJenkins] MCP server started');
}

module.exports = { jenkinsTriggerBuild, jenkinsGetBuildStatus, jenkinsGetRecentBuilds, TOOLS };
