# Graph Report - Blackboard  (2026-11-15)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 5294 nodes · 11894 edges · 247 communities (104 shown, 143 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 956 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `fa773dc6`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BlackboardState
- logging
- queue.py
- main.py
- nightwatcher_tools.py
- client.ts
- Archivist
- OpsStateContext.tsx
- tool_gates.py
- EventChatPanel.tsx
- EventSidebar.tsx
- Brain
- http-handler.js
- react
- App.tsx
- jenkins-mcp.js
- ArchitectureGraph.tsx
- ._process_with_llm
- ._run_agent_task
- ReconcileScheduler
- TurnBubble.tsx
- _BrainToolContext
- merge-guard.js
- EventRepository
- WorkspaceInspector.tsx
- cli-executor.js
- storage-recycler.js
- EventDocument
- JenkinsAdapter
- observations_mgmt.py
- Aligner
- GitHubPlatform
- useActiveEvents
- slack.py
- ConversationTurn
- ToolContext
- CortexGraph.tsx
- llm/__init__.py
- GeminiAdapter
- GitLabPlatform
- Headhunter
- TimeKeeperPage.tsx
- ws-client.js
- ui/package.json
- SlackChannel
- EventDrillDown.tsx
- context_parts.py
- KnowledgeGraphStore
- LiveAPIAdapter
- server.js
- StateWatcher
- ._close_and_broadcast
- ._process_event_inner
- spawn_event_namer_task
- ._triage_and_build_evidence
- cognitive_graph.py
- useCortexData.ts
- gemini_client.py
- lifespan
- PulseBatch
- ArgoCDObserver
- reconcile.py
- agents/__init__.py
- .get_blackboard
- prompt.py
- ._get_manager
- KargoObserver
- TopologyRepository
- dependencies
- adf_to_markdown
- ._build_contents
- types.py
- compilerOptions
- claude-guard.js
- scheduling/__init__.py
- FlowHistoryPage.tsx
- AgentRegistry
- GitHubAppAuth
- VcsPlatformPort
- cli-setup.js
- dispatch.py
- ReflexSearcher
- JenkinsObserver
- devDependencies
- FloatingWindow.tsx
- compilerOptions
- gemini-sidecar/package.json
- TaskBridge
- DashboardWSAdapter
- .__init__
- EphemeralProvisioner
- ObservationRepository
- ShiftsPage.tsx
- catalog-skills.js
- SlackAccessGate
- src/ports.py
- EscalationRepository
- cortex/types.ts
- BrainSkillLoader
- handle_report_incident
- FairQueue
- generate_map.py
- handlers_lookup.py
- OIDCKeyAdapter
- KubernetesSpawnHealthAdapter
- ._discover
- get_report
- ServiceNode.tsx
- observations_reporter.py
- ._connect
- ._build_system_prompt
- handlers_planning.py
- ScheduleRepository
- MultiInstallationManager
- analyzeTokens
- FilterRule
- ._send_turn_to_thread
- ScheduleCreateRequest
- get_current_shift
- IdleTimeoutManager
- CiContextCard.tsx
- NeuronInfoPanel.tsx
- ._process_message
- compress_contents
- ._authorize_plan_decision
- testSetup.ts
- QuotaTracker
- TokenMeter
- is_defer_event_available
- gitGuard
- parseShell
- generate_event_title
- ._extract_context_flags
- ._post_agent_recall
- entity_extractor.py
- handlers_verification.py
- ._github_poll_and_process
- ._process_candidates
- ._drain_once
- BrainIntrospectionPort
- delete_schedule
- CortexDevPage.tsx
- spawn_health.py
- classifyTool
- SpawnPollResult
- SmartsheetMaintainerCache
- .has_reeval_signal
- MetricsRepository
- AsyncGitHubClient
- GitLabTokenAuth
- _is_event_closed_or_missing
- ._evaluate_health
- HeadhunterJira
- LLMStreamInterChunkTimeoutError
- has_unevaluated_close_blocker
- TimeKeeperObserver
- CortexRepository
- validate-mutations.sh
- llm_stats
- update_schedule
- ._detect_repetition_collapse
- _format_graph_context
- Any
- get_all_journal
- create_schedule
- scripts
- security.py
- state.js
- io
- DispatchMetrics
- build_gate_context
- list_failed_stages
- dex_proxy
- ._wait_for_registration
- handle_recall_pruned_turns
- _resolve_slack_user
- agent_ws_endpoint
- get_notebook
- toggle_schedule
- classify
- Reservation
- delete_notebook_note
- list_reports
- require-results.sh
- _WSFrameFilter
- TokenUsageDict
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
1. `BlackboardState` - 285 edges
2. `Brain` - 166 edges
3. `ConversationTurn` - 127 edges
4. `ToolContext` - 103 edges
5. `GateContext` - 99 edges
6. `react` - 85 edges
7. `EventDocument` - 82 edges
8. `fetchApi()` - 66 edges
9. `lifespan()` - 65 edges
10. `LiveAPIAdapter` - 64 edges

