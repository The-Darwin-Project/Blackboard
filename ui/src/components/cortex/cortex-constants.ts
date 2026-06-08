// BlackBoard/ui/src/components/cortex/cortex-constants.ts
// @ai-rules:
// 1. [Constraint]: Executive hemisphere neurons are hardcoded -- they mirror Brain tool declarations.
// 2. [Pattern]: Tool groups map to functional clusters in the Brain's tool dispatcher.
// 3. [Gotcha]: Keep in sync with Brain's function tool list in brain.py.
// 4. [Pattern]: PHASE_TOOL_PRIORITY mirrors Brain's _phase_tool_priority in brain.py.
import type { Neuron } from './types';

export const TOOL_GROUPS: Record<string, string[]> = {
  observation: ['lookup_service', 'lookup_journal', 'consult_deep_memory', 'refresh_gitlab_context', 'refresh_kargo_context'],
  classification: ['classify_event', 'set_phase'],
  routing: ['select_agent', 'create_plan', 'message_agent', 'reply_to_agent'],
  lifecycle: ['defer_event', 'wait_for_user', 'close_event'],
  communication: ['notify_user_slack', 'notify_gitlab_result', 'report_incident', 'get_plan_progress'],
};

export const PHASES = ['triage', 'dispatch', 'verify', 'escalate', 'close'];
export const AGENTS = ['architect', 'sysadmin', 'developer', 'qe', 'security_analyst'];

const PHASE_TOOL_PRIORITY: Record<string, string[]> = {
  triage: ['refresh_gitlab_context', 'refresh_kargo_context'],
  dispatch: ['select_agent', 'create_plan', 'message_agent', 'reply_to_agent', 'defer_event', 'comment_jira_issue', 'transition_jira_issue'],
  verify: ['refresh_gitlab_context', 'refresh_kargo_context', 'get_plan_progress', 'defer_event'],
  escalate: ['report_incident', 'notify_user_slack', 'notify_gitlab_result', 'close_event', 'defer_event'],
  close: ['close_event', 'notify_gitlab_result', 'notify_user_slack', 'post_sticky_note', 'hold_watch'],
};

export function getExecutiveNeurons(): Neuron[] {
  const neurons: Neuron[] = [];

  for (const [group, tools] of Object.entries(TOOL_GROUPS)) {
    for (const tool of tools) {
      neurons.push({
        id: `tool:${tool}`,
        type: 'tool',
        heat: 0,
        payload: { group, label: tool.replace(/_/g, ' ') },
      });
    }
  }

  for (const phase of PHASES) {
    neurons.push({
      id: `phase:${phase}`,
      type: 'phase',
      heat: 0,
      payload: { label: phase },
    });
  }

  for (const agent of AGENTS) {
    neurons.push({
      id: `agent:${agent}`,
      type: 'agent',
      heat: 0,
      payload: { label: agent },
    });
  }

  return neurons;
}

/** X position bias: knowledge left, events center, executive right. Wide separation prevents mixing. */
export const HEMISPHERE_X = {
  knowledge: -500,
  events: 0,
  executive: 500,
} as const;

export const TOOL_GROUP_Y: Record<string, number> = {
  observation: -200,
  classification: -80,
  routing: 40,
  lifecycle: 160,
  communication: 280,
};

/** Deterministic color from event ID hash */
export function eventColor(eventId: string): string {
  let hash = 0;
  for (let i = 0; i < eventId.length; i++) {
    hash = ((hash << 5) - hash + eventId.charCodeAt(i)) | 0;
  }
  const h = Math.abs(hash) % 360;
  // Convert HSL to hex -- Sigma WebGL only understands hex colors
  const s = 0.7, l = 0.6;
  const a = s * Math.min(l, 1 - l);
  const f = (n: number) => {
    const k = (n + h / 30) % 12;
    const c = l - a * Math.max(Math.min(k - 3, 9 - k, 1), -1);
    return Math.round(255 * c).toString(16).padStart(2, '0');
  };
  return `#${f(0)}${f(8)}${f(4)}`;
}

interface StructuralEdge {
  source: string;
  target: string;
}

export function getStructuralEdges(): StructuralEdge[] {
  const edges: StructuralEdge[] = [];

  // Phase chain: triage -> dispatch -> ... -> close
  for (let i = 0; i < PHASES.length - 1; i++) {
    edges.push({ source: `phase:${PHASES[i]}`, target: `phase:${PHASES[i + 1]}` });
  }

  // Phase -> tools (from Brain's _phase_tool_priority)
  for (const [phase, tools] of Object.entries(PHASE_TOOL_PRIORITY)) {
    for (const tool of tools) {
      edges.push({ source: `phase:${phase}`, target: `tool:${tool}` });
    }
  }

  // Agent -> select_agent
  for (const a of AGENTS) {
    edges.push({ source: `agent:${a}`, target: 'tool:select_agent' });
  }

  // Tool group internal chains
  for (const tools of Object.values(TOOL_GROUPS)) {
    for (let i = 0; i < tools.length - 1; i++) {
      edges.push({ source: `tool:${tools[i]}`, target: `tool:${tools[i + 1]}` });
    }
  }

  return edges;
}
