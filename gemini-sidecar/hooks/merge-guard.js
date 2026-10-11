#!/usr/bin/env node
// gemini-sidecar/hooks/merge-guard.js
// @ai-rules:
// 1. [Pattern]: Classifier helper for validate-mutations.sh. Reads the PreToolUse JSON on stdin and prints
//    ONE line: `OK|||<tool>|||<guard 0|1>|||<readok 0|1>|||<shell command>` or `__MALFORMED__`.
//    guard=1  -> the call can merge / write to a default branch; it MUST pass the out-of-band approval check.
//    readok=1 -> non-shell tool that is read-only / comms (the only MCP tools read-only roles may call).
// 2. [Contract]: Fail-CLOSED. Any exception, unparseable shape or excessive shell nesting => guard=1 or
//    __MALFORMED__ (the shell wrapper denies). Never print anything else to stdout.
// 3. [Constraint]: Shell commands are TOKENIZED (quotes, escapes, ;&|, $(..), backticks, bash -c, eval,
//    env/sudo/xargs/find -exec wrappers, binary basename) -- not regex-matched -- so global options,
//    quoting and wrappers cannot hide `git merge|push`, `gh pr merge`, `glab mr merge`, or non-GET
//    curl/wget/gh api/glab api calls against merge endpoints.
// 4. [Gotcha]: Still defense-in-depth, not a sandbox: it cannot see inside scripts (`sh x.sh`), `python -c`,
//    `curl -d @file`, or values resolved at runtime ($VAR as a command word is treated as suspicious only
//    when merge/push appears among the arguments).
// 5. [Pattern]: MCP tools are classified by NAME TOKENS (camelCase + snake_case split), so `mergePullRequest`,
//    `merge_pull_request` and `glab_mr_merge` all yield the verb `merge`; `merge_request` (the noun) does not.
//    The read-only allowlist is verb-based -- extend READ/SAFE sets here, or set HOOK_EXTRA_ALLOWED_TOOLS in
//    validate-mutations.sh's env, rather than loosening the shell wrapper.
'use strict';
const { execFileSync } = require('child_process');

const PROTECTED = new Set(['main', 'master']);
const SHELLS = new Set(['bash', 'sh', 'zsh', 'dash', 'ksh', 'ash']);
const HTTP_CLIENTS = new Set(['curl', 'wget', 'http', 'https', 'xh', 'xhs']);
const MAX_DEPTH = 4;

