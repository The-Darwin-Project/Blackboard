# Graph Report - Blackboard  (2026-11-15)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 5297 nodes · 11907 edges · 218 communities (102 shown, 116 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 957 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `ab8144b8`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BlackboardState
- logging
- gemini_client.py
- blackboard.py
- queue.py
- react
- client.ts
- main.py
- EventSidebar.tsx
- ConversationTurn
- Brain
- tool_gates.py
- ._run_agent_task
- App.tsx
- http-handler.js
- topology.py
- colors.ts
- jenkins-mcp.js
- handlers_lookup.py
- agents/__init__.py
- EventDocument
- OpsStateContext.tsx
- ._process_with_llm
- fetchApi
- AgentRegistry
- brain.py
- TurnBubble.tsx
- Aligner
- BrainSkillLoader
- BaseModel
- _BrainToolContext
- merge-guard.js
- GitHubAppAuth
- KnowledgeGraphStore
- lucide-react
- ui/package.json
- cli-executor.js
- storage-recycler.js
- handlers_integration.py
- context_parts.py
- JenkinsAdapter
- EventRepository
- EventDrillDown.tsx
- slack.py
- GitHubPlatform
- SlackChannel
- auth.py
- ArchitectureGraph.tsx
- GitLabPlatform
- httpx
- reconcile.py
- DashboardWSAdapter
- TimeKeeperPage.tsx
- Headhunter
- ws-client.js
- CortexGraph.tsx
- BrainIntrospectionPort
- useCortexData.ts
- ScheduleCreateRequest
- NodeInspector.tsx
- EventEvidence
- .list_observations
- ._build_contents
- nightwatcher_tools.py
- LiveAPIAdapter
- server.js
- nightwatcher.py
- Archivist
- ArgoCDObserver
- ._get_manager
- NightwatcherObserver
- KargoObserver
- dependencies
- NeuronInfoPanel.tsx
- StateWatcher
- compilerOptions
- claude-guard.js
- QuotaTracker
- event_to_markdown
- FlowHistoryPage.tsx
- _sanitize_analysis_text
- VcsPlatformPort
- PulseBatch
- cli-setup.js
- ReflexSearcher
- ArchitectureEvent
- FairQueue
- devDependencies
- compilerOptions
- gemini-sidecar/package.json
- EphemeralProvisioner
- JenkinsObserver
- get_token_meter
- get_report
- VectorStore
- ClaudeAdapter
- delete_schedule
- ObservationRepository
- ShiftsPage.tsx
- catalog-skills.js
- SlackAccessGate
- EscalationRepository
- JiraIncidentAdapter
- ._process_candidates
- FlowSnapshot
- OIDCKeyAdapter
- KubernetesSpawnHealthAdapter
- ReconcileScheduler
- observations_reporter.py
- generate_event_title
- ._connect
- ScheduleRepository
- analyzeTokens
- .scroll
- ._extract_context_flags
- IncidentAdapterPort
- IdleTimeoutManager
- JarvisMemoryPage.tsx
- ._process_message
- HeadhunterJira
- ._authorize_plan_decision
- generate_observations_report
- .start_event_loop
- is_defer_event_available
- ._run_clustering_agent
- gitGuard
- parseShell
- extract_tables
- adf_to_markdown
- _resolve_phase
- ._tool_send_event_message
- ._post_agent_recall
- entity_extractor.py
- ._triage_and_build_evidence
- ._drain_once
- knowledge_graph_api.py
- CortexDevPage.tsx
- spawn_health.py
- classifyTool
- SpawnPollResult
- SmartsheetMaintainerCache
- .has_reeval_signal
- Trigger
- GitLabTokenAuth
- ._evaluate_health
- ConversationMessage
- TimeKeeperObserver
- BrainLifecyclePort
- CortexRepository
- validate-mutations.sh
- QuotaExhaustedError
- ._run_analysis_loop
- update_notebook_note
- rename_observation
- scripts
- state.js
- io
- DispatchMetrics
- build_gate_context
- ._wait_for_registration
- submit_feedback
- get_notebook
- classify
- is_stabilization_wake
- list_incidents
- require-results.sh
- get_intermediate_tools
- report_tampering
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
- _pred_unevaluated_close
- _tools_wait_loop

