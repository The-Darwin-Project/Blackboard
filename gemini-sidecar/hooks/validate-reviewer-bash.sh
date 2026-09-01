#!/bin/bash
# gemini-sidecar/hooks/validate-reviewer-bash.sh
# @ai-rules:
# 1. [Pattern]: Claude Code subagent-level PreToolUse hook (frontmatter `hooks:` field,
#    NOT the global settings.json hook registered by cli-setup.js). Wired per-subagent
#    in gemini-sidecar/agents/reviewers/*.md frontmatter, matcher "Bash".
# 2. [Constraint]: Read hook JSON from STDIN only (never argv -- avoids ARG_MAX/E2BIG).
#    Exit 2 (with stderr message) blocks the tool call; exit 0 allows it.
# 3. [Contract]: Defense-in-depth blocklist, NOT an exhaustive sandbox. This is layer 3 of 3:
#    (1) reviewer subagents' `tools:` allowlist (no Write/Edit/NotebookEdit), (2) native
#    Claude Code `permissions.deny` rules (--settings code-reviewer-permissions.json,
#    engine-enforced, shell-operator-aware), (3) this hook (custom regex, catches what the
#    denylist can't express, e.g. flag-insertion, indirection, heredoc-interpreter forms).
#    See gemini-sidecar/rules/code_reviewer.md Hard Rules for the documented residual-risk
#    trade-off (bypass risk + false-positive risk, both accepted) and the tracked sandboxing
#    follow-up (OS-level enforcement, gated on an OpenShift SCC/bubblewrap compatibility probe).
# 4. [Contract]: MUST fail CLOSED (exit 2), never fail OPEN (exit 0), on any extraction
#    failure -- missing node, parse error, or timeout. An empty command is only ever
#    "allow" when extraction explicitly succeeded and the command was genuinely empty.
# 5. [Gotcha]: Read-only commands (git diff/log/blame, rg, find, cat) must NOT match any
#    pattern below -- reviewer subagents need these for their actual job.

set -uo pipefail

INPUT=$(cat) || { echo "Blocked: failed to read hook input, failing closed" >&2; exit 2; }

if ! command -v node >/dev/null 2>&1; then
  echo "Blocked: node runtime unavailable, cannot validate command safely, failing closed" >&2
  exit 2
fi

