// BlackBoard/ui/src/components/ops/StreamGrid.tsx
// @ai-rules:
// 1. [Pattern]: CCTV-style adaptive grid. Column count = ceil(sqrt(tileCount)).
//    0 tiles → empty state (flow summary). 1 → full width. 2 → side-by-side. 3-4 → 2x2. etc.
// 2. [Pattern]: Tiles sourced from unified activeStreams + contentTiles. No persistent/ephemeral split.
// 3. [Pattern]: Grid never scrolls. Tiles shrink to fit. Each tile handles internal scroll.
// 4. [Pattern]: Hotspot mode: click tile to focus. Esc exits. Side-by-side when 4+ non-hotspot tiles.
// 5. [Pattern]: Auto-hotspot: when enabled, newly active streams auto-promote.
// 6. [Pattern]: Layout transitions use 150ms opacity fade.
import { useEffect, useCallback, useState, useRef, useMemo } from 'react';
import { Activity, Cpu, Layers, Radio } from 'lucide-react';
import GridTile from './GridTile';
import { useOpsState } from '../../contexts/OpsStateContext';
import { useFlowMetrics } from '../../hooks/useFlowMetrics';

type LayoutMode = 'grid' | 'top-bottom' | 'side-by-side';
const SIDE_BY_SIDE_THRESHOLD = 4;

interface TileDescriptor {
  id: string;
  type: 'stream' | 'content-viewer';
  actor?: string;
  eventId?: string;
}

function computeGridCols(count: number): number {
  if (count <= 1) return 1;
  if (count <= 2) return 2;
  return Math.ceil(Math.sqrt(count));
}

function EmptyState() {
  const { data } = useFlowMetrics();
  const { registeredAgents } = useOpsState();
  const connectedCount = registeredAgents.length;
  const busyCount = registeredAgents.filter(a => a.busy).length;

  return (
    <div className="h-full flex flex-col items-center justify-center gap-6 text-text-muted select-none">
      <div className="flex items-center gap-3 opacity-40">
        <Activity size={28} className="text-accent" />
        <span className="text-lg font-semibold text-text-secondary">Darwin Operations Center</span>
      </div>

      <div className="flex gap-8 text-center">
        <div className="flex flex-col items-center gap-1">
          <Cpu size={18} className={connectedCount > 0 ? 'text-green-400/70' : 'text-text-muted'} />
          <span className="text-[13px] font-medium text-text-secondary">
            {busyCount > 0 ? `${busyCount} busy` : `${connectedCount} agents`}
          </span>
          <span className="text-[10px] text-text-muted">connected</span>
        </div>
        {data && (
          <>
            <div className="flex flex-col items-center gap-1">
              <Radio size={18} className={data.active_events > 0 ? 'text-blue-400' : 'text-text-muted'} />
              <span className="text-[13px] font-medium text-text-secondary">{data.active_events}</span>
              <span className="text-[10px] text-text-muted">events</span>
            </div>
            <div className="flex flex-col items-center gap-1">
              <Layers size={18} className={data.queue_depth > 0 ? 'text-amber-400' : 'text-text-muted'} />
              <span className="text-[13px] font-medium text-text-secondary">{data.queue_depth}</span>
              <span className="text-[10px] text-text-muted">queued</span>
            </div>
          </>
        )}
      </div>

      <span className="text-[11px] text-text-muted/60">
        Agent streams appear here when work begins
      </span>
    </div>
  );
}

