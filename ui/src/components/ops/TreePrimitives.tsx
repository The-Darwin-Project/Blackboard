// BlackBoard/ui/src/components/ops/TreePrimitives.tsx
// @ai-rules:
// 1. [Pattern]: Reusable tree UI primitives for the EventSidebar. Stateless where possible.
// 2. [Constraint]: Pure presentational. No data fetching, no context access.
// 3. [Pattern]: TreeGroup is the only stateful primitive (open/close toggle).
import { useState, type ReactNode } from 'react';
import { ChevronRight, Bot, Radio } from 'lucide-react';
import { ACTOR_COLORS, STATUS_COLORS } from '../../constants/colors';
import SourceIcon from '../SourceIcon';

export function TreeGroup({ icon, label, count, countColor, children, nested, forceCollapsed }: {
  icon: ReactNode; label: string; count: number; countColor?: string; children: ReactNode; nested?: boolean; forceCollapsed?: boolean;
}) {
  const [userOpen, setUserOpen] = useState(true);
  const [userOverride, setUserOverride] = useState(false);
  const open = (forceCollapsed && !userOverride) ? false : userOpen;
  return (
    <div className={nested ? 'ml-2 mt-0.5' : 'mb-1'}>
      <button onClick={() => { setUserOpen(!open); if (forceCollapsed) setUserOverride(!userOverride); }}
        aria-expanded={open}
        className="w-full flex items-center gap-1.5 px-2 py-1 rounded text-left hover:bg-bg-tertiary transition-colors">
        <ChevronRight size={13} className={`text-text-muted transition-transform flex-shrink-0 ${open ? 'rotate-90' : ''}`} />
        <span className="flex-shrink-0 text-text-muted">{icon}</span>
        <span className="text-[14px] font-semibold text-text-secondary">{label}</span>
        <span className="ml-auto text-[12px] font-medium px-1.5 rounded-full"
          style={{ background: `${countColor || '#64748b'}18`, color: countColor || '#64748b' }}>
          {count}
        </span>
      </button>
      {open && <div className="ml-1 mt-0.5">{children}</div>}
    </div>
  );
}

export function TreeNode({ icon, label, labelColor, sublabel, sublabelColor, onClick, onContextMenu, style }: {
  icon: ReactNode; label: string; labelColor?: string; sublabel?: string; sublabelColor?: string;
  onClick?: () => void; onContextMenu?: (e: React.MouseEvent) => void; style?: React.CSSProperties;
}) {
  return (
    <div className="flex items-center gap-2 px-3 py-1 rounded text-[14px] hover:bg-bg-tertiary cursor-pointer transition-colors group"
      onClick={onClick} onContextMenu={onContextMenu} style={style}>
      <span className="flex-shrink-0">{icon}</span>
      <span className="truncate font-medium" style={labelColor ? { color: labelColor } : { color: 'var(--text-secondary)' }}>{label}</span>
      {sublabel && (
        <span className="ml-auto text-[12px] truncate flex-shrink-0" style={{ color: sublabelColor || '#475569' }}>{sublabel}</span>
      )}
    </div>
  );
}

export function EventNode({ evt, isSelected, onClick, onContextMenu }: {
  evt: { id: string; status: string; source: string; service: string; current_agent?: string | null };
  isSelected: boolean; onClick: () => void; onContextMenu: (e: React.MouseEvent) => void;
}) {
  const sc = STATUS_COLORS[evt.status];
  return (
    <div className={`flex items-center gap-2 px-3 py-1 rounded text-[14px] cursor-pointer transition-colors ${
      isSelected ? 'bg-accent/15 border border-accent/30' : 'hover:bg-bg-tertiary border border-transparent'
    }`} onClick={onClick} onContextMenu={onContextMenu}>
      <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: sc?.border || '#64748b' }} />
      <SourceIcon source={evt.source} size={18} />
      <span className="text-text-secondary truncate">{evt.id.slice(4, 12)}</span>
      {evt.current_agent && (
        <span className="ml-auto text-[12px] px-1 rounded"
          style={{ color: ACTOR_COLORS[evt.current_agent] || '#64748b', background: `${ACTOR_COLORS[evt.current_agent] || '#64748b'}15` }}>
          {evt.current_agent}
        </span>
      )}
    </div>
  );
}

export function EmptyLabel({ children }: { children: ReactNode }) {
  return <div className="pl-4 py-1 text-[12px] text-text-muted italic">{children}</div>;
}

export function AgentDot({ count, active }: { count: number; active: number }) {
  const hasActive = active > 0;
  return (
    <div className="flex flex-col items-center gap-0.5"
      title={`${count} connected, ${active} active`}>
      <div className="relative">
        <Bot size={18} className={count > 0 ? 'text-green-400/70' : 'text-text-muted'} />
        {hasActive && (
          <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-green-400"
            style={{ boxShadow: '0 0 4px #4ade80' }} />
        )}
      </div>
      <span className="text-[10px]" style={{ color: hasActive ? '#4ade80' : count > 0 ? '#4ade8070' : '#64748b' }}>
        {hasActive ? `${active} busy` : `${count}`}
      </span>
    </div>
  );
}

export function EventDot({ count }: { count: number }) {
  return (
    <div className="flex flex-col items-center gap-0.5" title={`${count} events`}>
      <Radio size={18} className={count > 0 ? 'text-blue-400' : 'text-text-muted'} />
      <span className="text-[11px] text-text-muted">{count}</span>
    </div>
  );
}
