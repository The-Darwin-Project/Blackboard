# Graph Report - Blackboard  (2026-11-18)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 5339 nodes · 12034 edges · 221 communities (106 shown, 115 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 962 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `51a8707d`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BlackboardState
- logging
- main.py
- client.ts
- lucide-react
- Brain
- EventDocument
- EventEvidence
- brain.py
- tool_gates.py
- Archivist
- EventSidebar.tsx
- colors.ts
- ._run_agent_task
- App.tsx
- http-handler.js
- get_blackboard
- jenkins-mcp.js
- GitHubPlatform
- HeadhunterJira
- WorkspaceInspector.tsx
- AgentRegistry
- react
- Aligner
- ._process_with_llm
- BrainSkillLoader
- GeminiAdapter
- ToolContext
- StreamGrid.tsx
- api/types.ts
- _BrainToolContext
- GitLabPlatform
- queue.py
- nightwatcher_tools.py
- merge-guard.js
- observations_mgmt.py
- Headhunter
- gemini_client.py
- cli-executor.js
- storage-recycler.js
- handlers_integration.py
- ScheduleRepository
- EventRepository
- llm/__init__.py
- auth.py
- ConversationTurn
- record_token_usage
- handlers_lookup.py
- .get_event
- ws-client.js
- NodeInspector.tsx
- ui/package.json
- JenkinsObserver
- get
- TimeKeeperPage.tsx
- CortexGraph.tsx
- cognitive_graph.py
- KnowledgeGraphStore
- LiveAPIAdapter
- server.js
- adf_to_markdown
- JenkinsAdapter
- PulseBatch
- ArgoCDObserver
- reports.py
- BrainIntrospectionPort
- KargoObserver
- TopologyRepository
- dependencies
- cortex/types.ts
- StateWatcher
- tool_router.py
- GitHubAppAuth
- compilerOptions
- claude-guard.js
- ArchitectureGraph.tsx
- DashboardWSAdapter
- _sanitize_analysis_text
- reconcile.py
- FlowHistoryPage.tsx
- .scroll
- VcsPlatformPort
- cli-setup.js
- ReflexSearcher
- FairQueue
- devDependencies
- compilerOptions
- gemini-sidecar/package.json
- EphemeralProvisioner
- .__init__
- ObservationRepository
- ShiftsPage.tsx
- catalog-skills.js
- OIDCKeyAdapter
- JarvisPeerPort
- observations.py
- EscalationRepository
- useCortexData.ts
- approve_event
- TokenMeter
- generate_map.py
- JenkinsPlatformPort
- ._poll_and_stage
- KubernetesSpawnHealthAdapter
- IdleTimeoutManager
- graph_recall.py
- ServiceNode.tsx
- ._connect
- handlers_planning.py
- nightwatcher_prompt.py
- SlackAccessGate
- analyzeTokens
- ._extract_context_flags
- QuotaTracker
- ._send_turn_to_thread
- ReconcileScheduler
- MultiInstallationManager
- NeuronInfoPanel.tsx
- ._process_message
- testSetup.ts
- .start_event_loop
- is_defer_event_available
- SlackChannel
- cortex-constants.ts
- CortexDevPage.tsx
- spawn_health.py
- gitGuard
- parseShell
- ._post_agent_recall
- FlowCollector
- entity_extractor.py
- ._clear_recovered_group_flags
- has_unevaluated_close_blocker
- Any
- ._register_handlers
- knowledge_graph_api.py
- EventDrillDown.tsx
- classifyTool
- get_quota_tracker
- SpawnPollResult
- SmartsheetMaintainerCache
- create_chat_event
- Trigger
- AsyncGitHubClient
- GitLabTokenAuth
- PulseBatch
- _is_event_closed_or_missing
- ._evaluate_health
- ._cleanup_stale_events
- ._triage_and_build_evidence
- TimeKeeperObserver
- CortexRepository
- validate-mutations.sh
- ._detect_repetition_collapse
- QuotaExhaustedError
- create_schedule
- scripts
- state.js
- _is_participant_turn
- DispatchMetrics
- _append_user_turn
- build_gate_context
- list_failed_stages
- dex_proxy
- ._wait_for_registration
- agent_ws_endpoint
- StalenessGuard
- classify
- _patch_enum_fields
- headhunter_pending_todos
- require-results.sh
- _walk_adf_mentions
- _env_flag
- get_intermediate_tools
- get_event_flow
- overrides
- findDuplicateJsonKeys.ts
- tsconfig.json
- gh-wrapper.sh
- check-inbox.sh
- cluster-context.sh
- validate-reviewer-bash.sh
- huddleSendMessage.sh
- update-agy.sh
- sendResults.sh
- diagnose_rejection
- GateDefinition
- _pred_dispatch_defer
- _pred_hard_strip_defer
- _pred_idle_agent_wait
- _pred_jarvis_wait
- _pred_obs_plateau
- _pred_silent_park
- _tools_wait_loop

