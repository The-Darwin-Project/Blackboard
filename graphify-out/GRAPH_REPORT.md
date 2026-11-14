# Graph Report - Blackboard  (2026-11-14)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 5233 nodes · 11747 edges · 214 communities (103 shown, 111 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 952 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `18b03069`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BlackboardState
- main.py
- Brain
- WorkspaceInspector.tsx
- logging
- models.py
- client.ts
- nightwatcher_tools.py
- Archivist
- EventDocument
- tool_gates.py
- EventSidebar.tsx
- colors.ts
- AgentRegistry
- EventEvidence
- http-handler.js
- react
- hooks/index.ts
- App.tsx
- brain.py
- jenkins-mcp.js
- BrainSkillLoader
- ._process_with_llm
- queue.py
- .get_event
- _BrainToolContext
- OpsStateContext.tsx
- merge-guard.js
- CortexGraph.tsx
- observations_mgmt.py
- ScheduleRepository
- GeminiAdapter
- cli-executor.js
- storage-recycler.js
- EventHistory.tsx
- JenkinsAdapter
- EventRepository
- auth.py
- SlackChannel
- ui/package.json
- EventDrillDown.tsx
- GitHubPlatform
- KnowledgeGraphStore
- ToolContext
- llm/__init__.py
- gemini_client.py
- ArchitectureGraph.tsx
- ConversationTurn
- GitLabPlatform
- Headhunter
- TimeKeeperPage.tsx
- cognitive_graph.py
- ws-client.js
- useCortexData.ts
- spawn_event_namer_task
- formatter.py
- HeadhunterJira
- server.js
- ArgoCDObserver
- reconcile.py
- ._get_manager
- KargoObserver
- TopologyRepository
- GitHubAppAuth
- dependencies
- compilerOptions
- claude-guard.js
- DashboardWSAdapter
- PulseBatch
- BrainIntrospectionPort
- scheduling/__init__.py
- tool_router.py
- handlers_dispatch.py
- VcsPlatformPort
- cli-setup.js
- ReflexSearcher
- StateWatcher
- .get_blackboard
- QuotaTracker
- devDependencies
- compilerOptions
- gemini-sidecar/package.json
- LiveAPIAdapter
- EphemeralProvisioner
- jira.py
- get_report
- JenkinsObserver
- ObservationRepository
- ShiftsPage.tsx
- TokenUtilizationPage.tsx
- catalog-skills.js
- EventType
- approve_event
- EscalationRepository
- FairQueue
- generate_map.py
- handlers_planning.py
- ._normalize_issue
- OIDCKeyAdapter
- KubernetesSpawnHealthAdapter
- slack.py
- .start_event_loop
- vcs_approval.py
- SlackAccessGate
- MultiInstallationManager
- analyzeTokens
- ._extract_context_flags
- TokenMeter
- IdleTimeoutManager
- ReconcileScheduler
- format_jira_for_llm
- _sanitize_analysis_text
- resolve_maintainer_emails
- is_defer_event_available
- CiContextCard.tsx
- NeuronInfoPanel.tsx
- gitGuard
- parseShell
- extract_tables
- generate_event_title
- ._post_agent_recall
- entity_extractor.py
- ._github_poll_and_process
- ._process_candidates
- _prepare_console_tail
- has_unevaluated_close_blocker
- CortexDevPage.tsx
- classifyTool
- get_quota_tracker
- _is_event_closed_or_missing
- SpawnPollResult
- SmartsheetMaintainerCache
- .has_reeval_signal
- create_chat_event
- Trigger
- AsyncGitHubClient
- GitLabTokenAuth
- ._evaluate_health
- ._triage_and_build_evidence
- ._drain_once
- ConversationMessage
- CortexRepository
- adf_to_markdown
- validate-mutations.sh
- scripts
- state.js
- ._process_message
- DispatchMetrics
- _append_user_turn
- build_gate_context
- SpawnStatus
- dex_proxy
- ._wait_for_registration
- _do_retrigger
- _resolve_slack_user
- _resolve_domain
- StalenessGuard
- ResyncTrigger
- classify
- derive_llm_priority
- list_incidents
- require-results.sh
- _WSFrameFilter
- TokenUsageDict
- get_intermediate_tools
- get_event_flow
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
2. `Brain` - 159 edges
3. `ConversationTurn` - 125 edges
4. `ToolContext` - 103 edges
5. `GateContext` - 96 edges
6. `react` - 85 edges
7. `EventDocument` - 82 edges
8. `fetchApi()` - 66 edges
9. `lifespan()` - 65 edges
10. `EventEvidence` - 58 edges

