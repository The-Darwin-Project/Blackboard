// BlackBoard/ui/src/components/ops/MockConversationFeed.tsx
// @ai-rules:
// 1. [Constraint]: Dev-only mock conversation feed. Renders static turns from mockData.ts.
// 2. [Pattern]: Mimics ConversationFeed's visual structure without API calls or WS handling.
// 3. [Gotcha]: NOT a production component. Remove when backend is available.
import { ACTOR_COLORS, STATUS_COLORS } from '../../constants/colors';
import SourceIcon from '../SourceIcon';
import { MOCK_EVENT_DOC } from './mockData';
import { useOpsState } from '../../contexts/OpsStateContext';

export default function MockConversationFeed() {
  const { openContentTile } = useOpsState();
  const evt = MOCK_EVENT_DOC;
  const sc = STATUS_COLORS[evt.status] || STATUS_COLORS.active;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0, overflow: 'hidden' }}>
      {/* Header -- matches real ConversationFeed header */}
      <div style={{ padding: '8px 12px', borderBottom: '1px solid #333', background: '#1e293b', flexShrink: 0 }}>
        {/* Row 1: service + status + event id + source */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <span style={{ fontSize: 14, color: '#e2e8f0', fontWeight: 600 }}>{evt.service}</span>
            <span style={{ padding: '2px 8px', borderRadius: 8, fontSize: 11, fontWeight: 600, background: sc.bg, color: sc.text }}>{sc.label}</span>
            <span style={{ fontSize: 12, color: '#64748b', fontFamily: 'monospace' }}>{evt.id}</span>
          </div>
          <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            <SourceIcon source={evt.source} size={14} />
            <span style={{ fontSize: 12, color: '#64748b' }}>{evt.source} | {evt.conversation.length} turns</span>
          </div>
        </div>
        {/* Row 2: action buttons */}
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <button onClick={() => {
              const md = `# Event Report: ${evt.id}\n\n**Service:** ${evt.service}\n**Status:** ${evt.status}\n**Source:** ${evt.source}\n**Domain:** ${evt.event.evidence.domain}\n\n## Conversation (${evt.conversation.length} turns)\n\n${evt.conversation.map(t => `### Turn ${t.turn} — ${t.actor} (${t.action})\n${t.thoughts || ''}\n${t.result || ''}\n${t.plan || ''}`).join('\n\n')}`;
              openContentTile(`Report: ${evt.id.slice(0, 12)}`, md);
            }}
            style={{ background: '#1e3a5f', border: '1px solid #2563eb44', borderRadius: 4, color: '#93c5fd', fontSize: 12, padding: '3px 10px', cursor: 'pointer', fontWeight: 600 }}
            title="View event report in stream grid">Report</button>
          <button style={{ background: '#14532d', border: '1px solid #22c55e44', borderRadius: 4, color: '#86efac', fontSize: 12, padding: '3px 10px', cursor: 'pointer', fontWeight: 600 }}
            title="Approve plan (demo)">Approve</button>
          <button style={{ background: '#7f1d1d', border: '1px solid #dc262644', borderRadius: 4, color: '#fca5a5', fontSize: 12, padding: '3px 10px', cursor: 'pointer', fontWeight: 600 }}
            title="Force close (demo)">Force Close</button>
          <div style={{ flex: 1 }} />
          <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 8, fontWeight: 600,
            background: evt.event.evidence.domain === 'complex' ? '#a855f715' : evt.event.evidence.domain === 'complicated' ? '#eab30815' : evt.event.evidence.domain === 'clear' ? '#22c55e15' : '#6b728015',
            color: evt.event.evidence.domain === 'complex' ? '#c084fc' : evt.event.evidence.domain === 'complicated' ? '#facc15' : evt.event.evidence.domain === 'clear' ? '#4ade80' : '#9ca3af',
            border: `1px solid ${evt.event.evidence.domain === 'complex' ? '#a855f730' : evt.event.evidence.domain === 'complicated' ? '#eab30830' : evt.event.evidence.domain === 'clear' ? '#22c55e30' : '#6b728030'}`,
          }}>{evt.event.evidence.domain}</span>
          <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 8, fontWeight: 600,
            background: evt.event.evidence.severity === 'critical' ? '#7f1d1d' : evt.event.evidence.severity === 'warning' ? '#78350f' : '#1e3a5f',
            color: evt.event.evidence.severity === 'critical' ? '#fca5a5' : evt.event.evidence.severity === 'warning' ? '#fcd34d' : '#7dd3fc',
          }}>{evt.event.evidence.severity}</span>
        </div>
      </div>

      <div style={{ flex: 1, overflow: 'auto', padding: 12, minHeight: 0 }}>
        {evt.conversation.map((turn, i) => {
          const color = ACTOR_COLORS[turn.actor] || '#6b7280';
          const isBrain = turn.actor === 'brain';
          const isUser = turn.actor === 'user';
          const ts = new Date(turn.timestamp * 1000).toLocaleTimeString('en-GB', { hour12: false, hour: '2-digit', minute: '2-digit' });

          return (
            <div key={i} style={{
              marginBottom: 10,
              padding: '8px 12px',
              borderRadius: 10,
              borderLeft: `3px solid ${color}`,
              background: `${color}08`,
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                  <span style={{ fontSize: 12, fontWeight: 700, color }}>{turn.actor}</span>
                  <span style={{ fontSize: 11, color: '#64748b', fontWeight: 500 }}>{turn.action}</span>
                  {turn.pendingApproval && (
                    <span style={{ fontSize: 11, padding: '1px 6px', borderRadius: 6, background: '#92400e', color: '#fcd34d', fontWeight: 600 }}>awaiting approval</span>
                  )}
                </div>
                <span style={{ fontSize: 11, color: '#475569', fontFamily: 'monospace' }}>{ts}</span>
              </div>
              {turn.thoughts && (
                <div style={{ fontSize: 13, color: isUser ? '#e2e8f0' : (isBrain ? '#c4b5fd' : '#94a3b8'), lineHeight: 1.5, whiteSpace: 'pre-wrap' }}>
                  {turn.thoughts}
                </div>
              )}
              {(turn.action === 'request_approval' || turn.pendingApproval) && (
                <button onClick={() => openContentTile(
                  `brain — Approval Request (turn ${turn.turn})`,
                  `# Approval Request\n\n**Turn ${turn.turn}** · ${ts}\n\n---\n\n${turn.thoughts || ''}\n\n---\n\n> **Action required:** Review the plan above and approve or reject.\n>\n> - **Approve** to proceed with implementation\n> - **Reject** with feedback to revise the plan`
                )}
                  style={{ background: '#92400e', border: '1px solid #f59e0b44', borderRadius: 4, color: '#fcd34d', fontSize: 11, padding: '2px 8px', cursor: 'pointer', fontWeight: 500, marginTop: 6 }}>
                  View in Grid
                </button>
              )}
              {turn.result && (
                <div style={{ marginTop: 6 }}>
                  <div style={{ fontSize: 12, color: '#94a3b8', lineHeight: 1.5, whiteSpace: 'pre-wrap', background: '#0f172a', padding: 8, borderRadius: 6, maxHeight: 120, overflow: 'hidden', position: 'relative' }}>
                    {turn.result}
                    <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 32, background: 'linear-gradient(transparent, #0f172a)', pointerEvents: 'none' }} />
                  </div>
                  <button onClick={() => openContentTile(
                    `${turn.actor} — ${turn.action} (turn ${turn.turn})`,
                    `# ${turn.actor} — ${turn.action}\n\n**Turn ${turn.turn}** · ${ts}\n\n---\n\n${turn.thoughts ? `## Analysis\n\n${turn.thoughts}\n\n` : ''}## Result\n\n${turn.result}`
                  )}
                    style={{ background: '#1e3a5f', border: '1px solid #2563eb44', borderRadius: 4, color: '#93c5fd', fontSize: 11, padding: '2px 8px', cursor: 'pointer', fontWeight: 500, marginTop: 4 }}>
                    View in Grid
                  </button>
                </div>
              )}
              {turn.plan && (
                <div style={{ marginTop: 6 }}>
                  <div style={{ fontSize: 12, color: '#94a3b8', lineHeight: 1.5, whiteSpace: 'pre-wrap', background: '#0f172a', padding: 8, borderRadius: 6, borderLeft: '2px solid #8b5cf6', maxHeight: 120, overflow: 'hidden', position: 'relative' }}>
                    {turn.plan}
                    <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 32, background: 'linear-gradient(transparent, #0f172a)', pointerEvents: 'none' }} />
                  </div>
                  <button onClick={() => openContentTile(
                    `${turn.actor} — Plan (turn ${turn.turn})`,
                    `# Plan by ${turn.actor}\n\n**Turn ${turn.turn}** · ${ts}\n\n${turn.thoughts ? `> ${turn.thoughts}\n\n` : ''}---\n\n${turn.plan}${turn.selectedAgents ? `\n\n---\n\n**Assigned agents:** ${turn.selectedAgents.join(', ')}` : ''}`
                  )}
                    style={{ background: '#8b5cf620', border: '1px solid #8b5cf644', borderRadius: 4, color: '#c084fc', fontSize: 11, padding: '2px 8px', cursor: 'pointer', fontWeight: 500, marginTop: 4 }}>
                    View in Grid
                  </button>
                </div>
              )}
              {turn.selectedAgents && (
                <div style={{ marginTop: 4, display: 'flex', gap: 4 }}>
                  {turn.selectedAgents.map(a => (
                    <span key={a} style={{ fontSize: 11, padding: '1px 6px', borderRadius: 8, background: `${ACTOR_COLORS[a] || '#6b7280'}20`, color: ACTOR_COLORS[a] || '#6b7280', fontWeight: 600 }}>{a}</span>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
