# Graph Report - Blackboard  (2026-11-11)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 5121 nodes · 11449 edges · 197 communities (104 shown, 93 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 947 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `4cad3b9f`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BlackboardState
- logging
- slack.py
- WorkspaceInspector.tsx
- main.py
- Archivist
- queue.py
- client.ts
- ConversationTurn
- colors.ts
- EventSidebar.tsx
- EventDocument
- Brain
- tool_gates.py
- brain.py
- App.tsx
- http-handler.js
- ._run_agent_task
- JarvisMemoryPage.tsx
- models.py
- jenkins-mcp.js
- topology.py
- react
- auth.py
- nightwatcher_tools.py
- BaseModel
- Aligner
- JenkinsObserver
- BrainSkillLoader
- ScheduleCreateRequest
- _BrainToolContext
- time
- merge-guard.js
- KnowledgeGraphStore
- observations_mgmt.py
- live_api_adapter.py
- ._process_with_llm
- GitHubAppAuth
- ephemeral_provisioner.py
- cli-executor.js
- storage-recycler.js
- GitHubPlatform
- JenkinsAdapter
- EventRepository
- EventDrillDown.tsx
- Headhunter
- GitLabPlatform
- httpx
- chat.py
- TimeKeeperPage.tsx
- jenkins.py
- ws-client.js
- NightwatcherObserver
- ui/package.json
- NodeInspector.tsx
- EphemeralProvisioner
- useCortexData.ts
- CortexGraph.tsx
- ._close_and_broadcast
- cognitive_graph.py
- GeminiAdapter
- server.js
- ArgoCDObserver
- ._get_manager
- types.py
- KargoObserver
- dependencies
- reconcile.py
- quota_tracker.py
- StateWatcher
- jira_incident.py
- compilerOptions
- claude-guard.js
- TokenUtilizationPage.tsx
- state/__init__.py
- VcsPlatformPort
- cli-setup.js
- ReflexSearcher
- .start_event_loop
- context_parts.py
- FairQueue
- devDependencies
- compilerOptions
- gemini-sidecar/package.json
- ServiceNode.tsx
- LiveAPIAdapter
- get_report
- OpsStateContext.tsx
- ObservationRepository
- ShiftsPage.tsx
- catalog-skills.js
- SlackAccessGate
- ArchitectureGraph.tsx
- ClaudeAdapter
- gemini_client.py
- EscalationRepository
- OIDCKeyAdapter
- .list_observations
- ReconcileScheduler
- handlers_planning.py
- IncidentAdapterPort
- ScheduleRepository
- analyzeTokens
- generate_map.py
- ._extract_context_flags
- BrainLifecyclePort
- TokenMeter
- IdleTimeoutManager
- NeuronInfoPanel.tsx
- generate_event_title
- CiContextCard.tsx
- CortexLiveFeed.tsx
- testSetup.ts
- is_defer_event_available
- cortex-constants.ts
- gitGuard
- parseShell
- _is_event_closed_or_missing
- ._post_agent_recall
- HeadhunterJira
- has_unevaluated_close_blocker
- knowledge_graph_api.py
- ._get_ticket_nodes
- classifyTool
- get_quota_tracker
- SmartsheetMaintainerCache
- .has_reeval_signal
- get_all_journal
- Trigger
- GitLabTokenAuth
- useDeferCountdown.ts
- sanitize_call_syntax
- ConversationMessage
- TimeKeeperObserver
- routes/kargo.py
- CortexRepository
- adf_to_markdown
- validate-mutations.sh
- scripts
- state.js
- ._process_message
- Neuron
- submit_feedback
- list_shifts
- QueueTrigger
- TicketNode.tsx
- classify
- list_incidents
- require-results.sh
- TokenUsageDict
- report_tampering
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
- build_gate_context
- diagnose_rejection
- GateDefinition
- _pred_dispatch_defer
- _pred_hard_strip_defer
- _pred_jarvis_wait
- _pred_obs_plateau
- _pred_silent_park
- _tools_wait_loop
- _normalize_gitlab_host

## God Nodes (most connected - your core abstractions)
1. `BlackboardState` - 285 edges
2. `Brain` - 151 edges
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

## Communities (197 total, 93 thin omitted)

