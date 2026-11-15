# Graph Report - Blackboard  (2026-11-15)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 5244 nodes · 11797 edges · 210 communities (100 shown, 110 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 953 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `bb6765cd`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BlackboardState
- logging
- models.py
- ConversationTurn
- queue.py
- client.ts
- nightwatcher_tools.py
- auth.py
- main.py
- Brain
- EventSidebar.tsx
- brain.py
- os
- tool_gates.py
- Archivist
- App.tsx
- ._run_agent_task
- http-handler.js
- EventHistory.tsx
- WorkspaceInspector.tsx
- api/types.ts
- jenkins-mcp.js
- useActiveEvents
- TurnBubble.tsx
- Aligner
- ._process_with_llm
- _BrainToolContext
- merge-guard.js
- EventDocument
- cli-executor.js
- storage-recycler.js
- BrainSkillLoader
- ObservationRepository
- OpsStateContext.tsx
- JenkinsAdapter
- EventRepository
- GitHubPlatform
- ScheduleRepository
- SlackChannel
- CortexGraph.tsx
- formatter.py
- GeminiAdapter
- GitLabPlatform
- EventEvidence
- Headhunter
- TimeKeeperPage.tsx
- ws-client.js
- DashboardWSAdapter
- AgentClient
- jenkins_observer.py
- ClaudeAdapter
- ui/package.json
- spawn_event_namer_task
- useCortexData.ts
- .list_observations
- types.py
- NodeInspector.tsx
- ._build_system_prompt
- KnowledgeGraphStore
- LiveAPIAdapter
- jira.py
- server.js
- VectorStore
- ArgoCDObserver
- reconcile.py
- slack.py
- ._get_manager
- KargoObserver
- TopologyRepository
- dependencies
- cortex/types.ts
- ._build_contents
- compilerOptions
- claude-guard.js
- FlowHistoryPage.tsx
- EventDrillDown.tsx
- GitHubAppAuth
- VcsPlatformPort
- PulseBatch
- cli-setup.js
- StateWatcher
- ReflexSearcher
- FairQueue
- devDependencies
- FloatingWindow.tsx
- compilerOptions
- gemini-sidecar/package.json
- ServiceNode.tsx
- EphemeralProvisioner
- get_report
- ArchitectureGraph.tsx
- JenkinsObserver
- gemini_client.py
- QuotaTracker
- TokenMeter
- ShiftsPage.tsx
- catalog-skills.js
- SlackAccessGate
- .__init__
- generate_map.py
- OIDCKeyAdapter
- KubernetesSpawnHealthAdapter
- IdleTimeoutManager
- ReconcileScheduler
- observations_reporter.py
- .start_event_loop
- MultiInstallationManager
- analyzeTokens
- BrainLifecyclePort
- IncidentAdapterPort
- ScheduleCreateRequest
- testSetup.ts
- is_defer_event_available
- NeuronInfoPanel.tsx
- spawn_health.py
- gitGuard
- parseShell
- scheduling/__init__.py
- ._extract_context_flags
- entity_extractor.py
- ._github_poll_and_process
- ._process_candidates
- ._triage_and_build_evidence
- ._drain_once
- sanitize_call_syntax
- has_unevaluated_close_blocker
- knowledge_graph_api.py
- PulseBatch
- classifyTool
- get_quota_tracker
- SpawnPollResult
- SmartsheetMaintainerCache
- .has_reeval_signal
- get_event_document
- Trigger
- AsyncGitHubClient
- GitLabTokenAuth
- _is_event_closed_or_missing
- ._evaluate_health
- HeadhunterJira
- TimeKeeperObserver
- validate-mutations.sh
- _format_graph_context
- LLMResponse
- scripts
- state.js
- io
- ._process_message
- DispatchMetrics
- build_gate_context
- list_failed_stages
- PollFn
- ._wait_for_registration
- submit_feedback
- get_notebook
- get_current_shift
- ResyncTrigger
- TicketNode.tsx
- classify
- Reservation
- list_incidents
- require-results.sh
- get_intermediate_tools
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
2. `Brain` - 159 edges
3. `ConversationTurn` - 125 edges
4. `ToolContext` - 103 edges
5. `GateContext` - 96 edges
6. `react` - 85 edges
7. `EventDocument` - 82 edges
8. `fetchApi()` - 66 edges
9. `lifespan()` - 65 edges
10. `EventEvidence` - 58 edges

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

