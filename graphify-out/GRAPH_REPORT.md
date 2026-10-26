# Graph Report - Blackboard  (2026-10-26)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 4825 nodes · 10718 edges · 192 communities (99 shown, 93 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 903 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `6044c30a`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BlackboardState
- logging
- client.ts
- lucide-react
- EventDocument
- Brain
- tool_gates.py
- models.py
- merge-guard.js
- react
- SlackChannel
- queue.py
- colors.ts
- ReconcileScheduler
- brain.py
- cognitive_graph.py
- ._run_agent_task
- topology.py
- jenkins-mcp.js
- dependencies.py
- HeadhunterJira
- fetchApi
- EventSidebar.tsx
- App.tsx
- AgentRegistry
- Aligner
- GitHubPlatform
- hooks/index.ts
- slack.py
- _BrainToolContext
- GitLabPlatform
- ._process_with_llm
- routes/timekeeper.py
- credentials.js
- Headhunter
- JenkinsObserver
- jenkins_observer.py
- CortexGraph.tsx
- EventRepository
- cli-executor.js
- JenkinsAdapter
- auth.py
- .get_event
- ToolContext
- httpx
- lifespan
- ConversationTurn
- TimeKeeperPage.tsx
- main.py
- EventDrillDown.tsx
- ActiveStreamsContext.tsx
- OpsStateContext.tsx
- ws-client.js
- ui/package.json
- useCortexData.ts
- DashboardWSAdapter
- KubernetesSpawnHealthAdapter
- KnowledgeGraphStore
- http-handler.js
- server.js
- LiveAPIAdapter
- StateWatcher
- adf_to_markdown
- handlers_integration.py
- GeminiAdapter
- nightwatcher_tools.py
- ._build_contents
- ArgoCDObserver
- llm/__init__.py
- observations_mgmt.py
- BrainSkillLoader
- nightwatcher.py
- KargoObserver
- TopologyRepository
- dependencies
- reconcile.py
- EphemeralProvisioner
- compilerOptions
- TokenUtilizationPage.tsx
- GitHubAppAuth
- cli-setup.js
- ArchitectureGraph.tsx
- VcsPlatformPort
- PulseBatch
- ephemeral_provisioner.py
- claude-guard.js
- scheduling/__init__.py
- ._build_system_prompt
- ReflexSearcher
- redis_client.py
- devDependencies
- compilerOptions
- get_report
- gemini-sidecar/package.json
- ObservationRepository
- ShiftsPage.tsx
- ConversationTurn
- catalog-skills.js
- OIDCKeyAdapter
- Archivist
- ClaudeAdapter
- VectorStore
- list_active_events
- observations_reporter.py
- generate_map.py
- IdleTimeoutManager
- src/ports.py
- ._discover
- EscalationRepository
- ServiceNode.tsx
- QuotaTracker
- ScheduleRepository
- MultiInstallationManager
- .scroll
- get_graph_context
- TokenMeter
- IncidentAdapterPort
- NightwatcherObserver
- .enqueue
- SlackAccessGate
- telemetry.py
- is_defer_event_available
- SecurityError
- vite.config.ts
- entity_extractor.py
- handle_report_incident
- has_unevaluated_close_blocker
- knowledge_graph_api.py
- CortexDevPage.tsx
- NeuronInfoPanel.tsx
- SmartsheetMaintainerCache
- AsyncGitHubClient
- GitLabTokenAuth
- _is_event_closed_or_missing
- TimeKeeperObserver
- CortexRepository
- BrainIntrospectionPort
- get_all_journal
- update_notebook_note
- scripts
- validate-mutations.sh
- ._process_message
- dex_proxy
- BrainCore
- get_notebook
- list_incidents
- delete_notebook_note
- CortexHeartbeat.tsx
- require-results.sh
- _walk_adf_mentions
- TokenUsageDict
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
1. `BlackboardState` - 279 edges
2. `Brain` - 148 edges
3. `ConversationTurn` - 122 edges
4. `ToolContext` - 102 edges
5. `GateContext` - 94 edges
6. `react` - 79 edges
7. `EventDocument` - 78 edges
8. `fetchApi()` - 65 edges
9. `lifespan()` - 64 edges
10. `LiveAPIAdapter` - 58 edges

