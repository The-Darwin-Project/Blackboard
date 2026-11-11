# Graph Report - Blackboard  (2026-11-11)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 5121 nodes · 11449 edges · 214 communities (102 shown, 112 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 947 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `7c241204`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- main.py
- logging
- BlackboardState
- Archivist
- queue.py
- client.ts
- WorkspaceInspector.tsx
- EventSidebar.tsx
- Brain
- nightwatcher_tools.py
- tool_gates.py
- OpsStateContext.tsx
- App.tsx
- ._run_agent_task
- os
- AgentRegistry
- react
- http-handler.js
- cognitive_graph.py
- ReconcileScheduler
- jenkins-mcp.js
- EventHistory.tsx
- .get_graph_data
- TurnBubble.tsx
- Aligner
- BrainSkillLoader
- EventDocument
- _BrainToolContext
- ToolContext
- merge-guard.js
- ConversationTurn
- observations_mgmt.py
- GitLabPlatform
- JarvisMemoryPage.tsx
- cli-executor.js
- storage-recycler.js
- brain.py
- ._process_with_llm
- SlackChannel
- JenkinsAdapter
- EventRepository
- handlers_integration.py
- EventEvidence
- EventDrillDown.tsx
- GitHubPlatform
- formatter.py
- dashboard_ws.py
- TimeKeeperPage.tsx
- gemini_client.py
- event_namer.py
- Headhunter
- ws-client.js
- ui/package.json
- ._build_contents
- TopologyRepository
- useCortexData.ts
- CortexGraph.tsx
- KnowledgeGraphStore
- slack.py
- LiveAPIAdapter
- server.js
- StateWatcher
- .list_observations
- NodeInspector.tsx
- GeminiAdapter
- state/ports.py
- ArgoCDObserver
- create_schedule
- GridTile.tsx
- get_brain
- ._get_manager
- KargoObserver
- GitHubAppAuth
- dependencies
- quota_tracker.py
- event_to_markdown
- adf_to_markdown
- compilerOptions
- claude-guard.js
- BrainIntrospectionPort
- reconcile.py
- VcsPlatformPort
- PulseBatch
- cli-setup.js
- ReflexSearcher
- devDependencies
- compilerOptions
- gemini-sidecar/package.json
- ServiceNode.tsx
- EphemeralProvisioner
- get_report
- NeuronInfoPanel.tsx
- handle_classify_event
- JenkinsObserver
- ObservationRepository
- ShiftsPage.tsx
- catalog-skills.js
- ArchitectureGraph.tsx
- ClaudeAdapter
- UserContext
- EscalationRepository
- generate_map.py
- handlers_planning.py
- OIDCKeyAdapter
- KubernetesSpawnHealthAdapter
- IdleTimeoutManager
- graph_recall.py
- ._github_poll_and_process
- _append_user_turn
- ScheduleRepository
- MultiInstallationManager
- analyzeTokens
- TokenMeter
- ScheduleCreateRequest
- HeadhunterJira
- _sanitize_analysis_text
- testSetup.ts
- is_defer_event_available
- create_chat_event
- cortex-constants.ts
- spawn_health.py
- gitGuard
- parseShell
- ._post_agent_recall
- ._process_candidates
- _prepare_console_tail
- has_unevaluated_close_blocker
- CortexDevPage.tsx
- classifyTool
- get_quota_tracker
- SpawnPollResult
- SmartsheetMaintainerCache
- .has_reeval_signal
- get_event_document
- AsyncGitHubClient
- GitLabTokenAuth
- _is_event_closed_or_missing
- ._evaluate_health
- ._triage_and_build_evidence
- ._drain_once
- ConversationMessage
- TimeKeeperObserver
- CortexRepository
- validate-mutations.sh
- update_schedule
- update_notebook_note
- scripts
- state.js
- ._process_message
- DispatchMetrics
- ._wait_for_registration
- submit_feedback
- get_notebook
- TicketNode.tsx
- classify
- derive_llm_priority
- delete_notebook_note
- require-results.sh
- TokenUsageDict
- report_tampering
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
3. `ConversationTurn` - 125 edges
4. `ToolContext` - 103 edges
5. `GateContext` - 94 edges
6. `react` - 85 edges
7. `EventDocument` - 79 edges
8. `fetchApi()` - 66 edges
9. `lifespan()` - 65 edges
10. `LiveAPIAdapter` - 58 edges

