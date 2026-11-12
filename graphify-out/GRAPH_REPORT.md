# Graph Report - Blackboard  (2026-11-12)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 5176 nodes · 11606 edges · 225 communities (98 shown, 127 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 950 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `883804ae`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BlackboardState
- main.py
- os
- logging
- Brain
- Archivist
- client.ts
- nightwatcher_tools.py
- App.tsx
- slack.py
- EventDocument
- tool_gates.py
- EventSidebar.tsx
- WorkspaceInspector.tsx
- http-handler.js
- react
- EventChatPanel.tsx
- brain.py
- ._process_with_llm
- jenkins-mcp.js
- ToolContext
- hooks/index.ts
- _BrainToolContext
- merge-guard.js
- GeminiAdapter
- handlers_integration.py
- ConversationTurn
- OpsStateContext.tsx
- cli-executor.js
- storage-recycler.js
- TurnBubble.tsx
- JenkinsAdapter
- KnowledgeGraphStore
- EventRepository
- EventDrillDown.tsx
- Aligner
- GitHubPlatform
- observations_mgmt.py
- CortexGraph.tsx
- llm/__init__.py
- GitLabPlatform
- gemini_client.py
- Headhunter
- TimeKeeperPage.tsx
- ws-client.js
- useQueue.ts
- ._build_system_prompt
- context_parts.py
- StreamGrid.tsx
- httpx
- queue.py
- useCortexData.ts
- FairQueue
- ui/package.json
- get_archivist
- server.js
- ArchitectureGraph.tsx
- tool_router.py
- .get_event
- SlackChannel
- ArgoCDObserver
- reconcile.py
- event_to_markdown
- BrainSkillLoader
- ._get_manager
- KargoObserver
- TopologyRepository
- GitHubAppAuth
- dependencies
- quota_tracker.py
- StateWatcher
- adf_to_markdown
- LiveAPIAdapter
- IdleTimeoutManager
- compilerOptions
- claude-guard.js
- VcsPlatformPort
- cli-setup.js
- approve_event
- ReflexSearcher
- devDependencies
- compilerOptions
- gemini-sidecar/package.json
- DashboardWSAdapter
- PulseBatch
- EphemeralProvisioner
- get_report
- JenkinsObserver
- ._gate_check
- EventStatus
- ObservationRepository
- ShiftsPage.tsx
- catalog-skills.js
- EscalationRepository
- TokenUtilizationPage.tsx
- generate_map.py
- OIDCKeyAdapter
- KubernetesSpawnHealthAdapter
- ._discover
- ServiceNode.tsx
- handlers_planning.py
- ScheduleRepository
- MultiInstallationManager
- analyzeTokens
- ._extract_context_flags
- BrainIntrospectionPort
- TokenMeter
- ScheduleCreateRequest
- JarvisMemoryPage.tsx
- _sanitize_analysis_text
- ._authorize_plan_decision
- NeuronInfoPanel.tsx
- testSetup.ts
- is_defer_event_available
- SlackAccessGate
- cortex-constants.ts
- CortexDevPage.tsx
- spawn_health.py
- gitGuard
- parseShell
- ._github_poll_and_process
- ._process_candidates
- _prepare_console_tail
- close_event_by_user
- io
- classifyTool
- get_quota_tracker
- _is_event_closed_or_missing
- PulseTracker
- SpawnPollResult
- SmartsheetMaintainerCache
- .has_reeval_signal
- MessageStatus
- MetricsRepository
- AsyncGitHubClient
- GitLabTokenAuth
- ._evaluate_health
- HeadhunterJira
- ._triage_and_build_evidence
- ._drain_once
- ._register_handlers
- ConversationMessage
- TimeKeeperObserver
- update_knowledge
- CortexRepository
- validate-mutations.sh
- FilterRule
- ._detect_repetition_collapse
- BrainLifecyclePort
- scripts
- state.js
- ._process_message
- .__init__
- DispatchMetrics
- _append_user_turn
- list_failed_stages
- dex_proxy
- ._wait_for_registration
- submit_feedback
- delete_knowledge
- classify
- derive_llm_priority
- TitleUpdateRequest
- rebuild_deep_memory
- require-results.sh
- _WSFrameFilter
- TokenUsageDict
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
- build_gate_context
- diagnose_rejection
- GateDefinition
- _pred_dispatch_defer
- _pred_hard_strip_defer
- _pred_jarvis_response
- _pred_jarvis_wait
- _pred_obs_plateau
- _pred_silent_park
- _pred_unevaluated_close
- _tools_wait_loop