## God Nodes (most connected - your core abstractions)
1. `BlackboardState` - 288 edges
2. `Brain` - 168 edges
3. `ConversationTurn` - 127 edges
4. `ToolContext` - 103 edges
5. `GateContext` - 99 edges
6. `react` - 85 edges
7. `EventDocument` - 84 edges
8. `fetchApi()` - 66 edges
9. `lifespan()` - 65 edges
10. `LiveAPIAdapter` - 64 edges

## Surprising Connections (you probably didn't know these)
- `EventRepository` --uses--> `ConversationMessage`  [INFERRED]
  src/state/ports.py → src/models.py
- `LiveAPIAdapter` --uses--> `EventStatus`  [INFERRED]
  src/adapters/live_api_adapter.py → src/models.py
- `Brain` --uses--> `EventStatus`  [INFERRED]
  src/agents/brain.py → src/models.py
- `handle_classify_event()` --uses--> `EventStatus`  [INFERRED]
  src/agents/handlers_state.py → src/models.py
- `handle_defer_event()` --uses--> `EventStatus`  [INFERRED]
  src/agents/handlers_state.py → src/models.py

## Import Cycles
- None detected.

## Communities (221 total, 115 thin omitted)

### Community 0 - "BlackboardState"
Cohesion: 0.01
Nodes (44): AppNode, ArchitectureEvent, ChatRequest, ChatResponse, ConversationMessage, EventInput, EventMetrics, EventStatus (+36 more)

### Community 1 - "logging"
Cohesion: 0.03
Nodes (23): _annotation_replace(), _strip_pipeline_annotations(), _sanitize_lesson_text(), _get_static_maintainer_emails(), _get_allowed_mention_authors(), _get_static_maintainer_emails(), _safe_int(), _parse_job_metadata() (+15 more)

### Community 2 - "main.py"
Cohesion: 0.02
Nodes (37): Architect, AgentClient, Developer, _check_security(), safe_execution(), wrapper(), SecurityError, SysAdmin (+29 more)

### Community 3 - "client.ts"
Cohesion: 0.03
Nodes (114): @tanstack/react-query, ApiError, applyLessons(), bulkDeleteObservations(), correctMemory(), createKnowledge(), createLesson(), deleteKnowledge() (+106 more)

### Community 4 - "lucide-react"
Cohesion: 0.05
Nodes (79): lucide-react, react-router-dom, createChatEvent(), getAgents(), getEventDocument(), getEvents(), getKargoStages(), updateEventTitle() (+71 more)

### Community 6 - "EventDocument"
Cohesion: 0.03
Nodes (16): _close_unanswered_fc(), _build_closed_block(), build_event_header(), _build_identity_block(), _build_journal_block(), _build_mermaid_block(), build_operational_briefing(), _build_related_block() (+8 more)

### Community 7 - "EventEvidence"
Cohesion: 0.04
Nodes (28): generate_event_title(), get_adapter(), _get_semaphore(), spawn_event_namer_task(), build_access_denied_home_view(), build_home_tab_view(), _context_line(), create_feedback_block() (+20 more)

