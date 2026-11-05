# Graph Report - Blackboard  (2026-11-05)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 5032 nodes · 11241 edges · 200 communities (101 shown, 99 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 938 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `61486f89`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BlackboardState
- logging
- brain.py
- auth.py
- react
- client.ts
- Archivist
- jenkins_observer.py
- Brain
- tool_gates.py
- EventSidebar.tsx
- EventDocument
- os
- AgentRegistry
- main.py
- merge-guard.js
- App.tsx
- http-handler.js
- jenkins-mcp.js
- TurnBubble.tsx
- ._run_agent_task
- ReconcileScheduler
- fetchApi
- EventHistory.tsx
- Aligner
- ToolContext
- _BrainToolContext
- observations_mgmt.py
- BrainSkillLoader
- ConversationTurn
- EventRepository
- cli-executor.js
- ._process_with_llm
- storage-recycler.js
- JenkinsAdapter
- spawn_event_namer_task
- AgentClient
- GitHubPlatform
- CortexGraph.tsx
- record_token_usage
- SlackChannel
- GitLabPlatform
- Headhunter
- TimeKeeperPage.tsx
- .start_event_loop
- handlers_integration.py
- ws-client.js
- OpsStateContext.tsx
- ActiveStreamsContext.tsx
- ui/package.json
- IdleTimeoutManager
- EventDrillDown.tsx
- useCortexData.ts
- server.js
- slack.py
- ._build_system_prompt
- dependencies.py
- cognitive_graph.py
- KnowledgeGraphStore
- queue.py
- get_archivist
- NodeInspector.tsx
- ArgoCDObserver
- reconcile.py
- gemini_client.py
- ._get_manager
- GeminiAdapter
- KargoObserver
- TopologyRepository
- dependencies
- StateWatcher
- adf_to_markdown
- LiveAPIAdapter
- compilerOptions
- claude-guard.js
- TokenUtilizationPage.tsx
- DashboardWSAdapter
- context_parts.py
- .get_event
- GitHubAppAuth
- cli-setup.js
- VcsPlatformPort
- ReflexSearcher
- devDependencies
- compilerOptions
- ServiceNode.tsx
- EphemeralProvisioner
- update_event_title
- gemini-sidecar/package.json
- ArchitectureGraph.tsx
- ObservationRepository
- ShiftsPage.tsx
- catalog-skills.js
- handle_notify_user_slack
- ClaudeAdapter
- RedisClient
- EscalationRepository
- IncidentAdapterPort
- list_active_events
- generate_map.py
- OIDCKeyAdapter
- KubernetesSpawnHealthAdapter
- QuotaTracker
- PulseTracker
- cortex/types.ts
- _append_user_turn
- ScheduleRepository
- close_event_by_user
- MultiInstallationManager
- ._extract_context_flags
- get_graph_context
- TokenMeter
- ScheduleCreateRequest
- .list_observations
- NeuronInfoPanel.tsx
- SlackAccessGate
- CortexLiveFeed.tsx
- testSetup.ts
- is_defer_event_available
- create_chat_event
- CiContextCard.tsx
- spawn_health.py
- approve_event
- generate_event_title
- entity_extractor.py
- ._github_poll_and_process
- sanitize_call_syntax
- get_quota_tracker
- SpawnPollResult
- SmartsheetMaintainerCache
- .has_reeval_signal
- format_turn
- AsyncGitHubClient
- GitLabTokenAuth
- useDeferCountdown.ts
- _is_event_closed_or_missing
- ._evaluate_health
- HeadhunterJira
- has_unevaluated_close_blocker
- TimeKeeperObserver
- routes/kargo.py
- CortexRepository
- scripts
- state.js
- validate-mutations.sh
- ._process_message
- get_registry_and_bridge
- DispatchMetrics
- ._wait_for_registration
- extract_tables
- TicketNode.tsx
- derive_llm_priority
- headhunter_pending_todos
- require-results.sh
- TokenUsageDict
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

## Communities (200 total, 99 thin omitted)

