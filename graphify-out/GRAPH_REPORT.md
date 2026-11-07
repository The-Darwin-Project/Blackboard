# Graph Report - Blackboard  (2026-11-07)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 5070 nodes · 11296 edges · 216 communities (108 shown, 108 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 938 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `685261e5`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BlackboardState
- models.py
- client.ts
- brain.py
- Brain
- EventDocument
- tool_gates.py
- FastAPI
- EventChatPanel.tsx
- EventEvidence
- react
- colors.ts
- EventSidebar.tsx
- os
- ReconcileScheduler
- main.py
- fetchApi
- http-handler.js
- ._run_agent_task
- jenkins-mcp.js
- Archivist
- BrainSkillLoader
- TurnBubble.tsx
- ._process_with_llm
- dependencies.py
- _BrainToolContext
- merge-guard.js
- KnowledgeGraphStore
- observations_mgmt.py
- slack.py
- nightwatcher_tools.py
- EventRepository
- cli-executor.js
- ToolContext
- storage-recycler.js
- JenkinsAdapter
- ScheduleRepository
- OpsStateContext.tsx
- GitHubPlatform
- ConversationTurn
- TimeKeeperPage.tsx
- Aligner
- GitLabPlatform
- gemini_client.py
- event_to_markdown
- Headhunter
- useOpsControl
- jenkins_observer.py
- queue.py
- ws-client.js
- useQueue.ts
- time
- AgentRegistry
- get_archivist
- EventDrillDown.tsx
- dispatch.py
- server.js
- ._close_and_broadcast
- cognitive_graph.py
- LiveAPIAdapter
- useCortexData.ts
- UserContext
- StateWatcher
- ui/package.json
- state/__init__.py
- NightwatcherObserver
- CortexGraph.tsx
- ._get_manager
- GeminiAdapter
- ArgoCDObserver
- KargoObserver
- TopologyRepository
- dependencies
- quota_tracker.py
- cortex/types.ts
- TokenUtilizationPage.tsx
- GitHubAppAuth
- compilerOptions
- claude-guard.js
- VectorStore
- reconcile.py
- cli-setup.js
- ArchitectureGraph.tsx
- tool_router.py
- HeadhunterJira
- VcsPlatformPort
- SlackChannel
- PulseBatch
- SecurityError
- DashboardWSAdapter
- .archive_event
- ReflexSearcher
- devDependencies
- NodeInspector.tsx
- compilerOptions
- EphemeralProvisioner
- gemini-sidecar/package.json
- handlers_verification.py
- handlers_state.py
- .get_event
- ObservationRepository
- ShiftsPage.tsx
- catalog-skills.js
- ClaudeAdapter
- EscalationRepository
- JiraIncidentAdapter
- close_event_by_user
- list_active_events
- generate_map.py
- OIDCKeyAdapter
- KubernetesSpawnHealthAdapter
- .scroll
- IdleTimeoutManager
- JenkinsObserver
- ServiceNode.tsx
- _append_user_turn
- nightwatcher_prompt.py
- SlackAccessGate
- analyzeTokens
- FilterRule
- BrainLifecyclePort
- TokenMeter
- .list_observations
- MultiInstallationManager
- JarvisMemoryPage.tsx
- ._authorize_plan_decision
- format_jira_for_llm
- NeuronInfoPanel.tsx
- testSetup.ts
- is_defer_event_available
- cortex-constants.ts
- CortexDevPage.tsx
- spawn_health.py
- gitGuard
- parseShell
- adf_to_markdown
- ._post_agent_recall
- ._process_candidates
- ._triage_and_build_evidence
- ._drain_once
- has_unevaluated_close_blocker
- ._send_turn_to_thread
- knowledge_graph_api.py
- classifyTool
- get_quota_tracker
- SpawnPollResult
- SmartsheetMaintainerCache
- ._register_handlers
- AsyncGitHubClient
- GitLabTokenAuth
- _is_event_closed_or_missing
- ._evaluate_health
- TimeKeeperObserver
- CortexRepository
- validate-mutations.sh
- scripts
- reconcile_cluster_plan
- state.js
- ._process_message
- DispatchMetrics
- list_failed_stages
- ._wait_for_registration
- agent_ws_endpoint
- TicketNode.tsx
- classify
- derive_llm_priority
- headhunter_pending_todos
- TitleUpdateRequest
- require-results.sh
- _walk_adf_mentions
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
3. `ConversationTurn` - 123 edges
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