## Surprising Connections (you probably didn't know these)
- `MetricsRepository` --uses--> `ArchitectureEvent`  [INFERRED]
  src/state/ports.py → src/models.py
- `get_flow_history()` --uses--> `FlowSnapshot`  [INFERRED]
  src/main.py → src/models.py
- `FlowCollector` --uses--> `FlowSnapshot`  [INFERRED]
  src/observers/flow_collector.py → src/models.py
- `DashboardWSAdapter` --uses--> `BlackboardState`  [INFERRED]
  src/adapters/dashboard_ws.py → src/state/blackboard.py
- `LiveAPIAdapter` --uses--> `BlackboardState`  [INFERRED]
  src/adapters/live_api_adapter.py → src/state/blackboard.py

## Import Cycles
- None detected.

## Communities (214 total, 111 thin omitted)

### Community 0 - "BlackboardState"
Cohesion: 0.01
Nodes (19): ArchitectureEvent, FlowSnapshot, list_events(), get_all_journal(), get_service_journal(), delete_notebook_note(), get_notebook(), NotePatchRequest (+11 more)

### Community 1 - "main.py"
Cohesion: 0.02
Nodes (38): Architect, AgentClient, Developer, set_incident_options(), SysAdmin, set_oidc_adapter(), get_aligner(), get_architect() (+30 more)

### Community 2 - "Brain"
Cohesion: 0.02
Nodes (8): Brain, on_huddle(), on_progress(), on_huddle(), on_progress(), _is_automated_nudge(), _sanitize_error_text(), get_registry_and_bridge()

### Community 3 - "WorkspaceInspector.tsx"
Cohesion: 0.04
Nodes (89): closeEvent(), enforceCasualDomain(), updateEventTitle(), ConversationTurn, TokenUsageDict, ChatInput(), CiContextCard(), ConversationFeed() (+81 more)

### Community 4 - "logging"
Cohesion: 0.04
Nodes (12): _annotation_replace(), _strip_pipeline_annotations(), _sanitize_lesson_text(), _parse_props(), _get_static_maintainer_emails(), _get_allowed_mention_authors(), _get_static_maintainer_emails(), _safe_int() (+4 more)

### Community 5 - "models.py"
Cohesion: 0.03
Nodes (32): AppNode, ChatRequest, ChatResponse, EventInput, EventMetrics, FlowMetricsResponse, GraphEdge, GraphNode (+24 more)

### Community 6 - "client.ts"
Cohesion: 0.03
Nodes (95): recharts, ApiError, bulkDeleteObservations(), deleteObservation(), dismissProposals(), EnhancementProposal, exportObservations(), ExtractedCorrection (+87 more)

### Community 7 - "nightwatcher_tools.py"
Cohesion: 0.04
Nodes (38): JiraIncidentAdapter, record_token_usage(), PulseContext, ShiftIncident, ShiftInvestigation, ShiftReport, StagedEscalation, _append_user_turn() (+30 more)

### Community 8 - "Archivist"
Cohesion: 0.04
Nodes (5): Archivist, Pulse, _decode_cursor(), _encode_cursor(), VectorStore

### Community 9 - "EventDocument"
Cohesion: 0.03
Nodes (21): _close_unanswered_fc(), _sanitize_recalled(), _build_closed_block(), build_event_header(), _build_identity_block(), _build_journal_block(), _build_mermaid_block(), build_operational_briefing() (+13 more)

### Community 10 - "tool_gates.py"
Cohesion: 0.05
Nodes (77): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+69 more)

### Community 11 - "EventSidebar.tsx"
Cohesion: 0.06
Nodes (71): getAlignerPending(), getClosedEvents(), getHeadhunterPending(), getJenkinsPending(), getJiraMissions(), getWaitingApprovalEvents(), HeadhunterTodo, postJiraAction() (+63 more)

### Community 12 - "colors.ts"
Cohesion: 0.06
Nodes (59): @uiw/react-markdown-preview, approveEvent(), rejectEvent(), submitFeedback(), ReportFull, AgentStreamCard(), AgentStreamCardProps, MessageCards() (+51 more)

