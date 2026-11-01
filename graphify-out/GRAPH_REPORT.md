# Graph Report - Blackboard  (2026-11-01)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 4880 nodes · 10883 edges · 206 communities (94 shown, 112 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 927 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `bbfa6973`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BlackboardState
- client.ts
- models.py
- logging
- EventSidebar.tsx
- react
- os
- tool_gates.py
- Brain
- EventDocument
- merge-guard.js
- ReconcileScheduler
- credentials.js
- jenkins-mcp.js
- dependencies.py
- ._run_agent_task
- App.tsx
- useMemory.ts
- agents/__init__.py
- AgentRegistry
- TurnBubble.tsx
- ToolContext
- _BrainToolContext
- GitLabPlatform
- brain.py
- nightwatcher_tools.py
- WorkspaceInspector.tsx
- KnowledgeGraphStore
- jenkins_observer.py
- observations_mgmt.py
- handlers_integration.py
- cli-executor.js
- EventRepository
- JenkinsAdapter
- storage-recycler.js
- ._process_with_llm
- GitHubPlatform
- ConversationTurn
- JenkinsObserver
- Aligner
- EventEvidence
- ws-client.js
- TimeKeeperPage.tsx
- ActiveStreamsContext.tsx
- .get_event
- main.py
- Headhunter
- .get_service
- ui/package.json
- get_archivist
- queue.py
- NodeInspector.tsx
- useCortexData.ts
- server.js
- auth.py
- CortexGraph.tsx
- LiveAPIAdapter
- Archivist
- StateWatcher
- SlackChannel
- adf_to_markdown
- GeminiAdapter
- state/__init__.py
- ._gate_check
- ArgoCDObserver
- create_schedule
- llm/__init__.py
- BrainSkillLoader
- ._get_manager
- cognitive_graph.py
- KargoObserver
- TopologyRepository
- dependencies
- ArchitectureGraph.tsx
- TokenUtilizationPage.tsx
- formatter.py
- GitHubAppAuth
- EventHistory.tsx
- cortex/types.ts
- compilerOptions
- claude-guard.js
- http-handler.js
- ._build_system_prompt
- reconcile.py
- EphemeralProvisioner
- VcsPlatformPort
- PulseBatch
- get_brain
- EventDrillDown.tsx
- ReflexSearcher
- tool_router.py
- devDependencies
- compilerOptions
- ServiceNode.tsx
- DashboardWSAdapter
- get_report
- ScheduleCreateRequest
- catalog-skills.js
- gemini-sidecar/package.json
- VectorStore
- ObservationRepository
- ShiftsPage.tsx
- ClaudeAdapter
- list_active_events
- generate_map.py
- OIDCKeyAdapter
- KubernetesSpawnHealthAdapter
- IdleTimeoutManager
- src/ports.py
- ._discover
- EscalationRepository
- QuotaTracker
- ._send_turn_to_thread
- ScheduleRepository
- FilterRule
- .scroll
- ._extract_context_flags
- handle_report_incident
- HeadhunterJira
- TokenMeter
- NightwatcherObserver
- MultiInstallationManager
- NeuronInfoPanel.tsx
- ._github_poll_and_process
- SlackAccessGate
- CortexLiveFeed.tsx
- is_defer_event_available
- cortex-constants.ts
- _md_table_to_text
- vite.config.ts
- _resolve_phase
- has_unevaluated_close_blocker
- get_quota_tracker
- SpawnPollResult
- SmartsheetMaintainerCache
- .has_reeval_signal
- create_chat_event
- get_current_shift
- AsyncGitHubClient
- GitLabTokenAuth
- _is_event_closed_or_missing
- get_kg_store
- TimeKeeperObserver
- CortexRepository
- BrainIntrospectionPort
- get_all_journal
- update_notebook_note
- scripts
- validate-mutations.sh
- ._process_message
- ._evaluate_health
- ._cleanup_stale_events
- SpawnStatus
- list_failed_stages
- dex_proxy
- ._wait_for_registration
- submit_feedback
- delete_notebook_note
- require-results.sh
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
- _parse_drain_timeout
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

