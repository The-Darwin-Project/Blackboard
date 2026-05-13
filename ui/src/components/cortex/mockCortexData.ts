// BlackBoard/ui/src/components/cortex/mockCortexData.ts
// @ai-rules:
// 1. [Constraint]: Dev-only mock data for Cortex EventDrillDown. NOT used in production.
// 2. [Pattern]: Shapes match types.ts interfaces exactly.
import type {
  Neuron, PulseBatch, CortexThinkingMessage,
  CortexShadowMessage, CortexStatusMessage, WhisperMessage,
} from './types';

export const MOCK_EVENT_ID = 'evt-mock-0001';

export const MOCK_NEURONS: Neuron[] = [
  { id: 'tool:classify_event', type: 'tool', heat: 3, payload: {} },
  { id: 'tool:refresh_gitlab_context', type: 'tool', heat: 5, payload: {} },
  { id: 'tool:defer_event', type: 'tool', heat: 4, payload: {} },
  { id: 'tool:set_phase', type: 'tool', heat: 3, payload: {} },
  { id: 'tool:consult_deep_memory', type: 'tool', heat: 2, payload: {} },
  { id: 'tool:respond_to_jarvis', type: 'tool', heat: 1, payload: {} },
  { id: 'phase:triage', type: 'phase', heat: 1, payload: {} },
  { id: 'phase:verify', type: 'phase', heat: 2, payload: {} },
  { id: 'phase:close', type: 'phase', heat: 1, payload: {} },
  { id: 'agent:developer', type: 'agent', heat: 1, payload: {} },
  { id: 'lesson:mock-001', type: 'lesson', heat: 2, payload: { title: 'Pipeline timeout recovery [experience]' } },
  { id: 'lesson:mock-002', type: 'lesson', heat: 1, payload: { title: 'Submodule update pattern [external]' } },
  { id: 'memory:mock-001', type: 'memory', heat: 3, payload: { service: 'kubevirt-plugin', root_cause: 'npm registry timeout' } },
];

const now = Date.now() / 1000;

export const MOCK_PULSE_BATCHES: PulseBatch[] = [
  { event_id: MOCK_EVENT_ID, turn: 1, timestamp: now - 600, event_elapsed_s: 0, pulses: [
    { neuron_id: 'tool:classify_event', neuron_type: 'tool', score: 1.0, injected: false },
  ]},
  { event_id: MOCK_EVENT_ID, turn: 2, timestamp: now - 540, event_elapsed_s: 60, pulses: [
    { neuron_id: 'phase:triage', neuron_type: 'phase', score: 1.0, injected: false },
  ]},
  { event_id: MOCK_EVENT_ID, turn: 3, timestamp: now - 480, event_elapsed_s: 120, pulses: [
    { neuron_id: 'tool:refresh_gitlab_context', neuron_type: 'tool', score: 1.0, injected: false },
  ]},
  { event_id: MOCK_EVENT_ID, turn: 4, timestamp: now - 420, event_elapsed_s: 180, pulses: [
    { neuron_id: 'tool:defer_event', neuron_type: 'tool', score: 1.0, injected: false },
  ]},
  { event_id: MOCK_EVENT_ID, turn: 5, timestamp: now - 300, event_elapsed_s: 300, pulses: [
    { neuron_id: 'tool:set_phase', neuron_type: 'tool', score: 1.0, injected: false },
    { neuron_id: 'phase:verify', neuron_type: 'phase', score: 1.0, injected: false },
  ]},
  { event_id: MOCK_EVENT_ID, turn: 6, timestamp: now - 240, event_elapsed_s: 360, pulses: [
    { neuron_id: 'tool:refresh_gitlab_context', neuron_type: 'tool', score: 1.0, injected: false },
  ]},
  { event_id: MOCK_EVENT_ID, turn: 7, timestamp: now - 180, event_elapsed_s: 420, pulses: [
    { neuron_id: 'tool:consult_deep_memory', neuron_type: 'tool', score: 1.0, injected: false },
    { neuron_id: 'lesson:mock-001', neuron_type: 'lesson', score: 0.71, injected: true },
    { neuron_id: 'memory:mock-001', neuron_type: 'memory', score: 0.81, injected: true },
  ]},
  { event_id: MOCK_EVENT_ID, turn: 8, timestamp: now - 120, event_elapsed_s: 480, pulses: [
    { neuron_id: 'tool:defer_event', neuron_type: 'tool', score: 1.0, injected: false },
  ]},
  { event_id: MOCK_EVENT_ID, turn: 9, timestamp: now - 60, event_elapsed_s: 540, pulses: [
    { neuron_id: 'tool:respond_to_jarvis', neuron_type: 'tool', score: 1.0, injected: false },
  ]},
  { event_id: MOCK_EVENT_ID, turn: 10, timestamp: now - 30, event_elapsed_s: 570, pulses: [
    { neuron_id: 'tool:defer_event', neuron_type: 'tool', score: 1.0, injected: false },
    { neuron_id: 'lesson:mock-002', neuron_type: 'lesson', score: 0.68, injected: true },
  ]},
];

export const MOCK_THINKING: CortexThinkingMessage[] = [
  { type: 'cortex_thinking', event_id: MOCK_EVENT_ID, content_type: 'tool_call', tool: 'get_pulse_history', args: { last_n_minutes: 10 } },
  { type: 'cortex_thinking', event_id: MOCK_EVENT_ID, content_type: 'tool_result', tool: 'get_pulse_history', result_preview: '10 batches, 23 neurons, top: tool:defer_event (4x)' },
  { type: 'cortex_thinking', event_id: MOCK_EVENT_ID, content_type: 'tool_call', tool: 'inject_system_insight', args: { event_id: MOCK_EVENT_ID, insight: 'The event has deferred three times with the same reason. Consider refreshing context.', severity: 'nudge' } },
  { type: 'cortex_thinking', event_id: MOCK_EVENT_ID, content_type: 'tool_result', tool: 'inject_system_insight', result_preview: 'Insight delivered to evt-mock-0001' },
  { type: 'cortex_thinking', event_id: MOCK_EVENT_ID, content_type: 'text', text: '[FRIDAY] The pipeline has been running for about 15 minutes. Deep memory shows 30-40min typical. I disagree with the stalled monitor assessment.' },
];

export const MOCK_SHADOW: CortexShadowMessage[] = [
  {
    type: 'cortex_shadow', event_id: MOCK_EVENT_ID, tool: 'inject_system_insight',
    args: { insight: 'The event has deferred three times with the same reason: pipeline still running. Consider checking for actual progress.', severity: 'nudge' },
    timestamp: now - 180, shadow: false, delivered: true,
  } as CortexShadowMessage & { shadow: boolean; delivered: boolean },
  {
    type: 'cortex_shadow', event_id: MOCK_EVENT_ID, tool: 'surface_context',
    args: { context: 'Deep memory shows this pipeline typically takes 20-30 minutes. Event age is 15 minutes — within expected window.' },
    timestamp: now - 300, shadow: true, delivered: false,
  } as CortexShadowMessage & { shadow: boolean; delivered: boolean },
];

export const MOCK_WHISPERS: WhisperMessage[] = [
  { type: 'whisper', event_id: MOCK_EVENT_ID, severity: 'nudge', insight: 'The event has deferred three times. Consider refreshing context and evaluating if the pipeline is truly progressing.', timestamp: now - 120 },
];

export const MOCK_CORTEX_STATUS: CortexStatusMessage = {
  type: 'cortex_status',
  status: 'watching',
  model: 'gemini-live-2.5-flash',
  shadow: false,
  timestamp: now,
};
