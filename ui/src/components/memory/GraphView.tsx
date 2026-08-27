// BlackBoard/ui/src/components/memory/GraphView.tsx
// @ai-rules:
// 1. [Pattern]: Table of KG service entities (getKGServices) + click-to-expand relationships
//    (getKGServiceDetail), header stats (getKGStats). Reuses hooks from useCortexData.ts --
//    the SAME KG hooks CortexPage uses for the ring's service nodes, not a parallel fetch path.
// 2. [Constraint]: Read-only. Does NOT raise Cortex's 15-node service cap on the ring -- this
//    tab is the full-corpus complement to that intentionally-capped layout sample.
// 3. [Pattern]: Dex-unmounted deployments fail-open to [] (KG REST already returns [] when the
//    store is unavailable, per src/routes/knowledge_graph_api.py) -- rendered as an empty state,
//    never a crash.
import { useState } from 'react';
import { Network, ChevronDown, ChevronRight, Share2 } from 'lucide-react';
import { useKGServices, useKGServiceDetail, useKGStats } from '../../hooks/useCortexData';

export default function GraphView() {
  const { data: services, isLoading, isError } = useKGServices();
  const { data: stats } = useKGStats();
  const [expanded, setExpanded] = useState<string | null>(null);
  const { data: detail } = useKGServiceDetail(expanded);

  if (isLoading) {
    return <div className="flex items-center justify-center h-full text-text-muted text-sm">Loading knowledge graph...</div>;
  }
  if (isError) {
    return <div className="flex items-center justify-center h-full text-red-400 text-sm">Failed to load knowledge graph.</div>;
  }

  const items = services ?? [];

  return (
    <div className="h-full overflow-auto p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-text-primary">
          Service Graph <span className="text-text-muted font-normal">({items.length} services)</span>
        </h2>
        {stats && (
          <div className="flex items-center gap-3 text-[10px] text-text-muted">
            {Object.entries(stats.relationships).map(([relType, count]) => (
              <span key={relType} className="inline-flex items-center gap-1">
                <Share2 size={9} /> {relType}: {count}
              </span>
            ))}
          </div>
        )}
      </div>

      {items.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 gap-2 text-text-muted">
          <Network size={24} className="opacity-50" />
          <span className="text-sm">No service relationships discovered yet.</span>
          <span className="text-xs">The knowledge graph fills in as events archive with extracted entities.</span>
        </div>
      ) : (
        <div className="space-y-2">
          {items.map(svc => {
            const isExpanded = expanded === svc.entity_id;
            const name = svc.entity_id.replace(/^service:/, '');
            return (
              <div key={svc.entity_id}
                className="border border-border rounded-lg bg-bg-secondary hover:bg-bg-tertiary transition-colors cursor-pointer"
                onClick={() => setExpanded(isExpanded ? null : svc.entity_id)}>
                <div className="px-4 py-3 flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2 min-w-0">
                    {isExpanded ? <ChevronDown size={12} className="text-text-muted flex-shrink-0" /> : <ChevronRight size={12} className="text-text-muted flex-shrink-0" />}
                    <span className="text-xs font-medium text-text-primary truncate">{name}</span>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0 text-[10px] text-text-muted">
                    <span>{svc.relationship_count} rel{svc.relationship_count !== 1 ? 's' : ''}</span>
                    <span>{svc.last_seen ? new Date(svc.last_seen).toLocaleDateString() : '?'}</span>
                  </div>
                </div>
                {isExpanded && (
                  <div className="px-4 pb-3 border-t border-border pt-3 space-y-2 text-xs">
                    {Object.entries(svc.properties).length > 0 && (
                      <div className="flex flex-wrap gap-1 mb-1">
                        {Object.entries(svc.properties).map(([k, v]) => (
                          <span key={k} className="px-1.5 py-0.5 rounded text-[9px] font-mono bg-accent/10 text-accent">{k}={v}</span>
                        ))}
                      </div>
                    )}
                    {!detail && <div className="text-[10px] text-text-muted italic">Loading relationships...</div>}
                    {detail && detail.relationships.length === 0 && (
                      <div className="text-[10px] text-text-muted">No known relationships.</div>
                    )}
                    {detail && detail.relationships.length > 0 && (
                      <div className="space-y-1">
                        {detail.relationships.map((rel, idx) => (
                          <div key={idx} className="flex items-center gap-1.5 text-[11px] text-text-secondary">
                            <span className="px-1.5 py-0.5 rounded text-[9px] font-mono bg-bg-tertiary text-text-muted">
                              {rel.direction === 'outgoing' ? '→' : '←'} {rel.rel_type}
                            </span>
                            <span>{rel.entity_type}: {rel.entity_id}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
