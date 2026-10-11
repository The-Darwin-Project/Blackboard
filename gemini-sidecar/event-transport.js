// gemini-sidecar/event-transport.js
// @ai-rules:
// 1. [Pattern]: Ensures event document is staged at {workDir}/events/event-{eventId}.md before CLI execution.
// 2. [Pattern]: Multi-stage staging: local workspace copy -> REST fetch from Brain (/events/{id}/document).
// 3. [Constraint]: Idempotent and fail-open with warnings (does not crash task if network down).

const fs = require('fs');
const path = require('path');
const { BRAIN_HTTP_URL, DEFAULT_WORK_DIR } = require('./config');

async function stageEventDocument(eventId, content) {
  if (!eventId || !content) return;
  const defaultDir = process.env.DEFAULT_WORK_DIR || DEFAULT_WORK_DIR;
  const dirs = new Set([
    '/data/workspace/events',
    path.join(defaultDir, 'events'),
  ]);
  for (const dir of dirs) {
    try {
      fs.mkdirSync(dir, { recursive: true });
      fs.writeFileSync(path.join(dir, `event-${eventId}.md`), content);
    } catch {}
  }
}

async function ensureEventDocument(workDir, eventId) {
  if (!eventId || eventId === 'unknown') return;
  const targetDir = path.join(workDir, 'events');
  const targetPath = path.join(targetDir, `event-${eventId}.md`);

  if (fs.existsSync(targetPath)) return;

  const workspacePath = `/data/workspace/events/event-${eventId}.md`;
  if (fs.existsSync(workspacePath)) {
    try {
      fs.mkdirSync(targetDir, { recursive: true });
      fs.copyFileSync(workspacePath, targetPath);
      console.log(`[event-transport] Staged event doc from workspace -> ${targetPath}`);
      return;
    } catch (err) {
      console.warn(`[event-transport] Failed to copy from workspace: ${err.message}`);
    }
  }

  const brainUrl = process.env.BRAIN_HTTP_URL || BRAIN_HTTP_URL;
  if (brainUrl) {
    const url = `${brainUrl}/events/${eventId}/document`;
    try {
      const res = await fetch(url);
      if (res.ok) {
        const content = await res.text();
        fs.mkdirSync(targetDir, { recursive: true });
        fs.writeFileSync(targetPath, content);
        await stageEventDocument(eventId, content);
        console.log(`[event-transport] Fetched and staged event doc -> ${targetPath} (${content.length} chars)`);
      } else {
        console.warn(`[event-transport] Fetch failed (${res.status}) from ${url}`);
      }
    } catch (err) {
      console.warn(`[event-transport] Fetch error from ${url}: ${err.message}`);
    }
  }
}

module.exports = { ensureEventDocument, stageEventDocument };