## Communities (216 total, 108 thin omitted)

### Community 0 - "BlackboardState"
Cohesion: 0.01
Nodes (7): delete_notebook_note(), get_notebook(), delete_schedule(), get_schedule(), list_schedules(), toggle_schedule(), BlackboardState

### Community 1 - "models.py"
Cohesion: 0.03
Nodes (37): AppNode, ArchitectureEvent, ChatRequest, ChatResponse, ConversationMessage, EventInput, EventMetrics, EventStatus (+29 more)

### Community 2 - "client.ts"
Cohesion: 0.03
Nodes (92): @tanstack/react-query, ApiError, bulkDeleteObservations(), deleteNote(), deleteObservation(), exportObservations(), ExtractionResult, generateObservationsReport() (+84 more)

### Community 3 - "brain.py"
Cohesion: 0.04
Nodes (17): _sanitize_lesson_text(), _apply_sibling_signature(), build_function_response(), build_single_function_response(), compress_contents(), estimate_msg_tokens(), estimate_tokens(), extract_model_parts() (+9 more)

### Community 5 - "EventDocument"
Cohesion: 0.03
Nodes (14): _close_unanswered_fc(), ContextFlags, _resolve_escalation_scope(), _build_closed_block(), build_event_header(), _build_identity_block(), _build_journal_block(), _build_mermaid_block() (+6 more)

### Community 6 - "tool_gates.py"
Cohesion: 0.05
Nodes (78): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+70 more)

### Community 7 - "FastAPI"
Cohesion: 0.04
Nodes (15): get_blackboard(), list_incidents(), get_all_journal(), get_service_journal(), NotePatchRequest, update_notebook_note(), get_report(), list_reports() (+7 more)

### Community 8 - "EventChatPanel.tsx"
Cohesion: 0.06
Nodes (58): updateEventTitle(), CiContext, ConversationTurn, TokenUsageDict, CiContextCard(), CiContextCardProps, ConsoleTailBlock(), FailedJobRow() (+50 more)

### Community 9 - "EventEvidence"
Cohesion: 0.05
Nodes (23): generate_event_title(), get_adapter(), _get_semaphore(), spawn_event_namer_task(), can_append_message(), can_rename_event(), get_user_from_websocket(), _normalize_email() (+15 more)

### Community 10 - "react"
Cohesion: 0.06
Nodes (51): oidc-client-ts, react, react-router-dom, getConfig(), getWSAuthFailureCallback(), setOnUnauthorized(), setTokenGetter(), setWSAuthFailureCallback() (+43 more)

### Community 11 - "colors.ts"
Cohesion: 0.07
Nodes (45): @tanstack/react-table, getReport(), getReports(), ReportFull, ReportMeta, DeferCountdownBar(), CompactCardStrip(), EventHistory() (+37 more)

### Community 12 - "EventSidebar.tsx"
Cohesion: 0.07
Nodes (61): getHeadhunterPending(), getJiraMissions(), HeadhunterTodo, postJiraAction(), AgentRegistryEntry, ChatInput(), ChatInputProps, Draft (+53 more)

### Community 13 - "os"
Cohesion: 0.05
Nodes (17): _get_static_maintainer_emails(), _get_allowed_mention_authors(), _get_static_maintainer_emails(), _safe_int(), dex_proxy(), approve_mission(), dismiss_mission(), _infer_phase() (+9 more)

