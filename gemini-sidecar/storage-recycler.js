// gemini-sidecar/storage-recycler.js
// @ai-rules:
// 1. [Constraint]: Closed-loop controller for CephFS volume headroom. Recycles above STORAGE_HIGH_WATERMARK (default 70%),
//    escalates to emergency LRU pruning above STORAGE_CRITICAL_WATERMARK (default 85%). Thresholds are validated in config.js.
// 2. [Pattern]: Protected CWDs are the UNION of candidateCwd + state.getCurrentTask().cwd + state.getLastTaskContext().cwd +
//    pinned task CWDs (pinTaskCwd/unpinTaskCwd), re-read LIVE immediately before every fs.rm -- never snapshot once per sweep.
// 3. [Gotcha]: A protected CWD equal to (or above) the volume root must NOT shield every sub-directory. Candidate C is protected by
//    P only if P === C, P is inside C, or C is inside P and P is a strict descendant of the root (see isProtectedPath).
// 4. [Pattern]: Re-entrancy mutex (_isRecycling) is released in a try/finally that starts on the very next statement; every state
//    getter is called INSIDE the try so a throwing getter can never wedge the mutex.
// 5. [Pattern]: Workspace activity = newest mtime of the dir, .git/{index,HEAD,FETCH_HEAD,darwin-active}, .darwin-active*/.active-*
//    markers and immediate children. developer and qe SHARE one PVC subPath, so activity must come from the filesystem, never
//    from per-process state alone. pinTaskCwd() heartbeats a marker for the task duration.
// 6. [Constraint]: Tier 1 refuses to descend into a symlinked results/ and requires realpath containment in the root. Tier 2/3 skip
//    symlinks, hidden dot-dirs, results, events, lost+found. Tier 3 is capped (STORAGE_MAX_TIER3_DELETIONS), age-gated
//    (STORAGE_TIER3_MIN_AGE_MS), isolates per-candidate rm errors, and stops on statfs failure or < HIGH watermark.
// 7. [Pattern]: statfs failure is reported as ok:false (never as a fake ok:true/finalRatio:0). Non-blocking fs.promises only.
// 8. [Pattern]: stopStorageRecycler() sets an abort flag checked between deletions and returns the in-flight sweep so SIGTERM can
//    drain cleanly. The pre-task timeout (STORAGE_PRETASK_TIMEOUT_MS) lives in cli-executor.js, not here.
// 9. [Pattern]: Sensitive denylist (/var/secrets, /secrets, /app, /tmp/agent-rules on path boundaries; /tmp/gh-token-map*,
//    /tmp/git-creds*, /tmp/.darwin-hooks* by stem) and the /data + /tmp jail are enforced inside isProtectedPath.

const fs = require('fs');
const path = require('path');
const state = require('./state');
const {
  STORAGE_SWEEP_INTERVAL_MS,
  STORAGE_HIGH_WATERMARK,
  STORAGE_CRITICAL_WATERMARK,
  STORAGE_STALE_MS,
  STORAGE_RESULTS_TTL_MS,
  STORAGE_TIER3_MIN_AGE_MS,
  STORAGE_MAX_TIER3_DELETIONS,
  STORAGE_ACTIVITY_HEARTBEAT_MS,
  resolveStorageRoot,
} = require('./config');

let _isRecycling = false;
let _inFlight = null;          // Promise of the running sweep (for stopStorageRecycler drain)
let _abortRequested = false;
const _pinned = new Map();     // resolved cwd -> { count, timer }

const ACTIVITY_MARKER = '.darwin-active';
const MAX_CHILD_STATS = 500;
// Top-level names that are never workspaces: protected from Tier 2/3 (results contents are handled by Tier 1).
const RESERVED_TOP_LEVEL = new Set(['results', 'events', 'lost+found']);

/**
 * Inspect storage volume headroom via Node.js native statfs.
 * Fail-safe: catches errors (ENOENT, unmounted volume, permission denied) and returns safe fallback object.
 */
async function getStorageUsage(mountPath) {
  try {
    const stat = await fs.promises.statfs(mountPath);
    const totalBytes = Number(stat.blocks) * Number(stat.bsize);
    const freeBytes = Number(stat.bavail) * Number(stat.bsize);
    const usedBytes = totalBytes - freeBytes;
    const usedRatio = totalBytes > 0 ? usedBytes / totalBytes : 0;
    return {
      ok: true,
      totalBytes,
      freeBytes,
      usedBytes,
      usedRatio,
    };
  } catch (err) {
    console.warn(`[storage-recycler] statfs failed for '${mountPath}': ${err.message}`);
    return {
      ok: false,
      totalBytes: 0,
      freeBytes: 0,
      usedBytes: 0,
      usedRatio: 0,
      error: err.message,
    };
  }
}

