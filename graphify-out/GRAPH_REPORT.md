# Graph Report - Blackboard  (2026-10-29)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 4871 nodes · 10855 edges · 204 communities (99 shown, 105 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 920 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `ea6e8be0`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BlackboardState
- client.ts
- logging
- auth.py
- api/types.ts
- EventChatPanel.tsx
- tool_gates.py
- os
- BaseModel
- merge-guard.js
- Brain
- EventSidebar.tsx
- ._run_agent_task
- jenkins-mcp.js
- Archivist
- GitHubPlatform
- HeadhunterJira
- lucide-react
- topology.py
- App.tsx
- hooks/index.ts
- react
- GitLabPlatform
- EventDocument
- AgentRegistry
- ConversationTurn
- _BrainToolContext
- credentials.js
- observations_mgmt.py
- brain.py
- main.py
- handlers_integration.py
- storage-recycler.js
- JenkinsAdapter
- nightwatcher_tools.py
- cli-executor.js
- jenkins_observer.py
- agents/__init__.py
- KnowledgeGraphStore
- EventRepository
- ._process_with_llm
- slack.py
- Aligner
- ToolContext
- ._gate_check
- ActiveStreamsContext.tsx
- JenkinsObserver
- Headhunter
- TimeKeeperPage.tsx
- SlackChannel
- queue.py
- CortexGraph.tsx
- models.py
- VectorStore
- ws-client.js
- ui/package.json
- lifespan
- StateWatcher
- EventDrillDown.tsx
- live_api_adapter.py
- dependencies.py
- server.js
- useCortexData.ts
- ArchitectureGraph.tsx
- adf_to_markdown
- EphemeralProvisioner
- GeminiAdapter
- get_archivist
- cognitive_graph.py
- ArgoCDObserver
- NeuronInfoPanel.tsx
- llm/__init__.py
- BrainSkillLoader
- KargoObserver
- GitHubAppAuth
- dependencies
- reconcile.py
- http-handler.js
- KubernetesSpawnHealthAdapter
- IdleTimeoutManager
- compilerOptions
- claude-guard.js
- cli-setup.js
- VcsPlatformPort
- ephemeral_provisioner.py
- ReflexSearcher
- ._poll_issues
- prompt.py
- devDependencies
- compilerOptions
- TokenUtilizationPage.tsx
- DashboardWSAdapter
- LiveAPIAdapter
- get_report
- gemini-sidecar/package.json
- ._build_contents
- ._build_system_prompt
- .get_event
- ObservationRepository
- ShiftsPage.tsx
- catalog-skills.js
- OIDCKeyAdapter
- archivist.py
- ClaudeAdapter
- FlowSnapshot
- list_active_events
- RedisClient
- SlackAccessGate
- generate_map.py
- src/ports.py
- ._discover
- NightwatcherObserver
- .list_observations
- EscalationRepository
- ServiceNode.tsx
- get_brain
- .get_blackboard
- close_event_by_user
- QuotaTracker
- MultiInstallationManager
- ScheduleCreateRequest
- FilterRule
- ._extract_context_flags
- TokenMeter
- ReconcileScheduler
- JarvisMemoryPage.tsx
- EventEvidence
- ._cleanup_stale_events
- ._github_poll_and_process
- CortexLiveFeed.tsx
- .start_event_loop
- handle_report_incident
- is_defer_event_available
- CiContextCard.tsx
- cortex/types.ts
- SecurityError
- vite.config.ts
- _is_event_closed_or_missing
- has_unevaluated_close_blocker
- IncidentAdapterPort
- nightwatcher_prompt.py
- FairQueue
- get_quota_tracker
- SmartsheetMaintainerCache
- Trigger
- AsyncGitHubClient
- GitLabTokenAuth
- ConversationMessage
- update_knowledge
- CortexRepository
- BrainIntrospectionPort
- scripts
- validate-mutations.sh
- ._process_message
- Pulse
- list_failed_stages
- dex_proxy
- submit_feedback
- QueueTrigger
- list_incidents
- headhunter_pending_todos
- require-results.sh
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
- _normalize_gitlab_host

