# Graph Report - Blackboard  (2026-11-04)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 5004 nodes · 11180 edges · 193 communities (95 shown, 98 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 938 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `8774ecc0`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BlackboardState
- main.py
- brain.py
- client.ts
- queue.py
- EventChatPanel.tsx
- nightwatcher_tools.py
- auth.py
- tool_gates.py
- logging
- Brain
- merge-guard.js
- llm/__init__.py
- EventSidebar.tsx
- Archivist
- SlackChannel
- ._run_agent_task
- http-handler.js
- App.tsx
- colors.ts
- jenkins-mcp.js
- react
- HeadhunterJira
- LiveAPIAdapter
- Service
- GitLabPlatform
- httpx
- EventDocument
- slack.py
- TurnBubble.tsx
- Aligner
- _BrainToolContext
- EphemeralProvisioner
- GitHubPlatform
- cli-executor.js
- re
- storage-recycler.js
- JenkinsAdapter
- EventRepository
- ToolContext
- Headhunter
- ._process_with_llm
- CortexGraph.tsx
- prompt.py
- lucide-react
- ConversationTurn
- TimeKeeperPage.tsx
- handlers_integration.py
- DashboardWSAdapter
- WorkspaceTaskItem.tsx
- ws-client.js
- jenkins_observer.py
- create_schedule
- ActiveStreamsContext.tsx
- KnowledgeGraphStore
- ui/package.json
- EventDrillDown.tsx
- ._close_and_broadcast
- server.js
- observations_mgmt.py
- GeminiAdapter
- cognitive_graph.py
- .list_observations
- NodeInspector.tsx
- useCortexData.ts
- PulseBatch
- KubernetesSpawnHealthAdapter
- VectorStore
- ArgoCDObserver
- ._build_contents
- BrainSkillLoader
- KargoObserver
- TopologyRepository
- dependencies
- StateWatcher
- compilerOptions
- claude-guard.js
- TokenUtilizationPage.tsx
- ._get_manager
- GitHubAppAuth
- reconcile.py
- cli-setup.js
- VcsPlatformPort
- ReflexSearcher
- .start_event_loop
- FairQueue
- devDependencies
- compilerOptions
- ServiceNode.tsx
- AgentRegistry
- get_report
- gemini-sidecar/package.json
- ArchitectureGraph.tsx
- ._build_system_prompt
- handle_classify_event
- JenkinsObserver
- ObservationRepository
- ShiftsPage.tsx
- catalog-skills.js
- dispatch.py
- EscalationRepository
- cortex/types.ts
- generate_map.py
- OIDCKeyAdapter
- src/ports.py
- ._discover
- graph_recall.py
- get_token_meter
- ReconcileScheduler
- observations_reporter.py
- ScheduleRepository
- MultiInstallationManager
- TaskBridge
- ._extract_context_flags
- ScheduleCreateRequest
- get_current_shift
- IdleTimeoutManager
- NeuronInfoPanel.tsx
- agent_websocket_handler
- SlackAccessGate
- agents/__init__.py
- testSetup.ts
- is_defer_event_available
- CiContextCard.tsx
- entity_extractor.py
- handle_report_incident
- ._process_candidates
- ._triage_and_build_evidence
- ._drain_once
- has_unevaluated_close_blocker
- knowledge_graph_api.py
- vcs_approval.py
- CortexDevPage.tsx
- handle_notify_user_slack
- SmartsheetMaintainerCache
- Trigger
- AsyncGitHubClient
- GitLabTokenAuth
- ConversationMessage
- TimeKeeperObserver
- CortexRepository
- llm_stats
- BrainIntrospectionPort
- scripts
- state.js
- validate-mutations.sh
- io
- list_failed_stages
- dex_proxy
- get_notebook
- QueueTrigger
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

## Communities (193 total, 98 thin omitted)

### Community 1 - "main.py"
Cohesion: 0.02
Nodes (37): Architect, AgentClient, Developer, _patch_enum_fields(), set_incident_options(), SysAdmin, set_oidc_adapter(), get_aligner() (+29 more)

### Community 2 - "brain.py"
Cohesion: 0.03
Nodes (34): _safe_int(), AppNode, ArchitectureEvent, ChatRequest, ChatResponse, EventEvidence, EventInput, EventMetrics (+26 more)

### Community 3 - "client.ts"
Cohesion: 0.03
Nodes (96): @tanstack/react-query, ApiError, bulkDeleteObservations(), deleteNote(), deleteObservation(), exportObservations(), ExtractedCorrection, ExtractedLesson (+88 more)

