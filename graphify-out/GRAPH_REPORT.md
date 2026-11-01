# Graph Report - Blackboard  (2026-11-01)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 4911 nodes · 10952 edges · 181 communities (87 shown, 94 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 927 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `a9af8709`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BlackboardState
- logging
- brain.py
- dependencies.py
- queue.py
- client.ts
- Brain
- EventChatPanel.tsx
- tool_gates.py
- EventDocument
- SlackChannel
- merge-guard.js
- ._process_with_llm
- hooks/index.ts
- ReconcileScheduler
- EventSidebar.tsx
- api/types.ts
- main.py
- credentials.js
- BrainSkillLoader
- jenkins-mcp.js
- lucide-react
- HeadhunterJira
- useMemory.ts
- App.tsx
- TurnBubble.tsx
- ToolContext
- GitHubPlatform
- Service
- _BrainToolContext
- GitLabPlatform
- EventRepository
- Archivist
- nightwatcher_tools.py
- cli-executor.js
- dispatch.py
- storage-recycler.js
- ArchitectureGraph.tsx
- JenkinsAdapter
- ui/package.json
- Headhunter
- JenkinsObserver
- jira.py
- EventDrillDown.tsx
- slack.py
- AgentClient
- Aligner
- ConversationTurn
- VectorStore
- ActiveStreamsContext.tsx
- ws-client.js
- ._close_and_broadcast
- fetchApi
- EventHistory.tsx
- handlers_integration.py
- GeminiAdapter
- KnowledgeGraphStore
- useQueue.ts
- server.js
- ._triage_and_build_evidence
- CortexGraph.tsx
- LiveAPIAdapter
- AgentRegistry
- adf_to_markdown
- IdleTimeoutManager
- ArgoCDObserver
- NeuronInfoPanel.tsx
- reconcile.py
- llm/__init__.py
- scheduling/__init__.py
- StateWatcher
- context_parts.py
- KargoObserver
- TopologyRepository
- dependencies
- http-handler.js
- compilerOptions
- claude-guard.js
- DashboardWSAdapter
- GitHubAppAuth
- VcsPlatformPort
- PulseBatch
- ReflexSearcher
- devDependencies
- compilerOptions
- EphemeralProvisioner
- generate_observations_report
- get_report
- gemini-sidecar/package.json
- ObservationRepository
- ShiftsPage.tsx
- QuotaTracker
- OIDCKeyAdapter
- .scroll
- handle_classify_event
- ClaudeAdapter
- catalog-skills.js
- react
- generate_map.py
- KubernetesSpawnHealthAdapter
- graph_recall.py
- EscalationRepository
- RedisClient
- ScheduleRepository
- nightwatcher_prompt.py
- MultiInstallationManager
- ScheduleCreateRequest
- FilterRule
- ._extract_context_flags
- TokenMeter
- ._github_poll_and_process
- SlackAccessGate
- CortexLiveFeed.tsx
- is_defer_event_available
- NightwatcherObserver
- ._post_agent_recall
- entity_extractor.py
- has_unevaluated_close_blocker
- knowledge_graph_api.py
- get_quota_tracker
- SpawnPollResult
- SmartsheetMaintainerCache
- AsyncGitHubClient
- GitLabTokenAuth
- _is_event_closed_or_missing
- ._evaluate_health
- resolve_maintainer_emails
- TimeKeeperObserver
- CortexRepository
- update_schedule
- scripts
- state.js
- validate-mutations.sh
- ._process_message
- DispatchMetrics
- SpawnStatus
- list_failed_stages
- dex_proxy
- _BatchContext
- ._wait_for_registration
- agent_ws_endpoint
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
1. `BlackboardState` - 280 edges
2. `Brain` - 148 edges
3. `ConversationTurn` - 122 edges
4. `ToolContext` - 103 edges
5. `GateContext` - 94 edges
6. `react` - 81 edges
7. `EventDocument` - 78 edges
8. `fetchApi()` - 65 edges
9. `lifespan()` - 64 edges
10. `LiveAPIAdapter` - 58 edges

## Surprising Connections (you probably didn't know these)
- `get_flow_history()` --uses--> `FlowSnapshot`  [INFERRED]
  src/main.py → src/models.py
- `FlowCollector` --uses--> `FlowSnapshot`  [INFERRED]
  src/observers/flow_collector.py → src/models.py
- `DashboardWSAdapter` --uses--> `BlackboardState`  [INFERRED]
  src/adapters/dashboard_ws.py → src/state/blackboard.py
