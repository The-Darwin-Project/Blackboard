# Graph Report - Blackboard  (2026-11-16)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 5302 nodes · 11925 edges · 207 communities (107 shown, 100 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 959 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `81f79e01`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BlackboardState
- logging
- EventEvidence
- brain.py
- models.py
- queue.py
- client.ts
- main.py
- Archivist
- Brain
- WorkspaceInspector.tsx
- EventSidebar.tsx
- App.tsx
- ._run_agent_task
- tool_gates.py
- auth.py
- http-handler.js
- colors.ts
- ReconcileScheduler
- api/types.ts
- BrainSkillLoader
- jenkins-mcp.js
- Aligner
- agents/__init__.py
- ToolContext
- ScheduleRepository
- _BrainToolContext
- merge-guard.js
- TurnBubble.tsx
- ._process_with_llm
- JarvisMemoryPage.tsx
- KnowledgeGraphStore
- observations_mgmt.py
- cli-executor.js
- storage-recycler.js
- ephemeral_provisioner.py
- hooks/index.ts
- JenkinsAdapter
- EventRepository
- handlers_integration.py
- llm/__init__.py
- GitHubPlatform
- GeminiAdapter
- EventDrillDown.tsx
- GitLabPlatform
- dispatch_to_agent
- Headhunter
- ws-client.js
- .append_and_broadcast
- TimeKeeperPage.tsx
- ui/package.json
- EphemeralProvisioner
- useCortexData.ts
- CortexGraph.tsx
- ConversationTurn
- types.py
- server.js
- adf_to_markdown
- JarvisPeerPort
- cognitive_graph.py
- ArgoCDObserver
- GridTile.tsx
- ._get_manager
- gemini_client.py
- KargoObserver
- TopologyRepository
- dependencies
- StateWatcher
- LiveAPIAdapter
- nightwatcher_tools.py
- GitHubAppAuth
- compilerOptions
- claude-guard.js
- DashboardWSAdapter
- NightwatcherObserver
- reconcile.py
- create_adapter
- VcsPlatformPort
- cli-setup.js
- FlowHistoryPage.tsx
- ._build_contents
- ReflexSearcher
- devDependencies
- compilerOptions
- nightwatcher.py
- gemini-sidecar/package.json
- ServiceNode.tsx
- get_report
- ArchitectureGraph.tsx
- _sanitize_analysis_text
- ObservationRepository
- ShiftsPage.tsx
- catalog-skills.js
- PulseBatch
- TokenMeter
- EscalationRepository
- nightwatcher_prompt.py
- generate_map.py
- OIDCKeyAdapter
- IdleTimeoutManager
- JenkinsObserver
- tool_router.py
- get
- PulseTracker
- ._connect
- analyzeTokens
- ._extract_context_flags
- QuotaTracker
- MultiInstallationManager
- NeuronInfoPanel.tsx
- ._process_message
- HeadhunterJira
- testSetup.ts
- @tanstack/react-query
- is_defer_event_available
- SlackAccessGate
- PulseBatch
- CiContextCard.tsx
- cortex-constants.ts
- gitGuard
- parseShell
- _is_event_closed_or_missing
- ._post_agent_recall
- entity_extractor.py
- ._process_candidates
- ._triage_and_build_evidence
- ._drain_once
- has_unevaluated_close_blocker
- knowledge_graph_api.py
- classifyTool
- get_quota_tracker
- SmartsheetMaintainerCache
- .has_reeval_signal
- MetricsRepository
- AsyncGitHubClient
- GitLabTokenAuth
- ConversationMessage
- ._run_report_cart
- TimeKeeperObserver
- CortexRepository
- validate-mutations.sh
- ._detect_repetition_collapse
- QuotaExhaustedError
- ._run_analysis_loop
- scripts
- state.js
- build_gate_context
- list_failed_stages
- dex_proxy
- handle_recall_pruned_turns
- submit_feedback
- TicketNode.tsx
- classify
- require-results.sh
- _WSFrameFilter
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

## Communities (207 total, 100 thin omitted)

### Community 0 - "BlackboardState"
Cohesion: 0.01
Nodes (12): get_all_journal(), get_service_journal(), get_notebook(), get_event_observations(), get_global_observations(), get_shift_detail(), list_shifts(), get_mermaid_diagram() (+4 more)

