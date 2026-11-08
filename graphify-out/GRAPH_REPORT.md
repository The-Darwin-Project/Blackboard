# Graph Report - Blackboard  (2026-11-08)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 5069 nodes · 11295 edges · 214 communities (99 shown, 115 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 938 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `2af4f011`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BlackboardState
- client.ts
- logging
- EventChatPanel.tsx
- models.py
- Brain
- EventEvidence
- brain.py
- main.py
- EventDocument
- App.tsx
- tool_gates.py
- ._run_agent_task
- EventSidebar.tsx
- AgentRegistry
- ReconcileScheduler
- colors.ts
- http-handler.js
- Archivist
- jenkins-mcp.js
- BrainSkillLoader
- jenkins_observer.py
- nightwatcher_tools.py
- react
- fetchApi
- _BrainToolContext
- merge-guard.js
- KnowledgeGraphStore
- observations_mgmt.py
- ui/package.json
- .get_service
- ._process_with_llm
- EventRepository
- cli-executor.js
- queue.py
- storage-recycler.js
- handlers_integration.py
- JenkinsAdapter
- ArchitectureGraph.tsx
- EventDrillDown.tsx
- Aligner
- ConversationTurn
- GitHubPlatform
- lucide-react
- CortexGraph.tsx
- ToolContext
- GitLabPlatform
- AgentClient
- TimeKeeperPage.tsx
- gemini_client.py
- formatter.py
- ScheduleRepository
- Headhunter
- ws-client.js
- useCortexData.ts
- ActiveStreamsContext.tsx
- VectorStore
- get_archivist
- server.js
- .get_event
- LiveAPIAdapter
- StateWatcher
- ArgoCDObserver
- NodeInspector.tsx
- tool_router.py
- ._get_manager
- GeminiAdapter
- NightwatcherObserver
- KargoObserver
- TopologyRepository
- dependencies
- quota_tracker.py
- jira_incident.py
- cognitive_graph.py
- GitHubAppAuth
- compilerOptions
- claude-guard.js
- reconcile.py
- cli-setup.js
- TokenUtilizationPage.tsx
- VcsPlatformPort
- PulseBatch
- DashboardWSAdapter
- .archive_event
- ReflexSearcher
- handle_select_agent
- UserContext
- SlackChannel
- devDependencies
- compilerOptions
- EphemeralProvisioner
- get_report
- NeuronInfoPanel.tsx
- gemini-sidecar/package.json
- ObservationRepository
- catalog-skills.js
- OIDCKeyAdapter
- ClaudeAdapter
- get
- EscalationRepository
- DeferCountdownBar.tsx
- list_active_events
- generate_map.py
- approve_event
- KubernetesSpawnHealthAdapter
- IdleTimeoutManager
- JenkinsObserver
- _append_user_turn
- analyzeTokens
- FilterRule
- BrainLifecyclePort
- TokenMeter
- ._send_turn_to_thread
- .list_observations
- MultiInstallationManager
- HeadhunterJira
- nightwatcher_prompt.py
- SlackAccessGate
- is_defer_event_available
- CiContextCard.tsx
- CortexLiveFeed.tsx
- spawn_health.py
- gitGuard
- parseShell
- ._extract_context_flags
- ._post_agent_recall
- ._process_candidates
- ._triage_and_build_evidence
- ._drain_once
- has_unevaluated_close_blocker
- Any
- knowledge_graph_api.py
- SecurityError
- classifyTool
- get_quota_tracker
- SpawnPollResult
- SmartsheetMaintainerCache
- .has_reeval_signal
- ._register_handlers
- list_shifts
- AsyncGitHubClient
- GitLabTokenAuth
- _is_event_closed_or_missing
- ._evaluate_health
- get_token_meter
- TimeKeeperObserver
- CortexRepository
- adf_to_markdown
- validate-mutations.sh
- update_notebook_note
- scripts
- state.js
- ._process_message
- DispatchMetrics
- format_jira_for_llm
- list_failed_stages
- ._wait_for_registration
- agent_ws_endpoint
- _resolve_domain
- classify
- derive_llm_priority
- headhunter_pending_todos
- require-results.sh
- _WSFrameFilter
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
1. `BlackboardState` - 285 edges
2. `Brain` - 151 edges
3. `ConversationTurn` - 123 edges
4. `ToolContext` - 103 edges
5. `GateContext` - 94 edges
6. `react` - 82 edges
7. `EventDocument` - 79 edges
8. `fetchApi()` - 66 edges
9. `lifespan()` - 65 edges
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

