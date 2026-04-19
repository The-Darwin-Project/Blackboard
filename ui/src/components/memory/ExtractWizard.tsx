// BlackBoard/ui/src/components/memory/ExtractWizard.tsx
// @ai-rules:
// 1. [Pattern]: 3-step wizard: Input -> Review -> Confirm. State machine via step number.
// 2. [Pattern]: Step 1 accepts paste, file upload, event selection, context notes.
// 3. [Pattern]: Step 2 shows editable cards with include/exclude toggles.
// 4. [Pattern]: Step 3 applies selected items and shows summary.
import { useState, useCallback } from 'react';
import { Upload, Loader2, Check, X, Download, ArrowLeft } from 'lucide-react';
import { useExtractLessons, useApplyLessons, useMemories } from '../../hooks/useMemory';
import type { ExtractedLesson, ExtractedCorrection } from '../../api/client';

type Step = 1 | 2 | 3;

interface ReviewItem<T> {
  data: T;
  included: boolean;
}

export default function ExtractWizard() {
  const [step, setStep] = useState<Step>(1);
  const [document, setDocument] = useState('');
  const [selectedEvents, setSelectedEvents] = useState<string[]>([]);
  const [contextNotes, setContextNotes] = useState('');
  const [lessons, setLessons] = useState<ReviewItem<ExtractedLesson>[]>([]);
  const [corrections, setCorrections] = useState<ReviewItem<ExtractedCorrection>[]>([]);
  const [result, setResult] = useState<{ stored_lessons: number; applied_corrections: number } | null>(null);

  const extractMutation = useExtractLessons();
  const applyMutation = useApplyLessons();
  const { data: memories } = useMemories();

  const handleFileUpload = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => setDocument(ev.target?.result as string || '');
    reader.readAsText(file);
  }, []);

  const handleExtract = () => {
    extractMutation.mutate(
      { document, event_ids: selectedEvents, context_notes: contextNotes },
      {
        onSuccess: (data) => {
          setLessons(data.lessons.map(l => ({ data: l, included: true })));
          setCorrections(data.corrections.map(c => ({ data: c, included: true })));
          setStep(2);
        },
      },
    );
  };

  const handleApply = () => {
    applyMutation.mutate(
      {
        lessons: lessons.filter(l => l.included).map(l => l.data),
        corrections: corrections.filter(c => c.included).map(c => c.data),
      },
      { onSuccess: (r) => { setResult(r); setStep(3); } },
    );
  };

  const toggleEvent = (eid: string) => {
    setSelectedEvents(prev => prev.includes(eid) ? prev.filter(e => e !== eid) : [...prev, eid]);
  };

  // --- STEP 1: Input ---
  if (step === 1) {
    return (
      <div className="h-full overflow-auto p-4 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-text-primary">Extract Lessons from Document</h2>
          <a href="/lessons-learned-template.md" download
            className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded text-xs font-medium text-text-muted hover:text-text-secondary hover:bg-bg-tertiary transition-colors">
            <Download size={12} /> Template
          </a>
        </div>

        <div>
          <label className="block text-[10px] text-text-muted mb-1">Paste Document (markdown)</label>
          <textarea className="w-full bg-bg-primary border border-border rounded px-3 py-2 text-xs text-text-primary resize-none font-mono"
            rows={10} value={document} onChange={e => setDocument(e.target.value)}
            placeholder="Paste your Lessons Learned document here..." />
        </div>

        <div>
          <label className="block text-[10px] text-text-muted mb-1">Or Upload File (.md, .txt)</label>
          <label className="flex items-center gap-2 px-3 py-2 border border-dashed border-border rounded cursor-pointer hover:bg-bg-tertiary transition-colors">
            <Upload size={14} className="text-text-muted" />
            <span className="text-xs text-text-muted">Choose file...</span>
            <input type="file" accept=".md,.txt,.markdown" className="hidden" onChange={handleFileUpload} />
          </label>
        </div>

        {memories && memories.length > 0 && (
          <div>
            <label className="block text-[10px] text-text-muted mb-1">Cross-reference Events (optional, from Deep Memory)</label>
            <div className="max-h-32 overflow-auto border border-border rounded p-2 space-y-1">
              {memories.slice(0, 50).map(mem => {
                const p = mem.payload as Record<string, unknown>;
                const eid = (p.event_id as string) || mem.id;
                return (
                  <label key={eid} className="flex items-center gap-2 text-xs cursor-pointer hover:bg-bg-tertiary rounded px-1 py-0.5">
                    <input type="checkbox" checked={selectedEvents.includes(eid)}
                      onChange={() => toggleEvent(eid)} className="rounded" />
                    <span className="font-mono text-[10px] text-text-muted">{eid.slice(0, 16)}</span>
                    <span className="text-text-secondary truncate">{(p.service as string) || '?'} -- {((p.symptom as string) || '').slice(0, 60)}</span>
                  </label>
                );
              })}
            </div>
          </div>
        )}

        <div>
          <label className="block text-[10px] text-text-muted mb-1">Additional Context (optional)</label>
          <input className="w-full bg-bg-primary border border-border rounded px-3 py-1.5 text-xs text-text-primary"
            value={contextNotes} onChange={e => setContextNotes(e.target.value)}
            placeholder="Focus on pipeline failure classification bias..." />
        </div>

        <button onClick={handleExtract}
          disabled={!document.trim() || extractMutation.isPending}
          className="inline-flex items-center gap-2 px-4 py-2 rounded text-xs font-medium bg-accent/20 text-accent hover:bg-accent/30 transition-colors disabled:opacity-50">
          {extractMutation.isPending ? <><Loader2 size={12} className="animate-spin" /> Claude is analyzing...</> : 'Extract Lessons'}
        </button>
        {extractMutation.isError && (
          <div className="text-xs text-red-400">Extraction failed: {(extractMutation.error as Error).message}</div>
        )}
      </div>
    );
  }

  // --- STEP 2: Review ---
  if (step === 2) {
    return (
      <div className="h-full overflow-auto p-4 space-y-4">
        <div className="flex items-center justify-between">
          <button onClick={() => setStep(1)}
            className="inline-flex items-center gap-1 text-xs text-text-muted hover:text-text-secondary">
            <ArrowLeft size={12} /> Back to input
          </button>
          <h2 className="text-sm font-semibold text-text-primary">Review Extracted Items</h2>
        </div>

        {lessons.length > 0 && (
          <div>
            <h3 className="text-xs font-semibold text-text-primary mb-2">
              Lessons ({lessons.filter(l => l.included).length}/{lessons.length} selected)
            </h3>
            <div className="space-y-2">
              {lessons.map((item, i) => (
                <div key={item.data.title || `lesson-${i}`} className={`border rounded-lg p-3 transition-colors ${
                  item.included ? 'border-accent/30 bg-accent/5' : 'border-border bg-bg-secondary opacity-60'
                }`}>
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <input className="w-full bg-transparent text-xs font-medium text-text-primary border-none outline-none"
                      value={item.data.title}
                      onChange={e => { const n = [...lessons]; n[i] = { ...item, data: { ...item.data, title: e.target.value } }; setLessons(n); }} />
                    <button onClick={() => { const n = [...lessons]; n[i] = { ...item, included: !item.included }; setLessons(n); }}
                      className={`p-1 rounded ${item.included ? 'text-green-400 hover:text-red-400' : 'text-text-muted hover:text-green-400'}`}>
                      {item.included ? <Check size={14} /> : <X size={14} />}
                    </button>
                  </div>
                  <textarea className="w-full bg-bg-primary/50 rounded px-2 py-1 text-[11px] text-text-secondary resize-none border border-border/50"
                    rows={3} value={item.data.pattern}
                    onChange={e => { const n = [...lessons]; n[i] = { ...item, data: { ...item.data, pattern: e.target.value } }; setLessons(n); }} />
                  {item.data.keywords && item.data.keywords.length > 0 && (
                    <div className="flex gap-1 mt-1.5 flex-wrap">
                      {item.data.keywords.map(kw => (
                        <span key={kw} className="px-1.5 py-0.5 rounded text-[9px] font-medium bg-accent/10 text-accent">{kw}</span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {corrections.length > 0 && (
          <div>
            <h3 className="text-xs font-semibold text-text-primary mb-2">
              Corrections ({corrections.filter(c => c.included).length}/{corrections.length} selected)
            </h3>
            <div className="space-y-2">
              {corrections.map((item, i) => (
                <div key={item.data.event_id || `correction-${i}`} className={`border rounded-lg p-3 transition-colors ${
                  item.included ? 'border-green-400/30 bg-green-400/5' : 'border-border bg-bg-secondary opacity-60'
                }`}>
                  <div className="flex items-start justify-between gap-2">
                    <span className="font-mono text-[10px] text-text-muted">{item.data.event_id}</span>
                    <button onClick={() => { const n = [...corrections]; n[i] = { ...item, included: !item.included }; setCorrections(n); }}
                      className={`p-1 rounded ${item.included ? 'text-green-400 hover:text-red-400' : 'text-text-muted hover:text-green-400'}`}>
                      {item.included ? <Check size={14} /> : <X size={14} />}
                    </button>
                  </div>
                  <div className="mt-1 text-[11px]">
                    <div className="text-text-muted line-through">{(item.data.current_root_cause || '').slice(0, 100)}</div>
                    <textarea className="w-full mt-1 bg-bg-primary/50 rounded px-2 py-1 text-text-secondary resize-none border border-border/50"
                      rows={2} value={item.data.corrected_root_cause}
                      onChange={e => { const n = [...corrections]; n[i] = { ...item, data: { ...item.data, corrected_root_cause: e.target.value } }; setCorrections(n); }} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        <button onClick={handleApply} disabled={applyMutation.isPending}
          className="inline-flex items-center gap-2 px-4 py-2 rounded text-xs font-medium bg-green-500/20 text-green-400 hover:bg-green-500/30 transition-colors disabled:opacity-50">
          {applyMutation.isPending ? <><Loader2 size={12} className="animate-spin" /> Applying...</> : `Apply ${lessons.filter(l => l.included).length} Lessons + ${corrections.filter(c => c.included).length} Corrections`}
        </button>
      </div>
    );
  }

  // --- STEP 3: Confirm ---
  return (
    <div className="flex flex-col items-center justify-center h-full gap-4 text-text-primary">
      <div className="w-12 h-12 rounded-full bg-green-500/20 flex items-center justify-center">
        <Check size={24} className="text-green-400" />
      </div>
      <h2 className="text-sm font-semibold">Applied Successfully</h2>
      {result && (
        <div className="text-xs text-text-muted text-center">
          <div>{result.stored_lessons} lesson{result.stored_lessons !== 1 ? 's' : ''} stored</div>
          <div>{result.applied_corrections} correction{result.applied_corrections !== 1 ? 's' : ''} applied</div>
        </div>
      )}
      <button onClick={() => { setStep(1); setDocument(''); setSelectedEvents([]); setContextNotes(''); setLessons([]); setCorrections([]); setResult(null); }}
        className="px-4 py-2 rounded text-xs font-medium bg-accent/20 text-accent hover:bg-accent/30 transition-colors">
        Extract Another
      </button>
    </div>
  );
}
