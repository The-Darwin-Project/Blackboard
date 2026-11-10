# Graph Report - Blackboard  (2026-11-10)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 5112 nodes · 11421 edges · 221 communities (115 shown, 106 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 941 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `e8be120d`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BlackboardState
- client.ts
- logging
- BaseModel
- EventChatPanel.tsx
- tool_gates.py
- Brain
- ReconcileScheduler
- ._run_agent_task
- App.tsx
- cognitive_graph.py
- HeadhunterJira
- asyncio
- http-handler.js
- WorkspaceInspector.tsx
- jenkins-mcp.js
- BrainSkillLoader
- EventDocument
- EventSidebar.tsx
- auth.py
- agents/__init__.py
- useMemory.ts
- brain.py
- Aligner
- ToolContext
- _BrainToolContext
- react
- merge-guard.js
- KnowledgeGraphStore
- GitLabPlatform
- TurnBubble.tsx
- observations_mgmt.py
- time
- cli-executor.js
- fetchApi
- main.py
- storage-recycler.js
- SlackChannel
- JenkinsAdapter
- ._process_with_llm
- lucide-react
- EventRepository
- formatter.py
- ConversationTurn
- jira.py
- live_api_adapter.py
- spawn_event_namer_task
- GitHubPlatform
- StreamGrid.tsx
- queue.py
- ws-client.js
- ui/package.json
- lifespan
- ._build_contents
- Headhunter
- re
- NodeInspector.tsx
- useCortexData.ts
- server.js
- dashboard_ws.py
- dependencies.py
- journal.py
- slack.py
- CortexGraph.tsx
- StateWatcher
- ._close_and_broadcast
- IdleTimeoutManager
- context_parts.py
- nightwatcher.py
- nightwatcher_tools.py
- state/__init__.py
- tool_router.py
- types.py
- gemini_client.py
- GeminiAdapter
- ArgoCDObserver
- NeuronInfoPanel.tsx
- create_adapter
- get_archivist
- NightwatcherObserver
- KargoObserver
- GitHubAppAuth
- dependencies
- cortex/types.ts
- compilerOptions
- claude-guard.js
- cli-setup.js
- VcsPlatformPort
- reports.py
- FloatingWindow.tsx
- reconcile.py
- EventEvidence
- ScheduleCreateRequest
- ReflexSearcher
- devDependencies
- compilerOptions
- ArchitectureGraph.tsx
- LiveAPIAdapter
- EphemeralProvisioner
- ClaudeAdapter
- gemini-sidecar/package.json
- _sanitize_analysis_text
- ObservationRepository
- ShiftsPage.tsx
- catalog-skills.js
- Archivist
- state/ports.py
- EscalationRepository
- TokenUtilizationPage.tsx
- get_brain
- JiraIncidentAdapter
- VectorStore
- list_active_events
- generate_map.py
- handlers_planning.py
- OIDCKeyAdapter
- KubernetesSpawnHealthAdapter
- JenkinsObserver
- ServiceNode.tsx
- ScheduleRepository
- MultiInstallationManager
- ephemeral_provisioner.py
- analyzeTokens
- EventDrillDown.tsx
- .scroll
- TokenMeter
- JarvisMemoryPage.tsx
- .get_event
- CortexLiveFeed.tsx
- testSetup.ts
- is_defer_event_available
- MessageStatus
- ._run_clustering_agent
- gitGuard
- parseShell
- _is_event_closed_or_missing
- ._post_agent_recall
- entity_extractor.py
- ._github_poll_and_process
- ._process_candidates
- ._triage_and_build_evidence
- ._drain_once
- observers/timekeeper.py
- PulseBatch
- classifyTool
- get_quota_tracker
- SpawnPollResult
- SmartsheetMaintainerCache
- record_token_usage
- list_shifts
- AsyncGitHubClient
- GitLabTokenAuth
- ._evaluate_health
- enforce_casual_domain
- ConversationMessage
- FlowSnapshot
- update_knowledge
- CortexRepository
- validate-mutations.sh
- list_events
- scripts
- state.js
- ._process_message
- DispatchMetrics
- AppNode
- list_failed_stages
- close_event_by_user
- dex_proxy
- ._wait_for_registration
- handle_report_incident
- classify
- has_unevaluated_close_blocker
- delete_notebook_note
- headhunter_pending_todos
- TitleUpdateRequest
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
- build_gate_context
- diagnose_rejection
- GateDefinition
- _pred_dispatch_defer
- _pred_hard_strip_defer
- _pred_jarvis_wait
- _pred_obs_plateau
- _pred_silent_park
- _tools_wait_loop
- build_summary_tool

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