### Community 1 - "logging"
Cohesion: 0.03
Nodes (25): _annotation_replace(), _strip_pipeline_annotations(), _heartbeat(), _sanitize_lesson_text(), _get_static_maintainer_emails(), _get_allowed_mention_authors(), _get_static_maintainer_emails(), _safe_int() (+17 more)

### Community 2 - "EventEvidence"
Cohesion: 0.03
Nodes (34): build_access_denied_home_view(), build_home_tab_view(), _context_line(), create_feedback_block(), extract_tables(), _replace(), format_event_summary(), format_plan_block() (+26 more)

### Community 3 - "brain.py"
Cohesion: 0.03
Nodes (50): _batch_is_terminal_for_flush(), _close_unanswered_fc(), _compute_processed_up_to(), _contents_have_pruned_or_decayed(), _has_non_user_turns(), _is_close_phase_fc(), _is_seed_turn(), _apply_sibling_signature() (+42 more)

### Community 4 - "models.py"
Cohesion: 0.03
Nodes (42): _resolve_escalation_scope(), _resolve_maintainer_enum(), AppNode, ArchitectureEvent, ChatRequest, ChatResponse, CIAnalysis, EventInput (+34 more)

### Community 5 - "queue.py"
Cohesion: 0.03
Nodes (54): get_token_meter(), resolve_approval_identity(), get_archivist(), get_brain(), get_flow_metrics(), report_tampering(), aligner_pending_items(), apply_lessons() (+46 more)

### Community 6 - "client.ts"
Cohesion: 0.04
Nodes (100): lucide-react, react, ApiError, applyLessons(), bulkDeleteObservations(), closeEvent(), correctMemory(), createKnowledge() (+92 more)

### Community 7 - "main.py"
Cohesion: 0.03
Nodes (29): AgentRegistry, agent_websocket_handler(), set_incident_options(), TaskBridge, set_oidc_adapter(), get_aligner(), get_architect(), get_argocd_observer() (+21 more)

### Community 8 - "Archivist"
Cohesion: 0.04
Nodes (4): Archivist, _decode_cursor(), _encode_cursor(), VectorStore

### Community 10 - "WorkspaceInspector.tsx"
Cohesion: 0.05
Nodes (69): createChatEvent(), updateEventTitle(), EventEvidence, TokenUsageDict, ChatInput(), ChatInputProps, Draft, LastSubmission (+61 more)

### Community 11 - "EventSidebar.tsx"
Cohesion: 0.06
Nodes (77): getAlignerPending(), getEventDocument(), getJenkinsPending(), getJiraMissions(), getWaitingApprovalEvents(), HeadhunterTodo, postJiraAction(), AgentRegistryEntry (+69 more)

### Community 12 - "App.tsx"
Cohesion: 0.05
Nodes (63): oidc-client-ts, react-dom, react-router-dom, getConfig(), getIncidents(), getKargoStages(), getWSAuthFailureCallback(), Incident (+55 more)

### Community 13 - "._run_agent_task"
Cohesion: 0.05
Nodes (9): on_huddle(), on_progress(), on_huddle(), on_progress(), _is_automated_nudge(), _sanitize_error_text(), _sanitize_override_reason(), _select_dispatch_tier() (+1 more)

### Community 14 - "tool_gates.py"
Cohesion: 0.05
Nodes (79): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+71 more)

### Community 15 - "auth.py"
Cohesion: 0.04
Nodes (24): can_append_message(), can_approve_event(), can_override_domain(), can_rename_event(), _claims_to_user(), get_user_from_request(), get_user_from_slack(), get_user_from_websocket() (+16 more)

### Community 16 - "http-handler.js"
Cohesion: 0.08
Nodes (62): is429Error(), registerMCPsAndHooks(), resolveCommand(), writeAgyMcpServer(), writeClaudeMcpServer(), parsePositiveInt(), buildArgoCDMcpConfig(), createAppJWT() (+54 more)

### Community 17 - "colors.ts"
Cohesion: 0.06
Nodes (44): @tanstack/react-table, getReport(), getReports(), ReportSearchParams, searchReports(), ReportFull, ReportMeta, ReportSearchResponse (+36 more)

### Community 18 - "ReconcileScheduler"
Cohesion: 0.04
Nodes (7): FlowCollector, FairQueue, ReconcileScheduler, Trigger, QueueTrigger, ResyncTrigger, StalenessGuard