### Community 8 - "brain.py"
Cohesion: 0.04
Nodes (29): _batch_is_terminal_for_flush(), _contents_have_pruned_or_decayed(), _is_close_phase_fc(), _apply_sibling_signature(), build_function_response(), build_single_function_response(), compress_contents(), contents_have_pruned_or_decayed() (+21 more)

### Community 9 - "tool_gates.py"
Cohesion: 0.05
Nodes (79): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+71 more)

### Community 11 - "EventSidebar.tsx"
Cohesion: 0.06
Nodes (69): getHeadhunterPending(), getJiraMissions(), HeadhunterTodo, postJiraAction(), ACTION_BADGE, formatAge(), HeadhunterQueuePanel(), renderItem() (+61 more)

### Community 12 - "colors.ts"
Cohesion: 0.06
Nodes (47): getReport(), getReports(), ActiveEvent, ReportFull, ReportMeta, DeferCountdownBar(), CompactCardStrip(), EventHistory() (+39 more)

### Community 13 - "._run_agent_task"
Cohesion: 0.05
Nodes (9): on_huddle(), on_progress(), on_huddle(), on_progress(), _is_automated_nudge(), _sanitize_error_text(), _sanitize_override_reason(), _select_dispatch_tier() (+1 more)

### Community 14 - "App.tsx"
Cohesion: 0.05
Nodes (53): oidc-client-ts, react-dom, dismissProposals(), EnhancementProposal, getConfig(), getHandoffReports(), getProposals(), getWSAuthFailureCallback() (+45 more)

### Community 15 - "http-handler.js"
Cohesion: 0.08
Nodes (62): is429Error(), registerMCPsAndHooks(), resolveCommand(), writeAgyMcpServer(), writeClaudeMcpServer(), parsePositiveInt(), buildArgoCDMcpConfig(), createAppJWT() (+54 more)

### Community 16 - "get_blackboard"
Cohesion: 0.04
Nodes (15): get_blackboard(), list_incidents(), approve_mission(), dismiss_mission(), _infer_phase(), _jira_config(), list_missions(), reanalyze_mission() (+7 more)

### Community 17 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 18 - "GitHubPlatform"
Cohesion: 0.05
Nodes (3): GitHubPlatform, _poll_one(), _poll_one()

### Community 20 - "WorkspaceInspector.tsx"
Cohesion: 0.07
Nodes (47): AgentRegistryEntry, CiContext, ConversationTurn, TokenUsageDict, CiContextCard(), CiContextCardProps, ConsoleTailBlock(), FailedJobRow() (+39 more)

### Community 21 - "AgentRegistry"
Cohesion: 0.06
Nodes (13): AgentConnection, AgentRegistry, agent_websocket_handler(), _heartbeat(), _build_prompt(), consume_wake_task(), _consume(), _dispatch_timeout_s() (+5 more)

### Community 22 - "react"
Cohesion: 0.09
Nodes (42): react, @uiw/react-markdown-preview, approveEvent(), closeEvent(), enforceCasualDomain(), getEventReport(), rejectEvent(), submitFeedback() (+34 more)

### Community 24 - "._process_with_llm"
Cohesion: 0.04
Nodes (4): _BatchContext, _ensure_recall_tool_if_needed(), _QuotaShedState, _retry_backoff_delay()

### Community 25 - "BrainSkillLoader"
Cohesion: 0.05
Nodes (3): BrainSkillLoader, _SkillCorpus, _wrap_section()

### Community 26 - "GeminiAdapter"
Cohesion: 0.08
Nodes (12): _attach_signature_to_parts(), _clone_part_with_sig(), _clone_part_with_text(), _coerce_part(), _decode_sig_bytes(), _extract_part_signature(), GeminiAdapter, _is_empty_sig_carrier() (+4 more)

### Community 27 - "ToolContext"
Cohesion: 0.08
Nodes (13): handle_message_agent(), handle_reply_to_agent(), handle_report_incident(), handle_select_agent(), _resolve_escalation_scope(), _sticky_work_style(), handle_search_open_incidents(), handle_defer_event() (+5 more)