## Communities (221 total, 106 thin omitted)

### Community 1 - "client.ts"
Cohesion: 0.03
Nodes (103): @tanstack/react-query, ApiError, bulkDeleteObservations(), deleteNote(), deleteObservation(), exportObservations(), ExtractionResult, generateObservationsReport() (+95 more)

### Community 2 - "logging"
Cohesion: 0.04
Nodes (16): _annotation_replace(), _strip_pipeline_annotations(), _get_static_maintainer_emails(), _get_allowed_mention_authors(), _get_static_maintainer_emails(), _safe_int(), _env_flag(), _parse_job_metadata() (+8 more)

### Community 3 - "BaseModel"
Cohesion: 0.03
Nodes (16): EventInput, GraphEdge, GraphNode, GraphResponse, Service, Snapshot, TicketNode, TopologySnapshot (+8 more)

### Community 4 - "EventChatPanel.tsx"
Cohesion: 0.06
Nodes (55): getReport(), getReports(), ReportFull, ReportMeta, SubjectType, DeferCountdownBar(), CompactCardStrip(), EventHistory() (+47 more)

### Community 5 - "tool_gates.py"
Cohesion: 0.05
Nodes (78): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+70 more)

### Community 7 - "ReconcileScheduler"
Cohesion: 0.04
Nodes (7): FlowCollector, FairQueue, ReconcileScheduler, Trigger, QueueTrigger, ResyncTrigger, StalenessGuard

### Community 8 - "._run_agent_task"
Cohesion: 0.06
Nodes (11): on_huddle(), on_progress(), on_huddle(), on_progress(), _compute_processed_up_to(), _is_automated_nudge(), _sanitize_error_text(), _sanitize_override_reason() (+3 more)

### Community 9 - "App.tsx"
Cohesion: 0.06
Nodes (46): oidc-client-ts, react-router-dom, getConfig(), getWSAuthFailureCallback(), setOnUnauthorized(), setTokenGetter(), setWSAuthFailureCallback(), AppConfig (+38 more)

### Community 10 - "cognitive_graph.py"
Cohesion: 0.05
Nodes (18): get_blackboard(), get_pulse_tracker(), dismiss_proposals(), DismissRequest, get_all_shadow_interventions(), get_cognitive_graph(), get_cortex_activity(), get_cortex_status() (+10 more)

### Community 11 - "HeadhunterJira"
Cohesion: 0.05
Nodes (3): HeadhunterJira, _walk_adf_mentions(), _walk()

### Community 12 - "asyncio"
Cohesion: 0.06
Nodes (13): AgentConnection, AgentRegistry, agent_websocket_handler(), _heartbeat(), _build_prompt(), consume_wake_task(), _consume(), _dispatch_timeout_s() (+5 more)

### Community 13 - "http-handler.js"
Cohesion: 0.09
Nodes (58): resolveCommand(), writeAgyMcpServer(), writeClaudeMcpServer(), buildArgoCDMcpConfig(), createAppJWT(), discoverAndGenerateTokens(), _discoverAndGenerateTokensInner(), discoverInstallations() (+50 more)

### Community 14 - "WorkspaceInspector.tsx"
Cohesion: 0.07
Nodes (52): updateEventTitle(), CiContext, ConversationTurn, TokenUsageDict, CiContextCard(), CiContextCardProps, ConsoleTailBlock(), FailedJobRow() (+44 more)

### Community 15 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 16 - "BrainSkillLoader"
Cohesion: 0.05
Nodes (4): BrainSkillLoader, _SkillCorpus, _wrap_section(), BrainIntrospectionPort