### Community 4 - "queue.py"
Cohesion: 0.03
Nodes (51): resolve_approval_identity(), get_archivist(), get_brain(), aligner_pending_items(), apply_lessons(), approve_event(), close_event_by_user(), CloseRequest (+43 more)

### Community 5 - "EventChatPanel.tsx"
Cohesion: 0.05
Nodes (79): react-router-dom, getActiveEvents(), getAlignerPending(), getEventDocument(), getEvents(), getJenkinsPending(), getKargoStages(), getWaitingApprovalEvents() (+71 more)

### Community 6 - "nightwatcher_tools.py"
Cohesion: 0.04
Nodes (33): record_token_usage(), PulseContext, ShiftIncident, ShiftInvestigation, ShiftReport, _env_float(), _env_int(), NightwatcherObserver (+25 more)

### Community 7 - "auth.py"
Cohesion: 0.04
Nodes (21): can_append_message(), can_approve_event(), can_override_domain(), can_rename_event(), _claims_to_user(), get_user_from_request(), get_user_from_websocket(), _normalize_email() (+13 more)

### Community 8 - "tool_gates.py"
Cohesion: 0.05
Nodes (78): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+70 more)

### Community 9 - "logging"
Cohesion: 0.06
Nodes (6): _heartbeat(), _get_static_maintainer_emails(), _get_allowed_mention_authors(), _get_static_maintainer_emails(), _safe_int(), _load_name_mapping()

### Community 11 - "merge-guard.js"
Cohesion: 0.05
Nodes (69): analyzeString(), analyzeTokens(), API_VALUED, apiTokens(), apiWriteNeedsGuard(), assignName(), bareBranchProtected(), base() (+61 more)

### Community 12 - "llm/__init__.py"
Cohesion: 0.05
Nodes (12): ClaudeAdapter, get_quota_tracker(), QuotaExhaustedError, QuotaTracker, RequestExceedsBurstError, Reservation, TokenUsageDict, FunctionCall (+4 more)

### Community 13 - "EventSidebar.tsx"
Cohesion: 0.08
Nodes (59): getHeadhunterPending(), getJiraMissions(), HeadhunterTodo, postJiraAction(), AgentRegistryEntry, ACTION_BADGE, formatAge(), HeadhunterQueuePanel() (+51 more)

### Community 15 - "SlackChannel"
Cohesion: 0.06
Nodes (13): spawn_event_namer_task(), get_user_from_slack(), format_event_summary(), SlackChannel, handle_app_home_opened(), handle_app_mention(), handle_approve(), handle_create_event_modal() (+5 more)

### Community 16 - "._run_agent_task"
Cohesion: 0.06
Nodes (10): on_huddle(), on_progress(), on_huddle(), on_progress(), _compute_processed_up_to(), _is_automated_nudge(), _sanitize_error_text(), _sanitize_override_reason() (+2 more)

### Community 17 - "http-handler.js"
Cohesion: 0.09
Nodes (58): resolveCommand(), writeAgyMcpServer(), writeClaudeMcpServer(), buildArgoCDMcpConfig(), createAppJWT(), discoverAndGenerateTokens(), _discoverAndGenerateTokensInner(), discoverInstallations() (+50 more)

### Community 18 - "App.tsx"
Cohesion: 0.06
Nodes (50): oidc-client-ts, react-dom, dismissProposals(), EnhancementProposal, getConfig(), getHandoffReports(), getProposals(), getWSAuthFailureCallback() (+42 more)

### Community 19 - "colors.ts"
Cohesion: 0.07
Nodes (38): getReport(), getReports(), ReportFull, ReportMeta, CompactCardStrip(), EventHistory(), TimeRange, ViewMode (+30 more)

### Community 20 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 21 - "react"
Cohesion: 0.08
Nodes (53): react, applyLessons(), correctMemory(), createKnowledge(), createLesson(), deleteKnowledge(), deleteLesson(), extractLessons() (+45 more)

### Community 23 - "LiveAPIAdapter"
Cohesion: 0.05
Nodes (3): _build_skill_refs(), _is_event_closed_or_missing(), LiveAPIAdapter

### Community 24 - "Service"
Cohesion: 0.05
Nodes (9): GraphResponse, Service, get_event_document(), get_graph_data(), get_mermaid_diagram(), get_service_details(), get_topology(), list_services() (+1 more)