// Boundary-matched denylist (exact path or descendant).
const SENSITIVE_BOUNDARY_PREFIXES = [
  '/var/secrets',
  '/secrets',
  '/app',
  '/tmp/agent-rules',
];

// Stem-matched denylist: the real names carry a suffix (/tmp/git-creds-1234, /tmp/gh-token-map.json, /tmp/.darwin-hooks-1000).
const SENSITIVE_STEM_PREFIXES = [
  '/tmp/gh-token-map',
  '/tmp/git-creds',
  '/tmp/.darwin-hooks',
];

const isInside = (child, parent) => child.startsWith(parent + path.sep);

/**
 * Check whether a candidate directory or file is protected from deletion.
 *
 * @param {string} candidatePath
 * @param {string[]|string|null} protectedCwds  union of active/last/pinned/candidate task CWDs
 * @param {string} [workDir]  volume root. When given, the candidate must be strictly inside it, the root's reserved
 *   top-level names are protected, and a protected CWD that is the root (or above it) does not shield its sub-directories.
 *   When omitted, the conservative bidirectional hierarchy match applies.
 */
function isProtectedPath(candidatePath, protectedCwds, workDir) {
  if (!candidatePath || typeof candidatePath !== 'string') {
    return true;
  }
  const resolved = path.resolve(candidatePath);

  // Explicitly protect filesystem and jail root directories
  if (resolved === '/' || resolved === '/data' || resolved === '/tmp' || resolved === '/private/tmp') {
    return true;
  }

  // Path jail: strictly allow recycling only inside /data/ or /tmp/ (or macOS /private/tmp)
  if (!isInside(resolved, '/data') && !isInside(resolved, '/tmp') && !isInside(resolved, '/private/tmp')) {
    return true;
  }

  for (const prefix of SENSITIVE_BOUNDARY_PREFIXES) {
    if (resolved === prefix || isInside(resolved, prefix)) return true;
  }
  for (const stem of SENSITIVE_STEM_PREFIXES) {
    if (resolved.startsWith(stem)) return true;
  }

  const resolvedWorkDir = workDir && typeof workDir === 'string' ? path.resolve(workDir) : null;
  if (resolvedWorkDir) {
    // The root itself and anything above or outside it is never a recycle target.
    if (!isInside(resolved, resolvedWorkDir)) return true;

    const segments = path.relative(resolvedWorkDir, resolved).split(path.sep);
    if (segments[0] === 'events' || segments[0] === 'lost+found') return true;
    if (segments.length === 1 && segments[0] === 'results') return true;
  }

  const cwds = Array.isArray(protectedCwds) ? protectedCwds : [protectedCwds];
  for (const cwd of cwds) {
    if (!cwd || typeof cwd !== 'string') continue;
    const p = path.resolve(cwd);

    if (resolvedWorkDir) {
      if (resolved === p || isInside(p, resolved)) return true; // candidate is the CWD, or holds it
      // candidate inside the CWD -- only meaningful when the CWD is a real workspace below the root, not the root/ancestor
      if (isInside(p, resolvedWorkDir) && isInside(resolved, p)) return true;
    } else if (resolved === p || isInside(resolved, p) || isInside(p, resolved)) {
      return true;
    }
  }

  return false;
}

/**
 * Live union of every CWD that must be shielded right now. Called immediately before each deletion.
 */
function collectProtectedCwds(candidateCwd) {
  const cwds = [candidateCwd, state.getCurrentTask()?.cwd, state.getLastTaskContext()?.cwd, ..._pinned.keys()];
  return cwds.filter((c) => c && typeof c === 'string');
}

/**
 * Newest mtime among the workspace dir, git bookkeeping files, activity markers and immediate children.
 * Used instead of the directory's own mtime, which does not change when nested files are edited.
 */
async function getWorkspaceActivityMs(dirPath) {
  let newest = 0;
  const bump = async (p) => {
    try {
      const st = await fs.promises.lstat(p);
      if (st.mtimeMs > newest) newest = st.mtimeMs;
    } catch (_) { /* missing/unreadable: contributes nothing */ }
  };

  const probes = [
    dirPath,
    path.join(dirPath, '.git', 'index'),
    path.join(dirPath, '.git', 'HEAD'),
    path.join(dirPath, '.git', 'FETCH_HEAD'),
    path.join(dirPath, '.git', 'darwin-active'),
  ];
  try {
    const names = (await fs.promises.readdir(dirPath)).slice(0, MAX_CHILD_STATS);
    for (const name of names) probes.push(path.join(dirPath, name));
  } catch (_) { /* unreadable dir: fall back to the probes above */ }

  await Promise.all(probes.map(bump));
  return newest;
}