### Community 18 - "EventSidebar.tsx"
Cohesion: 0.09
Nodes (52): getJiraMissions(), HeadhunterTodo, postJiraAction(), ACTION_BADGE, formatAge(), HeadhunterQueuePanel(), renderItem(), IN_PROGRESS_ACTIONS (+44 more)

### Community 19 - "auth.py"
Cohesion: 0.05
Nodes (17): _claims_to_user(), get_user_from_request(), get_user_from_slack(), get_user_from_websocket(), require_auth(), require_obs_admin(), UserContext, _validate_jwt() (+9 more)

### Community 20 - "agents/__init__.py"
Cohesion: 0.06
Nodes (8): Architect, AgentClient, Developer, _check_security(), safe_execution(), wrapper(), SecurityError, SysAdmin

### Community 21 - "useMemory.ts"
Cohesion: 0.07
Nodes (49): applyLessons(), correctMemory(), createKnowledge(), createLesson(), deleteKnowledge(), deleteLesson(), ExtractedCorrection, ExtractedLesson (+41 more)

### Community 22 - "brain.py"
Cohesion: 0.06
Nodes (17): _sanitize_lesson_text(), _is_seed_turn(), handle_set_phase(), ChatRequest, ChatResponse, EventMetrics, EventStatus, Metrics (+9 more)

### Community 24 - "ToolContext"
Cohesion: 0.08
Nodes (12): handle_message_agent(), handle_reply_to_agent(), handle_select_agent(), _sticky_work_style(), handle_classify_event(), handle_defer_event(), handle_hold_watch(), handle_respond_to_jarvis() (+4 more)

### Community 26 - "react"
Cohesion: 0.09
Nodes (34): react, getEvents(), ActivityStream(), ChatInput(), ChatInputProps, Draft, LastSubmission, ActivityPanel() (+26 more)

### Community 27 - "merge-guard.js"
Cohesion: 0.04
Nodes (46): API_VALUED, ARGO_MUTATING, ARGO_READ_SUB, ARGO_READ_TOP, BODY_FLAG, BROWSER_READ, CTX, ENV_BUILTINS (+38 more)

### Community 28 - "KnowledgeGraphStore"
Cohesion: 0.08
Nodes (9): _format_graph_context(), get_graph_context(), _parse_props(), _sanitize(), translate_to_lookups(), _acquire(), KnowledgeGraphStore, _sanitize() (+1 more)

### Community 30 - "TurnBubble.tsx"
Cohesion: 0.10
Nodes (34): @uiw/react-markdown-preview, approveEvent(), rejectEvent(), submitFeedback(), MessageStatus, CollapsibleSection(), CollapsibleSectionProps, MarkdownViewer() (+26 more)

### Community 31 - "observations_mgmt.py"
Cohesion: 0.07
Nodes (17): _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), render_pdf(), _sample_points(), _summarize() (+9 more)

### Community 32 - "time"
Cohesion: 0.08
Nodes (18): _alert_wrapper_retrigger(), _do_retrigger(), _get_jira_reporter(), handle_refresh_github_context(), handle_refresh_gitlab_context(), handle_refresh_kargo_context(), _is_darwin_reentrant_caller(), jenkins_retrigger_cooldown_key() (+10 more)

### Community 33 - "cli-executor.js"
Cohesion: 0.09
Nodes (36): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS, STORAGE_PRETASK_TIMEOUT_MS, resolveStorageRoot }, buildCLICommand(), { checkAndRecycleStorage, pinTaskCwd, unpinTaskCwd }, CLAUDE_JSON_PATH, cp, executeCLI(), executeCLIStreaming(), FALLBACK_MODEL (+28 more)

### Community 34 - "fetchApi"
Cohesion: 0.10
Nodes (34): closeEvent(), createChatEvent(), enforceCasualDomain(), fetchApi(), getActiveEvents(), getAlignerPending(), getEventDocument(), getEventReport() (+26 more)

### Community 35 - "main.py"
Cohesion: 0.06
Nodes (18): set_incident_options(), set_argocd_observer(), set_blackboard(), set_brain(), set_registry_and_bridge(), agent_ws_endpoint(), api_info(), get_config() (+10 more)

