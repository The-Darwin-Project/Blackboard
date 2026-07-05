// BlackBoard/ui/src/components/ops/GridTile.tsx
// @ai-rules:
// 1. [Pattern]: Generic tile wrapper — 2 modes: agent-stream, content-viewer.
// 2. [Pattern]: Click handler on tile border triggers hotspot focus (not on inner content).
// 3. [Pattern]: content-viewer renders InlineMarkdownViewer with close button.
// 4. [Pattern]: Agent tile color from ACTOR_COLORS (fallback #4ade80). Content-viewer infers from title regex.
// 5. [Pattern]: React.memo wraps export — parent passes ActiveStream object directly (no inline copy).
import { memo } from 'react';
import AgentStreamCard from '../AgentStreamCard';
import InlineMarkdownViewer from './InlineMarkdownViewer';
import { ACTOR_COLORS } from '../../constants/colors';
import type { ContentTile } from '../../contexts/OpsStateContext';
import type { ActiveStream } from '../../utils/streamReducers';

export type TileType = 'agent-stream' | 'content-viewer';

interface GridTileProps {
  type: TileType;
  tileId: string;
  isHotspot: boolean;
  onTileClick: (id: string) => void;
  agentName?: string;
  agentState?: ActiveStream;
  contentTile?: ContentTile;
  onCloseContent?: (id: string) => void;
}

function GridTile({
  type, tileId, isHotspot, onTileClick,
  agentName, agentState,
  contentTile, onCloseContent,
}: GridTileProps) {
  if (type === 'content-viewer' && contentTile) {
    const actorMatch = contentTile.title.match(/^(brain|architect|sysadmin|developer|qe|security_analyst|aligner|user)\b/i);
    const actorName = actorMatch ? actorMatch[1].toLowerCase() : null;
    const tileColor = actorName ? (ACTOR_COLORS[actorName] || '#6b7280') : '#6b7280';
    const isReport = contentTile.title.toLowerCase().startsWith('report');
    const headerColor = isReport ? '#8b5cf6' : tileColor;

    return (
      <div className="h-full rounded-lg flex flex-col overflow-hidden"
        style={{ border: `1px solid ${headerColor}40` }}>
        <div className="flex items-center justify-between px-3 py-1.5 flex-shrink-0"
          style={{ borderBottom: `1px solid ${headerColor}30`, background: `${headerColor}12` }}>
          <div className="flex items-center gap-2 truncate">
            <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: headerColor }} />
            <span className="text-xs font-semibold truncate" style={{ color: headerColor }}>{contentTile.title}</span>
          </div>
          <button onClick={() => onCloseContent?.(contentTile.id)}
            className="hover:text-text-primary text-sm ml-2 flex-shrink-0 cursor-pointer"
            style={{ color: `${headerColor}80` }}
            title="Close tile">&times;</button>
        </div>
        <div className="flex-1 overflow-hidden min-h-0 bg-bg-secondary">
          <InlineMarkdownViewer content={contentTile.content} />
        </div>
      </div>
    );
  }

  const name = agentName || tileId;
  const color = ACTOR_COLORS[name] || '#4ade80';
  const isActive = agentState?.isActive || false;

  return (
    <div className="relative h-full flex flex-col min-w-0 overflow-hidden focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent/50 focus-visible:outline-offset-[-2px]"
      role="button" tabIndex={0}
      onClick={(e) => {
        if ((e.target as HTMLElement).closest('button')) return;
        onTileClick(tileId);
      }}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onTileClick(tileId); } }}
      style={{ cursor: 'pointer' }}>
      {isHotspot && (
        <div className="absolute inset-0 rounded-lg pointer-events-none z-10"
          style={{ boxShadow: `inset 0 0 0 2px ${color}, 0 0 12px ${color}33` }} />
      )}
      <div className="flex-1 min-h-0 min-w-0 flex">
        <AgentStreamCard
          agentName={name}
          eventId={agentState?.eventId || null}
          messages={agentState?.messages || []}
          isActive={isActive}
        />
      </div>
    </div>
  );
}

export default memo(GridTile);
