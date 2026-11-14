# Graph Report - Blackboard  (2026-11-14)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 5238 nodes · 11772 edges · 224 communities (106 shown, 118 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 952 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `498dfe6d`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BlackboardState
- logging
- Archivist
- main.py
- os
- client.ts
- queue.py
- auth.py
- WorkspaceInspector.tsx
- App.tsx
- EventSidebar.tsx
- Brain
- tool_gates.py
- context_parts.py
- http-handler.js
- AgentRegistry
- EventHistory.tsx
- react
- jenkins-mcp.js
- ._run_agent_task
- ConversationTurn
- EventDocument
- ToolContext
- TurnBubble.tsx
- BrainSkillLoader
- StreamGrid.tsx
- ScheduleRepository
- _BrainToolContext
- EventRepository
- merge-guard.js
- ._process_with_llm
- KnowledgeGraphStore
- observations_mgmt.py
- GeminiAdapter
- cli-executor.js
- storage-recycler.js
- JenkinsAdapter
- llm/__init__.py
- GitHubPlatform
- OpsStateContext.tsx
- GitLabPlatform
- Headhunter
- TimeKeeperPage.tsx
- gemini_client.py
- Aligner
- ws-client.js
- SlackChannel
- ui/package.json
- EventDrillDown.tsx
- brain.py
- CortexGraph.tsx
- ._close_and_broadcast
- formatter.py
- server.js
- cognitive_graph.py
- NodeInspector.tsx
- useCortexData.ts
- nightwatcher_tools.py
- ArgoCDObserver
- reconcile.py
- event_to_markdown
- ._get_manager
- KargoObserver
- TopologyRepository
- GitHubAppAuth
- dependencies
- TokenUtilizationPage.tsx
- compilerOptions
- claude-guard.js
- DashboardWSAdapter
- NightwatcherObserver
- ArchitectureGraph.tsx
- VcsPlatformPort
- cli-setup.js
- ._build_contents
- ReflexSearcher
- StateWatcher
- _resolve_phase
- get_token_meter
- devDependencies
- compilerOptions
- gemini-sidecar/package.json
- LiveAPIAdapter
- EphemeralProvisioner
- cortex/types.ts
- JiraIncidentAdapter
- .__init__
- JenkinsObserver
- QuotaTracker
- ObservationRepository
- ShiftsPage.tsx
- nightwatcher.py
- catalog-skills.js
- SlackAccessGate
- ._authorize_plan_decision
- EscalationRepository
- prompt.py
- ._run_report_cart
- FairQueue
- generate_map.py
- OIDCKeyAdapter
- KubernetesSpawnHealthAdapter
- IdleTimeoutManager
- ServiceNode.tsx
- .start_event_loop
- handlers_planning.py
- MultiInstallationManager
- JarvisMemoryPage.tsx
- analyzeTokens
- scheduling/__init__.py
- FilterRule
- BrainLifecyclePort
- ArchitectureEvent
- ReconcileScheduler
- colors.ts
- _sanitize_analysis_text
- testSetup.ts
- ._extract_context_flags
- is_defer_event_available
- IncidentAdapterPort
- ._register_handlers
- cortex-constants.ts
- CortexLiveFeed.tsx
- spawn_health.py
- gitGuard
- parseShell
- _md_table_to_text
- generate_event_title
- entity_extractor.py
- ._github_poll_and_process
- ._process_candidates
- _prepare_console_tail
- has_unevaluated_close_blocker
- ._send_turn_to_thread
- knowledge_graph_api.py
- classifyTool
- get_quota_tracker
- _is_event_closed_or_missing
- SpawnPollResult
- SmartsheetMaintainerCache
- .has_reeval_signal
- Trigger
- AsyncGitHubClient
- GitLabTokenAuth
- ._evaluate_health
- ._post_agent_recall
- HeadhunterJira
- ._triage_and_build_evidence
- ._drain_once
- TimeKeeperObserver
- CortexRepository
- adf_to_markdown
- validate-mutations.sh
- ._run_analysis_loop
- list_events
- scripts
- state.js
- ._process_message
- DispatchMetrics
- _append_user_turn
- build_gate_context
- list_failed_stages
- dex_proxy
- ._wait_for_registration
- StalenessGuard
- ResyncTrigger
- classify
- derive_llm_priority
- require-results.sh
- _WSFrameFilter
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

