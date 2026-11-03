# Graph Report - Blackboard  (2026-11-03)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 4941 nodes · 11053 edges · 189 communities (86 shown, 103 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 932 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `fff04b48`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BlackboardState
- logging
- queue.py
- main.py
- react
- EventSidebar.tsx
- client.ts
- slack.py
- tool_gates.py
- Brain
- merge-guard.js
- App.tsx
- JenkinsObserver
- LiveAPIAdapter
- Archivist
- http-handler.js
- jenkins-mcp.js
- ._run_agent_task
- EventDocument
- useMemory.ts
- fetchApi
- scheduling/__init__.py
- EventDrillDown.tsx
- BrainSkillLoader
- Aligner
- _BrainToolContext
- GitLabPlatform
- models.py
- EventRepository
- .get_graph_data
- nightwatcher_tools.py
- observations_mgmt.py
- cli-executor.js
- KnowledgeGraphStore
- storage-recycler.js
- ui/package.json
- JenkinsAdapter
- ToolContext
- ._process_with_llm
- GitHubPlatform
- ActiveStreamsContext.tsx
- live_api_adapter.py
- ConversationTurn
- spawn_event_namer_task
- ArchitectureGraph.tsx
- TimeKeeperPage.tsx
- CortexGraph.tsx
- ws-client.js
- Headhunter
- state/ports.py
- useCortexData.ts
- TopologyRepository
- VectorStore
- ._close_and_broadcast
- server.js
- SlackChannel
- context_parts.py
- brain.py
- formatter.py
- adf_to_markdown
- GeminiAdapter
- NodeInspector.tsx
- dispatch_to_agent
- EphemeralProvisioner
- ArgoCDObserver
- useQueue.ts
- llm/__init__.py
- @tanstack/react-query
- ._build_contents
- handlers_integration.py
- ._get_manager
- KargoObserver
- GitHubAppAuth
- dependencies
- NeuronInfoPanel.tsx
- EventHistory.tsx
- compilerOptions
- claude-guard.js
- DashboardWSAdapter
- BrainIntrospectionPort
- reconcile.py
- cli-setup.js
- VcsPlatformPort
- ReflexSearcher
- devDependencies
- compilerOptions
- SpawnPollResult
- AgentRegistry
- NightwatcherObserver
- get_report
- gemini-sidecar/package.json
- handle_classify_event
- ObservationRepository
- ShiftsPage.tsx
- QuotaTracker
- catalog-skills.js
- ClaudeAdapter
- prompt.py
- KubernetesSpawnHealthAdapter
- SlackAccessGate
- generate_map.py
- OIDCKeyAdapter
- IdleTimeoutManager
- EscalationRepository
- ScheduleRepository
- MultiInstallationManager
- agent_websocket_handler
- ._extract_context_flags
- HeadhunterJira
- TokenMeter
- ScheduleCreateRequest
- .start_event_loop
- ._github_poll_and_process
- is_defer_event_available
- generate_event_title
- ._post_agent_recall
- ReconcileScheduler
- entity_extractor.py
- ._send_turn_to_thread
- knowledge_graph_api.py
- FairQueue
- get_quota_tracker
- pydantic
- SmartsheetMaintainerCache
- .has_reeval_signal
- Trigger
- AsyncGitHubClient
- GitLabTokenAuth
- useDeferCountdown.ts
- _md_table_to_text
- ._evaluate_health
- handlers_lookup.py
- TimeKeeperObserver
- event_markdown.py
- scripts
- state.js
- validate-mutations.sh
- Pulse
- dex_proxy
- ._wait_for_registration
- submit_feedback
- refine_instructions
- QueueTrigger
- StalenessGuard
- ResyncTrigger
- has_unevaluated_close_blocker
- list_incidents
- require-results.sh
- _WSFrameFilter
- math
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
1. `BlackboardState` - 283 edges
2. `Brain` - 148 edges
3. `ConversationTurn` - 122 edges
4. `ToolContext` - 103 edges
5. `GateContext` - 94 edges
6. `react` - 82 edges
7. `EventDocument` - 78 edges
8. `fetchApi()` - 66 edges
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

## Communities (189 total, 103 thin omitted)