# Input goes to node via STDIN (not argv) so a large command can never hit execve's
# ARG_MAX and silently truncate to empty (the fail-open bypass found in review).
PARSED=$(printf '%s' "$INPUT" | timeout 5 node -e "
  let raw = '';
  process.stdin.on('data', (chunk) => { raw += chunk; });
  process.stdin.on('end', () => {
    try {
      const data = JSON.parse(raw);
      process.stdout.write('OK:' + ((data.tool_input && data.tool_input.command) || ''));
    } catch (e) {
      process.stdout.write('ERR');
    }
  });
" 2>/dev/null)
NODE_STATUS=$?

# Any failure (missing node, non-zero exit, timeout kill, or an ERR sentinel from a
# JSON parse failure) fails CLOSED. Only an explicit "OK:" prefix is treated as a
# successfully-parsed command (which may legitimately be empty).
if [ "$NODE_STATUS" -ne 0 ] || [[ "$PARSED" != OK:* ]]; then
  echo "Blocked: could not parse hook input or validator timed out, failing closed" >&2
  exit 2
fi

COMMAND="${PARSED#OK:}"
[ -z "$COMMAND" ] && exit 0

# Join backslash-newline continuations the way bash itself does when it executes this
# string (deletes both characters, concatenating with no inserted space). Real
# (non-continuation) newlines are deliberately NOT collapsed yet -- the position-based
# checks below run against JOINED (still multi-line) so grep's default per-line
# behavior gives `^` a free per-line anchor, catching a substitution/ANSI-C construct
# that starts a genuine new statement on its own line, not just after a literal ;/&/|.
# Collapsing to a single line happens AFTER those checks, right before UNQUOTED.
JOINED=$(printf '%s' "$COMMAND" | sed -z 's/\\\n//g')

# ANSI-C quoting ($'...') lets bash interpret \xNN/\oNNN escapes into arbitrary literal
# bytes at parse time -- the only standard construct that can produce a command name
# (e.g. "rm") without its literal text ever appearing anywhere in $COMMAND for the
# checks below to see. Legitimate reviewer commands (git/grep/find/rg/cat) never need
# this construct; block it outright rather than trying to decode every escape form.
if printf '%s\n' "$JOINED" | grep -q "\$'"; then
  echo "Blocked: ANSI-C quoting (\$'...') is not permitted -- reviewer subagents are read-only." >&2
  exit 2
fi

# A command that STARTS a statement with a substitution ($(...), a backtick
# expression, OR a bare variable expansion ($VAR, ${VAR})) is computing its own
# command name dynamically -- this covers ANY mechanism that decodes to a command
# name at runtime (base64, printf hex-escapes, echo -e, variable-splitting across
# multiple assignments like `A=r;B=m;$A$B`, etc.), since the check is on POSITION,
# not content or how the value was constructed. A dangerous verb split across two
# separately-assigned variables never appears as a contiguous substring anywhere in
# $COMMAND for the word-boundary checks below to see -- blocking ANY variable
# reference in the command-name position closes this regardless of how many
# variables the value was assembled from. Legitimate read-only commands use
# variables and substitution as an ARGUMENT (e.g. `git log $BRANCH`,
# `git log $(cat ref.txt)`), never as the executable position. Checked at
# start-of-command AND after any command separator (;, &, |) -- not just the very
# start of the whole string -- so `true; $(echo r)m -rf /data` and
# `A=r;B=m;$A$B -rf /data` are both caught, not just position 0.
# Running this against JOINED (real newlines still present, grep's default per-line
# mode) also catches a substitution/variable starting a genuine new statement on its
# own line (`some_cmd\n$(echo r)m -rf /data`) via the same `^` anchor.
# `["']*` tolerates the construct being wrapped in quotes (`"$(...)"`), which would
# otherwise dodge a bare `^\$\(` anchor while still resolving to the same
# dynamically-computed command at execution time.
if printf '%s\n' "$JOINED" | grep -qE '(^|[;&|])[[:space:]]*["'"'"']*(\$\(|`|\$[A-Za-z_{])'; then
  echo "Blocked: command substitution or variable expansion as the command itself is not permitted." >&2
  exit 2
fi

# NOW collapse any remaining bare (non-continuation) newlines into spaces for the
# rest of the pipeline -- the \b-boundary matching below doesn't depend on exact
# separator characters the way the position checks above did.
NORMALIZED=$(printf '%s' "$JOINED" | tr '\n' ' ')

# Strip quote characters before the main mutation check so quote-splitting (writing a
# dangerous token as e.g. r'm' -- bash concatenates adjacent quoted/unquoted strings
# into one "rm" token at parse time, but the literal bytes "r","'","m","'" never
# contain the contiguous substring "rm" for \b matching to see) can't hide a token.
UNQUOTED=$(printf '%s' "$NORMALIZED" | sed -E "s/[\"']//g")

# Strip backslash-escapes the same way: outside single quotes (already stripped above),
# bash removes a backslash and keeps the following character literally, so `r\m -rf`
# executes as `rm -rf` while the literal text "r\m" never contains the contiguous
# substring "rm" for \b matching to see -- the same underlying class of bypass as
# quote-splitting, just via a different bash quoting mechanism. `\.` -> `.` keeps the
# escaped character.
UNESCAPED=$(printf '%s' "$UNQUOTED" | sed -E 's/\\(.)/\1/g')

# Strip the common /dev/null redirect idiom before the mutation check so legitimate
# read-only commands (`grep ... 2>/dev/null`, `git log ... 2>/dev/null`) aren't
# false-positived by the generic `>` pattern below.
CHECK_COMMAND=$(printf '%s' "$UNESCAPED" | sed -E 's#[0-9]?>>?[[:space:]]*/dev/null##g')

# Each alternative below corresponds to a category documented in code_reviewer.md:
# git mutations | filesystem mutations | remote pipe/heredoc execution |
# infra/package mutations | shell-wrapper mutation | interpreter-mediated mutation.
# \b (word boundary) is used instead of anchoring to start-of-string/separator so
# prefixed (`sudo rm`), substituted (`$(rm ...)`, `` `rm ...` ``), and indirected
# (`X=rm; $X`) forms are all caught -- absolute-path invocation still matches too,
# since `\b` fires at the path-separator boundary regardless of what precedes it.
# `((-\S+)(\s+\S+)?\s+)*` between a command and its dangerous subcommand tolerates
# flag insertion, including flags with a separate value argument (`git -C dir commit`,
# `kubectl --context=prod apply`, `sed -e 's/a/b/' -i`), without loosening enough to
# skip over a non-flag token (so `git log -- commit_msg.txt` correctly does NOT match:
# `log`/`--`/the filename never start with `-` immediately after `git`, so the
# alternation is never reached at all -- there is no partial-match path that lands on
# "commit" later). Used everywhere a flag might carry a separate value (FLAG_GAP was
# previously narrower for kubectl/oc/sed -i than for git -- inconsistent, now unified).
GIT_GAP='((-\S+)(\s+\S+)?\s+)*'
# `git config` covers the alias-definition bypass (`git config --local alias.p push`
# followed by `git p ...`): the runtime-resolved alias name is opaque to any static
# check, so the fix is blocking the ability to DEFINE a new alias in the first place.
# `branch`/`switch` apply GIT_GAP a SECOND time between the subcommand and ITS OWN
# mutating flag (`git branch --no-color -d x`), not just between `git` and the
# subcommand -- and include the GNU long-option spelling (`--delete`, `--create`)
# alongside the short form, since flag-gap tolerance alone doesn't help if the flag
# text itself isn't in the alternation.
BLOCK_PATTERN="\\bgit\\s+${GIT_GAP}(commit|push|merge|rebase|reset\\s+.*--hard|checkout\\s+-[bB]|branch\\s+${GIT_GAP}(-[dD]\\b|--delete\\b)|tag\\s|clean\\s+-\\S*f|rm\\b|apply\\b|am\\b|switch\\s+${GIT_GAP}(-c\\b|--create\\b)|config\\b)"
BLOCK_PATTERN+='|\b(rm|mv|chmod|chown|dd|cp|ln|install|mkdir|touch)\b'
BLOCK_PATTERN+='|\bfind\b.*(-delete\b|-exec(dir)?\s+(rm|mv|chmod|chown|dd|cp)\b)'
# Redirect-mutation check excludes only `&` (fd duplication: `2>&1`, `>&2`) -- NOT
# digits generally. A prior version excluded `[^&0-9]`, meaning any redirect target
# starting with a digit (`>1x.sh`) evaded detection entirely; digit-prefixed fd-target
# redirects (`2>&1`) are still correctly excluded because `&` itself is the excluded
# char, immediately after `>`, regardless of what precedes `>`.
# sed/perl/ruby in-place: covers the attached-suffix short form (`-ibak`, no space --
# GNU sed/perl accept a suffix glued directly onto -i) and sed's GNU long option
# (`--in-place`, `--in-place=.bak`). A prior version only matched bare `sed -i` with
# mandatory trailing whitespace, which a suffix like `-ibak` defeated (nothing to
# anchor `\b` on between "-i" and "bak" -- they're one token), and didn't cover
# perl -i/ruby -i at all despite sharing the exact same in-place-edit semantics.
# Requires a preceding space so this doesn't fire on a quoted search pattern that
# happens to contain the substring "-i".
BLOCK_PATTERN+='|\b(sed|perl|ruby)\b.*[[:space:]]-i[a-zA-Z0-9._-]*\b|\bsed\b.*--in-place\b'
BLOCK_PATTERN+="|>\\s*[^&]|\\btee\\b"
# curl/wget/scp/ssh/rsync/sftp: no legitimate read-only-review need for any network
# tool -- block outright rather than only the curl|bash pipe form. This hook's own
# BLOCK_PATTERN previously relied on layer 2 (native permissions.deny) to cover bare
# curl/wget, but that layer likely does literal-prefix matching too and is just as
# exposed to the backslash-escape bypass fixed above (`c\url`) -- Claude Code's engine
# is closed-source here, so this hook can't assume layer 2 covers what its own
# blocklist doesn't. Blocking bare curl/wget here as well is a real backstop, not
# redundant with layer 2.
BLOCK_PATTERN+='|\b(curl|wget|scp|ssh|rsync|sftp)\b'
# /dev/tcp and /dev/udp are bash's built-in pseudo-devices for raw socket I/O --
# `bash -s < /dev/tcp/host/port` is a classic reverse-shell primitive that needs no
# curl/wget/nc and so evades every network-tool-name-based rule above.
BLOCK_PATTERN+='|/dev/(tcp|udp)/'
BLOCK_PATTERN+="|\\b(kubectl|oc)\\s+${GIT_GAP}(apply|delete|patch|edit|scale)\\b|\\bnpm\\s+(publish|version)\\b"
# Dependency-install commands can trigger arbitrary code (npm postinstall scripts,
# setup.py, Makefile recipes) as a CHILD process of a benign-looking parent -- the
# payload never appears in $COMMAND for BLOCK_PATTERN to inspect at all, so this
# can't be closed by pattern-matching the install command's own text; it has to be
# closed by never running the install in the first place. No legitimate review need:
# reviewing a diff evaluates existing code, it doesn't require installing new
# packages (confirmed by this review's own verification usage: pytest/tsc/helm are
# already-installed binaries, never triggered via a fresh install).
BLOCK_PATTERN+='|\b(npm|yarn|pnpm)\s+(install|add|ci)\b|\bpip3?\s+install\b|\bpoetry\s+(install|add)\b'
BLOCK_PATTERN+='|\bbundle\s+install\b|\bcargo\s+install\b|\bgo\s+install\b|\bgem\s+install\b|\bmake\b'
BLOCK_PATTERN+='|\b(bash|sh|zsh)\s+(-\S+\s+)*-c\b|\|\s*(bash|sh|zsh)\b'
BLOCK_PATTERN+='|\bpython3?\s+(-\S+\s+)*-c\b|\bnode\s+(-\S+\s+)*(-e|--eval)\b|\bperl\s+(-\S+\s+)*-e\b|\bruby\s+(-\S+\s+)*-e\b|\|\s*(python3?|node|perl|ruby|deno|bun)\b'
BLOCK_PATTERN+='|\b(bash|sh|zsh|python3?|node|perl|ruby|deno|bun)\s*(<<|<[[:space:]])'
# Bare "<interpreter> <file>" (no -c/-e/heredoc/pipe) runs an arbitrary script FILE --
# a pre-existing malicious script committed to the reviewed repo needs no write at
# all, only invocation, so write-detection above doesn't cover this path. The next
# token after the interpreter name must start with `-` (a flag: --version, -m, etc.)
# to be allowed; anything else (a path, a bare filename) is blocked. This is stricter
# than "no legitimate use exists" -- it is "no legitimate use was found in this
# review's own verification commands" (helm/tsc/pytest are standalone binaries, not
# `python3 <file>` invocations), so the trade-off leans safe over permissive. Includes
# awk/gawk/php/lua/Rscript/deno/bun alongside the original bash/sh/zsh/python/node/
# perl/ruby set -- an enumerated interpreter list is inherently open-ended (there is
# always one more exotic interpreter); this is documented, accepted residual risk,
# not a claim of completeness.
BLOCK_PATTERN+='|\b(bash|sh|zsh|python3?|node|perl|ruby|awk|gawk|php|lua|Rscript|deno|bun)\s+[^-[:space:]]'
# awk/gawk -i inplace is a GNU extension that mutates a file internally (the write
# never appears as a shell redirect, so the generic `>` check can't see it either).
BLOCK_PATTERN+='|\b(awk|gawk)\b.*-i[[:space:]]*inplace\b'
# eval/exec/source (and `.` as the POSIX alias for source) re-interpret a
# dynamically-constructed string as a NEW command -- a fundamentally different
# mechanism from direct substitution-as-command-name above, and one where the
# actual dangerous verb can be hidden entirely inside the string being evaluated
# (`eval "$(printf '\x72\x6d -rf /data')"`). No legitimate read-only review command
# needs to re-interpret constructed strings as code. The dot-sourcing form (`.
# script.sh`) is anchored to start-of-command/after a separator -- NOT a bare
# `\.\s+\S` anywhere in the string, which would false-positive on the extremely
# common "." meaning current directory (`find . -name`, `grep -r pattern .`,
# `rg foo .`) that appears constantly in legitimate reviewer commands.
BLOCK_PATTERN+='|\b(eval|exec|source)\b|(^|[;&|]\s*)\.\s+\S'
# Direct execution of a relative path (`./repro.sh`, `../scripts/x.sh`) runs an
# arbitrary FILE via its own shebang line -- no interpreter name (bash/python3/etc.)
# ever appears in the command for the interpreter-name rules above to match against.
# A git-tracked file with its executable bit set (preserved by git) plus a
# prompt-injected instruction to run it is a full code-execution path this hook
# would otherwise never see. Legitimate reviewer commands are all installed system
# binaries resolved via $PATH (git, grep, rg, helm, tsc, pytest, ...) -- none of them
# are legitimately invoked via a `./`-relative path.
BLOCK_PATTERN+='|(^|[;&|]\s*)\.\.?/'
# Credential file paths this environment actually writes or is likely to contain --
# block ANY command that references them as an argument, regardless of which command
# (cat/grep/find/head/tail/whatever) is used to read them. This is a backstop
# independent of whether the native permissions.deny Read-tool rules (layer 2, see
# code-reviewer-permissions.json) extend to a given Bash command -- the hook does
# not need to know or trust that answer since it inspects the argument text
# directly. Mirrors the same path set as the layer-2 Read deny rules.
BLOCK_PATTERN+='|(~/\.ssh|~/\.git-credentials|~/\.aws/credentials|~/\.kube/config|~/\.netrc|/tmp/git-creds-|/tmp/gh-token-map|/secrets/)'

if printf '%s\n' "$CHECK_COMMAND" | grep -qiE "$BLOCK_PATTERN"; then
  # Bound + redact the logged command: blocked commands can legitimately contain
  # secrets (e.g. a curl -H "Authorization: Bearer ...") that must not reach pod logs.
  # Covers bearer/basic auth headers (the full "Authorization: Bearer <token>" span,
  # not just leftmost-matching "Authorization:" and leaving the token itself exposed),
  # curl -u user:pass basic auth, generic key=value secrets, basic-auth-in-URL
  # (https://user:pass@host), and common vendor token prefixes (GitHub ghp_/gho_,
  # GitLab glpat-, AWS AKIA) -- not exhaustive, but closes the specific gaps found
  # in review (colon-delimited custom headers, PAT-prefixed tokens, -u flag).
  LOG_COMMAND=$(printf '%s' "$COMMAND" \
    | sed -E 's#://[^/@[:space:]]+:[^/@[:space:]]+@#://<redacted>@#g' \
    | sed -E 's/Authorization:[[:space:]]*(Bearer|Basic)[[:space:]]+[^[:space:]"'"'"']*/Authorization: \1 <redacted>/gi' \
    | sed -E 's/(^|[[:space:]])-u[[:space:]]+[^[:space:]]+:[^[:space:]]*/\1-u <redacted>/g' \
    | sed -E 's/([A-Za-z_-]*(token|password|apikey|api_key|secret)[[:space:]]*[:=])[[:space:]]*[^[:space:]]*/\1 <redacted>/gi' \
    | sed -E 's/(Authorization:[[:space:]]*token|PRIVATE-TOKEN|X-Auth-Token)[[:space:]]+[^[:space:]"'"'"']*/\1 <redacted>/gi' \
    | sed -E 's/\b(ghp_|gho_|ghu_|ghs_|glpat-|AKIA)[A-Za-z0-9_-]+/\1<redacted>/g' \
    | cut -c1-200)
  echo "Blocked: reviewer subagents are read-only. Command matched a mutation pattern: $LOG_COMMAND" >&2
  exit 2
fi

exit 0
