// gemini-sidecar/tests/test_merge_guard_unit.js
// @ai-rules:
// 1. [Constraint]: Test-only file -- unit coverage for hooks/merge-guard.js reliability properties that the
//    bash suite cannot reach: fail-closed on UNKNOWN git state (budget exhausted, spawn cap, bad cwd) and
//    the Claude-path child-process classifier.
// 2. [Pattern]: classify(payload, {budgetMs: -1}) simulates an exhausted budget (deadline already passed).
const { describe, it, before, after } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { execFileSync } = require('child_process');
const mg = require('../hooks/merge-guard.js');

const sh = (command) => ({ tool_name: 'Bash', tool_input: { command } });
let repo;
before(() => {
  repo = fs.mkdtempSync(path.join(os.tmpdir(), 'mg-unit-'));
  execFileSync('git', ['init', '-q', '-b', 'feat/x'], { cwd: repo });
  execFileSync('git', ['config', 'alias.mm', 'merge'], { cwd: repo });
  execFileSync('git', ['-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-q', '--allow-empty', '-m', 'i'], { cwd: repo }); // rev-parse HEAD needs a commit
});
after(() => fs.rmSync(repo, { recursive: true, force: true }));

describe('git state lookups fail closed when the answer is unknown', () => {
  it('unknown subcommand + exhausted budget is guarded (alias lookup cannot be answered)', () => {
    assert.equal(mg.classify(sh('git lg'), { cwd: repo, budgetMs: -1 }).guard, true);
  });
  it('unknown subcommand with a working lookup and no alias is NOT guarded', () => {
    assert.equal(mg.classify(sh('git lg'), { cwd: repo }).guard, false);
  });
  it('alias that expands to merge is guarded', () => {
    assert.equal(mg.classify(sh('git mm x'), { cwd: repo }).guard, true);
  });
  it('bare push with exhausted budget is guarded; on a feature branch with budget it is not', () => {
    assert.equal(mg.classify(sh('git push'), { cwd: repo, budgetMs: -1 }).guard, true);
    assert.equal(mg.classify(sh('git push'), { cwd: repo }).guard, false);
  });
  it('git spawn count is capped: many unknown subcommands in one call end up guarded', () => {
    const many = Array.from({ length: 14 }, (_, i) => `git zz${i}`).join('; ');
    assert.equal(mg.classify(sh(many), { cwd: repo }).guard, true);
    assert.equal(mg.classify(sh('git zz1; git zz2'), { cwd: repo }).guard, false);
  });
});

describe('MCP classification tightening', () => {
  const c = (name, args = {}) => mg.classifyTool(name, args);
  it('only the generic API caller gets API semantics; names merely containing "api" do not', () => {
    assert.equal(c('mcp__X__create_api_key').readok, false);
    assert.equal(c('mcp__X__get_api_docs').readok, true);
    assert.equal(c('mcp__GitLab__glab_api', { args: ['projects/1/merge_requests'] }).readok, true);
  });
  it('Playwright: observation/navigation allowed, evaluate/type/fill/press/upload denied', () => {
    for (const t of ['snapshot', 'navigate', 'click', 'take_screenshot', 'network_requests', 'console_messages', 'wait_for', 'navigate_back', 'tabs']) {
      assert.equal(c(`mcp__Playwright__browser_${t}`).readok, true, t);
    }
    for (const t of ['evaluate', 'type', 'fill_form', 'press_key', 'select_option', 'run_code_unsafe', 'file_upload', 'drop', 'drag']) {
      assert.equal(c(`mcp__Playwright__browser_${t}`).readok, false, t);
    }
  });
  it('glab_api writes: commits to main / no branch / opaque target are guarded, feature branch is not', () => {
    const api = (flags, args = ['projects/1/repository/commits']) => c('mcp__GitLab__glab_api', { args, flags }).guard;
    assert.equal(api({ method: 'POST', field: 'branch=main' }), true);
    assert.equal(api({ method: 'POST' }), true);
    assert.equal(api({ method: 'POST', field: 'branch=feat' }), false);
    assert.equal(api('-X POST', '$URL'), true);
  });
});

describe('git-<sub> programs on PATH (external subcommands)', () => {
  it('an executable git-<name> on PATH is guarded; git-lfs and unknown names are not', () => {
    const bindir = fs.mkdtempSync(path.join(os.tmpdir(), 'mg-bin-'));
    const savedPath = process.env.PATH;
    try {
      fs.writeFileSync(path.join(bindir, 'git-m'), '#!/bin/sh\nexec git merge "$@"\n', { mode: 0o755 });
      fs.writeFileSync(path.join(bindir, 'git-lfs'), '#!/bin/sh\nexit 0\n', { mode: 0o755 });
      process.env.PATH = `${bindir}:${savedPath}`;
      assert.equal(mg.classify(sh('git m x'), { cwd: repo }).guard, true);
      assert.equal(mg.classify(sh('git lfs ls-files'), { cwd: repo }).guard, false);
      assert.equal(mg.classify(sh('git zzz'), { cwd: repo }).guard, false);
    } finally {
      process.env.PATH = savedPath;
      fs.rmSync(bindir, { recursive: true, force: true });
    }
  });
});
