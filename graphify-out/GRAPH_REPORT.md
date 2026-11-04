# Graph Report - Blackboard  (2026-11-04)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 5014 nodes · 11207 edges · 209 communities (97 shown, 112 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 938 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `2db20f79`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BlackboardState
- client.ts
- logging
- queue.py
- EventChatPanel.tsx
- nightwatcher_tools.py
- blackboard.py
- brain.py
- tool_gates.py
- Archivist
- Brain
- EventDocument
- merge-guard.js
- hooks/index.ts
- dependencies.py
- App.tsx
- http-handler.js
- colors.ts
- react
- ._run_agent_task
- jenkins-mcp.js
- GeminiAdapter
- ReconcileScheduler
- Service
- EventSidebar.tsx
- JenkinsObserver
- os
- Aligner
- ToolContext
- main.py
- TurnBubble.tsx
- _BrainToolContext
- ConversationTurn
- cli-executor.js
- handlers_integration.py
- storage-recycler.js
- UserContext
- JenkinsAdapter
- EventRepository
- agents/__init__.py
- types.py
- GitHubPlatform
- httpx
- formatter.py
- ._process_with_llm
- jenkins_observer.py
- SlackChannel
- GitLabPlatform
- Headhunter
- TimeKeeperPage.tsx
- observations_mgmt.py
- KnowledgeGraphStore
- ActiveStreamsContext.tsx
- ws-client.js
- create_schedule
- spawn_event_namer_task
- ui/package.json
- DashboardWSAdapter
- useCortexData.ts
- server.js
- EventDrillDown.tsx
- TopologyRepository
- LiveAPIAdapter
- CortexGraph.tsx
- .list_observations
- VectorStore
- tool_router.py
- ArgoCDObserver
- useQueue.ts
- NodeInspector.tsx
- reconcile.py
- ._build_contents
- BrainSkillLoader
- ._get_manager
- state/ports.py
- KargoObserver
- GitHubAppAuth
- dependencies
- compilerOptions
- claude-guard.js
- context_parts.py
- cli-setup.js
- VcsPlatformPort
- PulseBatch
- OpsStateContext.tsx
- TaskBridge
- dispatch.py
- ReflexSearcher
- devDependencies
- compilerOptions
- ServiceNode.tsx
- AgentRegistry
- EphemeralProvisioner
- get_report
- gemini-sidecar/package.json
- ArchitectureGraph.tsx
- JiraIncidentAdapter
- ObservationRepository
- ShiftsPage.tsx
- catalog-skills.js
- StateWatcher
- OIDCKeyAdapter
- EscalationRepository
- entity_extractor.py
- prompt.py
- FairQueue
- generate_map.py
- KubernetesSpawnHealthAdapter
- src/ports.py
- ._discover
- ScheduleRepository
- MultiInstallationManager
- ._extract_context_flags
- TokenMeter
- ScheduleCreateRequest
- IdleTimeoutManager
- SlackAccessGate
- cortex/types.ts
- CortexLiveFeed.tsx
- telemetry.py
- testSetup.ts
- is_defer_event_available
- cortex-constants.ts
- NeuronInfoPanel.tsx
- generate_event_title
- ._github_poll_and_process
- spawn_health.py
- SpawnPollResult
- graph_recall.py
- SmartsheetMaintainerCache
- .has_reeval_signal
- AsyncGitHubClient
- GitLabTokenAuth
- _is_event_closed_or_missing
- ._evaluate_health
- HeadhunterJira
- has_unevaluated_close_blocker
- ConversationMessage
- TimeKeeperObserver
- CortexRepository
- BrainIntrospectionPort
- update_notebook_note
- scripts
- security.py
- state.js
- validate-mutations.sh
- ._process_message
- DispatchMetrics
- rename_observation
- ._wait_for_registration
- handle_report_incident
- ._publish_home_tab
- submit_feedback
- get_notebook
- TicketNode.tsx
- _has_non_user_turns
- _patch_enum_fields
- delete_observation
- require-results.sh
- TokenUsageDict
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
2. `Brain` - 151 edges
3. `ConversationTurn` - 122 edges
4. `ToolContext` - 103 edges
5. `GateContext` - 94 edges
6. `react` - 82 edges
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

