#!/usr/bin/env node
// gemini-sidecar/hooks/merge-guard.js
// @ai-rules:
// 1. [Pattern]: Classifier helper for validate-mutations.sh. Reads the PreToolUse JSON on stdin and prints
//    ONE line: `OK|||<tool>|||<guard 0|1|2>|||<readok 0|1>|||<shell command>` or `__MALFORMED__`.
//    guard=1  -> category 'git_merge': the call can merge / write to a default branch. Needs approved === true AND
//                approved_mr_sha === live HEAD, for ANY role.
//    guard=2  -> category 'operational': mutating kubectl/oc/helm/argocd/kargo/tkn command or cluster/ArgoCD/Kargo MCP write.
//                Needs role `sysadmin` AND approved === true; there is no commit, so NO SHA check. git_merge always wins
//                when a call is both (combineCategories, find -exec clauses, pipelines).
//    readok=1 -> non-shell tool that is read-only / comms (the only MCP tools read-only roles may call).
// 2. [Contract]: Fail-CLOSED. Any exception, unparseable shape or excessive shell nesting => guard=1 or
//    __MALFORMED__ (the shell wrapper denies). Never print anything else to stdout. A tool name containing `|||` is
//    MALFORMED (it would shift the delimited fields).
// 3. [Constraint]: Shell commands are TOKENIZED (quotes, escapes, ;&|, $(..), backticks, bash -c, eval,
//    env/sudo/xargs/find -exec wrappers, binary basename) -- not regex-matched -- so global options,
//    quoting and wrappers cannot hide `git merge|push`, `gh pr merge`, `glab mr merge`, or non-GET
//    curl/wget/gh api/glab api calls against merge endpoints.
// 4. [Gotcha]: Still defense-in-depth, not a sandbox: it cannot see inside scripts (`sh x.sh`), `python -c`,
//    `curl -d @file`, or what runs INSIDE a pod (`kubectl exec pod -- git merge x` is 'operational'; the payload after `--`
//    is not analyzed). A dynamic command word ($VAR, `eval`, glob) is guarded as git_merge (see rule 5); the test builtins
//    `[` and `[[` are NOT dynamic words.
// 10. [Contract]: Operational classification is a READ ALLOWLIST per binary (kubectl/oc/helm/argocd/kargo/tkn): anything not
//    a known read verb/sub-verb is 'operational', value-taking flags before the verb cannot hide it, and a dynamic verb
//    ($VERB, "$@") is guarded like a dynamic git/gh/glab subcommand. Extend the *_READ sets to unguard a new read verb.
//    MCP tools: cluster-server/noun tools (ArgoCD, k8s, Helm, Kargo ...) with a mutating verb are 'operational'.
// 5. [Contract]: Also the Claude path's engine: claude-guard.js require()s classify()/approvalVerdict() for the
//    HTTP PreToolUse hook (payload `cwd` -> git lookups). `--verdict` CLI mode shares approvalVerdict with the
//    agy shell hook. Dynamic words ($ { ` * ?) in the command/sub-command position, stdin-fed shells
//    (`| bash`, heredocs, `bash -s`) and `-c "$(...)"` payloads are treated as merge-class (fail closed). `[`/`[[` excepted.
// 7. [Contract]: Tokenizer handles heredocs (<<, <<-, quoted/unquoted delimiters; unquoted bodies' $( ) are analyzed),
//    # comments, $'..' ANSI-C (escapes decoded), $"..", quoted vs unquoted < > (only unquoted ones are redirections).
//    git state is read via gitQuery(): ok=false (budget/spawn-cap/timeout/not-a-repo) is UNKNOWN and always guards;
//    at most MAX_GIT_SPAWNS git processes per call. `--json` mode (+ MERGE_GUARD_CWD) is how the Claude HTTP hook
//    runs classification in a child process so git never blocks the sidecar event loop.
// 8. [Contract]: Defining git configuration by ANY route is merge-class because a same-command-line alias is invisible to the
//    pre-flight alias lookup: `git config alias.*|include.*|includeIf.*` writes, GIT_CONFIG_* env (and HOME/GIT_DIR/
//    GIT_EXEC_PATH/PATH for a git call), redirects/`tee`/`cp`/`sed -i`/interpreters writing .git/config|~/.gitconfig, an
//    unknown subcommand under -C/--git-dir (its aliases can't be looked up), and an executable git-<sub> on PATH.
// 9. [Contract]: matchParen is heredoc-aware and returns n+1 for UNTERMINATED constructs; parseShell reports `unsafe`
//    for any unterminated quote/$( )/backtick/$'..'/heredoc and analyzeString then guards (fail closed). Wrapper table
//    WRAP covers sudo/doas/env(-S payloads)/xargs/parallel/ionice/taskset/chrt/flock/chroot/nsenter/unshare/watch/busybox;
//    su/script -c, `sudo -s 'cmd'` and `bash -s` are handled in analyzeTokens. `--readonly <role>` exposes ../roles.js.
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
  return { text: decodeAnsiC(str.slice(start, end)), end: Math.min(end + 1, str.length), closed: j < str.length };
}

// Index of the closing backtick (honouring \` escapes), or n if unterminated.
function matchBacktick(str, start) {
  let j = start;
  while (j < str.length && str[j] !== '`') j += str[j] === '\\' ? 2 : 1;
  return Math.min(j, str.length);
}

const isWordStart = (str, j, lo) => j === lo || /[\s;&|()]/.test(str[j - 1]);

