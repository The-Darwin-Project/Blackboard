// BlackBoard/ui/src/components/ops/HeadhunterQueueGroup.tsx
// @ai-rules:
// 1. [Pattern]: Self-contained Headhunter Queue tree group extracted from EventSidebar.
// 2. [Pattern]: Preserves platform filter toggles (All/GitLab/GitHub), degraded CB Reset/Poll Now banner,
//    Q# position badges, check/pipeline status dots, and mutation error/debounced feedback banners.
// 3. [Constraint]: Never pass extra args to resetHhBreaker.mutate(plat) or triggerHhPoll.mutate(); tests assert exact args.
import { useState, useEffect, useRef, useMemo } from 'react';
import { GitMerge, X } from 'lucide-react';
import type { HeadhunterTodo } from '../../api/client';
import {
  useHeadhunterStatus,
  useTriggerHeadhunterPoll,
  useResetHeadhunterBreaker,
  useHeadhunterItemAction,
} from '../../hooks/useQueue';
import SourceIcon from '../SourceIcon';
import { TreeGroup, TreeNode, EmptyLabel } from './TreePrimitives';
import {
  hhMenuItems,
  formatHeadhunterLabel,
  getHeadhunterItemKey,
  isGitHubTodo,
  type HeadhunterItemActionTarget,
  type HeadhunterMenuHandlers,
} from './sidebarMenus';
import { safeOpen } from '../../utils/safeOpen';
import type { ContextMenuItem } from './ContextMenu';

const CHECK_STATUS_STYLES: Record<string, { color: string; title: string }> = {
  passed: { color: '#22c55e', title: 'Checks passed' },
  success: { color: '#22c55e', title: 'Checks passed' },
  failed: { color: '#ef4444', title: 'Checks failed' },
  failure: { color: '#ef4444', title: 'Checks failed' },
  running: { color: '#3b82f6', title: 'Checks running' },
  pending: { color: '#f59e0b', title: 'Checks pending' },
};

function resolveHeadhunterStatusDot(todo: HeadhunterTodo): { color: string; title: string } | undefined {
  const raw = (todo.check_status || todo.pipeline_status || '').toLowerCase();
  if (!raw) return undefined;
  return CHECK_STATUS_STYLES[raw] ?? { color: '#64748b', title: `Checks: ${raw}` };
}

function extractErrorMessage(err: unknown): string {
  if (err instanceof Error && err.message) return err.message;
  if (err && typeof err === 'object' && 'message' in err && typeof (err as { message?: unknown }).message === 'string') {
    return (err as { message: string }).message;
  }
  return String(err || 'Operation failed');
}

export interface HeadhunterQueueGroupProps {
  todos: HeadhunterTodo[];
  isError: boolean;
  forceCollapsed: boolean;
  activeCtxKey: string | number | null;
  onOpenContextMenu: (menu: { x: number; y: number; items: ContextMenuItem[]; hhTargetKey: string | number }) => void;
  onClearContextMenu: () => void;
}

