// BlackBoard/ui/src/components/workspace/diffParser.ts
/**
 * Unified diff parsing utility. Extracts git patches and fenced diff blocks from conversation turns.
 */
import type { ConversationTurn } from '../../api/types';

export interface DiffLine {
  type: 'add' | 'delete' | 'normal' | 'info';
  content: string;
}

export interface DiffHunk {
  header: string;
  lines: DiffLine[];
}

export interface DiffFile {
  oldPath: string;
  newPath: string;
  hunks: DiffHunk[];
  raw?: string;
}

export function parseUnifiedDiff(rawDiff: string): DiffFile[] {
  if (!rawDiff || !rawDiff.trim()) return [];

  const files: DiffFile[] = [];
  // Split on diff boundaries: line-anchored 'diff --git' or '--- [ab]/'
  const fileBlocks = rawDiff
    .split(/(?:^|\n)(?=diff --git |--- [ab]\/)/g)
    .filter(b => b && b.trim());

  for (const block of fileBlocks) {
    try {
      const lines = block.split(/\r?\n/);
      let oldPath = 'a/file';
      let newPath = 'b/file';
      const hunks: DiffHunk[] = [];
      let currentHunk: DiffHunk | null = null;

      for (const line of lines) {
        if (line.startsWith('--- ')) {
          oldPath = line.replace(/^---\s+/, '').trim();
        } else if (line.startsWith('+++ ')) {
          newPath = line.replace(/^\+\+\+\s+/, '').trim();
        } else if (line.startsWith('@@')) {
          currentHunk = { header: line, lines: [] };
          hunks.push(currentHunk);
        } else if (currentHunk) {
          if (line.startsWith('+')) {
            currentHunk.lines.push({ type: 'add', content: line.slice(1) });
          } else if (line.startsWith('-')) {
            currentHunk.lines.push({ type: 'delete', content: line.slice(1) });
          } else if (line.startsWith(' ')) {
            currentHunk.lines.push({ type: 'normal', content: line.slice(1) });
          } else {
            currentHunk.lines.push({ type: 'info', content: line });
          }
        }
      }

      if (hunks.length > 0 || oldPath !== 'a/file' || newPath !== 'b/file') {
        files.push({ oldPath, newPath, hunks, raw: block });
      }
    } catch {
      // Graceful fallback for malformed hunks
      files.push({ oldPath: 'diff', newPath: 'patch', hunks: [], raw: block });
    }
  }

  return files;
}

export function extractDiffsFromConversation(conversation?: ConversationTurn[]): string[] {
  if (!conversation || !Array.isArray(conversation) || conversation.length === 0) return [];

  const collectedDiffs: string[] = [];

  for (const turn of conversation) {
    const texts = [turn.result, turn.evidence, turn.thoughts].filter((t): t is string => Boolean(t));
    for (const text of texts) {
      // Match markdown fenced ```diff blocks (with optional whitespace / metadata on the codeblock tag)
      const fencedMatches = text.matchAll(/```diff[^\n]*\n([\s\S]*?)```/gi);
      for (const match of fencedMatches) {
        if (match[1]?.trim()) {
          collectedDiffs.push(match[1].trim());
        }
      }
      // Match raw diff --git blocks if not inside fences
      if (!text.includes('```diff') && text.includes('diff --git')) {
        collectedDiffs.push(text.trim());
      }
    }
  }

  return collectedDiffs;
}