### Community 14 - "ReconcileScheduler"
Cohesion: 0.04
Nodes (7): FlowCollector, FairQueue, ReconcileScheduler, Trigger, QueueTrigger, ResyncTrigger, StalenessGuard

### Community 15 - "main.py"
Cohesion: 0.04
Nodes (21): set_incident_options(), set_oidc_adapter(), set_agents(), set_archivist(), set_argocd_observer(), set_blackboard(), set_brain(), set_kargo_observer() (+13 more)

### Community 16 - "fetchApi"
Cohesion: 0.07
Nodes (56): lucide-react, applyLessons(), correctMemory(), createKnowledge(), createLesson(), deleteKnowledge(), deleteLesson(), ExtractedCorrection (+48 more)

### Community 17 - "http-handler.js"
Cohesion: 0.09
Nodes (58): resolveCommand(), writeAgyMcpServer(), writeClaudeMcpServer(), buildArgoCDMcpConfig(), createAppJWT(), discoverAndGenerateTokens(), _discoverAndGenerateTokensInner(), discoverInstallations() (+50 more)

### Community 18 - "._run_agent_task"
Cohesion: 0.06
Nodes (10): on_huddle(), on_progress(), on_huddle(), on_progress(), _compute_processed_up_to(), _is_automated_nudge(), _sanitize_error_text(), _sanitize_override_reason() (+2 more)

### Community 19 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 21 - "BrainSkillLoader"
Cohesion: 0.05
Nodes (4): BrainSkillLoader, _SkillCorpus, _wrap_section(), BrainIntrospectionPort

### Community 22 - "TurnBubble.tsx"
Cohesion: 0.08
Nodes (41): @uiw/react-markdown-preview, approveEvent(), closeEvent(), enforceCasualDomain(), getEventReport(), rejectEvent(), submitFeedback(), CollapsibleSection() (+33 more)

### Community 23 - "._process_with_llm"
Cohesion: 0.04
Nodes (3): _BatchContext, compute_dispatch_backpressure(), _safe_int_env()

### Community 24 - "dependencies.py"
Cohesion: 0.06
Nodes (10): Architect, AgentClient, Developer, SysAdmin, get_aligner(), get_architect(), get_argocd_observer(), get_developer() (+2 more)

### Community 26 - "merge-guard.js"
Cohesion: 0.04
Nodes (46): API_VALUED, ARGO_MUTATING, ARGO_READ_SUB, ARGO_READ_TOP, BODY_FLAG, BROWSER_READ, CTX, ENV_BUILTINS (+38 more)

### Community 27 - "KnowledgeGraphStore"
Cohesion: 0.08
Nodes (9): _format_graph_context(), get_graph_context(), _parse_props(), _sanitize(), translate_to_lookups(), _acquire(), KnowledgeGraphStore, _sanitize() (+1 more)

### Community 28 - "observations_mgmt.py"
Cohesion: 0.06
Nodes (18): get_report_client(), _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), render_pdf(), _sample_points() (+10 more)

### Community 29 - "slack.py"
Cohesion: 0.07
Nodes (19): get_user_from_slack(), build_access_denied_home_view(), build_home_tab_view(), _context_line(), create_feedback_block(), extract_tables(), _replace(), format_plan_block() (+11 more)

### Community 30 - "nightwatcher_tools.py"
Cohesion: 0.09
Nodes (20): PulseContext, ShiftIncident, ShiftInvestigation, extract_full_links(), build_extend_tool(), build_report_tool(), build_summary_tool(), execute_tool() (+12 more)

### Community 32 - "cli-executor.js"
Cohesion: 0.09
Nodes (36): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS, STORAGE_PRETASK_TIMEOUT_MS, resolveStorageRoot }, buildCLICommand(), { checkAndRecycleStorage, pinTaskCwd, unpinTaskCwd }, CLAUDE_JSON_PATH, cp, executeCLI(), executeCLIStreaming(), FALLBACK_MODEL (+28 more)