## God Nodes (most connected - your core abstractions)
1. `BlackboardState` - 285 edges
2. `Brain` - 155 edges
3. `ConversationTurn` - 125 edges
4. `ToolContext` - 103 edges
5. `GateContext` - 94 edges
6. `react` - 85 edges
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

## Communities (225 total, 127 thin omitted)

### Community 0 - "BlackboardState"
Cohesion: 0.01
Nodes (22): list_events(), get_all_journal(), get_service_journal(), delete_notebook_note(), get_notebook(), get_current_shift(), get_shift_detail(), list_shifts() (+14 more)

### Community 1 - "main.py"
Cohesion: 0.02
Nodes (51): AgentConnection, AgentRegistry, agent_websocket_handler(), Architect, AgentClient, Developer, _build_prompt(), _check_security() (+43 more)

### Community 2 - "os"
Cohesion: 0.02
Nodes (40): _annotation_replace(), _strip_pipeline_annotations(), _heartbeat(), _sanitize_lesson_text(), _get_static_maintainer_emails(), _get_allowed_mention_authors(), _get_static_maintainer_emails(), _safe_int() (+32 more)

### Community 3 - "logging"
Cohesion: 0.03
Nodes (35): can_append_message(), _claims_to_user(), get_user_from_request(), get_user_from_slack(), get_user_from_websocket(), require_auth(), require_obs_admin(), UserContext (+27 more)

### Community 5 - "Archivist"
Cohesion: 0.04
Nodes (4): Archivist, _decode_cursor(), _encode_cursor(), VectorStore

### Community 6 - "client.ts"
Cohesion: 0.04
Nodes (82): recharts, bulkDeleteObservations(), deleteObservation(), exportObservations(), ExtractedCorrection, ExtractedLesson, ExtractionResult, generateObservationsReport() (+74 more)

### Community 7 - "nightwatcher_tools.py"
Cohesion: 0.04
Nodes (32): JiraIncidentAdapter, PulseContext, ShiftIncident, ShiftInvestigation, _append_user_turn(), _env_float(), _env_int(), NightwatcherObserver (+24 more)

### Community 8 - "App.tsx"
Cohesion: 0.05
Nodes (66): react-dom, react-router-dom, @tanstack/react-query, getConfig(), getReport(), getReports(), getWSAuthFailureCallback(), setOnUnauthorized() (+58 more)

### Community 9 - "slack.py"
Cohesion: 0.04
Nodes (30): generate_event_title(), get_adapter(), _get_semaphore(), spawn_event_namer_task(), create_adapter(), resolve_approval_identity(), build_access_denied_home_view(), build_home_tab_view() (+22 more)

### Community 10 - "EventDocument"
Cohesion: 0.03
Nodes (12): _close_unanswered_fc(), _build_closed_block(), build_event_header(), _build_identity_block(), _build_journal_block(), _build_mermaid_block(), _build_related_block(), _build_subject_block() (+4 more)

### Community 11 - "tool_gates.py"
Cohesion: 0.05
Nodes (78): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+70 more)

### Community 12 - "EventSidebar.tsx"
Cohesion: 0.06
Nodes (69): getHeadhunterPending(), getJiraMissions(), HeadhunterTodo, postJiraAction(), AgentRegistryEntry, CiContext, CiContextCard(), CiContextCardProps (+61 more)

### Community 13 - "WorkspaceInspector.tsx"
Cohesion: 0.06
Nodes (59): ConversationTurn, EventEvidence, TokenUsageDict, AgentStreamCard(), AgentStreamCardProps, MessageCards(), BORDER_COLOR, PlanProgress() (+51 more)

### Community 14 - "http-handler.js"
Cohesion: 0.08
Nodes (62): is429Error(), registerMCPsAndHooks(), resolveCommand(), writeAgyMcpServer(), writeClaudeMcpServer(), parsePositiveInt(), buildArgoCDMcpConfig(), createAppJWT() (+54 more)