### Community 1 - "logging"
Cohesion: 0.04
Nodes (14): _get_static_maintainer_emails(), _get_allowed_mention_authors(), _get_static_maintainer_emails(), _safe_int(), _env_flag(), create_adapter(), record_token_usage(), EventEvidence (+6 more)

### Community 2 - "slack.py"
Cohesion: 0.03
Nodes (32): spawn_event_namer_task(), build_access_denied_home_view(), build_home_tab_view(), _context_line(), create_feedback_block(), extract_tables(), _replace(), format_event_summary() (+24 more)

### Community 3 - "WorkspaceInspector.tsx"
Cohesion: 0.04
Nodes (85): lucide-react, closeEvent(), enforceCasualDomain(), updateEventTitle(), ConversationTurn, ChatInput(), ChatInputProps, Draft (+77 more)

### Community 4 - "main.py"
Cohesion: 0.02
Nodes (37): Architect, AgentClient, Developer, set_incident_options(), SysAdmin, set_oidc_adapter(), get_aligner(), get_architect() (+29 more)

### Community 5 - "Archivist"
Cohesion: 0.03
Nodes (11): Archivist, _sanitize_lesson_text(), Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship, Pulse (+3 more)

### Community 6 - "queue.py"
Cohesion: 0.03
Nodes (52): get_token_meter(), resolve_approval_identity(), get_archivist(), get_brain(), aligner_pending_items(), apply_lessons(), approve_event(), close_event_by_user() (+44 more)

### Community 7 - "client.ts"
Cohesion: 0.03
Nodes (93): @tanstack/react-query, ApiError, bulkDeleteObservations(), createChatEvent(), deleteNote(), deleteObservation(), exportObservations(), ExtractedLesson (+85 more)

### Community 8 - "ConversationTurn"
Cohesion: 0.07
Nodes (43): emit_tool_result(), handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_recall_pruned_turns(), handle_message_agent(), handle_reply_to_agent(), handle_report_incident() (+35 more)

### Community 9 - "colors.ts"
Cohesion: 0.06
Nodes (68): @uiw/react-markdown-preview, approveEvent(), getReport(), getReports(), rejectEvent(), submitFeedback(), ReportFull, ReportMeta (+60 more)

### Community 10 - "EventSidebar.tsx"
Cohesion: 0.06
Nodes (79): getActiveEvents(), getAlignerPending(), getEventDocument(), getHeadhunterPending(), getJenkinsPending(), getJiraMissions(), getWaitingApprovalEvents(), HeadhunterTodo (+71 more)

### Community 11 - "EventDocument"
Cohesion: 0.03
Nodes (13): _close_unanswered_fc(), _build_closed_block(), build_event_header(), _build_identity_block(), _build_journal_block(), _build_mermaid_block(), _build_related_block(), _build_subject_block() (+5 more)

### Community 13 - "tool_gates.py"
Cohesion: 0.05
Nodes (78): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+70 more)

### Community 14 - "brain.py"
Cohesion: 0.05
Nodes (17): AgentConnection, AgentRegistry, agent_websocket_handler(), _heartbeat(), _build_prompt(), _check_security(), consume_wake_task(), _consume() (+9 more)

### Community 15 - "App.tsx"
Cohesion: 0.06
Nodes (51): oidc-client-ts, react-router-dom, getConfig(), getWSAuthFailureCallback(), setOnUnauthorized(), setTokenGetter(), setWSAuthFailureCallback(), AppConfig (+43 more)

### Community 16 - "http-handler.js"
Cohesion: 0.08
Nodes (62): is429Error(), registerMCPsAndHooks(), resolveCommand(), writeAgyMcpServer(), writeClaudeMcpServer(), parsePositiveInt(), buildArgoCDMcpConfig(), createAppJWT() (+54 more)

### Community 17 - "._run_agent_task"
Cohesion: 0.06
Nodes (10): on_huddle(), on_progress(), on_huddle(), on_progress(), _compute_processed_up_to(), _is_automated_nudge(), _sanitize_error_text(), _sanitize_override_reason() (+2 more)

### Community 18 - "JarvisMemoryPage.tsx"
Cohesion: 0.06
Nodes (52): dismissProposals(), EnhancementProposal, getHandoffReports(), getProposals(), HandoffReport, AgentStreamCard(), AgentStreamCardProps, MessageCards() (+44 more)

