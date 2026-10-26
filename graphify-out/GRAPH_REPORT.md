# Graph Report - Blackboard  (2026-10-26)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 4763 nodes · 10519 edges · 207 communities (95 shown, 112 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 903 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `d5af35b9`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BlackboardState
- logging
- ConversationTurn
- client.ts
- queue.py
- brain.py
- tool_gates.py
- EventChatPanel.tsx
- Brain
- EventSidebar.tsx
- merge-guard.js
- ._run_agent_task
- colors.ts
- jenkins-mcp.js
- HeadhunterJira
- live_api_adapter.py
- BrainSkillLoader
- Aligner
- EventDocument
- GitHubPlatform
- TopologyRepository
- _BrainToolContext
- GitLabPlatform
- JenkinsObserver
- TurnBubble.tsx
- credentials.js
- react
- Archivist
- nightwatcher_tools.py
- ._process_with_llm
- cli-executor.js
- JenkinsAdapter
- ScheduleRepository
- App.tsx
- Headhunter
- EventRepository
- AgentRegistry
- slack.py
- AgentClient
- lifespan
- ui/package.json
- VectorStore
- TimeKeeperPage.tsx
- NodeInspector.tsx
- main.py
- ws-client.js
- useCortexData.ts
- CortexGraph.tsx
- SlackChannel
- EventDrillDown.tsx
- KnowledgeGraphStore
- StreamGrid.tsx
- http-handler.js
- server.js
- LiveAPIAdapter
- observations_mgmt.py
- adf_to_markdown
- GeminiAdapter
- ArgoCDObserver
- llm/__init__.py
- KargoObserver
- dependencies
- reconcile.py
- compilerOptions
- ArchitectureGraph.tsx
- TokenUtilizationPage.tsx
- DashboardWSAdapter
- BrainIntrospectionPort
- state/__init__.py
- GitHubAppAuth
- cli-setup.js
- EphemeralProvisioner
- VcsPlatformPort
- cognitive_graph.py
- PulseBatch
- claude-guard.js
- auth.py
- observations_reporter.py
- StateWatcher
- ReflexSearcher
- FairQueue
- devDependencies
- compilerOptions
- ServiceNode.tsx
- get_report
- gemini-sidecar/package.json
- ._build_contents
- ObservationRepository
- ShiftsPage.tsx
- catalog-skills.js
- OIDCKeyAdapter
- .scroll
- ClaudeAdapter
- ._gate_check
- scheduling/__init__.py
- DeferCountdownBar.tsx
- generate_map.py
- KubernetesSpawnHealthAdapter
- IdleTimeoutManager
- TaskBridge
- delete_schedule
- ReconcileScheduler
- EscalationRepository
- QuotaTracker
- create_chat_event
- nightwatcher_prompt.py
- MultiInstallationManager
- ._extract_context_flags
- TokenMeter
- IncidentAdapterPort
- ._send_turn_to_thread
- JarvisMemoryPage.tsx
- NeuronInfoPanel.tsx
- .start_event_loop
- ._github_poll_and_process
- SlackAccessGate
- CortexLiveFeed.tsx
- _prepare_console_tail
- is_defer_event_available
- NightwatcherObserver
- cortex-constants.ts
- CortexDevPage.tsx
- SecurityError
- ._post_agent_recall
- entity_extractor.py
- knowledge_graph_api.py
- get_quota_tracker
- SpawnPollResult
- SmartsheetMaintainerCache
- ._register_handlers
- Trigger
- MetricsRepository
- AsyncGitHubClient
- GitLabTokenAuth
- _is_event_closed_or_missing
- Any
- ConversationMessage
- TimeKeeperObserver
- CortexRepository
- vite.config.ts
- _format_graph_context
- update_notebook_note
- scripts
- validate-mutations.sh
- ._process_message
- ._evaluate_health
- get_graph_context
- SpawnStatus
- list_failed_stages
- dex_proxy
- ._wait_for_registration
- dismiss_proposals
- submit_feedback
- get_notebook
- ResyncTrigger
- Neuron
- list_incidents
- sanitize_prompt_text
- require-results.sh
- TokenUsageDict
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
- _pred_jarvis_response
- _pred_jarvis_wait
- _pred_obs_plateau
- _pred_silent_park
- _pred_unevaluated_close
- _tools_wait_loop

