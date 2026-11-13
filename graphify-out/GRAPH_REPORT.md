# Graph Report - Blackboard  (2026-11-13)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 5184 nodes · 11625 edges · 209 communities (108 shown, 101 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 950 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `c0ae8854`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BlackboardState
- logging
- models.py
- client.ts
- EventSidebar.tsx
- Brain
- WorkspaceInspector.tsx
- tool_gates.py
- App.tsx
- ReconcileScheduler
- http-handler.js
- EventEvidence
- Archivist
- brain.py
- dependencies.py
- ._run_agent_task
- hooks/index.ts
- useMemory.ts
- jenkins-mcp.js
- BrainSkillLoader
- EventDocument
- react
- EventHistory.tsx
- Aligner
- _BrainToolContext
- GitLabPlatform
- httpx
- merge-guard.js
- observations_mgmt.py
- ScheduleRepository
- create_adapter
- ToolContext
- nightwatcher_tools.py
- GeminiAdapter
- cli-executor.js
- storage-recycler.js
- EventRepository
- ._process_with_llm
- dispatch.py
- JenkinsAdapter
- GitHubPlatform
- gemini_client.py
- AgentClient
- StreamGrid.tsx
- KubernetesSpawnHealthAdapter
- ConversationTurn
- TimeKeeperPage.tsx
- formatter.py
- Headhunter
- get_archivist
- main.py
- ws-client.js
- VectorStore
- handlers_integration.py
- ClaudeAdapter
- queue.py
- cognitive_graph.py
- ui/package.json
- ._build_contents
- NightwatcherObserver
- CortexGraph.tsx
- KnowledgeGraphStore
- EventDrillDown.tsx
- server.js
- adf_to_markdown
- state/__init__.py
- AgentRegistry
- ArgoCDObserver
- EphemeralProvisioner
- ._get_manager
- KargoObserver
- TopologyRepository
- dependencies
- planState.ts
- StateWatcher
- LiveAPIAdapter
- PulseBatch
- .get_event
- GitHubAppAuth
- compilerOptions
- claude-guard.js
- UserContext
- useCortexData.ts
- reconcile.py
- ArchitectureGraph.tsx
- VcsPlatformPort
- cli-setup.js
- ReflexSearcher
- SlackChannel
- devDependencies
- compilerOptions
- gemini-sidecar/package.json
- get_brain
- TokenUtilizationPage.tsx
- handle_report_incident
- get_report
- _sanitize_analysis_text
- ObservationRepository
- catalog-skills.js
- DashboardWSAdapter
- EscalationRepository
- list_active_events
- generate_map.py
- OIDCKeyAdapter
- IdleTimeoutManager
- graph_recall.py
- JenkinsObserver
- QuotaTracker
- cortex/types.ts
- ServiceNode.tsx
- handlers_planning.py
- ._github_poll_and_process
- analyzeTokens
- BrainLifecyclePort
- handle_notify_user_slack
- TokenMeter
- ._send_turn_to_thread
- MultiInstallationManager
- NeuronInfoPanel.tsx
- SlackAccessGate
- CortexLiveFeed.tsx
- testSetup.ts
- is_defer_event_available
- cortex-constants.ts
- ._run_clustering_agent
- gitGuard
- parseShell
- ._post_agent_recall
- entity_extractor.py
- ._process_candidates
- ._triage_and_build_evidence
- ._drain_once
- has_unevaluated_close_blocker
- Any
- classifyTool
- get_quota_tracker
- SmartsheetMaintainerCache
- .has_reeval_signal
- ._register_handlers
- AsyncGitHubClient
- GitLabTokenAuth
- _is_event_closed_or_missing
- HeadhunterJira
- TimeKeeperObserver
- routes/kargo.py
- CortexRepository
- validate-mutations.sh
- ._detect_repetition_collapse
- record_token_usage
- scripts
- state.js
- ._process_message
- ._cleanup_stale_events
- _append_user_turn
- LLMPort
- submit_feedback
- classify
- headhunter_pending_todos
- TitleUpdateRequest
- require-results.sh
- _env_flag
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
1. `BlackboardState` - 285 edges
2. `Brain` - 156 edges
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

## Communities (209 total, 101 thin omitted)

### Community 0 - "BlackboardState"
Cohesion: 0.01
Nodes (12): get_all_journal(), get_service_journal(), delete_notebook_note(), get_notebook(), get_event_observations(), get_global_observations(), get_shift_detail(), list_shifts() (+4 more)

