// gemini-sidecar/tests/test_jenkins_mcp.js
// @ai-rules:
// 1. [Constraint]: Test-only file for Jenkins MCP credential discovery and registration.
// 2. [Pattern]: Uses node:test + node:assert with fs/env mocking before requiring credentials.js.
// 3. [Gotcha]: credentials.js destructures cli-setup exports at require time, so stub cli-setup before freshRequire().
// 4. [Contract]: Tests the planned public contract only: hasJenkinsCredentials(), setupJenkinsMCP(), and role-gated call-site wiring.

const { describe, it, beforeEach, afterEach } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const os = require('os');
const path = require('path');

const CREDENTIALS_PATH = path.resolve(__dirname, '..', 'credentials.js');
const CLI_SETUP_PATH = path.resolve(__dirname, '..', 'cli-setup.js');
const SERVER_PATH = path.resolve(__dirname, '..', 'server.js');
const WS_CLIENT_PATH = path.resolve(__dirname, '..', 'ws-client.js');
const WS_SERVER_PATH = path.resolve(__dirname, '..', 'ws-server.js');
const TEAM_CHAT_PATH = path.resolve(__dirname, '..', 'team-chat-mcp.js');

function freshRequire(modulePath) {
  const resolved = require.resolve(modulePath);
  delete require.cache[resolved];
  return require(resolved);
}

function clearModuleCache() {
  for (const modulePath of [CREDENTIALS_PATH, CLI_SETUP_PATH]) {
    const resolved = require.resolve(modulePath);
    delete require.cache[resolved];
  }
}

function mockFs(overrides) {
  const saved = {
    existsSync: fs.existsSync,
    readFileSync: fs.readFileSync,
  };

  fs.existsSync = (p) => {
    if (p in overrides.exists) return overrides.exists[p];
    return saved.existsSync(p);
  };

  fs.readFileSync = (p, ...args) => {
    if (overrides.readFileThrows && overrides.readFileThrows.includes(p)) {
      const err = new Error(`ENOENT: no such file or directory, open '${p}'`);
      err.code = 'ENOENT';
      throw err;
    }
    if (overrides.readFile && p in overrides.readFile) return overrides.readFile[p];
    return saved.readFileSync(p, ...args);
  };

  return () => {
    fs.existsSync = saved.existsSync;
    fs.readFileSync = saved.readFileSync;
  };
}

function withMockedCliSetup(stubs, fn) {
  const resolved = require.resolve(CLI_SETUP_PATH);
  const saved = require.cache[resolved];
  require.cache[resolved] = {
    id: resolved,
    filename: resolved,
    loaded: true,
    exports: stubs,
  };
  try {
    return fn();
  } finally {
    delete require.cache[resolved];
    if (saved) require.cache[resolved] = saved;
  }
}

const savedEnv = {};
function setEnv(key, value) {
  savedEnv[key] = process.env[key];
  if (value === undefined) {
    delete process.env[key];
  } else {
    process.env[key] = value;
  }
}

function restoreEnv() {
  for (const [key, value] of Object.entries(savedEnv)) {
    if (value === undefined) delete process.env[key];
    else process.env[key] = value;
  }
  Object.keys(savedEnv).forEach((key) => delete savedEnv[key]);
}