// ---------------------------------------------------------------------------------------------
// Shell tokenizer
// ---------------------------------------------------------------------------------------------
// Returns { cmds: string[][], nested: string[] }. `nested` holds the bodies of $(...), `...`, <(...), >(...)
// so they can be analyzed as commands of their own.
function parseShell(str) {
  const cmds = [];
  const nested = [];
  let tokens = [];
  let cur = '';
  let has = false; // a token is in progress (so '' counts as a token)
  const pushTok = () => { if (has) { tokens.push(cur); } cur = ''; has = false; };
  const pushCmd = () => { pushTok(); if (tokens.length) cmds.push(tokens); tokens = []; };
  const n = str.length;
  let i = 0;

  const grabParen = (start) => { // start points just after '('
    let depth = 1; let j = start;
    while (j < n && depth > 0) {
      const c = str[j];
      if (c === '\\') { j += 2; continue; }
      if (c === '(') depth++;
      else if (c === ')') depth--;
      j++;
    }
    nested.push(str.slice(start, depth === 0 ? j - 1 : j));
    return j;
  };

  while (i < n) {
    const c = str[i];
    if (c === '\\') {
      if (str[i + 1] === '\n') { i += 2; continue; }
      cur += str[i + 1] ?? ''; has = true; i += 2; continue;
    }
    if (c === "'") {
      const j = str.indexOf("'", i + 1);
      const end = j === -1 ? n : j;
      cur += str.slice(i + 1, end); has = true; i = end + 1; continue;
    }
    if (c === '"') {
      i++; has = true;
      while (i < n && str[i] !== '"') {
        if (str[i] === '\\' && i + 1 < n) { cur += str[i + 1]; i += 2; continue; }
        if (str[i] === '$' && str[i + 1] === '(') { i = grabParen(i + 2); cur += '$SUBST'; continue; }
        if (str[i] === '`') {
          const j = str.indexOf('`', i + 1); const end = j === -1 ? n : j;
          nested.push(str.slice(i + 1, end)); cur += '$SUBST'; i = end + 1; continue;
        }
        cur += str[i]; i++;
      }
      i++; continue;
    }
    if (c === '$' && str[i + 1] === '(') { i = grabParen(i + 2); cur += '$SUBST'; has = true; continue; }
    if ((c === '<' || c === '>') && str[i + 1] === '(') { i = grabParen(i + 2); cur += '$SUBST'; has = true; continue; }
    if (c === '`') {
      const j = str.indexOf('`', i + 1); const end = j === -1 ? n : j;
      nested.push(str.slice(i + 1, end)); cur += '$SUBST'; has = true; i = end + 1; continue;
    }
    if (c === ';' || c === '&' || c === '|' || c === '\n' || c === '(' || c === ')') {
      // `>&` / `2>&1` / `&>` are redirections, not command separators
      if (c === '&' && (/[<>]$/.test(cur) || str[i + 1] === '>')) { cur += c; has = true; i++; continue; }
      pushCmd(); i++; continue;
    }
    if (c === ' ' || c === '\t' || c === '\r') { pushTok(); i++; continue; }
    cur += c; has = true; i++;
  }
  pushCmd();

  // Drop redirections (`> file`, `2>/dev/null`, `<<EOF`) so they don't pollute positional parsing.
  const cleaned = cmds.map((toks) => {
    const out = [];
    for (let k = 0; k < toks.length; k++) {
      const t = toks[k];
      if (/^\d*(>>?|<<?<?|>&|<&|&>>?)/.test(t)) {
        if (/^\d*(>>?|<<?<?|>&|<&|&>>?)$/.test(t)) k++; // bare operator: next token is its target
        continue;
      }
      out.push(t);
    }
    return out;
  }).filter((t) => t.length);
  return { cmds: cleaned, nested };
}

const base = (p) => p.replace(/\/+$/, '').split('/').pop();
const isAssign = (t) => /^[A-Za-z_][A-Za-z0-9_]*=/.test(t);

// Wrapper commands that merely run another command: option set (with values) and leading positionals.
const WRAP = {
  env: { valued: new Set(['-u', '--unset', '-C', '--chdir']), pos: 0 },
  command: { valued: new Set(), pos: 0 },
  builtin: { valued: new Set(), pos: 0 },
  exec: { valued: new Set(['-a']), pos: 0 },
  sudo: { valued: new Set(['-u', '-g', '-h', '-p', '-C', '-D', '-R', '-T', '-U', '-r', '-t']), pos: 0 },
  doas: { valued: new Set(['-u', '-C']), pos: 0 },
  nice: { valued: new Set(['-n']), pos: 0 },
  nohup: { valued: new Set(), pos: 0 },
  time: { valued: new Set(['-f', '-o']), pos: 0 },
  timeout: { valued: new Set(['-k', '-s', '--kill-after', '--signal']), pos: 1 },
  stdbuf: { valued: new Set(['-i', '-o', '-e']), pos: 0 },
  setsid: { valued: new Set(), pos: 0 },
  xargs: { valued: new Set(['-I', '-n', '-P', '-d', '-L', '-s', '-E', '-a', '-l']), pos: 0 },
  // shell keywords that can precede a command word
  if: { valued: new Set(), pos: 0 }, then: { valued: new Set(), pos: 0 }, do: { valued: new Set(), pos: 0 },
  else: { valued: new Set(), pos: 0 }, elif: { valued: new Set(), pos: 0 }, while: { valued: new Set(), pos: 0 },
  until: { valued: new Set(), pos: 0 }, '!': { valued: new Set(), pos: 0 }, '{': { valued: new Set(), pos: 0 },
};