### Community 19 - "api/types.ts"
Cohesion: 0.05
Nodes (57): Agent, AlignerPendingItem, AppNode, AuthUser, BulkDeleteRequest, ChatEventRequest, ChatEventResponse, ConversationTurn (+49 more)

### Community 20 - "BrainSkillLoader"
Cohesion: 0.04
Nodes (5): _parse_positive_int_env(), BrainSkillLoader, _SkillCorpus, _wrap_section(), BrainIntrospectionPort

### Community 21 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 23 - "agents/__init__.py"
Cohesion: 0.06
Nodes (8): Architect, AgentClient, Developer, _check_security(), safe_execution(), wrapper(), SecurityError, SysAdmin

### Community 24 - "ToolContext"
Cohesion: 0.08
Nodes (14): handle_message_agent(), handle_reply_to_agent(), handle_report_incident(), handle_select_agent(), _sticky_work_style(), handle_notify_gitlab_result(), handle_search_open_incidents(), handle_close_event() (+6 more)

### Community 25 - "ScheduleRepository"
Cohesion: 0.05
Nodes (7): ScheduleCreateRequest, ScheduledEvent, delete_schedule(), get_schedule(), toggle_schedule(), update_schedule(), ScheduleRepository

### Community 27 - "merge-guard.js"
Cohesion: 0.04
Nodes (46): API_VALUED, ARGO_MUTATING, ARGO_READ_SUB, ARGO_READ_TOP, BODY_FLAG, BROWSER_READ, CTX, ENV_BUILTINS (+38 more)

### Community 28 - "TurnBubble.tsx"
Cohesion: 0.09
Nodes (35): @uiw/react-markdown-preview, approveEvent(), rejectEvent(), submitFeedback(), CollapsibleSection(), CollapsibleSectionProps, MarkdownViewer(), MermaidBlock() (+27 more)

### Community 29 - "._process_with_llm"
Cohesion: 0.05
Nodes (4): _BatchContext, _ensure_recall_tool_if_needed(), _QuotaShedState, _retry_backoff_delay()

### Community 30 - "JarvisMemoryPage.tsx"
Cohesion: 0.09
Nodes (37): dismissProposals(), EnhancementProposal, getFlowMetrics(), getHandoffReports(), getProposals(), HandoffReport, FlowMetrics, Dashboard() (+29 more)

### Community 31 - "KnowledgeGraphStore"
Cohesion: 0.08
Nodes (9): _format_graph_context(), get_graph_context(), _parse_props(), _sanitize(), translate_to_lookups(), _acquire(), KnowledgeGraphStore, _sanitize() (+1 more)

### Community 32 - "observations_mgmt.py"
Cohesion: 0.07
Nodes (17): _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), render_pdf(), _sample_points(), _summarize() (+9 more)

### Community 33 - "cli-executor.js"
Cohesion: 0.09
Nodes (37): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, MAX_TASK_WALL_MS, MAX_TIMER_MS, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS, STORAGE_PRETASK_TIMEOUT_MS, resolveStorageRoot }, buildCLICommand(), buildTimeoutResult(), { checkAndRecycleStorage, pinTaskCwd, unpinTaskCwd }, CLAUDE_JSON_PATH, cp, createInactivityWatchdog(), executeCLI() (+29 more)

### Community 34 - "storage-recycler.js"
Cohesion: 0.08
Nodes (37): withTaskStorage(), MAX_TASK_WALL_MS, parseTimerMs(), resolveStorageRoot(), resolveTimeoutMs(), ROLE_TIMEOUTS, STORAGE_ACTIVITY_HEARTBEAT_MS, STORAGE_MAX_TIER3_DELETIONS (+29 more)

### Community 35 - "ephemeral_provisioner.py"
Cohesion: 0.07
Nodes (5): KubernetesSpawnHealthAdapter, _PodHealthState, SpawnHealthPort, SpawnPollResult, SpawnStatus

### Community 36 - "hooks/index.ts"
Cohesion: 0.08
Nodes (35): getClosedEvents(), getEvents(), getService(), getTopology(), ArchitectureEvent, ArgoCDOperation, Service, TopologyResponse (+27 more)

### Community 37 - "JenkinsAdapter"
Cohesion: 0.06
Nodes (6): BuildDetails, JenkinsAdapter, JenkinsPlatformPort, JobResult, JobRunState, ViewScanResult

