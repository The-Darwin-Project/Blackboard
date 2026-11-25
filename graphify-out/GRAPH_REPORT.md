# Graph Report - Blackboard  (2026-11-25)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 5938 nodes · 13908 edges · 216 communities (110 shown, 106 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 1079 edges (avg confidence: 0.89)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `77e66450`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BlackboardState
- os
- models.py
- Brain
- main.py
- client.ts
- EventSidebar.tsx
- Archivist
- WorkspaceInspector.tsx
- brain.py
- dispatch.py
- App.tsx
- tool_gates.py
- EventRepository
- queue.py
- headhunter.py
- Headhunter
- http-handler.js
- ._process_with_llm
- fetchApi
- jenkins-mcp.js
- .get_event
- useMemory.ts
- EventDocument
- BrainSkillLoader
- GitLabPlatform
- .get_graph_data
- useQueue.ts
- _BrainToolContext
- llm/__init__.py
- approval_decision.py
- KargoObserver
- ActiveStreamsContext.tsx
- cli-executor.js
- GeminiAdapter
- handlers_integration.py
- context_parts.py
- storage-recycler.js
- formatter.py
- Aligner
- ConversationTurn
- sanitize_untrusted_line
- KnowledgeGraphStore
- ToolContext
- ._get
- SlackChannel
- CortexGraph.tsx
- LiveAPIAdapter
- GitHubPlatform
- TokenMeter
- reconcile.py
- types.py
- useTimeKeeper.ts
- ws-client.js
- ArchitectureGraph.tsx
- BrainLifecyclePort
- ._github_poll_and_process
- get_quota_registry
- BoolOutcome
- auth.py
- handlers_lookup.py
- ._poll_pr_feedback
- vcs_approval.py
- JenkinsObserver
- useCortexData.ts
- spawn_event_namer_task
- ._triage_and_build_evidence
- ConversationTurn
- EventDrillDown.tsx
- llm_error_classifier.py
- observations_mgmt.py
- server.js
- ._poll_issues
- cognitive_graph.py
- NodeInspector.tsx
- JenkinsAdapter
- QuotaTracker
- ArgoCDObserver
- handlers_dispatch.py
- slack.py
- TopologyRepository
- TokenUtilizationPage.tsx
- PulseBatch
- _process_decision
- slack_approvals.py
- EventType
- AsyncGitHubClient
- OpsStateContext.tsx
- gemini_client.py
- claude-guard.js
- jenkins.py
- ._feedback_reject_reason
- ._fetch_checks_and_legacy_status
- cli-setup.js
- ReflexSearcher
- FairQueue
- EphemeralProvisioner
- get_report
- .start_event_loop
- utils/__init__.py
- EventStatus
- ReconcileScheduler
- ObservationRepository
- GitHubAppAuth
- ShiftsPage.tsx
- catalog-skills.js
- StateWatcher
- reanalyze_mission
- EscalationRepository
- ._tool_send_event_message
- MultiInstallationManager
- github_app.py
- ._normalize_issue
- OIDCKeyAdapter
- KubernetesSpawnHealthAdapter
- HeadhunterJira
- ._process_candidates
- IncidentAdapterPort
- ._connect
- handlers_planning.py
- ScheduleRepository
- NeuronInfoPanel.tsx
- evaluate_gates
- ScheduleCreateRequest
- IdleTimeoutManager
- JarvisMemoryPage.tsx
- HeadhunterItemActionRequest
- CortexLiveFeed.tsx
- usage-tracker.js
- ._latest_bot_comment
- GitLabTokenAuth
- cortex/types.ts
- generate_event_title
- ._extract_context_flags
- ._post_agent_recall
- entity_extractor.py
- has_unevaluated_close_blocker
- knowledge_graph_api.py
- SpawnPollResult
- resolve_ca_bundle
- .poll_active_events_wakeup
- _get_canonical_or_alias
- MessageStatus
- create_chat_event
- Trigger
- ._evaluate_health
- TimeKeeperObserver
- CortexRepository
- adf_to_markdown
- update_schedule
- FilterRule
- ._cleanup_stale_events
- ._detect_repetition_collapse
- update_notebook_note
- llm_stats
- state.js
- io
- _compute_processed_up_to
- DispatchMetrics
- SpawnStatus
- list_failed_stages
- dex_proxy
- ._wait_for_registration
- StalenessGuard
- _NoAliasSafeLoader
- _WSFrameFilter
- _env_flag
- get_intermediate_tools
- get_event_flow
- findDuplicateJsonKeys.ts
- gh-wrapper.sh
- huddleSendMessage.sh
- sendResults.sh
- _decay_payload_len
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
1. `BlackboardState` - 332 edges
2. `Brain` - 170 edges
3. `ConversationTurn` - 157 edges
4. `ToolContext` - 103 edges
5. `EventDocument` - 102 edges
6. `GateContext` - 100 edges
7. `GitHubPlatform` - 99 edges
8. `EventRepository` - 97 edges
9. `Headhunter` - 89 edges
10. `GitLabPlatform` - 72 edges

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

