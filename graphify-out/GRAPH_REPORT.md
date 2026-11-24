# Graph Report - Blackboard  (2026-11-24)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 6020 nodes · 13725 edges · 248 communities (119 shown, 129 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 1038 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `f6e8e710`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BlackboardState
- Brain
- gemini_client.py
- react
- client.ts
- logging
- main.py
- queue.py
- EventSidebar.tsx
- GitLabPlatform
- brain.py
- os
- tool_gates.py
- Headhunter
- EventRepository
- models.py
- ReconcileScheduler
- http-handler.js
- ._process_with_llm
- TurnBubble.tsx
- jenkins-mcp.js
- App.tsx
- slack.py
- Service
- useMemory.ts
- EventChatPanel.tsx
- nightwatcher_tools.py
- Aligner
- _BrainToolContext
- handlers_integration.py
- KargoObserver
- merge-guard.js
- StreamGrid.tsx
- cli-executor.js
- storage-recycler.js
- ToolContext
- KnowledgeGraphStore
- context_parts.py
- sanitize_untrusted_line
- ConversationTurn
- dispatch.py
- jenkins_observer.py
- formatter.py
- VcsPlatformPort
- GitHubPlatform
- SlackChannel
- UserContext
- LiveAPIAdapter
- TimeKeeperPage.tsx
- ws-client.js
- observations_mgmt.py
- create_schedule
- KubernetesSpawnHealthAdapter
- ui/package.json
- BoolOutcome
- useCortexData.ts
- EphemeralProvisioner
- .list_observations
- EventDrillDown.tsx
- AgentRegistry
- Any
- QuotaTracker
- NightwatcherObserver
- CortexGraph.tsx
- ._poll_pr_feedback
- state/ports.py
- TopologyRepository
- BrainSkillLoader
- NodeInspector.tsx
- llm_error_classifier.py
- server.js
- cognitive_graph.py
- PulseBatch
- ArgoCDObserver
- handlers_lookup.py
- ._poll_issues
- dependencies
- NeuronInfoPanel.tsx
- JenkinsAdapter
- start_headhunter_task
- HeadhunterCircuitBreaker
- JenkinsObserver
- GitHubAppAuth
- EventHistory.tsx
- compilerOptions
- reconcile.py
- claude-guard.js
- AsyncGitHubClient
- FlowHistoryPage.tsx
- ._feedback_reject_reason
- Any
- cli-setup.js
- ReflexSearcher
- spawn_event_namer_task
- devDependencies
- compilerOptions
- gemini-sidecar/package.json
- ServiceNode.tsx
- get_report
- JiraIncidentAdapter
- HeadhunterJira
- TokenMeter
- headhunter_pending_todos
- ObservationRepository
- ShiftsPage.tsx
- catalog-skills.js
- StateWatcher
- ArchitectureGraph.tsx
- JenkinsPlatformPort
- Archivist
- JarvisPeerPort
- EscalationRepository
- VectorStore
- maintainers.py
- has_unevaluated_close_blocker
- cortex/types.ts
- ._poll_and_stage
- OIDCKeyAdapter
- ._discover
- MultiInstallationManager
- ._connect
- BrainLifecyclePort
- handlers_planning.py
- .fetch_context
- ScheduleRepository
- nightwatcher_prompt.py
- analyzeTokens
- generate_map.py
- .scroll
- ._extract_context_flags
- evaluate_gates
- ._process_message
- handle_report_incident
- testSetup.ts
- ._authorize_plan_decision
- ScheduleCreateRequest
- create_chat_event
- IdleTimeoutManager
- SlackAccessGate
- GitLabTokenAuth
- CortexLiveFeed.tsx
- gitGuard
- parseShell
- generate_event_title
- ._post_agent_recall
- entity_extractor.py
- ._clear_recovered_group_flags
- knowledge_graph_api.py
- BrainIntrospectionPort
- HeadhunterItemActionRequest
- classifyTool
- handlers_cross_event.py
- .has_reeval_signal
- _get_canonical_or_alias
- build_gate_context
- get_event_document
- _is_event_closed_or_missing
- handle_notify_user_slack
- ConversationMessage
- TimeKeeperObserver
- CortexRepository
- adf_to_markdown
- validate-mutations.sh
- ._detect_repetition_collapse
- update_notebook_note
- scripts
- state.js
- list_failed_stages
- rename_observation
- dex_proxy
- agent_ws_endpoint
- submit_feedback
- get_notebook
- TicketNode.tsx
- classify
- _compute_processed_up_to
- _has_non_user_turns
- delete_notebook_note
- delete_observation
- require-results.sh
- _env_flag
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
- _parse_ts_epoch
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
1. `BlackboardState` - 325 edges
2. `Brain` - 169 edges
3. `ConversationTurn` - 139 edges
4. `ToolContext` - 103 edges
5. `GateContext` - 100 edges
6. `GitHubPlatform` - 99 edges
7. `EventDocument` - 97 edges
8. `EventRepository` - 90 edges
9. `Headhunter` - 89 edges
10. `react` - 86 edges

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