### Community 36 - "storage-recycler.js"
Cohesion: 0.08
Nodes (34): withTaskStorage(), resolveStorageRoot(), ROLE_TIMEOUTS, STORAGE_ACTIVITY_HEARTBEAT_MS, STORAGE_MAX_TIER3_DELETIONS, STORAGE_PRETASK_TIMEOUT_MS, STORAGE_RESULTS_TTL_MS, STORAGE_STALE_MS (+26 more)

### Community 37 - "SlackChannel"
Cohesion: 0.07
Nodes (4): extract_tables(), get_agent_notification_text(), get_turn_attachment_color(), SlackChannel

### Community 38 - "JenkinsAdapter"
Cohesion: 0.06
Nodes (6): BuildDetails, JenkinsAdapter, JenkinsPlatformPort, JobResult, JobRunState, ViewScanResult

### Community 40 - "lucide-react"
Cohesion: 0.10
Nodes (29): lucide-react, recharts, createSchedule(), deleteSchedule(), getSchedules(), refineInstructions(), ScheduleCreatePayload, ScheduleItem (+21 more)

### Community 42 - "formatter.py"
Cohesion: 0.08
Nodes (17): build_access_denied_home_view(), build_home_tab_view(), _context_line(), create_feedback_block(), _replace(), format_event_summary(), format_plan_block(), format_task_card() (+9 more)

### Community 43 - "ConversationTurn"
Cohesion: 0.15
Nodes (27): emit_tool_result(), handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_recall_pruned_turns(), handle_ask_release_ai(), handle_comment_jira_issue(), handle_fetch_jira_issue() (+19 more)

### Community 44 - "jira.py"
Cohesion: 0.09
Nodes (15): _adf_to_text(), approve_mission(), dismiss_mission(), _infer_phase(), _jira_config(), list_missions(), reanalyze_mission(), retry_mission() (+7 more)

### Community 45 - "live_api_adapter.py"
Cohesion: 0.08
Nodes (5): PulseBatch, PulsePort, PulseObserver, PulseTracker, redact_pii()

### Community 46 - "spawn_event_namer_task"
Cohesion: 0.12
Nodes (10): spawn_event_namer_task(), handle_app_home_opened(), handle_app_mention(), handle_approve(), handle_create_event_modal(), handle_darwin_command(), handle_home_create_event(), handle_reject() (+2 more)

### Community 47 - "GitHubPlatform"
Cohesion: 0.08
Nodes (3): GitHubPlatform, _poll_one(), _poll_one()

### Community 48 - "StreamGrid.tsx"
Cohesion: 0.11
Nodes (29): getFlowMetrics(), FlowMetrics, FlowHealthWidget(), queueColor(), wipColor(), GridTile(), GridTileProps, TileType (+21 more)

### Community 49 - "queue.py"
Cohesion: 0.09
Nodes (16): JenkinsPendingItem, PendingAnomaly, apply_lessons(), CloseRequest, correct_memory(), CorrectMemoryRequest, create_knowledge(), create_lesson() (+8 more)

### Community 50 - "ws-client.js"
Cohesion: 0.09
Nodes (26): is429Error(), {
  DEFAULT_WORK_DIR, AGENT_CLI, AGENT_MODEL, AGENT_ROLE,
  EVENT_ID, EPHEMERAL, IDLE_TIMEOUT_MS,
  CLI_429_MAX_RETRIES, CLI_429_INITIAL_DELAY_MS, CLI_429_BACKOFF_MULTIPLIER,
}, { ensureEventDocument }, { executeCLIStreaming, prepareResultsDir, is429Error }, { filterSkillsByRole, filterSkillsByMode, swapActiveRules, restoreAllSkills }, fs, handleCancel(), resetTimer() (+18 more)

### Community 51 - "ui/package.json"
Cohesion: 0.08
Nodes (29): autoprefixer, cronstrue, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, graphology-layout-forceatlas2 (+21 more)

### Community 52 - "lifespan"
Cohesion: 0.07
Nodes (5): set_oidc_adapter(), set_agents(), set_archivist(), set_kargo_observer(), lifespan()