### Community 39 - "handlers_integration.py"
Cohesion: 0.07
Nodes (20): _alert_wrapper_retrigger(), _do_retrigger(), _get_jira_reporter(), handle_ask_release_ai(), handle_comment_jira_issue(), handle_fetch_jira_issue(), handle_greenwave(), handle_notify_user_slack() (+12 more)

### Community 40 - "llm/__init__.py"
Cohesion: 0.08
Nodes (7): ClaudeAdapter, _parse_tpm_limit(), FunctionCall, LLMChunk, LLMPort, LLMResponse, TokenUsage

### Community 42 - "GeminiAdapter"
Cohesion: 0.10
Nodes (6): _attach_signature_to_parts(), _clone_part_with_sig(), _extract_part_signature(), GeminiAdapter, _is_empty_sig_carrier(), _part_has_fc()

### Community 43 - "EventDrillDown.tsx"
Cohesion: 0.10
Nodes (30): three, getEventPulses(), BrainCore(), CortexDevPage(), CortexHeartbeat(), CortexHeartbeatProps, ensureKeyframes(), CortexLiveFeed() (+22 more)

### Community 45 - "dispatch_to_agent"
Cohesion: 0.07
Nodes (9): AgentConnection, _build_prompt(), consume_wake_task(), _consume(), _dispatch_timeout_s(), dispatch_to_agent(), _consume_queue(), _sanitize_stdout() (+1 more)

### Community 46 - "Headhunter"
Cohesion: 0.08
Nodes (3): Headhunter, _raise_if_systemic_failure(), _sanitize_xml_fence()

### Community 47 - "ws-client.js"
Cohesion: 0.10
Nodes (26): clearIdleTimer(), {
  DEFAULT_WORK_DIR, AGENT_CLI, AGENT_MODEL, AGENT_ROLE,
  EVENT_ID, EPHEMERAL, IDLE_TIMEOUT_MS,
  CLI_429_MAX_RETRIES, CLI_429_INITIAL_DELAY_MS, CLI_429_BACKOFF_MULTIPLIER,
  resolveTimeoutMs, parsePositiveInt, MAX_TASK_WALL_MS, MAX_TIMER_MS,
}, { ensureEventDocument }, { executeCLIStreaming, prepareResultsDir, is429Error }, { filterSkillsByRole, filterSkillsByMode, swapActiveRules, restoreAllSkills }, fs, handleCancel(), handleTask() (+18 more)

### Community 48 - ".append_and_broadcast"
Cohesion: 0.17
Nodes (19): handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_refresh_github_context(), handle_refresh_gitlab_context(), handle_refresh_kargo_context(), handle_consult_deep_memory(), handle_lookup_service() (+11 more)

### Community 49 - "TimeKeeperPage.tsx"
Cohesion: 0.13
Nodes (20): createSchedule(), getSchedules(), ScheduleCreatePayload, ScheduleItem, Props, ScheduleForm(), TEMPLATES, formatNextFire() (+12 more)

### Community 50 - "ui/package.json"
Cohesion: 0.08
Nodes (28): autoprefixer, cronstrue, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, graphology-layout-forceatlas2 (+20 more)

### Community 51 - "EphemeralProvisioner"
Cohesion: 0.09
Nodes (3): DispatchMetrics, EphemeralProvisioner, SpawnFailed

### Community 52 - "useCortexData.ts"
Cohesion: 0.17
Nodes (27): getCognitiveGraph(), getCortexActivity(), getEventReport(), getKGServiceDetail(), getKGServices(), getKGStats(), getKnowledgeById(), getMemory() (+19 more)

### Community 53 - "CortexGraph.tsx"
Cohesion: 0.14
Nodes (25): graphology, eventColor(), getExecutiveNeurons(), getStructuralEdges(), DEFAULT_TYPE_BUDGET, evictLru(), KNOWLEDGE_RING, KNOWLEDGE_RING_TYPES (+17 more)

### Community 54 - "ConversationTurn"
Cohesion: 0.11
Nodes (12): emit_tool_result(), _safe_int(), handle_google_web_search(), handle_lookup_journal(), _auto_complete_step(), _canonical_role(), handle_create_plan(), handle_get_plan_progress() (+4 more)