## Communities (248 total, 129 thin omitted)

### Community 1 - "Brain"
Cohesion: 0.02
Nodes (9): Brain, on_huddle(), on_progress(), on_huddle(), on_progress(), _is_automated_nudge(), _is_participant_turn(), _sanitize_error_text() (+1 more)

### Community 2 - "gemini_client.py"
Cohesion: 0.03
Nodes (43): ClaudeAdapter, _append_user_turn(), _attach_signature_to_parts(), _clone_part_with_sig(), _clone_part_with_text(), _coerce_part(), _decode_sig_bytes(), _extract_call_syntax() (+35 more)

### Community 3 - "react"
Cohesion: 0.04
Nodes (99): lucide-react, react, react-router-dom, createChatEvent(), getAgents(), getConfig(), getEventDocument(), getEvents() (+91 more)

### Community 4 - "client.ts"
Cohesion: 0.03
Nodes (115): @tanstack/react-query, ApiError, bulkDeleteObservations(), deleteNote(), deleteObservation(), exportObservations(), ExtractionResult, fetchApi() (+107 more)

### Community 5 - "logging"
Cohesion: 0.04
Nodes (11): _heartbeat(), create_adapter(), record_token_usage(), get_blackboard(), _load_name_mapping(), SpawnStatus, get_current_shift(), get_shift_detail() (+3 more)

### Community 6 - "main.py"
Cohesion: 0.02
Nodes (34): Architect, AgentClient, Developer, _patch_enum_fields(), set_incident_options(), SysAdmin, set_oidc_adapter(), get_aligner() (+26 more)

### Community 7 - "queue.py"
Cohesion: 0.03
Nodes (62): get_token_meter(), can_approve_event(), can_override_domain(), can_rename_event(), get_user_from_request(), _normalize_email(), get_archivist(), get_brain() (+54 more)

### Community 8 - "EventSidebar.tsx"
Cohesion: 0.05
Nodes (83): getJiraMissions(), HeadhunterTodo, postJiraAction(), ActiveEvent, ReportFull, ReportMeta, DeferCountdownBar(), GridTile() (+75 more)

### Community 9 - "GitLabPlatform"
Cohesion: 0.05
Nodes (6): _get_allowed_mention_authors(), _get_static_maintainer_emails(), GitLabPlatform, _reconcile_synthetic(), _check_one(), _valid_positive_int()

### Community 10 - "brain.py"
Cohesion: 0.04
Nodes (37): _build_active_overlay(), _build_event_state_tail_block(), _build_transient_overlays(), _build_turn0_anchor(), _call_anchor_get(), _call_anchor_set_nx(), _close_unanswered_fc(), _collect_turn_overlay_part() (+29 more)

### Community 11 - "os"
Cohesion: 0.04
Nodes (27): _sanitize_lesson_text(), PlatformBreakerStatus, PlatformQueueItem, _safe_int(), list_incidents(), get_installation_manager(), is_shared_installation_manager(), reset_installation_manager() (+19 more)

### Community 12 - "tool_gates.py"
Cohesion: 0.05
Nodes (79): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+71 more)

### Community 13 - "Headhunter"
Cohesion: 0.05
Nodes (8): Headhunter, _maybe_refresh_snapshot(), _on_gh_phase_b_created(), _iref(), _process_issue(), _try_queue_issue(), _on_gl_phase_b_created(), HeadhunterOperationError

### Community 15 - "models.py"
Cohesion: 0.04
Nodes (29): AppNode, ChatRequest, ChatResponse, CIAnalysis, EventEvidence, EventInput, EventMetrics, FlowMetricsResponse (+21 more)

