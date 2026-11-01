# Graph Report - Blackboard  (2026-11-01)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 4879 nodes · 10882 edges · 204 communities (86 shown, 118 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 927 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `8d8f7a0b`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BlackboardState
- logging
- queue.py
- brain.py
- client.ts
- react
- tool_gates.py
- Brain
- fetchApi
- lucide-react
- merge-guard.js
- prompt.py
- ._run_agent_task
- EventSidebar.tsx
- ReconcileScheduler
- credentials.js
- SlackChannel
- colors.ts
- jenkins-mcp.js
- BrainSkillLoader
- auth.py
- App.tsx
- slack.py
- Aligner
- _BrainToolContext
- GitLabPlatform
- nightwatcher_tools.py
- KnowledgeGraphStore
- utils/__init__.py
- TurnBubble.tsx
- EventRepository
- cli-executor.js
- JenkinsAdapter
- agents/__init__.py
- ToolContext
- storage-recycler.js
- ._process_with_llm
- GitHubPlatform
- handlers_integration.py
- ConversationTurn
- Archivist
- ws-client.js
- TimeKeeperPage.tsx
- create_schedule
- Headhunter
- ActiveStreamsContext.tsx
- ui/package.json
- EventDrillDown.tsx
- ._build_contents
- server.js
- ._build_system_prompt
- GeminiAdapter
- TaskBridge
- CortexGraph.tsx
- LiveAPIAdapter
- StateWatcher
- adf_to_markdown
- AgentRegistry
- NodeInspector.tsx
- ArgoCDObserver
- reconcile.py
- ._close_and_broadcast
- ._get_manager
- KargoObserver
- TopologyRepository
- dependencies
- lifespan
- FlowSnapshot
- compilerOptions
- llm/__init__.py
- claude-guard.js
- http-handler.js
- TokenUtilizationPage.tsx
- GitHubAppAuth
- useCortexData.ts
- ArchitectureGraph.tsx
- VcsPlatformPort
- PulseBatch
- ReflexSearcher
- handle_report_incident
- devDependencies
- compilerOptions
- DashboardWSAdapter
- ClaudeAdapter
- get_report
- OpsStateContext.tsx
- catalog-skills.js
- gemini-sidecar/package.json
- VectorStore
- ObservationRepository
- ShiftsPage.tsx
- QuotaTracker
- OIDCKeyAdapter
- EphemeralProvisioner
- cortex/types.ts
- SlackAccessGate
- generate_map.py
- KubernetesSpawnHealthAdapter
- .append_and_broadcast
- EscalationRepository
- ServiceNode.tsx
- observations_reporter.py
- ScheduleRepository
- MultiInstallationManager
- ScheduleCreateRequest
- .scroll
- HeadhunterJira
- TokenMeter
- NightwatcherObserver
- IdleTimeoutManager
- NeuronInfoPanel.tsx
- ._github_poll_and_process
- JenkinsObserver
- handle_notify_user_slack
- _resolve_phase
- is_defer_event_available
- cortex-constants.ts
- CortexLiveFeed.tsx
- spawn_health.py
- SecurityError
- vite.config.ts
- SpawnPollResult
- entity_extractor.py
- has_unevaluated_close_blocker
- knowledge_graph_api.py
- get_quota_tracker
- SmartsheetMaintainerCache
- .has_reeval_signal
- list_shifts
- MetricsRepository
- AsyncGitHubClient
- GitLabTokenAuth
- _is_event_closed_or_missing
- TimeKeeperObserver
- CortexRepository
- update_notebook_note
- scripts
- validate-mutations.sh
- io
- ._process_message
- ._evaluate_health
- nightwatcher_prompt.py
- list_failed_stages
- dex_proxy
- DispatchMetrics
- agent_ws_endpoint
- submit_feedback
- _patch_enum_fields
- list_incidents
- require-results.sh
- _WSFrameFilter
- SpawnFailed
- _env_flag
- TokenUsageDict
- findDuplicateJsonKeys.ts
- tsconfig.json
- gh-wrapper.sh
- check-inbox.sh
- cluster-context.sh
- validate-reviewer-bash.sh
- huddleSendMessage.sh
- update-agy.sh
- sendResults.sh
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
1. `BlackboardState` - 280 edges
2. `Brain` - 148 edges
3. `ConversationTurn` - 122 edges
4. `ToolContext` - 103 edges
5. `GateContext` - 94 edges
6. `react` - 80 edges
7. `EventDocument` - 78 edges
8. `fetchApi()` - 65 edges
9. `lifespan()` - 64 edges
10. `LiveAPIAdapter` - 58 edges

