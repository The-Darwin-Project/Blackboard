# Graph Report - Blackboard  (2026-11-08)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 5113 nodes · 11421 edges · 225 communities (105 shown, 120 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 941 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `b5a7363d`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BlackboardState
- models.py
- logging
- nightwatcher_tools.py
- gemini_client.py
- client.ts
- EventDocument
- tool_gates.py
- Brain
- ._process_with_llm
- main.py
- EventChatPanel.tsx
- EventSidebar.tsx
- http-handler.js
- BrainSkillLoader
- colors.ts
- brain.py
- jenkins-mcp.js
- EventDrillDown.tsx
- App.tsx
- lucide-react
- fetchApi
- ReconcileScheduler
- TurnBubble.tsx
- formatter.py
- _BrainToolContext
- merge-guard.js
- ScheduleRepository
- ToolContext
- handlers_integration.py
- cli-executor.js
- WorkspaceInspector.tsx
- storage-recycler.js
- JenkinsAdapter
- EventRepository
- agents/__init__.py
- KnowledgeGraphStore
- GitHubPlatform
- GeminiAdapter
- ConversationTurn
- observations_mgmt.py
- ArchitectureGraph.tsx
- Aligner
- GitLabPlatform
- react
- TimeKeeperPage.tsx
- StreamGrid.tsx
- Headhunter
- state/ports.py
- ws-client.js
- dispatch.py
- queue.py
- get_archivist
- useCortexData.ts
- ui/package.json
- CortexGraph.tsx
- NodeInspector.tsx
- server.js
- StateWatcher
- SlackChannel
- handlers_state.py
- .get_event
- lifespan
- LiveAPIAdapter
- spawn_event_namer_task
- AgentRegistry
- TreePrimitives.tsx
- headhunter_jira.py
- ArgoCDObserver
- .start_event_loop
- ._get_manager
- KargoObserver
- TopologyRepository
- dependencies
- adf_to_markdown
- IdleTimeoutManager
- GitHubAppAuth
- compilerOptions
- claude-guard.js
- reconcile.py
- cli-setup.js
- DashboardWSAdapter
- VcsPlatformPort
- PulseBatch
- ReflexSearcher
- UserContext
- devDependencies
- compilerOptions
- get_brain
- TokenUtilizationPage.tsx
- EphemeralProvisioner
- get_report
- gemini-sidecar/package.json
- _sanitize_analysis_text
- JenkinsObserver
- ObservationRepository
- ShiftsPage.tsx
- catalog-skills.js
- SlackAccessGate
- Archivist
- EscalationRepository
- VectorStore
- list_active_events
- generate_map.py
- handlers_planning.py
- OIDCKeyAdapter
- KubernetesSpawnHealthAdapter
- .list_observations
- analyzeTokens
- FilterRule
- .scroll
- ._extract_context_flags
- BrainLifecyclePort
- TokenMeter
- MultiInstallationManager
- JarvisMemoryPage.tsx
- cortex-pulse-handler.ts
- tool_router.py
- HeadhunterJira
- CiContextCard.tsx
- testSetup.ts
- is_defer_event_available
- NeuronInfoPanel.tsx
- gitGuard
- parseShell
- generate_event_title
- ._post_agent_recall
- entity_extractor.py
- ._process_candidates
- ._triage_and_build_evidence
- ._drain_once
- has_unevaluated_close_blocker
- ._register_handlers
- knowledge_graph_api.py
- io
- SecurityError
- classifyTool
- SpawnPollResult
- SmartsheetMaintainerCache
- .has_reeval_signal
- create_chat_event
- AsyncGitHubClient
- GitLabTokenAuth
- ._authorize_plan_decision
- _is_event_closed_or_missing
- ._evaluate_health
- ConversationMessage
- TimeKeeperObserver
- CortexRepository
- validate-mutations.sh
- llm_stats
- update_notebook_note
- scripts
- state.js
- ._process_message
- DispatchMetrics
- SpawnStatus
- list_failed_stages
- dex_proxy
- _BatchContext
- ._wait_for_registration
- agent_ws_endpoint
- WorkspaceStarterChips.tsx
- classify
- headhunter_pending_todos
- TitleUpdateRequest
- rebuild_deep_memory
- require-results.sh
- _WSFrameFilter
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

## Communities (225 total, 120 thin omitted)

