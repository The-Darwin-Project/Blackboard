# Graph Report - Blackboard  (2026-11-15)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 5245 nodes · 11799 edges · 211 communities (110 shown, 101 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 953 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `55cf7b29`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BlackboardState
- client.ts
- EventChatPanel.tsx
- brain.py
- logging
- models.py
- Archivist
- main.py
- os
- Brain
- nightwatcher_tools.py
- tool_gates.py
- ._run_agent_task
- WorkspaceInspector.tsx
- http-handler.js
- EventSidebar.tsx
- colors.ts
- App.tsx
- fetchApi
- jenkins-mcp.js
- ReconcileScheduler
- EventDocument
- BrainSkillLoader
- dispatch.py
- Aligner
- react
- slack.py
- ._process_with_llm
- _BrainToolContext
- auth.py
- merge-guard.js
- observations_mgmt.py
- GeminiAdapter
- cli-executor.js
- storage-recycler.js
- EventRepository
- JenkinsAdapter
- gemini_client.py
- GitHubPlatform
- SlackChannel
- AgentClient
- ToolContext
- GitLabPlatform
- cognitive_graph.py
- Headhunter
- TimeKeeperPage.tsx
- ScheduleRepository
- EventDrillDown.tsx
- ws-client.js
- IdleTimeoutManager
- ClaudeAdapter
- NodeInspector.tsx
- ui/package.json
- queue.py
- StreamGrid.tsx
- useCortexData.ts
- StateWatcher
- spawn_event_namer_task
- state/__init__.py
- KnowledgeGraphStore
- CortexGraph.tsx
- LiveAPIAdapter
- handlers_dispatch.py
- handlers_integration.py
- server.js
- scheduling/__init__.py
- quota_tracker.py
- .append_and_broadcast
- ArgoCDObserver
- create_schedule
- NeuronInfoPanel.tsx
- ._build_contents
- ._get_manager
- get_archivist
- KargoObserver
- TopologyRepository
- dependencies
- GitHubAppAuth
- compilerOptions
- claude-guard.js
- DashboardWSAdapter
- ArchitectureEvent
- reconcile.py
- jira_incident.py
- ArchitectureGraph.tsx
- lucide-react
- FlowHistoryPage.tsx
- VcsPlatformPort
- PulseBatch
- cli-setup.js
- ReflexSearcher
- ConversationTurn
- .get_event
- devDependencies
- compilerOptions
- gemini-sidecar/package.json
- EphemeralProvisioner
- get_report
- ObservationRepository
- catalog-skills.js
- EscalationRepository
- approve_event
- FlowSnapshot
- list_active_events
- generate_map.py
- OIDCKeyAdapter
- KubernetesSpawnHealthAdapter
- JenkinsObserver
- ServiceNode.tsx
- handlers_planning.py
- vcs_approval.py
- SlackAccessGate
- analyzeTokens
- ._extract_context_flags
- TokenMeter
- MultiInstallationManager
- ._authorize_plan_decision
- testSetup.ts
- is_defer_event_available
- CortexDevPage.tsx
- gitGuard
- parseShell
- ._post_agent_recall
- entity_extractor.py
- ._github_poll_and_process
- ._process_candidates
- ._triage_and_build_evidence
- ._drain_once
- has_unevaluated_close_blocker
- IncidentAdapterPort
- knowledge_graph_api.py
- PulseBatch
- spawn_health.py
- classifyTool
- get_quota_tracker
- SpawnPollResult
- SmartsheetMaintainerCache
- .has_reeval_signal
- create_chat_event
- list_shifts
- AsyncGitHubClient
- GitLabTokenAuth
- _is_event_closed_or_missing
- ._evaluate_health
- HeadhunterJira
- nightwatcher_prompt.py
- TimeKeeperObserver
- update_knowledge
- CortexRepository
- adf_to_markdown
- validate-mutations.sh
- ._detect_repetition_collapse
- scripts
- state.js
- ._process_message
- DispatchMetrics
- handlers_verification.py
- _append_user_turn
- build_gate_context
- ._wait_for_registration
- LLMPort
- classify
- require-results.sh
- _env_flag
- get_intermediate_tools
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
- _parse_drain_timeout
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