## Communities (224 total, 118 thin omitted)

### Community 0 - "BlackboardState"
Cohesion: 0.01
Nodes (14): get_all_journal(), get_service_journal(), get_notebook(), get_event_observations(), get_global_observations(), create_schedule(), list_schedules(), get_graph_data() (+6 more)

### Community 1 - "logging"
Cohesion: 0.03
Nodes (36): _annotation_replace(), _strip_pipeline_annotations(), _sanitize_lesson_text(), _safe_int(), _parse_job_metadata(), record_token_usage(), Pulse, AppNode (+28 more)

### Community 2 - "Archivist"
Cohesion: 0.03
Nodes (8): Archivist, PulseBatch, PulsePort, PulseObserver, PulseTracker, _decode_cursor(), _encode_cursor(), VectorStore

### Community 3 - "main.py"
Cohesion: 0.03
Nodes (38): Architect, AgentClient, Developer, set_incident_options(), SysAdmin, TaskBridge, set_oidc_adapter(), get_aligner() (+30 more)

### Community 4 - "os"
Cohesion: 0.03
Nodes (33): _get_static_maintainer_emails(), _get_allowed_mention_authors(), _get_static_maintainer_emails(), get_blackboard(), RefineRequest, RefineResponse, FeedbackRequest, submit_feedback() (+25 more)

### Community 5 - "client.ts"
Cohesion: 0.03
Nodes (89): @tanstack/react-query, ApiError, bulkDeleteObservations(), deleteNote(), deleteObservation(), exportObservations(), ExtractedCorrection, ExtractedLesson (+81 more)

### Community 6 - "queue.py"
Cohesion: 0.03
Nodes (47): get_archivist(), get_event_document(), report_tampering(), aligner_pending_items(), apply_lessons(), close_event_by_user(), CloseRequest, correct_memory() (+39 more)

### Community 7 - "auth.py"
Cohesion: 0.03
Nodes (31): spawn_event_namer_task(), can_append_message(), can_approve_event(), can_override_domain(), can_rename_event(), _claims_to_user(), get_user_from_request(), get_user_from_slack() (+23 more)

### Community 8 - "WorkspaceInspector.tsx"
Cohesion: 0.05
Nodes (77): updateEventTitle(), CiContext, ConversationTurn, EventEvidence, TokenUsageDict, CiContextCard(), CiContextCardProps, ConsoleTailBlock() (+69 more)

### Community 9 - "App.tsx"
Cohesion: 0.05
Nodes (64): oidc-client-ts, react-dom, react-router-dom, createChatEvent(), getConfig(), getEvents(), getWSAuthFailureCallback(), setOnUnauthorized() (+56 more)

### Community 10 - "EventSidebar.tsx"
Cohesion: 0.06
Nodes (79): getActiveEvents(), getAlignerPending(), getEventDocument(), getHeadhunterPending(), getJenkinsPending(), getJiraMissions(), getWaitingApprovalEvents(), HeadhunterTodo (+71 more)

### Community 12 - "tool_gates.py"
Cohesion: 0.05
Nodes (77): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+69 more)

### Community 13 - "context_parts.py"
Cohesion: 0.05
Nodes (29): _apply_sibling_signature(), build_function_response(), build_single_function_response(), compress_contents(), contents_have_pruned_or_decayed(), estimate_msg_tokens(), estimate_tokens(), extract_model_parts() (+21 more)

### Community 14 - "http-handler.js"
Cohesion: 0.08
Nodes (62): is429Error(), registerMCPsAndHooks(), resolveCommand(), writeAgyMcpServer(), writeClaudeMcpServer(), parsePositiveInt(), buildArgoCDMcpConfig(), createAppJWT() (+54 more)

### Community 15 - "AgentRegistry"
Cohesion: 0.05
Nodes (16): AgentConnection, AgentRegistry, agent_websocket_handler(), _heartbeat(), _build_prompt(), _check_security(), consume_wake_task(), _consume() (+8 more)

### Community 16 - "EventHistory.tsx"
Cohesion: 0.07
Nodes (40): @tanstack/react-table, getReport(), getReports(), ReportFull, ReportMeta, SubjectType, CompactCardStrip(), EventHistory() (+32 more)

### Community 17 - "react"
Cohesion: 0.08
Nodes (54): lucide-react, react, applyLessons(), correctMemory(), createKnowledge(), createLesson(), deleteKnowledge(), deleteLesson() (+46 more)

