# Graph Report - Blackboard  (2026-11-22)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 5453 nodes · 12255 edges · 213 communities (106 shown, 107 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 971 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `4c01b218`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BlackboardState
- queue.py
- client.ts
- BaseModel
- os
- Archivist
- logging
- OpsStateContext.tsx
- brain.py
- ConversationTurn
- main.py
- EventChatPanel.tsx
- Brain
- tool_gates.py
- EventSidebar.tsx
- AgentRegistry
- ._run_agent_task
- typing
- http-handler.js
- BrainSkillLoader
- WorkspaceInspector.tsx
- jenkins-mcp.js
- App.tsx
- react
- TurnBubble.tsx
- ._process_with_llm
- EventDocument
- Aligner
- Headhunter
- EventRepository
- _BrainToolContext
- StreamGrid.tsx
- ScheduleCreateRequest
- merge-guard.js
- GeminiAdapter
- EventEvidence
- ui/package.json
- cli-executor.js
- storage-recycler.js
- GitHubPlatform
- SlackChannel
- EventDrillDown.tsx
- llm/__init__.py
- models.py
- jenkins_observer.py
- observations_mgmt.py
- GitLabPlatform
- formatter.py
- AgentClient
- ArchitectureGraph.tsx
- handlers_integration.py
- TimeKeeperPage.tsx
- ws-client.js
- NightwatcherObserver
- useCortexData.ts
- spawn_event_namer_task
- time
- JenkinsObserver
- NeuronInfoPanel.tsx
- ._build_contents
- KnowledgeGraphStore
- ._close_and_broadcast
- types.py
- NodeInspector.tsx
- llm_error_classifier.py
- server.js
- CortexGraph.tsx
- quota_tracker.py
- JenkinsAdapter
- ._build_system_prompt
- ArgoCDObserver
- KargoObserver
- dependencies
- LiveAPIAdapter
- .fetch_context
- nightwatcher_tools.py
- GitHubAppAuth
- compilerOptions
- claude-guard.js
- FlowHistoryPage.tsx
- reconcile.py
- gemini_client.py
- VcsPlatformPort
- PulseBatch
- cli-setup.js
- slack.py
- ReflexSearcher
- StateWatcher
- FairQueue
- devDependencies
- compilerOptions
- gemini-sidecar/package.json
- handlers_dispatch.py
- EphemeralProvisioner
- get_report
- FlowSnapshot
- RedisClient
- nightwatcher_prompt.py
- ReconcileScheduler
- ObservationRepository
- ShiftsPage.tsx
- nightwatcher.py
- catalog-skills.js
- SlackAccessGate
- ._poll_and_stage
- JarvisPeerPort
- EscalationRepository
- JiraIncidentAdapter
- TokenMeter
- generate_map.py
- JenkinsPlatformPort
- OIDCKeyAdapter
- KubernetesSpawnHealthAdapter
- IdleTimeoutManager
- graph_recall.py
- IncidentAdapterPort
- .list_observations
- ._connect
- handlers_planning.py
- ScheduleRepository
- analyzeTokens
- ._extract_context_flags
- get_current_shift
- MultiInstallationManager
- ._process_message
- CortexLiveFeed.tsx
- .start_event_loop
- is_defer_event_available
- spawn_health.py
- gitGuard
- parseShell
- generate_event_title
- _is_event_closed_or_missing
- ._tool_send_event_message
- entity_extractor.py
- _consider
- ._clear_recovered_group_flags
- has_unevaluated_close_blocker
- knowledge_graph_api.py
- classifyTool
- get_quota_tracker
- SpawnPollResult
- SmartsheetMaintainerCache
- .has_reeval_signal
- get_event_document
- Trigger
- AsyncGitHubClient
- GitLabTokenAuth
- ._evaluate_health
- HeadhunterJira
- LLMStreamInterChunkTimeoutError
- ConversationMessage
- TimeKeeperObserver
- CortexRepository
- validate-mutations.sh
- ._run_analysis_loop
- get_all_journal
- scripts
- state.js
- DispatchMetrics
- build_gate_context
- list_failed_stages
- dex_proxy
- ._wait_for_registration
- get_notebook
- classify
- require-results.sh
- get_intermediate_tools
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

## Communities (213 total, 107 thin omitted)