## Communities (216 total, 106 thin omitted)

### Community 0 - "BlackboardState"
Cohesion: 0.01
Nodes (12): get_all_journal(), get_service_journal(), delete_notebook_note(), get_notebook(), get_event_observations(), get_global_observations(), create_schedule(), delete_schedule() (+4 more)

### Community 1 - "os"
Cohesion: 0.02
Nodes (48): JiraIncidentAdapter, _sanitize_lesson_text(), _get_static_maintainer_emails(), _safe_int(), create_adapter(), record_token_usage(), QuotaExhaustedError, RequestExceedsBurstError (+40 more)

### Community 2 - "models.py"
Cohesion: 0.02
Nodes (47): get_blackboard(), AppNode, ApprovalCommitResult, ApprovalOption, ApprovalResolution, ChatRequest, ChatResponse, CIAnalysis (+39 more)

### Community 3 - "Brain"
Cohesion: 0.02
Nodes (8): Brain, on_huddle(), on_progress(), on_huddle(), on_progress(), _is_automated_nudge(), _sanitize_error_text(), get_registry_and_bridge()

### Community 4 - "main.py"
Cohesion: 0.02
Nodes (36): Architect, AgentClient, Developer, set_incident_options(), SysAdmin, TaskBridge, set_oidc_adapter(), get_aligner() (+28 more)

### Community 5 - "client.ts"
Cohesion: 0.03
Nodes (99): ApiError, bulkDeleteObservations(), deleteNote(), deleteObservation(), exportObservations(), ExtractionResult, generateObservationsReport(), getActiveEvents() (+91 more)

### Community 6 - "EventSidebar.tsx"
Cohesion: 0.04
Nodes (79): getJiraMissions(), getReport(), getReports(), postJiraAction(), ReportSearchParams, searchReports(), ReportFull, ReportMeta (+71 more)

### Community 7 - "Archivist"
Cohesion: 0.04
Nodes (5): Archivist, Pulse, _decode_cursor(), _encode_cursor(), VectorStore

### Community 8 - "WorkspaceInspector.tsx"
Cohesion: 0.05
Nodes (75): createChatEvent(), updateEventTitle(), CiContext, EventEvidence, TokenUsageDict, ApprovalWriteInBox(), Props, ChatInput() (+67 more)

### Community 9 - "brain.py"
Cohesion: 0.04
Nodes (42): _batch_is_terminal_for_flush(), _build_active_overlay(), _build_event_state_tail_block(), _build_transient_overlays(), _build_turn0_anchor(), _call_anchor_get(), _call_anchor_set_nx(), _close_unanswered_fc() (+34 more)

### Community 10 - "dispatch.py"
Cohesion: 0.04
Nodes (26): AgentConnection, AgentRegistry, agent_websocket_handler(), _heartbeat(), _build_prompt(), _check_security(), _commit_with_task_cap(), consume_wake_task() (+18 more)

### Community 11 - "App.tsx"
Cohesion: 0.05
Nodes (60): getConfig(), getEvents(), getFlowMetrics(), getIncidents(), getWSAuthFailureCallback(), Incident, setOnUnauthorized(), setTokenGetter() (+52 more)

### Community 12 - "tool_gates.py"
Cohesion: 0.05
Nodes (79): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+71 more)

### Community 14 - "queue.py"
Cohesion: 0.05
Nodes (43): get_archivist(), aligner_pending_items(), apply_lessons(), ApproveRequest, CloseRequest, correct_memory(), CorrectMemoryRequest, create_knowledge() (+35 more)

### Community 15 - "headhunter.py"
Cohesion: 0.04
Nodes (12): HeadhunterCircuitBreaker, HeadhunterOperationError, PlatformQueueItem, PlatformSnapshot, redact_error_text(), VcsWorkItem, on_headhunter_done(), VcsPlatformPort (+4 more)

### Community 16 - "Headhunter"
Cohesion: 0.05
Nodes (4): Headhunter, _process_issue(), VcsContext, _validate_plan_yaml()

