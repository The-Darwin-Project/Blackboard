# Graph Report - Blackboard  (2026-11-13)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 5186 nodes · 11627 edges · 218 communities (98 shown, 120 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 950 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `be2cbabe`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BlackboardState
- logging
- queue.py
- routes/timekeeper.py
- EventSidebar.tsx
- brain.py
- client.ts
- Brain
- EventEvidence
- EventDocument
- main.py
- tool_gates.py
- App.tsx
- lucide-react
- WorkspaceInspector.tsx
- http-handler.js
- ReconcileScheduler
- ._process_with_llm
- HeadhunterJira
- jenkins-mcp.js
- react
- BrainSkillLoader
- fetchApi
- ArchitectureGraph.tsx
- _BrainToolContext
- merge-guard.js
- ScheduleRepository
- ui/package.json
- GitLabPlatform
- EventHistory.tsx
- cli-executor.js
- storage-recycler.js
- JenkinsAdapter
- EventRepository
- KnowledgeGraphStore
- observations_reporter.py
- handlers_integration.py
- AgentClient
- GitHubPlatform
- Headhunter
- EventDrillDown.tsx
- ToolContext
- TimeKeeperPage.tsx
- formatter.py
- Aligner
- ws-client.js
- useCortexData.ts
- CortexGraph.tsx
- nightwatcher_tools.py
- SlackChannel
- ClaudeAdapter
- useQueue.ts
- StreamGrid.tsx
- gemini_client.py
- TaskBridge
- LiveAPIAdapter
- tool_router.py
- server.js
- StateWatcher
- adf_to_markdown
- AgentRegistry
- GeminiAdapter
- scheduling/__init__.py
- ConversationTurn
- ArgoCDObserver
- reconcile.py
- ._close_and_broadcast
- KargoObserver
- TopologyRepository
- dependencies
- NeuronInfoPanel.tsx
- lifespan
- IdleTimeoutManager
- compilerOptions
- claude-guard.js
- BrainIntrospectionPort
- NightwatcherObserver
- GitHubAppAuth
- handlers_dispatch.py
- VcsPlatformPort
- PulseBatch
- cli-setup.js
- ReflexSearcher
- devDependencies
- compilerOptions
- nightwatcher.py
- gemini-sidecar/package.json
- event_to_markdown
- DashboardWSAdapter
- EphemeralProvisioner
- ._gate_check
- ObservationRepository
- ShiftsPage.tsx
- catalog-skills.js
- Archivist
- EscalationRepository
- VectorStore
- ._run_report_cart
- generate_map.py
- OIDCKeyAdapter
- KubernetesSpawnHealthAdapter
- JenkinsObserver
- .list_observations
- get_report
- ServiceNode.tsx
- handlers_planning.py
- MultiInstallationManager
- analyzeTokens
- FilterRule
- .scroll
- ._extract_context_flags
- QuotaTracker
- ._send_turn_to_thread
- get_current_shift
- is_defer_event_available
- ._authorize_plan_decision
- SlackAccessGate
- CortexLiveFeed.tsx
- gitGuard
- parseShell
- ._post_agent_recall
- entity_extractor.py
- ._process_candidates
- ._triage_and_build_evidence
- ._drain_once
- has_unevaluated_close_blocker
- ._register_handlers
- knowledge_graph_api.py
- spawn_health.py
- classifyTool
- SpawnPollResult
- SmartsheetMaintainerCache
- MetricsRepository
- AsyncGitHubClient
- GitLabTokenAuth
- useDeferCountdown.ts
- _is_event_closed_or_missing
- ._evaluate_health
- sanitize_call_syntax
- ConversationMessage
- TimeKeeperObserver
- CortexRepository
- validate-mutations.sh
- llm_stats
- ._detect_repetition_collapse
- QuotaExhaustedError
- scripts
- state.js
- ._process_message
- DispatchMetrics
- list_failed_stages
- dex_proxy
- BrainCore
- _BatchContext
- ._wait_for_registration
- LLMPort
- agent_ws_endpoint
- _resolve_domain
- classify
- require-results.sh
- _WSFrameFilter
- _env_flag
- TokenUsageDict
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
2. `Brain` - 156 edges
3. `ConversationTurn` - 125 edges
4. `ToolContext` - 103 edges
5. `GateContext` - 94 edges
6. `react` - 85 edges
7. `EventDocument` - 79 edges
8. `fetchApi()` - 66 edges
9. `lifespan()` - 65 edges
10. `LiveAPIAdapter` - 58 edges

