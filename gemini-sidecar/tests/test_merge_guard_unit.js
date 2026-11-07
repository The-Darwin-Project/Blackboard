// gemini-sidecar/tests/test_merge_guard_unit.js
// @ai-rules:
// 1. [Constraint]: Test-only file -- unit coverage for hooks/merge-guard.js reliability properties that the
//    bash suite cannot reach: fail-closed on UNKNOWN git state (budget exhausted, spawn cap, bad cwd) and
//    the Claude-path child-process classifier.
// 2. [Pattern]: classify(payload, {budgetMs: -1}) simulates an exhausted budget (deadline already passed).
// 3. [Coverage]: VMER-2271 category differentiation -- table-driven git_merge / operational / null classification
//    (find -exec accumulation, valued-flag + dynamic-verb bypass, read allowlist negatives, wrappers, mixed categories,
//    MCP tools), quote-aware array assignment vs quote-UNAWARE heredoc bodies, strict boolean `approved`.
//    Command strings are only CLASSIFIED here, never executed.
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

describe('operational mutations and dynamic binary classification', () => {
  it('dynamic binary word fails closed unconditionally to git_merge', () => {
    const res = mg.classify(sh('$CMD origin main'), { cwd: repo });
    assert.equal(res.guard, true);
    assert.equal(res.guardCategory, 'git_merge');
  });

  it('operational mutations with flags and verbs are classified as operational', () => {
    const commands = [
      'kubectl -l app=test delete pods',
      'kubectl --kubeconfig /path/config delete pods',
      'kubectl exec -it mypod -- sh',
      'helm delete my-release',
      'kargo stage promote --freight v1',
      'tkn pipeline start mypipe',
      'tkn pr create --from mypipe',
    ];
    for (const cmd of commands) {
      const res = mg.classify(sh(cmd), { cwd: repo });
      assert.equal(res.guard, true, `expected guard=true for: ${cmd}`);
      assert.equal(res.guardCategory, 'operational', `expected guardCategory=operational for: ${cmd}`);
    }
  });

  it('read-only rollout subcommands are NOT classified as operational mutations', () => {
    for (const cmd of ['kubectl rollout status deploy/x', 'kubectl rollout history deploy/x', 'oc rollout status deploy/x']) {
      const res = mg.classify(sh(cmd), { cwd: repo });
      assert.equal(res.guard, false, `expected guard=false for read-only rollout: ${cmd}`);
    }
  });
});


// ---------------------------------------------------------------------------------------------
// VMER-2271 remediation: category differentiation, table-driven
// ---------------------------------------------------------------------------------------------
const cat = (cmd) => mg.classify(sh(cmd), { cwd: repo }).guardCategory;
const table = (rows) => rows.forEach(([cmd, want]) => assert.equal(cat(cmd), want, `${JSON.stringify(cmd)} => expected ${want}`));

describe('find -exec accumulates categories across clauses (no downgrade git_merge -> operational)', () => {
  it('git_merge wins regardless of clause order', () => table([
    ['find . -exec oc rsh x \\; -exec git merge origin/main \\;', 'git_merge'],
    ['find . -exec git merge origin/main \\; -exec oc rsh x \\;', 'git_merge'],
    ['find . -exec oc rsh x \\; -exec gh pr merge 5 \\;', 'git_merge'],
    ['find . -exec kargo promote --stage s \\; -exec git push origin main \\;', 'git_merge'],
    ['find . -execdir oc rsh x \\; -execdir git merge m \\;', 'git_merge'],
    ['find . -ok oc rsh x \\; -okdir git merge m \\;', 'git_merge'],
    ['find . -exec oc rsh x \\; -exec echo hi \\; -exec glab mr merge 5 \\;', 'git_merge'],
  ]));
  it('operational-only and clean find stay what they are', () => table([
    ['find . -exec oc rsh x \\; -exec kubectl delete pod y \\;', 'operational'],
    ['find . -exec oc rsh x \\;', 'operational'],
    ['find . -name x -exec grep y {} +', null],
    ['find . -exec echo hi \\; -exec ls \\;', null],
  ]));
});

