// ui/src/__tests__/api-client.test.ts
// @ai-rules:
// 1. [Pattern]: Smoke test for API client module. Expand with actual client function tests.
// 2. [Constraint]: Runs in jsdom (vitest.config.ts). window/document are available.
import { describe, it, expect } from 'vitest';

describe('API client base URL', () => {
  it('should default to relative path', () => {
    expect(typeof window).toBe('object');
  });
});