### Community 17 - "http-handler.js"
Cohesion: 0.07
Nodes (64): is429Error(), registerMCPsAndHooks(), resolveCommand(), writeAgyMcpServer(), writeClaudeMcpServer(), buildArgoCDMcpConfig(), createAppJWT(), discoverAndGenerateTokens() (+56 more)

### Community 18 - "._process_with_llm"
Cohesion: 0.04
Nodes (9): _BatchContext, _ensure_recall_tool_if_needed(), _QuotaShedState, _retry_backoff_delay(), build_global_core_si(), canonical_wire_tools(), compute_prefix_hashes(), sha8_json() (+1 more)

### Community 19 - "fetchApi"
Cohesion: 0.07
Nodes (50): approveEvent(), closeEvent(), enforceCasualDomain(), fetchApi(), getAlignerPending(), getEventReport(), getHeadhunterPending(), getJenkinsPending() (+42 more)

### Community 20 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 21 - ".get_event"
Cohesion: 0.05
Nodes (21): get_token_meter(), get_brain(), report_tampering(), _acquire_hh_poll_lock(), approve_event(), _busy_lock_response(), close_event_by_user(), enforce_casual_domain() (+13 more)

### Community 22 - "useMemory.ts"
Cohesion: 0.07
Nodes (50): applyLessons(), correctMemory(), createKnowledge(), createLesson(), deleteKnowledge(), deleteLesson(), ExtractedCorrection, ExtractedLesson (+42 more)

### Community 23 - "EventDocument"
Cohesion: 0.04
Nodes (3): build_operational_briefing(), EventDocument, extract_jira_context()

### Community 24 - "BrainSkillLoader"
Cohesion: 0.05
Nodes (3): BrainSkillLoader, _SkillCorpus, BrainIntrospectionPort

### Community 25 - "GitLabPlatform"
Cohesion: 0.06
Nodes (3): GitLabPlatform, _valid_positive_int(), get_gitlab_auth()

### Community 26 - ".get_graph_data"
Cohesion: 0.05
Nodes (7): get_graph_data(), get_mermaid_diagram(), get_service_details(), get_topology(), list_services(), calculate_health_from_argocd(), infer_node_type()

### Community 27 - "useQueue.ts"
Cohesion: 0.09
Nodes (45): getEventDocument(), getHeadhunterStatus(), getWaitingApprovalEvents(), headhunterItemAction(), HeadhunterTodo, resetHeadhunterBreaker(), triggerHeadhunterPoll(), ContextMenu() (+37 more)

### Community 29 - "llm/__init__.py"
Cohesion: 0.07
Nodes (8): ClaudeAdapter, reset_quota_registry(), Reservation, FunctionCall, LLMChunk, LLMPort, LLMResponse, TokenUsage

### Community 30 - "approval_decision.py"
Cohesion: 0.08
Nodes (11): DashboardWSAdapter, prompt_display_name(), resolve_approval_identity(), execute_approval_decision(), ApprovalDecisionOutcome, DecisionRequest, resolve_selected_option(), validate_image_attachment() (+3 more)

### Community 31 - "KargoObserver"
Cohesion: 0.09
Nodes (9): build_verification_dedup_key(), extract_latest_verification(), is_verification_stale(), _parse_ts(), project_stage_status(), resolve_stage_freight(), _s(), KargoObserver (+1 more)

### Community 32 - "ActiveStreamsContext.tsx"
Cohesion: 0.08
Nodes (39): AgentStreamCard(), AgentStreamCardProps, MessageCards(), Dashboard(), GridTile(), GridTileProps, TileType, InlineMarkdownViewer() (+31 more)

### Community 33 - "cli-executor.js"
Cohesion: 0.09
Nodes (40): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, MAX_TASK_WALL_MS, MAX_TIMER_MS, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS, STORAGE_PRETASK_TIMEOUT_MS, resolveStorageRoot }, buildCLICommand(), buildTimeoutResult(), { checkAndRecycleStorage, pinTaskCwd, unpinTaskCwd }, CLAUDE_JSON_PATH, cp, createInactivityWatchdog(), createLineUsageEmitter() (+32 more)

### Community 34 - "GeminiAdapter"
Cohesion: 0.09
Nodes (10): _attach_signature_to_parts(), _clone_part_with_sig(), _clone_part_with_text(), _extract_part_signature(), GeminiAdapter, _is_empty_sig_carrier(), _part_has_fc(), _sanitize_candidate_parts() (+2 more)