function stripPrefix(tokens) {
  const t = tokens.slice();
  for (;;) {
    while (t.length && isAssign(t[0])) t.shift();
    if (!t.length) return t;
    const b = base(t[0]).toLowerCase();
    if (!Object.prototype.hasOwnProperty.call(WRAP, b)) return t;
    const spec = WRAP[b];
    t.shift();
    while (t.length) {
      const x = t[0];
      if (b === 'env' && isAssign(x)) { t.shift(); continue; }
      if (x.startsWith('-') && x.length > 1) {
        t.shift();
        if (spec.valued.has(x) && t.length) t.shift();
        continue;
      }
      break;
    }
    for (let k = 0; k < spec.pos && t.length; k++) t.shift();
  }
}

// ---------------------------------------------------------------------------------------------
// git / gh / glab / http-client analysis
// ---------------------------------------------------------------------------------------------
function gitOut(args) {
  try {
    return execFileSync('git', args, { encoding: 'utf8', timeout: 1000, stdio: ['ignore', 'pipe', 'ignore'] }).trim();
  } catch { return null; }
}

const normRef = (r) => r.trim().replace(/^\+/, '').replace(/^refs\/heads\//, '').toLowerCase();
const isProtected = (r) => PROTECTED.has(normRef(r));

function bareBranchProtected(hasDirOverride) {
  if (hasDirOverride) return true; // -C/--git-dir: cwd's repo state is not the target's
  const br = gitOut(['rev-parse', '--abbrev-ref', 'HEAD']);
  if (br === null || br === 'HEAD' || isProtected(br)) return true; // unknown/detached => fail closed
  const pd = (gitOut(['config', '--get', 'push.default']) || 'simple').toLowerCase();
  if (pd === 'matching') return true;
  if (pd === 'upstream' || pd === 'tracking') {
    const m = gitOut(['config', '--get', `branch.${br}.merge`]);
    if (!m || isProtected(m)) return true;
  }
  const rp = gitOut(['config', '--get-regexp', '^remote\\..*\\.push$']);
  if (rp) {
    for (const line of rp.split('\n')) {
      // HEAD-style values resolve to the current branch, already checked above
      if (refspecNamesProtected(line.split(/\s+/).slice(1).join(' '))) return true;
    }
  }
  return false;
}

// Static check of a refspec's destination (no git lookups, so no recursion).
function refspecNamesProtected(rs) {
  if (/[$`*{]/.test(rs)) return true; // dynamic or glob refspec: cannot prove it avoids main
  const spec = rs.replace(/^\+/, '');
  const idx = spec.lastIndexOf(':');
  const src = idx === -1 ? spec : spec.slice(0, idx);
  const dst = idx === -1 ? '' : spec.slice(idx + 1);
  return isProtected(dst || src);
}

function refspecProtected(rs, hasDirOverride) {
  if (refspecNamesProtected(rs)) return true;
  const spec = rs.replace(/^\+/, '');
  const idx = spec.lastIndexOf(':');
  const target = (idx === -1 ? spec : spec.slice(idx + 1) || spec.slice(0, idx));
  if (target === 'HEAD' || target === '@') return bareBranchProtected(hasDirOverride);
  return false;
}

function pushGuard(args, hasDirOverride) {
  const pos = [];
  let repoOpt = false;
  let tags = false;
  for (let i = 0; i < args.length; i++) {
    const a = args[i];
    if (a === '--') { pos.push(...args.slice(i + 1)); break; }
    if (a === '--all' || a === '--mirror') return true;
    if (a === '--tags') { tags = true; continue; }
    if (a === '--repo') { repoOpt = true; i++; continue; }
    if (a.startsWith('--repo=')) { repoOpt = true; continue; }
    if (a === '-o' || a === '--push-option' || a === '--receive-pack' || a === '--exec') { i++; continue; }
    if (a.startsWith('-')) continue;
    pos.push(a);
  }
  const refspecs = repoOpt ? pos : pos.slice(1);
  if (refspecs.length === 0) return tags ? false : bareBranchProtected(hasDirOverride);
  return refspecs.some((rs) => refspecProtected(rs, hasDirOverride));
}

const GIT_BUILTINS = new Set(['status', 'log', 'diff', 'commit', 'add', 'checkout', 'switch', 'branch', 'fetch', 'pull',
  'clone', 'rev-parse', 'show', 'config', 'remote', 'stash', 'rebase', 'reset', 'tag', 'cherry-pick', 'blame', 'grep',
  'ls-files', 'ls-tree', 'describe', 'cat-file', 'worktree', 'apply', 'am', 'restore', 'mv', 'rm', 'clean', 'init',
  'submodule', 'bisect', 'reflog', 'shortlog', 'format-patch', 'merge-base', 'rev-list', 'symbolic-ref',
  'for-each-ref', 'show-ref', 'diff-tree', 'update-ref', 'version', 'help', 'archive', 'gc', 'fsck', 'notes', 'bundle']);

function gitGuard(args, depth) {
  let i = 0;
  let dirOverride = false;
  while (i < args.length && args[i].startsWith('-')) {
    const a = args[i];
    if (a === '-C' || a === '--git-dir' || a === '--work-tree') { dirOverride = true; i += 2; continue; }
    if (a === '-c' || a === '--config-env') {
      if (/^alias\./i.test(args[i + 1] || '')) return true; // inline alias injection
      i += 2; continue;
    }
    if (a === '--namespace' || a === '--super-prefix' || a === '--attr-source') { i += 2; continue; }
    if (/^--(git-dir|work-tree)=/.test(a)) dirOverride = true;
    if (/^--config-env=alias\./i.test(a)) return true;
    i++;
  }
  const sub = (args[i] || '').toLowerCase();
  const rest = args.slice(i + 1);
  if (sub === 'merge') return true;
  if (sub === 'push') return pushGuard(rest, dirOverride);
  if (sub && !GIT_BUILTINS.has(sub) && depth < MAX_DEPTH) {
    const alias = gitOut(['config', '--get', `alias.${args[i]}`]);
    if (alias) {
      if (alias.startsWith('!')) return analyzeString(alias.slice(1) + ' ' + rest.join(' '), depth + 1);
      return gitGuard(parseShell(alias).cmds.flat().concat(rest), depth + 1);
    }
  }
  return false;
}

// Positional tokens of gh/glab, skipping the values of flags that take one.
const API_VALUED = new Set(['-R', '--repo', '--hostname', '-H', '--header', '-X', '--method', '-f', '--raw-field', '-F',
  '--field', '--input', '-q', '--jq', '-t', '--template', '--cache', '-p', '--preview', '-b', '--branch', '--hostname']);
function positionals(args) {
  const out = [];
  for (let i = 0; i < args.length; i++) {
    const a = args[i];
    if (a.startsWith('-')) { if (API_VALUED.has(a)) i++; continue; }
    out.push(a);
  }
  return out;
}
const hasSubseq = (arr, seq) => { let k = 0; for (const x of arr) { if (x.toLowerCase() === seq[k]) k++; if (k === seq.length) return true; } return false; };

const MERGE_ENDPOINT_RE = new RegExp([
  '\\/merges?(?![A-Za-z0-9_-])', '\\/merge-upstream', 'merge_when_pipeline_succeeds', 'mergePullRequest',
  'enablePullRequestAutoMerge', 'mergeBranch', 'merge_pull_request', '\\/auto[-_]?merge', 'git\\/refs\\/heads\\/(main|master)(?![A-Za-z0-9_-])',
].join('|'), 'i');

const BODY_FLAG = {
  curl: /^(-d|--data|--data-[a-z]+|--json|-F|--form|--form-string|-T|--upload-file)(=.*)?$|^-[dFT]./,
  wget: /^--(post-data|post-file|body-data|body-file)(=.*)?$/,
  api: /^(-f|-F|--field|--raw-field|--input)(=.*)?$|^-[fF]./,
};

// Non-GET request whose URL/body references a merge endpoint (or default-branch ref update).
function httpMethod(bin, args) {
  let method = null;
  let body = false;
  let getFlag = false;
  const kind = (bin === 'gh' || bin === 'glab') ? 'api' : (BODY_FLAG[bin] ? bin : null);
  for (let i = 0; i < args.length; i++) {
    const a = args[i];
    if (a === '-X' || a === '--request' || a === '--method') { method = (args[i + 1] || '').toUpperCase(); i++; continue; }
    if (/^--(request|method)=/.test(a)) { method = a.split('=')[1].toUpperCase(); continue; }
    if (bin === 'curl' && /^-X./.test(a)) { method = a.slice(2).toUpperCase(); continue; }
    if (bin === 'curl' && (a === '-G' || a === '--get')) getFlag = true;
    if (kind && BODY_FLAG[kind].test(a)) body = true;
    if (!kind && /^[A-Za-z0-9_.-]+(=|:=|=@|@)/.test(a) && !/[:/]\/|^\//.test(a)) body = true; // httpie items
  }
  if (!method && !kind) { const p = args.find((x) => !x.startsWith('-')); if (p && /^(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)$/i.test(p)) method = p.toUpperCase(); }
  return method || ((body && !getFlag) ? 'POST' : 'GET');
}
const isReadMethod = (m) => m === 'GET' || m === 'HEAD' || m === 'OPTIONS';

function httpGuard(bin, args) {
  if (isReadMethod(httpMethod(bin, args))) return false;
  return MERGE_ENDPOINT_RE.test(args.join(' '));
}

function analyzeTokens(tokens, depth) {
  const t = stripPrefix(tokens);
  if (!t.length) return false;
  const rawBin = t[0];
  const bin = base(rawBin).toLowerCase();
  const rest = t.slice(1);
  if (/[$`]/.test(rawBin)) return rest.some((x) => /^(merge|push)$/i.test(x)); // dynamic command word
  if (SHELLS.has(bin)) {
    const ci = rest.findIndex((x) => /^-[A-Za-z]*c[A-Za-z]*$/.test(x));
    if (ci !== -1 && rest[ci + 1] !== undefined) return analyzeString(rest[ci + 1], depth + 1);
    return false;
  }
  if (bin === 'eval') return analyzeString(rest.join(' '), depth + 1);
  if (bin === 'find') {
    for (let i = 0; i < rest.length; i++) {
      if (/^-(exec|execdir|ok|okdir)$/.test(rest[i])) {
        let j = i + 1; const sub = [];
        while (j < rest.length && rest[j] !== ';' && rest[j] !== '+') sub.push(rest[j++]);
        if (analyzeTokens(sub, depth + 1)) return true;
      }
    }
    return false;
  }
  if (bin === 'git') return gitGuard(rest, depth);
  if (bin === 'gh' || bin === 'glab') {
    const pos = positionals(rest);
    if (hasSubseq(pos, bin === 'gh' ? ['pr', 'merge'] : ['mr', 'merge'])) return true;
    if (pos[0] && pos[0].toLowerCase() === 'api') return httpGuard(bin, rest);
    return false;
  }
  if (HTTP_CLIENTS.has(bin)) return httpGuard(bin, rest);
  return false;
}

function analyzeString(str, depth) {
  if (depth > MAX_DEPTH) return true; // pathological nesting => fail closed
  const { cmds, nested } = parseShell(str);
  for (const c of cmds) if (analyzeTokens(c, depth)) return true;
  for (const nsub of nested) if (analyzeString(nsub, depth + 1)) return true;
  return false;
}

function shellNeedsGuard(cmd) {
  try { return analyzeString(cmd, 0); } catch { return true; }
}

// ---------------------------------------------------------------------------------------------
// MCP / non-shell tool classification (name tokens, not substrings)
// ---------------------------------------------------------------------------------------------
const nameTokens = (name) => name.replace(/([a-z0-9])([A-Z])/g, '$1_$2').toLowerCase().split(/[^a-z0-9]+/).filter(Boolean);
const PREFIX_TOKENS = new Set(['mcp', 'github', 'gitlab', 'glab', 'gh', 'argocd', 'jenkins', 'darwin', 'blackboard', 'journal', 'teamchat', 'playwright', 'kubearchive', 'konflux',
  'git', 'hub', 'lab', 'argo', 'cd', 'k8s', 'kube', 'archive', 'chat']);
const READ_VERBS = new Set(['get', 'list', 'read', 'search', 'view', 'find', 'fetch', 'query', 'show', 'describe', 'status', 'top',
  'log', 'logs', 'events', 'trace', 'diff', 'summary', 'stats', 'lint', 'contributors', 'count', 'compare', 'snapshot']);
const SAFE_TOKENS = new Set(['comment', 'note', 'review', 'reply']); // PR/MR discussion, not code mutation
const HARD_WRITE = new Set(['delete', 'remove', 'merge', 'push', 'revoke', 'destroy', 'drop', 'publish', 'transfer', 'archive', 'fork', 'assign']);
const WRITE = new Set(['create', 'update', 'write', 'set', 'add', 'run', 'sync', 'trigger', 'cancel', 'retry', 'close', 'reopen',
  'approve', 'upload', 'login', 'bootstrap', 'import', 'edit', 'save', 'amend', 'rebase', 'subscribe', 'unsubscribe', 'send',
  'execute', 'exec', 'start', 'stop', 'apply', 'patch', 'scale', 'rollback', 'promote', 'deploy', 'put', 'post', 'commit', 'upsert']);
const FAMILY_TOKENS = new Set(['team', 'bb', 'svc', 'ka']); // comms / blackboard / journal / kubearchive MCPs
const NATIVE_ALLOW = new Set(['task_boundary', 'notify_user', 'browser_subagent']);
// Native file-mutation tools: handled by validate-mutations.sh MUTATION_TOOLS (keep the two lists in sync).
const NATIVE_MUTATION = new Set(['write_to_file', 'replace_file_content', 'multi_replace_file_content', 'edit_file']);

function apiTokens(args) {
  // glab_api MCP shape: { args: ['endpoint'], flags: { method, field, raw_field, input, ... } }
  const toks = [];
  const a = args && typeof args === 'object' ? args : {};
  const f = a.flags && typeof a.flags === 'object' ? a.flags : {};
  if (f.method) toks.push('--method', String(f.method));
  for (const k of ['field', 'raw_field', 'form', 'input']) {
    if (f[k] !== undefined && f[k] !== false) toks.push('--field', ...[].concat(f[k]).map(String));
  }
  if (Array.isArray(a.args)) toks.push(...a.args.map(String));
  return toks;
}

function classifyTool(name, args) {
  if (NATIVE_MUTATION.has(name.toLowerCase())) return { guard: false, readok: false };
  const a = args && typeof args === 'object' ? args : {};
  const tokens = nameTokens(name);
  const set = new Set(tokens);
  const verb = tokens.find((t) => !PREFIX_TOKENS.has(t)) || '';
  const readFirst = READ_VERBS.has(verb);
  let guard = false;

  // merge verb: any `merge` token that is not the noun in "merge request(s)"; `accept` + merge-noun too
  if (!readFirst) {
    for (let i = 0; i < tokens.length; i++) {
      if (/^(auto)?merge[sd]?$/.test(tokens[i]) || tokens[i] === 'automerge') {
        const nextIsRequest = /^requests?$/.test(tokens[i + 1] || '');
        if (!nextIsRequest || set.has('accept')) guard = true;
      }
    }
  }
  // remote file writes: default branch (or unspecified branch) needs approval
  const isFileWrite = (set.has('push') && !readFirst)
    || ((set.has('file') || set.has('files') || set.has('contents')) && [...set].some((t) => WRITE.has(t) || t === 'delete'));
  if (isFileWrite) {
    const br = a.branch ?? a.ref ?? a.target_branch ?? a.base_branch;
    if (typeof br !== 'string' || !br.trim() || isProtected(br)) guard = true;
  }
  // generic API tool (glab_api): non-GET against a merge endpoint
  const isApi = set.has('api');
  let apiRead = false;
  if (isApi) {
    const toks = apiTokens(a);
    const m = httpMethod('glab', toks);
    apiRead = isReadMethod(m);
    if (!apiRead && MERGE_ENDPOINT_RE.test(toks.join(' '))) guard = true;
  }

  // Action tokens: server-name prefixes dropped, and `merge` dropped when it is only the noun
  // ("list_merge_requests") or the call is a read verb.
  const act = tokens.filter((t, i) => !PREFIX_TOKENS.has(t)
    && !(/^(auto)?merge[sd]?$/.test(t) && (readFirst || /^requests?$/.test(tokens[i + 1] || ''))));
  let readok = false;
  if (!guard) {
    if (NATIVE_ALLOW.has(name.toLowerCase())) readok = true;
    else if (isApi) readok = apiRead;
    else if (act.some((t) => HARD_WRITE.has(t))) readok = false;
    else if (tokens.some((t) => FAMILY_TOKENS.has(t))) readok = true;
    else if (set.has('browser')) readok = !['run', 'unsafe', 'upload', 'drop'].some((t) => set.has(t));
    else if (act.some((t) => SAFE_TOKENS.has(t))) readok = true;
    else if (act.some((t) => WRITE.has(t))) readok = false;
    else readok = act.some((t) => READ_VERBS.has(t));
  }
  return { guard, readok };
}

// ---------------------------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------------------------
// Keep in sync with SHELL_TOOLS in validate-mutations.sh.
const SHELL_TOOLS = new Set(['bash', 'shell', 'run_in_terminal', 'execute_command', 'run_shell_command', 'run_command']);

function main(raw) {
  const d = JSON.parse(raw);
  if (!d || typeof d !== 'object' || Array.isArray(d)) return '__MALFORMED__';
  let name = d.toolCall?.name || d.tool_name || d.functionCall?.name || '';
  if (!name || typeof name !== 'string') return '__MALFORMED__';
  name = name.trim();
  const rawCmd = d.toolCall?.args?.CommandLine ?? d.toolCall?.args?.command ?? (d.tool_input && d.tool_input.command) ?? (d.functionCall?.args?.command) ?? '';
  if (rawCmd !== null && rawCmd !== undefined && typeof rawCmd !== 'string') return '__MALFORMED__';
  const cmd = (rawCmd || '').trim();
  const args = d.toolCall?.args ?? d.tool_input ?? d.functionCall?.args ?? {};
  let guard = 0;
  let readok = 0;
  if (SHELL_TOOLS.has(name.toLowerCase())) {
    guard = cmd && shellNeedsGuard(cmd) ? 1 : 0;
  } else {
    const c = classifyTool(name, args);
    guard = c.guard ? 1 : 0;
    readok = c.readok ? 1 : 0;
  }
  return `OK|||${name}|||${guard}|||${readok}|||${cmd}`;
}

if (require.main === module) {
  let raw = '';
  process.stdin.on('data', (c) => { raw += c; });
  process.stdin.on('end', () => {
    let out;
    try { out = main(raw); } catch { out = '__MALFORMED__'; }
    process.stdout.write(out);
  });
}

module.exports = { shellNeedsGuard, classifyTool, parseShell, nameTokens };