### Community 16 - "ReconcileScheduler"
Cohesion: 0.04
Nodes (7): FlowCollector, FairQueue, ReconcileScheduler, Trigger, QueueTrigger, ResyncTrigger, StalenessGuard

### Community 17 - "http-handler.js"
Cohesion: 0.08
Nodes (62): is429Error(), registerMCPsAndHooks(), resolveCommand(), writeAgyMcpServer(), writeClaudeMcpServer(), parsePositiveInt(), buildArgoCDMcpConfig(), createAppJWT() (+54 more)

### Community 18 - "._process_with_llm"
Cohesion: 0.04
Nodes (14): _batch_is_terminal_for_flush(), _BatchContext, _is_close_phase_fc(), _retry_backoff_delay(), _wait_for_user_admissible(), can_transition_to_close(), build_global_core_si(), canonical_wire_tools() (+6 more)

### Community 19 - "TurnBubble.tsx"
Cohesion: 0.07
Nodes (48): @uiw/react-markdown-preview, approveEvent(), closeEvent(), enforceCasualDomain(), getEventReport(), rejectEvent(), submitFeedback(), MessageStatus (+40 more)

### Community 20 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 21 - "App.tsx"
Cohesion: 0.06
Nodes (46): react-dom, dismissProposals(), EnhancementProposal, getHandoffReports(), getProposals(), getWSAuthFailureCallback(), HandoffReport, setOnUnauthorized() (+38 more)

### Community 22 - "slack.py"
Cohesion: 0.06
Nodes (8): DashboardWSAdapter, can_append_message(), _claims_to_user(), get_user_from_slack(), get_user_from_websocket(), prompt_display_name(), resolve_approval_identity(), _validate_jwt()

### Community 23 - "Service"
Cohesion: 0.05
Nodes (7): Service, get_graph_data(), get_mermaid_diagram(), get_service_details(), get_topology(), list_services(), calculate_health_from_argocd()

### Community 24 - "useMemory.ts"
Cohesion: 0.08
Nodes (47): applyLessons(), correctMemory(), createKnowledge(), createLesson(), deleteKnowledge(), deleteLesson(), ExtractedCorrection, ExtractedLesson (+39 more)

### Community 25 - "EventChatPanel.tsx"
Cohesion: 0.07
Nodes (44): CiContext, ConversationTurn, TokenUsageDict, CiContextCard(), CiContextCardProps, ConsoleTailBlock(), FailedJobRow(), EventChatPanel() (+36 more)

### Community 26 - "nightwatcher_tools.py"
Cohesion: 0.08
Nodes (23): PulseContext, ShiftIncident, ShiftInvestigation, extract_full_links(), build_extend_tool(), build_report_tool(), build_summary_tool(), execute_tool() (+15 more)

### Community 29 - "handlers_integration.py"
Cohesion: 0.08
Nodes (22): _do_retrigger(), _get_jira_reporter(), handle_refresh_github_context(), _emit(), handle_refresh_gitlab_context(), handle_refresh_kargo_context(), _is_darwin_reentrant_caller(), _is_positive_int() (+14 more)

### Community 30 - "KargoObserver"
Cohesion: 0.09
Nodes (9): build_verification_dedup_key(), extract_latest_verification(), is_verification_stale(), _parse_ts(), project_stage_status(), resolve_stage_freight(), _s(), KargoObserver (+1 more)

### Community 31 - "merge-guard.js"
Cohesion: 0.04
Nodes (46): API_VALUED, ARGO_MUTATING, ARGO_READ_SUB, ARGO_READ_TOP, BODY_FLAG, BROWSER_READ, CTX, ENV_BUILTINS (+38 more)

### Community 32 - "StreamGrid.tsx"
Cohesion: 0.08
Nodes (38): AgentStreamCard(), AgentStreamCardProps, MessageCards(), Dashboard(), GridTile(), GridTileProps, TileType, InlineMarkdownViewer() (+30 more)

### Community 33 - "cli-executor.js"
Cohesion: 0.09
Nodes (37): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, MAX_TASK_WALL_MS, MAX_TIMER_MS, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS, STORAGE_PRETASK_TIMEOUT_MS, resolveStorageRoot }, buildCLICommand(), buildTimeoutResult(), { checkAndRecycleStorage, pinTaskCwd, unpinTaskCwd }, CLAUDE_JSON_PATH, cp, createInactivityWatchdog(), executeCLI() (+29 more)