## Communities (210 total, 110 thin omitted)

### Community 0 - "BlackboardState"
Cohesion: 0.01
Nodes (3): rename_observation(), get_shift_detail(), BlackboardState

### Community 1 - "logging"
Cohesion: 0.03
Nodes (22): AgentConnection, AgentRegistry, agent_websocket_handler(), _heartbeat(), _build_prompt(), _check_security(), consume_wake_task(), _consume() (+14 more)

### Community 2 - "models.py"
Cohesion: 0.03
Nodes (39): AppNode, ArchitectureEvent, ChatRequest, ChatResponse, ConversationMessage, EventInput, EventMetrics, EventType (+31 more)

### Community 3 - "ConversationTurn"
Cohesion: 0.05
Nodes (52): emit_tool_result(), _safe_int(), handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_recall_pruned_turns(), handle_message_agent(), handle_reply_to_agent() (+44 more)

### Community 4 - "queue.py"
Cohesion: 0.03
Nodes (57): get_token_meter(), can_approve_event(), can_override_domain(), can_rename_event(), _normalize_email(), resolve_approval_identity(), get_archivist(), get_brain() (+49 more)

### Community 5 - "client.ts"
Cohesion: 0.04
Nodes (98): lucide-react, react, ApiError, applyLessons(), bulkDeleteObservations(), correctMemory(), createKnowledge(), createLesson() (+90 more)

### Community 6 - "nightwatcher_tools.py"
Cohesion: 0.03
Nodes (37): _adf_to_text(), _escape_jql_string(), JiraIncidentAdapter, record_token_usage(), PulseContext, ShiftIncident, _append_user_turn(), _env_float() (+29 more)

### Community 7 - "auth.py"
Cohesion: 0.03
Nodes (35): can_append_message(), _claims_to_user(), get_user_from_request(), get_user_from_websocket(), require_auth(), require_obs_admin(), UserContext, _validate_jwt() (+27 more)

### Community 8 - "main.py"
Cohesion: 0.03
Nodes (36): Architect, set_incident_options(), SysAdmin, set_oidc_adapter(), get_aligner(), get_architect(), get_argocd_observer(), get_developer() (+28 more)

### Community 10 - "EventSidebar.tsx"
Cohesion: 0.06
Nodes (82): getAlignerPending(), getClosedEvents(), getHeadhunterPending(), getJenkinsPending(), getJiraMissions(), getWaitingApprovalEvents(), HeadhunterTodo, postJiraAction() (+74 more)

### Community 11 - "brain.py"
Cohesion: 0.04
Nodes (33): _sanitize_lesson_text(), _compute_processed_up_to(), _contents_have_pruned_or_decayed(), _has_non_user_turns(), _is_seed_turn(), _apply_sibling_signature(), build_function_response(), build_single_function_response() (+25 more)

### Community 12 - "os"
Cohesion: 0.04
Nodes (25): _get_jira_reporter(), handle_ask_release_ai(), handle_comment_jira_issue(), handle_fetch_jira_issue(), handle_greenwave(), handle_transition_jira_issue(), _is_darwin_reentrant_caller(), jenkins_retrigger_cooldown_key() (+17 more)

### Community 13 - "tool_gates.py"
Cohesion: 0.05
Nodes (77): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+69 more)

### Community 15 - "App.tsx"
Cohesion: 0.05
Nodes (56): oidc-client-ts, react-dom, react-router-dom, getConfig(), getEventDocument(), getIncidents(), getWSAuthFailureCallback(), Incident (+48 more)

### Community 16 - "._run_agent_task"
Cohesion: 0.05
Nodes (9): on_huddle(), on_progress(), on_huddle(), on_progress(), _is_automated_nudge(), _sanitize_error_text(), _sanitize_override_reason(), _select_dispatch_tier() (+1 more)