### Community 35 - "handlers_integration.py"
Cohesion: 0.08
Nodes (22): _alert_wrapper_retrigger(), _do_retrigger(), handle_notify_user_slack(), handle_refresh_github_context(), handle_refresh_gitlab_context(), handle_refresh_kargo_context(), _is_darwin_reentrant_caller(), _is_positive_int() (+14 more)

### Community 36 - "context_parts.py"
Cohesion: 0.08
Nodes (20): _contents_have_pruned_or_decayed(), _apply_sibling_signature(), build_function_response(), build_single_function_response(), compress_contents(), _compress_single_msg_parts(), contents_have_pruned_or_decayed(), estimate_msg_tokens() (+12 more)

### Community 37 - "storage-recycler.js"
Cohesion: 0.07
Nodes (38): withTaskStorage(), MAX_TASK_WALL_MS, parsePositiveInt(), parseTimerMs(), resolveStorageRoot(), resolveTimeoutMs(), ROLE_TIMEOUTS, STORAGE_ACTIVITY_HEARTBEAT_MS (+30 more)

### Community 38 - "formatter.py"
Cohesion: 0.08
Nodes (22): build_approval_blocks(), _derive_writein_hmac_key(), _escape_mrkdwn(), format_frozen_approval_blocks(), _safe_text(), sign_writein_metadata(), build_access_denied_home_view(), build_home_tab_view() (+14 more)

### Community 40 - "ConversationTurn"
Cohesion: 0.12
Nodes (25): emit_tool_result(), handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), _get_jira_reporter(), handle_ask_release_ai(), handle_comment_jira_issue(), handle_fetch_jira_issue() (+17 more)

### Community 41 - "sanitize_untrusted_line"
Cohesion: 0.09
Nodes (20): _clean_lines(), format_event_state_tail(), _build_closed_block(), build_event_header(), _build_identity_block(), build_immutable_event_anchor(), _build_journal_block(), _build_mermaid_block() (+12 more)

### Community 42 - "KnowledgeGraphStore"
Cohesion: 0.09
Nodes (9): _format_graph_context(), get_graph_context(), _parse_props(), _sanitize(), translate_to_lookups(), _acquire(), KnowledgeGraphStore, _sanitize() (+1 more)

### Community 43 - "ToolContext"
Cohesion: 0.10
Nodes (10): handle_message_agent(), handle_reply_to_agent(), handle_classify_event(), handle_defer_event(), handle_hold_watch(), handle_request_user_approval(), handle_respond_to_jarvis(), handle_wait_for_agent() (+2 more)

### Community 45 - "SlackChannel"
Cohesion: 0.08
Nodes (4): extract_tables(), get_agent_notification_text(), get_turn_attachment_color(), SlackChannel

### Community 46 - "CortexGraph.tsx"
Cohesion: 0.09
Nodes (34): AGENTS, DOMAINS, eventColor(), getExecutiveNeurons(), getStructuralEdges(), HEMISPHERE_X, NEURON_DESCRIPTIONS, PHASE_SKILL_FOLDERS (+26 more)

### Community 48 - "GitHubPlatform"
Cohesion: 0.07
Nodes (3): GitHubPlatform, _one(), PlatformBreakerStatus

### Community 49 - "TokenMeter"
Cohesion: 0.07
Nodes (5): BoundedTeamCounter, normalize_team_id(), _zero_bucket(), TokenMeter, TokenUsageDict

### Community 50 - "reconcile.py"
Cohesion: 0.10
Nodes (15): _enumerate_gates(), _GateInfo, generate_phase_tool_map(), _load_gate_registry(), _render_markdown(), _render_ooda_overlay(), _build_redis_client(), _fetch_commit_sha() (+7 more)

### Community 51 - "types.py"
Cohesion: 0.08
Nodes (17): get_default_role_cli_map(), _get_timeout_env_warned(), _get_timeout_order_warned(), is_partial_control_token(), LLMStreamInterChunkTimeoutError, LLMStreamTimeoutError, LLMStreamTotalTimeoutError, LLMStreamTTFBTimeoutError (+9 more)

### Community 52 - "useTimeKeeper.ts"
Cohesion: 0.12
Nodes (24): createSchedule(), deleteSchedule(), getSchedules(), refineInstructions(), ScheduleCreatePayload, ScheduleItem, toggleSchedule(), updateSchedule() (+16 more)