- `LiveAPIAdapter` --uses--> `BlackboardState`  [INFERRED]
  src/adapters/live_api_adapter.py → src/state/blackboard.py
- `Brain` --uses--> `BlackboardState`  [INFERRED]
  src/agents/brain.py → src/state/blackboard.py

## Import Cycles
- None detected.

## Communities (181 total, 94 thin omitted)

### Community 0 - "BlackboardState"
Cohesion: 0.01
Nodes (14): FlowSnapshot, get_all_journal(), get_service_journal(), delete_notebook_note(), get_notebook(), get_event_observations(), get_global_observations(), export_observations() (+6 more)

### Community 1 - "logging"
Cohesion: 0.03
Nodes (23): _annotation_replace(), _strip_pipeline_annotations(), _heartbeat(), _sanitize_lesson_text(), _get_static_maintainer_emails(), _get_allowed_mention_authors(), _get_static_maintainer_emails(), _safe_int() (+15 more)

### Community 2 - "brain.py"
Cohesion: 0.03
Nodes (41): _safe_int(), get_flow_metrics(), AppNode, ArchitectureEvent, ChatRequest, ChatResponse, CIAnalysis, EventEvidence (+33 more)

### Community 3 - "dependencies.py"
Cohesion: 0.03
Nodes (39): can_append_message(), can_approve_event(), can_override_domain(), _claims_to_user(), get_user_from_request(), get_user_from_slack(), get_user_from_websocket(), _normalize_email() (+31 more)

### Community 4 - "queue.py"
Cohesion: 0.03
Nodes (51): resolve_approval_identity(), get_archivist(), get_brain(), EventStatus, report_tampering(), aligner_pending_items(), apply_lessons(), approve_event() (+43 more)

### Community 5 - "client.ts"
Cohesion: 0.05
Nodes (71): @tanstack/react-query, bulkDeleteObservations(), createSchedule(), deleteNote(), deleteObservation(), deleteSchedule(), dismissProposals(), EnhancementProposal (+63 more)

### Community 7 - "EventChatPanel.tsx"
Cohesion: 0.06
Nodes (54): ConversationTurn, EventEvidence, ReportFull, ReportMeta, TokenUsageDict, DeferCountdownBar(), GridTile(), Props (+46 more)

### Community 8 - "tool_gates.py"
Cohesion: 0.05
Nodes (78): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+70 more)

### Community 9 - "EventDocument"
Cohesion: 0.03
Nodes (11): _close_unanswered_fc(), _build_closed_block(), build_event_header(), _build_identity_block(), _build_journal_block(), _build_mermaid_block(), _build_related_block(), _build_subject_block() (+3 more)

### Community 10 - "SlackChannel"
Cohesion: 0.05
Nodes (14): extract_tables(), _replace(), get_agent_notification_text(), get_turn_attachment_color(), _md_table_to_block_kit(), SlackChannel, handle_app_home_opened(), handle_app_mention() (+6 more)

### Community 11 - "merge-guard.js"
Cohesion: 0.05
Nodes (69): analyzeString(), analyzeTokens(), API_VALUED, apiTokens(), apiWriteNeedsGuard(), assignName(), bareBranchProtected(), base() (+61 more)

### Community 12 - "._process_with_llm"
Cohesion: 0.05
Nodes (9): on_huddle(), on_progress(), on_huddle(), on_progress(), _compute_processed_up_to(), _sanitize_error_text(), _sanitize_override_reason(), _select_dispatch_tier() (+1 more)

### Community 13 - "hooks/index.ts"
Cohesion: 0.05
Nodes (52): ApiError, createChatEvent(), getClosedEvents(), getEvents(), getFlowMetrics(), getGraphData(), getService(), getTopology() (+44 more)

### Community 14 - "ReconcileScheduler"
Cohesion: 0.04
Nodes (7): FlowCollector, FairQueue, ReconcileScheduler, Trigger, QueueTrigger, ResyncTrigger, StalenessGuard

### Community 15 - "EventSidebar.tsx"
Cohesion: 0.07
Nodes (59): getHeadhunterPending(), getJiraMissions(), HeadhunterTodo, postJiraAction(), JenkinsPendingItem, JiraMission, ChatInput(), ACTION_BADGE (+51 more)