## Surprising Connections (you probably didn't know these)
- `AgentClient` --uses--> `SecurityError`  [INFERRED]
  src/agents/base_client.py → src/agents/security.py
- `agent_websocket_handler()` --uses--> `TaskBridge`  [INFERRED]
  src/agents/agent_ws_handler.py → src/agents/task_bridge.py
- `consume_wake_task()` --uses--> `TaskBridge`  [INFERRED]
  src/agents/dispatch.py → src/agents/task_bridge.py
- `dispatch_to_agent()` --uses--> `TaskBridge`  [INFERRED]
  src/agents/dispatch.py → src/agents/task_bridge.py
- `send_cancel()` --uses--> `TaskBridge`  [INFERRED]
  src/agents/dispatch.py → src/agents/task_bridge.py

## Import Cycles
- None detected.

## Communities (214 total, 112 thin omitted)

### Community 0 - "main.py"
Cohesion: 0.02
Nodes (37): Architect, AgentClient, Developer, set_incident_options(), SysAdmin, TaskBridge, set_oidc_adapter(), get_aligner() (+29 more)

### Community 1 - "logging"
Cohesion: 0.03
Nodes (35): _annotation_replace(), _strip_pipeline_annotations(), _sanitize_lesson_text(), _parse_job_metadata(), create_adapter(), record_token_usage(), AppNode, ChatRequest (+27 more)

### Community 3 - "Archivist"
Cohesion: 0.04
Nodes (5): Archivist, Pulse, _decode_cursor(), _encode_cursor(), VectorStore

### Community 4 - "queue.py"
Cohesion: 0.04
Nodes (47): get_token_meter(), can_override_domain(), can_rename_event(), get_archivist(), EventStatus, aligner_pending_items(), apply_lessons(), close_event_by_user() (+39 more)

### Community 5 - "client.ts"
Cohesion: 0.04
Nodes (77): recharts, ApiError, bulkDeleteObservations(), deleteObservation(), exportObservations(), ExtractedCorrection, ExtractedLesson, ExtractionResult (+69 more)

### Community 6 - "WorkspaceInspector.tsx"
Cohesion: 0.05
Nodes (71): updateEventTitle(), AgentRegistryEntry, CiContext, ConversationTurn, TokenUsageDict, CiContextCard(), CiContextCardProps, ConsoleTailBlock() (+63 more)

### Community 7 - "EventSidebar.tsx"
Cohesion: 0.06
Nodes (78): getAlignerPending(), getHeadhunterPending(), getJenkinsPending(), getJiraMissions(), getWaitingApprovalEvents(), HeadhunterTodo, postJiraAction(), EventDocument (+70 more)

### Community 9 - "nightwatcher_tools.py"
Cohesion: 0.05
Nodes (32): PulseContext, ShiftIncident, ShiftInvestigation, _append_user_turn(), _env_float(), _env_int(), NightwatcherObserver, _finalize_analysis_handover() (+24 more)

### Community 10 - "tool_gates.py"
Cohesion: 0.05
Nodes (78): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+70 more)

### Community 11 - "OpsStateContext.tsx"
Cohesion: 0.06
Nodes (55): react-router-dom, @tanstack/react-query, createChatEvent(), getActiveEvents(), getEventDocument(), getEvents(), getKargoStages(), KargoStageStatus (+47 more)

### Community 12 - "App.tsx"
Cohesion: 0.05
Nodes (55): oidc-client-ts, getConfig(), getFlowHistory(), getIncidents(), getWSAuthFailureCallback(), Incident, setOnUnauthorized(), setTokenGetter() (+47 more)

### Community 13 - "._run_agent_task"
Cohesion: 0.05
Nodes (10): on_huddle(), on_progress(), on_huddle(), on_progress(), _has_non_user_turns(), _is_automated_nudge(), _sanitize_error_text(), _sanitize_override_reason() (+2 more)

### Community 14 - "os"
Cohesion: 0.05
Nodes (17): JiraIncidentAdapter, _get_static_maintainer_emails(), _get_allowed_mention_authors(), _get_static_maintainer_emails(), _safe_int(), dex_proxy(), list_incidents(), approve_mission() (+9 more)

