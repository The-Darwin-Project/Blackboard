// BlackBoard/ui/src/components/workspace/WorkspaceTaskItem.tsx
// @ai-rules:
// 1. [Pattern]: Presentational; selection is reported through onSelect(id) and the parent owns navigation.
// 2. [Pattern]: Matches EventNode visual density: status dot, SourceIcon, domain pill, agent badge, relative age, and DeferCountdownBar.
// 3. [Constraint]: Uses div role="button" with keyboard accessibility to allow valid nested DeferCountdownBar interaction.
/**
 * Single task session item with operational visibility parity.
 */
import type { KeyboardEvent, MouseEvent } from 'react';
import type { ActiveEvent } from '../../api/types';
import { ACTOR_COLORS, STATUS_COLORS, DOMAIN_COLORS } from '../../constants/colors';
import SourceIcon from '../SourceIcon';
import DeferCountdownBar from '../DeferCountdownBar';
import { relativeAge } from '../ops/TreePrimitives';

interface WorkspaceTaskItemProps {
  evt: ActiveEvent;
  isSelected: boolean;
  onSelect: (id: string) => void;
}

export default function WorkspaceTaskItem({ evt, isSelected, onSelect }: WorkspaceTaskItemProps) {
  const domain = (evt.evidence?.brain_domain || evt.evidence?.domain || 'casual') as keyof typeof DOMAIN_COLORS;
  const dc = DOMAIN_COLORS[domain] || DOMAIN_COLORS.casual;
  const sc = STATUS_COLORS[evt.status] || STATUS_COLORS.active;
  const isWaiting = evt.status === 'waiting_approval';
  const isDeferred = evt.status === 'deferred';
  const age = relativeAge(evt.created);
  const summary = evt.evidence?.display_text?.trim() || evt.reason?.trim() || 'Interactive session';

  const handleKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onSelect(evt.id);
    }
  };

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => onSelect(evt.id)}
      onKeyDown={handleKeyDown}
      title={evt.id}
      className={`w-full text-left p-2.5 rounded-lg border transition-all flex flex-col gap-1.5 cursor-pointer select-none ${
        isSelected
          ? 'bg-accent/10 border-accent/40 shadow-sm'
          : isWaiting
            ? 'border-amber-500/25 hover:border-amber-500/40 bg-amber-500/5 text-text-secondary'
            : isDeferred
              ? 'border-violet-500/20 hover:border-violet-500/35 bg-violet-500/5 text-text-secondary'
              : 'bg-bg-primary/50 border-transparent hover:bg-bg-tertiary/70 text-text-secondary'
      }`}
    >
      {/* Row 1: Status dot + SourceIcon + Service Name + Domain Pill + Current Agent Badge */}
      <div className="flex items-center gap-1.5 w-full min-w-0">
        <span
          className={`w-2 h-2 rounded-full flex-shrink-0 ${isWaiting ? 'animate-pulse' : ''}`}
          style={{ background: sc?.border || '#64748b', boxShadow: isWaiting ? `0 0 6px ${sc?.border}80` : 'none' }}
        />
        <SourceIcon
          source={evt.source}
          subjectType={evt.subject_type}
          evidence={evt.evidence as unknown as Record<string, unknown> | undefined}
          size={14}
        />
        <span className="text-xs font-mono font-medium truncate min-w-0 flex-1 text-text-primary">
          {evt.service || evt.id.slice(4, 12)}
        </span>
        {dc && (
          <span
            className="text-[10px] px-1.5 py-0.5 rounded border font-mono uppercase flex-shrink-0 font-medium leading-[14px]"
            style={{ background: dc.bg, color: dc.text, borderColor: `${dc.border}40` }}
          >
            {domain}
          </span>
        )}
        {evt.current_agent && (
          <span
            className="text-[10px] px-1.5 py-0.5 rounded flex-shrink-0 font-mono"
            style={{
              color: ACTOR_COLORS[evt.current_agent] || '#64748b',
              background: `${ACTOR_COLORS[evt.current_agent] || '#64748b'}18`,
            }}
          >
            {evt.current_agent}
          </span>
        )}
      </div>

      {/* Row 2: Summary text + Relative age */}
      <div className="flex items-center justify-between gap-2 w-full min-w-0">
        <span className="text-[11px] text-text-muted truncate flex-1 min-w-0">
          {summary}
        </span>
        {age && <span className="text-[10px] text-text-muted/60 flex-shrink-0">{age}</span>}
      </div>

      {/* Row 3: Deferred countdown bar if task is deferred */}
      {isDeferred && (
        <div className="w-full pt-0.5" onClick={(e: MouseEvent) => e.stopPropagation()}>
          <DeferCountdownBar
            deferUntil={evt.defer_until}
            deferStartedAt={evt.defer_started_at}
            compact
          />
        </div>
      )}
    </div>
  );
}