### Community 15 - "react"
Cohesion: 0.07
Nodes (57): lucide-react, react, applyLessons(), correctMemory(), createKnowledge(), createLesson(), deleteKnowledge(), deleteLesson() (+49 more)

### Community 16 - "EventChatPanel.tsx"
Cohesion: 0.08
Nodes (38): @tanstack/react-table, closeEvent(), enforceCasualDomain(), getEventReport(), ReportFull, ReportMeta, ConversationFeed(), ConversationFeedProps (+30 more)

### Community 17 - "brain.py"
Cohesion: 0.04
Nodes (13): _BatchContext, _compute_processed_up_to(), _has_non_user_turns(), _is_seed_turn(), _select_dispatch_tier(), get_token_meter(), Pulse, _resolve_domain() (+5 more)

### Community 18 - "._process_with_llm"
Cohesion: 0.06
Nodes (7): on_huddle(), on_progress(), on_huddle(), on_progress(), _is_automated_nudge(), _sanitize_error_text(), get_registry_and_bridge()

### Community 19 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 20 - "ToolContext"
Cohesion: 0.07
Nodes (14): handle_message_agent(), handle_reply_to_agent(), handle_report_incident(), handle_select_agent(), _resolve_escalation_scope(), _sticky_work_style(), handle_classify_event(), handle_defer_event() (+6 more)

### Community 21 - "hooks/index.ts"
Cohesion: 0.06
Nodes (43): ApiError, getClosedEvents(), getEvents(), getService(), getTopology(), ArchitectureEvent, ArgoCDOperation, Service (+35 more)

### Community 23 - "merge-guard.js"
Cohesion: 0.04
Nodes (46): API_VALUED, ARGO_MUTATING, ARGO_READ_SUB, ARGO_READ_TOP, BODY_FLAG, BROWSER_READ, CTX, ENV_BUILTINS (+38 more)

### Community 24 - "GeminiAdapter"
Cohesion: 0.08
Nodes (10): _attach_signature_to_parts(), _clone_part_with_sig(), _coerce_part(), _decode_sig_bytes(), _extract_call_syntax(), _extract_part_signature(), GeminiAdapter, _is_empty_sig_carrier() (+2 more)

### Community 25 - "handlers_integration.py"
Cohesion: 0.07
Nodes (20): _alert_wrapper_retrigger(), _do_retrigger(), _get_jira_reporter(), handle_notify_user_slack(), handle_refresh_github_context(), handle_refresh_gitlab_context(), handle_refresh_kargo_context(), _is_darwin_reentrant_caller() (+12 more)

### Community 26 - "ConversationTurn"
Cohesion: 0.12
Nodes (27): emit_tool_result(), handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_recall_pruned_turns(), handle_ask_release_ai(), handle_comment_jira_issue(), handle_fetch_jira_issue() (+19 more)

### Community 27 - "OpsStateContext.tsx"
Cohesion: 0.08
Nodes (34): createChatEvent(), getAgents(), getKargoStages(), KargoStageStatus, AgentRegistryPanel(), formatConnectedSince(), ChatInput(), ChatInputProps (+26 more)

### Community 28 - "cli-executor.js"
Cohesion: 0.09
Nodes (37): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, MAX_TASK_WALL_MS, MAX_TIMER_MS, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS, STORAGE_PRETASK_TIMEOUT_MS, resolveStorageRoot }, buildCLICommand(), buildTimeoutResult(), { checkAndRecycleStorage, pinTaskCwd, unpinTaskCwd }, CLAUDE_JSON_PATH, cp, createInactivityWatchdog(), executeCLI() (+29 more)

### Community 29 - "storage-recycler.js"
Cohesion: 0.08
Nodes (37): withTaskStorage(), MAX_TASK_WALL_MS, parseTimerMs(), resolveStorageRoot(), resolveTimeoutMs(), ROLE_TIMEOUTS, STORAGE_ACTIVITY_HEARTBEAT_MS, STORAGE_MAX_TIER3_DELETIONS (+29 more)