### Community 0 - "BlackboardState"
Cohesion: 0.01
Nodes (11): get_all_journal(), get_service_journal(), get_notebook(), get_current_shift(), get_shift_detail(), list_shifts(), get_mermaid_diagram(), get_service_details() (+3 more)

### Community 1 - "logging"
Cohesion: 0.03
Nodes (35): JiraIncidentAdapter, _sanitize_lesson_text(), _safe_int(), Pulse, PulseBatch, PulseContext, PulsePort, ShiftIncident (+27 more)

### Community 2 - "brain.py"
Cohesion: 0.03
Nodes (40): AppNode, ArchitectureEvent, ChatRequest, ChatResponse, CIAnalysis, ConversationMessage, EventEvidence, EventInput (+32 more)

### Community 3 - "auth.py"
Cohesion: 0.02
Nodes (29): can_append_message(), _claims_to_user(), get_user_from_request(), get_user_from_websocket(), require_auth(), require_obs_admin(), resolve_approval_identity(), UserContext (+21 more)

### Community 4 - "react"
Cohesion: 0.04
Nodes (95): lucide-react, react, createChatEvent(), getActiveEvents(), getAlignerPending(), getEventDocument(), getEvents(), getJenkinsPending() (+87 more)

### Community 5 - "client.ts"
Cohesion: 0.03
Nodes (88): @tanstack/react-query, ApiError, bulkDeleteObservations(), deleteNote(), deleteObservation(), exportObservations(), ExtractedCorrection, ExtractedLesson (+80 more)

### Community 6 - "Archivist"
Cohesion: 0.04
Nodes (4): Archivist, _decode_cursor(), _encode_cursor(), VectorStore

### Community 7 - "jenkins_observer.py"
Cohesion: 0.03
Nodes (20): _annotation_replace(), _strip_pipeline_annotations(), _clamp_confidence(), _env_flag(), _flood_service_key(), JenkinsObserver, _outage_service_key(), _parse_job_metadata() (+12 more)

### Community 9 - "tool_gates.py"
Cohesion: 0.05
Nodes (78): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+70 more)

### Community 10 - "EventSidebar.tsx"
Cohesion: 0.07
Nodes (66): getHeadhunterPending(), getJiraMissions(), HeadhunterTodo, postJiraAction(), AgentRegistryEntry, DeferCountdownBar(), ACTION_BADGE, formatAge() (+58 more)

### Community 11 - "EventDocument"
Cohesion: 0.03
Nodes (11): _close_unanswered_fc(), _build_closed_block(), build_event_header(), _build_identity_block(), _build_journal_block(), _build_mermaid_block(), _build_related_block(), _build_subject_block() (+3 more)

### Community 12 - "os"
Cohesion: 0.05
Nodes (19): _get_static_maintainer_emails(), _get_allowed_mention_authors(), _get_static_maintainer_emails(), _safe_int(), dex_proxy(), list_incidents(), approve_mission(), dismiss_mission() (+11 more)

### Community 13 - "AgentRegistry"
Cohesion: 0.05
Nodes (17): AgentConnection, AgentRegistry, agent_websocket_handler(), _heartbeat(), _build_prompt(), _check_security(), consume_wake_task(), _consume() (+9 more)

### Community 14 - "main.py"
Cohesion: 0.04
Nodes (24): set_incident_options(), set_oidc_adapter(), set_agents(), set_archivist(), set_argocd_observer(), set_blackboard(), set_brain(), set_kargo_observer() (+16 more)

### Community 15 - "merge-guard.js"
Cohesion: 0.05
Nodes (69): analyzeString(), analyzeTokens(), API_VALUED, apiTokens(), apiWriteNeedsGuard(), assignName(), bareBranchProtected(), base() (+61 more)

### Community 16 - "App.tsx"
Cohesion: 0.06
Nodes (48): oidc-client-ts, react-dom, react-router-dom, getConfig(), getWSAuthFailureCallback(), setOnUnauthorized(), setTokenGetter(), setWSAuthFailureCallback() (+40 more)