### Community 34 - "storage-recycler.js"
Cohesion: 0.08
Nodes (37): withTaskStorage(), MAX_TASK_WALL_MS, parseTimerMs(), resolveStorageRoot(), resolveTimeoutMs(), ROLE_TIMEOUTS, STORAGE_ACTIVITY_HEARTBEAT_MS, STORAGE_MAX_TIER3_DELETIONS (+29 more)

### Community 35 - "ToolContext"
Cohesion: 0.09
Nodes (9): handle_message_agent(), handle_reply_to_agent(), handle_select_agent(), _sticky_work_style(), handle_defer_event(), handle_hold_watch(), handle_wait_for_agent(), handle_wait_for_jarvis() (+1 more)

### Community 36 - "KnowledgeGraphStore"
Cohesion: 0.09
Nodes (9): _format_graph_context(), get_graph_context(), _parse_props(), _sanitize(), translate_to_lookups(), _acquire(), KnowledgeGraphStore, _sanitize() (+1 more)

### Community 37 - "context_parts.py"
Cohesion: 0.08
Nodes (19): _apply_sibling_signature(), build_function_response(), build_single_function_response(), compress_contents(), _compress_single_msg_parts(), estimate_msg_tokens(), estimate_tokens(), extract_model_parts() (+11 more)

### Community 38 - "sanitize_untrusted_line"
Cohesion: 0.09
Nodes (20): _clean_lines(), format_event_state_tail(), _build_closed_block(), build_event_header(), _build_identity_block(), build_immutable_event_anchor(), _build_journal_block(), _build_mermaid_block() (+12 more)

### Community 39 - "ConversationTurn"
Cohesion: 0.14
Nodes (25): emit_tool_result(), handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_ask_release_ai(), handle_comment_jira_issue(), handle_fetch_jira_issue(), handle_greenwave() (+17 more)

### Community 40 - "dispatch.py"
Cohesion: 0.09
Nodes (13): _build_prompt(), _check_security(), consume_wake_task(), _consume(), _dispatch_timeout_s(), dispatch_to_agent(), _consume_queue(), _sanitize_stdout() (+5 more)

### Community 41 - "jenkins_observer.py"
Cohesion: 0.07
Nodes (15): _annotation_replace(), _strip_pipeline_annotations(), _clamp_confidence(), _parse_job_metadata(), _prepare_console_tail(), _redact_build_parameters(), _redact_match(), _redact_secrets_in_text() (+7 more)

### Community 42 - "formatter.py"
Cohesion: 0.08
Nodes (18): build_access_denied_home_view(), build_home_tab_view(), _context_line(), create_feedback_block(), extract_tables(), _replace(), format_plan_block(), format_task_card() (+10 more)

### Community 43 - "VcsPlatformPort"
Cohesion: 0.07
Nodes (3): PlatformSnapshot, VcsWorkItem, VcsPlatformPort

### Community 45 - "SlackChannel"
Cohesion: 0.08
Nodes (3): get_agent_notification_text(), get_turn_attachment_color(), SlackChannel

### Community 46 - "UserContext"
Cohesion: 0.09
Nodes (14): require_auth(), require_obs_admin(), UserContext, approve_mission(), dismiss_mission(), _infer_phase(), _jira_config(), list_missions() (+6 more)

### Community 48 - "TimeKeeperPage.tsx"
Cohesion: 0.12
Nodes (24): createSchedule(), deleteSchedule(), getSchedules(), refineInstructions(), ScheduleCreatePayload, ScheduleItem, toggleSchedule(), updateSchedule() (+16 more)

### Community 49 - "ws-client.js"
Cohesion: 0.10
Nodes (26): clearIdleTimer(), {
  DEFAULT_WORK_DIR, AGENT_CLI, AGENT_MODEL, AGENT_ROLE,
  EVENT_ID, EPHEMERAL, IDLE_TIMEOUT_MS,
  CLI_429_MAX_RETRIES, CLI_429_INITIAL_DELAY_MS, CLI_429_BACKOFF_MULTIPLIER,
  resolveTimeoutMs, parsePositiveInt, MAX_TASK_WALL_MS, MAX_TIMER_MS,
}, { ensureEventDocument }, { executeCLIStreaming, prepareResultsDir, is429Error }, { filterSkillsByRole, filterSkillsByMode, swapActiveRules, restoreAllSkills }, fs, handleCancel(), handleTask() (+18 more)