### Community 17 - "http-handler.js"
Cohesion: 0.08
Nodes (62): is429Error(), registerMCPsAndHooks(), resolveCommand(), writeAgyMcpServer(), writeClaudeMcpServer(), parsePositiveInt(), buildArgoCDMcpConfig(), createAppJWT() (+54 more)

### Community 18 - "EventHistory.tsx"
Cohesion: 0.06
Nodes (42): getReport(), getReports(), ReportSearchParams, searchReports(), ReportFull, ReportMeta, ReportSearchResponse, SubjectType (+34 more)

### Community 19 - "WorkspaceInspector.tsx"
Cohesion: 0.07
Nodes (51): updateEventTitle(), CiContext, TokenUsageDict, ChatInput(), ChatInputProps, Draft, LastSubmission, CiContextCard() (+43 more)

### Community 20 - "api/types.ts"
Cohesion: 0.05
Nodes (57): Agent, AlignerPendingItem, AppNode, AuthUser, BulkDeleteRequest, ChatEventRequest, ChatEventResponse, ConversationTurn (+49 more)

### Community 21 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 22 - "useActiveEvents"
Cohesion: 0.07
Nodes (46): dismissProposals(), EnhancementProposal, getActiveEvents(), getFlowMetrics(), getHandoffReports(), getProposals(), HandoffReport, FlowMetrics (+38 more)

### Community 23 - "TurnBubble.tsx"
Cohesion: 0.08
Nodes (41): @uiw/react-markdown-preview, approveEvent(), closeEvent(), enforceCasualDomain(), rejectEvent(), submitFeedback(), CollapsibleSection(), CollapsibleSectionProps (+33 more)

### Community 25 - "._process_with_llm"
Cohesion: 0.04
Nodes (5): _BatchContext, _ensure_recall_tool_if_needed(), _QuotaShedState, RepetitionCollapse, _retry_backoff_delay()

### Community 27 - "merge-guard.js"
Cohesion: 0.04
Nodes (46): API_VALUED, ARGO_MUTATING, ARGO_READ_SUB, ARGO_READ_TOP, BODY_FLAG, BROWSER_READ, CTX, ENV_BUILTINS (+38 more)

### Community 29 - "cli-executor.js"
Cohesion: 0.09
Nodes (37): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, MAX_TASK_WALL_MS, MAX_TIMER_MS, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS, STORAGE_PRETASK_TIMEOUT_MS, resolveStorageRoot }, buildCLICommand(), buildTimeoutResult(), { checkAndRecycleStorage, pinTaskCwd, unpinTaskCwd }, CLAUDE_JSON_PATH, cp, createInactivityWatchdog(), executeCLI() (+29 more)

### Community 30 - "storage-recycler.js"
Cohesion: 0.08
Nodes (37): withTaskStorage(), MAX_TASK_WALL_MS, parseTimerMs(), resolveStorageRoot(), resolveTimeoutMs(), ROLE_TIMEOUTS, STORAGE_ACTIVITY_HEARTBEAT_MS, STORAGE_MAX_TIER3_DELETIONS (+29 more)

### Community 31 - "BrainSkillLoader"
Cohesion: 0.06
Nodes (3): BrainSkillLoader, _SkillCorpus, BrainIntrospectionPort

### Community 32 - "ObservationRepository"
Cohesion: 0.05
Nodes (3): CortexRepository, EscalationRepository, ObservationRepository

### Community 33 - "OpsStateContext.tsx"
Cohesion: 0.09
Nodes (31): @tanstack/react-query, createChatEvent(), getKargoStages(), EventEvidence, KargoStageStatus, STARTER_CHIPS, StarterChip, useSafeNavigate() (+23 more)

### Community 34 - "JenkinsAdapter"
Cohesion: 0.06
Nodes (6): BuildDetails, JenkinsAdapter, JenkinsPlatformPort, JobResult, JobRunState, ViewScanResult