### Community 33 - "ToolContext"
Cohesion: 0.09
Nodes (12): handle_message_agent(), handle_reply_to_agent(), handle_report_incident(), handle_select_agent(), _sticky_work_style(), handle_notify_gitlab_result(), handle_search_open_incidents(), handle_hold_watch() (+4 more)

### Community 34 - "storage-recycler.js"
Cohesion: 0.08
Nodes (34): withTaskStorage(), resolveStorageRoot(), ROLE_TIMEOUTS, STORAGE_ACTIVITY_HEARTBEAT_MS, STORAGE_MAX_TIER3_DELETIONS, STORAGE_PRETASK_TIMEOUT_MS, STORAGE_RESULTS_TTL_MS, STORAGE_STALE_MS (+26 more)

### Community 35 - "JenkinsAdapter"
Cohesion: 0.06
Nodes (6): BuildDetails, JenkinsAdapter, JenkinsPlatformPort, JobResult, JobRunState, ViewScanResult

### Community 36 - "ScheduleRepository"
Cohesion: 0.06
Nodes (5): ScheduleCreateRequest, ScheduledEvent, create_schedule(), update_schedule(), ScheduleRepository

### Community 37 - "OpsStateContext.tsx"
Cohesion: 0.09
Nodes (30): createChatEvent(), getKargoStages(), EventEvidence, KargoStageStatus, STARTER_CHIPS, StarterChip, useSafeNavigate(), WorkspaceCenterStage() (+22 more)

### Community 39 - "ConversationTurn"
Cohesion: 0.14
Nodes (21): emit_tool_result(), handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_recall_pruned_turns(), _get_jira_reporter(), handle_ask_release_ai(), handle_comment_jira_issue() (+13 more)

### Community 40 - "TimeKeeperPage.tsx"
Cohesion: 0.11
Nodes (25): react-dom, createSchedule(), deleteSchedule(), getSchedules(), refineInstructions(), ScheduleCreatePayload, ScheduleItem, toggleSchedule() (+17 more)

### Community 43 - "gemini_client.py"
Cohesion: 0.11
Nodes (10): _extract_call_syntax(), FunctionCall, LLMChunk, LLMPort, LLMResponse, process_stream_call_syntax_buffer(), sanitize_call_syntax(), scan_call_syntax() (+2 more)

### Community 44 - "event_to_markdown"
Cohesion: 0.08
Nodes (8): get_event_document(), list_events(), _esc(), _esc_join(), event_to_markdown(), get_github_auth(), maintainer_env_key(), resolve_maintainer_emails()

### Community 45 - "Headhunter"
Cohesion: 0.08
Nodes (3): Headhunter, _raise_if_systemic_failure(), _sanitize_xml_fence()

### Community 46 - "useOpsControl"
Cohesion: 0.12
Nodes (28): AgentStreamCard(), AgentStreamCardProps, FloatingWindow(), MessageCards(), Dashboard(), GridTile(), GridTileProps, TileType (+20 more)

### Community 47 - "jenkins_observer.py"
Cohesion: 0.09
Nodes (14): _annotation_replace(), _strip_pipeline_annotations(), _clamp_confidence(), _parse_job_metadata(), _prepare_console_tail(), _redact_match(), _redact_secrets_in_text(), _sanitize_analysis_text() (+6 more)

### Community 48 - "queue.py"
Cohesion: 0.10
Nodes (18): can_override_domain(), apply_lessons(), correct_memory(), CorrectMemoryRequest, create_knowledge(), create_lesson(), enforce_casual_domain(), EnforceCasualRequest (+10 more)