### Community 0 - "BlackboardState"
Cohesion: 0.01
Nodes (19): get_event_document(), get_all_journal(), get_service_journal(), delete_notebook_note(), get_notebook(), get_current_shift(), get_shift_detail(), list_shifts() (+11 more)

### Community 1 - "models.py"
Cohesion: 0.03
Nodes (45): get_aligner(), get_architect(), get_argocd_observer(), get_blackboard(), get_developer(), get_kargo_observer(), get_pulse_tracker(), get_sysadmin() (+37 more)

### Community 2 - "logging"
Cohesion: 0.04
Nodes (17): _annotation_replace(), _strip_pipeline_annotations(), _sanitize_lesson_text(), _get_static_maintainer_emails(), _get_allowed_mention_authors(), _get_static_maintainer_emails(), _safe_int(), _parse_job_metadata() (+9 more)

### Community 3 - "nightwatcher_tools.py"
Cohesion: 0.04
Nodes (36): JiraIncidentAdapter, record_token_usage(), ShiftIncident, ShiftInvestigation, ShiftReport, _append_user_turn(), _env_float(), _env_int() (+28 more)

### Community 4 - "gemini_client.py"
Cohesion: 0.04
Nodes (20): ClaudeAdapter, create_adapter(), get_quota_tracker(), QuotaExhaustedError, QuotaTracker, RequestExceedsBurstError, Reservation, derive_llm_priority() (+12 more)

### Community 5 - "client.ts"
Cohesion: 0.04
Nodes (70): @tanstack/react-query, ApiError, deleteNote(), ExtractedCorrection, ExtractedLesson, ExtractionResult, getFlowMetrics(), getGraphData() (+62 more)

### Community 6 - "EventDocument"
Cohesion: 0.03
Nodes (11): _close_unanswered_fc(), _build_closed_block(), build_event_header(), _build_identity_block(), _build_journal_block(), _build_mermaid_block(), _build_related_block(), _build_subject_block() (+3 more)

### Community 7 - "tool_gates.py"
Cohesion: 0.05
Nodes (78): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+70 more)

### Community 9 - "._process_with_llm"
Cohesion: 0.06
Nodes (9): on_huddle(), on_progress(), on_huddle(), on_progress(), _compute_processed_up_to(), _is_automated_nudge(), _sanitize_error_text(), _select_dispatch_tier() (+1 more)

### Community 10 - "main.py"
Cohesion: 0.04
Nodes (26): can_append_message(), can_rename_event(), get_user_from_slack(), _normalize_email(), set_oidc_adapter(), set_agents(), set_archivist(), set_argocd_observer() (+18 more)

### Community 11 - "EventChatPanel.tsx"
Cohesion: 0.07
Nodes (46): react-router-dom, KargoStageStatus, TokenUsageDict, ActivityStream(), ChatInput(), ChatInputProps, Draft, LastSubmission (+38 more)

### Community 12 - "EventSidebar.tsx"
Cohesion: 0.08
Nodes (58): HeadhunterTodo, ACTION_BADGE, formatAge(), HeadhunterQueuePanel(), renderItem(), IN_PROGRESS_ACTIONS, isInProgressTodo(), isQueuedTodo() (+50 more)

### Community 13 - "http-handler.js"
Cohesion: 0.09
Nodes (58): resolveCommand(), writeAgyMcpServer(), writeClaudeMcpServer(), buildArgoCDMcpConfig(), createAppJWT(), discoverAndGenerateTokens(), _discoverAndGenerateTokensInner(), discoverInstallations() (+50 more)

### Community 14 - "BrainSkillLoader"
Cohesion: 0.04
Nodes (4): BrainSkillLoader, _SkillCorpus, _wrap_section(), BrainIntrospectionPort

### Community 15 - "colors.ts"
Cohesion: 0.07
Nodes (39): getReport(), getReports(), ReportFull, ReportMeta, SubjectType, CompactCardStrip(), EventHistory(), TimeRange (+31 more)

### Community 16 - "brain.py"
Cohesion: 0.05
Nodes (17): _apply_sibling_signature(), build_function_response(), build_single_function_response(), compress_contents(), estimate_msg_tokens(), estimate_tokens(), extract_model_parts(), normalize_response_parts() (+9 more)

