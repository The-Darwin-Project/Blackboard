# Graph Report - Blackboard  (2026-11-19)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 5427 nodes · 12204 edges · 216 communities (113 shown, 103 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 971 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `fa918c40`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BlackboardState
- os
- EventSidebar.tsx
- queue.py
- Archivist
- client.ts
- nightwatcher_tools.py
- App.tsx
- tool_gates.py
- TopologyRepository
- Brain
- GitHubPlatform
- ._run_agent_task
- WorkspaceInspector.tsx
- react
- http-handler.js
- state/ports.py
- WebSocketContext.tsx
- HeadhunterJira
- dispatch.py
- jenkins-mcp.js
- TurnBubble.tsx
- EventRepository
- brain.py
- EventDocument
- BrainSkillLoader
- models.py
- slack.py
- _BrainToolContext
- ToolContext
- Headhunter
- ._process_with_llm
- ConversationTurn
- merge-guard.js
- auth.py
- AgentRegistry
- observations_mgmt.py
- GitLabPlatform
- hooks/index.ts
- ScheduleCreateRequest
- cli-executor.js
- storage-recycler.js
- SlackChannel
- OpsStateContext.tsx
- llm/__init__.py
- EventEvidence
- handlers_integration.py
- GeminiAdapter
- CortexGraph.tsx
- Aligner
- httpx
- main.py
- jenkins_observer.py
- lifespan
- TimeKeeperPage.tsx
- KnowledgeGraphStore
- ws-client.js
- jira_incident.py
- types.py
- ui/package.json
- EventDrillDown.tsx
- _resolve_phase
- cognitive_graph.py
- create_adapter
- server.js
- .list_observations
- useCortexData.ts
- scheduling/__init__.py
- LiveAPIAdapter
- archivist.py
- JenkinsObserver
- ArgoCDObserver
- reconcile.py
- BrainIntrospectionPort
- KargoObserver
- GitHubAppAuth
- dependencies
- StateWatcher
- JenkinsAdapter
- compilerOptions
- time
- claude-guard.js
- ._build_contents
- .start_event_loop
- ArchitectureGraph.tsx
- FlowHistoryPage.tsx
- VcsPlatformPort
- cli-setup.js
- ReflexSearcher
- gemini_client.py
- FairQueue
- devDependencies
- compilerOptions
- gemini-sidecar/package.json
- entity_extractor.py
- DashboardWSAdapter
- EphemeralProvisioner
- get_report
- .fetch_context
- ObservationRepository
- ShiftsPage.tsx
- catalog-skills.js
- handlers_lookup.py
- JenkinsPlatformPort
- OIDCKeyAdapter
- JarvisPeerPort
- cortex/types.ts
- TokenMeter
- generate_map.py
- KubernetesSpawnHealthAdapter
- IdleTimeoutManager
- ReconcileScheduler
- RedisClient
- ServiceNode.tsx
- generate_event_title
- ._connect
- handlers_planning.py
- ._process_candidates
- MultiInstallationManager
- analyzeTokens
- ._poll_and_stage
- FilterRule
- ._extract_context_flags
- NeuronInfoPanel.tsx
- ._process_message
- IncidentAdapterPort
- handlers_dispatch.py
- testSetup.ts
- _resolve_domain
- is_defer_event_available
- PulseTracker
- SlackAccessGate
- spawn_health.py
- gitGuard
- parseShell
- ._tool_send_event_message
- ._post_agent_recall
- has_unevaluated_close_blocker
- knowledge_graph_api.py
- CortexDevPage.tsx
- classifyTool
- get_quota_tracker
- SpawnPollResult
- SmartsheetMaintainerCache
- Trigger
- AsyncGitHubClient
- GitLabTokenAuth
- useDeferCountdown.ts
- _is_event_closed_or_missing
- ._evaluate_health
- LLMStreamInterChunkTimeoutError
- TimeKeeperObserver
- validate-mutations.sh
- ._detect_repetition_collapse
- _format_graph_context
- update_notebook_note
- scripts
- state.js
- DispatchMetrics
- build_gate_context
- resolve_live_head_sha
- ._wait_for_registration
- submit_feedback
- get_notebook
- StalenessGuard
- ResyncTrigger
- classify
- Reservation
- _patch_enum_fields
- list_incidents
- require-results.sh
- get_intermediate_tools
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
- diagnose_rejection
- GateDefinition
- _pred_dispatch_defer
- _pred_hard_strip_defer
- _pred_idle_agent_wait
- _pred_jarvis_wait
- _pred_obs_plateau
- _pred_silent_park
- _tools_wait_loop

