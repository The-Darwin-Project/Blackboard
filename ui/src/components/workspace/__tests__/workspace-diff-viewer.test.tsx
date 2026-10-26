import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import WorkspaceDiffViewer from '../WorkspaceDiffViewer';

describe('WorkspaceDiffViewer (T-7, T-13)', () => {
  const sampleDiff = `diff --git a/src/test.ts b/src/test.ts
index 1234567..89abcdef 100644
--- a/src/test.ts
+++ b/src/test.ts
@@ -1,3 +1,3 @@
-const oldVal = 10;
+const newVal = 20;
 const unchanged = true;
`;

  it('T-7: renders additions and deletions with Tailwind styling', () => {
    const { container } = render(
      <WorkspaceDiffViewer diffs={[sampleDiff]} />
    );

    // Verify filename or header is rendered
    expect(screen.getByText(/src\/test\.ts/i)).toBeInTheDocument();

    // Verify deleted line content and added line content
    expect(screen.getByText(/const oldVal = 10;/i)).toBeInTheDocument();
    expect(screen.getByText(/const newVal = 20;/i)).toBeInTheDocument();

    // Verify Tailwind classes for diff line styling (rose/emerald or bg-red/bg-green)
    const addLine = container.querySelector('[class*="emerald"], [class*="green"]');
    const delLine = container.querySelector('[class*="rose"], [class*="red"]');
    expect(addLine).toBeTruthy();
    expect(delLine).toBeTruthy();
  });

  it('T-13: gracefully handles empty diffs array or empty strings without throwing', () => {
    expect(() => {
      render(<WorkspaceDiffViewer diffs={[]} />);
    }).not.toThrow();

    expect(screen.getByText(/no diff|no changes/i)).toBeInTheDocument();

    expect(() => {
      render(<WorkspaceDiffViewer diffs={['']} />);
    }).not.toThrow();
  });

  it('T-13: gracefully handles malformed diff text with raw fallback', () => {
    const malformed = 'Not really a valid git diff string at all!';
    expect(() => {
      render(<WorkspaceDiffViewer diffs={[malformed]} />);
    }).not.toThrow();

    expect(screen.getByText(/Not really a valid git diff string at all!/i)).toBeInTheDocument();
  });
});
