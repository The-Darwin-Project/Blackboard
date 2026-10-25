# Graph Report - Blackboard  (2026-10-25)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 4750 nodes · 10471 edges · 179 communities (82 shown, 97 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 902 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `1f79c550`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BlackboardState
- brain.py
- EventDocument
- queue.py
- client.ts
- useCortexData.ts
- Archivist
- Brain
- tool_gates.py
- AgentRegistry
- merge-guard.js
- nightwatcher_tools.py
- auth.py
- colors.ts
- .get_graph_data
- jenkins-mcp.js
- SlackChannel
- EventChatPanel.tsx
- EventSidebar.tsx
- react
- App.tsx
- jenkins_observer.py
- slack.py
- OpsStateContext.tsx
- Aligner
- ReconcileScheduler
- ephemeral_provisioner.py
- ._run_agent_task
- _BrainToolContext
- GitLabPlatform
- KnowledgeGraphStore
- credentials.js
- httpx
- EventRepository
- ActiveStreamsContext.tsx
- cli-executor.js
- JenkinsAdapter
- ._process_with_llm
- JenkinsObserver
- GitHubPlatform
- ui/package.json
- TurnBubble.tsx
- AgentClient
- ToolContext
- ArchitectureGraph.tsx
- handlers_integration.py
- ConversationTurn
- TimeKeeperPage.tsx
- ScheduleRepository
- lifespan
- Headhunter
- observations_mgmt.py
- main.py
- ws-client.js
- dependencies.py
- GeminiAdapter
- http-handler.js
- server.js
- LiveAPIAdapter
- StateWatcher
- CortexGraph.tsx
- adf_to_markdown
- ._close_and_broadcast
- ArgoCDObserver
- llm/__init__.py
- BrainSkillLoader
- ._get_manager
- KargoObserver
- TopologyRepository
- dependencies
- NodeInspector.tsx
- reconcile.py
- IdleTimeoutManager
- compilerOptions
- scheduling/__init__.py
- state/__init__.py
- GitHubAppAuth
- cli-setup.js
- VcsPlatformPort
- PulseBatch
- claude-guard.js
- ._build_system_prompt
- ReflexSearcher
- context_parts.py
- EphemeralProvisioner
- devDependencies
- compilerOptions
- DashboardWSAdapter
- get_report
- gemini-sidecar/package.json
- ObservationRepository
- ShiftsPage.tsx
- QuotaTracker
- catalog-skills.js
- OIDCKeyAdapter
- ClaudeAdapter
- handle_classify_event
- FairQueue
- SlackAccessGate
- generate_map.py
- src/ports.py
- ._discover
- EscalationRepository
- .append_and_broadcast
- MultiInstallationManager
- .scroll
- ._extract_context_flags
- HeadhunterJira
- TokenMeter
- JarvisMemoryPage.tsx
- ._github_poll_and_process
- is_defer_event_available
- cortex-constants.ts
- NeuronInfoPanel.tsx
- entity_extractor.py
- has_unevaluated_close_blocker
- get_quota_tracker
- handlers_verification.py
- SmartsheetMaintainerCache
- .has_reeval_signal
- MetricsRepository
- AsyncGitHubClient
- GitLabTokenAuth
- _is_event_closed_or_missing
- TimeKeeperObserver
- CortexRepository
- BrainIntrospectionPort
- scripts
- validate-mutations.sh
- ._process_message
- list_failed_stages
- dex_proxy
- submit_feedback
- list_incidents
- require-results.sh
- TokenUsageDict
- tsconfig.json
- gh-wrapper.sh
- check-inbox.sh
- cluster-context.sh
- validate-reviewer-bash.sh
- huddleSendMessage.sh
- update-agy.sh
- sendResults.sh
- _patch_enum_fields
- build_gate_context
- diagnose_rejection
- GateDefinition
- _pred_dispatch_defer
- _pred_hard_strip_defer
- _pred_jarvis_wait
- _pred_obs_plateau
- _pred_silent_park
- _tools_wait_loop

## God Nodes (most connected - your core abstractions)
1. `BlackboardState` - 279 edges
2. `Brain` - 148 edges
3. `ConversationTurn` - 122 edges
4. `ToolContext` - 102 edges
5. `GateContext` - 94 edges
6. `EventDocument` - 78 edges
7. `react` - 71 edges
8. `fetchApi()` - 65 edges
9. `lifespan()` - 64 edges
10. `LiveAPIAdapter` - 58 edges

