// gemini-sidecar/storage-recycler.js
// @ai-rules:
// 1. [Constraint]: Pure closed-loop controller for CephFS volume headroom. Target usage <= 65%.
// 2. [Pattern]: Bidirectional CWD guard protects active & recently finished task CWD (and ancestors/descendants).
// 3. [Pattern]: Re-entrancy mutex (_isRecycling) prevents overlapping periodic sweeps and pre-task hooks.
// 4. [Pattern]: Non-blocking async directory removals via fs.promises.rm to prevent event loop / WebSocket jitter.
// 5. [Pattern]: Sensitive file denylist shielding /tmp/gh-token-map*, /tmp/git-creds*, /tmp/.darwin-hooks*, /var/secrets.

const fs = require('fs');
const path = require('path');
const state = require('./state');
const {
  STORAGE_RECYCLE_INTERVAL_MS,
  STORAGE_HIGH_WATERMARK_RATIO,
  STORAGE_CRITICAL_WATERMARK_RATIO,
  STORAGE_STALE_EVENT_TTL_MS,
  STORAGE_RESULTS_TTL_MS,
} = require('./config');

let _isRecycling = false;

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

/**
 * Sensitive path denylist patterns.
 * Never allow deletions of secret volumes, app binaries, or git/github credentials in /tmp.
 */
const SENSITIVE_PREFIXES = [
  '/var/secrets',
  '/secrets',
  '/app',
  '/tmp/gh-token-map',
  '/tmp/git-creds',
  '/tmp/.darwin-hooks',
  '/tmp/agent-rules',
];

/**
 * Check whether a candidate directory or file is protected from deletion.
 * Guarantees bidirectional shielding:
 * - candidate is equal to, parent of, or child of activeCwd
 * - candidate is equal to, parent of, or child of lastCwd
 * - candidate falls outside /data or /tmp jail
 * - candidate matches sensitive prefixes
 */
function isProtectedPath(candidatePath, activeCwd, lastCwd) {
  if (!candidatePath || typeof candidatePath !== 'string') {
    return true;
  }
  const resolved = path.resolve(candidatePath);

  // Explicitly protect filesystem and jail root directories
  if (resolved === '/' || resolved === '/data' || resolved === '/tmp') {
    return true;
  }

  // Path jail: strictly allow recycling only inside /data/ or /tmp/
  if (
    !resolved.startsWith('/data' + path.sep) &&
    !resolved.startsWith('/tmp' + path.sep)
  ) {
    return true;
  }

  // Sensitive prefix denylist
  for (const prefix of SENSITIVE_PREFIXES) {
    if (resolved === prefix || resolved.startsWith(prefix)) {
      return true;
    }
  }

  // Bidirectional protection helper
  const matchesHierarchy = (targetCwd) => {
    if (!targetCwd || typeof targetCwd !== 'string') return false;
    const resolvedTarget = path.resolve(targetCwd);
    return (
      resolved === resolvedTarget ||
      resolved.startsWith(resolvedTarget + path.sep) ||
      resolvedTarget.startsWith(resolved + path.sep)
    );
  };

  if (matchesHierarchy(activeCwd)) {
    return true;
  }

  if (matchesHierarchy(lastCwd)) {
    return true;
  }

  return false;
}

/**
 * Execute tiered storage recycling.
 * Mutex-protected against concurrent invocations.
 */
