# Graph Report - Blackboard  (2026-11-17)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 5329 nodes · 12010 edges · 207 communities (109 shown, 98 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 960 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `6436fe4b`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BlackboardState
- Brain
- logging
- brain.py
- client.ts
- queue.py
- EventSidebar.tsx
- Archivist
- EventChatPanel.tsx
- models.py
- tool_gates.py
- os
- dependencies.py
- http-handler.js
- ._process_with_llm
- colors.ts
- .get_graph_data
- jenkins-mcp.js
- SlackChannel
- react
- App.tsx
- auth.py
- ToolContext
- TurnBubble.tsx
- gemini_client.py
- WorkspaceInspector.tsx
- BrainSkillLoader
- _BrainToolContext
- GitHubPlatform
- merge-guard.js
- JenkinsAdapter
- KnowledgeGraphStore
- agents/__init__.py
- Headhunter
- StreamGrid.tsx
- cli-executor.js
- storage-recycler.js
- EventEvidence
- GitLabPlatform
- EventRepository
- llm/__init__.py
- Aligner
- dispatch.py
- time
- ConversationTurn
- CortexGraph.tsx
- create_schedule
- TimeKeeperPage.tsx
- observations_mgmt.py
- ws-client.js
- main.py
- ui/package.json
- ._build_system_prompt
- EventDrillDown.tsx
- ._add_labels
- KargoObserver
- IdleTimeoutManager
- useCortexData.ts
- asyncio
- headhunter_gitlab.py
- nightwatcher.py
- LiveAPIAdapter
- ArgoCDObserver
- server.js
- cognitive_graph.py
- nightwatcher_tools.py
- .list_observations
- ReconcileScheduler
- state/__init__.py
- NodeInspector.tsx
- PulseBatch
- types.py
- JarvisPeerPort
- NightwatcherObserver
- TopologyRepository
- dependencies
- StateWatcher
- jira_incident.py
- compilerOptions
- claude-guard.js
- DashboardWSAdapter
- record_token_usage
- GeminiAdapter
- reconcile.py
- FlowHistoryPage.tsx
- VcsPlatformPort
- quota_tracker.py
- cli-setup.js
- ReflexSearcher
- FairQueue
- devDependencies
- compilerOptions
- gemini-sidecar/package.json
- ServiceNode.tsx
- EphemeralProvisioner
- get_report
- GitHubAppAuth
- .start_event_loop
- ObservationRepository
- ShiftsPage.tsx
- cortex/types.ts
- catalog-skills.js
- SlackAccessGate
- ArchitectureGraph.tsx
- EscalationRepository
- TokenMeter
- generate_map.py
- OIDCKeyAdapter
- KubernetesSpawnHealthAdapter
- JenkinsObserver
- tool_router.py
- ._connect
- handlers_planning.py
- ScheduleRepository
- MultiInstallationManager
- analyzeTokens
- ScheduleCreateRequest
- ephemeral_provisioner.py
- ._process_message
- HeadhunterJira
- CortexLiveFeed.tsx
- testSetup.ts
- .ensure_agent
- is_defer_event_available
- NeuronInfoPanel.tsx
- ._run_clustering_agent
- gitGuard
- parseShell
- github_app.py
- entity_extractor.py
- ._process_candidates
- ._triage_and_build_evidence
- ._drain_once
- has_unevaluated_close_blocker
- knowledge_graph_api.py
- classifyTool
- get_quota_tracker
- SpawnPollResult
- SmartsheetMaintainerCache
- .has_reeval_signal
- list_shifts
- Trigger
- AsyncGitHubClient
- GitLabTokenAuth
- _is_event_closed_or_missing
- ._evaluate_health
- ConversationMessage
- TimeKeeperObserver
- CortexRepository
- adf_to_markdown
- validate-mutations.sh
- QuotaExhaustedError
- scripts
- state.js
- io
- build_gate_context
- PollFn
- handle_recall_pruned_turns
- handle_report_incident
- TicketNode.tsx
- classify
- require-results.sh
- _env_flag
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
- _pred_idle_agent_wait
- _pred_jarvis_wait
- _pred_obs_plateau
- _pred_silent_park
- _tools_wait_loop