describe('operational classifier: value-taking flags cannot hide the verb', () => {
  it('unlisted valued flags before the verb', () => table([
    ['kubectl -v 6 exec -it prodpod -- /bin/sh', 'operational'],
    ['kubectl -v 5 apply -f x', 'operational'],
    ['kubectl --request-timeout 5s delete pod x', 'operational'],
    ['kubectl --request-timeout=5s delete pod x', 'operational'],
    ['kubectl --some-unknown-flag 7 delete pod x', 'operational'],
    ['kargo --config-path /x promote --stage s', 'operational'],
    ['oc --loglevel 8 rsh x', 'operational'],
    ['helm --kube-context c upgrade r c', 'operational'],
    ['argocd --argocd-context ctx app sync a', 'operational'],
    ['kubectl --boolflag exec pod -- sh', 'operational'], // boolean unknown flag followed by a verb-looking word
    ['kubectl --boolflag unknownverb pod -- get x', 'operational'],
    ['kubectl --foo bar exec pod -- get x', 'operational'], // a trailing read verb after `--` is the REMOTE command
  ]));
  it('the same flags in front of a READ verb stay unguarded', () => table([
    ['kubectl -v 6 get pods', null],
    ['kubectl --request-timeout 5s get pods', null],
    ['kubectl --request-timeout=5s get pods', null],
    ['kubectl -n foo --context bar describe pod x', null],
    ['kargo --config-path /x get stages', null],
    ['helm --kube-context c list', null],
  ]));
});

describe('operational classifier: dynamic verbs fail closed', () => {
  it('dynamic verb / sub-verb / "$@" on an operational binary is guarded', () => table([
    ['kubectl $VERB pod x', 'operational'],
    ['kubectl "$@"', 'operational'],
    ['oc $ACTION deploy/x', 'operational'],
    ['helm $ACT r c', 'operational'],
    ['kargo $V --stage s', 'operational'],
    ['argocd app $V a', 'operational'],
    ['tkn pr $V x', 'operational'],
    ['kubectl rollout $ACT deploy/x', 'operational'],
    ['kubectl --some-flag $LVL get pods', 'operational'], // dynamic value after an UNKNOWN flag is kept as a verb candidate
    ['kubectl -v $LVL get pods', null], // -v is a known valued flag: its value is consumed
  ]));
  it('a dynamic ARGUMENT after a read verb is not a dynamic verb', () => table([
    ['kubectl get pods "$POD"', null],
    ['kubectl -n "$NS" get pods', null],
    ['kubectl logs "$POD" --tail=50', null],
    ['helm status "$REL"', null],
  ]));
});

