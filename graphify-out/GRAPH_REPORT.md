# Graph Report - Blackboard  (2026-11-19)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 5454 nodes · 12256 edges · 224 communities (100 shown, 124 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 971 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `19ee32dd`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BlackboardState
- logging
- lucide-react
- cognitive_graph.py
- queue.py
- main.py
- client.ts
- Brain
- os
- tool_gates.py
- react
- WorkspaceInspector.tsx
- auth.py
- http-handler.js
- colors.ts
- ._run_agent_task
- brain.py
- jenkins-mcp.js
- EventSidebar.tsx
- ReconcileScheduler
- useCortexData.ts
- GitHubPlatform
- App.tsx
- ToolContext
- TurnBubble.tsx
- GitLabPlatform
- EventRepository
- EventDocument
- _BrainToolContext
- ConversationTurn
- observations_mgmt.py
- merge-guard.js
- GeminiAdapter
- nightwatcher_tools.py
- ._process_with_llm
- ui/package.json
- cli-executor.js
- storage-recycler.js
- handlers_integration.py
- dispatch.py
- Aligner
- Headhunter
- llm/__init__.py
- formatter.py
- EventDrillDown.tsx
- SlackChannel
- ArchitectureGraph.tsx
- TimeKeeperPage.tsx
- ws-client.js
- BrainSkillLoader
- CortexGraph.tsx
- _resolve_phase
- WorkspaceTaskItem.tsx
- JenkinsObserver
- ._get_manager
- AgentRegistry
- KnowledgeGraphStore
- NightwatcherObserver
- LiveAPIAdapter
- types.py
- NodeInspector.tsx
- llm_error_classifier.py
- server.js
- StateWatcher
- ._build_system_prompt
- BrainIntrospectionPort
- quota_tracker.py
- JenkinsAdapter
- PulseBatch
- Archivist
- ArgoCDObserver
- handlers_dispatch.py
- KargoObserver
- TopologyRepository
- GitHubAppAuth
- dependencies
- NeuronInfoPanel.tsx
- gemini_client.py
- adf_to_markdown
- spawn_event_namer_task
- compilerOptions
- claude-guard.js
- FlowHistoryPage.tsx
- DashboardWSAdapter
- _sanitize_analysis_text
- reconcile.py
- IdleTimeoutManager
- VcsPlatformPort
- cli-setup.js
- ._shed_context_for_quota
- ReflexSearcher
- devDependencies
- compilerOptions
- gemini-sidecar/package.json
- ._build_contents
- EphemeralProvisioner
- ArchitectureEvent
- ObservationRepository
- catalog-skills.js
- TokenMeter
- .fetch_context
- EscalationRepository
- tool_router.py
- nightwatcher_prompt.py
- FairQueue
- generate_map.py
- JenkinsPlatformPort
- ._poll_and_stage
- OIDCKeyAdapter
- KubernetesSpawnHealthAdapter
- graph_recall.py
- VectorStore
- handlers_planning.py
- ._send_turn_to_thread
- ScheduleRepository
- SlackAccessGate
- MultiInstallationManager
- analyzeTokens
- record_token_usage
- .scroll
- ScheduleCreateRequest
- get_current_shift
- ._process_message
- _consider
- ._authorize_plan_decision
- is_defer_event_available
- gitGuard
- parseShell
- generate_event_title
- ._tool_send_event_message
- ._extract_context_flags
- JarvisPeerPort
- entity_extractor.py
- ._clear_recovered_group_flags
- knowledge_graph_api.py
- CortexDevPage.tsx
- classifyTool
- get_quota_tracker
- SpawnPollResult
- _sanitize_xml_fence
- SmartsheetMaintainerCache
- .has_reeval_signal
- AsyncGitHubClient
- GitLabTokenAuth
- _is_event_closed_or_missing
- ._evaluate_health
- HeadhunterJira
- ._triage_and_build_evidence
- LLMStreamInterChunkTimeoutError
- has_unevaluated_close_blocker
- TimeKeeperObserver
- CortexRepository
- validate-mutations.sh
- ._detect_repetition_collapse
- ._run_analysis_loop
- scripts
- state.js
- DispatchMetrics
- build_gate_context
- SpawnStatus
- BrainCore
- ._wait_for_registration
- agent_ws_endpoint
- classify
- _has_non_user_turns
- require-results.sh
- _WSFrameFilter
- _env_flag
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
1. `BlackboardState` - 298 edges
2. `Brain` - 168 edges
3. `ConversationTurn` - 131 edges
4. `ToolContext` - 103 edges
5. `GateContext` - 99 edges
6. `react` - 85 edges
7. `EventDocument` - 84 edges
8. `GitHubPlatform` - 73 edges
9. `fetchApi()` - 66 edges
10. `lifespan()` - 65 edges

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

