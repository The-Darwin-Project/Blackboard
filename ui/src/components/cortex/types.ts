// BlackBoard/ui/src/components/cortex/types.ts
// @ai-rules:
// 1. [Constraint]: All interfaces use snake_case to match Python API (PulseBatch, Pulse, CognitiveGraphResponse).
// 2. [Pattern]: neuron_type union matches backend PulsePort neuron categories exactly.
// 3. [Gotcha]: Executive hemisphere neurons (tool/phase/agent) have score=1.0 always; knowledge neurons have variable scores.
// 4. [Pattern]: event_source typed via shared EventSource from api/types.ts. Optional -- None when source unavailable.

import type { EventSource } from '../../api/types';

export interface Pulse {
  neuron_id: string;
  neuron_type: 'lesson' | 'memory' | 'tool' | 'phase' | 'agent';
  score: number;
  injected: boolean;
}

export interface PulseBatch {
  event_id: string;
  pulses: Pulse[];
  turn: number;
  event_elapsed_s: number;
  timestamp: number;
  reasoning?: string;
  is_defer_wake?: boolean;
  event_status?: string;
  event_source?: EventSource;
  _stream_id?: string;
}

export interface Neuron {
  id: string;
  type: 'lesson' | 'memory' | 'tool' | 'phase' | 'agent';
  heat: number;
  payload: Record<string, unknown>;
}

export interface CognitiveGraphResponse {
  neurons: Neuron[];
  total: number;
}

export interface CortexThinkingMessage {
  type: 'cortex_thinking';
  event_id: string;
  content_type: 'text' | 'tool_call' | 'tool_result';
  text?: string;
  tool?: string;
  args?: Record<string, unknown>;
  result_preview?: string;
  delivered?: boolean;
  timestamp?: number;
}

export type MessageClass = 'thinking' | 'peer_input' | 'investigation' | 'delivered' | 'tool_result';

export interface CortexStatusMessage {
  type: 'cortex_status';
  status: 'watching' | 'disconnected';
  model: string;
  shadow: boolean;
  timestamp: number;
}

export interface CortexHeartbeatMessage {
  type: 'cortex_heartbeat';
  heartbeat: 'spike' | 'wave';
  timestamp: number;
}

export interface CortexShadowMessage {
  type: 'cortex_shadow';
  event_id: string;
  tool: string;
  args: Record<string, unknown>;
  timestamp: number;
  shadow?: boolean;
  delivered?: boolean;
}

export interface WhisperMessage {
  type: 'whisper';
  event_id: string;
  severity: 'nudge' | 'course_correct' | 'alert';
  insight: string;
  timestamp: number;
}

export type FrictionPattern = 'spiral' | 'plateau' | 'agent_churn';

export interface FrictionIndicator {
  pattern: FrictionPattern;
  label: string;
  color: string;
}

/** Neuron visual config derived from neuron type */
export interface NeuronVisual {
  color: string;
  size: number;
  label: string;
}