### Community 49 - "ws-client.js"
Cohesion: 0.09
Nodes (26): is429Error(), {
  DEFAULT_WORK_DIR, AGENT_CLI, AGENT_MODEL, AGENT_ROLE,
  EVENT_ID, EPHEMERAL, IDLE_TIMEOUT_MS,
  CLI_429_MAX_RETRIES, CLI_429_INITIAL_DELAY_MS, CLI_429_BACKOFF_MULTIPLIER,
}, { ensureEventDocument }, { executeCLIStreaming, prepareResultsDir, is429Error }, { filterSkillsByRole, filterSkillsByMode, swapActiveRules, restoreAllSkills }, fs, handleCancel(), resetTimer() (+18 more)

### Community 50 - "useQueue.ts"
Cohesion: 0.11
Nodes (28): getActiveEvents(), getAlignerPending(), getClosedEvents(), getEventDocument(), getJenkinsPending(), getWaitingApprovalEvents(), EventDocument, MessageStatus (+20 more)

### Community 51 - "time"
Cohesion: 0.13
Nodes (13): handle_notify_user_slack(), handle_refresh_github_context(), handle_refresh_gitlab_context(), handle_refresh_kargo_context(), _resolve_maintainer_enum(), _resolve_slack_user(), build_event_report_md(), GitHubPrRef (+5 more)

### Community 52 - "AgentRegistry"
Cohesion: 0.09
Nodes (4): AgentConnection, AgentRegistry, agent_websocket_handler(), _heartbeat()

### Community 53 - "get_archivist"
Cohesion: 0.08
Nodes (14): get_archivist(), aligner_pending_items(), delete_knowledge(), delete_lesson(), demote_lesson(), get_event_turns(), get_knowledge(), get_lesson() (+6 more)

### Community 54 - "EventDrillDown.tsx"
Cohesion: 0.11
Nodes (24): three, getEventPulses(), BrainCore(), CortexDevPage(), CortexHeartbeat(), CortexHeartbeatProps, ensureKeyframes(), CortexLiveFeed() (+16 more)

### Community 55 - "dispatch.py"
Cohesion: 0.12
Nodes (10): _build_prompt(), _check_security(), consume_wake_task(), _consume(), _dispatch_timeout_s(), dispatch_to_agent(), _consume_queue(), _sanitize_stdout() (+2 more)

### Community 56 - "server.js"
Cohesion: 0.08
Nodes (18): hasRegistryCredentials(), { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, fs, path, stageEventDocument(), fetchEventDocument(), fs, { handleRequest } (+10 more)

### Community 57 - "._close_and_broadcast"
Cohesion: 0.08
Nodes (3): _has_non_user_turns(), _is_seed_turn(), get_token_meter()

### Community 58 - "cognitive_graph.py"
Cohesion: 0.10
Nodes (12): get_brain(), get_pulse_tracker(), dismiss_proposals(), DismissRequest, get_all_shadow_interventions(), get_cognitive_graph(), get_cortex_activity(), get_cortex_status() (+4 more)

### Community 60 - "useCortexData.ts"
Cohesion: 0.19
Nodes (24): getCognitiveGraph(), getCortexActivity(), getKGServiceDetail(), getKGServices(), getKGStats(), getRecentPulses(), getExecutiveNeurons(), CortexPage() (+16 more)

### Community 61 - "UserContext"
Cohesion: 0.11
Nodes (9): can_approve_event(), _claims_to_user(), get_user_from_request(), require_auth(), require_obs_admin(), UserContext, approve_event(), reject_event() (+1 more)

### Community 62 - "StateWatcher"
Cohesion: 0.10
Nodes (3): _QueueEntry, StateWatcher, _Subscription

### Community 63 - "ui/package.json"
Cohesion: 0.09
Nodes (24): autoprefixer, cronstrue, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, graphology-layout-forceatlas2 (+16 more)

### Community 64 - "state/__init__.py"
Cohesion: 0.10
Nodes (5): skills_version(), sanitize_redis_port(), close_redis(), get_redis(), RedisClient

### Community 65 - "NightwatcherObserver"
Cohesion: 0.11
Nodes (4): ShiftReport, _env_float(), _env_int(), NightwatcherObserver

### Community 66 - "CortexGraph.tsx"
Cohesion: 0.14
Nodes (24): @react-sigma/core, @react-sigma/layout-forceatlas2, sigma, @sigma/node-square, ActiveEvent, KGServiceEntity, eventColor(), getStructuralEdges() (+16 more)

### Community 72 - "dependencies"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 73 - "quota_tracker.py"
Cohesion: 0.12
Nodes (4): QuotaExhaustedError, QuotaTracker, RequestExceedsBurstError, Reservation

### Community 74 - "cortex/types.ts"
Cohesion: 0.12
Nodes (20): graphology, EventSource, DEFAULT_TYPE_BUDGET, KNOWLEDGE_RING, KNOWLEDGE_RING_TYPES, KnowledgeNodeAttributes, knowledgeRingColor(), knowledgeRingLabel() (+12 more)

### Community 75 - "TokenUtilizationPage.tsx"
Cohesion: 0.15
Nodes (18): recharts, getFlowHistory(), FlowSnapshot, ObservationSeries, FlowHistoryPage(), formatTime(), RANGES, SparkCard() (+10 more)

### Community 77 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 78 - "claude-guard.js"
Cohesion: 0.14
Nodes (18): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+10 more)

