#!/bin/bash
# gemini-sidecar/hooks/validate-reviewer-bash.sh
# @ai-rules:
# 1. [Pattern]: Claude Code subagent-level PreToolUse hook (frontmatter `hooks:` field,
#    NOT the global settings.json hook registered by cli-setup.js). Wired per-subagent
#    in gemini-sidecar/agents/reviewers/*.md frontmatter, matcher "Bash".
# 2. [Constraint]: Read hook JSON from stdin, extract .tool_input.command. Exit 2 (with
#    stderr message) blocks the tool call; exit 0 allows it. Never hang -- no network calls.
# 3. [Contract]: Defense-in-depth blocklist, NOT an exhaustive sandbox. Mirrors security.py's
#    own non-exhaustive FORBIDDEN_PATTERNS philosophy. The primary safety boundary is the
#    reviewer subagents' `tools:` allowlist (no Write/Edit) + behavioral prompt -- this hook
#    is a secondary layer. See gemini-sidecar/rules/code_reviewer.md Hard Rules for the
#    documented residual-risk trade-off (bypass risk + false-positive risk, both accepted).
# 4. [Gotcha]: Read-only commands (git diff/log/blame, rg, find, cat) must NOT match any
#    pattern below -- reviewer subagents need these for their actual job.

INPUT=$(cat)
COMMAND=$(node -e "
  try {
    const data = JSON.parse(process.argv[1]);
    process.stdout.write((data.tool_input && data.tool_input.command) || '');
  } catch (e) {
    process.stdout.write('');
  }
" "$INPUT" 2>/dev/null)

[ -z "$COMMAND" ] && exit 0

# Each alternative below corresponds 1:1 to a category documented in code_reviewer.md:
# git mutations | filesystem mutations | remote pipe execution | infra/package mutations |
# shell-wrapper mutation | interpreter-mediated mutation.
BLOCK_PATTERN='\bgit\s+(commit|push|merge|rebase|reset\s+--hard|checkout\s+-b|branch\s+-[dD]|tag\s)'
BLOCK_PATTERN+='|(^|[;&|]\s*)(rm|mv|chmod|chown)\s|sed\s+-i|>\s*[^&0-9]|\btee\b'
BLOCK_PATTERN+='|(curl|wget).*\|\s*(sh|bash)'
BLOCK_PATTERN+='|\b(kubectl|oc)\s+(apply|delete|patch|edit|scale)\b|\bnpm\s+publish\b'
BLOCK_PATTERN+='|\b(bash|sh|zsh)\s+-c\b'
BLOCK_PATTERN+='|\bpython3?\s+-c\b|\bnode\s+-e\b|\bperl\s+-e\b|\bruby\s+-e\b'

if echo "$COMMAND" | grep -qE "$BLOCK_PATTERN"; then
  echo "Blocked: reviewer subagents are read-only. Command matched a mutation pattern: $COMMAND" >&2
  exit 2
fi

exit 0
