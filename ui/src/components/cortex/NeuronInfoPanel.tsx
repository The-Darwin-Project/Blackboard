// BlackBoard/ui/src/components/cortex/NeuronInfoPanel.tsx
// @ai-rules:
// 1. [Constraint]: All payload access via type-safe extractors (asString, asNumber, asStringArray) -- never raw `as` casts.
// 2. [Pattern]: Viewport-clamped fixed position via ref + useLayoutEffect (ContextMenu pattern).
// 3. [Gotcha]: Memory payloads are LLM-generated; render defensively with fallbacks.
// 4. [Pattern]: Type-specific rendering via chained if-else on neuron.type.
import { memo, useEffect, useLayoutEffect, useRef, useState, type FC, type ReactNode } from 'react';
import { X } from 'lucide-react';
import { NEURON_COLORS, AGENT_NEURON_COLORS, DOMAIN_NEURON_COLORS, SKILL_TAG_COLORS } from '../../constants/colors';
import { NEURON_DESCRIPTIONS } from './cortex-constants';
import type { Neuron } from './types';

const asString = (v: unknown): string => typeof v === 'string' ? v : '';
const asNumber = (v: unknown): number => typeof v === 'number' ? v : 0;
const asStringArray = (v: unknown): string[] => Array.isArray(v) ? v.filter(i => typeof i === 'string') : [];
const describeNeuron = (id: string) => NEURON_DESCRIPTIONS[id] ?? id.replace(/^(tool|phase|agent|domain):/, '').replace(/_/g, ' ');

const Hdr: FC<{ text: string }> = ({ text }) => (
  <div className="text-[10px] text-text-muted uppercase tracking-wider mb-1">{text}</div>
);

const Badge: FC<{ text: string; color?: string }> = ({ text, color }) => (
  <span className="inline-block px-1.5 py-0.5 rounded text-[10px] font-mono"
    style={{ background: `${color ?? '#334155'}25`, color: color ?? '#94a3b8' }}>{text}</span>
);

interface NeuronInfoPanelProps {
  neuron: Neuron;
  position: { x: number; y: number };
  onClose: () => void;
}