## Surprising Connections (you probably didn't know these)
- `MetricsRepository` --uses--> `ArchitectureEvent`  [INFERRED]
  src/state/ports.py → src/models.py
- `Brain` --uses--> `EventType`  [INFERRED]
  src/agents/brain.py → src/models.py
- `handle_select_agent()` --uses--> `EventType`  [INFERRED]
  src/agents/handlers_dispatch.py → src/models.py
- `handle_defer_event()` --uses--> `EventType`  [INFERRED]
  src/agents/handlers_state.py → src/models.py
- `MetricsRepository` --uses--> `EventType`  [INFERRED]
  src/state/ports.py → src/models.py

## Import Cycles
- None detected.

## Communities (218 total, 120 thin omitted)

### Community 0 - "BlackboardState"
Cohesion: 0.01
Nodes (34): AppNode, ArchitectureEvent, ChatRequest, ChatResponse, EventInput, EventMetrics, EventType, FlowSnapshot (+26 more)

### Community 1 - "logging"
Cohesion: 0.03
Nodes (38): _annotation_replace(), _strip_pipeline_annotations(), _heartbeat(), _sanitize_lesson_text(), _check_security(), _get_static_maintainer_emails(), _get_allowed_mention_authors(), _get_static_maintainer_emails() (+30 more)

### Community 2 - "queue.py"
Cohesion: 0.03
Nodes (50): get_token_meter(), get_archivist(), get_brain(), EventStatus, aligner_pending_items(), apply_lessons(), close_event_by_user(), CloseRequest (+42 more)

### Community 3 - "routes/timekeeper.py"
Cohesion: 0.03
Nodes (32): get_quota_tracker(), require_auth(), require_obs_admin(), UserContext, get_blackboard(), get_pulse_tracker(), RefineRequest, RefineResponse (+24 more)

### Community 4 - "EventSidebar.tsx"
Cohesion: 0.05
Nodes (83): getJiraMissions(), HeadhunterTodo, Incident, postJiraAction(), CiContext, JenkinsPendingItem, JiraMission, ChatInput() (+75 more)

### Community 5 - "brain.py"
Cohesion: 0.03
Nodes (34): _apply_sibling_signature(), build_function_response(), build_single_function_response(), compress_contents(), estimate_msg_tokens(), estimate_tokens(), extract_model_parts(), _get_part_sig() (+26 more)

### Community 6 - "client.ts"
Cohesion: 0.03
Nodes (91): recharts, @tanstack/react-query, ApiError, bulkDeleteObservations(), deleteNote(), deleteObservation(), exportObservations(), ExtractedCorrection (+83 more)

### Community 8 - "EventEvidence"
Cohesion: 0.04
Nodes (28): generate_event_title(), get_adapter(), _get_semaphore(), spawn_event_namer_task(), create_adapter(), can_append_message(), can_approve_event(), can_override_domain() (+20 more)

### Community 9 - "EventDocument"
Cohesion: 0.03
Nodes (11): _close_unanswered_fc(), _build_closed_block(), build_event_header(), _build_identity_block(), _build_journal_block(), _build_mermaid_block(), _build_related_block(), _build_subject_block() (+3 more)

### Community 10 - "main.py"
Cohesion: 0.03
Nodes (30): Architect, set_oidc_adapter(), get_aligner(), get_architect(), get_argocd_observer(), get_developer(), get_kargo_observer(), get_report_client() (+22 more)

### Community 11 - "tool_gates.py"
Cohesion: 0.05
Nodes (78): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+70 more)

### Community 12 - "App.tsx"
Cohesion: 0.05
Nodes (63): oidc-client-ts, react-dom, dismissProposals(), EnhancementProposal, getConfig(), getFlowHistory(), getHandoffReports(), getProposals() (+55 more)