### Community 50 - "observations_mgmt.py"
Cohesion: 0.09
Nodes (15): get_report_client(), _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), render_pdf(), _sample_points() (+7 more)

### Community 51 - "create_schedule"
Cohesion: 0.06
Nodes (6): create_schedule(), delete_schedule(), get_schedule(), list_schedules(), toggle_schedule(), update_schedule()

### Community 52 - "KubernetesSpawnHealthAdapter"
Cohesion: 0.09
Nodes (4): KubernetesSpawnHealthAdapter, _PodHealthState, SpawnHealthPort, SpawnPollResult

### Community 53 - "ui/package.json"
Cohesion: 0.08
Nodes (29): autoprefixer, cronstrue, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, graphology-layout-forceatlas2 (+21 more)

### Community 55 - "useCortexData.ts"
Cohesion: 0.16
Nodes (28): getCognitiveGraph(), getCortexActivity(), getKGServiceDetail(), getKGServices(), getKGStats(), getKnowledgeById(), getLessonById(), getMemory() (+20 more)

### Community 56 - "EphemeralProvisioner"
Cohesion: 0.09
Nodes (3): DispatchMetrics, EphemeralProvisioner, SpawnFailed

### Community 57 - ".list_observations"
Cohesion: 0.07
Nodes (5): get_all_journal(), get_service_journal(), get_event_observations(), get_global_observations(), export_observations()

### Community 58 - "EventDrillDown.tsx"
Cohesion: 0.13
Nodes (23): three, getEventPulses(), BrainCore(), CortexDevPage(), devQueryClient, CortexLiveFeedProps, EventDrillDown(), EventDrillDownProps (+15 more)

### Community 59 - "AgentRegistry"
Cohesion: 0.09
Nodes (4): AgentConnection, AgentRegistry, agent_websocket_handler(), set_registry_and_bridge()

### Community 60 - "Any"
Cohesion: 0.12
Nodes (3): VcsContext, _NoAliasSafeLoader, _validate_plan_yaml()

### Community 61 - "QuotaTracker"
Cohesion: 0.08
Nodes (7): get_quota_tracker(), QuotaExhaustedError, QuotaTracker, RequestExceedsBurstError, _stale_reservation_ttl_s(), llm_stats(), receive_telemetry()

### Community 62 - "NightwatcherObserver"
Cohesion: 0.11
Nodes (6): ShiftReport, _append_user_turn(), _env_float(), _env_int(), NightwatcherObserver, _finalize_analysis_handover()

### Community 63 - "CortexGraph.tsx"
Cohesion: 0.13
Nodes (26): graphology, @react-sigma/core, eventColor(), getExecutiveNeurons(), getStructuralEdges(), DEFAULT_TYPE_BUDGET, evictLru(), KNOWLEDGE_RING (+18 more)

### Community 64 - "._poll_pr_feedback"
Cohesion: 0.08
Nodes (3): _get_static_maintainer_emails(), _iso(), _parse_ts()

### Community 65 - "state/ports.py"
Cohesion: 0.10
Nodes (7): ArchitectureEvent, EventType, HealthStatus, MessageStatus, NodeType, infer_node_type(), MetricsRepository

### Community 66 - "TopologyRepository"
Cohesion: 0.08
Nodes (3): Snapshot, TopologySnapshot, TopologyRepository

### Community 68 - "NodeInspector.tsx"
Cohesion: 0.13
Nodes (24): getClosedEvents(), ArchitectureEvent, ArgoCDOperation, ArchitectureGraph(), EVENT_LABELS, EventItem(), EventItemProps, healthTone() (+16 more)

### Community 69 - "llm_error_classifier.py"
Cohesion: 0.13
Nodes (9): _extract_status_code(), _has_non_retryable_cause(), _is_google_auth_transport_error(), is_rate_limit(), is_transient(), is_transient_llm_error_turn(), _iter_exception_chain(), _matches_mro() (+1 more)