## Surprising Connections (you probably didn't know these)
- `EventRepository` --uses--> `ConversationMessage`  [INFERRED]
  src/state/ports.py → src/models.py
- `get_flow_history()` --uses--> `FlowSnapshot`  [INFERRED]
  src/main.py → src/models.py
- `FlowCollector` --uses--> `FlowSnapshot`  [INFERRED]
  src/observers/flow_collector.py → src/models.py
- `DashboardWSAdapter` --uses--> `BlackboardState`  [INFERRED]
  src/adapters/dashboard_ws.py → src/state/blackboard.py
- `LiveAPIAdapter` --uses--> `BlackboardState`  [INFERRED]
  src/adapters/live_api_adapter.py → src/state/blackboard.py

## Import Cycles
- None detected.

## Communities (192 total, 93 thin omitted)

### Community 0 - "BlackboardState"
Cohesion: 0.01
Nodes (6): AppNode, ConversationMessage, FlowSnapshot, jenkins_pending_items(), get_shift_detail(), BlackboardState

### Community 1 - "logging"
Cohesion: 0.04
Nodes (15): _heartbeat(), _sanitize_lesson_text(), _get_static_maintainer_emails(), _get_allowed_mention_authors(), _get_static_maintainer_emails(), _safe_int(), create_adapter(), record_token_usage() (+7 more)

### Community 2 - "client.ts"
Cohesion: 0.03
Nodes (95): bulkDeleteObservations(), deleteNote(), deleteObservation(), exportObservations(), ExtractedCorrection, ExtractedLesson, ExtractionResult, generateObservationsReport() (+87 more)

### Community 3 - "lucide-react"
Cohesion: 0.05
Nodes (67): lucide-react, react-router-dom, ChatInput(), ChatInputProps, Draft, LastSubmission, ErrorBoundary, ErrorBoundaryProps (+59 more)

### Community 4 - "EventDocument"
Cohesion: 0.03
Nodes (15): _build_closed_block(), build_event_header(), _build_identity_block(), _build_journal_block(), _build_mermaid_block(), _build_related_block(), _build_subject_block(), _build_timing_block() (+7 more)

### Community 6 - "tool_gates.py"
Cohesion: 0.05
Nodes (78): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+70 more)

### Community 7 - "models.py"
Cohesion: 0.04
Nodes (24): _safe_int(), ArchitectureEvent, ChatRequest, ChatResponse, EventMetrics, EventStatus, EventType, FlowMetricsResponse (+16 more)

### Community 8 - "merge-guard.js"
Cohesion: 0.05
Nodes (69): analyzeString(), analyzeTokens(), API_VALUED, apiTokens(), apiWriteNeedsGuard(), assignName(), bareBranchProtected(), base() (+61 more)

### Community 9 - "react"
Cohesion: 0.07
Nodes (53): react, @uiw/react-markdown-preview, approveEvent(), closeEvent(), enforceCasualDomain(), getEventReport(), rejectEvent(), submitFeedback() (+45 more)

### Community 10 - "SlackChannel"
Cohesion: 0.06
Nodes (11): get_user_from_slack(), format_event_summary(), SlackChannel, handle_app_home_opened(), handle_app_mention(), handle_approve(), handle_create_event_modal(), handle_darwin_command() (+3 more)

### Community 11 - "queue.py"
Cohesion: 0.05
Nodes (32): get_archivist(), aligner_pending_items(), apply_lessons(), correct_memory(), CorrectMemoryRequest, create_knowledge(), create_lesson(), delete_knowledge() (+24 more)

### Community 12 - "colors.ts"
Cohesion: 0.07
Nodes (42): @tanstack/react-query, @tanstack/react-table, getReport(), getReports(), ReportFull, ReportMeta, CompactCardStrip(), EventHistory() (+34 more)

### Community 13 - "ReconcileScheduler"
Cohesion: 0.04
Nodes (7): FlowCollector, FairQueue, ReconcileScheduler, Trigger, QueueTrigger, ResyncTrigger, StalenessGuard

### Community 14 - "brain.py"
Cohesion: 0.05
Nodes (22): _close_unanswered_fc(), _apply_sibling_signature(), build_function_response(), build_single_function_response(), compress_contents(), estimate_msg_tokens(), estimate_tokens(), extract_model_parts() (+14 more)