### Community 55 - "types.py"
Cohesion: 0.10
Nodes (13): derive_llm_priority(), _get_timeout_env_warned(), _get_timeout_order_warned(), LLMStreamInterChunkTimeoutError, LLMStreamTimeoutError, LLMStreamTotalTimeoutError, LLMStreamTTFBTimeoutError, parse_timeout_env() (+5 more)

### Community 56 - "server.js"
Cohesion: 0.09
Nodes (18): { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, ensureEventDocument(), fs, path, stageEventDocument(), fetchEventDocument(), fs, { handleRequest } (+10 more)

### Community 57 - "adf_to_markdown"
Cohesion: 0.12
Nodes (10): _adf_to_text(), _escape_jql_string(), JiraIncidentAdapter, adf_to_markdown(), _apply_marks(), _children(), _render(), _render_list() (+2 more)

### Community 58 - "JarvisPeerPort"
Cohesion: 0.08
Nodes (3): BrainLifecyclePort, BroadcastPort, JarvisPeerPort

### Community 59 - "cognitive_graph.py"
Cohesion: 0.11
Nodes (11): get_pulse_tracker(), dismiss_proposals(), DismissRequest, get_all_shadow_interventions(), get_cognitive_graph(), get_cortex_activity(), get_cortex_status(), get_event_shadow_interventions() (+3 more)

### Community 61 - "GridTile.tsx"
Cohesion: 0.14
Nodes (21): AgentStreamCard(), AgentStreamCardProps, MessageCards(), GridTile(), GridTileProps, TileType, InlineMarkdownViewer(), DEFAULT_POS (+13 more)

### Community 63 - "gemini_client.py"
Cohesion: 0.11
Nodes (11): _append_user_turn(), _coerce_part(), _decode_sig_bytes(), _extract_call_syntax(), _is_function_response_part(), _parse_drain_timeout(), _strip_user_thought_signature(), _validated_parts() (+3 more)

### Community 66 - "dependencies"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 67 - "StateWatcher"
Cohesion: 0.11
Nodes (3): _QueueEntry, StateWatcher, _Subscription

### Community 69 - "nightwatcher_tools.py"
Cohesion: 0.17
Nodes (12): ShiftIncident, ShiftInvestigation, execute_tool(), _handle_consult_deep_memory(), _handle_dispatch_investigation(), _handle_extend_incident(), _handle_get_event_report(), _handle_post_shift_summary() (+4 more)

### Community 71 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 72 - "claude-guard.js"
Cohesion: 0.14
Nodes (18): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+10 more)

### Community 74 - "NightwatcherObserver"
Cohesion: 0.14
Nodes (3): ShiftReport, _env_float(), NightwatcherObserver

### Community 75 - "reconcile.py"
Cohesion: 0.18
Nodes (9): _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers(), main(), _parse_frontmatter() (+1 more)

### Community 76 - "create_adapter"
Cohesion: 0.13
Nodes (6): generate_event_title(), get_adapter(), _get_semaphore(), spawn_event_namer_task(), create_adapter(), sanitize_title()

### Community 79 - "cli-setup.js"
Cohesion: 0.13
Nodes (18): { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync }, filterSkillsByMode() (+10 more)

### Community 80 - "FlowHistoryPage.tsx"
Cohesion: 0.22
Nodes (15): recharts, getFlowHistory(), FlowSnapshot, FlowHistoryPage(), RANGES, SparkCard(), SparkCardProps, formatTime() (+7 more)

### Community 83 - "devDependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 84 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 85 - "nightwatcher.py"
Cohesion: 0.15
Nodes (7): record_token_usage(), _env_int(), _fallback_platform(), _handle_declare_clusters(), reconcile_cluster_plan(), salvage_cluster_plan(), validate_cluster_plan()

### Community 86 - "gemini-sidecar/package.json"
Cohesion: 0.11
Nodes (18): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+10 more)

### Community 87 - "ServiceNode.tsx"
Cohesion: 0.15
Nodes (13): @xyflow/react, HealthStatus, NodeType, AppNodeData, ARGOCD_HEALTH_COLORS, SYNC_ICONS, NamespaceGroupNodeData, GENERIC_TAGS (+5 more)

### Community 89 - "get_report"
Cohesion: 0.11
Nodes (6): get_report(), list_reports(), reports_spa_no_slash(), reports_spa_with_slash(), search_reports(), _serve_spa()

### Community 90 - "ArchitectureGraph.tsx"
Cohesion: 0.17
Nodes (16): @dagrejs/dagre, applyDagreLayout(), applyGridLayout(), applyLayout(), ArchitectureGraphInner(), buildGraph(), computeIdHash(), edgeTypes (+8 more)