describe('Jenkins MCP credential helpers', () => {
  let restore;
  let tmpHome;

  beforeEach(() => {
    clearModuleCache();
    tmpHome = fs.mkdtempSync(path.join(os.tmpdir(), 'darwin-jenkins-mcp-'));
    setEnv('HOME', tmpHome);
    setEnv('JENKINS_URL', 'https://jenkins.example.test');
    setEnv('JENKINS_INSECURE_TLS', 'false');
    setEnv('NODE_TLS_REJECT_UNAUTHORIZED', undefined);
  });

  afterEach(() => {
    if (restore) restore();
    restoreEnv();
    clearModuleCache();
    fs.rmSync(tmpHome, { recursive: true, force: true });
    restore = null;
  });

  it('T-6: hasJenkinsCredentials returns true when secret files and URL exist', () => {
    restore = mockFs({
      exists: {
        '/secrets/jenkins/username': true,
        '/secrets/jenkins/api-token': true,
      },
    });

    const { hasJenkinsCredentials } = freshRequire(CREDENTIALS_PATH);
    assert.equal(hasJenkinsCredentials(), true);
  });

  it('T-7: hasJenkinsCredentials returns false when secret files are missing', () => {
    restore = mockFs({
      exists: {
        '/secrets/jenkins/username': false,
        '/secrets/jenkins/api-token': false,
      },
    });

    const { hasJenkinsCredentials } = freshRequire(CREDENTIALS_PATH);
    assert.equal(hasJenkinsCredentials(), false);
  });

  it('T-8: setupJenkinsMCP writes Jenkins MCP config and dual-registers Claude', async () => {
    let claudeRegistration = null;
    restore = mockFs({
      exists: {
        '/secrets/jenkins/username': true,
        '/secrets/jenkins/api-token': true,
      },
      readFile: {
        '/secrets/jenkins/username': 'darwin-user\n',
        '/secrets/jenkins/api-token': 'darwin-token\n',
      },
    });

    await withMockedCliSetup({
      resolveCommand: () => 'node',
      writeClaudeMcpServer: (name, config) => {
        claudeRegistration = { name, config };
      },
    }, async () => {
      const { setupJenkinsMCP } = freshRequire(CREDENTIALS_PATH);
      await setupJenkinsMCP();
    });

    const settingsPath = path.join(tmpHome, '.gemini', 'settings.json');
    const settings = JSON.parse(fs.readFileSync(settingsPath, 'utf8'));
    const config = settings.mcpServers.Jenkins;

    assert.equal(config.command, 'node');
    assert.deepEqual(config.args, ['/app/jenkins-mcp.js']);
    assert.equal(config.env.MCP_JENKINS_URL, 'https://jenkins.example.test');
    assert.equal(config.env.MCP_JENKINS_USER, 'darwin-user');
    assert.equal(config.env.MCP_JENKINS_API_TOKEN, 'darwin-token');
    assert.deepEqual(claudeRegistration, { name: 'Jenkins', config });
  });

  it('T-8b: setupJenkinsMCP scopes insecure TLS to the MCP child env only', async () => {
    restore = mockFs({
      exists: {
        '/secrets/jenkins/username': true,
        '/secrets/jenkins/api-token': true,
      },
      readFile: {
        '/secrets/jenkins/username': 'darwin-user\n',
        '/secrets/jenkins/api-token': 'darwin-token\n',
      },
    });
    setEnv('JENKINS_INSECURE_TLS', 'true');

    await withMockedCliSetup({
      resolveCommand: () => 'node',
      writeClaudeMcpServer: () => {},
    }, async () => {
      const { setupJenkinsMCP } = freshRequire(CREDENTIALS_PATH);
      await setupJenkinsMCP();
    });

    const settingsPath = path.join(tmpHome, '.gemini', 'settings.json');
    const settings = JSON.parse(fs.readFileSync(settingsPath, 'utf8'));
    assert.equal(
      settings.mcpServers.Jenkins.env.NODE_TLS_REJECT_UNAUTHORIZED,
      '0',
    );
    assert.equal(settings.mcpServers.Jenkins.env.MCP_JENKINS_INSECURE_TLS, 'true');
    assert.equal(process.env.NODE_TLS_REJECT_UNAUTHORIZED, undefined);
  });

  it('T-crash: setupJenkinsMCP does not throw on credential read failure (TOCTOU guard)', async () => {
    // existsSync returns true but files vanished (TOCTOU) — readFileSync throws ENOENT.
    // readFileThrows forces the failure explicitly rather than relying on the real
    // path being absent on disk: agent pods with real Jenkins credentials mounted at
    // this exact path would otherwise make readFileSync succeed and silently defeat
    // this test (observed in the Darwin QE sidecar sandbox, which mounts a real
    // /secrets/jenkins/* Secret for its own Jenkins MCP access).
    restore = mockFs({
      exists: {
        '/secrets/jenkins/username': true,
        '/secrets/jenkins/api-token': true,
      },
      readFileThrows: ['/secrets/jenkins/username', '/secrets/jenkins/api-token'],
    });

    await withMockedCliSetup({
      resolveCommand: () => 'node',
      writeClaudeMcpServer: () => {},
    }, async () => {
      const { setupJenkinsMCP } = freshRequire(CREDENTIALS_PATH);
      await assert.doesNotReject(setupJenkinsMCP());
    });

    const settingsPath = path.join(tmpHome, '.gemini', 'settings.json');
    assert.equal(fs.existsSync(settingsPath), false, 'settings.json must not be created on read failure');
  });
});