### Community 1 - "queue.py"
Cohesion: 0.03
Nodes (55): get_token_meter(), can_approve_event(), can_override_domain(), can_rename_event(), _normalize_email(), get_archivist(), get_brain(), aligner_pending_items() (+47 more)

### Community 2 - "client.ts"
Cohesion: 0.03
Nodes (93): @tanstack/react-query, ApiError, bulkDeleteObservations(), createChatEvent(), deleteNote(), deleteObservation(), exportObservations(), ExtractedCorrection (+85 more)

### Community 3 - "BaseModel"
Cohesion: 0.02
Nodes (22): AppNode, GraphEdge, GraphNode, GraphResponse, JenkinsPendingItem, PendingAnomaly, RefineRequest, RefineResponse (+14 more)

### Community 4 - "os"
Cohesion: 0.04
Nodes (38): _adf_to_text(), _resolve_maintainer_enum(), _csv_env(), _get_static_maintainer_emails(), _iso(), _parse_ts(), _review_ignore_logins(), _review_trusted_associations() (+30 more)

### Community 5 - "Archivist"
Cohesion: 0.04
Nodes (4): Archivist, _decode_cursor(), _encode_cursor(), VectorStore

### Community 6 - "logging"
Cohesion: 0.04
Nodes (25): _claims_to_user(), get_user_from_request(), get_user_from_websocket(), require_auth(), require_obs_admin(), UserContext, _validate_jwt(), get_blackboard() (+17 more)

### Community 7 - "OpsStateContext.tsx"
Cohesion: 0.05
Nodes (65): react-router-dom, getActiveEvents(), getAgents(), getEventDocument(), getEvents(), getKargoStages(), updateEventTitle(), EventEvidence (+57 more)

### Community 8 - "brain.py"
Cohesion: 0.04
Nodes (41): _close_unanswered_fc(), _contents_have_pruned_or_decayed(), _apply_sibling_signature(), build_function_response(), build_single_function_response(), compress_contents(), contents_have_pruned_or_decayed(), estimate_msg_tokens() (+33 more)

### Community 9 - "ConversationTurn"
Cohesion: 0.07
Nodes (38): emit_tool_result(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_message_agent(), handle_reply_to_agent(), handle_report_incident(), handle_select_agent(), handle_ask_release_ai() (+30 more)

### Community 10 - "main.py"
Cohesion: 0.03
Nodes (35): set_incident_options(), SysAdmin, set_oidc_adapter(), get_aligner(), get_architect(), get_argocd_observer(), get_developer(), get_kargo_observer() (+27 more)

### Community 11 - "EventChatPanel.tsx"
Cohesion: 0.06
Nodes (55): getReport(), getReports(), ReportFull, ReportMeta, SubjectType, DeferCountdownBar(), CompactCardStrip(), EventHistory() (+47 more)

### Community 13 - "tool_gates.py"
Cohesion: 0.05
Nodes (79): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+71 more)

### Community 14 - "EventSidebar.tsx"
Cohesion: 0.06
Nodes (72): getAlignerPending(), getHeadhunterPending(), getJenkinsPending(), getJiraMissions(), getWaitingApprovalEvents(), HeadhunterTodo, postJiraAction(), AgentRegistryEntry (+64 more)

### Community 15 - "AgentRegistry"
Cohesion: 0.05
Nodes (17): AgentConnection, AgentRegistry, agent_websocket_handler(), _heartbeat(), _build_prompt(), _check_security(), consume_wake_task(), _consume() (+9 more)

### Community 16 - "._run_agent_task"
Cohesion: 0.05
Nodes (13): on_huddle(), on_progress(), on_huddle(), on_progress(), _compute_processed_up_to(), _is_automated_nudge(), _is_external_input_turn(), _is_participant_turn() (+5 more)

### Community 17 - "typing"
Cohesion: 0.05
Nodes (5): _sanitize_lesson_text(), create_adapter(), Pulse, _load_name_mapping(), sanitize_redis_port()

### Community 18 - "http-handler.js"
Cohesion: 0.08
Nodes (62): is429Error(), registerMCPsAndHooks(), resolveCommand(), writeAgyMcpServer(), writeClaudeMcpServer(), parsePositiveInt(), buildArgoCDMcpConfig(), createAppJWT() (+54 more)