## God Nodes (most connected - your core abstractions)
1. `BlackboardState` - 285 edges
2. `Brain` - 168 edges
3. `ConversationTurn` - 127 edges
4. `ToolContext` - 103 edges
5. `GateContext` - 99 edges
6. `react` - 85 edges
7. `EventDocument` - 84 edges
8. `fetchApi()` - 66 edges
9. `lifespan()` - 65 edges
10. `LiveAPIAdapter` - 64 edges

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

## Communities (207 total, 98 thin omitted)

### Community 1 - "Brain"
Cohesion: 0.02
Nodes (8): Brain, on_huddle(), on_progress(), on_huddle(), on_progress(), _is_automated_nudge(), _sanitize_error_text(), get_registry_and_bridge()

### Community 2 - "logging"
Cohesion: 0.03
Nodes (36): _sanitize_lesson_text(), _sanitize_recalled(), _safe_seconds(), _clamp_confidence(), _parse_job_metadata(), _prepare_console_tail(), _redact_match(), _redact_secrets_in_text() (+28 more)

### Community 3 - "brain.py"
Cohesion: 0.03
Nodes (52): _batch_is_terminal_for_flush(), _close_unanswered_fc(), _compute_processed_up_to(), _contents_have_pruned_or_decayed(), _has_non_user_turns(), _is_close_phase_fc(), _is_participant_turn(), _is_seed_turn() (+44 more)

### Community 4 - "client.ts"
Cohesion: 0.03
Nodes (103): oidc-client-ts, @tanstack/react-query, ApiError, bulkDeleteObservations(), deleteNote(), deleteObservation(), exportObservations(), ExtractedCorrection (+95 more)

### Community 5 - "queue.py"
Cohesion: 0.03
Nodes (53): get_token_meter(), resolve_approval_identity(), get_archivist(), get_brain(), report_tampering(), aligner_pending_items(), apply_lessons(), approve_event() (+45 more)

### Community 6 - "EventSidebar.tsx"
Cohesion: 0.05
Nodes (94): getActiveEvents(), getAlignerPending(), getEventDocument(), getHeadhunterPending(), getJenkinsPending(), getJiraMissions(), getWaitingApprovalEvents(), HeadhunterTodo (+86 more)

### Community 7 - "Archivist"
Cohesion: 0.04
Nodes (4): Archivist, _decode_cursor(), _encode_cursor(), VectorStore

### Community 8 - "EventChatPanel.tsx"
Cohesion: 0.05
Nodes (72): react-router-dom, createChatEvent(), getAgents(), getEvents(), getKargoStages(), updateEventTitle(), AgentRegistryEntry, KargoStageStatus (+64 more)

### Community 9 - "models.py"
Cohesion: 0.04
Nodes (32): _resolve_escalation_scope(), AppNode, ArchitectureEvent, ChatRequest, ChatResponse, EventInput, EventMetrics, EventStatus (+24 more)

### Community 10 - "tool_gates.py"
Cohesion: 0.05
Nodes (79): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+71 more)

### Community 11 - "os"
Cohesion: 0.05
Nodes (15): _safe_int(), get_blackboard(), get_flow_metrics(), dex_proxy(), FeedbackRequest, submit_feedback(), list_incidents(), approve_mission() (+7 more)

### Community 12 - "dependencies.py"
Cohesion: 0.04
Nodes (19): AgentConnection, AgentRegistry, get_aligner(), get_architect(), get_argocd_observer(), get_developer(), get_kargo_observer(), get_report_client() (+11 more)