### Community 53 - "._build_contents"
Cohesion: 0.07
Nodes (4): _close_unanswered_fc(), compute_dispatch_backpressure(), ContextFlags, _safe_int_env()

### Community 55 - "re"
Cohesion: 0.10
Nodes (8): generate_event_title(), get_adapter(), _get_semaphore(), ChatEventRequest, ChatEventResponse, create_chat_event(), sanitize_prompt_text(), sanitize_title()

### Community 57 - "NodeInspector.tsx"
Cohesion: 0.12
Nodes (26): getClosedEvents(), ArchitectureEvent, ArgoCDOperation, ArchitectureGraph(), ArchitectureGraphInner(), computeIdHash(), EVENT_LABELS, EventItem() (+18 more)

### Community 58 - "useCortexData.ts"
Cohesion: 0.17
Nodes (26): getCognitiveGraph(), getCortexActivity(), getKGServiceDetail(), getKGServices(), getKGStats(), getKnowledgeById(), getMemory(), getRecentPulses() (+18 more)

### Community 59 - "server.js"
Cohesion: 0.08
Nodes (18): hasRegistryCredentials(), { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, fs, path, stageEventDocument(), fetchEventDocument(), fs, { handleRequest } (+10 more)

### Community 60 - "dashboard_ws.py"
Cohesion: 0.12
Nodes (5): DashboardWSAdapter, can_append_message(), can_approve_event(), prompt_display_name(), resolve_approval_identity()

### Community 61 - "dependencies.py"
Cohesion: 0.09
Nodes (13): get_aligner(), get_architect(), get_argocd_observer(), get_developer(), get_kargo_observer(), get_kg_store(), get_report_client(), get_sysadmin() (+5 more)

### Community 62 - "journal.py"
Cohesion: 0.08
Nodes (4): get_all_journal(), get_service_journal(), get_event_observations(), get_global_observations()

### Community 63 - "slack.py"
Cohesion: 0.09
Nodes (4): table_block_to_code_block(), _PlanDecision, _mask_email(), SlackAccessGate

### Community 64 - "CortexGraph.tsx"
Cohesion: 0.14
Nodes (25): graphology, @sigma/node-square, eventColor(), getExecutiveNeurons(), getStructuralEdges(), DEFAULT_TYPE_BUDGET, evictLru(), KNOWLEDGE_RING (+17 more)

### Community 65 - "StateWatcher"
Cohesion: 0.10
Nodes (3): _QueueEntry, StateWatcher, _Subscription

### Community 67 - "IdleTimeoutManager"
Cohesion: 0.08
Nodes (3): BrainLifecyclePort, BroadcastPort, IdleTimeoutManager

### Community 68 - "context_parts.py"
Cohesion: 0.10
Nodes (11): _apply_sibling_signature(), build_function_response(), build_single_function_response(), compress_contents(), estimate_msg_tokens(), estimate_tokens(), extract_model_parts(), normalize_response_parts() (+3 more)

### Community 69 - "nightwatcher.py"
Cohesion: 0.10
Nodes (11): StagedEscalation, _env_int(), build_manifest_table(), build_report_iteration_prompt(), build_summary_prompt(), build_system_prompt(), extract_event_links(), extract_full_links() (+3 more)

### Community 70 - "nightwatcher_tools.py"
Cohesion: 0.15
Nodes (14): ShiftIncident, ShiftInvestigation, execute_tool(), _handle_consult_deep_memory(), _handle_declare_clusters(), _handle_dispatch_investigation(), _handle_extend_incident(), _handle_get_event_report() (+6 more)

### Community 71 - "state/__init__.py"
Cohesion: 0.11
Nodes (4): sanitize_redis_port(), close_redis(), get_redis(), RedisClient

### Community 72 - "tool_router.py"
Cohesion: 0.10
Nodes (6): _safe_int(), handle_consult_deep_memory(), IdleTimeoutPort, IncidentAdapterPort, StateWatcherPort, PulseContext

### Community 73 - "types.py"
Cohesion: 0.12
Nodes (7): derive_llm_priority(), LLMChunk, LLMPort, LLMResponse, _patch_enum_fields(), TokenUsage, _turn_field()

### Community 74 - "gemini_client.py"
Cohesion: 0.10
Nodes (11): _append_user_turn(), _coerce_part(), _extract_call_syntax(), _is_function_response_part(), _parse_drain_timeout(), _strip_user_thought_signature(), _validated_parts(), process_stream_call_syntax_buffer() (+3 more)

### Community 77 - "NeuronInfoPanel.tsx"
Cohesion: 0.11
Nodes (23): KGServiceDetail, AGENTS, DOMAINS, HEMISPHERE_X, NEURON_DESCRIPTIONS, PHASE_SKILL_FOLDERS, PHASE_TOOL_PRIORITY, PHASES (+15 more)

### Community 78 - "create_adapter"
Cohesion: 0.12
Nodes (5): create_adapter(), QuotaExhaustedError, QuotaTracker, RequestExceedsBurstError, Reservation

### Community 79 - "get_archivist"
Cohesion: 0.11
Nodes (11): get_archivist(), aligner_pending_items(), delete_knowledge(), delete_lesson(), get_knowledge(), get_lesson(), get_memory(), jenkins_pending_items() (+3 more)

### Community 80 - "NightwatcherObserver"
Cohesion: 0.14
Nodes (3): ShiftReport, _env_float(), NightwatcherObserver

### Community 82 - "GitHubAppAuth"
Cohesion: 0.11
Nodes (3): _find_pem_file(), get_github_auth(), GitHubAppAuth

### Community 83 - "dependencies"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 85 - "cortex/types.ts"
Cohesion: 0.15
Nodes (20): devQueryClient, CortexLiveFeedProps, EventDrillDownProps, MOCK_CORTEX_STATUS, MOCK_EVENT_ID, MOCK_NEURONS, MOCK_PULSE_BATCHES, MOCK_SHADOW (+12 more)

### Community 86 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 87 - "claude-guard.js"
Cohesion: 0.14
Nodes (18): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+10 more)