## God Nodes (most connected - your core abstractions)
1. `BlackboardState` - 285 edges
2. `Brain` - 168 edges
3. `ConversationTurn` - 127 edges
4. `ToolContext` - 103 edges
5. `GateContext` - 99 edges
6. `react` - 85 edges
7. `EventDocument` - 82 edges
8. `fetchApi()` - 66 edges
9. `lifespan()` - 65 edges
10. `LiveAPIAdapter` - 64 edges

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

## Communities (218 total, 116 thin omitted)

### Community 1 - "logging"
Cohesion: 0.04
Nodes (11): _heartbeat(), _sanitize_lesson_text(), _get_static_maintainer_emails(), _get_allowed_mention_authors(), _get_static_maintainer_emails(), _safe_int(), _env_flag(), _parse_job_metadata() (+3 more)

### Community 2 - "gemini_client.py"
Cohesion: 0.04
Nodes (36): _append_user_turn(), _attach_signature_to_parts(), _clone_part_with_sig(), _coerce_part(), _decode_sig_bytes(), _extract_call_syntax(), _extract_part_signature(), GeminiAdapter (+28 more)

### Community 3 - "blackboard.py"
Cohesion: 0.03
Nodes (30): get_aligner(), get_architect(), get_argocd_observer(), get_blackboard(), get_brain(), get_developer(), get_kargo_observer(), get_pulse_tracker() (+22 more)

### Community 4 - "queue.py"
Cohesion: 0.04
Nodes (49): get_archivist(), EventStatus, aligner_pending_items(), apply_lessons(), approve_event(), close_event_by_user(), CloseRequest, correct_memory() (+41 more)

### Community 5 - "react"
Cohesion: 0.05
Nodes (83): react, updateEventTitle(), CiContext, ConversationTurn, EventEvidence, TokenUsageDict, ChatInput(), CiContextCard() (+75 more)

### Community 6 - "client.ts"
Cohesion: 0.03
Nodes (88): ApiError, bulkDeleteObservations(), deleteNote(), deleteObservation(), exportObservations(), ExtractedCorrection, ExtractedLesson, ExtractionResult (+80 more)

### Community 7 - "main.py"
Cohesion: 0.03
Nodes (32): _patch_enum_fields(), set_incident_options(), set_oidc_adapter(), set_agents(), set_archivist(), set_argocd_observer(), set_blackboard(), set_brain() (+24 more)

### Community 8 - "EventSidebar.tsx"
Cohesion: 0.05
Nodes (79): getActiveEvents(), getAlignerPending(), getEventDocument(), getHeadhunterPending(), getJenkinsPending(), getJiraMissions(), getWaitingApprovalEvents(), HeadhunterTodo (+71 more)

### Community 9 - "ConversationTurn"
Cohesion: 0.07
Nodes (39): emit_tool_result(), handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_message_agent(), handle_reply_to_agent(), handle_report_incident(), handle_select_agent() (+31 more)

### Community 11 - "tool_gates.py"
Cohesion: 0.05
Nodes (79): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+71 more)

### Community 12 - "._run_agent_task"
Cohesion: 0.05
Nodes (10): on_huddle(), on_progress(), on_huddle(), on_progress(), _has_non_user_turns(), _is_automated_nudge(), _sanitize_error_text(), _sanitize_override_reason() (+2 more)

### Community 13 - "App.tsx"
Cohesion: 0.05
Nodes (54): oidc-client-ts, react-dom, react-router-dom, getConfig(), getIncidents(), getWSAuthFailureCallback(), Incident, setOnUnauthorized() (+46 more)

### Community 14 - "http-handler.js"
Cohesion: 0.08
Nodes (62): is429Error(), registerMCPsAndHooks(), resolveCommand(), writeAgyMcpServer(), writeClaudeMcpServer(), parsePositiveInt(), buildArgoCDMcpConfig(), createAppJWT() (+54 more)

### Community 15 - "topology.py"
Cohesion: 0.04
Nodes (10): AppNode, GraphNode, TicketNode, get_graph_data(), get_mermaid_diagram(), get_service_details(), get_topology(), list_services() (+2 more)

### Community 16 - "colors.ts"
Cohesion: 0.07
Nodes (38): @tanstack/react-query, getReport(), getReports(), ReportFull, ReportMeta, SubjectType, CompactCardStrip(), EventHistory() (+30 more)