## Surprising Connections (you probably didn't know these)
- `MetricsRepository` --uses--> `ArchitectureEvent`  [INFERRED]
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

## Communities (247 total, 143 thin omitted)

### Community 0 - "BlackboardState"
Cohesion: 0.01
Nodes (47): _sanitize_recalled(), AppNode, ArchitectureEvent, ChatRequest, ChatResponse, CIAnalysis, EventInput, EventMetrics (+39 more)

### Community 1 - "logging"
Cohesion: 0.03
Nodes (30): _annotation_replace(), _strip_pipeline_annotations(), _safe_score(), _sanitize_lesson_text(), get_graph_context(), translate_to_lookups(), _get_static_maintainer_emails(), _get_allowed_mention_authors() (+22 more)

### Community 2 - "queue.py"
Cohesion: 0.02
Nodes (63): get_token_meter(), can_append_message(), can_approve_event(), can_override_domain(), can_rename_event(), _claims_to_user(), get_user_from_request(), get_user_from_slack() (+55 more)

### Community 3 - "main.py"
Cohesion: 0.02
Nodes (45): get_aligner(), get_architect(), get_argocd_observer(), get_blackboard(), get_brain(), get_developer(), get_kargo_observer(), get_kg_store() (+37 more)

### Community 4 - "nightwatcher_tools.py"
Cohesion: 0.03
Nodes (39): JiraIncidentAdapter, record_token_usage(), QuotaExhaustedError, RequestExceedsBurstError, PulseContext, ShiftIncident, ShiftInvestigation, ShiftReport (+31 more)

### Community 5 - "client.ts"
Cohesion: 0.03
Nodes (91): @tanstack/react-query, ApiError, bulkDeleteObservations(), deleteNote(), deleteObservation(), exportObservations(), ExtractedCorrection, ExtractedLesson (+83 more)

### Community 6 - "Archivist"
Cohesion: 0.04
Nodes (5): Archivist, Pulse, _decode_cursor(), _encode_cursor(), VectorStore

### Community 7 - "OpsStateContext.tsx"
Cohesion: 0.05
Nodes (62): react-router-dom, createChatEvent(), getEventDocument(), getKargoStages(), updateEventTitle(), AppConfig, KargoStageStatus, ChatInput() (+54 more)

### Community 8 - "tool_gates.py"
Cohesion: 0.05
Nodes (79): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+71 more)

### Community 9 - "EventChatPanel.tsx"
Cohesion: 0.06
Nodes (51): getReport(), getReports(), ReportFull, ReportMeta, DeferCountdownBar(), CompactCardStrip(), EventHistory(), TimeRange (+43 more)