### Community 28 - "StreamGrid.tsx"
Cohesion: 0.08
Nodes (40): getFlowMetrics(), FlowMetrics, AgentStreamCard(), AgentStreamCardProps, MessageCards(), Dashboard(), FlowHealthWidget(), queueColor() (+32 more)

### Community 29 - "api/types.ts"
Cohesion: 0.05
Nodes (45): ReportSearchParams, Agent, AlignerPendingItem, AppNode, AuthUser, BulkDeleteRequest, ChatEventRequest, ChatEventResponse (+37 more)

### Community 32 - "queue.py"
Cohesion: 0.07
Nodes (24): get_archivist(), apply_lessons(), correct_memory(), CorrectMemoryRequest, create_knowledge(), create_lesson(), delete_knowledge(), delete_lesson() (+16 more)

### Community 33 - "nightwatcher_tools.py"
Cohesion: 0.08
Nodes (23): PulseContext, ShiftIncident, ShiftInvestigation, extract_full_links(), build_extend_tool(), build_report_tool(), build_summary_tool(), execute_tool() (+15 more)

### Community 34 - "merge-guard.js"
Cohesion: 0.04
Nodes (46): API_VALUED, ARGO_MUTATING, ARGO_READ_SUB, ARGO_READ_TOP, BODY_FLAG, BROWSER_READ, CTX, ENV_BUILTINS (+38 more)

### Community 35 - "observations_mgmt.py"
Cohesion: 0.06
Nodes (18): get_report_client(), _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), render_pdf(), _sample_points() (+10 more)

### Community 36 - "Headhunter"
Cohesion: 0.06
Nodes (3): Headhunter, _raise_if_systemic_failure(), _sanitize_xml_fence()

### Community 37 - "gemini_client.py"
Cohesion: 0.07
Nodes (20): _extract_call_syntax(), _parse_drain_timeout(), derive_llm_priority(), _get_timeout_env_warned(), _get_timeout_order_warned(), is_partial_control_token(), LLMStreamInterChunkTimeoutError, LLMStreamTimeoutError (+12 more)

### Community 38 - "cli-executor.js"
Cohesion: 0.09
Nodes (37): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, MAX_TASK_WALL_MS, MAX_TIMER_MS, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS, STORAGE_PRETASK_TIMEOUT_MS, resolveStorageRoot }, buildCLICommand(), buildTimeoutResult(), { checkAndRecycleStorage, pinTaskCwd, unpinTaskCwd }, CLAUDE_JSON_PATH, cp, createInactivityWatchdog(), executeCLI() (+29 more)

### Community 39 - "storage-recycler.js"
Cohesion: 0.08
Nodes (37): withTaskStorage(), MAX_TASK_WALL_MS, parseTimerMs(), resolveStorageRoot(), resolveTimeoutMs(), ROLE_TIMEOUTS, STORAGE_ACTIVITY_HEARTBEAT_MS, STORAGE_MAX_TIER3_DELETIONS (+29 more)

### Community 40 - "handlers_integration.py"
Cohesion: 0.08
Nodes (19): _alert_wrapper_retrigger(), _do_retrigger(), _get_jira_reporter(), handle_notify_user_slack(), handle_refresh_github_context(), handle_refresh_gitlab_context(), handle_refresh_kargo_context(), _is_darwin_reentrant_caller() (+11 more)

### Community 41 - "ScheduleRepository"
Cohesion: 0.06
Nodes (6): ScheduleCreateRequest, ScheduledEvent, delete_schedule(), toggle_schedule(), update_schedule(), ScheduleRepository

### Community 43 - "llm/__init__.py"
Cohesion: 0.08
Nodes (7): ClaudeAdapter, _parse_tpm_limit(), FunctionCall, LLMChunk, LLMPort, LLMResponse, TokenUsage

### Community 44 - "auth.py"
Cohesion: 0.08
Nodes (15): can_append_message(), can_approve_event(), can_override_domain(), can_rename_event(), _claims_to_user(), get_user_from_request(), get_user_from_slack(), get_user_from_websocket() (+7 more)

