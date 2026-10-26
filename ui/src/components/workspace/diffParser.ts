// BlackBoard/ui/src/components/workspace/diffParser.ts
// @ai-rules:
// 1. [Constraint]: '--- ' / '+++ ' are file headers only OUTSIDE a hunk (or when '---','+++','@@' appear in sequence).
//    Inside a hunk they are deleted/added lines ('-- x' / '++ x') and must be preserved.
// 2. [Pattern]: Blocks opened by 'diff --git' are always kept (binary / rename / mode-only have no hunks).
// 3. [Constraint]: Pure functions, must never throw on malformed input.
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

const DEFAULT_OLD = 'a/file';
const DEFAULT_NEW = 'b/file';

/** `--- x` / `+++ y` / `@@` at index i: a file header, not a deleted/added line that happens to look like one. */
function isFileHeaderAt(lines: string[], i: number): boolean {
  return (
    lines[i].startsWith('--- ') &&
    (lines[i + 1] ?? '').startsWith('+++ ') &&
    (lines[i + 2] ?? '').startsWith('@@')
  );
}

export function parseUnifiedDiff(rawDiff: string): DiffFile[] {
  if (!rawDiff || !rawDiff.trim()) return [];

  const lines = rawDiff.split(/\r?\n/);
  // A trailing newline yields a final empty element that is not part of the patch
  if (lines[lines.length - 1] === '') lines.pop();

  const files: DiffFile[] = [];
  const st = {
    file: null as DiffFile | null,
    hunk: null as DiffHunk | null,
    start: 0,
    // True when the block was opened by 'diff --git' (kept even without hunks: binary/rename/mode-only)
    gitBlock: false,
  };

  const finishFile = (end: number) => {
    const f = st.file;
    if (f && (st.gitBlock || f.hunks.length > 0 || f.oldPath !== DEFAULT_OLD || f.newPath !== DEFAULT_NEW)) {
      f.raw = lines.slice(st.start, end).join('\n');
      files.push(f);
    }
    st.file = null;
    st.hunk = null;
    st.gitBlock = false;
  };

  const startFile = (at: number, isGit: boolean): DiffFile => {
    finishFile(at);
    st.start = at;
    st.gitBlock = isGit;
    st.file = { oldPath: DEFAULT_OLD, newPath: DEFAULT_NEW, hunks: [] };
    return st.file;
  };

  try {
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];

      if (line.startsWith('diff --git ')) {
        const f = startFile(i, true);
        const m = /^diff --git (a\/.+?) (b\/.+)$/.exec(line) ?? /^diff --git (\S+) (\S+)$/.exec(line);
        if (m) {
          f.oldPath = m[1];
          f.newPath = m[2];
        }
        continue;
      }

      // '--- x' / '+++ x' are file headers only outside a hunk; inside one they are deleted '-- x' /
      // added '++ x' lines (unless '---', '+++', '@@' in sequence unmistakably open the next file).
      if (!st.hunk || isFileHeaderAt(lines, i)) {
        if (line.startsWith('--- ')) {
          // A '---' after hunks (plain unified diff, no 'diff --git') opens a new file
          const f = !st.file || st.hunk || (!st.gitBlock && st.file.hunks.length > 0) ? startFile(i, false) : st.file;
          f.oldPath = line.replace(/^---\s+/, '').trim();
          continue;
        }
        if (line.startsWith('+++ ') && st.file) {
          st.file.newPath = line.replace(/^\+\+\+\s+/, '').trim();
          continue;
        }
        if (st.file && /^(rename|copy) from /.test(line)) {
          st.file.oldPath = line.replace(/^(rename|copy) from /, '');
          continue;
        }
        if (st.file && /^(rename|copy) to /.test(line)) {
          st.file.newPath = line.replace(/^(rename|copy) to /, '');
          continue;
        }
      }

      if (line.startsWith('@@')) {
        const f = st.file ?? startFile(i, false);
        st.hunk = { header: line, lines: [] };
        f.hunks.push(st.hunk);
      } else if (st.hunk) {
        if (line.startsWith('+')) {
          st.hunk.lines.push({ type: 'add', content: line.slice(1) });
        } else if (line.startsWith('-')) {
          st.hunk.lines.push({ type: 'delete', content: line.slice(1) });
        } else if (line.startsWith(' ')) {
          st.hunk.lines.push({ type: 'normal', content: line.slice(1) });
        } else {
          st.hunk.lines.push({ type: 'info', content: line });
        }
      }
    }
    finishFile(lines.length);
  } catch {
    // Graceful fallback for malformed hunks
    return [{ oldPath: 'diff', newPath: 'patch', hunks: [], raw: rawDiff }];
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
