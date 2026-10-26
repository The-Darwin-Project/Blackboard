// BlackBoard/ui/src/components/workspace/__tests__/diff-parser.test.ts
import { describe, it, expect } from 'vitest';
import { parseUnifiedDiff, extractDiffsFromConversation } from '../diffParser';
import type { ConversationTurn } from '../../../api/types';

describe('diffParser (T-7, T-13)', () => {
  const sampleDiff = `diff --git a/src/example.ts b/src/example.ts
index e69de29..4994342 100644
--- a/src/example.ts
+++ b/src/example.ts
@@ -1,3 +1,4 @@
 const hello = "world";
-const count = 1;
+const count = 2;
+console.log(count);
 return hello;
`;

  it('T-7: parseUnifiedDiff parses hunks with additions and deletions', () => {
    const files = parseUnifiedDiff(sampleDiff);
    expect(files.length).toBe(1);

    const file = files[0];
    expect(file.oldPath).toContain('src/example.ts');
    expect(file.newPath).toContain('src/example.ts');
    expect(file.hunks.length).toBeGreaterThan(0);

    const lines = file.hunks[0].lines;
    const addLines = lines.filter((l) => l.type === 'add');
    const deleteLines = lines.filter((l) => l.type === 'delete');
    const normalLines = lines.filter((l) => l.type === 'normal');

    expect(addLines.length).toBe(2);
    expect(deleteLines.length).toBe(1);
    expect(normalLines.length).toBe(2);

    expect(deleteLines[0].content).toContain('const count = 1;');
    expect(addLines[0].content).toContain('const count = 2;');
    expect(addLines[1].content).toContain('console.log(count);');
  });

  it('parses multi-hunk and new-file diffs cleanly', () => {
    const multiHunkDiff = `diff --git a/src/multi.ts b/src/multi.ts
--- /dev/null
+++ b/src/multi.ts
@@ -0,0 +1,3 @@
+line 1
+line 2
+line 3
@@ -10,3 +12,4 @@
 line 10
-line 11
+line 11 modified
+line 11.5
 line 12
`;
    const files = parseUnifiedDiff(multiHunkDiff);
    expect(files.length).toBe(1);
    expect(files[0].oldPath).toBe('/dev/null');
    expect(files[0].newPath).toBe('b/src/multi.ts');
    expect(files[0].hunks.length).toBe(2);
    expect(files[0].hunks[0].lines.length).toBe(3);
    expect(files[0].hunks[1].lines.some(l => l.type === 'delete')).toBe(true);
  });

  it('T-13: parseUnifiedDiff gracefully handles malformed/empty diffs without throwing', () => {
    expect(() => parseUnifiedDiff('')).not.toThrow();
    expect(parseUnifiedDiff('')).toEqual([]);

    expect(() => parseUnifiedDiff('   \n\n  ')).not.toThrow();
    expect(parseUnifiedDiff('   \n\n  ')).toEqual([]);

    // Malformed patch string without headers or hunks
    const malformed = 'Not a git diff at all! Just some random string\nAnother random line';
    expect(() => parseUnifiedDiff(malformed)).not.toThrow();
    const result = parseUnifiedDiff(malformed);
    expect(Array.isArray(result)).toBe(true);
  });

  it('extractDiffsFromConversation extracts diff blocks from markdown codeblocks in turns', () => {
    const conversation: ConversationTurn[] = [
      {
        turn: 1,
        actor: 'user',
        action: 'message',
        timestamp: 1700000000,
        thoughts: 'Please fix the count variable',
      },
      {
        turn: 2,
        actor: 'developer',
        action: 'tool_result',
        timestamp: 1700000010,
        result: `Here is the patch:\n\`\`\`diff\n${sampleDiff}\`\`\``,
      },
    ];

    const extracted = extractDiffsFromConversation(conversation);
    expect(extracted.length).toBe(1);
    expect(extracted[0]).toContain('diff --git a/src/example.ts');
  });

  it('extractDiffsFromConversation handles turns with no diffs gracefully', () => {
    const conversation: ConversationTurn[] = [
      {
        turn: 1,
        actor: 'user',
        action: 'message',
        timestamp: 1700000000,
        thoughts: 'Hello',
      },
      {
        turn: 2,
        actor: 'architect',
        action: 'thoughts',
        timestamp: 1700000005,
        thoughts: 'Analyzing architecture...',
      },
    ];

    const extracted = extractDiffsFromConversation(conversation);
    expect(extracted).toEqual([]);
    expect(() => extractDiffsFromConversation([])).not.toThrow();
  });
});