### Community 1 - "logging"
Cohesion: 0.03
Nodes (15): _annotation_replace(), _strip_pipeline_annotations(), _heartbeat(), _sanitize_lesson_text(), _get_static_maintainer_emails(), _safe_int(), _parse_job_metadata(), _stale_reservation_ttl_s() (+7 more)

### Community 2 - "models.py"
Cohesion: 0.03
Nodes (41): AppNode, ArchitectureEvent, ChatRequest, ChatResponse, ConversationMessage, EventInput, EventMetrics, EventStatus (+33 more)

### Community 3 - "client.ts"
Cohesion: 0.03
Nodes (109): ApiError, bulkDeleteObservations(), deleteObservation(), exportObservations(), ExtractionResult, fetchApi(), generateObservationsReport(), getActiveEvents() (+101 more)

### Community 4 - "EventSidebar.tsx"
Cohesion: 0.05
Nodes (99): getHeadhunterPending(), getJiraMissions(), HeadhunterTodo, postJiraAction(), CiContext, ChatInput(), CiContextCard(), CiContextCardProps (+91 more)

### Community 6 - "WorkspaceInspector.tsx"
Cohesion: 0.05
Nodes (73): lucide-react, getAgents(), getKargoStages(), updateEventTitle(), AgentRegistryEntry, EventEvidence, KargoStageStatus, TokenUsageDict (+65 more)

### Community 7 - "tool_gates.py"
Cohesion: 0.05
Nodes (78): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+70 more)

### Community 8 - "App.tsx"
Cohesion: 0.05
Nodes (58): oidc-client-ts, react-router-dom, dismissProposals(), EnhancementProposal, getConfig(), getHandoffReports(), getIncidents(), getProposals() (+50 more)

### Community 9 - "ReconcileScheduler"
Cohesion: 0.04
Nodes (7): FlowCollector, FairQueue, ReconcileScheduler, Trigger, QueueTrigger, ResyncTrigger, StalenessGuard

### Community 10 - "http-handler.js"
Cohesion: 0.08
Nodes (62): is429Error(), registerMCPsAndHooks(), resolveCommand(), writeAgyMcpServer(), writeClaudeMcpServer(), parsePositiveInt(), buildArgoCDMcpConfig(), createAppJWT() (+54 more)

### Community 11 - "EventEvidence"
Cohesion: 0.05
Nodes (19): spawn_event_namer_task(), can_append_message(), can_override_domain(), get_user_from_slack(), _normalize_email(), prompt_display_name(), resolve_approval_identity(), format_event_summary() (+11 more)

### Community 13 - "brain.py"
Cohesion: 0.04
Nodes (16): _close_unanswered_fc(), _safe_int(), _resolve_escalation_scope(), RequestExceedsBurstError, CIAnalysis, _resolve_domain(), resolve_event_domain(), _resolve_phase() (+8 more)

### Community 14 - "dependencies.py"
Cohesion: 0.04
Nodes (22): set_incident_options(), set_oidc_adapter(), get_aligner(), get_architect(), get_argocd_observer(), get_developer(), get_kargo_observer(), get_kg_store() (+14 more)

### Community 15 - "._run_agent_task"
Cohesion: 0.06
Nodes (10): on_huddle(), on_progress(), on_huddle(), on_progress(), _compute_processed_up_to(), _is_automated_nudge(), _sanitize_error_text(), _sanitize_override_reason() (+2 more)

### Community 16 - "hooks/index.ts"
Cohesion: 0.06
Nodes (48): @tanstack/react-query, createChatEvent(), getClosedEvents(), getEventDocument(), getEvents(), ArchitectureEvent, ArgoCDOperation, ActivityStream() (+40 more)

### Community 17 - "useMemory.ts"
Cohesion: 0.07
Nodes (54): applyLessons(), correctMemory(), createKnowledge(), createLesson(), deleteKnowledge(), deleteLesson(), deleteNote(), ExtractedCorrection (+46 more)

### Community 18 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 19 - "BrainSkillLoader"
Cohesion: 0.04
Nodes (5): _parse_positive_int_env(), BrainSkillLoader, _SkillCorpus, _wrap_section(), BrainIntrospectionPort

### Community 20 - "EventDocument"
Cohesion: 0.04
Nodes (10): _build_closed_block(), build_event_header(), _build_identity_block(), _build_journal_block(), _build_mermaid_block(), _build_related_block(), _build_subject_block(), _build_timing_block() (+2 more)