## God Nodes (most connected - your core abstractions)
1. `BlackboardState` - 279 edges
2. `Brain` - 148 edges
3. `ConversationTurn` - 122 edges
4. `ToolContext` - 102 edges
5. `GateContext` - 94 edges
6. `EventDocument` - 78 edges
7. `react` - 71 edges
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

## Communities (207 total, 112 thin omitted)

### Community 0 - "BlackboardState"
Cohesion: 0.01
Nodes (18): get_event_document(), list_events(), get_all_journal(), get_service_journal(), delete_notebook_note(), get_event_observations(), get_global_observations(), get_shift_detail() (+10 more)

### Community 1 - "logging"
Cohesion: 0.03
Nodes (27): _sanitize_lesson_text(), _get_static_maintainer_emails(), _get_allowed_mention_authors(), _get_static_maintainer_emails(), _safe_int(), _parse_job_metadata(), create_adapter(), record_token_usage() (+19 more)

### Community 2 - "ConversationTurn"
Cohesion: 0.05
Nodes (56): emit_tool_result(), _safe_int(), handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_recall_pruned_turns(), handle_message_agent(), handle_reply_to_agent() (+48 more)

### Community 3 - "client.ts"
Cohesion: 0.03
Nodes (115): @tanstack/react-query, ApiError, applyLessons(), bulkDeleteObservations(), correctMemory(), createChatEvent(), createKnowledge(), createLesson() (+107 more)

### Community 4 - "queue.py"
Cohesion: 0.03
Nodes (57): get_token_meter(), can_approve_event(), resolve_approval_identity(), get_archivist(), get_brain(), get_flow_metrics(), aligner_pending_items(), apply_lessons() (+49 more)

### Community 5 - "brain.py"
Cohesion: 0.03
Nodes (44): _compute_processed_up_to(), _has_non_user_turns(), _is_seed_turn(), _apply_sibling_signature(), build_function_response(), build_single_function_response(), compress_contents(), estimate_msg_tokens() (+36 more)

### Community 6 - "tool_gates.py"
Cohesion: 0.05
Nodes (78): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+70 more)

### Community 7 - "EventChatPanel.tsx"
Cohesion: 0.06
Nodes (62): getEventDocument(), AgentRegistryEntry, KargoStageStatus, ChatInput(), ChatInputProps, Draft, LastSubmission, ErrorBoundary (+54 more)

### Community 9 - "EventSidebar.tsx"
Cohesion: 0.07
Nodes (60): getJiraMissions(), HeadhunterTodo, postJiraAction(), CiContext, CiContextCard(), CiContextCardProps, ConsoleTailBlock(), FailedJobRow() (+52 more)

### Community 10 - "merge-guard.js"
Cohesion: 0.05
Nodes (69): analyzeString(), analyzeTokens(), API_VALUED, apiTokens(), apiWriteNeedsGuard(), assignName(), bareBranchProtected(), base() (+61 more)

### Community 11 - "._run_agent_task"
Cohesion: 0.06
Nodes (7): on_huddle(), on_progress(), on_huddle(), on_progress(), _sanitize_error_text(), _sanitize_override_reason(), get_registry_and_bridge()

### Community 12 - "colors.ts"
Cohesion: 0.07
Nodes (39): react-router-dom, getReport(), getReports(), ReportFull, ReportMeta, CompactCardStrip(), EventHistory(), TimeRange (+31 more)

### Community 13 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 14 - "HeadhunterJira"
Cohesion: 0.05
Nodes (3): HeadhunterJira, _walk_adf_mentions(), _walk()

### Community 15 - "live_api_adapter.py"
Cohesion: 0.05
Nodes (17): _resolve_maintainer_enum(), _resolve_slack_user(), _clamp_confidence(), _sanitize_analysis_text(), _strip_newlines(), _validate_analysis(), _validate_triage_entry(), _parse_drain_timeout() (+9 more)

### Community 16 - "BrainSkillLoader"
Cohesion: 0.05
Nodes (3): BrainSkillLoader, _SkillCorpus, _wrap_section()

### Community 19 - "GitHubPlatform"
Cohesion: 0.06
Nodes (3): GitHubPlatform, _poll_one(), _poll_one()

### Community 20 - "TopologyRepository"
Cohesion: 0.05
Nodes (11): _build_closed_block(), build_event_header(), _build_identity_block(), _build_journal_block(), _build_mermaid_block(), _build_related_block(), _build_subject_block(), _build_timing_block() (+3 more)

