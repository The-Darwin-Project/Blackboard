// gemini-sidecar/claude-guard.js
// @ai-rules:
// 1. [Pattern]: Merge-approval guard for the CLAUDE path. Claude Code PreToolUse hooks are HTTP
//    (POST /hooks/pre-tool-use in http-handler.js); the agy path uses hooks/validate-mutations.sh.
//    Both share hooks/merge-guard.js (classification) + approvalVerdict (same approval/SHA contract).
// 2. [Contract]: Returns null (allow) or a denial reason string. Any failure while the call is
//    merge-class (analysis error, approval unreachable, git unavailable) => denial (fail CLOSED).
//    For MUTATING roles, calls that are not merge-class are never blocked here. READ-ONLY roles (roles.js) are
//    delegated wholesale to hooks/validate-mutations.sh (denylist + read-only tool allowlist + merge guard), on top of
//    Claude's engine-level permission files (cli-executor.js ROLE_SETTINGS_FILE). developer + atdd_green (deps.workStyle)
//    additionally runs that hook first for the test/spec tamper lock, then continues to the merge guard.
// 3. [Constraint]: Latency budget < the hook timeout (cli-setup.js, 10s): classify <=2.5s, approval
//    fetch <=3s, git rev-parse <=1s. classify runs in a CHILD PROCESS (async) so git never blocks the
//    event loop. A timed-out hook is a non-blocking error (fail-open), so we must answer with a denial
//    ourselves before that.
// 4. [Gotcha]: The Claude payload carries `cwd`; git lookups (bare `git push`, HEAD SHA) MUST run there,
//    not in the sidecar's own cwd.
const { execFile, spawn } = require('child_process');
const path = require('path');
const { isReadOnlyRoleName, isMutatingRoleName, normalizeRole } = require('./roles');
const mergeGuard = require('./hooks/merge-guard.js'); // approvalVerdict only; classification runs in a child process
const GUARD_SCRIPT = path.join(__dirname, 'hooks', 'merge-guard.js');
const VALIDATE_SCRIPT = path.join(__dirname, 'hooks', 'validate-mutations.sh');

const APPROVAL_TIMEOUT_MS = 3000;
const GIT_TIMEOUT_MS = 1000;
const READONLY_HOOK_TIMEOUT_MS = 9000; // validate-mutations.sh enforces its own 8s budget; this is the hard kill
const CLASSIFY_TIMEOUT_MS = 2500; // child kill deadline; the child enforces its own 1.5s git budget

function gitHead(cwd) {
  return new Promise((resolve) => {
    execFile('git', ['rev-parse', 'HEAD'], { cwd: cwd || undefined, timeout: GIT_TIMEOUT_MS, killSignal: 'SIGKILL' },
      (err, out) => resolve(err ? '' : String(out).trim()));
  });
}

function withTimeout(promise, ms) {
  let timer;
  const timeout = new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('timeout')), ms); });
  return Promise.race([promise, timeout]).finally(() => clearTimeout(timer));
}

// Classification shells out to git (bare-push / alias lookups). Doing that synchronously would block the sidecar's
// event loop (WS, /health, other hooks), so run merge-guard.js --json as a child process instead. Resolves to the
// classify() result, or null when malformed. Rejects on spawn failure/timeout/garbled output (caller fails closed).
function classifyInChild(payload) {
  return new Promise((resolve, reject) => {
    const cwd = typeof payload?.cwd === 'string' ? payload.cwd : '';
    const child = spawn(process.execPath, [GUARD_SCRIPT, '--json'], {
      env: { ...process.env, MERGE_GUARD_CWD: cwd }, stdio: ['pipe', 'pipe', 'ignore'],
    });
    let out = '';
    const killer = setTimeout(() => { child.kill('SIGKILL'); reject(new Error('classify timeout')); }, CLASSIFY_TIMEOUT_MS);
    child.stdout.on('data', (c) => { out += c; });
    child.on('error', (e) => { clearTimeout(killer); reject(e); });
    child.on('close', () => {
      clearTimeout(killer);
      try { resolve(JSON.parse(out)); } catch (e) { reject(e); }
    });
    child.stdin.on('error', () => {});
    child.stdin.end(JSON.stringify(payload ?? null));
  });
}