### Community 53 - "ws-client.js"
Cohesion: 0.10
Nodes (27): buildRegisterPayload(), clearIdleTimer(), {
  DEFAULT_WORK_DIR, AGENT_CLI, AGENT_MODEL, AGENT_ROLE,
  EVENT_ID, EPHEMERAL, IDLE_TIMEOUT_MS,
  CLI_429_MAX_RETRIES, CLI_429_INITIAL_DELAY_MS, CLI_429_BACKOFF_MULTIPLIER,
  resolveTimeoutMs, parsePositiveInt, MAX_TASK_WALL_MS, MAX_TIMER_MS,
}, { ensureEventDocument }, { executeCLIStreaming, prepareResultsDir, is429Error }, { filterSkillsByRole, filterSkillsByMode, swapActiveRules, restoreAllSkills }, fs, handleCancel() (+19 more)

### Community 54 - "ArchitectureGraph.tsx"
Cohesion: 0.09
Nodes (26): HealthStatus, NodeType, AppNodeData, applyDagreLayout(), applyGridLayout(), applyLayout(), ArchitectureGraphInner(), buildGraph() (+18 more)

### Community 55 - "BrainLifecyclePort"
Cohesion: 0.06
Nodes (3): BrainLifecyclePort, BroadcastPort, JarvisPeerPort

### Community 56 - "._github_poll_and_process"
Cohesion: 0.09
Nodes (6): _maybe_refresh_snapshot(), _on_gh_phase_b_created(), _iref(), _try_queue_issue(), _on_gl_phase_b_created(), _raise_if_systemic_failure()

### Community 57 - "get_quota_registry"
Cohesion: 0.12
Nodes (14): get_quota_registry(), acquire_raw_genai(), extract_genai_usage(), finalize_raw_genai(), _int_field(), record_raw_genai_post_hoc(), rollback_raw_genai(), _analyze_series() (+6 more)

### Community 59 - "auth.py"
Cohesion: 0.10
Nodes (13): can_append_message(), can_approve_event(), can_override_domain(), can_rename_event(), _claims_to_user(), get_user_from_request(), get_user_from_websocket(), _normalize_email() (+5 more)

### Community 60 - "handlers_lookup.py"
Cohesion: 0.11
Nodes (11): _safe_int(), _coerce_turn_int(), handle_recall_pruned_turns(), _parse_turn_int(), _sanitize_recalled(), _format_bounded_journal(), handle_consult_deep_memory(), handle_lookup_journal() (+3 more)

### Community 61 - "._poll_pr_feedback"
Cohesion: 0.08
Nodes (3): _get_static_maintainer_emails(), _iso(), _parse_ts()

### Community 62 - "vcs_approval.py"
Cohesion: 0.11
Nodes (14): get_installation_manager(), normalize_gitlab_host(), ApprovalDriftResult, _effective_gitlab_context(), _effective_kargo_context(), extract_context_head_sha(), _gitlab_ctx_matches_mr_url(), is_stale_verification_gitlab_mirror() (+6 more)

### Community 64 - "useCortexData.ts"
Cohesion: 0.17
Nodes (26): getCognitiveGraph(), getCortexActivity(), getKGServiceDetail(), getKGServices(), getKGStats(), getKnowledgeById(), getMemory(), getRecentPulses() (+18 more)

### Community 65 - "spawn_event_namer_task"
Cohesion: 0.14
Nodes (9): spawn_event_namer_task(), format_event_summary(), handle_app_home_opened(), handle_app_mention(), handle_create_event_modal(), handle_darwin_command(), handle_home_create_event(), on_dm_message() (+1 more)

### Community 66 - "._triage_and_build_evidence"
Cohesion: 0.08
Nodes (11): _clamp_confidence(), _parse_job_metadata(), _prepare_console_tail(), _redact_build_parameters(), _redact_match(), _redact_secrets_in_text(), _sanitize_analysis_text(), _sanitize_console_tail() (+3 more)

### Community 67 - "ConversationTurn"
Cohesion: 0.14
Nodes (23): ConversationTurn, Props, BORDER_COLOR, PlanProgressProps, STATUS_ICON, DeferCountdownState, useDeferCountdown(), EMPTY_CONVERSATION (+15 more)

### Community 68 - "EventDrillDown.tsx"
Cohesion: 0.14
Nodes (22): getEventPulses(), BrainCore(), CortexDevPage(), devQueryClient, CortexLiveFeedProps, EventDrillDown(), EventDrillDownProps, FRICTION_COLORS (+14 more)