const NeuronInfoPanel: FC<NeuronInfoPanelProps> = ({ neuron, position, onClose }) => {
  const panelRef = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState(position);
  const p = neuron.payload;
  const typeColor = NEURON_COLORS[neuron.type] ?? '#6b7280';

  useLayoutEffect(() => {
    const el = panelRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    setPos({
      x: Math.max(4, Math.min(position.x, window.innerWidth - rect.width - 8)),
      y: Math.max(4, Math.min(position.y, window.innerHeight - rect.height - 8)),
    });
  }, [position]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  let body: ReactNode;
  if (neuron.type === 'lesson') {
    body = (<>
      {asString(p.title) && <div className="text-[12px] text-text-primary font-medium mb-1">{asString(p.title)}</div>}
      {asString(p.pattern) && <><Hdr text="Pattern" /><div className="text-[11px] text-text-secondary mb-2">{asString(p.pattern)}</div></>}
      {asString(p.anti_pattern) && <><Hdr text="Anti-pattern" /><div className="text-[11px] text-text-secondary mb-2">{asString(p.anti_pattern)}</div></>}
      <div className="flex flex-wrap gap-1 mb-1">{asStringArray(p.keywords).map(k => <Badge key={k} text={k} color={typeColor} />)}</div>
      <div className="flex items-center gap-2 text-[10px] text-text-muted">
        {asString(p.channel) && <Badge text={asString(p.channel)} />}
        <span>Verified: {asNumber(p.verification_count)}&times;</span>
      </div>
    </>);
  } else if (neuron.type === 'memory') {
    body = (<>
      {asString(p.symptom) && <><Hdr text="Symptom" /><div className="text-[11px] text-text-secondary mb-2">{asString(p.symptom)}</div></>}
      {asString(p.root_cause) && <><Hdr text="Root Cause" /><div className="text-[11px] text-text-secondary mb-2">{asString(p.root_cause)}</div></>}
      {asString(p.fix_action) && <><Hdr text="Fix" /><div className="text-[11px] text-text-secondary mb-2">{asString(p.fix_action)}</div></>}
      <div className="flex items-center gap-2 mt-1">
        {asString(p.service) && <Badge text={asString(p.service)} />}
        {asString(p.domain) && <Badge text={asString(p.domain)} color={typeColor} />}
      </div>
      {asString(p.outcome) && <div className="text-[10px] text-text-muted mt-1">Outcome: {asString(p.outcome)}</div>}
      {asNumber(p.duration_seconds) > 0 && <div className="text-[10px] text-text-muted">Duration: {Math.round(asNumber(p.duration_seconds) / 60)}min</div>}
    </>);
  } else if (neuron.type === 'knowledge') {
    const confidence = asNumber(p.confidence);
    body = (<>
      {asString(p.topic) && <div className="text-[12px] text-text-primary font-medium mb-1">{asString(p.topic)}</div>}
      {asString(p.fact) && <div className="text-[11px] text-text-secondary mb-2">{asString(p.fact)}</div>}
      {confidence > 0 && <div className="mb-2">
        <Hdr text={`Confidence ${Math.round(confidence * 100)}%`} />
        <div className="h-1.5 rounded-full bg-bg-tertiary overflow-hidden">
          <div className="h-full rounded-full" style={{ width: `${confidence * 100}%`, background: typeColor }} />
        </div>
      </div>}
      <div className="flex items-center gap-2 text-[10px] text-text-muted">
        {asString(p.scope) && <Badge text={asString(p.scope)} />}
        {asString(p.source) && <span>Source: {asString(p.source)}</span>}
      </div>
    </>);
  } else if (neuron.type === 'skill') {
    const tagType = asString(p.tag_type);
    const tagColor = SKILL_TAG_COLORS[tagType] ?? typeColor;
    const phaseFolder = asString(p.phase_folder);
    body = (<>
      {asString(p.label) && <div className="text-[12px] text-text-primary font-medium mb-1">{asString(p.label)}</div>}
      <div className="flex flex-wrap gap-1 mb-2">
        {tagType && <Badge text={tagType} color={tagColor} />}
        {phaseFolder && <Badge text={phaseFolder} />}
      </div>
      {neuron.heat > 0 && <div className="text-[10px] text-text-muted">Heat: {neuron.heat}</div>}
    </>);
  } else {
    const subName = neuron.id.replace(/^(tool|phase|agent|domain):/, '');
    const accent = neuron.type === 'agent' ? (AGENT_NEURON_COLORS[subName] ?? typeColor)
      : neuron.type === 'domain' ? (DOMAIN_NEURON_COLORS[subName] ?? typeColor)
      : typeColor;
    body = (<>
      {asString(p.label) && <div className="text-[12px] text-text-primary font-medium mb-1" style={{ color: accent }}>{asString(p.label)}</div>}
      {asString(p.group) && <div className="mb-1"><Badge text={asString(p.group)} /></div>}
      <div className="text-[11px] text-text-secondary">{describeNeuron(neuron.id)}</div>
    </>);
  }

  return (
    <div ref={panelRef} className="fixed z-50 bg-bg-primary border border-border rounded-lg shadow-xl"
      style={{ left: pos.x, top: pos.y, maxWidth: 320, borderTopColor: typeColor, borderTopWidth: 2 }}>
      <div className="flex items-center justify-between px-3 py-2 border-b border-border">
        <div className="flex items-center gap-2 min-w-0">
          <span className="flex-shrink-0 w-2 h-2 rounded-full" style={{ background: typeColor }} />
          <span className="text-[11px] font-semibold text-text-primary truncate">
            {asString(p.label) || asString(p.title) || asString(p.topic) || neuron.id}
          </span>
        </div>
        <button onClick={onClose} className="flex-shrink-0 text-text-muted hover:text-text-primary"><X size={14} /></button>
      </div>
      <div className="px-3 py-2 overflow-y-auto" style={{ maxHeight: 360 }}>{body}</div>
    </div>
  );
};

export default memo(NeuronInfoPanel);