### Community 30 - "TurnBubble.tsx"
Cohesion: 0.11
Nodes (31): @uiw/react-markdown-preview, approveEvent(), rejectEvent(), submitFeedback(), MarkdownViewer(), MermaidBlock(), InlineMarkdownViewerProps, JournalRow() (+23 more)

### Community 31 - "JenkinsAdapter"
Cohesion: 0.06
Nodes (6): BuildDetails, JenkinsAdapter, JenkinsPlatformPort, JobResult, JobRunState, ViewScanResult

### Community 32 - "KnowledgeGraphStore"
Cohesion: 0.09
Nodes (9): _format_graph_context(), get_graph_context(), _parse_props(), _sanitize(), translate_to_lookups(), _acquire(), KnowledgeGraphStore, _sanitize() (+1 more)

### Community 34 - "EventDrillDown.tsx"
Cohesion: 0.09
Nodes (33): three, getEventPulses(), EventSource, BrainCore(), CortexHeartbeat(), CortexHeartbeatProps, ensureKeyframes(), CortexLiveFeed() (+25 more)

### Community 37 - "observations_mgmt.py"
Cohesion: 0.08
Nodes (16): get_report_client(), _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), render_pdf(), _sample_points() (+8 more)

### Community 38 - "CortexGraph.tsx"
Cohesion: 0.10
Nodes (35): graphology, @react-sigma/core, @react-sigma/layout-forceatlas2, sigma, @sigma/node-square, ActiveEvent, KGServiceEntity, eventColor() (+27 more)

### Community 39 - "llm/__init__.py"
Cohesion: 0.09
Nodes (6): ClaudeAdapter, FunctionCall, LLMChunk, LLMPort, LLMResponse, TokenUsage

### Community 41 - "gemini_client.py"
Cohesion: 0.10
Nodes (15): _parse_drain_timeout(), _get_timeout_env_warned(), _get_timeout_order_warned(), LLMStreamInterChunkTimeoutError, LLMStreamTimeoutError, LLMStreamTotalTimeoutError, LLMStreamTTFBTimeoutError, parse_timeout_env() (+7 more)

### Community 43 - "TimeKeeperPage.tsx"
Cohesion: 0.12
Nodes (24): createSchedule(), deleteSchedule(), getSchedules(), refineInstructions(), ScheduleCreatePayload, ScheduleItem, toggleSchedule(), updateSchedule() (+16 more)

### Community 44 - "ws-client.js"
Cohesion: 0.10
Nodes (26): clearIdleTimer(), {
  DEFAULT_WORK_DIR, AGENT_CLI, AGENT_MODEL, AGENT_ROLE,
  EVENT_ID, EPHEMERAL, IDLE_TIMEOUT_MS,
  CLI_429_MAX_RETRIES, CLI_429_INITIAL_DELAY_MS, CLI_429_BACKOFF_MULTIPLIER,
  resolveTimeoutMs, parsePositiveInt, MAX_TASK_WALL_MS, MAX_TIMER_MS,
}, { ensureEventDocument }, { executeCLIStreaming, prepareResultsDir, is429Error }, { filterSkillsByRole, filterSkillsByMode, swapActiveRules, restoreAllSkills }, fs, handleCancel(), handleTask() (+18 more)

### Community 45 - "useQueue.ts"
Cohesion: 0.12
Nodes (27): getActiveEvents(), getAlignerPending(), getEventDocument(), getJenkinsPending(), getWaitingApprovalEvents(), updateEventTitle(), EventDocument, MessageStatus (+19 more)

### Community 46 - "._build_system_prompt"
Cohesion: 0.08
Nodes (8): _init_tool_names(), _strip_tool_names(), _wrap_section(), Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship

### Community 47 - "context_parts.py"
Cohesion: 0.10
Nodes (14): _apply_sibling_signature(), build_function_response(), build_single_function_response(), compress_contents(), estimate_msg_tokens(), estimate_tokens(), extract_model_parts(), _get_part_sig() (+6 more)

### Community 48 - "StreamGrid.tsx"
Cohesion: 0.13
Nodes (26): Dashboard(), GridTile(), GridTileProps, TileType, InlineMarkdownViewer(), EmptyState(), LayoutMode, StreamGrid() (+18 more)