## Surprising Connections (you probably didn't know these)
- `DashboardWSAdapter` --uses--> `BlackboardState`  [INFERRED]
  src/adapters/dashboard_ws.py → src/state/blackboard.py
- `LiveAPIAdapter` --uses--> `BlackboardState`  [INFERRED]
  src/adapters/live_api_adapter.py → src/state/blackboard.py
- `Brain` --uses--> `BlackboardState`  [INFERRED]
  src/agents/brain.py → src/state/blackboard.py
- `handle_record_observation()` --uses--> `BlackboardState`  [INFERRED]
  src/agents/handlers_observations.py → src/state/blackboard.py
- `HeadhunterJira` --uses--> `BlackboardState`  [INFERRED]
  src/agents/headhunter_jira.py → src/state/blackboard.py

## Import Cycles
- None detected.

## Communities (179 total, 97 thin omitted)

### Community 0 - "BlackboardState"
Cohesion: 0.01
Nodes (16): get_all_journal(), get_service_journal(), delete_notebook_note(), get_notebook(), NotePatchRequest, update_notebook_note(), get_event_observations(), get_global_observations() (+8 more)

### Community 1 - "brain.py"
Cohesion: 0.03
Nodes (26): _sanitize_lesson_text(), _get_static_maintainer_emails(), _get_allowed_mention_authors(), _get_static_maintainer_emails(), _safe_int(), create_adapter(), record_token_usage(), get_blackboard() (+18 more)

### Community 2 - "EventDocument"
Cohesion: 0.02
Nodes (34): _close_unanswered_fc(), _resolve_escalation_scope(), _build_closed_block(), build_event_header(), _build_identity_block(), _build_journal_block(), _build_mermaid_block(), _build_related_block() (+26 more)

### Community 3 - "queue.py"
Cohesion: 0.03
Nodes (54): get_token_meter(), get_archivist(), get_brain(), get_pulse_tracker(), dismiss_proposals(), DismissRequest, get_all_shadow_interventions(), get_cognitive_graph() (+46 more)

### Community 4 - "client.ts"
Cohesion: 0.03
Nodes (90): recharts, @tanstack/react-query, ApiError, bulkDeleteObservations(), createChatEvent(), deleteNote(), deleteObservation(), exportObservations() (+82 more)

### Community 5 - "useCortexData.ts"
Cohesion: 0.05
Nodes (78): three, getCognitiveGraph(), getCortexActivity(), getEventPulses(), getEventReport(), getKGServiceDetail(), getKGServices(), getKGStats() (+70 more)

### Community 8 - "tool_gates.py"
Cohesion: 0.05
Nodes (78): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+70 more)

### Community 9 - "AgentRegistry"
Cohesion: 0.05
Nodes (17): AgentConnection, AgentRegistry, agent_websocket_handler(), _heartbeat(), _build_prompt(), _check_security(), consume_wake_task(), _consume() (+9 more)

### Community 10 - "merge-guard.js"
Cohesion: 0.05
Nodes (69): analyzeString(), analyzeTokens(), API_VALUED, apiTokens(), apiWriteNeedsGuard(), assignName(), bareBranchProtected(), base() (+61 more)

### Community 11 - "nightwatcher_tools.py"
Cohesion: 0.06
Nodes (28): PulseContext, ShiftIncident, ShiftInvestigation, ShiftReport, NightwatcherObserver, build_manifest_table(), build_report_iteration_prompt(), build_summary_prompt() (+20 more)

### Community 12 - "auth.py"
Cohesion: 0.05
Nodes (23): can_append_message(), can_approve_event(), can_override_domain(), _claims_to_user(), get_user_from_request(), get_user_from_websocket(), _normalize_email(), prompt_display_name() (+15 more)

### Community 13 - "colors.ts"
Cohesion: 0.07
Nodes (39): @tanstack/react-table, getReport(), getReports(), ReportFull, ReportMeta, CompactCardStrip(), EventHistory(), TimeRange (+31 more)

### Community 14 - ".get_graph_data"
Cohesion: 0.04
Nodes (13): GraphNode, TicketNode, get_event_document(), _defer_timeline_fields(), _has_active_subscription(), list_active_events(), get_graph_data(), get_mermaid_diagram() (+5 more)