### Community 15 - "AgentRegistry"
Cohesion: 0.04
Nodes (18): AgentConnection, AgentRegistry, agent_websocket_handler(), _heartbeat(), _build_prompt(), _check_security(), consume_wake_task(), _consume() (+10 more)

### Community 16 - "react"
Cohesion: 0.07
Nodes (60): lucide-react, react, applyLessons(), correctMemory(), createKnowledge(), createLesson(), deleteKnowledge(), deleteLesson() (+52 more)

### Community 17 - "http-handler.js"
Cohesion: 0.08
Nodes (62): is429Error(), registerMCPsAndHooks(), resolveCommand(), writeAgyMcpServer(), writeClaudeMcpServer(), parsePositiveInt(), buildArgoCDMcpConfig(), createAppJWT() (+54 more)

### Community 18 - "cognitive_graph.py"
Cohesion: 0.05
Nodes (22): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship, get_blackboard(), get_kg_store(), get_pulse_tracker() (+14 more)

### Community 19 - "ReconcileScheduler"
Cohesion: 0.04
Nodes (7): FlowCollector, FairQueue, ReconcileScheduler, Trigger, QueueTrigger, ResyncTrigger, StalenessGuard

### Community 20 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 21 - "EventHistory.tsx"
Cohesion: 0.07
Nodes (38): getReport(), getReports(), ReportFull, ReportMeta, SubjectType, CompactCardStrip(), EventHistory(), TimeRange (+30 more)

### Community 22 - ".get_graph_data"
Cohesion: 0.05
Nodes (7): get_graph_data(), get_mermaid_diagram(), get_service_details(), get_topology(), list_services(), calculate_health_from_argocd(), infer_node_type()

### Community 23 - "TurnBubble.tsx"
Cohesion: 0.09
Nodes (40): @uiw/react-markdown-preview, approveEvent(), closeEvent(), enforceCasualDomain(), rejectEvent(), submitFeedback(), CollapsibleSection(), CollapsibleSectionProps (+32 more)

### Community 25 - "BrainSkillLoader"
Cohesion: 0.05
Nodes (3): BrainSkillLoader, _SkillCorpus, _wrap_section()

### Community 28 - "ToolContext"
Cohesion: 0.08
Nodes (11): handle_message_agent(), handle_reply_to_agent(), handle_report_incident(), handle_select_agent(), _resolve_escalation_scope(), _sticky_work_style(), handle_defer_event(), handle_hold_watch() (+3 more)

### Community 29 - "merge-guard.js"
Cohesion: 0.04
Nodes (46): API_VALUED, ARGO_MUTATING, ARGO_READ_SUB, ARGO_READ_TOP, BODY_FLAG, BROWSER_READ, CTX, ENV_BUILTINS (+38 more)

### Community 30 - "ConversationTurn"
Cohesion: 0.13
Nodes (31): emit_tool_result(), _safe_int(), handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_recall_pruned_turns(), handle_ask_release_ai(), handle_comment_jira_issue() (+23 more)

### Community 31 - "observations_mgmt.py"
Cohesion: 0.06
Nodes (18): get_report_client(), _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), render_pdf(), _sample_points() (+10 more)

### Community 33 - "JarvisMemoryPage.tsx"
Cohesion: 0.09
Nodes (37): dismissProposals(), EnhancementProposal, getFlowMetrics(), getHandoffReports(), getProposals(), HandoffReport, FlowMetrics, Dashboard() (+29 more)

### Community 34 - "cli-executor.js"
Cohesion: 0.09
Nodes (37): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, MAX_TASK_WALL_MS, MAX_TIMER_MS, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS, STORAGE_PRETASK_TIMEOUT_MS, resolveStorageRoot }, buildCLICommand(), buildTimeoutResult(), { checkAndRecycleStorage, pinTaskCwd, unpinTaskCwd }, CLAUDE_JSON_PATH, cp, createInactivityWatchdog(), executeCLI() (+29 more)

### Community 35 - "storage-recycler.js"
Cohesion: 0.08
Nodes (37): withTaskStorage(), MAX_TASK_WALL_MS, parseTimerMs(), resolveStorageRoot(), resolveTimeoutMs(), ROLE_TIMEOUTS, STORAGE_ACTIVITY_HEARTBEAT_MS, STORAGE_MAX_TIER3_DELETIONS (+29 more)