### Community 13 - "AgentRegistry"
Cohesion: 0.04
Nodes (19): AgentConnection, AgentRegistry, agent_websocket_handler(), _heartbeat(), _build_prompt(), _check_security(), consume_wake_task(), _consume() (+11 more)

### Community 14 - "EventEvidence"
Cohesion: 0.04
Nodes (4): Aligner, FilterRule, EventEvidence, TimeKeeperObserver

### Community 15 - "http-handler.js"
Cohesion: 0.08
Nodes (62): is429Error(), registerMCPsAndHooks(), resolveCommand(), writeAgyMcpServer(), writeClaudeMcpServer(), parsePositiveInt(), buildArgoCDMcpConfig(), createAppJWT() (+54 more)

### Community 16 - "react"
Cohesion: 0.07
Nodes (58): lucide-react, react, applyLessons(), correctMemory(), createKnowledge(), createLesson(), deleteKnowledge(), deleteLesson() (+50 more)

### Community 17 - "hooks/index.ts"
Cohesion: 0.06
Nodes (50): @tanstack/react-query, createChatEvent(), getActiveEvents(), getEventDocument(), getEvents(), ArchitectureEvent, ArgoCDOperation, ActivityStream() (+42 more)

### Community 18 - "App.tsx"
Cohesion: 0.06
Nodes (45): oidc-client-ts, react-dom, react-router-dom, getConfig(), getIncidents(), getWSAuthFailureCallback(), Incident, setOnUnauthorized() (+37 more)

### Community 19 - "brain.py"
Cohesion: 0.06
Nodes (24): _compute_processed_up_to(), _contents_have_pruned_or_decayed(), _ensure_recall_tool_if_needed(), _has_non_user_turns(), _is_seed_turn(), _QuotaShedState, _sanitize_override_reason(), _select_dispatch_tier() (+16 more)

### Community 20 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 21 - "BrainSkillLoader"
Cohesion: 0.05
Nodes (5): _incr_flow_counter_safely(), _parse_positive_int_env(), BrainSkillLoader, _SkillCorpus, _wrap_section()

### Community 22 - "._process_with_llm"
Cohesion: 0.04
Nodes (3): _BatchContext, RepetitionCollapse, _retry_backoff_delay()

### Community 23 - "queue.py"
Cohesion: 0.06
Nodes (28): get_archivist(), apply_lessons(), CloseRequest, correct_memory(), CorrectMemoryRequest, create_knowledge(), create_lesson(), delete_knowledge() (+20 more)

### Community 24 - ".get_event"
Cohesion: 0.04
Nodes (18): get_token_meter(), EventStatus, report_tampering(), FeedbackRequest, submit_feedback(), close_event_by_user(), _defer_timeline_fields(), get_event_approval() (+10 more)

### Community 26 - "OpsStateContext.tsx"
Cohesion: 0.08
Nodes (39): getAgents(), getKargoStages(), EventEvidence, KargoStageStatus, AgentRegistryPanel(), formatConnectedSince(), Dashboard(), EmptyState() (+31 more)

### Community 27 - "merge-guard.js"
Cohesion: 0.04
Nodes (46): API_VALUED, ARGO_MUTATING, ARGO_READ_SUB, ARGO_READ_TOP, BODY_FLAG, BROWSER_READ, CTX, ENV_BUILTINS (+38 more)

### Community 28 - "CortexGraph.tsx"
Cohesion: 0.07
Nodes (44): graphology, @react-sigma/core, @react-sigma/layout-forceatlas2, @sigma/node-square, ActiveEvent, AGENTS, DOMAINS, eventColor() (+36 more)

### Community 29 - "observations_mgmt.py"
Cohesion: 0.06
Nodes (18): get_report_client(), _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), render_pdf(), _sample_points() (+10 more)

### Community 30 - "ScheduleRepository"
Cohesion: 0.06
Nodes (6): ScheduleCreateRequest, ScheduledEvent, delete_schedule(), toggle_schedule(), update_schedule(), ScheduleRepository

### Community 31 - "GeminiAdapter"
Cohesion: 0.09
Nodes (9): _attach_signature_to_parts(), _clone_part_with_sig(), _coerce_part(), _decode_sig_bytes(), _extract_part_signature(), GeminiAdapter, _is_empty_sig_carrier(), _part_has_fc() (+1 more)