### Community 21 - "react"
Cohesion: 0.08
Nodes (43): react, @uiw/react-markdown-preview, approveEvent(), closeEvent(), enforceCasualDomain(), getEventReport(), rejectEvent(), submitFeedback() (+35 more)

### Community 22 - "EventHistory.tsx"
Cohesion: 0.07
Nodes (35): getReport(), getReports(), ReportMeta, SubjectType, CompactCardStrip(), EventHistory(), TimeRange, ViewMode (+27 more)

### Community 25 - "GitLabPlatform"
Cohesion: 0.07
Nodes (3): _get_allowed_mention_authors(), _get_static_maintainer_emails(), GitLabPlatform

### Community 26 - "httpx"
Cohesion: 0.07
Nodes (14): handle_approve(), dex_proxy(), approve_mission(), dismiss_mission(), _infer_phase(), _jira_config(), list_missions(), reanalyze_mission() (+6 more)

### Community 27 - "merge-guard.js"
Cohesion: 0.04
Nodes (46): API_VALUED, ARGO_MUTATING, ARGO_READ_SUB, ARGO_READ_TOP, BODY_FLAG, BROWSER_READ, CTX, ENV_BUILTINS (+38 more)

### Community 28 - "observations_mgmt.py"
Cohesion: 0.06
Nodes (18): get_report_client(), _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), render_pdf(), _sample_points() (+10 more)

### Community 29 - "ScheduleRepository"
Cohesion: 0.06
Nodes (6): ScheduleCreateRequest, ScheduledEvent, delete_schedule(), toggle_schedule(), update_schedule(), ScheduleRepository

### Community 30 - "create_adapter"
Cohesion: 0.07
Nodes (18): _apply_sibling_signature(), build_function_response(), build_single_function_response(), compress_contents(), estimate_msg_tokens(), estimate_tokens(), extract_model_parts(), _get_part_sig() (+10 more)

### Community 31 - "ToolContext"
Cohesion: 0.08
Nodes (11): handle_message_agent(), handle_reply_to_agent(), handle_select_agent(), _sticky_work_style(), handle_classify_event(), handle_defer_event(), handle_hold_watch(), handle_respond_to_jarvis() (+3 more)

### Community 32 - "nightwatcher_tools.py"
Cohesion: 0.09
Nodes (22): ShiftIncident, ShiftInvestigation, build_report_iteration_prompt(), build_summary_prompt(), extract_full_links(), _normalize_gitlab_host(), build_extend_tool(), build_report_tool() (+14 more)

### Community 33 - "GeminiAdapter"
Cohesion: 0.09
Nodes (9): _attach_signature_to_parts(), _clone_part_with_sig(), _coerce_part(), _decode_sig_bytes(), _extract_part_signature(), GeminiAdapter, _is_empty_sig_carrier(), _part_has_fc() (+1 more)

### Community 34 - "cli-executor.js"
Cohesion: 0.09
Nodes (37): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, MAX_TASK_WALL_MS, MAX_TIMER_MS, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS, STORAGE_PRETASK_TIMEOUT_MS, resolveStorageRoot }, buildCLICommand(), buildTimeoutResult(), { checkAndRecycleStorage, pinTaskCwd, unpinTaskCwd }, CLAUDE_JSON_PATH, cp, createInactivityWatchdog(), executeCLI() (+29 more)

### Community 35 - "storage-recycler.js"
Cohesion: 0.08
Nodes (37): withTaskStorage(), MAX_TASK_WALL_MS, parseTimerMs(), resolveStorageRoot(), resolveTimeoutMs(), ROLE_TIMEOUTS, STORAGE_ACTIVITY_HEARTBEAT_MS, STORAGE_MAX_TIER3_DELETIONS (+29 more)

### Community 38 - "dispatch.py"
Cohesion: 0.08
Nodes (13): _build_prompt(), _check_security(), consume_wake_task(), _consume(), _dispatch_timeout_s(), dispatch_to_agent(), _consume_queue(), _sanitize_stdout() (+5 more)

### Community 39 - "JenkinsAdapter"
Cohesion: 0.06
Nodes (6): BuildDetails, JenkinsAdapter, JenkinsPlatformPort, JobResult, JobRunState, ViewScanResult