### Community 69 - "llm_error_classifier.py"
Cohesion: 0.13
Nodes (9): _extract_status_code(), _has_non_retryable_cause(), _is_google_auth_transport_error(), is_rate_limit(), is_transient(), is_transient_llm_error_turn(), _iter_exception_chain(), _matches_mro() (+1 more)

### Community 70 - "observations_mgmt.py"
Cohesion: 0.10
Nodes (10): get_report_client(), render_pdf(), bulk_delete_observations(), BulkDeleteRequest, delete_observation(), export_observations(), generate_observations_report(), rename_observation() (+2 more)

### Community 71 - "server.js"
Cohesion: 0.09
Nodes (18): { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, ensureEventDocument(), fs, path, stageEventDocument(), fetchEventDocument(), fs, { handleRequest } (+10 more)

### Community 73 - "cognitive_graph.py"
Cohesion: 0.11
Nodes (11): get_pulse_tracker(), dismiss_proposals(), DismissRequest, get_all_shadow_interventions(), get_cognitive_graph(), get_cortex_activity(), get_cortex_status(), get_event_shadow_interventions() (+3 more)

### Community 74 - "NodeInspector.tsx"
Cohesion: 0.13
Nodes (23): getClosedEvents(), ArchitectureEvent, ArgoCDOperation, ArchitectureGraph(), EVENT_LABELS, EventItem(), EventItemProps, healthTone() (+15 more)

### Community 76 - "QuotaTracker"
Cohesion: 0.10
Nodes (4): _parse_ceiling_ratio(), QuotaPoolRegistry, _parse_priority_aging_sec(), QuotaTracker

### Community 78 - "handlers_dispatch.py"
Cohesion: 0.11
Nodes (8): _consecutive_tpm_defers(), get_registry_and_bridge(), handle_report_incident(), handle_select_agent(), _max_tpm_reserve_defers(), _resolve_escalation_scope(), _sticky_work_style(), derive_llm_priority()

### Community 79 - "slack.py"
Cohesion: 0.10
Nodes (4): table_block_to_code_block(), _PlanDecision, _mask_email(), SlackAccessGate

### Community 81 - "TokenUtilizationPage.tsx"
Cohesion: 0.19
Nodes (18): getFlowHistory(), getLlmTelemetry(), FlowSnapshot, LlmTelemetryBreakdown, FlowHistoryPage(), RANGES, SparkCard(), SparkCardProps (+10 more)

### Community 82 - "PulseBatch"
Cohesion: 0.11
Nodes (4): PulseBatch, PulsePort, PulseObserver, PulseTracker

### Community 83 - "_process_decision"
Cohesion: 0.15
Nodes (5): get_user_from_slack(), _process_decision(), handle_approve(), handle_approve_sha(), handle_reject()

### Community 84 - "slack_approvals.py"
Cohesion: 0.20
Nodes (12): build_writein_modal(), verify_writein_metadata(), extract_action_context(), extract_action_fields(), extract_selected_option(), extract_view_fields(), get_slack_user_context(), post_slack_ephemeral_error() (+4 more)

### Community 85 - "EventType"
Cohesion: 0.12
Nodes (4): ArchitectureEvent, EventType, list_events(), MetricsRepository

### Community 86 - "AsyncGitHubClient"
Cohesion: 0.17
Nodes (5): AsyncGitHubClient, _handle_rate_limit(), _paginate_github_get(), parse_github_next_link(), _safe_parse_int()

### Community 87 - "OpsStateContext.tsx"
Cohesion: 0.15
Nodes (19): getAgents(), getKargoStages(), AgentRegistryEntry, ApprovalErrorKind, KargoStageStatus, AgentRegistryPanel(), formatConnectedSince(), AgentGroups (+11 more)

### Community 88 - "gemini_client.py"
Cohesion: 0.12
Nodes (9): _append_user_turn(), _coerce_part(), _decode_sig_bytes(), _extract_call_syntax(), _is_function_response_part(), _parse_drain_timeout(), _validated_parts(), sanitize_call_syntax() (+1 more)

### Community 89 - "claude-guard.js"
Cohesion: 0.15
Nodes (17): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+9 more)

### Community 90 - "jenkins.py"
Cohesion: 0.11
Nodes (6): _annotation_replace(), BuildDetails, JenkinsPlatformPort, JobRunState, _strip_pipeline_annotations(), ViewScanResult

### Community 91 - "._feedback_reject_reason"
Cohesion: 0.11
Nodes (7): _bot_login(), _csv_env(), _consider(), _is_slash_command_only(), _mention_pattern(), _review_ignore_logins(), _review_trusted_associations()