### Community 17 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 18 - "EventDrillDown.tsx"
Cohesion: 0.07
Nodes (49): three, getEventPulses(), ActiveEvent, EventSource, KGServiceDetail, KGServiceEntity, BrainCore(), CortexDevPage() (+41 more)

### Community 19 - "App.tsx"
Cohesion: 0.06
Nodes (43): oidc-client-ts, react-dom, getConfig(), getIncidents(), getWSAuthFailureCallback(), Incident, setOnUnauthorized(), setTokenGetter() (+35 more)

### Community 20 - "lucide-react"
Cohesion: 0.08
Nodes (47): lucide-react, correctMemory(), createKnowledge(), createLesson(), deleteKnowledge(), deleteLesson(), getLessonById(), scrollKnowledge() (+39 more)

### Community 21 - "fetchApi"
Cohesion: 0.07
Nodes (44): applyLessons(), bulkDeleteObservations(), closeEvent(), createChatEvent(), deleteObservation(), enforceCasualDomain(), exportObservations(), extractLessons() (+36 more)

### Community 22 - "ReconcileScheduler"
Cohesion: 0.05
Nodes (6): FairQueue, ReconcileScheduler, Trigger, QueueTrigger, ResyncTrigger, StalenessGuard

### Community 23 - "TurnBubble.tsx"
Cohesion: 0.09
Nodes (38): @uiw/react-markdown-preview, approveEvent(), rejectEvent(), submitFeedback(), CollapsibleSection(), CollapsibleSectionProps, ConversationFeed(), ConversationFeedProps (+30 more)

### Community 24 - "formatter.py"
Cohesion: 0.06
Nodes (20): build_access_denied_home_view(), build_home_tab_view(), _context_line(), create_feedback_block(), extract_tables(), _replace(), format_plan_block(), format_task_card() (+12 more)

### Community 26 - "merge-guard.js"
Cohesion: 0.04
Nodes (46): API_VALUED, ARGO_MUTATING, ARGO_READ_SUB, ARGO_READ_TOP, BODY_FLAG, BROWSER_READ, CTX, ENV_BUILTINS (+38 more)

### Community 27 - "ScheduleRepository"
Cohesion: 0.06
Nodes (6): ScheduleCreateRequest, ScheduledEvent, delete_schedule(), toggle_schedule(), update_schedule(), ScheduleRepository

### Community 28 - "ToolContext"
Cohesion: 0.08
Nodes (12): handle_message_agent(), handle_reply_to_agent(), handle_report_incident(), handle_select_agent(), _resolve_escalation_scope(), _sticky_work_style(), handle_search_open_incidents(), handle_defer_event() (+4 more)

### Community 29 - "handlers_integration.py"
Cohesion: 0.07
Nodes (20): _alert_wrapper_retrigger(), _do_retrigger(), _get_jira_reporter(), handle_comment_jira_issue(), handle_notify_user_slack(), handle_refresh_github_context(), handle_refresh_gitlab_context(), handle_refresh_kargo_context() (+12 more)

### Community 30 - "cli-executor.js"
Cohesion: 0.09
Nodes (36): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS, STORAGE_PRETASK_TIMEOUT_MS, resolveStorageRoot }, buildCLICommand(), { checkAndRecycleStorage, pinTaskCwd, unpinTaskCwd }, CLAUDE_JSON_PATH, cp, executeCLI(), executeCLIStreaming(), FALLBACK_MODEL (+28 more)

### Community 31 - "WorkspaceInspector.tsx"
Cohesion: 0.09
Nodes (36): AgentRegistryEntry, ConversationTurn, AgentGroups, BORDER_COLOR, PlanProgress(), PlanProgressProps, STATUS_ICON, DiffFile (+28 more)

### Community 32 - "storage-recycler.js"
Cohesion: 0.08
Nodes (34): withTaskStorage(), resolveStorageRoot(), ROLE_TIMEOUTS, STORAGE_ACTIVITY_HEARTBEAT_MS, STORAGE_MAX_TIER3_DELETIONS, STORAGE_PRETASK_TIMEOUT_MS, STORAGE_RESULTS_TTL_MS, STORAGE_STALE_MS (+26 more)

### Community 33 - "JenkinsAdapter"
Cohesion: 0.06
Nodes (6): BuildDetails, JenkinsAdapter, JenkinsPlatformPort, JobResult, JobRunState, ViewScanResult

