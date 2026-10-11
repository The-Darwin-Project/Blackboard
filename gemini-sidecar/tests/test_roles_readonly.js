// gemini-sidecar/tests/test_roles_readonly.js
// @ai-rules:
// 1. [Constraint]: Test-only file -- the shared read-only role predicate (roles.js) and its consumers:
//    ArgoCD MCP config (credentials.js buildArgoCDMcpConfig) and the Claude --settings deny file.
// 2. [Gotcha]: ephemeral agents boot with AGENT_ROLE="" and learn their role per task, so consumers MUST be handed the
//    per-task role; these tests pin that explorer/security_analyst (not just architect) are read-only.
const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { isReadOnlyRoleName, isMutatingRoleName, normalizeRole } = require('../roles');

describe('isReadOnlyRoleName & isMutatingRoleName', () => {
  it('listed read-only roles', () => {
    for (const r of ['architect', 'explorer', 'code_reviewer', 'reviewer', 'security_analyst']) {
      assert.equal(isReadOnlyRoleName(r), true, r);
      assert.equal(isMutatingRoleName(r), false, r);
    }
  });
  it('mutating roles are mutating and not read-only', () => {
    for (const r of ['developer', 'sysadmin', 'qe', 'tester', 'executor']) {
      assert.equal(isReadOnlyRoleName(r), false, r);
      assert.equal(isMutatingRoleName(r), true, r);
    }
    // release_manager is unlisted mutating role, neither explicitly mutating nor read-only
    assert.equal(isReadOnlyRoleName('release_manager'), false);
    assert.equal(isMutatingRoleName('release_manager'), false);
  });
  it('read-only-looking and oddly-cased names fail closed', () => {
    for (const r of ['qa_reviewer_agent', 'ARCHITECT_LEAD', 'security-analyst', '  Explorer \n']) {
      assert.equal(isReadOnlyRoleName(r), true, JSON.stringify(r));
      assert.equal(isMutatingRoleName(r), false, JSON.stringify(r));
    }
  });
  it('unset role is neither (callers have their own unresolved-role fail-closed path)', () => {
    for (const r of ['', undefined, null]) {
      assert.equal(isReadOnlyRoleName(r), false);
      assert.equal(isMutatingRoleName(r), false);
    }
    assert.equal(normalizeRole(' A/B '), 'ab');
  });
});

describe('ArgoCD MCP config', () => {
  it('read-only roles get MCP_READ_ONLY, mutating roles do not', () => {
    // credentials.js needs no network at require time
    const { buildArgoCDMcpConfig } = require('../credentials');
    const cfg = (role) => buildArgoCDMcpConfig({ baseUrl: 'https://argocd.example', sessionJwt: 'jwt', role, insecure: false });
    for (const r of ['architect', 'explorer', 'security_analyst', 'code_reviewer', 'qa_reviewer_agent']) {
      assert.equal(cfg(r).env.MCP_READ_ONLY, 'true', r);
    }
    for (const r of ['developer', 'sysadmin', 'qe']) assert.equal(cfg(r).env.MCP_READ_ONLY, undefined, r);
    for (const r of ['', undefined, null]) assert.equal(cfg(r).env.MCP_READ_ONLY, 'true', JSON.stringify(r));
  });
});

describe('readonly-role-permissions.json (Claude engine-enforced deny list)', () => {
  const file = path.resolve(__dirname, '..', 'claude-settings', 'readonly-role-permissions.json');
  const deny = JSON.parse(fs.readFileSync(file, 'utf8')).permissions.deny;
  it('denies MCP write tools for every registered server', () => {
    for (const t of ['mcp__GitHub__push_files', 'mcp__GitHub__create_or_update_file', 'mcp__GitHub__merge_pull_request', 'mcp__GitHub__create_branch',
      'mcp__GitHub__pull_request_review_write', 'mcp__GitLab__glab_mr_merge', 'mcp__GitLab__glab_mr_create', 'mcp__GitLab__glab_ci_run',
      'mcp__ArgoCD__sync_application', 'mcp__ArgoCD__run_resource_action', 'mcp__Jenkins__jenkins_trigger_build',
      'mcp__Playwright__browser_evaluate', 'mcp__Playwright__browser_run_code_unsafe']) assert.ok(deny.includes(t), t);
  });
  it('keeps read tools available', () => {
    for (const t of ['mcp__GitHub__get_file_contents', 'mcp__GitHub__list_pull_requests', 'mcp__GitLab__glab_mr_view', 'mcp__ArgoCD__get_application',
      'mcp__DarwinBlackboard__bb_catch_up', 'mcp__TeamChat__team_send_results']) assert.equal(deny.includes(t), false, t);
  });
  it('denies the credential stores beyond the original set', () => {
    for (const r of ['Read(~/.claude.json)', 'Read(~/.docker/**)', 'Read(~/.gemini/**)', 'Read(~/.config/gh/**)', 'Read(//var/run/secrets/**)', 'Read(~/.kube/**)']) {
      assert.ok(deny.includes(r), r);
    }
  });
  it('has Bash parity with the agy hook denylist (infra + merge commands)', () => {
    for (const r of ['Bash(helm install *)', 'Bash(argocd app sync *)', 'Bash(kubectl create *)', 'Bash(gh pr merge *)', 'Bash(glab mr merge *)', 'Bash(tkn pipeline start *)', 'Bash(kargo promote *)']) {
      assert.ok(deny.includes(r), r);
    }
  });
  it('denies WebFetch and WebSearch to prevent external network exfiltration', () => {
    for (const tool of ['WebFetch', 'WebSearch']) {
      assert.ok(deny.includes(tool), tool);
    }
  });
  it('denies Bash(cat ...) for all sensitive credential stores', () => {
    for (const r of [
      'Bash(cat ~/.claude.json*)', 'Bash(cat ~/.claude/.credentials.json*)', 'Bash(cat ~/.claude/*)',
      'Bash(cat ~/.gemini/*)', 'Bash(cat ~/.docker/*)', 'Bash(cat /var/run/secrets/*)', 'Bash(cat /run/secrets/*)',
      'Bash(cat /secrets/*)', 'Bash(cat ~/.ssh/*)', 'Bash(cat ~/.git-credentials*)', 'Bash(cat ~/.gitconfig*)',
      'Bash(cat ~/.config/git/*)', 'Bash(cat ~/.netrc*)', 'Bash(cat ~/.aws/*)', 'Bash(cat ~/.kube/config*)',
      'Bash(cat ~/.kube/*)', 'Bash(cat ~/.config/gh/*)', 'Bash(cat ~/.config/glab-cli/*)', 'Bash(cat ~/.config/gcloud/*)',
      'Bash(cat /tmp/vertex-sa*)', 'Bash(cat /tmp/*token*)', 'Bash(cat /tmp/*credential*)',
      'Bash(cat /tmp/git-creds-*)', 'Bash(cat /tmp/gh-token-map*)',
    ]) {
      assert.ok(deny.includes(r), r);
    }
  });
});