## Communities (214 total, 115 thin omitted)

### Community 0 - "BlackboardState"
Cohesion: 0.01
Nodes (10): get_all_journal(), get_service_journal(), delete_notebook_note(), get_notebook(), create_schedule(), delete_schedule(), get_schedule(), list_schedules() (+2 more)

### Community 1 - "client.ts"
Cohesion: 0.03
Nodes (103): @tanstack/react-query, ApiError, bulkDeleteObservations(), deleteNote(), deleteObservation(), exportObservations(), ExtractedCorrection, ExtractedLesson (+95 more)

### Community 2 - "logging"
Cohesion: 0.04
Nodes (20): _get_static_maintainer_emails(), _get_allowed_mention_authors(), _get_static_maintainer_emails(), _safe_int(), get_blackboard(), dex_proxy(), list_incidents(), approve_mission() (+12 more)

### Community 3 - "EventChatPanel.tsx"
Cohesion: 0.05
Nodes (78): getActiveEvents(), getAlignerPending(), getEventDocument(), getEvents(), getJenkinsPending(), getWaitingApprovalEvents(), updateEventTitle(), EventDocument (+70 more)

### Community 4 - "models.py"
Cohesion: 0.04
Nodes (33): AppNode, ArchitectureEvent, ChatRequest, ChatResponse, ConversationMessage, EventInput, EventMetrics, EventStatus (+25 more)

### Community 6 - "EventEvidence"
Cohesion: 0.04
Nodes (26): _sanitize_lesson_text(), generate_event_title(), get_adapter(), _get_semaphore(), spawn_event_namer_task(), can_append_message(), can_rename_event(), get_user_from_slack() (+18 more)

### Community 7 - "brain.py"
Cohesion: 0.04
Nodes (15): _apply_sibling_signature(), build_function_response(), build_single_function_response(), compress_contents(), estimate_msg_tokens(), estimate_tokens(), extract_model_parts(), normalize_response_parts() (+7 more)

### Community 8 - "main.py"
Cohesion: 0.04
Nodes (24): Architect, set_incident_options(), SysAdmin, get_aligner(), get_architect(), get_argocd_observer(), get_developer(), get_kargo_observer() (+16 more)

### Community 9 - "EventDocument"
Cohesion: 0.03
Nodes (15): _close_unanswered_fc(), ContextFlags, _resolve_escalation_scope(), _build_closed_block(), build_event_header(), _build_identity_block(), _build_journal_block(), _build_mermaid_block() (+7 more)

### Community 10 - "App.tsx"
Cohesion: 0.05
Nodes (62): oidc-client-ts, react-dom, react-router-dom, dismissProposals(), EnhancementProposal, getConfig(), getHandoffReports(), getProposals() (+54 more)

### Community 11 - "tool_gates.py"
Cohesion: 0.05
Nodes (78): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+70 more)

### Community 12 - "._run_agent_task"
Cohesion: 0.05
Nodes (10): on_huddle(), on_progress(), on_huddle(), on_progress(), _compute_processed_up_to(), _is_automated_nudge(), _sanitize_error_text(), _sanitize_override_reason() (+2 more)

### Community 13 - "EventSidebar.tsx"
Cohesion: 0.08
Nodes (59): getHeadhunterPending(), getJiraMissions(), HeadhunterTodo, postJiraAction(), AgentRegistryEntry, ACTION_BADGE, formatAge(), HeadhunterQueuePanel() (+51 more)

### Community 14 - "AgentRegistry"
Cohesion: 0.06
Nodes (14): AgentConnection, AgentRegistry, agent_websocket_handler(), _heartbeat(), _build_prompt(), _check_security(), consume_wake_task(), _consume() (+6 more)