### Community 13 - "http-handler.js"
Cohesion: 0.08
Nodes (62): is429Error(), registerMCPsAndHooks(), resolveCommand(), writeAgyMcpServer(), writeClaudeMcpServer(), parsePositiveInt(), buildArgoCDMcpConfig(), createAppJWT() (+54 more)

### Community 14 - "._process_with_llm"
Cohesion: 0.03
Nodes (10): _BatchContext, compute_dispatch_backpressure(), ContextFlags, _ensure_recall_tool_if_needed(), _incr_flow_counter_safely(), _QuotaShedState, RepetitionCollapse, _retry_backoff_delay() (+2 more)

### Community 15 - "colors.ts"
Cohesion: 0.07
Nodes (39): getReport(), getReports(), ReportFull, ReportMeta, CompactCardStrip(), EventHistory(), TimeRange, ViewMode (+31 more)

### Community 16 - ".get_graph_data"
Cohesion: 0.04
Nodes (8): get_event_document(), list_events(), get_graph_data(), get_mermaid_diagram(), get_service_details(), get_topology(), list_services(), calculate_health_from_argocd()

### Community 17 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 18 - "SlackChannel"
Cohesion: 0.05
Nodes (8): extract_tables(), _replace(), get_agent_notification_text(), get_turn_attachment_color(), _md_table_to_block_kit(), SlackChannel, handle_home_create_event(), handle_reject()

### Community 19 - "react"
Cohesion: 0.08
Nodes (52): lucide-react, react, applyLessons(), correctMemory(), createKnowledge(), createLesson(), deleteKnowledge(), deleteLesson() (+44 more)

### Community 20 - "App.tsx"
Cohesion: 0.07
Nodes (45): react-dom, dismissProposals(), EnhancementProposal, getHandoffReports(), getProposals(), getWSAuthFailureCallback(), HandoffReport, App() (+37 more)

### Community 21 - "auth.py"
Cohesion: 0.05
Nodes (18): can_approve_event(), can_override_domain(), can_rename_event(), _claims_to_user(), get_user_from_request(), get_user_from_slack(), get_user_from_websocket(), _normalize_email() (+10 more)

### Community 22 - "ToolContext"
Cohesion: 0.08
Nodes (12): handle_message_agent(), handle_reply_to_agent(), handle_select_agent(), _sticky_work_style(), handle_classify_event(), handle_defer_event(), handle_hold_watch(), handle_request_user_approval() (+4 more)

### Community 23 - "TurnBubble.tsx"
Cohesion: 0.09
Nodes (39): @uiw/react-markdown-preview, approveEvent(), closeEvent(), enforceCasualDomain(), getEventReport(), rejectEvent(), submitFeedback(), ConversationFeed() (+31 more)

### Community 24 - "gemini_client.py"
Cohesion: 0.08
Nodes (18): _append_user_turn(), _attach_signature_to_parts(), _clone_part_with_sig(), _clone_part_with_text(), _coerce_part(), _decode_sig_bytes(), _extract_call_syntax(), _extract_part_signature() (+10 more)

### Community 25 - "WorkspaceInspector.tsx"
Cohesion: 0.08
Nodes (41): ConversationTurn, BORDER_COLOR, PlanProgress(), PlanProgressProps, STATUS_ICON, DiffFile, DiffHunk, DiffLine (+33 more)

### Community 26 - "BrainSkillLoader"
Cohesion: 0.05
Nodes (3): BrainSkillLoader, _SkillCorpus, BrainIntrospectionPort

### Community 28 - "GitHubPlatform"
Cohesion: 0.05
Nodes (3): GitHubPlatform, _poll_one(), _poll_one()

### Community 29 - "merge-guard.js"
Cohesion: 0.04
Nodes (46): API_VALUED, ARGO_MUTATING, ARGO_READ_SUB, ARGO_READ_TOP, BODY_FLAG, BROWSER_READ, CTX, ENV_BUILTINS (+38 more)