## Communities (206 total, 112 thin omitted)

### Community 0 - "BlackboardState"
Cohesion: 0.01
Nodes (4): get_notebook(), get_event_observations(), get_global_observations(), BlackboardState

### Community 1 - "client.ts"
Cohesion: 0.03
Nodes (108): @tanstack/react-query, ApiError, bulkDeleteObservations(), deleteNote(), deleteObservation(), exportObservations(), ExtractionResult, fetchApi() (+100 more)

### Community 2 - "models.py"
Cohesion: 0.03
Nodes (33): AppNode, ArchitectureEvent, ChatRequest, ChatResponse, ConversationMessage, EventInput, EventMetrics, EventStatus (+25 more)

### Community 3 - "logging"
Cohesion: 0.04
Nodes (5): get_blackboard(), build_manifest_table(), build_system_prompt(), extract_event_links(), list_shifts()

### Community 4 - "EventSidebar.tsx"
Cohesion: 0.05
Nodes (70): getHeadhunterPending(), HeadhunterTodo, ReportFull, ReportMeta, DeferCountdownBar(), GridTile(), Props, col (+62 more)

### Community 5 - "react"
Cohesion: 0.05
Nodes (71): lucide-react, react, react-router-dom, createChatEvent(), getAgents(), getKargoStages(), AgentRegistryEntry, KargoStageStatus (+63 more)

### Community 6 - "os"
Cohesion: 0.04
Nodes (22): _get_static_maintainer_emails(), _get_allowed_mention_authors(), _get_static_maintainer_emails(), _safe_int(), create_adapter(), record_token_usage(), can_append_message(), list_incidents() (+14 more)

### Community 7 - "tool_gates.py"
Cohesion: 0.05
Nodes (78): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+70 more)

### Community 9 - "EventDocument"
Cohesion: 0.03
Nodes (12): _close_unanswered_fc(), _build_closed_block(), build_event_header(), _build_identity_block(), _build_journal_block(), _build_mermaid_block(), _build_related_block(), _build_subject_block() (+4 more)

### Community 10 - "merge-guard.js"
Cohesion: 0.05
Nodes (69): analyzeString(), analyzeTokens(), API_VALUED, apiTokens(), apiWriteNeedsGuard(), assignName(), bareBranchProtected(), base() (+61 more)

### Community 11 - "ReconcileScheduler"
Cohesion: 0.04
Nodes (7): FlowCollector, FairQueue, ReconcileScheduler, Trigger, QueueTrigger, ResyncTrigger, StalenessGuard

### Community 12 - "credentials.js"
Cohesion: 0.07
Nodes (59): is429Error(), { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync } (+51 more)

### Community 13 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 14 - "dependencies.py"
Cohesion: 0.04
Nodes (19): set_incident_options(), set_oidc_adapter(), get_aligner(), get_architect(), get_argocd_observer(), get_developer(), get_kargo_observer(), get_report_client() (+11 more)

### Community 15 - "._run_agent_task"
Cohesion: 0.06
Nodes (8): on_huddle(), on_progress(), on_huddle(), on_progress(), _compute_processed_up_to(), _sanitize_error_text(), _sanitize_override_reason(), get_registry_and_bridge()

### Community 16 - "App.tsx"
Cohesion: 0.06
Nodes (46): oidc-client-ts, react-dom, dismissProposals(), EnhancementProposal, getConfig(), getHandoffReports(), getProposals(), getWSAuthFailureCallback() (+38 more)

### Community 17 - "useMemory.ts"
Cohesion: 0.07
Nodes (50): applyLessons(), correctMemory(), createKnowledge(), createLesson(), deleteKnowledge(), deleteLesson(), ExtractedCorrection, ExtractedLesson (+42 more)