### Community 10 - "EventSidebar.tsx"
Cohesion: 0.06
Nodes (71): getAlignerPending(), getHeadhunterPending(), getJenkinsPending(), getJiraMissions(), getWaitingApprovalEvents(), HeadhunterTodo, postJiraAction(), AgentRegistryEntry (+63 more)

### Community 12 - "http-handler.js"
Cohesion: 0.08
Nodes (62): is429Error(), registerMCPsAndHooks(), resolveCommand(), writeAgyMcpServer(), writeClaudeMcpServer(), parsePositiveInt(), buildArgoCDMcpConfig(), createAppJWT() (+54 more)

### Community 13 - "react"
Cohesion: 0.07
Nodes (58): lucide-react, react, applyLessons(), correctMemory(), createKnowledge(), createLesson(), deleteKnowledge(), deleteLesson() (+50 more)

### Community 14 - "App.tsx"
Cohesion: 0.06
Nodes (50): oidc-client-ts, react-dom, dismissProposals(), EnhancementProposal, getConfig(), getHandoffReports(), getProposals(), getWSAuthFailureCallback() (+42 more)

### Community 15 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 16 - "ArchitectureGraph.tsx"
Cohesion: 0.06
Nodes (47): @dagrejs/dagre, @xyflow/react, getClosedEvents(), getEvents(), ArchitectureEvent, ArgoCDOperation, ActivityStream(), applyDagreLayout() (+39 more)

### Community 17 - "._process_with_llm"
Cohesion: 0.04
Nodes (5): _BatchContext, _contents_have_pruned_or_decayed(), _ensure_recall_tool_if_needed(), _QuotaShedState, _retry_backoff_delay()

### Community 18 - "._run_agent_task"
Cohesion: 0.07
Nodes (6): on_huddle(), on_progress(), on_huddle(), on_progress(), _select_dispatch_tier(), get_registry_and_bridge()

### Community 19 - "ReconcileScheduler"
Cohesion: 0.05
Nodes (6): FlowCollector, ReconcileScheduler, Trigger, QueueTrigger, ResyncTrigger, StalenessGuard

### Community 20 - "TurnBubble.tsx"
Cohesion: 0.09
Nodes (39): @uiw/react-markdown-preview, approveEvent(), closeEvent(), enforceCasualDomain(), getEventReport(), rejectEvent(), submitFeedback(), ConversationFeed() (+31 more)

### Community 22 - "merge-guard.js"
Cohesion: 0.04
Nodes (46): API_VALUED, ARGO_MUTATING, ARGO_READ_SUB, ARGO_READ_TOP, BODY_FLAG, BROWSER_READ, CTX, ENV_BUILTINS (+38 more)

### Community 24 - "WorkspaceInspector.tsx"
Cohesion: 0.09
Nodes (38): ConversationTurn, EventEvidence, TokenUsageDict, BORDER_COLOR, PlanProgress(), PlanProgressProps, STATUS_ICON, DiffFile (+30 more)

### Community 25 - "cli-executor.js"
Cohesion: 0.09
Nodes (37): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, MAX_TASK_WALL_MS, MAX_TIMER_MS, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS, STORAGE_PRETASK_TIMEOUT_MS, resolveStorageRoot }, buildCLICommand(), buildTimeoutResult(), { checkAndRecycleStorage, pinTaskCwd, unpinTaskCwd }, CLAUDE_JSON_PATH, cp, createInactivityWatchdog(), executeCLI() (+29 more)

### Community 26 - "storage-recycler.js"
Cohesion: 0.08
Nodes (37): withTaskStorage(), MAX_TASK_WALL_MS, parseTimerMs(), resolveStorageRoot(), resolveTimeoutMs(), ROLE_TIMEOUTS, STORAGE_ACTIVITY_HEARTBEAT_MS, STORAGE_MAX_TIER3_DELETIONS (+29 more)

### Community 28 - "JenkinsAdapter"
Cohesion: 0.06
Nodes (6): BuildDetails, JenkinsAdapter, JenkinsPlatformPort, JobResult, JobRunState, ViewScanResult