// Parse `<<[-]WORD` starting at str[i] === '<' (not `<<<`). Returns { delim, strip, quoted, next } or null.
function readHeredocStart(str, i) {
  if (!(str[i] === '<' && str[i + 1] === '<' && str[i + 2] !== '<')) return null;
  const n = str.length;
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
  return { delim, strip, quoted, next: j };
}

// Skip heredoc bodies starting at str[i] (just after a newline). Returns { next, bodies, ok } -- ok=false when a
// terminator line is missing (unterminated heredoc).
function skipHeredocBodies(str, i, pending) {
  const n = str.length;
  const bodies = [];
  let ok = true;
  for (const hd of pending) {
    const body = [];
    let found = false;
    while (i < n) {
      let e = str.indexOf('\n', i);
      if (e === -1) e = n;
      const line = str.slice(i, e);
      i = Math.min(e + 1, n);
      if ((hd.strip ? line.replace(/^\t+/, '') : line) === hd.delim) { found = true; break; }
      body.push(line);
    }
    if (!found) ok = false;
    bodies.push({ hd, text: body.join('\n') });
  }
  return { next: i, bodies, ok };
}

// Quote-, comment-, heredoc- and nesting-aware: returns the index just past the ')' matching the '(' before `start`,
// or n + 1 when the construct is UNTERMINATED (callers must fail closed). Quotes ('..', "..", $'..'), backticks,
// ${..}, `# comments`, heredoc bodies and nested $( ) must not close the substitution early; otherwise the remainder
// of the command is re-parsed with the wrong state and a trailing `git push origin main` hides.
function matchParen(str, start) {
  const n = str.length;
  const UNTERM = n + 1;
  let depth = 1;
  let j = start;
  const pending = [];
  while (j < n && depth > 0) {
    const c = str[j];
    if (c === '\\') { j += 2; continue; }
    if (c === "'") { const k = str.indexOf("'", j + 1); if (k === -1) return UNTERM; j = k + 1; continue; }
    if (c === '$' && str[j + 1] === "'") { const r = scanAnsiC(str, j + 2); if (!r.closed) return UNTERM; j = r.end; continue; }
    if (c === '"') {
      j++;
      while (j < n && str[j] !== '"') {
        if (str[j] === '\\') { j += 2; continue; }
        if (str[j] === '$' && str[j + 1] === '(') { j = matchParen(str, j + 2); if (j > n) return UNTERM; continue; }
        if (str[j] === '`') { const k = matchBacktick(str, j + 1); if (k >= n) return UNTERM; j = k + 1; continue; }
        j++;
      }
      if (j >= n) return UNTERM;
      j++; continue;
    }
    if (c === '`') { const k = matchBacktick(str, j + 1); if (k >= n) return UNTERM; j = k + 1; continue; }
    if (c === '$' && str[j + 1] === '{') { const k = str.indexOf('}', j + 2); if (k === -1) return UNTERM; j = k + 1; continue; }
    if (c === '#' && isWordStart(str, j, start)) { const k = str.indexOf('\n', j); j = k === -1 ? n : k; continue; }
    if (c === '<' && str[j + 1] === '<' && str[j + 2] !== '<') {
      const hd = readHeredocStart(str, j);
      pending.push(hd); j = hd.next; continue;
    }
    if (c === '\n' && pending.length) {
      const r = skipHeredocBodies(str, j + 1, pending.splice(0));
      if (!r.ok) return UNTERM;
      j = r.next; continue;
    }
    if (c === '$' && str[j + 1] === '(') { depth++; j += 2; continue; }
    if (c === '(') depth++;
    else if (c === ')') depth--;
    j++;
  }
  return depth === 0 ? j : UNTERM;
}

// Collect $( ) / backtick substitutions that an UNQUOTED heredoc body would execute. Returns true if one is
// unterminated (caller treats the whole command as unanalyzable => guarded).
// quoteAware=true is for array-assignment bodies `arr=('$(x)' "$(y)")`: inside '...' nothing expands (skip it), inside
// "..." substitutions are live. Heredoc bodies MUST stay quoteAware=false: a single quote there is a literal character
// and `$( )` still executes.
function bodySubstitutions(body, nested, quoteAware = false) {
  let unsafe = false;
  let inDouble = false;
  for (let i = 0; i < body.length; i++) {
    if (body[i] === '\\') { i++; continue; }
    if (quoteAware) {
      if (body[i] === '"') { inDouble = !inDouble; continue; }
      if (body[i] === "'" && !inDouble) {
        const k = body.indexOf("'", i + 1);
        if (k === -1) { unsafe = true; break; } // unterminated '...' => unanalyzable
        i = k; continue;
      }
    }
    if (body[i] === '$' && body[i + 1] === '(') {
      const end = matchParen(body, i + 2);
      if (end > body.length) { unsafe = true; nested.push(body.slice(i + 2)); break; }
      nested.push(body.slice(i + 2, Math.max(i + 2, end - 1)));
      i = end - 1;
    } else if ((body[i] === '<' || body[i] === '>') && body[i + 1] === '(') {
      const end = matchParen(body, i + 2);
      if (end > body.length) { unsafe = true; nested.push(body.slice(i + 2)); break; }
      nested.push(body.slice(i + 2, Math.max(i + 2, end - 1)));
      i = end - 1;
    } else if (body[i] === '`') {
      const end = matchBacktick(body, i + 1);
      if (end >= body.length) { unsafe = true; nested.push(body.slice(i + 1)); break; }
      nested.push(body.slice(i + 1, end));
      i = end;
    }
  }
  return unsafe;
}

