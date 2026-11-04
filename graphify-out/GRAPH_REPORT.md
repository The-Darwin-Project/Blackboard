# Graph Report - Blackboard  (2026-11-04)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 5005 nodes · 11181 edges · 193 communities (91 shown, 102 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 938 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `aeafed38`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BlackboardState
- main.py
- queue.py
- client.ts
- react
- logging
- nightwatcher_tools.py
- models.py
- App.tsx
- lucide-react
- Brain
- tool_gates.py
- brain.py
- EventSidebar.tsx
- auth.py
- create_adapter
- merge-guard.js
- Archivist
- os
- ._run_agent_task
- http-handler.js
- jenkins-mcp.js
- LiveAPIAdapter
- Service
- EventDocument
- fetchApi
- Aligner
- slack.py
- BrainSkillLoader
- cognitive_graph.py
- _BrainToolContext
- EphemeralProvisioner
- JarvisMemoryPage.tsx
- cli-executor.js
- ui/package.json
- storage-recycler.js
- EventDrillDown.tsx
- JenkinsAdapter
- EventRepository
- ToolContext
- GitHubPlatform
- ._process_with_llm
- CortexGraph.tsx
- ArchitectureGraph.tsx
- GitLabPlatform
- ConversationTurn
- Headhunter
- TimeKeeperPage.tsx
- handlers_integration.py
- OpsStateContext.tsx
- ws-client.js
- KnowledgeGraphStore
- useCortexData.ts
- ._close_and_broadcast
- server.js
- useQueue.ts
- observations_mgmt.py
- GeminiAdapter
- NodeInspector.tsx
- PulseBatch
- KubernetesSpawnHealthAdapter
- VectorStore
- ArgoCDObserver
- SlackChannel
- ._build_contents
- ._get_manager
- KargoObserver
- TopologyRepository
- dependencies
- StateWatcher
- HeadhunterJira
- GitHubAppAuth
- compilerOptions
- claude-guard.js
- DashboardWSAdapter
- BrainIntrospectionPort
- reconcile.py
- cli-setup.js
- VcsPlatformPort
- ReflexSearcher
- .start_event_loop
- ArchitectureEvent
- FairQueue
- devDependencies
- compilerOptions
- AgentRegistry
- get_report
- gemini-sidecar/package.json
- JiraIncidentAdapter
- handle_classify_event
- _sanitize_analysis_text
- JenkinsObserver
- ._gate_check
- ObservationRepository
- ShiftsPage.tsx
- catalog-skills.js
- TokenUtilizationPage.tsx
- dispatch.py
- EscalationRepository
- generate_map.py
- OIDCKeyAdapter
- graph_recall.py
- get_token_meter
- .list_observations
- ReconcileScheduler
- SourceIcon.tsx
- observations_reporter.py
- ScheduleRepository
- TaskBridge
- spawn_event_namer_task
- ._extract_context_flags
- ScheduleCreateRequest
- get_current_shift
- IdleTimeoutManager
- MultiInstallationManager
- agent_websocket_handler
- format_jira_for_llm
- SlackAccessGate
- agents/__init__.py
- is_defer_event_available
- Any
- CortexDevPage.tsx
- NeuronInfoPanel.tsx
- telemetry.py
- ._post_agent_recall
- entity_extractor.py
- handle_report_incident
- ._github_poll_and_process
- ._process_candidates
- ._triage_and_build_evidence
- ._drain_once
- has_unevaluated_close_blocker
- knowledge_graph_api.py
- handle_notify_user_slack
- SmartsheetMaintainerCache
- ._register_handlers
- Trigger
- AsyncGitHubClient
- GitLabTokenAuth
- ConversationMessage
- TimeKeeperObserver
- CortexRepository
- adf_to_markdown
- get_all_journal
- scripts
- state.js
- validate-mutations.sh
- io
- list_failed_stages
- submit_feedback
- QueueTrigger
- list_incidents
- require-results.sh
- _walk_adf_mentions
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

## Communities (193 total, 102 thin omitted)

### Community 0 - "BlackboardState"
Cohesion: 0.01
Nodes (3): report_tampering(), get_notebook(), BlackboardState

### Community 1 - "main.py"
Cohesion: 0.02
Nodes (37): Architect, AgentClient, Developer, _patch_enum_fields(), set_incident_options(), SysAdmin, set_oidc_adapter(), get_aligner() (+29 more)