// Read-only roles on the Claude path get the SAME enforcement as the agy hook: run validate-mutations.sh (role
// denylist for shell, read-only tool allowlist for everything else, merge-approval guard) with the Claude payload
// as-is (it understands {tool_name, tool_input}). Spawned, never execSync: the sidecar event loop stays free (the
// script may call back into this process's /hook-status and /proxy/approval). Resolves to a denial reason or null.
function readOnlyRoleHook(payload, role, sidecarPort, workStyle) {
  return new Promise((resolve) => {
    const cwd = typeof payload?.cwd === 'string' && payload.cwd ? payload.cwd : undefined;
    const child = spawn('bash', [VALIDATE_SCRIPT], {
      cwd,
      env: {
        ...process.env,
        AGENT_ROLE: role,
        SIDECAR_PORT: String(sidecarPort || process.env.PORT || 9090),
        // Task-scoped work style (never the process-global env) so the ATDD tamper lock sees the running task's style.
        ...(workStyle ? { DARWIN_WORK_STYLE: workStyle } : {}),
      },
      stdio: ['pipe', 'pipe', 'ignore'],
    });
    let out = '';
    const fail = (why) => resolve(role
      ? `Read-only role '${role}': tool call could not be validated (${why}); failing closed.`
      : `Unresolved or empty agent role: tool call could not be validated (${why}); failing closed.`);
    const killer = setTimeout(() => { child.kill('SIGKILL'); fail('timeout'); }, READONLY_HOOK_TIMEOUT_MS);
    child.stdout.on('data', (c) => { out += c; });
    child.on('error', () => { clearTimeout(killer); fail('spawn error'); });
    child.on('close', () => {
      clearTimeout(killer);
      try {
        const d = JSON.parse(out);
        if (d.decision === 'allow') return resolve(null);
        return resolve(d.reason || (role ? `Read-only role '${role}': tool call denied.` : 'Unresolved or empty agent role: tool call denied.'));
      } catch { return fail('unparseable hook output'); }
    });
    child.stdin.on('error', () => {});
    child.stdin.end(JSON.stringify(payload ?? null));
  });
}

/**
 * @param {object} payload   Claude PreToolUse payload ({tool_name, tool_input, cwd, ...})
 * @param {{fetchApproval: () => Promise<object>, role?: string, sidecarPort?: number, workStyle?: string}} deps  fetchApproval
 *   resolves the Brain approval JSON for the current event; role is the resolved per-task role (read-only roles get the
 *   full hook policy); workStyle is the per-task work style (developer + atdd_green also gets the tamper-lock hook)
 * @returns {Promise<string|null>} denial reason, or null to allow
 */
async function claudeMergeGuard(payload, deps) {
  const role = normalizeRole(deps.role);
  if (!isMutatingRoleName(role)) return readOnlyRoleHook(payload, role, deps.sidecarPort);
  // ATDD Farley anti-tampering lock: developer + atdd_green runs the shared hook first (test/spec files are read-only).
  // A denial is final; an allow still falls through to the merge guard below, which stays intact.
  if (role === 'developer' && deps.workStyle === 'atdd_green') {
    const tamperDenial = await readOnlyRoleHook(payload, role, deps.sidecarPort, deps.workStyle);
    if (tamperDenial) return tamperDenial;
  }
  let result;
  try {
    result = await classifyInChild(payload);
  } catch {
    return 'Merge REFUSED: guard analysis failed (failing closed).';
  }
  if (!result) return 'Malformed or unrecognized tool payload (failing closed).';
  if (result.isShell && !result.cmd) return 'Shell tool call with empty or unextractable command (failing closed).';
  if (!result.guard) return null;

  let approval = null;
  try { approval = await withTimeout(deps.fetchApproval(), APPROVAL_TIMEOUT_MS); } catch { approval = null; }
  const sha = await gitHead(payload.cwd);
  const verdict = mergeGuard.approvalVerdict(approval, sha);
  return verdict.allow ? null : verdict.reason;
}

module.exports = { claudeMergeGuard };
