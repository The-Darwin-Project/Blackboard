# Graph Report - Blackboard  (2026-11-19)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 5340 nodes · 12035 edges · 223 communities (111 shown, 112 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 962 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `a44f069e`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BlackboardState
- EventSidebar.tsx
- ConversationTurn
- client.ts
- queue.py
- logging
- models.py
- api/types.ts
- dependencies.py
- WorkspaceInspector.tsx
- tool_gates.py
- Brain
- ._run_agent_task
- App.tsx
- TopologyRepository
- Archivist
- http-handler.js
- os
- nightwatcher_tools.py
- jenkins-mcp.js
- auth.py
- ScheduleRepository
- EventDocument
- react
- AgentRegistry
- ._process_with_llm
- BrainSkillLoader
- brain.py
- _BrainToolContext
- useOpsControl
- GitHubPlatform
- merge-guard.js
- GeminiAdapter
- gemini_client.py
- cli-executor.js
- storage-recycler.js
- slack.py
- EventRepository
- agents/__init__.py
- llm/__init__.py
- OpsStateContext.tsx
- Headhunter
- Aligner
- main.py
- lifespan
- LiveAPIAdapter
- BrainIntrospectionPort
- ws-client.js
- ui/package.json
- CortexGraph.tsx
- GitLabPlatform
- TimeKeeperPage.tsx
- SlackChannel
- JenkinsObserver
- EventDrillDown.tsx
- NightwatcherObserver
- KnowledgeGraphStore
- PlanProgress.tsx
- observations_mgmt.py
- server.js
- .create_platform_event
- .list_observations
- JenkinsAdapter
- PulseBatch
- ArgoCDObserver
- reconcile.py
- ._build_contents
- KargoObserver
- dependencies
- StateWatcher
- FlowHistoryPage.tsx
- compilerOptions
- claude-guard.js
- ArchitectureGraph.tsx
- GitHubAppAuth
- .scroll
- VcsPlatformPort
- jenkins_observer.py
- useCortexData.ts
- context_parts.py
- cli-setup.js
- observations_reporter.py
- QuotaTracker
- event_namer.py
- ReflexSearcher
- prompt.py
- FairQueue
- devDependencies
- compilerOptions
- gemini-sidecar/package.json
- handlers_lookup.py
- EphemeralProvisioner
- get_report
- ._process_candidates
- ObservationRepository
- ShiftsPage.tsx
- catalog-skills.js
- TokenMeter
- OIDCKeyAdapter
- spawn_event_namer_task
- EscalationRepository
- JiraIncidentAdapter
- VectorStore
- generate_map.py
- jira_incident.py
- JenkinsPlatformPort
- KubernetesSpawnHealthAdapter
- IdleTimeoutManager
- graph_recall.py
- RedisClient
- ServiceNode.tsx
- SlackAccessGate
- MultiInstallationManager
- NeuronInfoPanel.tsx
- analyzeTokens
- scheduling/__init__.py
- ._poll_and_stage
- FilterRule
- ._extract_context_flags
- IncidentAdapterPort
- ReconcileScheduler
- ._process_message
- compress_contents
- ._triage_and_build_evidence
- ._authorize_plan_decision
- cortex/types.ts
- CortexLiveFeed.tsx
- testSetup.ts
- .start_event_loop
- is_defer_event_available
- cortex-constants.ts
- SecurityError
- gitGuard
- parseShell
- SpawnPollResult
- ._post_agent_recall
- FlowCollector
- entity_extractor.py
- has_unevaluated_close_blocker
- ._send_turn_to_thread
- ._gate_check
- knowledge_graph_api.py
- classifyTool
- strip_xml_fences
- _resolve_domain
- .has_reeval_signal
- get_current_shift
- Trigger
- AsyncGitHubClient
- GitLabTokenAuth
- _is_event_closed_or_missing
- ._evaluate_health
- HeadhunterJira
- TimeKeeperObserver
- CortexRepository
- validate-mutations.sh
- ._detect_repetition_collapse
- QuotaExhaustedError
- update_notebook_note
- scripts
- state.js
- _append_user_turn
- build_gate_context
- ._register_handlers
- build_manifest_table
- DispatchMetrics
- ._wait_for_registration
- get_notebook
- StalenessGuard
- classify
- _coerce_part
- _patch_enum_fields
- list_incidents
- require-results.sh
- TokenUsageDict
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
1. `BlackboardState` - 288 edges
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