### Community 15 - "cognitive_graph.py"
Cohesion: 0.05
Nodes (17): get_blackboard(), get_brain(), get_pulse_tracker(), dismiss_proposals(), DismissRequest, get_all_shadow_interventions(), get_cognitive_graph(), get_cortex_activity() (+9 more)

### Community 16 - "._run_agent_task"
Cohesion: 0.06
Nodes (9): on_huddle(), on_progress(), on_huddle(), on_progress(), _compute_processed_up_to(), _has_non_user_turns(), _is_seed_turn(), _sanitize_error_text() (+1 more)

### Community 17 - "topology.py"
Cohesion: 0.04
Nodes (12): GraphNode, GraphResponse, Snapshot, TicketNode, TopologySnapshot, get_graph_data(), get_mermaid_diagram(), get_service_details() (+4 more)

### Community 18 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 19 - "dependencies.py"
Cohesion: 0.05
Nodes (11): Architect, AgentClient, Developer, SysAdmin, get_aligner(), get_architect(), get_argocd_observer(), get_developer() (+3 more)

### Community 21 - "fetchApi"
Cohesion: 0.08
Nodes (49): applyLessons(), correctMemory(), createKnowledge(), createLesson(), deleteKnowledge(), deleteLesson(), extractLessons(), fetchApi() (+41 more)

### Community 22 - "EventSidebar.tsx"
Cohesion: 0.09
Nodes (48): getHeadhunterPending(), getJiraMissions(), HeadhunterTodo, postJiraAction(), ACTION_BADGE, formatAge(), HeadhunterQueuePanel(), renderItem() (+40 more)

### Community 23 - "App.tsx"
Cohesion: 0.07
Nodes (41): oidc-client-ts, react-dom, getConfig(), getIncidents(), getWSAuthFailureCallback(), Incident, setOnUnauthorized(), setTokenGetter() (+33 more)

### Community 24 - "AgentRegistry"
Cohesion: 0.06
Nodes (13): AgentConnection, AgentRegistry, agent_websocket_handler(), _build_prompt(), consume_wake_task(), _consume(), _dispatch_timeout_s(), dispatch_to_agent() (+5 more)

### Community 26 - "GitHubPlatform"
Cohesion: 0.06
Nodes (3): GitHubPlatform, _poll_one(), _poll_one()

### Community 27 - "hooks/index.ts"
Cohesion: 0.07
Nodes (38): ApiError, createChatEvent(), getClosedEvents(), getEvents(), getService(), getTopology(), ArchitectureEvent, ArgoCDOperation (+30 more)

### Community 28 - "slack.py"
Cohesion: 0.06
Nodes (19): build_access_denied_home_view(), build_home_tab_view(), _context_line(), create_feedback_block(), extract_tables(), _replace(), format_plan_block(), format_task_card() (+11 more)

### Community 31 - "._process_with_llm"
Cohesion: 0.04
Nodes (3): _BatchContext, compute_dispatch_backpressure(), _safe_int_env()

### Community 32 - "routes/timekeeper.py"
Cohesion: 0.06
Nodes (8): ScheduleCreateRequest, create_schedule(), delete_schedule(), get_schedule(), list_schedules(), _load_brain_context(), toggle_schedule(), update_schedule()

### Community 33 - "credentials.js"
Cohesion: 0.13
Nodes (44): resolveCommand(), writeAgyMcpServer(), writeClaudeMcpServer(), buildArgoCDMcpConfig(), createAppJWT(), discoverAndGenerateTokens(), _discoverAndGenerateTokensInner(), discoverInstallations() (+36 more)

### Community 34 - "Headhunter"
Cohesion: 0.06
Nodes (3): Headhunter, _raise_if_systemic_failure(), _sanitize_xml_fence()

### Community 36 - "jenkins_observer.py"
Cohesion: 0.07
Nodes (15): _annotation_replace(), _strip_pipeline_annotations(), _clamp_confidence(), _env_flag(), _parse_job_metadata(), _prepare_console_tail(), _redact_build_parameters(), _redact_match() (+7 more)

### Community 37 - "CortexGraph.tsx"
Cohesion: 0.08
Nodes (40): graphology, KGServiceEntity, AGENTS, DOMAINS, eventColor(), getExecutiveNeurons(), getStructuralEdges(), HEMISPHERE_X (+32 more)