### Community 93 - "cli-setup.js"
Cohesion: 0.13
Nodes (18): { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync }, filterSkillsByMode() (+10 more)

### Community 98 - "get_report"
Cohesion: 0.11
Nodes (6): get_report(), list_reports(), reports_spa_no_slash(), reports_spa_with_slash(), search_reports(), _serve_spa()

### Community 100 - "utils/__init__.py"
Cohesion: 0.18
Nodes (8): _resolve_maintainer_enum(), _dedupe(), _extract_evidence_maintainer_emails(), is_slack_recipient_allowed(), maintainer_env_key(), _resolve_evidence_env_maintainer_emails(), resolve_maintainer_emails(), _resolve_static_env_emails()

### Community 102 - "EventStatus"
Cohesion: 0.12
Nodes (7): EventStatus, _defer_timeline_fields(), _has_active_subscription(), list_active_events(), list_closed_events(), list_waiting_approval_events(), _serialize_evidence()

### Community 103 - "ReconcileScheduler"
Cohesion: 0.14
Nodes (3): ReconcileScheduler, QueueTrigger, ResyncTrigger

### Community 106 - "ShiftsPage.tsx"
Cohesion: 0.23
Nodes (16): getCurrentShift(), getShiftDetail(), getShiftsList(), ShiftReportFull, ShiftReportSummary, FailedClusterBadge(), getISOWeek(), getWeekDates() (+8 more)

### Community 107 - "catalog-skills.js"
Cohesion: 0.16
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 108 - "StateWatcher"
Cohesion: 0.17
Nodes (3): _QueueEntry, StateWatcher, _Subscription

### Community 110 - "reanalyze_mission"
Cohesion: 0.16
Nodes (8): approve_mission(), dismiss_mission(), _infer_phase(), _jira_config(), list_missions(), reanalyze_mission(), retry_mission(), _validate_jira_key()

### Community 114 - "github_app.py"
Cohesion: 0.13
Nodes (4): _find_pem_file(), get_github_auth(), is_shared_installation_manager(), reset_installation_manager()

### Community 121 - "._process_candidates"
Cohesion: 0.13
Nodes (3): _flood_service_key(), _outage_service_key(), _service_key()

### Community 122 - "IncidentAdapterPort"
Cohesion: 0.13
Nodes (3): IdleTimeoutPort, IncidentAdapterPort, StateWatcherPort

### Community 124 - "handlers_planning.py"
Cohesion: 0.23
Nodes (7): _auto_complete_step(), _canonical_role(), handle_create_plan(), handle_get_plan_progress(), _is_failed_turn(), _is_orchestrator_turn(), _normalize_step_id()

### Community 126 - "NeuronInfoPanel.tsx"
Cohesion: 0.23
Nodes (13): KGServiceDetail, asNumber(), asString(), asStringArray(), Badge(), describeNeuron(), Hdr(), NeuronInfoPanel() (+5 more)