## Communities (209 total, 112 thin omitted)

### Community 1 - "client.ts"
Cohesion: 0.03
Nodes (101): recharts, ApiError, bulkDeleteObservations(), deleteNote(), deleteObservation(), exportObservations(), ExtractedCorrection, ExtractedLesson (+93 more)

### Community 2 - "logging"
Cohesion: 0.04
Nodes (8): _heartbeat(), EventEvidence, _load_name_mapping(), build_manifest_table(), extract_event_links(), get_current_shift(), get_shift_detail(), list_shifts()

### Community 3 - "queue.py"
Cohesion: 0.04
Nodes (46): get_token_meter(), get_archivist(), get_brain(), aligner_pending_items(), apply_lessons(), close_event_by_user(), CloseRequest, correct_memory() (+38 more)

### Community 4 - "EventChatPanel.tsx"
Cohesion: 0.05
Nodes (72): updateEventTitle(), CiContext, ConversationTurn, TokenUsageDict, CiContextCard(), CiContextCardProps, ConsoleTailBlock(), FailedJobRow() (+64 more)

### Community 5 - "nightwatcher_tools.py"
Cohesion: 0.05
Nodes (31): record_token_usage(), PulseContext, ShiftIncident, ShiftInvestigation, ShiftReport, _env_float(), _env_int(), NightwatcherObserver (+23 more)

### Community 6 - "blackboard.py"
Cohesion: 0.04
Nodes (19): can_append_message(), require_auth(), require_obs_admin(), get_blackboard(), get_pulse_tracker(), dismiss_proposals(), DismissRequest, get_all_shadow_interventions() (+11 more)

### Community 7 - "brain.py"
Cohesion: 0.04
Nodes (32): _compute_processed_up_to(), AppNode, ChatRequest, ChatResponse, CIAnalysis, EventInput, EventMetrics, EventType (+24 more)

### Community 8 - "tool_gates.py"
Cohesion: 0.05
Nodes (78): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+70 more)

### Community 11 - "EventDocument"
Cohesion: 0.03
Nodes (4): _init_tool_names(), _strip_tool_names(), _wrap_section(), EventDocument

### Community 12 - "merge-guard.js"
Cohesion: 0.05
Nodes (69): analyzeString(), analyzeTokens(), API_VALUED, apiTokens(), apiWriteNeedsGuard(), assignName(), bareBranchProtected(), base() (+61 more)

### Community 13 - "hooks/index.ts"
Cohesion: 0.06
Nodes (46): react-router-dom, @tanstack/react-query, createChatEvent(), getConfig(), getEvents(), AppConfig, ActivityStream(), ChatInput() (+38 more)

### Community 14 - "dependencies.py"
Cohesion: 0.04
Nodes (21): get_aligner(), get_architect(), get_argocd_observer(), get_developer(), get_kargo_observer(), get_kg_store(), get_report_client(), get_sysadmin() (+13 more)

### Community 15 - "App.tsx"
Cohesion: 0.06
Nodes (50): oidc-client-ts, react-dom, dismissProposals(), EnhancementProposal, getHandoffReports(), getIncidents(), getProposals(), getWSAuthFailureCallback() (+42 more)

### Community 16 - "http-handler.js"
Cohesion: 0.09
Nodes (58): resolveCommand(), writeAgyMcpServer(), writeClaudeMcpServer(), buildArgoCDMcpConfig(), createAppJWT(), discoverAndGenerateTokens(), _discoverAndGenerateTokensInner(), discoverInstallations() (+50 more)

### Community 17 - "colors.ts"
Cohesion: 0.07
Nodes (39): getReport(), getReports(), ReportFull, ReportMeta, CompactCardStrip(), EventHistory(), TimeRange, ViewMode (+31 more)