### Community 15 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 16 - "SlackChannel"
Cohesion: 0.06
Nodes (11): get_user_from_slack(), format_event_summary(), SlackChannel, handle_app_home_opened(), handle_app_mention(), handle_approve(), handle_create_event_modal(), handle_darwin_command() (+3 more)

### Community 17 - "EventChatPanel.tsx"
Cohesion: 0.07
Nodes (48): closeEvent(), enforceCasualDomain(), CiContext, ConversationTurn, CiContextCard(), CiContextCardProps, ConsoleTailBlock(), FailedJobRow() (+40 more)

### Community 18 - "EventSidebar.tsx"
Cohesion: 0.07
Nodes (50): getAlignerPending(), getHeadhunterPending(), getJenkinsPending(), getJiraMissions(), getWaitingApprovalEvents(), HeadhunterTodo, postJiraAction(), EventDocument (+42 more)

### Community 19 - "react"
Cohesion: 0.08
Nodes (52): lucide-react, react, applyLessons(), correctMemory(), createKnowledge(), createLesson(), deleteKnowledge(), deleteLesson() (+44 more)

### Community 20 - "App.tsx"
Cohesion: 0.06
Nodes (44): oidc-client-ts, getFlowHistory(), getWSAuthFailureCallback(), setOnUnauthorized(), setTokenGetter(), setWSAuthFailureCallback(), AuthConfig, FlowSnapshot (+36 more)

### Community 21 - "jenkins_observer.py"
Cohesion: 0.06
Nodes (19): _annotation_replace(), _strip_pipeline_annotations(), _clamp_confidence(), _parse_job_metadata(), _prepare_console_tail(), _redact_build_parameters(), _redact_match(), _redact_secrets_in_text() (+11 more)

### Community 22 - "slack.py"
Cohesion: 0.06
Nodes (19): build_access_denied_home_view(), build_home_tab_view(), _context_line(), create_feedback_block(), extract_tables(), _replace(), format_plan_block(), format_task_card() (+11 more)

### Community 23 - "OpsStateContext.tsx"
Cohesion: 0.08
Nodes (38): react-router-dom, getActiveEvents(), getAgents(), getConfig(), getEventDocument(), getEvents(), getKargoStages(), AgentRegistryEntry (+30 more)

### Community 25 - "ReconcileScheduler"
Cohesion: 0.05
Nodes (6): FlowCollector, ReconcileScheduler, Trigger, QueueTrigger, ResyncTrigger, StalenessGuard

### Community 26 - "ephemeral_provisioner.py"
Cohesion: 0.06
Nodes (6): KubernetesSpawnHealthAdapter, _PodHealthState, DispatchMetrics, SpawnHealthPort, SpawnPollResult, SpawnStatus

### Community 27 - "._run_agent_task"
Cohesion: 0.08
Nodes (7): on_huddle(), on_progress(), on_huddle(), on_progress(), _compute_processed_up_to(), _sanitize_error_text(), get_registry_and_bridge()

### Community 30 - "KnowledgeGraphStore"
Cohesion: 0.08
Nodes (9): _format_graph_context(), get_graph_context(), _parse_props(), _sanitize(), translate_to_lookups(), _acquire(), KnowledgeGraphStore, _sanitize() (+1 more)

### Community 31 - "credentials.js"
Cohesion: 0.13
Nodes (44): resolveCommand(), writeAgyMcpServer(), writeClaudeMcpServer(), buildArgoCDMcpConfig(), createAppJWT(), discoverAndGenerateTokens(), _discoverAndGenerateTokensInner(), discoverInstallations() (+36 more)

### Community 32 - "httpx"
Cohesion: 0.08
Nodes (14): _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), _sample_points(), _summarize(), approve_mission() (+6 more)

### Community 34 - "ActiveStreamsContext.tsx"
Cohesion: 0.09
Nodes (35): getFlowMetrics(), FlowMetrics, AgentStreamCard(), AgentStreamCardProps, FloatingWindow(), MessageCards(), Dashboard(), FlowHealthWidget() (+27 more)

### Community 35 - "cli-executor.js"
Cohesion: 0.09
Nodes (35): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS }, buildCLICommand(), CLAUDE_JSON_PATH, cp, executeCLI(), executeCLIStreaming(), FALLBACK_MODEL, fs (+27 more)

### Community 36 - "JenkinsAdapter"
Cohesion: 0.06
Nodes (6): BuildDetails, JenkinsAdapter, JenkinsPlatformPort, JobResult, JobRunState, ViewScanResult