### Community 19 - "BrainSkillLoader"
Cohesion: 0.04
Nodes (6): _parse_positive_int_env(), BrainSkillLoader, _SkillCorpus, BrainIntrospectionPort, BrainLifecyclePort, BroadcastPort

### Community 20 - "WorkspaceInspector.tsx"
Cohesion: 0.06
Nodes (52): CiContext, ConversationTurn, TokenUsageDict, CiContextCard(), CiContextCardProps, ConsoleTailBlock(), FailedJobRow(), BORDER_COLOR (+44 more)

### Community 21 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 22 - "App.tsx"
Cohesion: 0.06
Nodes (48): oidc-client-ts, react-dom, dismissProposals(), EnhancementProposal, getConfig(), getHandoffReports(), getProposals(), getWSAuthFailureCallback() (+40 more)

### Community 23 - "react"
Cohesion: 0.08
Nodes (52): lucide-react, react, applyLessons(), correctMemory(), createKnowledge(), createLesson(), deleteKnowledge(), deleteLesson() (+44 more)

### Community 24 - "TurnBubble.tsx"
Cohesion: 0.08
Nodes (44): @uiw/react-markdown-preview, approveEvent(), closeEvent(), enforceCasualDomain(), getEventReport(), rejectEvent(), submitFeedback(), ChatInputProps (+36 more)

### Community 25 - "._process_with_llm"
Cohesion: 0.04
Nodes (5): _BatchContext, _ensure_recall_tool_if_needed(), _QuotaShedState, RepetitionCollapse, _retry_backoff_delay()

### Community 31 - "StreamGrid.tsx"
Cohesion: 0.08
Nodes (40): AgentStreamCard(), AgentStreamCardProps, MessageCards(), Dashboard(), GridTile(), GridTileProps, TileType, InlineMarkdownViewer() (+32 more)

### Community 32 - "ScheduleCreateRequest"
Cohesion: 0.05
Nodes (8): EventInput, ScheduleCreateRequest, create_schedule(), delete_schedule(), get_schedule(), list_schedules(), toggle_schedule(), update_schedule()

### Community 33 - "merge-guard.js"
Cohesion: 0.04
Nodes (46): API_VALUED, ARGO_MUTATING, ARGO_READ_SUB, ARGO_READ_TOP, BODY_FLAG, BROWSER_READ, CTX, ENV_BUILTINS (+38 more)

### Community 34 - "GeminiAdapter"
Cohesion: 0.09
Nodes (10): _attach_signature_to_parts(), _clone_part_with_text(), _coerce_part(), _decode_sig_bytes(), _extract_part_signature(), GeminiAdapter, _is_empty_sig_carrier(), _part_has_fc() (+2 more)

### Community 35 - "EventEvidence"
Cohesion: 0.07
Nodes (8): DashboardWSAdapter, can_append_message(), prompt_display_name(), resolve_approval_identity(), EventEvidence, ChatEventRequest, ChatEventResponse, create_chat_event()

### Community 36 - "ui/package.json"
Cohesion: 0.05
Nodes (37): autoprefixer, cronstrue, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, graphology-layout-forceatlas2 (+29 more)

### Community 37 - "cli-executor.js"
Cohesion: 0.09
Nodes (37): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, MAX_TASK_WALL_MS, MAX_TIMER_MS, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS, STORAGE_PRETASK_TIMEOUT_MS, resolveStorageRoot }, buildCLICommand(), buildTimeoutResult(), { checkAndRecycleStorage, pinTaskCwd, unpinTaskCwd }, CLAUDE_JSON_PATH, cp, createInactivityWatchdog(), executeCLI() (+29 more)

### Community 38 - "storage-recycler.js"
Cohesion: 0.08
Nodes (37): withTaskStorage(), MAX_TASK_WALL_MS, parseTimerMs(), resolveStorageRoot(), resolveTimeoutMs(), ROLE_TIMEOUTS, STORAGE_ACTIVITY_HEARTBEAT_MS, STORAGE_MAX_TIER3_DELETIONS (+29 more)

### Community 39 - "GitHubPlatform"
Cohesion: 0.06
Nodes (3): GitHubPlatform, _poll_one(), _poll_one()