### Community 41 - "gemini_client.py"
Cohesion: 0.10
Nodes (16): _extract_call_syntax(), derive_llm_priority(), _get_timeout_env_warned(), _get_timeout_order_warned(), LLMStreamInterChunkTimeoutError, LLMStreamTimeoutError, LLMStreamTotalTimeoutError, LLMStreamTTFBTimeoutError (+8 more)

### Community 42 - "AgentClient"
Cohesion: 0.07
Nodes (4): Architect, AgentClient, Developer, SysAdmin

### Community 43 - "StreamGrid.tsx"
Cohesion: 0.10
Nodes (31): getFlowMetrics(), FlowMetrics, Dashboard(), FlowHealthWidget(), queueColor(), wipColor(), GridTile(), GridTileProps (+23 more)

### Community 44 - "KubernetesSpawnHealthAdapter"
Cohesion: 0.07
Nodes (5): KubernetesSpawnHealthAdapter, _PodHealthState, DispatchMetrics, SpawnHealthPort, SpawnPollResult

### Community 45 - "ConversationTurn"
Cohesion: 0.16
Nodes (26): emit_tool_result(), handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_recall_pruned_turns(), handle_ask_release_ai(), handle_comment_jira_issue(), handle_greenwave() (+18 more)

### Community 46 - "TimeKeeperPage.tsx"
Cohesion: 0.11
Nodes (25): react-dom, createSchedule(), deleteSchedule(), getSchedules(), refineInstructions(), ScheduleCreatePayload, ScheduleItem, toggleSchedule() (+17 more)

### Community 47 - "formatter.py"
Cohesion: 0.09
Nodes (15): build_access_denied_home_view(), build_home_tab_view(), _context_line(), create_feedback_block(), format_plan_block(), format_task_card(), format_tool_result_blocks(), format_turn() (+7 more)

### Community 49 - "get_archivist"
Cohesion: 0.07
Nodes (16): get_archivist(), aligner_pending_items(), delete_knowledge(), delete_lesson(), demote_lesson(), get_event_turns(), get_knowledge(), get_lesson() (+8 more)

### Community 50 - "main.py"
Cohesion: 0.08
Nodes (14): agent_ws_endpoint(), api_info(), get_config(), get_event_flow(), delta(), get_flow_history(), get_flow_metrics(), health_check() (+6 more)

### Community 51 - "ws-client.js"
Cohesion: 0.10
Nodes (26): clearIdleTimer(), {
  DEFAULT_WORK_DIR, AGENT_CLI, AGENT_MODEL, AGENT_ROLE,
  EVENT_ID, EPHEMERAL, IDLE_TIMEOUT_MS,
  CLI_429_MAX_RETRIES, CLI_429_INITIAL_DELAY_MS, CLI_429_BACKOFF_MULTIPLIER,
  resolveTimeoutMs, parsePositiveInt, MAX_TASK_WALL_MS, MAX_TIMER_MS,
}, { ensureEventDocument }, { executeCLIStreaming, prepareResultsDir, is429Error }, { filterSkillsByRole, filterSkillsByMode, swapActiveRules, restoreAllSkills }, fs, handleCancel(), handleTask() (+18 more)

### Community 52 - "VectorStore"
Cohesion: 0.08
Nodes (3): _decode_cursor(), _encode_cursor(), VectorStore

### Community 53 - "handlers_integration.py"
Cohesion: 0.11
Nodes (14): _get_jira_reporter(), handle_fetch_jira_issue(), handle_refresh_github_context(), handle_refresh_gitlab_context(), handle_refresh_kargo_context(), _is_darwin_reentrant_caller(), jenkins_retrigger_cooldown_key(), format_jira_for_llm() (+6 more)

### Community 54 - "ClaudeAdapter"
Cohesion: 0.10
Nodes (5): ClaudeAdapter, FunctionCall, LLMChunk, LLMResponse, TokenUsage

### Community 55 - "queue.py"
Cohesion: 0.10
Nodes (16): apply_lessons(), CloseRequest, correct_memory(), CorrectMemoryRequest, create_knowledge(), create_lesson(), enforce_casual_domain(), EnforceCasualRequest (+8 more)

### Community 56 - "cognitive_graph.py"
Cohesion: 0.10
Nodes (12): get_blackboard(), get_pulse_tracker(), dismiss_proposals(), DismissRequest, get_all_shadow_interventions(), get_cognitive_graph(), get_cortex_activity(), get_cortex_status() (+4 more)