### Community 17 - "http-handler.js"
Cohesion: 0.09
Nodes (58): resolveCommand(), writeAgyMcpServer(), writeClaudeMcpServer(), buildArgoCDMcpConfig(), createAppJWT(), discoverAndGenerateTokens(), _discoverAndGenerateTokensInner(), discoverInstallations() (+50 more)

### Community 18 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 19 - "TurnBubble.tsx"
Cohesion: 0.08
Nodes (44): @uiw/react-markdown-preview, approveEvent(), closeEvent(), enforceCasualDomain(), getEventReport(), rejectEvent(), submitFeedback(), ReportFull (+36 more)

### Community 20 - "._run_agent_task"
Cohesion: 0.06
Nodes (9): on_huddle(), on_progress(), on_huddle(), on_progress(), _compute_processed_up_to(), _is_automated_nudge(), _sanitize_error_text(), _sanitize_override_reason() (+1 more)

### Community 21 - "ReconcileScheduler"
Cohesion: 0.05
Nodes (6): FairQueue, ReconcileScheduler, Trigger, QueueTrigger, ResyncTrigger, StalenessGuard

### Community 22 - "fetchApi"
Cohesion: 0.08
Nodes (49): applyLessons(), correctMemory(), createKnowledge(), createLesson(), deleteKnowledge(), deleteLesson(), extractLessons(), fetchApi() (+41 more)

### Community 23 - "EventHistory.tsx"
Cohesion: 0.07
Nodes (35): getReport(), getReports(), ReportMeta, SubjectType, CompactCardStrip(), EventHistory(), TimeRange, ViewMode (+27 more)

### Community 25 - "ToolContext"
Cohesion: 0.07
Nodes (13): handle_message_agent(), handle_reply_to_agent(), handle_report_incident(), handle_select_agent(), _resolve_escalation_scope(), _sticky_work_style(), handle_classify_event(), handle_defer_event() (+5 more)

### Community 27 - "observations_mgmt.py"
Cohesion: 0.07
Nodes (17): _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), render_pdf(), _sample_points(), _summarize() (+9 more)

### Community 28 - "BrainSkillLoader"
Cohesion: 0.06
Nodes (3): BrainSkillLoader, _SkillCorpus, BrainIntrospectionPort

### Community 29 - "ConversationTurn"
Cohesion: 0.13
Nodes (30): emit_tool_result(), handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_recall_pruned_turns(), handle_ask_release_ai(), handle_comment_jira_issue(), handle_fetch_jira_issue() (+22 more)

### Community 31 - "cli-executor.js"
Cohesion: 0.09
Nodes (36): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS, STORAGE_PRETASK_TIMEOUT_MS, resolveStorageRoot }, buildCLICommand(), { checkAndRecycleStorage, pinTaskCwd, unpinTaskCwd }, CLAUDE_JSON_PATH, cp, executeCLI(), executeCLIStreaming(), FALLBACK_MODEL (+28 more)

### Community 33 - "storage-recycler.js"
Cohesion: 0.08
Nodes (34): withTaskStorage(), resolveStorageRoot(), ROLE_TIMEOUTS, STORAGE_ACTIVITY_HEARTBEAT_MS, STORAGE_MAX_TIER3_DELETIONS, STORAGE_PRETASK_TIMEOUT_MS, STORAGE_RESULTS_TTL_MS, STORAGE_STALE_MS (+26 more)

### Community 34 - "JenkinsAdapter"
Cohesion: 0.06
Nodes (6): BuildDetails, JenkinsAdapter, JenkinsPlatformPort, JobResult, JobRunState, ViewScanResult

### Community 35 - "spawn_event_namer_task"
Cohesion: 0.09
Nodes (13): spawn_event_namer_task(), can_approve_event(), get_user_from_slack(), format_event_summary(), handle_app_home_opened(), handle_app_mention(), handle_approve(), handle_create_event_modal() (+5 more)

### Community 36 - "AgentClient"
Cohesion: 0.07
Nodes (4): Architect, AgentClient, Developer, SysAdmin

### Community 38 - "CortexGraph.tsx"
Cohesion: 0.09
Nodes (35): graphology, AGENTS, DOMAINS, eventColor(), getExecutiveNeurons(), getStructuralEdges(), HEMISPHERE_X, NEURON_DESCRIPTIONS (+27 more)