### Community 23 - "JenkinsObserver"
Cohesion: 0.05
Nodes (3): _env_flag(), JenkinsObserver, _redact_build_parameters()

### Community 24 - "TurnBubble.tsx"
Cohesion: 0.09
Nodes (37): @uiw/react-markdown-preview, approveEvent(), closeEvent(), enforceCasualDomain(), rejectEvent(), submitFeedback(), ConversationFeed(), ConversationFeedProps (+29 more)

### Community 25 - "credentials.js"
Cohesion: 0.13
Nodes (44): resolveCommand(), writeAgyMcpServer(), writeClaudeMcpServer(), buildArgoCDMcpConfig(), createAppJWT(), discoverAndGenerateTokens(), _discoverAndGenerateTokensInner(), discoverInstallations() (+36 more)

### Community 26 - "react"
Cohesion: 0.09
Nodes (39): lucide-react, react, ExtractedCorrection, ExtractedLesson, getAgents(), KnowledgeScope, AgentRegistryPanel(), formatConnectedSince() (+31 more)

### Community 28 - "nightwatcher_tools.py"
Cohesion: 0.09
Nodes (20): PulseContext, ShiftIncident, ShiftInvestigation, extract_full_links(), build_extend_tool(), build_report_tool(), build_summary_tool(), execute_tool() (+12 more)

### Community 30 - "cli-executor.js"
Cohesion: 0.09
Nodes (35): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS }, buildCLICommand(), CLAUDE_JSON_PATH, cp, executeCLI(), executeCLIStreaming(), FALLBACK_MODEL, fs (+27 more)

### Community 31 - "JenkinsAdapter"
Cohesion: 0.06
Nodes (6): BuildDetails, JenkinsAdapter, JenkinsPlatformPort, JobResult, JobRunState, ViewScanResult

### Community 32 - "ScheduleRepository"
Cohesion: 0.06
Nodes (5): ScheduleCreateRequest, ScheduledEvent, create_schedule(), update_schedule(), ScheduleRepository

### Community 33 - "App.tsx"
Cohesion: 0.09
Nodes (30): oidc-client-ts, getConfig(), getIncidents(), getWSAuthFailureCallback(), Incident, setOnUnauthorized(), setTokenGetter(), setWSAuthFailureCallback() (+22 more)

### Community 36 - "AgentRegistry"
Cohesion: 0.07
Nodes (9): AgentConnection, AgentRegistry, agent_websocket_handler(), _heartbeat(), _build_prompt(), _consume(), dispatch_to_agent(), _consume_queue() (+1 more)

### Community 37 - "slack.py"
Cohesion: 0.08
Nodes (14): build_access_denied_home_view(), build_home_tab_view(), _context_line(), create_feedback_block(), format_plan_block(), format_task_card(), format_turn(), _md_table_to_text() (+6 more)

### Community 38 - "AgentClient"
Cohesion: 0.08
Nodes (4): Architect, AgentClient, Developer, SysAdmin

### Community 39 - "lifespan"
Cohesion: 0.06
Nodes (10): set_incident_options(), set_agents(), set_archivist(), set_argocd_observer(), set_blackboard(), set_brain(), set_kargo_observer(), set_kg_store() (+2 more)

### Community 40 - "ui/package.json"
Cohesion: 0.07
Nodes (30): autoprefixer, cronstrue, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, graphology-layout-forceatlas2 (+22 more)

### Community 42 - "TimeKeeperPage.tsx"
Cohesion: 0.13
Nodes (20): createSchedule(), getSchedules(), ScheduleCreatePayload, ScheduleItem, Props, ScheduleForm(), TEMPLATES, formatNextFire() (+12 more)

### Community 43 - "NodeInspector.tsx"
Cohesion: 0.11
Nodes (26): getClosedEvents(), getEvents(), ArchitectureEvent, ArgoCDOperation, ActivityStream(), ArchitectureGraph(), EVENT_LABELS, EventItem() (+18 more)

### Community 44 - "main.py"
Cohesion: 0.09
Nodes (12): set_pulse_tracker(), agent_ws_endpoint(), api_info(), get_config(), get_event_flow(), get_flow_history(), health_check(), list_agents() (+4 more)

### Community 45 - "ws-client.js"
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