### Community 18 - "react"
Cohesion: 0.08
Nodes (53): lucide-react, react, applyLessons(), correctMemory(), createKnowledge(), createLesson(), deleteKnowledge(), deleteLesson() (+45 more)

### Community 19 - "._run_agent_task"
Cohesion: 0.06
Nodes (9): on_huddle(), on_progress(), on_huddle(), on_progress(), _is_automated_nudge(), _sanitize_error_text(), _sanitize_override_reason(), _select_dispatch_tier() (+1 more)

### Community 20 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 21 - "GeminiAdapter"
Cohesion: 0.06
Nodes (8): ClaudeAdapter, _extract_call_syntax(), GeminiAdapter, FunctionCall, LLMChunk, LLMPort, LLMResponse, TokenUsage

### Community 22 - "ReconcileScheduler"
Cohesion: 0.05
Nodes (7): FlowSnapshot, FlowCollector, ReconcileScheduler, Trigger, QueueTrigger, ResyncTrigger, StalenessGuard

### Community 23 - "Service"
Cohesion: 0.05
Nodes (10): GraphResponse, Service, get_event_document(), get_graph_data(), get_mermaid_diagram(), get_service_details(), get_topology(), list_services() (+2 more)

### Community 24 - "EventSidebar.tsx"
Cohesion: 0.08
Nodes (52): getJiraMissions(), HeadhunterTodo, postJiraAction(), JenkinsPendingItem, JiraMission, ACTION_BADGE, formatAge(), HeadhunterQueuePanel() (+44 more)

### Community 25 - "JenkinsObserver"
Cohesion: 0.05
Nodes (4): _flood_service_key(), JenkinsObserver, _outage_service_key(), _service_key()

### Community 26 - "os"
Cohesion: 0.07
Nodes (12): _sanitize_lesson_text(), _get_static_maintainer_emails(), _get_allowed_mention_authors(), _get_static_maintainer_emails(), _safe_int(), create_adapter(), get_gitlab_auth(), sanitize_title() (+4 more)

### Community 28 - "ToolContext"
Cohesion: 0.08
Nodes (12): handle_message_agent(), handle_reply_to_agent(), handle_select_agent(), _sticky_work_style(), handle_classify_event(), handle_defer_event(), handle_hold_watch(), handle_request_user_approval() (+4 more)

### Community 29 - "main.py"
Cohesion: 0.05
Nodes (15): agent_ws_endpoint(), api_info(), get_config(), get_event_flow(), get_flow_history(), get_flow_metrics(), health_check(), list_agents() (+7 more)

### Community 30 - "TurnBubble.tsx"
Cohesion: 0.09
Nodes (38): @uiw/react-markdown-preview, approveEvent(), closeEvent(), enforceCasualDomain(), rejectEvent(), submitFeedback(), ConversationFeed(), ConversationFeedProps (+30 more)

### Community 32 - "ConversationTurn"
Cohesion: 0.13
Nodes (31): emit_tool_result(), handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_recall_pruned_turns(), handle_ask_release_ai(), handle_comment_jira_issue(), handle_fetch_jira_issue() (+23 more)

### Community 33 - "cli-executor.js"
Cohesion: 0.09
Nodes (36): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS, STORAGE_PRETASK_TIMEOUT_MS, resolveStorageRoot }, buildCLICommand(), { checkAndRecycleStorage, pinTaskCwd, unpinTaskCwd }, CLAUDE_JSON_PATH, cp, executeCLI(), executeCLIStreaming(), FALLBACK_MODEL (+28 more)

### Community 34 - "handlers_integration.py"
Cohesion: 0.08
Nodes (18): _alert_wrapper_retrigger(), _do_retrigger(), _get_jira_reporter(), handle_refresh_github_context(), handle_refresh_gitlab_context(), handle_refresh_kargo_context(), _is_darwin_reentrant_caller(), jenkins_retrigger_cooldown_key() (+10 more)