/**
 * Cross-process activity marker for the top-level workspace containing cwd. The developer and qe sidecars share one
 * PVC subPath, so each refreshes this file for its tasks and the other sidecar's sweeps see it in the filesystem.
 * Written inside .git/ when the workspace is a repo so it never dirties `git status`. Best effort; returns the path or null.
 */
async function touchActivityMarker(cwd, workDir) {
  try {
    if (!cwd || typeof cwd !== 'string') return null;
    const root = path.resolve(workDir || resolveStorageRoot(cwd));
    const resolvedCwd = path.resolve(cwd);
    if (!isInside(resolvedCwd, root)) return null;

    const top = path.join(root, path.relative(root, resolvedCwd).split(path.sep)[0]);
    if (RESERVED_TOP_LEVEL.has(path.basename(top))) return null;

    const topStat = await fs.promises.lstat(top);
    if (!topStat.isDirectory()) return null;

    const gitStat = await fs.promises.lstat(path.join(top, '.git')).catch(() => null);
    const marker = gitStat && gitStat.isDirectory()
      ? path.join(top, '.git', 'darwin-active')
      : path.join(top, ACTIVITY_MARKER);
    await fs.promises.writeFile(marker, `${process.pid} ${new Date().toISOString()}\n`);
    return marker;
  } catch (_) {
    return null;
  }
}

/**
 * Register a task CWD as in-flight. Safe to call while a sweep is running: the sweep re-reads the pinned set before every
 * deletion. Reference counted; starts a marker heartbeat so a sibling sidecar sharing the volume also sees the activity.
 */
function pinTaskCwd(cwd) {
  if (!cwd || typeof cwd !== 'string') return;
  const key = path.resolve(cwd);
  const entry = _pinned.get(key);
  if (entry) {
    entry.count += 1;
    return;
  }
  const timer = setInterval(() => { touchActivityMarker(key); }, STORAGE_ACTIVITY_HEARTBEAT_MS);
  if (timer.unref) timer.unref();
  _pinned.set(key, { count: 1, timer });
  touchActivityMarker(key);
}

function unpinTaskCwd(cwd) {
  if (!cwd || typeof cwd !== 'string') return;
  const key = path.resolve(cwd);
  const entry = _pinned.get(key);
  if (!entry) return;
  entry.count -= 1;
  if (entry.count <= 0) {
    clearInterval(entry.timer);
    _pinned.delete(key);
  }
}

/**
 * Delete one entry after re-validating, at the last possible moment, that it is still safe:
 * not shut down, not protected by the LIVE CWD union, and (unless it is a symlink, which rm only unlinks) still inside the
 * real volume root.
 * @returns {'removed'|'protected'|'aborted'|'escaped'}
 */
async function guardedRemove(target, ctx) {
  if (_abortRequested) return 'aborted';
  if (isProtectedPath(target, collectProtectedCwds(ctx.candidateCwd), ctx.workDir)) return 'protected';

  const st = await fs.promises.lstat(target);
  if (!st.isSymbolicLink()) {
    const real = await fs.promises.realpath(target);
    if (!isInside(real, ctx.realWorkDir)) return 'escaped';
  }
  await fs.promises.rm(target, { recursive: true, force: true });
  return 'removed';
}

/**
 * Execute tiered storage recycling.
 * Mutex-protected against concurrent invocations.
 */