### Community 70 - "server.js"
Cohesion: 0.09
Nodes (18): { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, ensureEventDocument(), fs, path, stageEventDocument(), fetchEventDocument(), fs, { handleRequest } (+10 more)

### Community 71 - "cognitive_graph.py"
Cohesion: 0.11
Nodes (11): get_pulse_tracker(), dismiss_proposals(), DismissRequest, get_all_shadow_interventions(), get_cognitive_graph(), get_cortex_activity(), get_cortex_status(), get_event_shadow_interventions() (+3 more)

### Community 72 - "PulseBatch"
Cohesion: 0.10
Nodes (4): PulseBatch, PulsePort, PulseObserver, PulseTracker

### Community 74 - "handlers_lookup.py"
Cohesion: 0.11
Nodes (8): _safe_int(), _format_bounded_journal(), handle_consult_deep_memory(), handle_google_web_search(), handle_lookup_journal(), _safe_seconds(), IdleTimeoutPort, StateWatcherPort

### Community 76 - "dependencies"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 77 - "NeuronInfoPanel.tsx"
Cohesion: 0.11
Nodes (22): KGServiceDetail, AGENTS, DOMAINS, HEMISPHERE_X, NEURON_DESCRIPTIONS, PHASE_SKILL_FOLDERS, PHASE_TOOL_PRIORITY, PHASES (+14 more)

### Community 80 - "start_headhunter_task"
Cohesion: 0.09
Nodes (3): redact_error_text(), on_headhunter_done(), start_headhunter_task()

### Community 84 - "EventHistory.tsx"
Cohesion: 0.15
Nodes (19): getReport(), getReports(), CompactCardStrip(), EventHistory(), TimeRange, ViewMode, EventHistoryGrid(), EventHistoryTable() (+11 more)

### Community 85 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 86 - "reconcile.py"
Cohesion: 0.17
Nodes (10): generate_phase_tool_map(), _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers(), main() (+2 more)

### Community 87 - "claude-guard.js"
Cohesion: 0.14
Nodes (18): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+10 more)

### Community 88 - "AsyncGitHubClient"
Cohesion: 0.17
Nodes (5): AsyncGitHubClient, _handle_rate_limit(), _paginate_github_get(), parse_github_next_link(), _safe_parse_int()

### Community 89 - "FlowHistoryPage.tsx"
Cohesion: 0.23
Nodes (16): recharts, getFlowHistory(), FlowSnapshot, FlowHistoryPage(), RANGES, SparkCard(), SparkCardProps, formatTime() (+8 more)

### Community 90 - "._feedback_reject_reason"
Cohesion: 0.11
Nodes (7): _bot_login(), _csv_env(), _consider(), _is_slash_command_only(), _mention_pattern(), _review_ignore_logins(), _review_trusted_associations()

### Community 91 - "Any"
Cohesion: 0.13
Nodes (4): handle_app_home_opened(), handle_approve(), handle_approve_sha(), handle_reject()

### Community 92 - "cli-setup.js"
Cohesion: 0.13
Nodes (18): { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync }, filterSkillsByMode() (+10 more)

### Community 94 - "spawn_event_namer_task"
Cohesion: 0.20
Nodes (8): spawn_event_namer_task(), format_event_summary(), handle_app_mention(), handle_create_event_modal(), handle_darwin_command(), handle_home_create_event(), on_dm_message(), fallback_title()

### Community 95 - "devDependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 96 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 97 - "gemini-sidecar/package.json"
Cohesion: 0.11
Nodes (18): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+10 more)

### Community 98 - "ServiceNode.tsx"
Cohesion: 0.15
Nodes (13): @xyflow/react, HealthStatus, NodeType, AppNodeData, ARGOCD_HEALTH_COLORS, SYNC_ICONS, NamespaceGroupNodeData, GENERIC_TAGS (+5 more)

### Community 99 - "get_report"
Cohesion: 0.11
Nodes (6): get_report(), list_reports(), reports_spa_no_slash(), reports_spa_with_slash(), search_reports(), _serve_spa()

### Community 100 - "JiraIncidentAdapter"
Cohesion: 0.15
Nodes (3): _adf_to_text(), _escape_jql_string(), JiraIncidentAdapter

### Community 103 - "headhunter_pending_todos"
Cohesion: 0.18
Nodes (12): _extract_snapshot_items(), _github_active_item(), headhunter_pending_todos(), _normalized_row_keys(), headhunter_platform_status(), _match_snapshot_item(), _pending_row_keys(), _read_headhunter_snapshot_safe() (+4 more)

### Community 105 - "ShiftsPage.tsx"
Cohesion: 0.23
Nodes (16): getCurrentShift(), getShiftDetail(), getShiftsList(), ShiftReportFull, ShiftReportSummary, FailedClusterBadge(), getISOWeek(), getWeekDates() (+8 more)

