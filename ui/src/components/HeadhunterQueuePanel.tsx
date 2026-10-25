// BlackBoard/ui/src/components/HeadhunterQueuePanel.tsx
// @ai-rules:
// 1. [Pattern]: Polls GET /queue/headhunter/pending every 30s. Pure display component.
// 2. [Pattern]: Shows pending items (GitLab todos + GitHub queued/active PRs and Issues) sorted oldest-first (FIFO).
// 3. [Constraint]: Read-only -- no actions, just observability.
// 4. [Pattern]: Shares the 4 sidebarMenus helpers (isGitHubTodo, isGitHubIssue, formatHeadhunterLabel, getHeadhunterItemKey);
//    this file calls isGitHubTodo/formatHeadhunterLabel/getHeadhunterItemKey, PR vs Issue handled inside the label helper.
//    Label is built ONLY by formatHeadhunterLabel(todo, { truncate: false }) -- never re-implement pfx/num/title here.
//    Prefix: "!" for GitLab MRs, "#" for GitHub PRs/Issues; missing number falls back to title or "Queued Item".
// 5. [Constraint]: Cards route clicks through preventDefault + safeOpen (http/https only); the <a href> is only a
//    hint for hover/middle-click and is limited to http(s) (else "#").
// 6. [Pattern]: The single "NEXT" badge goes to the first genuinely queued row (queue_position != null or action
//    "queued"); in-progress rows (action active/new/deferred, queue_position null) are never badged.
// 7. [Gotcha]: All HeadhunterTodo fields are optional except action/project_path/author/created_at.
/**
 * Headhunter Queue panel — shows pending GitLab todos waiting to be processed.
 * Displays in the right panel alongside Resources and Agents tabs.
 */
import { useState, useEffect, useCallback } from 'react';
import { Loader2 } from 'lucide-react';
import { getHeadhunterPending } from '../api/client';
import type { HeadhunterTodo } from '../api/client';
import { isGitHubTodo, formatHeadhunterLabel, getHeadhunterItemKey } from './ops/sidebarMenus';
import { safeOpen } from '../utils/safeOpen';

const ACTION_BADGE: Record<string, { bg: string; text: string }> = {
  build_failed:       { bg: '#7f1d1d', text: '#fca5a5' },
  unmergeable:        { bg: '#78350f', text: '#fcd34d' },
  assigned:           { bg: '#1e3a5f', text: '#93c5fd' },
  approval_required:  { bg: '#312e81', text: '#a5b4fc' },
  review_requested:   { bg: '#312e81', text: '#a5b4fc' },
  directly_addressed: { bg: '#064e3b', text: '#6ee7b7' },
};

const PIPELINE_DOT: Record<string, string> = {
  success: '#22c55e',
  failed: '#ef4444',
  running: '#3b82f6',
  pending: '#94a3b8',
  unknown: '#475569',
};

// Backend marks items Darwin already has an event for with the event status (see _github_active_item).
const IN_PROGRESS_ACTIONS = new Set(['active', 'new', 'deferred']);

function isQueuedTodo(todo: HeadhunterTodo): boolean {
  return todo.queue_position != null || todo.action === 'queued';
}

function isInProgressTodo(todo: HeadhunterTodo): boolean {
  return todo.queue_position == null && IN_PROGRESS_ACTIONS.has(todo.action);
}

/** Only http(s) URLs may reach href; anything else (javascript:, data:, empty) degrades to "#". */
function safeHref(url: string | undefined | null): string {
  if (!url) return '#';
  try {
    const parsed = new URL(url, window.location.origin);
    return parsed.protocol === 'https:' || parsed.protocol === 'http:' ? url : '#';
  } catch {
    return '#';
  }
}

function formatAge(isoDate: string): string {
  if (!isoDate) return '';
  const ms = Date.now() - new Date(isoDate).getTime();
  const min = Math.floor(ms / 60000);
  if (min < 60) return `${min}m`;
  const hrs = Math.floor(min / 60);
  if (hrs < 24) return `${hrs}h`;
  return `${Math.floor(hrs / 24)}d`;
}