export default function HeadhunterQueueGroup({
  todos,
  isError,
  forceCollapsed,
  activeCtxKey,
  onOpenContextMenu,
  onClearContextMenu,
}: HeadhunterQueueGroupProps) {
  const [hhFilter, setHhFilter] = useState<'all' | 'gitlab' | 'github'>('all');
  const [dismissedError, setDismissedError] = useState<unknown>(null);
  const [debouncedNotice, setDebouncedNotice] = useState<string | null>(null);

  const { data: hhStatus } = useHeadhunterStatus();
  const triggerHhPoll = useTriggerHeadhunterPoll();
  const resetHhBreaker = useResetHeadhunterBreaker();
  const hhItemAction = useHeadhunterItemAction();

  const filteredHH = useMemo(
    () =>
      todos.filter((todo) => {
        if (hhFilter === 'all') return true;
        const isGh = isGitHubTodo(todo);
        return hhFilter === 'github' ? isGh : !isGh;
      }),
    [todos, hhFilter],
  );

  // Close an open HH context menu if filter changes or its target leaves filteredHH.
  const prevFilterRef = useRef(hhFilter);
  useEffect(() => {
    const filterChanged = prevFilterRef.current !== hhFilter;
    prevFilterRef.current = hhFilter;
    if (activeCtxKey == null) return;
    if (filterChanged || !filteredHH.some((t, idx) => getHeadhunterItemKey(t, idx) === activeCtxKey)) {
      onClearContextMenu();
    }
  }, [activeCtxKey, filteredHH, hhFilter, onClearContextMenu]);

  const pollData = triggerHhPoll.data;
  const breakerData = resetHhBreaker.data;
  const itemData = hhItemAction.data;
  useEffect(() => {
    if (pollData?.debounced) setDebouncedNotice('Poll request debounced — try again shortly.');
  }, [pollData]);
  useEffect(() => {
    if (breakerData?.debounced) setDebouncedNotice('Breaker reset debounced — try again shortly.');
  }, [breakerData]);
  useEffect(() => {
    if (itemData?.debounced) setDebouncedNotice('Item action debounced — try again shortly.');
  }, [itemData]);

  useEffect(() => {
    if (!debouncedNotice) return;
    const timer = window.setTimeout(() => setDebouncedNotice(null), 5000);
    return () => window.clearTimeout(timer);
  }, [debouncedNotice]);

  const activeError = triggerHhPoll.error ?? resetHhBreaker.error ?? hhItemAction.error ?? null;
  const visibleError = activeError != null && activeError !== dismissedError ? activeError : null;

  const dismissError = () => {
    setDismissedError(activeError);
    triggerHhPoll.reset?.();
    resetHhBreaker.reset?.();
    hhItemAction.reset?.();
  };

  const degradedHhPlatforms = (['gitlab', 'github'] as const).filter((plat) => {
    const st = hhStatus?.platforms?.[plat]?.breaker?.state;
    return st === 'open' || st === 'half_open';
  });

  const hhMenuHandlers: HeadhunterMenuHandlers = {
    promote: (payload: HeadhunterItemActionTarget) => hhItemAction.mutate({ action: 'promote', payload }),
    dismiss: (payload: HeadhunterItemActionTarget) => hhItemAction.mutate({ action: 'dismiss', payload }),
    requeue: (payload: HeadhunterItemActionTarget) => hhItemAction.mutate({ action: 'requeue', payload }),
    disabled: hhItemAction.isPending,
  };

  return (
    <TreeGroup
      icon={<GitMerge size={16} />}
      label="Headhunter Queue"
      count={todos.length}
      countColor={todos.length > 0 ? '#f59e0b' : '#64748b'}
      forceCollapsed={forceCollapsed}
    >
      <div className="flex items-center gap-1 px-2 py-1">
        {(['all', 'gitlab', 'github'] as const).map((plat) => (
          <button
            key={plat}
            type="button"
            onClick={() => setHhFilter(plat)}
            aria-pressed={hhFilter === plat}
            className={`px-1.5 py-0.5 text-[10px] rounded transition-colors ${
              hhFilter === plat
                ? 'bg-accent/20 text-accent font-semibold'
                : 'text-text-muted hover:bg-bg-tertiary'
            }`}
          >
            {plat === 'all' ? 'All' : plat === 'gitlab' ? 'GitLab' : 'GitHub'}
          </button>
        ))}
      </div>

      {visibleError && (
        <div
          role="alert"
          className="mx-2 my-1 px-2 py-1 rounded border border-red-500/30 bg-red-500/10 text-[11px] text-red-400 flex items-start justify-between gap-1.5"
        >
          <span className="break-words min-w-0">{extractErrorMessage(visibleError)}</span>
          <button
            type="button"
            onClick={dismissError}
            aria-label="Dismiss error"
            className="flex-shrink-0 p-0.5 rounded hover:bg-red-500/20 text-red-400"
          >
            <X size={12} />
          </button>
        </div>
      )}

      {debouncedNotice && (
        <div
          role="status"
          className="mx-2 my-1 px-2 py-1 rounded border border-amber-500/30 bg-amber-500/10 text-[11px] text-amber-300 flex items-center justify-between gap-1.5"
        >
          <span className="min-w-0">{debouncedNotice}</span>
          <button
            type="button"
            onClick={() => setDebouncedNotice(null)}
            aria-label="Dismiss notice"
            className="flex-shrink-0 p-0.5 rounded hover:bg-amber-500/20 text-amber-300"
          >
            <X size={12} />
          </button>
        </div>
      )}

      {degradedHhPlatforms.length > 0 && (
        <div className="mx-2 my-1 p-1.5 rounded border border-amber-500/30 bg-amber-500/10 text-[11px] space-y-1">
          {degradedHhPlatforms.map((plat) => {
            const st = hhStatus!.platforms[plat].breaker.state;
            const isOpen = st === 'open';
            return (
              <div key={plat} className="flex items-center justify-between gap-1.5">
                <span className={isOpen ? 'text-red-400 font-medium' : 'text-amber-400 font-medium'}>
                  {plat === 'gitlab' ? 'GitLab' : 'GitHub'} CB: {st}
                </span>
                <button
                  type="button"
                  onClick={() => resetHhBreaker.mutate(plat)}
                  disabled={resetHhBreaker.isPending}
                  className="px-1.5 py-0.5 rounded bg-bg-tertiary hover:bg-bg-primary text-text-secondary text-[10px]"
                >
                  Reset
                </button>
              </div>
            );
          })}
          <div className="flex justify-end">
            <button
              type="button"
              onClick={() => triggerHhPoll.mutate()}
              disabled={triggerHhPoll.isPending}
              className="px-1.5 py-0.5 rounded bg-bg-tertiary hover:bg-bg-primary text-text-secondary text-[10px]"
            >
              Poll Now
            </button>
          </div>
        </div>
      )}

      {isError && <EmptyLabel>Failed to load queue</EmptyLabel>}
      {!isError && todos.length === 0 && <EmptyLabel>No pending todos</EmptyLabel>}
      {!isError && todos.length > 0 && filteredHH.length === 0 && <EmptyLabel>No matching todos</EmptyLabel>}

      {filteredHH.map((todo, idx) => {
        const isGitHub = isGitHubTodo(todo);
        const statusDot = resolveHeadhunterStatusDot(todo);
        const checkState = (todo.check_status || todo.pipeline_status || '').toLowerCase();
        const isFailed = checkState === 'failed' || checkState === 'failure';
        const badge = todo.queue_position != null ? `Q${todo.queue_position}` : undefined;
        const itemKey = getHeadhunterItemKey(todo, idx);
        return (
          <TreeNode
            key={itemKey}
            icon={<SourceIcon source={isGitHub ? 'github' : 'gitlab'} size={18} />}
            label={formatHeadhunterLabel(todo)}
            badge={badge}
            statusDot={statusDot}
            sublabel={todo.action?.replace(/_/g, ' ') || ''}
            sublabelColor={isFailed ? '#ef4444' : '#64748b'}
            onClick={() => safeOpen(todo.target_url)}
            onContextMenu={(e) => {
              e.preventDefault();
              onOpenContextMenu({
                x: e.clientX,
                y: e.clientY,
                items: hhMenuItems(todo, hhMenuHandlers),
                hhTargetKey: itemKey,
              });
            }}
          />
        );
      })}
    </TreeGroup>
  );
}
