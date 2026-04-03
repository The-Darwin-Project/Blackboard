// BlackBoard/ui/src/components/ops/mockData.ts
// @ai-rules:
// 1. [Constraint]: Dev-only mock data. Used when backend is offline to demo the sidebar UI.
// 2. [Pattern]: Mock events match the EventDocument shape from api/types.ts.
// 3. [Gotcha]: These are NOT real events. They exist only to visualize the sidebar tree + accordion.

export const MOCK_EVENTS = [
  {
    id: 'evt-demo0001',
    status: 'active',
    source: 'chat',
    service: 'inventory-api',
    current_agent: 'architect',
  },
  {
    id: 'evt-demo0002',
    status: 'waiting_approval',
    source: 'headhunter',
    service: 'general',
    current_agent: 'developer',
  },
  {
    id: 'evt-demo0003',
    status: 'deferred',
    source: 'aligner',
    service: 'redis',
    current_agent: null,
  },
];

export const MOCK_CLOSED_EVENTS = [
  {
    id: 'evt-demo-c01',
    status: 'closed',
    source: 'chat',
    service: 'customer-svc',
    current_agent: null,
    created: new Date(Date.now() - 10 * 60 * 1000).toISOString(),
  },
  {
    id: 'evt-demo-c02',
    status: 'closed',
    source: 'headhunter',
    service: 'general',
    current_agent: null,
    created: new Date(Date.now() - 22 * 60 * 1000).toISOString(),
  },
];

export const MOCK_EVENT_DOC = {
  id: 'evt-demo0001',
  source: 'chat' as const,
  status: 'active',
  service: 'inventory-api',
  event: {
    reason: 'Split the darwin-store backend into inventory and customer management services',
    evidence: {
      display_text: 'User requested backend service split for inventory-api',
      source_type: 'chat',
      domain: 'complex',
      severity: 'info',
      triggered_by: 'dashboard',
    },
    timeDate: new Date().toISOString(),
  },
  conversation: [
    {
      turn: 1, actor: 'user', action: 'message',
      thoughts: 'Split the darwin-store backend into inventory and customer management services',
      timestamp: Date.now() / 1000 - 300,
    },
    {
      turn: 2, actor: 'brain', action: 'triage',
      thoughts: 'COMPLEX domain: This is a backend architecture split with unknown dependencies. Creating a 4-step plan.',
      result: 'Classified as COMPLEX. Creating plan before routing.',
      timestamp: Date.now() / 1000 - 290,
    },
    {
      turn: 3, actor: 'brain', action: 'plan',
      thoughts: 'Plan chalked with 4 steps.',
      plan: '## Service Split Plan\n\n1. **architect** — Analyze codebase and propose split strategy\n2. **developer** — Implement the code split\n3. **qe** — Write and execute tests\n4. **sysadmin** — Update GitOps configuration',
      selectedAgents: ['architect', 'developer', 'qe', 'sysadmin'],
      taskForAgent: {
        steps: [
          { id: 'step-1', agent: 'architect', summary: 'Analyze codebase and propose split strategy' },
          { id: 'step-2', agent: 'developer', summary: 'Implement the code split' },
          { id: 'step-3', agent: 'qe', summary: 'Write and execute tests for split services' },
          { id: 'step-4', agent: 'sysadmin', summary: 'Update GitOps configuration and deploy' },
        ],
      },
      timestamp: Date.now() / 1000 - 280,
    },
    {
      turn: 4, actor: 'brain', action: 'route',
      thoughts: 'Routing to architect for codebase analysis (probe step).',
      selectedAgents: ['architect'],
      taskForAgent: { agent: 'architect', mode: 'plan' },
      timestamp: Date.now() / 1000 - 270,
    },
    {
      turn: 5, actor: 'architect', action: 'plan_step',
      thoughts: 'Analyzing darwin-store codebase. Found 12 service files, 3 shared modules, 2 database schemas.',
      evidence: 'in_progress',
      taskForAgent: { step_id: 'step-1', status: 'in_progress' },
      timestamp: Date.now() / 1000 - 200,
    },
    {
      turn: 6, actor: 'architect', action: 'plan_step',
      thoughts: 'Step 1 complete: Analysis finished.',
      taskForAgent: { step_id: 'step-1', status: 'completed' },
      timestamp: Date.now() / 1000 - 125,
    },
    {
      turn: 7, actor: 'architect', action: 'turn',
      thoughts: 'Analysis complete. The store has clear boundaries between inventory (products, stock, warehousing) and customer (accounts, orders, addresses). Shared modules: auth middleware, logging, database connection pool.',
      result: '## Architectural Plan\n\n### Inventory Service\n- Products CRUD\n- Stock management\n- Warehouse allocation\n\n### Customer Service\n- Account management\n- Order processing\n- Address book\n\n### Shared Libraries\n- Extract auth middleware to npm package\n- Shared DB connection pool config\n\n### Migration Strategy\n- Phase 1: Extract inventory routes\n- Phase 2: Separate database schemas\n- Phase 3: Deploy independently',
      timestamp: Date.now() / 1000 - 120,
    },
    {
      turn: 8, actor: 'brain', action: 'request_approval',
      thoughts: 'Architect analysis complete. Requesting user approval before proceeding with implementation.',
      pendingApproval: true,
      waitingFor: 'user',
      timestamp: Date.now() / 1000 - 110,
    },
  ],
  slack_thread_ts: null,
  slack_channel_id: null,
  slack_user_id: null,
  slack_thread_title: null,
};

export const MOCK_HH_TODOS = [
  {
    todo_id: 9901,
    mr_iid: 297,
    mr_title: 'Submodule Update: cnv-operator v4.19.1',
    project_path: 'openshift-virtualization/release-app',
    action: 'build_failed',
    priority: 1,
    pipeline_status: 'failed',
    target_url: 'https://gitlab.example.com/mr/297',
    author: 'kargo-bot',
    created_at: new Date(Date.now() - 45 * 60000).toISOString(),
  },
  {
    todo_id: 9902,
    mr_iid: 301,
    mr_title: 'Konflux Release: bundle v4.19.1-rc2',
    project_path: 'openshift-virtualization/openshift-gitops',
    action: 'approval_required',
    priority: 2,
    pipeline_status: 'success',
    target_url: 'https://gitlab.example.com/mr/301',
    author: 'konflux-release',
    created_at: new Date(Date.now() - 15 * 60000).toISOString(),
  },
];