## Communities (224 total, 124 thin omitted)

### Community 0 - "BlackboardState"
Cohesion: 0.01
Nodes (15): get_event_document(), get_all_journal(), get_service_journal(), delete_notebook_note(), get_notebook(), get_event_observations(), get_global_observations(), get_graph_data() (+7 more)

### Community 1 - "logging"
Cohesion: 0.03
Nodes (34): _annotation_replace(), _strip_pipeline_annotations(), _sanitize_lesson_text(), _parse_job_metadata(), AppNode, ChatRequest, ChatResponse, ConversationMessage (+26 more)

### Community 2 - "lucide-react"
Cohesion: 0.04
Nodes (95): lucide-react, react-router-dom, createChatEvent(), getActiveEvents(), getAgents(), getAlignerPending(), getEventDocument(), getEvents() (+87 more)

### Community 3 - "cognitive_graph.py"
Cohesion: 0.03
Nodes (33): get_archivist(), get_blackboard(), get_brain(), get_pulse_tracker(), ChatEventRequest, ChatEventResponse, create_chat_event(), dismiss_proposals() (+25 more)

### Community 4 - "queue.py"
Cohesion: 0.03
Nodes (47): resolve_approval_identity(), aligner_pending_items(), apply_lessons(), approve_event(), close_event_by_user(), CloseRequest, correct_memory(), CorrectMemoryRequest (+39 more)

### Community 5 - "main.py"
Cohesion: 0.03
Nodes (35): Architect, AgentClient, Developer, set_incident_options(), SysAdmin, set_oidc_adapter(), get_aligner(), get_architect() (+27 more)

### Community 6 - "client.ts"
Cohesion: 0.04
Nodes (82): ApiError, bulkDeleteObservations(), deleteNote(), deleteObservation(), exportObservations(), ExtractionResult, generateObservationsReport(), getEventObservations() (+74 more)

### Community 8 - "os"
Cohesion: 0.04
Nodes (28): JiraIncidentAdapter, _csv_env(), _get_static_maintainer_emails(), _iso(), _mention_pattern(), _parse_ts(), _review_ignore_logins(), _review_trusted_associations() (+20 more)

### Community 9 - "tool_gates.py"
Cohesion: 0.05
Nodes (79): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+71 more)

### Community 10 - "react"
Cohesion: 0.06
Nodes (72): react, applyLessons(), correctMemory(), createKnowledge(), createLesson(), deleteKnowledge(), deleteLesson(), ExtractedCorrection (+64 more)

### Community 11 - "WorkspaceInspector.tsx"
Cohesion: 0.05
Nodes (64): CiContext, ConversationTurn, EventEvidence, TokenUsageDict, CiContextCard(), CiContextCardProps, ConsoleTailBlock(), FailedJobRow() (+56 more)

### Community 12 - "auth.py"
Cohesion: 0.04
Nodes (21): can_append_message(), can_approve_event(), can_override_domain(), can_rename_event(), _claims_to_user(), get_user_from_request(), get_user_from_slack(), get_user_from_websocket() (+13 more)

### Community 13 - "http-handler.js"
Cohesion: 0.08
Nodes (62): is429Error(), registerMCPsAndHooks(), resolveCommand(), writeAgyMcpServer(), writeClaudeMcpServer(), parsePositiveInt(), buildArgoCDMcpConfig(), createAppJWT() (+54 more)