### Community 36 - "brain.py"
Cohesion: 0.07
Nodes (15): _compute_processed_up_to(), _is_seed_turn(), _apply_sibling_signature(), build_function_response(), build_single_function_response(), compress_contents(), estimate_msg_tokens(), estimate_tokens() (+7 more)

### Community 38 - "SlackChannel"
Cohesion: 0.07
Nodes (4): extract_tables(), get_agent_notification_text(), get_turn_attachment_color(), SlackChannel

### Community 39 - "JenkinsAdapter"
Cohesion: 0.06
Nodes (6): BuildDetails, JenkinsAdapter, JenkinsPlatformPort, JobResult, JobRunState, ViewScanResult

### Community 41 - "handlers_integration.py"
Cohesion: 0.08
Nodes (17): _alert_wrapper_retrigger(), _do_retrigger(), _get_jira_reporter(), handle_refresh_github_context(), handle_refresh_gitlab_context(), handle_refresh_kargo_context(), _is_darwin_reentrant_caller(), _resolve_maintainer_enum() (+9 more)

### Community 42 - "EventEvidence"
Cohesion: 0.10
Nodes (10): spawn_event_namer_task(), handle_app_home_opened(), handle_app_mention(), handle_create_event_modal(), handle_darwin_command(), handle_home_create_event(), handle_reject(), on_dm_message() (+2 more)

### Community 43 - "EventDrillDown.tsx"
Cohesion: 0.09
Nodes (34): three, getEventPulses(), EventSource, BrainCore(), CortexDevPage(), CortexHeartbeat(), CortexHeartbeatProps, ensureKeyframes() (+26 more)

### Community 45 - "formatter.py"
Cohesion: 0.08
Nodes (17): build_access_denied_home_view(), build_home_tab_view(), _context_line(), create_feedback_block(), _replace(), format_event_summary(), format_plan_block(), format_task_card() (+9 more)

### Community 46 - "dashboard_ws.py"
Cohesion: 0.08
Nodes (9): DashboardWSAdapter, can_append_message(), can_approve_event(), _normalize_email(), prompt_display_name(), resolve_approval_identity(), handle_approve(), resolve_live_head_sha() (+1 more)

### Community 47 - "TimeKeeperPage.tsx"
Cohesion: 0.12
Nodes (24): createSchedule(), deleteSchedule(), getSchedules(), refineInstructions(), ScheduleCreatePayload, ScheduleItem, toggleSchedule(), updateSchedule() (+16 more)

### Community 48 - "gemini_client.py"
Cohesion: 0.11
Nodes (10): _extract_call_syntax(), FunctionCall, LLMChunk, LLMPort, LLMResponse, process_stream_call_syntax_buffer(), sanitize_call_syntax(), scan_call_syntax() (+2 more)

### Community 49 - "event_namer.py"
Cohesion: 0.09
Nodes (14): generate_event_title(), get_adapter(), _get_semaphore(), _build_closed_block(), build_event_header(), _build_identity_block(), _build_journal_block(), _build_mermaid_block() (+6 more)

### Community 51 - "ws-client.js"
Cohesion: 0.10
Nodes (26): clearIdleTimer(), {
  DEFAULT_WORK_DIR, AGENT_CLI, AGENT_MODEL, AGENT_ROLE,
  EVENT_ID, EPHEMERAL, IDLE_TIMEOUT_MS,
  CLI_429_MAX_RETRIES, CLI_429_INITIAL_DELAY_MS, CLI_429_BACKOFF_MULTIPLIER,
  resolveTimeoutMs, parsePositiveInt, MAX_TASK_WALL_MS, MAX_TIMER_MS,
}, { ensureEventDocument }, { executeCLIStreaming, prepareResultsDir, is429Error }, { filterSkillsByRole, filterSkillsByMode, swapActiveRules, restoreAllSkills }, fs, handleCancel(), handleTask() (+18 more)

### Community 52 - "ui/package.json"
Cohesion: 0.08
Nodes (29): autoprefixer, cronstrue, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, graphology-layout-forceatlas2 (+21 more)