async function runStorageRecycle(workDir, options = {}) {
  if (_abortRequested) {
    return { skipped: true, reason: 'shutting_down' };
  }
  if (_isRecycling) {
    return { skipped: true, reason: 'in-flight' };
  }
  let releaseInFlight;
  _inFlight = new Promise((resolve) => { releaseInFlight = resolve; });
  _isRecycling = true;
  try {
    const candidateCwd = options.candidateCwd || null;

    const initialUsage = await getStorageUsage(workDir);
    if (!initialUsage.ok) {
      return { ok: false, error: initialUsage.error };
    }

    const resolvedWorkDir = path.resolve(workDir);
    const ctx = { workDir: resolvedWorkDir, realWorkDir: await fs.promises.realpath(resolvedWorkDir), candidateCwd };
    const now = Date.now();
    let purgedCount = 0;
    let failedCount = 0;
    let lastValid = initialUsage;

    // Summarize the sweep. A statfs failure is reported as ok:false with the last good reading, never as a fake success.
    const settle = (usage) => {
      if (usage.ok) lastValid = usage;
      const cleanedBytes = Math.max(0, (initialUsage.usedBytes || 0) - (lastValid.usedBytes || 0));
      const summary = { purgedCount, failedCount, cleanedBytes };
      if (!usage.ok) return { ok: false, error: usage.error, ...summary, finalRatio: lastValid.usedRatio };
      return { ok: true, ...summary, finalRatio: usage.usedRatio };
    };

    // --- Tier 1: Volatile Sweep (results older than STORAGE_RESULTS_TTL_MS) ---
    const resultsDir = path.join(resolvedWorkDir, 'results');
    try {
      const resultsStat = await fs.promises.lstat(resultsDir);
      if (resultsStat.isSymbolicLink() || !resultsStat.isDirectory()) {
        console.warn(`[storage-recycler] Tier 1 skipped: '${resultsDir}' is not a plain directory (symlink refused)`);
      } else if (!isInside(await fs.promises.realpath(resultsDir), ctx.realWorkDir)) {
        console.warn(`[storage-recycler] Tier 1 skipped: '${resultsDir}' resolves outside '${ctx.realWorkDir}'`);
      } else {
        const entries = await fs.promises.readdir(resultsDir, { withFileTypes: true });
        for (const entry of entries) {
          if (_abortRequested) break;
          const fullPath = path.join(resultsDir, entry.name);
          try {
            const stat = await fs.promises.lstat(fullPath);
            if (now - stat.mtimeMs > STORAGE_RESULTS_TTL_MS) {
              if ((await guardedRemove(fullPath, ctx)) === 'removed') purgedCount++;
            }
          } catch (fileErr) {
            // File may have been removed or locked, ignore non-fatal
          }
        }
      }
    } catch (err) {
      if (err.code !== 'ENOENT') {
        console.warn(`[storage-recycler] Tier 1 sweep warning in '${resultsDir}': ${err.message}`);
      }
    }

    // Proactive check: if usage is already below high watermark, skip heavier tiers
    let currentUsage = await getStorageUsage(workDir);
    if (!currentUsage.ok || currentUsage.usedRatio < STORAGE_HIGH_WATERMARK || _abortRequested) {
      return settle(currentUsage);
    }

    // --- Tier 2: Stale Event Workspaces (*-evt-*, evt-*, *-baseline idle > STORAGE_STALE_MS) ---
    try {
      const entries = await fs.promises.readdir(resolvedWorkDir, { withFileTypes: true });
      for (const entry of entries) {
        if (_abortRequested) break;
        if (!entry.isDirectory()) continue;
        const name = entry.name;
        const isEventDir = name.includes('-evt-') || name.startsWith('evt-') || name.endsWith('-baseline');
        if (!isEventDir) continue;

        const dirPath = path.join(resolvedWorkDir, name);
        if (isProtectedPath(dirPath, collectProtectedCwds(candidateCwd), resolvedWorkDir)) continue;

        try {
          const activityMs = await getWorkspaceActivityMs(dirPath);
          if (now - activityMs > STORAGE_STALE_MS) {
            console.log(`[storage-recycler] Tier 2 evicting stale event workspace: ${dirPath}`);
            if ((await guardedRemove(dirPath, ctx)) === 'removed') purgedCount++;
          }
        } catch (dirErr) {
          failedCount++;
          console.warn(`[storage-recycler] Tier 2 could not evict '${dirPath}': ${dirErr.message}`);
        }
      }
    } catch (err) {
      console.warn(`[storage-recycler] Tier 2 sweep warning in '${resolvedWorkDir}': ${err.message}`);
    }

    // Check again after Tier 2
    currentUsage = await getStorageUsage(workDir);
    if (!currentUsage.ok || currentUsage.usedRatio < STORAGE_CRITICAL_WATERMARK || _abortRequested) {
      return settle(currentUsage);
    }

    // --- Tier 3: Emergency LRU Prune of Idle Cloned Repositories (>= critical watermark) ---
    try {
      const entries = await fs.promises.readdir(resolvedWorkDir, { withFileTypes: true });
      const candidates = [];
      for (const entry of entries) {
        if (!entry.isDirectory()) continue;
        if (entry.name.startsWith('.') || RESERVED_TOP_LEVEL.has(entry.name)) continue;

        const dirPath = path.join(resolvedWorkDir, entry.name);
        if (isProtectedPath(dirPath, collectProtectedCwds(candidateCwd), resolvedWorkDir)) continue;

        try {
          const activityMs = await getWorkspaceActivityMs(dirPath);
          // Age gate: a recently touched workspace is never purged, even if CephFS statfs lags behind reality.
          if (now - activityMs < STORAGE_TIER3_MIN_AGE_MS) continue;
          candidates.push({ path: dirPath, activityMs });
        } catch (e) { /* vanished between readdir and stat */ }
      }

      // Sort LRU (least recently active first)
      candidates.sort((a, b) => a.activityMs - b.activityMs);

      let tier3Deleted = 0;
      for (const candidate of candidates) {
        if (_abortRequested || tier3Deleted >= STORAGE_MAX_TIER3_DELETIONS) break;

        try {
          console.warn(`[storage-recycler] Tier 3 emergency LRU purging: ${candidate.path}`);
          if ((await guardedRemove(candidate.path, ctx)) === 'removed') {
            purgedCount++;
            tier3Deleted++;
          }
        } catch (rmErr) {
          failedCount++;
          console.warn(`[storage-recycler] Tier 3 could not purge '${candidate.path}': ${rmErr.message}`);
          continue;
        }

        const check = await getStorageUsage(workDir);
        if (!check.ok || check.usedRatio < STORAGE_HIGH_WATERMARK) {
          break;
        }
      }
    } catch (err) {
      console.warn(`[storage-recycler] Tier 3 sweep warning: ${err.message}`);
    }

    return settle(await getStorageUsage(workDir));
  } finally {
    _isRecycling = false;
    _inFlight = null;
    releaseInFlight();
  }
}

