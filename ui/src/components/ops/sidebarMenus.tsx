// BlackBoard/ui/src/components/ops/sidebarMenus.tsx
// @ai-rules:
// 1. [Pattern]: Context menu item builders for EventSidebar. One function per node type.
// 2. [Constraint]: Pure functions returning ContextMenuItem arrays. No hooks, no state.
// 3. [Pattern]: Each menu item has an icon (lucide), label, color, and optional danger flag.
// 4. [Pattern]: kargoStageMenuItems sends create_kargo_event WS command. Conditional MR link.
// 5. [Pattern]: alignerPendingMenuItems — Copy only (Create Event deferred to v2, needs full WS+Brain chain).
// 6. [Pattern]: jenkinsQueueMenuItems — Open in Jenkins (safeOpen, XSS prevention) + Copy Job Name.
// 7. [Pattern]: Exported Headhunter helpers shared with EventSidebar + HeadhunterQueuePanel:
//    isGitHubTodo / isGitHubIssue (platform + PR-vs-Issue detection), formatHeadhunterLabel (label, optional
//    { truncate: false }), getHeadhunterItemKey (React key; idx only used when no todo_id and no item number).
// 8. [Constraint]: GitHub detection parses URLs (hostname === github.com). Never substring-match target_url.
//    Precedence: explicit platform > github.com host > mr_iid (GitLab) > pr_number/issue_number (GitHub).
// 9. [Pattern]: hhMenuItems + eventMenuItems open links via safeOpen (http/https only) and support GitLab MR,
//    GitHub PR and GitHub Issue. eventMenuItems labels follow the evidence field the URL came from
//    (gitlab_context > github_context.pr_url > github_issue_context.html_url > target_url host/path).
import {
  Focus, Info, Copy, MessageSquare, ListChecks, Check,
  Square, ExternalLink, PlusCircle, FileText, RefreshCw, XCircle, CheckCircle2, RotateCcw,
} from 'lucide-react';
import { ACTOR_COLORS } from '../../constants/colors';
import { safeOpen } from '../../utils/safeOpen';
import type { AgentRegistryEntry, KargoStageStatus, JiraMission, JenkinsPendingItem } from '../../api/types';
import type { HeadhunterTodo } from '../../api/client';
import type { ContextMenuItem } from './ContextMenu';

const GITHUB_HOSTS = new Set(['github.com', 'www.github.com']);

/** Parse an absolute http(s) URL; null for relative, malformed or non-http(s) input. */
function parseHttpUrl(url: string | null | undefined): URL | null {
  if (!url) return null;
  try {
    const parsed = new URL(url);
    return parsed.protocol === 'https:' || parsed.protocol === 'http:' ? parsed : null;
  } catch {
    return null;
  }
}

/** For github.com URLs returns the third path segment kind ('issues' | 'pull' | ...); null otherwise. */
function githubPathKind(url: string | null | undefined): string | null {
  const parsed = parseHttpUrl(url);
  if (!parsed || !GITHUB_HOSTS.has(parsed.hostname.toLowerCase())) return null;
  // /{owner}/{repo}/{issues|pull}/{n}
  return parsed.pathname.split('/').filter(Boolean)[2] ?? '';
}

function isGitHubUrl(url: string | null | undefined): boolean {
  return githubPathKind(url) !== null;
}

export function isGitHubTodo(todo: HeadhunterTodo): boolean {
  if (todo.platform === 'github') return true;
  if (todo.platform === 'gitlab') return false;
  if (isGitHubUrl(todo.target_url)) return true;
  // Platform unset: an MR iid is GitLab-only, so it wins over PR/issue numbers.
  if (todo.mr_iid != null) return false;
  return todo.pr_number != null || todo.issue_number != null;
}

export function isGitHubIssue(todo: HeadhunterTodo): boolean {
  if (!isGitHubTodo(todo)) return false;
  if (todo.pr_number != null) return false;
  return todo.issue_number != null || githubPathKind(todo.target_url) === 'issues';
}

export function agentMenuItems(
  name: string, reg: AgentRegistryEntry | undefined, setHotspot: (id: string | null) => void,
): ContextMenuItem[] {
  const color = ACTOR_COLORS[name] || '#6b7280';
  return [
    { id: 'focus', label: 'Focus in Grid', icon: <Focus size={18} />, color, onClick: () => setHotspot(name) },
    { id: 'info', label: 'Agent Info', icon: <Info size={18} />, color: '#94a3b8', onClick: () => {
      window.alert(`Agent: ${name}\nID: ${reg?.agent_id || 'N/A'}\nCLI: ${reg?.cli || 'N/A'}\nModel: ${reg?.model || 'N/A'}\nBusy: ${reg?.busy || false}`);
    }},
    { id: 'sep1', label: '', icon: null, separator: true, onClick: () => {} },
    { id: 'copy', label: 'Copy Agent ID', icon: <Copy size={18} />, color: '#64748b', onClick: () => {
      navigator.clipboard.writeText(reg?.agent_id || name);
    }},
  ];
}