### Community 35 - "storage-recycler.js"
Cohesion: 0.08
Nodes (34): withTaskStorage(), resolveStorageRoot(), ROLE_TIMEOUTS, STORAGE_ACTIVITY_HEARTBEAT_MS, STORAGE_MAX_TIER3_DELETIONS, STORAGE_PRETASK_TIMEOUT_MS, STORAGE_RESULTS_TTL_MS, STORAGE_STALE_MS (+26 more)

### Community 36 - "UserContext"
Cohesion: 0.06
Nodes (16): can_approve_event(), can_override_domain(), can_rename_event(), _claims_to_user(), get_user_from_request(), get_user_from_websocket(), _normalize_email(), resolve_approval_identity() (+8 more)

### Community 37 - "JenkinsAdapter"
Cohesion: 0.06
Nodes (6): BuildDetails, JenkinsAdapter, JenkinsPlatformPort, JobResult, JobRunState, ViewScanResult

### Community 39 - "agents/__init__.py"
Cohesion: 0.07
Nodes (4): Architect, AgentClient, Developer, SysAdmin

### Community 40 - "types.py"
Cohesion: 0.07
Nodes (9): _parse_drain_timeout(), QuotaExhaustedError, QuotaTracker, RequestExceedsBurstError, Reservation, derive_llm_priority(), process_stream_call_syntax_buffer(), sanitize_call_syntax() (+1 more)

### Community 42 - "httpx"
Cohesion: 0.10
Nodes (15): _adf_to_text(), approve_mission(), dismiss_mission(), _infer_phase(), _jira_config(), list_missions(), reanalyze_mission(), retry_mission() (+7 more)

### Community 43 - "formatter.py"
Cohesion: 0.08
Nodes (17): build_home_tab_view(), _context_line(), create_feedback_block(), extract_tables(), _replace(), format_event_summary(), format_plan_block(), format_task_card() (+9 more)

### Community 45 - "jenkins_observer.py"
Cohesion: 0.08
Nodes (14): _annotation_replace(), _strip_pipeline_annotations(), _clamp_confidence(), _env_flag(), _parse_job_metadata(), _prepare_console_tail(), _redact_build_parameters(), _redact_match() (+6 more)

### Community 46 - "SlackChannel"
Cohesion: 0.08
Nodes (3): get_agent_notification_text(), get_turn_attachment_color(), SlackChannel

### Community 49 - "TimeKeeperPage.tsx"
Cohesion: 0.12
Nodes (24): createSchedule(), deleteSchedule(), getSchedules(), refineInstructions(), ScheduleCreatePayload, ScheduleItem, toggleSchedule(), updateSchedule() (+16 more)

### Community 50 - "observations_mgmt.py"
Cohesion: 0.09
Nodes (15): _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), render_pdf(), _sample_points(), _summarize() (+7 more)

### Community 51 - "KnowledgeGraphStore"
Cohesion: 0.11
Nodes (6): get_graph_context(), translate_to_lookups(), _acquire(), KnowledgeGraphStore, _sanitize(), _with_timeout()

### Community 52 - "ActiveStreamsContext.tsx"
Cohesion: 0.12
Nodes (27): AgentStreamCard(), AgentStreamCardProps, FloatingWindow(), MessageCards(), Dashboard(), GridTile(), GridTileProps, TileType (+19 more)

### Community 53 - "ws-client.js"
Cohesion: 0.09
Nodes (26): is429Error(), {
  DEFAULT_WORK_DIR, AGENT_CLI, AGENT_MODEL, AGENT_ROLE,
  EVENT_ID, EPHEMERAL, IDLE_TIMEOUT_MS,
  CLI_429_MAX_RETRIES, CLI_429_INITIAL_DELAY_MS, CLI_429_BACKOFF_MULTIPLIER,
}, { ensureEventDocument }, { executeCLIStreaming, prepareResultsDir, is429Error }, { filterSkillsByRole, filterSkillsByMode, swapActiveRules, restoreAllSkills }, fs, handleCancel(), resetTimer() (+18 more)

### Community 54 - "create_schedule"
Cohesion: 0.06
Nodes (6): create_schedule(), delete_schedule(), get_schedule(), list_schedules(), toggle_schedule(), update_schedule()