### Community 19 - "models.py"
Cohesion: 0.05
Nodes (16): _safe_int(), _resolve_escalation_scope(), ArchitectureEvent, EventStatus, EventType, HealthStatus, MessageStatus, NodeType (+8 more)

### Community 20 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 21 - "topology.py"
Cohesion: 0.05
Nodes (11): GraphNode, GraphResponse, get_event_document(), list_events(), get_graph_data(), get_mermaid_diagram(), get_service_details(), get_topology() (+3 more)

### Community 22 - "react"
Cohesion: 0.08
Nodes (51): react, applyLessons(), correctMemory(), createKnowledge(), createLesson(), deleteKnowledge(), deleteLesson(), ExtractedCorrection (+43 more)

### Community 23 - "auth.py"
Cohesion: 0.05
Nodes (17): can_approve_event(), can_override_domain(), can_rename_event(), _claims_to_user(), get_user_from_request(), get_user_from_slack(), get_user_from_websocket(), _normalize_email() (+9 more)

### Community 24 - "nightwatcher_tools.py"
Cohesion: 0.07
Nodes (24): PulseContext, ShiftIncident, ShiftInvestigation, build_report_iteration_prompt(), build_summary_prompt(), extract_full_links(), build_extend_tool(), build_report_tool() (+16 more)

### Community 25 - "BaseModel"
Cohesion: 0.04
Nodes (14): AppNode, ChatRequest, ChatResponse, EventMetrics, GraphEdge, JenkinsPendingItem, Metrics, PendingAnomaly (+6 more)

### Community 27 - "JenkinsObserver"
Cohesion: 0.05
Nodes (4): _flood_service_key(), JenkinsObserver, _outage_service_key(), _service_key()

### Community 28 - "BrainSkillLoader"
Cohesion: 0.05
Nodes (3): BrainSkillLoader, _SkillCorpus, BrainIntrospectionPort

### Community 29 - "ScheduleCreateRequest"
Cohesion: 0.05
Nodes (8): EventInput, ScheduleCreateRequest, create_schedule(), delete_schedule(), get_schedule(), list_schedules(), toggle_schedule(), update_schedule()

### Community 31 - "time"
Cohesion: 0.07
Nodes (18): _alert_wrapper_retrigger(), _do_retrigger(), _get_jira_reporter(), handle_refresh_github_context(), handle_refresh_gitlab_context(), handle_refresh_kargo_context(), _is_darwin_reentrant_caller(), jenkins_retrigger_cooldown_key() (+10 more)

### Community 32 - "merge-guard.js"
Cohesion: 0.04
Nodes (46): API_VALUED, ARGO_MUTATING, ARGO_READ_SUB, ARGO_READ_TOP, BODY_FLAG, BROWSER_READ, CTX, ENV_BUILTINS (+38 more)

### Community 33 - "KnowledgeGraphStore"
Cohesion: 0.08
Nodes (9): _format_graph_context(), get_graph_context(), _parse_props(), _sanitize(), translate_to_lookups(), _acquire(), KnowledgeGraphStore, _sanitize() (+1 more)

### Community 34 - "observations_mgmt.py"
Cohesion: 0.06
Nodes (18): get_report_client(), _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), render_pdf(), _sample_points() (+10 more)

### Community 35 - "live_api_adapter.py"
Cohesion: 0.06
Nodes (8): PulseBatch, PulsePort, PulseObserver, PulseTracker, get_github_auth(), maintainer_env_key(), resolve_maintainer_emails(), redact_pii()

### Community 37 - "GitHubAppAuth"
Cohesion: 0.07
Nodes (4): AsyncGitHubClient, _find_pem_file(), GitHubAppAuth, MultiInstallationManager

### Community 38 - "ephemeral_provisioner.py"
Cohesion: 0.07
Nodes (5): KubernetesSpawnHealthAdapter, _PodHealthState, SpawnHealthPort, SpawnPollResult, SpawnStatus