export function eventMenuItems(
  evt: { id: string; status: string; source: string; evidence?: unknown },
  selectEvent: (id: string) => void,
  send: (data: Record<string, unknown>) => void,
  connected: boolean,
): ContextMenuItem[] {
  const ev = evt.evidence as Record<string, unknown> | undefined;
  const gc = ev?.gitlab_context as Record<string, unknown> | undefined;
  const ghc = ev?.github_context as Record<string, unknown> | undefined;
  const ghic = ev?.github_issue_context as Record<string, unknown> | undefined;
  const nonEmpty = (v: unknown): string | null => (typeof v === 'string' && v ? v : null);
  // Label follows the evidence field the URL came from, so an empty github_context ({}) or a GitLab URL
  // can never be mislabelled as GitHub. Only the generic target_url falls back to host/path inspection.
  type MrKind = 'gitlab' | 'pr' | 'issue';
  let mrUrl: string | null = null;
  let mrKind: MrKind = 'gitlab';
  if (evt.source === 'headhunter') {
    const candidates: Array<[string | null, MrKind | null]> = [
      [nonEmpty(gc?.target_url), 'gitlab'],
      [nonEmpty(ghc?.pr_url), 'pr'],
      [nonEmpty(ghic?.html_url), 'issue'],
      [nonEmpty(ev?.target_url), null],
    ];
    const hit = candidates.find(([url]) => url);
    if (hit) {
      mrUrl = hit[0];
      const pathKind = githubPathKind(mrUrl);
      mrKind = hit[1] ?? (pathKind === null ? 'gitlab' : pathKind === 'issues' ? 'issue' : 'pr');
    }
  }
  const mrLabel = mrKind === 'issue' ? 'Open Issue in GitHub' : mrKind === 'pr' ? 'Open PR in GitHub' : 'Open MR in GitLab';

  return [
    { id: 'chat', label: 'Open Chat', icon: <MessageSquare size={18} />, color: '#3b82f6', onClick: () => selectEvent(evt.id) },
    { id: 'plan', label: 'Open Plan', icon: <ListChecks size={18} />, color: '#8b5cf6', onClick: () => selectEvent(evt.id) },
    { id: 'sep1', label: '', icon: null, separator: true, onClick: () => {} },
    ...(mrUrl ? [
      { id: 'open-mr', label: mrLabel, icon: <ExternalLink size={18} />, color: '#f59e0b', onClick: () => safeOpen(mrUrl) },
      { id: 'copy-mr', label: 'Copy URL', icon: <Copy size={18} />, color: '#64748b', onClick: () => navigator.clipboard.writeText(mrUrl) },
      { id: 'sep-mr', label: '', icon: null, separator: true, onClick: () => {} },
    ] : []),
    ...(evt.status === 'waiting_approval' ? [{
      id: 'approve', label: 'Approve Plan', icon: <Check size={18} />, color: '#22c55e',
      onClick: () => { if (connected) send({ type: 'approve', event_id: evt.id }); },
    }] : []),
    { id: 'stop', label: 'Force Close', icon: <Square size={18} />, danger: true,
      onClick: () => { if (window.confirm(`Force close ${evt.id}?`)) send({ type: 'emergency_stop' }); },
      disabled: !connected },
    { id: 'sep2', label: '', icon: null, separator: true, onClick: () => {} },
    { id: 'copy', label: 'Copy Event ID', icon: <Copy size={18} />, color: '#64748b', onClick: () => navigator.clipboard.writeText(evt.id) },
  ];
}

export function hhMenuItems(todo: HeadhunterTodo): ContextMenuItem[] {
  const isGitHub = isGitHubTodo(todo);
  const isIssue = isGitHubIssue(todo);
  const openLabel = isIssue ? 'Open Issue in GitHub' : isGitHub ? 'Open PR in GitHub' : 'Open MR in GitLab';
  const copyLabel = isGitHub ? (isIssue ? 'Copy Issue URL' : 'Copy PR URL') : 'Copy MR URL';

  return [
    { id: 'open', label: openLabel, icon: <ExternalLink size={18} />, color: '#f59e0b', onClick: () => safeOpen(todo.target_url) },
    { id: 'sep1', label: '', icon: null, separator: true, onClick: () => {} },
    { id: 'copy', label: copyLabel, icon: <Copy size={18} />, color: '#64748b', onClick: () => {
      if (todo.target_url && navigator.clipboard?.writeText) {
        navigator.clipboard.writeText(todo.target_url).catch(() => {});
      }
    }},
  ];
}