### Community 80 - "reconcile.py"
Cohesion: 0.18
Nodes (9): _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers(), main(), _parse_frontmatter() (+1 more)

### Community 81 - "cli-setup.js"
Cohesion: 0.13
Nodes (19): { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync }, filterSkillsByMode() (+11 more)

### Community 82 - "ArchitectureGraph.tsx"
Cohesion: 0.14
Nodes (17): @dagrejs/dagre, @xyflow/react, applyDagreLayout(), applyGridLayout(), applyLayout(), ArchitectureGraphInner(), buildGraph(), computeIdHash() (+9 more)

### Community 83 - "tool_router.py"
Cohesion: 0.11
Nodes (6): _safe_int(), handle_consult_deep_memory(), handle_google_web_search(), handle_lookup_service(), IncidentAdapterPort, StateWatcherPort

### Community 88 - "PulseBatch"
Cohesion: 0.12
Nodes (4): PulseBatch, PulsePort, PulseObserver, PulseTracker

### Community 89 - "SecurityError"
Cohesion: 0.11
Nodes (3): safe_execution(), wrapper(), SecurityError

### Community 91 - ".archive_event"
Cohesion: 0.14
Nodes (5): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship

### Community 93 - "devDependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 94 - "NodeInspector.tsx"
Cohesion: 0.16
Nodes (17): getEvents(), ArchitectureEvent, ArgoCDOperation, ActivityStream(), EVENT_LABELS, EventItem(), EventItemProps, healthTone() (+9 more)

### Community 95 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 98 - "gemini-sidecar/package.json"
Cohesion: 0.11
Nodes (17): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+9 more)

### Community 100 - "handlers_verification.py"
Cohesion: 0.12
Nodes (8): _alert_wrapper_retrigger(), _do_retrigger(), handle_retrigger_jenkins_build(), jenkins_retrigger_cooldown_key(), handle_re_trigger_aligner(), handle_set_phase(), handle_wait_for_verification(), resolve_event_domain()

### Community 101 - "handlers_state.py"
Cohesion: 0.14
Nodes (6): handle_classify_event(), handle_defer_event(), handle_request_user_approval(), handle_wait_for_user(), IdleTimeoutPort, _resolve_domain()

### Community 102 - ".get_event"
Cohesion: 0.11
Nodes (6): report_tampering(), FeedbackRequest, submit_feedback(), get_event_approval(), get_event_document(), rebuild_deep_memory()