### Community 2 - "queue.py"
Cohesion: 0.03
Nodes (49): can_rename_event(), resolve_approval_identity(), get_archivist(), aligner_pending_items(), apply_lessons(), approve_event(), close_event_by_user(), CloseRequest (+41 more)

### Community 3 - "client.ts"
Cohesion: 0.03
Nodes (94): @tanstack/react-query, ApiError, bulkDeleteObservations(), deleteNote(), deleteObservation(), exportObservations(), ExtractedCorrection, ExtractedLesson (+86 more)

### Community 4 - "react"
Cohesion: 0.05
Nodes (83): react, @uiw/react-markdown-preview, approveEvent(), closeEvent(), enforceCasualDomain(), getEventReport(), getReport(), getReports() (+75 more)

### Community 5 - "logging"
Cohesion: 0.05
Nodes (7): _annotation_replace(), _strip_pipeline_annotations(), _heartbeat(), _sanitize_lesson_text(), _parse_job_metadata(), _load_name_mapping(), sanitize_title()

### Community 6 - "nightwatcher_tools.py"
Cohesion: 0.04
Nodes (33): record_token_usage(), PulseContext, ShiftIncident, ShiftInvestigation, ShiftReport, _env_float(), _env_int(), NightwatcherObserver (+25 more)

### Community 7 - "models.py"
Cohesion: 0.04
Nodes (30): _safe_int(), AppNode, ChatRequest, ChatResponse, EventInput, EventMetrics, EventStatus, EventType (+22 more)

### Community 8 - "App.tsx"
Cohesion: 0.05
Nodes (60): react-dom, react-router-dom, createChatEvent(), getConfig(), getEventDocument(), getEvents(), getWSAuthFailureCallback(), setOnUnauthorized() (+52 more)

### Community 9 - "lucide-react"
Cohesion: 0.06
Nodes (65): lucide-react, updateEventTitle(), CiContext, ConversationTurn, TokenUsageDict, CiContextCard(), CiContextCardProps, ConsoleTailBlock() (+57 more)

### Community 11 - "tool_gates.py"
Cohesion: 0.05
Nodes (78): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+70 more)

### Community 12 - "brain.py"
Cohesion: 0.04
Nodes (30): _apply_sibling_signature(), build_function_response(), build_single_function_response(), compress_contents(), estimate_msg_tokens(), estimate_tokens(), extract_model_parts(), normalize_response_parts() (+22 more)

### Community 13 - "EventSidebar.tsx"
Cohesion: 0.06
Nodes (66): getJiraMissions(), HeadhunterTodo, postJiraAction(), AgentRegistryEntry, ChatInput(), ChatInputProps, Draft, LastSubmission (+58 more)

### Community 14 - "auth.py"
Cohesion: 0.04
Nodes (20): can_approve_event(), can_override_domain(), _claims_to_user(), get_user_from_request(), get_user_from_websocket(), _normalize_email(), require_auth(), require_obs_admin() (+12 more)

### Community 15 - "create_adapter"
Cohesion: 0.05
Nodes (14): ClaudeAdapter, _parse_drain_timeout(), create_adapter(), get_quota_tracker(), QuotaExhaustedError, QuotaTracker, RequestExceedsBurstError, Reservation (+6 more)

### Community 16 - "merge-guard.js"
Cohesion: 0.05
Nodes (69): analyzeString(), analyzeTokens(), API_VALUED, apiTokens(), apiWriteNeedsGuard(), assignName(), bareBranchProtected(), base() (+61 more)

### Community 18 - "os"
Cohesion: 0.06
Nodes (17): _get_static_maintainer_emails(), _get_allowed_mention_authors(), _get_static_maintainer_emails(), _safe_int(), dex_proxy(), approve_mission(), dismiss_mission(), _infer_phase() (+9 more)

### Community 19 - "._run_agent_task"
Cohesion: 0.06
Nodes (10): on_huddle(), on_progress(), on_huddle(), on_progress(), _compute_processed_up_to(), _is_automated_nudge(), _sanitize_error_text(), _sanitize_override_reason() (+2 more)