### Community 0 - "BlackboardState"
Cohesion: 0.01
Nodes (14): FlowSnapshot, get_all_journal(), get_service_journal(), get_notebook(), get_event_observations(), get_global_observations(), get_shift_detail(), create_schedule() (+6 more)

### Community 1 - "logging"
Cohesion: 0.03
Nodes (23): _check_security(), _get_static_maintainer_emails(), _get_allowed_mention_authors(), _get_static_maintainer_emails(), _safe_int(), _parse_job_metadata(), create_adapter(), record_token_usage() (+15 more)

### Community 2 - "queue.py"
Cohesion: 0.02
Nodes (65): get_token_meter(), get_archivist(), get_blackboard(), get_brain(), get_pulse_tracker(), EventStatus, dismiss_proposals(), DismissRequest (+57 more)

### Community 3 - "main.py"
Cohesion: 0.02
Nodes (35): Architect, AgentClient, Developer, set_incident_options(), SysAdmin, set_oidc_adapter(), get_aligner(), get_architect() (+27 more)

### Community 4 - "react"
Cohesion: 0.04
Nodes (94): lucide-react, react, react-router-dom, createChatEvent(), getEvents(), getKargoStages(), updateEventTitle(), CiContext (+86 more)

### Community 5 - "EventSidebar.tsx"
Cohesion: 0.04
Nodes (90): HeadhunterTodo, JenkinsPendingItem, JiraMission, ReportFull, ReportMeta, CiContextCard(), ConsoleTailBlock(), FailedJobRow() (+82 more)

### Community 6 - "client.ts"
Cohesion: 0.04
Nodes (86): ApiError, bulkDeleteObservations(), deleteNote(), deleteObservation(), exportObservations(), ExtractionResult, generateObservationsReport(), getAgents() (+78 more)

### Community 7 - "slack.py"
Cohesion: 0.04
Nodes (28): can_append_message(), can_approve_event(), can_override_domain(), can_rename_event(), _claims_to_user(), get_user_from_request(), get_user_from_slack(), get_user_from_websocket() (+20 more)

### Community 8 - "tool_gates.py"
Cohesion: 0.05
Nodes (78): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+70 more)

### Community 10 - "merge-guard.js"
Cohesion: 0.05
Nodes (69): analyzeString(), analyzeTokens(), API_VALUED, apiTokens(), apiWriteNeedsGuard(), assignName(), bareBranchProtected(), base() (+61 more)

### Community 11 - "App.tsx"
Cohesion: 0.05
Nodes (56): oidc-client-ts, react-dom, dismissProposals(), EnhancementProposal, getConfig(), getHandoffReports(), getIncidents(), getProposals() (+48 more)

### Community 12 - "JenkinsObserver"
Cohesion: 0.04
Nodes (14): _annotation_replace(), _strip_pipeline_annotations(), _clamp_confidence(), _env_flag(), JenkinsObserver, _prepare_console_tail(), _redact_build_parameters(), _redact_match() (+6 more)

### Community 15 - "http-handler.js"
Cohesion: 0.09
Nodes (58): resolveCommand(), writeAgyMcpServer(), writeClaudeMcpServer(), buildArgoCDMcpConfig(), createAppJWT(), discoverAndGenerateTokens(), _discoverAndGenerateTokensInner(), discoverInstallations() (+50 more)

### Community 16 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 17 - "._run_agent_task"
Cohesion: 0.06
Nodes (9): on_huddle(), on_progress(), on_huddle(), on_progress(), _compute_processed_up_to(), _sanitize_error_text(), _sanitize_override_reason(), _select_dispatch_tier() (+1 more)

### Community 19 - "useMemory.ts"
Cohesion: 0.08
Nodes (47): applyLessons(), correctMemory(), createKnowledge(), createLesson(), deleteKnowledge(), deleteLesson(), ExtractedCorrection, ExtractedLesson (+39 more)

### Community 20 - "fetchApi"
Cohesion: 0.09
Nodes (41): @uiw/react-markdown-preview, approveEvent(), closeEvent(), enforceCasualDomain(), fetchApi(), getEventReport(), getSchedule(), rejectEvent() (+33 more)