### Community 106 - "catalog-skills.js"
Cohesion: 0.16
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 108 - "ArchitectureGraph.tsx"
Cohesion: 0.18
Nodes (15): @dagrejs/dagre, applyDagreLayout(), applyGridLayout(), applyLayout(), ArchitectureGraphInner(), buildGraph(), computeIdHash(), edgeTypes (+7 more)

### Community 109 - "JenkinsPlatformPort"
Cohesion: 0.12
Nodes (4): BuildDetails, JenkinsPlatformPort, JobRunState, ViewScanResult

### Community 116 - "maintainers.py"
Cohesion: 0.20
Nodes (8): _resolve_maintainer_enum(), _dedupe(), _extract_evidence_maintainer_emails(), is_slack_recipient_allowed(), maintainer_env_key(), _resolve_evidence_env_maintainer_emails(), resolve_maintainer_emails(), _resolve_static_env_emails()

### Community 117 - "has_unevaluated_close_blocker"
Cohesion: 0.14
Nodes (7): has_unevaluated_close_blocker(), _pred_jarvis_response(), _pred_unevaluated_close(), is_jarvis_acknowledgment(), is_stabilization_wake(), safe_score(), strip_stabilization_wake_prefix()

### Community 118 - "cortex/types.ts"
Cohesion: 0.17
Nodes (14): EventSource, KGServiceEntity, CortexGraphProps, GraphLoaderProps, PulseTimelineProps, CognitiveGraphResponse, CortexHeartbeatMessage, FrictionIndicator (+6 more)

### Community 128 - "handlers_planning.py"
Cohesion: 0.23
Nodes (7): _auto_complete_step(), _canonical_role(), handle_create_plan(), handle_get_plan_progress(), _is_failed_turn(), _is_orchestrator_turn(), _normalize_step_id()

### Community 131 - "nightwatcher_prompt.py"
Cohesion: 0.16
Nodes (6): StagedEscalation, build_manifest_table(), build_report_iteration_prompt(), build_summary_prompt(), build_system_prompt(), extract_event_links()

### Community 132 - "analyzeTokens"
Cohesion: 0.19
Nodes (13): analyzeString(), analyzeTokens(), assignName(), base(), combineCategories(), configEnvGuard(), configFileWriteGuard(), hasSubseq() (+5 more)

### Community 133 - "generate_map.py"
Cohesion: 0.19
Nodes (5): _enumerate_gates(), _GateInfo, _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 135 - "._extract_context_flags"
Cohesion: 0.15
Nodes (3): compute_dispatch_backpressure(), ContextFlags, _safe_int_env()