### Community 104 - "ShiftsPage.tsx"
Cohesion: 0.23
Nodes (16): getCurrentShift(), getShiftDetail(), getShiftsList(), ShiftReportFull, ShiftReportSummary, FailedClusterBadge(), getISOWeek(), getWeekDates() (+8 more)

### Community 105 - "catalog-skills.js"
Cohesion: 0.16
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 110 - "close_event_by_user"
Cohesion: 0.12
Nodes (3): close_event_by_user(), CloseRequest, get_event_report()

### Community 111 - "list_active_events"
Cohesion: 0.12
Nodes (6): _defer_timeline_fields(), _has_active_subscription(), list_active_events(), list_closed_events(), list_waiting_approval_events(), _serialize_evidence()

### Community 112 - "generate_map.py"
Cohesion: 0.19
Nodes (6): _enumerate_gates(), _GateInfo, generate_phase_tool_map(), _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 118 - "ServiceNode.tsx"
Cohesion: 0.20
Nodes (11): HealthStatus, NodeType, AppNodeData, ARGOCD_HEALTH_COLORS, SYNC_ICONS, GENERIC_TAGS, HEALTH_COLORS, NODE_ICONS (+3 more)

### Community 120 - "_append_user_turn"
Cohesion: 0.14
Nodes (5): _append_user_turn(), _coerce_part(), _is_function_response_part(), _strip_user_thought_signature(), _validated_parts()

### Community 121 - "nightwatcher_prompt.py"
Cohesion: 0.16
Nodes (6): build_manifest_table(), build_report_iteration_prompt(), build_summary_prompt(), build_system_prompt(), extract_event_links(), _normalize_gitlab_host()

### Community 123 - "analyzeTokens"
Cohesion: 0.19
Nodes (13): analyzeString(), analyzeTokens(), assignName(), base(), combineCategories(), configEnvGuard(), configFileWriteGuard(), hasSubseq() (+5 more)

### Community 129 - "JarvisMemoryPage.tsx"
Cohesion: 0.27
Nodes (12): dismissProposals(), EnhancementProposal, getHandoffReports(), getProposals(), HandoffReport, FilterMode, formatDate(), formatTime() (+4 more)

### Community 130 - "._authorize_plan_decision"
Cohesion: 0.18
Nodes (3): _PlanDecision, handle_approve(), handle_reject()

### Community 134 - "NeuronInfoPanel.tsx"
Cohesion: 0.26
Nodes (11): asNumber(), asString(), asStringArray(), Badge(), describeNeuron(), Hdr(), NeuronInfoPanel(), NeuronInfoPanelProps (+3 more)

### Community 135 - "testSetup.ts"
Cohesion: 0.18
Nodes (5): @tailwindcss/vite, @testing-library/react, vite, @vitejs/plugin-react, vitest

### Community 136 - "is_defer_event_available"
Cohesion: 0.18
Nodes (6): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 137 - "cortex-constants.ts"
Cohesion: 0.18
Nodes (10): AGENTS, DOMAINS, HEMISPHERE_X, NEURON_DESCRIPTIONS, PHASE_SKILL_FOLDERS, PHASE_TOOL_PRIORITY, PHASES, StructuralEdge (+2 more)

### Community 138 - "CortexDevPage.tsx"
Cohesion: 0.31
Nodes (9): devQueryClient, MOCK_CORTEX_STATUS, MOCK_EVENT_ID, MOCK_NEURONS, MOCK_PULSE_BATCHES, MOCK_SHADOW, MOCK_THINKING, MOCK_WHISPERS (+1 more)

### Community 140 - "gitGuard"
Cohesion: 0.29
Nodes (10): bareBranchProtected(), configWriteGuard(), externalGitCommand(), gitGuard(), gitQuery(), isProtected(), normRef(), pushGuard() (+2 more)

