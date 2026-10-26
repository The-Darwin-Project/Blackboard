// BlackBoard/ui/src/components/workspace/WorkspaceTaskItem.tsx
// @ai-rules:
// 1. [Pattern]: Presentational; selection is reported through onSelect(id) and the parent owns navigation.
// 2. [Gotcha]: Unknown Cynefin domains fall back to the 'casual' badge style.
/**
 * Single task session button item with Cynefin pill.
 */
import type { ActiveEvent } from '../../api/types';

interface WorkspaceTaskItemProps {
  evt: ActiveEvent;
  isSelected: boolean;
  onSelect: (id: string) => void;
}

const CYNEFIN_COLORS: Record<string, string> = {
  clear: 'bg-emerald-950/60 text-emerald-400 border-emerald-800/50',
  complicated: 'bg-blue-950/60 text-blue-400 border-blue-800/50',
  complex: 'bg-amber-950/60 text-amber-400 border-amber-800/50',
  chaotic: 'bg-rose-950/60 text-rose-400 border-rose-800/50',
  disorder: 'bg-slate-800 text-slate-400 border-slate-700',
  casual: 'bg-indigo-950/60 text-indigo-400 border-indigo-800/50',
};

export default function WorkspaceTaskItem({ evt, isSelected, onSelect }: WorkspaceTaskItemProps) {
  const domain = evt.evidence?.brain_domain || evt.evidence?.domain || 'casual';
  const domainClass = Object.hasOwn(CYNEFIN_COLORS, domain) ? CYNEFIN_COLORS[domain] : CYNEFIN_COLORS.casual;
  const summary = evt.evidence?.display_text?.trim() || evt.reason?.trim() || 'Interactive session';

  return (
    <button
      onClick={() => onSelect(evt.id)}
      className={`w-full text-left p-2.5 rounded-lg border transition-all flex flex-col gap-1.5 ${
        isSelected
          ? 'bg-accent/10 border-accent/40 shadow-sm'
          : 'bg-bg-primary/50 border-transparent hover:bg-bg-tertiary/70 text-text-secondary'
      }`}
    >
      <div className="flex items-center justify-between gap-1 w-full">
        <span className="text-xs font-mono font-medium truncate text-text-primary">
          {evt.service || evt.id}
        </span>
        <span className={`text-[10px] px-1.5 py-0.5 rounded border font-mono uppercase ${domainClass}`}>
          {domain}
        </span>
      </div>
      <div className="text-[11px] text-text-muted line-clamp-1">{summary}</div>
    </button>
  );
}