### Community 91 - "_sanitize_analysis_text"
Cohesion: 0.12
Nodes (9): _clamp_confidence(), _prepare_console_tail(), _redact_match(), _redact_secrets_in_text(), _sanitize_analysis_text(), _sanitize_console_tail(), _strip_newlines(), _validate_analysis() (+1 more)

### Community 93 - "ShiftsPage.tsx"
Cohesion: 0.23
Nodes (16): getCurrentShift(), getShiftDetail(), getShiftsList(), ShiftReportFull, ShiftReportSummary, FailedClusterBadge(), getISOWeek(), getWeekDates() (+8 more)

### Community 94 - "catalog-skills.js"
Cohesion: 0.16
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 95 - "PulseBatch"
Cohesion: 0.14
Nodes (4): Pulse, PulseBatch, PulseContext, PulsePort

### Community 98 - "nightwatcher_prompt.py"
Cohesion: 0.15
Nodes (7): build_manifest_table(), build_report_iteration_prompt(), build_summary_prompt(), build_system_prompt(), extract_event_links(), extract_full_links(), _normalize_gitlab_host()

### Community 99 - "generate_map.py"
Cohesion: 0.19
Nodes (6): _enumerate_gates(), _GateInfo, generate_phase_tool_map(), _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 103 - "tool_router.py"
Cohesion: 0.15
Nodes (3): IdleTimeoutPort, IncidentAdapterPort, StateWatcherPort

### Community 104 - "get"
Cohesion: 0.13
Nodes (8): api_info(), get_config(), get_event_flow(), delta(), get_flow_history(), health_check(), list_agents(), spa_fallback()

### Community 109 - "analyzeTokens"
Cohesion: 0.19
Nodes (13): analyzeString(), analyzeTokens(), assignName(), base(), combineCategories(), configEnvGuard(), configFileWriteGuard(), hasSubseq() (+5 more)

### Community 110 - "._extract_context_flags"
Cohesion: 0.15
Nodes (3): compute_dispatch_backpressure(), ContextFlags, _safe_int_env()

### Community 113 - "NeuronInfoPanel.tsx"
Cohesion: 0.24
Nodes (12): KGServiceDetail, asNumber(), asString(), asStringArray(), Badge(), describeNeuron(), Hdr(), NeuronInfoPanel() (+4 more)

### Community 118 - "testSetup.ts"
Cohesion: 0.18
Nodes (5): @tailwindcss/vite, @testing-library/react, vite, @vitejs/plugin-react, vitest

### Community 119 - "@tanstack/react-query"
Cohesion: 0.31
Nodes (9): @tanstack/react-query, devQueryClient, MOCK_CORTEX_STATUS, MOCK_EVENT_ID, MOCK_NEURONS, MOCK_PULSE_BATCHES, MOCK_SHADOW, MOCK_THINKING (+1 more)

### Community 120 - "is_defer_event_available"
Cohesion: 0.18
Nodes (6): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 122 - "PulseBatch"
Cohesion: 0.25
Nodes (10): ActiveEvent, EventSource, KGServiceEntity, CortexGraphProps, GraphLoaderProps, PulseTimelineProps, Neuron, PulseBatch (+2 more)

### Community 123 - "CiContextCard.tsx"
Cohesion: 0.31
Nodes (9): CiContext, CiContextCardProps, ConsoleTailBlock(), FailedJobRow(), annotationReplacer(), PIPELINE_ANNOTATION_RE, REDACTION_TRIGGER_KEYWORDS, stripAnsi() (+1 more)

### Community 124 - "cortex-constants.ts"
Cohesion: 0.18
Nodes (10): AGENTS, DOMAINS, HEMISPHERE_X, NEURON_DESCRIPTIONS, PHASE_SKILL_FOLDERS, PHASE_TOOL_PRIORITY, PHASES, StructuralEdge (+2 more)

### Community 125 - "gitGuard"
Cohesion: 0.29
Nodes (10): bareBranchProtected(), configWriteGuard(), externalGitCommand(), gitGuard(), gitQuery(), isProtected(), normRef(), pushGuard() (+2 more)