async function runStorageRecycle(workDir, options = {}) {
  if (_isRecycling) {
    return { skipped: true, reason: 'in-flight' };
  }
  _isRecycling = true;

  const candidateCwd = options.candidateCwd || null;
  const activeCwd = candidateCwd || state.getCurrentTask()?.cwd || null;
  const lastCwd = state.getLastTaskContext()?.cwd || null;

  try {
    const initialUsage = await getStorageUsage(workDir);
    if (!initialUsage.ok) {
      return { ok: false, error: initialUsage.error };
    }

    const now = Date.now();
    let purgedCount = 0;

    // --- Tier 1: Volatile Sweep (results older than STORAGE_RESULTS_TTL_MS) ---
    const resultsDir = path.join(workDir, 'results');
    try {
      const entries = await fs.promises.readdir(resultsDir, { withFileTypes: true });
      for (const entry of entries) {
        const fullPath = path.join(resultsDir, entry.name);
        if (isProtectedPath(fullPath, activeCwd, lastCwd)) continue;

        try {
          const stat = await fs.promises.stat(fullPath);
          if (now - stat.mtimeMs > STORAGE_RESULTS_TTL_MS) {
            await fs.promises.rm(fullPath, { recursive: true, force: true });
            purgedCount++;
          }
        } catch (fileErr) {
          // File may have been removed or locked, ignore non-fatal
        }
      }
    } catch (err) {
      if (err.code !== 'ENOENT') {
        console.warn(`[storage-recycler] Tier 1 sweep warning in '${resultsDir}': ${err.message}`);
      }
    }

    // Proactive check: if usage is already below high watermark, skip heavier tiers
    let currentUsage = await getStorageUsage(workDir);
    if (currentUsage.ok && currentUsage.usedRatio < STORAGE_HIGH_WATERMARK_RATIO) {
      const cleanedBytes = Math.max(0, (initialUsage.usedBytes || 0) - (currentUsage.usedBytes || 0));
      return { ok: true, purgedCount, cleanedBytes, finalRatio: currentUsage.usedRatio };
    }

    // --- Tier 2: Stale Event Workspaces (*-evt-*, evt-*, *-baseline > 24h) ---
    try {
      const entries = await fs.promises.readdir(workDir, { withFileTypes: true });
      for (const entry of entries) {
        if (!entry.isDirectory()) continue;
        const name = entry.name;
        const isEventDir = name.includes('-evt-') || name.startsWith('evt-') || name.endsWith('-baseline');
        if (!isEventDir) continue;

        const dirPath = path.join(workDir, name);
        if (isProtectedPath(dirPath, activeCwd, lastCwd)) continue;

        try {
          const stat = await fs.promises.stat(dirPath);
          if (now - stat.mtimeMs > STORAGE_STALE_EVENT_TTL_MS) {
            console.log(`[storage-recycler] Tier 2 evicting stale event workspace: ${dirPath}`);
            await fs.promises.rm(dirPath, { recursive: true, force: true });
            purgedCount++;
          }
        } catch (dirErr) {
          // Ignore transient error
        }
      }
    } catch (err) {
      console.warn(`[storage-recycler] Tier 2 sweep warning in '${workDir}': ${err.message}`);
    }

    // Check again after Tier 2
    currentUsage = await getStorageUsage(workDir);
    if (!currentUsage.ok || currentUsage.usedRatio < STORAGE_CRITICAL_WATERMARK_RATIO) {
      const cleanedBytes = Math.max(0, (initialUsage.usedBytes || 0) - (currentUsage.usedBytes || 0));
      return { ok: true, purgedCount, cleanedBytes, finalRatio: currentUsage.usedRatio };
    }

    // --- Tier 3: Emergency LRU Prune of Idle Cloned Repositories (> 85% disk used) ---
    try {
      const entries = await fs.promises.readdir(workDir, { withFileTypes: true });
      const candidates = [];
      for (const entry of entries) {
        if (!entry.isDirectory()) continue;
        if (['results', 'lost+found', 'events'].includes(entry.name)) continue;

        const dirPath = path.join(workDir, entry.name);
        if (isProtectedPath(dirPath, activeCwd, lastCwd)) continue;

        try {
          const stat = await fs.promises.stat(dirPath);
          candidates.push({ path: dirPath, mtimeMs: stat.mtimeMs });
        } catch (e) {}
      }

      // Sort LRU (oldest mtime first)
      candidates.sort((a, b) => a.mtimeMs - b.mtimeMs);

      for (const candidate of candidates) {
        console.warn(`[storage-recycler] Tier 3 emergency LRU purging: ${candidate.path}`);
        await fs.promises.rm(candidate.path, { recursive: true, force: true });
        purgedCount++;

        const check = await getStorageUsage(workDir);
        if (check.ok && check.usedRatio < STORAGE_HIGH_WATERMARK_RATIO) {
          break;
        }
      }
    } catch (err) {
      console.warn(`[storage-recycler] Tier 3 sweep warning: ${err.message}`);
    }

    const finalUsage = await getStorageUsage(workDir);
    const cleanedBytes = Math.max(0, (initialUsage.usedBytes || 0) - (finalUsage.usedBytes || 0));
    return {
      ok: true,
      purgedCount,
      cleanedBytes,
      finalRatio: finalUsage.usedRatio,
    };
  } finally {
    _isRecycling = false;
  }
}

/**
 * Fast-path pre-task check:
 * Inspects volume headroom. If below STORAGE_HIGH_WATERMARK_RATIO, exits with 0 file I/O.
 */
async function checkAndRecycleStorage(workDir, candidateCwd) {
  try {
    const usage = await getStorageUsage(workDir);
    if (!usage.ok) return { skipped: true, reason: 'statfs_failed' };

    if (usage.usedRatio < STORAGE_HIGH_WATERMARK_RATIO) {
      return { skipped: true, reason: 'headroom_sufficient', usedRatio: usage.usedRatio };
    }

    console.log(
      `[storage-recycler] High volume usage detected (${(usage.usedRatio * 100).toFixed(1)}%). Triggering proactive recycle...`
    );
    return await runStorageRecycle(workDir, { candidateCwd });
  } catch (err) {
    console.warn(`[storage-recycler] checkAndRecycleStorage error: ${err.message}`);
    return { skipped: true, error: err.message };
  }
}

/**
 * Background periodic loop initialization.
 * Returns timer handle with .unref() so it does not block process exit or tests.
 */
function startPeriodicRecycler(workDir) {
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
  }, STORAGE_RECYCLE_INTERVAL_MS);

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

module.exports = {
  getStorageUsage,
  isProtectedPath,
  runStorageRecycle,
  checkAndRecycleStorage,
  startPeriodicRecycler,
  stopPeriodicRecycler,
};