### Community 53 - "._build_contents"
Cohesion: 0.07
Nodes (4): _close_unanswered_fc(), compute_dispatch_backpressure(), ContextFlags, _safe_int_env()

### Community 54 - "TopologyRepository"
Cohesion: 0.08
Nodes (4): Service, Snapshot, TopologySnapshot, TopologyRepository

### Community 55 - "useCortexData.ts"
Cohesion: 0.17
Nodes (27): getCognitiveGraph(), getCortexActivity(), getEventReport(), getKGServiceDetail(), getKGServices(), getKGStats(), getKnowledgeById(), getMemory() (+19 more)

### Community 56 - "CortexGraph.tsx"
Cohesion: 0.13
Nodes (26): graphology, sigma, eventColor(), getExecutiveNeurons(), getStructuralEdges(), DEFAULT_TYPE_BUDGET, evictLru(), KNOWLEDGE_RING (+18 more)

### Community 57 - "KnowledgeGraphStore"
Cohesion: 0.15
Nodes (4): _acquire(), KnowledgeGraphStore, _sanitize(), _with_timeout()

### Community 58 - "slack.py"
Cohesion: 0.09
Nodes (4): table_block_to_code_block(), _PlanDecision, _mask_email(), SlackAccessGate

### Community 60 - "server.js"
Cohesion: 0.09
Nodes (18): { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, ensureEventDocument(), fs, path, stageEventDocument(), fetchEventDocument(), fs, { handleRequest } (+10 more)

### Community 61 - "StateWatcher"
Cohesion: 0.10
Nodes (3): _QueueEntry, StateWatcher, _Subscription

### Community 62 - ".list_observations"
Cohesion: 0.08
Nodes (4): get_all_journal(), get_service_journal(), get_event_observations(), get_global_observations()

### Community 63 - "NodeInspector.tsx"
Cohesion: 0.13
Nodes (23): getClosedEvents(), ArchitectureEvent, ArgoCDOperation, ArchitectureGraph(), EVENT_LABELS, EventItem(), EventItemProps, healthTone() (+15 more)

### Community 65 - "state/ports.py"
Cohesion: 0.11
Nodes (6): ArchitectureEvent, EventType, HealthStatus, MessageStatus, NodeType, MetricsRepository

### Community 67 - "create_schedule"
Cohesion: 0.08
Nodes (5): create_schedule(), delete_schedule(), get_schedule(), list_schedules(), toggle_schedule()

### Community 68 - "GridTile.tsx"
Cohesion: 0.14
Nodes (21): AgentStreamCard(), AgentStreamCardProps, MessageCards(), GridTile(), GridTileProps, TileType, InlineMarkdownViewer(), DEFAULT_POS (+13 more)

### Community 69 - "get_brain"
Cohesion: 0.10
Nodes (8): get_brain(), KargoStageSnapshot, list_failed_stages(), approve_event(), PlanStepRequest, reject_event(), RejectRequest, update_plan_step()

### Community 72 - "GitHubAppAuth"
Cohesion: 0.11
Nodes (3): _find_pem_file(), get_github_auth(), GitHubAppAuth

### Community 73 - "dependencies"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 74 - "quota_tracker.py"
Cohesion: 0.12
Nodes (4): QuotaExhaustedError, QuotaTracker, RequestExceedsBurstError, Reservation

### Community 75 - "event_to_markdown"
Cohesion: 0.13
Nodes (7): CIAnalysis, _esc(), _esc_join(), event_to_markdown(), maintainer_env_key(), resolve_maintainer_emails(), redact_pii()

### Community 76 - "adf_to_markdown"
Cohesion: 0.13
Nodes (9): _adf_to_text(), _escape_jql_string(), adf_to_markdown(), _apply_marks(), _children(), _render(), _render_list(), _render_list_item() (+1 more)

### Community 77 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 78 - "claude-guard.js"
Cohesion: 0.14
Nodes (18): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+10 more)

### Community 79 - "BrainIntrospectionPort"
Cohesion: 0.10
Nodes (3): BrainIntrospectionPort, BrainLifecyclePort, BroadcastPort

### Community 80 - "reconcile.py"
Cohesion: 0.18
Nodes (9): _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers(), main(), _parse_frontmatter() (+1 more)