### Community 127 - "evaluate_gates"
Cohesion: 0.15
Nodes (7): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), is_wait_for_user_admissible_after_response(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 130 - "JarvisMemoryPage.tsx"
Cohesion: 0.27
Nodes (12): dismissProposals(), EnhancementProposal, getHandoffReports(), getProposals(), HandoffReport, FilterMode, formatDate(), formatTime() (+4 more)

### Community 135 - "HeadhunterItemActionRequest"
Cohesion: 0.18
Nodes (3): HeadhunterItemActionRequest, TitleUpdateRequest, sanitize_title()

### Community 136 - "CortexLiveFeed.tsx"
Cohesion: 0.24
Nodes (10): CortexHeartbeat(), CortexHeartbeatProps, ensureKeyframes(), CortexLiveFeed(), FILTER_PILLS, FilterKey, getStoredFilter(), MESSAGE_STYLES (+2 more)

### Community 137 - "usage-tracker.js"
Cohesion: 0.29
Nodes (9): ALL_KEYS, createTaskUsageAccumulator(), startSpawn(), diffAndAdd(), emptyUsage(), extractStreamUsage(), inferProvider(), normalizeUsage() (+1 more)

### Community 140 - "cortex/types.ts"
Cohesion: 0.24
Nodes (9): EventSource, PulseTimelineProps, CognitiveGraphResponse, CortexHeartbeatMessage, FrictionIndicator, FrictionPattern, NeuronVisual, PulseBatch (+1 more)

### Community 141 - "generate_event_title"
Cohesion: 0.22
Nodes (3): generate_event_title(), get_adapter(), _get_semaphore()

### Community 145 - "entity_extractor.py"
Cohesion: 0.33
Nodes (5): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship

### Community 147 - "has_unevaluated_close_blocker"
Cohesion: 0.22
Nodes (5): has_unevaluated_close_blocker(), _pred_jarvis_response(), _pred_unevaluated_close(), is_jarvis_acknowledgment(), is_stabilization_wake()

### Community 148 - "knowledge_graph_api.py"
Cohesion: 0.31
Nodes (4): get_kg_store(), get_service_detail(), get_stats(), list_services()

### Community 154 - "MessageStatus"
Cohesion: 0.28
Nodes (3): HealthStatus, MessageStatus, NodeType

### Community 155 - "create_chat_event"
Cohesion: 0.25
Nodes (3): ChatEventRequest, ChatEventResponse, create_chat_event()

### Community 161 - "adf_to_markdown"
Cohesion: 0.57
Nodes (7): adf_to_markdown(), _apply_marks(), _children(), _render(), _render_list(), _render_list_item(), _render_table_like()

### Community 169 - "state.js"
Cohesion: 0.33
Nodes (4): { AGENT_ROLE }, _blackboardTurns, _inboundMessages, _teammateMessages

### Community 171 - "_compute_processed_up_to"
Cohesion: 0.33
Nodes (3): _compute_processed_up_to(), _is_participant_turn(), _is_steering_turn()

## Knowledge Gaps
- **106 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `os`, `models.py`, `Brain`, `main.py`, `brain.py`, `generate_event_title`, `queue.py`, `headhunter.py`, `.get_event`, `EventDocument`, `BrainSkillLoader`, `.get_graph_data`, `create_chat_event`, `MessageStatus`, `approval_decision.py`, `KargoObserver`, `._update_event_vcs_context`, `update_schedule`, `update_notebook_note`, `ConversationTurn`, `LiveAPIAdapter`, `get_quota_registry`, `handlers_lookup.py`, `observations_mgmt.py`, `slack.py`, `PulseBatch`, `EventType`, `get_report`, `EventStatus`, `reanalyze_mission`, `HeadhunterJira`, `ScheduleRepository`?**
  _High betweenness centrality (0.136) - this node is a cross-community bridge._
- **Are the 86 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 86 INFERRED edges - model-reasoned connections that need verification._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.008268924058397742 - nodes in this community are weakly interconnected._
- **Why does `ConversationTurn` connect `ConversationTurn` to `BlackboardState`, `os`, `models.py`, `Brain`, `brain.py`, `EventRepository`, `queue.py`, `headhunter.py`, `._process_with_llm`, `.get_event`, `EventDocument`, `.poll_active_events_wakeup`, `GitLabPlatform`, `create_chat_event`, `approval_decision.py`, `handlers_integration.py`, `._cleanup_stale_events`, `context_parts.py`, `formatter.py`, `Aligner`, `_compute_processed_up_to`, `ToolContext`, `SlackChannel`, `LiveAPIAdapter`, `GitHubPlatform`, `BrainLifecyclePort`, `handlers_lookup.py`, `._poll_pr_feedback`, `spawn_event_namer_task`, `handlers_dispatch.py`, `slack.py`, `_process_decision`, `._tool_send_event_message`, `handlers_planning.py`?**
  _High betweenness centrality (0.062) - this node is a cross-community bridge._
- **Are the 20 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Should `os` be split into smaller, more focused modules?**
  _Cohesion score 0.02180948360771071 - nodes in this community are weakly interconnected._
- **Why does `Brain` connect `Brain` to `BlackboardState`, `IdleTimeoutManager`, `models.py`, `main.py`, `Archivist`, `brain.py`, `._extract_context_flags`, `._resolve_llm_params`, `._post_agent_recall`, `._process_with_llm`, `EventDocument`, `BrainSkillLoader`, `MessageStatus`, `approval_decision.py`, `._cleanup_stale_events`, `._detect_repetition_collapse`, `ConversationTurn`, `sanitize_untrusted_line`, `StalenessGuard`, `._sweep_waiting_approval_zombies`, `BrainLifecyclePort`, `.count_global_wip`, `.get_active_subscription_count`, `.set_headhunter_close_signal`, `slack.py`, `PulseBatch`, `EventType`, `ReflexSearcher`, `.start_event_loop`, `EventStatus`, `ReconcileScheduler`, `StateWatcher`?**
  _High betweenness centrality (0.043) - this node is a cross-community bridge._