### Community 39 - "cli-executor.js"
Cohesion: 0.09
Nodes (35): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS }, buildCLICommand(), CLAUDE_JSON_PATH, cp, executeCLI(), executeCLIStreaming(), FALLBACK_MODEL, fs (+27 more)

### Community 40 - "JenkinsAdapter"
Cohesion: 0.06
Nodes (6): BuildDetails, JenkinsAdapter, JenkinsPlatformPort, JobResult, JobRunState, ViewScanResult

### Community 41 - "auth.py"
Cohesion: 0.08
Nodes (14): can_append_message(), can_approve_event(), can_override_domain(), _claims_to_user(), get_user_from_request(), get_user_from_websocket(), _normalize_email(), require_auth() (+6 more)

### Community 42 - ".get_event"
Cohesion: 0.06
Nodes (9): get_token_meter(), FeedbackRequest, submit_feedback(), get_event_observations(), get_global_observations(), close_event_by_user(), CloseRequest, get_event_document() (+1 more)

### Community 43 - "ToolContext"
Cohesion: 0.10
Nodes (9): handle_message_agent(), handle_reply_to_agent(), handle_select_agent(), handle_close_event(), handle_defer_event(), handle_hold_watch(), handle_wait_for_agent(), handle_wait_for_jarvis() (+1 more)

### Community 44 - "httpx"
Cohesion: 0.09
Nodes (12): approve_mission(), dismiss_mission(), _infer_phase(), _jira_config(), list_missions(), reanalyze_mission(), retry_mission(), get_gitlab_auth() (+4 more)

### Community 45 - "lifespan"
Cohesion: 0.06
Nodes (8): set_incident_options(), set_agents(), set_archivist(), set_argocd_observer(), set_blackboard(), set_brain(), set_kargo_observer(), lifespan()

### Community 46 - "ConversationTurn"
Cohesion: 0.16
Nodes (21): emit_tool_result(), handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_recall_pruned_turns(), handle_consult_deep_memory(), handle_google_web_search(), handle_lookup_journal() (+13 more)

### Community 47 - "TimeKeeperPage.tsx"
Cohesion: 0.12
Nodes (24): createSchedule(), deleteSchedule(), getSchedules(), refineInstructions(), ScheduleCreatePayload, ScheduleItem, toggleSchedule(), updateSchedule() (+16 more)

### Community 48 - "main.py"
Cohesion: 0.08
Nodes (14): set_kg_store(), set_pulse_tracker(), agent_ws_endpoint(), api_info(), get_config(), get_event_flow(), get_flow_history(), get_flow_metrics() (+6 more)

### Community 49 - "EventDrillDown.tsx"
Cohesion: 0.12
Nodes (29): getEventPulses(), EventSource, CortexDevPage(), CortexLiveFeed(), CortexLiveFeedProps, FILTER_PILLS, FilterKey, getStoredFilter() (+21 more)

### Community 50 - "ActiveStreamsContext.tsx"
Cohesion: 0.13
Nodes (26): AgentStreamCard(), AgentStreamCardProps, FloatingWindow(), MessageCards(), Dashboard(), GridTile(), GridTileProps, TileType (+18 more)

### Community 51 - "OpsStateContext.tsx"
Cohesion: 0.11
Nodes (27): dismissProposals(), EnhancementProposal, getAgents(), getHandoffReports(), getKargoStages(), getProposals(), HandoffReport, AgentRegistryEntry (+19 more)

### Community 52 - "ws-client.js"
Cohesion: 0.10
Nodes (24): is429Error(), {
  DEFAULT_WORK_DIR, AGENT_CLI, AGENT_MODEL, AGENT_ROLE,
  EVENT_ID, EPHEMERAL, IDLE_TIMEOUT_MS,
  CLI_429_MAX_RETRIES, CLI_429_INITIAL_DELAY_MS, CLI_429_BACKOFF_MULTIPLIER,
}, { ensureEventDocument }, { executeCLIStreaming, prepareResultsDir, is429Error }, { filterSkillsByRole, filterSkillsByMode, swapActiveRules, restoreAllSkills }, handleCancel(), resetTimer(), {
  hasGitHubCredentials, discoverAndGenerateTokens, setupGitCredentials, setupGitHubTooling,
  hasGitLabCredentials, readGitLabToken, setupGitLabCredentials, setupGitLabTooling,
  setupArgoCDMCP, setupCLILogins, setupRemoteK8sMCPs, setupRegistryCredentials, GITLAB_HOST,
  hasJenkinsCredentials, setupJenkinsMCP, hasGoogleServiceAccount, setupGoogleAuthForAgy,
} (+16 more)