### Community 14 - "colors.ts"
Cohesion: 0.07
Nodes (43): @tanstack/react-query, getReport(), getReports(), searchReports(), ReportFull, ReportMeta, CompactCardStrip(), EventHistory() (+35 more)

### Community 15 - "._run_agent_task"
Cohesion: 0.06
Nodes (12): on_huddle(), on_progress(), on_huddle(), on_progress(), _compute_processed_up_to(), _is_automated_nudge(), _is_external_input_turn(), _is_participant_turn() (+4 more)

### Community 16 - "brain.py"
Cohesion: 0.06
Nodes (26): _contents_have_pruned_or_decayed(), _apply_sibling_signature(), build_function_response(), build_single_function_response(), compress_contents(), contents_have_pruned_or_decayed(), estimate_msg_tokens(), estimate_tokens() (+18 more)

### Community 17 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 18 - "EventSidebar.tsx"
Cohesion: 0.09
Nodes (52): getHeadhunterPending(), getJiraMissions(), HeadhunterTodo, postJiraAction(), ACTION_BADGE, formatAge(), HeadhunterQueuePanel(), renderItem() (+44 more)

### Community 19 - "ReconcileScheduler"
Cohesion: 0.05
Nodes (7): get_token_meter(), FlowCollector, ReconcileScheduler, Trigger, QueueTrigger, ResyncTrigger, StalenessGuard

### Community 20 - "useCortexData.ts"
Cohesion: 0.08
Nodes (51): dismissProposals(), EnhancementProposal, getCognitiveGraph(), getCortexActivity(), getHandoffReports(), getKGServiceDetail(), getKGServices(), getKGStats() (+43 more)

### Community 22 - "App.tsx"
Cohesion: 0.06
Nodes (41): oidc-client-ts, getConfig(), getIncidents(), getWSAuthFailureCallback(), Incident, setOnUnauthorized(), setTokenGetter(), setWSAuthFailureCallback() (+33 more)

### Community 23 - "ToolContext"
Cohesion: 0.07
Nodes (13): handle_message_agent(), handle_reply_to_agent(), handle_select_agent(), _sticky_work_style(), handle_classify_event(), handle_defer_event(), handle_hold_watch(), handle_request_user_approval() (+5 more)

### Community 24 - "TurnBubble.tsx"
Cohesion: 0.08
Nodes (39): @uiw/react-markdown-preview, approveEvent(), closeEvent(), enforceCasualDomain(), getEventReport(), rejectEvent(), submitFeedback(), CollapsibleSectionProps (+31 more)

### Community 29 - "ConversationTurn"
Cohesion: 0.12
Nodes (31): emit_tool_result(), _coerce_turn_int(), handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_recall_pruned_turns(), _parse_turn_int(), _sanitize_recalled() (+23 more)

### Community 30 - "observations_mgmt.py"
Cohesion: 0.06
Nodes (18): get_report_client(), _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), render_pdf(), _sample_points() (+10 more)

### Community 31 - "merge-guard.js"
Cohesion: 0.04
Nodes (46): API_VALUED, ARGO_MUTATING, ARGO_READ_SUB, ARGO_READ_TOP, BODY_FLAG, BROWSER_READ, CTX, ENV_BUILTINS (+38 more)

### Community 32 - "GeminiAdapter"
Cohesion: 0.09
Nodes (9): _attach_signature_to_parts(), _clone_part_with_sig(), _coerce_part(), _decode_sig_bytes(), _extract_part_signature(), GeminiAdapter, _is_empty_sig_carrier(), _part_has_fc() (+1 more)

### Community 33 - "nightwatcher_tools.py"
Cohesion: 0.09
Nodes (22): PulseContext, ShiftIncident, ShiftInvestigation, extract_full_links(), build_extend_tool(), build_report_tool(), build_summary_tool(), execute_tool() (+14 more)