## Communities (211 total, 101 thin omitted)

### Community 0 - "BlackboardState"
Cohesion: 0.01
Nodes (7): get_all_journal(), get_service_journal(), get_event_observations(), get_global_observations(), aligner_pending_items(), close_event_by_user(), BlackboardState

### Community 1 - "client.ts"
Cohesion: 0.03
Nodes (106): @tanstack/react-query, ApiError, bulkDeleteObservations(), deleteNote(), deleteObservation(), exportObservations(), ExtractionResult, generateObservationsReport() (+98 more)

### Community 2 - "EventChatPanel.tsx"
Cohesion: 0.04
Nodes (93): react-router-dom, closeEvent(), createChatEvent(), enforceCasualDomain(), getActiveEvents(), getAlignerPending(), getEventDocument(), getEventReport() (+85 more)

### Community 3 - "brain.py"
Cohesion: 0.03
Nodes (47): _contents_have_pruned_or_decayed(), _apply_sibling_signature(), build_function_response(), build_single_function_response(), compress_contents(), contents_have_pruned_or_decayed(), estimate_msg_tokens(), estimate_tokens() (+39 more)

### Community 4 - "logging"
Cohesion: 0.03
Nodes (21): _annotation_replace(), _strip_pipeline_annotations(), _sanitize_lesson_text(), _format_graph_context(), get_graph_context(), _parse_props(), _sanitize(), translate_to_lookups() (+13 more)

### Community 5 - "models.py"
Cohesion: 0.03
Nodes (34): AppNode, ChatRequest, ChatResponse, ConversationMessage, EventInput, EventMetrics, EventStatus, EventType (+26 more)

### Community 6 - "Archivist"
Cohesion: 0.04
Nodes (4): Archivist, _decode_cursor(), _encode_cursor(), VectorStore

### Community 7 - "main.py"
Cohesion: 0.03
Nodes (34): AgentConnection, AgentRegistry, set_incident_options(), set_oidc_adapter(), get_aligner(), get_architect(), get_argocd_observer(), get_developer() (+26 more)

### Community 8 - "os"
Cohesion: 0.04
Nodes (19): _get_static_maintainer_emails(), _get_allowed_mention_authors(), _get_static_maintainer_emails(), _safe_int(), create_adapter(), record_token_usage(), get_blackboard(), dex_proxy() (+11 more)

### Community 10 - "nightwatcher_tools.py"
Cohesion: 0.04
Nodes (31): ShiftIncident, ShiftInvestigation, ShiftReport, _append_user_turn(), _env_float(), _env_int(), NightwatcherObserver, _finalize_analysis_handover() (+23 more)

### Community 11 - "tool_gates.py"
Cohesion: 0.05
Nodes (77): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+69 more)

### Community 12 - "._run_agent_task"
Cohesion: 0.05
Nodes (13): on_huddle(), on_progress(), on_huddle(), on_progress(), _compute_processed_up_to(), _has_non_user_turns(), _is_automated_nudge(), _is_seed_turn() (+5 more)

### Community 13 - "WorkspaceInspector.tsx"
Cohesion: 0.06
Nodes (57): CiContext, ConversationTurn, TokenUsageDict, CiContextCard(), CiContextCardProps, ConsoleTailBlock(), FailedJobRow(), DeferCountdownBar() (+49 more)

### Community 14 - "http-handler.js"
Cohesion: 0.08
Nodes (62): is429Error(), registerMCPsAndHooks(), resolveCommand(), writeAgyMcpServer(), writeClaudeMcpServer(), parsePositiveInt(), buildArgoCDMcpConfig(), createAppJWT() (+54 more)

