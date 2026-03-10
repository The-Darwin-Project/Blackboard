// BlackBoard/ui/src/components/ReportTurnCard.tsx
// @ai-rules:
// 1. [Pattern]: Agent-colored left border using ACTOR_COLORS. Matches TurnBubble visual language.
// 2. [Pattern]: MarkdownPreview for body content -- supports tables, code blocks, mermaid.
// 3. [Constraint]: Read-only display. No approve/reject/feedback buttons (reports are closed events).
import MarkdownPreview from '@uiw/react-markdown-preview';
import { getCodeString } from 'rehype-rewrite';
import MermaidBlock from './MermaidBlock';
import { ACTOR_COLORS } from '../constants/colors';
import type { ParsedTurn } from '../utils/parseReport';

export default function ReportTurnCard({ turn }: { turn: ParsedTurn }) {
  const color = ACTOR_COLORS[turn.actor] || '#6b7280';

  return (
    <div style={{
      borderLeft: `3px solid ${color}`,
      paddingLeft: 14,
      marginBottom: 16,
    }}>
      {/* Turn header row */}
      <div style={{
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'center',
        gap: 8,
        marginBottom: 6,
      }}>
        <span style={{
          background: color,
          color: '#fff',
          padding: '2px 10px',
          borderRadius: 12,
          fontSize: 12,
          fontWeight: 600,
        }}>
          {turn.actor}
        </span>
        <span style={{ fontSize: 12, color: '#94a3b8' }}>
          {turn.action}
        </span>
        <span style={{ fontSize: 11, color: '#64748b', fontFamily: 'monospace' }}>
          {turn.time}
        </span>
        <span style={{ fontSize: 11, color: '#475569' }}>
          {turn.delta}
        </span>
        {turn.actor !== 'user' && (
          <span style={{
            fontSize: 10,
            color: '#94a3b8',
            background: '#334155',
            padding: '1px 6px',
            borderRadius: 8,
            fontWeight: 500,
          }}>
            AI-generated
          </span>
        )}
      </div>

      {/* Turn body -- rendered as markdown */}
      {turn.body && (
        <MarkdownPreview
          source={turn.body}
          style={{
            background: 'transparent',
            fontSize: 13,
            lineHeight: 1.65,
            color: '#e2e8f0',
          }}
          wrapperElement={{ 'data-color-mode': 'dark' }}
          components={{
            code: ({ children, className, ...props }) => {
              const code = props.node?.children
                ? getCodeString(props.node.children)
                : String(children ?? '');
              if (typeof code === 'string' && typeof className === 'string'
                  && /^language-mermaid/.test(className.toLowerCase())) {
                return <MermaidBlock code={code} />;
              }
              return <code className={String(className ?? '')}>{children}</code>;
            },
          }}
        />
      )}
    </div>
  );
}