## God Nodes (most connected - your core abstractions)
1. `BlackboardState` - 298 edges
2. `Brain` - 168 edges
3. `ConversationTurn` - 131 edges
4. `ToolContext` - 103 edges
5. `GateContext` - 99 edges
6. `react` - 85 edges
7. `EventDocument` - 84 edges
8. `GitHubPlatform` - 73 edges
9. `fetchApi()` - 66 edges
10. `lifespan()` - 65 edges

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

## Communities (216 total, 103 thin omitted)

### Community 1 - "os"
Cohesion: 0.03
Nodes (18): _csv_env(), _get_static_maintainer_emails(), _iso(), _mention_pattern(), _parse_ts(), _review_ignore_logins(), _review_trusted_associations(), _get_allowed_mention_authors() (+10 more)

### Community 2 - "EventSidebar.tsx"
Cohesion: 0.04
Nodes (114): getActiveEvents(), getAlignerPending(), getEventDocument(), getHeadhunterPending(), getJenkinsPending(), getJiraMissions(), getWaitingApprovalEvents(), HeadhunterTodo (+106 more)

### Community 3 - "queue.py"
Cohesion: 0.04
Nodes (52): get_token_meter(), get_archivist(), get_brain(), EventStatus, aligner_pending_items(), apply_lessons(), approve_event(), close_event_by_user() (+44 more)

### Community 4 - "Archivist"
Cohesion: 0.04
Nodes (4): Archivist, _decode_cursor(), _encode_cursor(), VectorStore

### Community 5 - "client.ts"
Cohesion: 0.04
Nodes (87): oidc-client-ts, bulkDeleteObservations(), deleteObservation(), exportObservations(), ExtractedCorrection, ExtractedLesson, ExtractionResult, generateObservationsReport() (+79 more)

### Community 6 - "nightwatcher_tools.py"
Cohesion: 0.04
Nodes (36): record_token_usage(), RequestExceedsBurstError, ShiftIncident, ShiftInvestigation, ShiftReport, _append_user_turn(), _env_float(), _env_int() (+28 more)

### Community 7 - "App.tsx"
Cohesion: 0.05
Nodes (63): react-dom, react-router-dom, @tanstack/react-query, getIncidents(), getReport(), getReports(), Incident, ReportFull (+55 more)

### Community 8 - "tool_gates.py"
Cohesion: 0.05
Nodes (79): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+71 more)

### Community 9 - "TopologyRepository"
Cohesion: 0.04
Nodes (12): GraphResponse, Service, Snapshot, TopologySnapshot, get_graph_data(), get_mermaid_diagram(), get_service_details(), get_topology() (+4 more)

### Community 11 - "GitHubPlatform"
Cohesion: 0.04
Nodes (4): GitHubPlatform, _poll_one(), _one(), _poll_one()

### Community 12 - "._run_agent_task"
Cohesion: 0.05
Nodes (10): on_huddle(), on_progress(), on_huddle(), on_progress(), _is_automated_nudge(), _is_participant_turn(), _sanitize_error_text(), _sanitize_override_reason() (+2 more)

### Community 13 - "WorkspaceInspector.tsx"
Cohesion: 0.06
Nodes (58): updateEventTitle(), ConversationTurn, AgentStreamCard(), AgentStreamCardProps, MessageCards(), BORDER_COLOR, PlanProgress(), PlanProgressProps (+50 more)

### Community 14 - "react"
Cohesion: 0.07
Nodes (61): lucide-react, react, applyLessons(), correctMemory(), createKnowledge(), createLesson(), deleteKnowledge(), deleteLesson() (+53 more)