### Community 57 - "ui/package.json"
Cohesion: 0.08
Nodes (29): autoprefixer, cronstrue, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, graphology-layout-forceatlas2 (+21 more)

### Community 58 - "._build_contents"
Cohesion: 0.07
Nodes (3): compute_dispatch_backpressure(), ContextFlags, _safe_int_env()

### Community 59 - "NightwatcherObserver"
Cohesion: 0.10
Nodes (6): QuotaExhaustedError, ShiftReport, _env_float(), _env_int(), NightwatcherObserver, build_system_prompt()

### Community 60 - "CortexGraph.tsx"
Cohesion: 0.13
Nodes (26): graphology, sigma, eventColor(), getExecutiveNeurons(), getStructuralEdges(), DEFAULT_TYPE_BUDGET, evictLru(), KNOWLEDGE_RING (+18 more)

### Community 61 - "KnowledgeGraphStore"
Cohesion: 0.15
Nodes (4): _acquire(), KnowledgeGraphStore, _sanitize(), _with_timeout()

### Community 62 - "EventDrillDown.tsx"
Cohesion: 0.14
Nodes (22): getEventPulses(), BrainCore(), CortexDevPage(), devQueryClient, CortexLiveFeedProps, EventDrillDown(), EventDrillDownProps, FRICTION_COLORS (+14 more)

### Community 63 - "server.js"
Cohesion: 0.09
Nodes (18): { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, ensureEventDocument(), fs, path, stageEventDocument(), fetchEventDocument(), fs, { handleRequest } (+10 more)

### Community 64 - "adf_to_markdown"
Cohesion: 0.12
Nodes (10): _adf_to_text(), _escape_jql_string(), JiraIncidentAdapter, adf_to_markdown(), _apply_marks(), _children(), _render(), _render_list() (+2 more)

### Community 65 - "state/__init__.py"
Cohesion: 0.11
Nodes (4): sanitize_redis_port(), close_redis(), get_redis(), RedisClient

### Community 66 - "AgentRegistry"
Cohesion: 0.11
Nodes (3): AgentConnection, AgentRegistry, agent_websocket_handler()

### Community 72 - "dependencies"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 73 - "planState.ts"
Cohesion: 0.16
Nodes (20): ConversationTurn, PlanProgressProps, DeferCountdownState, useDeferCountdown(), EMPTY_CONVERSATION, computeDeferProgress(), DeferTimeline, formatDeferRemaining() (+12 more)

### Community 74 - "StateWatcher"
Cohesion: 0.11
Nodes (3): _QueueEntry, StateWatcher, _Subscription

### Community 76 - "PulseBatch"
Cohesion: 0.11
Nodes (4): PulseBatch, PulsePort, PulseObserver, PulseTracker

### Community 77 - ".get_event"
Cohesion: 0.10
Nodes (6): get_token_meter(), report_tampering(), close_event_by_user(), get_event_approval(), get_event_document(), get_event_report()

### Community 79 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 80 - "claude-guard.js"
Cohesion: 0.14
Nodes (18): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+10 more)

### Community 81 - "UserContext"
Cohesion: 0.12
Nodes (9): _claims_to_user(), get_user_from_request(), get_user_from_websocket(), require_auth(), require_obs_admin(), UserContext, _validate_jwt(), NotePatchRequest (+1 more)

### Community 82 - "useCortexData.ts"
Cohesion: 0.25
Nodes (19): getCortexActivity(), getRecentPulses(), CortexPage(), isOffRingCollection(), OffRingCollection, GraphView(), useWSMessage(), useCortexGraph() (+11 more)

### Community 83 - "reconcile.py"
Cohesion: 0.18
Nodes (9): _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers(), main(), _parse_frontmatter() (+1 more)

### Community 84 - "ArchitectureGraph.tsx"
Cohesion: 0.14
Nodes (17): @dagrejs/dagre, @xyflow/react, applyDagreLayout(), applyGridLayout(), applyLayout(), ArchitectureGraphInner(), buildGraph(), computeIdHash() (+9 more)

### Community 86 - "cli-setup.js"
Cohesion: 0.13
Nodes (18): { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync }, filterSkillsByMode() (+10 more)

### Community 89 - "devDependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 90 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 91 - "gemini-sidecar/package.json"
Cohesion: 0.11
Nodes (18): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+10 more)