### Community 30 - "JenkinsAdapter"
Cohesion: 0.06
Nodes (8): _annotation_replace(), BuildDetails, JenkinsAdapter, JenkinsPlatformPort, JobResult, JobRunState, _strip_pipeline_annotations(), ViewScanResult

### Community 31 - "KnowledgeGraphStore"
Cohesion: 0.08
Nodes (9): _format_graph_context(), get_graph_context(), _parse_props(), _sanitize(), translate_to_lookups(), _acquire(), KnowledgeGraphStore, _sanitize() (+1 more)

### Community 32 - "agents/__init__.py"
Cohesion: 0.07
Nodes (4): Architect, AgentClient, Developer, SysAdmin

### Community 33 - "Headhunter"
Cohesion: 0.06
Nodes (3): Headhunter, _raise_if_systemic_failure(), _sanitize_xml_fence()

### Community 34 - "StreamGrid.tsx"
Cohesion: 0.08
Nodes (36): getFlowMetrics(), FlowMetrics, AgentStreamCard(), AgentStreamCardProps, MessageCards(), Dashboard(), FlowHealthWidget(), queueColor() (+28 more)

### Community 35 - "cli-executor.js"
Cohesion: 0.09
Nodes (37): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, MAX_TASK_WALL_MS, MAX_TIMER_MS, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS, STORAGE_PRETASK_TIMEOUT_MS, resolveStorageRoot }, buildCLICommand(), buildTimeoutResult(), { checkAndRecycleStorage, pinTaskCwd, unpinTaskCwd }, CLAUDE_JSON_PATH, cp, createInactivityWatchdog(), executeCLI() (+29 more)

### Community 36 - "storage-recycler.js"
Cohesion: 0.08
Nodes (37): withTaskStorage(), MAX_TASK_WALL_MS, parseTimerMs(), resolveStorageRoot(), resolveTimeoutMs(), ROLE_TIMEOUTS, STORAGE_ACTIVITY_HEARTBEAT_MS, STORAGE_MAX_TIER3_DELETIONS (+29 more)

### Community 37 - "EventEvidence"
Cohesion: 0.08
Nodes (14): generate_event_title(), get_adapter(), _get_semaphore(), spawn_event_namer_task(), handle_app_home_opened(), handle_app_mention(), handle_create_event_modal(), handle_darwin_command() (+6 more)

### Community 40 - "llm/__init__.py"
Cohesion: 0.08
Nodes (7): ClaudeAdapter, _parse_tpm_limit(), FunctionCall, LLMChunk, LLMPort, LLMResponse, TokenUsage

### Community 42 - "dispatch.py"
Cohesion: 0.08
Nodes (13): _build_prompt(), _check_security(), consume_wake_task(), _consume(), _dispatch_timeout_s(), dispatch_to_agent(), _consume_queue(), _sanitize_stdout() (+5 more)

### Community 43 - "time"
Cohesion: 0.09
Nodes (18): _alert_wrapper_retrigger(), _do_retrigger(), _get_jira_reporter(), handle_notify_user_slack(), handle_refresh_github_context(), handle_refresh_gitlab_context(), handle_refresh_kargo_context(), _is_darwin_reentrant_caller() (+10 more)

### Community 44 - "ConversationTurn"
Cohesion: 0.15
Nodes (26): emit_tool_result(), _safe_int(), handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_ask_release_ai(), handle_comment_jira_issue(), handle_fetch_jira_issue() (+18 more)

### Community 45 - "CortexGraph.tsx"
Cohesion: 0.09
Nodes (35): graphology, AGENTS, DOMAINS, eventColor(), getExecutiveNeurons(), getStructuralEdges(), HEMISPHERE_X, NEURON_DESCRIPTIONS (+27 more)

### Community 46 - "create_schedule"
Cohesion: 0.06
Nodes (8): create_schedule(), delete_schedule(), get_schedule(), list_schedules(), _load_brain_context(), refine_instructions(), toggle_schedule(), update_schedule()