### Community 18 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 19 - "._run_agent_task"
Cohesion: 0.06
Nodes (5): on_huddle(), on_progress(), on_huddle(), on_progress(), get_registry_and_bridge()

### Community 20 - "ConversationTurn"
Cohesion: 0.10
Nodes (35): emit_tool_result(), handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), _alert_wrapper_retrigger(), _do_retrigger(), _get_jira_reporter(), handle_ask_release_ai() (+27 more)

### Community 22 - "ToolContext"
Cohesion: 0.08
Nodes (13): handle_message_agent(), handle_reply_to_agent(), handle_report_incident(), handle_select_agent(), _resolve_escalation_scope(), _sticky_work_style(), handle_defer_event(), handle_hold_watch() (+5 more)

### Community 23 - "TurnBubble.tsx"
Cohesion: 0.09
Nodes (40): @uiw/react-markdown-preview, approveEvent(), closeEvent(), enforceCasualDomain(), getEventReport(), rejectEvent(), submitFeedback(), ConversationFeed() (+32 more)

### Community 24 - "BrainSkillLoader"
Cohesion: 0.05
Nodes (3): BrainSkillLoader, _SkillCorpus, BrainIntrospectionPort

### Community 25 - "StreamGrid.tsx"
Cohesion: 0.08
Nodes (40): AgentStreamCard(), AgentStreamCardProps, MessageCards(), Dashboard(), GridTile(), GridTileProps, TileType, InlineMarkdownViewer() (+32 more)

### Community 26 - "ScheduleRepository"
Cohesion: 0.05
Nodes (7): ScheduleCreateRequest, ScheduledEvent, delete_schedule(), get_schedule(), toggle_schedule(), update_schedule(), ScheduleRepository

### Community 29 - "merge-guard.js"
Cohesion: 0.04
Nodes (46): API_VALUED, ARGO_MUTATING, ARGO_READ_SUB, ARGO_READ_TOP, BODY_FLAG, BROWSER_READ, CTX, ENV_BUILTINS (+38 more)

### Community 30 - "._process_with_llm"
Cohesion: 0.05
Nodes (7): _compute_processed_up_to(), _contents_have_pruned_or_decayed(), _ensure_recall_tool_if_needed(), _is_automated_nudge(), _QuotaShedState, _retry_backoff_delay(), _sanitize_error_text()

### Community 31 - "KnowledgeGraphStore"
Cohesion: 0.08
Nodes (9): _format_graph_context(), get_graph_context(), _parse_props(), _sanitize(), translate_to_lookups(), _acquire(), KnowledgeGraphStore, _sanitize() (+1 more)

### Community 32 - "observations_mgmt.py"
Cohesion: 0.06
Nodes (18): get_report_client(), _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), render_pdf(), _sample_points() (+10 more)

### Community 33 - "GeminiAdapter"
Cohesion: 0.09
Nodes (9): _attach_signature_to_parts(), _clone_part_with_sig(), _coerce_part(), _decode_sig_bytes(), _extract_part_signature(), GeminiAdapter, _is_empty_sig_carrier(), _part_has_fc() (+1 more)

### Community 34 - "cli-executor.js"
Cohesion: 0.09
Nodes (37): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, MAX_TASK_WALL_MS, MAX_TIMER_MS, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS, STORAGE_PRETASK_TIMEOUT_MS, resolveStorageRoot }, buildCLICommand(), buildTimeoutResult(), { checkAndRecycleStorage, pinTaskCwd, unpinTaskCwd }, CLAUDE_JSON_PATH, cp, createInactivityWatchdog(), executeCLI() (+29 more)

### Community 35 - "storage-recycler.js"
Cohesion: 0.08
Nodes (37): withTaskStorage(), MAX_TASK_WALL_MS, parseTimerMs(), resolveStorageRoot(), resolveTimeoutMs(), ROLE_TIMEOUTS, STORAGE_ACTIVITY_HEARTBEAT_MS, STORAGE_MAX_TIER3_DELETIONS (+29 more)

### Community 36 - "JenkinsAdapter"
Cohesion: 0.06
Nodes (6): BuildDetails, JenkinsAdapter, JenkinsPlatformPort, JobResult, JobRunState, ViewScanResult