### Community 47 - "useCortexData.ts"
Cohesion: 0.17
Nodes (27): getCognitiveGraph(), getCortexActivity(), getEventReport(), getKGServiceDetail(), getKGServices(), getKGStats(), getKnowledgeById(), getMemory() (+19 more)

### Community 48 - "CortexGraph.tsx"
Cohesion: 0.13
Nodes (27): graphology, @react-sigma/layout-forceatlas2, eventColor(), getExecutiveNeurons(), getStructuralEdges(), DEFAULT_TYPE_BUDGET, evictLru(), KNOWLEDGE_RING (+19 more)

### Community 50 - "EventDrillDown.tsx"
Cohesion: 0.13
Nodes (22): three, getEventPulses(), EventSource, BrainCore(), CortexLiveFeedProps, EventDrillDown(), EventDrillDownProps, FRICTION_COLORS (+14 more)

### Community 51 - "KnowledgeGraphStore"
Cohesion: 0.15
Nodes (4): _acquire(), KnowledgeGraphStore, _sanitize(), _with_timeout()

### Community 52 - "StreamGrid.tsx"
Cohesion: 0.13
Nodes (22): getFlowMetrics(), FlowMetrics, AgentStreamCard(), AgentStreamCardProps, FloatingWindow(), MessageCards(), Dashboard(), FlowHealthWidget() (+14 more)

### Community 53 - "http-handler.js"
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

### Community 54 - "server.js"
Cohesion: 0.09
Nodes (17): hasRegistryCredentials(), { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, fs, path, stageEventDocument(), fetchEventDocument(), fs, { handleRequest } (+9 more)

### Community 56 - "observations_mgmt.py"
Cohesion: 0.10
Nodes (10): get_report_client(), render_pdf(), bulk_delete_observations(), BulkDeleteRequest, delete_observation(), export_observations(), generate_observations_report(), rename_observation() (+2 more)

### Community 57 - "adf_to_markdown"
Cohesion: 0.12
Nodes (10): _adf_to_text(), _escape_jql_string(), JiraIncidentAdapter, adf_to_markdown(), _apply_marks(), _children(), _render(), _render_list() (+2 more)

### Community 60 - "llm/__init__.py"
Cohesion: 0.16
Nodes (5): FunctionCall, LLMChunk, LLMPort, LLMResponse, TokenUsage

### Community 62 - "dependencies"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 63 - "reconcile.py"
Cohesion: 0.15
Nodes (9): _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers(), main(), _parse_frontmatter() (+1 more)

### Community 64 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 65 - "ArchitectureGraph.tsx"
Cohesion: 0.13
Nodes (19): @dagrejs/dagre, applyDagreLayout(), applyGridLayout(), applyLayout(), ArchitectureGraphInner(), buildGraph(), computeIdHash(), edgeTypes (+11 more)

### Community 66 - "TokenUtilizationPage.tsx"
Cohesion: 0.16
Nodes (17): recharts, getFlowHistory(), FlowSnapshot, ObservationSeries, FlowHistoryPage(), formatTime(), RANGES, SparkCard() (+9 more)

### Community 68 - "BrainIntrospectionPort"
Cohesion: 0.10
Nodes (3): BrainIntrospectionPort, BrainLifecyclePort, BroadcastPort

### Community 69 - "state/__init__.py"
Cohesion: 0.12
Nodes (3): close_redis(), get_redis(), RedisClient

### Community 71 - "cli-setup.js"
Cohesion: 0.13
Nodes (19): { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync }, filterSkillsByMode() (+11 more)

### Community 74 - "cognitive_graph.py"
Cohesion: 0.14
Nodes (9): get_pulse_tracker(), get_all_shadow_interventions(), get_cognitive_graph(), get_cortex_activity(), get_cortex_status(), get_event_shadow_interventions(), get_handoff_reports(), get_proposals() (+1 more)

### Community 75 - "PulseBatch"
Cohesion: 0.12
Nodes (4): PulseBatch, PulsePort, PulseObserver, PulseTracker

### Community 76 - "claude-guard.js"
Cohesion: 0.14
Nodes (16): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+8 more)

### Community 77 - "auth.py"
Cohesion: 0.16
Nodes (7): _claims_to_user(), get_user_from_request(), get_user_from_websocket(), require_auth(), require_obs_admin(), UserContext, _validate_jwt()

### Community 78 - "observations_reporter.py"
Cohesion: 0.15
Nodes (8): _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), _sample_points(), _summarize(), download_skill_md()