### Community 32 - "cli-executor.js"
Cohesion: 0.09
Nodes (37): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, MAX_TASK_WALL_MS, MAX_TIMER_MS, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS, STORAGE_PRETASK_TIMEOUT_MS, resolveStorageRoot }, buildCLICommand(), buildTimeoutResult(), { checkAndRecycleStorage, pinTaskCwd, unpinTaskCwd }, CLAUDE_JSON_PATH, cp, createInactivityWatchdog(), executeCLI() (+29 more)

### Community 33 - "storage-recycler.js"
Cohesion: 0.08
Nodes (37): withTaskStorage(), MAX_TASK_WALL_MS, parseTimerMs(), resolveStorageRoot(), resolveTimeoutMs(), ROLE_TIMEOUTS, STORAGE_ACTIVITY_HEARTBEAT_MS, STORAGE_MAX_TIER3_DELETIONS (+29 more)

### Community 34 - "EventHistory.tsx"
Cohesion: 0.11
Nodes (34): @tanstack/react-table, getReport(), getReports(), ReportMeta, SubjectType, CompactCardStrip(), EventHistory(), TimeRange (+26 more)

### Community 35 - "JenkinsAdapter"
Cohesion: 0.06
Nodes (6): BuildDetails, JenkinsAdapter, JenkinsPlatformPort, JobResult, JobRunState, ViewScanResult

### Community 37 - "auth.py"
Cohesion: 0.08
Nodes (15): can_append_message(), can_approve_event(), can_override_domain(), can_rename_event(), _claims_to_user(), get_user_from_request(), get_user_from_slack(), get_user_from_websocket() (+7 more)

### Community 39 - "ui/package.json"
Cohesion: 0.06
Nodes (33): autoprefixer, cronstrue, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, graphology-layout-forceatlas2 (+25 more)

### Community 40 - "EventDrillDown.tsx"
Cohesion: 0.09
Nodes (33): three, getEventPulses(), EventSource, BrainCore(), CortexDevPage(), CortexHeartbeat(), CortexHeartbeatProps, ensureKeyframes() (+25 more)

### Community 42 - "KnowledgeGraphStore"
Cohesion: 0.09
Nodes (8): _format_graph_context(), get_graph_context(), _sanitize(), translate_to_lookups(), _acquire(), KnowledgeGraphStore, _sanitize(), _with_timeout()

### Community 43 - "ToolContext"
Cohesion: 0.09
Nodes (10): handle_classify_event(), handle_close_event(), handle_defer_event(), handle_hold_watch(), handle_request_user_approval(), handle_wait_for_agent(), handle_wait_for_jarvis(), handle_wait_for_user() (+2 more)

### Community 44 - "llm/__init__.py"
Cohesion: 0.09
Nodes (6): ClaudeAdapter, FunctionCall, LLMChunk, LLMPort, LLMResponse, TokenUsage

### Community 45 - "gemini_client.py"
Cohesion: 0.09
Nodes (16): _extract_call_syntax(), _parse_drain_timeout(), _stale_reservation_ttl_s(), _get_timeout_env_warned(), _get_timeout_order_warned(), LLMStreamInterChunkTimeoutError, LLMStreamTimeoutError, LLMStreamTotalTimeoutError (+8 more)

### Community 46 - "ArchitectureGraph.tsx"
Cohesion: 0.09
Nodes (29): @dagrejs/dagre, @xyflow/react, HealthStatus, NodeType, AppNodeData, applyDagreLayout(), applyGridLayout(), applyLayout() (+21 more)

### Community 47 - "ConversationTurn"
Cohesion: 0.13
Nodes (22): emit_tool_result(), _get_jira_reporter(), handle_ask_release_ai(), handle_comment_jira_issue(), handle_fetch_jira_issue(), handle_greenwave(), handle_notify_gitlab_result(), handle_notify_user_slack() (+14 more)

### Community 50 - "TimeKeeperPage.tsx"
Cohesion: 0.12
Nodes (24): createSchedule(), deleteSchedule(), getSchedules(), refineInstructions(), ScheduleCreatePayload, ScheduleItem, toggleSchedule(), updateSchedule() (+16 more)

### Community 51 - "cognitive_graph.py"
Cohesion: 0.08
Nodes (14): get_brain(), get_pulse_tracker(), dismiss_proposals(), DismissRequest, get_all_shadow_interventions(), get_cognitive_graph(), get_cortex_activity(), get_cortex_status() (+6 more)