### Community 49 - "httpx"
Cohesion: 0.11
Nodes (12): approve_mission(), dismiss_mission(), _infer_phase(), _jira_config(), list_missions(), reanalyze_mission(), retry_mission(), get_gitlab_auth() (+4 more)

### Community 50 - "queue.py"
Cohesion: 0.11
Nodes (16): apply_lessons(), correct_memory(), CorrectMemoryRequest, create_knowledge(), create_lesson(), enforce_casual_domain(), EnforceCasualRequest, extract_lessons() (+8 more)

### Community 51 - "useCortexData.ts"
Cohesion: 0.17
Nodes (27): getCognitiveGraph(), getCortexActivity(), getKGServiceDetail(), getKGServices(), getKGStats(), getKnowledgeById(), getMemory(), getRecentPulses() (+19 more)

### Community 53 - "ui/package.json"
Cohesion: 0.09
Nodes (25): autoprefixer, cronstrue, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, graphology-layout-forceatlas2 (+17 more)

### Community 54 - "get_archivist"
Cohesion: 0.09
Nodes (13): get_archivist(), aligner_pending_items(), get_event_approval(), get_event_document(), get_event_report(), get_event_turns(), get_knowledge(), get_lesson() (+5 more)

### Community 55 - "server.js"
Cohesion: 0.09
Nodes (18): { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, ensureEventDocument(), fs, path, stageEventDocument(), fetchEventDocument(), fs, { handleRequest } (+10 more)

### Community 56 - "ArchitectureGraph.tsx"
Cohesion: 0.11
Nodes (21): @dagrejs/dagre, @xyflow/react, applyDagreLayout(), applyGridLayout(), applyLayout(), ArchitectureGraphInner(), buildGraph(), computeIdHash() (+13 more)

### Community 57 - "tool_router.py"
Cohesion: 0.09
Nodes (7): _safe_int(), handle_search_open_incidents(), handle_consult_deep_memory(), handle_google_web_search(), IdleTimeoutPort, IncidentAdapterPort, StateWatcherPort

### Community 58 - ".get_event"
Cohesion: 0.09
Nodes (4): get_event_document(), report_tampering(), get_event_observations(), get_global_observations()

### Community 61 - "reconcile.py"
Cohesion: 0.15
Nodes (10): sanitize_redis_port(), _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers(), main() (+2 more)

### Community 62 - "event_to_markdown"
Cohesion: 0.12
Nodes (6): CIAnalysis, _esc(), _esc_join(), event_to_markdown(), maintainer_env_key(), resolve_maintainer_emails()

### Community 67 - "GitHubAppAuth"
Cohesion: 0.11
Nodes (3): _find_pem_file(), get_github_auth(), GitHubAppAuth

### Community 68 - "dependencies"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 69 - "quota_tracker.py"
Cohesion: 0.12
Nodes (4): QuotaExhaustedError, QuotaTracker, RequestExceedsBurstError, Reservation

### Community 70 - "StateWatcher"
Cohesion: 0.11
Nodes (3): _QueueEntry, StateWatcher, _Subscription

### Community 71 - "adf_to_markdown"
Cohesion: 0.13
Nodes (9): _adf_to_text(), _escape_jql_string(), adf_to_markdown(), _apply_marks(), _children(), _render(), _render_list(), _render_list_item() (+1 more)

### Community 74 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 75 - "claude-guard.js"
Cohesion: 0.14
Nodes (18): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+10 more)

### Community 78 - "cli-setup.js"
Cohesion: 0.13
Nodes (18): { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync }, filterSkillsByMode() (+10 more)

### Community 79 - "approve_event"
Cohesion: 0.13
Nodes (7): can_approve_event(), can_override_domain(), can_rename_event(), _normalize_email(), approve_event(), reject_event(), update_event_title()

### Community 81 - "devDependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 82 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 83 - "gemini-sidecar/package.json"
Cohesion: 0.11
Nodes (18): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+10 more)

### Community 85 - "PulseBatch"
Cohesion: 0.12
Nodes (3): PulseBatch, PulsePort, PulseObserver

### Community 87 - "get_report"
Cohesion: 0.11
Nodes (6): get_report(), list_reports(), reports_spa_no_slash(), reports_spa_with_slash(), search_reports(), _serve_spa()