### Community 37 - "llm/__init__.py"
Cohesion: 0.08
Nodes (7): ClaudeAdapter, create_adapter(), FunctionCall, LLMChunk, LLMPort, LLMResponse, TokenUsage

### Community 39 - "OpsStateContext.tsx"
Cohesion: 0.10
Nodes (29): getAgents(), getKargoStages(), KargoStageStatus, AgentRegistryPanel(), formatConnectedSince(), ChatInput(), STARTER_CHIPS, StarterChip (+21 more)

### Community 42 - "TimeKeeperPage.tsx"
Cohesion: 0.12
Nodes (24): createSchedule(), deleteSchedule(), getSchedules(), refineInstructions(), ScheduleCreatePayload, ScheduleItem, toggleSchedule(), updateSchedule() (+16 more)

### Community 43 - "gemini_client.py"
Cohesion: 0.10
Nodes (13): _extract_call_syntax(), _parse_drain_timeout(), Reservation, _stale_reservation_ttl_s(), _get_timeout_env_warned(), _get_timeout_order_warned(), parse_timeout_env(), process_stream_call_syntax_buffer() (+5 more)

### Community 45 - "ws-client.js"
Cohesion: 0.10
Nodes (26): clearIdleTimer(), {
  DEFAULT_WORK_DIR, AGENT_CLI, AGENT_MODEL, AGENT_ROLE,
  EVENT_ID, EPHEMERAL, IDLE_TIMEOUT_MS,
  CLI_429_MAX_RETRIES, CLI_429_INITIAL_DELAY_MS, CLI_429_BACKOFF_MULTIPLIER,
  resolveTimeoutMs, parsePositiveInt, MAX_TASK_WALL_MS, MAX_TIMER_MS,
}, { ensureEventDocument }, { executeCLIStreaming, prepareResultsDir, is429Error }, { filterSkillsByRole, filterSkillsByMode, swapActiveRules, restoreAllSkills }, fs, handleCancel(), handleTask() (+18 more)

### Community 47 - "ui/package.json"
Cohesion: 0.08
Nodes (28): autoprefixer, cronstrue, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, graphology-layout-forceatlas2 (+20 more)

### Community 48 - "EventDrillDown.tsx"
Cohesion: 0.13
Nodes (23): three, getEventPulses(), BrainCore(), CortexDevPage(), devQueryClient, CortexLiveFeedProps, EventDrillDown(), EventDrillDownProps (+15 more)

### Community 49 - "brain.py"
Cohesion: 0.08
Nodes (11): _BatchContext, compute_dispatch_backpressure(), _init_tool_names(), RepetitionCollapse, _sanitize_override_reason(), _select_dispatch_tier(), _wrap_section(), LLMStreamInterChunkTimeoutError (+3 more)

### Community 50 - "CortexGraph.tsx"
Cohesion: 0.14
Nodes (25): graphology, eventColor(), getExecutiveNeurons(), getStructuralEdges(), DEFAULT_TYPE_BUDGET, evictLru(), KNOWLEDGE_RING, KNOWLEDGE_RING_TYPES (+17 more)

### Community 52 - "formatter.py"
Cohesion: 0.12
Nodes (12): build_home_tab_view(), _context_line(), create_feedback_block(), format_event_summary(), format_plan_block(), format_task_card(), format_tool_result_blocks(), format_turn() (+4 more)