### Community 17 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 18 - "handlers_lookup.py"
Cohesion: 0.06
Nodes (28): _close_unanswered_fc(), _safe_int(), _coerce_turn_int(), handle_recall_pruned_turns(), _parse_turn_int(), _sanitize_recalled(), _format_bounded_journal(), handle_consult_deep_memory() (+20 more)

### Community 19 - "agents/__init__.py"
Cohesion: 0.06
Nodes (8): Architect, AgentClient, Developer, _check_security(), safe_execution(), wrapper(), SecurityError, SysAdmin

### Community 21 - "OpsStateContext.tsx"
Cohesion: 0.07
Nodes (45): getAgents(), getKargoStages(), KargoStageStatus, AgentRegistryPanel(), formatConnectedSince(), Dashboard(), GridTile(), GridTileProps (+37 more)

### Community 22 - "._process_with_llm"
Cohesion: 0.04
Nodes (5): _BatchContext, _ensure_recall_tool_if_needed(), _QuotaShedState, RepetitionCollapse, _retry_backoff_delay()

### Community 23 - "fetchApi"
Cohesion: 0.09
Nodes (47): applyLessons(), correctMemory(), createKnowledge(), createLesson(), deleteKnowledge(), deleteLesson(), extractLessons(), fetchApi() (+39 more)

### Community 24 - "AgentRegistry"
Cohesion: 0.06
Nodes (12): AgentConnection, AgentRegistry, agent_websocket_handler(), _build_prompt(), consume_wake_task(), _consume(), _dispatch_timeout_s(), dispatch_to_agent() (+4 more)

### Community 25 - "brain.py"
Cohesion: 0.06
Nodes (17): _compute_processed_up_to(), _is_seed_turn(), _resolve_escalation_scope(), _auto_complete_step(), _canonical_role(), handle_get_plan_progress(), _is_failed_turn(), _is_orchestrator_turn() (+9 more)

### Community 26 - "TurnBubble.tsx"
Cohesion: 0.08
Nodes (41): @uiw/react-markdown-preview, approveEvent(), closeEvent(), enforceCasualDomain(), getEventReport(), rejectEvent(), submitFeedback(), ConversationFeed() (+33 more)

### Community 28 - "BrainSkillLoader"
Cohesion: 0.05
Nodes (4): _parse_positive_int_env(), BrainSkillLoader, _SkillCorpus, _wrap_section()

### Community 29 - "BaseModel"
Cohesion: 0.05
Nodes (14): ChatRequest, ChatResponse, EventMetrics, GraphEdge, GraphResponse, JenkinsPendingItem, Metrics, PendingAnomaly (+6 more)

### Community 31 - "merge-guard.js"
Cohesion: 0.04
Nodes (46): API_VALUED, ARGO_MUTATING, ARGO_READ_SUB, ARGO_READ_TOP, BODY_FLAG, BROWSER_READ, CTX, ENV_BUILTINS (+38 more)

### Community 32 - "GitHubAppAuth"
Cohesion: 0.06
Nodes (5): AsyncGitHubClient, _find_pem_file(), get_github_auth(), GitHubAppAuth, MultiInstallationManager

### Community 33 - "KnowledgeGraphStore"
Cohesion: 0.08
Nodes (9): _format_graph_context(), get_graph_context(), _parse_props(), _sanitize(), translate_to_lookups(), _acquire(), KnowledgeGraphStore, _sanitize() (+1 more)

### Community 34 - "lucide-react"
Cohesion: 0.08
Nodes (34): lucide-react, createChatEvent(), AgentStreamCard(), AgentStreamCardProps, MessageCards(), ChatInputProps, Draft, LastSubmission (+26 more)

### Community 35 - "ui/package.json"
Cohesion: 0.05
Nodes (37): autoprefixer, cronstrue, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, graphology-layout-forceatlas2 (+29 more)

### Community 36 - "cli-executor.js"
Cohesion: 0.09
Nodes (37): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, MAX_TASK_WALL_MS, MAX_TIMER_MS, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS, STORAGE_PRETASK_TIMEOUT_MS, resolveStorageRoot }, buildCLICommand(), buildTimeoutResult(), { checkAndRecycleStorage, pinTaskCwd, unpinTaskCwd }, CLAUDE_JSON_PATH, cp, createInactivityWatchdog(), executeCLI() (+29 more)