### Community 39 - "cli-executor.js"
Cohesion: 0.09
Nodes (37): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, MAX_TASK_WALL_MS, MAX_TIMER_MS, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS, STORAGE_PRETASK_TIMEOUT_MS, resolveStorageRoot }, buildCLICommand(), buildTimeoutResult(), { checkAndRecycleStorage, pinTaskCwd, unpinTaskCwd }, CLAUDE_JSON_PATH, cp, createInactivityWatchdog(), executeCLI() (+29 more)

### Community 40 - "storage-recycler.js"
Cohesion: 0.08
Nodes (37): withTaskStorage(), MAX_TASK_WALL_MS, parseTimerMs(), resolveStorageRoot(), resolveTimeoutMs(), ROLE_TIMEOUTS, STORAGE_ACTIVITY_HEARTBEAT_MS, STORAGE_MAX_TIER3_DELETIONS (+29 more)

### Community 42 - "JenkinsAdapter"
Cohesion: 0.06
Nodes (6): BuildDetails, JenkinsAdapter, JenkinsPlatformPort, JobResult, JobRunState, ViewScanResult

### Community 44 - "EventDrillDown.tsx"
Cohesion: 0.10
Nodes (31): three, getEventPulses(), EventSource, BrainCore(), CortexDevPage(), devQueryClient, CortexLiveFeedProps, EventDrillDown() (+23 more)

### Community 45 - "Headhunter"
Cohesion: 0.07
Nodes (3): Headhunter, _raise_if_systemic_failure(), _sanitize_xml_fence()

### Community 47 - "httpx"
Cohesion: 0.09
Nodes (13): dex_proxy(), approve_mission(), dismiss_mission(), _infer_phase(), _jira_config(), list_missions(), reanalyze_mission(), retry_mission() (+5 more)

### Community 48 - "chat.py"
Cohesion: 0.09
Nodes (6): DashboardWSAdapter, can_append_message(), prompt_display_name(), ChatEventRequest, ChatEventResponse, create_chat_event()

### Community 49 - "TimeKeeperPage.tsx"
Cohesion: 0.12
Nodes (24): createSchedule(), deleteSchedule(), getSchedules(), refineInstructions(), ScheduleCreatePayload, ScheduleItem, toggleSchedule(), updateSchedule() (+16 more)

### Community 50 - "jenkins.py"
Cohesion: 0.07
Nodes (13): _annotation_replace(), _strip_pipeline_annotations(), _clamp_confidence(), _parse_job_metadata(), _prepare_console_tail(), _redact_build_parameters(), _redact_match(), _redact_secrets_in_text() (+5 more)

### Community 51 - "ws-client.js"
Cohesion: 0.10
Nodes (26): clearIdleTimer(), {
  DEFAULT_WORK_DIR, AGENT_CLI, AGENT_MODEL, AGENT_ROLE,
  EVENT_ID, EPHEMERAL, IDLE_TIMEOUT_MS,
  CLI_429_MAX_RETRIES, CLI_429_INITIAL_DELAY_MS, CLI_429_BACKOFF_MULTIPLIER,
  resolveTimeoutMs, parsePositiveInt, MAX_TASK_WALL_MS, MAX_TIMER_MS,
}, { ensureEventDocument }, { executeCLIStreaming, prepareResultsDir, is429Error }, { filterSkillsByRole, filterSkillsByMode, swapActiveRules, restoreAllSkills }, fs, handleCancel(), handleTask() (+18 more)

### Community 52 - "NightwatcherObserver"
Cohesion: 0.09
Nodes (8): ShiftReport, _append_user_turn(), _env_float(), _env_int(), NightwatcherObserver, _finalize_analysis_handover(), build_system_prompt(), get_phase_tools()

### Community 53 - "ui/package.json"
Cohesion: 0.08
Nodes (29): autoprefixer, cronstrue, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, graphology-layout-forceatlas2 (+21 more)

### Community 54 - "NodeInspector.tsx"
Cohesion: 0.11
Nodes (26): getClosedEvents(), getEvents(), ArchitectureEvent, ArgoCDOperation, ActivityStream(), ArchitectureGraph(), EVENT_LABELS, EventItem() (+18 more)

### Community 55 - "EphemeralProvisioner"
Cohesion: 0.09
Nodes (3): DispatchMetrics, EphemeralProvisioner, SpawnFailed