### Community 16 - "api/types.ts"
Cohesion: 0.05
Nodes (55): recharts, getFlowHistory(), Agent, AlignerPendingItem, AppNode, AuthUser, BulkDeleteRequest, ChatEventRequest (+47 more)

### Community 17 - "main.py"
Cohesion: 0.04
Nodes (21): set_incident_options(), set_agents(), set_archivist(), set_argocd_observer(), set_blackboard(), set_brain(), set_kargo_observer(), set_kg_store() (+13 more)

### Community 18 - "credentials.js"
Cohesion: 0.07
Nodes (58): is429Error(), { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync } (+50 more)

### Community 19 - "BrainSkillLoader"
Cohesion: 0.04
Nodes (4): BrainSkillLoader, _SkillCorpus, _wrap_section(), BrainIntrospectionPort

### Community 20 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 21 - "lucide-react"
Cohesion: 0.07
Nodes (45): lucide-react, react-router-dom, getAgents(), getKargoStages(), AgentRegistryEntry, KargoStageStatus, AgentRegistryPanel(), formatConnectedSince() (+37 more)

### Community 22 - "HeadhunterJira"
Cohesion: 0.05
Nodes (3): HeadhunterJira, _walk_adf_mentions(), _walk()

### Community 23 - "useMemory.ts"
Cohesion: 0.07
Nodes (51): applyLessons(), correctMemory(), createKnowledge(), createLesson(), deleteKnowledge(), deleteLesson(), ExtractedCorrection, ExtractedLesson (+43 more)

### Community 24 - "App.tsx"
Cohesion: 0.07
Nodes (42): oidc-client-ts, getConfig(), getWSAuthFailureCallback(), setOnUnauthorized(), setTokenGetter(), setWSAuthFailureCallback(), AppConfig, AuthConfig (+34 more)

### Community 25 - "TurnBubble.tsx"
Cohesion: 0.08
Nodes (41): react-dom, @uiw/react-markdown-preview, approveEvent(), closeEvent(), enforceCasualDomain(), rejectEvent(), submitFeedback(), ConversationFeed() (+33 more)

### Community 26 - "ToolContext"
Cohesion: 0.08
Nodes (14): handle_message_agent(), handle_reply_to_agent(), handle_report_incident(), handle_select_agent(), _resolve_escalation_scope(), handle_notify_gitlab_result(), handle_search_open_incidents(), handle_close_event() (+6 more)

### Community 27 - "GitHubPlatform"
Cohesion: 0.06
Nodes (3): GitHubPlatform, _poll_one(), _poll_one()

### Community 28 - "Service"
Cohesion: 0.05
Nodes (8): GraphResponse, Service, get_graph_data(), get_mermaid_diagram(), get_service_details(), get_topology(), list_services(), calculate_health_from_argocd()

### Community 33 - "nightwatcher_tools.py"
Cohesion: 0.09
Nodes (20): PulseContext, ShiftIncident, ShiftInvestigation, extract_full_links(), build_extend_tool(), build_report_tool(), build_summary_tool(), execute_tool() (+12 more)

### Community 34 - "cli-executor.js"
Cohesion: 0.09
Nodes (36): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS, STORAGE_PRETASK_TIMEOUT_MS, resolveStorageRoot }, buildCLICommand(), { checkAndRecycleStorage, pinTaskCwd, unpinTaskCwd }, CLAUDE_JSON_PATH, cp, executeCLI(), executeCLIStreaming(), FALLBACK_MODEL (+28 more)

### Community 35 - "dispatch.py"
Cohesion: 0.08
Nodes (13): _build_prompt(), _check_security(), consume_wake_task(), _consume(), _dispatch_timeout_s(), dispatch_to_agent(), _consume_queue(), _sanitize_stdout() (+5 more)

### Community 36 - "storage-recycler.js"
Cohesion: 0.08
Nodes (34): withTaskStorage(), resolveStorageRoot(), ROLE_TIMEOUTS, STORAGE_ACTIVITY_HEARTBEAT_MS, STORAGE_MAX_TIER3_DELETIONS, STORAGE_PRETASK_TIMEOUT_MS, STORAGE_RESULTS_TTL_MS, STORAGE_STALE_MS (+26 more)

### Community 37 - "ArchitectureGraph.tsx"
Cohesion: 0.07
Nodes (33): @dagrejs/dagre, @xyflow/react, HealthStatus, NodeType, AppNodeData, applyDagreLayout(), applyGridLayout(), applyLayout() (+25 more)