### Community 15 - "EventSidebar.tsx"
Cohesion: 0.07
Nodes (60): getHeadhunterPending(), getJiraMissions(), HeadhunterTodo, postJiraAction(), AgentRegistryEntry, ACTION_BADGE, formatAge(), HeadhunterQueuePanel() (+52 more)

### Community 16 - "colors.ts"
Cohesion: 0.07
Nodes (41): @tanstack/react-table, getReport(), getReports(), ReportFull, ReportMeta, CompactCardStrip(), EventHistory(), TimeRange (+33 more)

### Community 17 - "App.tsx"
Cohesion: 0.06
Nodes (50): oidc-client-ts, react-dom, dismissProposals(), EnhancementProposal, getConfig(), getHandoffReports(), getProposals(), getWSAuthFailureCallback() (+42 more)

### Community 18 - "fetchApi"
Cohesion: 0.07
Nodes (55): applyLessons(), correctMemory(), createKnowledge(), createLesson(), deleteKnowledge(), deleteLesson(), ExtractedCorrection, ExtractedLesson (+47 more)

### Community 19 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 20 - "ReconcileScheduler"
Cohesion: 0.05
Nodes (6): FairQueue, ReconcileScheduler, Trigger, QueueTrigger, ResyncTrigger, StalenessGuard

### Community 22 - "BrainSkillLoader"
Cohesion: 0.05
Nodes (4): BrainSkillLoader, _SkillCorpus, _wrap_section(), BrainIntrospectionPort

### Community 23 - "dispatch.py"
Cohesion: 0.06
Nodes (15): agent_websocket_handler(), _heartbeat(), _build_prompt(), _check_security(), consume_wake_task(), _consume(), _dispatch_timeout_s(), dispatch_to_agent() (+7 more)

### Community 25 - "react"
Cohesion: 0.09
Nodes (38): react, @uiw/react-markdown-preview, approveEvent(), getAgents(), rejectEvent(), submitFeedback(), AgentRegistryPanel(), formatConnectedSince() (+30 more)

### Community 26 - "slack.py"
Cohesion: 0.06
Nodes (21): resolve_approval_identity(), build_access_denied_home_view(), build_home_tab_view(), _context_line(), create_feedback_block(), extract_tables(), _replace(), format_plan_block() (+13 more)

### Community 27 - "._process_with_llm"
Cohesion: 0.04
Nodes (4): _BatchContext, _ensure_recall_tool_if_needed(), _QuotaShedState, _retry_backoff_delay()

### Community 29 - "auth.py"
Cohesion: 0.06
Nodes (16): can_approve_event(), can_override_domain(), can_rename_event(), _claims_to_user(), get_user_from_request(), get_user_from_slack(), get_user_from_websocket(), _normalize_email() (+8 more)

### Community 30 - "merge-guard.js"
Cohesion: 0.04
Nodes (46): API_VALUED, ARGO_MUTATING, ARGO_READ_SUB, ARGO_READ_TOP, BODY_FLAG, BROWSER_READ, CTX, ENV_BUILTINS (+38 more)

### Community 31 - "observations_mgmt.py"
Cohesion: 0.07
Nodes (17): _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), render_pdf(), _sample_points(), _summarize() (+9 more)

### Community 32 - "GeminiAdapter"
Cohesion: 0.09
Nodes (9): _attach_signature_to_parts(), _clone_part_with_sig(), _coerce_part(), _decode_sig_bytes(), _extract_part_signature(), GeminiAdapter, _is_empty_sig_carrier(), _part_has_fc() (+1 more)

### Community 33 - "cli-executor.js"
Cohesion: 0.09
Nodes (37): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, MAX_TASK_WALL_MS, MAX_TIMER_MS, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS, STORAGE_PRETASK_TIMEOUT_MS, resolveStorageRoot }, buildCLICommand(), buildTimeoutResult(), { checkAndRecycleStorage, pinTaskCwd, unpinTaskCwd }, CLAUDE_JSON_PATH, cp, createInactivityWatchdog(), executeCLI() (+29 more)