### Community 53 - "ui/package.json"
Cohesion: 0.08
Nodes (28): autoprefixer, cronstrue, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, graphology-layout-forceatlas2 (+20 more)

### Community 55 - "useCortexData.ts"
Cohesion: 0.17
Nodes (26): getCognitiveGraph(), getCortexActivity(), getKGServiceDetail(), getKGServices(), getKGStats(), getKnowledgeById(), getMemory(), getRecentPulses() (+18 more)

### Community 56 - "DashboardWSAdapter"
Cohesion: 0.12
Nodes (5): DashboardWSAdapter, prompt_display_name(), ChatEventRequest, ChatEventResponse, create_chat_event()

### Community 57 - "KubernetesSpawnHealthAdapter"
Cohesion: 0.10
Nodes (3): KubernetesSpawnHealthAdapter, SpawnHealthPort, SpawnPollResult

### Community 58 - "KnowledgeGraphStore"
Cohesion: 0.15
Nodes (4): _acquire(), KnowledgeGraphStore, _sanitize(), _with_timeout()

### Community 59 - "http-handler.js"
Cohesion: 0.08
Nodes (21): ROLE_TIMEOUTS, SUPPORTED_AGENT_CLIS, getRemoteClustersMeta(), { AGENT_CLI, AGENT_MODEL, DEFAULT_WORK_DIR, PORT, BRAIN_HTTP_URL }, { claudeMergeGuard }, { executeCLI }, fs, {
  hasGitHubCredentials,
  discoverAndGenerateTokens,
  setupGitCredentials,
  setupGitHubTooling,
  hasGitLabCredentials,
  readGitLabToken,
  setupGitLabCredentials,
  setupGitLabTooling,
  setupArgoCDMCP,
  setupCLILogins,
  setupRegistryCredentials,
  setupRemoteK8sMCPs,
  getRemoteClustersMeta,
  GITLAB_HOST,
} (+13 more)

### Community 60 - "server.js"
Cohesion: 0.09
Nodes (17): hasRegistryCredentials(), { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, fs, path, stageEventDocument(), fetchEventDocument(), fs, { handleRequest } (+9 more)

### Community 62 - "StateWatcher"
Cohesion: 0.10
Nodes (3): _QueueEntry, StateWatcher, _Subscription

### Community 63 - "adf_to_markdown"
Cohesion: 0.12
Nodes (10): _adf_to_text(), _escape_jql_string(), JiraIncidentAdapter, adf_to_markdown(), _apply_marks(), _children(), _render(), _render_list() (+2 more)

### Community 64 - "handlers_integration.py"
Cohesion: 0.10
Nodes (14): _alert_wrapper_retrigger(), _do_retrigger(), _get_jira_reporter(), handle_ask_release_ai(), handle_comment_jira_issue(), handle_fetch_jira_issue(), handle_greenwave(), handle_notify_user_slack() (+6 more)

### Community 66 - "nightwatcher_tools.py"
Cohesion: 0.14
Nodes (13): ShiftIncident, ShiftInvestigation, execute_tool(), get_phase_tools(), _handle_consult_deep_memory(), _handle_declare_clusters(), _handle_dispatch_investigation(), _handle_get_event_report() (+5 more)

### Community 69 - "llm/__init__.py"
Cohesion: 0.16
Nodes (5): FunctionCall, LLMChunk, LLMPort, LLMResponse, TokenUsage

### Community 70 - "observations_mgmt.py"
Cohesion: 0.12
Nodes (9): render_pdf(), bulk_delete_observations(), BulkDeleteRequest, delete_observation(), export_observations(), generate_observations_report(), rename_observation(), RenameRequest (+1 more)

### Community 72 - "nightwatcher.py"
Cohesion: 0.11
Nodes (9): build_report_iteration_prompt(), build_summary_prompt(), extract_full_links(), _normalize_gitlab_host(), build_extend_tool(), build_report_tool(), build_summary_tool(), _handle_extend_incident() (+1 more)

### Community 75 - "dependencies"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 76 - "reconcile.py"
Cohesion: 0.15
Nodes (9): _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers(), main(), _parse_frontmatter() (+1 more)

### Community 79 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 80 - "TokenUtilizationPage.tsx"
Cohesion: 0.16
Nodes (17): recharts, getFlowHistory(), FlowSnapshot, ObservationSeries, FlowHistoryPage(), formatTime(), RANGES, SparkCard() (+9 more)

### Community 82 - "cli-setup.js"
Cohesion: 0.13
Nodes (19): { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync }, filterSkillsByMode() (+11 more)

### Community 83 - "ArchitectureGraph.tsx"
Cohesion: 0.14
Nodes (17): @dagrejs/dagre, @xyflow/react, applyDagreLayout(), applyGridLayout(), applyLayout(), ArchitectureGraphInner(), buildGraph(), computeIdHash() (+9 more)

### Community 85 - "PulseBatch"
Cohesion: 0.12
Nodes (4): PulseBatch, PulsePort, PulseObserver, PulseTracker

### Community 86 - "ephemeral_provisioner.py"
Cohesion: 0.13
Nodes (3): _PodHealthState, SpawnFailed, SpawnStatus

### Community 87 - "claude-guard.js"
Cohesion: 0.14
Nodes (16): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+8 more)