## God Nodes (most connected - your core abstractions)
1. `BlackboardState` - 279 edges
2. `Brain` - 148 edges
3. `ConversationTurn` - 122 edges
4. `ToolContext` - 102 edges
5. `GateContext` - 94 edges
6. `react` - 80 edges
7. `EventDocument` - 78 edges
8. `fetchApi()` - 65 edges
9. `lifespan()` - 64 edges
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

## Communities (204 total, 105 thin omitted)

### Community 0 - "BlackboardState"
Cohesion: 0.01
Nodes (4): get_all_journal(), get_service_journal(), get_notebook(), BlackboardState

### Community 1 - "client.ts"
Cohesion: 0.04
Nodes (97): @tanstack/react-query, ApiError, applyLessons(), bulkDeleteObservations(), correctMemory(), createKnowledge(), createLesson(), deleteKnowledge() (+89 more)

### Community 2 - "logging"
Cohesion: 0.04
Nodes (5): _heartbeat(), _load_name_mapping(), get_current_shift(), get_shift_detail(), list_shifts()

### Community 3 - "auth.py"
Cohesion: 0.03
Nodes (26): can_append_message(), _claims_to_user(), get_user_from_request(), get_user_from_websocket(), _normalize_email(), prompt_display_name(), require_auth(), require_obs_admin() (+18 more)

### Community 4 - "api/types.ts"
Cohesion: 0.04
Nodes (73): @tanstack/react-table, getReport(), getReports(), ReportSearchParams, searchReports(), Agent, AlignerPendingItem, AppNode (+65 more)

### Community 5 - "EventChatPanel.tsx"
Cohesion: 0.06
Nodes (57): closeEvent(), enforceCasualDomain(), ConversationTurn, TokenUsageDict, CiContextCard(), ConversationFeed(), ConversationFeedProps, eventToMarkdown() (+49 more)

### Community 6 - "tool_gates.py"
Cohesion: 0.05
Nodes (78): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+70 more)

### Community 7 - "os"
Cohesion: 0.05
Nodes (21): _get_static_maintainer_emails(), _get_allowed_mention_authors(), _get_static_maintainer_emails(), _safe_int(), create_adapter(), record_token_usage(), _md_table_to_text(), _md_to_mrkdwn() (+13 more)

### Community 8 - "BaseModel"
Cohesion: 0.04
Nodes (12): ArchitectureEvent, EventInput, GraphEdge, GraphResponse, ScheduledEvent, Service, Snapshot, TopologySnapshot (+4 more)

### Community 9 - "merge-guard.js"
Cohesion: 0.05
Nodes (69): analyzeString(), analyzeTokens(), API_VALUED, apiTokens(), apiWriteNeedsGuard(), assignName(), bareBranchProtected(), base() (+61 more)

### Community 11 - "EventSidebar.tsx"
Cohesion: 0.08
Nodes (54): getAlignerPending(), getHeadhunterPending(), getJenkinsPending(), getJiraMissions(), getWaitingApprovalEvents(), HeadhunterTodo, postJiraAction(), EventDocument (+46 more)

### Community 12 - "._run_agent_task"
Cohesion: 0.06
Nodes (7): on_huddle(), on_progress(), on_huddle(), on_progress(), _compute_processed_up_to(), _sanitize_error_text(), get_registry_and_bridge()

### Community 13 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 16 - "HeadhunterJira"
Cohesion: 0.05
Nodes (3): HeadhunterJira, _walk_adf_mentions(), _walk()

### Community 17 - "lucide-react"
Cohesion: 0.07
Nodes (44): lucide-react, createChatEvent(), getAgents(), getKargoStages(), AgentRegistryEntry, KargoStageStatus, AgentRegistryPanel(), formatConnectedSince() (+36 more)

### Community 18 - "topology.py"
Cohesion: 0.04
Nodes (11): AppNode, GraphNode, TicketNode, get_event_document(), get_graph_data(), get_mermaid_diagram(), get_service_details(), get_topology() (+3 more)