## Communities (223 total, 112 thin omitted)

### Community 1 - "EventSidebar.tsx"
Cohesion: 0.04
Nodes (100): getJiraMissions(), getReport(), getReports(), HeadhunterTodo, postJiraAction(), ReportFull, ReportMeta, DeferCountdownBar() (+92 more)

### Community 2 - "ConversationTurn"
Cohesion: 0.05
Nodes (49): emit_tool_result(), handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_message_agent(), handle_reply_to_agent(), handle_report_incident(), handle_select_agent() (+41 more)

### Community 3 - "client.ts"
Cohesion: 0.04
Nodes (102): ApiError, applyLessons(), approveEvent(), bulkDeleteObservations(), correctMemory(), createKnowledge(), createLesson(), createSchedule() (+94 more)

### Community 4 - "queue.py"
Cohesion: 0.03
Nodes (51): get_token_meter(), can_rename_event(), resolve_approval_identity(), get_archivist(), report_tampering(), aligner_pending_items(), apply_lessons(), approve_event() (+43 more)

### Community 5 - "logging"
Cohesion: 0.04
Nodes (6): _annotation_replace(), _strip_pipeline_annotations(), _heartbeat(), _load_name_mapping(), SpawnStatus, list_shifts()

### Community 6 - "models.py"
Cohesion: 0.03
Nodes (37): AppNode, ArchitectureEvent, ChatRequest, ChatResponse, CIAnalysis, ConversationMessage, EventEvidence, EventInput (+29 more)

### Community 7 - "api/types.ts"
Cohesion: 0.03
Nodes (86): @tanstack/react-query, getClosedEvents(), getConfig(), getEvents(), getFlowMetrics(), getGraphData(), getService(), getTopology() (+78 more)

### Community 8 - "dependencies.py"
Cohesion: 0.04
Nodes (28): get_aligner(), get_architect(), get_argocd_observer(), get_blackboard(), get_brain(), get_developer(), get_kargo_observer(), get_pulse_tracker() (+20 more)

### Community 9 - "WorkspaceInspector.tsx"
Cohesion: 0.05
Nodes (71): lucide-react, createChatEvent(), updateEventTitle(), AgentRegistryEntry, CiContext, TokenUsageDict, ChatInput(), ChatInputProps (+63 more)

### Community 10 - "tool_gates.py"
Cohesion: 0.05
Nodes (79): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+71 more)

### Community 12 - "._run_agent_task"
Cohesion: 0.05
Nodes (11): on_huddle(), on_progress(), on_huddle(), on_progress(), _has_non_user_turns(), _is_automated_nudge(), _is_participant_turn(), _sanitize_error_text() (+3 more)

### Community 13 - "App.tsx"
Cohesion: 0.05
Nodes (60): oidc-client-ts, react-dom, react-router-dom, dismissProposals(), EnhancementProposal, getHandoffReports(), getIncidents(), getProposals() (+52 more)

### Community 14 - "TopologyRepository"
Cohesion: 0.03
Nodes (9): Service, get_event_document(), list_events(), get_graph_data(), get_mermaid_diagram(), get_service_details(), get_topology(), list_services() (+1 more)

### Community 15 - "Archivist"
Cohesion: 0.05
Nodes (5): Archivist, _sanitize_lesson_text(), create_adapter(), record_token_usage(), Pulse