### Community 45 - "ConversationTurn"
Cohesion: 0.15
Nodes (24): emit_tool_result(), handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_ask_release_ai(), handle_comment_jira_issue(), handle_fetch_jira_issue(), handle_greenwave() (+16 more)

### Community 46 - "record_token_usage"
Cohesion: 0.10
Nodes (7): record_token_usage(), ShiftReport, _append_user_turn(), _env_float(), _env_int(), NightwatcherObserver, _finalize_analysis_handover()

### Community 47 - "handlers_lookup.py"
Cohesion: 0.09
Nodes (14): _safe_int(), _coerce_turn_int(), handle_recall_pruned_turns(), _parse_turn_int(), _sanitize_recalled(), _format_bounded_journal(), handle_consult_deep_memory(), handle_google_web_search() (+6 more)

### Community 48 - ".get_event"
Cohesion: 0.06
Nodes (10): get_token_meter(), report_tampering(), FeedbackRequest, submit_feedback(), close_event_by_user(), CloseRequest, get_event_approval(), get_event_document() (+2 more)

### Community 49 - "ws-client.js"
Cohesion: 0.10
Nodes (26): clearIdleTimer(), {
  DEFAULT_WORK_DIR, AGENT_CLI, AGENT_MODEL, AGENT_ROLE,
  EVENT_ID, EPHEMERAL, IDLE_TIMEOUT_MS,
  CLI_429_MAX_RETRIES, CLI_429_INITIAL_DELAY_MS, CLI_429_BACKOFF_MULTIPLIER,
  resolveTimeoutMs, parsePositiveInt, MAX_TASK_WALL_MS, MAX_TIMER_MS,
}, { ensureEventDocument }, { executeCLIStreaming, prepareResultsDir, is429Error }, { filterSkillsByRole, filterSkillsByMode, swapActiveRules, restoreAllSkills }, fs, handleCancel(), handleTask() (+18 more)

### Community 50 - "NodeInspector.tsx"
Cohesion: 0.10
Nodes (28): getClosedEvents(), getService(), getTopology(), ArchitectureEvent, ArgoCDOperation, Service, TopologyResponse, EVENT_LABELS (+20 more)

### Community 51 - "ui/package.json"
Cohesion: 0.08
Nodes (29): autoprefixer, cronstrue, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, graphology-layout-forceatlas2 (+21 more)

### Community 53 - "get"
Cohesion: 0.07
Nodes (13): aligner_pending_items(), _defer_timeline_fields(), get_knowledge(), get_memory(), _has_active_subscription(), jenkins_pending_items(), list_active_events(), list_closed_events() (+5 more)

### Community 54 - "TimeKeeperPage.tsx"
Cohesion: 0.13
Nodes (20): createSchedule(), getSchedules(), ScheduleCreatePayload, ScheduleItem, Props, ScheduleForm(), TEMPLATES, formatNextFire() (+12 more)

### Community 56 - "CortexGraph.tsx"
Cohesion: 0.13
Nodes (26): graphology, sigma, eventColor(), getExecutiveNeurons(), getStructuralEdges(), DEFAULT_TYPE_BUDGET, evictLru(), KNOWLEDGE_RING (+18 more)

### Community 57 - "cognitive_graph.py"
Cohesion: 0.10
Nodes (12): get_brain(), get_pulse_tracker(), dismiss_proposals(), DismissRequest, get_all_shadow_interventions(), get_cognitive_graph(), get_cortex_activity(), get_cortex_status() (+4 more)

### Community 58 - "KnowledgeGraphStore"
Cohesion: 0.15
Nodes (4): _acquire(), KnowledgeGraphStore, _sanitize(), _with_timeout()