### Community 40 - "ui/package.json"
Cohesion: 0.06
Nodes (34): autoprefixer, cronstrue, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, graphology-layout-forceatlas2 (+26 more)

### Community 41 - "TurnBubble.tsx"
Cohesion: 0.11
Nodes (29): @uiw/react-markdown-preview, approveEvent(), rejectEvent(), submitFeedback(), MarkdownViewer(), MermaidBlock(), InlineMarkdownViewerProps, JournalRow() (+21 more)

### Community 42 - "AgentClient"
Cohesion: 0.07
Nodes (4): Architect, AgentClient, Developer, SysAdmin

### Community 43 - "ToolContext"
Cohesion: 0.09
Nodes (7): handle_select_agent(), handle_close_event(), handle_defer_event(), handle_hold_watch(), handle_wait_for_jarvis(), handle_wait_for_user(), ToolContext

### Community 44 - "ArchitectureGraph.tsx"
Cohesion: 0.09
Nodes (28): @dagrejs/dagre, @xyflow/react, HealthStatus, NodeType, AppNodeData, applyDagreLayout(), applyGridLayout(), applyLayout() (+20 more)

### Community 45 - "handlers_integration.py"
Cohesion: 0.08
Nodes (18): _alert_wrapper_retrigger(), _do_retrigger(), _get_jira_reporter(), handle_ask_release_ai(), handle_comment_jira_issue(), handle_fetch_jira_issue(), handle_greenwave(), handle_notify_user_slack() (+10 more)

### Community 46 - "ConversationTurn"
Cohesion: 0.14
Nodes (17): emit_tool_result(), _safe_int(), handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_recall_pruned_turns(), handle_consult_deep_memory(), handle_google_web_search() (+9 more)

### Community 47 - "TimeKeeperPage.tsx"
Cohesion: 0.12
Nodes (24): createSchedule(), deleteSchedule(), getSchedules(), refineInstructions(), ScheduleCreatePayload, ScheduleItem, toggleSchedule(), updateSchedule() (+16 more)

### Community 48 - "ScheduleRepository"
Cohesion: 0.08
Nodes (4): ScheduleCreateRequest, ScheduledEvent, update_schedule(), ScheduleRepository

### Community 49 - "lifespan"
Cohesion: 0.06
Nodes (7): set_incident_options(), set_agents(), set_blackboard(), set_brain(), set_kargo_observer(), set_registry_and_bridge(), lifespan()

### Community 51 - "observations_mgmt.py"
Cohesion: 0.09
Nodes (10): render_pdf(), bulk_delete_observations(), BulkDeleteRequest, delete_observation(), export_observations(), generate_observations_report(), rename_observation(), RenameRequest (+2 more)

### Community 52 - "main.py"
Cohesion: 0.09
Nodes (12): set_archivist(), agent_ws_endpoint(), api_info(), get_config(), get_event_flow(), get_flow_history(), health_check(), list_agents() (+4 more)

### Community 53 - "ws-client.js"
Cohesion: 0.10
Nodes (24): is429Error(), {
  DEFAULT_WORK_DIR, AGENT_CLI, AGENT_MODEL, AGENT_ROLE,
  EVENT_ID, EPHEMERAL, IDLE_TIMEOUT_MS,
  CLI_429_MAX_RETRIES, CLI_429_INITIAL_DELAY_MS, CLI_429_BACKOFF_MULTIPLIER,
}, { ensureEventDocument }, { executeCLIStreaming, prepareResultsDir, is429Error }, { filterSkillsByRole, filterSkillsByMode, swapActiveRules, restoreAllSkills }, handleCancel(), resetTimer(), {
  hasGitHubCredentials, discoverAndGenerateTokens, setupGitCredentials, setupGitHubTooling,
  hasGitLabCredentials, readGitLabToken, setupGitLabCredentials, setupGitLabTooling,
  setupArgoCDMCP, setupCLILogins, setupRemoteK8sMCPs, setupRegistryCredentials, GITLAB_HOST,
  hasJenkinsCredentials, setupJenkinsMCP, hasGoogleServiceAccount, setupGoogleAuthForAgy,
} (+16 more)

### Community 54 - "dependencies.py"
Cohesion: 0.08
Nodes (14): get_aligner(), get_architect(), get_argocd_observer(), get_developer(), get_kargo_observer(), get_kg_store(), get_report_client(), get_sysadmin() (+6 more)