### Community 47 - "TimeKeeperPage.tsx"
Cohesion: 0.12
Nodes (24): createSchedule(), deleteSchedule(), getSchedules(), refineInstructions(), ScheduleCreatePayload, ScheduleItem, toggleSchedule(), updateSchedule() (+16 more)

### Community 48 - "observations_mgmt.py"
Cohesion: 0.08
Nodes (11): render_pdf(), KargoStageSnapshot, list_failed_stages(), bulk_delete_observations(), BulkDeleteRequest, delete_observation(), export_observations(), generate_observations_report() (+3 more)

### Community 49 - "ws-client.js"
Cohesion: 0.10
Nodes (26): clearIdleTimer(), {
  DEFAULT_WORK_DIR, AGENT_CLI, AGENT_MODEL, AGENT_ROLE,
  EVENT_ID, EPHEMERAL, IDLE_TIMEOUT_MS,
  CLI_429_MAX_RETRIES, CLI_429_INITIAL_DELAY_MS, CLI_429_BACKOFF_MULTIPLIER,
  resolveTimeoutMs, parsePositiveInt, MAX_TASK_WALL_MS, MAX_TIMER_MS,
}, { ensureEventDocument }, { executeCLIStreaming, prepareResultsDir, is429Error }, { filterSkillsByRole, filterSkillsByMode, swapActiveRules, restoreAllSkills }, fs, handleCancel(), handleTask() (+18 more)

### Community 50 - "main.py"
Cohesion: 0.08
Nodes (14): set_incident_options(), set_oidc_adapter(), agent_ws_endpoint(), api_info(), get_config(), get_event_flow(), delta(), get_flow_history() (+6 more)

### Community 51 - "ui/package.json"
Cohesion: 0.08
Nodes (29): autoprefixer, cronstrue, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, graphology-layout-forceatlas2 (+21 more)

### Community 52 - "._build_system_prompt"
Cohesion: 0.07
Nodes (5): _init_tool_names(), _strip_tool_names(), _wrap_section(), maintainer_env_key(), resolve_maintainer_emails()

### Community 53 - "EventDrillDown.tsx"
Cohesion: 0.12
Nodes (24): three, getEventPulses(), BrainCore(), CortexDevPage(), devQueryClient, CortexLiveFeedProps, EventDrillDown(), EventDrillDownProps (+16 more)

### Community 57 - "useCortexData.ts"
Cohesion: 0.17
Nodes (26): getCognitiveGraph(), getCortexActivity(), getKGServiceDetail(), getKGServices(), getKGStats(), getKnowledgeById(), getMemory(), getRecentPulses() (+18 more)

### Community 58 - "asyncio"
Cohesion: 0.11
Nodes (9): agent_websocket_handler(), _heartbeat(), _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), _sample_points() (+1 more)

### Community 59 - "headhunter_gitlab.py"
Cohesion: 0.11
Nodes (10): _get_allowed_mention_authors(), _get_static_maintainer_emails(), get_gitlab_auth(), parse_mr_url(), resolve_ca_bundle(), _resolve_github_head(), _resolve_gitlab_head(), resolve_live_head_sha() (+2 more)

### Community 60 - "nightwatcher.py"
Cohesion: 0.11
Nodes (11): build_manifest_table(), build_report_iteration_prompt(), build_summary_prompt(), build_system_prompt(), extract_event_links(), extract_full_links(), _normalize_gitlab_host(), build_extend_tool() (+3 more)