### Community 92 - "get_brain"
Cohesion: 0.14
Nodes (7): can_approve_event(), can_rename_event(), get_brain(), approve_event(), reject_event(), update_event_title(), update_plan_step()

### Community 93 - "TokenUtilizationPage.tsx"
Cohesion: 0.18
Nodes (15): recharts, getFlowHistory(), FlowSnapshot, ObservationSeries, formatTime(), RANGES, SparkCard(), SparkCardProps (+7 more)

### Community 94 - "handle_report_incident"
Cohesion: 0.11
Nodes (5): handle_report_incident(), handle_search_open_incidents(), IdleTimeoutPort, IncidentAdapterPort, StateWatcherPort

### Community 95 - "get_report"
Cohesion: 0.11
Nodes (6): get_report(), list_reports(), reports_spa_no_slash(), reports_spa_with_slash(), search_reports(), _serve_spa()

### Community 97 - "_sanitize_analysis_text"
Cohesion: 0.12
Nodes (9): _clamp_confidence(), _prepare_console_tail(), _redact_match(), _redact_secrets_in_text(), _sanitize_analysis_text(), _sanitize_console_tail(), _strip_newlines(), _validate_analysis() (+1 more)

### Community 99 - "catalog-skills.js"
Cohesion: 0.16
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 103 - "list_active_events"
Cohesion: 0.12
Nodes (6): _defer_timeline_fields(), _has_active_subscription(), list_active_events(), list_closed_events(), list_waiting_approval_events(), _serialize_evidence()

### Community 104 - "generate_map.py"
Cohesion: 0.19
Nodes (6): _enumerate_gates(), _GateInfo, generate_phase_tool_map(), _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 107 - "graph_recall.py"
Cohesion: 0.19
Nodes (5): _format_graph_context(), get_graph_context(), _parse_props(), _sanitize(), translate_to_lookups()

### Community 110 - "cortex/types.ts"
Cohesion: 0.19
Nodes (13): EventSource, KGServiceEntity, CortexGraphProps, GraphLoaderProps, PulseTimelineProps, CognitiveGraphResponse, CortexHeartbeatMessage, FrictionIndicator (+5 more)

### Community 111 - "ServiceNode.tsx"
Cohesion: 0.20
Nodes (11): HealthStatus, NodeType, AppNodeData, ARGOCD_HEALTH_COLORS, SYNC_ICONS, GENERIC_TAGS, HEALTH_COLORS, NODE_ICONS (+3 more)

### Community 112 - "handlers_planning.py"
Cohesion: 0.23
Nodes (7): _auto_complete_step(), _canonical_role(), handle_create_plan(), handle_get_plan_progress(), _is_failed_turn(), _is_orchestrator_turn(), _normalize_step_id()

### Community 115 - "analyzeTokens"
Cohesion: 0.19
Nodes (13): analyzeString(), analyzeTokens(), assignName(), base(), combineCategories(), configEnvGuard(), configFileWriteGuard(), hasSubseq() (+5 more)

### Community 117 - "handle_notify_user_slack"
Cohesion: 0.15
Nodes (6): _alert_wrapper_retrigger(), _do_retrigger(), handle_notify_user_slack(), _resolve_maintainer_enum(), _resolve_slack_user(), build_event_report_md()

### Community 119 - "._send_turn_to_thread"
Cohesion: 0.19
Nodes (5): extract_tables(), _replace(), get_agent_notification_text(), get_turn_attachment_color(), _md_table_to_block_kit()

### Community 121 - "NeuronInfoPanel.tsx"
Cohesion: 0.24
Nodes (12): KGServiceDetail, asNumber(), asString(), asStringArray(), Badge(), describeNeuron(), Hdr(), NeuronInfoPanel() (+4 more)

### Community 126 - "CortexLiveFeed.tsx"
Cohesion: 0.24
Nodes (10): CortexHeartbeat(), CortexHeartbeatProps, ensureKeyframes(), CortexLiveFeed(), FILTER_PILLS, FilterKey, getStoredFilter(), MESSAGE_STYLES (+2 more)

### Community 127 - "testSetup.ts"
Cohesion: 0.18
Nodes (5): @tailwindcss/vite, @testing-library/react, vite, @vitejs/plugin-react, vitest

### Community 128 - "is_defer_event_available"
Cohesion: 0.18
Nodes (6): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 129 - "cortex-constants.ts"
Cohesion: 0.18
Nodes (10): AGENTS, DOMAINS, HEMISPHERE_X, NEURON_DESCRIPTIONS, PHASE_SKILL_FOLDERS, PHASE_TOOL_PRIORITY, PHASES, StructuralEdge (+2 more)