### Community 37 - "storage-recycler.js"
Cohesion: 0.08
Nodes (37): withTaskStorage(), MAX_TASK_WALL_MS, parseTimerMs(), resolveStorageRoot(), resolveTimeoutMs(), ROLE_TIMEOUTS, STORAGE_ACTIVITY_HEARTBEAT_MS, STORAGE_MAX_TIER3_DELETIONS (+29 more)

### Community 38 - "handlers_integration.py"
Cohesion: 0.08
Nodes (18): _alert_wrapper_retrigger(), _do_retrigger(), _get_jira_reporter(), handle_refresh_github_context(), handle_refresh_gitlab_context(), handle_refresh_kargo_context(), _is_darwin_reentrant_caller(), jenkins_retrigger_cooldown_key() (+10 more)

### Community 39 - "context_parts.py"
Cohesion: 0.08
Nodes (18): _contents_have_pruned_or_decayed(), _apply_sibling_signature(), build_function_response(), build_single_function_response(), compress_contents(), contents_have_pruned_or_decayed(), estimate_msg_tokens(), estimate_tokens() (+10 more)

### Community 40 - "JenkinsAdapter"
Cohesion: 0.06
Nodes (6): BuildDetails, JenkinsAdapter, JenkinsPlatformPort, JobResult, JobRunState, ViewScanResult

### Community 42 - "EventDrillDown.tsx"
Cohesion: 0.09
Nodes (32): three, getEventPulses(), EventSource, BrainCore(), CortexDevPage(), CortexHeartbeat(), CortexHeartbeatProps, ensureKeyframes() (+24 more)

### Community 43 - "slack.py"
Cohesion: 0.08
Nodes (16): build_access_denied_home_view(), build_home_tab_view(), _context_line(), create_feedback_block(), format_event_summary(), format_plan_block(), format_task_card(), format_tool_result_blocks() (+8 more)

### Community 46 - "auth.py"
Cohesion: 0.08
Nodes (14): can_append_message(), can_approve_event(), can_override_domain(), can_rename_event(), _claims_to_user(), get_user_from_request(), get_user_from_slack(), get_user_from_websocket() (+6 more)

### Community 47 - "ArchitectureGraph.tsx"
Cohesion: 0.09
Nodes (28): @dagrejs/dagre, @xyflow/react, HealthStatus, NodeType, AppNodeData, applyDagreLayout(), applyGridLayout(), applyLayout() (+20 more)

### Community 49 - "httpx"
Cohesion: 0.09
Nodes (13): dex_proxy(), approve_mission(), dismiss_mission(), _infer_phase(), _jira_config(), list_missions(), reanalyze_mission(), retry_mission() (+5 more)

### Community 50 - "reconcile.py"
Cohesion: 0.10
Nodes (15): _enumerate_gates(), _GateInfo, generate_phase_tool_map(), _load_gate_registry(), _render_markdown(), _render_ooda_overlay(), _build_redis_client(), _fetch_commit_sha() (+7 more)

### Community 51 - "DashboardWSAdapter"
Cohesion: 0.09
Nodes (6): DashboardWSAdapter, prompt_display_name(), resolve_approval_identity(), ChatEventRequest, ChatEventResponse, create_chat_event()

### Community 52 - "TimeKeeperPage.tsx"
Cohesion: 0.12
Nodes (24): createSchedule(), deleteSchedule(), getSchedules(), refineInstructions(), ScheduleCreatePayload, ScheduleItem, toggleSchedule(), updateSchedule() (+16 more)

### Community 53 - "Headhunter"
Cohesion: 0.08
Nodes (3): Headhunter, _raise_if_systemic_failure(), _sanitize_xml_fence()

### Community 54 - "ws-client.js"
Cohesion: 0.10
Nodes (26): clearIdleTimer(), {
  DEFAULT_WORK_DIR, AGENT_CLI, AGENT_MODEL, AGENT_ROLE,
  EVENT_ID, EPHEMERAL, IDLE_TIMEOUT_MS,
  CLI_429_MAX_RETRIES, CLI_429_INITIAL_DELAY_MS, CLI_429_BACKOFF_MULTIPLIER,
  resolveTimeoutMs, parsePositiveInt, MAX_TASK_WALL_MS, MAX_TIMER_MS,
}, { ensureEventDocument }, { executeCLIStreaming, prepareResultsDir, is429Error }, { filterSkillsByRole, filterSkillsByMode, swapActiveRules, restoreAllSkills }, fs, handleCancel(), handleTask() (+18 more)