### Community 63 - "server.js"
Cohesion: 0.09
Nodes (18): { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, ensureEventDocument(), fs, path, stageEventDocument(), fetchEventDocument(), fs, { handleRequest } (+10 more)

### Community 64 - "cognitive_graph.py"
Cohesion: 0.11
Nodes (11): get_pulse_tracker(), dismiss_proposals(), DismissRequest, get_all_shadow_interventions(), get_cognitive_graph(), get_cortex_activity(), get_cortex_status(), get_event_shadow_interventions() (+3 more)

### Community 65 - "nightwatcher_tools.py"
Cohesion: 0.14
Nodes (14): PulseContext, ShiftIncident, ShiftInvestigation, execute_tool(), _handle_consult_deep_memory(), _handle_declare_clusters(), _handle_dispatch_investigation(), _handle_get_event_report() (+6 more)

### Community 66 - ".list_observations"
Cohesion: 0.08
Nodes (4): get_all_journal(), get_service_journal(), get_event_observations(), get_global_observations()

### Community 67 - "ReconcileScheduler"
Cohesion: 0.12
Nodes (4): ReconcileScheduler, QueueTrigger, ResyncTrigger, StalenessGuard

### Community 68 - "state/__init__.py"
Cohesion: 0.11
Nodes (4): sanitize_redis_port(), close_redis(), get_redis(), RedisClient

### Community 69 - "NodeInspector.tsx"
Cohesion: 0.13
Nodes (23): getClosedEvents(), ArchitectureEvent, ArgoCDOperation, ArchitectureGraph(), EVENT_LABELS, EventItem(), EventItemProps, healthTone() (+15 more)

### Community 70 - "PulseBatch"
Cohesion: 0.10
Nodes (4): PulseBatch, PulsePort, PulseObserver, PulseTracker

### Community 71 - "types.py"
Cohesion: 0.11
Nodes (12): _get_timeout_env_warned(), _get_timeout_order_warned(), is_partial_control_token(), parse_timeout_env(), _patch_enum_fields(), process_stream_call_syntax_buffer(), resolve_stream_timeouts(), _split_partial_control_token() (+4 more)

### Community 72 - "JarvisPeerPort"
Cohesion: 0.08
Nodes (3): BrainLifecyclePort, BroadcastPort, JarvisPeerPort

### Community 73 - "NightwatcherObserver"
Cohesion: 0.13
Nodes (4): ShiftReport, _env_float(), _env_int(), NightwatcherObserver

### Community 75 - "dependencies"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 76 - "StateWatcher"
Cohesion: 0.11
Nodes (3): _QueueEntry, StateWatcher, _Subscription

### Community 77 - "jira_incident.py"
Cohesion: 0.12
Nodes (3): _adf_to_text(), _escape_jql_string(), JiraIncidentAdapter

### Community 78 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 79 - "claude-guard.js"
Cohesion: 0.14
Nodes (18): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+10 more)

### Community 81 - "record_token_usage"
Cohesion: 0.10
Nodes (5): FilterRule, record_token_usage(), _append_user_turn(), _finalize_analysis_handover(), get_phase_tools()

### Community 82 - "GeminiAdapter"
Cohesion: 0.10
Nodes (5): GeminiAdapter, LLMStreamInterChunkTimeoutError, LLMStreamTimeoutError, LLMStreamTotalTimeoutError, LLMStreamTTFBTimeoutError

### Community 83 - "reconcile.py"
Cohesion: 0.18
Nodes (9): _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers(), main(), _parse_frontmatter() (+1 more)

### Community 84 - "FlowHistoryPage.tsx"
Cohesion: 0.23
Nodes (16): recharts, getFlowHistory(), FlowSnapshot, FlowHistoryPage(), RANGES, SparkCard(), SparkCardProps, formatTime() (+8 more)

### Community 86 - "quota_tracker.py"
Cohesion: 0.13
Nodes (3): QuotaTracker, Reservation, _stale_reservation_ttl_s()

### Community 87 - "cli-setup.js"
Cohesion: 0.13
Nodes (18): { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync }, filterSkillsByMode() (+10 more)

### Community 90 - "devDependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 91 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 92 - "gemini-sidecar/package.json"
Cohesion: 0.11
Nodes (18): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+10 more)