### Community 15 - "ReconcileScheduler"
Cohesion: 0.04
Nodes (7): FlowCollector, FairQueue, ReconcileScheduler, Trigger, QueueTrigger, ResyncTrigger, StalenessGuard

### Community 16 - "colors.ts"
Cohesion: 0.07
Nodes (40): getReport(), getReports(), ReportFull, ReportMeta, SubjectType, CompactCardStrip(), EventHistory(), TimeRange (+32 more)

### Community 17 - "http-handler.js"
Cohesion: 0.09
Nodes (58): resolveCommand(), writeAgyMcpServer(), writeClaudeMcpServer(), buildArgoCDMcpConfig(), createAppJWT(), discoverAndGenerateTokens(), _discoverAndGenerateTokensInner(), discoverInstallations() (+50 more)

### Community 19 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 20 - "BrainSkillLoader"
Cohesion: 0.05
Nodes (4): BrainSkillLoader, _SkillCorpus, _wrap_section(), BrainIntrospectionPort

### Community 21 - "jenkins_observer.py"
Cohesion: 0.06
Nodes (20): _annotation_replace(), _strip_pipeline_annotations(), _clamp_confidence(), _parse_job_metadata(), _prepare_console_tail(), _redact_match(), _redact_secrets_in_text(), _sanitize_analysis_text() (+12 more)

### Community 22 - "nightwatcher_tools.py"
Cohesion: 0.07
Nodes (23): PulseContext, ShiftIncident, ShiftInvestigation, build_summary_prompt(), extract_full_links(), build_extend_tool(), build_report_tool(), build_summary_tool() (+15 more)

### Community 23 - "react"
Cohesion: 0.09
Nodes (41): react, @uiw/react-markdown-preview, approveEvent(), closeEvent(), enforceCasualDomain(), getEventReport(), rejectEvent(), submitFeedback() (+33 more)

### Community 24 - "fetchApi"
Cohesion: 0.09
Nodes (47): applyLessons(), correctMemory(), createKnowledge(), createLesson(), deleteKnowledge(), deleteLesson(), extractLessons(), fetchApi() (+39 more)

### Community 26 - "merge-guard.js"
Cohesion: 0.04
Nodes (46): API_VALUED, ARGO_MUTATING, ARGO_READ_SUB, ARGO_READ_TOP, BODY_FLAG, BROWSER_READ, CTX, ENV_BUILTINS (+38 more)

### Community 27 - "KnowledgeGraphStore"
Cohesion: 0.08
Nodes (9): _format_graph_context(), get_graph_context(), _parse_props(), _sanitize(), translate_to_lookups(), _acquire(), KnowledgeGraphStore, _sanitize() (+1 more)

### Community 28 - "observations_mgmt.py"
Cohesion: 0.06
Nodes (18): get_report_client(), _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), render_pdf(), _sample_points() (+10 more)

### Community 29 - "ui/package.json"
Cohesion: 0.05
Nodes (37): autoprefixer, cronstrue, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, graphology-layout-forceatlas2 (+29 more)

### Community 30 - ".get_service"
Cohesion: 0.06
Nodes (6): get_event_document(), list_events(), get_mermaid_diagram(), get_service_details(), get_topology(), list_services()

### Community 33 - "cli-executor.js"
Cohesion: 0.09
Nodes (36): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS, STORAGE_PRETASK_TIMEOUT_MS, resolveStorageRoot }, buildCLICommand(), { checkAndRecycleStorage, pinTaskCwd, unpinTaskCwd }, CLAUDE_JSON_PATH, cp, executeCLI(), executeCLIStreaming(), FALLBACK_MODEL (+28 more)

### Community 34 - "queue.py"
Cohesion: 0.08
Nodes (21): can_override_domain(), apply_lessons(), CloseRequest, correct_memory(), CorrectMemoryRequest, create_knowledge(), create_lesson(), enforce_casual_domain() (+13 more)