### Community 16 - "http-handler.js"
Cohesion: 0.08
Nodes (62): is429Error(), registerMCPsAndHooks(), resolveCommand(), writeAgyMcpServer(), writeClaudeMcpServer(), parsePositiveInt(), buildArgoCDMcpConfig(), createAppJWT() (+54 more)

### Community 17 - "os"
Cohesion: 0.05
Nodes (21): _get_static_maintainer_emails(), _get_allowed_mention_authors(), _get_static_maintainer_emails(), _safe_int(), _stale_reservation_ttl_s(), dex_proxy(), approve_mission(), dismiss_mission() (+13 more)

### Community 18 - "nightwatcher_tools.py"
Cohesion: 0.06
Nodes (26): PulseContext, ShiftIncident, ShiftInvestigation, build_report_iteration_prompt(), build_summary_prompt(), extract_full_links(), _normalize_gitlab_host(), build_extend_tool() (+18 more)

### Community 19 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 20 - "auth.py"
Cohesion: 0.06
Nodes (17): DashboardWSAdapter, can_append_message(), can_approve_event(), can_override_domain(), _claims_to_user(), get_user_from_request(), get_user_from_slack(), get_user_from_websocket() (+9 more)

### Community 21 - "ScheduleRepository"
Cohesion: 0.04
Nodes (9): ScheduleCreateRequest, ScheduledEvent, create_schedule(), delete_schedule(), get_schedule(), list_schedules(), toggle_schedule(), update_schedule() (+1 more)

### Community 23 - "react"
Cohesion: 0.09
Nodes (41): react, @uiw/react-markdown-preview, closeEvent(), enforceCasualDomain(), rejectEvent(), MessageStatus, CollapsibleSection(), CollapsibleSectionProps (+33 more)

### Community 24 - "AgentRegistry"
Cohesion: 0.06
Nodes (12): AgentConnection, AgentRegistry, agent_websocket_handler(), _build_prompt(), consume_wake_task(), _consume(), _dispatch_timeout_s(), dispatch_to_agent() (+4 more)

### Community 25 - "._process_with_llm"
Cohesion: 0.04
Nodes (6): _BatchContext, _contents_have_pruned_or_decayed(), _ensure_recall_tool_if_needed(), _is_close_phase_fc(), _QuotaShedState, _retry_backoff_delay()

### Community 26 - "BrainSkillLoader"
Cohesion: 0.05
Nodes (4): _parse_positive_int_env(), BrainSkillLoader, _SkillCorpus, _wrap_section()

### Community 27 - "brain.py"
Cohesion: 0.06
Nodes (21): _compute_processed_up_to(), _is_seed_turn(), _is_steering_turn(), _coerce_turn_int(), handle_recall_pruned_turns(), _parse_turn_int(), _sanitize_recalled(), _alert_wrapper_retrigger() (+13 more)

### Community 29 - "useOpsControl"
Cohesion: 0.08
Nodes (40): AgentStreamCard(), AgentStreamCardProps, MessageCards(), Dashboard(), GridTile(), GridTileProps, TileType, InlineMarkdownViewer() (+32 more)

### Community 30 - "GitHubPlatform"
Cohesion: 0.05
Nodes (3): GitHubPlatform, _poll_one(), _poll_one()

### Community 31 - "merge-guard.js"
Cohesion: 0.04
Nodes (46): API_VALUED, ARGO_MUTATING, ARGO_READ_SUB, ARGO_READ_TOP, BODY_FLAG, BROWSER_READ, CTX, ENV_BUILTINS (+38 more)

### Community 32 - "GeminiAdapter"
Cohesion: 0.09
Nodes (10): _attach_signature_to_parts(), _clone_part_with_sig(), _clone_part_with_text(), _extract_part_signature(), GeminiAdapter, _is_empty_sig_carrier(), _part_has_fc(), _sanitize_candidate_parts() (+2 more)