### Community 89 - "._gate_check"
Cohesion: 0.20
Nodes (5): handle_app_mention(), handle_approve(), handle_darwin_command(), handle_home_create_event(), on_dm_message()

### Community 90 - "EventStatus"
Cohesion: 0.12
Nodes (7): EventStatus, _defer_timeline_fields(), _has_active_subscription(), list_active_events(), list_closed_events(), list_waiting_approval_events(), _serialize_evidence()

### Community 92 - "ShiftsPage.tsx"
Cohesion: 0.23
Nodes (16): getCurrentShift(), getShiftDetail(), getShiftsList(), ShiftReportFull, ShiftReportSummary, FailedClusterBadge(), getISOWeek(), getWeekDates() (+8 more)

### Community 93 - "catalog-skills.js"
Cohesion: 0.16
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 95 - "TokenUtilizationPage.tsx"
Cohesion: 0.23
Nodes (13): getFlowHistory(), FlowSnapshot, FlowHistoryPage(), formatTime(), RANGES, SparkCard(), SparkCardProps, formatTime() (+5 more)

### Community 96 - "generate_map.py"
Cohesion: 0.19
Nodes (6): _enumerate_gates(), _GateInfo, generate_phase_tool_map(), _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 101 - "ServiceNode.tsx"
Cohesion: 0.20
Nodes (11): HealthStatus, NodeType, AppNodeData, ARGOCD_HEALTH_COLORS, SYNC_ICONS, GENERIC_TAGS, HEALTH_COLORS, NODE_ICONS (+3 more)

### Community 102 - "handlers_planning.py"
Cohesion: 0.23
Nodes (7): _auto_complete_step(), _canonical_role(), handle_create_plan(), handle_get_plan_progress(), _is_failed_turn(), _is_orchestrator_turn(), _normalize_step_id()

### Community 106 - "analyzeTokens"
Cohesion: 0.19
Nodes (13): analyzeString(), analyzeTokens(), assignName(), base(), combineCategories(), configEnvGuard(), configFileWriteGuard(), hasSubseq() (+5 more)

### Community 107 - "._extract_context_flags"
Cohesion: 0.15
Nodes (3): compute_dispatch_backpressure(), ContextFlags, _safe_int_env()

### Community 111 - "JarvisMemoryPage.tsx"
Cohesion: 0.27
Nodes (12): dismissProposals(), EnhancementProposal, getHandoffReports(), getProposals(), HandoffReport, FilterMode, formatDate(), formatTime() (+4 more)

### Community 115 - "_sanitize_analysis_text"
Cohesion: 0.20
Nodes (5): _clamp_confidence(), _sanitize_analysis_text(), _strip_newlines(), _validate_analysis(), _validate_triage_entry()

### Community 116 - "._authorize_plan_decision"
Cohesion: 0.17
Nodes (3): _PlanDecision, handle_reject(), _mask_email()

### Community 117 - "NeuronInfoPanel.tsx"
Cohesion: 0.26
Nodes (11): asNumber(), asString(), asStringArray(), Badge(), describeNeuron(), Hdr(), NeuronInfoPanel(), NeuronInfoPanelProps (+3 more)

### Community 118 - "testSetup.ts"
Cohesion: 0.18
Nodes (5): @tailwindcss/vite, @testing-library/react, vite, @vitejs/plugin-react, vitest

### Community 119 - "is_defer_event_available"
Cohesion: 0.18
Nodes (6): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 121 - "cortex-constants.ts"
Cohesion: 0.18
Nodes (10): AGENTS, DOMAINS, HEMISPHERE_X, NEURON_DESCRIPTIONS, PHASE_SKILL_FOLDERS, PHASE_TOOL_PRIORITY, PHASES, StructuralEdge (+2 more)

### Community 122 - "CortexDevPage.tsx"
Cohesion: 0.31
Nodes (9): CortexDevPage(), devQueryClient, MOCK_CORTEX_STATUS, MOCK_EVENT_ID, MOCK_NEURONS, MOCK_PULSE_BATCHES, MOCK_SHADOW, MOCK_THINKING (+1 more)