### Community 56 - "useCortexData.ts"
Cohesion: 0.17
Nodes (27): getCognitiveGraph(), getCortexActivity(), getEventReport(), getKGServiceDetail(), getKGServices(), getKGStats(), getKnowledgeById(), getMemory() (+19 more)

### Community 57 - "CortexGraph.tsx"
Cohesion: 0.13
Nodes (27): graphology, sigma, eventColor(), getExecutiveNeurons(), getStructuralEdges(), DEFAULT_TYPE_BUDGET, evictLru(), KNOWLEDGE_RING (+19 more)

### Community 59 - "cognitive_graph.py"
Cohesion: 0.11
Nodes (12): get_blackboard(), get_pulse_tracker(), dismiss_proposals(), DismissRequest, get_all_shadow_interventions(), get_cognitive_graph(), get_cortex_activity(), get_cortex_status() (+4 more)

### Community 60 - "GeminiAdapter"
Cohesion: 0.13
Nodes (3): _extract_call_syntax(), GeminiAdapter, FunctionCall

### Community 61 - "server.js"
Cohesion: 0.09
Nodes (18): { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, ensureEventDocument(), fs, path, stageEventDocument(), fetchEventDocument(), fs, { handleRequest } (+10 more)

### Community 64 - "types.py"
Cohesion: 0.13
Nodes (6): derive_llm_priority(), LLMChunk, LLMPort, LLMResponse, TokenUsage, _turn_field()

### Community 66 - "dependencies"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 67 - "reconcile.py"
Cohesion: 0.16
Nodes (10): generate_phase_tool_map(), _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers(), main() (+2 more)

### Community 68 - "quota_tracker.py"
Cohesion: 0.12
Nodes (4): QuotaExhaustedError, QuotaTracker, RequestExceedsBurstError, Reservation

### Community 69 - "StateWatcher"
Cohesion: 0.11
Nodes (3): _QueueEntry, StateWatcher, _Subscription

### Community 70 - "jira_incident.py"
Cohesion: 0.12
Nodes (3): _adf_to_text(), _escape_jql_string(), JiraIncidentAdapter

### Community 71 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 72 - "claude-guard.js"
Cohesion: 0.14
Nodes (18): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+10 more)

### Community 73 - "TokenUtilizationPage.tsx"
Cohesion: 0.16
Nodes (17): recharts, getFlowHistory(), FlowSnapshot, ObservationSeries, FlowHistoryPage(), formatTime(), RANGES, SparkCard() (+9 more)

### Community 74 - "state/__init__.py"
Cohesion: 0.12
Nodes (3): sanitize_redis_port(), get_redis(), RedisClient

### Community 76 - "cli-setup.js"
Cohesion: 0.13
Nodes (18): { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync }, filterSkillsByMode() (+10 more)

### Community 79 - "context_parts.py"
Cohesion: 0.13
Nodes (9): _apply_sibling_signature(), build_function_response(), build_single_function_response(), compress_contents(), estimate_msg_tokens(), estimate_tokens(), extract_model_parts(), normalize_response_parts() (+1 more)

### Community 81 - "devDependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 82 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 83 - "gemini-sidecar/package.json"
Cohesion: 0.11
Nodes (18): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+10 more)

### Community 84 - "ServiceNode.tsx"
Cohesion: 0.15
Nodes (13): @xyflow/react, HealthStatus, NodeType, AppNodeData, ARGOCD_HEALTH_COLORS, SYNC_ICONS, NamespaceGroupNodeData, GENERIC_TAGS (+5 more)

### Community 87 - "get_report"
Cohesion: 0.11
Nodes (6): get_report(), list_reports(), reports_spa_no_slash(), reports_spa_with_slash(), search_reports(), _serve_spa()

### Community 88 - "OpsStateContext.tsx"
Cohesion: 0.17
Nodes (16): getAgents(), getKargoStages(), EventEvidence, KargoStageStatus, AgentRegistryPanel(), formatConnectedSince(), AGENTS, EVIDENCE_SEVERITIES (+8 more)

### Community 90 - "ShiftsPage.tsx"
Cohesion: 0.23
Nodes (16): getCurrentShift(), getShiftDetail(), getShiftsList(), ShiftReportFull, ShiftReportSummary, FailedClusterBadge(), getISOWeek(), getWeekDates() (+8 more)