### Community 29 - "observations_mgmt.py"
Cohesion: 0.06
Nodes (12): get_report_client(), render_pdf(), get_event_observations(), get_global_observations(), bulk_delete_observations(), BulkDeleteRequest, delete_observation(), export_observations() (+4 more)

### Community 32 - "useActiveEvents"
Cohesion: 0.10
Nodes (33): getActiveEvents(), getFlowMetrics(), FlowMetrics, FlowHealthWidget(), queueColor(), wipColor(), GridTile(), GridTileProps (+25 more)

### Community 33 - "slack.py"
Cohesion: 0.08
Nodes (15): build_access_denied_home_view(), build_home_tab_view(), _context_line(), create_feedback_block(), format_plan_block(), format_task_card(), format_tool_result_blocks(), format_turn() (+7 more)

### Community 34 - "ConversationTurn"
Cohesion: 0.12
Nodes (23): emit_tool_result(), handle_post_sticky_note(), handle_read_sticky_notes(), _get_jira_reporter(), handle_ask_release_ai(), handle_comment_jira_issue(), handle_fetch_jira_issue(), handle_greenwave() (+15 more)

### Community 35 - "ToolContext"
Cohesion: 0.10
Nodes (9): handle_message_agent(), handle_reply_to_agent(), handle_select_agent(), _sticky_work_style(), handle_defer_event(), handle_respond_to_jarvis(), handle_wait_for_agent(), handle_wait_for_jarvis() (+1 more)

### Community 36 - "CortexGraph.tsx"
Cohesion: 0.09
Nodes (35): graphology, AGENTS, DOMAINS, eventColor(), getExecutiveNeurons(), getStructuralEdges(), HEMISPHERE_X, NEURON_DESCRIPTIONS (+27 more)

### Community 37 - "llm/__init__.py"
Cohesion: 0.09
Nodes (6): ClaudeAdapter, FunctionCall, LLMChunk, LLMPort, LLMResponse, TokenUsage

### Community 38 - "GeminiAdapter"
Cohesion: 0.11
Nodes (5): _attach_signature_to_parts(), _extract_part_signature(), GeminiAdapter, _is_empty_sig_carrier(), _part_has_fc()

### Community 41 - "TimeKeeperPage.tsx"
Cohesion: 0.12
Nodes (24): createSchedule(), deleteSchedule(), getSchedules(), refineInstructions(), ScheduleCreatePayload, ScheduleItem, toggleSchedule(), updateSchedule() (+16 more)

### Community 42 - "ws-client.js"
Cohesion: 0.10
Nodes (26): clearIdleTimer(), {
  DEFAULT_WORK_DIR, AGENT_CLI, AGENT_MODEL, AGENT_ROLE,
  EVENT_ID, EPHEMERAL, IDLE_TIMEOUT_MS,
  CLI_429_MAX_RETRIES, CLI_429_INITIAL_DELAY_MS, CLI_429_BACKOFF_MULTIPLIER,
  resolveTimeoutMs, parsePositiveInt, MAX_TASK_WALL_MS, MAX_TIMER_MS,
}, { ensureEventDocument }, { executeCLIStreaming, prepareResultsDir, is429Error }, { filterSkillsByRole, filterSkillsByMode, swapActiveRules, restoreAllSkills }, fs, handleCancel(), handleTask() (+18 more)

### Community 43 - "ui/package.json"
Cohesion: 0.08
Nodes (29): autoprefixer, cronstrue, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, graphology-layout-forceatlas2 (+21 more)

### Community 45 - "EventDrillDown.tsx"
Cohesion: 0.12
Nodes (25): three, getEventPulses(), BrainCore(), CortexDevPage(), CortexHeartbeat(), CortexHeartbeatProps, ensureKeyframes(), CortexLiveFeed() (+17 more)