### Community 33 - "gemini_client.py"
Cohesion: 0.07
Nodes (21): _extract_call_syntax(), _parse_drain_timeout(), derive_llm_priority(), _get_timeout_env_warned(), _get_timeout_order_warned(), is_partial_control_token(), LLMStreamInterChunkTimeoutError, LLMStreamTimeoutError (+13 more)

### Community 34 - "cli-executor.js"
Cohesion: 0.09
Nodes (37): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, MAX_TASK_WALL_MS, MAX_TIMER_MS, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS, STORAGE_PRETASK_TIMEOUT_MS, resolveStorageRoot }, buildCLICommand(), buildTimeoutResult(), { checkAndRecycleStorage, pinTaskCwd, unpinTaskCwd }, CLAUDE_JSON_PATH, cp, createInactivityWatchdog(), executeCLI() (+29 more)

### Community 35 - "storage-recycler.js"
Cohesion: 0.08
Nodes (37): withTaskStorage(), MAX_TASK_WALL_MS, parseTimerMs(), resolveStorageRoot(), resolveTimeoutMs(), ROLE_TIMEOUTS, STORAGE_ACTIVITY_HEARTBEAT_MS, STORAGE_MAX_TIER3_DELETIONS (+29 more)

### Community 36 - "slack.py"
Cohesion: 0.07
Nodes (18): build_access_denied_home_view(), build_event_report_md(), build_home_tab_view(), _context_line(), create_feedback_block(), _replace(), format_plan_block(), format_task_card() (+10 more)

### Community 38 - "agents/__init__.py"
Cohesion: 0.07
Nodes (4): Architect, AgentClient, Developer, SysAdmin

### Community 39 - "llm/__init__.py"
Cohesion: 0.08
Nodes (7): ClaudeAdapter, _parse_tpm_limit(), FunctionCall, LLMChunk, LLMPort, LLMResponse, TokenUsage

### Community 40 - "OpsStateContext.tsx"
Cohesion: 0.09
Nodes (34): getAgents(), getAlignerPending(), getEventDocument(), getJenkinsPending(), getKargoStages(), getWaitingApprovalEvents(), EventDocument, EventEvidence (+26 more)

### Community 41 - "Headhunter"
Cohesion: 0.08
Nodes (3): Headhunter, _raise_if_systemic_failure(), _sanitize_xml_fence()

### Community 43 - "main.py"
Cohesion: 0.07
Nodes (16): set_kg_store(), set_pulse_tracker(), set_registry_and_bridge(), agent_ws_endpoint(), api_info(), get_config(), get_event_flow(), delta() (+8 more)

### Community 44 - "lifespan"
Cohesion: 0.06
Nodes (7): set_agents(), set_archivist(), set_argocd_observer(), set_brain(), set_kargo_observer(), lifespan(), close_redis()

### Community 46 - "BrainIntrospectionPort"
Cohesion: 0.06
Nodes (4): BrainIntrospectionPort, BrainLifecyclePort, BroadcastPort, JarvisPeerPort

### Community 47 - "ws-client.js"
Cohesion: 0.10
Nodes (26): clearIdleTimer(), {
  DEFAULT_WORK_DIR, AGENT_CLI, AGENT_MODEL, AGENT_ROLE,
  EVENT_ID, EPHEMERAL, IDLE_TIMEOUT_MS,
  CLI_429_MAX_RETRIES, CLI_429_INITIAL_DELAY_MS, CLI_429_BACKOFF_MULTIPLIER,
  resolveTimeoutMs, parsePositiveInt, MAX_TASK_WALL_MS, MAX_TIMER_MS,
}, { ensureEventDocument }, { executeCLIStreaming, prepareResultsDir, is429Error }, { filterSkillsByRole, filterSkillsByMode, swapActiveRules, restoreAllSkills }, fs, handleCancel(), handleTask() (+18 more)

