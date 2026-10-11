// gemini-sidecar/tests/test_claude_merge_guard.js
// @ai-rules:
// 1. [Constraint]: Test-only file -- regression coverage for the Claude-path merge-approval guard
//    (POST /hooks/pre-tool-use -> claude-guard.js -> hooks/merge-guard.js).
// 2. [Pattern]: End-to-end over real loopback HTTP: handleRequest + a fake Brain that serves
//    /queue/<eventId>/approval. Git state comes from a throwaway repo passed as payload.cwd.

const { describe, it, afterEach, before, after } = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');
const http = require('http');
const fs = require('fs');
const os = require('os');
const { execFileSync } = require('child_process');

const CONFIG_PATH = path.resolve(__dirname, '..', 'config.js');
const STATE_PATH = path.resolve(__dirname, '..', 'state.js');
const HTTP_HANDLER_PATH = path.resolve(__dirname, '..', 'http-handler.js');

const savedEnv = {};
function setEnv(key, value) {
  if (!(key in savedEnv)) savedEnv[key] = process.env[key];
  if (value === undefined) delete process.env[key]; else process.env[key] = value;
}
function clearCache() {
  [CONFIG_PATH, STATE_PATH, HTTP_HANDLER_PATH].forEach((p) => delete require.cache[require.resolve(p)]);
}
afterEach(() => {
  for (const [k, v] of Object.entries(savedEnv)) { if (v === undefined) delete process.env[k]; else process.env[k] = v; }
  Object.keys(savedEnv).forEach((k) => delete savedEnv[k]);
  clearCache();
});

const git = (cwd, ...args) => execFileSync('git', ['-c', 'user.name=t', '-c', 'user.email=t@t', ...args], { cwd, encoding: 'utf8' }).trim();
let repoFeat; let repoMain; let featSha;
before(() => {
  repoFeat = fs.mkdtempSync(path.join(os.tmpdir(), 'cg-feat-'));
  repoMain = fs.mkdtempSync(path.join(os.tmpdir(), 'cg-main-'));
  // distinct messages => distinct commit SHAs even when created within the same second
  [repoFeat, repoMain].forEach((r, i) => { git(r, 'init', '-q', '-b', 'main'); git(r, 'commit', '-q', '--allow-empty', '-m', `init-${i}`); });
  git(repoFeat, 'checkout', '-q', '-b', 'feat/x');
  featSha = git(repoFeat, 'rev-parse', 'HEAD');
});
after(() => { for (const r of [repoFeat, repoMain]) fs.rmSync(r, { recursive: true, force: true }); });

function startServer(handleRequest, brainBody) {
  return new Promise((resolve) => {
    const brain = http.createServer((req, res) => {
      res.writeHead(brainBody === null ? 502 : 200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(brainBody === null ? { error: 'down' } : brainBody));
    });
    brain.listen(0, '127.0.0.1', () => resolve({ brain, brainPort: brain.address().port }));
  });
}

async function setup(approval, role = 'developer') {
  const { brain, brainPort } = await startServer(null, approval);
  setEnv('BRAIN_HTTP_URL', `http://127.0.0.1:${brainPort}`);
  clearCache();
  const handler = require(HTTP_HANDLER_PATH);
  const state = require(STATE_PATH);
  state.setCurrentTask({ eventId: 'evt-1', role });
  const app = await new Promise((resolve) => {
    const server = http.createServer((req, res) => { handler.handleRequest(req, res).catch(() => {}); });
    server.listen(0, '127.0.0.1', () => resolve(server));
  });
  const post = (body) => new Promise((resolve, reject) => {
    const data = typeof body === 'string' ? body : JSON.stringify(body);
    const req = http.request({ hostname: '127.0.0.1', port: app.address().port, path: '/hooks/pre-tool-use', method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(data) } }, (res) => {
      let c = ''; res.on('data', (d) => { c += d; }); res.on('end', () => resolve({ status: res.statusCode, body: JSON.parse(c) }));
    });
    req.on('error', reject); req.write(data); req.end();
  });
  return { post, close: () => { app.close(); brain.close(); state.setCurrentTask(null); } };
}

const bash = (command, cwd) => ({ tool_name: 'Bash', tool_input: { command }, cwd });
const denied = (r) => r.body?.hookSpecificOutput?.permissionDecision === 'deny';

