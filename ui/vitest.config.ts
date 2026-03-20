// ui/vitest.config.ts
// @ai-rules:
// 1. [Constraint]: jsdom environment required for React component tests. Do not switch to node.
// 2. [Pattern]: Test files follow src/**/*.test.{ts,tsx} glob. Colocate tests near source or in __tests__/.
// 3. [Constraint]: Uses same @vitejs/plugin-react as vite.config.ts. Keep plugins in sync.
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.{ts,tsx}'],
  },
});