### Community 48 - "ui/package.json"
Cohesion: 0.08
Nodes (29): autoprefixer, cronstrue, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, graphology-layout-forceatlas2 (+21 more)

### Community 49 - "CortexGraph.tsx"
Cohesion: 0.12
Nodes (29): graphology, ActiveEvent, KGServiceEntity, eventColor(), getExecutiveNeurons(), getStructuralEdges(), DEFAULT_TYPE_BUDGET, evictLru() (+21 more)

### Community 51 - "TimeKeeperPage.tsx"
Cohesion: 0.13
Nodes (20): getSchedules(), ScheduleCreatePayload, ScheduleItem, toggleSchedule(), Props, ScheduleForm(), TEMPLATES, formatNextFire() (+12 more)

### Community 54 - "EventDrillDown.tsx"
Cohesion: 0.13
Nodes (23): three, getEventPulses(), BrainCore(), CortexDevPage(), devQueryClient, CortexLiveFeedProps, EventDrillDown(), EventDrillDownProps (+15 more)

### Community 55 - "NightwatcherObserver"
Cohesion: 0.11
Nodes (6): ShiftReport, _append_user_turn(), _env_float(), _env_int(), NightwatcherObserver, _finalize_analysis_handover()

### Community 56 - "KnowledgeGraphStore"
Cohesion: 0.15
Nodes (4): _acquire(), KnowledgeGraphStore, _sanitize(), _with_timeout()

### Community 57 - "PlanProgress.tsx"
Cohesion: 0.15
Nodes (22): ConversationTurn, BORDER_COLOR, PlanProgressProps, STATUS_ICON, DeferCountdownState, useDeferCountdown(), EMPTY_CONVERSATION, computeDeferProgress() (+14 more)

### Community 58 - "observations_mgmt.py"
Cohesion: 0.10
Nodes (10): get_report_client(), render_pdf(), bulk_delete_observations(), BulkDeleteRequest, delete_observation(), export_observations(), generate_observations_report(), rename_observation() (+2 more)

### Community 59 - "server.js"
Cohesion: 0.09
Nodes (18): { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, ensureEventDocument(), fs, path, stageEventDocument(), fetchEventDocument(), fs, { handleRequest } (+10 more)

### Community 62 - ".list_observations"
Cohesion: 0.08
Nodes (4): get_all_journal(), get_service_journal(), get_event_observations(), get_global_observations()

### Community 64 - "PulseBatch"
Cohesion: 0.10
Nodes (4): PulseBatch, PulsePort, PulseObserver, PulseTracker

### Community 66 - "reconcile.py"
Cohesion: 0.15
Nodes (10): sanitize_redis_port(), _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers(), main() (+2 more)

### Community 69 - "dependencies"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 70 - "StateWatcher"
Cohesion: 0.11
Nodes (3): _QueueEntry, StateWatcher, _Subscription

### Community 71 - "FlowHistoryPage.tsx"
Cohesion: 0.20
Nodes (18): recharts, getFlowHistory(), FlowSnapshot, FlowHistoryPage(), RANGES, SparkCard(), SparkCardProps, TokenUsageMini() (+10 more)

### Community 72 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 73 - "claude-guard.js"
Cohesion: 0.14
Nodes (18): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+10 more)

### Community 74 - "ArchitectureGraph.tsx"
Cohesion: 0.14
Nodes (18): @dagrejs/dagre, @xyflow/react, applyDagreLayout(), applyGridLayout(), applyLayout(), ArchitectureGraph(), ArchitectureGraphInner(), buildGraph() (+10 more)

### Community 78 - "jenkins_observer.py"
Cohesion: 0.14
Nodes (9): _clamp_confidence(), _prepare_console_tail(), _redact_match(), _redact_secrets_in_text(), _sanitize_analysis_text(), _sanitize_console_tail(), _strip_newlines(), _validate_analysis() (+1 more)