### Community 82 - "PulseBatch"
Cohesion: 0.12
Nodes (4): PulseBatch, PulsePort, PulseObserver, PulseTracker

### Community 83 - "cli-setup.js"
Cohesion: 0.13
Nodes (18): { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync }, filterSkillsByMode() (+10 more)

### Community 85 - "devDependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

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

### Community 91 - "NeuronInfoPanel.tsx"
Cohesion: 0.16
Nodes (18): ActiveEvent, KGServiceDetail, KGServiceEntity, CortexGraphProps, GraphLoaderProps, asNumber(), asString(), asStringArray() (+10 more)

### Community 93 - "handle_classify_event"
Cohesion: 0.11
Nodes (4): handle_classify_event(), IdleTimeoutPort, IncidentAdapterPort, StateWatcherPort

### Community 96 - "ShiftsPage.tsx"
Cohesion: 0.23
Nodes (16): getCurrentShift(), getShiftDetail(), getShiftsList(), ShiftReportFull, ShiftReportSummary, FailedClusterBadge(), getISOWeek(), getWeekDates() (+8 more)

### Community 97 - "catalog-skills.js"
Cohesion: 0.16
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 98 - "ArchitectureGraph.tsx"
Cohesion: 0.18
Nodes (15): @dagrejs/dagre, applyDagreLayout(), applyGridLayout(), applyLayout(), ArchitectureGraphInner(), buildGraph(), computeIdHash(), edgeTypes (+7 more)

### Community 101 - "UserContext"
Cohesion: 0.16
Nodes (8): _claims_to_user(), get_user_from_request(), get_user_from_slack(), get_user_from_websocket(), require_auth(), require_obs_admin(), UserContext, _validate_jwt()

### Community 103 - "generate_map.py"
Cohesion: 0.19
Nodes (6): _enumerate_gates(), _GateInfo, generate_phase_tool_map(), _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 104 - "handlers_planning.py"
Cohesion: 0.22
Nodes (7): _auto_complete_step(), _canonical_role(), handle_create_plan(), handle_get_plan_progress(), _is_failed_turn(), _is_orchestrator_turn(), _normalize_step_id()

### Community 108 - "graph_recall.py"
Cohesion: 0.19
Nodes (5): _format_graph_context(), get_graph_context(), _parse_props(), _sanitize(), translate_to_lookups()

### Community 111 - "_append_user_turn"
Cohesion: 0.14
Nodes (5): _append_user_turn(), _coerce_part(), _is_function_response_part(), _strip_user_thought_signature(), _validated_parts()

### Community 114 - "analyzeTokens"
Cohesion: 0.19
Nodes (13): analyzeString(), analyzeTokens(), assignName(), base(), combineCategories(), configEnvGuard(), configFileWriteGuard(), hasSubseq() (+5 more)

### Community 120 - "_sanitize_analysis_text"
Cohesion: 0.20
Nodes (5): _clamp_confidence(), _sanitize_analysis_text(), _strip_newlines(), _validate_analysis(), _validate_triage_entry()

### Community 121 - "testSetup.ts"
Cohesion: 0.18
Nodes (5): @tailwindcss/vite, @testing-library/react, vite, @vitejs/plugin-react, vitest

### Community 122 - "is_defer_event_available"
Cohesion: 0.18
Nodes (6): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 123 - "create_chat_event"
Cohesion: 0.20
Nodes (3): ChatEventRequest, ChatEventResponse, create_chat_event()

### Community 124 - "cortex-constants.ts"
Cohesion: 0.18
Nodes (10): AGENTS, DOMAINS, HEMISPHERE_X, NEURON_DESCRIPTIONS, PHASE_SKILL_FOLDERS, PHASE_TOOL_PRIORITY, PHASES, StructuralEdge (+2 more)

### Community 126 - "gitGuard"
Cohesion: 0.29
Nodes (10): bareBranchProtected(), configWriteGuard(), externalGitCommand(), gitGuard(), gitQuery(), isProtected(), normRef(), pushGuard() (+2 more)

### Community 127 - "parseShell"
Cohesion: 0.33
Nodes (10): bodySubstitutions(), decodeAnsiC(), isArrayAssignPrefix(), isWordStart(), matchBacktick(), matchParen(), parseShell(), readHeredocStart() (+2 more)