### Community 38 - "JenkinsAdapter"
Cohesion: 0.06
Nodes (6): BuildDetails, JenkinsAdapter, JenkinsPlatformPort, JobResult, JobRunState, ViewScanResult

### Community 39 - "ui/package.json"
Cohesion: 0.06
Nodes (34): autoprefixer, cronstrue, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, graphology-layout-forceatlas2 (+26 more)

### Community 42 - "jira.py"
Cohesion: 0.08
Nodes (15): _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), _sample_points(), _summarize(), approve_mission() (+7 more)

### Community 43 - "EventDrillDown.tsx"
Cohesion: 0.10
Nodes (32): three, getEventPulses(), EventSource, BrainCore(), CortexDevPage(), devQueryClient, CortexLiveFeedProps, EventDrillDown() (+24 more)

### Community 44 - "slack.py"
Cohesion: 0.08
Nodes (15): build_access_denied_home_view(), build_home_tab_view(), _context_line(), create_feedback_block(), format_event_summary(), format_plan_block(), format_task_card(), format_turn() (+7 more)

### Community 45 - "AgentClient"
Cohesion: 0.07
Nodes (4): Architect, AgentClient, Developer, SysAdmin

### Community 47 - "ConversationTurn"
Cohesion: 0.15
Nodes (20): emit_tool_result(), handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_recall_pruned_turns(), _sticky_work_style(), handle_consult_deep_memory(), handle_google_web_search() (+12 more)

### Community 49 - "ActiveStreamsContext.tsx"
Cohesion: 0.13
Nodes (26): AgentStreamCard(), AgentStreamCardProps, FloatingWindow(), MessageCards(), Dashboard(), GridTile(), GridTileProps, TileType (+18 more)

### Community 50 - "ws-client.js"
Cohesion: 0.10
Nodes (25): {
  DEFAULT_WORK_DIR, AGENT_CLI, AGENT_MODEL, AGENT_ROLE,
  EVENT_ID, EPHEMERAL, IDLE_TIMEOUT_MS,
  CLI_429_MAX_RETRIES, CLI_429_INITIAL_DELAY_MS, CLI_429_BACKOFF_MULTIPLIER,
}, { ensureEventDocument }, { executeCLIStreaming, prepareResultsDir, is429Error }, { filterSkillsByRole, filterSkillsByMode, swapActiveRules, restoreAllSkills }, fs, handleCancel(), resetTimer(), {
  hasGitHubCredentials, discoverAndGenerateTokens, setupGitCredentials, setupGitHubTooling,
  hasGitLabCredentials, readGitLabToken, setupGitLabCredentials, setupGitLabTooling,
  setupArgoCDMCP, setupCLILogins, setupRemoteK8sMCPs, setupRegistryCredentials, GITLAB_HOST,
  hasJenkinsCredentials, setupJenkinsMCP, hasGoogleServiceAccount, setupGoogleAuthForAgy,
} (+17 more)

### Community 51 - "._close_and_broadcast"
Cohesion: 0.07
Nodes (3): _has_non_user_turns(), _is_seed_turn(), get_token_meter()

### Community 53 - "fetchApi"
Cohesion: 0.17
Nodes (28): fetchApi(), getCognitiveGraph(), getCortexActivity(), getEventReport(), getKGServiceDetail(), getKGServices(), getKGStats(), getKnowledgeById() (+20 more)

### Community 54 - "EventHistory.tsx"
Cohesion: 0.12
Nodes (24): getReport(), getReports(), ReportSearchParams, searchReports(), ReportSearchResponse, CompactCardStrip(), EventHistory(), TimeRange (+16 more)

### Community 55 - "handlers_integration.py"
Cohesion: 0.10
Nodes (15): _alert_wrapper_retrigger(), _do_retrigger(), _get_jira_reporter(), handle_ask_release_ai(), handle_comment_jira_issue(), handle_fetch_jira_issue(), handle_greenwave(), handle_notify_user_slack() (+7 more)

### Community 57 - "KnowledgeGraphStore"
Cohesion: 0.15
Nodes (4): _acquire(), KnowledgeGraphStore, _sanitize(), _with_timeout()

### Community 58 - "useQueue.ts"
Cohesion: 0.12
Nodes (25): getActiveEvents(), getAlignerPending(), getEventDocument(), getJenkinsPending(), getWaitingApprovalEvents(), ActiveEvent, EventDocument, KGServiceEntity (+17 more)