// Returns { cmds, nested, unsafe }; unsafe=true when ANY construct is unterminated (quote, $( ), backtick, $'..', heredoc
// without terminator) -- the shell would reject or mis-split it, so it is analyzed as guarded. `f[k]` marks token k as a redirection operator
// (built from an UNQUOTED < or >, so a quoted '>' argument is never mistaken for one). `nested` holds the bodies of
// $(...), `...`, <(...), >(...) and of command substitutions inside unquoted heredocs, to be analyzed as commands.
function parseShell(str) {
  const cmds = [];
  const nested = [];
  const pending = []; // heredocs whose bodies start after the next newline
  let unsafe = false;
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
    const closed = end <= n;
    if (!closed) unsafe = true;
    const body = str.slice(start, closed ? end - 1 : n);
    nested.push(body);
    // `case x in a) ...;; esac` has unbalanced ')' of its own: also analyze everything that follows.
    if (/\bcase\b/.test(body)) nested.push(str.slice(start));
    return Math.min(end, n);
  };
  const grabTick = (start) => { // start points just after the opening backtick
    const end = matchBacktick(str, start);
    if (end >= n) unsafe = true;
    nested.push(str.slice(start, end));
    return end + 1;
  };
  const readHeredocBodies = () => {
    const r = skipHeredocBodies(str, i, pending);
    i = r.next;
    if (!r.ok) unsafe = true; // heredoc never terminated
    for (const { hd, text } of r.bodies) if (!hd.quoted && bodySubstitutions(text, nested)) unsafe = true;
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
      if (j === -1) unsafe = true;
      const end = j === -1 ? n : j;
      cur += str.slice(i + 1, end); has = true; i = end + 1; continue;
    }
    if (c === '$' && str[i + 1] === "'") { const r = scanAnsiC(str, i + 2); if (!r.closed) unsafe = true; cur += r.text; has = true; i = r.end; continue; }
    if (c === '$' && str[i + 1] === '"') { i++; continue; } // $"..." locale quoting: same as "..."
    if (c === '"') {
      i++; has = true;
      while (i < n && str[i] !== '"') {
        if (str[i] === '\\' && i + 1 < n) { cur += str[i + 1]; i += 2; continue; }
        if (str[i] === '$' && str[i + 1] === '(') { i = grabParen(i + 2); cur += '$SUBST'; continue; }
        if (str[i] === '`') { i = grabTick(i + 1); cur += '$SUBST'; continue; }
        cur += str[i]; i++;
      }
      if (i >= n) unsafe = true; // unterminated "..."
      i++; continue;
    }
    if (c === '$' && str[i + 1] === '(') { i = grabParen(i + 2); cur += '$SUBST'; has = true; continue; }
    if ((c === '<' || c === '>') && str[i + 1] === '(') { i = grabParen(i + 2); cur += '$SUBST'; has = true; continue; }
    if (c === '`') { i = grabTick(i + 1); cur += '$SUBST'; has = true; continue; }
    if (c === '#' && !has) { const e = str.indexOf('\n', i); i = e === -1 ? n : e; continue; } // comment to end of line
    if (c === '<' && str[i + 1] === '<' && str[i + 2] !== '<') { // heredoc: <<WORD / <<-WORD / <<'WORD'
      if (/^\d+$/.test(cur)) { cur = ''; has = false; } // fd prefix (3<<EOF)
      pushTok();
      const hd = readHeredocStart(str, i);
      pending.push(hd);
      i = hd.next; continue;
    }
    if (c === '(' && isArrayAssignPrefix(cur)) {
      const end = matchParen(str, i + 1);
      const closed = end <= n;
      if (!closed) unsafe = true;
      const body = str.slice(i + 1, closed ? end - 1 : n);
      if (bodySubstitutions(body, nested, true)) unsafe = true;
      const normBody = body.replace(/\r?\n/g, ' ');
      cur += '(' + normBody + ')';
      has = true;
      i = Math.min(end, n);
      continue;
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
  if (pending.length) unsafe = true; // heredoc operator with no body at all
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
  return { cmds: cleaned, nested, unsafe };
}