export default function HeadhunterQueuePanel() {
  const [todos, setTodos] = useState<HeadhunterTodo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchTodos = useCallback(async () => {
    try {
      const data = await getHeadhunterPending();
      setTodos(data);
      setError(null);
    } catch (e) {
      setError((e instanceof Error && e.message) || 'Failed to fetch');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTodos();
    const interval = setInterval(fetchTodos, 30000);
    return () => clearInterval(interval);
  }, [fetchTodos]);

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: 24, color: '#64748b' }}>
        <Loader2 size={18} style={{ animation: 'spin 1s linear infinite' }} />
      </div>
    );
  }

  if (error) {
    return <div style={{ color: '#f87171', fontSize: 12, padding: 8 }}>{error}</div>;
  }

  if (todos.length === 0) {
    return (
      <div style={{ color: '#475569', fontSize: 12, padding: 16, textAlign: 'center' }}>
        No pending items
      </div>
    );
  }

  const gitlabItems = todos.filter(t => !isGitHubTodo(t));
  const githubItems = todos.filter(t => isGitHubTodo(t));
  // Single NEXT target: first queued row; else first not-in-progress row (GitLab todos carry no queue state).
  const nextTodo = todos.find(isQueuedTodo) ?? todos.find(t => !isInProgressTodo(t));

  function renderItem(todo: HeadhunterTodo, i: number) {
    const isGitHub = isGitHubTodo(todo);
    const badge = ACTION_BADGE[todo.action] || { bg: '#1e293b', text: '#94a3b8' };
    const pipeDot = PIPELINE_DOT[todo.pipeline_status ?? 'unknown'] || PIPELINE_DOT.unknown;
    const projectName = todo.project_path.split('/').pop() || todo.project_path;
    const isFirst = todo === nextTodo;

    return (
      <a
        key={getHeadhunterItemKey(todo, i)}
        href={safeHref(todo.target_url)}
        target="_blank"
        rel="noopener noreferrer"
        onClick={(e) => { e.preventDefault(); safeOpen(todo.target_url); }}
        style={{
          display: 'block',
          padding: '10px 12px',
          borderRadius: 8,
          background: isFirst ? '#1e293b' : '#0f172a',
          border: `1px solid ${isFirst ? '#334155' : '#1e293b'}`,
          textDecoration: 'none',
          transition: 'background 0.15s',
        }}
        onMouseEnter={(e) => { e.currentTarget.style.background = '#1e293b'; }}
        onMouseLeave={(e) => { if (!isFirst) e.currentTarget.style.background = '#0f172a'; }}
      >
        {/* Row 1: action badge + pipeline dot + age */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
          <span style={{
            background: badge.bg, color: badge.text,
            padding: '2px 8px', borderRadius: 8, fontSize: 10, fontWeight: 600,
          }}>
            {todo.action?.replace(/_/g, ' ') || ''}
          </span>
          {!isGitHub && (
            <span style={{
              width: 8, height: 8, borderRadius: '50%', background: pipeDot, flexShrink: 0,
            }} title={`Pipeline: ${todo.pipeline_status}`} />
          )}
          {isGitHub && todo.queue_position != null && (
            <span style={{
              fontSize: 9, color: '#f59e0b', fontWeight: 600, background: '#292524',
              padding: '1px 6px', borderRadius: 6,
            }}>
              Q#{todo.queue_position}
            </span>
          )}
          <span style={{ flex: 1 }} />
          <span style={{ fontSize: 10, color: '#475569' }}>{formatAge(todo.created_at)}</span>
          {isFirst && (
            <span style={{
              fontSize: 9, color: '#3b82f6', fontWeight: 600, textTransform: 'uppercase',
            }}>
              next
            </span>
          )}
        </div>
        {/* Row 2: item number + title */}
        <div style={{
          fontSize: 12, color: '#e2e8f0', fontWeight: 500,
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          marginBottom: 4,
        }}>
          {formatHeadhunterLabel(todo, { truncate: false })}
        </div>
        {/* Row 3: project + author */}
        <div style={{
          fontSize: 10, color: '#64748b',
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        }}>
          {projectName} · {todo.author}
        </div>
      </a>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ fontSize: 11, color: '#64748b', marginBottom: 4 }}>
        {todos.length} pending · oldest first
      </div>
      {gitlabItems.length > 0 && (
        <>
          {gitlabItems.length > 0 && githubItems.length > 0 && (
            <div style={{ fontSize: 10, color: '#475569', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              GitLab
            </div>
          )}
          {gitlabItems.map((todo, i) => renderItem(todo, i))}
        </>
      )}
      {githubItems.length > 0 && (
        <>
          <div style={{ fontSize: 10, color: '#475569', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', marginTop: 4 }}>
            GitHub Queued
          </div>
          {githubItems.map((todo, i) => renderItem(todo, i))}
        </>
      )}
    </div>
  );
}