### Community 15 - "http-handler.js"
Cohesion: 0.08
Nodes (62): is429Error(), registerMCPsAndHooks(), resolveCommand(), writeAgyMcpServer(), writeClaudeMcpServer(), parsePositiveInt(), buildArgoCDMcpConfig(), createAppJWT() (+54 more)

### Community 16 - "state/ports.py"
Cohesion: 0.04
Nodes (9): ArchitectureEvent, EventType, ScheduledEvent, get_event_document(), list_events(), CortexRepository, EscalationRepository, MetricsRepository (+1 more)

### Community 17 - "WebSocketContext.tsx"
Cohesion: 0.06
Nodes (51): dismissProposals(), EnhancementProposal, getFlowMetrics(), getHandoffReports(), getProposals(), getWSAuthFailureCallback(), HandoffReport, FlowMetrics (+43 more)

### Community 18 - "HeadhunterJira"
Cohesion: 0.05
Nodes (3): HeadhunterJira, _walk_adf_mentions(), _walk()

### Community 19 - "dispatch.py"
Cohesion: 0.05
Nodes (9): Architect, AgentClient, Developer, _check_security(), safe_execution(), wrapper(), SecurityError, SysAdmin (+1 more)

### Community 20 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 21 - "TurnBubble.tsx"
Cohesion: 0.07
Nodes (45): @uiw/react-markdown-preview, approveEvent(), closeEvent(), enforceCasualDomain(), getEventReport(), rejectEvent(), submitFeedback(), ChatInputProps (+37 more)

### Community 23 - "brain.py"
Cohesion: 0.06
Nodes (24): _close_unanswered_fc(), _compute_processed_up_to(), _contents_have_pruned_or_decayed(), _has_non_user_turns(), _is_external_input_turn(), _is_seed_turn(), _is_steering_turn(), _apply_sibling_signature() (+16 more)

### Community 25 - "BrainSkillLoader"
Cohesion: 0.05
Nodes (4): _parse_positive_int_env(), BrainSkillLoader, _SkillCorpus, _wrap_section()

### Community 26 - "models.py"
Cohesion: 0.05
Nodes (20): AppNode, ChatRequest, ChatResponse, EventInput, EventMetrics, GraphEdge, GraphNode, HealthResponse (+12 more)

### Community 27 - "slack.py"
Cohesion: 0.06
Nodes (20): build_access_denied_home_view(), build_home_tab_view(), _context_line(), create_feedback_block(), _replace(), format_event_summary(), format_plan_block(), format_task_card() (+12 more)

### Community 29 - "ToolContext"
Cohesion: 0.07
Nodes (11): handle_message_agent(), handle_reply_to_agent(), handle_select_agent(), _sticky_work_style(), _alert_wrapper_retrigger(), _do_retrigger(), handle_defer_event(), handle_hold_watch() (+3 more)

### Community 31 - "._process_with_llm"
Cohesion: 0.05
Nodes (4): _BatchContext, _ensure_recall_tool_if_needed(), _QuotaShedState, _retry_backoff_delay()

### Community 32 - "ConversationTurn"
Cohesion: 0.12
Nodes (28): emit_tool_result(), handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_report_incident(), _resolve_escalation_scope(), handle_comment_jira_issue(), handle_fetch_jira_issue() (+20 more)

### Community 33 - "merge-guard.js"
Cohesion: 0.04
Nodes (46): API_VALUED, ARGO_MUTATING, ARGO_READ_SUB, ARGO_READ_TOP, BODY_FLAG, BROWSER_READ, CTX, ENV_BUILTINS (+38 more)

### Community 34 - "auth.py"
Cohesion: 0.07
Nodes (17): can_append_message(), can_approve_event(), can_override_domain(), can_rename_event(), _claims_to_user(), get_user_from_request(), get_user_from_slack(), get_user_from_websocket() (+9 more)

### Community 35 - "AgentRegistry"
Cohesion: 0.06
Nodes (11): AgentConnection, AgentRegistry, _build_prompt(), consume_wake_task(), _consume(), _dispatch_timeout_s(), dispatch_to_agent(), _consume_queue() (+3 more)