### Community 26 - "httpx"
Cohesion: 0.06
Nodes (17): _adf_to_text(), _escape_jql_string(), JiraIncidentAdapter, approve_mission(), dismiss_mission(), _infer_phase(), _jira_config(), list_missions() (+9 more)

### Community 28 - "slack.py"
Cohesion: 0.06
Nodes (19): build_access_denied_home_view(), build_home_tab_view(), _context_line(), create_feedback_block(), extract_tables(), _replace(), format_plan_block(), format_task_card() (+11 more)

### Community 29 - "TurnBubble.tsx"
Cohesion: 0.08
Nodes (42): @uiw/react-markdown-preview, approveEvent(), closeEvent(), enforceCasualDomain(), getEventReport(), rejectEvent(), submitFeedback(), CollapsibleSection() (+34 more)

### Community 32 - "EphemeralProvisioner"
Cohesion: 0.05
Nodes (6): DispatchMetrics, EphemeralProvisioner, SpawnFailed, SpawnHealthPort, SpawnPollResult, SpawnStatus

### Community 34 - "cli-executor.js"
Cohesion: 0.09
Nodes (36): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS, STORAGE_PRETASK_TIMEOUT_MS, resolveStorageRoot }, buildCLICommand(), { checkAndRecycleStorage, pinTaskCwd, unpinTaskCwd }, CLAUDE_JSON_PATH, cp, executeCLI(), executeCLIStreaming(), FALLBACK_MODEL (+28 more)

### Community 35 - "re"
Cohesion: 0.07
Nodes (17): _sanitize_lesson_text(), _apply_sibling_signature(), build_function_response(), build_single_function_response(), compress_contents(), estimate_msg_tokens(), estimate_tokens(), extract_model_parts() (+9 more)

### Community 36 - "storage-recycler.js"
Cohesion: 0.08
Nodes (34): withTaskStorage(), resolveStorageRoot(), ROLE_TIMEOUTS, STORAGE_ACTIVITY_HEARTBEAT_MS, STORAGE_MAX_TIER3_DELETIONS, STORAGE_PRETASK_TIMEOUT_MS, STORAGE_RESULTS_TTL_MS, STORAGE_STALE_MS (+26 more)

### Community 37 - "JenkinsAdapter"
Cohesion: 0.06
Nodes (6): BuildDetails, JenkinsAdapter, JenkinsPlatformPort, JobResult, JobRunState, ViewScanResult

### Community 39 - "ToolContext"
Cohesion: 0.09
Nodes (9): handle_message_agent(), handle_reply_to_agent(), handle_select_agent(), _sticky_work_style(), handle_defer_event(), handle_hold_watch(), handle_wait_for_agent(), handle_wait_for_jarvis() (+1 more)

### Community 40 - "Headhunter"
Cohesion: 0.07
Nodes (3): Headhunter, _raise_if_systemic_failure(), _sanitize_xml_fence()

### Community 42 - "CortexGraph.tsx"
Cohesion: 0.09
Nodes (35): graphology, AGENTS, DOMAINS, eventColor(), getExecutiveNeurons(), getStructuralEdges(), HEMISPHERE_X, NEURON_DESCRIPTIONS (+27 more)

### Community 43 - "prompt.py"
Cohesion: 0.08
Nodes (17): _resolve_maintainer_enum(), _build_closed_block(), build_event_header(), _build_identity_block(), _build_journal_block(), _build_mermaid_block(), _build_related_block(), _build_subject_block() (+9 more)

### Community 44 - "lucide-react"
Cohesion: 0.11
Nodes (23): lucide-react, createChatEvent(), ChatInput(), ChatInputProps, Draft, LastSubmission, ErrorBoundary, ErrorBoundaryProps (+15 more)

### Community 45 - "ConversationTurn"
Cohesion: 0.17
Nodes (26): emit_tool_result(), handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_recall_pruned_turns(), handle_ask_release_ai(), handle_fetch_jira_issue(), handle_greenwave() (+18 more)

### Community 46 - "TimeKeeperPage.tsx"
Cohesion: 0.12
Nodes (24): createSchedule(), deleteSchedule(), getSchedules(), refineInstructions(), ScheduleCreatePayload, ScheduleItem, toggleSchedule(), updateSchedule() (+16 more)

### Community 47 - "handlers_integration.py"
Cohesion: 0.11
Nodes (15): _do_retrigger(), _get_jira_reporter(), handle_comment_jira_issue(), handle_refresh_github_context(), handle_refresh_gitlab_context(), handle_refresh_kargo_context(), handle_retrigger_jenkins_build(), _is_darwin_reentrant_caller() (+7 more)