### Community 59 - "server.js"
Cohesion: 0.09
Nodes (19): hasRegistryCredentials(), { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, ensureEventDocument(), fs, path, stageEventDocument(), fetchEventDocument(), fs (+11 more)

### Community 60 - "._triage_and_build_evidence"
Cohesion: 0.09
Nodes (10): _clamp_confidence(), _prepare_console_tail(), _redact_build_parameters(), _redact_match(), _redact_secrets_in_text(), _sanitize_analysis_text(), _sanitize_console_tail(), _strip_newlines() (+2 more)

### Community 61 - "CortexGraph.tsx"
Cohesion: 0.14
Nodes (25): graphology, eventColor(), getExecutiveNeurons(), getStructuralEdges(), DEFAULT_TYPE_BUDGET, evictLru(), KNOWLEDGE_RING, KNOWLEDGE_RING_TYPES (+17 more)

### Community 63 - "AgentRegistry"
Cohesion: 0.10
Nodes (3): AgentConnection, AgentRegistry, agent_websocket_handler()

### Community 64 - "adf_to_markdown"
Cohesion: 0.12
Nodes (10): _adf_to_text(), _escape_jql_string(), JiraIncidentAdapter, adf_to_markdown(), _apply_marks(), _children(), _render(), _render_list() (+2 more)

### Community 65 - "IdleTimeoutManager"
Cohesion: 0.08
Nodes (3): BrainLifecyclePort, BroadcastPort, IdleTimeoutManager

### Community 67 - "NeuronInfoPanel.tsx"
Cohesion: 0.11
Nodes (23): KGServiceDetail, AGENTS, DOMAINS, HEMISPHERE_X, NEURON_DESCRIPTIONS, PHASE_SKILL_FOLDERS, PHASE_TOOL_PRIORITY, PHASES (+15 more)

### Community 68 - "reconcile.py"
Cohesion: 0.15
Nodes (10): sanitize_redis_port(), _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers(), main() (+2 more)

### Community 69 - "llm/__init__.py"
Cohesion: 0.16
Nodes (5): FunctionCall, LLMChunk, LLMPort, LLMResponse, TokenUsage

### Community 70 - "scheduling/__init__.py"
Cohesion: 0.14
Nodes (11): handle_refresh_github_context(), handle_refresh_gitlab_context(), handle_refresh_kargo_context(), StateWatcherPort, GitHubPrRef, GitLabMrRef, GitLabPipelineRef, KargoStageRef (+3 more)

### Community 72 - "context_parts.py"
Cohesion: 0.11
Nodes (10): _apply_sibling_signature(), build_function_response(), build_single_function_response(), compress_contents(), estimate_msg_tokens(), estimate_tokens(), extract_model_parts(), normalize_response_parts() (+2 more)

### Community 75 - "dependencies"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 76 - "http-handler.js"
Cohesion: 0.12
Nodes (19): getRemoteClustersMeta(), hasGitLabCredentials(), setupGitLabCredentials(), setupRegistryCredentials(), { AGENT_CLI, AGENT_MODEL, DEFAULT_WORK_DIR, PORT, BRAIN_HTTP_URL }, { claudeMergeGuard }, { executeCLI }, fs (+11 more)

### Community 77 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 78 - "claude-guard.js"
Cohesion: 0.14
Nodes (18): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+10 more)

### Community 82 - "PulseBatch"
Cohesion: 0.12
Nodes (4): PulseBatch, PulsePort, PulseObserver, PulseTracker

### Community 84 - "devDependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 85 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 87 - "generate_observations_report"
Cohesion: 0.11
Nodes (8): render_pdf(), bulk_delete_observations(), BulkDeleteRequest, delete_observation(), generate_observations_report(), rename_observation(), RenameRequest, ReportRequest

### Community 88 - "get_report"
Cohesion: 0.11
Nodes (6): get_report(), list_reports(), reports_spa_no_slash(), reports_spa_with_slash(), search_reports(), _serve_spa()

### Community 89 - "gemini-sidecar/package.json"
Cohesion: 0.11
Nodes (17): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+9 more)

### Community 92 - "ShiftsPage.tsx"
Cohesion: 0.23
Nodes (16): getCurrentShift(), getShiftDetail(), getShiftsList(), ShiftReportFull, ShiftReportSummary, FailedClusterBadge(), getISOWeek(), getWeekDates() (+8 more)