### Community 36 - "observations_mgmt.py"
Cohesion: 0.06
Nodes (18): get_report_client(), _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), render_pdf(), _sample_points() (+10 more)

### Community 38 - "hooks/index.ts"
Cohesion: 0.08
Nodes (35): ApiError, createChatEvent(), getClosedEvents(), getEvents(), getService(), getTopology(), ArchitectureEvent, ArgoCDOperation (+27 more)

### Community 39 - "ScheduleCreateRequest"
Cohesion: 0.05
Nodes (7): ScheduleCreateRequest, create_schedule(), delete_schedule(), get_schedule(), list_schedules(), toggle_schedule(), update_schedule()

### Community 40 - "cli-executor.js"
Cohesion: 0.09
Nodes (37): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, MAX_TASK_WALL_MS, MAX_TIMER_MS, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS, STORAGE_PRETASK_TIMEOUT_MS, resolveStorageRoot }, buildCLICommand(), buildTimeoutResult(), { checkAndRecycleStorage, pinTaskCwd, unpinTaskCwd }, CLAUDE_JSON_PATH, cp, createInactivityWatchdog(), executeCLI() (+29 more)

### Community 41 - "storage-recycler.js"
Cohesion: 0.08
Nodes (37): withTaskStorage(), MAX_TASK_WALL_MS, parseTimerMs(), resolveStorageRoot(), resolveTimeoutMs(), ROLE_TIMEOUTS, STORAGE_ACTIVITY_HEARTBEAT_MS, STORAGE_MAX_TIER3_DELETIONS (+29 more)

### Community 42 - "SlackChannel"
Cohesion: 0.07
Nodes (4): extract_tables(), get_agent_notification_text(), get_turn_attachment_color(), SlackChannel

### Community 43 - "OpsStateContext.tsx"
Cohesion: 0.08
Nodes (30): getAgents(), AgentRegistryEntry, EventEvidence, AgentRegistryPanel(), formatConnectedSince(), ErrorBoundary, ErrorBoundaryProps, ErrorBoundaryState (+22 more)

### Community 44 - "llm/__init__.py"
Cohesion: 0.08
Nodes (7): ClaudeAdapter, _parse_tpm_limit(), FunctionCall, LLMChunk, LLMPort, LLMResponse, TokenUsage

### Community 45 - "EventEvidence"
Cohesion: 0.11
Nodes (10): spawn_event_namer_task(), handle_app_home_opened(), handle_app_mention(), handle_create_event_modal(), handle_darwin_command(), handle_home_create_event(), handle_reject(), on_dm_message() (+2 more)

### Community 46 - "handlers_integration.py"
Cohesion: 0.07
Nodes (15): _coerce_turn_int(), handle_recall_pruned_turns(), _parse_turn_int(), _sanitize_recalled(), _get_jira_reporter(), handle_ask_release_ai(), _is_darwin_reentrant_caller(), jenkins_retrigger_cooldown_key() (+7 more)

### Community 47 - "GeminiAdapter"
Cohesion: 0.11
Nodes (6): _attach_signature_to_parts(), _extract_part_signature(), GeminiAdapter, _is_empty_sig_carrier(), _part_has_fc(), _sanitize_candidate_parts()

### Community 48 - "CortexGraph.tsx"
Cohesion: 0.09
Nodes (35): graphology, AGENTS, DOMAINS, eventColor(), getExecutiveNeurons(), getStructuralEdges(), HEMISPHERE_X, NEURON_DESCRIPTIONS (+27 more)

### Community 50 - "httpx"
Cohesion: 0.09
Nodes (13): dex_proxy(), approve_mission(), dismiss_mission(), _infer_phase(), _jira_config(), list_missions(), reanalyze_mission(), retry_mission() (+5 more)

### Community 51 - "main.py"
Cohesion: 0.07
Nodes (16): set_kg_store(), set_pulse_tracker(), agent_ws_endpoint(), api_info(), get_config(), get_event_flow(), delta(), get_flow_history() (+8 more)

