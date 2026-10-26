// @vitest-environment node
// BlackBoard/ui/src/components/workspace/__tests__/manifest.test.ts
// @ai-rules:
// 1. [Constraint]: Must agree with src/__tests__/pwaManifest.test.ts on the standalone launch contract (id/start_url/scope).
import { describe, it, expect } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { findDuplicateJsonKeys } from '../../../testUtils/findDuplicateJsonKeys';

const manifestPath = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '../../../../public/manifest.webmanifest',
);

describe('PWA Web Manifest (T-11)', () => {
  it('exists and has no duplicate JSON keys', () => {
    expect(fs.existsSync(manifestPath)).toBe(true);
    expect(findDuplicateJsonKeys(fs.readFileSync(manifestPath, 'utf8'))).toEqual([]);
  });

  it('launches standalone into /workspace while keeping the whole app in scope', () => {
    const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
    expect(manifest.display).toBe('standalone');
    expect(manifest.id).toBe('/workspace');
    expect(manifest.start_url).toBe('/workspace');
    expect(manifest.scope).toBe('/');
  });

  it('includes /workspace shortcut for desktop PWA app launch', () => {
    const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
    expect(Array.isArray(manifest.shortcuts)).toBe(true);

    const workspaceShortcut = manifest.shortcuts.find(
      (s: { url: string; name?: string }) => s.url === '/workspace',
    );
    expect(workspaceShortcut).toBeDefined();
    expect(workspaceShortcut.name).toMatch(/workspace/i);
  });
});