### Community 40 - "SlackChannel"
Cohesion: 0.06
Nodes (3): table_block_to_code_block(), SlackChannel, handle_home_create_event()

### Community 41 - "EventDrillDown.tsx"
Cohesion: 0.09
Nodes (34): three, getEventPulses(), EventSource, BrainCore(), CortexDevPage(), devQueryClient, CortexLiveFeedProps, EventDrillDown() (+26 more)

### Community 42 - "llm/__init__.py"
Cohesion: 0.08
Nodes (7): ClaudeAdapter, _parse_tpm_limit(), FunctionCall, LLMChunk, LLMPort, LLMResponse, TokenUsage

### Community 43 - "models.py"
Cohesion: 0.07
Nodes (13): ArchitectureEvent, ChatRequest, ChatResponse, EventMetrics, EventStatus, EventType, HealthStatus, MessageStatus (+5 more)

### Community 44 - "jenkins_observer.py"
Cohesion: 0.07
Nodes (16): _annotation_replace(), _strip_pipeline_annotations(), _clamp_confidence(), _env_flag(), _parse_job_metadata(), _prepare_console_tail(), _redact_build_parameters(), _redact_match() (+8 more)

### Community 45 - "observations_mgmt.py"
Cohesion: 0.08
Nodes (16): _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), render_pdf(), _sample_points(), _summarize() (+8 more)

### Community 47 - "formatter.py"
Cohesion: 0.08
Nodes (17): build_access_denied_home_view(), build_home_tab_view(), _context_line(), create_feedback_block(), _replace(), format_event_summary(), format_plan_block(), format_task_card() (+9 more)

### Community 48 - "AgentClient"
Cohesion: 0.07
Nodes (3): Architect, AgentClient, Developer

### Community 49 - "ArchitectureGraph.tsx"
Cohesion: 0.09
Nodes (28): @dagrejs/dagre, @xyflow/react, HealthStatus, NodeType, AppNodeData, applyDagreLayout(), applyGridLayout(), applyLayout() (+20 more)

### Community 50 - "handlers_integration.py"
Cohesion: 0.08
Nodes (15): _alert_wrapper_retrigger(), _do_retrigger(), _get_jira_reporter(), handle_refresh_gitlab_context(), _is_darwin_reentrant_caller(), jenkins_retrigger_cooldown_key(), _resolve_slack_user(), format_jira_for_llm() (+7 more)

### Community 51 - "TimeKeeperPage.tsx"
Cohesion: 0.12
Nodes (24): createSchedule(), deleteSchedule(), getSchedules(), refineInstructions(), ScheduleCreatePayload, ScheduleItem, toggleSchedule(), updateSchedule() (+16 more)

### Community 52 - "ws-client.js"
Cohesion: 0.10
Nodes (26): clearIdleTimer(), {
  DEFAULT_WORK_DIR, AGENT_CLI, AGENT_MODEL, AGENT_ROLE,
  EVENT_ID, EPHEMERAL, IDLE_TIMEOUT_MS,
  CLI_429_MAX_RETRIES, CLI_429_INITIAL_DELAY_MS, CLI_429_BACKOFF_MULTIPLIER,
  resolveTimeoutMs, parsePositiveInt, MAX_TASK_WALL_MS, MAX_TIMER_MS,
}, { ensureEventDocument }, { executeCLIStreaming, prepareResultsDir, is429Error }, { filterSkillsByRole, filterSkillsByMode, swapActiveRules, restoreAllSkills }, fs, handleCancel(), handleTask() (+18 more)

### Community 53 - "NightwatcherObserver"
Cohesion: 0.10
Nodes (7): ShiftReport, _env_float(), _env_int(), NightwatcherObserver, build_extend_tool(), build_report_tool(), build_summary_tool()

### Community 54 - "useCortexData.ts"
Cohesion: 0.16
Nodes (28): getCognitiveGraph(), getCortexActivity(), getKGServiceDetail(), getKGServices(), getKGStats(), getKnowledgeById(), getMemory(), getRecentPulses() (+20 more)

### Community 55 - "spawn_event_namer_task"
Cohesion: 0.14
Nodes (9): spawn_event_namer_task(), handle_app_home_opened(), handle_app_mention(), handle_approve(), handle_create_event_modal(), handle_darwin_command(), handle_reject(), on_dm_message() (+1 more)