### Community 34 - "storage-recycler.js"
Cohesion: 0.08
Nodes (37): withTaskStorage(), MAX_TASK_WALL_MS, parseTimerMs(), resolveStorageRoot(), resolveTimeoutMs(), ROLE_TIMEOUTS, STORAGE_ACTIVITY_HEARTBEAT_MS, STORAGE_MAX_TIER3_DELETIONS (+29 more)

### Community 36 - "JenkinsAdapter"
Cohesion: 0.06
Nodes (6): BuildDetails, JenkinsAdapter, JenkinsPlatformPort, JobResult, JobRunState, ViewScanResult

### Community 37 - "gemini_client.py"
Cohesion: 0.09
Nodes (17): _extract_call_syntax(), _parse_tpm_limit(), derive_llm_priority(), _get_timeout_env_warned(), _get_timeout_order_warned(), LLMStreamInterChunkTimeoutError, LLMStreamTimeoutError, LLMStreamTotalTimeoutError (+9 more)

### Community 40 - "AgentClient"
Cohesion: 0.07
Nodes (4): Architect, AgentClient, Developer, SysAdmin

### Community 41 - "ToolContext"
Cohesion: 0.10
Nodes (9): handle_classify_event(), handle_defer_event(), handle_hold_watch(), handle_request_user_approval(), handle_wait_for_agent(), handle_wait_for_jarvis(), handle_wait_for_user(), ToolContext (+1 more)

### Community 43 - "cognitive_graph.py"
Cohesion: 0.08
Nodes (14): get_brain(), get_pulse_tracker(), dismiss_proposals(), DismissRequest, get_all_shadow_interventions(), get_cognitive_graph(), get_cortex_activity(), get_cortex_status() (+6 more)

### Community 45 - "TimeKeeperPage.tsx"
Cohesion: 0.12
Nodes (24): createSchedule(), deleteSchedule(), getSchedules(), refineInstructions(), ScheduleCreatePayload, ScheduleItem, toggleSchedule(), updateSchedule() (+16 more)

### Community 46 - "ScheduleRepository"
Cohesion: 0.08
Nodes (4): ScheduleCreateRequest, ScheduledEvent, update_schedule(), ScheduleRepository

### Community 47 - "EventDrillDown.tsx"
Cohesion: 0.11
Nodes (27): three, getEventPulses(), BrainCore(), CortexHeartbeat(), CortexHeartbeatProps, ensureKeyframes(), CortexLiveFeed(), CortexLiveFeedProps (+19 more)

### Community 48 - "ws-client.js"
Cohesion: 0.10
Nodes (26): clearIdleTimer(), {
  DEFAULT_WORK_DIR, AGENT_CLI, AGENT_MODEL, AGENT_ROLE,
  EVENT_ID, EPHEMERAL, IDLE_TIMEOUT_MS,
  CLI_429_MAX_RETRIES, CLI_429_INITIAL_DELAY_MS, CLI_429_BACKOFF_MULTIPLIER,
  resolveTimeoutMs, parsePositiveInt, MAX_TASK_WALL_MS, MAX_TIMER_MS,
}, { ensureEventDocument }, { executeCLIStreaming, prepareResultsDir, is429Error }, { filterSkillsByRole, filterSkillsByMode, swapActiveRules, restoreAllSkills }, fs, handleCancel(), handleTask() (+18 more)

### Community 49 - "IdleTimeoutManager"
Cohesion: 0.07
Nodes (4): _parse_positive_int_env(), BrainLifecyclePort, BroadcastPort, IdleTimeoutManager

### Community 50 - "ClaudeAdapter"
Cohesion: 0.10
Nodes (5): ClaudeAdapter, FunctionCall, LLMChunk, LLMResponse, TokenUsage