### Community 52 - "jenkins_observer.py"
Cohesion: 0.08
Nodes (13): _annotation_replace(), _strip_pipeline_annotations(), _clamp_confidence(), _env_flag(), _parse_job_metadata(), _prepare_console_tail(), _redact_match(), _redact_secrets_in_text() (+5 more)

### Community 53 - "lifespan"
Cohesion: 0.06
Nodes (8): set_agents(), set_archivist(), set_argocd_observer(), set_blackboard(), set_brain(), set_kargo_observer(), lifespan(), close_redis()

### Community 54 - "TimeKeeperPage.tsx"
Cohesion: 0.12
Nodes (24): createSchedule(), deleteSchedule(), getSchedules(), refineInstructions(), ScheduleCreatePayload, ScheduleItem, toggleSchedule(), updateSchedule() (+16 more)

### Community 55 - "KnowledgeGraphStore"
Cohesion: 0.11
Nodes (6): get_graph_context(), translate_to_lookups(), _acquire(), KnowledgeGraphStore, _sanitize(), _with_timeout()

### Community 56 - "ws-client.js"
Cohesion: 0.10
Nodes (26): clearIdleTimer(), {
  DEFAULT_WORK_DIR, AGENT_CLI, AGENT_MODEL, AGENT_ROLE,
  EVENT_ID, EPHEMERAL, IDLE_TIMEOUT_MS,
  CLI_429_MAX_RETRIES, CLI_429_INITIAL_DELAY_MS, CLI_429_BACKOFF_MULTIPLIER,
  resolveTimeoutMs, parsePositiveInt, MAX_TASK_WALL_MS, MAX_TIMER_MS,
}, { ensureEventDocument }, { executeCLIStreaming, prepareResultsDir, is429Error }, { filterSkillsByRole, filterSkillsByMode, swapActiveRules, restoreAllSkills }, fs, handleCancel(), handleTask() (+18 more)

### Community 57 - "jira_incident.py"
Cohesion: 0.10
Nodes (10): _adf_to_text(), _escape_jql_string(), JiraIncidentAdapter, adf_to_markdown(), _apply_marks(), _children(), _render(), _render_list() (+2 more)

### Community 58 - "types.py"
Cohesion: 0.09
Nodes (16): _extract_call_syntax(), derive_llm_priority(), _get_timeout_env_warned(), _get_timeout_order_warned(), is_partial_control_token(), parse_timeout_env(), process_stream_call_syntax_buffer(), resolve_stream_timeouts() (+8 more)

### Community 59 - "ui/package.json"
Cohesion: 0.08
Nodes (29): autoprefixer, cronstrue, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, graphology-layout-forceatlas2 (+21 more)

### Community 60 - "EventDrillDown.tsx"
Cohesion: 0.12
Nodes (25): three, getEventPulses(), BrainCore(), CortexDevPage(), CortexHeartbeat(), CortexHeartbeatProps, ensureKeyframes(), CortexLiveFeed() (+17 more)

### Community 62 - "_resolve_phase"
Cohesion: 0.13
Nodes (16): _build_closed_block(), build_event_header(), _build_identity_block(), _build_journal_block(), _build_mermaid_block(), build_operational_briefing(), _build_related_block(), _build_subject_block() (+8 more)

### Community 63 - "cognitive_graph.py"
Cohesion: 0.11
Nodes (12): get_blackboard(), get_pulse_tracker(), dismiss_proposals(), DismissRequest, get_all_shadow_interventions(), get_cognitive_graph(), get_cortex_activity(), get_cortex_status() (+4 more)

### Community 64 - "create_adapter"
Cohesion: 0.09
Nodes (6): create_adapter(), QuotaExhaustedError, QuotaTracker, _stale_reservation_ttl_s(), _load_brain_context(), refine_instructions()