### Community 91 - "catalog-skills.js"
Cohesion: 0.16
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 93 - "ArchitectureGraph.tsx"
Cohesion: 0.18
Nodes (15): @dagrejs/dagre, applyDagreLayout(), applyGridLayout(), applyLayout(), ArchitectureGraphInner(), buildGraph(), computeIdHash(), edgeTypes (+7 more)

### Community 96 - "gemini_client.py"
Cohesion: 0.18
Nodes (6): _append_user_turn(), _coerce_part(), _is_function_response_part(), _parse_drain_timeout(), _strip_user_thought_signature(), _validated_parts()

### Community 100 - "ReconcileScheduler"
Cohesion: 0.16
Nodes (3): ReconcileScheduler, ResyncTrigger, StalenessGuard

### Community 101 - "handlers_planning.py"
Cohesion: 0.23
Nodes (6): _auto_complete_step(), _canonical_role(), handle_get_plan_progress(), _is_failed_turn(), _is_orchestrator_turn(), _normalize_step_id()

### Community 103 - "IncidentAdapterPort"
Cohesion: 0.14
Nodes (3): IdleTimeoutPort, IncidentAdapterPort, StateWatcherPort

### Community 105 - "analyzeTokens"
Cohesion: 0.19
Nodes (13): analyzeString(), analyzeTokens(), assignName(), base(), combineCategories(), configEnvGuard(), configFileWriteGuard(), hasSubseq() (+5 more)

### Community 106 - "generate_map.py"
Cohesion: 0.19
Nodes (5): _enumerate_gates(), _GateInfo, _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 107 - "._extract_context_flags"
Cohesion: 0.15
Nodes (3): compute_dispatch_backpressure(), ContextFlags, _safe_int_env()

### Community 111 - "NeuronInfoPanel.tsx"
Cohesion: 0.24
Nodes (12): KGServiceDetail, asNumber(), asString(), asStringArray(), Badge(), describeNeuron(), Hdr(), NeuronInfoPanel() (+4 more)

### Community 112 - "generate_event_title"
Cohesion: 0.18
Nodes (4): generate_event_title(), get_adapter(), _get_semaphore(), sanitize_title()

### Community 115 - "CiContextCard.tsx"
Cohesion: 0.29
Nodes (10): CiContext, CiContextCard(), CiContextCardProps, ConsoleTailBlock(), FailedJobRow(), annotationReplacer(), PIPELINE_ANNOTATION_RE, REDACTION_TRIGGER_KEYWORDS (+2 more)

### Community 116 - "CortexLiveFeed.tsx"
Cohesion: 0.24
Nodes (10): CortexHeartbeat(), CortexHeartbeatProps, ensureKeyframes(), CortexLiveFeed(), FILTER_PILLS, FilterKey, getStoredFilter(), MESSAGE_STYLES (+2 more)

### Community 117 - "testSetup.ts"
Cohesion: 0.18
Nodes (5): @tailwindcss/vite, @testing-library/react, vite, @vitejs/plugin-react, vitest

### Community 118 - "is_defer_event_available"
Cohesion: 0.18
Nodes (6): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 119 - "cortex-constants.ts"
Cohesion: 0.18
Nodes (10): AGENTS, DOMAINS, HEMISPHERE_X, NEURON_DESCRIPTIONS, PHASE_SKILL_FOLDERS, PHASE_TOOL_PRIORITY, PHASES, StructuralEdge (+2 more)

### Community 120 - "gitGuard"
Cohesion: 0.29
Nodes (10): bareBranchProtected(), configWriteGuard(), externalGitCommand(), gitGuard(), gitQuery(), isProtected(), normRef(), pushGuard() (+2 more)

### Community 121 - "parseShell"
Cohesion: 0.33
Nodes (10): bodySubstitutions(), decodeAnsiC(), isArrayAssignPrefix(), isWordStart(), matchBacktick(), matchParen(), parseShell(), readHeredocStart() (+2 more)

### Community 127 - "has_unevaluated_close_blocker"
Cohesion: 0.20
Nodes (4): has_unevaluated_close_blocker(), _pred_jarvis_response(), _pred_unevaluated_close(), is_jarvis_acknowledgment()

### Community 128 - "knowledge_graph_api.py"
Cohesion: 0.31
Nodes (4): get_kg_store(), get_service_detail(), get_stats(), list_services()