### Community 21 - "scheduling/__init__.py"
Cohesion: 0.06
Nodes (15): _alert_wrapper_retrigger(), _do_retrigger(), handle_refresh_github_context(), handle_refresh_gitlab_context(), handle_refresh_kargo_context(), StateWatcherPort, GitHubPrRef, GitLabMrRef (+7 more)

### Community 22 - "EventDrillDown.tsx"
Cohesion: 0.08
Nodes (42): three, getEventPulses(), EventSource, BrainCore(), CortexDevPage(), devQueryClient, CortexHeartbeat(), CortexHeartbeatProps (+34 more)

### Community 23 - "BrainSkillLoader"
Cohesion: 0.05
Nodes (3): BrainSkillLoader, _SkillCorpus, _wrap_section()

### Community 27 - "models.py"
Cohesion: 0.06
Nodes (21): AppNode, ChatRequest, ChatResponse, EventInput, EventMetrics, FlowMetricsResponse, GraphEdge, GraphNode (+13 more)

### Community 29 - ".get_graph_data"
Cohesion: 0.05
Nodes (8): GraphResponse, get_graph_data(), get_mermaid_diagram(), get_service_details(), get_topology(), list_services(), calculate_health_from_argocd(), infer_node_type()

### Community 30 - "nightwatcher_tools.py"
Cohesion: 0.09
Nodes (22): ShiftIncident, ShiftInvestigation, build_report_iteration_prompt(), build_summary_prompt(), extract_full_links(), _normalize_gitlab_host(), build_extend_tool(), build_report_tool() (+14 more)

### Community 31 - "observations_mgmt.py"
Cohesion: 0.06
Nodes (18): get_report_client(), _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), render_pdf(), _sample_points() (+10 more)

### Community 32 - "cli-executor.js"
Cohesion: 0.09
Nodes (36): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS, STORAGE_PRETASK_TIMEOUT_MS, resolveStorageRoot }, buildCLICommand(), { checkAndRecycleStorage, pinTaskCwd, unpinTaskCwd }, CLAUDE_JSON_PATH, cp, executeCLI(), executeCLIStreaming(), FALLBACK_MODEL (+28 more)

### Community 33 - "KnowledgeGraphStore"
Cohesion: 0.09
Nodes (9): _format_graph_context(), get_graph_context(), _parse_props(), _sanitize(), translate_to_lookups(), _acquire(), KnowledgeGraphStore, _sanitize() (+1 more)

### Community 34 - "storage-recycler.js"
Cohesion: 0.08
Nodes (34): withTaskStorage(), resolveStorageRoot(), ROLE_TIMEOUTS, STORAGE_ACTIVITY_HEARTBEAT_MS, STORAGE_MAX_TIER3_DELETIONS, STORAGE_PRETASK_TIMEOUT_MS, STORAGE_RESULTS_TTL_MS, STORAGE_STALE_MS (+26 more)

### Community 35 - "ui/package.json"
Cohesion: 0.06
Nodes (34): autoprefixer, cronstrue, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, graphology-layout-forceatlas2 (+26 more)

### Community 36 - "JenkinsAdapter"
Cohesion: 0.06
Nodes (6): BuildDetails, JenkinsAdapter, JenkinsPlatformPort, JobResult, JobRunState, ViewScanResult

### Community 37 - "ToolContext"
Cohesion: 0.09
Nodes (9): handle_message_agent(), handle_reply_to_agent(), handle_select_agent(), _sticky_work_style(), handle_defer_event(), handle_hold_watch(), handle_wait_for_agent(), handle_wait_for_jarvis() (+1 more)

### Community 40 - "ActiveStreamsContext.tsx"
Cohesion: 0.10
Nodes (32): getFlowMetrics(), FlowMetrics, AgentStreamCard(), AgentStreamCardProps, FloatingWindow(), MessageCards(), Dashboard(), FlowHealthWidget() (+24 more)

### Community 41 - "live_api_adapter.py"
Cohesion: 0.07
Nodes (7): _build_skill_refs(), PulseBatch, PulseContext, PulsePort, PulseObserver, PulseTracker, redact_pii()