### Community 19 - "App.tsx"
Cohesion: 0.07
Nodes (44): oidc-client-ts, react-router-dom, getConfig(), getWSAuthFailureCallback(), setOnUnauthorized(), setTokenGetter(), setWSAuthFailureCallback(), AppConfig (+36 more)

### Community 20 - "hooks/index.ts"
Cohesion: 0.07
Nodes (44): getActiveEvents(), getClosedEvents(), getEventDocument(), getEvents(), getService(), getTopology(), ArchitectureEvent, ArgoCDOperation (+36 more)

### Community 21 - "react"
Cohesion: 0.08
Nodes (38): react, react-dom, @uiw/react-markdown-preview, approveEvent(), rejectEvent(), submitFeedback(), ChatInputProps, Draft (+30 more)

### Community 24 - "AgentRegistry"
Cohesion: 0.06
Nodes (12): AgentConnection, AgentRegistry, agent_websocket_handler(), _build_prompt(), consume_wake_task(), _consume(), _dispatch_timeout_s(), dispatch_to_agent() (+4 more)

### Community 25 - "ConversationTurn"
Cohesion: 0.10
Nodes (25): emit_tool_result(), _safe_int(), handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_recall_pruned_turns(), handle_ask_release_ai(), handle_greenwave() (+17 more)

### Community 27 - "credentials.js"
Cohesion: 0.12
Nodes (45): resolveCommand(), writeAgyMcpServer(), writeClaudeMcpServer(), buildArgoCDMcpConfig(), createAppJWT(), discoverAndGenerateTokens(), _discoverAndGenerateTokensInner(), discoverInstallations() (+37 more)

### Community 28 - "observations_mgmt.py"
Cohesion: 0.06
Nodes (17): _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), render_pdf(), _sample_points(), _summarize() (+9 more)

### Community 29 - "brain.py"
Cohesion: 0.08
Nodes (15): _apply_sibling_signature(), build_function_response(), build_single_function_response(), compress_contents(), estimate_msg_tokens(), estimate_tokens(), extract_model_parts(), normalize_response_parts() (+7 more)

### Community 30 - "main.py"
Cohesion: 0.06
Nodes (17): set_agents(), set_kargo_observer(), agent_ws_endpoint(), api_info(), get_config(), get_event_flow(), get_flow_history(), get_flow_metrics() (+9 more)

### Community 31 - "handlers_integration.py"
Cohesion: 0.08
Nodes (20): _alert_wrapper_retrigger(), _do_retrigger(), _get_jira_reporter(), handle_comment_jira_issue(), handle_fetch_jira_issue(), handle_notify_user_slack(), handle_refresh_github_context(), handle_refresh_gitlab_context() (+12 more)

### Community 32 - "storage-recycler.js"
Cohesion: 0.08
Nodes (34): withTaskStorage(), resolveStorageRoot(), ROLE_TIMEOUTS, STORAGE_ACTIVITY_HEARTBEAT_MS, STORAGE_MAX_TIER3_DELETIONS, STORAGE_PRETASK_TIMEOUT_MS, STORAGE_RESULTS_TTL_MS, STORAGE_STALE_MS (+26 more)

### Community 33 - "JenkinsAdapter"
Cohesion: 0.06
Nodes (6): BuildDetails, JenkinsAdapter, JenkinsPlatformPort, JobResult, JobRunState, ViewScanResult

### Community 34 - "nightwatcher_tools.py"
Cohesion: 0.10
Nodes (20): ShiftIncident, ShiftInvestigation, build_report_iteration_prompt(), build_summary_prompt(), extract_full_links(), build_extend_tool(), build_report_tool(), build_summary_tool() (+12 more)

### Community 35 - "cli-executor.js"
Cohesion: 0.09
Nodes (34): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS, STORAGE_PRETASK_TIMEOUT_MS, resolveStorageRoot }, buildCLICommand(), { checkAndRecycleStorage, pinTaskCwd, unpinTaskCwd }, CLAUDE_JSON_PATH, cp, executeCLI(), executeCLIStreaming(), FALLBACK_MODEL (+26 more)