### Community 56 - "time"
Cohesion: 0.11
Nodes (11): _batch_is_terminal_for_flush(), _is_close_phase_fc(), _coerce_turn_int(), handle_inspect_event(), handle_recall_pruned_turns(), _parse_turn_int(), can_transition_to_close(), handle_set_phase() (+3 more)

### Community 58 - "NeuronInfoPanel.tsx"
Cohesion: 0.10
Nodes (27): ActiveEvent, KGServiceEntity, AGENTS, DOMAINS, HEMISPHERE_X, NEURON_DESCRIPTIONS, PHASE_SKILL_FOLDERS, PHASE_TOOL_PRIORITY (+19 more)

### Community 60 - "KnowledgeGraphStore"
Cohesion: 0.15
Nodes (4): _acquire(), KnowledgeGraphStore, _sanitize(), _with_timeout()

### Community 62 - "types.py"
Cohesion: 0.10
Nodes (13): derive_llm_priority(), _get_timeout_env_warned(), _get_timeout_order_warned(), is_partial_control_token(), parse_timeout_env(), _patch_enum_fields(), process_stream_call_syntax_buffer(), resolve_stream_timeouts() (+5 more)

### Community 63 - "NodeInspector.tsx"
Cohesion: 0.13
Nodes (24): getClosedEvents(), ArchitectureEvent, ArgoCDOperation, ArchitectureGraph(), EVENT_LABELS, EventItem(), EventItemProps, healthTone() (+16 more)

### Community 64 - "llm_error_classifier.py"
Cohesion: 0.13
Nodes (9): _extract_status_code(), _has_non_retryable_cause(), _is_google_auth_transport_error(), is_rate_limit(), is_transient(), is_transient_llm_error_turn(), _iter_exception_chain(), _matches_mro() (+1 more)

### Community 65 - "server.js"
Cohesion: 0.09
Nodes (18): { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, ensureEventDocument(), fs, path, stageEventDocument(), fetchEventDocument(), fs, { handleRequest } (+10 more)

### Community 66 - "CortexGraph.tsx"
Cohesion: 0.15
Nodes (24): graphology, eventColor(), getExecutiveNeurons(), getStructuralEdges(), DEFAULT_TYPE_BUDGET, evictLru(), KNOWLEDGE_RING, KNOWLEDGE_RING_TYPES (+16 more)

### Community 68 - "quota_tracker.py"
Cohesion: 0.11
Nodes (5): QuotaExhaustedError, QuotaTracker, RequestExceedsBurstError, Reservation, _stale_reservation_ttl_s()

### Community 70 - "._build_system_prompt"
Cohesion: 0.09
Nodes (3): _init_tool_names(), _strip_tool_names(), _wrap_section()

### Community 73 - "dependencies"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 76 - "nightwatcher_tools.py"
Cohesion: 0.16
Nodes (12): PulseContext, ShiftIncident, ShiftInvestigation, execute_tool(), _handle_consult_deep_memory(), _handle_dispatch_investigation(), _handle_get_event_report(), _handle_post_shift_summary() (+4 more)

### Community 78 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 79 - "claude-guard.js"
Cohesion: 0.14
Nodes (18): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+10 more)

### Community 80 - "FlowHistoryPage.tsx"
Cohesion: 0.21
Nodes (17): recharts, getFlowHistory(), FlowSnapshot, FlowHistoryPage(), RANGES, SparkCard(), SparkCardProps, TokenUsageMini() (+9 more)

### Community 81 - "reconcile.py"
Cohesion: 0.18
Nodes (9): _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers(), main(), _parse_frontmatter() (+1 more)

### Community 82 - "gemini_client.py"
Cohesion: 0.12
Nodes (9): _append_user_turn(), _clone_part_with_sig(), _extract_call_syntax(), _is_function_response_part(), _parse_drain_timeout(), _validated_parts(), sanitize_call_syntax(), scan_call_syntax() (+1 more)

### Community 85 - "PulseBatch"
Cohesion: 0.12
Nodes (4): PulseBatch, PulsePort, PulseObserver, PulseTracker

### Community 86 - "cli-setup.js"
Cohesion: 0.13
Nodes (18): { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync }, filterSkillsByMode() (+10 more)

