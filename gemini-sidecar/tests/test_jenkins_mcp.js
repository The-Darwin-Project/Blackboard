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
    // existsSync returns true but files vanished (TOCTOU) — readFileSync throws ENOENT
    restore = mockFs({
      exists: {
        '/secrets/jenkins/username': true,
        '/secrets/jenkins/api-token': true,
      },
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

  function stubHttps({ getBody, capturePostBody }) {
    const saved = https.request;
    https.request = (opts, callback) => {
      const req = {
        on() { return req; },
        write(chunk) { if (opts.method === 'POST' && capturePostBody) capturePostBody(chunk); },
        end() {
          const isPost = opts.method === 'POST';
          const res = {
            statusCode: isPost ? 201 : 200,
            headers: isPost ? { location: 'https://jenkins.example.test/queue/item/42/' } : {},
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
