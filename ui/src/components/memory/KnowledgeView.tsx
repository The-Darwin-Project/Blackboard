// BlackBoard/ui/src/components/memory/KnowledgeView.tsx
// @ai-rules:
// 1. [Pattern]: Table view of knowledge facts with create form, inline edit, and delete.
// 2. [Pattern]: 3 states: loading, empty, populated. Same pattern as LessonsView + NotebookPanel inline edit.
// 3. [Constraint]: Scope values match backend regex: convention | ownership | historical | relationship.
// 4. [Gotcha]: Identity fields (topic, scope) are immutable after creation -- PATCH only allows fact, source, confidence, valid_until.
import { useState, useCallback } from 'react';
import { Plus, Trash2, Library, Pencil, Check, X, AlertTriangle } from 'lucide-react';
import { useKnowledge, useCreateKnowledge, useUpdateKnowledge, useDeleteKnowledge } from '../../hooks/useMemory';
import type { KnowledgeScope } from '../../api/types';

const SCOPES: KnowledgeScope[] = ['convention', 'ownership', 'historical', 'relationship'];

const SCOPE_COLORS: Record<KnowledgeScope, string> = {
  convention: 'bg-emerald-500/20 text-emerald-300',
  ownership: 'bg-blue-500/20 text-blue-300',
  historical: 'bg-purple-500/20 text-purple-300',
  relationship: 'bg-amber-500/20 text-amber-300',
};

const SOURCE_COLORS: Record<string, string> = {
  admin: 'bg-cyan-500/20 text-cyan-300',
  field_notes: 'bg-orange-500/20 text-orange-300',
};

interface CreateForm {
  topic: string;
  fact: string;
  scope: KnowledgeScope;
  source: string;
  confidence: string;
}

const EMPTY_FORM: CreateForm = {
  topic: '',
  fact: '',
  scope: 'convention',
  source: 'admin',
  confidence: '1.0',
};

function ConfidenceBadge({ value }: { value: number }) {
  const color = value >= 0.7
    ? 'bg-emerald-500/20 text-emerald-300'
    : value >= 0.3
      ? 'bg-amber-500/20 text-amber-300'
      : 'bg-red-500/20 text-red-300';
  return (
    <span className={`inline-flex px-1.5 py-0.5 rounded text-[9px] font-mono font-medium ${color}`}>
      {value.toFixed(1)}
    </span>
  );
}

function StaleBadge({ validUntil }: { validUntil: number | null }) {
  if (!validUntil) return null;
  if (validUntil > Date.now() / 1000) return null;
  return (
    <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[9px] font-medium bg-red-500/20 text-red-300">
      <AlertTriangle size={9} /> STALE
    </span>
  );
}