describe('jenkins-mcp.js parameter merge', () => {
  const JENKINS_MCP_PATH = path.resolve(__dirname, '..', 'jenkins-mcp.js');
  const https = require('https');

  function stubHttps({ getBody, getStatus = 200, postStatus = 201, postHeaders, capturePostBody, calls }) {
    const saved = https.request;
    const resolvedPostHeaders = postHeaders !== undefined
      ? postHeaders
      : { location: 'https://jenkins.example.test/queue/item/42/' };
    https.request = (opts, callback) => {
      if (calls) calls.push(opts);
      const req = {
        on() { return req; },
        write(chunk) { if (opts.method === 'POST' && capturePostBody) capturePostBody(chunk); },
        end() {
          const isPost = opts.method === 'POST';
          const res = {
            statusCode: isPost ? postStatus : getStatus,
            headers: isPost ? resolvedPostHeaders : {},
            on(event, handler) {
              if (event === 'data') handler(isPost ? '' : getBody);
              if (event === 'end') handler();
              return res;
            },
          };
          callback(res);
        },
      };
      return req;
    };
    return () => { https.request = saved; };
  }

  it('T-9: jenkins_trigger_build merges fetched build parameters with caller overrides (caller wins)', async () => {
    setEnv('MCP_JENKINS_URL', 'https://jenkins.example.test');
    setEnv('MCP_JENKINS_USER', 'darwin-user');
    setEnv('MCP_JENKINS_API_TOKEN', 'darwin-token');

    let postBody = '';
    const restoreHttps = stubHttps({
      getBody: JSON.stringify({
        actions: [{ parameters: [{ name: 'BRANCH', value: 'main' }, { name: 'CLUSTER', value: 'old-cluster' }] }],
      }),
      capturePostBody: (chunk) => { postBody += chunk; },
    });

    try {
      delete require.cache[require.resolve(JENKINS_MCP_PATH)];
      const { jenkinsTriggerBuild } = require(JENKINS_MCP_PATH);

      const result = await jenkinsTriggerBuild({ job: 'my-job', parameters: { CLUSTER: 'new-cluster' } });

      assert.equal(result.triggered, true);
      assert.equal(result.queueUrl, 'https://jenkins.example.test/queue/item/42/');
      assert.deepEqual(result.parametersUsed, { BRANCH: 'main', CLUSTER: 'new-cluster' });
      const params = new URLSearchParams(postBody);
      assert.equal(params.get('BRANCH'), 'main');
      assert.equal(params.get('CLUSTER'), 'new-cluster');
    } finally {
      restoreHttps();
      delete require.cache[require.resolve(JENKINS_MCP_PATH)];
    }
  });

  it('T-9b: jenkins_trigger_build fetches parameters from an explicit build, not the lastFailedBuild default', async () => {
    setEnv('MCP_JENKINS_URL', 'https://jenkins.example.test');
    setEnv('MCP_JENKINS_USER', 'darwin-user');
    setEnv('MCP_JENKINS_API_TOKEN', 'darwin-token');

    const calls = [];
    const restoreHttps = stubHttps({
      getBody: JSON.stringify({ actions: [{ parameters: [{ name: 'BRANCH', value: 'release' }] }] }),
      calls,
    });

    try {
      delete require.cache[require.resolve(JENKINS_MCP_PATH)];
      const { jenkinsTriggerBuild } = require(JENKINS_MCP_PATH);

      const result = await jenkinsTriggerBuild({ job: 'my-job', build: '55' });

      assert.equal(result.sourceBuild, '55');
      assert.match(calls[0].path, /\/55\/api\/json/, 'must fetch parameters from the explicit build, not lastFailedBuild');
      assert.equal(result.parametersUsed.BRANCH, 'release');
    } finally {
      restoreHttps();
      delete require.cache[require.resolve(JENKINS_MCP_PATH)];
    }
  });

  it('T-9c: jenkins_trigger_build posts to /build (not /buildWithParameters) when there are no parameters at all', async () => {
    setEnv('MCP_JENKINS_URL', 'https://jenkins.example.test');
    setEnv('MCP_JENKINS_USER', 'darwin-user');
    setEnv('MCP_JENKINS_API_TOKEN', 'darwin-token');

    const calls = [];
    const restoreHttps = stubHttps({
      getBody: JSON.stringify({ actions: [] }),
      calls,
    });

    try {
      delete require.cache[require.resolve(JENKINS_MCP_PATH)];
      const { jenkinsTriggerBuild } = require(JENKINS_MCP_PATH);

      const result = await jenkinsTriggerBuild({ job: 'my-job' });

      const postCall = calls.find((c) => c.method === 'POST');
      assert.ok(postCall, 'expected a POST call to trigger the build');
      assert.match(postCall.path, /\/build$/);
      assert.doesNotMatch(postCall.path, /buildWithParameters/);
      assert.deepEqual(result.parametersUsed, {});
    } finally {
      restoreHttps();
      delete require.cache[require.resolve(JENKINS_MCP_PATH)];
    }
  });

  it('T-9d: jenkins_trigger_build reports triggered:false for a 200 dedup no-op with no queue Location', async () => {
    setEnv('MCP_JENKINS_URL', 'https://jenkins.example.test');
    setEnv('MCP_JENKINS_USER', 'darwin-user');
    setEnv('MCP_JENKINS_API_TOKEN', 'darwin-token');

    const restoreHttps = stubHttps({
      getBody: JSON.stringify({ actions: [] }),
      postStatus: 200,
      postHeaders: {},
    });

    try {
      delete require.cache[require.resolve(JENKINS_MCP_PATH)];
      const { jenkinsTriggerBuild } = require(JENKINS_MCP_PATH);

      const result = await jenkinsTriggerBuild({ job: 'my-job' });

      assert.equal(result.triggered, false);
      assert.equal(result.queueUrl, null);
      assert.equal(result.statusCode, 200);
    } finally {
      restoreHttps();
      delete require.cache[require.resolve(JENKINS_MCP_PATH)];
    }
  });

  it('T-9e: jenkins_trigger_build reports triggered:false for a redirect that is not a queue item (e.g. auth-proxy login bounce)', async () => {
    setEnv('MCP_JENKINS_URL', 'https://jenkins.example.test');
    setEnv('MCP_JENKINS_USER', 'darwin-user');
    setEnv('MCP_JENKINS_API_TOKEN', 'darwin-token');

    const loginUrl = 'https://jenkins.example.test/login?from=%2Fjob%2Fmy-job%2Fbuild';
    const restoreHttps = stubHttps({
      getBody: JSON.stringify({ actions: [] }),
      postStatus: 302,
      postHeaders: { location: loginUrl },
    });

    try {
      delete require.cache[require.resolve(JENKINS_MCP_PATH)];
      const { jenkinsTriggerBuild } = require(JENKINS_MCP_PATH);

      const result = await jenkinsTriggerBuild({ job: 'my-job' });

      assert.equal(result.triggered, false);
      assert.equal(result.statusCode, 302);
      assert.equal(result.queueUrl, loginUrl);
    } finally {
      restoreHttps();
      delete require.cache[require.resolve(JENKINS_MCP_PATH)];
    }
  });
});