### Community 65 - "server.js"
Cohesion: 0.09
Nodes (18): { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, ensureEventDocument(), fs, path, stageEventDocument(), fetchEventDocument(), fs, { handleRequest } (+10 more)

### Community 66 - ".list_observations"
Cohesion: 0.08
Nodes (4): get_all_journal(), get_service_journal(), get_event_observations(), get_global_observations()

### Community 67 - "useCortexData.ts"
Cohesion: 0.20
Nodes (23): getCognitiveGraph(), getCortexActivity(), getKGServiceDetail(), getKGServices(), getKGStats(), getRecentPulses(), CortexPage(), isOffRingCollection() (+15 more)

### Community 68 - "scheduling/__init__.py"
Cohesion: 0.13
Nodes (11): handle_refresh_github_context(), handle_refresh_gitlab_context(), handle_refresh_kargo_context(), StateWatcherPort, GitHubPrRef, GitLabMrRef, GitLabPipelineRef, KargoStageRef (+3 more)

### Community 70 - "archivist.py"
Cohesion: 0.10
Nodes (6): _sanitize_lesson_text(), Pulse, PulseBatch, PulseContext, PulsePort, PulseObserver

### Community 73 - "reconcile.py"
Cohesion: 0.15
Nodes (10): sanitize_redis_port(), _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers(), main() (+2 more)

### Community 74 - "BrainIntrospectionPort"
Cohesion: 0.08
Nodes (3): BrainIntrospectionPort, BrainLifecyclePort, BroadcastPort

### Community 76 - "GitHubAppAuth"
Cohesion: 0.11
Nodes (3): _find_pem_file(), get_github_auth(), GitHubAppAuth

### Community 77 - "dependencies"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 78 - "StateWatcher"
Cohesion: 0.11
Nodes (3): _QueueEntry, StateWatcher, _Subscription

### Community 81 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 82 - "time"
Cohesion: 0.14
Nodes (5): agent_websocket_handler(), _heartbeat(), get_current_shift(), get_shift_detail(), list_shifts()

### Community 83 - "claude-guard.js"
Cohesion: 0.14
Nodes (18): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+10 more)

### Community 86 - "ArchitectureGraph.tsx"
Cohesion: 0.14
Nodes (17): @dagrejs/dagre, @xyflow/react, applyDagreLayout(), applyGridLayout(), applyLayout(), ArchitectureGraphInner(), buildGraph(), computeIdHash() (+9 more)

### Community 87 - "FlowHistoryPage.tsx"
Cohesion: 0.23
Nodes (16): recharts, getFlowHistory(), FlowSnapshot, FlowHistoryPage(), RANGES, SparkCard(), SparkCardProps, formatTime() (+8 more)

### Community 89 - "cli-setup.js"
Cohesion: 0.13
Nodes (18): { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync }, filterSkillsByMode() (+10 more)

### Community 91 - "gemini_client.py"
Cohesion: 0.12
Nodes (9): _append_user_turn(), _clone_part_with_sig(), _clone_part_with_text(), _coerce_part(), _decode_sig_bytes(), _is_function_response_part(), _parse_drain_timeout(), _strip_user_thought_signature() (+1 more)

### Community 93 - "devDependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 94 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 95 - "gemini-sidecar/package.json"
Cohesion: 0.11
Nodes (18): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+10 more)

### Community 96 - "entity_extractor.py"
Cohesion: 0.15
Nodes (7): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship, KargoStageSnapshot, list_failed_stages()

### Community 99 - "get_report"
Cohesion: 0.11
Nodes (6): get_report(), list_reports(), reports_spa_no_slash(), reports_spa_with_slash(), search_reports(), _serve_spa()

### Community 100 - ".fetch_context"
Cohesion: 0.12
Nodes (3): _bot_login(), _consider(), _is_slash_command_only()

### Community 102 - "ShiftsPage.tsx"
Cohesion: 0.23
Nodes (16): getCurrentShift(), getShiftDetail(), getShiftsList(), ShiftReportFull, ShiftReportSummary, FailedClusterBadge(), getISOWeek(), getWeekDates() (+8 more)

### Community 103 - "catalog-skills.js"
Cohesion: 0.16
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 104 - "handlers_lookup.py"
Cohesion: 0.18
Nodes (7): _safe_int(), _format_bounded_journal(), handle_consult_deep_memory(), handle_google_web_search(), handle_lookup_journal(), _safe_seconds(), safe_score()

### Community 105 - "JenkinsPlatformPort"
Cohesion: 0.12
Nodes (4): BuildDetails, JenkinsPlatformPort, JobRunState, ViewScanResult