### Community 53 - "server.js"
Cohesion: 0.09
Nodes (18): { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, ensureEventDocument(), fs, path, stageEventDocument(), fetchEventDocument(), fs, { handleRequest } (+10 more)

### Community 54 - "cognitive_graph.py"
Cohesion: 0.11
Nodes (11): get_pulse_tracker(), dismiss_proposals(), DismissRequest, get_all_shadow_interventions(), get_cognitive_graph(), get_cortex_activity(), get_cortex_status(), get_event_shadow_interventions() (+3 more)

### Community 55 - "NodeInspector.tsx"
Cohesion: 0.13
Nodes (23): getClosedEvents(), ArchitectureEvent, ArgoCDOperation, ArchitectureGraph(), EVENT_LABELS, EventItem(), EventItemProps, healthTone() (+15 more)

### Community 56 - "useCortexData.ts"
Cohesion: 0.20
Nodes (23): getCognitiveGraph(), getCortexActivity(), getKGServiceDetail(), getKGServices(), getKGStats(), getRecentPulses(), CortexPage(), isOffRingCollection() (+15 more)

### Community 57 - "nightwatcher_tools.py"
Cohesion: 0.15
Nodes (13): PulseContext, ShiftIncident, ShiftInvestigation, execute_tool(), _handle_consult_deep_memory(), _handle_dispatch_investigation(), _handle_extend_incident(), _handle_get_event_report() (+5 more)

### Community 59 - "reconcile.py"
Cohesion: 0.15
Nodes (10): sanitize_redis_port(), _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers(), main() (+2 more)

### Community 60 - "event_to_markdown"
Cohesion: 0.12
Nodes (8): _resolve_maintainer_enum(), _resolve_slack_user(), CIAnalysis, _esc(), _esc_join(), event_to_markdown(), maintainer_env_key(), resolve_maintainer_emails()

### Community 64 - "GitHubAppAuth"
Cohesion: 0.11
Nodes (3): _find_pem_file(), get_github_auth(), GitHubAppAuth

### Community 65 - "dependencies"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 66 - "TokenUtilizationPage.tsx"
Cohesion: 0.15
Nodes (18): recharts, getFlowHistory(), FlowSnapshot, ObservationSeries, FlowHistoryPage(), formatTime(), RANGES, SparkCard() (+10 more)

### Community 67 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 68 - "claude-guard.js"
Cohesion: 0.14
Nodes (18): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+10 more)

### Community 70 - "NightwatcherObserver"
Cohesion: 0.14
Nodes (3): ShiftReport, _env_float(), NightwatcherObserver

### Community 71 - "ArchitectureGraph.tsx"
Cohesion: 0.14
Nodes (17): @dagrejs/dagre, @xyflow/react, applyDagreLayout(), applyGridLayout(), applyLayout(), ArchitectureGraphInner(), buildGraph(), computeIdHash() (+9 more)

### Community 74 - "cli-setup.js"
Cohesion: 0.13
Nodes (18): { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync }, filterSkillsByMode() (+10 more)

### Community 77 - "StateWatcher"
Cohesion: 0.13
Nodes (3): _QueueEntry, StateWatcher, _Subscription

### Community 78 - "_resolve_phase"
Cohesion: 0.13
Nodes (7): handle_classify_event(), handle_request_user_approval(), handle_set_phase(), IdleTimeoutPort, _resolve_domain(), resolve_event_domain(), _resolve_phase()

### Community 79 - "get_token_meter"
Cohesion: 0.10
Nodes (3): get_token_meter(), TokenMeter, TokenUsageDict

### Community 80 - "devDependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 81 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 82 - "gemini-sidecar/package.json"
Cohesion: 0.11
Nodes (18): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+10 more)

### Community 85 - "cortex/types.ts"
Cohesion: 0.15
Nodes (17): ActiveEvent, EventSource, KGServiceDetail, KGServiceEntity, CortexGraphProps, GraphLoaderProps, NeuronInfoPanelProps, PulseTimelineProps (+9 more)

### Community 86 - "JiraIncidentAdapter"
Cohesion: 0.15
Nodes (3): _adf_to_text(), _escape_jql_string(), JiraIncidentAdapter

### Community 89 - "QuotaTracker"
Cohesion: 0.14
Nodes (3): QuotaExhaustedError, QuotaTracker, RequestExceedsBurstError

### Community 91 - "ShiftsPage.tsx"
Cohesion: 0.23
Nodes (16): getCurrentShift(), getShiftDetail(), getShiftsList(), ShiftReportFull, ShiftReportSummary, FailedClusterBadge(), getISOWeek(), getWeekDates() (+8 more)

### Community 92 - "nightwatcher.py"
Cohesion: 0.16
Nodes (6): _env_int(), _fallback_platform(), _handle_declare_clusters(), reconcile_cluster_plan(), salvage_cluster_plan(), validate_cluster_plan()

### Community 93 - "catalog-skills.js"
Cohesion: 0.16
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 96 - "._authorize_plan_decision"
Cohesion: 0.13
Nodes (3): _PlanDecision, handle_approve(), handle_reject()

### Community 98 - "prompt.py"
Cohesion: 0.21
Nodes (11): _build_closed_block(), build_event_header(), _build_identity_block(), _build_journal_block(), _build_mermaid_block(), _build_related_block(), _build_subject_block(), _build_timing_block() (+3 more)