### Community 35 - "storage-recycler.js"
Cohesion: 0.08
Nodes (34): withTaskStorage(), resolveStorageRoot(), ROLE_TIMEOUTS, STORAGE_ACTIVITY_HEARTBEAT_MS, STORAGE_MAX_TIER3_DELETIONS, STORAGE_PRETASK_TIMEOUT_MS, STORAGE_RESULTS_TTL_MS, STORAGE_STALE_MS (+26 more)

### Community 36 - "handlers_integration.py"
Cohesion: 0.08
Nodes (18): _alert_wrapper_retrigger(), _do_retrigger(), _get_jira_reporter(), handle_notify_user_slack(), handle_refresh_github_context(), handle_refresh_gitlab_context(), handle_refresh_kargo_context(), _is_darwin_reentrant_caller() (+10 more)

### Community 37 - "JenkinsAdapter"
Cohesion: 0.06
Nodes (6): BuildDetails, JenkinsAdapter, JenkinsPlatformPort, JobResult, JobRunState, ViewScanResult

### Community 38 - "ArchitectureGraph.tsx"
Cohesion: 0.08
Nodes (32): @dagrejs/dagre, @xyflow/react, getGraphData(), GraphResponse, HealthStatus, NodeType, AppNodeData, applyDagreLayout() (+24 more)

### Community 39 - "EventDrillDown.tsx"
Cohesion: 0.09
Nodes (34): three, getEventPulses(), EventSource, BrainCore(), CortexDevPage(), devQueryClient, CortexLiveFeedProps, EventDrillDown() (+26 more)

### Community 41 - "ConversationTurn"
Cohesion: 0.15
Nodes (25): emit_tool_result(), handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_recall_pruned_turns(), handle_ask_release_ai(), handle_comment_jira_issue(), handle_fetch_jira_issue() (+17 more)

### Community 43 - "lucide-react"
Cohesion: 0.10
Nodes (30): lucide-react, createChatEvent(), getAgents(), getKargoStages(), KargoStageStatus, AgentRegistryPanel(), formatConnectedSince(), STARTER_CHIPS (+22 more)

### Community 44 - "CortexGraph.tsx"
Cohesion: 0.09
Nodes (35): graphology, AGENTS, DOMAINS, eventColor(), getExecutiveNeurons(), getStructuralEdges(), HEMISPHERE_X, NEURON_DESCRIPTIONS (+27 more)

### Community 45 - "ToolContext"
Cohesion: 0.10
Nodes (9): handle_classify_event(), handle_close_event(), handle_defer_event(), handle_hold_watch(), handle_request_user_approval(), handle_respond_to_jarvis(), handle_wait_for_agent(), handle_wait_for_jarvis() (+1 more)

### Community 48 - "TimeKeeperPage.tsx"
Cohesion: 0.12
Nodes (24): createSchedule(), deleteSchedule(), getSchedules(), refineInstructions(), ScheduleCreatePayload, ScheduleItem, toggleSchedule(), updateSchedule() (+16 more)

### Community 49 - "gemini_client.py"
Cohesion: 0.11
Nodes (10): _extract_call_syntax(), FunctionCall, LLMChunk, LLMPort, LLMResponse, process_stream_call_syntax_buffer(), sanitize_call_syntax(), scan_call_syntax() (+2 more)

### Community 50 - "formatter.py"
Cohesion: 0.09
Nodes (15): build_access_denied_home_view(), build_home_tab_view(), _context_line(), create_feedback_block(), format_plan_block(), format_task_card(), format_tool_result_blocks(), format_turn() (+7 more)

### Community 51 - "ScheduleRepository"
Cohesion: 0.08
Nodes (4): ScheduleCreateRequest, ScheduledEvent, update_schedule(), ScheduleRepository

### Community 52 - "Headhunter"
Cohesion: 0.08
Nodes (3): Headhunter, _raise_if_systemic_failure(), _sanitize_xml_fence()

### Community 53 - "ws-client.js"
Cohesion: 0.09
Nodes (26): is429Error(), {
  DEFAULT_WORK_DIR, AGENT_CLI, AGENT_MODEL, AGENT_ROLE,
  EVENT_ID, EPHEMERAL, IDLE_TIMEOUT_MS,
  CLI_429_MAX_RETRIES, CLI_429_INITIAL_DELAY_MS, CLI_429_BACKOFF_MULTIPLIER,
}, { ensureEventDocument }, { executeCLIStreaming, prepareResultsDir, is429Error }, { filterSkillsByRole, filterSkillsByMode, swapActiveRules, restoreAllSkills }, fs, handleCancel(), resetTimer() (+18 more)