### Community 46 - "context_parts.py"
Cohesion: 0.12
Nodes (12): _apply_sibling_signature(), build_function_response(), build_single_function_response(), extract_model_parts(), format_evidence_decay_reference(), _get_part_sig(), _is_empty_carrier_dict(), normalize_response_parts() (+4 more)

### Community 47 - "KnowledgeGraphStore"
Cohesion: 0.15
Nodes (4): _acquire(), KnowledgeGraphStore, _sanitize(), _with_timeout()

### Community 49 - "server.js"
Cohesion: 0.09
Nodes (18): { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, ensureEventDocument(), fs, path, stageEventDocument(), fetchEventDocument(), fs, { handleRequest } (+10 more)

### Community 50 - "StateWatcher"
Cohesion: 0.10
Nodes (3): _QueueEntry, StateWatcher, _Subscription

### Community 52 - "._process_event_inner"
Cohesion: 0.08
Nodes (3): _compute_processed_up_to(), _is_automated_nudge(), _sanitize_error_text()

### Community 53 - "spawn_event_namer_task"
Cohesion: 0.15
Nodes (8): spawn_event_namer_task(), handle_app_home_opened(), handle_app_mention(), handle_create_event_modal(), handle_darwin_command(), handle_home_create_event(), on_dm_message(), fallback_title()

### Community 54 - "._triage_and_build_evidence"
Cohesion: 0.09
Nodes (10): _clamp_confidence(), _prepare_console_tail(), _redact_build_parameters(), _redact_match(), _redact_secrets_in_text(), _sanitize_analysis_text(), _sanitize_console_tail(), _strip_newlines() (+2 more)

### Community 55 - "cognitive_graph.py"
Cohesion: 0.11
Nodes (11): get_pulse_tracker(), dismiss_proposals(), DismissRequest, get_all_shadow_interventions(), get_cognitive_graph(), get_cortex_activity(), get_cortex_status(), get_event_shadow_interventions() (+3 more)

### Community 56 - "useCortexData.ts"
Cohesion: 0.20
Nodes (23): getCognitiveGraph(), getCortexActivity(), getKGServiceDetail(), getKGServices(), getKGStats(), getRecentPulses(), CortexPage(), isOffRingCollection() (+15 more)

### Community 57 - "gemini_client.py"
Cohesion: 0.10
Nodes (11): _append_user_turn(), _clone_part_with_sig(), _coerce_part(), _decode_sig_bytes(), _extract_call_syntax(), _is_function_response_part(), _parse_drain_timeout(), _strip_user_thought_signature() (+3 more)

### Community 59 - "PulseBatch"
Cohesion: 0.10
Nodes (4): PulseBatch, PulsePort, PulseObserver, PulseTracker

### Community 61 - "reconcile.py"
Cohesion: 0.15
Nodes (10): sanitize_redis_port(), _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers(), main() (+2 more)

### Community 62 - "agents/__init__.py"
Cohesion: 0.12
Nodes (4): Architect, AgentClient, Developer, SysAdmin

### Community 63 - ".get_blackboard"
Cohesion: 0.13
Nodes (10): handle_inspect_event(), handle_classify_event(), handle_close_event(), handle_hold_watch(), handle_request_user_approval(), handle_wait_for_user(), handle_set_phase(), _resolve_domain() (+2 more)

### Community 64 - "prompt.py"
Cohesion: 0.14
Nodes (15): _format_bounded_journal(), _build_closed_block(), build_event_header(), _build_identity_block(), _build_journal_block(), _build_mermaid_block(), build_operational_briefing(), _build_related_block() (+7 more)

### Community 68 - "dependencies"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 69 - "adf_to_markdown"
Cohesion: 0.13
Nodes (9): _adf_to_text(), _escape_jql_string(), adf_to_markdown(), _apply_marks(), _children(), _render(), _render_list(), _render_list_item() (+1 more)

### Community 70 - "._build_contents"
Cohesion: 0.09
Nodes (3): _close_unanswered_fc(), ContextFlags, _incr_flow_counter_safely()

### Community 71 - "types.py"
Cohesion: 0.12
Nodes (11): derive_llm_priority(), _get_timeout_env_warned(), _get_timeout_order_warned(), parse_timeout_env(), _patch_enum_fields(), process_stream_call_syntax_buffer(), resolve_stream_timeouts(), set_incident_options() (+3 more)

### Community 72 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 73 - "claude-guard.js"
Cohesion: 0.14
Nodes (18): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+10 more)