### Community 79 - "useCortexData.ts"
Cohesion: 0.24
Nodes (19): getCortexActivity(), getEventReport(), getKnowledgeById(), getMemory(), getRecentPulses(), CortexPage(), fetchOffRingNeuron(), isOffRingCollection() (+11 more)

### Community 80 - "context_parts.py"
Cohesion: 0.17
Nodes (7): _apply_sibling_signature(), extract_model_parts(), _get_part_sig(), _is_empty_carrier_dict(), normalize_response_parts(), turn_to_parts(), _valid_sig()

### Community 81 - "cli-setup.js"
Cohesion: 0.13
Nodes (18): { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync }, filterSkillsByMode() (+10 more)

### Community 82 - "observations_reporter.py"
Cohesion: 0.15
Nodes (8): _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), _sample_points(), _summarize(), download_skill_md()

### Community 83 - "QuotaTracker"
Cohesion: 0.11
Nodes (4): get_quota_tracker(), QuotaTracker, llm_stats(), receive_telemetry()

### Community 84 - "event_namer.py"
Cohesion: 0.14
Nodes (5): generate_event_title(), get_adapter(), _get_semaphore(), sanitize_prompt_text(), sanitize_title()

### Community 86 - "prompt.py"
Cohesion: 0.17
Nodes (13): _build_closed_block(), build_event_header(), _build_identity_block(), _build_journal_block(), _build_mermaid_block(), build_operational_briefing(), _build_related_block(), _build_subject_block() (+5 more)

### Community 88 - "devDependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 89 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 90 - "gemini-sidecar/package.json"
Cohesion: 0.11
Nodes (18): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+10 more)

### Community 91 - "handlers_lookup.py"
Cohesion: 0.16
Nodes (7): _safe_int(), _format_bounded_journal(), handle_consult_deep_memory(), handle_lookup_journal(), _safe_seconds(), safe_score(), strip_stabilization_wake_prefix()

### Community 94 - "get_report"
Cohesion: 0.11
Nodes (6): get_report(), list_reports(), reports_spa_no_slash(), reports_spa_with_slash(), search_reports(), _serve_spa()

### Community 95 - "._process_candidates"
Cohesion: 0.12
Nodes (3): _flood_service_key(), _outage_service_key(), _service_key()

### Community 97 - "ShiftsPage.tsx"
Cohesion: 0.23
Nodes (16): getCurrentShift(), getShiftDetail(), getShiftsList(), ShiftReportFull, ShiftReportSummary, FailedClusterBadge(), getISOWeek(), getWeekDates() (+8 more)

### Community 98 - "catalog-skills.js"
Cohesion: 0.16
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 101 - "spawn_event_namer_task"
Cohesion: 0.22
Nodes (7): spawn_event_namer_task(), format_event_summary(), handle_app_mention(), handle_create_event_modal(), handle_darwin_command(), on_dm_message(), fallback_title()

### Community 105 - "generate_map.py"
Cohesion: 0.19
Nodes (6): _enumerate_gates(), _GateInfo, generate_phase_tool_map(), _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 106 - "jira_incident.py"
Cohesion: 0.23
Nodes (8): _adf_to_text(), adf_to_markdown(), _apply_marks(), _children(), _render(), _render_list(), _render_list_item(), _render_table_like()

### Community 107 - "JenkinsPlatformPort"
Cohesion: 0.13
Nodes (4): BuildDetails, JenkinsPlatformPort, JobRunState, ViewScanResult

### Community 110 - "graph_recall.py"
Cohesion: 0.19
Nodes (5): _format_graph_context(), get_graph_context(), _parse_props(), _sanitize(), translate_to_lookups()

### Community 112 - "ServiceNode.tsx"
Cohesion: 0.20
Nodes (11): HealthStatus, NodeType, AppNodeData, ARGOCD_HEALTH_COLORS, SYNC_ICONS, GENERIC_TAGS, HEALTH_COLORS, NODE_ICONS (+3 more)

