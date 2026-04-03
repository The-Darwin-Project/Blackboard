// BlackBoard/ui/src/components/ops/StreamGrid.tsx
// @ai-rules:
// 1. [Pattern]: Adaptive CSS Grid. Column count computed from tile count. Fills remaining slots with empty tiles.
// 2. [Pattern]: Hotspot mode: clicked tile takes full top area, others in horizontal-scroll thumbnail strip.
// 3. [Pattern]: Reads all state from OpsStateContext. No local WS handling.
// 4. [Constraint]: Esc exits hotspot. Click hotspot tile exits. Click other tile swaps hotspot.
// 5. [Pattern]: Stale hotspot cleanup via useEffect (never setState during render).
// 5. [Pattern]: Auto-hotspot: when enabled and an agent becomes isActive, it auto-promotes to hotspot.
import { useEffect, useCallback } from 'react';
import GridTile from './GridTile';
import { useOpsState } from '../../contexts/OpsStateContext';

interface TileDescriptor {
  id: string;
  type: 'agent-stream' | 'oncall-stream' | 'content-viewer' | 'empty';
  agentName?: string;
}

function computeGridCols(count: number): number {
  if (count <= 1) return 1;
  if (count <= 2) return 2;
  if (count <= 4) return 2;
  if (count <= 6) return 3;
  if (count <= 8) return 4;
  return 4;
}


export default function StreamGrid() {
  const {
    agents, agentStreams, ephemeralAgents, ephemeralStream,
    contentTiles, closeContentTile,
    hotspotTileId, setHotspot, autoHotspot,
  } = useOpsState();

  const tiles: TileDescriptor[] = [];

  for (const a of agents) {
    tiles.push({ id: a, type: 'agent-stream', agentName: a });
  }
  for (const ea of ephemeralAgents) {
    tiles.push({ id: ea.agent_id, type: 'oncall-stream', agentName: ea.current_role || 'oncall' });
  }
  for (const ct of contentTiles) {
    tiles.push({ id: ct.id, type: 'content-viewer' });
  }

  const cols = computeGridCols(tiles.length);
  const rows = Math.ceil(tiles.length / cols);
  const totalSlots = cols * rows;
  while (tiles.length < totalSlots) {
    tiles.push({ id: `empty-${tiles.length}`, type: 'empty' });
  }

  const handleTileClick = useCallback((id: string) => {
    if (hotspotTileId === id) {
      setHotspot(null);
    } else {
      setHotspot(id);
    }
  }, [hotspotTileId, setHotspot]);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && hotspotTileId) {
        const active = document.activeElement;
        if (active && (active.tagName === 'INPUT' || active.tagName === 'TEXTAREA')) return;
        setHotspot(null);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [hotspotTileId, setHotspot]);

  useEffect(() => {
    if (!autoHotspot) return;
    const activeAgent = agents.find(a => agentStreams[a]?.isActive);
    if (activeAgent && hotspotTileId !== activeAgent) {
      setHotspot(activeAgent);
    } else if (!activeAgent && hotspotTileId) {
      const isContentOrEphemeral = hotspotTileId.startsWith('content-') || ephemeralAgents.some(e => e.agent_id === hotspotTileId);
      if (!isContentOrEphemeral) setHotspot(null);
    }
  }, [autoHotspot, agents, agentStreams, hotspotTileId, setHotspot, ephemeralAgents]);

  const renderTile = (tile: TileDescriptor) => {
    const ct = contentTiles.find(c => c.id === tile.id);
    const ea = ephemeralAgents.find(e => e.agent_id === tile.id);
    return (
      <GridTile
        key={tile.id}
        type={tile.type}
        tileId={tile.id}
        isHotspot={hotspotTileId === tile.id}
        onTileClick={handleTileClick}
        agentName={tile.agentName}
        agentState={tile.type === 'agent-stream' ? agentStreams[tile.agentName!] : undefined}
        contentTile={ct}
        onCloseContent={closeContentTile}
        ephemeralMessages={ea ? ephemeralStream[ea.bound_event_id || ''] : undefined}
        ephemeralActive={ea?.busy}
      />
    );
  };

  useEffect(() => {
    if (hotspotTileId && !tiles.some(t => t.id === hotspotTileId)) {
      setHotspot(null);
    }
  }, [hotspotTileId, tiles, setHotspot]);

  if (hotspotTileId) {
    const hotspotTile = tiles.find(t => t.id === hotspotTileId);
    const stripTiles = tiles.filter(t => t.id !== hotspotTileId && t.type !== 'empty');

    if (!hotspotTile) return null;

    return (
      <div className="h-full flex flex-col p-3 gap-3 overflow-hidden">
        {/* Hotspot tile -- takes ~65% of height */}
        <div className="overflow-hidden" style={{ flex: '2 1 0%', minHeight: 0 }}>
          {renderTile(hotspotTile)}
        </div>

        {/* Thumbnail strip -- tiles fill available width and remaining height */}
        {stripTiles.length > 0 && (
          <div className="flex gap-3 overflow-x-auto overflow-y-hidden" style={{ flex: '1 1 0%', minHeight: 0 }}>
            {stripTiles.map(t => (
              <div key={t.id} className="h-full overflow-hidden flex-shrink-0" style={{ minWidth: 200, width: `${100 / Math.min(stripTiles.length, 6)}%` }}>
                {renderTile(t)}
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="h-full p-3 overflow-hidden">
      <div style={{
        display: 'grid',
        gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))`,
        gridTemplateRows: `repeat(${rows}, minmax(0, 1fr))`,
        gap: 10,
        height: '100%',
        transition: 'all 0.2s ease',
      }}>
        {tiles.map(t => renderTile(t))}
      </div>
    </div>
  );
}