### Community 35 - "agents/__init__.py"
Cohesion: 0.07
Nodes (4): Architect, AgentClient, Developer, SysAdmin

### Community 36 - "KnowledgeGraphStore"
Cohesion: 0.09
Nodes (9): _format_graph_context(), get_graph_context(), _parse_props(), _sanitize(), translate_to_lookups(), _acquire(), KnowledgeGraphStore, _sanitize() (+1 more)

### Community 38 - "GeminiAdapter"
Cohesion: 0.08
Nodes (8): _append_user_turn(), _coerce_part(), _extract_call_syntax(), GeminiAdapter, _is_function_response_part(), _parse_drain_timeout(), _strip_user_thought_signature(), _validated_parts()

### Community 39 - "ConversationTurn"
Cohesion: 0.15
Nodes (24): emit_tool_result(), handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_recall_pruned_turns(), handle_ask_release_ai(), handle_fetch_jira_issue(), handle_greenwave() (+16 more)

### Community 40 - "observations_mgmt.py"
Cohesion: 0.08
Nodes (16): get_report_client(), _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), render_pdf(), _sample_points() (+8 more)

### Community 41 - "ArchitectureGraph.tsx"
Cohesion: 0.09
Nodes (28): @dagrejs/dagre, @xyflow/react, HealthStatus, NodeType, AppNodeData, applyDagreLayout(), applyGridLayout(), applyLayout() (+20 more)

### Community 44 - "react"
Cohesion: 0.10
Nodes (27): react, updateEventTitle(), AgentRegistryPanel(), formatConnectedSince(), AgentStreamCard(), AgentStreamCardProps, MessageCards(), CopyButton() (+19 more)

### Community 45 - "TimeKeeperPage.tsx"
Cohesion: 0.12
Nodes (24): createSchedule(), deleteSchedule(), getSchedules(), refineInstructions(), ScheduleCreatePayload, ScheduleItem, toggleSchedule(), updateSchedule() (+16 more)

### Community 46 - "StreamGrid.tsx"
Cohesion: 0.12
Nodes (28): Dashboard(), FlowHealthWidget(), queueColor(), wipColor(), GridTile(), GridTileProps, TileType, InlineMarkdownViewer() (+20 more)

### Community 47 - "Headhunter"
Cohesion: 0.08
Nodes (3): Headhunter, _raise_if_systemic_failure(), _sanitize_xml_fence()

### Community 48 - "state/ports.py"
Cohesion: 0.09
Nodes (7): ArchitectureEvent, EventType, HealthStatus, MessageStatus, NodeType, list_events(), MetricsRepository

### Community 49 - "ws-client.js"
Cohesion: 0.09
Nodes (26): is429Error(), {
  DEFAULT_WORK_DIR, AGENT_CLI, AGENT_MODEL, AGENT_ROLE,
  EVENT_ID, EPHEMERAL, IDLE_TIMEOUT_MS,
  CLI_429_MAX_RETRIES, CLI_429_INITIAL_DELAY_MS, CLI_429_BACKOFF_MULTIPLIER,
}, { ensureEventDocument }, { executeCLIStreaming, prepareResultsDir, is429Error }, { filterSkillsByRole, filterSkillsByMode, swapActiveRules, restoreAllSkills }, fs, handleCancel(), resetTimer() (+18 more)

### Community 50 - "dispatch.py"
Cohesion: 0.10
Nodes (10): _build_prompt(), _check_security(), consume_wake_task(), _consume(), _dispatch_timeout_s(), dispatch_to_agent(), _consume_queue(), _sanitize_stdout() (+2 more)

### Community 51 - "queue.py"
Cohesion: 0.11
Nodes (17): can_override_domain(), apply_lessons(), correct_memory(), CorrectMemoryRequest, create_knowledge(), create_lesson(), enforce_casual_domain(), EnforceCasualRequest (+9 more)

### Community 52 - "get_archivist"
Cohesion: 0.08
Nodes (14): get_archivist(), aligner_pending_items(), delete_knowledge(), delete_lesson(), demote_lesson(), get_event_document(), get_knowledge(), get_lesson() (+6 more)

### Community 53 - "useCortexData.ts"
Cohesion: 0.16
Nodes (28): getCognitiveGraph(), getCortexActivity(), getEventReport(), getKGServiceDetail(), getKGServices(), getKGStats(), getKnowledgeById(), getMemory() (+20 more)