### Community 60 - "server.js"
Cohesion: 0.09
Nodes (18): { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, ensureEventDocument(), fs, path, stageEventDocument(), fetchEventDocument(), fs, { handleRequest } (+10 more)

### Community 61 - "adf_to_markdown"
Cohesion: 0.12
Nodes (10): _adf_to_text(), _escape_jql_string(), JiraIncidentAdapter, adf_to_markdown(), _apply_marks(), _children(), _render(), _render_list() (+2 more)

### Community 63 - "PulseBatch"
Cohesion: 0.10
Nodes (4): PulseBatch, PulsePort, PulseObserver, PulseTracker

### Community 65 - "reports.py"
Cohesion: 0.11
Nodes (6): get_report(), list_reports(), reports_spa_no_slash(), reports_spa_with_slash(), search_reports(), _serve_spa()

### Community 66 - "BrainIntrospectionPort"
Cohesion: 0.08
Nodes (3): BrainIntrospectionPort, BrainLifecyclePort, BroadcastPort

### Community 69 - "dependencies"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 70 - "cortex/types.ts"
Cohesion: 0.14
Nodes (21): CortexHeartbeat(), CortexHeartbeatProps, ensureKeyframes(), CortexLiveFeed(), CortexLiveFeedProps, FILTER_PILLS, FilterKey, getStoredFilter() (+13 more)

### Community 71 - "StateWatcher"
Cohesion: 0.11
Nodes (3): _QueueEntry, StateWatcher, _Subscription

### Community 72 - "tool_router.py"
Cohesion: 0.10
Nodes (5): can_transition_to_close(), IdleTimeoutPort, IncidentAdapterPort, StateWatcherPort, resolve_event_domain()

### Community 74 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 75 - "claude-guard.js"
Cohesion: 0.14
Nodes (18): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+10 more)

### Community 76 - "ArchitectureGraph.tsx"
Cohesion: 0.14
Nodes (18): @dagrejs/dagre, @xyflow/react, applyDagreLayout(), applyGridLayout(), applyLayout(), ArchitectureGraph(), ArchitectureGraphInner(), buildGraph() (+10 more)

### Community 78 - "_sanitize_analysis_text"
Cohesion: 0.10
Nodes (9): _clamp_confidence(), _prepare_console_tail(), _redact_match(), _redact_secrets_in_text(), _sanitize_analysis_text(), _sanitize_console_tail(), _strip_newlines(), _validate_analysis() (+1 more)

### Community 79 - "reconcile.py"
Cohesion: 0.18
Nodes (9): _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers(), main(), _parse_frontmatter() (+1 more)

### Community 80 - "FlowHistoryPage.tsx"
Cohesion: 0.23
Nodes (16): recharts, getFlowHistory(), FlowSnapshot, FlowHistoryPage(), RANGES, SparkCard(), SparkCardProps, formatTime() (+8 more)

### Community 83 - "cli-setup.js"
Cohesion: 0.13
Nodes (18): { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync }, filterSkillsByMode() (+10 more)

### Community 86 - "devDependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 87 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 88 - "gemini-sidecar/package.json"
Cohesion: 0.11
Nodes (18): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+10 more)

### Community 92 - "ShiftsPage.tsx"
Cohesion: 0.23
Nodes (16): getCurrentShift(), getShiftDetail(), getShiftsList(), ShiftReportFull, ShiftReportSummary, FailedClusterBadge(), getISOWeek(), getWeekDates() (+8 more)

### Community 93 - "catalog-skills.js"
Cohesion: 0.16
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 99 - "useCortexData.ts"
Cohesion: 0.31
Nodes (15): getCortexActivity(), getRecentPulses(), CortexPage(), isOffRingCollection(), OffRingCollection, useWSMessage(), useCortexGraph(), useCortexShadow() (+7 more)

### Community 100 - "approve_event"
Cohesion: 0.16
Nodes (4): approve_event(), reject_event(), TitleUpdateRequest, update_event_title()

### Community 102 - "generate_map.py"
Cohesion: 0.19
Nodes (6): _enumerate_gates(), _GateInfo, generate_phase_tool_map(), _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 103 - "JenkinsPlatformPort"
Cohesion: 0.13
Nodes (4): BuildDetails, JenkinsPlatformPort, JobRunState, ViewScanResult

### Community 107 - "graph_recall.py"
Cohesion: 0.19
Nodes (5): _format_graph_context(), get_graph_context(), _parse_props(), _sanitize(), translate_to_lookups()