### Community 99 - "._run_report_cart"
Cohesion: 0.12
Nodes (7): build_report_iteration_prompt(), build_summary_prompt(), extract_full_links(), _normalize_gitlab_host(), build_extend_tool(), build_report_tool(), build_summary_tool()

### Community 101 - "generate_map.py"
Cohesion: 0.19
Nodes (6): _enumerate_gates(), _GateInfo, generate_phase_tool_map(), _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 106 - "ServiceNode.tsx"
Cohesion: 0.20
Nodes (11): HealthStatus, NodeType, AppNodeData, ARGOCD_HEALTH_COLORS, SYNC_ICONS, GENERIC_TAGS, HEALTH_COLORS, NODE_ICONS (+3 more)

### Community 108 - "handlers_planning.py"
Cohesion: 0.23
Nodes (7): _auto_complete_step(), _canonical_role(), handle_create_plan(), handle_get_plan_progress(), _is_failed_turn(), _is_orchestrator_turn(), _normalize_step_id()

### Community 111 - "JarvisMemoryPage.tsx"
Cohesion: 0.25
Nodes (13): dismissProposals(), EnhancementProposal, getHandoffReports(), getProposals(), HandoffReport, FilterMode, formatDate(), formatTime() (+5 more)

### Community 112 - "analyzeTokens"
Cohesion: 0.19
Nodes (13): analyzeString(), analyzeTokens(), assignName(), base(), combineCategories(), configEnvGuard(), configFileWriteGuard(), hasSubseq() (+5 more)

### Community 113 - "scheduling/__init__.py"
Cohesion: 0.22
Nodes (5): GitHubPrRef, GitLabMrRef, GitLabPipelineRef, KargoStageRef, PollFn

### Community 118 - "colors.ts"
Cohesion: 0.28
Nodes (11): asNumber(), asString(), asStringArray(), Badge(), describeNeuron(), Hdr(), NeuronInfoPanel(), AGENT_NEURON_COLORS (+3 more)

### Community 122 - "_sanitize_analysis_text"
Cohesion: 0.20
Nodes (5): _clamp_confidence(), _sanitize_analysis_text(), _strip_newlines(), _validate_analysis(), _validate_triage_entry()

### Community 123 - "testSetup.ts"
Cohesion: 0.18
Nodes (5): @tailwindcss/vite, @testing-library/react, vite, @vitejs/plugin-react, vitest

### Community 125 - "is_defer_event_available"
Cohesion: 0.18
Nodes (6): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 127 - "._register_handlers"
Cohesion: 0.18
Nodes (3): build_access_denied_home_view(), handle_app_home_opened(), handle_home_create_event()

### Community 128 - "cortex-constants.ts"
Cohesion: 0.18
Nodes (10): AGENTS, DOMAINS, HEMISPHERE_X, NEURON_DESCRIPTIONS, PHASE_SKILL_FOLDERS, PHASE_TOOL_PRIORITY, PHASES, StructuralEdge (+2 more)

### Community 129 - "CortexLiveFeed.tsx"
Cohesion: 0.27
Nodes (9): CortexHeartbeat(), CortexHeartbeatProps, ensureKeyframes(), CortexLiveFeed(), FILTER_PILLS, FilterKey, getStoredFilter(), MESSAGE_STYLES (+1 more)

### Community 131 - "gitGuard"
Cohesion: 0.29
Nodes (10): bareBranchProtected(), configWriteGuard(), externalGitCommand(), gitGuard(), gitQuery(), isProtected(), normRef(), pushGuard() (+2 more)

### Community 132 - "parseShell"
Cohesion: 0.33
Nodes (10): bodySubstitutions(), decodeAnsiC(), isArrayAssignPrefix(), isWordStart(), matchBacktick(), matchParen(), parseShell(), readHeredocStart() (+2 more)

### Community 133 - "_md_table_to_text"
Cohesion: 0.20
Nodes (5): _replace(), _md_table_to_block_kit(), _md_table_to_text(), _md_to_mrkdwn(), _parse_md_table()

### Community 134 - "generate_event_title"
Cohesion: 0.22
Nodes (3): generate_event_title(), get_adapter(), _get_semaphore()

### Community 136 - "entity_extractor.py"
Cohesion: 0.33
Nodes (5): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship

### Community 140 - "_prepare_console_tail"
Cohesion: 0.20
Nodes (4): _prepare_console_tail(), _redact_match(), _redact_secrets_in_text(), _sanitize_console_tail()

### Community 141 - "has_unevaluated_close_blocker"
Cohesion: 0.20
Nodes (4): has_unevaluated_close_blocker(), _pred_jarvis_response(), _pred_unevaluated_close(), is_jarvis_acknowledgment()

### Community 142 - "._send_turn_to_thread"
Cohesion: 0.27
Nodes (3): extract_tables(), get_agent_notification_text(), get_turn_attachment_color()

### Community 143 - "knowledge_graph_api.py"
Cohesion: 0.31
Nodes (4): get_kg_store(), get_service_detail(), get_stats(), list_services()

### Community 144 - "classifyTool"
Cohesion: 0.31
Nodes (9): apiTokens(), apiWriteNeedsGuard(), branchValues(), classifyTool(), hasOpaqueTarget(), httpGuard(), httpMethod(), isReadMethod() (+1 more)

### Community 145 - "get_quota_tracker"
Cohesion: 0.22
Nodes (3): get_quota_tracker(), llm_stats(), receive_telemetry()

### Community 164 - "adf_to_markdown"
Cohesion: 0.57
Nodes (7): adf_to_markdown(), _apply_marks(), _children(), _render(), _render_list(), _render_list_item(), _render_table_like()

### Community 165 - "validate-mutations.sh"
Cohesion: 0.57
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

### Community 166 - "._run_analysis_loop"
Cohesion: 0.33
Nodes (3): _append_user_turn(), _finalize_analysis_handover(), get_phase_tools()

### Community 168 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 169 - "state.js"
Cohesion: 0.33
Nodes (4): { AGENT_ROLE }, _blackboardTurns, _inboundMessages, _teammateMessages

### Community 179 - "_append_user_turn"
Cohesion: 0.33
Nodes (3): _append_user_turn(), _is_function_response_part(), _validated_parts()

### Community 180 - "build_gate_context"
Cohesion: 0.33
Nodes (3): build_gate_context(), conversation_has_decayed_turns(), _decay_payload_len()

### Community 190 - "classify"
Cohesion: 0.50
Nodes (4): classify(), main(), shellCategory(), shellNeedsGuard()

### Community 200 - "overrides"
Cohesion: 0.67
Nodes (3): overrides, @typescript-eslint/typescript-estree, minimatch

## Knowledge Gaps
- **13 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+8 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2300 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **118 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `logging`, `Archivist`, `main.py`, `os`, `queue.py`, `auth.py`, `generate_event_title`, `Brain`, `context_parts.py`, `ConversationTurn`, `EventDocument`, `ToolContext`, `ScheduleRepository`, `EventRepository`, `HeadhunterJira`, `observations_mgmt.py`, `list_events`, `brain.py`, `._restage_pending_signal`, `._stage_pending_signal`, `nightwatcher_tools.py`, `._count_pending`, `DashboardWSAdapter`, `NightwatcherObserver`, `LiveAPIAdapter`, `.__init__`, `nightwatcher.py`, `ArchitectureEvent`?**
  _High betweenness centrality (0.106) - this node is a cross-community bridge._
- **Are the 80 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 80 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.010711272513847622 - nodes in this community are weakly interconnected._
- **Why does `Brain` connect `Brain` to `BlackboardState`, `logging`, `Archivist`, `main.py`, `auth.py`, `._run_agent_task`, `ConversationTurn`, `EventDocument`, `ToolContext`, `BrainSkillLoader`, `._post_agent_recall`, `._process_with_llm`, `._resolve_grounding_urls`, `brain.py`, `._close_and_broadcast`, `._resolve_maintainer_enum`, `StalenessGuard`, `ResyncTrigger`, `DashboardWSAdapter`, `._build_contents`, `ReflexSearcher`, `StateWatcher`, `.__init__`, `IdleTimeoutManager`, `.start_event_loop`, `BrainLifecyclePort`, `ReconcileScheduler`, `._extract_context_flags`?**
  _High betweenness centrality (0.067) - this node is a cross-community bridge._
- **Are the 19 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 19 INFERRED edges - model-reasoned connections that need verification._
- **Should `logging` be split into smaller, more focused modules?**
  _Cohesion score 0.026194144838212634 - nodes in this community are weakly interconnected._