### Community 109 - "cortex/types.ts"
Cohesion: 0.15
Nodes (15): ActiveEvent, EventSource, KGServiceEntity, CortexGraphProps, GraphLoaderProps, PulseTimelineProps, CognitiveGraphResponse, CortexHeartbeatMessage (+7 more)

### Community 111 - "generate_map.py"
Cohesion: 0.19
Nodes (6): _enumerate_gates(), _GateInfo, generate_phase_tool_map(), _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 116 - "ServiceNode.tsx"
Cohesion: 0.20
Nodes (11): HealthStatus, NodeType, AppNodeData, ARGOCD_HEALTH_COLORS, SYNC_ICONS, GENERIC_TAGS, HEALTH_COLORS, NODE_ICONS (+3 more)

### Community 117 - "generate_event_title"
Cohesion: 0.15
Nodes (4): generate_event_title(), get_adapter(), _get_semaphore(), sanitize_title()

### Community 119 - "handlers_planning.py"
Cohesion: 0.23
Nodes (7): _auto_complete_step(), _canonical_role(), handle_create_plan(), handle_get_plan_progress(), _is_failed_turn(), _is_orchestrator_turn(), _normalize_step_id()

### Community 120 - "._process_candidates"
Cohesion: 0.15
Nodes (3): _flood_service_key(), _outage_service_key(), _service_key()

### Community 122 - "analyzeTokens"
Cohesion: 0.19
Nodes (13): analyzeString(), analyzeTokens(), assignName(), base(), combineCategories(), configEnvGuard(), configFileWriteGuard(), hasSubseq() (+5 more)

### Community 125 - "._extract_context_flags"
Cohesion: 0.15
Nodes (3): compute_dispatch_backpressure(), ContextFlags, _safe_int_env()

### Community 126 - "NeuronInfoPanel.tsx"
Cohesion: 0.24
Nodes (12): KGServiceDetail, asNumber(), asString(), asStringArray(), Badge(), describeNeuron(), Hdr(), NeuronInfoPanel() (+4 more)

### Community 132 - "handlers_dispatch.py"
Cohesion: 0.27
Nodes (3): _esc(), _esc_join(), event_to_markdown()

### Community 133 - "testSetup.ts"
Cohesion: 0.18
Nodes (5): @tailwindcss/vite, @testing-library/react, vite, @vitejs/plugin-react, vitest

### Community 134 - "_resolve_domain"
Cohesion: 0.20
Nodes (5): _batch_is_terminal_for_flush(), _is_close_phase_fc(), can_transition_to_close(), _resolve_domain(), resolve_event_domain()

### Community 135 - "is_defer_event_available"
Cohesion: 0.18
Nodes (6): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 139 - "gitGuard"
Cohesion: 0.29
Nodes (10): bareBranchProtected(), configWriteGuard(), externalGitCommand(), gitGuard(), gitQuery(), isProtected(), normRef(), pushGuard() (+2 more)

### Community 140 - "parseShell"
Cohesion: 0.33
Nodes (10): bodySubstitutions(), decodeAnsiC(), isArrayAssignPrefix(), isWordStart(), matchBacktick(), matchParen(), parseShell(), readHeredocStart() (+2 more)

### Community 144 - "has_unevaluated_close_blocker"
Cohesion: 0.22
Nodes (5): has_unevaluated_close_blocker(), _pred_jarvis_response(), _pred_unevaluated_close(), is_jarvis_acknowledgment(), is_stabilization_wake()

### Community 145 - "knowledge_graph_api.py"
Cohesion: 0.31
Nodes (4): get_kg_store(), get_service_detail(), get_stats(), list_services()

### Community 146 - "CortexDevPage.tsx"
Cohesion: 0.36
Nodes (8): devQueryClient, MOCK_CORTEX_STATUS, MOCK_EVENT_ID, MOCK_NEURONS, MOCK_PULSE_BATCHES, MOCK_SHADOW, MOCK_THINKING, MOCK_WHISPERS