### Community 20 - "http-handler.js"
Cohesion: 0.09
Nodes (58): resolveCommand(), writeAgyMcpServer(), writeClaudeMcpServer(), buildArgoCDMcpConfig(), createAppJWT(), discoverAndGenerateTokens(), _discoverAndGenerateTokensInner(), discoverInstallations() (+50 more)

### Community 21 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 22 - "LiveAPIAdapter"
Cohesion: 0.05
Nodes (3): _build_skill_refs(), _is_event_closed_or_missing(), LiveAPIAdapter

### Community 23 - "Service"
Cohesion: 0.05
Nodes (9): GraphResponse, Service, get_event_document(), get_graph_data(), get_mermaid_diagram(), get_service_details(), get_topology(), list_services() (+1 more)

### Community 25 - "fetchApi"
Cohesion: 0.08
Nodes (49): applyLessons(), correctMemory(), createKnowledge(), createLesson(), deleteKnowledge(), deleteLesson(), extractLessons(), fetchApi() (+41 more)

### Community 27 - "slack.py"
Cohesion: 0.06
Nodes (19): build_access_denied_home_view(), build_home_tab_view(), _context_line(), create_feedback_block(), extract_tables(), _replace(), format_plan_block(), format_task_card() (+11 more)

### Community 28 - "BrainSkillLoader"
Cohesion: 0.05
Nodes (3): BrainSkillLoader, _SkillCorpus, _wrap_section()

### Community 29 - "cognitive_graph.py"
Cohesion: 0.06
Nodes (19): can_append_message(), get_blackboard(), get_brain(), get_pulse_tracker(), ChatEventRequest, ChatEventResponse, create_chat_event(), dismiss_proposals() (+11 more)

### Community 31 - "EphemeralProvisioner"
Cohesion: 0.05
Nodes (6): DispatchMetrics, EphemeralProvisioner, SpawnFailed, SpawnHealthPort, SpawnPollResult, SpawnStatus

### Community 32 - "JarvisMemoryPage.tsx"
Cohesion: 0.09
Nodes (37): dismissProposals(), EnhancementProposal, getFlowMetrics(), getHandoffReports(), getProposals(), HandoffReport, FlowMetrics, Dashboard() (+29 more)

### Community 33 - "cli-executor.js"
Cohesion: 0.09
Nodes (36): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS, STORAGE_PRETASK_TIMEOUT_MS, resolveStorageRoot }, buildCLICommand(), { checkAndRecycleStorage, pinTaskCwd, unpinTaskCwd }, CLAUDE_JSON_PATH, cp, executeCLI(), executeCLIStreaming(), FALLBACK_MODEL (+28 more)

### Community 34 - "ui/package.json"
Cohesion: 0.06
Nodes (35): autoprefixer, cronstrue, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, graphology-layout-forceatlas2 (+27 more)

### Community 35 - "storage-recycler.js"
Cohesion: 0.08
Nodes (34): withTaskStorage(), resolveStorageRoot(), ROLE_TIMEOUTS, STORAGE_ACTIVITY_HEARTBEAT_MS, STORAGE_MAX_TIER3_DELETIONS, STORAGE_PRETASK_TIMEOUT_MS, STORAGE_RESULTS_TTL_MS, STORAGE_STALE_MS (+26 more)

### Community 36 - "EventDrillDown.tsx"
Cohesion: 0.09
Nodes (34): three, getEventPulses(), EventSource, BrainCore(), CortexHeartbeat(), CortexHeartbeatProps, ensureKeyframes(), CortexLiveFeed() (+26 more)

### Community 37 - "JenkinsAdapter"
Cohesion: 0.06
Nodes (6): BuildDetails, JenkinsAdapter, JenkinsPlatformPort, JobResult, JobRunState, ViewScanResult

### Community 39 - "ToolContext"
Cohesion: 0.09
Nodes (9): handle_message_agent(), handle_reply_to_agent(), handle_select_agent(), _sticky_work_style(), handle_defer_event(), handle_hold_watch(), handle_wait_for_agent(), handle_wait_for_jarvis() (+1 more)

### Community 42 - "CortexGraph.tsx"
Cohesion: 0.09
Nodes (34): graphology, AGENTS, DOMAINS, eventColor(), getExecutiveNeurons(), getStructuralEdges(), HEMISPHERE_X, NEURON_DESCRIPTIONS (+26 more)