### Community 124 - "gitGuard"
Cohesion: 0.29
Nodes (10): bareBranchProtected(), configWriteGuard(), externalGitCommand(), gitGuard(), gitQuery(), isProtected(), normRef(), pushGuard() (+2 more)

### Community 125 - "parseShell"
Cohesion: 0.33
Nodes (10): bodySubstitutions(), decodeAnsiC(), isArrayAssignPrefix(), isWordStart(), matchBacktick(), matchParen(), parseShell(), readHeredocStart() (+2 more)

### Community 131 - "_prepare_console_tail"
Cohesion: 0.20
Nodes (4): _prepare_console_tail(), _redact_match(), _redact_secrets_in_text(), _sanitize_console_tail()

### Community 134 - "classifyTool"
Cohesion: 0.31
Nodes (9): apiTokens(), apiWriteNeedsGuard(), branchValues(), classifyTool(), hasOpaqueTarget(), httpGuard(), httpMethod(), isReadMethod() (+1 more)

### Community 135 - "get_quota_tracker"
Cohesion: 0.22
Nodes (3): get_quota_tracker(), llm_stats(), receive_telemetry()

### Community 141 - "MessageStatus"
Cohesion: 0.28
Nodes (3): HealthStatus, MessageStatus, NodeType

### Community 155 - "update_knowledge"
Cohesion: 0.25
Nodes (4): demote_lesson(), KnowledgeUpdateRequest, update_knowledge(), verify_lesson()

### Community 158 - "validate-mutations.sh"
Cohesion: 0.57
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

### Community 162 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 163 - "state.js"
Cohesion: 0.33
Nodes (4): { AGENT_ROLE }, _blackboardTurns, _inboundMessages, _teammateMessages

### Community 174 - "_append_user_turn"
Cohesion: 0.33
Nodes (3): _append_user_turn(), _is_function_response_part(), _validated_parts()

### Community 185 - "classify"
Cohesion: 0.50
Nodes (4): classify(), main(), shellCategory(), shellNeedsGuard()

### Community 198 - "overrides"
Cohesion: 0.67
Nodes (3): overrides, @typescript-eslint/typescript-estree, minimatch

## Knowledge Gaps
- **13 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+8 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2269 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **127 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `main.py`, `os`, `logging`, `Brain`, `io`, `close_event_by_user`, `nightwatcher_tools.py`, `slack.py`, `PulseTracker`, `EventDocument`, `MessageStatus`, `brain.py`, `HeadhunterJira`, `ToolContext`, `ConversationMessage`, `ConversationTurn`, `.drain_notes`, `observations_mgmt.py`, `.__init__`, `._restage_pending_signal`, `httpx`, `queue.py`, `._stage_pending_signal`, `submit_feedback`, `get_archivist`, `._count_pending`, `tool_router.py`, `.get_event`, `rebuild_deep_memory`, `.cleanup_stale_services`, `._drain_pending`, `LiveAPIAdapter`, `approve_event`, `DashboardWSAdapter`, `get_report`, `EventStatus`, `ScheduleRepository`?**
  _High betweenness centrality (0.128) - this node is a cross-community bridge._
- **Are the 80 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 80 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.010906100264607022 - nodes in this community are weakly interconnected._
- **Why does `EventEvidence` connect `os` to `BlackboardState`, `logging`, `Brain`, `Archivist`, `_is_event_closed_or_missing`, `slack.py`, `EventDocument`, `brain.py`, `HeadhunterJira`, `._triage_and_build_evidence`, `TimeKeeperObserver`, `EventRepository`, `Aligner`, `GitHubPlatform`, `GitLabPlatform`, `queue.py`, `SlackChannel`, `event_to_markdown`, `LiveAPIAdapter`, `DashboardWSAdapter`, `JenkinsObserver`, `._gate_check`, `EventStatus`, `.create_platform_event`, `.poll_and_process`, `ScheduleCreateRequest`?**
  _High betweenness centrality (0.053) - this node is a cross-community bridge._
- **Are the 19 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 19 INFERRED edges - model-reasoned connections that need verification._
- **Should `main.py` be split into smaller, more focused modules?**
  _Cohesion score 0.016951608229498694 - nodes in this community are weakly interconnected._