### Community 54 - "useCortexData.ts"
Cohesion: 0.15
Nodes (29): getCognitiveGraph(), getCortexActivity(), getKGServiceDetail(), getKGServices(), getKGStats(), getKnowledgeById(), getLessonById(), getMemory() (+21 more)

### Community 55 - "ActiveStreamsContext.tsx"
Cohesion: 0.13
Nodes (26): AgentStreamCard(), AgentStreamCardProps, FloatingWindow(), MessageCards(), Dashboard(), GridTile(), GridTileProps, TileType (+18 more)

### Community 56 - "VectorStore"
Cohesion: 0.08
Nodes (3): _decode_cursor(), _encode_cursor(), VectorStore

### Community 57 - "get_archivist"
Cohesion: 0.08
Nodes (14): get_archivist(), aligner_pending_items(), delete_knowledge(), delete_lesson(), demote_lesson(), get_event_document(), get_knowledge(), get_lesson() (+6 more)

### Community 58 - "server.js"
Cohesion: 0.08
Nodes (18): hasRegistryCredentials(), { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, fs, path, stageEventDocument(), fetchEventDocument(), fs, { handleRequest } (+10 more)

### Community 59 - ".get_event"
Cohesion: 0.08
Nodes (7): report_tampering(), FeedbackRequest, submit_feedback(), close_event_by_user(), get_event_approval(), get_event_report(), get_event_turns()

### Community 61 - "StateWatcher"
Cohesion: 0.10
Nodes (3): _QueueEntry, StateWatcher, _Subscription

### Community 63 - "NodeInspector.tsx"
Cohesion: 0.13
Nodes (22): getClosedEvents(), ArchitectureEvent, ArgoCDOperation, EVENT_LABELS, EventItem(), EventItemProps, healthTone(), lastOperationSummary() (+14 more)

### Community 64 - "tool_router.py"
Cohesion: 0.10
Nodes (6): _safe_int(), handle_consult_deep_memory(), handle_google_web_search(), IdleTimeoutPort, IncidentAdapterPort, StateWatcherPort

### Community 67 - "NightwatcherObserver"
Cohesion: 0.13
Nodes (4): ShiftReport, _env_float(), _env_int(), NightwatcherObserver

### Community 70 - "dependencies"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 71 - "quota_tracker.py"
Cohesion: 0.12
Nodes (4): QuotaExhaustedError, QuotaTracker, RequestExceedsBurstError, Reservation

### Community 72 - "jira_incident.py"
Cohesion: 0.12
Nodes (3): _adf_to_text(), _escape_jql_string(), JiraIncidentAdapter

### Community 73 - "cognitive_graph.py"
Cohesion: 0.13
Nodes (10): get_brain(), get_pulse_tracker(), get_all_shadow_interventions(), get_cognitive_graph(), get_cortex_activity(), get_cortex_status(), get_event_shadow_interventions(), get_handoff_reports() (+2 more)

### Community 75 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 76 - "claude-guard.js"
Cohesion: 0.14
Nodes (18): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+10 more)

### Community 77 - "reconcile.py"
Cohesion: 0.18
Nodes (9): _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers(), main(), _parse_frontmatter() (+1 more)

### Community 78 - "cli-setup.js"
Cohesion: 0.13
Nodes (19): { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync }, filterSkillsByMode() (+11 more)

### Community 79 - "TokenUtilizationPage.tsx"
Cohesion: 0.17
Nodes (16): recharts, getFlowHistory(), FlowSnapshot, ObservationSeries, formatTime(), RANGES, SparkCard(), SparkCardProps (+8 more)

### Community 82 - "PulseBatch"
Cohesion: 0.12
Nodes (4): PulseBatch, PulsePort, PulseObserver, PulseTracker