### Community 48 - "DashboardWSAdapter"
Cohesion: 0.09
Nodes (5): DashboardWSAdapter, prompt_display_name(), ChatEventRequest, ChatEventResponse, create_chat_event()

### Community 49 - "WorkspaceTaskItem.tsx"
Cohesion: 0.10
Nodes (25): ConversationTurn, DeferCountdownBar(), STATUS_COLORS, TICKET_COLORS, TicketNodeComponent(), TicketNodeData, relativeAge(), BORDER_COLOR (+17 more)

### Community 50 - "ws-client.js"
Cohesion: 0.09
Nodes (26): is429Error(), {
  DEFAULT_WORK_DIR, AGENT_CLI, AGENT_MODEL, AGENT_ROLE,
  EVENT_ID, EPHEMERAL, IDLE_TIMEOUT_MS,
  CLI_429_MAX_RETRIES, CLI_429_INITIAL_DELAY_MS, CLI_429_BACKOFF_MULTIPLIER,
}, { ensureEventDocument }, { executeCLIStreaming, prepareResultsDir, is429Error }, { filterSkillsByRole, filterSkillsByMode, swapActiveRules, restoreAllSkills }, fs, handleCancel(), resetTimer() (+18 more)

### Community 51 - "jenkins_observer.py"
Cohesion: 0.09
Nodes (13): _annotation_replace(), _strip_pipeline_annotations(), _clamp_confidence(), _parse_job_metadata(), _prepare_console_tail(), _redact_match(), _redact_secrets_in_text(), _sanitize_analysis_text() (+5 more)

### Community 52 - "create_schedule"
Cohesion: 0.06
Nodes (6): create_schedule(), delete_schedule(), get_schedule(), list_schedules(), toggle_schedule(), update_schedule()

### Community 53 - "ActiveStreamsContext.tsx"
Cohesion: 0.13
Nodes (26): AgentStreamCard(), AgentStreamCardProps, FloatingWindow(), MessageCards(), Dashboard(), GridTile(), GridTileProps, TileType (+18 more)

### Community 54 - "KnowledgeGraphStore"
Cohesion: 0.14
Nodes (4): _acquire(), KnowledgeGraphStore, _sanitize(), _with_timeout()

### Community 55 - "ui/package.json"
Cohesion: 0.08
Nodes (29): autoprefixer, cronstrue, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, graphology-layout-forceatlas2 (+21 more)

### Community 56 - "EventDrillDown.tsx"
Cohesion: 0.12
Nodes (25): three, getEventPulses(), BrainCore(), CortexDevPage(), CortexHeartbeat(), CortexHeartbeatProps, ensureKeyframes(), CortexLiveFeed() (+17 more)

### Community 58 - "server.js"
Cohesion: 0.08
Nodes (18): hasRegistryCredentials(), { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, fs, path, stageEventDocument(), fetchEventDocument(), fs, { handleRequest } (+10 more)

### Community 59 - "observations_mgmt.py"
Cohesion: 0.10
Nodes (10): get_report_client(), render_pdf(), bulk_delete_observations(), BulkDeleteRequest, delete_observation(), export_observations(), generate_observations_report(), rename_observation() (+2 more)

### Community 61 - "cognitive_graph.py"
Cohesion: 0.11
Nodes (11): get_pulse_tracker(), dismiss_proposals(), DismissRequest, get_all_shadow_interventions(), get_cognitive_graph(), get_cortex_activity(), get_cortex_status(), get_event_shadow_interventions() (+3 more)

### Community 62 - ".list_observations"
Cohesion: 0.08
Nodes (4): get_all_journal(), get_service_journal(), get_event_observations(), get_global_observations()

### Community 63 - "NodeInspector.tsx"
Cohesion: 0.13
Nodes (23): getClosedEvents(), ArchitectureEvent, ArgoCDOperation, ArchitectureGraph(), EVENT_LABELS, EventItem(), EventItemProps, healthTone() (+15 more)

### Community 64 - "useCortexData.ts"
Cohesion: 0.20
Nodes (23): getCognitiveGraph(), getCortexActivity(), getKGServiceDetail(), getKGServices(), getKGStats(), getRecentPulses(), CortexPage(), isOffRingCollection() (+15 more)

### Community 65 - "PulseBatch"
Cohesion: 0.10
Nodes (4): PulseBatch, PulsePort, PulseObserver, PulseTracker

### Community 67 - "VectorStore"
Cohesion: 0.11
Nodes (3): _decode_cursor(), _encode_cursor(), VectorStore

### Community 73 - "dependencies"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 74 - "StateWatcher"
Cohesion: 0.11
Nodes (3): _QueueEntry, StateWatcher, _Subscription

### Community 75 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 76 - "claude-guard.js"
Cohesion: 0.14
Nodes (18): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+10 more)