### Community 42 - "ConversationTurn"
Cohesion: 0.16
Nodes (28): emit_tool_result(), handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_recall_pruned_turns(), handle_ask_release_ai(), handle_fetch_jira_issue(), handle_greenwave() (+20 more)

### Community 43 - "spawn_event_namer_task"
Cohesion: 0.11
Nodes (11): spawn_event_namer_task(), format_event_summary(), handle_app_home_opened(), handle_app_mention(), handle_approve(), handle_create_event_modal(), handle_darwin_command(), handle_home_create_event() (+3 more)

### Community 44 - "ArchitectureGraph.tsx"
Cohesion: 0.09
Nodes (28): @dagrejs/dagre, @xyflow/react, HealthStatus, NodeType, AppNodeData, applyDagreLayout(), applyGridLayout(), applyLayout() (+20 more)

### Community 45 - "TimeKeeperPage.tsx"
Cohesion: 0.12
Nodes (24): createSchedule(), deleteSchedule(), getSchedules(), refineInstructions(), ScheduleCreatePayload, ScheduleItem, toggleSchedule(), updateSchedule() (+16 more)

### Community 46 - "CortexGraph.tsx"
Cohesion: 0.11
Nodes (31): graphology, ActiveEvent, KGServiceEntity, eventColor(), getExecutiveNeurons(), getStructuralEdges(), DEFAULT_TYPE_BUDGET, evictLru() (+23 more)

### Community 47 - "ws-client.js"
Cohesion: 0.09
Nodes (26): is429Error(), {
  DEFAULT_WORK_DIR, AGENT_CLI, AGENT_MODEL, AGENT_ROLE,
  EVENT_ID, EPHEMERAL, IDLE_TIMEOUT_MS,
  CLI_429_MAX_RETRIES, CLI_429_INITIAL_DELAY_MS, CLI_429_BACKOFF_MULTIPLIER,
}, { ensureEventDocument }, { executeCLIStreaming, prepareResultsDir, is429Error }, { filterSkillsByRole, filterSkillsByMode, swapActiveRules, restoreAllSkills }, fs, handleCancel(), resetTimer() (+18 more)

### Community 49 - "state/ports.py"
Cohesion: 0.08
Nodes (5): ArchitectureEvent, EventType, list_events(), CortexRepository, MetricsRepository

### Community 50 - "useCortexData.ts"
Cohesion: 0.16
Nodes (28): getCognitiveGraph(), getCortexActivity(), getKGServiceDetail(), getKGServices(), getKGStats(), getKnowledgeById(), getLessonById(), getMemory() (+20 more)

### Community 51 - "TopologyRepository"
Cohesion: 0.08
Nodes (4): Service, Snapshot, TopologySnapshot, TopologyRepository

### Community 52 - "VectorStore"
Cohesion: 0.09
Nodes (3): _decode_cursor(), _encode_cursor(), VectorStore