### Community 108 - "ServiceNode.tsx"
Cohesion: 0.20
Nodes (11): HealthStatus, NodeType, AppNodeData, ARGOCD_HEALTH_COLORS, SYNC_ICONS, GENERIC_TAGS, HEALTH_COLORS, NODE_ICONS (+3 more)

### Community 110 - "handlers_planning.py"
Cohesion: 0.23
Nodes (7): _auto_complete_step(), _canonical_role(), handle_create_plan(), handle_get_plan_progress(), _is_failed_turn(), _is_orchestrator_turn(), _normalize_step_id()

### Community 111 - "nightwatcher_prompt.py"
Cohesion: 0.16
Nodes (6): build_manifest_table(), build_report_iteration_prompt(), build_summary_prompt(), build_system_prompt(), extract_event_links(), _normalize_gitlab_host()

### Community 113 - "analyzeTokens"
Cohesion: 0.19
Nodes (13): analyzeString(), analyzeTokens(), assignName(), base(), combineCategories(), configEnvGuard(), configFileWriteGuard(), hasSubseq() (+5 more)

### Community 114 - "._extract_context_flags"
Cohesion: 0.15
Nodes (3): compute_dispatch_backpressure(), ContextFlags, _safe_int_env()

### Community 116 - "._send_turn_to_thread"
Cohesion: 0.19
Nodes (4): extract_tables(), _replace(), get_agent_notification_text(), _md_table_to_block_kit()

### Community 119 - "NeuronInfoPanel.tsx"
Cohesion: 0.24
Nodes (12): KGServiceDetail, asNumber(), asString(), asStringArray(), Badge(), describeNeuron(), Hdr(), NeuronInfoPanel() (+4 more)

### Community 124 - "testSetup.ts"
Cohesion: 0.18
Nodes (5): @tailwindcss/vite, @testing-library/react, vite, @vitejs/plugin-react, vitest

### Community 126 - "is_defer_event_available"
Cohesion: 0.18
Nodes (6): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 128 - "cortex-constants.ts"
Cohesion: 0.18
Nodes (10): AGENTS, DOMAINS, HEMISPHERE_X, NEURON_DESCRIPTIONS, PHASE_SKILL_FOLDERS, PHASE_TOOL_PRIORITY, PHASES, StructuralEdge (+2 more)

### Community 129 - "CortexDevPage.tsx"
Cohesion: 0.31
Nodes (9): CortexDevPage(), devQueryClient, MOCK_CORTEX_STATUS, MOCK_EVENT_ID, MOCK_NEURONS, MOCK_PULSE_BATCHES, MOCK_SHADOW, MOCK_THINKING (+1 more)

### Community 131 - "gitGuard"
Cohesion: 0.29
Nodes (10): bareBranchProtected(), configWriteGuard(), externalGitCommand(), gitGuard(), gitQuery(), isProtected(), normRef(), pushGuard() (+2 more)

### Community 132 - "parseShell"
Cohesion: 0.33
Nodes (10): bodySubstitutions(), decodeAnsiC(), isArrayAssignPrefix(), isWordStart(), matchBacktick(), matchParen(), parseShell(), readHeredocStart() (+2 more)

### Community 135 - "entity_extractor.py"
Cohesion: 0.33
Nodes (5): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship

### Community 137 - "has_unevaluated_close_blocker"
Cohesion: 0.22
Nodes (5): has_unevaluated_close_blocker(), _pred_jarvis_response(), _pred_unevaluated_close(), is_jarvis_acknowledgment(), is_stabilization_wake()

### Community 139 - "._register_handlers"
Cohesion: 0.22
Nodes (3): handle_approve(), handle_home_create_event(), handle_reject()

### Community 140 - "knowledge_graph_api.py"
Cohesion: 0.31
Nodes (4): get_kg_store(), get_service_detail(), get_stats(), list_services()