### Community 18 - "agents/__init__.py"
Cohesion: 0.06
Nodes (8): Architect, AgentClient, Developer, _check_security(), safe_execution(), wrapper(), SecurityError, SysAdmin

### Community 19 - "AgentRegistry"
Cohesion: 0.06
Nodes (13): AgentConnection, AgentRegistry, agent_websocket_handler(), _heartbeat(), _build_prompt(), consume_wake_task(), _consume(), _dispatch_timeout_s() (+5 more)

### Community 20 - "TurnBubble.tsx"
Cohesion: 0.08
Nodes (40): @uiw/react-markdown-preview, approveEvent(), closeEvent(), enforceCasualDomain(), rejectEvent(), submitFeedback(), CollapsibleSection(), CollapsibleSectionProps (+32 more)

### Community 21 - "ToolContext"
Cohesion: 0.08
Nodes (11): handle_message_agent(), handle_reply_to_agent(), handle_select_agent(), _sticky_work_style(), handle_classify_event(), handle_defer_event(), handle_hold_watch(), handle_respond_to_jarvis() (+3 more)

### Community 24 - "brain.py"
Cohesion: 0.07
Nodes (17): _apply_sibling_signature(), build_function_response(), build_single_function_response(), compress_contents(), estimate_msg_tokens(), estimate_tokens(), extract_model_parts(), normalize_response_parts() (+9 more)

### Community 25 - "nightwatcher_tools.py"
Cohesion: 0.08
Nodes (23): PulseContext, ShiftIncident, ShiftInvestigation, build_report_iteration_prompt(), build_summary_prompt(), extract_full_links(), _normalize_gitlab_host(), build_extend_tool() (+15 more)

### Community 26 - "WorkspaceInspector.tsx"
Cohesion: 0.08
Nodes (40): CiContext, ConversationTurn, EventEvidence, TokenUsageDict, CiContextCard(), CiContextCardProps, ConsoleTailBlock(), FailedJobRow() (+32 more)

### Community 27 - "KnowledgeGraphStore"
Cohesion: 0.08
Nodes (9): _format_graph_context(), get_graph_context(), _parse_props(), _sanitize(), translate_to_lookups(), _acquire(), KnowledgeGraphStore, _sanitize() (+1 more)

### Community 28 - "jenkins_observer.py"
Cohesion: 0.06
Nodes (16): _annotation_replace(), _strip_pipeline_annotations(), _clamp_confidence(), _env_flag(), _parse_job_metadata(), _prepare_console_tail(), _redact_build_parameters(), _redact_match() (+8 more)

### Community 30 - "observations_mgmt.py"
Cohesion: 0.07
Nodes (17): _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), render_pdf(), _sample_points(), _summarize() (+9 more)

### Community 31 - "handlers_integration.py"
Cohesion: 0.08
Nodes (19): _alert_wrapper_retrigger(), _do_retrigger(), _get_jira_reporter(), handle_notify_user_slack(), handle_refresh_github_context(), handle_refresh_gitlab_context(), handle_refresh_kargo_context(), _is_darwin_reentrant_caller() (+11 more)

### Community 32 - "cli-executor.js"
Cohesion: 0.09
Nodes (36): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS, STORAGE_PRETASK_TIMEOUT_MS, resolveStorageRoot }, buildCLICommand(), { checkAndRecycleStorage, pinTaskCwd, unpinTaskCwd }, CLAUDE_JSON_PATH, cp, executeCLI(), executeCLIStreaming(), FALLBACK_MODEL (+28 more)

### Community 34 - "JenkinsAdapter"
Cohesion: 0.06
Nodes (6): BuildDetails, JenkinsAdapter, JenkinsPlatformPort, JobResult, JobRunState, ViewScanResult

### Community 35 - "storage-recycler.js"
Cohesion: 0.09
Nodes (32): withTaskStorage(), resolveStorageRoot(), ROLE_TIMEOUTS, STORAGE_ACTIVITY_HEARTBEAT_MS, STORAGE_MAX_TIER3_DELETIONS, STORAGE_PRETASK_TIMEOUT_MS, STORAGE_RESULTS_TTL_MS, STORAGE_STALE_MS (+24 more)