### Community 56 - "http-handler.js"
Cohesion: 0.08
Nodes (21): ROLE_TIMEOUTS, SUPPORTED_AGENT_CLIS, getRemoteClustersMeta(), { AGENT_CLI, AGENT_MODEL, DEFAULT_WORK_DIR, PORT, BRAIN_HTTP_URL }, { claudeMergeGuard }, { executeCLI }, fs, {
  hasGitHubCredentials,
  discoverAndGenerateTokens,
  setupGitCredentials,
  setupGitHubTooling,
  hasGitLabCredentials,
  readGitLabToken,
  setupGitLabCredentials,
  setupGitLabTooling,
  setupArgoCDMCP,
  setupCLILogins,
  setupRegistryCredentials,
  setupRemoteK8sMCPs,
  getRemoteClustersMeta,
  GITLAB_HOST,
} (+13 more)

### Community 57 - "server.js"
Cohesion: 0.09
Nodes (17): hasRegistryCredentials(), { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, fs, path, stageEventDocument(), fetchEventDocument(), fs, { handleRequest } (+9 more)

### Community 59 - "StateWatcher"
Cohesion: 0.10
Nodes (3): _QueueEntry, StateWatcher, _Subscription

### Community 60 - "CortexGraph.tsx"
Cohesion: 0.15
Nodes (24): graphology, eventColor(), getExecutiveNeurons(), getStructuralEdges(), DEFAULT_TYPE_BUDGET, evictLru(), KNOWLEDGE_RING, KNOWLEDGE_RING_TYPES (+16 more)

### Community 61 - "adf_to_markdown"
Cohesion: 0.12
Nodes (10): _adf_to_text(), _escape_jql_string(), JiraIncidentAdapter, adf_to_markdown(), _apply_marks(), _children(), _render(), _render_list() (+2 more)

### Community 64 - "llm/__init__.py"
Cohesion: 0.16
Nodes (5): FunctionCall, LLMChunk, LLMPort, LLMResponse, TokenUsage

### Community 69 - "dependencies"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 70 - "NodeInspector.tsx"
Cohesion: 0.13
Nodes (22): getClosedEvents(), ArchitectureEvent, ArgoCDOperation, EVENT_LABELS, EventItem(), EventItemProps, healthTone(), lastOperationSummary() (+14 more)

### Community 71 - "reconcile.py"
Cohesion: 0.15
Nodes (9): _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers(), main(), _parse_frontmatter() (+1 more)

### Community 73 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 74 - "scheduling/__init__.py"
Cohesion: 0.15
Nodes (10): handle_refresh_github_context(), handle_refresh_gitlab_context(), handle_refresh_kargo_context(), StateWatcherPort, GitHubPrRef, GitLabMrRef, GitLabPipelineRef, KargoStageRef (+2 more)

### Community 75 - "state/__init__.py"
Cohesion: 0.12
Nodes (3): close_redis(), get_redis(), RedisClient

### Community 77 - "cli-setup.js"
Cohesion: 0.13
Nodes (19): { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync }, filterSkillsByMode() (+11 more)

### Community 79 - "PulseBatch"
Cohesion: 0.12
Nodes (4): PulseBatch, PulsePort, PulseObserver, PulseTracker

### Community 80 - "claude-guard.js"
Cohesion: 0.14
Nodes (16): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+8 more)

### Community 81 - "._build_system_prompt"
Cohesion: 0.11
Nodes (3): _init_tool_names(), _strip_tool_names(), _wrap_section()

### Community 83 - "context_parts.py"
Cohesion: 0.13
Nodes (9): _apply_sibling_signature(), build_function_response(), build_single_function_response(), compress_contents(), estimate_msg_tokens(), estimate_tokens(), extract_model_parts(), normalize_response_parts() (+1 more)

### Community 85 - "devDependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 86 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 88 - "get_report"
Cohesion: 0.11
Nodes (6): get_report(), list_reports(), reports_spa_no_slash(), reports_spa_with_slash(), search_reports(), _serve_spa()

### Community 89 - "gemini-sidecar/package.json"
Cohesion: 0.11
Nodes (17): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+9 more)

### Community 92 - "ShiftsPage.tsx"
Cohesion: 0.23
Nodes (16): getCurrentShift(), getShiftDetail(), getShiftsList(), ShiftReportFull, ShiftReportSummary, FailedClusterBadge(), getISOWeek(), getWeekDates() (+8 more)