### Community 96 - "handle_classify_event"
Cohesion: 0.13
Nodes (5): handle_classify_event(), handle_request_user_approval(), handle_set_phase(), IdleTimeoutPort, IncidentAdapterPort

### Community 98 - "catalog-skills.js"
Cohesion: 0.17
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 99 - "react"
Cohesion: 0.22
Nodes (13): react, CiContext, CiContextCard(), CiContextCardProps, ConsoleTailBlock(), FailedJobRow(), CollapsibleSection(), CollapsibleSectionProps (+5 more)

### Community 100 - "generate_map.py"
Cohesion: 0.19
Nodes (6): _enumerate_gates(), _GateInfo, generate_phase_tool_map(), _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 102 - "graph_recall.py"
Cohesion: 0.19
Nodes (5): _format_graph_context(), get_graph_context(), _parse_props(), _sanitize(), translate_to_lookups()

### Community 106 - "nightwatcher_prompt.py"
Cohesion: 0.16
Nodes (6): build_manifest_table(), build_report_iteration_prompt(), build_summary_prompt(), build_system_prompt(), extract_event_links(), _normalize_gitlab_host()

### Community 110 - "._extract_context_flags"
Cohesion: 0.15
Nodes (3): compute_dispatch_backpressure(), ContextFlags, _safe_int_env()

### Community 117 - "CortexLiveFeed.tsx"
Cohesion: 0.24
Nodes (10): CortexHeartbeat(), CortexHeartbeatProps, ensureKeyframes(), CortexLiveFeed(), FILTER_PILLS, FilterKey, getStoredFilter(), MESSAGE_STYLES (+2 more)

### Community 118 - "is_defer_event_available"
Cohesion: 0.18
Nodes (6): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 121 - "entity_extractor.py"
Cohesion: 0.33
Nodes (5): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship

### Community 122 - "has_unevaluated_close_blocker"
Cohesion: 0.20
Nodes (4): has_unevaluated_close_blocker(), _pred_jarvis_response(), _pred_unevaluated_close(), is_jarvis_acknowledgment()

### Community 123 - "knowledge_graph_api.py"
Cohesion: 0.31
Nodes (4): get_kg_store(), get_service_detail(), get_stats(), list_services()

### Community 124 - "get_quota_tracker"
Cohesion: 0.22
Nodes (3): get_quota_tracker(), llm_stats(), receive_telemetry()

### Community 131 - "resolve_maintainer_emails"
Cohesion: 0.29
Nodes (3): _resolve_maintainer_enum(), maintainer_env_key(), resolve_maintainer_emails()

### Community 135 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 136 - "state.js"
Cohesion: 0.33
Nodes (4): { AGENT_ROLE }, _blackboardTurns, _inboundMessages, _teammateMessages

### Community 137 - "validate-mutations.sh"
Cohesion: 0.73
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

## Knowledge Gaps
- **13 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+8 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2144 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **94 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `logging`, `brain.py`, `_is_event_closed_or_missing`, `dependencies.py`, `queue.py`, `Brain`, `update_schedule`, `EventDocument`, `._restage_pending_signal`, `main.py`, `._stage_pending_signal`, `BrainSkillLoader`, `HeadhunterJira`, `Service`, `EventRepository`, `nightwatcher_tools.py`, `jira.py`, `slack.py`, `ConversationTurn`, `LiveAPIAdapter`, `DashboardWSAdapter`, `generate_observations_report`, `get_report`, `ScheduleRepository`, `NightwatcherObserver`?**
  _High betweenness centrality (0.092) - this node is a cross-community bridge._
- **Are the 79 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 79 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.011024978466838932 - nodes in this community are weakly interconnected._
- **Why does `Brain` connect `Brain` to `BlackboardState`, `logging`, `brain.py`, `dependencies.py`, `queue.py`, `EventDocument`, `._process_with_llm`, `._resolve_llm_params`, `ReconcileScheduler`, `main.py`, `BrainSkillLoader`, `dispatch.py`, `slack.py`, `ConversationTurn`, `._close_and_broadcast`, `IdleTimeoutManager`, `StateWatcher`, `DashboardWSAdapter`, `PulseBatch`, `ReflexSearcher`, `QuotaTracker`, `._extract_context_flags`, `._post_agent_recall`?**
  _High betweenness centrality (0.051) - this node is a cross-community bridge._
- **Are the 20 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Should `logging` be split into smaller, more focused modules?**
  _Cohesion score 0.03018867924528302 - nodes in this community are weakly interconnected._