### Community 55 - "CortexGraph.tsx"
Cohesion: 0.11
Nodes (31): graphology, ActiveEvent, KGServiceEntity, eventColor(), getExecutiveNeurons(), getStructuralEdges(), DEFAULT_TYPE_BUDGET, evictLru() (+23 more)

### Community 56 - "BrainIntrospectionPort"
Cohesion: 0.06
Nodes (3): BrainIntrospectionPort, BroadcastPort, JarvisPeerPort

### Community 57 - "useCortexData.ts"
Cohesion: 0.15
Nodes (29): getCognitiveGraph(), getCortexActivity(), getKGServiceDetail(), getKGServices(), getKGStats(), getKnowledgeById(), getLessonById(), getMemory() (+21 more)

### Community 58 - "ScheduleCreateRequest"
Cohesion: 0.08
Nodes (4): EventInput, ScheduleCreateRequest, create_schedule(), update_schedule()

### Community 59 - "NodeInspector.tsx"
Cohesion: 0.11
Nodes (26): getClosedEvents(), getEvents(), ArchitectureEvent, ArgoCDOperation, ActivityStream(), ArchitectureGraph(), EVENT_LABELS, EventItem() (+18 more)

### Community 60 - "EventEvidence"
Cohesion: 0.13
Nodes (9): spawn_event_namer_task(), handle_app_home_opened(), handle_app_mention(), handle_create_event_modal(), handle_darwin_command(), handle_home_create_event(), on_dm_message(), EventEvidence (+1 more)

### Community 61 - ".list_observations"
Cohesion: 0.07
Nodes (5): get_all_journal(), get_service_journal(), get_event_observations(), get_global_observations(), export_observations()

### Community 63 - "nightwatcher_tools.py"
Cohesion: 0.13
Nodes (15): PulseContext, ShiftIncident, ShiftInvestigation, execute_tool(), _handle_consult_deep_memory(), _handle_declare_clusters(), _handle_dispatch_investigation(), _handle_extend_incident() (+7 more)

### Community 65 - "server.js"
Cohesion: 0.09
Nodes (18): { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, ensureEventDocument(), fs, path, stageEventDocument(), fetchEventDocument(), fs, { handleRequest } (+10 more)

### Community 66 - "nightwatcher.py"
Cohesion: 0.10
Nodes (11): _env_int(), build_manifest_table(), build_report_iteration_prompt(), build_summary_prompt(), build_system_prompt(), extract_event_links(), extract_full_links(), _normalize_gitlab_host() (+3 more)

### Community 70 - "NightwatcherObserver"
Cohesion: 0.14
Nodes (3): ShiftReport, _env_float(), NightwatcherObserver

### Community 72 - "dependencies"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 73 - "NeuronInfoPanel.tsx"
Cohesion: 0.12
Nodes (22): AGENTS, DOMAINS, HEMISPHERE_X, NEURON_DESCRIPTIONS, PHASE_SKILL_FOLDERS, PHASE_TOOL_PRIORITY, PHASES, StructuralEdge (+14 more)

### Community 74 - "StateWatcher"
Cohesion: 0.11
Nodes (3): _QueueEntry, StateWatcher, _Subscription

### Community 75 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 76 - "claude-guard.js"
Cohesion: 0.14
Nodes (18): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+10 more)

### Community 77 - "QuotaTracker"
Cohesion: 0.10
Nodes (5): get_quota_tracker(), QuotaTracker, _stale_reservation_ttl_s(), llm_stats(), receive_telemetry()

### Community 78 - "event_to_markdown"
Cohesion: 0.14
Nodes (6): get_event_document(), _esc(), _esc_join(), event_to_markdown(), maintainer_env_key(), resolve_maintainer_emails()

### Community 79 - "FlowHistoryPage.tsx"
Cohesion: 0.23
Nodes (16): recharts, getFlowHistory(), FlowSnapshot, FlowHistoryPage(), RANGES, SparkCard(), SparkCardProps, formatTime() (+8 more)