### Community 13 - "lucide-react"
Cohesion: 0.06
Nodes (51): lucide-react, react-router-dom, createChatEvent(), getAgents(), getEvents(), getKargoStages(), AgentRegistryEntry, KargoStageStatus (+43 more)

### Community 14 - "WorkspaceInspector.tsx"
Cohesion: 0.06
Nodes (58): updateEventTitle(), ConversationTurn, AgentStreamCard(), AgentStreamCardProps, MessageCards(), BORDER_COLOR, PlanProgress(), PlanProgressProps (+50 more)

### Community 15 - "http-handler.js"
Cohesion: 0.08
Nodes (62): is429Error(), registerMCPsAndHooks(), resolveCommand(), writeAgyMcpServer(), writeClaudeMcpServer(), parsePositiveInt(), buildArgoCDMcpConfig(), createAppJWT() (+54 more)

### Community 16 - "ReconcileScheduler"
Cohesion: 0.04
Nodes (7): FlowCollector, FairQueue, ReconcileScheduler, Trigger, QueueTrigger, ResyncTrigger, StalenessGuard

### Community 17 - "._process_with_llm"
Cohesion: 0.06
Nodes (9): on_huddle(), on_progress(), on_huddle(), on_progress(), _compute_processed_up_to(), _is_automated_nudge(), _sanitize_error_text(), _select_dispatch_tier() (+1 more)

### Community 18 - "HeadhunterJira"
Cohesion: 0.05
Nodes (4): format_jira_for_llm(), HeadhunterJira, _walk_adf_mentions(), _walk()

### Community 19 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 20 - "react"
Cohesion: 0.08
Nodes (46): react, @uiw/react-markdown-preview, approveEvent(), closeEvent(), enforceCasualDomain(), getEventReport(), rejectEvent(), submitFeedback() (+38 more)

### Community 21 - "BrainSkillLoader"
Cohesion: 0.05
Nodes (4): _parse_positive_int_env(), BrainSkillLoader, _SkillCorpus, _wrap_section()

### Community 22 - "fetchApi"
Cohesion: 0.09
Nodes (47): applyLessons(), correctMemory(), createKnowledge(), createLesson(), deleteKnowledge(), deleteLesson(), extractLessons(), fetchApi() (+39 more)

### Community 23 - "ArchitectureGraph.tsx"
Cohesion: 0.06
Nodes (44): @xyflow/react, getClosedEvents(), ArchitectureEvent, ArgoCDOperation, applyDagreLayout(), applyGridLayout(), applyLayout(), ArchitectureGraph() (+36 more)

### Community 25 - "merge-guard.js"
Cohesion: 0.04
Nodes (46): API_VALUED, ARGO_MUTATING, ARGO_READ_SUB, ARGO_READ_TOP, BODY_FLAG, BROWSER_READ, CTX, ENV_BUILTINS (+38 more)

### Community 26 - "ScheduleRepository"
Cohesion: 0.06
Nodes (6): ScheduleCreateRequest, ScheduledEvent, delete_schedule(), toggle_schedule(), update_schedule(), ScheduleRepository

### Community 27 - "ui/package.json"
Cohesion: 0.05
Nodes (38): autoprefixer, cronstrue, @dagrejs/dagre, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals (+30 more)

### Community 29 - "EventHistory.tsx"
Cohesion: 0.10
Nodes (35): getReport(), getReports(), ReportFull, ReportMeta, SubjectType, CompactCardStrip(), EventHistory(), TimeRange (+27 more)

### Community 30 - "cli-executor.js"
Cohesion: 0.09
Nodes (37): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, MAX_TASK_WALL_MS, MAX_TIMER_MS, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS, STORAGE_PRETASK_TIMEOUT_MS, resolveStorageRoot }, buildCLICommand(), buildTimeoutResult(), { checkAndRecycleStorage, pinTaskCwd, unpinTaskCwd }, CLAUDE_JSON_PATH, cp, createInactivityWatchdog(), executeCLI() (+29 more)

### Community 31 - "storage-recycler.js"
Cohesion: 0.08
Nodes (37): withTaskStorage(), MAX_TASK_WALL_MS, parseTimerMs(), resolveStorageRoot(), resolveTimeoutMs(), ROLE_TIMEOUTS, STORAGE_ACTIVITY_HEARTBEAT_MS, STORAGE_MAX_TIER3_DELETIONS (+29 more)