### Community 88 - "scheduling/__init__.py"
Cohesion: 0.18
Nodes (9): handle_refresh_github_context(), handle_refresh_gitlab_context(), handle_refresh_kargo_context(), GitHubPrRef, GitLabMrRef, GitLabPipelineRef, KargoStageRef, PollFn (+1 more)

### Community 89 - "._build_system_prompt"
Cohesion: 0.11
Nodes (3): _init_tool_names(), _strip_tool_names(), _wrap_section()

### Community 91 - "redis_client.py"
Cohesion: 0.13
Nodes (3): close_redis(), get_redis(), RedisClient

### Community 92 - "devDependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 93 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 94 - "get_report"
Cohesion: 0.11
Nodes (6): get_report(), list_reports(), reports_spa_no_slash(), reports_spa_with_slash(), search_reports(), _serve_spa()

### Community 95 - "gemini-sidecar/package.json"
Cohesion: 0.11
Nodes (17): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+9 more)

### Community 98 - "ShiftsPage.tsx"
Cohesion: 0.23
Nodes (16): getCurrentShift(), getShiftDetail(), getShiftsList(), ShiftReportFull, ShiftReportSummary, FailedClusterBadge(), getISOWeek(), getWeekDates() (+8 more)

### Community 99 - "ConversationTurn"
Cohesion: 0.21
Nodes (14): ConversationTurn, DeferCountdownBar(), STATUS_COLORS, TICKET_COLORS, TicketNodeComponent(), TicketNodeData, PlanProgressProps, DeferCountdownState (+6 more)

### Community 100 - "catalog-skills.js"
Cohesion: 0.16
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 105 - "list_active_events"
Cohesion: 0.12
Nodes (6): _defer_timeline_fields(), _has_active_subscription(), list_active_events(), list_closed_events(), list_waiting_approval_events(), _serialize_evidence()

### Community 106 - "observations_reporter.py"
Cohesion: 0.20
Nodes (7): _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), _sample_points(), _summarize()

### Community 107 - "generate_map.py"
Cohesion: 0.19
Nodes (6): _enumerate_gates(), _GateInfo, generate_phase_tool_map(), _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 112 - "ServiceNode.tsx"
Cohesion: 0.20
Nodes (11): HealthStatus, NodeType, AppNodeData, ARGOCD_HEALTH_COLORS, SYNC_ICONS, GENERIC_TAGS, HEALTH_COLORS, NODE_ICONS (+3 more)

### Community 118 - "get_graph_context"
Cohesion: 0.18
Nodes (5): _format_graph_context(), get_graph_context(), _parse_props(), _sanitize(), translate_to_lookups()

### Community 120 - "IncidentAdapterPort"
Cohesion: 0.15
Nodes (3): IdleTimeoutPort, IncidentAdapterPort, StateWatcherPort