### Community 43 - "ArchitectureGraph.tsx"
Cohesion: 0.09
Nodes (28): @dagrejs/dagre, @xyflow/react, HealthStatus, NodeType, AppNodeData, applyDagreLayout(), applyGridLayout(), applyLayout() (+20 more)

### Community 45 - "ConversationTurn"
Cohesion: 0.17
Nodes (26): emit_tool_result(), handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_recall_pruned_turns(), handle_ask_release_ai(), handle_fetch_jira_issue(), handle_greenwave() (+18 more)

### Community 47 - "TimeKeeperPage.tsx"
Cohesion: 0.12
Nodes (24): createSchedule(), deleteSchedule(), getSchedules(), refineInstructions(), ScheduleCreatePayload, ScheduleItem, toggleSchedule(), updateSchedule() (+16 more)

### Community 48 - "handlers_integration.py"
Cohesion: 0.11
Nodes (15): _do_retrigger(), _get_jira_reporter(), handle_comment_jira_issue(), handle_refresh_github_context(), handle_refresh_gitlab_context(), handle_refresh_kargo_context(), handle_retrigger_jenkins_build(), _is_darwin_reentrant_caller() (+7 more)

### Community 49 - "OpsStateContext.tsx"
Cohesion: 0.11
Nodes (25): getKargoStages(), EventEvidence, KargoStageStatus, STARTER_CHIPS, StarterChip, useSafeNavigate(), WorkspaceCenterStage(), WorkspaceCenterStageProps (+17 more)

### Community 50 - "ws-client.js"
Cohesion: 0.09
Nodes (26): is429Error(), {
  DEFAULT_WORK_DIR, AGENT_CLI, AGENT_MODEL, AGENT_ROLE,
  EVENT_ID, EPHEMERAL, IDLE_TIMEOUT_MS,
  CLI_429_MAX_RETRIES, CLI_429_INITIAL_DELAY_MS, CLI_429_BACKOFF_MULTIPLIER,
}, { ensureEventDocument }, { executeCLIStreaming, prepareResultsDir, is429Error }, { filterSkillsByRole, filterSkillsByMode, swapActiveRules, restoreAllSkills }, fs, handleCancel(), resetTimer() (+18 more)

### Community 51 - "KnowledgeGraphStore"
Cohesion: 0.14
Nodes (4): _acquire(), KnowledgeGraphStore, _sanitize(), _with_timeout()

### Community 52 - "useCortexData.ts"
Cohesion: 0.16
Nodes (28): getCognitiveGraph(), getCortexActivity(), getKGServiceDetail(), getKGServices(), getKGStats(), getKnowledgeById(), getMemory(), getRecentPulses() (+20 more)

### Community 54 - "server.js"
Cohesion: 0.08
Nodes (18): hasRegistryCredentials(), { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, fs, path, stageEventDocument(), fetchEventDocument(), fs, { handleRequest } (+10 more)

### Community 55 - "useQueue.ts"
Cohesion: 0.12
Nodes (25): getActiveEvents(), getAlignerPending(), getHeadhunterPending(), getJenkinsPending(), getWaitingApprovalEvents(), ActiveEvent, EventDocument, KGServiceEntity (+17 more)

### Community 56 - "observations_mgmt.py"
Cohesion: 0.10
Nodes (10): get_report_client(), render_pdf(), bulk_delete_observations(), BulkDeleteRequest, delete_observation(), export_observations(), generate_observations_report(), rename_observation() (+2 more)

### Community 58 - "NodeInspector.tsx"
Cohesion: 0.13
Nodes (23): getClosedEvents(), ArchitectureEvent, ArgoCDOperation, ArchitectureGraph(), EVENT_LABELS, EventItem(), EventItemProps, healthTone() (+15 more)

### Community 59 - "PulseBatch"
Cohesion: 0.10
Nodes (4): PulseBatch, PulsePort, PulseObserver, PulseTracker

### Community 61 - "VectorStore"
Cohesion: 0.11
Nodes (3): _decode_cursor(), _encode_cursor(), VectorStore

### Community 68 - "dependencies"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 69 - "StateWatcher"
Cohesion: 0.11
Nodes (3): _QueueEntry, StateWatcher, _Subscription

### Community 72 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 73 - "claude-guard.js"
Cohesion: 0.14
Nodes (18): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+10 more)

