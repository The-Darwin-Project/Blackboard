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
// 5. [Contract]: Also the Claude path's engine: claude-guard.js require()s classify()/approvalVerdict() for the
//    HTTP PreToolUse hook (payload `cwd` -> git lookups). `--verdict` CLI mode shares approvalVerdict with the
//    agy shell hook. Dynamic words ($ { ` * ?) in the command/sub-command position, stdin-fed shells
//    (`| bash`, heredocs, `bash -s`) and `-c "$(...)"` payloads are treated as merge-class (fail closed).
// 7. [Contract]: Tokenizer handles heredocs (<<, <<-, quoted/unquoted delimiters; unquoted bodies' $( ) are analyzed),
//    # comments, $'..' ANSI-C (escapes decoded), $"..", quoted vs unquoted < > (only unquoted ones are redirections).
//    git state is read via gitQuery(): ok=false (budget/spawn-cap/timeout/not-a-repo) is UNKNOWN and always guards;
//    at most MAX_GIT_SPAWNS git processes per call. `--json` mode (+ MERGE_GUARD_CWD) is how the Claude HTTP hook
//    runs classification in a child process so git never blocks the sidecar event loop.
// 8. [Contract]: Defining git configuration by ANY route is merge-class because a same-command-line alias is invisible to the
//    pre-flight alias lookup: `git config alias.*|include.*|includeIf.*` writes, GIT_CONFIG_* env (and HOME/GIT_DIR/
//    GIT_EXEC_PATH/PATH for a git call), redirects/`tee`/`cp`/`sed -i`/interpreters writing .git/config|~/.gitconfig, an
//    unknown subcommand under -C/--git-dir (its aliases can't be looked up), and an executable git-<sub> on PATH.
// 6. [Pattern]: MCP tools are classified by NAME TOKENS (camelCase + snake_case split), so `mergePullRequest`,
//    `merge_pull_request` and `glab_mr_merge` all yield the verb `merge`; `merge_request` (the noun) does not.
//    The read-only allowlist is verb-based -- extend READ/SAFE sets here, or set HOOK_EXTRA_ALLOWED_TOOLS in
//    validate-mutations.sh's env, rather than loosening the shell wrapper.
'use strict';
const { spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const PROTECTED = new Set(['main', 'master']);
const SHELLS = new Set(['bash', 'sh', 'zsh', 'dash', 'ksh', 'ash']);
const HTTP_CLIENTS = new Set(['curl', 'wget', 'http', 'https', 'xh', 'xhs']);
const MAX_DEPTH = 4;

// ---------------------------------------------------------------------------------------------
// Shell tokenizer
// ---------------------------------------------------------------------------------------------
// Decode the body of an ANSI-C quoted string $'...' (\xHH, \NNN, \uHHHH, \n ...): `git $'m\x65rge'` IS `git merge`.
function decodeAnsiC(s) {
  const simple = { n: '\n', t: '\t', r: '\r', a: '\x07', b: '\b', e: '\x1b', E: '\x1b', f: '\f', v: '\v', '\\': '\\', "'": "'", '"': '"', '?': '?' };
  let out = '';
  for (let i = 0; i < s.length; i++) {
    const c = s[i];
    if (c !== '\\' || i + 1 >= s.length) { out += c; continue; }
    const d = s[++i];
    if (Object.prototype.hasOwnProperty.call(simple, d)) { out += simple[d]; continue; }
    let m;
    if (d === 'x' && (m = /^[0-9a-fA-F]{1,2}/.exec(s.slice(i + 1)))) { out += String.fromCharCode(parseInt(m[0], 16)); i += m[0].length; continue; }
    if ((d === 'u' || d === 'U') && (m = new RegExp(`^[0-9a-fA-F]{1,${d === 'u' ? 4 : 8}}`).exec(s.slice(i + 1)))) {
      try { out += String.fromCodePoint(parseInt(m[0], 16)); } catch { /* invalid code point */ }
      i += m[0].length; continue;
    }
    if (/[0-7]/.test(d) && (m = /^[0-7]{1,3}/.exec(s.slice(i)))) { out += String.fromCharCode(parseInt(m[0], 8) & 0xff); i += m[0].length - 1; continue; }
    if (d === 'c' && i + 1 < s.length) { out += String.fromCharCode(s[++i].charCodeAt(0) & 0x1f); continue; }
    out += `\\${d}`;
  }
  return out;
}
// Index just past the closing quote of an ANSI-C string whose body starts at `start` (\' is an escaped quote).
function scanAnsiC(str, start) {
  let j = start;
  while (j < str.length && str[j] !== "'") j += str[j] === '\\' ? 2 : 1;
  const end = Math.min(j, str.length);
  return { text: decodeAnsiC(str.slice(start, end)), end: Math.min(end + 1, str.length) };
}

// Index of the closing backtick (honouring \` escapes), or n if unterminated.
function matchBacktick(str, start) {
  let j = start;
  while (j < str.length && str[j] !== '`') j += str[j] === '\\' ? 2 : 1;
  return Math.min(j, str.length);
}

const isWordStart = (str, j, lo) => j === lo || /[\s;&|()]/.test(str[j - 1]);

// Quote-, comment- and nesting-aware: returns the index just past the ')' matching the '(' before `start`.
// Quotes ('..', "..", $'..'), backticks, ${..}, `# comments` and nested $( ) must not close the substitution early;
// otherwise the remainder of the command is re-parsed with the wrong state and a trailing `git merge` hides.
function matchParen(str, start) {
  const n = str.length;
  let depth = 1;
  let j = start;
  while (j < n && depth > 0) {
    const c = str[j];
    if (c === '\\') { j += 2; continue; }
    if (c === "'") { const k = str.indexOf("'", j + 1); j = k === -1 ? n : k + 1; continue; }
    if (c === '$' && str[j + 1] === "'") { j = scanAnsiC(str, j + 2).end; continue; }
    if (c === '"') {
      j++;
      while (j < n && str[j] !== '"') {
        if (str[j] === '\\') { j += 2; continue; }
        if (str[j] === '$' && str[j + 1] === '(') { j = matchParen(str, j + 2); continue; }
        if (str[j] === '`') { j = matchBacktick(str, j + 1) + 1; continue; }
        j++;
      }
      j++; continue;
    }
    if (c === '`') { j = matchBacktick(str, j + 1) + 1; continue; }
    if (c === '$' && str[j + 1] === '{') { const k = str.indexOf('}', j + 2); j = k === -1 ? n : k + 1; continue; }
    if (c === '#' && isWordStart(str, j, start)) { const k = str.indexOf('\n', j); j = k === -1 ? n : k; continue; }
    if (c === '$' && str[j + 1] === '(') { depth++; j += 2; continue; }
    if (c === '(') depth++;
    else if (c === ')') depth--;
    j++;
  }
  return j; // == n (unterminated) or index after ')'
}

// Collect $( ) / backtick substitutions that an UNQUOTED heredoc body would execute.
function bodySubstitutions(body, nested) {
  for (let i = 0; i < body.length; i++) {
    if (body[i] === '\\') { i++; continue; }
    if (body[i] === '$' && body[i + 1] === '(') {
      const end = matchParen(body, i + 2);
      nested.push(body.slice(i + 2, Math.max(i + 2, end - 1)));
      i = end - 1;
    } else if (body[i] === '`') {
      const end = matchBacktick(body, i + 1);
      nested.push(body.slice(i + 1, end));
      i = end;
    }
  }
}

// Returns { cmds: {t: string[], f: boolean[]}[], nested: string[] }. `f[k]` marks token k as a redirection operator
// (built from an UNQUOTED < or >, so a quoted '>' argument is never mistaken for one). `nested` holds the bodies of
// $(...), `...`, <(...), >(...) and of command substitutions inside unquoted heredocs, to be analyzed as commands.
function parseShell(str) {
  const cmds = [];
  const nested = [];
  const pending = []; // heredocs whose bodies start after the next newline
  let tokens = [];
  let flags = [];
  let cur = '';
  let has = false; // a token is in progress (so '' counts as a token)
  let curRedir = false;
  let redirTail = false; // previous char appended was an unquoted < or >
  const pushTok = () => { if (has) { tokens.push(cur); flags.push(curRedir); } cur = ''; has = false; curRedir = false; };
  const pushCmd = () => { pushTok(); if (tokens.length) cmds.push({ t: tokens, f: flags }); tokens = []; flags = []; };
  const n = str.length;
  let i = 0;

  const grabParen = (start) => { // start points just after '('
    const end = matchParen(str, start);
    const closed = end <= n && str[end - 1] === ')';
    const body = str.slice(start, closed ? end - 1 : end);
    nested.push(body);
    // `case x in a) ...;; esac` has unbalanced ')' of its own: also analyze everything that follows.
    if (/\bcase\b/.test(body)) nested.push(str.slice(start));
    return Math.min(end, n);
  };
  const grabTick = (start) => { // start points just after the opening backtick
    const end = matchBacktick(str, start);
    nested.push(str.slice(start, end));
    return end + 1;
  };
  const readHeredocBodies = () => {
    for (const hd of pending) {
      const body = [];
      while (i < n) {
        let e = str.indexOf('\n', i);
        if (e === -1) e = n;
        const line = str.slice(i, e);
        i = Math.min(e + 1, n);
        if ((hd.strip ? line.replace(/^\t+/, '') : line) === hd.delim) break;
        body.push(line);
      }
      if (!hd.quoted) bodySubstitutions(body.join('\n'), nested);
    }
    pending.length = 0;
  };

  while (i < n) {
    const c = str[i];
    const prevRedir = redirTail;
    redirTail = false;
    if (c === '\\') {
      if (str[i + 1] === '\n') { i += 2; continue; }
      cur += str[i + 1] ?? ''; has = true; i += 2; continue;
    }
    if (c === "'") {
      const j = str.indexOf("'", i + 1);
      const end = j === -1 ? n : j;
      cur += str.slice(i + 1, end); has = true; i = end + 1; continue;
    }
    if (c === '$' && str[i + 1] === "'") { const r = scanAnsiC(str, i + 2); cur += r.text; has = true; i = r.end; continue; }
    if (c === '$' && str[i + 1] === '"') { i++; continue; } // $"..." locale quoting: same as "..."
    if (c === '"') {
      i++; has = true;
      while (i < n && str[i] !== '"') {
        if (str[i] === '\\' && i + 1 < n) { cur += str[i + 1]; i += 2; continue; }
        if (str[i] === '$' && str[i + 1] === '(') { i = grabParen(i + 2); cur += '$SUBST'; continue; }
        if (str[i] === '`') { i = grabTick(i + 1); cur += '$SUBST'; continue; }
        cur += str[i]; i++;
      }
      i++; continue;
    }
    if (c === '$' && str[i + 1] === '(') { i = grabParen(i + 2); cur += '$SUBST'; has = true; continue; }
    if ((c === '<' || c === '>') && str[i + 1] === '(') { i = grabParen(i + 2); cur += '$SUBST'; has = true; continue; }
    if (c === '`') { i = grabTick(i + 1); cur += '$SUBST'; has = true; continue; }
    if (c === '#' && !has) { const e = str.indexOf('\n', i); i = e === -1 ? n : e; continue; } // comment to end of line
    if (c === '<' && str[i + 1] === '<' && str[i + 2] !== '<') { // heredoc: <<WORD / <<-WORD / <<'WORD'
      if (/^\d+$/.test(cur)) { cur = ''; has = false; } // fd prefix (3<<EOF)
      pushTok();
      let j = i + 2;
      const strip = str[j] === '-';
      if (strip) j++;
      while (str[j] === ' ' || str[j] === '\t') j++;
      let delim = '';
      let quoted = false;
      while (j < n && !/[\s;&|()<>]/.test(str[j])) {
        const ch = str[j];
        if (ch === "'" || ch === '"') {
          quoted = true;
          const k = str.indexOf(ch, j + 1);
          const e = k === -1 ? n : k;
          delim += str.slice(j + 1, e); j = e + 1; continue;
        }
        if (ch === '\\') { quoted = true; delim += str[j + 1] ?? ''; j += 2; continue; }
        delim += ch; j++;
      }
      pending.push({ delim, strip, quoted });
      i = j; continue;
    }
    if (c === ';' || c === '&' || c === '|' || c === '\n' || c === '(' || c === ')') {
      // `>&` / `2>&1` / `&>` are redirections, not command separators. Only an UNQUOTED < or > counts, so
      // `echo ">" & git merge` still splits at the '&'.
      if (c === '&' && (prevRedir || str[i + 1] === '>')) { cur += c; has = true; i++; continue; }
      pushCmd(); i++;
      if (c === '\n' && pending.length) readHeredocBodies();
      continue;
    }
    if (c === ' ' || c === '\t' || c === '\r') { pushTok(); i++; continue; }
    if ((c === '<' || c === '>') && (!has || /^\d*$/.test(cur) || cur === '&')) curRedir = true;
    if (c === '<' || c === '>') redirTail = true;
    cur += c; has = true; i++;
  }
  pushCmd();

  // Drop redirections (`> file`, `2>/dev/null`, `<<<`) so they don't pollute positional parsing. A bare operator
  // token consumes the next token (its target). Quoted '>' arguments are NOT flagged and are kept.
  // Redirection TARGETS are kept on `out.redirs` (`echo x >> .git/config` must stay visible to the config-file check).
  const cleaned = cmds.map(({ t, f }) => {
    const out = [];
    out.redirs = [];
    for (let k = 0; k < t.length; k++) {
      if (f[k]) {
        const m = /^\d*(>>?\|?|<<?<?|>&|<&|&>>?)/.exec(t[k]);
        const attached = m ? t[k].slice(m[0].length) : '';
        if (attached) out.redirs.push(attached);
        else if (m && k + 1 < t.length) { out.redirs.push(t[k + 1]); k++; }
        continue;
      }
      out.push(t[k]);
    }
    return out;
  }).filter((t) => t.length || t.redirs.length);
  return { cmds: cleaned, nested };
}

const base = (p) => p.replace(/\/+$/, '').split('/').pop();
// Word that is only known at runtime (variable, substitution, brace expansion, glob) -- cannot be proven safe.
const DYN = /[$`{*?[]/;
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

// Returns the command with wrappers/assignments removed; `.assigns` lists every VAR=value seen in front of it
// (leading assignments and `env VAR=value`), which matter for git (GIT_CONFIG_*, HOME, PATH ...).
function stripPrefix(tokens) {
  const t = tokens.slice();
  const assigns = [];
  t.assigns = assigns;
  for (;;) {
    while (t.length && isAssign(t[0])) assigns.push(t.shift());
    if (!t.length) return t;
    const b = base(t[0]).toLowerCase();
    if (!Object.prototype.hasOwnProperty.call(WRAP, b)) return t;
    const spec = WRAP[b];
    t.shift();
    while (t.length) {
      const x = t[0];
      if (b === 'env' && isAssign(x)) { assigns.push(t.shift()); continue; }
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
// Per-invocation context. cwd: directory of the agent's repo (the agy command hook inherits it; the Claude HTTP
// hook runs this file as a child process with MERGE_GUARD_CWD). deadline: absolute ms. spawns: git processes
// started so far. Once the deadline passed or the spawn cap is hit, git lookups report "unknown" => fail closed.
const CTX = { cwd: undefined, deadline: Infinity, spawns: 0, aliasCache: new Map() };
const GIT_TIMEOUT_MS = 500;
const MAX_GIT_SPAWNS = 8;

// Run a read-only git query. ok=false means the answer is UNKNOWN (budget/cap/timeout/spawn error/not a repo) and
// callers must treat that as "guarded". ok=true with out==='' means the key/match is genuinely absent (exit 1).
function gitQuery(args) {
  if (Date.now() >= CTX.deadline || CTX.spawns >= MAX_GIT_SPAWNS) return { ok: false, out: '' };
  CTX.spawns++;
  const r = spawnSync('git', args, {
    encoding: 'utf8', timeout: GIT_TIMEOUT_MS, killSignal: 'SIGKILL', cwd: CTX.cwd, stdio: ['ignore', 'pipe', 'ignore'],
  });
  if (r.error || r.signal) return { ok: false, out: '' };
  const out = String(r.stdout || '').trim();
  if (r.status === 0) return { ok: true, out };
  if (r.status === 1 && !out) return { ok: true, out: '' }; // `git config --get` / --get-regexp: no such key
  return { ok: false, out: '' };
}

// `heads/main`, `refs/heads/main`, `+main` all name the same branch.
const normRef = (r) => r.trim().replace(/^\+/, '').replace(/^(refs\/)?heads\//, '').toLowerCase();
const isProtected = (r) => PROTECTED.has(normRef(r));

function bareBranchProtected(hasDirOverride) {
  if (hasDirOverride) return true; // -C/--git-dir: cwd's repo state is not the target's
  const head = gitQuery(['rev-parse', '--abbrev-ref', 'HEAD']);
  if (!head.ok || head.out === 'HEAD' || isProtected(head.out)) return true; // unknown/detached/main => guarded
  const pdq = gitQuery(['config', '--get', 'push.default']);
  if (!pdq.ok) return true;
  const pd = (pdq.out || 'simple').toLowerCase();
  if (pd === 'matching') return true;
  if (pd === 'upstream' || pd === 'tracking') {
    const m = gitQuery(['config', '--get', `branch.${head.out}.merge`]);
    if (!m.ok || !m.out || isProtected(m.out)) return true;
  }
  const rp = gitQuery(['config', '--get-regexp', '^remote\\..*\\.push$']);
  if (!rp.ok) return true;
  for (const line of rp.out ? rp.out.split('\n') : []) {
    // HEAD-style values resolve to the current branch, already checked above
    if (refspecNamesProtected(line.split(/\s+/).slice(1).join(' '))) return true;
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
  'for-each-ref', 'show-ref', 'diff-tree', 'update-ref', 'version', 'help', 'archive', 'gc', 'fsck', 'notes', 'bundle',
  'ls-remote', 'cherry', 'count-objects', 'name-rev', 'merge-tree', 'diff-index', 'diff-files', 'write-tree', 'read-tree',
  'commit-tree', 'mktree', 'hash-object', 'verify-commit', 'verify-tag', 'stripspace', 'check-ignore', 'sparse-checkout',
  'maintenance', 'range-diff', 'whatchanged', 'revert', 'difftool', 'request-pull', 'prune', 'repack', 'pack-refs']);

// ---- Same-command-line / out-of-band git configuration (aliases, includes, env, config files) ----
// An alias (or git-<name> program) that is DEFINED and USED in one command line is invisible to the pre-flight alias
// lookup, so defining one by any route is itself merge-class: `git config alias.m merge; git m x`,
// `GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=alias.m GIT_CONFIG_VALUE_0=merge git m x`, `echo '[alias] m=merge' >> .git/config`.
const CONFIG_ENV_RE = /^GIT_CONFIG(_[A-Z0-9_]*)?$/i; // GIT_CONFIG_COUNT/KEY_n/VALUE_n/PARAMETERS/GLOBAL/SYSTEM/NOSYSTEM
const GIT_ENV_RE = /^(HOME|XDG_CONFIG_HOME|GIT_DIR|GIT_COMMON_DIR|GIT_WORK_TREE|GIT_EXEC_PATH|PATH)$/i; // redirect config/programs for a git call
const ASSIGN_ONLY_ENV_RE = /^(HOME|XDG_CONFIG_HOME|GIT_DIR|GIT_COMMON_DIR|GIT_WORK_TREE|GIT_EXEC_PATH)$/i; // (PATH is too common to flag alone)
const GITCFG_PATH_RE = /(\.git\/config(\.worktree)?|\.gitconfig|\.config\/git\/config|\/etc\/gitconfig|gitdir\/config)(?![\w.-])/i;
// Programs that write to the file operands they are given.
const FILE_WRITERS = new Set(['tee', 'cp', 'mv', 'install', 'ln', 'dd', 'truncate', 'sponge', 'perl', 'python', 'python2', 'python3',
  'ruby', 'node', 'php', 'awk', 'gawk', 'ed', 'ex', 'vi', 'vim', 'nano']);
const ENV_BUILTINS = new Set(['export', 'declare', 'typeset', 'readonly', 'local']);

function assignName(a) { return a.slice(0, a.indexOf('=')); }

function configEnvGuard(assigns, bin) {
  for (const a of assigns) {
    const name = assignName(a);
    if (CONFIG_ENV_RE.test(name)) return true;
    if (bin === 'git' && GIT_ENV_RE.test(name)) return true;
    if (!bin && ASSIGN_ONLY_ENV_RE.test(name)) return true; // `HOME=/tmp/x; git ...` persists for later commands
  }
  return false;
}

// `git config` writes of alias.* / include.* / includeIf.* keys (or opening the editor).
function configWriteGuard(args) {
  if (args.some((a) => /^(-e|--edit)$/.test(a))) return true;
  if (args.some((a) => /^(--get|--get-all|--get-regexp|--get-urlmatch|--list|-l|--show-origin|--show-scope|--name-only)$/.test(a))) return false;
  const keys = args.filter((a) => !a.startsWith('-'));
  const writeFlag = args.some((a) => /^--(add|replace-all|unset|unset-all|rename-section|remove-section)$/.test(a));
  if (keys.length < 2 && !writeFlag) return false; // `git config alias.m` is a read
  return keys.some((k) => /^(alias\.|include\.|includeif\.)/i.test(k) || DYN.test(k));
}

// Writes to git config files: redirection targets, or file operands of write-capable programs.
function configFileWriteGuard(bin, rest, redirs, src) {
  const gitish = /\.git\b|GIT_DIR/.test(src);
  for (const r of redirs) {
    if (GITCFG_PATH_RE.test(r)) return true;
    if (gitish && /(^|\/)config(\.worktree)?$/.test(r)) return true; // `cd .git; echo ... >> config`
  }
  const writer = FILE_WRITERS.has(bin) || (bin === 'sed' && rest.some((a) => /^(-[A-Za-z]*i|--in-place)/.test(a)));
  if (writer && rest.some((a) => GITCFG_PATH_RE.test(a) || (gitish && /(^|\/)config$/.test(a)))) return true;
  return false;
}

// `git <sub>` with no builtin/alias runs an external `git-<sub>` program found on PATH (an attacker-supplied
// shim can `exec git merge`). Git's own exec-path programs are not attacker controlled and are not checked.
const SAFE_EXTERNAL = new Set(['lfs']);
function externalGitCommand(sub) {
  if (!/^[A-Za-z0-9][A-Za-z0-9_.-]*$/.test(sub) || SAFE_EXTERNAL.has(sub)) return false;
  for (const dir of String(process.env.PATH || '').split(':')) {
    try {
      const f = path.join(dir || '.', `git-${sub}`);
      if (fs.statSync(f).isFile()) { fs.accessSync(f, fs.constants.X_OK); return true; }
    } catch { /* not here */ }
  }
  return false;
}

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
  if (DYN.test(sub)) return true; // git $SUB / ${X} / m{er,}ge / mer*: dynamic subcommand
  if (sub === 'merge') return true;
  if (sub === 'config') return configWriteGuard(rest);
  if (sub === 'push') return pushGuard(rest, dirOverride);
  if (sub && !GIT_BUILTINS.has(sub)) {
    if (depth >= MAX_DEPTH) return true; // alias chain too deep to follow => guarded
    if (dirOverride) return true; // -C/--git-dir: that repo's aliases are not the ones we can look up
    if (externalGitCommand(sub)) return true; // user-supplied git-<sub> program on PATH
    let alias = CTX.aliasCache.get(args[i]);
    if (alias === undefined) {
      alias = gitQuery(['config', '--get', `alias.${args[i]}`]);
      CTX.aliasCache.set(args[i], alias);
    }
    // Unknown (budget/cap/timeout/not a repo) must NOT read as "no alias": that would fail open.
    if (!alias.ok) return true;
    if (alias.out) {
      if (alias.out.startsWith('!')) return analyzeString(alias.out.slice(1) + ' ' + rest.join(' '), depth + 1, true);
      return gitGuard(parseShell(alias.out).cmds.flat().concat(rest), depth + 1);
    }
  }
  return false;
}

// Positional tokens of gh/glab, skipping the values of flags that take one.
const API_VALUED = new Set(['-R', '--repo', '--hostname', '-H', '--header', '-X', '--method', '-f', '--raw-field', '-F',
  '--field', '--input', '-q', '--jq', '-t', '--template', '--cache', '-p', '--preview', '-b', '--branch']);
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

// Endpoints/mutations that merge or rewrite a branch regardless of which branch the body names.
const MERGE_ENDPOINT_RE = new RegExp([
  '\\/merges?(?![A-Za-z0-9_-])', '\\/merge-upstream', 'merge_when_pipeline_succeeds', 'mergePullRequest',
  'enablePullRequestAutoMerge', 'mergeBranch', 'merge_pull_request', '\\/auto[-_]?merge', 'createCommitOnBranch', 'updateRef',
].join('|'), 'i');
// Direct writes to the default branch's ref / branch resource.
const REFS_MAIN_RE = /refs\/heads\/(main|master)(?![\w.-])|\/git\/refs\/(heads\/)?(main|master)(?![\w.-])|\/branches\/(main|master)(?![\w.-])/i;
// Contents/commit APIs write to the DEFAULT branch unless a non-default `branch` is given.
const CONTENTS_RE = /\/contents\/|\/repository\/files\/|\/repository\/commits(?![\w-])/i;
function branchValues(text) {
  const out = [];
  const re = /\bbranch(?:Name)?["']?\s*[:=]\s*["']?([^"'&\s,}]+)/gi;
  let m;
  while ((m = re.exec(text))) out.push(m[1]);
  return out;
}
// text = URL + body/fields of a NON-GET API call (shell curl/wget/gh api/glab api and the glab_api MCP tool).
function apiWriteNeedsGuard(text) {
  if (MERGE_ENDPOINT_RE.test(text) || REFS_MAIN_RE.test(text)) return true;
  if (CONTENTS_RE.test(text)) {
    const b = branchValues(text);
    return !(b.length && b.every((v) => !isProtected(v)));
  }
  return false;
}

const BODY_FLAG = {
  curl: /^(-d|--data|--data-[a-z]+|--json|-F|--form|--form-string|-T|--upload-file)(=.*)?$|^-[dFT]./,
  wget: /^--(post-data|post-file|body-data|body-file)(=.*)?$/,
  api: /^(-f|-F|--field|--raw-field|--input)(=.*)?$|^-[fF]./,
};
// Flags whose NEXT token is a value, not the request target (used to find the URL/endpoint candidates).
const HTTP_VALUED = new Set(['-H', '--header', '-d', '--data', '--data-raw', '--data-binary', '--data-urlencode', '-X', '--request',
  '--method', '-o', '--output', '-u', '--user', '-F', '--form', '--form-string', '-T', '--upload-file', '-A', '--user-agent', '-e',
  '--referer', '-b', '--cookie', '-c', '--cookie-jar', '-w', '--write-out', '-m', '--max-time', '--connect-timeout', '--json',
  '-O', '-U', '--post-data', '--post-file', '--body-data', '--body-file', '--password', '--proxy', '-x', ...API_VALUED]);

// Request method of an http-client invocation: explicit flag (incl. attached -XPUT for curl, gh and glab) or implied by body flags.
function httpMethod(bin, args) {
  let method = null;
  let body = false;
  let getFlag = false;
  const kind = (bin === 'gh' || bin === 'glab') ? 'api' : (BODY_FLAG[bin] ? bin : null);
  for (let i = 0; i < args.length; i++) {
    const a = args[i];
    if (bin === 'curl' && /^-[A-Za-z]{2,}/.test(a)) { // combined short flags: -sXPUT, -sX PUT, -sd '{}', -fsSLd
      const SHORT_VALUED = 'XdFTHoUuAebcDEwymxKCrtQ';
      for (let k = 1; k < a.length; k++) {
        const ch = a[k];
        if (ch === 'G') getFlag = true;
        if (!SHORT_VALUED.includes(ch)) continue;
        const val = a.slice(k + 1) || args[i + 1] || '';
        if (ch === 'X') method = val.toUpperCase();
        else if ('dFT'.includes(ch)) body = true;
        if (!a.slice(k + 1)) i++; // value was the next token
        break;
      }
      continue;
    }
    if (a === '-X' || a === '--request' || a === '--method') { method = (args[i + 1] || '').toUpperCase(); i++; continue; }
    if (/^--(request|method)=/.test(a)) { method = a.split('=')[1].toUpperCase(); continue; }
    if ((bin === 'curl' || kind === 'api') && /^-X./.test(a)) { method = a.slice(2).toUpperCase().replace(/^=/, ''); continue; } // -XPUT (curl, gh api, glab api)
    if (bin === 'curl' && (a === '-G' || a === '--get')) getFlag = true;
    if (kind && BODY_FLAG[kind].test(a)) body = true;
    if (!kind && /^[A-Za-z0-9_.-]+(=|:=|=@|@)/.test(a) && !/[:/]\/|^\//.test(a)) body = true; // httpie items
  }
  if (!method && !kind) { const p = args.find((x) => !x.startsWith('-')); if (p && /^(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)$/i.test(p)) method = p.toUpperCase(); }
  return method || ((body && !getFlag) ? 'POST' : 'GET');
}
const isReadMethod = (m) => m === 'GET' || m === 'HEAD' || m === 'OPTIONS';

// A request target that is ENTIRELY runtime-determined ($URL) cannot be checked against the endpoint lists.
function hasOpaqueTarget(args) {
  for (let i = 0; i < args.length; i++) {
    const a = args[i];
    if (a.startsWith('-')) { if (HTTP_VALUED.has(a)) i++; continue; }
    if (DYN.test(a) && !a.includes('/') && !a.includes('=')) return true;
  }
  return false;
}

function httpGuard(bin, args) {
  if (isReadMethod(httpMethod(bin, args))) return false;
  return apiWriteNeedsGuard(args.join(' ')) || hasOpaqueTarget(args);
}

function analyzeTokens(tokens, depth, strict) {
  const redirs = tokens.redirs || [];
  const t = stripPrefix(tokens);
  const assigns = t.assigns || [];
  const src = SRC.cur;
  if (!t.length) { // assignment-only / redirect-only command
    return configEnvGuard(assigns, '') || configFileWriteGuard('', [], redirs, src);
  }
  const rawBin = t[0];
  const bin = base(rawBin).toLowerCase();
  const rest = t.slice(1);
  if (configEnvGuard(assigns, bin)) return true;
  if (ENV_BUILTINS.has(bin) && configEnvGuard(rest.filter(isAssign), '')) return true; // export GIT_CONFIG_COUNT=1
  if (configFileWriteGuard(bin, rest, redirs, src)) return true;
  if (DYN.test(rawBin)) { // dynamic command word
    if (strict) return true;
    return rest.some((x) => /^(merge|push|api)$/i.test(x) || DYN.test(x) && /merge|push/i.test(x));
  }
  if (SHELLS.has(bin)) {
    const ci = rest.findIndex((x) => /^-[A-Za-z]*c[A-Za-z]*$/.test(x));
    if (ci !== -1 && rest[ci + 1] !== undefined) return analyzeString(rest[ci + 1], depth + 1, true);
    // No -c and no script file: the shell reads its program from stdin (`... | bash`, `bash <<EOF`, `bash -s`,
    // here-strings) which cannot be inspected => needs approval. `bash script.sh` is NOT flagged (file body unseen).
    const hasScript = rest.some((x, k) => !x.startsWith('-') && !(k > 0 && /^-[A-Za-z]*[oO]$/.test(rest[k - 1])));
    return !hasScript;
  }
  if (bin === 'eval') return analyzeString(rest.join(' '), depth + 1, true);
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
    // Only the command path (group/action) being dynamic is suspicious (`gh pr $ACT 5`); a dynamic ID/arg in a
    // read-style call (`gh pr view "$PR"`, `glab mr list --label "$L"`) is not.
    if (pos.slice(0, 2).some((x) => DYN.test(x))) return true;
    if (hasSubseq(pos, bin === 'gh' ? ['pr', 'merge'] : ['mr', 'merge'])) return true;
    if (pos[0] && pos[0].toLowerCase() === 'api') return httpGuard(bin, rest);
    return false;
  }
  if (HTTP_CLIENTS.has(bin)) return httpGuard(bin, rest);
  return false;
}

// Source text currently being analyzed (config-file checks look for `.git` anywhere in it).
const SRC = { cur: '' };
function analyzeString(str, depth, strict) {
  if (depth > MAX_DEPTH) return true; // pathological nesting => fail closed
  const prev = SRC.cur;
  SRC.cur = str;
  try {
    const { cmds, nested } = parseShell(str);
    for (const c of cmds) if (analyzeTokens(c, depth, strict)) return true;
    for (const nsub of nested) if (analyzeString(nsub, depth + 1)) return true;
    return false;
  } finally {
    SRC.cur = prev;
  }
}

function shellNeedsGuard(cmd) {
  try { return analyzeString(cmd, 0); } catch { return true; }
}

// ---------------------------------------------------------------------------------------------
// MCP / non-shell tool classification (name tokens, not substrings)
// ---------------------------------------------------------------------------------------------
const nameTokens = (name) => name.replace(/([a-z0-9])([A-Z])/g, '$1_$2').toLowerCase().split(/[^a-z0-9]+/).filter(Boolean);
// Server-name fragments (mcp__GitHub__x, mcp_KubeArchive_x ...). Dropped before looking for the action verb.
const PREFIX_TOKENS = new Set(['mcp', 'github', 'gitlab', 'glab', 'gh', 'argocd', 'jenkins', 'darwin', 'blackboard', 'journal', 'teamchat', 'playwright', 'kubearchive', 'konflux',
  'git', 'hub', 'lab', 'argo', 'cd', 'k8s', 'kube', 'archive', 'chat']);
const READ_VERBS = new Set(['get', 'list', 'read', 'search', 'view', 'find', 'fetch', 'query', 'show', 'describe', 'status', 'top',
  'log', 'logs', 'events', 'trace', 'diff', 'summary', 'stats', 'lint', 'contributors', 'count', 'compare', 'snapshot']);
// PR/MR discussion, not code mutation. `review` is deliberately NOT here: *_review_write can APPROVE/submit reviews.
const SAFE_TOKENS = new Set(['comment', 'note', 'reply']);
const HARD_WRITE = new Set(['delete', 'remove', 'merge', 'push', 'revoke', 'destroy', 'drop', 'publish', 'transfer', 'archive', 'fork', 'assign']);
const WRITE = new Set(['create', 'update', 'write', 'set', 'add', 'run', 'sync', 'trigger', 'cancel', 'retry', 'close', 'reopen',
  'approve', 'upload', 'login', 'bootstrap', 'import', 'edit', 'save', 'amend', 'rebase', 'subscribe', 'unsubscribe', 'send',
  'execute', 'exec', 'start', 'stop', 'apply', 'patch', 'scale', 'rollback', 'promote', 'deploy', 'put', 'post', 'commit', 'upsert', 'submit']);
const FAMILY_TOKENS = new Set(['team', 'bb', 'svc', 'ka']); // comms / blackboard / journal / kubearchive MCPs
// Tokens allowed after `browser_` for read-only roles (snapshot, take_screenshot, console_messages, network_requests,
// network_request, find, tabs, wait_for, navigate, navigate_back, resize, hover, click, close).
const BROWSER_READ = new Set(['snapshot', 'take', 'screenshot', 'console', 'messages', 'network', 'requests', 'request', 'find',
  'tabs', 'wait', 'for', 'navigate', 'back', 'resize', 'hover', 'click', 'close']);
const NATIVE_ALLOW = new Set(['task_boundary', 'notify_user', 'browser_subagent']);
// Native file-mutation tools: handled by validate-mutations.sh MUTATION_TOOLS (keep the two lists in sync).
const NATIVE_MUTATION = new Set(['write_to_file', 'replace_file_content', 'multi_replace_file_content', 'edit_file']);

// glab_api MCP shape: { args: ['endpoint'] | 'endpoint', flags: { method, field, ... } | '-X PUT' }. Either may be a string.
function apiTokens(args) {
  const toks = [];
  const a = args && typeof args === 'object' ? args : {};
  const asTokens = (v) => (typeof v === 'string' ? parseShell(v).cmds.flat() : []);
  if (typeof a.flags === 'string') toks.push(...asTokens(a.flags));
  else if (a.flags && typeof a.flags === 'object') {
    const f = a.flags;
    if (f.method) toks.push('--method', String(f.method));
    for (const k of ['field', 'raw_field', 'form', 'input']) {
      if (f[k] !== undefined && f[k] !== false) toks.push('--field', ...[].concat(f[k]).map(String));
    }
  }
  if (Array.isArray(a.args)) toks.push(...a.args.map(String));
  else if (typeof a.args === 'string') toks.push(...asTokens(a.args));
  if (typeof args === 'string') toks.push(...asTokens(args));
  return toks;
}

function classifyTool(name, args) {
  const lname = name.toLowerCase();
  if (NATIVE_MUTATION.has(lname)) return { guard: false, readok: false };
  const a = args && typeof args === 'object' ? args : {};
  // mcp__<server>__<tool>: classify on the tool part only, so server names cannot masquerade as verbs/families.
  const parts = name.split('__');
  const toolPart = parts.length >= 3 && /^mcp$/i.test(parts[0]) ? parts.slice(2).join('__') : name;
  const tokens = nameTokens(toolPart);
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
  // remote file/commit writes: default branch (or unspecified branch) needs approval
  const writeish = [...set].some((t) => WRITE.has(t) || t === 'delete');
  const isFileWrite = !readFirst && verb !== 'browser' && (set.has('push')
    || ((set.has('file') || set.has('files') || set.has('contents') || set.has('commit') || set.has('commits')) && writeish));
  if (isFileWrite) {
    const br = a.branch ?? a.ref ?? a.target_branch ?? a.base_branch;
    if (typeof br !== 'string' || !br.trim() || isProtected(br)) guard = true;
  }
  // generic API tool (glab_api): non-GET against a merge endpoint
  // Only a tool that IS the generic API caller (glab_api / gh_api / api) -- not any name that merely contains `api`
  // (create_api_key, get_api_docs): those go through the normal verb logic below.
  const isApi = tokens.filter((t) => !PREFIX_TOKENS.has(t)).join('_') === 'api';
  let apiRead = false;
  if (isApi) {
    const toks = apiTokens(args);
    const m = httpMethod('glab', toks);
    apiRead = isReadMethod(m);
    if (!apiRead && (apiWriteNeedsGuard(toks.join(' ')) || hasOpaqueTarget(toks))) guard = true;
  }

  // Action tokens: server-name prefixes dropped, and `merge` dropped when it is only the noun
  // ("list_merge_requests") or the call is a read verb.
  const act = tokens.filter((t, i) => !PREFIX_TOKENS.has(t)
    && !(/^(auto)?merge[sd]?$/.test(t) && (readFirst || /^requests?$/.test(tokens[i + 1] || ''))));
  // Families are anchored: the tool's FIRST action token must be the family (bb_get_approval, team_send_results),
  // not merely contained somewhere in the name (create_team_discussion).
  const family = FAMILY_TOKENS.has(verb);
  let readok = false;
  if (!guard) {
    if (NATIVE_ALLOW.has(lname)) readok = true;
    else if (isApi) readok = apiRead;
    else if (act.some((t) => HARD_WRITE.has(t))) readok = false;
    else if (family) readok = true;
    // Playwright: observation + navigation only. Anything that evaluates JS, types/fills/uploads/drags, or presses
    // keys can submit forms or act on logged-in pages, so read-only roles don't get it.
    else if (verb === 'browser') readok = tokens.slice(tokens.indexOf('browser') + 1).every((t) => BROWSER_READ.has(t));
    else if (act.some((t) => SAFE_TOKENS.has(t))) readok = true;
    // read-verb-first tools (get_commit, get_workflow_run, list_*) may carry write-ish nouns (commit, run)
    else if (!readFirst && act.some((t) => WRITE.has(t))) readok = false;
    else readok = act.some((t) => READ_VERBS.has(t));
  }
  return { guard, readok };
}

// ---------------------------------------------------------------------------------------------
// Approval verdict (shared by validate-mutations.sh and the Claude HTTP hook)
// ---------------------------------------------------------------------------------------------
function approvalVerdict(approval, localSha) {
  if (!approval || typeof approval !== 'object' || !approval.approved) {
    return { allow: false, reason: 'Merge REFUSED: event not approved by authorized maintainer (bb_get_approval/proxy/approval reports approved=false or was unreachable).' };
  }
  if (!approval.approved_mr_sha || !localSha || approval.approved_mr_sha !== localSha) {
    return { allow: false, reason: `Merge REFUSED: live HEAD (${localSha || ''}) differs from authenticated approval SHA (${approval.approved_mr_sha}).` };
  }
  return { allow: true, reason: '' };
}

// ---------------------------------------------------------------------------------------------
// Entry points
// ---------------------------------------------------------------------------------------------
// Keep in sync with SHELL_TOOLS in validate-mutations.sh. Claude Code's tool is named `Bash`.
const SHELL_TOOLS = new Set(['bash', 'shell', 'run_in_terminal', 'execute_command', 'run_shell_command', 'run_command']);

// Classify a PreToolUse payload (agy {toolCall:{name,args}} or Claude {tool_name,tool_input}).
// Returns null if malformed, else { name, guard, readok, cmd, isShell }.
function classify(d, opts = {}) {
  CTX.cwd = opts.cwd || undefined;
  CTX.spawns = 0;
  CTX.aliasCache = new Map();
  CTX.deadline = Date.now() + (opts.budgetMs || 1500);
  if (!d || typeof d !== 'object' || Array.isArray(d)) return null;
  let name = d.toolCall?.name || d.tool_name || d.functionCall?.name || '';
  if (!name || typeof name !== 'string') return null;
  name = name.trim();
  const rawCmd = d.toolCall?.args?.CommandLine ?? d.toolCall?.args?.command ?? (d.tool_input && d.tool_input.command) ?? (d.functionCall?.args?.command) ?? '';
  if (rawCmd !== null && rawCmd !== undefined && typeof rawCmd !== 'string') return null;
  const cmd = (rawCmd || '').trim();
  const args = d.toolCall?.args ?? d.tool_input ?? d.functionCall?.args ?? {};
  const isShell = SHELL_TOOLS.has(name.toLowerCase());
  if (isShell) return { name, guard: !!cmd && shellNeedsGuard(cmd), readok: false, cmd, isShell };
  const c = classifyTool(name, args);
  return { name, guard: c.guard, readok: c.readok, cmd, isShell };
}

function main(raw) {
  const r = classify(JSON.parse(raw));
  if (!r) return '__MALFORMED__';
  return `OK|||${r.name}|||${r.guard ? 1 : 0}|||${r.readok ? 1 : 0}|||${r.cmd}`;
}

if (require.main === module) {
  if (process.argv[2] === '--json') {
    // node merge-guard.js --json < payload  =>  JSON classify() result, or `null` if malformed.
    // MERGE_GUARD_CWD: directory git lookups must run in (the Claude HTTP hook runs us as a child process so the
    // sidecar's event loop never blocks on git).
    let raw = '';
    process.stdin.on('data', (c) => { raw += c; });
    process.stdin.on('end', () => {
      let out = 'null';
      try { out = JSON.stringify(classify(JSON.parse(raw), { cwd: process.env.MERGE_GUARD_CWD || undefined, budgetMs: 1500 })); } catch { out = 'null'; }
      process.stdout.write(out);
    });
  } else if (process.argv[2] === '--verdict') {
    // node merge-guard.js --verdict -- <approval-json> <local-sha>  =>  ALLOW||| | BLOCK|||<reason>
    const [, , , , rawApproval, sha] = process.argv;
    let approval = null;
    try { approval = JSON.parse(rawApproval || ''); } catch { approval = null; }
    const v = approvalVerdict(approval, sha || '');
    process.stdout.write(`${v.allow ? 'ALLOW' : 'BLOCK'}|||${v.reason}`);
  } else {
    let raw = '';
    process.stdin.on('data', (c) => { raw += c; });
    process.stdin.on('end', () => {
      let out;
      try { out = main(raw); } catch { out = '__MALFORMED__'; }
      process.stdout.write(out);
    });
  }
}

module.exports = { shellNeedsGuard, classifyTool, classify, approvalVerdict, parseShell, nameTokens };