### Community 130 - "._run_clustering_agent"
Cohesion: 0.24
Nodes (3): _fallback_platform(), reconcile_cluster_plan(), salvage_cluster_plan()

### Community 131 - "gitGuard"
Cohesion: 0.29
Nodes (10): bareBranchProtected(), configWriteGuard(), externalGitCommand(), gitGuard(), gitQuery(), isProtected(), normRef(), pushGuard() (+2 more)

### Community 132 - "parseShell"
Cohesion: 0.33
Nodes (10): bodySubstitutions(), decodeAnsiC(), isArrayAssignPrefix(), isWordStart(), matchBacktick(), matchParen(), parseShell(), readHeredocStart() (+2 more)

### Community 136 - "entity_extractor.py"
Cohesion: 0.33
Nodes (5): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship

### Community 140 - "has_unevaluated_close_blocker"
Cohesion: 0.20
Nodes (4): has_unevaluated_close_blocker(), _pred_jarvis_response(), _pred_unevaluated_close(), is_jarvis_acknowledgment()

### Community 142 - "classifyTool"
Cohesion: 0.31
Nodes (9): apiTokens(), apiWriteNeedsGuard(), branchValues(), classifyTool(), hasOpaqueTarget(), httpGuard(), httpMethod(), isReadMethod() (+1 more)

### Community 143 - "get_quota_tracker"
Cohesion: 0.22
Nodes (3): get_quota_tracker(), llm_stats(), receive_telemetry()

### Community 156 - "validate-mutations.sh"
Cohesion: 0.57
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

### Community 159 - "record_token_usage"
Cohesion: 0.33
Nodes (3): record_token_usage(), _append_user_turn(), _finalize_analysis_handover()

### Community 160 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 161 - "state.js"
Cohesion: 0.33
Nodes (4): { AGENT_ROLE }, _blackboardTurns, _inboundMessages, _teammateMessages

### Community 171 - "_append_user_turn"
Cohesion: 0.33
Nodes (3): _append_user_turn(), _is_function_response_part(), _validated_parts()

### Community 174 - "classify"
Cohesion: 0.50
Nodes (4): classify(), main(), shellCategory(), shellNeedsGuard()

### Community 183 - "overrides"
Cohesion: 0.67
Nodes (3): overrides, @typescript-eslint/typescript-estree, minimatch

## Knowledge Gaps
- **13 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+8 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2272 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **101 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `logging`, `models.py`, `Brain`, `EventEvidence`, `brain.py`, `dependencies.py`, `BrainSkillLoader`, `EventDocument`, `_is_event_closed_or_missing`, `HeadhunterJira`, `httpx`, `observations_mgmt.py`, `ScheduleRepository`, `create_adapter`, `nightwatcher_tools.py`, `ConversationTurn`, `submit_feedback`, `get_archivist`, `main.py`, `queue.py`, `cognitive_graph.py`, `NightwatcherObserver`, `state/__init__.py`, `LiveAPIAdapter`, `.get_event`, `UserContext`, `get_brain`, `get_report`, `DashboardWSAdapter`, `list_active_events`?**
  _High betweenness centrality (0.125) - this node is a cross-community bridge._
- **Are the 80 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 80 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.011072725662148994 - nodes in this community are weakly interconnected._
- **Why does `Brain` connect `Brain` to `BlackboardState`, `logging`, `models.py`, `._resolve_llm_params`, `._post_agent_recall`, `ReconcileScheduler`, `EventEvidence`, `brain.py`, `dependencies.py`, `._run_agent_task`, `BrainSkillLoader`, `EventDocument`, `._detect_repetition_collapse`, `._cleanup_stale_events`, `._process_with_llm`, `dispatch.py`, `ConversationTurn`, `main.py`, `._build_contents`, `StateWatcher`, `PulseBatch`, `ReflexSearcher`, `DashboardWSAdapter`, `IdleTimeoutManager`, `BrainLifecyclePort`?**
  _High betweenness centrality (0.086) - this node is a cross-community bridge._
- **Are the 19 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 19 INFERRED edges - model-reasoned connections that need verification._
- **Should `logging` be split into smaller, more focused modules?**
  _Cohesion score 0.03165245782695447 - nodes in this community are weakly interconnected._