### Community 38 - "ConversationTurn"
Cohesion: 0.16
Nodes (26): emit_tool_result(), handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_recall_pruned_turns(), handle_ask_release_ai(), handle_comment_jira_issue(), handle_fetch_jira_issue() (+18 more)

### Community 41 - "EventEvidence"
Cohesion: 0.08
Nodes (8): _sanitize_lesson_text(), Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship, EventEvidence, _load_name_mapping()

### Community 42 - "ws-client.js"
Cohesion: 0.08
Nodes (27): { AGENT_ROLE }, _blackboardTurns, _inboundMessages, _teammateMessages, {
  DEFAULT_WORK_DIR, AGENT_CLI, AGENT_MODEL, AGENT_ROLE,
  EVENT_ID, EPHEMERAL, IDLE_TIMEOUT_MS,
  CLI_429_MAX_RETRIES, CLI_429_INITIAL_DELAY_MS, CLI_429_BACKOFF_MULTIPLIER,
}, { ensureEventDocument }, { executeCLIStreaming, prepareResultsDir, is429Error }, { filterSkillsByRole, filterSkillsByMode, swapActiveRules, restoreAllSkills } (+19 more)

### Community 43 - "TimeKeeperPage.tsx"
Cohesion: 0.12
Nodes (24): createSchedule(), deleteSchedule(), getSchedules(), refineInstructions(), ScheduleCreatePayload, ScheduleItem, toggleSchedule(), updateSchedule() (+16 more)

### Community 44 - "ActiveStreamsContext.tsx"
Cohesion: 0.12
Nodes (28): AgentStreamCard(), AgentStreamCardProps, FloatingWindow(), MessageCards(), Dashboard(), GridTile(), GridTileProps, TileType (+20 more)

### Community 45 - ".get_event"
Cohesion: 0.07
Nodes (8): get_token_meter(), report_tampering(), close_event_by_user(), get_event_approval(), get_event_document(), get_event_report(), get_event_turns(), rebuild_deep_memory()

### Community 46 - "main.py"
Cohesion: 0.08
Nodes (13): agent_ws_endpoint(), api_info(), get_config(), get_event_flow(), get_flow_history(), get_flow_metrics(), health_check(), list_agents() (+5 more)

### Community 48 - ".get_service"
Cohesion: 0.08
Nodes (6): get_event_document(), list_events(), get_mermaid_diagram(), get_service_details(), get_topology(), list_services()

### Community 49 - "ui/package.json"
Cohesion: 0.08
Nodes (29): autoprefixer, cronstrue, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, graphology-layout-forceatlas2 (+21 more)

### Community 50 - "get_archivist"
Cohesion: 0.08
Nodes (14): get_archivist(), get_cognitive_graph(), aligner_pending_items(), delete_knowledge(), delete_lesson(), demote_lesson(), get_knowledge(), get_lesson() (+6 more)

### Community 51 - "queue.py"
Cohesion: 0.11
Nodes (17): apply_lessons(), CloseRequest, correct_memory(), CorrectMemoryRequest, create_knowledge(), create_lesson(), enforce_casual_domain(), EnforceCasualRequest (+9 more)

### Community 52 - "NodeInspector.tsx"
Cohesion: 0.11
Nodes (25): getClosedEvents(), getEvents(), ArchitectureEvent, ArgoCDOperation, ActivityStream(), EVENT_LABELS, EventItem(), EventItemProps (+17 more)

### Community 53 - "useCortexData.ts"
Cohesion: 0.17
Nodes (27): getCognitiveGraph(), getCortexActivity(), getEventReport(), getKGServiceDetail(), getKGServices(), getKGStats(), getKnowledgeById(), getMemory() (+19 more)