### Community 37 - "ScheduleRepository"
Cohesion: 0.06
Nodes (7): ScheduledEvent, delete_schedule(), get_schedule(), list_schedules(), toggle_schedule(), update_schedule(), ScheduleRepository

### Community 39 - "CortexGraph.tsx"
Cohesion: 0.09
Nodes (35): graphology, AGENTS, DOMAINS, eventColor(), getExecutiveNeurons(), getStructuralEdges(), HEMISPHERE_X, NEURON_DESCRIPTIONS (+27 more)

### Community 40 - "formatter.py"
Cohesion: 0.08
Nodes (17): build_access_denied_home_view(), build_home_tab_view(), _context_line(), create_feedback_block(), _replace(), format_event_summary(), format_plan_block(), format_task_card() (+9 more)

### Community 41 - "GeminiAdapter"
Cohesion: 0.11
Nodes (5): _attach_signature_to_parts(), _extract_part_signature(), GeminiAdapter, _is_empty_sig_carrier(), _part_has_fc()

### Community 43 - "EventEvidence"
Cohesion: 0.10
Nodes (18): _build_closed_block(), build_event_header(), _build_identity_block(), _build_journal_block(), _build_mermaid_block(), build_operational_briefing(), _build_related_block(), _build_subject_block() (+10 more)

### Community 45 - "TimeKeeperPage.tsx"
Cohesion: 0.12
Nodes (24): createSchedule(), deleteSchedule(), getSchedules(), refineInstructions(), ScheduleCreatePayload, ScheduleItem, toggleSchedule(), updateSchedule() (+16 more)

### Community 46 - "ws-client.js"
Cohesion: 0.10
Nodes (26): clearIdleTimer(), {
  DEFAULT_WORK_DIR, AGENT_CLI, AGENT_MODEL, AGENT_ROLE,
  EVENT_ID, EPHEMERAL, IDLE_TIMEOUT_MS,
  CLI_429_MAX_RETRIES, CLI_429_INITIAL_DELAY_MS, CLI_429_BACKOFF_MULTIPLIER,
  resolveTimeoutMs, parsePositiveInt, MAX_TASK_WALL_MS, MAX_TIMER_MS,
}, { ensureEventDocument }, { executeCLIStreaming, prepareResultsDir, is429Error }, { filterSkillsByRole, filterSkillsByMode, swapActiveRules, restoreAllSkills }, fs, handleCancel(), handleTask() (+18 more)

### Community 47 - "DashboardWSAdapter"
Cohesion: 0.09
Nodes (5): DashboardWSAdapter, prompt_display_name(), ChatEventRequest, ChatEventResponse, create_chat_event()

### Community 49 - "jenkins_observer.py"
Cohesion: 0.09
Nodes (13): _annotation_replace(), _strip_pipeline_annotations(), _normalize_step_id(), _clamp_confidence(), _parse_job_metadata(), _prepare_console_tail(), _redact_match(), _redact_secrets_in_text() (+5 more)

### Community 50 - "ClaudeAdapter"
Cohesion: 0.10
Nodes (4): ClaudeAdapter, FunctionCall, LLMChunk, TokenUsage

### Community 51 - "ui/package.json"
Cohesion: 0.08
Nodes (29): autoprefixer, cronstrue, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, graphology-layout-forceatlas2 (+21 more)

### Community 52 - "spawn_event_namer_task"
Cohesion: 0.14
Nodes (9): spawn_event_namer_task(), handle_app_home_opened(), handle_app_mention(), handle_approve(), handle_create_event_modal(), handle_darwin_command(), handle_reject(), on_dm_message() (+1 more)

### Community 53 - "useCortexData.ts"
Cohesion: 0.17
Nodes (27): getCognitiveGraph(), getCortexActivity(), getEventReport(), getKGServiceDetail(), getKGServices(), getKGStats(), getKnowledgeById(), getMemory() (+19 more)

### Community 54 - ".list_observations"
Cohesion: 0.07
Nodes (5): get_all_journal(), get_service_journal(), get_event_observations(), get_global_observations(), export_observations()