### Community 54 - "ui/package.json"
Cohesion: 0.08
Nodes (28): autoprefixer, cronstrue, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, graphology-layout-forceatlas2 (+20 more)

### Community 55 - "CortexGraph.tsx"
Cohesion: 0.10
Nodes (28): @react-sigma/core, @react-sigma/layout-forceatlas2, sigma, @sigma/node-square, AGENTS, DOMAINS, eventColor(), getExecutiveNeurons() (+20 more)

### Community 56 - "NodeInspector.tsx"
Cohesion: 0.12
Nodes (25): getClosedEvents(), getEvents(), ArchitectureEvent, ArgoCDOperation, ArchitectureGraph(), EVENT_LABELS, EventItem(), EventItemProps (+17 more)

### Community 57 - "server.js"
Cohesion: 0.08
Nodes (18): hasRegistryCredentials(), { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, fs, path, stageEventDocument(), fetchEventDocument(), fs, { handleRequest } (+10 more)

### Community 58 - "StateWatcher"
Cohesion: 0.09
Nodes (3): _QueueEntry, StateWatcher, _Subscription

### Community 60 - "handlers_state.py"
Cohesion: 0.08
Nodes (7): handle_classify_event(), handle_hold_watch(), handle_request_user_approval(), IdleTimeoutPort, IncidentAdapterPort, _resolve_domain(), resolve_event_domain()

### Community 61 - ".get_event"
Cohesion: 0.07
Nodes (8): report_tampering(), FeedbackRequest, submit_feedback(), close_event_by_user(), CloseRequest, get_event_approval(), get_event_report(), get_event_turns()

### Community 64 - "spawn_event_namer_task"
Cohesion: 0.15
Nodes (8): spawn_event_namer_task(), format_event_summary(), handle_app_home_opened(), handle_app_mention(), handle_create_event_modal(), handle_darwin_command(), on_dm_message(), fallback_title()

### Community 65 - "AgentRegistry"
Cohesion: 0.10
Nodes (4): AgentConnection, AgentRegistry, agent_websocket_handler(), _heartbeat()

### Community 66 - "TreePrimitives.tsx"
Cohesion: 0.16
Nodes (19): DeferCountdownBar(), STATUS_COLORS, TICKET_COLORS, TicketNodeComponent(), TicketNodeData, EventNode(), relativeAge(), WorkspaceTaskItem() (+11 more)

### Community 67 - "headhunter_jira.py"
Cohesion: 0.12
Nodes (7): approve_mission(), dismiss_mission(), _infer_phase(), _jira_config(), list_missions(), reanalyze_mission(), retry_mission()

### Community 69 - ".start_event_loop"
Cohesion: 0.10
Nodes (4): _has_non_user_turns(), _is_seed_turn(), get_token_meter(), FlowCollector

### Community 73 - "dependencies"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 74 - "adf_to_markdown"
Cohesion: 0.13
Nodes (9): _adf_to_text(), _escape_jql_string(), adf_to_markdown(), _apply_marks(), _children(), _render(), _render_list(), _render_list_item() (+1 more)

### Community 78 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 79 - "claude-guard.js"
Cohesion: 0.14
Nodes (18): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+10 more)

### Community 80 - "reconcile.py"
Cohesion: 0.18
Nodes (9): _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers(), main(), _parse_frontmatter() (+1 more)

### Community 81 - "cli-setup.js"
Cohesion: 0.13
Nodes (19): { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync }, filterSkillsByMode() (+11 more)

### Community 82 - "DashboardWSAdapter"
Cohesion: 0.17
Nodes (3): DashboardWSAdapter, prompt_display_name(), resolve_approval_identity()

### Community 85 - "PulseBatch"
Cohesion: 0.12
Nodes (4): PulseBatch, PulsePort, PulseObserver, PulseTracker

### Community 88 - "UserContext"
Cohesion: 0.13
Nodes (9): _claims_to_user(), get_user_from_request(), get_user_from_websocket(), require_auth(), require_obs_admin(), UserContext, _validate_jwt(), dismiss_proposals() (+1 more)

### Community 89 - "devDependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 90 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 91 - "get_brain"
Cohesion: 0.15
Nodes (6): can_approve_event(), get_brain(), approve_event(), reject_event(), update_event_title(), update_plan_step()

