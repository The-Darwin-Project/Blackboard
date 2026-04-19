// BlackBoard/ui/src/components/memory/MemoriesView.tsx
// @ai-rules:
// 1. [Pattern]: Table view of archived event memories with inline correction form.
// 2. [Pattern]: 3 states: loading, empty, populated. Same pattern as IncidentsPage.
// 3. [Pattern]: Click row to expand detail + correction form. Submit invalidates query cache.
import { useState } from 'react';
import { CheckCircle, ChevronDown, ChevronRight, Send } from 'lucide-react';
import { useMemories, useCorrectMemory } from '../../hooks/useMemory';

interface CorrectionForm {
  eventId: string;
  rootCause: string;
  fixAction: string;
  note: string;
}

export default function MemoriesView() {
  const { data: memories, isLoading, isError } = useMemories();
  const correctMutation = useCorrectMemory();
  const [expanded, setExpanded] = useState<string | null>(null);
  const [form, setForm] = useState<CorrectionForm | null>(null);

  if (isLoading) {
    return <div className="flex items-center justify-center h-full text-text-muted text-sm">Loading memories...</div>;
  }
  if (isError) {
    return <div className="flex items-center justify-center h-full text-red-400 text-sm">Failed to load memories.</div>;
  }
  if (!memories || memories.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-2 text-text-muted">
        <span className="text-sm">No archived memories yet.</span>
        <span className="text-xs">Memories are created when the Brain closes events.</span>
      </div>
    );
  }

  const toggle = (id: string) => {
    if (expanded === id) {
      setExpanded(null);
      setForm(null);
    } else {
      setExpanded(id);
      setForm(null);
    }
  };

  const startCorrection = (eventId: string, currentRoot: string, currentFix: string) => {
    setForm({ eventId, rootCause: currentRoot, fixAction: currentFix, note: '' });
  };

  const submitCorrection = () => {
    if (!form) return;
    correctMutation.mutate({
      event_id: form.eventId,
      corrected_root_cause: form.rootCause,
      corrected_fix_action: form.fixAction,
      correction_note: form.note,
    }, {
      onSuccess: () => { setForm(null); setExpanded(null); },
    });
  };

  return (
    <div className="h-full overflow-auto p-4">
      <div className="mb-3">
        <h2 className="text-sm font-semibold text-text-primary">
          Event Memories <span className="text-text-muted font-normal">({memories.length})</span>
        </h2>
      </div>
      <div className="border border-border rounded-lg overflow-hidden">
        <table className="w-full text-xs" style={{ tableLayout: 'auto' }}>
          <thead>
            <tr className="bg-bg-secondary border-b border-border">
              <th className="px-3 py-2 text-left font-medium text-text-muted w-6" />
              <th className="px-3 py-2 text-left font-medium text-text-muted whitespace-nowrap">Event</th>
              <th className="px-3 py-2 text-left font-medium text-text-muted whitespace-nowrap">Service</th>
              <th className="px-3 py-2 text-left font-medium text-text-muted">Pattern</th>
              <th className="px-3 py-2 text-left font-medium text-text-muted">Root Cause</th>
              <th className="px-3 py-2 text-left font-medium text-text-muted whitespace-nowrap">Status</th>
            </tr>
          </thead>
          <tbody>
            {memories.map((m) => {
              const p = m.payload as Record<string, unknown>;
              const eid = (p.event_id as string) || m.id;
              const isExpanded = expanded === eid;
              const corrected = !!p.corrected;
              return (
                <tr key={m.id}
                  className="border-b border-border hover:bg-bg-tertiary cursor-pointer transition-colors align-top"
                  onClick={() => toggle(eid)}>
                  <td className="px-3 py-2 text-text-muted">
                    {isExpanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                  </td>
                  <td className="px-3 py-2 whitespace-nowrap text-text-secondary font-mono text-[10px]">
                    {eid.slice(0, 16)}
                  </td>
                  <td className="px-3 py-2 whitespace-nowrap text-text-secondary">{p.service as string || '?'}</td>
                  <td className="px-3 py-2 text-text-secondary break-words max-w-[200px]">
                    {((p.symptom as string) || '?').slice(0, 80)}
                  </td>
                  <td className="px-3 py-2 text-text-secondary break-words max-w-[200px]">
                    {((p.root_cause as string) || '?').slice(0, 80)}
                  </td>
                  <td className="px-3 py-2 whitespace-nowrap">
                    {corrected ? (
                      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium text-green-400 bg-green-400/10">
                        <CheckCircle size={10} /> corrected
                      </span>
                    ) : (
                      <span className="text-text-muted text-[10px]">original</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {expanded && (() => {
        const mem = memories.find(m => ((m.payload as Record<string, unknown>).event_id as string || m.id) === expanded);
        if (!mem) return null;
        const p = mem.payload as Record<string, unknown>;
        return (
          <div className="mt-3 border border-border rounded-lg p-4 bg-bg-secondary">
            <div className="grid grid-cols-2 gap-3 text-xs mb-3">
              <div><span className="text-text-muted">Event:</span> <span className="text-text-primary font-mono">{p.event_id as string}</span></div>
              <div><span className="text-text-muted">Service:</span> <span className="text-text-primary">{p.service as string}</span></div>
              <div><span className="text-text-muted">Domain:</span> <span className="text-text-primary">{(p.brain_domain || p.domain) as string}</span></div>
              <div><span className="text-text-muted">Outcome:</span> <span className="text-text-primary">{p.outcome as string}</span></div>
              <div className="col-span-2"><span className="text-text-muted">Pattern:</span> <span className="text-text-primary">{p.symptom as string}</span></div>
              <div className="col-span-2"><span className="text-text-muted">Root cause:</span> <span className="text-text-primary">{p.root_cause as string}</span></div>
              <div className="col-span-2"><span className="text-text-muted">Fix:</span> <span className="text-text-primary">{p.fix_action as string}</span></div>
              {typeof p.correction_note === 'string' && p.correction_note && (
                <div className="col-span-2"><span className="text-text-muted">Correction note:</span> <span className="text-green-400">{p.correction_note}</span></div>
              )}
            </div>

            {!form ? (
              <button onClick={(e) => { e.stopPropagation(); startCorrection(expanded, p.root_cause as string || '', p.fix_action as string || ''); }}
                className="px-3 py-1.5 rounded text-xs font-medium bg-accent/20 text-accent hover:bg-accent/30 transition-colors">
                Correct Memory
              </button>
            ) : (
              <div className="space-y-2 border-t border-border pt-3 mt-2" onClick={e => e.stopPropagation()}>
                <div>
                  <label className="block text-[10px] text-text-muted mb-1">Corrected Root Cause</label>
                  <textarea className="w-full bg-bg-primary border border-border rounded px-2 py-1.5 text-xs text-text-primary resize-none"
                    rows={2} value={form.rootCause} onChange={e => setForm({ ...form, rootCause: e.target.value })} />
                </div>
                <div>
                  <label className="block text-[10px] text-text-muted mb-1">Corrected Fix Action</label>
                  <textarea className="w-full bg-bg-primary border border-border rounded px-2 py-1.5 text-xs text-text-primary resize-none"
                    rows={2} value={form.fixAction} onChange={e => setForm({ ...form, fixAction: e.target.value })} />
                </div>
                <div>
                  <label className="block text-[10px] text-text-muted mb-1">Correction Note (optional)</label>
                  <input className="w-full bg-bg-primary border border-border rounded px-2 py-1.5 text-xs text-text-primary"
                    value={form.note} onChange={e => setForm({ ...form, note: e.target.value })} placeholder="Why is this being corrected?" />
                </div>
                <div className="flex gap-2">
                  <button onClick={submitCorrection} disabled={correctMutation.isPending}
                    className="inline-flex items-center gap-1 px-3 py-1.5 rounded text-xs font-medium bg-green-500/20 text-green-400 hover:bg-green-500/30 transition-colors disabled:opacity-50">
                    <Send size={10} /> {correctMutation.isPending ? 'Saving...' : 'Apply Correction'}
                  </button>
                  <button onClick={() => setForm(null)}
                    className="px-3 py-1.5 rounded text-xs font-medium text-text-muted hover:bg-bg-tertiary transition-colors">
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>
        );
      })()}
    </div>
  );
}
