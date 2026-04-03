// BlackBoard/ui/src/components/ops/sidebarMenus.tsx
// @ai-rules:
// 1. [Pattern]: Context menu item builders for EventSidebar. One function per node type.
// 2. [Constraint]: Pure functions returning ContextMenuItem arrays. No hooks, no state.
// 3. [Pattern]: Each menu item has an icon (lucide), label, color, and optional danger flag.
import {
  Focus, Info, Copy, MessageSquare, ListChecks, Check,
  Square, ExternalLink,
} from 'lucide-react';
import { ACTOR_COLORS } from '../../constants/colors';
import type { AgentRegistryEntry } from '../../api/types';
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
  evt: { id: string; status: string },
  selectEvent: (id: string) => void,
  send: (data: Record<string, unknown>) => void,
  connected: boolean,
): ContextMenuItem[] {
  return [
    { id: 'chat', label: 'Open Chat', icon: <MessageSquare size={18} />, color: '#3b82f6', onClick: () => selectEvent(evt.id) },
    { id: 'plan', label: 'Open Plan', icon: <ListChecks size={18} />, color: '#8b5cf6', onClick: () => selectEvent(evt.id) },
    { id: 'sep1', label: '', icon: null, separator: true, onClick: () => {} },
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
    { id: 'open', label: 'Open MR in GitLab', icon: <ExternalLink size={18} />, color: '#f59e0b', onClick: () => window.open(todo.target_url, '_blank') },
    { id: 'sep1', label: '', icon: null, separator: true, onClick: () => {} },
    { id: 'copy', label: 'Copy MR URL', icon: <Copy size={18} />, color: '#64748b', onClick: () => navigator.clipboard.writeText(todo.target_url) },
  ];
}