### Community 39 - "record_token_usage"
Cohesion: 0.09
Nodes (7): record_token_usage(), QuotaExhaustedError, RequestExceedsBurstError, ShiftReport, _env_float(), _env_int(), NightwatcherObserver

### Community 40 - "SlackChannel"
Cohesion: 0.08
Nodes (3): get_agent_notification_text(), get_turn_attachment_color(), SlackChannel

### Community 43 - "TimeKeeperPage.tsx"
Cohesion: 0.12
Nodes (24): createSchedule(), deleteSchedule(), getSchedules(), refineInstructions(), ScheduleCreatePayload, ScheduleItem, toggleSchedule(), updateSchedule() (+16 more)

### Community 44 - ".start_event_loop"
Cohesion: 0.07
Nodes (5): _has_non_user_turns(), _is_seed_turn(), get_token_meter(), FlowSnapshot, FlowCollector

### Community 45 - "handlers_integration.py"
Cohesion: 0.11
Nodes (14): _do_retrigger(), _get_jira_reporter(), handle_refresh_github_context(), handle_refresh_gitlab_context(), handle_refresh_kargo_context(), _is_darwin_reentrant_caller(), jenkins_retrigger_cooldown_key(), format_jira_for_llm() (+6 more)

### Community 46 - "ws-client.js"
Cohesion: 0.09
Nodes (26): is429Error(), {
  DEFAULT_WORK_DIR, AGENT_CLI, AGENT_MODEL, AGENT_ROLE,
  EVENT_ID, EPHEMERAL, IDLE_TIMEOUT_MS,
  CLI_429_MAX_RETRIES, CLI_429_INITIAL_DELAY_MS, CLI_429_BACKOFF_MULTIPLIER,
}, { ensureEventDocument }, { executeCLIStreaming, prepareResultsDir, is429Error }, { filterSkillsByRole, filterSkillsByMode, swapActiveRules, restoreAllSkills }, fs, handleCancel(), resetTimer() (+18 more)

### Community 47 - "OpsStateContext.tsx"
Cohesion: 0.11
Nodes (28): dismissProposals(), EnhancementProposal, getAgents(), getHandoffReports(), getKargoStages(), getProposals(), HandoffReport, KargoStageStatus (+20 more)

### Community 48 - "ActiveStreamsContext.tsx"
Cohesion: 0.13
Nodes (26): AgentStreamCard(), AgentStreamCardProps, FloatingWindow(), MessageCards(), Dashboard(), GridTile(), GridTileProps, TileType (+18 more)

### Community 49 - "ui/package.json"
Cohesion: 0.08
Nodes (29): autoprefixer, cronstrue, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, graphology-layout-forceatlas2 (+21 more)

### Community 50 - "IdleTimeoutManager"
Cohesion: 0.07
Nodes (3): BrainLifecyclePort, BroadcastPort, IdleTimeoutManager

### Community 51 - "EventDrillDown.tsx"
Cohesion: 0.13
Nodes (23): three, getEventPulses(), BrainCore(), CortexDevPage(), devQueryClient, CortexLiveFeedProps, EventDrillDown(), EventDrillDownProps (+15 more)

### Community 52 - "useCortexData.ts"
Cohesion: 0.17
Nodes (26): getCognitiveGraph(), getCortexActivity(), getKGServiceDetail(), getKGServices(), getKGStats(), getKnowledgeById(), getMemory(), getRecentPulses() (+18 more)