### Community 84 - ".archive_event"
Cohesion: 0.14
Nodes (5): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship

### Community 86 - "handle_select_agent"
Cohesion: 0.14
Nodes (6): handle_message_agent(), handle_reply_to_agent(), handle_report_incident(), handle_select_agent(), _sticky_work_style(), handle_search_open_incidents()

### Community 87 - "UserContext"
Cohesion: 0.13
Nodes (9): _claims_to_user(), get_user_from_request(), get_user_from_websocket(), require_auth(), require_obs_admin(), UserContext, _validate_jwt(), dismiss_proposals() (+1 more)

### Community 89 - "devDependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 90 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 93 - "get_report"
Cohesion: 0.11
Nodes (6): get_report(), list_reports(), reports_spa_no_slash(), reports_spa_with_slash(), search_reports(), _serve_spa()

### Community 94 - "NeuronInfoPanel.tsx"
Cohesion: 0.16
Nodes (18): ActiveEvent, KGServiceDetail, KGServiceEntity, CortexGraphProps, GraphLoaderProps, asNumber(), asString(), asStringArray() (+10 more)

### Community 95 - "gemini-sidecar/package.json"
Cohesion: 0.11
Nodes (17): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+9 more)

### Community 98 - "catalog-skills.js"
Cohesion: 0.16
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 101 - "get"
Cohesion: 0.12
Nodes (8): api_info(), get_config(), get_event_flow(), get_flow_history(), get_flow_metrics(), health_check(), list_agents(), spa_fallback()

### Community 103 - "DeferCountdownBar.tsx"
Cohesion: 0.23
Nodes (13): ConversationTurn, DeferCountdownBar(), STATUS_COLORS, TICKET_COLORS, TicketNodeComponent(), TicketNodeData, DeferCountdownState, useDeferCountdown() (+5 more)

### Community 104 - "list_active_events"
Cohesion: 0.12
Nodes (6): _defer_timeline_fields(), _has_active_subscription(), list_active_events(), list_closed_events(), list_waiting_approval_events(), _serialize_evidence()

### Community 105 - "generate_map.py"
Cohesion: 0.19
Nodes (6): _enumerate_gates(), _GateInfo, generate_phase_tool_map(), _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 106 - "approve_event"
Cohesion: 0.18
Nodes (4): can_approve_event(), approve_event(), reject_event(), update_event_title()

### Community 112 - "_append_user_turn"
Cohesion: 0.14
Nodes (5): _append_user_turn(), _coerce_part(), _is_function_response_part(), _strip_user_thought_signature(), _validated_parts()

### Community 113 - "analyzeTokens"
Cohesion: 0.19
Nodes (13): analyzeString(), analyzeTokens(), assignName(), base(), combineCategories(), configEnvGuard(), configFileWriteGuard(), hasSubseq() (+5 more)

### Community 117 - "._send_turn_to_thread"
Cohesion: 0.19
Nodes (5): extract_tables(), _replace(), get_agent_notification_text(), get_turn_attachment_color(), _md_table_to_block_kit()

### Community 123 - "nightwatcher_prompt.py"
Cohesion: 0.20
Nodes (5): build_manifest_table(), build_report_iteration_prompt(), build_system_prompt(), extract_event_links(), _normalize_gitlab_host()

### Community 125 - "is_defer_event_available"
Cohesion: 0.18
Nodes (6): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 126 - "CiContextCard.tsx"
Cohesion: 0.31
Nodes (9): CiContext, CiContextCardProps, ConsoleTailBlock(), FailedJobRow(), annotationReplacer(), PIPELINE_ANNOTATION_RE, REDACTION_TRIGGER_KEYWORDS, stripAnsi() (+1 more)

### Community 127 - "CortexLiveFeed.tsx"
Cohesion: 0.27
Nodes (9): CortexHeartbeat(), CortexHeartbeatProps, ensureKeyframes(), CortexLiveFeed(), FILTER_PILLS, FilterKey, getStoredFilter(), MESSAGE_STYLES (+1 more)

