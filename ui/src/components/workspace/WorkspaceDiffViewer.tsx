// BlackBoard/ui/src/components/workspace/WorkspaceDiffViewer.tsx
// @ai-rules:
// 1. [Constraint]: Parsing is memoized on the diffs prop; callers must pass a referentially stable array.
// 2. [Pattern]: Unparseable diffs fall back to a raw <pre> block rather than being dropped.
/**
 * Unified diff viewer component using Tailwind color tokens.
 * Displays file headers, hunk offsets, and highlighted additions and deletions.
 */
import { useMemo } from 'react';
import { FileCode2 } from 'lucide-react';
import { parseUnifiedDiff, type DiffFile } from './diffParser';

interface WorkspaceDiffViewerProps {
  diffs: string[];
}

export default function WorkspaceDiffViewer({ diffs }: WorkspaceDiffViewerProps) {
  const parsedFiles = useMemo<DiffFile[]>(() => {
    const nonEmpty = (diffs || []).filter(d => Boolean(d && d.trim()));
    return nonEmpty.flatMap(raw => {
      const files = parseUnifiedDiff(raw);
      return files.length > 0 ? files : [{ oldPath: 'diff', newPath: 'patch', hunks: [], raw }];
    });
  }, [diffs]);

  if (parsedFiles.length === 0) {
    return (
      <div className="p-8 text-center text-text-muted text-xs">
        <FileCode2 size={24} className="mx-auto mb-2 opacity-40" />
        No diff or changes found.
      </div>
    );
  }

  return (
    <div className="p-3 space-y-4 font-mono text-xs overflow-x-auto">
      {parsedFiles.map((file, fileIdx) => (
        <div key={fileIdx} className="rounded-lg border border-border bg-bg-primary overflow-hidden">
          <div className="px-3 py-1.5 bg-bg-secondary border-b border-border flex items-center justify-between text-text-secondary text-[11px] font-semibold">
            <span className="truncate">{file.newPath || file.oldPath}</span>
            <span className="text-[10px] text-text-muted">{file.hunks.length} hunks</span>
          </div>

          {file.hunks.length > 0 ? (
            <div className="divide-y divide-border/40">
              {file.hunks.map((hunk, hIdx) => (
                <div key={hIdx}>
                  <div className="px-3 py-1 bg-blue-950/20 text-blue-400 text-[10px] select-none border-b border-border/30">
                    {hunk.header}
                  </div>
                  <div className="py-0.5">
                    {hunk.lines.map((line, lIdx) => {
                      if (line.type === 'add') {
                        return (
                          <div key={lIdx} className="px-3 py-0.5 bg-emerald-950/30 text-emerald-300 flex gap-2">
                            <span className="select-none opacity-60 w-3 text-center">+</span>
                            <span className="whitespace-pre overflow-x-auto">{line.content}</span>
                          </div>
                        );
                      }
                      if (line.type === 'delete') {
                        return (
                          <div key={lIdx} className="px-3 py-0.5 bg-rose-950/30 text-rose-300 flex gap-2">
                            <span className="select-none opacity-60 w-3 text-center">-</span>
                            <span className="whitespace-pre overflow-x-auto">{line.content}</span>
                          </div>
                        );
                      }
                      return (
                        <div key={lIdx} className="px-3 py-0.5 text-text-muted flex gap-2">
                          <span className="select-none opacity-30 w-3 text-center"> </span>
                          <span className="whitespace-pre overflow-x-auto">{line.content}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <pre className="p-3 text-text-muted text-[11px] whitespace-pre-wrap overflow-x-auto">
              {file.raw}
            </pre>
          )}
        </div>
      ))}
    </div>
  );
}