## Surprising Connections (you probably didn't know these)
- `Archivist` --uses--> `EventDocument`  [INFERRED]
  src/agents/archivist.py → src/models.py
- `Brain` --uses--> `EventDocument`  [INFERRED]
  src/agents/brain.py → src/models.py
- `_resolve_escalation_scope()` --uses--> `EventDocument`  [INFERRED]
  src/agents/handlers_dispatch.py → src/models.py
- `build_event_header()` --uses--> `EventDocument`  [INFERRED]
  src/agents/llm/prompt.py → src/models.py
- `_build_identity_block()` --uses--> `EventDocument`  [INFERRED]
  src/agents/llm/prompt.py → src/models.py

## Import Cycles
- None detected.

## Communities (204 total, 118 thin omitted)

### Community 0 - "BlackboardState"
Cohesion: 0.01
Nodes (18): _close_unanswered_fc(), get_report_client(), EventDocument, render_pdf(), get_all_journal(), get_service_journal(), get_notebook(), get_event_observations() (+10 more)

### Community 1 - "logging"
Cohesion: 0.02
Nodes (37): _sanitize_lesson_text(), _get_static_maintainer_emails(), _get_allowed_mention_authors(), _get_static_maintainer_emails(), _safe_int(), create_adapter(), record_token_usage(), get_aligner() (+29 more)

### Community 2 - "queue.py"
Cohesion: 0.03
Nodes (59): get_token_meter(), get_archivist(), get_brain(), get_pulse_tracker(), dismiss_proposals(), DismissRequest, get_all_shadow_interventions(), get_cognitive_graph() (+51 more)

### Community 3 - "brain.py"
Cohesion: 0.03
Nodes (48): _apply_sibling_signature(), build_function_response(), build_single_function_response(), compress_contents(), estimate_msg_tokens(), estimate_tokens(), extract_model_parts(), normalize_response_parts() (+40 more)

### Community 4 - "client.ts"
Cohesion: 0.04
Nodes (86): @tanstack/react-query, ApiError, bulkDeleteObservations(), deleteNote(), deleteObservation(), exportObservations(), ExtractionResult, generateObservationsReport() (+78 more)

### Community 5 - "react"
Cohesion: 0.05
Nodes (71): react, ActiveEvent, CiContext, ConversationTurn, EventEvidence, TokenUsageDict, CiContextCard(), CiContextCardProps (+63 more)

### Community 6 - "tool_gates.py"
Cohesion: 0.05
Nodes (78): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+70 more)

### Community 8 - "fetchApi"
Cohesion: 0.06
Nodes (65): applyLessons(), closeEvent(), correctMemory(), createKnowledge(), createLesson(), deleteKnowledge(), deleteLesson(), enforceCasualDomain() (+57 more)

### Community 9 - "lucide-react"
Cohesion: 0.06
Nodes (49): lucide-react, react-router-dom, createChatEvent(), getConfig(), getEvents(), AppConfig, ActivityStream(), ChatInput() (+41 more)

### Community 10 - "merge-guard.js"
Cohesion: 0.05
Nodes (69): analyzeString(), analyzeTokens(), API_VALUED, apiTokens(), apiWriteNeedsGuard(), assignName(), bareBranchProtected(), base() (+61 more)

### Community 11 - "prompt.py"
Cohesion: 0.04
Nodes (19): _build_closed_block(), build_event_header(), _build_identity_block(), _build_journal_block(), _build_mermaid_block(), _build_related_block(), _build_subject_block(), _build_timing_block() (+11 more)

### Community 12 - "._run_agent_task"
Cohesion: 0.06
Nodes (8): on_huddle(), on_progress(), on_huddle(), on_progress(), _compute_processed_up_to(), _sanitize_error_text(), _sanitize_override_reason(), get_registry_and_bridge()

### Community 13 - "EventSidebar.tsx"
Cohesion: 0.08
Nodes (58): getActiveEvents(), getAlignerPending(), getEventDocument(), getHeadhunterPending(), getJenkinsPending(), getJiraMissions(), getWaitingApprovalEvents(), HeadhunterTodo (+50 more)

### Community 14 - "ReconcileScheduler"
Cohesion: 0.04
Nodes (7): FlowCollector, FairQueue, ReconcileScheduler, Trigger, QueueTrigger, ResyncTrigger, StalenessGuard