### Community 126 - "parseShell"
Cohesion: 0.33
Nodes (10): bodySubstitutions(), decodeAnsiC(), isArrayAssignPrefix(), isWordStart(), matchBacktick(), matchParen(), parseShell(), readHeredocStart() (+2 more)

### Community 130 - "entity_extractor.py"
Cohesion: 0.33
Nodes (5): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship

### Community 134 - "has_unevaluated_close_blocker"
Cohesion: 0.22
Nodes (5): has_unevaluated_close_blocker(), _pred_jarvis_response(), _pred_unevaluated_close(), is_jarvis_acknowledgment(), is_stabilization_wake()

### Community 135 - "knowledge_graph_api.py"
Cohesion: 0.31
Nodes (4): get_kg_store(), get_service_detail(), get_stats(), list_services()

### Community 136 - "classifyTool"
Cohesion: 0.31
Nodes (9): apiTokens(), apiWriteNeedsGuard(), branchValues(), classifyTool(), hasOpaqueTarget(), httpGuard(), httpMethod(), isReadMethod() (+1 more)

### Community 137 - "get_quota_tracker"
Cohesion: 0.22
Nodes (3): get_quota_tracker(), llm_stats(), receive_telemetry()

### Community 147 - "._run_report_cart"
Cohesion: 0.25
Nodes (3): build_extend_tool(), build_report_tool(), build_summary_tool()

### Community 150 - "validate-mutations.sh"
Cohesion: 0.57
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

### Community 154 - "._run_analysis_loop"
Cohesion: 0.33
Nodes (3): _append_user_turn(), _finalize_analysis_handover(), get_phase_tools()

### Community 155 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 156 - "state.js"
Cohesion: 0.33
Nodes (4): { AGENT_ROLE }, _blackboardTurns, _inboundMessages, _teammateMessages

### Community 163 - "build_gate_context"
Cohesion: 0.33
Nodes (3): build_gate_context(), conversation_has_decayed_turns(), _decay_payload_len()

### Community 168 - "handle_recall_pruned_turns"
Cohesion: 0.50
Nodes (3): _coerce_turn_int(), handle_recall_pruned_turns(), _parse_turn_int()

### Community 171 - "TicketNode.tsx"
Cohesion: 0.40
Nodes (4): STATUS_COLORS, TICKET_COLORS, TicketNodeComponent(), TicketNodeData

### Community 172 - "classify"
Cohesion: 0.50
Nodes (4): classify(), main(), shellCategory(), shellNeedsGuard()

### Community 182 - "overrides"
Cohesion: 0.67
Nodes (3): overrides, @typescript-eslint/typescript-estree, minimatch

## Knowledge Gaps
- **13 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+8 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2329 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **100 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `logging`, `EventEvidence`, `brain.py`, `models.py`, `queue.py`, `main.py`, `Brain`, `auth.py`, `ConversationMessage`, `BrainSkillLoader`, `ScheduleRepository`, `observations_mgmt.py`, `._restage_pending_signal`, `._stage_pending_signal`, `submit_feedback`, `._count_pending`, `.append_and_broadcast`, `._drain_pending`, `ConversationTurn`, `LiveAPIAdapter`, `nightwatcher_tools.py`, `DashboardWSAdapter`, `NightwatcherObserver`, `create_adapter`, `nightwatcher.py`, `get_report`, `tool_router.py`, `HeadhunterJira`, `_is_event_closed_or_missing`?**
  _High betweenness centrality (0.127) - this node is a cross-community bridge._
- **Are the 80 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 80 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.009252450980392157 - nodes in this community are weakly interconnected._
- **Why does `Brain` connect `Brain` to `._resolve_llm_params`, `logging`, `._post_agent_recall`, `brain.py`, `EventEvidence`, `models.py`, `BlackboardState`, `main.py`, `._run_agent_task`, `ReconcileScheduler`, `BrainSkillLoader`, `._detect_repetition_collapse`, `agents/__init__.py`, `._process_with_llm`, `.next_turn_number`, `ConversationTurn`, `JarvisPeerPort`, `StateWatcher`, `DashboardWSAdapter`, `._build_contents`, `ReflexSearcher`, `PulseBatch`, `IdleTimeoutManager`, `._extract_context_flags`?**
  _High betweenness centrality (0.063) - this node is a cross-community bridge._
- **Are the 20 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Should `logging` be split into smaller, more focused modules?**
  _Cohesion score 0.0282765737874097 - nodes in this community are weakly interconnected._