### Community 147 - "classifyTool"
Cohesion: 0.31
Nodes (9): apiTokens(), apiWriteNeedsGuard(), branchValues(), classifyTool(), hasOpaqueTarget(), httpGuard(), httpMethod(), isReadMethod() (+1 more)

### Community 148 - "get_quota_tracker"
Cohesion: 0.22
Nodes (3): get_quota_tracker(), llm_stats(), receive_telemetry()

### Community 155 - "useDeferCountdown.ts"
Cohesion: 0.47
Nodes (7): DeferCountdownState, useDeferCountdown(), computeDeferProgress(), DeferTimeline, formatDeferRemaining(), inferDeferFromConversation(), resolveDeferTimeline()

### Community 158 - "LLMStreamInterChunkTimeoutError"
Cohesion: 0.25
Nodes (4): LLMStreamInterChunkTimeoutError, LLMStreamTimeoutError, LLMStreamTotalTimeoutError, LLMStreamTTFBTimeoutError

### Community 160 - "validate-mutations.sh"
Cohesion: 0.57
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

### Community 162 - "_format_graph_context"
Cohesion: 0.38
Nodes (3): _format_graph_context(), _parse_props(), _sanitize()

### Community 165 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 166 - "state.js"
Cohesion: 0.33
Nodes (4): { AGENT_ROLE }, _blackboardTurns, _inboundMessages, _teammateMessages

### Community 170 - "build_gate_context"
Cohesion: 0.33
Nodes (3): build_gate_context(), conversation_has_decayed_turns(), _decay_payload_len()

### Community 171 - "resolve_live_head_sha"
Cohesion: 0.33
Nodes (3): handle_approve(), resolve_live_head_sha(), verify_merge_guard()

### Community 180 - "classify"
Cohesion: 0.50
Nodes (4): classify(), main(), shellCategory(), shellNeedsGuard()

### Community 191 - "overrides"
Cohesion: 0.67
Nodes (3): overrides, @typescript-eslint/typescript-estree, minimatch

## Knowledge Gaps
- **13 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+8 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2390 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **103 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `os`, `queue.py`, `nightwatcher_tools.py`, `TopologyRepository`, `Brain`, `state/ports.py`, `HeadhunterJira`, `EventRepository`, `brain.py`, `EventDocument`, `BrainSkillLoader`, `models.py`, `slack.py`, `_is_event_closed_or_missing`, `ConversationTurn`, `auth.py`, `observations_mgmt.py`, `update_notebook_note`, `ScheduleCreateRequest`, `._get_ticket_nodes`, `EventEvidence`, `._restage_pending_signal`, `._stage_pending_signal`, `submit_feedback`, `get_notebook`, `httpx`, `main.py`, `jenkins_observer.py`, `lifespan`, `report_tampering`, `cognitive_graph.py`, `.list_observations`, `LiveAPIAdapter`, `time`, `.start_event_loop`, `DashboardWSAdapter`, `get_report`, `generate_event_title`?**
  _High betweenness centrality (0.109) - this node is a cross-community bridge._
- **Are the 80 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 80 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.012623745930502956 - nodes in this community are weakly interconnected._
- **Why does `Brain` connect `Brain` to `BlackboardState`, `os`, `queue.py`, `._run_agent_task`, `._resolve_llm_params`, `._post_agent_recall`, `state/ports.py`, `dispatch.py`, `brain.py`, `EventDocument`, `BrainSkillLoader`, `models.py`, `slack.py`, `._process_with_llm`, `ConversationTurn`, `._detect_repetition_collapse`, `auth.py`, `EventEvidence`, `StalenessGuard`, `ResyncTrigger`, `main.py`, `lifespan`, `archivist.py`, `BrainIntrospectionPort`, `StateWatcher`, `._close_and_broadcast`, `._build_contents`, `.start_event_loop`, `ReflexSearcher`, `DashboardWSAdapter`, `JarvisPeerPort`, `IdleTimeoutManager`, `ReconcileScheduler`, `._extract_context_flags`?**
  _High betweenness centrality (0.071) - this node is a cross-community bridge._
- **Are the 20 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Should `os` be split into smaller, more focused modules?**
  _Cohesion score 0.03496732026143791 - nodes in this community are weakly interconnected._