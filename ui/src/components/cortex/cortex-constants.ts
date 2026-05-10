// BlackBoard/ui/src/components/cortex/cortex-constants.ts
// @ai-rules:
// 1. [Constraint]: Executive hemisphere neurons are hardcoded -- they mirror Brain tool declarations.
// 2. [Pattern]: Tool groups map to functional clusters in the Brain's tool dispatcher.
// 3. [Gotcha]: Keep in sync with Brain's function tool list in brain.py.
import type { Neuron } from './types';

const TOOL_GROUPS: Record<string, string[]> = {
  observation: ['lookup_service', 'lookup_journal', 'consult_deep_memory', 'refresh_gitlab_context', 'refresh_kargo_context'],
  classification: ['classify_event', 'set_phase'],
  routing: ['select_agent', 'create_plan', 'message_agent', 'reply_to_agent'],
  lifecycle: ['defer_event', 'wait_for_user', 'close_event'],
  communication: ['notify_user_slack', 'notify_gitlab_result', 'report_incident', 'get_plan_progress'],
};

const PHASES = ['triage', 'investigate', 'execute', 'verify', 'escalate', 'close'];
const AGENTS = ['architect', 'sysadmin', 'developer', 'qe'];

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

/** X position bias: knowledge neurons left, executive right */
export const HEMISPHERE_X = {
  knowledge: -200,
  executive: 200,
} as const;

export const TOOL_GROUP_Y: Record<string, number> = {
  observation: -150,
  classification: -50,
  routing: 50,
  lifecycle: 150,
  communication: 250,
};
