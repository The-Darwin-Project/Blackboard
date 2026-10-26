// @vitest-environment node
// BlackBoard/ui/src/__tests__/pwaManifest.test.ts
// @ai-rules:
// 1. [Constraint]: Reads ui/public and ui/index.html from disk via node:fs (node environment, not jsdom).
// 2. [Pattern]: manifest.webmanifest is the single manifest source of truth; manifest.json must not exist.
import { describe, it, expect } from 'vitest';
import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const uiRoot = resolve(fileURLToPath(new URL('.', import.meta.url)), '..', '..');
const publicDir = resolve(uiRoot, 'public');
const publicFile = (urlPath: string) => resolve(publicDir, urlPath.replace(/^\//, ''));

interface ManifestIcon {
  src: string;
  sizes: string;
  type?: string;
  purpose?: string;
}

const manifest = JSON.parse(
  readFileSync(publicFile('/manifest.webmanifest'), 'utf-8'),
) as Record<string, unknown> & { icons: ManifestIcon[] };
const indexHtml = readFileSync(resolve(uiRoot, 'index.html'), 'utf-8');

const PNG_SIGNATURE = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);

function pngDimensions(path: string): { width: number; height: number } {
  const buf = readFileSync(path);
  expect(buf.subarray(0, 8).equals(PNG_SIGNATURE)).toBe(true);
  // IHDR chunk data starts at byte 16: width (4 bytes BE), height (4 bytes BE)
  return { width: buf.readUInt32BE(16), height: buf.readUInt32BE(20) };
}

describe('PWA manifest', () => {
  it('has the required top-level fields', () => {
    expect(manifest.name).toBeTruthy();
    expect(manifest.short_name).toBeTruthy();
    expect(manifest.id).toBe('/');
    expect(manifest.start_url).toBe('/');
    expect(manifest.scope).toBe('/');
    expect(manifest.display).toBe('standalone');
    expect(manifest.background_color).toBeTruthy();
    expect(manifest.theme_color).toBeTruthy();
  });

  it('declares at least one icon', () => {
    expect(Array.isArray(manifest.icons)).toBe(true);
    expect(manifest.icons.length).toBeGreaterThan(0);
  });

  it.each(manifest.icons.map((icon) => [icon.src, icon] as const))(
    'icon %s exists with matching size and valid purpose',
    (_src, icon) => {
      const file = publicFile(icon.src);
      expect(existsSync(file)).toBe(true);

      expect([undefined, 'any', 'maskable']).toContain(icon.purpose);

      if (icon.type === 'image/png') {
        const match = /^(\d+)x(\d+)$/.exec(icon.sizes);
        expect(match).not.toBeNull();
        const { width, height } = pngDimensions(file);
        expect({ width, height }).toEqual({ width: Number(match![1]), height: Number(match![2]) });
      } else {
        expect(icon.sizes).toBe('any');
      }
    },
  );
});

describe('index.html icon and manifest links', () => {
  it.each(['/manifest.webmanifest', '/darwin.svg', '/favicon.ico', '/apple-touch-icon.png'])(
    'links %s and the file exists in public/',
    (href) => {
      expect(indexHtml).toContain(`href="${href}"`);
      expect(existsSync(publicFile(href))).toBe(true);
    },
  );
});

describe('unreferenced PWA duplicates', () => {
  it.each(['/manifest.json', '/darwin-maskable.svg'])('%s does not exist in public/', (path) => {
    expect(existsSync(publicFile(path))).toBe(false);
  });
});