### Community 80 - "_sanitize_analysis_text"
Cohesion: 0.10
Nodes (11): _annotation_replace(), _strip_pipeline_annotations(), _clamp_confidence(), _prepare_console_tail(), _redact_match(), _redact_secrets_in_text(), _sanitize_analysis_text(), _sanitize_console_tail() (+3 more)

### Community 83 - "PulseBatch"
Cohesion: 0.12
Nodes (4): PulseBatch, PulsePort, PulseObserver, PulseTracker

### Community 84 - "cli-setup.js"
Cohesion: 0.13
Nodes (18): { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync }, filterSkillsByMode() (+10 more)

### Community 86 - "ArchitectureEvent"
Cohesion: 0.13
Nodes (3): ArchitectureEvent, list_events(), MetricsRepository

### Community 88 - "devDependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 89 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 90 - "gemini-sidecar/package.json"
Cohesion: 0.11
Nodes (18): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+10 more)

### Community 95 - "get_token_meter"
Cohesion: 0.11
Nodes (3): get_token_meter(), TokenMeter, TokenUsageDict

### Community 96 - "get_report"
Cohesion: 0.11
Nodes (6): get_report(), list_reports(), reports_spa_no_slash(), reports_spa_with_slash(), search_reports(), _serve_spa()

### Community 99 - "delete_schedule"
Cohesion: 0.11
Nodes (4): delete_schedule(), get_schedule(), list_schedules(), toggle_schedule()

### Community 101 - "ShiftsPage.tsx"
Cohesion: 0.23
Nodes (16): getCurrentShift(), getShiftDetail(), getShiftsList(), ShiftReportFull, ShiftReportSummary, FailedClusterBadge(), getISOWeek(), getWeekDates() (+8 more)

### Community 102 - "catalog-skills.js"
Cohesion: 0.16
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 110 - "ReconcileScheduler"
Cohesion: 0.16
Nodes (3): ReconcileScheduler, ResyncTrigger, StalenessGuard

### Community 111 - "observations_reporter.py"
Cohesion: 0.21
Nodes (7): _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), _sample_points(), _summarize()

### Community 112 - "generate_event_title"
Cohesion: 0.15
Nodes (4): generate_event_title(), get_adapter(), _get_semaphore(), sanitize_title()

### Community 117 - "analyzeTokens"
Cohesion: 0.19
Nodes (13): analyzeString(), analyzeTokens(), assignName(), base(), combineCategories(), configEnvGuard(), configFileWriteGuard(), hasSubseq() (+5 more)

### Community 119 - "._extract_context_flags"
Cohesion: 0.15
Nodes (3): compute_dispatch_backpressure(), ContextFlags, _safe_int_env()

### Community 120 - "IncidentAdapterPort"
Cohesion: 0.15
Nodes (3): IdleTimeoutPort, IncidentAdapterPort, StateWatcherPort

### Community 122 - "JarvisMemoryPage.tsx"
Cohesion: 0.27
Nodes (12): dismissProposals(), EnhancementProposal, getHandoffReports(), getProposals(), HandoffReport, FilterMode, formatDate(), formatTime() (+4 more)

### Community 127 - "._authorize_plan_decision"
Cohesion: 0.18
Nodes (3): _PlanDecision, handle_approve(), handle_reject()

### Community 128 - "generate_observations_report"
Cohesion: 0.18
Nodes (6): render_pdf(), bulk_delete_observations(), BulkDeleteRequest, delete_observation(), generate_observations_report(), ReportRequest

### Community 130 - "is_defer_event_available"
Cohesion: 0.18
Nodes (6): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 131 - "._run_clustering_agent"
Cohesion: 0.24
Nodes (3): _fallback_platform(), reconcile_cluster_plan(), salvage_cluster_plan()

### Community 132 - "gitGuard"
Cohesion: 0.29
Nodes (10): bareBranchProtected(), configWriteGuard(), externalGitCommand(), gitGuard(), gitQuery(), isProtected(), normRef(), pushGuard() (+2 more)

### Community 133 - "parseShell"
Cohesion: 0.33
Nodes (10): bodySubstitutions(), decodeAnsiC(), isArrayAssignPrefix(), isWordStart(), matchBacktick(), matchParen(), parseShell(), readHeredocStart() (+2 more)

