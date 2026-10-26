import { describe, it, expect } from 'vitest';
import fs from 'fs';
import path from 'path';

describe('PWA Web Manifest (T-11)', () => {
  it('includes /workspace shortcut for desktop PWA app launch', () => {
    // Resolve manifest.webmanifest from public folder
    const manifestPath = path.resolve(__dirname, '../../../../public/manifest.webmanifest');
    expect(fs.existsSync(manifestPath)).toBe(true);

    const manifestContent = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));

    // Verify manifest has name / display settings
    expect(manifestContent.display).toBe('standalone');

    // DoD T-11: Verify shortcuts array contains entry with url '/workspace'
    expect(manifestContent.shortcuts).toBeDefined();
    expect(Array.isArray(manifestContent.shortcuts)).toBe(true);

    const workspaceShortcut = manifestContent.shortcuts.find(
      (s: { url: string; name?: string }) => s.url === '/workspace'
    );
    expect(workspaceShortcut).toBeDefined();
    expect(workspaceShortcut.name).toMatch(/workspace/i);
  });
});
