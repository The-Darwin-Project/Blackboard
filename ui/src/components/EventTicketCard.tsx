// BlackBoard/ui/src/components/EventTicketCard.tsx
// @ai-rules:
// 1. [Pattern]: STATUS_COLORS.border drives full card border ring (status-based). Domain pill badge still uses DOMAIN_COLORS.
// 2. [Pattern]: Close uses window.confirm() -- KISS, matching existing ConversationFeed pattern.
// 3. [Constraint]: Props use ActiveEvent type from api/types.ts.
/**
 * Polymorphic event ticket card with status color coding.
 * Renders in EventTicketList grid inside the middle panel "Tickets" tab.
 */
import type { ActiveEvent } from '../api/types';
import { DOMAIN_COLORS, STATUS_COLORS } from '../constants/colors';
import SourceIcon from './SourceIcon';

interface EventTicketCardProps {
  event: ActiveEvent;
  isSelected: boolean;
  onSelect: () => void;
  onClose: (id: string) => void;
}

export default function EventTicketCard({ event, isSelected, onSelect, onClose }: EventTicketCardProps) {
  const domain = (event.evidence?.domain || 'complicated') as keyof typeof DOMAIN_COLORS;
  const domainColor = DOMAIN_COLORS[domain] || DOMAIN_COLORS.complicated;
  const statusStyle = STATUS_COLORS[event.status] || STATUS_COLORS.active;
  const metrics = event.evidence?.metrics;

  const handleClose = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (event.status === 'closed') return;
    if (window.confirm(`Close event ${event.id}?\nActive agents will be stopped.`)) {
      onClose(event.id);
    }
  };

  return (
    <div
      onClick={onSelect}
      style={{
        padding: '14px 16px',
        borderRadius: 12,
        background: isSelected ? '#334155' : '#0f172a',
        border: `2px solid ${isSelected ? statusStyle.border : statusStyle.border + '88'}`,
        cursor: 'pointer',
        fontSize: 14,
        transition: 'all 0.15s',
      }}
    >
      {/* Row 1: icon + state + domain */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <SourceIcon source={event.source} size={28} />
        <span style={{
          background: statusStyle.bg, color: statusStyle.text,
          padding: '3px 12px', borderRadius: 12, fontSize: 12, fontWeight: 600,
        }}>
          {statusStyle.label}
        </span>
        <span style={{ flex: 1 }} />
        <span style={{
          background: domainColor.bg, color: domainColor.text,
          padding: '3px 10px', borderRadius: 12, fontSize: 11, fontWeight: 600,
          textTransform: 'uppercase',
        }}>
          {domain}
        </span>
        {event.status !== 'closed' && (
          <button
            onClick={handleClose}
            style={{
              background: '#7f1d1d', border: '1px solid #dc262644',
              borderRadius: 8, color: '#fca5a5', fontSize: 14,
              width: 28, height: 28, lineHeight: '28px', textAlign: 'center',
              padding: 0, cursor: 'pointer', fontWeight: 700, flexShrink: 0,
            }}
            title="Close event"
          >
            ✕
          </button>
        )}
      </div>

      {/* Row 2: service name + timestamp */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8, gap: 8 }}>
        <strong style={{ color: '#e2e8f0', fontSize: 14, flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {event.service}
        </strong>
        {event.created && (
          <span style={{ fontSize: 11, color: '#64748b', flexShrink: 0 }}>
            {new Date(event.created).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })}
          </span>
        )}
      </div>

      {/* Row 3: reason */}
      <div style={{
        color: '#94a3b8', fontSize: 13, lineHeight: 1.5,
        overflow: 'hidden', display: '-webkit-box',
        WebkitLineClamp: 3, WebkitBoxOrient: 'vertical',
        marginBottom: metrics ? 8 : 0,
      }} title={event.reason}>
        {event.reason}
      </div>

      {/* Metrics + turns (compact footer) */}
      {metrics && (
        <div style={{ display: 'flex', gap: 12, fontSize: 11, color: '#64748b', marginBottom: 4 }}>
          <span>CPU: {metrics.cpu.toFixed(1)}%</span>
          <span>Mem: {metrics.memory.toFixed(1)}%</span>
          {metrics.replicas !== 'unknown' && <span>Replicas: {metrics.replicas}</span>}
        </div>
      )}
      <div style={{ fontSize: 11, color: '#475569', marginTop: 4 }}>
        {event.turns} turns
      </div>
    </div>
  );
}