### Community 93 - "ServiceNode.tsx"
Cohesion: 0.15
Nodes (13): @xyflow/react, HealthStatus, NodeType, AppNodeData, ARGOCD_HEALTH_COLORS, SYNC_ICONS, NamespaceGroupNodeData, GENERIC_TAGS (+5 more)

### Community 95 - "get_report"
Cohesion: 0.11
Nodes (6): get_report(), list_reports(), reports_spa_no_slash(), reports_spa_with_slash(), search_reports(), _serve_spa()

### Community 99 - "ShiftsPage.tsx"
Cohesion: 0.23
Nodes (16): getCurrentShift(), getShiftDetail(), getShiftsList(), ShiftReportFull, ShiftReportSummary, FailedClusterBadge(), getISOWeek(), getWeekDates() (+8 more)

### Community 100 - "cortex/types.ts"
Cohesion: 0.16
Nodes (16): ActiveEvent, EventSource, KGServiceEntity, CortexGraphProps, GraphLoaderProps, NeuronInfoPanelProps, PulseTimelineProps, CognitiveGraphResponse (+8 more)

### Community 101 - "catalog-skills.js"
Cohesion: 0.16
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 103 - "ArchitectureGraph.tsx"
Cohesion: 0.18
Nodes (15): @dagrejs/dagre, applyDagreLayout(), applyGridLayout(), applyLayout(), ArchitectureGraphInner(), buildGraph(), computeIdHash(), edgeTypes (+7 more)

### Community 107 - "generate_map.py"
Cohesion: 0.19
Nodes (6): _enumerate_gates(), _GateInfo, generate_phase_tool_map(), _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 111 - "tool_router.py"
Cohesion: 0.15
Nodes (3): IdleTimeoutPort, IncidentAdapterPort, StateWatcherPort

### Community 113 - "handlers_planning.py"
Cohesion: 0.23
Nodes (7): _auto_complete_step(), _canonical_role(), handle_create_plan(), handle_get_plan_progress(), _is_failed_turn(), _is_orchestrator_turn(), _normalize_step_id()

### Community 118 - "analyzeTokens"
Cohesion: 0.19
Nodes (13): analyzeString(), analyzeTokens(), assignName(), base(), combineCategories(), configEnvGuard(), configFileWriteGuard(), hasSubseq() (+5 more)

### Community 126 - "CortexLiveFeed.tsx"
Cohesion: 0.24
Nodes (10): CortexHeartbeat(), CortexHeartbeatProps, ensureKeyframes(), CortexLiveFeed(), FILTER_PILLS, FilterKey, getStoredFilter(), MESSAGE_STYLES (+2 more)

### Community 127 - "testSetup.ts"
Cohesion: 0.18
Nodes (5): @tailwindcss/vite, @testing-library/react, vite, @vitejs/plugin-react, vitest

### Community 129 - "is_defer_event_available"
Cohesion: 0.18
Nodes (6): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 130 - "NeuronInfoPanel.tsx"
Cohesion: 0.29
Nodes (10): asNumber(), asString(), asStringArray(), Badge(), describeNeuron(), Hdr(), NeuronInfoPanel(), AGENT_NEURON_COLORS (+2 more)

### Community 131 - "._run_clustering_agent"
Cohesion: 0.24
Nodes (3): _fallback_platform(), reconcile_cluster_plan(), salvage_cluster_plan()

### Community 132 - "gitGuard"
Cohesion: 0.29
Nodes (10): bareBranchProtected(), configWriteGuard(), externalGitCommand(), gitGuard(), gitQuery(), isProtected(), normRef(), pushGuard() (+2 more)

### Community 133 - "parseShell"
Cohesion: 0.33
Nodes (10): bodySubstitutions(), decodeAnsiC(), isArrayAssignPrefix(), isWordStart(), matchBacktick(), matchParen(), parseShell(), readHeredocStart() (+2 more)

### Community 135 - "entity_extractor.py"
Cohesion: 0.33
Nodes (5): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship

### Community 139 - "has_unevaluated_close_blocker"
Cohesion: 0.22
Nodes (5): has_unevaluated_close_blocker(), _pred_jarvis_response(), _pred_unevaluated_close(), is_jarvis_acknowledgment(), is_stabilization_wake()

### Community 140 - "knowledge_graph_api.py"
Cohesion: 0.31
Nodes (4): get_kg_store(), get_service_detail(), get_stats(), list_services()

### Community 141 - "classifyTool"
Cohesion: 0.31
Nodes (9): apiTokens(), apiWriteNeedsGuard(), branchValues(), classifyTool(), hasOpaqueTarget(), httpGuard(), httpMethod(), isReadMethod() (+1 more)

### Community 142 - "get_quota_tracker"
Cohesion: 0.22
Nodes (3): get_quota_tracker(), llm_stats(), receive_telemetry()

### Community 156 - "adf_to_markdown"
Cohesion: 0.57
Nodes (7): adf_to_markdown(), _apply_marks(), _children(), _render(), _render_list(), _render_list_item(), _render_table_like()

### Community 157 - "validate-mutations.sh"
Cohesion: 0.57
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

### Community 160 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 161 - "state.js"
Cohesion: 0.33
Nodes (4): { AGENT_ROLE }, _blackboardTurns, _inboundMessages, _teammateMessages

### Community 168 - "build_gate_context"
Cohesion: 0.33
Nodes (3): build_gate_context(), conversation_has_decayed_turns(), _decay_payload_len()

### Community 171 - "handle_recall_pruned_turns"
Cohesion: 0.50
Nodes (3): _coerce_turn_int(), handle_recall_pruned_turns(), _parse_turn_int()

### Community 173 - "TicketNode.tsx"
Cohesion: 0.40
Nodes (4): STATUS_COLORS, TICKET_COLORS, TicketNodeComponent(), TicketNodeData

### Community 174 - "classify"
Cohesion: 0.50
Nodes (4): classify(), main(), shellCategory(), shellNeedsGuard()

### Community 181 - "overrides"
Cohesion: 0.67
Nodes (3): overrides, @typescript-eslint/typescript-estree, minimatch

## Knowledge Gaps
- **13 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+8 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2342 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **98 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `Brain`, `logging`, `brain.py`, `queue.py`, `models.py`, `os`, `dependencies.py`, `.get_graph_data`, `list_shifts`, `auth.py`, `_is_event_closed_or_missing`, `ConversationMessage`, `EventEvidence`, `ConversationTurn`, `create_schedule`, `observations_mgmt.py`, `main.py`, `KargoObserver`, `IdleTimeoutManager`, `asyncio`, `headhunter_gitlab.py`, `nightwatcher.py`, `LiveAPIAdapter`, `nightwatcher_tools.py`, `.list_observations`, `state/__init__.py`, `NightwatcherObserver`, `DashboardWSAdapter`, `get_report`, `tool_router.py`, `ScheduleRepository`, `HeadhunterJira`?**
  _High betweenness centrality (0.114) - this node is a cross-community bridge._
- **Are the 80 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 80 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.011136434269139128 - nodes in this community are weakly interconnected._
- **Why does `Brain` connect `Brain` to `BlackboardState`, `logging`, `brain.py`, `models.py`, `dependencies.py`, `._process_with_llm`, `BrainSkillLoader`, `agents/__init__.py`, `EventEvidence`, `.stop_event_loop`, `ConversationTurn`, `main.py`, `._build_system_prompt`, `IdleTimeoutManager`, `.create_kargo_event`, `ReconcileScheduler`, `PulseBatch`, `JarvisPeerPort`, `StateWatcher`, `DashboardWSAdapter`, `ReflexSearcher`, `.start_event_loop`?**
  _High betweenness centrality (0.068) - this node is a cross-community bridge._
- **Are the 20 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Should `Brain` be split into smaller, more focused modules?**
  _Cohesion score 0.020821018062397372 - nodes in this community are weakly interconnected._