### Community 77 - "TokenUtilizationPage.tsx"
Cohesion: 0.16
Nodes (17): recharts, getFlowHistory(), FlowSnapshot, ObservationSeries, FlowHistoryPage(), formatTime(), RANGES, SparkCard() (+9 more)

### Community 80 - "reconcile.py"
Cohesion: 0.18
Nodes (9): _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers(), main(), _parse_frontmatter() (+1 more)

### Community 81 - "cli-setup.js"
Cohesion: 0.13
Nodes (19): { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync }, filterSkillsByMode() (+11 more)

### Community 86 - "devDependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 87 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 88 - "ServiceNode.tsx"
Cohesion: 0.15
Nodes (13): @xyflow/react, HealthStatus, NodeType, AppNodeData, ARGOCD_HEALTH_COLORS, SYNC_ICONS, NamespaceGroupNodeData, GENERIC_TAGS (+5 more)

### Community 91 - "get_report"
Cohesion: 0.11
Nodes (6): get_report(), list_reports(), reports_spa_no_slash(), reports_spa_with_slash(), search_reports(), _serve_spa()

### Community 92 - "gemini-sidecar/package.json"
Cohesion: 0.11
Nodes (17): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+9 more)

### Community 93 - "ArchitectureGraph.tsx"
Cohesion: 0.17
Nodes (16): @dagrejs/dagre, applyDagreLayout(), applyGridLayout(), applyLayout(), ArchitectureGraphInner(), buildGraph(), computeIdHash(), edgeTypes (+8 more)

### Community 95 - "._build_system_prompt"
Cohesion: 0.12
Nodes (3): _init_tool_names(), _strip_tool_names(), _wrap_section()

### Community 96 - "handle_classify_event"
Cohesion: 0.12
Nodes (5): handle_classify_event(), handle_request_user_approval(), IdleTimeoutPort, IncidentAdapterPort, StateWatcherPort

### Community 99 - "ShiftsPage.tsx"
Cohesion: 0.23
Nodes (16): getCurrentShift(), getShiftDetail(), getShiftsList(), ShiftReportFull, ShiftReportSummary, FailedClusterBadge(), getISOWeek(), getWeekDates() (+8 more)

### Community 100 - "catalog-skills.js"
Cohesion: 0.16
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 101 - "dispatch.py"
Cohesion: 0.18
Nodes (8): _build_prompt(), _check_security(), consume_wake_task(), _consume(), _dispatch_timeout_s(), dispatch_to_agent(), _consume_queue(), _sanitize_stdout()

### Community 103 - "cortex/types.ts"
Cohesion: 0.15
Nodes (15): ActiveEvent, EventSource, KGServiceEntity, CortexGraphProps, GraphLoaderProps, PulseTimelineProps, CognitiveGraphResponse, CortexHeartbeatMessage (+7 more)

### Community 104 - "generate_map.py"
Cohesion: 0.19
Nodes (6): _enumerate_gates(), _GateInfo, generate_phase_tool_map(), _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 108 - "graph_recall.py"
Cohesion: 0.19
Nodes (5): _format_graph_context(), get_graph_context(), _parse_props(), _sanitize(), translate_to_lookups()

### Community 110 - "ReconcileScheduler"
Cohesion: 0.16
Nodes (3): ReconcileScheduler, ResyncTrigger, StalenessGuard

### Community 111 - "observations_reporter.py"
Cohesion: 0.21
Nodes (7): _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), _sample_points(), _summarize()

### Community 115 - "._extract_context_flags"
Cohesion: 0.15
Nodes (3): compute_dispatch_backpressure(), ContextFlags, _safe_int_env()

### Community 117 - "get_current_shift"
Cohesion: 0.15
Nodes (3): get_current_shift(), get_shift_detail(), list_shifts()

### Community 119 - "NeuronInfoPanel.tsx"
Cohesion: 0.24
Nodes (12): KGServiceDetail, asNumber(), asString(), asStringArray(), Badge(), describeNeuron(), Hdr(), NeuronInfoPanel() (+4 more)

### Community 121 - "agent_websocket_handler"
Cohesion: 0.17
Nodes (3): agent_websocket_handler(), agent_ws_endpoint(), websocket_endpoint()