### Community 53 - "server.js"
Cohesion: 0.08
Nodes (18): hasRegistryCredentials(), { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, fs, path, stageEventDocument(), fetchEventDocument(), fs, { handleRequest } (+10 more)

### Community 54 - "slack.py"
Cohesion: 0.10
Nodes (10): build_access_denied_home_view(), build_home_tab_view(), create_feedback_block(), format_plan_block(), _md_table_to_text(), _md_to_mrkdwn(), _parse_md_table(), resolve_source_emoji() (+2 more)

### Community 55 - "._build_system_prompt"
Cohesion: 0.07
Nodes (3): _init_tool_names(), _strip_tool_names(), _wrap_section()

### Community 56 - "dependencies.py"
Cohesion: 0.09
Nodes (13): get_aligner(), get_architect(), get_argocd_observer(), get_developer(), get_kargo_observer(), get_kg_store(), get_report_client(), get_sysadmin() (+5 more)

### Community 57 - "cognitive_graph.py"
Cohesion: 0.10
Nodes (12): get_brain(), get_pulse_tracker(), dismiss_proposals(), DismissRequest, get_all_shadow_interventions(), get_cognitive_graph(), get_cortex_activity(), get_cortex_status() (+4 more)

### Community 58 - "KnowledgeGraphStore"
Cohesion: 0.15
Nodes (4): _acquire(), KnowledgeGraphStore, _sanitize(), _with_timeout()

### Community 59 - "queue.py"
Cohesion: 0.12
Nodes (15): apply_lessons(), correct_memory(), CorrectMemoryRequest, create_knowledge(), create_lesson(), enforce_casual_domain(), EnforceCasualRequest, extract_lessons() (+7 more)

### Community 60 - "get_archivist"
Cohesion: 0.10
Nodes (12): get_archivist(), aligner_pending_items(), delete_knowledge(), delete_lesson(), get_event_report(), get_knowledge(), get_lesson(), get_memory() (+4 more)

### Community 61 - "NodeInspector.tsx"
Cohesion: 0.13
Nodes (23): getClosedEvents(), ArchitectureEvent, ArgoCDOperation, EVENT_LABELS, EventItem(), EventItemProps, healthTone(), lastOperationSummary() (+15 more)

### Community 63 - "reconcile.py"
Cohesion: 0.15
Nodes (10): sanitize_redis_port(), _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers(), main() (+2 more)

### Community 64 - "gemini_client.py"
Cohesion: 0.16
Nodes (5): FunctionCall, LLMChunk, LLMPort, LLMResponse, TokenUsage

### Community 69 - "dependencies"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 70 - "StateWatcher"
Cohesion: 0.11
Nodes (3): _QueueEntry, StateWatcher, _Subscription

### Community 71 - "adf_to_markdown"
Cohesion: 0.13
Nodes (9): _adf_to_text(), _escape_jql_string(), adf_to_markdown(), _apply_marks(), _children(), _render(), _render_list(), _render_list_item() (+1 more)

### Community 73 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 74 - "claude-guard.js"
Cohesion: 0.14
Nodes (18): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+10 more)

### Community 75 - "TokenUtilizationPage.tsx"
Cohesion: 0.16
Nodes (17): recharts, getFlowHistory(), FlowSnapshot, ObservationSeries, FlowHistoryPage(), formatTime(), RANGES, SparkCard() (+9 more)

### Community 77 - "context_parts.py"
Cohesion: 0.11
Nodes (9): _apply_sibling_signature(), build_function_response(), build_single_function_response(), compress_contents(), estimate_msg_tokens(), estimate_tokens(), extract_model_parts(), normalize_response_parts() (+1 more)

### Community 78 - ".get_event"
Cohesion: 0.09
Nodes (7): report_tampering(), FeedbackRequest, submit_feedback(), get_event_approval(), get_event_document(), get_event_turns(), rebuild_deep_memory()

### Community 80 - "cli-setup.js"
Cohesion: 0.13
Nodes (19): { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync }, filterSkillsByMode() (+11 more)

### Community 84 - "devDependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 85 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 86 - "ServiceNode.tsx"
Cohesion: 0.15
Nodes (13): @xyflow/react, HealthStatus, NodeType, AppNodeData, ARGOCD_HEALTH_COLORS, SYNC_ICONS, NamespaceGroupNodeData, GENERIC_TAGS (+5 more)

### Community 88 - "update_event_title"
Cohesion: 0.11
Nodes (9): can_override_domain(), can_rename_event(), _normalize_email(), demote_lesson(), KnowledgeUpdateRequest, TitleUpdateRequest, update_event_title(), update_knowledge() (+1 more)