### Community 55 - "spawn_event_namer_task"
Cohesion: 0.13
Nodes (10): spawn_event_namer_task(), get_user_from_slack(), handle_app_mention(), handle_approve(), handle_create_event_modal(), handle_darwin_command(), handle_home_create_event(), handle_reject() (+2 more)

### Community 56 - "ui/package.json"
Cohesion: 0.08
Nodes (29): autoprefixer, cronstrue, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, graphology-layout-forceatlas2 (+21 more)

### Community 57 - "DashboardWSAdapter"
Cohesion: 0.11
Nodes (5): DashboardWSAdapter, prompt_display_name(), ChatEventRequest, ChatEventResponse, create_chat_event()

### Community 58 - "useCortexData.ts"
Cohesion: 0.17
Nodes (27): getCognitiveGraph(), getCortexActivity(), getEventReport(), getKGServiceDetail(), getKGServices(), getKGStats(), getKnowledgeById(), getMemory() (+19 more)

### Community 59 - "server.js"
Cohesion: 0.08
Nodes (18): hasRegistryCredentials(), { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, fs, path, stageEventDocument(), fetchEventDocument(), fs, { handleRequest } (+10 more)

### Community 60 - "EventDrillDown.tsx"
Cohesion: 0.13
Nodes (23): three, getEventPulses(), BrainCore(), CortexDevPage(), devQueryClient, CortexLiveFeedProps, EventDrillDown(), EventDrillDownProps (+15 more)

### Community 61 - "TopologyRepository"
Cohesion: 0.08
Nodes (3): Snapshot, TopologySnapshot, TopologyRepository

### Community 63 - "CortexGraph.tsx"
Cohesion: 0.15
Nodes (24): graphology, eventColor(), getExecutiveNeurons(), getStructuralEdges(), DEFAULT_TYPE_BUDGET, evictLru(), KNOWLEDGE_RING, KNOWLEDGE_RING_TYPES (+16 more)

### Community 64 - ".list_observations"
Cohesion: 0.08
Nodes (4): get_all_journal(), get_service_journal(), get_event_observations(), get_global_observations()

### Community 65 - "VectorStore"
Cohesion: 0.11
Nodes (3): _decode_cursor(), _encode_cursor(), VectorStore

### Community 67 - "tool_router.py"
Cohesion: 0.09
Nodes (5): _safe_int(), handle_google_web_search(), IdleTimeoutPort, IncidentAdapterPort, StateWatcherPort

### Community 69 - "useQueue.ts"
Cohesion: 0.14
Nodes (22): getActiveEvents(), getAlignerPending(), getEventDocument(), getHeadhunterPending(), getJenkinsPending(), getWaitingApprovalEvents(), EventDocument, MessageStatus (+14 more)

### Community 70 - "NodeInspector.tsx"
Cohesion: 0.13
Nodes (22): getClosedEvents(), ArchitectureEvent, ArgoCDOperation, EVENT_LABELS, EventItem(), EventItemProps, healthTone(), lastOperationSummary() (+14 more)

### Community 71 - "reconcile.py"
Cohesion: 0.15
Nodes (10): sanitize_redis_port(), _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers(), main() (+2 more)

### Community 75 - "state/ports.py"
Cohesion: 0.11
Nodes (3): ArchitectureEvent, list_events(), MetricsRepository

### Community 77 - "GitHubAppAuth"
Cohesion: 0.11
Nodes (3): _find_pem_file(), get_github_auth(), GitHubAppAuth

### Community 78 - "dependencies"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 79 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 80 - "claude-guard.js"
Cohesion: 0.14
Nodes (18): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+10 more)

### Community 81 - "context_parts.py"
Cohesion: 0.11
Nodes (9): _apply_sibling_signature(), build_function_response(), build_single_function_response(), compress_contents(), estimate_msg_tokens(), estimate_tokens(), extract_model_parts(), normalize_response_parts() (+1 more)