### Community 55 - "types.py"
Cohesion: 0.11
Nodes (13): _parse_tpm_limit(), derive_llm_priority(), _get_timeout_env_warned(), _get_timeout_order_warned(), LLMStreamInterChunkTimeoutError, LLMStreamTimeoutError, LLMStreamTotalTimeoutError, LLMStreamTTFBTimeoutError (+5 more)

### Community 56 - "NodeInspector.tsx"
Cohesion: 0.12
Nodes (24): getEvents(), ArchitectureEvent, ArgoCDOperation, ActivityStream(), EVENT_LABELS, EventItem(), EventItemProps, healthTone() (+16 more)

### Community 57 - "._build_system_prompt"
Cohesion: 0.07
Nodes (3): _init_tool_names(), _strip_tool_names(), _wrap_section()

### Community 58 - "KnowledgeGraphStore"
Cohesion: 0.15
Nodes (4): _acquire(), KnowledgeGraphStore, _sanitize(), _with_timeout()

### Community 60 - "jira.py"
Cohesion: 0.13
Nodes (14): approve_mission(), dismiss_mission(), _infer_phase(), _jira_config(), list_missions(), reanalyze_mission(), retry_mission(), adf_to_markdown() (+6 more)

### Community 61 - "server.js"
Cohesion: 0.09
Nodes (18): { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, ensureEventDocument(), fs, path, stageEventDocument(), fetchEventDocument(), fs, { handleRequest } (+10 more)

### Community 62 - "VectorStore"
Cohesion: 0.11
Nodes (3): _decode_cursor(), _encode_cursor(), VectorStore

### Community 64 - "reconcile.py"
Cohesion: 0.15
Nodes (10): sanitize_redis_port(), _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers(), main() (+2 more)

### Community 65 - "slack.py"
Cohesion: 0.11
Nodes (6): get_user_from_slack(), extract_tables(), get_agent_notification_text(), get_turn_attachment_color(), table_block_to_code_block(), _PlanDecision

### Community 69 - "dependencies"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 70 - "cortex/types.ts"
Cohesion: 0.14
Nodes (21): CortexHeartbeat(), CortexHeartbeatProps, ensureKeyframes(), CortexLiveFeed(), CortexLiveFeedProps, FILTER_PILLS, FilterKey, getStoredFilter() (+13 more)

### Community 71 - "._build_contents"
Cohesion: 0.09
Nodes (3): _close_unanswered_fc(), ContextFlags, _incr_flow_counter_safely()

### Community 72 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 73 - "claude-guard.js"
Cohesion: 0.14
Nodes (18): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+10 more)

### Community 74 - "FlowHistoryPage.tsx"
Cohesion: 0.21
Nodes (17): recharts, getFlowHistory(), FlowSnapshot, FlowHistoryPage(), RANGES, SparkCard(), SparkCardProps, formatTime() (+9 more)

### Community 75 - "EventDrillDown.tsx"
Cohesion: 0.15
Nodes (17): three, getEventPulses(), BrainCore(), CortexDevPage(), devQueryClient, EventDrillDown(), FRICTION_COLORS, WHISPER_COLORS (+9 more)

### Community 79 - "PulseBatch"
Cohesion: 0.12
Nodes (4): PulseBatch, PulsePort, PulseObserver, PulseTracker

### Community 80 - "cli-setup.js"
Cohesion: 0.13
Nodes (18): { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync }, filterSkillsByMode() (+10 more)

### Community 81 - "StateWatcher"
Cohesion: 0.13
Nodes (3): _QueueEntry, StateWatcher, _Subscription

### Community 84 - "devDependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 85 - "FloatingWindow.tsx"
Cohesion: 0.17
Nodes (16): AgentStreamCard(), AgentStreamCardProps, MessageCards(), CopyButtonProps, DEFAULT_POS, DEFAULT_SIZE, EMPTY_MESSAGES, FloatingWindow() (+8 more)

### Community 86 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 87 - "gemini-sidecar/package.json"
Cohesion: 0.11
Nodes (18): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+10 more)