### Community 88 - "cli-setup.js"
Cohesion: 0.13
Nodes (19): { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync }, filterSkillsByMode() (+11 more)

### Community 91 - "reports.py"
Cohesion: 0.12
Nodes (6): get_report(), list_reports(), reports_spa_no_slash(), reports_spa_with_slash(), search_reports(), _serve_spa()

### Community 92 - "FloatingWindow.tsx"
Cohesion: 0.16
Nodes (17): AgentStreamCard(), AgentStreamCardProps, MessageCards(), CopyButton(), CopyButtonProps, DEFAULT_POS, DEFAULT_SIZE, EMPTY_MESSAGES (+9 more)

### Community 93 - "reconcile.py"
Cohesion: 0.19
Nodes (9): _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers(), main(), _parse_frontmatter() (+1 more)

### Community 94 - "EventEvidence"
Cohesion: 0.17
Nodes (11): _build_closed_block(), build_event_header(), _build_identity_block(), _build_journal_block(), _build_mermaid_block(), _build_related_block(), _build_subject_block(), _build_timing_block() (+3 more)

### Community 97 - "devDependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 98 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 99 - "ArchitectureGraph.tsx"
Cohesion: 0.15
Nodes (15): @dagrejs/dagre, @xyflow/react, applyDagreLayout(), applyGridLayout(), applyLayout(), buildGraph(), edgeTypes, LAYOUT_OPTIONS (+7 more)

### Community 103 - "gemini-sidecar/package.json"
Cohesion: 0.11
Nodes (17): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+9 more)

### Community 104 - "_sanitize_analysis_text"
Cohesion: 0.12
Nodes (9): _clamp_confidence(), _prepare_console_tail(), _redact_match(), _redact_secrets_in_text(), _sanitize_analysis_text(), _sanitize_console_tail(), _strip_newlines(), _validate_analysis() (+1 more)

### Community 106 - "ShiftsPage.tsx"
Cohesion: 0.23
Nodes (16): getCurrentShift(), getShiftDetail(), getShiftsList(), ShiftReportFull, ShiftReportSummary, FailedClusterBadge(), getISOWeek(), getWeekDates() (+8 more)