### Community 74 - "scheduling/__init__.py"
Cohesion: 0.15
Nodes (10): handle_refresh_github_context(), handle_refresh_gitlab_context(), handle_refresh_kargo_context(), StateWatcherPort, GitHubPrRef, GitLabMrRef, GitLabPipelineRef, KargoStageRef (+2 more)

### Community 75 - "FlowHistoryPage.tsx"
Cohesion: 0.21
Nodes (17): recharts, getFlowHistory(), FlowSnapshot, FlowHistoryPage(), RANGES, SparkCard(), SparkCardProps, formatTime() (+9 more)

### Community 76 - "AgentRegistry"
Cohesion: 0.12
Nodes (3): AgentConnection, AgentRegistry, send_cancel()

### Community 80 - "cli-setup.js"
Cohesion: 0.13
Nodes (18): { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync }, filterSkillsByMode() (+10 more)

### Community 81 - "dispatch.py"
Cohesion: 0.15
Nodes (9): _build_prompt(), _check_security(), consume_wake_task(), _consume(), _dispatch_timeout_s(), dispatch_to_agent(), _consume_queue(), _sanitize_stdout() (+1 more)

### Community 84 - "devDependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 85 - "FloatingWindow.tsx"
Cohesion: 0.17
Nodes (16): AgentStreamCard(), AgentStreamCardProps, MessageCards(), CopyButtonProps, DEFAULT_POS, DEFAULT_SIZE, EMPTY_MESSAGES, FloatingWindow() (+8 more)

### Community 86 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 87 - "gemini-sidecar/package.json"
Cohesion: 0.11
Nodes (18): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+10 more)

### Community 88 - "TaskBridge"
Cohesion: 0.13
Nodes (4): agent_websocket_handler(), _heartbeat(), TaskBridge, set_registry_and_bridge()

### Community 93 - "ShiftsPage.tsx"
Cohesion: 0.23
Nodes (16): getCurrentShift(), getShiftDetail(), getShiftsList(), ShiftReportFull, ShiftReportSummary, FailedClusterBadge(), getISOWeek(), getWeekDates() (+8 more)

### Community 94 - "catalog-skills.js"
Cohesion: 0.16
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 99 - "cortex/types.ts"
Cohesion: 0.15
Nodes (15): ActiveEvent, EventSource, KGServiceEntity, CortexGraphProps, GraphLoaderProps, PulseTimelineProps, CognitiveGraphResponse, CortexHeartbeatMessage (+7 more)

### Community 101 - "handle_report_incident"
Cohesion: 0.12
Nodes (4): handle_report_incident(), _resolve_escalation_scope(), IdleTimeoutPort, IncidentAdapterPort

### Community 103 - "generate_map.py"
Cohesion: 0.19
Nodes (6): _enumerate_gates(), _GateInfo, generate_phase_tool_map(), _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 104 - "handlers_lookup.py"
Cohesion: 0.20
Nodes (6): _safe_int(), handle_consult_deep_memory(), handle_google_web_search(), handle_lookup_journal(), _safe_score(), _safe_seconds()

### Community 109 - "get_report"
Cohesion: 0.14
Nodes (5): get_report(), reports_spa_no_slash(), reports_spa_with_slash(), search_reports(), _serve_spa()