### Community 36 - "jenkins_observer.py"
Cohesion: 0.07
Nodes (14): _annotation_replace(), _strip_pipeline_annotations(), _clamp_confidence(), _env_flag(), _parse_job_metadata(), _prepare_console_tail(), _redact_build_parameters(), _redact_match() (+6 more)

### Community 37 - "agents/__init__.py"
Cohesion: 0.07
Nodes (4): Architect, AgentClient, Developer, SysAdmin

### Community 38 - "KnowledgeGraphStore"
Cohesion: 0.09
Nodes (9): _format_graph_context(), get_graph_context(), _parse_props(), _sanitize(), translate_to_lookups(), _acquire(), KnowledgeGraphStore, _sanitize() (+1 more)

### Community 41 - "slack.py"
Cohesion: 0.08
Nodes (15): build_access_denied_home_view(), build_home_tab_view(), _context_line(), create_feedback_block(), extract_tables(), _replace(), format_plan_block(), format_task_card() (+7 more)

### Community 43 - "ToolContext"
Cohesion: 0.10
Nodes (8): handle_message_agent(), handle_reply_to_agent(), handle_select_agent(), handle_defer_event(), handle_hold_watch(), handle_wait_for_agent(), handle_wait_for_jarvis(), ToolContext

### Community 44 - "._gate_check"
Cohesion: 0.10
Nodes (11): can_approve_event(), get_user_from_slack(), format_event_summary(), handle_app_home_opened(), handle_app_mention(), handle_approve(), handle_create_event_modal(), handle_darwin_command() (+3 more)

### Community 45 - "ActiveStreamsContext.tsx"
Cohesion: 0.11
Nodes (30): getFlowMetrics(), FlowMetrics, AgentStreamCard(), AgentStreamCardProps, FloatingWindow(), MessageCards(), Dashboard(), GridTile() (+22 more)

### Community 48 - "TimeKeeperPage.tsx"
Cohesion: 0.12
Nodes (24): createSchedule(), deleteSchedule(), getSchedules(), refineInstructions(), ScheduleCreatePayload, ScheduleItem, toggleSchedule(), updateSchedule() (+16 more)

### Community 50 - "queue.py"
Cohesion: 0.10
Nodes (18): can_override_domain(), JenkinsPendingItem, PendingAnomaly, apply_lessons(), correct_memory(), CorrectMemoryRequest, create_knowledge(), create_lesson() (+10 more)

### Community 51 - "CortexGraph.tsx"
Cohesion: 0.12
Nodes (30): graphology, ActiveEvent, KGServiceEntity, eventColor(), getExecutiveNeurons(), getStructuralEdges(), DEFAULT_TYPE_BUDGET, evictLru() (+22 more)

### Community 52 - "models.py"
Cohesion: 0.08
Nodes (13): ChatRequest, ChatResponse, EventMetrics, EventStatus, EventType, HealthStatus, MessageStatus, Metrics (+5 more)

### Community 53 - "VectorStore"
Cohesion: 0.08
Nodes (3): _decode_cursor(), _encode_cursor(), VectorStore

### Community 54 - "ws-client.js"
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

### Community 55 - "ui/package.json"
Cohesion: 0.08
Nodes (28): autoprefixer, cronstrue, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, graphology-layout-forceatlas2 (+20 more)

### Community 56 - "lifespan"
Cohesion: 0.07
Nodes (7): set_incident_options(), set_archivist(), set_argocd_observer(), set_blackboard(), set_brain(), set_registry_and_bridge(), lifespan()

### Community 57 - "StateWatcher"
Cohesion: 0.09
Nodes (4): PollFn, _QueueEntry, StateWatcher, _Subscription

### Community 58 - "EventDrillDown.tsx"
Cohesion: 0.13
Nodes (23): three, getEventPulses(), BrainCore(), CortexDevPage(), devQueryClient, CortexLiveFeedProps, EventDrillDown(), EventDrillDownProps (+15 more)