export default function StreamGrid() {
  const {
    activeStreams, contentTiles, closeContentTile,
    hotspotTileId, setHotspot, autoHotspot,
  } = useOpsState();

  const tiles = useMemo(() => {
    const result: TileDescriptor[] = [];
    for (const [key, stream] of Object.entries(activeStreams)) {
      if (stream.messages.length === 0) continue;
      result.push({
        id: key,
        type: 'stream',
        actor: stream.actor,
        eventId: stream.eventId,
      });
    }
    for (const ct of contentTiles) {
      result.push({ id: ct.id, type: 'content-viewer' });
    }
    return result;
  }, [activeStreams, contentTiles]);

  const cols = computeGridCols(tiles.length);
  const rows = Math.ceil(tiles.length / cols);

  const stripCount = hotspotTileId
    ? tiles.filter(t => t.id !== hotspotTileId).length
    : 0;
  const currentMode: LayoutMode = !hotspotTileId
    ? 'grid'
    : stripCount >= SIDE_BY_SIDE_THRESHOLD ? 'side-by-side' : 'top-bottom';

  const [fadeIn, setFadeIn] = useState(true);
  const prevModeRef = useRef<LayoutMode>(currentMode);

  useEffect(() => {
    if (prevModeRef.current !== currentMode) {
      setFadeIn(false);
      const timer = setTimeout(() => setFadeIn(true), 50);
      prevModeRef.current = currentMode;
      return () => clearTimeout(timer);
    }
  }, [currentMode]);

  const fadeStyle = { opacity: fadeIn ? 1 : 0, transition: 'opacity 0.15s ease' } as const;

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
    const activeStream = Object.entries(activeStreams).find(([, s]) => s.isActive);
    if (activeStream && hotspotTileId !== activeStream[0]) {
      setHotspot(activeStream[0]);
    } else if (!activeStream && hotspotTileId && !hotspotTileId.startsWith('content-')) {
      setHotspot(null);
    }
  }, [autoHotspot, activeStreams, hotspotTileId, setHotspot]);

  const renderTile = (tile: TileDescriptor) => {
    const ct = contentTiles.find(c => c.id === tile.id);
    const stream = tile.type === 'stream' ? activeStreams[tile.id] : undefined;
    return (
      <GridTile
        key={tile.id}
        type={tile.type === 'stream' ? 'agent-stream' : 'content-viewer'}
        tileId={tile.id}
        isHotspot={hotspotTileId === tile.id}
        onTileClick={handleTileClick}
        agentName={tile.actor}
        agentState={stream ? {
          messages: stream.messages,
          eventId: stream.eventId,
          isActive: stream.isActive,
        } : undefined}
        contentTile={ct}
        onCloseContent={closeContentTile}
      />
    );
  };

  useEffect(() => {
    if (hotspotTileId && !tiles.some(t => t.id === hotspotTileId)) {
      setHotspot(null);
    }
  }, [hotspotTileId, tiles, setHotspot]);

  if (tiles.length === 0) {
    return <EmptyState />;
  }

  if (hotspotTileId) {
    const hotspotTile = tiles.find(t => t.id === hotspotTileId);
    const stripTiles = tiles.filter(t => t.id !== hotspotTileId);

    if (!hotspotTile) return null;

    if (stripTiles.length >= SIDE_BY_SIDE_THRESHOLD) {
      const subCols = stripTiles.length <= 8 ? 2 : 3;
      const subRows = Math.ceil(stripTiles.length / subCols);
      return (
        <div className="h-full flex p-3 gap-3 overflow-hidden" style={fadeStyle}>
          <div className="overflow-hidden min-w-0 min-h-0" style={{ flex: '3 1 0%' }}>
            {renderTile(hotspotTile)}
          </div>
          <div className="overflow-hidden min-w-0 min-h-0" style={{
            flex: '2 1 0%',
            display: 'grid',
            gridTemplateColumns: `repeat(${subCols}, minmax(0, 1fr))`,
            gridTemplateRows: `repeat(${subRows}, minmax(0, 1fr))`,
            gap: 8,
          }}>
            {stripTiles.map(t => renderTile(t))}
          </div>
        </div>
      );
    }

    return (
      <div className="h-full flex flex-col p-3 gap-3 overflow-hidden" style={fadeStyle}>
        <div className="overflow-hidden min-w-0 min-h-0" style={{ flex: '2 1 0%' }}>
          {renderTile(hotspotTile)}
        </div>
        {stripTiles.length > 0 && (
          <div className="flex gap-3 overflow-hidden min-w-0 min-h-0" style={{ flex: '1 1 0%' }}>
            {stripTiles.map(t => (
              <div key={t.id} className="h-full overflow-hidden min-w-0" style={{ flex: '1 1 0%' }}>
                {renderTile(t)}
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="h-full p-3 overflow-hidden" style={fadeStyle}>
      <div style={{
        display: 'grid',
        gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))`,
        gridTemplateRows: `repeat(${rows}, minmax(0, 1fr))`,
        gap: 10,
        height: '100%',
      }}>
        {tiles.map(t => renderTile(t))}
      </div>
    </div>
  );
}