### Community 54 - "server.js"
Cohesion: 0.08
Nodes (18): hasRegistryCredentials(), { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, fs, path, stageEventDocument(), fetchEventDocument(), fs, { handleRequest } (+10 more)

### Community 56 - "context_parts.py"
Cohesion: 0.09
Nodes (12): _apply_sibling_signature(), build_function_response(), build_single_function_response(), compress_contents(), estimate_msg_tokens(), estimate_tokens(), extract_model_parts(), normalize_response_parts() (+4 more)

### Community 57 - "brain.py"
Cohesion: 0.11
Nodes (5): handle_report_incident(), _resolve_escalation_scope(), _resolve_domain(), resolve_event_domain(), _resolve_phase()

### Community 58 - "formatter.py"
Cohesion: 0.11
Nodes (12): build_access_denied_home_view(), build_home_tab_view(), _context_line(), create_feedback_block(), format_plan_block(), format_task_card(), format_turn(), _md_to_mrkdwn() (+4 more)

### Community 59 - "adf_to_markdown"
Cohesion: 0.12
Nodes (10): _adf_to_text(), _escape_jql_string(), JiraIncidentAdapter, adf_to_markdown(), _apply_marks(), _children(), _render(), _render_list() (+2 more)

### Community 61 - "NodeInspector.tsx"
Cohesion: 0.13
Nodes (23): getClosedEvents(), ArchitectureEvent, ArgoCDOperation, ArchitectureGraph(), EVENT_LABELS, EventItem(), EventItemProps, healthTone() (+15 more)

### Community 62 - "dispatch_to_agent"
Cohesion: 0.10
Nodes (8): _build_prompt(), consume_wake_task(), _consume(), _dispatch_timeout_s(), dispatch_to_agent(), _consume_queue(), _sanitize_stdout(), send_cancel()

### Community 65 - "useQueue.ts"
Cohesion: 0.14
Nodes (22): getActiveEvents(), getAlignerPending(), getEventDocument(), getHeadhunterPending(), getJenkinsPending(), getWaitingApprovalEvents(), EventDocument, MessageStatus (+14 more)

### Community 66 - "llm/__init__.py"
Cohesion: 0.16
Nodes (5): FunctionCall, LLMChunk, LLMPort, LLMResponse, TokenUsage

### Community 67 - "@tanstack/react-query"
Cohesion: 0.15
Nodes (19): recharts, @tanstack/react-query, getFlowHistory(), getJiraMissions(), postJiraAction(), FlowSnapshot, FlowHistoryPage(), formatTime() (+11 more)

### Community 69 - "handlers_integration.py"
Cohesion: 0.10
Nodes (10): _get_jira_reporter(), handle_comment_jira_issue(), _is_darwin_reentrant_caller(), jenkins_retrigger_cooldown_key(), _resolve_maintainer_enum(), _resolve_slack_user(), format_jira_for_llm(), build_event_report_md() (+2 more)

### Community 72 - "GitHubAppAuth"
Cohesion: 0.11
Nodes (3): _find_pem_file(), get_github_auth(), GitHubAppAuth

### Community 73 - "dependencies"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 74 - "NeuronInfoPanel.tsx"
Cohesion: 0.12
Nodes (22): AGENTS, DOMAINS, HEMISPHERE_X, NEURON_DESCRIPTIONS, PHASE_SKILL_FOLDERS, PHASE_TOOL_PRIORITY, PHASES, StructuralEdge (+14 more)

### Community 75 - "EventHistory.tsx"
Cohesion: 0.15
Nodes (19): getReport(), getReports(), CompactCardStrip(), EventHistory(), TimeRange, ViewMode, EventHistoryGrid(), EventHistoryTable() (+11 more)

### Community 76 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 77 - "claude-guard.js"
Cohesion: 0.14
Nodes (18): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+10 more)

### Community 79 - "BrainIntrospectionPort"
Cohesion: 0.10
Nodes (3): BrainIntrospectionPort, BrainLifecyclePort, BroadcastPort

### Community 80 - "reconcile.py"
Cohesion: 0.18
Nodes (9): _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers(), main(), _parse_frontmatter() (+1 more)

### Community 81 - "cli-setup.js"
Cohesion: 0.13
Nodes (19): { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync }, filterSkillsByMode() (+11 more)

### Community 84 - "devDependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 85 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 88 - "NightwatcherObserver"
Cohesion: 0.14
Nodes (5): ShiftReport, NightwatcherObserver, build_manifest_table(), build_system_prompt(), extract_event_links()

### Community 89 - "get_report"
Cohesion: 0.11
Nodes (6): get_report(), list_reports(), reports_spa_no_slash(), reports_spa_with_slash(), search_reports(), _serve_spa()

### Community 90 - "gemini-sidecar/package.json"
Cohesion: 0.11
Nodes (17): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+9 more)

### Community 91 - "handle_classify_event"
Cohesion: 0.12
Nodes (4): handle_classify_event(), handle_request_user_approval(), IdleTimeoutPort, IncidentAdapterPort

### Community 93 - "ShiftsPage.tsx"
Cohesion: 0.23
Nodes (16): getCurrentShift(), getShiftDetail(), getShiftsList(), ShiftReportFull, ShiftReportSummary, FailedClusterBadge(), getISOWeek(), getWeekDates() (+8 more)

### Community 95 - "catalog-skills.js"
Cohesion: 0.16
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 98 - "prompt.py"
Cohesion: 0.21
Nodes (10): _build_closed_block(), build_event_header(), _build_identity_block(), _build_journal_block(), _build_mermaid_block(), _build_related_block(), _build_subject_block(), _build_timing_block() (+2 more)