### Community 129 - "gitGuard"
Cohesion: 0.29
Nodes (10): bareBranchProtected(), configWriteGuard(), externalGitCommand(), gitGuard(), gitQuery(), isProtected(), normRef(), pushGuard() (+2 more)

### Community 130 - "parseShell"
Cohesion: 0.33
Nodes (10): bodySubstitutions(), decodeAnsiC(), isArrayAssignPrefix(), isWordStart(), matchBacktick(), matchParen(), parseShell(), readHeredocStart() (+2 more)

### Community 138 - "has_unevaluated_close_blocker"
Cohesion: 0.20
Nodes (4): has_unevaluated_close_blocker(), _pred_jarvis_response(), _pred_unevaluated_close(), is_jarvis_acknowledgment()

### Community 140 - "knowledge_graph_api.py"
Cohesion: 0.31
Nodes (4): get_kg_store(), get_service_detail(), get_stats(), list_services()

### Community 141 - "SecurityError"
Cohesion: 0.28
Nodes (3): safe_execution(), wrapper(), SecurityError

### Community 142 - "classifyTool"
Cohesion: 0.31
Nodes (9): apiTokens(), apiWriteNeedsGuard(), branchValues(), classifyTool(), hasOpaqueTarget(), httpGuard(), httpMethod(), isReadMethod() (+1 more)

### Community 143 - "get_quota_tracker"
Cohesion: 0.22
Nodes (3): get_quota_tracker(), llm_stats(), receive_telemetry()

### Community 153 - "get_token_meter"
Cohesion: 0.25
Nodes (3): _has_non_user_turns(), _is_seed_turn(), get_token_meter()

### Community 156 - "adf_to_markdown"
Cohesion: 0.57
Nodes (7): adf_to_markdown(), _apply_marks(), _children(), _render(), _render_list(), _render_list_item(), _render_table_like()

### Community 157 - "validate-mutations.sh"
Cohesion: 0.57
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

### Community 160 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 161 - "state.js"
Cohesion: 0.33
Nodes (4): { AGENT_ROLE }, _blackboardTurns, _inboundMessages, _teammateMessages

### Community 174 - "classify"
Cohesion: 0.50
Nodes (4): classify(), main(), shellCategory(), shellNeedsGuard()

## Knowledge Gaps
- **13 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+8 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2229 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **115 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `logging`, `models.py`, `Brain`, `EventEvidence`, `brain.py`, `main.py`, `EventDocument`, `AgentRegistry`, `BrainSkillLoader`, `jenkins_observer.py`, `nightwatcher_tools.py`, `_is_event_closed_or_missing`, `list_shifts`, `observations_mgmt.py`, `.get_service`, `update_notebook_note`, `queue.py`, `ConversationTurn`, `ScheduleRepository`, `get_archivist`, `.get_event`, `LiveAPIAdapter`, `tool_router.py`, `NightwatcherObserver`, `DashboardWSAdapter`, `get_report`, `list_active_events`, `approve_event`, `.list_observations`, `HeadhunterJira`?**
  _High betweenness centrality (0.135) - this node is a cross-community bridge._
- **Are the 80 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 80 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.011878597592883308 - nodes in this community are weakly interconnected._
- **Why does `Brain` connect `Brain` to `BlackboardState`, `._extract_context_flags`, `._post_agent_recall`, `EventEvidence`, `brain.py`, `main.py`, `EventDocument`, `models.py`, `._run_agent_task`, `AgentRegistry`, `ReconcileScheduler`, `BrainSkillLoader`, `get_token_meter`, `._process_with_llm`, `ConversationTurn`, `.broadcast`, `.clear_jarvis_wait`, `.next_turn_number`, `StateWatcher`, `._turn_to_parts`, `quota_tracker.py`, `PulseBatch`, `DashboardWSAdapter`, `ReflexSearcher`, `IdleTimeoutManager`, `BrainLifecyclePort`?**
  _High betweenness centrality (0.063) - this node is a cross-community bridge._
- **Are the 21 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 21 INFERRED edges - model-reasoned connections that need verification._
- **Should `client.ts` be split into smaller, more focused modules?**
  _Cohesion score 0.03140495867768595 - nodes in this community are weakly interconnected._