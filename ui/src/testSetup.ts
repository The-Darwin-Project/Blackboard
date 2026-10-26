// BlackBoard/ui/src/testSetup.ts
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