describe('operational classifier: read allowlist (mutating verbs missing from the old denylist)', () => {
  it('kubectl / oc', () => table([
    ['kubectl label pod x a=b', 'operational'], ['kubectl annotate pod x a=b', 'operational'],
    ['kubectl set image deploy/x c=img', 'operational'], ['kubectl taint nodes n k=v:NoSchedule', 'operational'],
    ['kubectl drain n', 'operational'], ['kubectl cordon n', 'operational'], ['kubectl uncordon n', 'operational'],
    ['kubectl debug pod/x -it', 'operational'], ['kubectl expose deploy x --port 80', 'operational'],
    ['kubectl autoscale deploy x --max 3', 'operational'], ['kubectl replace -f x', 'operational'],
    ['kubectl adm x', 'operational'], ['kubectl certificate approve csr', 'operational'],
    ['kubectl auth reconcile -f x', 'operational'], ['kubectl rollout restart deploy/x', 'operational'],
    ['kubectl rollout undo deploy/x', 'operational'], ['kubectl cp a pod:/b', 'operational'],
    ['kubectl port-forward pod/x 8080', 'operational'], ['kubectl attach pod', 'operational'], ['kubectl run x --image i', 'operational'],
    ['oc adm drain n', 'operational'], ['oc adm policy add-role-to-user x y', 'operational'], ['oc start-build x', 'operational'],
    ['oc new-app x', 'operational'], ['oc tag a b', 'operational'], ['oc rollback dc/x', 'operational'], ['oc rsh pod', 'operational'],
    ['oc debug node/n', 'operational'],
  ]));
  it('kargo / argocd / helm / tkn', () => table([
    ['kargo approve --freight x', 'operational'], ['kargo create project x', 'operational'], ['kargo delete stage x', 'operational'],
    ['kargo apply -f x', 'operational'], ['kargo refresh warehouse w', 'operational'], ['kargo abort promotion p', 'operational'],
    ['kargo update x', 'operational'], ['kargo promote --stage s', 'operational'], ['kargo verify --stage s', 'operational'],
    ['argocd app rollback a 1', 'operational'], ['argocd app patch a', 'operational'], ['argocd app terminate-op a', 'operational'],
    ['argocd app actions run a restart', 'operational'], ['argocd app create a', 'operational'], ['argocd app set a', 'operational'],
    ['argocd app unset a', 'operational'], ['argocd app sync a', 'operational'], ['argocd app delete a', 'operational'],
    ['argocd appset create x', 'operational'], ['argocd proj create x', 'operational'], ['argocd repo add x', 'operational'], ['argocd cluster rm x', 'operational'],
    ['helm install r c', 'operational'], ['helm upgrade r c', 'operational'], ['helm rollback r 1', 'operational'], ['helm uninstall r', 'operational'],
    ['helm repo add x y', 'operational'], ['helm plugin install x', 'operational'],
    ['tkn pipeline start p', 'operational'], ['tkn pr delete x', 'operational'], ['tkn pr cancel x', 'operational'], ['tkn pipeline rerun x', 'operational'],
    ['tkn pipelinerun rerun x', 'operational'], ['tkn taskrun delete x', 'operational'], ['tkn clustertask delete x', 'operational'],
  ]));
  it('read-only subcommands remain unguarded', () => table([
    ['kubectl get pods -A', null], ['kubectl describe pod x', null], ['kubectl logs x -f', null], ['kubectl top pods', null],
    ['kubectl explain pod', null], ['kubectl version', null], ['kubectl diff -f x', null], ['kubectl events', null],
    ['kubectl rollout status deploy/x', null], ['kubectl rollout history deploy/x', null], ['oc get pods', null], ['oc whoami', null],
    ['helm list', null], ['helm ls -A', null], ['helm status r', null], ['helm get values r', null], ['helm history r', null],
    ['helm show chart c', null], ['helm template r c', null], ['helm lint c', null],
    ['argocd app get a', null], ['argocd app list', null], ['argocd app diff a', null], ['argocd app history a', null],
    ['argocd app manifests a', null], ['argocd app logs a', null],
    ['kargo get stages', null], ['kargo get promotions -p x', null], ['kargo list', null],
    ['tkn pr list', null], ['tkn pipelinerun ls', null], ['tkn pr describe x', null], ['tkn pr logs x -f', null], ['tkn task list', null],
    ['kubectl --help', null], ['kubectl -h', null], ['kubectl --version', null], ['helm --help', null], ['kubectl', null],
    ['kubectl delete pod x --help', null], ['argocd app sync a -h', null],
  ]));
  it('`--help` after the `--` separator belongs to the remote command, not kubectl', () => table([
    ['kubectl exec pod -- ls --help', 'operational'],
    ['kubectl exec pod -- sh -h', 'operational'],
  ]));
  it('bare kubectl exec payload after `--` is not analyzed (documented: runs in the pod)', () => {
    assert.equal(cat('kubectl exec pod -- git merge x'), 'operational');
  });
});

describe('operational classifier: wrappers, paths, pipelines and mixed categories', () => {
  it('wrappers and absolute paths do not hide operational commands', () => table([
    ['sudo kubectl delete pod x', 'operational'], ['env FOO=1 kubectl apply -f x', 'operational'],
    ['/usr/local/bin/kubectl delete pod x', 'operational'], ['KUBECTL delete pod x', 'operational'],
    ['timeout 5 kubectl delete pod x', 'operational'], ['xargs kubectl delete pod', 'operational'],
    ['bash -c "kubectl delete pod x"', 'operational'], ['echo $(kubectl delete pod x)', 'operational'],
    ['nohup helm upgrade r c', 'operational'], ['sudo kubectl get pods', null],
  ]));
  it('git_merge always wins over operational in lists, pipes and nesting (both orders)', () => table([
    ['kubectl delete pod x && git merge origin/main', 'git_merge'],
    ['git merge origin/main && kubectl delete pod x', 'git_merge'],
    ['kubectl delete pod x; gh pr merge 5', 'git_merge'],
    ['kubectl get pods | xargs git merge', 'git_merge'],
    ['bash -c "kargo promote --stage s; git push origin main"', 'git_merge'],
    ['echo $(kubectl delete pod x) $(git merge m)', 'git_merge'],
  ]));
  it('a mixed command with an operational part and a read-only part is operational', () => table([
    ['kubectl get pods && kubectl delete pod x', 'operational'],
    ['kubectl get pods | grep x', null],
  ]));
});