### Community 79 - "StateWatcher"
Cohesion: 0.13
Nodes (3): _QueueEntry, StateWatcher, _Subscription

### Community 82 - "devDependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 83 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 84 - "ServiceNode.tsx"
Cohesion: 0.15
Nodes (13): @xyflow/react, HealthStatus, NodeType, AppNodeData, ARGOCD_HEALTH_COLORS, SYNC_ICONS, NamespaceGroupNodeData, GENERIC_TAGS (+5 more)

### Community 85 - "get_report"
Cohesion: 0.11
Nodes (6): get_report(), list_reports(), reports_spa_no_slash(), reports_spa_with_slash(), search_reports(), _serve_spa()

### Community 86 - "gemini-sidecar/package.json"
Cohesion: 0.11
Nodes (17): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+9 more)

### Community 90 - "ShiftsPage.tsx"
Cohesion: 0.23
Nodes (16): getCurrentShift(), getShiftDetail(), getShiftsList(), ShiftReportFull, ShiftReportSummary, FailedClusterBadge(), getISOWeek(), getWeekDates() (+8 more)

### Community 91 - "catalog-skills.js"
Cohesion: 0.16
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 95 - "._gate_check"
Cohesion: 0.21
Nodes (7): get_user_from_slack(), format_event_summary(), handle_approve(), handle_create_event_modal(), handle_darwin_command(), handle_reject(), on_dm_message()

### Community 96 - "scheduling/__init__.py"
Cohesion: 0.17
Nodes (5): GitHubPrRef, GitLabMrRef, GitLabPipelineRef, KargoStageRef, PollFn

### Community 97 - "DeferCountdownBar.tsx"
Cohesion: 0.24
Nodes (12): ConversationTurn, DeferCountdownBar(), PlanProgressProps, PlanStep, STATUS_ICON, DeferCountdownState, useDeferCountdown(), computeDeferProgress() (+4 more)

### Community 98 - "generate_map.py"
Cohesion: 0.19
Nodes (6): _enumerate_gates(), _GateInfo, generate_phase_tool_map(), _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 101 - "TaskBridge"
Cohesion: 0.18
Nodes (4): consume_wake_task(), _dispatch_timeout_s(), send_cancel(), TaskBridge

### Community 102 - "delete_schedule"
Cohesion: 0.13
Nodes (3): delete_schedule(), get_schedule(), toggle_schedule()

### Community 103 - "ReconcileScheduler"
Cohesion: 0.16
Nodes (3): ReconcileScheduler, QueueTrigger, StalenessGuard

### Community 106 - "create_chat_event"
Cohesion: 0.15
Nodes (6): can_append_message(), can_override_domain(), _normalize_email(), ChatEventRequest, ChatEventResponse, create_chat_event()

### Community 107 - "nightwatcher_prompt.py"
Cohesion: 0.16
Nodes (6): build_manifest_table(), build_report_iteration_prompt(), build_summary_prompt(), build_system_prompt(), extract_event_links(), _normalize_gitlab_host()

### Community 109 - "._extract_context_flags"
Cohesion: 0.15
Nodes (3): compute_dispatch_backpressure(), ContextFlags, _safe_int_env()

### Community 111 - "IncidentAdapterPort"
Cohesion: 0.15
Nodes (3): IdleTimeoutPort, IncidentAdapterPort, StateWatcherPort

### Community 112 - "._send_turn_to_thread"
Cohesion: 0.19
Nodes (5): extract_tables(), _replace(), get_agent_notification_text(), get_turn_attachment_color(), _md_table_to_block_kit()

### Community 113 - "JarvisMemoryPage.tsx"
Cohesion: 0.27
Nodes (12): dismissProposals(), EnhancementProposal, getHandoffReports(), getProposals(), HandoffReport, FilterMode, formatDate(), formatTime() (+4 more)

### Community 114 - "NeuronInfoPanel.tsx"
Cohesion: 0.24
Nodes (12): KGServiceDetail, asNumber(), asString(), asStringArray(), Badge(), describeNeuron(), Hdr(), NeuronInfoPanel() (+4 more)

### Community 121 - "CortexLiveFeed.tsx"
Cohesion: 0.24
Nodes (10): CortexHeartbeat(), CortexHeartbeatProps, ensureKeyframes(), CortexLiveFeed(), FILTER_PILLS, FilterKey, getStoredFilter(), MESSAGE_STYLES (+2 more)