### Community 107 - "catalog-skills.js"
Cohesion: 0.16
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 109 - "state/ports.py"
Cohesion: 0.16
Nodes (3): ArchitectureEvent, EventType, MetricsRepository

### Community 111 - "TokenUtilizationPage.tsx"
Cohesion: 0.23
Nodes (13): getFlowHistory(), FlowSnapshot, FlowHistoryPage(), formatTime(), RANGES, SparkCard(), SparkCardProps, formatTime() (+5 more)

### Community 112 - "get_brain"
Cohesion: 0.17
Nodes (5): get_brain(), approve_event(), reject_event(), update_event_title(), update_plan_step()

### Community 115 - "list_active_events"
Cohesion: 0.12
Nodes (6): _defer_timeline_fields(), _has_active_subscription(), list_active_events(), list_closed_events(), list_waiting_approval_events(), _serialize_evidence()

### Community 116 - "generate_map.py"
Cohesion: 0.19
Nodes (6): _enumerate_gates(), _GateInfo, generate_phase_tool_map(), _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 117 - "handlers_planning.py"
Cohesion: 0.22
Nodes (7): _auto_complete_step(), _canonical_role(), handle_create_plan(), handle_get_plan_progress(), _is_failed_turn(), _is_orchestrator_turn(), _normalize_step_id()

### Community 121 - "ServiceNode.tsx"
Cohesion: 0.20
Nodes (11): HealthStatus, NodeType, AppNodeData, ARGOCD_HEALTH_COLORS, SYNC_ICONS, GENERIC_TAGS, HEALTH_COLORS, NODE_ICONS (+3 more)

### Community 126 - "analyzeTokens"
Cohesion: 0.19
Nodes (13): analyzeString(), analyzeTokens(), assignName(), base(), combineCategories(), configEnvGuard(), configFileWriteGuard(), hasSubseq() (+5 more)

### Community 127 - "EventDrillDown.tsx"
Cohesion: 0.22
Nodes (10): three, getEventPulses(), BrainCore(), CortexDevPage(), EventDrillDown(), FRICTION_COLORS, WHISPER_COLORS, PulseTimeline() (+2 more)

### Community 130 - "JarvisMemoryPage.tsx"
Cohesion: 0.27
Nodes (12): dismissProposals(), EnhancementProposal, getHandoffReports(), getProposals(), HandoffReport, FilterMode, formatDate(), formatTime() (+4 more)

### Community 133 - ".get_event"
Cohesion: 0.17
Nodes (4): get_event_approval(), get_event_document(), get_event_report(), get_event_turns()

### Community 134 - "CortexLiveFeed.tsx"
Cohesion: 0.24
Nodes (10): CortexHeartbeat(), CortexHeartbeatProps, ensureKeyframes(), CortexLiveFeed(), FILTER_PILLS, FilterKey, getStoredFilter(), MESSAGE_STYLES (+2 more)

### Community 135 - "testSetup.ts"
Cohesion: 0.18
Nodes (5): @tailwindcss/vite, @testing-library/react, vite, @vitejs/plugin-react, vitest

### Community 136 - "is_defer_event_available"
Cohesion: 0.18
Nodes (6): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 137 - "MessageStatus"
Cohesion: 0.22
Nodes (4): HealthStatus, MessageStatus, NodeType, infer_node_type()

### Community 138 - "._run_clustering_agent"
Cohesion: 0.24
Nodes (3): _fallback_platform(), reconcile_cluster_plan(), salvage_cluster_plan()

### Community 139 - "gitGuard"
Cohesion: 0.29
Nodes (10): bareBranchProtected(), configWriteGuard(), externalGitCommand(), gitGuard(), gitQuery(), isProtected(), normRef(), pushGuard() (+2 more)

### Community 140 - "parseShell"
Cohesion: 0.33
Nodes (10): bodySubstitutions(), decodeAnsiC(), isArrayAssignPrefix(), isWordStart(), matchBacktick(), matchParen(), parseShell(), readHeredocStart() (+2 more)

### Community 146 - "entity_extractor.py"
Cohesion: 0.33
Nodes (5): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship

### Community 153 - "PulseBatch"
Cohesion: 0.27
Nodes (9): ActiveEvent, EventSource, KGServiceEntity, CortexGraphProps, GraphLoaderProps, PulseTimelineProps, PulseBatch, WorkspaceTaskItemProps (+1 more)

### Community 154 - "classifyTool"
Cohesion: 0.31
Nodes (9): apiTokens(), apiWriteNeedsGuard(), branchValues(), classifyTool(), hasOpaqueTarget(), httpGuard(), httpMethod(), isReadMethod() (+1 more)

### Community 155 - "get_quota_tracker"
Cohesion: 0.22
Nodes (3): get_quota_tracker(), llm_stats(), receive_telemetry()

### Community 158 - "record_token_usage"
Cohesion: 0.25
Nodes (4): record_token_usage(), _append_user_turn(), _finalize_analysis_handover(), get_phase_tools()

### Community 167 - "enforce_casual_domain"
Cohesion: 0.25
Nodes (5): can_override_domain(), can_rename_event(), _normalize_email(), enforce_casual_domain(), EnforceCasualRequest

### Community 170 - "update_knowledge"
Cohesion: 0.25
Nodes (4): demote_lesson(), KnowledgeUpdateRequest, update_knowledge(), verify_lesson()

### Community 172 - "validate-mutations.sh"
Cohesion: 0.57
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

### Community 175 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 176 - "state.js"
Cohesion: 0.33
Nodes (4): { AGENT_ROLE }, _blackboardTurns, _inboundMessages, _teammateMessages

### Community 186 - "classify"
Cohesion: 0.50
Nodes (4): classify(), main(), shellCategory(), shellNeedsGuard()

### Community 196 - "overrides"
Cohesion: 0.67
Nodes (3): overrides, @typescript-eslint/typescript-estree, minimatch

## Knowledge Gaps
- **13 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+8 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2245 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **106 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `logging`, `BaseModel`, `.get_event`, `Brain`, `MessageStatus`, `cognitive_graph.py`, `HeadhunterJira`, `asyncio`, `_is_event_closed_or_missing`, `BrainSkillLoader`, `EventDocument`, `auth.py`, `brain.py`, `observations_mgmt.py`, `list_shifts`, `main.py`, `enforce_casual_domain`, `ConversationMessage`, `FlowSnapshot`, `ConversationTurn`, `jira.py`, `live_api_adapter.py`, `list_events`, `queue.py`, `lifespan`, `AppNode`, `close_event_by_user`, `re`, `dashboard_ws.py`, `dependencies.py`, `journal.py`, `slack.py`, `delete_notebook_note`, `nightwatcher.py`, `nightwatcher_tools.py`, `state/__init__.py`, `tool_router.py`, `get_archivist`, `NightwatcherObserver`, `reports.py`, `EventEvidence`, `ScheduleCreateRequest`, `LiveAPIAdapter`, `state/ports.py`, `get_brain`, `list_active_events`, `ScheduleRepository`?**
  _High betweenness centrality (0.128) - this node is a cross-community bridge._
- **Are the 80 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 80 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.015708812260536397 - nodes in this community are weakly interconnected._
- **Why does `Brain` connect `Brain` to `BlackboardState`, `ReconcileScheduler`, `._run_agent_task`, `MessageStatus`, `BrainSkillLoader`, `EventDocument`, `._post_agent_recall`, `agents/__init__.py`, `brain.py`, `main.py`, `._process_with_llm`, `ConversationTurn`, `live_api_adapter.py`, `lifespan`, `._build_contents`, `dashboard_ws.py`, `dependencies.py`, `slack.py`, `StateWatcher`, `._close_and_broadcast`, `IdleTimeoutManager`, `create_adapter`, `EventEvidence`, `ReflexSearcher`, `state/ports.py`?**
  _High betweenness centrality (0.079) - this node is a cross-community bridge._
- **Are the 21 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 21 INFERRED edges - model-reasoned connections that need verification._
- **Should `client.ts` be split into smaller, more focused modules?**
  _Cohesion score 0.030890123289527165 - nodes in this community are weakly interconnected._