export function formatHeadhunterLabel(todo: HeadhunterTodo, opts: { truncate?: boolean } = {}): string {
  const { truncate = true } = opts;
  const isGitHub = isGitHubTodo(todo);
  const num = isGitHub ? (todo.pr_number ?? todo.issue_number) : todo.mr_iid;
  const title = isGitHub ? (todo.pr_title ?? todo.issue_title ?? '') : (todo.mr_title ?? '');
  const pfx = isGitHub ? '#' : '!';
  // Code-point safe truncation (Array.from) so emoji surrogate pairs are never split.
  const safeTitle = truncate ? Array.from(title).slice(0, 30).join('') : title;
  if (num != null) return `${pfx}${num}${safeTitle ? ' ' + safeTitle : ''}`;
  return safeTitle || 'Queued Item';
}

export function getHeadhunterItemKey(todo: HeadhunterTodo, idx: number): string | number {
  if (todo.todo_id != null) return todo.todo_id;
  const pfx = isGitHubTodo(todo) ? 'gh' : 'gl';
  const num = todo.pr_number ?? todo.issue_number ?? todo.mr_iid;
  // Stable identity when we have one; list index only as a last resort (it shifts as the queue drains).
  if (num != null) return `${pfx}-${num}-${todo.project_path ?? ''}`;
  return `${pfx}-${todo.project_path ?? ''}-${idx}`;
}

export function alignerPendingMenuItems(item: { target: string; key: string }): ContextMenuItem[] {
  return [
    { id: 'copy-target', label: 'Copy Service Name', icon: <Copy size={18} />, color: '#64748b', onClick: () => navigator.clipboard.writeText(item.target) },
  ];
}

export function jenkinsQueueMenuItems(item: JenkinsPendingItem): ContextMenuItem[] {
  return [
    ...(item.url ? [
      { id: 'open-jenkins', label: 'Open in Jenkins', icon: <ExternalLink size={18} />, color: '#D33833', onClick: () => safeOpen(item.url) },
      { id: 'sep1', label: '', icon: null, separator: true, onClick: () => {} },
    ] : []),
    { id: 'copy-job', label: 'Copy Job Name', icon: <Copy size={18} />, color: '#64748b', onClick: () => navigator.clipboard.writeText(item.job_name || item.target) },
  ];
}

export function kargoStageMenuItems(
  stage: KargoStageStatus,
  send: (data: Record<string, unknown>) => void,
  connected: boolean,
): ContextMenuItem[] {
  return [
    {
      id: 'create-event', label: 'Create Event', icon: <PlusCircle size={18} />, color: '#3b82f6',
      disabled: !connected,
      onClick: () => {
        const directive = window.prompt(
          `Create event for ${stage.stage}@${stage.project}\n\nWhat should FRIDAY do? (optional)`,
        );
        if (directive !== null) {
          send({ type: 'create_kargo_event', project: stage.project, stage: stage.stage, directive: directive || undefined });
        }
      },
    },
    { id: 'sep1', label: '', icon: null, separator: true, onClick: () => {} },
    { id: 'copy-stage', label: 'Copy Stage Name', icon: <Copy size={18} />, color: '#64748b',
      onClick: () => navigator.clipboard.writeText(`${stage.stage}@${stage.project}`) },
    ...(stage.mr_url ? [
      { id: 'open-mr', label: 'Open MR in GitLab', icon: <ExternalLink size={18} />, color: '#f59e0b',
        onClick: () => safeOpen(stage.mr_url) },
    ] : []),
  ];
}

export function jiraMissionMenuItems(
  mission: JiraMission,
  openContentTile: (title: string, content: string) => void,
  actions: { approve: (key: string) => void; reanalyze: (key: string) => void; dismiss: (key: string) => void; retry: (key: string) => void },
): ContextMenuItem[] {
  return [
    { id: 'view-plan', label: 'View Plan', icon: <FileText size={18} />, color: '#8b5cf6',
      disabled: !mission.analysis,
      onClick: () => mission.analysis && openContentTile(`${mission.key}: Analysis`, mission.analysis),
    },
    { id: 'open-jira', label: 'Open in Jira', icon: <ExternalLink size={18} />, color: '#2684FF',
      onClick: () => safeOpen(mission.issue_url) },
    { id: 'sep1', label: '', icon: null, separator: true, onClick: () => {} },
    { id: 'approve', label: 'Approve (→ To Do)', icon: <CheckCircle2 size={18} />, color: '#22c55e',
      onClick: () => actions.approve(mission.key) },
    { id: 'reanalyze', label: 'Re-analyze', icon: <RefreshCw size={18} />, color: '#f59e0b',
      onClick: () => actions.reanalyze(mission.key) },
    { id: 'retry', label: 'Retry (Reset & Re-trigger)', icon: <RotateCcw size={18} />, color: '#6366f1',
      onClick: () => actions.retry(mission.key) },
    { id: 'dismiss', label: 'Dismiss', icon: <XCircle size={18} />, color: '#ef4444',
      onClick: () => actions.dismiss(mission.key) },
  ];
}