### Community 32 - "JenkinsAdapter"
Cohesion: 0.06
Nodes (6): BuildDetails, JenkinsAdapter, JenkinsPlatformPort, JobResult, JobRunState, ViewScanResult

### Community 34 - "KnowledgeGraphStore"
Cohesion: 0.09
Nodes (9): _format_graph_context(), get_graph_context(), _parse_props(), _sanitize(), translate_to_lookups(), _acquire(), KnowledgeGraphStore, _sanitize() (+1 more)

### Community 35 - "observations_reporter.py"
Cohesion: 0.06
Nodes (16): _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), render_pdf(), _sample_points(), _summarize() (+8 more)

### Community 36 - "handlers_integration.py"
Cohesion: 0.10
Nodes (20): emit_tool_result(), _alert_wrapper_retrigger(), _do_retrigger(), _get_jira_reporter(), handle_ask_release_ai(), handle_comment_jira_issue(), handle_fetch_jira_issue(), handle_greenwave() (+12 more)

### Community 37 - "AgentClient"
Cohesion: 0.07
Nodes (3): AgentClient, Developer, SysAdmin

### Community 38 - "GitHubPlatform"
Cohesion: 0.08
Nodes (3): GitHubPlatform, _poll_one(), _poll_one()

### Community 39 - "Headhunter"
Cohesion: 0.08
Nodes (3): Headhunter, _raise_if_systemic_failure(), _sanitize_xml_fence()

### Community 40 - "EventDrillDown.tsx"
Cohesion: 0.11
Nodes (31): getEventPulses(), EventSource, CortexDevPage(), devQueryClient, CortexLiveFeedProps, EventDrillDown(), EventDrillDownProps, FRICTION_COLORS (+23 more)

### Community 41 - "ToolContext"
Cohesion: 0.11
Nodes (9): handle_classify_event(), handle_close_event(), handle_defer_event(), handle_hold_watch(), handle_request_user_approval(), handle_wait_for_agent(), handle_wait_for_jarvis(), handle_wait_for_user() (+1 more)

### Community 42 - "TimeKeeperPage.tsx"
Cohesion: 0.12
Nodes (24): createSchedule(), deleteSchedule(), getSchedules(), refineInstructions(), ScheduleCreatePayload, ScheduleItem, toggleSchedule(), updateSchedule() (+16 more)

### Community 43 - "formatter.py"
Cohesion: 0.09
Nodes (15): build_access_denied_home_view(), build_home_tab_view(), _context_line(), create_feedback_block(), format_plan_block(), format_task_card(), format_tool_result_blocks(), format_turn() (+7 more)

### Community 45 - "ws-client.js"
Cohesion: 0.10
Nodes (26): clearIdleTimer(), {
  DEFAULT_WORK_DIR, AGENT_CLI, AGENT_MODEL, AGENT_ROLE,
  EVENT_ID, EPHEMERAL, IDLE_TIMEOUT_MS,
  CLI_429_MAX_RETRIES, CLI_429_INITIAL_DELAY_MS, CLI_429_BACKOFF_MULTIPLIER,
  resolveTimeoutMs, parsePositiveInt, MAX_TASK_WALL_MS, MAX_TIMER_MS,
}, { ensureEventDocument }, { executeCLIStreaming, prepareResultsDir, is429Error }, { filterSkillsByRole, filterSkillsByMode, swapActiveRules, restoreAllSkills }, fs, handleCancel(), handleTask() (+18 more)

### Community 46 - "useCortexData.ts"
Cohesion: 0.14
Nodes (30): getCognitiveGraph(), getCortexActivity(), getKGServiceDetail(), getKGServices(), getKGStats(), getKnowledgeById(), getLessonById(), getMemory() (+22 more)

### Community 47 - "CortexGraph.tsx"
Cohesion: 0.12
Nodes (30): graphology, ActiveEvent, KGServiceEntity, eventColor(), getExecutiveNeurons(), getStructuralEdges(), DEFAULT_TYPE_BUDGET, evictLru() (+22 more)