### Community 51 - "NodeInspector.tsx"
Cohesion: 0.11
Nodes (26): getClosedEvents(), getEvents(), ArchitectureEvent, ArgoCDOperation, ActivityStream(), ArchitectureGraph(), EVENT_LABELS, EventItem() (+18 more)

### Community 52 - "ui/package.json"
Cohesion: 0.08
Nodes (28): autoprefixer, cronstrue, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, graphology-layout-forceatlas2 (+20 more)

### Community 53 - "queue.py"
Cohesion: 0.11
Nodes (16): apply_lessons(), CloseRequest, correct_memory(), CorrectMemoryRequest, create_knowledge(), create_lesson(), enforce_casual_domain(), EnforceCasualRequest (+8 more)

### Community 54 - "StreamGrid.tsx"
Cohesion: 0.14
Nodes (24): Dashboard(), GridTile(), GridTileProps, TileType, InlineMarkdownViewer(), EmptyState(), LayoutMode, StreamGrid() (+16 more)

### Community 55 - "useCortexData.ts"
Cohesion: 0.17
Nodes (26): getCognitiveGraph(), getCortexActivity(), getKGServiceDetail(), getKGServices(), getKGStats(), getRecentPulses(), CortexPage(), isOffRingCollection() (+18 more)

### Community 56 - "StateWatcher"
Cohesion: 0.09
Nodes (3): _QueueEntry, StateWatcher, _Subscription

### Community 57 - "spawn_event_namer_task"
Cohesion: 0.14
Nodes (9): spawn_event_namer_task(), format_event_summary(), handle_app_home_opened(), handle_app_mention(), handle_create_event_modal(), handle_darwin_command(), handle_home_create_event(), on_dm_message() (+1 more)

### Community 58 - "state/__init__.py"
Cohesion: 0.10
Nodes (5): skills_version(), sanitize_redis_port(), close_redis(), get_redis(), RedisClient

### Community 59 - "KnowledgeGraphStore"
Cohesion: 0.15
Nodes (4): _acquire(), KnowledgeGraphStore, _sanitize(), _with_timeout()

### Community 60 - "CortexGraph.tsx"
Cohesion: 0.14
Nodes (25): graphology, eventColor(), getExecutiveNeurons(), getStructuralEdges(), DEFAULT_TYPE_BUDGET, evictLru(), KNOWLEDGE_RING, KNOWLEDGE_RING_TYPES (+17 more)

### Community 62 - "handlers_dispatch.py"
Cohesion: 0.11
Nodes (8): handle_message_agent(), handle_reply_to_agent(), handle_report_incident(), handle_select_agent(), _resolve_escalation_scope(), _sticky_work_style(), handle_search_open_incidents(), handle_respond_to_jarvis()

### Community 63 - "handlers_integration.py"
Cohesion: 0.09
Nodes (14): _alert_wrapper_retrigger(), _get_jira_reporter(), handle_comment_jira_issue(), handle_fetch_jira_issue(), handle_greenwave(), handle_notify_user_slack(), handle_retrigger_jenkins_build(), handle_transition_jira_issue() (+6 more)