### Community 121 - "NightwatcherObserver"
Cohesion: 0.21
Nodes (3): ShiftReport, NightwatcherObserver, build_system_prompt()

### Community 127 - "telemetry.py"
Cohesion: 0.22
Nodes (3): get_quota_tracker(), llm_stats(), receive_telemetry()

### Community 128 - "is_defer_event_available"
Cohesion: 0.18
Nodes (6): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 129 - "SecurityError"
Cohesion: 0.24
Nodes (4): _check_security(), safe_execution(), wrapper(), SecurityError

### Community 130 - "vite.config.ts"
Cohesion: 0.20
Nodes (5): @tailwindcss/vite, @testing-library/react, vite, @vitejs/plugin-react, vitest

### Community 133 - "entity_extractor.py"
Cohesion: 0.33
Nodes (5): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship

### Community 134 - "handle_report_incident"
Cohesion: 0.22
Nodes (5): handle_report_incident(), handle_notify_gitlab_result(), handle_search_open_incidents(), handle_respond_to_jarvis(), handle_set_phase()

### Community 135 - "has_unevaluated_close_blocker"
Cohesion: 0.20
Nodes (4): has_unevaluated_close_blocker(), _pred_jarvis_response(), _pred_unevaluated_close(), is_jarvis_acknowledgment()

### Community 136 - "knowledge_graph_api.py"
Cohesion: 0.31
Nodes (4): get_kg_store(), get_service_detail(), get_stats(), list_services()

### Community 137 - "CortexDevPage.tsx"
Cohesion: 0.36
Nodes (8): devQueryClient, MOCK_CORTEX_STATUS, MOCK_EVENT_ID, MOCK_NEURONS, MOCK_PULSE_BATCHES, MOCK_SHADOW, MOCK_THINKING, MOCK_WHISPERS

### Community 138 - "NeuronInfoPanel.tsx"
Cohesion: 0.33
Nodes (9): asNumber(), asString(), asStringArray(), Badge(), describeNeuron(), Hdr(), NeuronInfoPanel(), AGENT_NEURON_COLORS (+1 more)

### Community 149 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 150 - "validate-mutations.sh"
Cohesion: 0.73
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

### Community 160 - "CortexHeartbeat.tsx"
Cohesion: 0.67
Nodes (3): CortexHeartbeat(), CortexHeartbeatProps, ensureKeyframes()

## Knowledge Gaps
- **13 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+8 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2109 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **93 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `logging`, `EventDocument`, `Brain`, `models.py`, `queue.py`, `_is_event_closed_or_missing`, `brain.py`, `cognitive_graph.py`, `topology.py`, `dependencies.py`, `HeadhunterJira`, `get_all_journal`, `update_notebook_note`, `get_notebook`, `slack.py`, `.__init__`, `delete_notebook_note`, `routes/timekeeper.py`, `jenkins_observer.py`, `auth.py`, `.get_event`, `httpx`, `lifespan`, `ConversationTurn`, `main.py`, `DashboardWSAdapter`, `LiveAPIAdapter`, `nightwatcher_tools.py`, `observations_mgmt.py`, `nightwatcher.py`, `get_report`, `list_active_events`, `observations_reporter.py`, `ScheduleRepository`, `NightwatcherObserver`?**
  _High betweenness centrality (0.132) - this node is a cross-community bridge._
- **Are the 78 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 78 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.014314928425357873 - nodes in this community are weakly interconnected._
- **Why does `Brain` connect `Brain` to `BlackboardState`, `EventDocument`, `models.py`, `ReconcileScheduler`, `brain.py`, `._run_agent_task`, `dependencies.py`, `.__init__`, `slack.py`, `._process_with_llm`, `.append_and_broadcast`, `httpx`, `lifespan`, `ConversationTurn`, `main.py`, `DashboardWSAdapter`, `StateWatcher`, `._build_contents`, `BrainSkillLoader`, `PulseBatch`, `._build_system_prompt`, `ReflexSearcher`, `IdleTimeoutManager`, `src/ports.py`, `QuotaTracker`, `.enqueue`?**
  _High betweenness centrality (0.060) - this node is a cross-community bridge._
- **Are the 20 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Should `logging` be split into smaller, more focused modules?**
  _Cohesion score 0.03718507751937984 - nodes in this community are weakly interconnected._