### Community 82 - "cli-setup.js"
Cohesion: 0.13
Nodes (19): { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync }, filterSkillsByMode() (+11 more)

### Community 85 - "PulseBatch"
Cohesion: 0.12
Nodes (4): PulseBatch, PulsePort, PulseObserver, PulseTracker

### Community 86 - "OpsStateContext.tsx"
Cohesion: 0.16
Nodes (18): getAgents(), getKargoStages(), AgentRegistryEntry, EventEvidence, KargoStageStatus, AgentRegistryPanel(), formatConnectedSince(), AgentGroups (+10 more)

### Community 87 - "TaskBridge"
Cohesion: 0.13
Nodes (3): agent_websocket_handler(), send_cancel(), TaskBridge

### Community 88 - "dispatch.py"
Cohesion: 0.15
Nodes (9): _build_prompt(), _check_security(), consume_wake_task(), _consume(), _dispatch_timeout_s(), dispatch_to_agent(), _consume_queue(), _sanitize_stdout() (+1 more)

### Community 90 - "devDependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 91 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 92 - "ServiceNode.tsx"
Cohesion: 0.15
Nodes (13): @xyflow/react, HealthStatus, NodeType, AppNodeData, ARGOCD_HEALTH_COLORS, SYNC_ICONS, NamespaceGroupNodeData, GENERIC_TAGS (+5 more)

### Community 95 - "get_report"
Cohesion: 0.11
Nodes (6): get_report(), list_reports(), reports_spa_no_slash(), reports_spa_with_slash(), search_reports(), _serve_spa()

### Community 96 - "gemini-sidecar/package.json"
Cohesion: 0.11
Nodes (17): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+9 more)

### Community 97 - "ArchitectureGraph.tsx"
Cohesion: 0.17
Nodes (16): @dagrejs/dagre, applyDagreLayout(), applyGridLayout(), applyLayout(), ArchitectureGraph(), ArchitectureGraphInner(), buildGraph(), computeIdHash() (+8 more)

### Community 101 - "ShiftsPage.tsx"
Cohesion: 0.23
Nodes (16): getCurrentShift(), getShiftDetail(), getShiftsList(), ShiftReportFull, ShiftReportSummary, FailedClusterBadge(), getISOWeek(), getWeekDates() (+8 more)

### Community 102 - "catalog-skills.js"
Cohesion: 0.16
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 103 - "StateWatcher"
Cohesion: 0.16
Nodes (3): _QueueEntry, StateWatcher, _Subscription

### Community 106 - "entity_extractor.py"
Cohesion: 0.17
Nodes (7): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship, KargoStageSnapshot, list_failed_stages()

### Community 107 - "prompt.py"
Cohesion: 0.21
Nodes (10): _build_closed_block(), build_event_header(), _build_identity_block(), _build_journal_block(), _build_mermaid_block(), _build_related_block(), _build_subject_block(), _build_timing_block() (+2 more)

### Community 109 - "generate_map.py"
Cohesion: 0.19
Nodes (6): _enumerate_gates(), _GateInfo, generate_phase_tool_map(), _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 117 - "._extract_context_flags"
Cohesion: 0.15
Nodes (3): compute_dispatch_backpressure(), ContextFlags, _safe_int_env()

### Community 125 - "cortex/types.ts"
Cohesion: 0.21
Nodes (10): EventSource, PulseTimelineProps, CognitiveGraphResponse, CortexHeartbeatMessage, FrictionIndicator, FrictionPattern, NeuronVisual, Pulse (+2 more)

### Community 126 - "CortexLiveFeed.tsx"
Cohesion: 0.24
Nodes (10): CortexHeartbeat(), CortexHeartbeatProps, ensureKeyframes(), CortexLiveFeed(), FILTER_PILLS, FilterKey, getStoredFilter(), MESSAGE_STYLES (+2 more)

### Community 127 - "telemetry.py"
Cohesion: 0.22
Nodes (3): get_quota_tracker(), llm_stats(), receive_telemetry()