### Community 15 - "credentials.js"
Cohesion: 0.07
Nodes (59): is429Error(), { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync } (+51 more)

### Community 16 - "SlackChannel"
Cohesion: 0.06
Nodes (11): get_user_from_slack(), format_event_summary(), SlackChannel, handle_app_home_opened(), handle_app_mention(), handle_approve(), handle_create_event_modal(), handle_darwin_command() (+3 more)

### Community 17 - "colors.ts"
Cohesion: 0.07
Nodes (38): getReport(), getReports(), ReportFull, ReportMeta, CompactCardStrip(), EventHistory(), TimeRange, ViewMode (+30 more)

### Community 18 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 19 - "BrainSkillLoader"
Cohesion: 0.04
Nodes (5): BrainSkillLoader, _SkillCorpus, BrainIntrospectionPort, BrainLifecyclePort, BroadcastPort

### Community 20 - "auth.py"
Cohesion: 0.05
Nodes (18): can_append_message(), can_approve_event(), can_override_domain(), _claims_to_user(), get_user_from_request(), get_user_from_websocket(), _normalize_email(), require_auth() (+10 more)

### Community 21 - "App.tsx"
Cohesion: 0.07
Nodes (43): oidc-client-ts, react-dom, dismissProposals(), EnhancementProposal, getHandoffReports(), getProposals(), getWSAuthFailureCallback(), HandoffReport (+35 more)

### Community 22 - "slack.py"
Cohesion: 0.07
Nodes (19): build_access_denied_home_view(), build_home_tab_view(), _context_line(), create_feedback_block(), extract_tables(), _replace(), format_plan_block(), format_task_card() (+11 more)

### Community 26 - "nightwatcher_tools.py"
Cohesion: 0.08
Nodes (23): PulseContext, ShiftIncident, ShiftInvestigation, build_report_iteration_prompt(), build_summary_prompt(), extract_full_links(), _normalize_gitlab_host(), build_extend_tool() (+15 more)

### Community 27 - "KnowledgeGraphStore"
Cohesion: 0.08
Nodes (9): _format_graph_context(), get_graph_context(), _parse_props(), _sanitize(), translate_to_lookups(), _acquire(), KnowledgeGraphStore, _sanitize() (+1 more)

### Community 28 - "utils/__init__.py"
Cohesion: 0.05
Nodes (17): _annotation_replace(), _strip_pipeline_annotations(), _clamp_confidence(), _parse_job_metadata(), _prepare_console_tail(), _redact_build_parameters(), _redact_match(), _redact_secrets_in_text() (+9 more)

### Community 29 - "TurnBubble.tsx"
Cohesion: 0.10
Nodes (34): @uiw/react-markdown-preview, approveEvent(), rejectEvent(), submitFeedback(), CollapsibleSection(), CollapsibleSectionProps, MarkdownViewer(), MermaidBlock() (+26 more)

### Community 31 - "cli-executor.js"
Cohesion: 0.09
Nodes (36): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS, STORAGE_PRETASK_TIMEOUT_MS, resolveStorageRoot }, buildCLICommand(), { checkAndRecycleStorage, pinTaskCwd, unpinTaskCwd }, CLAUDE_JSON_PATH, cp, executeCLI(), executeCLIStreaming(), FALLBACK_MODEL (+28 more)

### Community 32 - "JenkinsAdapter"
Cohesion: 0.06
Nodes (6): BuildDetails, JenkinsAdapter, JenkinsPlatformPort, JobResult, JobRunState, ViewScanResult

### Community 33 - "agents/__init__.py"
Cohesion: 0.07
Nodes (4): Architect, AgentClient, Developer, SysAdmin

### Community 34 - "ToolContext"
Cohesion: 0.09
Nodes (8): handle_select_agent(), handle_classify_event(), handle_close_event(), handle_defer_event(), handle_hold_watch(), handle_request_user_approval(), handle_wait_for_jarvis(), ToolContext

### Community 35 - "storage-recycler.js"
Cohesion: 0.09
Nodes (32): withTaskStorage(), resolveStorageRoot(), ROLE_TIMEOUTS, STORAGE_ACTIVITY_HEARTBEAT_MS, STORAGE_MAX_TIER3_DELETIONS, STORAGE_PRETASK_TIMEOUT_MS, STORAGE_RESULTS_TTL_MS, STORAGE_STALE_MS (+24 more)