### Community 92 - "TokenUtilizationPage.tsx"
Cohesion: 0.18
Nodes (15): recharts, getFlowHistory(), FlowSnapshot, ObservationSeries, formatTime(), RANGES, SparkCard(), SparkCardProps (+7 more)

### Community 95 - "get_report"
Cohesion: 0.11
Nodes (6): get_report(), list_reports(), reports_spa_no_slash(), reports_spa_with_slash(), search_reports(), _serve_spa()

### Community 96 - "gemini-sidecar/package.json"
Cohesion: 0.11
Nodes (17): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+9 more)

### Community 98 - "_sanitize_analysis_text"
Cohesion: 0.12
Nodes (9): _clamp_confidence(), _prepare_console_tail(), _redact_match(), _redact_secrets_in_text(), _sanitize_analysis_text(), _sanitize_console_tail(), _strip_newlines(), _validate_analysis() (+1 more)

### Community 101 - "ShiftsPage.tsx"
Cohesion: 0.23
Nodes (16): getCurrentShift(), getShiftDetail(), getShiftsList(), ShiftReportFull, ShiftReportSummary, FailedClusterBadge(), getISOWeek(), getWeekDates() (+8 more)

### Community 102 - "catalog-skills.js"
Cohesion: 0.16
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 107 - "list_active_events"
Cohesion: 0.12
Nodes (6): _defer_timeline_fields(), _has_active_subscription(), list_active_events(), list_closed_events(), list_waiting_approval_events(), _serialize_evidence()

### Community 108 - "generate_map.py"
Cohesion: 0.19
Nodes (6): _enumerate_gates(), _GateInfo, generate_phase_tool_map(), _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 109 - "handlers_planning.py"
Cohesion: 0.22
Nodes (7): _auto_complete_step(), _canonical_role(), handle_create_plan(), handle_get_plan_progress(), _is_failed_turn(), _is_orchestrator_turn(), _normalize_step_id()

### Community 116 - "analyzeTokens"
Cohesion: 0.19
Nodes (13): analyzeString(), analyzeTokens(), assignName(), base(), combineCategories(), configEnvGuard(), configFileWriteGuard(), hasSubseq() (+5 more)

### Community 119 - "._extract_context_flags"
Cohesion: 0.15
Nodes (3): compute_dispatch_backpressure(), ContextFlags, _safe_int_env()

### Community 123 - "JarvisMemoryPage.tsx"
Cohesion: 0.27
Nodes (12): dismissProposals(), EnhancementProposal, getHandoffReports(), getProposals(), HandoffReport, FilterMode, formatDate(), formatTime() (+4 more)

### Community 124 - "cortex-pulse-handler.ts"
Cohesion: 0.21
Nodes (11): graphology, DEFAULT_TYPE_BUDGET, evictLru(), KNOWLEDGE_RING, KNOWLEDGE_RING_TYPES, KnowledgeNodeAttributes, knowledgeRingColor(), knowledgeRingLabel() (+3 more)

### Community 127 - "tool_router.py"
Cohesion: 0.23
Nodes (4): _safe_int(), handle_consult_deep_memory(), handle_google_web_search(), PulseContext

### Community 129 - "CiContextCard.tsx"
Cohesion: 0.29
Nodes (10): CiContext, CiContextCard(), CiContextCardProps, ConsoleTailBlock(), FailedJobRow(), annotationReplacer(), PIPELINE_ANNOTATION_RE, REDACTION_TRIGGER_KEYWORDS (+2 more)

### Community 130 - "testSetup.ts"
Cohesion: 0.18
Nodes (5): @tailwindcss/vite, @testing-library/react, vite, @vitejs/plugin-react, vitest

### Community 131 - "is_defer_event_available"
Cohesion: 0.18
Nodes (6): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 132 - "NeuronInfoPanel.tsx"
Cohesion: 0.29
Nodes (10): asNumber(), asString(), asStringArray(), Badge(), describeNeuron(), Hdr(), NeuronInfoPanel(), AGENT_NEURON_COLORS (+2 more)

### Community 133 - "gitGuard"
Cohesion: 0.29
Nodes (10): bareBranchProtected(), configWriteGuard(), externalGitCommand(), gitGuard(), gitQuery(), isProtected(), normRef(), pushGuard() (+2 more)