describe('dynamic command word: test builtins are not dynamic words', () => {
  it('`[` and `[[` do not escalate; eval and $VAR command words still do', () => table([
    ['[ -f x ] && echo y', null], ['[[ -f x ]] && echo y', null], ['[ -d "$D" ] || echo no', null],
    ['eval "git status"', 'git_merge'], ['eval "$CMD"', 'git_merge'], ['$CMD origin main', 'git_merge'],
    ['$PYTHON -m pytest tests', 'git_merge'], ['eval "$(ssh-agent -s)"', 'git_merge'],
    ['[ -f x ] && git merge main', 'git_merge'], ['[[ $(git merge main) ]]', 'git_merge'],
  ]));
});

describe('bodySubstitutions: quote-aware for array assignment, quote-UNAWARE for heredoc bodies', () => {
  it("single-quoted `$(...)` in an array assignment is literal", () => table([
    ["arr=('$(git merge main)')", null],
    ["arr=('`git merge main`' 'b')", null],
    ["arr=('$(git merge main)' \"x\")", null],
  ]));
  it('double-quoted, unquoted and mixed array elements still run substitutions', () => table([
    ['arr=("$(git merge main)")', 'git_merge'],
    ['arr=($(git merge main))', 'git_merge'],
    ['arr=(`git merge main`)', 'git_merge'],
    ["arr=('a' \"$(git merge main)\")", 'git_merge'],
    ['arr=("it\'s" $(git merge main))', 'git_merge'], // a ' inside "..." must not open a single-quoted span
    ['arr=([k]=<(git merge main))', 'git_merge'],
  ]));
  it('an unterminated single quote inside the array body fails closed', () => {
    assert.equal(cat("arr=('$(git merge main)"), 'git_merge');
  });
  it("heredoc bodies stay quote-unaware: a single quote there is literal and $( ) still runs", () => table([
    ["cat <<EOF\n'$(git merge main)'\nEOF", 'git_merge'],
    ['cat <<EOF\n$(git merge main)\nEOF', 'git_merge'],
    ["cat <<'EOF'\n$(git merge main)\nEOF", null], // quoted delimiter: body is literal text
  ]));
});

describe('MCP / non-shell tools carry their real category', () => {
  const tool = (name, input = {}) => mg.classify({ tool_name: name, tool_input: input });
  it('cluster / ArgoCD / Kargo / Helm mutating tools are operational (guard=true, readok=false)', () => {
    for (const n of ['mcp__ArgoCD__sync_application', 'mcp__ArgoCD__delete_application', 'mcp__ArgoCD__create_application',
      'mcp__ArgoCD__update_application', 'mcp__ArgoCD__run_resource_action', 'mcp__K8s_konflux__pods_delete',
      'mcp__K8s_konflux__pods_exec', 'mcp__K8s_konflux__resources_create_or_update', 'mcp__Kargo__promote_freight',
      'mcp__Helm__install_release', 'sync_application']) {
      const r = tool(n);
      assert.equal(r.guard, true, n);
      assert.equal(r.guardCategory, 'operational', n);
      assert.equal(r.readok, false, n);
    }
  });
  it('read-only tools of the same servers stay unguarded and read-ok', () => {
    for (const n of ['mcp__ArgoCD__get_application', 'mcp__ArgoCD__list_applications', 'mcp__ArgoCD__get_application_workload_logs',
      'mcp__ArgoCD__get_resource_events', 'mcp__ArgoCD__get_resource_actions', 'mcp__K8s_konflux__pods_list', 'mcp__K8s_konflux__pods_log',
      'mcp__K8s_konflux__events_list', 'mcp__KubeArchive_konflux__ka_get_log', 'mcp__KubeArchive_konflux__ka_list_pipelineruns']) {
      const r = tool(n);
      assert.equal(r.guard, false, n);
      assert.equal(r.guardCategory, null, n);
      assert.equal(r.readok, true, n);
    }
  });
  it('VCS merge / default-branch write tools are git_merge', () => {
    for (const [n, input] of [['mcp__GitHub__merge_pull_request', {}], ['mcp__GitLab__glab_mr_merge', {}], ['mcp__GitHub__push_files', { branch: 'main' }],
      ['mcp__GitHub__create_or_update_file', { branch: 'main' }], ['mcp__GitHub__create_or_update_file', {}]]) {
      const r = tool(n, input);
      assert.equal(r.guard, true, n);
      assert.equal(r.guardCategory, 'git_merge', n);
    }
  });
  it('unrelated tools are not guarded (no category leakage)', () => {
    for (const n of ['mcp__GitHub__issue_write', 'mcp__GitHub__add_issue_comment', 'mcp__Jenkins__jenkins_get_build_status', 'mcp__DarwinBlackboard__bb_update_plan_step',
      'mcp__TeamChat__team_send_results', 'mcp__Playwright__browser_click', 'Read', 'Write']) {
      const r = tool(n, { branch: 'feat' });
      assert.equal(r.guard, false, n);
      assert.equal(r.guardCategory, null, n);
    }
  });
  it('classifyTool exposes guardCategory directly; classify() returns it instead of hardcoding git_merge', () => {
    assert.equal(mg.classifyTool('mcp__ArgoCD__sync_application', {}).guardCategory, 'operational');
    assert.equal(mg.classifyTool('mcp__GitHub__merge_pull_request', {}).guardCategory, 'git_merge');
    assert.equal(mg.classifyTool('mcp__ArgoCD__get_application', {}).guardCategory, null);
  });
  it('a tool name containing ||| is malformed (it would shift the delimited hook fields)', () => {
    assert.equal(mg.classify({ tool_name: 'x|||0|||1|||y', tool_input: {} }), null);
  });
});

