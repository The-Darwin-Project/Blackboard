// gemini-sidecar/claude-guard.js
// @ai-rules:
// 1. [Pattern]: Merge-approval guard for the CLAUDE path. Claude Code PreToolUse hooks are HTTP
//    (POST /hooks/pre-tool-use in http-handler.js); the agy path uses hooks/validate-mutations.sh.
//    Both share hooks/merge-guard.js (classification) + approvalVerdict (same approval/SHA contract).
// 2. [Contract]: Returns null (allow) or a denial reason string. Any failure while the call is
//    merge-class (analysis error, approval unreachable, git unavailable) => denial (fail CLOSED).
//    Calls that are NOT merge-class are never blocked here (read-only roles are enforced by Claude's
//    engine-level permission files, see cli-executor.js ROLE_SETTINGS_FILE).
// 3. [Constraint]: Latency budget < the hook timeout (cli-setup.js, 10s): classify <=2.5s, approval
//    fetch <=3s, git rev-parse <=1s. classify runs in a CHILD PROCESS (async) so git never blocks the
//    event loop. A timed-out hook is a non-blocking error (fail-open), so we must answer with a denial
//    ourselves before that.
// 4. [Gotcha]: The Claude payload carries `cwd`; git lookups (bare `git push`, HEAD SHA) MUST run there,
//    not in the sidecar's own cwd.
const { execFile, spawn } = require('child_process');
const path = require('path');
const mergeGuard = require('./hooks/merge-guard.js'); // approvalVerdict only; classification runs in a child process
const GUARD_SCRIPT = path.join(__dirname, 'hooks', 'merge-guard.js');

const APPROVAL_TIMEOUT_MS = 3000;
const GIT_TIMEOUT_MS = 1000;
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

/**
 * @param {object} payload   Claude PreToolUse payload ({tool_name, tool_input, cwd, ...})
 * @param {{fetchApproval: () => Promise<object>}} deps  fetchApproval resolves the Brain approval JSON for the current event
 * @returns {Promise<string|null>} denial reason, or null to allow
 */
async function claudeMergeGuard(payload, deps) {
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