### Community 34 - "._process_with_llm"
Cohesion: 0.05
Nodes (4): _BatchContext, _ensure_recall_tool_if_needed(), _QuotaShedState, _retry_backoff_delay()

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

### Community 39 - "dispatch.py"
Cohesion: 0.08
Nodes (13): _build_prompt(), _check_security(), consume_wake_task(), _consume(), _dispatch_timeout_s(), dispatch_to_agent(), _consume_queue(), _sanitize_stdout() (+5 more)

### Community 42 - "llm/__init__.py"
Cohesion: 0.09
Nodes (7): ClaudeAdapter, _parse_tpm_limit(), FunctionCall, LLMChunk, LLMPort, LLMResponse, TokenUsage

### Community 43 - "formatter.py"
Cohesion: 0.08
Nodes (17): build_access_denied_home_view(), build_home_tab_view(), _context_line(), create_feedback_block(), _replace(), format_event_summary(), format_plan_block(), format_task_card() (+9 more)

### Community 44 - "EventDrillDown.tsx"
Cohesion: 0.10
Nodes (32): getEventPulses(), EventSource, CortexDevPage(), CortexHeartbeat(), CortexHeartbeatProps, ensureKeyframes(), CortexLiveFeed(), CortexLiveFeedProps (+24 more)

### Community 46 - "ArchitectureGraph.tsx"
Cohesion: 0.09
Nodes (28): @dagrejs/dagre, @xyflow/react, HealthStatus, NodeType, AppNodeData, applyDagreLayout(), applyGridLayout(), applyLayout() (+20 more)

### Community 47 - "TimeKeeperPage.tsx"
Cohesion: 0.11
Nodes (25): react-dom, createSchedule(), deleteSchedule(), getSchedules(), refineInstructions(), ScheduleCreatePayload, ScheduleItem, toggleSchedule() (+17 more)

### Community 48 - "ws-client.js"
Cohesion: 0.10
Nodes (26): clearIdleTimer(), {
  DEFAULT_WORK_DIR, AGENT_CLI, AGENT_MODEL, AGENT_ROLE,
  EVENT_ID, EPHEMERAL, IDLE_TIMEOUT_MS,
  CLI_429_MAX_RETRIES, CLI_429_INITIAL_DELAY_MS, CLI_429_BACKOFF_MULTIPLIER,
  resolveTimeoutMs, parsePositiveInt, MAX_TASK_WALL_MS, MAX_TIMER_MS,
}, { ensureEventDocument }, { executeCLIStreaming, prepareResultsDir, is429Error }, { filterSkillsByRole, filterSkillsByMode, swapActiveRules, restoreAllSkills }, fs, handleCancel(), handleTask() (+18 more)

### Community 50 - "CortexGraph.tsx"
Cohesion: 0.12
Nodes (30): graphology, ActiveEvent, KGServiceEntity, eventColor(), getExecutiveNeurons(), getStructuralEdges(), DEFAULT_TYPE_BUDGET, evictLru() (+22 more)

### Community 51 - "_resolve_phase"
Cohesion: 0.10
Nodes (18): _batch_is_terminal_for_flush(), _is_close_phase_fc(), can_transition_to_close(), _build_closed_block(), build_event_header(), _build_identity_block(), _build_journal_block(), _build_mermaid_block() (+10 more)

### Community 52 - "WorkspaceTaskItem.tsx"
Cohesion: 0.11
Nodes (26): AgentStreamCard(), AgentStreamCardProps, MessageCards(), GridTile(), GridTileProps, TileType, InlineMarkdownViewer(), relativeAge() (+18 more)

### Community 55 - "AgentRegistry"
Cohesion: 0.09
Nodes (4): AgentConnection, AgentRegistry, agent_websocket_handler(), _heartbeat()

### Community 56 - "KnowledgeGraphStore"
Cohesion: 0.15
Nodes (4): _acquire(), KnowledgeGraphStore, _sanitize(), _with_timeout()

### Community 57 - "NightwatcherObserver"
Cohesion: 0.12
Nodes (4): ShiftReport, _env_float(), _env_int(), NightwatcherObserver