### Community 110 - "ServiceNode.tsx"
Cohesion: 0.20
Nodes (11): HealthStatus, NodeType, AppNodeData, ARGOCD_HEALTH_COLORS, SYNC_ICONS, GENERIC_TAGS, HEALTH_COLORS, NODE_ICONS (+3 more)

### Community 111 - "observations_reporter.py"
Cohesion: 0.21
Nodes (7): _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), _sample_points(), _summarize()

### Community 114 - "handlers_planning.py"
Cohesion: 0.23
Nodes (7): _auto_complete_step(), _canonical_role(), handle_create_plan(), handle_get_plan_progress(), _is_failed_turn(), _is_orchestrator_turn(), _normalize_step_id()

### Community 118 - "analyzeTokens"
Cohesion: 0.19
Nodes (13): analyzeString(), analyzeTokens(), assignName(), base(), combineCategories(), configEnvGuard(), configFileWriteGuard(), hasSubseq() (+5 more)

### Community 120 - "._send_turn_to_thread"
Cohesion: 0.19
Nodes (5): extract_tables(), _replace(), get_agent_notification_text(), get_turn_attachment_color(), _md_table_to_block_kit()

### Community 122 - "get_current_shift"
Cohesion: 0.15
Nodes (3): get_current_shift(), get_shift_detail(), list_shifts()

### Community 124 - "CiContextCard.tsx"
Cohesion: 0.27
Nodes (11): CiContext, CiContextCard(), CiContextCardProps, ConsoleTailBlock(), FailedJobRow(), CollapsibleSection(), annotationReplacer(), PIPELINE_ANNOTATION_RE (+3 more)

### Community 125 - "NeuronInfoPanel.tsx"
Cohesion: 0.24
Nodes (12): KGServiceDetail, asNumber(), asString(), asStringArray(), Badge(), describeNeuron(), Hdr(), NeuronInfoPanel() (+4 more)

### Community 129 - "compress_contents"
Cohesion: 0.18
Nodes (6): compress_contents(), contents_have_pruned_or_decayed(), estimate_msg_tokens(), estimate_tokens(), format_prune_notice(), prune_notice_count()

### Community 131 - "._authorize_plan_decision"
Cohesion: 0.18
Nodes (3): _PlanDecision, handle_approve(), handle_reject()

### Community 132 - "testSetup.ts"
Cohesion: 0.18
Nodes (5): @tailwindcss/vite, @testing-library/react, vite, @vitejs/plugin-react, vitest

### Community 136 - "is_defer_event_available"
Cohesion: 0.18
Nodes (6): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 137 - "gitGuard"
Cohesion: 0.29
Nodes (10): bareBranchProtected(), configWriteGuard(), externalGitCommand(), gitGuard(), gitQuery(), isProtected(), normRef(), pushGuard() (+2 more)

### Community 138 - "parseShell"
Cohesion: 0.33
Nodes (10): bodySubstitutions(), decodeAnsiC(), isArrayAssignPrefix(), isWordStart(), matchBacktick(), matchParen(), parseShell(), readHeredocStart() (+2 more)

### Community 139 - "generate_event_title"
Cohesion: 0.22
Nodes (3): generate_event_title(), get_adapter(), _get_semaphore()

### Community 142 - "entity_extractor.py"
Cohesion: 0.33
Nodes (5): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship

### Community 143 - "handlers_verification.py"
Cohesion: 0.22
Nodes (4): _alert_wrapper_retrigger(), _do_retrigger(), handle_re_trigger_aligner(), handle_wait_for_verification()

### Community 149 - "CortexDevPage.tsx"
Cohesion: 0.36
Nodes (8): devQueryClient, MOCK_CORTEX_STATUS, MOCK_EVENT_ID, MOCK_NEURONS, MOCK_PULSE_BATCHES, MOCK_SHADOW, MOCK_THINKING, MOCK_WHISPERS