### Community 128 - "testSetup.ts"
Cohesion: 0.18
Nodes (5): @tailwindcss/vite, @testing-library/react, vite, @vitejs/plugin-react, vitest

### Community 129 - "is_defer_event_available"
Cohesion: 0.18
Nodes (6): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 130 - "cortex-constants.ts"
Cohesion: 0.18
Nodes (10): AGENTS, DOMAINS, HEMISPHERE_X, NEURON_DESCRIPTIONS, PHASE_SKILL_FOLDERS, PHASE_TOOL_PRIORITY, PHASES, StructuralEdge (+2 more)

### Community 131 - "NeuronInfoPanel.tsx"
Cohesion: 0.29
Nodes (10): asNumber(), asString(), asStringArray(), Badge(), describeNeuron(), Hdr(), NeuronInfoPanel(), AGENT_NEURON_COLORS (+2 more)

### Community 132 - "generate_event_title"
Cohesion: 0.22
Nodes (3): generate_event_title(), get_adapter(), _get_semaphore()

### Community 136 - "graph_recall.py"
Cohesion: 0.33
Nodes (3): _format_graph_context(), _parse_props(), _sanitize()

### Community 145 - "has_unevaluated_close_blocker"
Cohesion: 0.25
Nodes (4): has_unevaluated_close_blocker(), _pred_jarvis_response(), _pred_unevaluated_close(), is_jarvis_acknowledgment()

### Community 151 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 153 - "state.js"
Cohesion: 0.33
Nodes (4): { AGENT_ROLE }, _blackboardTurns, _inboundMessages, _teammateMessages

### Community 154 - "validate-mutations.sh"
Cohesion: 0.73
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

### Community 171 - "TicketNode.tsx"
Cohesion: 0.40
Nodes (4): STATUS_COLORS, TICKET_COLORS, TicketNodeComponent(), TicketNodeData

## Knowledge Gaps
- **13 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+8 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2195 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **112 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `logging`, `queue.py`, `generate_event_title`, `nightwatcher_tools.py`, `blackboard.py`, `brain.py`, `Brain`, `EventDocument`, `_is_event_closed_or_missing`, `dependencies.py`, `HeadhunterJira`, `ConversationMessage`, `update_notebook_note`, `Service`, `ReconcileScheduler`, `os`, `ToolContext`, `main.py`, `ConversationTurn`, `rename_observation`, `._restage_pending_signal`, `UserContext`, `._stage_pending_signal`, `submit_feedback`, `get_notebook`, `httpx`, `._count_pending`, `.__init__`, `jenkins_observer.py`, `delete_observation`, `observations_mgmt.py`, `._get_app_nodes`, `.get_edge_metadata`, `create_schedule`, `report_tampering`, `DashboardWSAdapter`, `TopologyRepository`, `LiveAPIAdapter`, `.list_observations`, `tool_router.py`, `state/ports.py`, `get_report`, `ScheduleRepository`?**
  _High betweenness centrality (0.139) - this node is a cross-community bridge._
- **Are the 80 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 80 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.01579520697167756 - nodes in this community are weakly interconnected._
- **Why does `Brain` connect `Brain` to `BlackboardState`, `logging`, `brain.py`, `EventDocument`, `dependencies.py`, `._run_agent_task`, `ReconcileScheduler`, `os`, `ToolContext`, `main.py`, `ConversationTurn`, `agents/__init__.py`, `types.py`, `._process_with_llm`, `.__init__`, `.next_turn_number`, `DashboardWSAdapter`, `._close_and_broadcast`, `._build_contents`, `BrainSkillLoader`, `PulseBatch`, `ReflexSearcher`, `src/ports.py`, `._extract_context_flags`, `IdleTimeoutManager`?**
  _High betweenness centrality (0.072) - this node is a cross-community bridge._
- **Are the 21 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 21 INFERRED edges - model-reasoned connections that need verification._
- **Should `client.ts` be split into smaller, more focused modules?**
  _Cohesion score 0.030566420396928872 - nodes in this community are weakly interconnected._