const base = (p) => p.replace(/\/+$/, '').split('/').pop();
// Word that is only known at runtime (variable, substitution, brace expansion, glob) -- cannot be proven safe.
const DYN = /[$`{*?[]/;
const isArrayAssignPrefix = (s) => /^[A-Za-z_][A-Za-z0-9_]*(\[[^\]]*\])?\+?=$/.test(s);
const isAssign = (t) => /^[A-Za-z_][A-Za-z0-9_]*(\[[^\]]*\])?\+?=/.test(t);

// Wrapper commands that merely run another command: option set (with values) and leading positionals.
const NOVAL = new Set();
const WRAP = {
  env: { valued: new Set(['-u', '--unset', '-C', '--chdir', '-S', '--split-string', '--default-signal', '--block-signal']), pos: 0 },
  command: { valued: NOVAL, pos: 0 },
  builtin: { valued: NOVAL, pos: 0 },
  exec: { valued: new Set(['-a']), pos: 0 },
  sudo: { valued: new Set(['-u', '-g', '-h', '-p', '-C', '-D', '-R', '-T', '-U', '-r', '-t', '--user', '--group', '--host', '--prompt',
    '--chdir', '--role', '--type', '--other-user', '--close-from', '--command-timeout', '--chroot']), pos: 0 },
  doas: { valued: new Set(['-u', '-C']), pos: 0 },
  nice: { valued: new Set(['-n', '--adjustment']), pos: 0 },
  nohup: { valued: NOVAL, pos: 0 },
  time: { valued: new Set(['-f', '-o', '--format', '--output']), pos: 0 },
  timeout: { valued: new Set(['-k', '-s', '--kill-after', '--signal']), pos: 1 },
  stdbuf: { valued: new Set(['-i', '-o', '-e']), pos: 0 },
  setsid: { valued: NOVAL, pos: 0 },
  xargs: { valued: new Set(['-I', '-n', '-P', '-d', '-L', '-s', '-E', '-a', '-l', '--max-args', '--max-procs', '--delimiter', '--arg-file',
    '--max-lines', '--max-chars', '--eof']), pos: 0 },
  parallel: { valued: new Set(['-j', '--jobs', '-n', '--max-args', '-N', '-I', '-S', '--sshlogin', '-a', '--arg-file']), pos: 0 },
  ionice: { valued: new Set(['-c', '-n', '-p', '-P', '-u', '--class', '--classdata', '--pid', '--pgid', '--uid']), pos: 0 },
  taskset: { valued: NOVAL, pos: 1 }, // `taskset [-c] MASK cmd`
  chrt: { valued: NOVAL, pos: 1 }, // `chrt [opts] PRIORITY cmd`
  flock: { valued: new Set(['-w', '-E', '--timeout', '--conflict-exit-code']), pos: 1 }, // `flock LOCKFILE cmd`
  chroot: { valued: new Set(['--userspec', '--groups']), pos: 1 }, // `chroot NEWROOT cmd`
  nsenter: { valued: new Set(['-t', '--target', '-S', '--setuid', '-G', '--setgid', '-w', '--wd']), pos: 0 },
  unshare: { valued: new Set(['--map-user', '--map-group', '--propagation', '-S', '-G', '--setuid', '--setgid', '-w', '--wd']), pos: 0 },
  watch: { valued: new Set(['-n', '--interval', '-d']), pos: 0 },
  busybox: { valued: NOVAL, pos: 0 },
  // shell keywords that can precede a command word
  if: { valued: NOVAL, pos: 0 }, then: { valued: NOVAL, pos: 0 }, do: { valued: NOVAL, pos: 0 },
  else: { valued: NOVAL, pos: 0 }, elif: { valued: NOVAL, pos: 0 }, while: { valued: NOVAL, pos: 0 },
  until: { valued: NOVAL, pos: 0 }, '!': { valued: NOVAL, pos: 0 }, '{': { valued: NOVAL, pos: 0 },
};

// Returns the command with wrappers/assignments removed; `.assigns` lists every VAR=value seen in front of it
// (leading assignments and `env VAR=value`), which matter for git (GIT_CONFIG_*, HOME, PATH ...).
function stripPrefix(tokens) {
  const t = tokens.slice();
  const assigns = [];
  const extras = []; // `env -S 'cmd args'` split-string payloads: more command text to analyze
  t.assigns = assigns;
  t.extras = extras;
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
      if (b === 'env' && /^(-S|--split-string)$/.test(x)) { t.shift(); if (t.length) extras.push(t.shift()); continue; }
      if (b === 'env' && /^-S./.test(x)) { extras.push(t.shift().slice(2)); continue; }
      if (b === 'env' && /^--split-string=/.test(x)) { extras.push(t.shift().slice(15)); continue; }
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

function assignName(a) { return a.slice(0, a.indexOf('=')).replace(/\[.*/, '').replace(/\+$/, ''); }

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

const OPERATIONAL_BINS = new Set(['kargo', 'oc', 'kubectl', 'helm', 'argocd', 'tkn']);
// Operational classification is a READ ALLOWLIST: for an operational binary every invocation is 'operational' unless
// its verb (and, where the verb has sub-verbs, the sub-verb) is a known read-only one. A mutating verb we have never
// heard of (kubectl label, oc adm, kargo approve, argocd app rollback, tkn rerun ...) therefore fails CLOSED instead of
// slipping through a denylist.
const KUBE_READ = new Set(['get', 'describe', 'logs', 'top', 'explain', 'version', 'diff', 'events', 'api-resources',
  'api-versions', 'cluster-info', 'wait', 'help', 'completion', 'whoami', 'status', 'projects', 'kustomize']);
const KUBE_READ_SUB = {
  rollout: new Set(['status', 'history']),
  config: new Set(['view', 'current-context', 'get-contexts', 'get-clusters', 'get-users']),
  auth: new Set(['can-i', 'whoami']),
  plugin: new Set(['list'])
};
const HELM_READ = new Set(['list', 'ls', 'status', 'get', 'history', 'show', 'template', 'lint', 'version', 'env', 'search', 'help', 'completion']);
// Known mutating verbs. Defence in depth for kubectl/oc/helm: a read verb at pos[0] does NOT make the call safe if ANY other
// positional is one of these, because a mis-parsed flag (boolean vs valued) could have shifted the real verb out of pos[0].
// Cost: a resource literally named `delete` (`kubectl get pod delete`) is guarded -- fail closed.
const KUBE_MUTATING = new Set(['delete', 'apply', 'create', 'patch', 'replace', 'scale', 'edit', 'set', 'label', 'annotate', 'taint',
  'drain', 'cordon', 'uncordon', 'exec', 'run', 'expose', 'autoscale', 'cp', 'port-forward', 'attach', 'debug', 'adm', 'rsh', 'rsync',
  'new-app', 'start-build', 'import-image']);
// Verbs that are ALSO common resource / release / subcommand names (rollout, certificate, tag, policy, proxy; helm test|repo|plugin|pull)
// are left out so `kubectl get rollout x`, `kubectl get certificate`, `helm search repo x`, `helm get values test` stay read-only.
const HELM_MUTATING = new Set(['install', 'upgrade', 'uninstall', 'delete', 'rollback', 'push']);
const ARGO_READ_SUB = new Set(['get', 'list', 'ls', 'diff', 'history', 'manifests', 'logs', 'resources', 'wait', 'get-resource']);
const ARGO_READ_TOP = new Set(['version', 'help', 'completion']);
const KARGO_READ = new Set(['get', 'list', 'ls', 'describe', 'version', 'help', 'completion']);
const TKN_READ_SUB = new Set(['list', 'ls', 'describe', 'desc', 'logs', 'version']);
const TKN_READ_TOP = new Set(['version', 'help', 'completion']);
// Flags (before the verb) that consume the NEXT token as their value. ONLY genuine single-value flags belong here: a
// BOOLEAN flag listed here (--insecure-skip-tls-verify, --kube-insecure-skip-tls-verify, --debug, --plaintext ...) makes
// operationalPositionals swallow the VERB as its "value" (`helm --kube-insecure-skip-tls-verify upgrade list x` -> verb
// `list` => unguarded). An UNLISTED flag is handled by the "value-looking token after a flag" rule in
// operationalPositionals (a bare word after it is kept as the verb candidate and fails closed), so when unsure, leave it out.
const OP_VALUED = new Set([
  '-n', '--namespace', '--context', '--kube-context', '--kubeconfig', '-s', '--server', '--user', '--cluster',
  '-p', '--project', '--as', '--as-group', '--as-uid', '-l', '--selector', '-f', '--filename', '-k', '--kustomize',
  '-o', '--output', '--timeout', '--token', '--auth-token', '--kube-token', '--certificate-authority',
  '--client-certificate', '--client-key', '-v', '--v', '--vmodule', '--loglevel', '--log-level', '--request-timeout',
  '--config', '--config-path', '--tls-server-name', '--username', '--password', '--cache-dir', '--profile',
  '--profile-output', '--kube-apiserver', '--field-selector', '--grpc-web-root-path',
  '--argocd-context', '--controller-namespace', '--registry-config', '--repository-config', '--repository-cache',
  '--burst-limit', '--qps', '--kube-as-user', '--kube-as-group', '--kube-ca-file'
]);
const BARE_WORD = /^[A-Za-z][A-Za-z-]*$/;

// Positional words of an operational CLI invocation, in order. Tokens consumed as the value of a known valued flag are
// dropped. A token right after an UNKNOWN flag is dropped only when it LOOKS like a value (`6`, `5s`, `/x`, `a=b`): a bare
// alphabetic word there is as likely to be the verb (boolean flag + verb), so it is kept as a candidate and, being an
// unknown verb, fails closed. A dynamic token ($VERB, "$@") is always kept. Scanning stops at `--` (the remote command of
// `kubectl exec pod -- ...`); `sep` reports whether it was seen. `help` = --help/-h before `--`.
function operationalPositionals(args) {
  const pos = [];
  let help = false;
  let sep = false;
  let afterFlag = false;
  for (let i = 0; i < args.length; i++) {
    const a = args[i];
    if (a === '--') { sep = true; break; }
    if (a.startsWith('-')) {
      if (a === '--help' || a === '-h') help = true;
      if (OP_VALUED.has(a)) { i++; afterFlag = false; continue; }
      afterFlag = !a.includes('=');
      continue;
    }
    if (afterFlag && !DYN.test(a) && !BARE_WORD.test(a)) { afterFlag = false; continue; }
    afterFlag = false;
    pos.push(a);
  }
  return { pos, help, sep };
}

function isOperationalMutation(bin, args) {
  const b = bin.toLowerCase();
  if (!OPERATIONAL_BINS.has(b)) return false;
  const { pos: rawPos, help, sep } = operationalPositionals(args);
  if (help) return false; // `kubectl delete pod x --help` prints usage and exits
  if (!rawPos.length) {
    // bare invocation / --version / -h: read-only. Tokens only after `--` have no verb => unknown => guarded.
    return sep;
  }
  // A dynamic verb or sub-verb ($VERB, "$@") can never match a read allowlist below, so it is guarded (the same fail-closed
  // rule as a dynamic git/gh/glab subcommand) without a special case; dynamic ARGUMENTS after a read verb are fine.
  const pos = rawPos.map((x) => x.toLowerCase());
  if (b === 'kubectl' || b === 'oc') {
    const sub = KUBE_READ_SUB[pos[0]];
    if (sub) return !sub.has(pos[1]) || pos.slice(2).some((x) => KUBE_MUTATING.has(x));
    return !KUBE_READ.has(pos[0]) || pos.slice(1).some((x) => KUBE_MUTATING.has(x));
  }
  if (b === 'helm') return !HELM_READ.has(pos[0]) || pos.slice(1).some((x) => HELM_MUTATING.has(x));
  if (b === 'kargo') return !KARGO_READ.has(pos[0]);
  if (b === 'argocd') {
    if (ARGO_READ_TOP.has(pos[0])) return false;
    // `argocd app|appset|proj|repo|cluster|... <verb>`; `app actions list` is read, `app actions run` is not.
    if (pos[1] === 'actions') return pos[2] !== 'list';
    return !ARGO_READ_SUB.has(pos[1]);
  }
  if (b === 'tkn') {
    if (TKN_READ_TOP.has(pos[0])) return false;
    return !TKN_READ_SUB.has(pos[1]);
  }
  return true;
}

function combineCategories(c1, c2) {
  if (c1 === 'git_merge' || c2 === 'git_merge') return 'git_merge';
  if (c1 === 'operational' || c2 === 'operational') return 'operational';
  return null;
}

function analyzeTokens(tokens, depth, strict) {
  const redirs = tokens.redirs || [];
  const t = stripPrefix(tokens);
  const assigns = t.assigns || [];
  const src = SRC.cur;
  if (t.extras && t.extras.length) return analyzeString(`${t.extras.join(' ')} ${t.join(' ')}`, depth + 1, true); // env -S 'git merge x'
  if (!t.length) { // assignment-only / redirect-only command
    return (configEnvGuard(assigns, '') || configFileWriteGuard('', [], redirs, src)) ? 'git_merge' : null;
  }
  const rawBin = t[0];
  const bin = base(rawBin).toLowerCase();
  const rest = t.slice(1);
  if (/\s/.test(rawBin)) return analyzeString(t.join(' '), depth + 1, true); // `sudo -s 'git merge x'`: the "command" is a script
  if (configEnvGuard(assigns, bin)) return 'git_merge';
  if (ENV_BUILTINS.has(bin) && configEnvGuard(rest.filter(isAssign), '')) return 'git_merge'; // export GIT_CONFIG_COUNT=1
  if (configFileWriteGuard(bin, rest, redirs, src)) return 'git_merge';
  if (bin === 'eval') return 'git_merge';
  // `[` / `[[` are the shell test builtins, not a glob character class: `[ -f x ] && echo y` is not a dynamic command word.
  if (bin !== '[' && bin !== '[[' && DYN.test(bin)) { // dynamic command word (e.g. $CMD, $TOOL)
    if (rest.length > 0 && rest.every((x) => x === '--help' || x === '-h' || x === '--version' || x === '-v')) {
      return null;
    }
    return 'git_merge';
  }
  if (SHELLS.has(bin)) {
    const ci = rest.findIndex((x) => /^-[A-Za-z]*c[A-Za-z]*$/.test(x));
    if (ci !== -1 && rest[ci + 1] !== undefined) return analyzeString(rest[ci + 1], depth + 1, true);
    // `bash -s [-- args]` reads the program from stdin even when positional args follow.
    if (rest.some((x) => /^-[A-Za-z]*s[A-Za-z]*$/.test(x))) return 'git_merge';
    // No -c and no script file: the shell reads its program from stdin (`... | bash`, `bash <<EOF`, `bash -s`,
    // here-strings) which cannot be inspected => needs approval. `bash script.sh` is NOT flagged (file body unseen).
    const hasScript = rest.some((x, k) => !x.startsWith('-') && !(k > 0 && /^-[A-Za-z]*[oO]$/.test(rest[k - 1])));
    return hasScript ? null : 'git_merge';
  }
  if (bin === 'su' || bin === 'script' || bin === 'runuser') { // `su -c 'cmd' user`, `script -qc 'cmd' file`
    const ci = rest.findIndex((x) => /^-[A-Za-z]*c$/.test(x) || /^--command(=|$)/.test(x));
    if (ci === -1) return null;
    const sc = rest[ci].includes('=') ? rest[ci].slice(rest[ci].indexOf('=') + 1) : rest[ci + 1];
    return sc === undefined ? null : analyzeString(sc, depth + 1, true);
  }
  if (bin === 'find') {
    // Accumulate across EVERY -exec/-execdir/-ok/-okdir clause: `find . -exec oc rsh x \; -exec git merge m \;` is
    // git_merge whatever the clause order. Only git_merge short-circuits.
    let category = null;
    for (let i = 0; i < rest.length; i++) {
      if (/^-(exec|execdir|ok|okdir)$/.test(rest[i])) {
        let j = i + 1; const sub = [];
        while (j < rest.length && rest[j] !== ';' && rest[j] !== '+') sub.push(rest[j++]);
        category = combineCategories(category, analyzeTokens(sub, depth + 1, strict));
        if (category === 'git_merge') return category;
      }
    }
    return category;
  }
  if (bin === 'git') return gitGuard(rest, depth) ? 'git_merge' : null;
  if (bin === 'gh' || bin === 'glab') {
    const pos = positionals(rest);
    // Only the command path (group/action) being dynamic is suspicious (`gh pr $ACT 5`); a dynamic ID/arg in a
    // read-style call (`gh pr view "$PR"`, `glab mr list --label "$L"`) is not.
    if (pos.slice(0, 2).some((x) => DYN.test(x))) return 'git_merge';
    if (hasSubseq(pos, bin === 'gh' ? ['pr', 'merge'] : ['mr', 'merge'])) return 'git_merge';
    if (pos[0] && pos[0].toLowerCase() === 'api') return httpGuard(bin, rest) ? 'git_merge' : null;
    return null;
  }
  if (HTTP_CLIENTS.has(bin)) return httpGuard(bin, rest) ? 'git_merge' : null;
  if (isOperationalMutation(bin, rest)) return 'operational';
  return null;
}

// Source text currently being analyzed (config-file checks look for `.git` anywhere in it).
const SRC = { cur: '' };
function analyzeString(str, depth, strict) {
  if (depth > MAX_DEPTH) return 'git_merge'; // pathological nesting => fail closed
  const prev = SRC.cur;
  SRC.cur = str;
  try {
    const { cmds, nested, unsafe } = parseShell(str);
    if (unsafe) return 'git_merge'; // unterminated construct: cannot be analyzed reliably => guarded
    let category = null;
    for (const c of cmds) {
      const cat = analyzeTokens(c, depth, strict);
      category = combineCategories(category, cat);
      if (category === 'git_merge') return 'git_merge';
    }
    for (const nsub of nested) {
      const cat = analyzeString(nsub, depth + 1);
      category = combineCategories(category, cat);
      if (category === 'git_merge') return 'git_merge';
    }
    return category;
  } finally {
    SRC.cur = prev;
  }
}

function shellCategory(cmd) {
  try { return analyzeString(cmd, 0); } catch { return 'git_merge'; }
}

function shellNeedsGuard(cmd) {
  return shellCategory(cmd) !== null;
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
// Cluster / delivery MCP servers and tool nouns whose WRITE tools are 'operational' (sysadmin + event approval), not git_merge.
// Matched on the SERVER part of mcp__<server>__<tool> (first name token) and, for un-prefixed names, on the tool tokens.
const OPERATIONAL_SERVER_TOKENS = new Set(['argocd', 'argo', 'k8s', 'kube', 'kubernetes', 'kubectl', 'openshift', 'ocp', 'oc', 'helm', 'kargo', 'tekton', 'tkn']);
// Un-prefixed tool names (`delete_namespace`, `patch_secret`) are matched on these nouns. Generic words that other MCPs use for
// non-cluster objects (job, cluster, release, project, pipeline, role, route) are deliberately NOT here.
const OPERATIONAL_NOUNS = new Set(['application', 'applications', 'pod', 'pods', 'deployment', 'deployments', 'promotion', 'promotions',
  'freight', 'kargo', 'helm', 'k8s', 'kubectl', 'argocd', 'namespace', 'namespaces', 'node', 'nodes', 'secret', 'secrets', 'configmap',
  'configmaps', 'service', 'services', 'serviceaccount', 'serviceaccounts', 'statefulset', 'statefulsets', 'daemonset', 'daemonsets',
  'replicaset', 'replicasets', 'cronjob', 'cronjobs', 'ingress', 'ingresses', 'pv', 'pvc', 'pvcs', 'persistentvolume', 'persistentvolumes',
  'persistentvolumeclaim', 'persistentvolumeclaims', 'rolebinding', 'rolebindings', 'clusterrole', 'clusterrolebinding', 'pipelinerun',
  'pipelineruns', 'taskrun', 'taskruns']);
// Mutating verbs for those tools (WRITE/HARD_WRITE minus the git-only ones, plus cluster-specific ones).
const OPERATIONAL_WRITE = new Set([...WRITE, ...HARD_WRITE, 'restart', 'evict', 'drain', 'cordon', 'uncordon', 'taint', 'label', 'annotate',
  'terminate', 'refresh', 'install', 'uninstall', 'upgrade', 'replace', 'expose', 'autoscale', 'debug', 'attach', 'copy', 'cp', 'forward', 'rerun']);
const FAMILY_TOKENS = new Set(['team', 'bb', 'svc', 'ka']); // comms / blackboard / journal / kubearchive MCPs
// Tokens allowed after `browser_` for read-only roles (snapshot, take_screenshot, console_messages, network_requests,
// network_request, find, tabs, wait_for, navigate, navigate_back, resize, hover, click, close).
const BROWSER_READ = new Set(['snapshot', 'take', 'screenshot', 'console', 'messages', 'network', 'requests', 'request', 'find',
  'tabs', 'wait', 'for', 'navigate', 'back', 'resize', 'hover', 'click', 'close']);
// Native (non-MCP) tools that never mutate: agy built-ins and Claude Code's read/search/orchestration tools.
const NATIVE_ALLOW = new Set(['task_boundary', 'notify_user', 'browser_subagent',
  'read', 'grep', 'glob', 'ls', 'webfetch', 'websearch', 'todowrite', 'task', 'agent', 'exitplanmode', 'enterplanmode',
  'bashoutput', 'killshell', 'notebookread', 'skill', 'askuserquestion', 'taskoutput']);
// Native file-mutation tools: handled by validate-mutations.sh MUTATION_TOOLS (keep the two lists in sync).
const NATIVE_MUTATION = new Set(['write_to_file', 'replace_file_content', 'multi_replace_file_content', 'edit_file',
  'write', 'edit', 'multiedit', 'notebookedit']); // last four: Claude Code's file-mutation tools

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

// Returns { guard, readok, guardCategory } where guardCategory is 'git_merge' | 'operational' | null (null iff !guard).
function classifyTool(name, args) {
  const lname = name.toLowerCase();
  if (NATIVE_MUTATION.has(lname)) return { guard: false, readok: false, guardCategory: null };
  const a = args && typeof args === 'object' ? args : {};
  // mcp__<server>__<tool>: classify on the tool part only, so server names cannot masquerade as verbs/families.
  const parts = name.split('__');
  const toolPart = parts.length >= 3 && /^mcp$/i.test(parts[0]) ? parts.slice(2).join('__') : name;
  const tokens = nameTokens(toolPart);
  const set = new Set(tokens);
  const verb = tokens.find((t) => !PREFIX_TOKENS.has(t)) || '';
  const readFirst = READ_VERBS.has(verb);
  let guard = false;
  let guardCategory = null;

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

  if (guard) guardCategory = 'git_merge'; // VCS merge / default-branch write / merge-endpoint API call
  // Cluster / delivery MCP tools (k8s, OpenShift, ArgoCD, Helm, Kargo, Tekton): a MUTATING verb is operational. A VCS merge
  // verdict above always wins (git_merge is the stricter, SHA-bound rule).
  if (!guard && !readFirst) {
    const serverTokens = parts.length >= 3 && /^mcp$/i.test(parts[0]) ? nameTokens(parts[1]) : [];
    const clusterServer = serverTokens.length > 0 && OPERATIONAL_SERVER_TOKENS.has(serverTokens[0]) && !serverTokens.includes('archive');
    const clusterNoun = tokens.some((t) => OPERATIONAL_NOUNS.has(t));
    const opWrite = tokens.some((t) => OPERATIONAL_WRITE.has(t));
    if ((clusterServer || clusterNoun) && opWrite && !FAMILY_TOKENS.has(verb)) { guard = true; guardCategory = 'operational'; }
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
  return { guard, readok, guardCategory };
}

// ---------------------------------------------------------------------------------------------
// Approval verdict (shared by validate-mutations.sh and the Claude HTTP hook)
// ---------------------------------------------------------------------------------------------
// category 'git_merge' (default; anything that is not exactly 'operational'): approval AND approved_mr_sha === local HEAD.
// category 'operational': approval only (no commit to bind to); the ROLE gate (sysadmin) is enforced by the callers.
// `approved` must be the boolean true: truthy non-booleans ("false", 1, {}) are rejected.
function approvalVerdict(approval, localSha, category = 'git_merge') {
  if (category !== 'operational') category = 'git_merge';
  if (!approval || typeof approval !== 'object' || approval.approved !== true) {
    if (category === 'operational') {
      return { allow: false, reason: 'Operational mutation REFUSED: event not approved by authorized maintainer (bb_get_approval/proxy/approval reports approved=false or was unreachable).' };
    }
    return { allow: false, reason: 'Merge REFUSED: event not approved by authorized maintainer (bb_get_approval/proxy/approval reports approved=false or was unreachable).' };
  }
  if (category === 'operational') {
    return { allow: true, reason: '' };
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
const SHELL_TOOLS = new Set(['bash', 'shell', 'run_in_terminal', 'execute_command', 'run_shell_command', 'run_command', 'execute']);

// Classify a PreToolUse payload (agy {toolCall:{name,args}} or Claude {tool_name,tool_input}).
// Returns null if malformed, else { name, guard, readok, cmd, isShell, guardCategory }.
function classify(d, opts = {}) {
  CTX.cwd = opts.cwd || undefined;
  CTX.spawns = 0;
  CTX.aliasCache = new Map();
  CTX.deadline = Date.now() + (opts.budgetMs || 1500);
  if (!d || typeof d !== 'object' || Array.isArray(d)) return null;
  let name = d.toolCall?.name || d.tool_name || d.functionCall?.name || '';
  if (!name || typeof name !== 'string') return null;
  name = name.trim();
  if (name.includes('|||')) return null; // would shift the `|||`-delimited fields of main()'s output (guard=0 => fast allow)
  const rawCmd = d.toolCall?.args?.CommandLine ?? d.toolCall?.args?.command ?? (d.tool_input && d.tool_input.command) ?? (d.functionCall?.args?.command) ?? '';
  if (rawCmd !== null && rawCmd !== undefined && typeof rawCmd !== 'string') return null;
  const cmd = (rawCmd || '').trim();
  const args = d.toolCall?.args ?? d.tool_input ?? d.functionCall?.args ?? {};
  const isShell = SHELL_TOOLS.has(name.toLowerCase());
  if (isShell) {
    const cat = cmd ? shellCategory(cmd) : null;
    return { name, guard: cat !== null, readok: false, cmd, isShell, guardCategory: cat };
  }
  const c = classifyTool(name, args);
  return { name, guard: c.guard, readok: c.readok, cmd, isShell, guardCategory: c.guardCategory ?? (c.guard ? 'git_merge' : null) };
}

function main(raw) {
  const r = classify(JSON.parse(raw));
  if (!r) return '__MALFORMED__';
  const guardField = r.guardCategory === 'operational' ? 2 : (r.guard ? 1 : 0);
  return `OK|||${r.name}|||${guardField}|||${r.readok ? 1 : 0}|||${r.cmd}`;
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
  } else if (process.argv[2] === '--readonly') {
    // node merge-guard.js --readonly <role>  =>  1 | 0 (shared predicate, ../roles.js)
    let ro = true;
    try { ro = require('../roles').isReadOnlyRoleName(process.argv[3]); } catch { ro = true; }
    process.stdout.write(ro ? '1' : '0');
  } else if (process.argv[2] === '--verdict') {
    // node merge-guard.js --verdict [--] <approval-json> <local-sha> [category]  =>  ALLOW||| | BLOCK|||<reason>
    const args = process.argv.slice(process.argv.indexOf('--verdict') + 1);
    if (args[0] === '--') args.shift();
    const [rawApproval, sha = '', category = 'git_merge'] = args;
    let approval = null;
    try { approval = JSON.parse(rawApproval || ''); } catch { approval = null; }
    const v = approvalVerdict(approval, sha, category);
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