### Community 48 - "nightwatcher_tools.py"
Cohesion: 0.11
Nodes (16): PulseContext, ShiftIncident, ShiftInvestigation, _append_user_turn(), _finalize_analysis_handover(), execute_tool(), get_phase_tools(), _handle_consult_deep_memory() (+8 more)

### Community 51 - "ClaudeAdapter"
Cohesion: 0.11
Nodes (5): ClaudeAdapter, FunctionCall, LLMChunk, LLMResponse, TokenUsage

### Community 52 - "useQueue.ts"
Cohesion: 0.12
Nodes (26): getActiveEvents(), getAlignerPending(), getEventDocument(), getHeadhunterPending(), getJenkinsPending(), getWaitingApprovalEvents(), EventDocument, EventEvidence (+18 more)

### Community 53 - "StreamGrid.tsx"
Cohesion: 0.14
Nodes (24): Dashboard(), GridTile(), GridTileProps, TileType, InlineMarkdownViewer(), EmptyState(), LayoutMode, StreamGrid() (+16 more)

### Community 54 - "gemini_client.py"
Cohesion: 0.13
Nodes (12): _append_user_turn(), _attach_signature_to_parts(), _clone_part_with_sig(), _coerce_part(), _decode_sig_bytes(), _extract_part_signature(), _is_empty_sig_carrier(), _is_function_response_part() (+4 more)

### Community 55 - "TaskBridge"
Cohesion: 0.11
Nodes (9): _build_prompt(), consume_wake_task(), _consume(), _dispatch_timeout_s(), dispatch_to_agent(), _consume_queue(), _sanitize_stdout(), send_cancel() (+1 more)

### Community 57 - "tool_router.py"
Cohesion: 0.09
Nodes (7): _safe_int(), handle_consult_deep_memory(), handle_google_web_search(), handle_lookup_journal(), IdleTimeoutPort, IncidentAdapterPort, StateWatcherPort

### Community 58 - "server.js"
Cohesion: 0.09
Nodes (18): { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, ensureEventDocument(), fs, path, stageEventDocument(), fetchEventDocument(), fs, { handleRequest } (+10 more)

### Community 59 - "StateWatcher"
Cohesion: 0.10
Nodes (3): _QueueEntry, StateWatcher, _Subscription

### Community 60 - "adf_to_markdown"
Cohesion: 0.12
Nodes (10): _adf_to_text(), _escape_jql_string(), JiraIncidentAdapter, adf_to_markdown(), _apply_marks(), _children(), _render(), _render_list() (+2 more)

### Community 61 - "AgentRegistry"
Cohesion: 0.10
Nodes (3): AgentConnection, AgentRegistry, agent_websocket_handler()

### Community 63 - "scheduling/__init__.py"
Cohesion: 0.14
Nodes (9): handle_refresh_github_context(), handle_refresh_gitlab_context(), handle_refresh_kargo_context(), GitHubPrRef, GitLabMrRef, GitLabPipelineRef, KargoStageRef, PollFn (+1 more)

### Community 64 - "ConversationTurn"
Cohesion: 0.16
Nodes (13): handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_recall_pruned_turns(), handle_list_observations(), handle_record_observation(), handle_review_notes(), handle_take_note() (+5 more)

### Community 66 - "reconcile.py"
Cohesion: 0.15
Nodes (10): sanitize_redis_port(), _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers(), main() (+2 more)

### Community 70 - "dependencies"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 71 - "NeuronInfoPanel.tsx"
Cohesion: 0.12
Nodes (22): AGENTS, DOMAINS, HEMISPHERE_X, NEURON_DESCRIPTIONS, PHASE_SKILL_FOLDERS, PHASE_TOOL_PRIORITY, PHASES, StructuralEdge (+14 more)

### Community 75 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 76 - "claude-guard.js"
Cohesion: 0.14
Nodes (18): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+10 more)

### Community 77 - "BrainIntrospectionPort"
Cohesion: 0.10
Nodes (3): BrainIntrospectionPort, BrainLifecyclePort, BroadcastPort

### Community 78 - "NightwatcherObserver"
Cohesion: 0.14
Nodes (3): ShiftReport, _env_float(), NightwatcherObserver