### Community 64 - "server.js"
Cohesion: 0.09
Nodes (18): { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, ensureEventDocument(), fs, path, stageEventDocument(), fetchEventDocument(), fs, { handleRequest } (+10 more)

### Community 65 - "scheduling/__init__.py"
Cohesion: 0.13
Nodes (12): _do_retrigger(), handle_refresh_github_context(), handle_refresh_gitlab_context(), handle_refresh_kargo_context(), handle_re_trigger_aligner(), StateWatcherPort, GitHubPrRef, GitLabMrRef (+4 more)

### Community 66 - "quota_tracker.py"
Cohesion: 0.11
Nodes (5): QuotaExhaustedError, QuotaTracker, RequestExceedsBurstError, Reservation, _stale_reservation_ttl_s()

### Community 67 - ".append_and_broadcast"
Cohesion: 0.18
Nodes (15): _coerce_turn_int(), handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_recall_pruned_turns(), _parse_turn_int(), _sanitize_recalled(), handle_ask_release_ai() (+7 more)

### Community 69 - "create_schedule"
Cohesion: 0.08
Nodes (5): create_schedule(), delete_schedule(), get_schedule(), list_schedules(), toggle_schedule()

### Community 70 - "NeuronInfoPanel.tsx"
Cohesion: 0.11
Nodes (23): KGServiceDetail, AGENTS, DOMAINS, HEMISPHERE_X, NEURON_DESCRIPTIONS, PHASE_SKILL_FOLDERS, PHASE_TOOL_PRIORITY, PHASES (+15 more)

### Community 73 - "get_archivist"
Cohesion: 0.11
Nodes (11): get_archivist(), delete_knowledge(), delete_lesson(), get_event_turns(), get_knowledge(), get_lesson(), get_memory(), jenkins_pending_items() (+3 more)

### Community 76 - "dependencies"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 78 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 79 - "claude-guard.js"
Cohesion: 0.14
Nodes (18): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+10 more)

### Community 81 - "ArchitectureEvent"
Cohesion: 0.11
Nodes (4): ArchitectureEvent, get_event_document(), list_events(), MetricsRepository

### Community 82 - "reconcile.py"
Cohesion: 0.18
Nodes (9): _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers(), main(), _parse_frontmatter() (+1 more)

### Community 83 - "jira_incident.py"
Cohesion: 0.13
Nodes (3): _adf_to_text(), _escape_jql_string(), JiraIncidentAdapter

### Community 84 - "ArchitectureGraph.tsx"
Cohesion: 0.14
Nodes (17): @dagrejs/dagre, @xyflow/react, applyDagreLayout(), applyGridLayout(), applyLayout(), ArchitectureGraphInner(), buildGraph(), computeIdHash() (+9 more)

### Community 85 - "lucide-react"
Cohesion: 0.17
Nodes (17): lucide-react, AgentStreamCard(), AgentStreamCardProps, MessageCards(), CopyButtonProps, DEFAULT_POS, DEFAULT_SIZE, EMPTY_MESSAGES (+9 more)

### Community 86 - "FlowHistoryPage.tsx"
Cohesion: 0.23
Nodes (16): recharts, getFlowHistory(), FlowSnapshot, FlowHistoryPage(), RANGES, SparkCard(), SparkCardProps, formatTime() (+8 more)

### Community 89 - "PulseBatch"
Cohesion: 0.12
Nodes (4): PulseBatch, PulsePort, PulseObserver, PulseTracker

### Community 90 - "cli-setup.js"
Cohesion: 0.13
Nodes (18): { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync }, filterSkillsByMode() (+10 more)

### Community 92 - "ConversationTurn"
Cohesion: 0.17
Nodes (9): emit_tool_result(), _safe_int(), _format_bounded_journal(), handle_consult_deep_memory(), handle_google_web_search(), handle_lookup_journal(), handle_lookup_service(), PulseContext (+1 more)

### Community 93 - ".get_event"
Cohesion: 0.10
Nodes (7): report_tampering(), FeedbackRequest, submit_feedback(), get_event_approval(), get_event_document(), get_event_report(), rebuild_deep_memory()

### Community 94 - "devDependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 95 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 96 - "gemini-sidecar/package.json"
Cohesion: 0.11
Nodes (18): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+10 more)

### Community 98 - "get_report"
Cohesion: 0.11
Nodes (6): get_report(), list_reports(), reports_spa_no_slash(), reports_spa_with_slash(), search_reports(), _serve_spa()

### Community 101 - "catalog-skills.js"
Cohesion: 0.16
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 103 - "approve_event"
Cohesion: 0.16
Nodes (4): approve_event(), reject_event(), TitleUpdateRequest, update_event_title()