### Community 38 - "handlers_integration.py"
Cohesion: 0.10
Nodes (18): _do_retrigger(), _get_jira_reporter(), handle_ask_release_ai(), handle_comment_jira_issue(), handle_fetch_jira_issue(), handle_refresh_github_context(), handle_refresh_gitlab_context(), handle_refresh_kargo_context() (+10 more)

### Community 39 - "ConversationTurn"
Cohesion: 0.13
Nodes (19): emit_tool_result(), _safe_int(), handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_recall_pruned_turns(), handle_consult_deep_memory(), handle_google_web_search() (+11 more)

### Community 41 - "ws-client.js"
Cohesion: 0.08
Nodes (27): { AGENT_ROLE }, _blackboardTurns, _inboundMessages, _teammateMessages, {
  DEFAULT_WORK_DIR, AGENT_CLI, AGENT_MODEL, AGENT_ROLE,
  EVENT_ID, EPHEMERAL, IDLE_TIMEOUT_MS,
  CLI_429_MAX_RETRIES, CLI_429_INITIAL_DELAY_MS, CLI_429_BACKOFF_MULTIPLIER,
}, { ensureEventDocument }, { executeCLIStreaming, prepareResultsDir, is429Error }, { filterSkillsByRole, filterSkillsByMode, swapActiveRules, restoreAllSkills } (+19 more)

### Community 43 - "TimeKeeperPage.tsx"
Cohesion: 0.12
Nodes (24): createSchedule(), deleteSchedule(), getSchedules(), refineInstructions(), ScheduleCreatePayload, ScheduleItem, toggleSchedule(), updateSchedule() (+16 more)

### Community 44 - "create_schedule"
Cohesion: 0.06
Nodes (8): create_schedule(), delete_schedule(), get_schedule(), list_schedules(), _load_brain_context(), refine_instructions(), toggle_schedule(), update_schedule()

### Community 46 - "ActiveStreamsContext.tsx"
Cohesion: 0.13
Nodes (26): AgentStreamCard(), AgentStreamCardProps, FloatingWindow(), MessageCards(), Dashboard(), GridTile(), GridTileProps, TileType (+18 more)

### Community 47 - "ui/package.json"
Cohesion: 0.08
Nodes (29): autoprefixer, cronstrue, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, graphology-layout-forceatlas2 (+21 more)

### Community 48 - "EventDrillDown.tsx"
Cohesion: 0.13
Nodes (24): three, getEventPulses(), BrainCore(), CortexDevPage(), devQueryClient, CortexLiveFeedProps, EventDrillDown(), EventDrillDownProps (+16 more)

### Community 49 - "._build_contents"
Cohesion: 0.07
Nodes (3): compute_dispatch_backpressure(), ContextFlags, _safe_int_env()

### Community 50 - "server.js"
Cohesion: 0.08
Nodes (21): hasRegistryCredentials(), { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, ensureEventDocument(), fs, path, stageEventDocument(), fetchEventDocument(), fs (+13 more)

### Community 51 - "._build_system_prompt"
Cohesion: 0.07
Nodes (3): _init_tool_names(), _strip_tool_names(), _wrap_section()

### Community 53 - "TaskBridge"
Cohesion: 0.11
Nodes (9): _build_prompt(), consume_wake_task(), _consume(), _dispatch_timeout_s(), dispatch_to_agent(), _consume_queue(), _sanitize_stdout(), send_cancel() (+1 more)

### Community 54 - "CortexGraph.tsx"
Cohesion: 0.14
Nodes (25): graphology, eventColor(), getExecutiveNeurons(), getStructuralEdges(), DEFAULT_TYPE_BUDGET, evictLru(), KNOWLEDGE_RING, KNOWLEDGE_RING_TYPES (+17 more)

### Community 56 - "StateWatcher"
Cohesion: 0.10
Nodes (3): _QueueEntry, StateWatcher, _Subscription

### Community 57 - "adf_to_markdown"
Cohesion: 0.12
Nodes (10): _adf_to_text(), _escape_jql_string(), JiraIncidentAdapter, adf_to_markdown(), _apply_marks(), _children(), _render(), _render_list() (+2 more)

### Community 58 - "AgentRegistry"
Cohesion: 0.10
Nodes (4): AgentConnection, AgentRegistry, agent_websocket_handler(), _heartbeat()

### Community 59 - "NodeInspector.tsx"
Cohesion: 0.13
Nodes (23): getClosedEvents(), ArchitectureEvent, ArgoCDOperation, ArchitectureGraph(), EVENT_LABELS, EventItem(), EventItemProps, healthTone() (+15 more)

### Community 61 - "reconcile.py"
Cohesion: 0.15
Nodes (10): sanitize_redis_port(), _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers(), main() (+2 more)

### Community 66 - "dependencies"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 68 - "FlowSnapshot"
Cohesion: 0.09
Nodes (8): api_info(), get_event_flow(), get_flow_history(), get_flow_metrics(), health_check(), list_agents(), spa_fallback(), FlowSnapshot

### Community 69 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 70 - "llm/__init__.py"
Cohesion: 0.17
Nodes (4): LLMChunk, LLMPort, LLMResponse, TokenUsage

### Community 71 - "claude-guard.js"
Cohesion: 0.14
Nodes (18): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+10 more)

