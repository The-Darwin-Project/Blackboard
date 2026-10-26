// BlackBoard/ui/src/testSetup.ts
// @ai-rules:
// 1. [Pattern]: Vitest global setup; unmounts RTL trees after each test and registers a minimal toBeInTheDocument matcher.
// 2. [Constraint]: Do not pull in jest-dom; extend matchers here only when a test needs one.
import { expect, afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';

afterEach(() => {
  cleanup();
});

expect.extend({
  toBeInTheDocument(received: Element | null | undefined) {
    const pass = Boolean(received && received.ownerDocument?.contains(received));
    return {
      pass,
      message: () => `expected element ${pass ? 'not ' : ''}to be in document`,
    };
  },
});