### Community 87 - "slack.py"
Cohesion: 0.13
Nodes (5): get_user_from_slack(), extract_tables(), get_agent_notification_text(), get_turn_attachment_color(), _PlanDecision

### Community 89 - "StateWatcher"
Cohesion: 0.13
Nodes (3): _QueueEntry, StateWatcher, _Subscription

### Community 91 - "devDependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 92 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 93 - "gemini-sidecar/package.json"
Cohesion: 0.11
Nodes (18): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+10 more)

### Community 94 - "handlers_dispatch.py"
Cohesion: 0.14
Nodes (7): _resolve_escalation_scope(), _sticky_work_style(), CIAnalysis, StagedEscalation, _esc(), _esc_join(), event_to_markdown()

### Community 96 - "get_report"
Cohesion: 0.11
Nodes (6): get_report(), list_reports(), reports_spa_no_slash(), reports_spa_with_slash(), search_reports(), _serve_spa()

### Community 98 - "RedisClient"
Cohesion: 0.14
Nodes (3): skills_version(), get_redis(), RedisClient

### Community 99 - "nightwatcher_prompt.py"
Cohesion: 0.13
Nodes (8): build_manifest_table(), build_report_iteration_prompt(), build_summary_prompt(), build_system_prompt(), extract_event_links(), extract_full_links(), _normalize_gitlab_host(), _handle_extend_incident()

### Community 100 - "ReconcileScheduler"
Cohesion: 0.14
Nodes (3): ReconcileScheduler, QueueTrigger, StalenessGuard

### Community 102 - "ShiftsPage.tsx"
Cohesion: 0.23
Nodes (16): getCurrentShift(), getShiftDetail(), getShiftsList(), ShiftReportFull, ShiftReportSummary, FailedClusterBadge(), getISOWeek(), getWeekDates() (+8 more)

### Community 103 - "nightwatcher.py"
Cohesion: 0.17
Nodes (6): record_token_usage(), _fallback_platform(), _handle_declare_clusters(), reconcile_cluster_plan(), salvage_cluster_plan(), validate_cluster_plan()

### Community 104 - "catalog-skills.js"
Cohesion: 0.16
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 111 - "generate_map.py"
Cohesion: 0.19
Nodes (6): _enumerate_gates(), _GateInfo, generate_phase_tool_map(), _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 112 - "JenkinsPlatformPort"
Cohesion: 0.13
Nodes (4): BuildDetails, JenkinsPlatformPort, JobRunState, ViewScanResult

### Community 116 - "graph_recall.py"
Cohesion: 0.19
Nodes (5): _format_graph_context(), get_graph_context(), _parse_props(), _sanitize(), translate_to_lookups()

### Community 117 - "IncidentAdapterPort"
Cohesion: 0.13
Nodes (3): IdleTimeoutPort, IncidentAdapterPort, StateWatcherPort

### Community 120 - "handlers_planning.py"
Cohesion: 0.23
Nodes (7): _auto_complete_step(), _canonical_role(), handle_create_plan(), handle_get_plan_progress(), _is_failed_turn(), _is_orchestrator_turn(), _normalize_step_id()

### Community 123 - "analyzeTokens"
Cohesion: 0.19
Nodes (13): analyzeString(), analyzeTokens(), assignName(), base(), combineCategories(), configEnvGuard(), configFileWriteGuard(), hasSubseq() (+5 more)

### Community 124 - "._extract_context_flags"
Cohesion: 0.15
Nodes (3): compute_dispatch_backpressure(), ContextFlags, _safe_int_env()

### Community 125 - "get_current_shift"
Cohesion: 0.15
Nodes (3): get_current_shift(), get_shift_detail(), list_shifts()

### Community 131 - "CortexLiveFeed.tsx"
Cohesion: 0.24
Nodes (10): CortexHeartbeat(), CortexHeartbeatProps, ensureKeyframes(), CortexLiveFeed(), FILTER_PILLS, FilterKey, getStoredFilter(), MESSAGE_STYLES (+2 more)

### Community 133 - "is_defer_event_available"
Cohesion: 0.18
Nodes (6): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 135 - "gitGuard"
Cohesion: 0.29
Nodes (10): bareBranchProtected(), configWriteGuard(), externalGitCommand(), gitGuard(), gitQuery(), isProtected(), normRef(), pushGuard() (+2 more)