### Community 134 - "extract_tables"
Cohesion: 0.20
Nodes (5): extract_tables(), _replace(), _md_table_to_block_kit(), _md_table_to_text(), _parse_md_table()

### Community 135 - "adf_to_markdown"
Cohesion: 0.40
Nodes (8): _adf_to_text(), adf_to_markdown(), _apply_marks(), _children(), _render(), _render_list(), _render_list_item(), _render_table_like()

### Community 141 - "entity_extractor.py"
Cohesion: 0.33
Nodes (5): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship

### Community 144 - "knowledge_graph_api.py"
Cohesion: 0.31
Nodes (4): get_kg_store(), get_service_detail(), get_stats(), list_services()

### Community 145 - "CortexDevPage.tsx"
Cohesion: 0.36
Nodes (8): devQueryClient, MOCK_CORTEX_STATUS, MOCK_EVENT_ID, MOCK_NEURONS, MOCK_PULSE_BATCHES, MOCK_SHADOW, MOCK_THINKING, MOCK_WHISPERS

### Community 147 - "classifyTool"
Cohesion: 0.31
Nodes (9): apiTokens(), apiWriteNeedsGuard(), branchValues(), classifyTool(), hasOpaqueTarget(), httpGuard(), httpMethod(), isReadMethod() (+1 more)

### Community 161 - "validate-mutations.sh"
Cohesion: 0.57
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

### Community 164 - "._run_analysis_loop"
Cohesion: 0.33
Nodes (3): _append_user_turn(), _finalize_analysis_handover(), get_phase_tools()

### Community 167 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 168 - "state.js"
Cohesion: 0.33
Nodes (4): { AGENT_ROLE }, _blackboardTurns, _inboundMessages, _teammateMessages

### Community 178 - "build_gate_context"
Cohesion: 0.33
Nodes (3): build_gate_context(), conversation_has_decayed_turns(), _decay_payload_len()

### Community 183 - "classify"
Cohesion: 0.50
Nodes (4): classify(), main(), shellCategory(), shellNeedsGuard()

## Knowledge Gaps
- **13 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+8 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2327 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **116 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `generate_observations_report`, `logging`, `blackboard.py`, `queue.py`, `main.py`, `_resolve_phase`, `ConversationTurn`, `Brain`, `topology.py`, `EventDocument`, `brain.py`, `BrainSkillLoader`, `ConversationMessage`, `BaseModel`, `update_notebook_note`, `rename_observation`, `slack.py`, `auth.py`, `httpx`, `DashboardWSAdapter`, `submit_feedback`, `get_notebook`, `ScheduleCreateRequest`, `EventEvidence`, `.list_observations`, `nightwatcher_tools.py`, `LiveAPIAdapter`, `report_tampering`, `nightwatcher.py`, `NightwatcherObserver`, `event_to_markdown`, `ArchitectureEvent`, `get_report`, `delete_schedule`, `FlowSnapshot`, `observations_reporter.py`, `generate_event_title`, `ScheduleRepository`, `HeadhunterJira`?**
  _High betweenness centrality (0.126) - this node is a cross-community bridge._
- **Are the 80 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 80 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.014208721215090642 - nodes in this community are weakly interconnected._
- **Why does `Brain` connect `Brain` to `BlackboardState`, `logging`, `.start_event_loop`, `blackboard.py`, `queue.py`, `main.py`, `ConversationTurn`, `._resolve_llm_params`, `._run_agent_task`, `._post_agent_recall`, `agents/__init__.py`, `EventDocument`, `._process_with_llm`, `brain.py`, `BrainSkillLoader`, `slack.py`, `DashboardWSAdapter`, `.stop_event_loop`, `BrainIntrospectionPort`, `EventEvidence`, `.clear_jarvis_wait`, `._build_contents`, `Archivist`, `StateWatcher`, `PulseBatch`, `ReflexSearcher`, `FlowSnapshot`, `ReconcileScheduler`, `._extract_context_flags`, `IdleTimeoutManager`?**
  _High betweenness centrality (0.065) - this node is a cross-community bridge._
- **Are the 20 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Should `logging` be split into smaller, more focused modules?**
  _Cohesion score 0.04132231404958678 - nodes in this community are weakly interconnected._