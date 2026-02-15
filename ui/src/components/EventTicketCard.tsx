// BlackBoard/ui/src/components/EventTicketCard.tsx
// @ai-rules:
// 1. [Pattern]: Cynefin domain color from DOMAIN_COLORS drives left border color.
// 2. [Pattern]: Close uses window.confirm() -- KISS, matching existing ConversationFeed pattern.
// 3. [Constraint]: Props use ActiveEvent type from api/types.ts.
/**
 * Polymorphic event ticket card with Cynefin color coding.
 * Renders in EventTicketList inside the middle panel "Tickets" tab.
 */
import type { ActiveEvent } from '../api/types';
import { DOMAIN_COLORS, STATUS_COLORS } from '../constants/colors';

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
        padding: '10px 12px',
        marginBottom: 6,
        borderRadius: 8,
        background: isSelected ? '#334155' : '#1e293b',
        borderLeft: `4px solid ${domainColor.border}`,
        cursor: 'pointer',
        fontSize: 13,
        transition: 'background 0.15s',
      }}
    >
      {/* Header: service + status */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
        <strong style={{ color: '#e2e8f0', fontSize: 13 }}>{event.service}</strong>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{
            background: statusStyle.bg, color: statusStyle.text,
            padding: '1px 8px', borderRadius: 10, fontSize: 10, fontWeight: 600,
          }}>
            {statusStyle.label}
          </span>
          <span style={{
            background: domainColor.bg, color: domainColor.text,
            padding: '1px 6px', borderRadius: 10, fontSize: 9, fontWeight: 600,
            textTransform: 'uppercase',
          }}>
            {domain}
          </span>
        </div>
      </div>

      {/* Reason */}
      <div style={{
        color: '#94a3b8', fontSize: 12, marginBottom: 4,
        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
      }} title={event.reason}>
        {event.reason}
      </div>

      {/* Metrics mini-bar (if available) */}
      {metrics && (
        <div style={{ display: 'flex', gap: 12, fontSize: 11, color: '#64748b', marginBottom: 4 }}>
          <span>CPU: {metrics.cpu.toFixed(1)}%</span>
          <span>Mem: {metrics.memory.toFixed(1)}%</span>
          {metrics.replicas !== 'unknown' && <span>Replicas: {metrics.replicas}</span>}
        </div>
      )}

      {/* Footer: source + turns + close */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 11, color: '#64748b' }}>
        <div style={{ display: 'flex', gap: 8 }}>
          <span>{event.source}</span>
          <span>{event.turns} turns</span>
        </div>
        {event.status !== 'closed' && (
          <button
            onClick={handleClose}
            style={{
              background: '#7f1d1d', border: '1px solid #dc262644',
              borderRadius: 4, color: '#fca5a5', fontSize: 10,
              padding: '1px 6px', cursor: 'pointer', fontWeight: 600,
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