### Community 80 - "handlers_dispatch.py"
Cohesion: 0.13
Nodes (6): handle_message_agent(), handle_reply_to_agent(), handle_report_incident(), handle_select_agent(), _resolve_escalation_scope(), _sticky_work_style()

### Community 83 - "PulseBatch"
Cohesion: 0.12
Nodes (4): PulseBatch, PulsePort, PulseObserver, PulseTracker

### Community 84 - "cli-setup.js"
Cohesion: 0.13
Nodes (18): { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync }, filterSkillsByMode() (+10 more)

### Community 86 - "devDependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 87 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 88 - "nightwatcher.py"
Cohesion: 0.14
Nodes (7): _env_int(), build_system_prompt(), _fallback_platform(), _handle_declare_clusters(), reconcile_cluster_plan(), salvage_cluster_plan(), validate_cluster_plan()

### Community 89 - "gemini-sidecar/package.json"
Cohesion: 0.11
Nodes (18): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+10 more)

### Community 90 - "event_to_markdown"
Cohesion: 0.15
Nodes (6): CIAnalysis, get_event_document(), report_tampering(), _esc(), _esc_join(), event_to_markdown()

### Community 94 - "._gate_check"
Cohesion: 0.18
Nodes (3): handle_app_home_opened(), handle_app_mention(), on_dm_message()

### Community 96 - "ShiftsPage.tsx"
Cohesion: 0.23
Nodes (16): getCurrentShift(), getShiftDetail(), getShiftsList(), ShiftReportFull, ShiftReportSummary, FailedClusterBadge(), getISOWeek(), getWeekDates() (+8 more)

### Community 97 - "catalog-skills.js"
Cohesion: 0.16
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 101 - "._run_report_cart"
Cohesion: 0.12
Nodes (7): build_report_iteration_prompt(), build_summary_prompt(), extract_full_links(), _normalize_gitlab_host(), build_extend_tool(), build_report_tool(), build_summary_tool()

### Community 102 - "generate_map.py"
Cohesion: 0.19
Nodes (6): _enumerate_gates(), _GateInfo, generate_phase_tool_map(), _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 107 - "get_report"
Cohesion: 0.14
Nodes (5): get_report(), reports_spa_no_slash(), reports_spa_with_slash(), search_reports(), _serve_spa()

### Community 108 - "ServiceNode.tsx"
Cohesion: 0.20
Nodes (11): HealthStatus, NodeType, AppNodeData, ARGOCD_HEALTH_COLORS, SYNC_ICONS, GENERIC_TAGS, HEALTH_COLORS, NODE_ICONS (+3 more)

### Community 110 - "handlers_planning.py"
Cohesion: 0.23
Nodes (7): _auto_complete_step(), _canonical_role(), handle_create_plan(), handle_get_plan_progress(), _is_failed_turn(), _is_orchestrator_turn(), _normalize_step_id()

### Community 112 - "analyzeTokens"
Cohesion: 0.19
Nodes (13): analyzeString(), analyzeTokens(), assignName(), base(), combineCategories(), configEnvGuard(), configFileWriteGuard(), hasSubseq() (+5 more)

### Community 115 - "._extract_context_flags"
Cohesion: 0.15
Nodes (3): compute_dispatch_backpressure(), ContextFlags, _safe_int_env()

### Community 117 - "._send_turn_to_thread"
Cohesion: 0.19
Nodes (5): extract_tables(), _replace(), get_agent_notification_text(), get_turn_attachment_color(), _md_table_to_block_kit()

### Community 118 - "get_current_shift"
Cohesion: 0.15
Nodes (3): get_current_shift(), get_shift_detail(), list_shifts()

### Community 122 - "is_defer_event_available"
Cohesion: 0.18
Nodes (6): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 125 - "CortexLiveFeed.tsx"
Cohesion: 0.27
Nodes (9): CortexHeartbeat(), CortexHeartbeatProps, ensureKeyframes(), CortexLiveFeed(), FILTER_PILLS, FilterKey, getStoredFilter(), MESSAGE_STYLES (+1 more)

### Community 126 - "gitGuard"
Cohesion: 0.29
Nodes (10): bareBranchProtected(), configWriteGuard(), externalGitCommand(), gitGuard(), gitQuery(), isProtected(), normRef(), pushGuard() (+2 more)