describe('jenkins-mcp.js HTTP tool functions & error handling', () => {
  const JENKINS_MCP_PATH = path.resolve(__dirname, '..', 'jenkins-mcp.js');
  const https = require('https');
  const ENV_KEYS = ['MCP_JENKINS_URL', 'MCP_JENKINS_USER', 'MCP_JENKINS_API_TOKEN'];
  let savedLocalEnv;

  // Self-contained env save/restore (not the shared setEnv/restoreEnv helper above,
  // which the sibling 'parameter merge' describe never calls restoreEnv() for) so
  // this describe's env state can't leak into or be polluted by other describes.
  beforeEach(() => {
    savedLocalEnv = Object.fromEntries(ENV_KEYS.map((k) => [k, process.env[k]]));
    process.env.MCP_JENKINS_URL = 'https://jenkins.example.test';
    process.env.MCP_JENKINS_USER = 'darwin-user';
    process.env.MCP_JENKINS_API_TOKEN = 'darwin-token';
    delete require.cache[require.resolve(JENKINS_MCP_PATH)];
  });

  afterEach(() => {
    for (const k of ENV_KEYS) {
      if (savedLocalEnv[k] === undefined) delete process.env[k];
      else process.env[k] = savedLocalEnv[k];
    }
    delete require.cache[require.resolve(JENKINS_MCP_PATH)];
  });

  function freshMcp() {
    delete require.cache[require.resolve(JENKINS_MCP_PATH)];
    return require(JENKINS_MCP_PATH);
  }

  // Queue-based https.request stub: each call to https.request() consumes the next
  // queued item, in order, so a single test can script a GET followed by a POST (or
  // several retried GETs) with independent statuses/bodies/errors.
  function stubHttpsQueue(queue) {
    const saved = https.request;
    const calls = [];
    https.request = (opts, callback) => {
      calls.push(opts);
      const item = queue.shift();
      if (!item) throw new Error(`stubHttpsQueue: no queued response for call #${calls.length} (${opts.method} ${opts.path})`);
      const req = {
        _handlers: {},
        on(event, handler) { req._handlers[event] = handler; return req; },
        write() {},
        destroy() {},
        end() {
          if (item.type === 'error') {
            if (req._handlers.error) req._handlers.error(item.err);
            return;
          }
          if (item.type === 'timeout') {
            if (req._handlers.timeout) req._handlers.timeout.call(req);
            return;
          }
          const res = {
            statusCode: item.statusCode,
            headers: item.headers || {},
            on(event, handler) {
              if (event === 'data') handler(item.body !== undefined ? item.body : '');
              if (event === 'end') handler();
              return res;
            },
          };
          callback(res);
        },
      };
      return req;
    };
    return { restore: () => { https.request = saved; }, calls };
  }

  it('T-20: jenkins_get_build_status requests lastBuild by default and returns the parsed body verbatim', async () => {
    const { restore, calls } = stubHttpsQueue([
      { statusCode: 200, body: JSON.stringify({ number: 7, result: 'SUCCESS' }) },
    ]);
    try {
      const { jenkinsGetBuildStatus } = freshMcp();
      const result = await jenkinsGetBuildStatus({ job: 'my-job' });
      assert.deepEqual(result, { number: 7, result: 'SUCCESS' });
      assert.match(calls[0].path, /\/job\/my-job\/lastBuild\/api\/json/);
      assert.match(calls[0].path, /tree=number,result,building,url,actions/);
    } finally {
      restore();
    }
  });

  it('T-21: jenkins_get_build_status honors an explicit build number', async () => {
    const { restore, calls } = stubHttpsQueue([
      { statusCode: 200, body: JSON.stringify({ number: 42 }) },
    ]);
    try {
      const { jenkinsGetBuildStatus } = freshMcp();
      await jenkinsGetBuildStatus({ job: 'my-job', build: '42' });
      assert.match(calls[0].path, /\/job\/my-job\/42\/api\/json/);
    } finally {
      restore();
    }
  });

  it('T-22: jenkins_get_recent_builds defaults to a limit of 10', async () => {
    const { restore, calls } = stubHttpsQueue([
      { statusCode: 200, body: JSON.stringify({ builds: [] }) },
    ]);
    try {
      const { jenkinsGetRecentBuilds } = freshMcp();
      const result = await jenkinsGetRecentBuilds({ job: 'my-job' });
      assert.deepEqual(result, { builds: [] });
      assert.match(calls[0].path, /\{0,10\}/);
    } finally {
      restore();
    }
  });

  it('T-23: jenkins_get_recent_builds honors a custom limit', async () => {
    const { restore, calls } = stubHttpsQueue([
      { statusCode: 200, body: JSON.stringify({ builds: [] }) },
    ]);
    try {
      const { jenkinsGetRecentBuilds } = freshMcp();
      await jenkinsGetRecentBuilds({ job: 'my-job', limit: 3 });
      assert.match(calls[0].path, /\{0,3\}/);
    } finally {
      restore();
    }
  });

  it('T-24: jenkins_get_build_status throws (does not silently return HTML) on a 404', async () => {
    const { restore, calls } = stubHttpsQueue([
      { statusCode: 404, body: '<html>Not Found</html>' },
    ]);
    try {
      const { jenkinsGetBuildStatus } = freshMcp();
      await assert.rejects(jenkinsGetBuildStatus({ job: 'missing-job' }), /HTTP 404/);
      assert.equal(calls.length, 1, '4xx must not be retried');
    } finally {
      restore();
    }
  });

  it('T-16: a GET request retries once on a 5xx then succeeds', async () => {
    const { restore, calls } = stubHttpsQueue([
      { statusCode: 503, body: 'Service Unavailable' },
      { statusCode: 200, body: JSON.stringify({ number: 9 }) },
    ]);
    try {
      const { jenkinsGetBuildStatus } = freshMcp();
      const result = await jenkinsGetBuildStatus({ job: 'my-job' });
      assert.deepEqual(result, { number: 9 });
      assert.equal(calls.length, 2);
    } finally {
      restore();
    }
  });

  it('T-16b: a GET request retries on a network error, then throws once retries are exhausted', async () => {
    const err = new Error('connect ECONNREFUSED');
    const { restore, calls } = stubHttpsQueue([
      { type: 'error', err },
      { type: 'error', err },
      { type: 'error', err },
    ]);
    try {
      const { jenkinsGetBuildStatus } = freshMcp();
      await assert.rejects(jenkinsGetBuildStatus({ job: 'my-job' }), /ECONNREFUSED/);
      assert.equal(calls.length, 3, 'expected 1 initial attempt + 2 retries');
    } finally {
      restore();
    }
  });

  it('T-16c: a GET request retries on timeout, then throws once retries are exhausted', async () => {
    const { restore, calls } = stubHttpsQueue([
      { type: 'timeout' },
      { type: 'timeout' },
      { type: 'timeout' },
    ]);
    try {
      const { jenkinsGetBuildStatus } = freshMcp();
      await assert.rejects(jenkinsGetBuildStatus({ job: 'my-job' }), /timeout/);
      assert.equal(calls.length, 3);
    } finally {
      restore();
    }
  });

  it('T-17: fetchBuildParameters treats a non-JSON 200 response as "no parameters" instead of throwing', async () => {
    const { restore } = stubHttpsQueue([
      { statusCode: 200, body: '<html>not json</html>' }, // GET for fetchBuildParameters
      { statusCode: 201, headers: { location: 'https://jenkins.example.test/queue/item/1/' } }, // POST trigger
    ]);
    try {
      const { jenkinsTriggerBuild } = freshMcp();
      const result = await jenkinsTriggerBuild({ job: 'my-job', parameters: { FOO: 'bar' } });
      assert.deepEqual(result.parametersUsed, { FOO: 'bar' });
      assert.equal(result.triggered, true);
    } finally {
      restore();
    }
  });

  it('T-18: fetchBuildParameters failure (Jenkins down) falls back to caller-supplied parameters only', async () => {
    const err = new Error('connect ECONNREFUSED 127.0.0.1:443');
    const savedConsoleError = console.error;
    const errorLogs = [];
    console.error = (...args) => errorLogs.push(args.join(' '));
    const { restore } = stubHttpsQueue([
      { type: 'error', err }, { type: 'error', err }, { type: 'error', err }, // GET exhausts retries
      { statusCode: 201, headers: { location: 'https://jenkins.example.test/queue/item/2/' } }, // POST trigger
    ]);
    try {
      const { jenkinsTriggerBuild } = freshMcp();
      const result = await jenkinsTriggerBuild({ job: 'my-job', parameters: { FOO: 'bar' } });
      assert.deepEqual(result.parametersUsed, { FOO: 'bar' });
      assert.equal(result.triggered, true);
      assert.ok(
        errorLogs.some((l) => l.includes('Failed to fetch parameters')),
        'the fetch failure must be logged for diagnostics, not silently swallowed',
      );
    } finally {
      console.error = savedConsoleError;
      restore();
    }
  });

  it('T-19: fetchBuildParameters failure (404 on the source build) falls back without retrying', async () => {
    const savedConsoleError = console.error;
    console.error = () => {};
    const { restore, calls } = stubHttpsQueue([
      { statusCode: 404, body: 'Not Found' }, // GET -- no retry on 4xx
      { statusCode: 200, headers: {} }, // POST trigger, no params -> /build, dedup no-op
    ]);
    try {
      const { jenkinsTriggerBuild } = freshMcp();
      const result = await jenkinsTriggerBuild({ job: 'my-job', build: '999' });
      assert.deepEqual(result.parametersUsed, {});
      assert.equal(calls.filter((c) => c.method === 'GET').length, 1, '404 must not be retried');
    } finally {
      console.error = savedConsoleError;
      restore();
    }
  });
});