### Community 54 - "server.js"
Cohesion: 0.08
Nodes (21): hasRegistryCredentials(), { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, ensureEventDocument(), fs, path, stageEventDocument(), fetchEventDocument(), fs (+13 more)

### Community 55 - "auth.py"
Cohesion: 0.11
Nodes (11): can_approve_event(), can_override_domain(), _claims_to_user(), get_user_from_request(), get_user_from_slack(), get_user_from_websocket(), _normalize_email(), require_auth() (+3 more)

### Community 56 - "CortexGraph.tsx"
Cohesion: 0.13
Nodes (26): graphology, eventColor(), getExecutiveNeurons(), getStructuralEdges(), DEFAULT_TYPE_BUDGET, evictLru(), KNOWLEDGE_RING, KNOWLEDGE_RING_TYPES (+18 more)

### Community 59 - "StateWatcher"
Cohesion: 0.10
Nodes (3): _QueueEntry, StateWatcher, _Subscription

### Community 61 - "adf_to_markdown"
Cohesion: 0.12
Nodes (10): _adf_to_text(), _escape_jql_string(), JiraIncidentAdapter, adf_to_markdown(), _apply_marks(), _children(), _render(), _render_list() (+2 more)

### Community 63 - "state/__init__.py"
Cohesion: 0.11
Nodes (4): sanitize_redis_port(), close_redis(), get_redis(), RedisClient

### Community 64 - "._gate_check"
Cohesion: 0.15
Nodes (9): format_event_summary(), handle_app_home_opened(), handle_app_mention(), handle_approve(), handle_create_event_modal(), handle_darwin_command(), handle_home_create_event(), handle_reject() (+1 more)

### Community 66 - "create_schedule"
Cohesion: 0.08
Nodes (5): create_schedule(), delete_schedule(), get_schedule(), list_schedules(), toggle_schedule()

### Community 67 - "llm/__init__.py"
Cohesion: 0.16
Nodes (5): FunctionCall, LLMChunk, LLMPort, LLMResponse, TokenUsage

### Community 70 - "cognitive_graph.py"
Cohesion: 0.12
Nodes (10): get_pulse_tracker(), dismiss_proposals(), DismissRequest, get_all_shadow_interventions(), get_cortex_activity(), get_cortex_status(), get_event_shadow_interventions(), get_handoff_reports() (+2 more)

### Community 73 - "dependencies"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 74 - "ArchitectureGraph.tsx"
Cohesion: 0.12
Nodes (20): @dagrejs/dagre, applyDagreLayout(), applyGridLayout(), applyLayout(), ArchitectureGraph(), ArchitectureGraphInner(), buildGraph(), computeIdHash() (+12 more)

### Community 75 - "TokenUtilizationPage.tsx"
Cohesion: 0.15
Nodes (18): recharts, getFlowHistory(), FlowSnapshot, ObservationSeries, FlowHistoryPage(), formatTime(), RANGES, SparkCard() (+10 more)

### Community 76 - "formatter.py"
Cohesion: 0.13
Nodes (10): build_access_denied_home_view(), build_home_tab_view(), _context_line(), create_feedback_block(), format_plan_block(), format_task_card(), format_turn(), resolve_source_emoji() (+2 more)

### Community 78 - "EventHistory.tsx"
Cohesion: 0.15
Nodes (19): getReport(), getReports(), CompactCardStrip(), EventHistory(), TimeRange, ViewMode, EventHistoryGrid(), EventHistoryTable() (+11 more)

### Community 79 - "cortex/types.ts"
Cohesion: 0.15
Nodes (20): EventSource, devQueryClient, CortexLiveFeedProps, EventDrillDownProps, MOCK_CORTEX_STATUS, MOCK_EVENT_ID, MOCK_NEURONS, MOCK_PULSE_BATCHES (+12 more)

### Community 80 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 81 - "claude-guard.js"
Cohesion: 0.14
Nodes (18): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+10 more)