### Community 59 - "live_api_adapter.py"
Cohesion: 0.10
Nodes (4): PulseBatch, PulsePort, PulseObserver, PulseTracker

### Community 60 - "dependencies.py"
Cohesion: 0.09
Nodes (13): get_aligner(), get_architect(), get_argocd_observer(), get_developer(), get_kargo_observer(), get_kg_store(), get_report_client(), get_sysadmin() (+5 more)

### Community 61 - "server.js"
Cohesion: 0.09
Nodes (18): hasRegistryCredentials(), { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, fs, path, stageEventDocument(), fetchEventDocument(), fs, { handleRequest } (+10 more)

### Community 62 - "useCortexData.ts"
Cohesion: 0.19
Nodes (24): getCognitiveGraph(), getCortexActivity(), getEventReport(), getKGServiceDetail(), getKGServices(), getKGStats(), getRecentPulses(), CortexPage() (+16 more)

### Community 63 - "ArchitectureGraph.tsx"
Cohesion: 0.11
Nodes (21): @dagrejs/dagre, @xyflow/react, applyDagreLayout(), applyGridLayout(), applyLayout(), ArchitectureGraphInner(), buildGraph(), computeIdHash() (+13 more)

### Community 64 - "adf_to_markdown"
Cohesion: 0.12
Nodes (10): _adf_to_text(), _escape_jql_string(), JiraIncidentAdapter, adf_to_markdown(), _apply_marks(), _children(), _render(), _render_list() (+2 more)

### Community 65 - "EphemeralProvisioner"
Cohesion: 0.09
Nodes (3): DispatchMetrics, EphemeralProvisioner, SpawnFailed

### Community 67 - "get_archivist"
Cohesion: 0.10
Nodes (12): get_archivist(), get_cognitive_graph(), aligner_pending_items(), delete_knowledge(), delete_lesson(), get_knowledge(), get_lesson(), get_memory() (+4 more)

### Community 68 - "cognitive_graph.py"
Cohesion: 0.12
Nodes (11): get_blackboard(), get_pulse_tracker(), dismiss_proposals(), DismissRequest, get_all_shadow_interventions(), get_cortex_activity(), get_cortex_status(), get_event_shadow_interventions() (+3 more)

### Community 70 - "NeuronInfoPanel.tsx"
Cohesion: 0.11
Nodes (23): KGServiceDetail, AGENTS, DOMAINS, HEMISPHERE_X, NEURON_DESCRIPTIONS, PHASE_SKILL_FOLDERS, PHASE_TOOL_PRIORITY, PHASES (+15 more)

### Community 71 - "llm/__init__.py"
Cohesion: 0.16
Nodes (5): FunctionCall, LLMChunk, LLMPort, LLMResponse, TokenUsage

### Community 74 - "GitHubAppAuth"
Cohesion: 0.11
Nodes (3): _find_pem_file(), get_github_auth(), GitHubAppAuth

### Community 75 - "dependencies"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 76 - "reconcile.py"
Cohesion: 0.15
Nodes (9): _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers(), main(), _parse_frontmatter() (+1 more)

### Community 77 - "http-handler.js"
Cohesion: 0.09
Nodes (18): { AGENT_CLI, AGENT_MODEL, DEFAULT_WORK_DIR, PORT, BRAIN_HTTP_URL }, { claudeMergeGuard }, { executeCLI }, fs, {
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
}, http, isLoopbackAddress(), { isReadOnlyRoleName } (+10 more)

### Community 80 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 81 - "claude-guard.js"
Cohesion: 0.14
Nodes (18): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+10 more)

### Community 82 - "cli-setup.js"
Cohesion: 0.13
Nodes (19): { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync }, filterSkillsByMode() (+11 more)

### Community 84 - "ephemeral_provisioner.py"
Cohesion: 0.15
Nodes (3): SpawnHealthPort, SpawnPollResult, SpawnStatus

### Community 87 - "prompt.py"
Cohesion: 0.16
Nodes (11): _build_closed_block(), build_event_header(), _build_identity_block(), _build_journal_block(), _build_mermaid_block(), _build_related_block(), _build_subject_block(), _build_timing_block() (+3 more)