describe('Claude PreToolUse merge guard', () => {
  it('denies merge-class shell commands when the event is not approved', async () => {
    const s = await setup({ approved: false });
    try {
      for (const c of ['git merge x', 'git -C . merge x', 'gh -R o/r pr merge 1', 'git push origin main', 'git push',
        'curl -X PUT https://api.github.com/repos/o/r/pulls/1/merge', 'echo "git merge x" | bash', 'git $SUB x',
        'git config alias.m merge; git m x', 'GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=alias.m GIT_CONFIG_VALUE_0=merge git m x',
        'echo "[alias] m = merge" >> .git/config; git m x']) {
        const r = await s.post(bash(c, repoMain));
        assert.equal(r.status, 200, c);
        assert.ok(denied(r), `expected deny for: ${c}`);
        assert.match(r.body.hookSpecificOutput.permissionDecisionReason, /Merge REFUSED/);
      }
    } finally { s.close(); }
  });

  it('denies MCP merge tools (Claude mcp__ naming) when not approved', async () => {
    const s = await setup({ approved: false });
    try {
      for (const t of ['mcp__GitHub__merge_pull_request', 'mcp__GitLab__glab_mr_merge', 'mcp__GitHub__push_files']) {
        const r = await s.post({ tool_name: t, tool_input: { branch: 'main' }, cwd: repoFeat });
        assert.ok(denied(r), t);
      }
    } finally { s.close(); }
  });

  it('allows ordinary commands and non-main pushes without consulting approval', async () => {
    const s = await setup({ approved: false });
    try {
      for (const c of ['git status', 'git log --merges -3', 'git merge-base a b', 'git commit -m "fix merge guard"', 'git push']) {
        const r = await s.post(bash(c, repoFeat));
        assert.ok(!denied(r), `expected allow for: ${c} -> ${JSON.stringify(r.body)}`);
      }
      const r = await s.post({ tool_name: 'Read', tool_input: { file_path: '/x' }, cwd: repoFeat });
      assert.ok(!denied(r));
    } finally { s.close(); }
  });

  it('allows a merge only when approved AND the approved SHA equals the cwd HEAD', async () => {
    let s = await setup({ approved: true, approved_mr_sha: featSha });
    try {
      assert.ok(!denied(await s.post(bash('git merge x', repoFeat))));
      assert.ok(denied(await s.post(bash('git merge x', repoMain))), 'different repo HEAD must not match the approved SHA');
    } finally { s.close(); }
    s = await setup({ approved: true, approved_mr_sha: 'deadbeef' });
    try {
      const r = await s.post(bash('gh pr merge 1', repoFeat));
      assert.ok(denied(r));
      assert.match(r.body.hookSpecificOutput.permissionDecisionReason, /differs from authenticated approval SHA/);
    } finally { s.close(); }
  });

  it('fails closed when the Brain approval endpoint is unreachable or there is no active event', async () => {
    let s = await setup(null);
    try { assert.ok(denied(await s.post(bash('git merge x', repoFeat)))); } finally { s.close(); }
    s = await setup({ approved: true, approved_mr_sha: featSha });
    try {
      require(STATE_PATH).setCurrentTask(null);
      assert.ok(denied(await s.post(bash('git merge x', repoFeat))));
    } finally { s.close(); }
  });

  it('fails closed on malformed bodies and empty shell commands', async () => {
    const s = await setup({ approved: false });
    try {
      assert.ok(denied(await s.post('not json')));
      assert.ok(denied(await s.post({ tool_name: 'Bash', tool_input: {}, cwd: repoFeat })));
    } finally { s.close(); }
  });

  it('keeps injecting context for allowed calls (existing behavior)', async () => {
    const s = await setup({ approved: false });
    try {
      const r = await s.post(bash('git status', repoFeat));
      assert.equal(r.status, 200);
      assert.ok(!denied(r));
    } finally { s.close(); }
  });
});

describe('Claude PreToolUse for READ-ONLY roles (delegated to validate-mutations.sh)', () => {
  const tool = (tool_name, tool_input = {}, cwd) => ({ tool_name, tool_input, cwd });
  for (const role of ['explorer', 'security_analyst', 'architect']) {
    it(`${role}: native read tools allowed; writes, MCP writes and mutating shell denied`, async () => {
      const s = await setup({ approved: false }, role);
      try {
        for (const t of ['Read', 'Grep', 'Glob', 'Task', 'WebFetch', 'mcp__GitHub__get_file_contents', 'mcp__GitHub__list_pull_requests', 'mcp__ArgoCD__get_application']) {
          assert.ok(!denied(await s.post(tool(t, {}, repoFeat))), `expected allow: ${t}`);
        }
        assert.ok(!denied(await s.post(bash('git status', repoFeat))), 'read-only shell allowed');
        for (const t of ['Write', 'Edit', 'NotebookEdit', 'mcp__GitHub__create_branch', 'mcp__GitHub__push_files', 'mcp__ArgoCD__sync_application', 'mcp__Playwright__browser_evaluate']) {
          assert.ok(denied(await s.post(tool(t, { branch: 'feat/x' }, repoFeat))), `expected deny: ${t}`);
        }
        for (const c of ['git push origin feat/x', 'rm -rf x', 'echo x > f.txt', 'kubectl delete pod p']) {
          assert.ok(denied(await s.post(bash(c, repoFeat))), `expected deny: ${c}`);
        }
      } finally { s.close(); }
    });
  }
  it('a name-heuristic read-only role (qa_reviewer_agent) is read-only too', async () => {
    const s = await setup({ approved: false }, 'qa_reviewer_agent');
    try {
      assert.ok(denied(await s.post(tool('Write', {}, repoFeat))));
      assert.ok(!denied(await s.post(tool('Read', {}, repoFeat))));
    } finally { s.close(); }
  });
  it('mutating roles keep the old behaviour (no read-only allowlist)', async () => {
    const s = await setup({ approved: false }, 'developer');
    try {
      assert.ok(!denied(await s.post(tool('Write', {}, repoFeat))));
      assert.ok(!denied(await s.post(tool('mcp__GitHub__create_branch', { branch: 'feat/x' }, repoFeat))));
    } finally { s.close(); }
  });
});