describe('jenkins-mcp.js stdio JSON-RPC protocol loop', () => {
  const { spawn } = require('child_process');
  const readlineModule = require('readline');
  const JENKINS_MCP_PATH = path.resolve(__dirname, '..', 'jenkins-mcp.js');

  const children = [];

  afterEach(() => {
    while (children.length) {
      const child = children.pop();
      try { child.kill(); } catch { /* already dead */ }
    }
  });

  function startServer(envOverrides = {}) {
    const child = spawn(process.execPath, [JENKINS_MCP_PATH], {
      env: {
        ...process.env,
        MCP_JENKINS_URL: 'https://jenkins.example.test',
        MCP_JENKINS_USER: 'darwin-user',
        MCP_JENKINS_API_TOKEN: 'darwin-token',
        ...envOverrides,
      },
      stdio: ['pipe', 'pipe', 'pipe'],
    });
    children.push(child);

    const lineRl = readlineModule.createInterface({ input: child.stdout });
    const pendingLines = [];
    const waiters = [];
    lineRl.on('line', (line) => {
      if (waiters.length) waiters.shift()(line);
      else pendingLines.push(line);
    });

    let stderr = '';
    child.stderr.on('data', (chunk) => { stderr += chunk.toString(); });

    function nextLine(timeoutMs = 5000) {
      if (pendingLines.length) return Promise.resolve(pendingLines.shift());
      return new Promise((resolve, reject) => {
        const timer = setTimeout(
          () => reject(new Error(`timed out waiting for a response line (stderr so far: ${stderr})`)),
          timeoutMs,
        );
        waiters.push((line) => { clearTimeout(timer); resolve(line); });
      });
    }

    return {
      child,
      nextLine,
      send: (obj) => child.stdin.write(JSON.stringify(obj) + '\n'),
      sendRaw: (text) => child.stdin.write(text + '\n'),
      stop: () => { child.stdin.end(); child.kill(); },
    };
  }

  it('T-25: initialize responds with protocolVersion, capabilities, and serverInfo', async () => {
    const srv = startServer();
    srv.send({ jsonrpc: '2.0', id: 1, method: 'initialize', params: {} });
    const msg = JSON.parse(await srv.nextLine());
    assert.equal(msg.id, 1);
    assert.equal(msg.result.protocolVersion, '2024-11-05');
    assert.deepEqual(msg.result.capabilities, { tools: {} });
    assert.equal(msg.result.serverInfo.name, 'DarwinJenkins');
    srv.stop();
  });

  it('T-26: tools/list responds with exactly the 3-tool contract server.js/ws-*.js depend on', async () => {
    const srv = startServer();
    srv.send({ jsonrpc: '2.0', id: 2, method: 'tools/list' });
    const msg = JSON.parse(await srv.nextLine());
    assert.equal(msg.id, 2);
    const names = msg.result.tools.map((t) => t.name);
    assert.deepEqual(names, ['jenkins_trigger_build', 'jenkins_get_build_status', 'jenkins_get_recent_builds']);
    srv.stop();
  });

  it('T-27: an unrecognized method returns a JSON-RPC -32601 respondError', async () => {
    const srv = startServer();
    srv.send({ jsonrpc: '2.0', id: 3, method: 'bogus/method' });
    const msg = JSON.parse(await srv.nextLine());
    assert.equal(msg.id, 3);
    assert.equal(msg.error.code, -32601);
    assert.match(msg.error.message, /bogus\/method/);
    srv.stop();
  });

  it('T-28: a malformed JSON line does not crash the process -- later lines still get responses', async () => {
    const srv = startServer();
    srv.sendRaw('{not valid json');
    srv.send({ jsonrpc: '2.0', id: 4, method: 'tools/list' });
    const msg = JSON.parse(await srv.nextLine());
    assert.equal(msg.id, 4);
    assert.ok(Array.isArray(msg.result.tools));
    assert.equal(srv.child.exitCode, null, 'process must still be alive after a malformed line');
    srv.stop();
  });

  it('T-29: valid JSON that is not a request object (null/number) is ignored without crashing', async () => {
    const srv = startServer();
    srv.sendRaw('null');
    srv.sendRaw('42');
    srv.send({ jsonrpc: '2.0', id: 5, method: 'tools/list' });
    const msg = JSON.parse(await srv.nextLine());
    assert.equal(msg.id, 5);
    assert.equal(srv.child.exitCode, null);
    srv.stop();
  });

  it('T-30: notifications/initialized produces no response line', async () => {
    const srv = startServer();
    srv.send({ jsonrpc: '2.0', method: 'notifications/initialized' });
    srv.send({ jsonrpc: '2.0', id: 6, method: 'tools/list' });
    // If notifications/initialized had (incorrectly) produced a response, it would
    // be the *first* line read here instead of the tools/list response.
    const msg = JSON.parse(await srv.nextLine());
    assert.equal(msg.id, 6);
    srv.stop();
  });

  it('T-31: tools/call dispatches to handleToolCall and wraps an unknown-tool error as response content (no crash)', async () => {
    const srv = startServer();
    srv.send({ jsonrpc: '2.0', id: 7, method: 'tools/call', params: { name: 'nonexistent_tool', arguments: {} } });
    const msg = JSON.parse(await srv.nextLine());
    assert.equal(msg.id, 7);
    assert.ok(Array.isArray(msg.result.content));
    assert.match(msg.result.content[0].text, /Unknown tool: nonexistent_tool/);
    assert.equal(srv.child.exitCode, null);
    srv.stop();
  });
});