### Community 82 - "http-handler.js"
Cohesion: 0.12
Nodes (18): getRemoteClustersMeta(), setupCLILogins(), setupRegistryCredentials(), { AGENT_CLI, AGENT_MODEL, DEFAULT_WORK_DIR, PORT, BRAIN_HTTP_URL }, { claudeMergeGuard }, { executeCLI }, fs, handleRequest() (+10 more)

### Community 83 - "._build_system_prompt"
Cohesion: 0.10
Nodes (3): _init_tool_names(), _strip_tool_names(), _wrap_section()

### Community 84 - "reconcile.py"
Cohesion: 0.18
Nodes (9): _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers(), main(), _parse_frontmatter() (+1 more)

### Community 87 - "PulseBatch"
Cohesion: 0.12
Nodes (4): PulseBatch, PulsePort, PulseObserver, PulseTracker

### Community 88 - "get_brain"
Cohesion: 0.13
Nodes (7): resolve_approval_identity(), get_brain(), approve_event(), _github_active_item(), headhunter_pending_todos(), reject_event(), update_plan_step()

### Community 89 - "EventDrillDown.tsx"
Cohesion: 0.16
Nodes (15): three, getEventPulses(), KGServiceEntity, BrainCore(), CortexDevPage(), CortexGraphProps, GraphLoaderProps, EventDrillDown() (+7 more)

### Community 91 - "tool_router.py"
Cohesion: 0.12
Nodes (5): _safe_int(), handle_consult_deep_memory(), handle_google_web_search(), IdleTimeoutPort, StateWatcherPort

### Community 92 - "devDependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 93 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 94 - "ServiceNode.tsx"
Cohesion: 0.15
Nodes (13): @xyflow/react, HealthStatus, NodeType, AppNodeData, ARGOCD_HEALTH_COLORS, SYNC_ICONS, NamespaceGroupNodeData, GENERIC_TAGS (+5 more)

### Community 96 - "get_report"
Cohesion: 0.11
Nodes (6): get_report(), list_reports(), reports_spa_no_slash(), reports_spa_with_slash(), search_reports(), _serve_spa()

### Community 98 - "catalog-skills.js"
Cohesion: 0.15
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 99 - "gemini-sidecar/package.json"
Cohesion: 0.11
Nodes (17): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+9 more)

### Community 103 - "ShiftsPage.tsx"
Cohesion: 0.23
Nodes (16): getCurrentShift(), getShiftDetail(), getShiftsList(), ShiftReportFull, ShiftReportSummary, FailedClusterBadge(), getISOWeek(), getWeekDates() (+8 more)

### Community 106 - "list_active_events"
Cohesion: 0.12
Nodes (6): _defer_timeline_fields(), _has_active_subscription(), list_active_events(), list_closed_events(), list_waiting_approval_events(), _serialize_evidence()

### Community 107 - "generate_map.py"
Cohesion: 0.19
Nodes (6): _enumerate_gates(), _GateInfo, generate_phase_tool_map(), _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 116 - "._send_turn_to_thread"
Cohesion: 0.18
Nodes (4): extract_tables(), get_agent_notification_text(), get_turn_attachment_color(), table_block_to_code_block()

### Community 120 - "._extract_context_flags"
Cohesion: 0.15
Nodes (3): compute_dispatch_backpressure(), ContextFlags, _safe_int_env()

### Community 121 - "handle_report_incident"
Cohesion: 0.15
Nodes (4): handle_report_incident(), _resolve_escalation_scope(), handle_search_open_incidents(), IncidentAdapterPort

### Community 126 - "NeuronInfoPanel.tsx"
Cohesion: 0.24
Nodes (12): KGServiceDetail, asNumber(), asString(), asStringArray(), Badge(), describeNeuron(), Hdr(), NeuronInfoPanel() (+4 more)