### Community 59 - "types.py"
Cohesion: 0.10
Nodes (13): derive_llm_priority(), _get_timeout_env_warned(), _get_timeout_order_warned(), is_partial_control_token(), parse_timeout_env(), _patch_enum_fields(), process_stream_call_syntax_buffer(), resolve_stream_timeouts() (+5 more)

### Community 60 - "NodeInspector.tsx"
Cohesion: 0.13
Nodes (24): getClosedEvents(), ArchitectureEvent, ArgoCDOperation, ArchitectureGraph(), EVENT_LABELS, EventItem(), EventItemProps, healthTone() (+16 more)

### Community 61 - "llm_error_classifier.py"
Cohesion: 0.13
Nodes (9): _extract_status_code(), _has_non_retryable_cause(), _is_google_auth_transport_error(), is_rate_limit(), is_transient(), is_transient_llm_error_turn(), _iter_exception_chain(), _matches_mro() (+1 more)

### Community 62 - "server.js"
Cohesion: 0.09
Nodes (18): { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, ensureEventDocument(), fs, path, stageEventDocument(), fetchEventDocument(), fs, { handleRequest } (+10 more)

### Community 63 - "StateWatcher"
Cohesion: 0.10
Nodes (3): _QueueEntry, StateWatcher, _Subscription

### Community 64 - "._build_system_prompt"
Cohesion: 0.08
Nodes (3): _init_tool_names(), _strip_tool_names(), _wrap_section()

### Community 65 - "BrainIntrospectionPort"
Cohesion: 0.08
Nodes (3): BrainIntrospectionPort, BrainLifecyclePort, BroadcastPort

### Community 66 - "quota_tracker.py"
Cohesion: 0.11
Nodes (5): QuotaExhaustedError, QuotaTracker, RequestExceedsBurstError, Reservation, _stale_reservation_ttl_s()

### Community 68 - "PulseBatch"
Cohesion: 0.10
Nodes (4): PulseBatch, PulsePort, PulseObserver, PulseTracker

### Community 71 - "handlers_dispatch.py"
Cohesion: 0.12
Nodes (7): handle_report_incident(), _resolve_escalation_scope(), _esc(), _esc_join(), event_to_markdown(), maintainer_env_key(), resolve_maintainer_emails()

### Community 74 - "GitHubAppAuth"
Cohesion: 0.11
Nodes (3): _find_pem_file(), get_github_auth(), GitHubAppAuth

### Community 75 - "dependencies"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 76 - "NeuronInfoPanel.tsx"
Cohesion: 0.12
Nodes (22): AGENTS, DOMAINS, HEMISPHERE_X, NEURON_DESCRIPTIONS, PHASE_SKILL_FOLDERS, PHASE_TOOL_PRIORITY, PHASES, StructuralEdge (+14 more)

### Community 77 - "gemini_client.py"
Cohesion: 0.11
Nodes (10): _append_user_turn(), _clone_part_with_text(), _extract_call_syntax(), _is_function_response_part(), _parse_drain_timeout(), _strip_user_thought_signature(), _validated_parts(), sanitize_call_syntax() (+2 more)

### Community 78 - "adf_to_markdown"
Cohesion: 0.13
Nodes (9): _adf_to_text(), _escape_jql_string(), adf_to_markdown(), _apply_marks(), _children(), _render(), _render_list(), _render_list_item() (+1 more)

### Community 79 - "spawn_event_namer_task"
Cohesion: 0.18
Nodes (7): spawn_event_namer_task(), handle_app_home_opened(), handle_app_mention(), handle_create_event_modal(), handle_darwin_command(), on_dm_message(), fallback_title()

### Community 80 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 81 - "claude-guard.js"
Cohesion: 0.14
Nodes (18): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+10 more)

### Community 82 - "FlowHistoryPage.tsx"
Cohesion: 0.21
Nodes (17): recharts, getFlowHistory(), FlowSnapshot, FlowHistoryPage(), RANGES, SparkCard(), SparkCardProps, formatTime() (+9 more)