### Community 52 - "ws-client.js"
Cohesion: 0.10
Nodes (26): clearIdleTimer(), {
  DEFAULT_WORK_DIR, AGENT_CLI, AGENT_MODEL, AGENT_ROLE,
  EVENT_ID, EPHEMERAL, IDLE_TIMEOUT_MS,
  CLI_429_MAX_RETRIES, CLI_429_INITIAL_DELAY_MS, CLI_429_BACKOFF_MULTIPLIER,
  resolveTimeoutMs, parsePositiveInt, MAX_TASK_WALL_MS, MAX_TIMER_MS,
}, { ensureEventDocument }, { executeCLIStreaming, prepareResultsDir, is429Error }, { filterSkillsByRole, filterSkillsByMode, swapActiveRules, restoreAllSkills }, fs, handleCancel(), handleTask() (+18 more)

### Community 53 - "useCortexData.ts"
Cohesion: 0.16
Nodes (28): getCognitiveGraph(), getCortexActivity(), getEventReport(), getKGServiceDetail(), getKGServices(), getKGStats(), getKnowledgeById(), getMemory() (+20 more)

### Community 54 - "spawn_event_namer_task"
Cohesion: 0.14
Nodes (9): spawn_event_namer_task(), handle_app_home_opened(), handle_app_mention(), handle_create_event_modal(), handle_darwin_command(), handle_home_create_event(), handle_reject(), on_dm_message() (+1 more)

### Community 55 - "formatter.py"
Cohesion: 0.11
Nodes (13): build_access_denied_home_view(), build_home_tab_view(), _context_line(), create_feedback_block(), format_event_summary(), format_plan_block(), format_task_card(), format_tool_result_blocks() (+5 more)

### Community 57 - "server.js"
Cohesion: 0.09
Nodes (18): { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, ensureEventDocument(), fs, path, stageEventDocument(), fetchEventDocument(), fs, { handleRequest } (+10 more)

### Community 59 - "reconcile.py"
Cohesion: 0.15
Nodes (10): sanitize_redis_port(), _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers(), main() (+2 more)

### Community 63 - "GitHubAppAuth"
Cohesion: 0.11
Nodes (3): _find_pem_file(), get_github_auth(), GitHubAppAuth

### Community 64 - "dependencies"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 65 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 66 - "claude-guard.js"
Cohesion: 0.14
Nodes (18): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+10 more)

### Community 68 - "PulseBatch"
Cohesion: 0.11
Nodes (4): PulseBatch, PulsePort, PulseObserver, PulseTracker

### Community 69 - "BrainIntrospectionPort"
Cohesion: 0.10
Nodes (3): BrainIntrospectionPort, BrainLifecyclePort, BroadcastPort

### Community 70 - "scheduling/__init__.py"
Cohesion: 0.18
Nodes (9): handle_refresh_github_context(), handle_refresh_gitlab_context(), handle_refresh_kargo_context(), GitHubPrRef, GitLabMrRef, GitLabPipelineRef, KargoStageRef, PollFn (+1 more)

### Community 71 - "tool_router.py"
Cohesion: 0.11
Nodes (5): _safe_int(), handle_consult_deep_memory(), handle_google_web_search(), IncidentAdapterPort, StateWatcherPort

### Community 72 - "handlers_dispatch.py"
Cohesion: 0.13
Nodes (6): handle_message_agent(), handle_reply_to_agent(), handle_report_incident(), handle_select_agent(), _resolve_escalation_scope(), _sticky_work_style()

### Community 75 - "cli-setup.js"
Cohesion: 0.13
Nodes (18): { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync }, filterSkillsByMode() (+10 more)

### Community 77 - "StateWatcher"
Cohesion: 0.13
Nodes (3): _QueueEntry, StateWatcher, _Subscription

### Community 78 - ".get_blackboard"
Cohesion: 0.15
Nodes (10): _coerce_turn_int(), handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_recall_pruned_turns(), _parse_turn_int(), handle_re_trigger_aligner(), handle_set_phase() (+2 more)

### Community 79 - "QuotaTracker"
Cohesion: 0.13
Nodes (4): QuotaExhaustedError, QuotaTracker, RequestExceedsBurstError, Reservation

### Community 80 - "devDependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 81 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 82 - "gemini-sidecar/package.json"
Cohesion: 0.11
Nodes (18): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+10 more)

### Community 85 - "jira.py"
Cohesion: 0.16
Nodes (7): approve_mission(), dismiss_mission(), _infer_phase(), _jira_config(), list_missions(), reanalyze_mission(), retry_mission()