### Community 136 - "evaluate_gates"
Cohesion: 0.15
Nodes (7): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), is_wait_for_user_admissible_after_response(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 140 - "handle_report_incident"
Cohesion: 0.17
Nodes (3): handle_report_incident(), _resolve_escalation_scope(), IncidentAdapterPort

### Community 143 - "testSetup.ts"
Cohesion: 0.18
Nodes (5): @tailwindcss/vite, @testing-library/react, vite, @vitejs/plugin-react, vitest

### Community 147 - "create_chat_event"
Cohesion: 0.20
Nodes (3): ChatEventRequest, ChatEventResponse, create_chat_event()

### Community 151 - "CortexLiveFeed.tsx"
Cohesion: 0.27
Nodes (9): CortexHeartbeat(), CortexHeartbeatProps, ensureKeyframes(), CortexLiveFeed(), FILTER_PILLS, FilterKey, getStoredFilter(), MESSAGE_STYLES (+1 more)

### Community 152 - "gitGuard"
Cohesion: 0.29
Nodes (10): bareBranchProtected(), configWriteGuard(), externalGitCommand(), gitGuard(), gitQuery(), isProtected(), normRef(), pushGuard() (+2 more)

### Community 153 - "parseShell"
Cohesion: 0.33
Nodes (10): bodySubstitutions(), decodeAnsiC(), isArrayAssignPrefix(), isWordStart(), matchBacktick(), matchParen(), parseShell(), readHeredocStart() (+2 more)

### Community 154 - "generate_event_title"
Cohesion: 0.22
Nodes (3): generate_event_title(), get_adapter(), _get_semaphore()

### Community 159 - "entity_extractor.py"
Cohesion: 0.33
Nodes (5): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship

### Community 161 - "knowledge_graph_api.py"
Cohesion: 0.31
Nodes (4): get_kg_store(), get_service_detail(), get_stats(), list_services()

### Community 164 - "classifyTool"
Cohesion: 0.31
Nodes (9): apiTokens(), apiWriteNeedsGuard(), branchValues(), classifyTool(), hasOpaqueTarget(), httpGuard(), httpMethod(), isReadMethod() (+1 more)

### Community 166 - "handlers_cross_event.py"
Cohesion: 0.33
Nodes (4): _coerce_turn_int(), handle_recall_pruned_turns(), _parse_turn_int(), _sanitize_recalled()

### Community 170 - "build_gate_context"
Cohesion: 0.22
Nodes (4): build_gate_context(), conversation_has_decayed_turns(), _decay_payload_len(), decay_cutoff_index()

### Community 173 - "handle_notify_user_slack"
Cohesion: 0.25
Nodes (4): _alert_wrapper_retrigger(), handle_notify_user_slack(), _resolve_slack_user(), build_event_report_md()

### Community 179 - "adf_to_markdown"
Cohesion: 0.57
Nodes (7): adf_to_markdown(), _apply_marks(), _children(), _render(), _render_list(), _render_list_item(), _render_table_like()

### Community 180 - "validate-mutations.sh"
Cohesion: 0.57
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

### Community 184 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 185 - "state.js"
Cohesion: 0.33
Nodes (4): { AGENT_ROLE }, _blackboardTurns, _inboundMessages, _teammateMessages

### Community 201 - "TicketNode.tsx"
Cohesion: 0.40
Nodes (4): STATUS_COLORS, TICKET_COLORS, TicketNodeComponent(), TicketNodeData

### Community 202 - "classify"
Cohesion: 0.50
Nodes (4): classify(), main(), shellCategory(), shellNeedsGuard()

### Community 220 - "overrides"
Cohesion: 0.67
Nodes (3): overrides, @typescript-eslint/typescript-estree, minimatch

## Knowledge Gaps
- **13 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+8 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2639 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **129 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `Brain`, `ScheduleRepository`, `nightwatcher_prompt.py`, `logging`, `main.py`, `queue.py`, `brain.py`, `os`, `models.py`, `._process_with_llm`, `create_chat_event`, `slack.py`, `Service`, `nightwatcher_tools.py`, `generate_event_title`, `KargoObserver`, `ConversationTurn`, `jenkins_observer.py`, `get_event_document`, `_is_event_closed_or_missing`, `UserContext`, `LiveAPIAdapter`, `ConversationMessage`, `._update_event_vcs_context`, `observations_mgmt.py`, `create_schedule`, `update_notebook_note`, `.list_observations`, `NightwatcherObserver`, `rename_observation`, `._restage_pending_signal`, `state/ports.py`, `TopologyRepository`, `BrainSkillLoader`, `submit_feedback`, `get_notebook`, `._count_pending`, `._downsample_snapshots`, `.is_github_pr_feedback_seen`, `._stage_pending_signal`, `handlers_lookup.py`, `delete_notebook_note`, `delete_observation`, `.cleanup_stale_services`, `.drain_notes`, `.get_edge_metadata`, `report_tampering`, `get_report`, `HeadhunterJira`, `headhunter_pending_todos`, `.clear_event_approval`, `._validate_gitlab_ids`?**
  _High betweenness centrality (0.098) - this node is a cross-community bridge._
- **Are the 81 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 81 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.00979164803719932 - nodes in this community are weakly interconnected._
- **Why does `Brain` connect `Brain` to `BlackboardState`, `main.py`, `._extract_context_flags`, `queue.py`, `brain.py`, `models.py`, `ReconcileScheduler`, `._process_with_llm`, `IdleTimeoutManager`, `slack.py`, `._resolve_llm_params`, `._post_agent_recall`, `sanitize_untrusted_line`, `ConversationTurn`, `dispatch.py`, `._detect_repetition_collapse`, `._escalation_blocked`, `state/ports.py`, `BrainSkillLoader`, `PulseBatch`, `._enrich_graph_from_agent`, `._extract_jira_context`, `._github_pr_differs`, `.set_headhunter_close_signal`, `ReflexSearcher`, `StateWatcher`, `JarvisPeerPort`, `BrainLifecyclePort`?**
  _High betweenness centrality (0.073) - this node is a cross-community bridge._
- **Are the 20 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Should `Brain` be split into smaller, more focused modules?**
  _Cohesion score 0.022220559628909172 - nodes in this community are weakly interconnected._