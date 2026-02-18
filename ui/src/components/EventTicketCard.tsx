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
      {/* Header: service + status */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
        <strong style={{ color: '#e2e8f0', fontSize: 15 }}>{event.service}</strong>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{
            background: statusStyle.bg, color: statusStyle.text,
            padding: '2px 10px', borderRadius: 10, fontSize: 11, fontWeight: 600,
          }}>
            {statusStyle.label}
          </span>
          <span style={{
            background: domainColor.bg, color: domainColor.text,
            padding: '2px 8px', borderRadius: 10, fontSize: 10, fontWeight: 600,
            textTransform: 'uppercase',
          }}>
            {domain}
          </span>
        </div>
      </div>

      {/* Reason */}
      <div style={{
        color: '#94a3b8', fontSize: 13, marginBottom: 8,
        overflow: 'hidden', display: '-webkit-box',
        WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
        lineHeight: 1.4,
      }} title={event.reason}>
        {event.reason}
      </div>

      {/* Metrics mini-bar (if available) */}
      {metrics && (
        <div style={{ display: 'flex', gap: 14, fontSize: 12, color: '#64748b', marginBottom: 6 }}>
          <span>CPU: {metrics.cpu.toFixed(1)}%</span>
          <span>Mem: {metrics.memory.toFixed(1)}%</span>
          {metrics.replicas !== 'unknown' && <span>Replicas: {metrics.replicas}</span>}
        </div>
      )}

      {/* Footer: source + turns + close */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 12, color: '#64748b' }}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <SourceIcon source={event.source} size={16} />
          <span>{event.turns} turns</span>
        </div>
        {event.status !== 'closed' && (
          <button
            onClick={handleClose}
            style={{
              background: '#7f1d1d', border: '1px solid #dc262644',
              borderRadius: 6, color: '#fca5a5', fontSize: 11,
              padding: '2px 8px', cursor: 'pointer', fontWeight: 600,
            }}
            title="Close event"
          >
            x
          </button>
        )}
      </div>
    </div>
  );
}