### Community 101 - "generate_map.py"
Cohesion: 0.19
Nodes (6): _enumerate_gates(), _GateInfo, generate_phase_tool_map(), _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 109 - "agent_websocket_handler"
Cohesion: 0.17
Nodes (4): agent_websocket_handler(), _heartbeat(), agent_ws_endpoint(), websocket_endpoint()

### Community 110 - "._extract_context_flags"
Cohesion: 0.15
Nodes (3): compute_dispatch_backpressure(), ContextFlags, _safe_int_env()

### Community 117 - "is_defer_event_available"
Cohesion: 0.18
Nodes (6): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 118 - "generate_event_title"
Cohesion: 0.22
Nodes (3): generate_event_title(), get_adapter(), _get_semaphore()

### Community 122 - "entity_extractor.py"
Cohesion: 0.33
Nodes (5): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship

### Community 123 - "._send_turn_to_thread"
Cohesion: 0.27
Nodes (3): extract_tables(), get_agent_notification_text(), get_turn_attachment_color()

### Community 124 - "knowledge_graph_api.py"
Cohesion: 0.31
Nodes (4): get_kg_store(), get_service_detail(), get_stats(), list_services()

### Community 127 - "get_quota_tracker"
Cohesion: 0.22
Nodes (3): get_quota_tracker(), llm_stats(), receive_telemetry()

### Community 134 - "useDeferCountdown.ts"
Cohesion: 0.47
Nodes (7): DeferCountdownState, useDeferCountdown(), computeDeferProgress(), DeferTimeline, formatDeferRemaining(), inferDeferFromConversation(), resolveDeferTimeline()

### Community 135 - "_md_table_to_text"
Cohesion: 0.25
Nodes (4): _replace(), _md_table_to_block_kit(), _md_table_to_text(), _parse_md_table()

### Community 138 - "handlers_lookup.py"
Cohesion: 0.32
Nodes (3): _safe_int(), handle_consult_deep_memory(), handle_google_web_search()

### Community 143 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 144 - "state.js"
Cohesion: 0.33
Nodes (4): { AGENT_ROLE }, _blackboardTurns, _inboundMessages, _teammateMessages

### Community 145 - "validate-mutations.sh"
Cohesion: 0.73
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

## Knowledge Gaps
- **13 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+8 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2160 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **103 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `logging`, `queue.py`, `main.py`, `slack.py`, `Brain`, `LiveAPIAdapter`, `EventDocument`, `BrainSkillLoader`, `submit_feedback`, `models.py`, `EventRepository`, `.get_graph_data`, `nightwatcher_tools.py`, `observations_mgmt.py`, `live_api_adapter.py`, `ConversationTurn`, `state/ports.py`, `TopologyRepository`, `brain.py`, `DashboardWSAdapter`, `NightwatcherObserver`, `get_report`, `ScheduleRepository`, `HeadhunterJira`, `generate_event_title`?**
  _High betweenness centrality (0.107) - this node is a cross-community bridge._
- **Are the 80 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 80 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.010907768755302388 - nodes in this community are weakly interconnected._
- **Why does `Brain` connect `Brain` to `BlackboardState`, `logging`, `queue.py`, `main.py`, `slack.py`, `._run_agent_task`, `EventDocument`, `Pulse`, `scheduling/__init__.py`, `BrainSkillLoader`, `QueueTrigger`, `models.py`, `ResyncTrigger`, `StalenessGuard`, `.broadcast`, `._process_with_llm`, `live_api_adapter.py`, `ConversationTurn`, `state/ports.py`, `._close_and_broadcast`, `brain.py`, `._build_contents`, `DashboardWSAdapter`, `BrainIntrospectionPort`, `ReflexSearcher`, `QuotaTracker`, `IdleTimeoutManager`, `._extract_context_flags`, `.start_event_loop`, `._post_agent_recall`, `ReconcileScheduler`?**
  _High betweenness centrality (0.053) - this node is a cross-community bridge._
- **Are the 20 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Should `logging` be split into smaller, more focused modules?**
  _Cohesion score 0.028852056476365868 - nodes in this community are weakly interconnected._