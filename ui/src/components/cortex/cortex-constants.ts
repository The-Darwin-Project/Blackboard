// BlackBoard/ui/src/components/cortex/cortex-constants.ts
// @ai-rules:
// 1. [Constraint]: Executive hemisphere neurons are hardcoded -- they mirror Brain tool declarations.
// 2. [Pattern]: Tool groups map to functional clusters in the Brain's tool dispatcher.
// 3. [Gotcha]: Keep in sync with Brain's function tool list in brain.py.
// 4. [Pattern]: PHASE_TOOL_PRIORITY mirrors Brain's _phase_tool_priority in brain.py.
import type { Neuron } from './types';

export const TOOL_GROUPS: Record<string, string[]> = {
  observation: ['lookup_service', 'lookup_journal', 'consult_deep_memory', 'refresh_gitlab_context', 'refresh_kargo_context', 'take_note', 'review_notes'],
  classification: ['classify_event', 'set_phase'],
  routing: ['select_agent', 'create_plan', 'message_agent', 'reply_to_agent'],
  lifecycle: ['defer_event', 'wait_for_user', 'close_event'],
  communication: ['notify_user_slack', 'notify_gitlab_result', 'report_incident', 'get_plan_progress'],
};

export const PHASES = ['triage', 'dispatch', 'verify', 'escalate', 'close'];
export const AGENTS = ['architect', 'sysadmin', 'developer', 'qe', 'security_analyst'];
export const DOMAINS = ['clear', 'complicated', 'complex', 'chaotic', 'casual', 'disorder'];

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

  for (const domain of DOMAINS) {
    neurons.push({
      id: `domain:${domain}`,
      type: 'domain',
      heat: 0,
      payload: { label: domain },
    });
  }

  return neurons;
}

export const NEURON_DESCRIPTIONS: Record<string, string> = {
  // Observation tools
  'tool:lookup_service': 'Query K8s service metrics and annotations',
  'tool:lookup_journal': 'Search system journal for recent log entries',
  'tool:consult_deep_memory': 'Query vector memory for lessons and past events',
  'tool:refresh_gitlab_context': 'Fetch latest GitLab MR and pipeline status',
  'tool:refresh_kargo_context': 'Fetch latest Kargo promotion status',
  'tool:take_note': 'Record a qualitative field note for long-term knowledge',
  'tool:review_notes': 'Review all accumulated field notes in the notebook',
  // Classification tools
  'tool:classify_event': 'Classify event domain and severity via LLM',
  'tool:set_phase': 'Transition event to a new lifecycle phase',
  // Routing tools
  'tool:select_agent': 'Route event to the appropriate CLI agent',
  'tool:create_plan': 'Generate an action plan for the selected agent',
  'tool:message_agent': 'Send instructions to a dispatched agent',
  'tool:reply_to_agent': 'Respond to an agent follow-up question',
  // Lifecycle tools
  'tool:defer_event': 'Park event and schedule a wake-up timer',
  'tool:wait_for_user': 'Pause event pending user response',
  'tool:close_event': 'Resolve and close the event lifecycle',
  // Communication tools
  'tool:notify_user_slack': 'Send a message to the user via Slack',
  'tool:notify_gitlab_result': 'Post results as a GitLab MR comment',
  'tool:report_incident': 'Escalate to Smartsheet incident report',
  'tool:get_plan_progress': 'Check execution status of the current plan',
  'tool:comment_jira_issue': 'Post a comment on a Jira issue',
  'tool:transition_jira_issue': 'Move a Jira issue to a new status',
  'tool:post_sticky_note': 'Leave a cross-event sticky note for future reference',
  'tool:hold_watch': 'Park meta-event and watch queue membership changes',
  // Phases
  'phase:triage': 'Initial classification and context gathering',
  'phase:dispatch': 'Agent selection and plan creation',
  'phase:verify': 'Validate agent execution results',
  'phase:escalate': 'Escalate unresolved issues to stakeholders',
  'phase:close': 'Resolve and finalize the event',
  // Agents
  'agent:architect': 'Strategy and plan creation (Claude CLI, plan-only)',
  'agent:sysadmin': 'GitOps and kubectl execution (Gemini CLI)',
  'agent:developer': 'Pair programming: Dev implements, QE verifies',
  'agent:qe': 'Quality verification of developer output',
  'agent:security_analyst': 'Security analysis and vulnerability assessment',
  // Cynefin domains
  'domain:clear': 'Known knowns — best practice, single correct solution',
  'domain:complicated': 'Known unknowns — expert analysis, multiple good practices',
  'domain:complex': 'Unknown unknowns — emergent practice, safe-to-fail probes',
  'domain:chaotic': 'System in crisis — act first, stabilize, then analyze',
  'domain:casual': 'Non-problem interaction — conversational, reclassify when purpose emerges',
  'domain:disorder': 'Default state — not yet classified into a domain',
};

/**
 * Phase-to-skill-folder mapping for structural edges in the cognitive graph.
 * Mirrors BRAIN_PHASE_SKILLS in brain.py. always/ skills are omnipresent and
 * intentionally left unconnected (connecting to all phases is visual noise).
 */
export const PHASE_SKILL_FOLDERS: Record<string, string[]> = {
  dispatch: ['dispatch', 'coordination'],
  verify: ['post-agent', 'defer-wake'],
  escalate: ['post-agent', 'escalate'],
  close: ['close'],
};

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

  // Domain -> classify_event
  for (const d of DOMAINS) {
    edges.push({ source: 'tool:classify_event', target: `domain:${d}` });
  }

  return edges;
}