### Community 151 - "classifyTool"
Cohesion: 0.31
Nodes (9): apiTokens(), apiWriteNeedsGuard(), branchValues(), classifyTool(), hasOpaqueTarget(), httpGuard(), httpMethod(), isReadMethod() (+1 more)

### Community 162 - "LLMStreamInterChunkTimeoutError"
Cohesion: 0.25
Nodes (4): LLMStreamInterChunkTimeoutError, LLMStreamTimeoutError, LLMStreamTotalTimeoutError, LLMStreamTTFBTimeoutError

### Community 163 - "has_unevaluated_close_blocker"
Cohesion: 0.25
Nodes (4): has_unevaluated_close_blocker(), _pred_jarvis_response(), _pred_unevaluated_close(), is_stabilization_wake()

### Community 166 - "validate-mutations.sh"
Cohesion: 0.57
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

### Community 170 - "_format_graph_context"
Cohesion: 0.38
Nodes (3): _format_graph_context(), _parse_props(), _sanitize()

### Community 174 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 176 - "state.js"
Cohesion: 0.33
Nodes (4): { AGENT_ROLE }, _blackboardTurns, _inboundMessages, _teammateMessages

### Community 187 - "build_gate_context"
Cohesion: 0.33
Nodes (3): build_gate_context(), conversation_has_decayed_turns(), _decay_payload_len()

### Community 194 - "handle_recall_pruned_turns"
Cohesion: 0.50
Nodes (3): _coerce_turn_int(), handle_recall_pruned_turns(), _parse_turn_int()

### Community 200 - "classify"
Cohesion: 0.50
Nodes (4): classify(), main(), shellCategory(), shellNeedsGuard()

### Community 220 - "overrides"
Cohesion: 0.67
Nodes (3): overrides, @typescript-eslint/typescript-estree, minimatch

## Knowledge Gaps
- **13 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+8 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2324 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **143 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `logging`, `queue.py`, `main.py`, `nightwatcher_tools.py`, `Brain`, `generate_event_title`, `delete_schedule`, `EventRepository`, `EventDocument`, `observations_mgmt.py`, `_is_event_closed_or_missing`, `HeadhunterJira`, `slack.py`, `ConversationTurn`, `update_schedule`, `get_all_journal`, `create_schedule`, `LiveAPIAdapter`, `lifespan`, `._restage_pending_signal`, `._stage_pending_signal`, `get_notebook`, `toggle_schedule`, `._count_pending`, `delete_notebook_note`, `list_reports`, `.cleanup_stale_services`, `._commit_pending_signal`, `._drain_pending`, `.drain_notes`, `.get_edge_metadata`, `DashboardWSAdapter`, `.__init__`, `get_report`, `observations_reporter.py`, `ScheduleRepository`, `get_current_shift`?**
  _High betweenness centrality (0.115) - this node is a cross-community bridge._
- **Are the 80 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 80 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.011963352767471794 - nodes in this community are weakly interconnected._
- **Why does `Brain` connect `Brain` to `BlackboardState`, `logging`, `main.py`, `Archivist`, `._extract_context_flags`, `._post_agent_recall`, `._process_with_llm`, `._run_agent_task`, `ReconcileScheduler`, `EventDocument`, `slack.py`, `ConversationTurn`, `._detect_repetition_collapse`, `StateWatcher`, `._close_and_broadcast`, `._process_event_inner`, `lifespan`, `PulseBatch`, `agents/__init__.py`, `._build_contents`, `._enrich_graph_from_agent`, `ReflexSearcher`, `.append_and_broadcast`, `.broadcast`, `DashboardWSAdapter`, `.__init__`, `BrainSkillLoader`, `._build_system_prompt`, `IdleTimeoutManager`?**
  _High betweenness centrality (0.065) - this node is a cross-community bridge._
- **Are the 19 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 19 INFERRED edges - model-reasoned connections that need verification._
- **Should `logging` be split into smaller, more focused modules?**
  _Cohesion score 0.027450980392156862 - nodes in this community are weakly interconnected._