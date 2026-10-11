// gemini-sidecar/tests/test_event_transport.js
// @ai-rules:
// 1. [Constraint]: Unit tests for event document transport and staging.
// 2. [Pattern]: Uses node:test and node:assert/strict. Mocks fs/fetch as needed with temp directories.

const { describe, it, beforeEach, afterEach } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');
const os = require('os');

// Set test environment before requiring
const tmpRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'evt-trans-'));
const defaultWorkDir = path.join(tmpRoot, 'default-work');
const customWorkDir = path.join(tmpRoot, 'custom-work');
const workspaceDir = path.join(tmpRoot, 'workspace');

process.env.DEFAULT_WORK_DIR = defaultWorkDir;
process.env.BRAIN_HTTP_URL = 'http://brain.local:8000';

const { ensureEventDocument, stageEventDocument } = require('../event-transport');

describe('event-transport: ensureEventDocument and stageEventDocument', () => {
  beforeEach(() => {
    fs.mkdirSync(defaultWorkDir, { recursive: true });
    fs.mkdirSync(customWorkDir, { recursive: true });
    fs.mkdirSync(workspaceDir, { recursive: true });
  });

  afterEach(() => {
    fs.rmSync(tmpRoot, { recursive: true, force: true });
  });

  it('stageEventDocument creates events directory and stages markdown content', async () => {
    const eventId = 'test-stage-1';
    const content = '# Event test-stage-1 document\nDetails here.';
    await stageEventDocument(eventId, content);

    const stagedInDefault = path.join(defaultWorkDir, 'events', `event-${eventId}.md`);
    assert.equal(fs.existsSync(stagedInDefault), true);
    assert.equal(fs.readFileSync(stagedInDefault, 'utf8'), content);
  });

  it('ensureEventDocument returns immediately if eventId is unknown or empty', async () => {
    await ensureEventDocument(customWorkDir, '');
    await ensureEventDocument(customWorkDir, 'unknown');
    assert.equal(fs.existsSync(path.join(customWorkDir, 'events')), false);
  });

  it('ensureEventDocument skips fetch/copy if target file already exists in workDir', async () => {
    const eventId = 'test-exists-1';
    const targetDir = path.join(customWorkDir, 'events');
    const targetPath = path.join(targetDir, `event-${eventId}.md`);
    fs.mkdirSync(targetDir, { recursive: true });
    fs.writeFileSync(targetPath, 'Original content');

    await ensureEventDocument(customWorkDir, eventId);
    assert.equal(fs.readFileSync(targetPath, 'utf8'), 'Original content');
  });

  it('ensureEventDocument fetches from BRAIN_HTTP_URL when document is missing', async () => {
    const eventId = 'test-fetch-1';
    const originalFetch = global.fetch;
    try {
      global.fetch = async (url) => {
        assert.equal(url, `http://brain.local:8000/events/${eventId}/document`);
        return {
          ok: true,
          status: 200,
          text: async () => `# Fetched doc for ${eventId}`,
        };
      };

      await ensureEventDocument(customWorkDir, eventId);

      const targetPath = path.join(customWorkDir, 'events', `event-${eventId}.md`);
      assert.equal(fs.existsSync(targetPath), true);
      assert.equal(fs.readFileSync(targetPath, 'utf8'), `# Fetched doc for ${eventId}`);
    } finally {
      global.fetch = originalFetch;
    }
  });

  it('ensureEventDocument fails open on fetch network error without throwing', async () => {
    const eventId = 'test-fail-open-1';
    const originalFetch = global.fetch;
    try {
      global.fetch = async () => {
        throw new Error('Connection refused');
      };

      await ensureEventDocument(customWorkDir, eventId);
      const targetPath = path.join(customWorkDir, 'events', `event-${eventId}.md`);
      assert.equal(fs.existsSync(targetPath), false);
    } finally {
      global.fetch = originalFetch;
    }
  });
});