### Community 105 - "list_active_events"
Cohesion: 0.12
Nodes (6): _defer_timeline_fields(), _has_active_subscription(), list_active_events(), list_closed_events(), list_waiting_approval_events(), _serialize_evidence()

### Community 106 - "generate_map.py"
Cohesion: 0.19
Nodes (6): _enumerate_gates(), _GateInfo, generate_phase_tool_map(), _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 111 - "ServiceNode.tsx"
Cohesion: 0.20
Nodes (11): HealthStatus, NodeType, AppNodeData, ARGOCD_HEALTH_COLORS, SYNC_ICONS, GENERIC_TAGS, HEALTH_COLORS, NODE_ICONS (+3 more)

### Community 112 - "handlers_planning.py"
Cohesion: 0.23
Nodes (7): _auto_complete_step(), _canonical_role(), handle_create_plan(), handle_get_plan_progress(), _is_failed_turn(), _is_orchestrator_turn(), _normalize_step_id()

### Community 114 - "vcs_approval.py"
Cohesion: 0.19
Nodes (7): _github_active_item(), headhunter_pending_todos(), get_gitlab_auth(), _resolve_github_head(), _resolve_gitlab_head(), resolve_live_head_sha(), verify_merge_guard()

### Community 116 - "analyzeTokens"
Cohesion: 0.19
Nodes (13): analyzeString(), analyzeTokens(), assignName(), base(), combineCategories(), configEnvGuard(), configFileWriteGuard(), hasSubseq() (+5 more)

### Community 117 - "._extract_context_flags"
Cohesion: 0.15
Nodes (3): compute_dispatch_backpressure(), ContextFlags, _safe_int_env()

### Community 123 - "._authorize_plan_decision"
Cohesion: 0.18
Nodes (3): _PlanDecision, handle_approve(), handle_reject()

### Community 124 - "testSetup.ts"
Cohesion: 0.18
Nodes (5): @tailwindcss/vite, @testing-library/react, vite, @vitejs/plugin-react, vitest

### Community 125 - "is_defer_event_available"
Cohesion: 0.18
Nodes (6): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 126 - "CortexDevPage.tsx"
Cohesion: 0.31
Nodes (9): CortexDevPage(), devQueryClient, MOCK_CORTEX_STATUS, MOCK_EVENT_ID, MOCK_NEURONS, MOCK_PULSE_BATCHES, MOCK_SHADOW, MOCK_THINKING (+1 more)

### Community 127 - "gitGuard"
Cohesion: 0.29
Nodes (10): bareBranchProtected(), configWriteGuard(), externalGitCommand(), gitGuard(), gitQuery(), isProtected(), normRef(), pushGuard() (+2 more)

### Community 128 - "parseShell"
Cohesion: 0.33
Nodes (10): bodySubstitutions(), decodeAnsiC(), isArrayAssignPrefix(), isWordStart(), matchBacktick(), matchParen(), parseShell(), readHeredocStart() (+2 more)

### Community 131 - "entity_extractor.py"
Cohesion: 0.33
Nodes (5): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship

### Community 136 - "has_unevaluated_close_blocker"
Cohesion: 0.20
Nodes (4): has_unevaluated_close_blocker(), _pred_jarvis_response(), _pred_unevaluated_close(), is_jarvis_acknowledgment()

### Community 138 - "knowledge_graph_api.py"
Cohesion: 0.31
Nodes (4): get_kg_store(), get_service_detail(), get_stats(), list_services()

### Community 139 - "PulseBatch"
Cohesion: 0.27
Nodes (9): ActiveEvent, EventSource, KGServiceEntity, CortexGraphProps, GraphLoaderProps, PulseTimelineProps, PulseBatch, WorkspaceTaskItemProps (+1 more)