### Community 132 - "CortexLiveFeed.tsx"
Cohesion: 0.24
Nodes (10): CortexHeartbeat(), CortexHeartbeatProps, ensureKeyframes(), CortexLiveFeed(), FILTER_PILLS, FilterKey, getStoredFilter(), MESSAGE_STYLES (+2 more)

### Community 133 - "is_defer_event_available"
Cohesion: 0.18
Nodes (6): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 134 - "cortex-constants.ts"
Cohesion: 0.18
Nodes (10): AGENTS, DOMAINS, HEMISPHERE_X, NEURON_DESCRIPTIONS, PHASE_SKILL_FOLDERS, PHASE_TOOL_PRIORITY, PHASES, StructuralEdge (+2 more)

### Community 135 - "_md_table_to_text"
Cohesion: 0.20
Nodes (5): _replace(), _md_table_to_block_kit(), _md_table_to_text(), _md_to_mrkdwn(), _parse_md_table()

### Community 136 - "vite.config.ts"
Cohesion: 0.20
Nodes (5): @tailwindcss/vite, @testing-library/react, vite, @vitejs/plugin-react, vitest

### Community 138 - "_resolve_phase"
Cohesion: 0.24
Nodes (3): handle_set_phase(), resolve_event_domain(), _resolve_phase()

### Community 139 - "has_unevaluated_close_blocker"
Cohesion: 0.20
Nodes (4): has_unevaluated_close_blocker(), _pred_jarvis_response(), _pred_unevaluated_close(), is_jarvis_acknowledgment()

### Community 140 - "get_quota_tracker"
Cohesion: 0.22
Nodes (3): get_quota_tracker(), llm_stats(), receive_telemetry()

### Community 144 - "create_chat_event"
Cohesion: 0.25
Nodes (3): ChatEventRequest, ChatEventResponse, create_chat_event()

### Community 150 - "get_kg_store"
Cohesion: 0.32
Nodes (4): get_kg_store(), get_service_detail(), get_stats(), list_services()

### Community 158 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 159 - "validate-mutations.sh"
Cohesion: 0.73
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

## Knowledge Gaps
- **13 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+8 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2130 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **112 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `models.py`, `logging`, `os`, `Brain`, `EventDocument`, `_resolve_phase`, `dependencies.py`, `create_chat_event`, `get_current_shift`, `_is_event_closed_or_missing`, `brain.py`, `nightwatcher_tools.py`, `jenkins_observer.py`, `get_all_journal`, `observations_mgmt.py`, `update_notebook_note`, `ConversationTurn`, `EventEvidence`, `submit_feedback`, `.__init__`, `main.py`, `.get_event`, `.get_service`, `delete_notebook_note`, `get_archivist`, `queue.py`, `LiveAPIAdapter`, `state/__init__.py`, `create_schedule`, `get_brain`, `tool_router.py`, `DashboardWSAdapter`, `get_report`, `ScheduleCreateRequest`, `list_active_events`, `ScheduleRepository`, `HeadhunterJira`, `NightwatcherObserver`?**
  _High betweenness centrality (0.103) - this node is a cross-community bridge._
- **Are the 79 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 79 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.013267651888341543 - nodes in this community are weakly interconnected._
- **Why does `EventEvidence` connect `EventEvidence` to `BlackboardState`, `models.py`, `logging`, `os`, `Brain`, `EventDocument`, `create_chat_event`, `_is_event_closed_or_missing`, `GitLabPlatform`, `brain.py`, `TimeKeeperObserver`, `Any`, `jenkins_observer.py`, `EventRepository`, `GitHubPlatform`, `JenkinsObserver`, `Aligner`, `queue.py`, `LiveAPIAdapter`, `Archivist`, `SlackChannel`, `._gate_check`, `DashboardWSAdapter`, `list_active_events`, `HeadhunterJira`?**
  _High betweenness centrality (0.048) - this node is a cross-community bridge._
- **Are the 20 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Should `client.ts` be split into smaller, more focused modules?**
  _Cohesion score 0.03262092238470191 - nodes in this community are weakly interconnected._