### Community 88 - "devDependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 89 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 90 - "TokenUtilizationPage.tsx"
Cohesion: 0.20
Nodes (15): recharts, getFlowHistory(), FlowSnapshot, FlowHistoryPage(), formatTime(), RANGES, SparkCard(), SparkCardProps (+7 more)

### Community 93 - "get_report"
Cohesion: 0.11
Nodes (6): get_report(), list_reports(), reports_spa_no_slash(), reports_spa_with_slash(), search_reports(), _serve_spa()

### Community 94 - "gemini-sidecar/package.json"
Cohesion: 0.11
Nodes (17): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+9 more)

### Community 96 - "._build_system_prompt"
Cohesion: 0.12
Nodes (3): _init_tool_names(), _strip_tool_names(), _wrap_section()

### Community 97 - ".get_event"
Cohesion: 0.12
Nodes (4): get_event_approval(), get_event_report(), get_event_turns(), rebuild_deep_memory()

### Community 99 - "ShiftsPage.tsx"
Cohesion: 0.23
Nodes (16): getCurrentShift(), getShiftDetail(), getShiftsList(), ShiftReportFull, ShiftReportSummary, FailedClusterBadge(), getISOWeek(), getWeekDates() (+8 more)

### Community 100 - "catalog-skills.js"
Cohesion: 0.16
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 102 - "archivist.py"
Cohesion: 0.16
Nodes (7): _sanitize_lesson_text(), Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship, PulseContext

### Community 105 - "list_active_events"
Cohesion: 0.12
Nodes (6): _defer_timeline_fields(), _has_active_subscription(), list_active_events(), list_closed_events(), list_waiting_approval_events(), _serialize_evidence()

### Community 108 - "generate_map.py"
Cohesion: 0.19
Nodes (6): _enumerate_gates(), _GateInfo, generate_phase_tool_map(), _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 111 - "NightwatcherObserver"
Cohesion: 0.19
Nodes (3): ShiftReport, NightwatcherObserver, get_phase_tools()

### Community 114 - "ServiceNode.tsx"
Cohesion: 0.20
Nodes (11): HealthStatus, NodeType, AppNodeData, ARGOCD_HEALTH_COLORS, SYNC_ICONS, GENERIC_TAGS, HEALTH_COLORS, NODE_ICONS (+3 more)

### Community 115 - "get_brain"
Cohesion: 0.19
Nodes (4): resolve_approval_identity(), get_brain(), approve_event(), reject_event()

### Community 116 - ".get_blackboard"
Cohesion: 0.21
Nodes (5): handle_classify_event(), handle_close_event(), handle_request_user_approval(), handle_wait_for_user(), IdleTimeoutPort

### Community 117 - "close_event_by_user"
Cohesion: 0.14
Nodes (4): get_token_meter(), close_event_by_user(), CloseRequest, get_event_document()

### Community 122 - "._extract_context_flags"
Cohesion: 0.15
Nodes (3): compute_dispatch_backpressure(), ContextFlags, _safe_int_env()

### Community 125 - "JarvisMemoryPage.tsx"
Cohesion: 0.27
Nodes (12): dismissProposals(), EnhancementProposal, getHandoffReports(), getProposals(), HandoffReport, FilterMode, formatDate(), formatTime() (+4 more)

### Community 131 - "CortexLiveFeed.tsx"
Cohesion: 0.24
Nodes (10): CortexHeartbeat(), CortexHeartbeatProps, ensureKeyframes(), CortexLiveFeed(), FILTER_PILLS, FilterKey, getStoredFilter(), MESSAGE_STYLES (+2 more)

### Community 133 - "handle_report_incident"
Cohesion: 0.20
Nodes (5): handle_report_incident(), _resolve_escalation_scope(), handle_notify_gitlab_result(), handle_search_open_incidents(), handle_respond_to_jarvis()