### Community 88 - "ServiceNode.tsx"
Cohesion: 0.15
Nodes (13): @xyflow/react, HealthStatus, NodeType, AppNodeData, ARGOCD_HEALTH_COLORS, SYNC_ICONS, NamespaceGroupNodeData, GENERIC_TAGS (+5 more)

### Community 90 - "get_report"
Cohesion: 0.11
Nodes (6): get_report(), list_reports(), reports_spa_no_slash(), reports_spa_with_slash(), search_reports(), _serve_spa()

### Community 91 - "ArchitectureGraph.tsx"
Cohesion: 0.17
Nodes (16): @dagrejs/dagre, applyDagreLayout(), applyGridLayout(), applyLayout(), ArchitectureGraph(), ArchitectureGraphInner(), buildGraph(), computeIdHash() (+8 more)

### Community 94 - "gemini_client.py"
Cohesion: 0.13
Nodes (8): _append_user_turn(), _clone_part_with_sig(), _coerce_part(), _decode_sig_bytes(), _is_function_response_part(), _parse_drain_timeout(), _strip_user_thought_signature(), _validated_parts()

### Community 95 - "QuotaTracker"
Cohesion: 0.14
Nodes (4): QuotaExhaustedError, QuotaTracker, RequestExceedsBurstError, _stale_reservation_ttl_s()

### Community 97 - "ShiftsPage.tsx"
Cohesion: 0.23
Nodes (16): getCurrentShift(), getShiftDetail(), getShiftsList(), ShiftReportFull, ShiftReportSummary, FailedClusterBadge(), getISOWeek(), getWeekDates() (+8 more)

### Community 98 - "catalog-skills.js"
Cohesion: 0.16
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 101 - "generate_map.py"
Cohesion: 0.19
Nodes (6): _enumerate_gates(), _GateInfo, generate_phase_tool_map(), _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 106 - "ReconcileScheduler"
Cohesion: 0.16
Nodes (3): ReconcileScheduler, QueueTrigger, StalenessGuard

### Community 107 - "observations_reporter.py"
Cohesion: 0.21
Nodes (7): _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), _sample_points(), _summarize()

### Community 111 - "analyzeTokens"
Cohesion: 0.19
Nodes (13): analyzeString(), analyzeTokens(), assignName(), base(), combineCategories(), configEnvGuard(), configFileWriteGuard(), hasSubseq() (+5 more)

### Community 113 - "IncidentAdapterPort"
Cohesion: 0.15
Nodes (3): IdleTimeoutPort, IncidentAdapterPort, StateWatcherPort

### Community 118 - "testSetup.ts"
Cohesion: 0.18
Nodes (5): @tailwindcss/vite, @testing-library/react, vite, @vitejs/plugin-react, vitest

### Community 119 - "is_defer_event_available"
Cohesion: 0.18
Nodes (6): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 120 - "NeuronInfoPanel.tsx"
Cohesion: 0.29
Nodes (10): asNumber(), asString(), asStringArray(), Badge(), describeNeuron(), Hdr(), NeuronInfoPanel(), AGENT_NEURON_COLORS (+2 more)

### Community 122 - "gitGuard"
Cohesion: 0.29
Nodes (10): bareBranchProtected(), configWriteGuard(), externalGitCommand(), gitGuard(), gitQuery(), isProtected(), normRef(), pushGuard() (+2 more)

### Community 123 - "parseShell"
Cohesion: 0.33
Nodes (10): bodySubstitutions(), decodeAnsiC(), isArrayAssignPrefix(), isWordStart(), matchBacktick(), matchParen(), parseShell(), readHeredocStart() (+2 more)

### Community 124 - "scheduling/__init__.py"
Cohesion: 0.29
Nodes (4): GitHubPrRef, GitLabMrRef, GitLabPipelineRef, KargoStageRef

### Community 126 - "entity_extractor.py"
Cohesion: 0.33
Nodes (5): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship

### Community 131 - "sanitize_call_syntax"
Cohesion: 0.20
Nodes (5): _extract_call_syntax(), process_stream_call_syntax_buffer(), sanitize_call_syntax(), scan_call_syntax(), split_stream_call_syntax()