### Community 117 - "NeuronInfoPanel.tsx"
Cohesion: 0.23
Nodes (13): KGServiceDetail, asNumber(), asString(), asStringArray(), Badge(), describeNeuron(), Hdr(), NeuronInfoPanel() (+5 more)

### Community 118 - "analyzeTokens"
Cohesion: 0.19
Nodes (13): analyzeString(), analyzeTokens(), assignName(), base(), combineCategories(), configEnvGuard(), configFileWriteGuard(), hasSubseq() (+5 more)

### Community 119 - "scheduling/__init__.py"
Cohesion: 0.22
Nodes (5): GitHubPrRef, GitLabMrRef, GitLabPipelineRef, KargoStageRef, PollFn

### Community 122 - "._extract_context_flags"
Cohesion: 0.15
Nodes (3): compute_dispatch_backpressure(), ContextFlags, _safe_int_env()

### Community 123 - "IncidentAdapterPort"
Cohesion: 0.15
Nodes (3): IdleTimeoutPort, IncidentAdapterPort, StateWatcherPort

### Community 127 - "compress_contents"
Cohesion: 0.18
Nodes (6): compress_contents(), contents_have_pruned_or_decayed(), estimate_msg_tokens(), estimate_tokens(), format_prune_notice(), prune_notice_count()

### Community 129 - "._authorize_plan_decision"
Cohesion: 0.18
Nodes (3): _PlanDecision, handle_approve(), handle_reject()

### Community 130 - "cortex/types.ts"
Cohesion: 0.21
Nodes (10): EventSource, PulseTimelineProps, CognitiveGraphResponse, CortexHeartbeatMessage, FrictionIndicator, FrictionPattern, NeuronVisual, Pulse (+2 more)

### Community 131 - "CortexLiveFeed.tsx"
Cohesion: 0.24
Nodes (10): CortexHeartbeat(), CortexHeartbeatProps, ensureKeyframes(), CortexLiveFeed(), FILTER_PILLS, FilterKey, getStoredFilter(), MESSAGE_STYLES (+2 more)

### Community 132 - "testSetup.ts"
Cohesion: 0.18
Nodes (5): @tailwindcss/vite, @testing-library/react, vite, @vitejs/plugin-react, vitest

### Community 134 - "is_defer_event_available"
Cohesion: 0.18
Nodes (6): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 135 - "cortex-constants.ts"
Cohesion: 0.18
Nodes (10): AGENTS, DOMAINS, HEMISPHERE_X, NEURON_DESCRIPTIONS, PHASE_SKILL_FOLDERS, PHASE_TOOL_PRIORITY, PHASES, StructuralEdge (+2 more)

### Community 136 - "SecurityError"
Cohesion: 0.24
Nodes (4): _check_security(), safe_execution(), wrapper(), SecurityError

### Community 137 - "gitGuard"
Cohesion: 0.29
Nodes (10): bareBranchProtected(), configWriteGuard(), externalGitCommand(), gitGuard(), gitQuery(), isProtected(), normRef(), pushGuard() (+2 more)

### Community 138 - "parseShell"
Cohesion: 0.33
Nodes (10): bodySubstitutions(), decodeAnsiC(), isArrayAssignPrefix(), isWordStart(), matchBacktick(), matchParen(), parseShell(), readHeredocStart() (+2 more)

### Community 143 - "entity_extractor.py"
Cohesion: 0.33
Nodes (5): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship

### Community 144 - "has_unevaluated_close_blocker"
Cohesion: 0.22
Nodes (5): has_unevaluated_close_blocker(), _pred_jarvis_response(), _pred_unevaluated_close(), is_jarvis_acknowledgment(), is_stabilization_wake()

### Community 145 - "._send_turn_to_thread"
Cohesion: 0.27
Nodes (3): extract_tables(), get_agent_notification_text(), get_turn_attachment_color()