### Community 134 - "is_defer_event_available"
Cohesion: 0.18
Nodes (6): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 135 - "CiContextCard.tsx"
Cohesion: 0.31
Nodes (9): CiContext, CiContextCardProps, ConsoleTailBlock(), FailedJobRow(), annotationReplacer(), PIPELINE_ANNOTATION_RE, REDACTION_TRIGGER_KEYWORDS, stripAnsi() (+1 more)

### Community 136 - "cortex/types.ts"
Cohesion: 0.24
Nodes (9): EventSource, PulseTimelineProps, CognitiveGraphResponse, CortexHeartbeatMessage, FrictionIndicator, FrictionPattern, NeuronVisual, PulseBatch (+1 more)

### Community 137 - "SecurityError"
Cohesion: 0.24
Nodes (4): _check_security(), safe_execution(), wrapper(), SecurityError

### Community 138 - "vite.config.ts"
Cohesion: 0.20
Nodes (5): @tailwindcss/vite, @testing-library/react, vite, @vitejs/plugin-react, vitest

### Community 142 - "has_unevaluated_close_blocker"
Cohesion: 0.20
Nodes (4): has_unevaluated_close_blocker(), _pred_jarvis_response(), _pred_unevaluated_close(), is_jarvis_acknowledgment()

### Community 144 - "nightwatcher_prompt.py"
Cohesion: 0.24
Nodes (4): StagedEscalation, build_manifest_table(), build_system_prompt(), extract_event_links()

### Community 147 - "get_quota_tracker"
Cohesion: 0.22
Nodes (3): get_quota_tracker(), llm_stats(), receive_telemetry()

### Community 157 - "update_knowledge"
Cohesion: 0.25
Nodes (4): demote_lesson(), KnowledgeUpdateRequest, update_knowledge(), verify_lesson()

### Community 160 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 161 - "validate-mutations.sh"
Cohesion: 0.73
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

## Knowledge Gaps
- **13 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+8 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2126 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **105 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `logging`, `auth.py`, `os`, `BaseModel`, `Brain`, `_is_event_closed_or_missing`, `HeadhunterJira`, `nightwatcher_prompt.py`, `topology.py`, `EventDocument`, `ConversationTurn`, `observations_mgmt.py`, `brain.py`, `main.py`, `ConversationMessage`, `nightwatcher_tools.py`, `jenkins_observer.py`, `submit_feedback`, `.__init__`, `slack.py`, `queue.py`, `models.py`, `lifespan`, `live_api_adapter.py`, `dependencies.py`, `get_archivist`, `cognitive_graph.py`, `DashboardWSAdapter`, `LiveAPIAdapter`, `get_report`, `.get_event`, `FlowSnapshot`, `list_active_events`, `NightwatcherObserver`, `.list_observations`, `get_brain`, `close_event_by_user`, `EventEvidence`?**
  _High betweenness centrality (0.126) - this node is a cross-community bridge._
- **Are the 78 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 78 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.014617017801731177 - nodes in this community are weakly interconnected._
- **Why does `Brain` connect `Brain` to `BlackboardState`, `._cleanup_stale_events`, `.start_event_loop`, `os`, `._run_agent_task`, `EventDocument`, `ConversationTurn`, `brain.py`, `main.py`, `Pulse`, `agents/__init__.py`, `QueueTrigger`, `._process_with_llm`, `._format_merge_evidence`, `.__init__`, `slack.py`, `.append_and_broadcast`, `.broadcast`, `models.py`, `lifespan`, `StateWatcher`, `live_api_adapter.py`, `dependencies.py`, `BrainSkillLoader`, `IdleTimeoutManager`, `ReflexSearcher`, `DashboardWSAdapter`, `._build_contents`, `._build_system_prompt`, `FlowSnapshot`, `src/ports.py`, `QuotaTracker`, `._extract_context_flags`, `ReconcileScheduler`, `EventEvidence`?**
  _High betweenness centrality (0.066) - this node is a cross-community bridge._
- **Are the 20 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Should `client.ts` be split into smaller, more focused modules?**
  _Cohesion score 0.04047976011994003 - nodes in this community are weakly interconnected._