### Community 84 - "_sanitize_analysis_text"
Cohesion: 0.10
Nodes (9): _clamp_confidence(), _prepare_console_tail(), _redact_match(), _redact_secrets_in_text(), _sanitize_analysis_text(), _sanitize_console_tail(), _strip_newlines(), _validate_analysis() (+1 more)

### Community 85 - "reconcile.py"
Cohesion: 0.18
Nodes (9): _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers(), main(), _parse_frontmatter() (+1 more)

### Community 88 - "cli-setup.js"
Cohesion: 0.13
Nodes (18): { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync }, filterSkillsByMode() (+10 more)

### Community 91 - "devDependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 92 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 93 - "gemini-sidecar/package.json"
Cohesion: 0.11
Nodes (18): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+10 more)

### Community 97 - "ArchitectureEvent"
Cohesion: 0.13
Nodes (3): ArchitectureEvent, list_events(), MetricsRepository

### Community 100 - "catalog-skills.js"
Cohesion: 0.16
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 106 - "tool_router.py"
Cohesion: 0.14
Nodes (3): IdleTimeoutPort, IncidentAdapterPort, StateWatcherPort

### Community 107 - "nightwatcher_prompt.py"
Cohesion: 0.14
Nodes (7): StagedEscalation, build_manifest_table(), build_report_iteration_prompt(), build_summary_prompt(), build_system_prompt(), extract_event_links(), _normalize_gitlab_host()

### Community 109 - "generate_map.py"
Cohesion: 0.19
Nodes (6): _enumerate_gates(), _GateInfo, generate_phase_tool_map(), _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 110 - "JenkinsPlatformPort"
Cohesion: 0.13
Nodes (4): BuildDetails, JenkinsPlatformPort, JobRunState, ViewScanResult

### Community 114 - "graph_recall.py"
Cohesion: 0.19
Nodes (5): _format_graph_context(), get_graph_context(), _parse_props(), _sanitize(), translate_to_lookups()

### Community 117 - "handlers_planning.py"
Cohesion: 0.23
Nodes (7): _auto_complete_step(), _canonical_role(), handle_create_plan(), handle_get_plan_progress(), _is_failed_turn(), _is_orchestrator_turn(), _normalize_step_id()

### Community 119 - "._send_turn_to_thread"
Cohesion: 0.18
Nodes (4): extract_tables(), get_agent_notification_text(), get_turn_attachment_color(), table_block_to_code_block()

### Community 123 - "analyzeTokens"
Cohesion: 0.19
Nodes (13): analyzeString(), analyzeTokens(), assignName(), base(), combineCategories(), configEnvGuard(), configFileWriteGuard(), hasSubseq() (+5 more)

### Community 127 - "get_current_shift"
Cohesion: 0.15
Nodes (3): get_current_shift(), get_shift_detail(), list_shifts()

### Community 131 - "._authorize_plan_decision"
Cohesion: 0.18
Nodes (3): _PlanDecision, handle_approve(), handle_reject()

### Community 132 - "is_defer_event_available"
Cohesion: 0.18
Nodes (6): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 133 - "gitGuard"
Cohesion: 0.29
Nodes (10): bareBranchProtected(), configWriteGuard(), externalGitCommand(), gitGuard(), gitQuery(), isProtected(), normRef(), pushGuard() (+2 more)

### Community 134 - "parseShell"
Cohesion: 0.33
Nodes (10): bodySubstitutions(), decodeAnsiC(), isArrayAssignPrefix(), isWordStart(), matchBacktick(), matchParen(), parseShell(), readHeredocStart() (+2 more)

### Community 135 - "generate_event_title"
Cohesion: 0.22
Nodes (3): generate_event_title(), get_adapter(), _get_semaphore()

### Community 140 - "entity_extractor.py"
Cohesion: 0.33
Nodes (5): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship

### Community 142 - "knowledge_graph_api.py"
Cohesion: 0.31
Nodes (4): get_kg_store(), get_service_detail(), get_stats(), list_services()

