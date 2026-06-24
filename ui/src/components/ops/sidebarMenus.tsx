// BlackBoard/ui/src/components/ops/sidebarMenus.tsx
// @ai-rules:
// 1. [Pattern]: Context menu item builders for EventSidebar. One function per node type.
// 2. [Constraint]: Pure functions returning ContextMenuItem arrays. No hooks, no state.
// 3. [Pattern]: Each menu item has an icon (lucide), label, color, and optional danger flag.
// 4. [Pattern]: kargoStageMenuItems sends create_kargo_event WS command. Conditional MR link.
import {
  Focus, Info, Copy, MessageSquare, ListChecks, Check,
  Square, ExternalLink, PlusCircle, FileText, RefreshCw, XCircle, CheckCircle2, RotateCcw,
} from 'lucide-react';
import { ACTOR_COLORS } from '../../constants/colors';
import { safeOpen } from '../../utils/safeOpen';
import type { AgentRegistryEntry, KargoStageStatus, JiraMission } from '../../api/types';
import type { HeadhunterTodo } from '../../api/client';
import type { ContextMenuItem } from './ContextMenu';

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
  const mrUrl = evt.source === 'headhunter'
    ? (gc?.target_url as string || ev?.target_url as string || null)
    : null;

  return [
    { id: 'chat', label: 'Open Chat', icon: <MessageSquare size={18} />, color: '#3b82f6', onClick: () => selectEvent(evt.id) },
    { id: 'plan', label: 'Open Plan', icon: <ListChecks size={18} />, color: '#8b5cf6', onClick: () => selectEvent(evt.id) },
    { id: 'sep1', label: '', icon: null, separator: true, onClick: () => {} },
    ...(mrUrl ? [
      { id: 'open-mr', label: 'Open MR in GitLab', icon: <ExternalLink size={18} />, color: '#f59e0b', onClick: () => safeOpen(mrUrl) },
      { id: 'copy-mr', label: 'Copy MR URL', icon: <Copy size={18} />, color: '#64748b', onClick: () => navigator.clipboard.writeText(mrUrl) },
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
  return [
    { id: 'open', label: 'Open MR in GitLab', icon: <ExternalLink size={18} />, color: '#f59e0b', onClick: () => safeOpen(todo.target_url) },
    { id: 'sep1', label: '', icon: null, separator: true, onClick: () => {} },
    { id: 'copy', label: 'Copy MR URL', icon: <Copy size={18} />, color: '#64748b', onClick: () => navigator.clipboard.writeText(todo.target_url) },
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