### Community 75 - "BrainIntrospectionPort"
Cohesion: 0.10
Nodes (3): BrainIntrospectionPort, BrainLifecyclePort, BroadcastPort

### Community 76 - "reconcile.py"
Cohesion: 0.18
Nodes (9): _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers(), main(), _parse_frontmatter() (+1 more)

### Community 77 - "cli-setup.js"
Cohesion: 0.13
Nodes (19): { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync }, filterSkillsByMode() (+11 more)

### Community 82 - "ArchitectureEvent"
Cohesion: 0.13
Nodes (3): ArchitectureEvent, list_events(), MetricsRepository

### Community 84 - "devDependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 85 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 87 - "get_report"
Cohesion: 0.11
Nodes (6): get_report(), list_reports(), reports_spa_no_slash(), reports_spa_with_slash(), search_reports(), _serve_spa()

### Community 88 - "gemini-sidecar/package.json"
Cohesion: 0.11
Nodes (17): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+9 more)

### Community 89 - "JiraIncidentAdapter"
Cohesion: 0.15
Nodes (3): _adf_to_text(), _escape_jql_string(), JiraIncidentAdapter

### Community 91 - "handle_classify_event"
Cohesion: 0.12
Nodes (5): handle_classify_event(), handle_request_user_approval(), IdleTimeoutPort, IncidentAdapterPort, StateWatcherPort

### Community 92 - "_sanitize_analysis_text"
Cohesion: 0.12
Nodes (9): _clamp_confidence(), _prepare_console_tail(), _redact_match(), _redact_secrets_in_text(), _sanitize_analysis_text(), _sanitize_console_tail(), _strip_newlines(), _validate_analysis() (+1 more)

### Community 94 - "._gate_check"
Cohesion: 0.22
Nodes (8): get_user_from_slack(), handle_app_mention(), handle_approve(), handle_create_event_modal(), handle_darwin_command(), handle_reject(), on_dm_message(), fallback_title()

### Community 96 - "ShiftsPage.tsx"
Cohesion: 0.23
Nodes (16): getCurrentShift(), getShiftDetail(), getShiftsList(), ShiftReportFull, ShiftReportSummary, FailedClusterBadge(), getISOWeek(), getWeekDates() (+8 more)

### Community 97 - "catalog-skills.js"
Cohesion: 0.16
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 98 - "TokenUtilizationPage.tsx"
Cohesion: 0.22
Nodes (13): recharts, getFlowHistory(), FlowSnapshot, formatTime(), RANGES, SparkCard(), SparkCardProps, formatTime() (+5 more)

### Community 99 - "dispatch.py"
Cohesion: 0.18
Nodes (8): _build_prompt(), _check_security(), consume_wake_task(), _consume(), _dispatch_timeout_s(), dispatch_to_agent(), _consume_queue(), _sanitize_stdout()

### Community 103 - "generate_map.py"
Cohesion: 0.19
Nodes (6): _enumerate_gates(), _GateInfo, generate_phase_tool_map(), _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 105 - "graph_recall.py"
Cohesion: 0.19
Nodes (5): _format_graph_context(), get_graph_context(), _parse_props(), _sanitize(), translate_to_lookups()

### Community 109 - "ReconcileScheduler"
Cohesion: 0.16
Nodes (3): ReconcileScheduler, ResyncTrigger, StalenessGuard

### Community 110 - "SourceIcon.tsx"
Cohesion: 0.13
Nodes (3): ICON_MAP, SourceIconProps, SUBJECT_ICON_MAP

### Community 111 - "observations_reporter.py"
Cohesion: 0.21
Nodes (7): _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), _sample_points(), _summarize()

### Community 114 - "spawn_event_namer_task"
Cohesion: 0.18
Nodes (4): generate_event_title(), get_adapter(), _get_semaphore(), spawn_event_namer_task()

### Community 115 - "._extract_context_flags"
Cohesion: 0.15
Nodes (3): compute_dispatch_backpressure(), ContextFlags, _safe_int_env()

### Community 117 - "get_current_shift"
Cohesion: 0.15
Nodes (3): get_current_shift(), get_shift_detail(), list_shifts()

### Community 121 - "agent_websocket_handler"
Cohesion: 0.17
Nodes (3): agent_websocket_handler(), agent_ws_endpoint(), websocket_endpoint()