/**
 * Fast-path pre-task check:
 * Inspects volume headroom. If below STORAGE_HIGH_WATERMARK, exits with 0 file I/O.
 * candidateCwd is pinned for the duration so an already-running sweep (which makes this call return 'in-flight')
 * still shields the task that is about to start.
 */
async function checkAndRecycleStorage(workDir, candidateCwd) {
  pinTaskCwd(candidateCwd);
  try {
    const usage = await getStorageUsage(workDir);
    if (!usage.ok) return { skipped: true, reason: 'statfs_failed' };

    if (usage.usedRatio < STORAGE_HIGH_WATERMARK) {
      return { skipped: true, reason: 'headroom_sufficient', usedRatio: usage.usedRatio };
    }

    console.log(
      `[storage-recycler] High volume usage detected (${(usage.usedRatio * 100).toFixed(1)}%). Triggering proactive recycle...`
    );
    return await runStorageRecycle(workDir, { candidateCwd });
  } catch (err) {
    console.warn(`[storage-recycler] checkAndRecycleStorage error: ${err.message}`);
    return { skipped: true, error: err.message };
  } finally {
    unpinTaskCwd(candidateCwd);
  }
}

/**
 * Background periodic loop initialization.
 * Returns timer handle with .unref() so it does not block process exit or tests.
 */
function startPeriodicRecycler(workDir) {
  _abortRequested = false;

  // Run initial sweep asynchronously after boot
  setImmediate(() => {
    runStorageRecycle(workDir).catch((err) => {
      console.warn(`[storage-recycler] Initial boot sweep warning: ${err.message}`);
    });
  });

  const timer = setInterval(() => {
    runStorageRecycle(workDir).catch((err) => {
      console.warn(`[storage-recycler] Periodic sweep warning: ${err.message}`);
    });
  }, STORAGE_SWEEP_INTERVAL_MS);

  if (timer.unref) {
    timer.unref();
  }

  return timer;
}

/**
 * Graceful teardown of periodic timer.
 */
function stopPeriodicRecycler(timer) {
  if (timer) {
    clearInterval(timer);
  }
}

/**
 * Request shutdown: no new sweeps start and a running one stops between deletions.
 * Resolves once any in-flight sweep has finished, so an fs.rm is never cut off mid-directory by process exit.
 */
function stopStorageRecycler() {
  _abortRequested = true;
  return _inFlight || Promise.resolve();
}

/** Test hook: clear abort flag and pinned CWDs. */
function resetStorageRecycler() {
  _abortRequested = false;
  for (const entry of _pinned.values()) clearInterval(entry.timer);
  _pinned.clear();
}

module.exports = {
  getStorageUsage,
  isProtectedPath,
  collectProtectedCwds,
  getWorkspaceActivityMs,
  touchActivityMarker,
  pinTaskCwd,
  unpinTaskCwd,
  runStorageRecycle,
  checkAndRecycleStorage,
  startPeriodicRecycler,
  stopPeriodicRecycler,
  stopStorageRecycler,
  resetStorageRecycler,
};