### Community 147 - "knowledge_graph_api.py"
Cohesion: 0.31
Nodes (4): get_kg_store(), get_service_detail(), get_stats(), list_services()

### Community 148 - "classifyTool"
Cohesion: 0.31
Nodes (9): apiTokens(), apiWriteNeedsGuard(), branchValues(), classifyTool(), hasOpaqueTarget(), httpGuard(), httpMethod(), isReadMethod() (+1 more)

### Community 149 - "strip_xml_fences"
Cohesion: 0.25
Nodes (4): build_function_response(), build_single_function_response(), format_evidence_decay_reference(), strip_xml_fences()

### Community 151 - "_resolve_domain"
Cohesion: 0.25
Nodes (4): _batch_is_terminal_for_flush(), can_transition_to_close(), _resolve_domain(), resolve_event_domain()

### Community 163 - "validate-mutations.sh"
Cohesion: 0.57
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

### Community 168 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 169 - "state.js"
Cohesion: 0.33
Nodes (4): { AGENT_ROLE }, _blackboardTurns, _inboundMessages, _teammateMessages

### Community 176 - "_append_user_turn"
Cohesion: 0.33
Nodes (3): _append_user_turn(), _is_function_response_part(), _validated_parts()

### Community 177 - "build_gate_context"
Cohesion: 0.33
Nodes (3): build_gate_context(), conversation_has_decayed_turns(), _decay_payload_len()

### Community 179 - "build_manifest_table"
Cohesion: 0.33
Nodes (3): build_manifest_table(), build_system_prompt(), extract_event_links()

### Community 185 - "classify"
Cohesion: 0.50
Nodes (4): classify(), main(), shellCategory(), shellNeedsGuard()

### Community 198 - "overrides"
Cohesion: 0.67
Nodes (3): overrides, @typescript-eslint/typescript-estree, minimatch

## Knowledge Gaps
- **13 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+8 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2347 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **112 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `ConversationTurn`, `queue.py`, `logging`, `models.py`, `dependencies.py`, `Brain`, `TopologyRepository`, `os`, `nightwatcher_tools.py`, `auth.py`, `ScheduleRepository`, `EventDocument`, `get_current_shift`, `BrainSkillLoader`, `brain.py`, `_is_event_closed_or_missing`, `HeadhunterJira`, `slack.py`, `update_notebook_note`, `main.py`, `lifespan`, `LiveAPIAdapter`, `get_notebook`, `NightwatcherObserver`, `observations_mgmt.py`, `.list_observations`, `jenkins_observer.py`, `observations_reporter.py`, `event_namer.py`, `get_report`?**
  _High betweenness centrality (0.101) - this node is a cross-community bridge._
- **Are the 80 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 80 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.012742200328407225 - nodes in this community are weakly interconnected._
- **Why does `Brain` connect `Brain` to `BlackboardState`, `ConversationTurn`, `.start_event_loop`, `models.py`, `dependencies.py`, `._run_agent_task`, `._resolve_llm_params`, `._post_agent_recall`, `FlowCollector`, `Archivist`, `auth.py`, `EventDocument`, `._process_with_llm`, `BrainSkillLoader`, `brain.py`, `._detect_repetition_collapse`, `slack.py`, `agents/__init__.py`, `main.py`, `lifespan`, `BrainIntrospectionPort`, `._resolve_maintainer_enum`, `StalenessGuard`, `PulseBatch`, `.clear_jarvis_wait`, `.has_subscription`, `._build_contents`, `.next_turn_number`, `StateWatcher`, `ReflexSearcher`, `IdleTimeoutManager`, `._extract_context_flags`, `ReconcileScheduler`?**
  _High betweenness centrality (0.083) - this node is a cross-community bridge._
- **Are the 20 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Should `EventSidebar.tsx` be split into smaller, more focused modules?**
  _Cohesion score 0.03793574846206425 - nodes in this community are weakly interconnected._