### Community 141 - "EventDrillDown.tsx"
Cohesion: 0.31
Nodes (7): getEventPulses(), BrainCore(), EventDrillDown(), FRICTION_COLORS, WHISPER_COLORS, PulseTimeline(), useFrictionIndicators()

### Community 142 - "classifyTool"
Cohesion: 0.31
Nodes (9): apiTokens(), apiWriteNeedsGuard(), branchValues(), classifyTool(), hasOpaqueTarget(), httpGuard(), httpMethod(), isReadMethod() (+1 more)

### Community 143 - "get_quota_tracker"
Cohesion: 0.22
Nodes (3): get_quota_tracker(), llm_stats(), receive_telemetry()

### Community 146 - "create_chat_event"
Cohesion: 0.25
Nodes (3): ChatEventRequest, ChatEventResponse, create_chat_event()

### Community 150 - "PulseBatch"
Cohesion: 0.31
Nodes (8): EventSource, KGServiceEntity, CortexGraphProps, GraphLoaderProps, PulseTimelineProps, Neuron, PulseBatch, NEURON_COLORS

### Community 157 - "validate-mutations.sh"
Cohesion: 0.57
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

### Community 162 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 163 - "state.js"
Cohesion: 0.33
Nodes (4): { AGENT_ROLE }, _blackboardTurns, _inboundMessages, _teammateMessages

### Community 164 - "_is_participant_turn"
Cohesion: 0.33
Nodes (3): _compute_processed_up_to(), _is_participant_turn(), _is_steering_turn()

### Community 166 - "_append_user_turn"
Cohesion: 0.33
Nodes (3): _append_user_turn(), _is_function_response_part(), _validated_parts()

### Community 167 - "build_gate_context"
Cohesion: 0.33
Nodes (3): build_gate_context(), conversation_has_decayed_turns(), _decay_payload_len()

### Community 178 - "classify"
Cohesion: 0.50
Nodes (4): classify(), main(), shellCategory(), shellNeedsGuard()

### Community 196 - "overrides"
Cohesion: 0.67
Nodes (3): overrides, @typescript-eslint/typescript-estree, minimatch

## Knowledge Gaps
- **13 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+8 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2346 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **115 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `logging`, `main.py`, `Brain`, `EventDocument`, `EventEvidence`, `brain.py`, `get_blackboard`, `create_chat_event`, `HeadhunterJira`, `_is_event_closed_or_missing`, `queue.py`, `nightwatcher_tools.py`, `create_schedule`, `observations_mgmt.py`, `ScheduleRepository`, `._restage_pending_signal`, `._stage_pending_signal`, `ConversationTurn`, `record_token_usage`, `.get_event`, `._count_pending`, `get`, `.cleanup_stale_services`, `._commit_pending_signal`, `._drain_pending`, `LiveAPIAdapter`, `.drain_notes`, `.get_edge_metadata`, `reports.py`, `tool_router.py`, `DashboardWSAdapter`, `.__init__`, `observations.py`, `approve_event`?**
  _High betweenness centrality (0.138) - this node is a cross-community bridge._
- **Are the 80 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 80 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.011646903820816864 - nodes in this community are weakly interconnected._
- **Why does `Brain` connect `Brain` to `BlackboardState`, `logging`, `main.py`, `._post_agent_recall`, `EventDocument`, `EventEvidence`, `brain.py`, `FlowCollector`, `._run_agent_task`, `._process_with_llm`, `._cleanup_stale_events`, `BrainSkillLoader`, `._detect_repetition_collapse`, `ConversationTurn`, `StalenessGuard`, `.clear_jarvis_wait`, `.has_subscription`, `PulseBatch`, `BrainIntrospectionPort`, `StateWatcher`, `DashboardWSAdapter`, `ReflexSearcher`, `.__init__`, `JarvisPeerPort`, `IdleTimeoutManager`, `._extract_context_flags`, `ReconcileScheduler`, `.start_event_loop`?**
  _High betweenness centrality (0.087) - this node is a cross-community bridge._
- **Are the 20 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Should `logging` be split into smaller, more focused modules?**
  _Cohesion score 0.03090507726269316 - nodes in this community are weakly interconnected._