### Community 130 - "classifyTool"
Cohesion: 0.31
Nodes (9): apiTokens(), apiWriteNeedsGuard(), branchValues(), classifyTool(), hasOpaqueTarget(), httpGuard(), httpMethod(), isReadMethod() (+1 more)

### Community 131 - "get_quota_tracker"
Cohesion: 0.22
Nodes (3): get_quota_tracker(), llm_stats(), receive_telemetry()

### Community 137 - "useDeferCountdown.ts"
Cohesion: 0.47
Nodes (7): DeferCountdownState, useDeferCountdown(), computeDeferProgress(), DeferTimeline, formatDeferRemaining(), inferDeferFromConversation(), resolveDeferTimeline()

### Community 142 - "sanitize_call_syntax"
Cohesion: 0.25
Nodes (4): process_stream_call_syntax_buffer(), sanitize_call_syntax(), scan_call_syntax(), split_stream_call_syntax()

### Community 147 - "adf_to_markdown"
Cohesion: 0.57
Nodes (7): adf_to_markdown(), _apply_marks(), _children(), _render(), _render_list(), _render_list_item(), _render_table_like()

### Community 148 - "validate-mutations.sh"
Cohesion: 0.57
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

### Community 150 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 151 - "state.js"
Cohesion: 0.33
Nodes (4): { AGENT_ROLE }, _blackboardTurns, _inboundMessages, _teammateMessages

### Community 157 - "Neuron"
Cohesion: 0.47
Nodes (6): ActiveEvent, KGServiceEntity, CortexGraphProps, GraphLoaderProps, Neuron, WorkspaceTaskItemProps

### Community 162 - "TicketNode.tsx"
Cohesion: 0.40
Nodes (4): STATUS_COLORS, TICKET_COLORS, TicketNodeComponent(), TicketNodeData

### Community 163 - "classify"
Cohesion: 0.50
Nodes (4): classify(), main(), shellCategory(), shellNeedsGuard()

### Community 171 - "overrides"
Cohesion: 0.67
Nodes (3): overrides, @typescript-eslint/typescript-estree, minimatch

## Knowledge Gaps
- **13 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+8 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2245 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **93 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `logging`, `slack.py`, `._get_ticket_nodes`, `main.py`, `get_all_journal`, `queue.py`, `ConversationTurn`, `EventDocument`, `Brain`, `brain.py`, `ConversationMessage`, `models.py`, `topology.py`, `auth.py`, `nightwatcher_tools.py`, `BaseModel`, `BrainSkillLoader`, `ScheduleCreateRequest`, `submit_feedback`, `list_shifts`, `observations_mgmt.py`, `live_api_adapter.py`, `report_tampering`, `httpx`, `chat.py`, `NightwatcherObserver`, `cognitive_graph.py`, `state/__init__.py`, `.start_event_loop`, `LiveAPIAdapter`, `get_report`, `.list_observations`, `ScheduleRepository`, `generate_event_title`, `_is_event_closed_or_missing`, `HeadhunterJira`?**
  _High betweenness centrality (0.127) - this node is a cross-community bridge._
- **Are the 80 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 80 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.014208721215090642 - nodes in this community are weakly interconnected._
- **Why does `Brain` connect `Brain` to `BlackboardState`, `logging`, `slack.py`, `main.py`, `Archivist`, `ConversationTurn`, `EventDocument`, `brain.py`, `._run_agent_task`, `models.py`, `BrainSkillLoader`, `.stop_event_loop`, `QueueTrigger`, `live_api_adapter.py`, `._process_with_llm`, `chat.py`, `._close_and_broadcast`, `quota_tracker.py`, `StateWatcher`, `ReflexSearcher`, `.start_event_loop`, `ReconcileScheduler`, `._extract_context_flags`, `BrainLifecyclePort`, `IdleTimeoutManager`, `._execute_function_call`, `._post_agent_recall`?**
  _High betweenness centrality (0.058) - this node is a cross-community bridge._
- **Are the 21 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 21 INFERRED edges - model-reasoned connections that need verification._
- **Should `logging` be split into smaller, more focused modules?**
  _Cohesion score 0.03801673228346457 - nodes in this community are weakly interconnected._