describe('approvalVerdict: strict boolean approved, category-specific reasons', () => {
  const SHA = 'a'.repeat(40);
  it('truthy non-booleans are rejected for BOTH categories', () => {
    for (const approved of ['false', 'true', 1, 'yes', {}, [], 'x']) {
      for (const category of ['git_merge', 'operational']) {
        const v = mg.approvalVerdict({ approved, approved_mr_sha: SHA }, SHA, category);
        assert.equal(v.allow, false, `approved=${JSON.stringify(approved)} category=${category}`);
      }
    }
  });
  it('only boolean true is accepted; missing/null/false/non-object approval is rejected', () => {
    assert.equal(mg.approvalVerdict({ approved: true, approved_mr_sha: SHA }, SHA, 'git_merge').allow, true);
    assert.equal(mg.approvalVerdict({ approved: true }, '', 'operational').allow, true);
    for (const a of [null, undefined, {}, { approved: false }, { approved: null }, 'approved', 1, []]) {
      assert.equal(mg.approvalVerdict(a, SHA, 'git_merge').allow, false, JSON.stringify(a));
      assert.equal(mg.approvalVerdict(a, '', 'operational').allow, false, JSON.stringify(a));
    }
  });
  it('git_merge keeps the SHA binding; operational ignores the SHA entirely', () => {
    assert.equal(mg.approvalVerdict({ approved: true, approved_mr_sha: SHA }, 'b'.repeat(40), 'git_merge').allow, false);
    assert.equal(mg.approvalVerdict({ approved: true, approved_mr_sha: null }, SHA, 'git_merge').allow, false);
    assert.equal(mg.approvalVerdict({ approved: true, approved_mr_sha: SHA }, '', 'git_merge').allow, false);
    assert.equal(mg.approvalVerdict({ approved: true, approved_mr_sha: null }, null, 'operational').allow, true);
    assert.equal(mg.approvalVerdict({ approved: true, approved_mr_sha: SHA }, 'b'.repeat(40), 'operational').allow, true);
  });
  it('only the exact string "operational" relaxes the SHA rule', () => {
    for (const c of ['OPERATIONAL', 'Operational', ' operational', '', undefined, null, 'ops', 'git_merge']) {
      const v = mg.approvalVerdict({ approved: true, approved_mr_sha: null }, '', c); // undefined => default 'git_merge'
      assert.equal(v.allow, false, `category=${JSON.stringify(c)}`);
    }
  });
  it('reason wording: git_merge says Merge REFUSED, operational says Operational mutation REFUSED', () => {
    assert.match(mg.approvalVerdict({ approved: false }, SHA, 'git_merge').reason, /^Merge REFUSED/);
    assert.match(mg.approvalVerdict({ approved: false }, '', 'operational').reason, /^Operational mutation REFUSED/);
  });
});