### Community 143 - "CortexDevPage.tsx"
Cohesion: 0.36
Nodes (8): devQueryClient, MOCK_CORTEX_STATUS, MOCK_EVENT_ID, MOCK_NEURONS, MOCK_PULSE_BATCHES, MOCK_SHADOW, MOCK_THINKING, MOCK_WHISPERS

### Community 144 - "classifyTool"
Cohesion: 0.31
Nodes (9): apiTokens(), apiWriteNeedsGuard(), branchValues(), classifyTool(), hasOpaqueTarget(), httpGuard(), httpMethod(), isReadMethod() (+1 more)

### Community 145 - "get_quota_tracker"
Cohesion: 0.22
Nodes (3): get_quota_tracker(), llm_stats(), receive_telemetry()

### Community 158 - "LLMStreamInterChunkTimeoutError"
Cohesion: 0.25
Nodes (4): LLMStreamInterChunkTimeoutError, LLMStreamTimeoutError, LLMStreamTotalTimeoutError, LLMStreamTTFBTimeoutError

### Community 159 - "has_unevaluated_close_blocker"
Cohesion: 0.25
Nodes (4): has_unevaluated_close_blocker(), _pred_jarvis_response(), _pred_unevaluated_close(), is_stabilization_wake()

### Community 162 - "validate-mutations.sh"
Cohesion: 0.57
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

### Community 165 - "._run_analysis_loop"
Cohesion: 0.33
Nodes (3): _append_user_turn(), _finalize_analysis_handover(), get_phase_tools()

### Community 166 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 167 - "state.js"
Cohesion: 0.33
Nodes (4): { AGENT_ROLE }, _blackboardTurns, _inboundMessages, _teammateMessages

### Community 177 - "build_gate_context"
Cohesion: 0.33
Nodes (3): build_gate_context(), conversation_has_decayed_turns(), _decay_payload_len()

### Community 183 - "classify"
Cohesion: 0.50
Nodes (4): classify(), main(), shellCategory(), shellNeedsGuard()

## Knowledge Gaps
- **13 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+8 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2404 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **124 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `logging`, `cognitive_graph.py`, `queue.py`, `main.py`, `Brain`, `os`, `generate_event_title`, `auth.py`, `brain.py`, `_is_event_closed_or_missing`, `HeadhunterJira`, `EventDocument`, `ConversationTurn`, `observations_mgmt.py`, `nightwatcher_tools.py`, `_resolve_phase`, `NightwatcherObserver`, `LiveAPIAdapter`, `DashboardWSAdapter`, `._shed_context_for_quota`, `ArchitectureEvent`, `tool_router.py`, `nightwatcher_prompt.py`, `ScheduleRepository`, `get_current_shift`?**
  _High betweenness centrality (0.118) - this node is a cross-community bridge._
- **Are the 80 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 80 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.00973614471713331 - nodes in this community are weakly interconnected._
- **Why does `Brain` connect `Brain` to `BlackboardState`, `logging`, `main.py`, `._extract_context_flags`, `JarvisPeerPort`, `._run_agent_task`, `brain.py`, `ReconcileScheduler`, `EventDocument`, `ConversationTurn`, `._process_with_llm`, `._detect_repetition_collapse`, `dispatch.py`, `._escalation_blocked`, `BrainSkillLoader`, `._resolve_maintainer_enum`, `.execute_tool_locked`, `._format_merge_evidence`, `StateWatcher`, `.append_and_broadcast`, `.broadcast`, `._build_system_prompt`, `.next_turn_number`, `BrainIntrospectionPort`, `.set_headhunter_close_signal`, `Archivist`, `PulseBatch`, `DashboardWSAdapter`, `IdleTimeoutManager`, `._shed_context_for_quota`, `ReflexSearcher`, `._build_contents`?**
  _High betweenness centrality (0.045) - this node is a cross-community bridge._
- **Are the 20 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Should `logging` be split into smaller, more focused modules?**
  _Cohesion score 0.02701009397841977 - nodes in this community are weakly interconnected._