### Community 123 - "agents/__init__.py"
Cohesion: 0.24
Nodes (3): safe_execution(), wrapper(), SecurityError

### Community 124 - "testSetup.ts"
Cohesion: 0.18
Nodes (5): @tailwindcss/vite, @testing-library/react, vite, @vitejs/plugin-react, vitest

### Community 125 - "is_defer_event_available"
Cohesion: 0.18
Nodes (6): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 126 - "CiContextCard.tsx"
Cohesion: 0.31
Nodes (9): CiContext, CiContextCardProps, ConsoleTailBlock(), FailedJobRow(), annotationReplacer(), PIPELINE_ANNOTATION_RE, REDACTION_TRIGGER_KEYWORDS, stripAnsi() (+1 more)

### Community 127 - "entity_extractor.py"
Cohesion: 0.33
Nodes (5): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship

### Community 128 - "handle_report_incident"
Cohesion: 0.22
Nodes (4): handle_report_incident(), _resolve_escalation_scope(), handle_search_open_incidents(), handle_respond_to_jarvis()

### Community 132 - "has_unevaluated_close_blocker"
Cohesion: 0.20
Nodes (4): has_unevaluated_close_blocker(), _pred_jarvis_response(), _pred_unevaluated_close(), is_jarvis_acknowledgment()

### Community 133 - "knowledge_graph_api.py"
Cohesion: 0.31
Nodes (4): get_kg_store(), get_service_detail(), get_stats(), list_services()

### Community 134 - "vcs_approval.py"
Cohesion: 0.29
Nodes (5): get_gitlab_auth(), _resolve_github_head(), _resolve_gitlab_head(), resolve_live_head_sha(), verify_merge_guard()

### Community 135 - "CortexDevPage.tsx"
Cohesion: 0.36
Nodes (8): devQueryClient, MOCK_CORTEX_STATUS, MOCK_EVENT_ID, MOCK_NEURONS, MOCK_PULSE_BATCHES, MOCK_SHADOW, MOCK_THINKING, MOCK_WHISPERS

### Community 136 - "handle_notify_user_slack"
Cohesion: 0.22
Nodes (4): _alert_wrapper_retrigger(), handle_notify_user_slack(), _resolve_slack_user(), build_event_report_md()

### Community 148 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 149 - "state.js"
Cohesion: 0.33
Nodes (4): { AGENT_ROLE }, _blackboardTurns, _inboundMessages, _teammateMessages

### Community 150 - "validate-mutations.sh"
Cohesion: 0.73
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

## Knowledge Gaps
- **13 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+8 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2190 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **98 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `main.py`, `brain.py`, `queue.py`, `nightwatcher_tools.py`, `auth.py`, `logging`, `Brain`, `ConversationMessage`, `HeadhunterJira`, `LiveAPIAdapter`, `Service`, `httpx`, `EventDocument`, `slack.py`, `get_notebook`, `.__init__`, `re`, `ConversationTurn`, `DashboardWSAdapter`, `jenkins_observer.py`, `create_schedule`, `observations_mgmt.py`, `.list_observations`, `.start_event_loop`, `get_report`, `observations_reporter.py`, `ScheduleRepository`, `get_current_shift`?**
  _High betweenness centrality (0.122) - this node is a cross-community bridge._
- **Are the 80 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 80 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.014453699167074964 - nodes in this community are weakly interconnected._
- **Why does `Brain` connect `Brain` to `BlackboardState`, `main.py`, `brain.py`, `llm/__init__.py`, `._run_agent_task`, `EventDocument`, `.stop_event_loop`, `slack.py`, `QueueTrigger`, `._format_merge_evidence`, `.__init__`, `.broadcast`, `.next_turn_number`, `._process_with_llm`, `ConversationTurn`, `DashboardWSAdapter`, `._close_and_broadcast`, `PulseBatch`, `._build_contents`, `BrainSkillLoader`, `StateWatcher`, `ReflexSearcher`, `.start_event_loop`, `._build_system_prompt`, `src/ports.py`, `ReconcileScheduler`, `._extract_context_flags`, `IdleTimeoutManager`, `agents/__init__.py`?**
  _High betweenness centrality (0.068) - this node is a cross-community bridge._
- **Are the 21 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 21 INFERRED edges - model-reasoned connections that need verification._
- **Should `main.py` be split into smaller, more focused modules?**
  _Cohesion score 0.022775013819789938 - nodes in this community are weakly interconnected._