### Community 86 - "get_report"
Cohesion: 0.11
Nodes (6): get_report(), list_reports(), reports_spa_no_slash(), reports_spa_with_slash(), search_reports(), _serve_spa()

### Community 89 - "ShiftsPage.tsx"
Cohesion: 0.23
Nodes (16): getCurrentShift(), getShiftDetail(), getShiftsList(), ShiftReportFull, ShiftReportSummary, FailedClusterBadge(), getISOWeek(), getWeekDates() (+8 more)

### Community 90 - "TokenUtilizationPage.tsx"
Cohesion: 0.21
Nodes (14): getFlowHistory(), FlowSnapshot, FlowHistoryPage(), formatTime(), RANGES, SparkCard(), SparkCardProps, formatTime() (+6 more)

### Community 91 - "catalog-skills.js"
Cohesion: 0.16
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 92 - "EventType"
Cohesion: 0.14
Nodes (4): EventType, HealthStatus, MessageStatus, MetricsRepository

### Community 93 - "approve_event"
Cohesion: 0.14
Nodes (5): approve_event(), reject_event(), TitleUpdateRequest, update_event_title(), sanitize_title()

### Community 96 - "generate_map.py"
Cohesion: 0.19
Nodes (6): _enumerate_gates(), _GateInfo, generate_phase_tool_map(), _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 97 - "handlers_planning.py"
Cohesion: 0.22
Nodes (7): _auto_complete_step(), _canonical_role(), handle_create_plan(), handle_get_plan_progress(), _is_failed_turn(), _is_orchestrator_turn(), _normalize_step_id()

### Community 102 - "slack.py"
Cohesion: 0.14
Nodes (4): get_agent_notification_text(), get_turn_attachment_color(), table_block_to_code_block(), _PlanDecision

### Community 104 - "vcs_approval.py"
Cohesion: 0.19
Nodes (7): _github_active_item(), headhunter_pending_todos(), get_gitlab_auth(), _resolve_github_head(), _resolve_gitlab_head(), resolve_live_head_sha(), verify_merge_guard()

### Community 107 - "analyzeTokens"
Cohesion: 0.19
Nodes (13): analyzeString(), analyzeTokens(), assignName(), base(), combineCategories(), configEnvGuard(), configFileWriteGuard(), hasSubseq() (+5 more)

### Community 108 - "._extract_context_flags"
Cohesion: 0.15
Nodes (3): compute_dispatch_backpressure(), ContextFlags, _safe_int_env()

### Community 116 - "_sanitize_analysis_text"
Cohesion: 0.20
Nodes (5): _clamp_confidence(), _sanitize_analysis_text(), _strip_newlines(), _validate_analysis(), _validate_triage_entry()

### Community 118 - "is_defer_event_available"
Cohesion: 0.18
Nodes (6): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 119 - "CiContextCard.tsx"
Cohesion: 0.31
Nodes (9): CiContext, CiContextCardProps, ConsoleTailBlock(), FailedJobRow(), annotationReplacer(), PIPELINE_ANNOTATION_RE, REDACTION_TRIGGER_KEYWORDS, stripAnsi() (+1 more)

### Community 120 - "NeuronInfoPanel.tsx"
Cohesion: 0.29
Nodes (10): asNumber(), asString(), asStringArray(), Badge(), describeNeuron(), Hdr(), NeuronInfoPanel(), AGENT_NEURON_COLORS (+2 more)

### Community 121 - "gitGuard"
Cohesion: 0.29
Nodes (10): bareBranchProtected(), configWriteGuard(), externalGitCommand(), gitGuard(), gitQuery(), isProtected(), normRef(), pushGuard() (+2 more)

### Community 122 - "parseShell"
Cohesion: 0.33
Nodes (10): bodySubstitutions(), decodeAnsiC(), isArrayAssignPrefix(), isWordStart(), matchBacktick(), matchParen(), parseShell(), readHeredocStart() (+2 more)

### Community 123 - "extract_tables"
Cohesion: 0.20
Nodes (5): extract_tables(), _replace(), _md_table_to_block_kit(), _md_table_to_text(), _parse_md_table()

### Community 124 - "generate_event_title"
Cohesion: 0.22
Nodes (3): generate_event_title(), get_adapter(), _get_semaphore()

### Community 127 - "entity_extractor.py"
Cohesion: 0.33
Nodes (5): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship

### Community 132 - "_prepare_console_tail"
Cohesion: 0.20
Nodes (4): _prepare_console_tail(), _redact_match(), _redact_secrets_in_text(), _sanitize_console_tail()

### Community 133 - "has_unevaluated_close_blocker"
Cohesion: 0.20
Nodes (4): has_unevaluated_close_blocker(), _pred_jarvis_response(), _pred_unevaluated_close(), is_jarvis_acknowledgment()

### Community 134 - "CortexDevPage.tsx"
Cohesion: 0.36
Nodes (8): devQueryClient, MOCK_CORTEX_STATUS, MOCK_EVENT_ID, MOCK_NEURONS, MOCK_PULSE_BATCHES, MOCK_SHADOW, MOCK_THINKING, MOCK_WHISPERS

### Community 135 - "classifyTool"
Cohesion: 0.31
Nodes (9): apiTokens(), apiWriteNeedsGuard(), branchValues(), classifyTool(), hasOpaqueTarget(), httpGuard(), httpMethod(), isReadMethod() (+1 more)

### Community 136 - "get_quota_tracker"
Cohesion: 0.22
Nodes (3): get_quota_tracker(), llm_stats(), receive_telemetry()

### Community 141 - "create_chat_event"
Cohesion: 0.25
Nodes (3): ChatEventRequest, ChatEventResponse, create_chat_event()

### Community 153 - "adf_to_markdown"
Cohesion: 0.57
Nodes (7): adf_to_markdown(), _apply_marks(), _children(), _render(), _render_list(), _render_list_item(), _render_table_like()

### Community 154 - "validate-mutations.sh"
Cohesion: 0.57
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

### Community 155 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 156 - "state.js"
Cohesion: 0.33
Nodes (4): { AGENT_ROLE }, _blackboardTurns, _inboundMessages, _teammateMessages

### Community 161 - "_append_user_turn"
Cohesion: 0.33
Nodes (3): _append_user_turn(), _is_function_response_part(), _validated_parts()

### Community 162 - "build_gate_context"
Cohesion: 0.33
Nodes (3): build_gate_context(), conversation_has_decayed_turns(), _decay_payload_len()

### Community 171 - "classify"
Cohesion: 0.50
Nodes (4): classify(), main(), shellCategory(), shellNeedsGuard()

## Knowledge Gaps
- **13 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+8 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2298 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **111 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `main.py`, `Brain`, `logging`, `models.py`, `nightwatcher_tools.py`, `EventDocument`, `create_chat_event`, `EventEvidence`, `brain.py`, `BrainSkillLoader`, `queue.py`, `.get_event`, `ConversationMessage`, `observations_mgmt.py`, `ScheduleRepository`, `auth.py`, `ConversationTurn`, `HeadhunterJira`, `DashboardWSAdapter`, `PulseBatch`, `tool_router.py`, `.get_blackboard`, `LiveAPIAdapter`, `jira.py`, `get_report`, `EventType`, `approve_event`, `slack.py`, `generate_event_title`?**
  _High betweenness centrality (0.118) - this node is a cross-community bridge._
- **Are the 80 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 80 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.010988567042378702 - nodes in this community are weakly interconnected._
- **Why does `Brain` connect `Brain` to `BlackboardState`, `main.py`, `Archivist`, `EventDocument`, `AgentRegistry`, `EventEvidence`, `brain.py`, `BrainSkillLoader`, `._process_with_llm`, `.get_event`, `auth.py`, `StalenessGuard`, `ResyncTrigger`, `._format_merge_evidence`, `._sweep_waiting_approval_zombies`, `ConversationTurn`, `.append_and_broadcast`, `.set_headhunter_close_signal`, `DashboardWSAdapter`, `PulseBatch`, `._check_jarvis_staleness`, `._determine_thinking_params_legacy`, `.get_ephemeral_provisioner`, `.get_staleness_guard_metrics`, `BrainIntrospectionPort`, `ReflexSearcher`, `StateWatcher`, `EventType`, `slack.py`, `.start_event_loop`, `._extract_context_flags`, `IdleTimeoutManager`, `ReconcileScheduler`, `resolve_maintainer_emails`, `._post_agent_recall`?**
  _High betweenness centrality (0.054) - this node is a cross-community bridge._
- **Are the 19 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 19 INFERRED edges - model-reasoned connections that need verification._
- **Should `main.py` be split into smaller, more focused modules?**
  _Cohesion score 0.019615311369263 - nodes in this community are weakly interconnected._