### Community 122 - "_prepare_console_tail"
Cohesion: 0.18
Nodes (6): _annotation_replace(), _strip_pipeline_annotations(), _prepare_console_tail(), _redact_match(), _redact_secrets_in_text(), _sanitize_console_tail()

### Community 123 - "is_defer_event_available"
Cohesion: 0.18
Nodes (6): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 125 - "cortex-constants.ts"
Cohesion: 0.18
Nodes (10): AGENTS, DOMAINS, HEMISPHERE_X, NEURON_DESCRIPTIONS, PHASE_SKILL_FOLDERS, PHASE_TOOL_PRIORITY, PHASES, StructuralEdge (+2 more)

### Community 126 - "CortexDevPage.tsx"
Cohesion: 0.31
Nodes (9): CortexDevPage(), devQueryClient, MOCK_CORTEX_STATUS, MOCK_EVENT_ID, MOCK_NEURONS, MOCK_PULSE_BATCHES, MOCK_SHADOW, MOCK_THINKING (+1 more)

### Community 127 - "SecurityError"
Cohesion: 0.24
Nodes (4): _check_security(), safe_execution(), wrapper(), SecurityError

### Community 129 - "entity_extractor.py"
Cohesion: 0.33
Nodes (5): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship

### Community 130 - "knowledge_graph_api.py"
Cohesion: 0.31
Nodes (4): get_kg_store(), get_service_detail(), get_stats(), list_services()

### Community 131 - "get_quota_tracker"
Cohesion: 0.22
Nodes (3): get_quota_tracker(), llm_stats(), receive_telemetry()

### Community 145 - "vite.config.ts"
Cohesion: 0.29
Nodes (4): @tailwindcss/vite, vite, @vitejs/plugin-react, vitest

### Community 146 - "_format_graph_context"
Cohesion: 0.38
Nodes (3): _format_graph_context(), _parse_props(), _sanitize()

### Community 148 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 149 - "validate-mutations.sh"
Cohesion: 0.73
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

### Community 166 - "Neuron"
Cohesion: 0.60
Nodes (5): ActiveEvent, KGServiceEntity, CortexGraphProps, GraphLoaderProps, Neuron

## Knowledge Gaps
- **14 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+9 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2091 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **112 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `logging`, `ConversationTurn`, `queue.py`, `brain.py`, `Brain`, `_is_event_closed_or_missing`, `HeadhunterJira`, `live_api_adapter.py`, `BrainSkillLoader`, `ConversationMessage`, `EventDocument`, `update_notebook_note`, `TopologyRepository`, `nightwatcher_tools.py`, `._restage_pending_signal`, `._stage_pending_signal`, `ScheduleRepository`, `submit_feedback`, `get_notebook`, `slack.py`, `._count_pending`, `lifespan`, `.cleanup_stale_services`, `main.py`, `._commit_pending_signal`, `._drain_pending`, `.drain_notes`, `.get_edge_metadata`, `LiveAPIAdapter`, `observations_mgmt.py`, `DashboardWSAdapter`, `state/__init__.py`, `observations_reporter.py`, `get_report`, `delete_schedule`, `create_chat_event`, `NightwatcherObserver`?**
  _High betweenness centrality (0.098) - this node is a cross-community bridge._
- **Are the 78 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 78 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _14 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.01147576613779613 - nodes in this community are weakly interconnected._
- **Why does `Brain` connect `Brain` to `._post_agent_recall`, `logging`, `ConversationTurn`, `BlackboardState`, `queue.py`, `brain.py`, `._run_agent_task`, `._cleanup_stale_events`, `live_api_adapter.py`, `BrainSkillLoader`, `EventDocument`, `._process_with_llm`, `.stop_event_loop`, `ResyncTrigger`, `slack.py`, `lifespan`, `main.py`, `.append_and_broadcast`, `DashboardWSAdapter`, `BrainIntrospectionPort`, `PulseBatch`, `StateWatcher`, `ReflexSearcher`, `._build_contents`, `IdleTimeoutManager`, `ReconcileScheduler`, `QuotaTracker`, `._extract_context_flags`, `.start_event_loop`?**
  _High betweenness centrality (0.078) - this node is a cross-community bridge._
- **Are the 20 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Should `logging` be split into smaller, more focused modules?**
  _Cohesion score 0.0258727881396461 - nodes in this community are weakly interconnected._