### Community 132 - "has_unevaluated_close_blocker"
Cohesion: 0.20
Nodes (4): has_unevaluated_close_blocker(), _pred_jarvis_response(), _pred_unevaluated_close(), is_jarvis_acknowledgment()

### Community 133 - "knowledge_graph_api.py"
Cohesion: 0.31
Nodes (4): get_kg_store(), get_service_detail(), get_stats(), list_services()

### Community 134 - "PulseBatch"
Cohesion: 0.27
Nodes (9): EventSource, KGServiceEntity, CortexGraphProps, GraphLoaderProps, NeuronInfoPanelProps, PulseTimelineProps, Neuron, PulseBatch (+1 more)

### Community 135 - "classifyTool"
Cohesion: 0.31
Nodes (9): apiTokens(), apiWriteNeedsGuard(), branchValues(), classifyTool(), hasOpaqueTarget(), httpGuard(), httpMethod(), isReadMethod() (+1 more)

### Community 136 - "get_quota_tracker"
Cohesion: 0.22
Nodes (3): get_quota_tracker(), llm_stats(), receive_telemetry()

### Community 149 - "validate-mutations.sh"
Cohesion: 0.57
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

### Community 150 - "_format_graph_context"
Cohesion: 0.38
Nodes (3): _format_graph_context(), _parse_props(), _sanitize()

### Community 152 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 153 - "state.js"
Cohesion: 0.33
Nodes (4): { AGENT_ROLE }, _blackboardTurns, _inboundMessages, _teammateMessages

### Community 164 - "build_gate_context"
Cohesion: 0.33
Nodes (3): build_gate_context(), conversation_has_decayed_turns(), _decay_payload_len()

### Community 174 - "TicketNode.tsx"
Cohesion: 0.40
Nodes (4): STATUS_COLORS, TICKET_COLORS, TicketNodeComponent(), TicketNodeData

### Community 175 - "classify"
Cohesion: 0.50
Nodes (4): classify(), main(), shellCategory(), shellNeedsGuard()

### Community 185 - "overrides"
Cohesion: 0.67
Nodes (3): overrides, @typescript-eslint/typescript-estree, minimatch

## Knowledge Gaps
- **13 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+8 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2301 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **110 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `logging`, `models.py`, `ConversationTurn`, `queue.py`, `nightwatcher_tools.py`, `auth.py`, `main.py`, `Brain`, `brain.py`, `os`, `get_event_document`, `_is_event_closed_or_missing`, `HeadhunterJira`, `EventDocument`, `ScheduleRepository`, `submit_feedback`, `get_notebook`, `get_current_shift`, `EventEvidence`, `DashboardWSAdapter`, `jenkins_observer.py`, `.list_observations`, `LiveAPIAdapter`, `jira.py`, `slack.py`, `get_report`, `.__init__`, `observations_reporter.py`?**
  _High betweenness centrality (0.094) - this node is a cross-community bridge._
- **Are the 80 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 80 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.01160405872193437 - nodes in this community are weakly interconnected._
- **Why does `EventEvidence` connect `EventEvidence` to `BlackboardState`, `logging`, `._triage_and_build_evidence`, `models.py`, `queue.py`, `auth.py`, `Brain`, `brain.py`, `os`, `Archivist`, `_is_event_closed_or_missing`, `HeadhunterJira`, `TimeKeeperObserver`, `Aligner`, `EventRepository`, `GitHubPlatform`, `SlackChannel`, `GitLabPlatform`, `DashboardWSAdapter`, `jenkins_observer.py`, `spawn_event_namer_task`, `LiveAPIAdapter`, `slack.py`, `JenkinsObserver`, `.create_platform_event`, `.poll_and_process`, `ScheduleCreateRequest`?**
  _High betweenness centrality (0.063) - this node is a cross-community bridge._
- **Are the 19 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 19 INFERRED edges - model-reasoned connections that need verification._
- **Should `logging` be split into smaller, more focused modules?**
  _Cohesion score 0.029113005623072737 - nodes in this community are weakly interconnected._