### Community 141 - "classifyTool"
Cohesion: 0.31
Nodes (9): apiTokens(), apiWriteNeedsGuard(), branchValues(), classifyTool(), hasOpaqueTarget(), httpGuard(), httpMethod(), isReadMethod() (+1 more)

### Community 142 - "get_quota_tracker"
Cohesion: 0.22
Nodes (3): get_quota_tracker(), llm_stats(), receive_telemetry()

### Community 146 - "create_chat_event"
Cohesion: 0.25
Nodes (3): ChatEventRequest, ChatEventResponse, create_chat_event()

### Community 154 - "nightwatcher_prompt.py"
Cohesion: 0.32
Nodes (3): build_manifest_table(), build_system_prompt(), extract_event_links()

### Community 156 - "update_knowledge"
Cohesion: 0.25
Nodes (4): demote_lesson(), KnowledgeUpdateRequest, update_knowledge(), verify_lesson()

### Community 158 - "adf_to_markdown"
Cohesion: 0.57
Nodes (7): adf_to_markdown(), _apply_marks(), _children(), _render(), _render_list(), _render_list_item(), _render_table_like()

### Community 159 - "validate-mutations.sh"
Cohesion: 0.57
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

### Community 161 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 162 - "state.js"
Cohesion: 0.33
Nodes (4): { AGENT_ROLE }, _blackboardTurns, _inboundMessages, _teammateMessages

### Community 173 - "_append_user_turn"
Cohesion: 0.33
Nodes (3): _append_user_turn(), _is_function_response_part(), _validated_parts()

### Community 174 - "build_gate_context"
Cohesion: 0.33
Nodes (3): build_gate_context(), conversation_has_decayed_turns(), _decay_payload_len()

### Community 177 - "classify"
Cohesion: 0.50
Nodes (4): classify(), main(), shellCategory(), shellNeedsGuard()

### Community 184 - "overrides"
Cohesion: 0.67
Nodes (3): overrides, @typescript-eslint/typescript-estree, minimatch

## Knowledge Gaps
- **13 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+8 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2302 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **101 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `brain.py`, `logging`, `models.py`, `main.py`, `os`, `Brain`, `nightwatcher_tools.py`, `create_chat_event`, `list_shifts`, `EventDocument`, `_is_event_closed_or_missing`, `dispatch.py`, `HeadhunterJira`, `slack.py`, `auth.py`, `observations_mgmt.py`, `ScheduleRepository`, `IdleTimeoutManager`, `queue.py`, `state/__init__.py`, `LiveAPIAdapter`, `.append_and_broadcast`, `create_schedule`, `get_archivist`, `DashboardWSAdapter`, `ArchitectureEvent`, `ConversationTurn`, `.get_event`, `get_report`, `approve_event`, `FlowSnapshot`, `list_active_events`?**
  _High betweenness centrality (0.104) - this node is a cross-community bridge._
- **Are the 80 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 80 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.011776051977057002 - nodes in this community are weakly interconnected._
- **Why does `Brain` connect `Brain` to `BlackboardState`, `._resolve_llm_params`, `._post_agent_recall`, `brain.py`, `logging`, `models.py`, `main.py`, `._run_agent_task`, `ReconcileScheduler`, `EventDocument`, `BrainSkillLoader`, `dispatch.py`, `slack.py`, `._process_with_llm`, `._detect_repetition_collapse`, `IdleTimeoutManager`, `StateWatcher`, `._build_contents`, `DashboardWSAdapter`, `PulseBatch`, `ReflexSearcher`, `ConversationTurn`, `FlowSnapshot`, `._extract_context_flags`?**
  _High betweenness centrality (0.064) - this node is a cross-community bridge._
- **Are the 19 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 19 INFERRED edges - model-reasoned connections that need verification._
- **Should `client.ts` be split into smaller, more focused modules?**
  _Cohesion score 0.030838709677419356 - nodes in this community are weakly interconnected._