### Community 72 - "http-handler.js"
Cohesion: 0.12
Nodes (18): getRemoteClustersMeta(), setupCLILogins(), setupRegistryCredentials(), { AGENT_CLI, AGENT_MODEL, DEFAULT_WORK_DIR, PORT, BRAIN_HTTP_URL }, { claudeMergeGuard }, { executeCLI }, fs, handleRequest() (+10 more)

### Community 73 - "TokenUtilizationPage.tsx"
Cohesion: 0.16
Nodes (17): recharts, getFlowHistory(), FlowSnapshot, ObservationSeries, FlowHistoryPage(), formatTime(), RANGES, SparkCard() (+9 more)

### Community 75 - "useCortexData.ts"
Cohesion: 0.23
Nodes (20): getCognitiveGraph(), getCortexActivity(), getKGServiceDetail(), getKGServices(), getRecentPulses(), CortexPage(), isOffRingCollection(), OffRingCollection (+12 more)

### Community 76 - "ArchitectureGraph.tsx"
Cohesion: 0.14
Nodes (17): @dagrejs/dagre, @xyflow/react, applyDagreLayout(), applyGridLayout(), applyLayout(), ArchitectureGraphInner(), buildGraph(), computeIdHash() (+9 more)

### Community 78 - "PulseBatch"
Cohesion: 0.12
Nodes (4): PulseBatch, PulsePort, PulseObserver, PulseTracker

### Community 80 - "handle_report_incident"
Cohesion: 0.10
Nodes (5): handle_report_incident(), _resolve_escalation_scope(), IdleTimeoutPort, IncidentAdapterPort, StateWatcherPort

### Community 81 - "devDependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 82 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 85 - "get_report"
Cohesion: 0.11
Nodes (6): get_report(), list_reports(), reports_spa_no_slash(), reports_spa_with_slash(), search_reports(), _serve_spa()

### Community 86 - "OpsStateContext.tsx"
Cohesion: 0.18
Nodes (16): getAgents(), getKargoStages(), AgentRegistryEntry, KargoStageStatus, AgentRegistryPanel(), formatConnectedSince(), AGENTS, EVIDENCE_SEVERITIES (+8 more)

### Community 87 - "catalog-skills.js"
Cohesion: 0.15
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 88 - "gemini-sidecar/package.json"
Cohesion: 0.11
Nodes (17): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+9 more)

### Community 92 - "ShiftsPage.tsx"
Cohesion: 0.23
Nodes (16): getCurrentShift(), getShiftDetail(), getShiftsList(), ShiftReportFull, ShiftReportSummary, FailedClusterBadge(), getISOWeek(), getWeekDates() (+8 more)

### Community 97 - "cortex/types.ts"
Cohesion: 0.17
Nodes (14): EventSource, KGServiceEntity, CortexGraphProps, GraphLoaderProps, PulseTimelineProps, CognitiveGraphResponse, CortexHeartbeatMessage, FrictionIndicator (+6 more)

### Community 99 - "generate_map.py"
Cohesion: 0.19
Nodes (6): _enumerate_gates(), _GateInfo, generate_phase_tool_map(), _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 101 - ".append_and_broadcast"
Cohesion: 0.22
Nodes (9): handle_message_agent(), handle_reply_to_agent(), _sticky_work_style(), handle_greenwave(), handle_notify_gitlab_result(), handle_search_open_incidents(), handle_transition_jira_issue(), handle_respond_to_jarvis() (+1 more)

### Community 103 - "ServiceNode.tsx"
Cohesion: 0.20
Nodes (11): HealthStatus, NodeType, AppNodeData, ARGOCD_HEALTH_COLORS, SYNC_ICONS, GENERIC_TAGS, HEALTH_COLORS, NODE_ICONS (+3 more)