describe('Jenkins MCP call-site contracts', () => {
  it('T-13: role gate is limited to sysadmin and developer call sites', () => {
    const serverBody = fs.readFileSync(SERVER_PATH, 'utf8');
    const wsClientBody = fs.readFileSync(WS_CLIENT_PATH, 'utf8');
    const wsServerBody = fs.readFileSync(WS_SERVER_PATH, 'utf8');
    const serverGate = /\[(?:'|")sysadmin(?:'|"),\s*(?:'|")developer(?:'|")\]\.includes\(agentRole\)/;
    const taskGate = /\[(?:'|")sysadmin(?:'|"),\s*(?:'|")developer(?:'|")\]\.includes\(role\)/;

    assert.match(serverBody, /setupJenkinsMCP/);
    assert.match(serverBody, serverGate);
    assert.match(wsClientBody, /setupJenkinsMCP/);
    assert.match(wsClientBody, taskGate);
    assert.match(wsServerBody, /setupJenkinsMCP/);
    assert.match(wsServerBody, taskGate);
  });

  it('T-13b: role gate evaluates correctly at runtime', () => {
    // Extract the allowed-roles array from ws-client.js source (not hand-rewritten)
    const wsClientBody = fs.readFileSync(WS_CLIENT_PATH, 'utf8');
    const arrayMatch = wsClientBody.match(/(\['sysadmin',\s*'developer'\])\.includes\(role\)/);
    assert.ok(arrayMatch, 'Role gate array must exist in ws-client.js');
    const JENKINS_ROLES = JSON.parse(arrayMatch[1].replace(/'/g, '"'));

    for (const role of ['explorer', 'architect', 'security_analyst', 'code_reviewer', 'qe']) {
      assert.equal(JENKINS_ROLES.includes(role), false, `${role} must be excluded from Jenkins MCP`);
    }
    for (const role of JENKINS_ROLES) {
      assert.equal(JENKINS_ROLES.includes(role), true, `${role} must pass Jenkins MCP role gate`);
    }
  });

  it('T-comms-2: team_send_results description includes jenkins_retrigger for sysadmin/developer', () => {
    const body = fs.readFileSync(TEAM_CHAT_PATH, 'utf8');
    assert.match(body, /JENKINS_RETRIGGER_CLAUSE\s*=\s*['"`][^'"`]*jenkins_retrigger[^'"`]*['"`]/);
    assert.match(body, /CAN_RETRIGGER_JENKINS\s*\?\s*JENKINS_RETRIGGER_CLAUSE/);
    assert.match(body, /team_send_results[\s\S]*?description:\s*SEND_RESULTS_CONTENT_DESC/);
  });

  it('T-comms-4: JENKINS_RETRIGGER_CLAUSE includes wrapper_job (drives the cooldown consumed by brain.py)', () => {
    const body = fs.readFileSync(TEAM_CHAT_PATH, 'utf8');
    const clauseMatch = body.match(/JENKINS_RETRIGGER_CLAUSE\s*=\s*'([^']*)'/);
    assert.ok(clauseMatch, 'JENKINS_RETRIGGER_CLAUSE must be defined as a single-quoted string');
    assert.match(clauseMatch[1], /wrapper_job:\s*<exact-jenkins-wrapper-job-name-that-owns-this-leaf>/,
      'clause must advertise wrapper_job — brain.py::_consume_jenkins_retrigger_signal early-returns without it');
  });

  it('T-comms-3: team_send_results description excludes jenkins_retrigger for non-sysadmin/developer', () => {
    const body = fs.readFileSync(TEAM_CHAT_PATH, 'utf8');
    assert.match(body, /CAN_RETRIGGER_JENKINS\s*=\s*ROLE\s*===\s*'sysadmin'\s*\|\|\s*ROLE\s*===\s*'developer'/);
    const gateExpr = (role) => role === 'sysadmin' || role === 'developer';
    for (const role of ['explorer', 'architect', 'security_analyst', 'code_reviewer', 'qe']) {
      assert.equal(gateExpr(role), false, `${role} must NOT get jenkins_retrigger in description`);
    }
    for (const role of ['sysadmin', 'developer']) {
      assert.equal(gateExpr(role), true, `${role} must get jenkins_retrigger in description`);
    }
  });
});