### Community 89 - "gemini-sidecar/package.json"
Cohesion: 0.11
Nodes (17): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+9 more)

### Community 90 - "ArchitectureGraph.tsx"
Cohesion: 0.17
Nodes (16): @dagrejs/dagre, applyDagreLayout(), applyGridLayout(), applyLayout(), ArchitectureGraph(), ArchitectureGraphInner(), buildGraph(), computeIdHash() (+8 more)

### Community 92 - "ShiftsPage.tsx"
Cohesion: 0.23
Nodes (16): getCurrentShift(), getShiftDetail(), getShiftsList(), ShiftReportFull, ShiftReportSummary, FailedClusterBadge(), getISOWeek(), getWeekDates() (+8 more)

### Community 93 - "catalog-skills.js"
Cohesion: 0.16
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 94 - "handle_notify_user_slack"
Cohesion: 0.12
Nodes (7): _alert_wrapper_retrigger(), handle_notify_user_slack(), _resolve_maintainer_enum(), _resolve_slack_user(), build_event_report_md(), maintainer_env_key(), resolve_maintainer_emails()

### Community 96 - "RedisClient"
Cohesion: 0.15
Nodes (3): skills_version(), get_redis(), RedisClient

### Community 98 - "IncidentAdapterPort"
Cohesion: 0.12
Nodes (4): handle_search_open_incidents(), IdleTimeoutPort, IncidentAdapterPort, StateWatcherPort

### Community 99 - "list_active_events"
Cohesion: 0.12
Nodes (6): _defer_timeline_fields(), _has_active_subscription(), list_active_events(), list_closed_events(), list_waiting_approval_events(), _serialize_evidence()

### Community 100 - "generate_map.py"
Cohesion: 0.19
Nodes (6): _enumerate_gates(), _GateInfo, generate_phase_tool_map(), _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 106 - "cortex/types.ts"
Cohesion: 0.19
Nodes (13): EventSource, KGServiceEntity, CortexGraphProps, GraphLoaderProps, PulseTimelineProps, CognitiveGraphResponse, CortexHeartbeatMessage, FrictionIndicator (+5 more)

### Community 108 - "_append_user_turn"
Cohesion: 0.14
Nodes (5): _append_user_turn(), _coerce_part(), _is_function_response_part(), _strip_user_thought_signature(), _validated_parts()

### Community 112 - "._extract_context_flags"
Cohesion: 0.15
Nodes (3): compute_dispatch_backpressure(), ContextFlags, _safe_int_env()

### Community 113 - "get_graph_context"
Cohesion: 0.18
Nodes (5): _format_graph_context(), get_graph_context(), _parse_props(), _sanitize(), translate_to_lookups()

### Community 117 - "NeuronInfoPanel.tsx"
Cohesion: 0.24
Nodes (12): KGServiceDetail, asNumber(), asString(), asStringArray(), Badge(), describeNeuron(), Hdr(), NeuronInfoPanel() (+4 more)

### Community 122 - "CortexLiveFeed.tsx"
Cohesion: 0.24
Nodes (10): CortexHeartbeat(), CortexHeartbeatProps, ensureKeyframes(), CortexLiveFeed(), FILTER_PILLS, FilterKey, getStoredFilter(), MESSAGE_STYLES (+2 more)

### Community 123 - "testSetup.ts"
Cohesion: 0.18
Nodes (5): @tailwindcss/vite, @testing-library/react, vite, @vitejs/plugin-react, vitest

### Community 124 - "is_defer_event_available"
Cohesion: 0.18
Nodes (6): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 125 - "create_chat_event"
Cohesion: 0.20
Nodes (3): ChatEventRequest, ChatEventResponse, create_chat_event()

### Community 126 - "CiContextCard.tsx"
Cohesion: 0.31
Nodes (9): CiContext, CiContextCardProps, ConsoleTailBlock(), FailedJobRow(), annotationReplacer(), PIPELINE_ANNOTATION_RE, REDACTION_TRIGGER_KEYWORDS, stripAnsi() (+1 more)