### Community 104 - "observations_reporter.py"
Cohesion: 0.21
Nodes (7): _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), _sample_points(), _summarize()

### Community 114 - "NeuronInfoPanel.tsx"
Cohesion: 0.24
Nodes (12): KGServiceDetail, asNumber(), asString(), asStringArray(), Badge(), describeNeuron(), Hdr(), NeuronInfoPanel() (+4 more)

### Community 120 - "handle_notify_user_slack"
Cohesion: 0.18
Nodes (5): _alert_wrapper_retrigger(), handle_notify_user_slack(), _resolve_maintainer_enum(), _resolve_slack_user(), build_event_report_md()

### Community 121 - "_resolve_phase"
Cohesion: 0.22
Nodes (5): handle_re_trigger_aligner(), handle_set_phase(), _resolve_domain(), resolve_event_domain(), _resolve_phase()

### Community 122 - "is_defer_event_available"
Cohesion: 0.18
Nodes (6): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 123 - "cortex-constants.ts"
Cohesion: 0.18
Nodes (10): AGENTS, DOMAINS, HEMISPHERE_X, NEURON_DESCRIPTIONS, PHASE_SKILL_FOLDERS, PHASE_TOOL_PRIORITY, PHASES, StructuralEdge (+2 more)

### Community 124 - "CortexLiveFeed.tsx"
Cohesion: 0.27
Nodes (9): CortexHeartbeat(), CortexHeartbeatProps, ensureKeyframes(), CortexLiveFeed(), FILTER_PILLS, FilterKey, getStoredFilter(), MESSAGE_STYLES (+1 more)

### Community 126 - "SecurityError"
Cohesion: 0.24
Nodes (4): _check_security(), safe_execution(), wrapper(), SecurityError

### Community 127 - "vite.config.ts"
Cohesion: 0.20
Nodes (5): @tailwindcss/vite, @testing-library/react, vite, @vitejs/plugin-react, vitest

### Community 129 - "entity_extractor.py"
Cohesion: 0.33
Nodes (5): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship

### Community 130 - "has_unevaluated_close_blocker"
Cohesion: 0.20
Nodes (4): has_unevaluated_close_blocker(), _pred_jarvis_response(), _pred_unevaluated_close(), is_jarvis_acknowledgment()

### Community 131 - "knowledge_graph_api.py"
Cohesion: 0.31
Nodes (4): get_kg_store(), get_service_detail(), get_stats(), list_services()

### Community 132 - "get_quota_tracker"
Cohesion: 0.22
Nodes (3): get_quota_tracker(), llm_stats(), receive_telemetry()

### Community 146 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 147 - "validate-mutations.sh"
Cohesion: 0.73
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

## Knowledge Gaps
- **13 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+8 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2129 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **118 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `logging`, `queue.py`, `brain.py`, `Brain`, `list_shifts`, `_is_event_closed_or_missing`, `prompt.py`, `update_notebook_note`, `BrainSkillLoader`, `auth.py`, `slack.py`, `nightwatcher_tools.py`, `EventRepository`, `._restage_pending_signal`, `._stage_pending_signal`, `submit_feedback`, `ConversationTurn`, `._count_pending`, `._commit_pending_signal`, `create_schedule`, `._drain_pending`, `.drain_notes`, `LiveAPIAdapter`, `lifespan`, `FlowSnapshot`, `DashboardWSAdapter`, `get_report`, `observations_reporter.py`, `ScheduleRepository`, `HeadhunterJira`?**
  _High betweenness centrality (0.124) - this node is a cross-community bridge._
- **Are the 79 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 79 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.010898044427567876 - nodes in this community are weakly interconnected._
- **Why does `Brain` connect `Brain` to `BlackboardState`, `logging`, `brain.py`, `._run_agent_task`, `ReconcileScheduler`, `BrainSkillLoader`, `slack.py`, `agents/__init__.py`, `._process_with_llm`, `ConversationTurn`, `._build_contents`, `._build_system_prompt`, `StateWatcher`, `._close_and_broadcast`, `lifespan`, `PulseBatch`, `ReflexSearcher`, `DashboardWSAdapter`, `QuotaTracker`, `IdleTimeoutManager`?**
  _High betweenness centrality (0.082) - this node is a cross-community bridge._
- **Are the 20 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Should `logging` be split into smaller, more focused modules?**
  _Cohesion score 0.02332373508844097 - nodes in this community are weakly interconnected._