### Community 134 - "parseShell"
Cohesion: 0.33
Nodes (10): bodySubstitutions(), decodeAnsiC(), isArrayAssignPrefix(), isWordStart(), matchBacktick(), matchParen(), parseShell(), readHeredocStart() (+2 more)

### Community 135 - "generate_event_title"
Cohesion: 0.22
Nodes (3): generate_event_title(), get_adapter(), _get_semaphore()

### Community 139 - "entity_extractor.py"
Cohesion: 0.33
Nodes (5): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship

### Community 143 - "has_unevaluated_close_blocker"
Cohesion: 0.20
Nodes (4): has_unevaluated_close_blocker(), _pred_jarvis_response(), _pred_unevaluated_close(), is_jarvis_acknowledgment()

### Community 144 - "._register_handlers"
Cohesion: 0.22
Nodes (3): handle_approve(), handle_home_create_event(), handle_reject()

### Community 145 - "knowledge_graph_api.py"
Cohesion: 0.31
Nodes (4): get_kg_store(), get_service_detail(), get_stats(), list_services()

### Community 147 - "SecurityError"
Cohesion: 0.28
Nodes (3): safe_execution(), wrapper(), SecurityError

### Community 148 - "classifyTool"
Cohesion: 0.31
Nodes (9): apiTokens(), apiWriteNeedsGuard(), branchValues(), classifyTool(), hasOpaqueTarget(), httpGuard(), httpMethod(), isReadMethod() (+1 more)

### Community 152 - "create_chat_event"
Cohesion: 0.25
Nodes (3): ChatEventRequest, ChatEventResponse, create_chat_event()

### Community 162 - "validate-mutations.sh"
Cohesion: 0.57
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

### Community 166 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 167 - "state.js"
Cohesion: 0.33
Nodes (4): { AGENT_ROLE }, _blackboardTurns, _inboundMessages, _teammateMessages

### Community 188 - "WorkspaceStarterChips.tsx"
Cohesion: 0.50
Nodes (3): STARTER_CHIPS, StarterChip, WorkspaceStarterChipsProps

### Community 189 - "classify"
Cohesion: 0.50
Nodes (4): classify(), main(), shellCategory(), shellNeedsGuard()

## Knowledge Gaps
- **13 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+8 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2246 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **120 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `HeadhunterJira`, `models.py`, `logging`, `nightwatcher_tools.py`, `EventDocument`, `generate_event_title`, `Brain`, `main.py`, `BrainSkillLoader`, `brain.py`, `io`, `create_chat_event`, `ScheduleRepository`, `_is_event_closed_or_missing`, `ConversationMessage`, `update_notebook_note`, `ConversationTurn`, `observations_mgmt.py`, `state/ports.py`, `queue.py`, `get_archivist`, `._restage_pending_signal`, `._stage_pending_signal`, `._count_pending`, `.get_event`, `lifespan`, `LiveAPIAdapter`, `headhunter_jira.py`, `rebuild_deep_memory`, `DashboardWSAdapter`, `get_brain`, `get_report`, `list_active_events`, `.list_observations`, `tool_router.py`?**
  _High betweenness centrality (0.126) - this node is a cross-community bridge._
- **Are the 80 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 80 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.010911074740861976 - nodes in this community are weakly interconnected._
- **Why does `EventEvidence` connect `logging` to `HeadhunterJira`, `models.py`, `BlackboardState`, `EventDocument`, `Brain`, `._triage_and_build_evidence`, `brain.py`, `create_chat_event`, `ScheduleRepository`, `_is_event_closed_or_missing`, `TimeKeeperObserver`, `EventRepository`, `GitHubPlatform`, `Aligner`, `GitLabPlatform`, `state/ports.py`, `queue.py`, `SlackChannel`, `LiveAPIAdapter`, `spawn_event_namer_task`, `headhunter_jira.py`, `DashboardWSAdapter`, `.create_platform_event`, `JenkinsObserver`, `Archivist`, `list_active_events`, `.poll_and_process`?**
  _High betweenness centrality (0.053) - this node is a cross-community bridge._
- **Are the 21 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 21 INFERRED edges - model-reasoned connections that need verification._
- **Should `models.py` be split into smaller, more focused modules?**
  _Cohesion score 0.027716068972812865 - nodes in this community are weakly interconnected._