### Community 132 - "_prepare_console_tail"
Cohesion: 0.20
Nodes (4): _prepare_console_tail(), _redact_match(), _redact_secrets_in_text(), _sanitize_console_tail()

### Community 133 - "has_unevaluated_close_blocker"
Cohesion: 0.20
Nodes (4): has_unevaluated_close_blocker(), _pred_jarvis_response(), _pred_unevaluated_close(), is_jarvis_acknowledgment()

### Community 134 - "CortexDevPage.tsx"
Cohesion: 0.36
Nodes (8): devQueryClient, MOCK_CORTEX_STATUS, MOCK_EVENT_ID, MOCK_NEURONS, MOCK_PULSE_BATCHES, MOCK_SHADOW, MOCK_THINKING, MOCK_WHISPERS

### Community 135 - "classifyTool"
Cohesion: 0.31
Nodes (9): apiTokens(), apiWriteNeedsGuard(), branchValues(), classifyTool(), hasOpaqueTarget(), httpGuard(), httpMethod(), isReadMethod() (+1 more)

### Community 136 - "get_quota_tracker"
Cohesion: 0.22
Nodes (3): get_quota_tracker(), llm_stats(), receive_telemetry()

### Community 151 - "validate-mutations.sh"
Cohesion: 0.57
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

### Community 155 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 156 - "state.js"
Cohesion: 0.33
Nodes (4): { AGENT_ROLE }, _blackboardTurns, _inboundMessages, _teammateMessages

### Community 170 - "TicketNode.tsx"
Cohesion: 0.40
Nodes (4): STATUS_COLORS, TICKET_COLORS, TicketNodeComponent(), TicketNodeData

### Community 171 - "classify"
Cohesion: 0.50
Nodes (4): classify(), main(), shellCategory(), shellNeedsGuard()

### Community 184 - "overrides"
Cohesion: 0.67
Nodes (3): overrides, @typescript-eslint/typescript-estree, minimatch

## Knowledge Gaps
- **13 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+8 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2245 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **112 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `main.py`, `logging`, `queue.py`, `Brain`, `nightwatcher_tools.py`, `get_event_document`, `os`, `_is_event_closed_or_missing`, `cognitive_graph.py`, `ConversationMessage`, `.get_graph_data`, `update_schedule`, `BrainSkillLoader`, `update_notebook_note`, `EventDocument`, `ConversationTurn`, `observations_mgmt.py`, `brain.py`, `._restage_pending_signal`, `._stage_pending_signal`, `submit_feedback`, `get_notebook`, `._count_pending`, `EventEvidence`, `dashboard_ws.py`, `delete_notebook_note`, `event_namer.py`, `.cleanup_stale_services`, `._downsample_snapshots`, `.drain_notes`, `.get_edge_metadata`, `TopologyRepository`, `report_tampering`, `slack.py`, `LiveAPIAdapter`, `.list_observations`, `state/ports.py`, `create_schedule`, `get_brain`, `.close_event`, `.delete_slack_mapping`, `.get_all_closed_event_ids`, `get_report`, `ScheduleRepository`, `HeadhunterJira`, `create_chat_event`?**
  _High betweenness centrality (0.092) - this node is a cross-community bridge._
- **Are the 80 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 80 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `main.py` be split into smaller, more focused modules?**
  _Cohesion score 0.02109181141439206 - nodes in this community are weakly interconnected._
- **Why does `Brain` connect `Brain` to `._post_agent_recall`, `main.py`, `BlackboardState`, `Archivist`, `queue.py`, `._run_agent_task`, `ReconcileScheduler`, `BrainSkillLoader`, `EventDocument`, `ConversationTurn`, `brain.py`, `._process_with_llm`, `EventEvidence`, `dashboard_ws.py`, `._build_contents`, `slack.py`, `StateWatcher`, `state/ports.py`, `quota_tracker.py`, `BrainIntrospectionPort`, `PulseBatch`, `ReflexSearcher`, `IdleTimeoutManager`?**
  _High betweenness centrality (0.063) - this node is a cross-community bridge._
- **Are the 21 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 21 INFERRED edges - model-reasoned connections that need verification._
- **Should `logging` be split into smaller, more focused modules?**
  _Cohesion score 0.028180969357439946 - nodes in this community are weakly interconnected._