### Community 141 - "parseShell"
Cohesion: 0.33
Nodes (10): bodySubstitutions(), decodeAnsiC(), isArrayAssignPrefix(), isWordStart(), matchBacktick(), matchParen(), parseShell(), readHeredocStart() (+2 more)

### Community 142 - "adf_to_markdown"
Cohesion: 0.40
Nodes (8): _adf_to_text(), adf_to_markdown(), _apply_marks(), _children(), _render(), _render_list(), _render_list_item(), _render_table_like()

### Community 148 - "has_unevaluated_close_blocker"
Cohesion: 0.20
Nodes (4): has_unevaluated_close_blocker(), _pred_jarvis_response(), _pred_unevaluated_close(), is_jarvis_acknowledgment()

### Community 150 - "knowledge_graph_api.py"
Cohesion: 0.31
Nodes (4): get_kg_store(), get_service_detail(), get_stats(), list_services()

### Community 151 - "classifyTool"
Cohesion: 0.31
Nodes (9): apiTokens(), apiWriteNeedsGuard(), branchValues(), classifyTool(), hasOpaqueTarget(), httpGuard(), httpMethod(), isReadMethod() (+1 more)

### Community 152 - "get_quota_tracker"
Cohesion: 0.22
Nodes (3): get_quota_tracker(), llm_stats(), receive_telemetry()

### Community 162 - "validate-mutations.sh"
Cohesion: 0.57
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

### Community 165 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 167 - "state.js"
Cohesion: 0.33
Nodes (4): { AGENT_ROLE }, _blackboardTurns, _inboundMessages, _teammateMessages

### Community 177 - "TicketNode.tsx"
Cohesion: 0.40
Nodes (4): STATUS_COLORS, TICKET_COLORS, TicketNodeComponent(), TicketNodeData

### Community 178 - "classify"
Cohesion: 0.50
Nodes (4): classify(), main(), shellCategory(), shellNeedsGuard()

### Community 189 - "overrides"
Cohesion: 0.67
Nodes (3): overrides, @typescript-eslint/typescript-estree, minimatch

## Knowledge Gaps
- **13 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+8 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2230 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **108 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `models.py`, `brain.py`, `Brain`, `EventDocument`, `FastAPI`, `EventEvidence`, `os`, `main.py`, `BrainSkillLoader`, `dependencies.py`, `observations_mgmt.py`, `slack.py`, `nightwatcher_tools.py`, `_is_event_closed_or_missing`, `ScheduleRepository`, `ConversationTurn`, `event_to_markdown`, `jenkins_observer.py`, `queue.py`, `AgentRegistry`, `get_archivist`, `LiveAPIAdapter`, `UserContext`, `state/__init__.py`, `NightwatcherObserver`, `tool_router.py`, `HeadhunterJira`, `DashboardWSAdapter`, `.get_event`, `close_event_by_user`, `list_active_events`, `.list_observations`?**
  _High betweenness centrality (0.101) - this node is a cross-community bridge._
- **Are the 80 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 80 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.012380122057541413 - nodes in this community are weakly interconnected._
- **Why does `Brain` connect `Brain` to `BlackboardState`, `models.py`, `brain.py`, `EventDocument`, `EventEvidence`, `ReconcileScheduler`, `._post_agent_recall`, `main.py`, `._run_agent_task`, `BrainSkillLoader`, `._process_with_llm`, `dependencies.py`, `slack.py`, `ConversationTurn`, `._close_and_broadcast`, `StateWatcher`, `quota_tracker.py`, `PulseBatch`, `DashboardWSAdapter`, `ReflexSearcher`, `IdleTimeoutManager`, `BrainLifecyclePort`?**
  _High betweenness centrality (0.066) - this node is a cross-community bridge._
- **Are the 21 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 21 INFERRED edges - model-reasoned connections that need verification._
- **Should `models.py` be split into smaller, more focused modules?**
  _Cohesion score 0.02824646919135108 - nodes in this community are weakly interconnected._