export default function KnowledgeView() {
  const { data: knowledge, isLoading, isError } = useKnowledge();
  const createMutation = useCreateKnowledge();
  const updateMutation = useUpdateKnowledge();
  const deleteMutation = useDeleteKnowledge();

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<CreateForm>(EMPTY_FORM);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editFact, setEditFact] = useState('');

  const submitFact = () => {
    const trimmedTopic = form.topic.trim();
    const trimmedFact = form.fact.trim();
    if (!trimmedTopic || !trimmedFact) return;
    const confidence = parseFloat(form.confidence);
    if (isNaN(confidence) || confidence < 0 || confidence > 1) return;
    createMutation.mutate({
      topic: trimmedTopic,
      fact: trimmedFact,
      scope: form.scope,
      source: form.source.trim() || 'admin',
      confidence,
    }, {
      onSuccess: () => { setForm(EMPTY_FORM); setShowForm(false); },
    });
  };

  const startEdit = useCallback((knowledgeId: string, currentFact: string) => {
    setEditingId(knowledgeId);
    setEditFact(currentFact);
  }, []);

  const commitEdit = useCallback((knowledgeId: string) => {
    if (editFact.trim()) {
      updateMutation.mutate({ id: knowledgeId, updates: { fact: editFact.trim() } }, {
        onSuccess: () => setEditingId(prev => prev === knowledgeId ? null : prev),
      });
    } else {
      setEditingId(null);
    }
  }, [editFact, updateMutation]);

  if (isLoading) {
    return <div className="flex items-center justify-center h-full text-text-muted text-sm">Loading reference facts...</div>;
  }
  if (isError) {
    return <div className="flex items-center justify-center h-full text-red-400 text-sm">Failed to load reference facts.</div>;
  }

  const items = knowledge || [];

  return (
    <div className="h-full overflow-auto p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-text-primary">
          Reference Facts <span className="text-text-muted font-normal">({items.length})</span>
        </h2>
        <button onClick={() => setShowForm(!showForm)}
          className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded text-xs font-medium bg-accent/20 text-accent hover:bg-accent/30 transition-colors">
          <Plus size={12} /> New Fact
        </button>
      </div>

      {showForm && (
        <div className="mb-4 border border-border rounded-lg p-4 bg-bg-secondary space-y-2">
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="block text-[10px] text-text-muted mb-1">Topic</label>
              <input className="w-full bg-bg-primary border border-border rounded px-2 py-1.5 text-xs text-text-primary"
                value={form.topic} onChange={e => setForm({ ...form, topic: e.target.value })}
                placeholder="e.g. CNV nightly pipeline owner" maxLength={200} />
            </div>
            <div>
              <label className="block text-[10px] text-text-muted mb-1">Scope</label>
              <select className="w-full bg-bg-primary border border-border rounded px-2 py-1.5 text-xs text-text-primary"
                value={form.scope} onChange={e => setForm({ ...form, scope: e.target.value as KnowledgeScope })}>
                {SCOPES.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
          </div>
          <div>
            <label className="block text-[10px] text-text-muted mb-1">Fact</label>
            <textarea className="w-full bg-bg-primary border border-border rounded px-2 py-1.5 text-xs text-text-primary resize-none"
              rows={3} value={form.fact} onChange={e => setForm({ ...form, fact: e.target.value })}
              placeholder="The nightly pipeline is owned by the Release Engineering team..." maxLength={2000} />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="block text-[10px] text-text-muted mb-1">Source</label>
              <input className="w-full bg-bg-primary border border-border rounded px-2 py-1.5 text-xs text-text-primary"
                value={form.source} onChange={e => setForm({ ...form, source: e.target.value })}
                placeholder="admin" maxLength={200} />
            </div>
            <div>
              <label className="block text-[10px] text-text-muted mb-1">Confidence (0.0 - 1.0)</label>
              <input className="w-full bg-bg-primary border border-border rounded px-2 py-1.5 text-xs text-text-primary"
                type="number" min="0" max="1" step="0.1"
                value={form.confidence} onChange={e => setForm({ ...form, confidence: e.target.value })} />
            </div>
          </div>
          <div className="flex gap-2 pt-1 items-center">
            <button onClick={submitFact}
              disabled={!form.topic.trim() || !form.fact.trim() || createMutation.isPending}
              className="px-3 py-1.5 rounded text-xs font-medium bg-green-500/20 text-green-400 hover:bg-green-500/30 transition-colors disabled:opacity-50">
              {createMutation.isPending ? 'Storing...' : 'Store Fact'}
            </button>
            <button onClick={() => { setShowForm(false); setForm(EMPTY_FORM); }}
              className="px-3 py-1.5 rounded text-xs font-medium text-text-muted hover:bg-bg-tertiary transition-colors">
              Cancel
            </button>
            {createMutation.isError && (
              <span className="text-[10px] text-red-400">Failed to store fact. Try again.</span>
            )}
          </div>
        </div>
      )}

      {items.length === 0 && !showForm ? (
        <div className="flex flex-col items-center justify-center py-16 gap-2 text-text-muted">
          <Library size={24} className="opacity-50" />
          <span className="text-sm">No reference facts yet.</span>
          <span className="text-xs">Create one manually or let the Nightwatcher digest them from Field Notes.</span>
        </div>
      ) : (
        <div className="space-y-2">
          {items.map((point) => {
            const p = point.payload;
            const isExpanded = expanded === p.knowledge_id;
            const isEditing = editingId === p.knowledge_id;
            return (
              <div key={p.knowledge_id}
                className="group border border-border rounded-lg bg-bg-secondary hover:bg-bg-tertiary transition-colors cursor-pointer"
                onClick={() => { if (!isEditing) setExpanded(isExpanded ? null : p.knowledge_id); }}>
                <div className="px-4 py-3 flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5 mb-1.5 flex-wrap">
                      <span className={`inline-flex px-1.5 py-0.5 rounded text-[10px] font-medium ${SCOPE_COLORS[p.scope] ?? 'bg-gray-500/20 text-gray-300'}`}>
                        {p.scope}
                      </span>
                      <span className={`inline-flex px-1.5 py-0.5 rounded text-[10px] font-medium ${SOURCE_COLORS[p.source] ?? 'bg-gray-500/20 text-gray-300'}`}>
                        {p.source}
                      </span>
                      <ConfidenceBadge value={p.confidence} />
                      <StaleBadge validUntil={p.valid_until} />
                    </div>
                    <div className="text-xs font-medium text-text-primary">{p.topic}</div>
                    {isEditing ? (
                      <div className="mt-1.5 flex items-start gap-1" onClick={e => e.stopPropagation()}>
                        <textarea
                          className="flex-1 bg-bg-primary border border-border rounded px-2 py-1 text-xs text-text-primary resize-none focus:outline-none focus:border-accent"
                          value={editFact}
                          onChange={e => setEditFact(e.target.value)}
                          onKeyDown={e => {
                            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); commitEdit(p.knowledge_id); }
                            if (e.key === 'Escape') setEditingId(null);
                          }}
                          rows={3}
                          maxLength={2000}
                          autoFocus
                        />
                        <button onClick={() => commitEdit(p.knowledge_id)} className="p-1 text-emerald-400 hover:text-emerald-300" title="Save">
                          <Check size={14} />
                        </button>
                        <button onClick={() => setEditingId(null)} className="p-1 text-text-muted hover:text-text-secondary" title="Cancel">
                          <X size={14} />
                        </button>
                        {updateMutation.isError && (
                          <span className="text-[10px] text-red-400 ml-1">Save failed</span>
                        )}
                      </div>
                    ) : (
                      <div className="text-[11px] text-text-muted mt-1 line-clamp-2">{p.fact}</div>
                    )}
                  </div>
                  {!isEditing && (
                    <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0">
                      <button onClick={(e) => { e.stopPropagation(); startEdit(p.knowledge_id, p.fact); }}
                        className="p-1 text-text-muted hover:text-accent" title="Edit fact">
                        <Pencil size={12} />
                      </button>
                      <button onClick={(e) => {
                          e.stopPropagation();
                          if (window.confirm(`Delete fact "${p.topic}"? This cannot be undone.`)) {
                            deleteMutation.mutate(p.knowledge_id);
                          }
                        }}
                        className="p-1.5 rounded text-text-muted hover:text-red-400 hover:bg-red-400/10 transition-colors"
                        title="Delete fact">
                        <Trash2 size={12} />
                      </button>
                    </div>
                  )}
                </div>
                {isExpanded && !isEditing && (
                  <div className="px-4 pb-3 border-t border-border pt-3 space-y-2 text-xs">
                    <div><span className="text-text-muted">Full fact:</span> <span className="text-text-secondary">{p.fact}</span></div>
                    <div><span className="text-text-muted">Source:</span> <span className="text-text-secondary">{p.source}</span></div>
                    <div><span className="text-text-muted">Confidence:</span> <span className="text-text-secondary">{p.confidence}</span></div>
                    {p.valid_until && (
                      <div><span className="text-text-muted">Valid until:</span> <span className="text-text-secondary">{new Date(p.valid_until * 1000).toLocaleString()}</span></div>
                    )}
                    <div><span className="text-text-muted">Created:</span> <span className="text-text-secondary">{new Date(p.created_at * 1000).toLocaleString()}</span></div>
                    {p.updated_at !== p.created_at && (
                      <div><span className="text-text-muted">Updated:</span> <span className="text-text-secondary">{new Date(p.updated_at * 1000).toLocaleString()}</span></div>
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