### Community 94 - "catalog-skills.js"
Cohesion: 0.16
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 97 - "handle_classify_event"
Cohesion: 0.14
Nodes (4): handle_classify_event(), handle_request_user_approval(), IdleTimeoutPort, IncidentAdapterPort

### Community 101 - "generate_map.py"
Cohesion: 0.19
Nodes (6): _enumerate_gates(), _GateInfo, generate_phase_tool_map(), _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 105 - ".append_and_broadcast"
Cohesion: 0.26
Nodes (7): handle_message_agent(), handle_reply_to_agent(), handle_report_incident(), handle_notify_gitlab_result(), handle_search_open_incidents(), handle_respond_to_jarvis(), handle_wait_for_agent()

### Community 109 - "._extract_context_flags"
Cohesion: 0.15
Nodes (3): compute_dispatch_backpressure(), ContextFlags, _safe_int_env()

### Community 112 - "JarvisMemoryPage.tsx"
Cohesion: 0.27
Nodes (12): dismissProposals(), EnhancementProposal, getHandoffReports(), getProposals(), HandoffReport, FilterMode, formatDate(), formatTime() (+4 more)

### Community 117 - "is_defer_event_available"
Cohesion: 0.18
Nodes (6): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 118 - "cortex-constants.ts"
Cohesion: 0.18
Nodes (10): AGENTS, DOMAINS, HEMISPHERE_X, NEURON_DESCRIPTIONS, PHASE_SKILL_FOLDERS, PHASE_TOOL_PRIORITY, PHASES, StructuralEdge (+2 more)

### Community 119 - "NeuronInfoPanel.tsx"
Cohesion: 0.29
Nodes (10): asNumber(), asString(), asStringArray(), Badge(), describeNeuron(), Hdr(), NeuronInfoPanel(), AGENT_NEURON_COLORS (+2 more)

### Community 120 - "entity_extractor.py"
Cohesion: 0.33
Nodes (5): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship

### Community 121 - "has_unevaluated_close_blocker"
Cohesion: 0.20
Nodes (4): has_unevaluated_close_blocker(), _pred_jarvis_response(), _pred_unevaluated_close(), is_jarvis_acknowledgment()

### Community 122 - "get_quota_tracker"
Cohesion: 0.22
Nodes (3): get_quota_tracker(), llm_stats(), receive_telemetry()

### Community 123 - "handlers_verification.py"
Cohesion: 0.28
Nodes (4): handle_re_trigger_aligner(), handle_set_phase(), handle_wait_for_verification(), resolve_event_domain()

### Community 135 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 136 - "validate-mutations.sh"
Cohesion: 0.73
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

## Knowledge Gaps
- **14 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+9 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2088 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **97 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `brain.py`, `_is_event_closed_or_missing`, `EventDocument`, `queue.py`, `Brain`, `AgentRegistry`, `nightwatcher_tools.py`, `auth.py`, `.get_graph_data`, `._restage_pending_signal`, `._stage_pending_signal`, `submit_feedback`, `._count_pending`, `.__init__`, `jenkins_observer.py`, `slack.py`, `httpx`, `ConversationTurn`, `ScheduleRepository`, `lifespan`, `observations_mgmt.py`, `main.py`, `dependencies.py`, `LiveAPIAdapter`, `state/__init__.py`, `DashboardWSAdapter`, `get_report`, `HeadhunterJira`?**
  _High betweenness centrality (0.116) - this node is a cross-community bridge._
- **Are the 78 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 78 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _14 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.010680363621540092 - nodes in this community are weakly interconnected._
- **Why does `Brain` connect `Brain` to `BlackboardState`, `brain.py`, `EventDocument`, `AgentRegistry`, `auth.py`, `.__init__`, `slack.py`, `.next_turn_number`, `ReconcileScheduler`, `._run_agent_task`, `._process_with_llm`, `ConversationTurn`, `lifespan`, `main.py`, `dependencies.py`, `StateWatcher`, `._close_and_broadcast`, `BrainSkillLoader`, `IdleTimeoutManager`, `PulseBatch`, `._build_system_prompt`, `ReflexSearcher`, `DashboardWSAdapter`, `QuotaTracker`, `src/ports.py`, `._extract_context_flags`?**
  _High betweenness centrality (0.081) - this node is a cross-community bridge._
- **Are the 20 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Should `brain.py` be split into smaller, more focused modules?**
  _Cohesion score 0.03020295837633299 - nodes in this community are weakly interconnected._