### Community 129 - "generate_event_title"
Cohesion: 0.22
Nodes (3): generate_event_title(), get_adapter(), _get_semaphore()

### Community 131 - "entity_extractor.py"
Cohesion: 0.33
Nodes (5): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship

### Community 133 - "sanitize_call_syntax"
Cohesion: 0.20
Nodes (5): _extract_call_syntax(), process_stream_call_syntax_buffer(), sanitize_call_syntax(), scan_call_syntax(), split_stream_call_syntax()

### Community 134 - "get_quota_tracker"
Cohesion: 0.22
Nodes (3): get_quota_tracker(), llm_stats(), receive_telemetry()

### Community 138 - "format_turn"
Cohesion: 0.25
Nodes (4): _context_line(), format_task_card(), format_turn(), _truncate()

### Community 141 - "useDeferCountdown.ts"
Cohesion: 0.47
Nodes (7): DeferCountdownState, useDeferCountdown(), computeDeferProgress(), DeferTimeline, formatDeferRemaining(), inferDeferFromConversation(), resolveDeferTimeline()

### Community 148 - "has_unevaluated_close_blocker"
Cohesion: 0.25
Nodes (4): has_unevaluated_close_blocker(), _pred_jarvis_response(), _pred_unevaluated_close(), is_jarvis_acknowledgment()

### Community 153 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 154 - "state.js"
Cohesion: 0.33
Nodes (4): { AGENT_ROLE }, _blackboardTurns, _inboundMessages, _teammateMessages

### Community 155 - "validate-mutations.sh"
Cohesion: 0.73
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

### Community 165 - "extract_tables"
Cohesion: 0.40
Nodes (3): extract_tables(), _replace(), _md_table_to_block_kit()

### Community 166 - "TicketNode.tsx"
Cohesion: 0.40
Nodes (4): STATUS_COLORS, TICKET_COLORS, TicketNodeComponent(), TicketNodeData

### Community 173 - "overrides"
Cohesion: 0.67
Nodes (3): overrides, @typescript-eslint/typescript-estree, minimatch

## Knowledge Gaps
- **13 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+8 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2203 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **99 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `approve_event`, `logging`, `brain.py`, `auth.py`, `generate_event_title`, `jenkins_observer.py`, `Brain`, `EventDocument`, `os`, `AgentRegistry`, `_is_event_closed_or_missing`, `main.py`, `HeadhunterJira`, `state/__init__.py`, `observations_mgmt.py`, `ConversationTurn`, `record_token_usage`, `.start_event_loop`, `IdleTimeoutManager`, `slack.py`, `dependencies.py`, `queue.py`, `get_archivist`, `.update_event_phase`, `LiveAPIAdapter`, `DashboardWSAdapter`, `.get_event`, `update_event_title`, `list_active_events`, `ScheduleRepository`, `close_event_by_user`, `.list_observations`, `create_chat_event`?**
  _High betweenness centrality (0.109) - this node is a cross-community bridge._
- **Are the 80 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 80 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.011949470809149881 - nodes in this community are weakly interconnected._
- **Why does `EventEvidence` connect `brain.py` to `BlackboardState`, `logging`, `auth.py`, `Archivist`, `jenkins_observer.py`, `Brain`, `EventDocument`, `os`, `_is_event_closed_or_missing`, `HeadhunterJira`, `TimeKeeperObserver`, `Aligner`, `EventRepository`, `spawn_event_namer_task`, `GitHubPlatform`, `SlackChannel`, `GitLabPlatform`, `slack.py`, `queue.py`, `LiveAPIAdapter`, `DashboardWSAdapter`, `list_active_events`, `.create_platform_event`, `.poll_and_process`, `ScheduleCreateRequest`, `create_chat_event`?**
  _High betweenness centrality (0.052) - this node is a cross-community bridge._
- **Are the 21 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 21 INFERRED edges - model-reasoned connections that need verification._
- **Should `logging` be split into smaller, more focused modules?**
  _Cohesion score 0.026257861635220127 - nodes in this community are weakly interconnected._