### Community 136 - "parseShell"
Cohesion: 0.33
Nodes (10): bodySubstitutions(), decodeAnsiC(), isArrayAssignPrefix(), isWordStart(), matchBacktick(), matchParen(), parseShell(), readHeredocStart() (+2 more)

### Community 137 - "generate_event_title"
Cohesion: 0.22
Nodes (3): generate_event_title(), get_adapter(), _get_semaphore()

### Community 141 - "entity_extractor.py"
Cohesion: 0.33
Nodes (5): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship

### Community 142 - "_consider"
Cohesion: 0.20
Nodes (3): _consider(), _is_slash_command_only(), _mention_pattern()

### Community 144 - "has_unevaluated_close_blocker"
Cohesion: 0.22
Nodes (5): has_unevaluated_close_blocker(), _pred_jarvis_response(), _pred_unevaluated_close(), is_jarvis_acknowledgment(), is_stabilization_wake()

### Community 145 - "knowledge_graph_api.py"
Cohesion: 0.31
Nodes (4): get_kg_store(), get_service_detail(), get_stats(), list_services()

### Community 146 - "classifyTool"
Cohesion: 0.31
Nodes (9): apiTokens(), apiWriteNeedsGuard(), branchValues(), classifyTool(), hasOpaqueTarget(), httpGuard(), httpMethod(), isReadMethod() (+1 more)

### Community 147 - "get_quota_tracker"
Cohesion: 0.22
Nodes (3): get_quota_tracker(), llm_stats(), receive_telemetry()

### Community 159 - "LLMStreamInterChunkTimeoutError"
Cohesion: 0.25
Nodes (4): LLMStreamInterChunkTimeoutError, LLMStreamTimeoutError, LLMStreamTotalTimeoutError, LLMStreamTTFBTimeoutError

### Community 163 - "validate-mutations.sh"
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

### Community 177 - "build_gate_context"
Cohesion: 0.33
Nodes (3): build_gate_context(), conversation_has_decayed_turns(), _decay_payload_len()

### Community 182 - "classify"
Cohesion: 0.50
Nodes (4): classify(), main(), shellCategory(), shellNeedsGuard()

## Knowledge Gaps
- **13 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+8 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2403 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **107 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `queue.py`, `BaseModel`, `os`, `logging`, `brain.py`, `ConversationTurn`, `_is_event_closed_or_missing`, `main.py`, `Brain`, `generate_event_title`, `AgentRegistry`, `typing`, `BrainSkillLoader`, `get_event_document`, `EventDocument`, `HeadhunterJira`, `ScheduleCreateRequest`, `ConversationMessage`, `EventEvidence`, `get_all_journal`, `models.py`, `jenkins_observer.py`, `observations_mgmt.py`, `get_notebook`, `NightwatcherObserver`, `time`, `LiveAPIAdapter`, `nightwatcher_tools.py`, `slack.py`, `handlers_dispatch.py`, `get_report`, `FlowSnapshot`, `nightwatcher.py`, `.list_observations`, `ScheduleRepository`, `get_current_shift`?**
  _High betweenness centrality (0.147) - this node is a cross-community bridge._
- **Are the 80 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 80 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.012352576039726879 - nodes in this community are weakly interconnected._
- **Why does `Brain` connect `Brain` to `BlackboardState`, `.start_event_loop`, `brain.py`, `ConversationTurn`, `main.py`, `._resolve_llm_params`, `AgentRegistry`, `._run_agent_task`, `typing`, `BrainSkillLoader`, `._process_with_llm`, `EventDocument`, `EventEvidence`, `models.py`, `._build_contents`, `._close_and_broadcast`, `._build_system_prompt`, `PulseBatch`, `slack.py`, `ReflexSearcher`, `StateWatcher`, `FlowSnapshot`, `ReconcileScheduler`, `JarvisPeerPort`, `IdleTimeoutManager`, `._extract_context_flags`?**
  _High betweenness centrality (0.085) - this node is a cross-community bridge._
- **Are the 20 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Should `queue.py` be split into smaller, more focused modules?**
  _Cohesion score 0.03068450039339103 - nodes in this community are weakly interconnected._