### Community 125 - "agents/__init__.py"
Cohesion: 0.24
Nodes (3): safe_execution(), wrapper(), SecurityError

### Community 126 - "is_defer_event_available"
Cohesion: 0.18
Nodes (6): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 128 - "CortexDevPage.tsx"
Cohesion: 0.31
Nodes (9): CortexDevPage(), devQueryClient, MOCK_CORTEX_STATUS, MOCK_EVENT_ID, MOCK_NEURONS, MOCK_PULSE_BATCHES, MOCK_SHADOW, MOCK_THINKING (+1 more)

### Community 129 - "NeuronInfoPanel.tsx"
Cohesion: 0.29
Nodes (10): asNumber(), asString(), asStringArray(), Badge(), describeNeuron(), Hdr(), NeuronInfoPanel(), AGENT_NEURON_COLORS (+2 more)

### Community 132 - "entity_extractor.py"
Cohesion: 0.33
Nodes (5): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship

### Community 133 - "handle_report_incident"
Cohesion: 0.22
Nodes (4): handle_report_incident(), _resolve_escalation_scope(), handle_search_open_incidents(), handle_respond_to_jarvis()

### Community 139 - "has_unevaluated_close_blocker"
Cohesion: 0.20
Nodes (4): has_unevaluated_close_blocker(), _pred_jarvis_response(), _pred_unevaluated_close(), is_jarvis_acknowledgment()

### Community 140 - "knowledge_graph_api.py"
Cohesion: 0.31
Nodes (4): get_kg_store(), get_service_detail(), get_stats(), list_services()

### Community 141 - "handle_notify_user_slack"
Cohesion: 0.22
Nodes (4): _alert_wrapper_retrigger(), handle_notify_user_slack(), _resolve_slack_user(), build_event_report_md()

### Community 151 - "adf_to_markdown"
Cohesion: 0.57
Nodes (7): adf_to_markdown(), _apply_marks(), _children(), _render(), _render_list(), _render_list_item(), _render_table_like()

### Community 153 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 154 - "state.js"
Cohesion: 0.33
Nodes (4): { AGENT_ROLE }, _blackboardTurns, _inboundMessages, _teammateMessages

### Community 155 - "validate-mutations.sh"
Cohesion: 0.73
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

## Knowledge Gaps
- **13 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+8 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2191 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **102 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `main.py`, `queue.py`, `logging`, `nightwatcher_tools.py`, `models.py`, `Brain`, `brain.py`, `auth.py`, `os`, `ConversationMessage`, `LiveAPIAdapter`, `Service`, `get_all_journal`, `EventDocument`, `slack.py`, `BrainSkillLoader`, `cognitive_graph.py`, `submit_feedback`, `ConversationTurn`, `observations_mgmt.py`, `HeadhunterJira`, `DashboardWSAdapter`, `.start_event_loop`, `ArchitectureEvent`, `get_report`, `.list_observations`, `observations_reporter.py`, `ScheduleRepository`, `spawn_event_namer_task`, `get_current_shift`?**
  _High betweenness centrality (0.140) - this node is a cross-community bridge._
- **Are the 80 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 80 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.01429038053241875 - nodes in this community are weakly interconnected._
- **Why does `Brain` connect `Brain` to `BlackboardState`, `main.py`, `._post_agent_recall`, `logging`, `models.py`, `brain.py`, `create_adapter`, `._run_agent_task`, `EventDocument`, `slack.py`, `BrainSkillLoader`, `.stop_event_loop`, `QueueTrigger`, `._process_with_llm`, `ConversationTurn`, `._close_and_broadcast`, `PulseBatch`, `._build_contents`, `StateWatcher`, `DashboardWSAdapter`, `BrainIntrospectionPort`, `ReflexSearcher`, `.start_event_loop`, `ReconcileScheduler`, `._extract_context_flags`, `IdleTimeoutManager`, `agents/__init__.py`?**
  _High betweenness centrality (0.069) - this node is a cross-community bridge._
- **Are the 21 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 21 INFERRED edges - model-reasoned connections that need verification._
- **Should `main.py` be split into smaller, more focused modules?**
  _Cohesion score 0.023400601116358954 - nodes in this community are weakly interconnected._