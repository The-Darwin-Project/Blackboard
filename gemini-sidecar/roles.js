// gemini-sidecar/roles.js
// @ai-rules:
// 1. [Pattern]: SINGLE source of truth for "is this role read-only?" -- used by cli-executor.js (agy plan mode,
//    Claude --settings deny file), credentials.js (read-only ArgoCD MCP), http-handler.js (/health toolRestrictions)
//    and claude-guard.js (Claude PreToolUse allowlist). Do not inline role lists elsewhere.
// 2. [Constraint]: Pure module, zero dependencies (it is also loaded from tests and hooks).
// 3. [Contract]: Names are normalised (trim, lower-case, [a-z0-9_-]); unlisted but read-only-LOOKING names
//    (qa_reviewer_agent, ARCHITECT_LEAD, security-analyst) count as read-only so a new/renamed role fails CLOSED.
// 4. [Gotcha]: hooks/validate-mutations.sh keeps its own READONLY_ROLES string (bash, no node dependency on the
//    fast path); keep it in sync with READ_ONLY_ROLES below.
const READ_ONLY_ROLES = new Set(['architect', 'explorer', 'code_reviewer', 'reviewer', 'security_analyst']);

function normalizeRole(role) {
  return String(role ?? '').trim().toLowerCase().replace(/[^a-z0-9_-]/g, '');
}

function isReadOnlyRoleName(role) {
  const r = normalizeRole(role);
  if (!r) return false; // unset role is handled by each caller's own fail-closed path
  return READ_ONLY_ROLES.has(r) || /review|analyst|explorer|architect/.test(r);
}

module.exports = { READ_ONLY_ROLES, normalizeRole, isReadOnlyRoleName };