### Community 127 - "parseShell"
Cohesion: 0.33
Nodes (10): bodySubstitutions(), decodeAnsiC(), isArrayAssignPrefix(), isWordStart(), matchBacktick(), matchParen(), parseShell(), readHeredocStart() (+2 more)

### Community 132 - "entity_extractor.py"
Cohesion: 0.33
Nodes (5): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship

### Community 136 - "has_unevaluated_close_blocker"
Cohesion: 0.20
Nodes (4): has_unevaluated_close_blocker(), _pred_jarvis_response(), _pred_unevaluated_close(), is_jarvis_acknowledgment()

### Community 137 - "._register_handlers"
Cohesion: 0.22
Nodes (3): handle_approve(), handle_home_create_event(), handle_reject()

### Community 138 - "knowledge_graph_api.py"
Cohesion: 0.31
Nodes (4): get_kg_store(), get_service_detail(), get_stats(), list_services()

### Community 140 - "classifyTool"
Cohesion: 0.31
Nodes (9): apiTokens(), apiWriteNeedsGuard(), branchValues(), classifyTool(), hasOpaqueTarget(), httpGuard(), httpMethod(), isReadMethod() (+1 more)

### Community 146 - "useDeferCountdown.ts"
Cohesion: 0.47
Nodes (7): DeferCountdownState, useDeferCountdown(), computeDeferProgress(), DeferTimeline, formatDeferRemaining(), inferDeferFromConversation(), resolveDeferTimeline()

### Community 149 - "sanitize_call_syntax"
Cohesion: 0.25
Nodes (4): _extract_call_syntax(), sanitize_call_syntax(), scan_call_syntax(), split_stream_call_syntax()

### Community 153 - "validate-mutations.sh"
Cohesion: 0.57
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

### Community 158 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 159 - "state.js"
Cohesion: 0.33
Nodes (4): { AGENT_ROLE }, _blackboardTurns, _inboundMessages, _teammateMessages

### Community 180 - "classify"
Cohesion: 0.50
Nodes (4): classify(), main(), shellCategory(), shellNeedsGuard()

## Knowledge Gaps
- **13 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+8 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2274 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **120 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `logging`, `queue.py`, `routes/timekeeper.py`, `brain.py`, `Brain`, `EventEvidence`, `EventDocument`, `main.py`, `HeadhunterJira`, `_is_event_closed_or_missing`, `BrainSkillLoader`, `ConversationMessage`, `ScheduleRepository`, `observations_reporter.py`, `._restage_pending_signal`, `._stage_pending_signal`, `nightwatcher_tools.py`, `._count_pending`, `LiveAPIAdapter`, `tool_router.py`, `.cleanup_stale_services`, `._commit_pending_signal`, `._drain_pending`, `ConversationTurn`, `lifespan`, `NightwatcherObserver`, `nightwatcher.py`, `event_to_markdown`, `DashboardWSAdapter`, `.list_observations`, `get_report`, `get_current_shift`?**
  _High betweenness centrality (0.104) - this node is a cross-community bridge._
- **Are the 80 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 80 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.01263549693091289 - nodes in this community are weakly interconnected._
- **Why does `Brain` connect `Brain` to `BlackboardState`, `._resolve_llm_params`, `._post_agent_recall`, `queue.py`, `brain.py`, `EventEvidence`, `EventDocument`, `main.py`, `ReconcileScheduler`, `._process_with_llm`, `BrainSkillLoader`, `._detect_repetition_collapse`, `._resolve_grounding_urls`, `StateWatcher`, `ConversationTurn`, `._close_and_broadcast`, `lifespan`, `IdleTimeoutManager`, `BrainIntrospectionPort`, `PulseBatch`, `ReflexSearcher`, `DashboardWSAdapter`, `._extract_context_flags`?**
  _High betweenness centrality (0.045) - this node is a cross-community bridge._
- **Are the 19 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 19 INFERRED edges - model-reasoned connections that need verification._
- **Should `logging` be split into smaller, more focused modules?**
  _Cohesion score 0.025645908715800164 - nodes in this community are weakly interconnected._