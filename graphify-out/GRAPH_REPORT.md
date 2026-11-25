# Graph Report - Blackboard  (2026-11-25)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 5970 nodes · 14134 edges · 221 communities (97 shown, 124 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 1079 edges (avg confidence: 0.89)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `af1ef1da`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- logging
- BlackboardState
- models.py
- os
- brain.py
- nightwatcher_tools.py
- queue.py
- Archivist
- GitLabPlatform
- EventSidebar.tsx
- client.ts
- WorkspaceInspector.tsx
- colors.ts
- tool_gates.py
- Headhunter
- EventRepository
- useCortexData.ts
- App.tsx
- Brain
- EventEvidence
- http-handler.js
- ref_react
- api/types.ts
- ._run_agent_task
- ReconcileScheduler
- jenkins-mcp.js
- CortexGraph.tsx
- Service
- ToolContext
- Aligner
- ._process_with_llm
- Any
- _BrainToolContext
- KargoObserver
- cli-executor.js
- storage-recycler.js
- LiveAPIAdapter
- StreamGrid.tsx
- EventDocument
- VcsPlatformPort
- ConversationTurn
- handlers_integration.py
- formatter.py
- KnowledgeGraphStore
- observations_mgmt.py
- ._process_event_inner
- SlackChannel
- ConversationTurn
- ArchitectureGraph.tsx
- TurnBubble.tsx
- sanitize_untrusted_line
- ws-client.js
- GitHubPlatform
- BoolOutcome
- ._poll_pr_feedback
- ClaudeAdapter
- observations_reporter.py
- create_schedule
- Any
- TokenMeter
- spawn_event_namer_task
- Any
- approve_event
- NodeInspector.tsx
- .list_observations
- IdleTimeoutManager
- BrainSkillLoader
- TopologyRepository
- httpx
- start_headhunter_task
- WorkspaceCenterStage.tsx
- llm_error_classifier.py
- server.js
- ._poll_issues
- PulseBatch
- GeminiAdapter
- ArgoCDObserver
- reconcile.py
- StateWatcher
- TokenUtilizationPage.tsx
- DashboardWSAdapter
- JenkinsAdapter
- JenkinsObserver
- claude-guard.js
- tool_router.py
- gemini_client.py
- AsyncGitHubClient
- GitHubAppAuth
- _build_event_state_tail_block
- ReflexSearcher
- .create_platform_event
- slack_approvals.py
- cli-setup.js
- .fetch_context
- HeadhunterCircuitBreaker
- get_report
- catalog-skills.js
- JarvisPeerPort
- _process_decision
- ObservationRepository
- JenkinsPlatformPort
- HeadhunterJira
- EscalationRepository
- ShiftsPage.tsx
- ._connect
- maintainers.py
- EventType
- MultiInstallationManager
- ._poll_and_stage
- ._normalize_issue
- OIDCKeyAdapter
- BrainLifecyclePort
- ._discover
- ScheduleCreateRequest
- prefix_builder.py
- _batch_is_terminal_for_flush
- handlers_planning.py
- state/ports.py
- ScheduleRepository
- SlackAccessGate
- generate_map.py
- ._extract_context_flags
- EphemeralProvisioner
- FlowSnapshot
- usage-tracker.js
- approval_blocks.py
- evaluate_gates
- GitLabTokenAuth
- ._process_message
- SpawnPollResult
- ._clear_recovered_group_flags
- has_unevaluated_close_blocker
- BrainIntrospectionPort
- HeadhunterItemActionRequest
- _get_canonical_or_alias
- create_chat_event
- get_event_document
- list_shifts
- ._evaluate_health
- handle_notify_user_slack
- ConversationMessage
- CortexRepository
- adf_to_markdown
- .has_reeval_signal
- LLMResponse
- update_notebook_note
- llm_stats
- state.js
- io
- SpawnStatus
- list_failed_stages
- rename_observation
- dex_proxy
- KubernetesSpawnHealthAdapter
- .__init__
- DispatchMetrics
- ._wait_for_registration
- handle_recall_pruned_turns
- can_transition_to_close
- submit_feedback
- get_notebook
- delete_notebook_note
- delete_observation
- turn_decay.py
- _WSFrameFilter
- _env_flag
- get_intermediate_tools
- report_tampering
- get_event_flow
- findDuplicateJsonKeys.ts
- gh-wrapper.sh
- huddleSendMessage.sh
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
1. `BlackboardState` - 332 edges
2. `Brain` - 170 edges
3. `ConversationTurn` - 157 edges
4. `ToolContext` - 103 edges
5. `EventDocument` - 102 edges
6. `GateContext` - 100 edges
7. `GitHubPlatform` - 99 edges
8. `EventRepository` - 97 edges
9. `Headhunter` - 89 edges
10. `GitLabPlatform` - 74 edges

## Surprising Connections (you probably didn't know these)
- `EphemeralProvisioner` --uses--> `AgentRegistry`  [INFERRED]
  src/agents/ephemeral_provisioner.py → src/agents/agent_registry.py
- `get_registry_and_bridge()` --uses--> `AgentRegistry`  [INFERRED]
  src/dependencies.py → src/agents/agent_registry.py
- `get_registry_and_bridge()` --uses--> `TaskBridge`  [INFERRED]
  src/dependencies.py → src/agents/task_bridge.py
- `DashboardWSAdapter` --uses--> `BlackboardState`  [INFERRED]
  src/adapters/dashboard_ws.py → src/state/blackboard.py
- `LiveAPIAdapter` --uses--> `BlackboardState`  [INFERRED]
  src/adapters/live_api_adapter.py → src/state/blackboard.py

## Import Cycles
- None detected.

## Communities (221 total, 124 thin omitted)

### Community 0 - "logging"
Cohesion: 0.02
Nodes (54): AgentConnection, AgentRegistry, agent_websocket_handler(), _heartbeat(), Architect, AgentClient, Developer, _build_prompt() (+46 more)

### Community 2 - "models.py"
Cohesion: 0.02
Nodes (58): _close_unanswered_fc(), _contents_have_pruned_or_decayed(), _apply_sibling_signature(), build_function_response(), build_single_function_response(), compress_contents(), _compress_single_msg_parts(), contents_have_pruned_or_decayed() (+50 more)

### Community 3 - "os"
Cohesion: 0.03
Nodes (30): _annotation_replace(), _strip_pipeline_annotations(), PlatformBreakerStatus, _safe_int(), _parse_job_metadata(), _load_name_mapping(), get_flow_metrics(), get_current_shift() (+22 more)

### Community 4 - "brain.py"
Cohesion: 0.03
Nodes (45): _commit_with_task_cap(), _consume(), _consume_queue(), _reconcile_terminal_token_usage(), _record_live_token_usage(), _sanitize_stdout(), create_adapter(), get_quota_tracker() (+37 more)

### Community 5 - "nightwatcher_tools.py"
Cohesion: 0.03
Nodes (51): JiraIncidentAdapter, PulseContext, AppNode, ApprovalCommitResult, ChatRequest, ChatResponse, EventInput, EventMetrics (+43 more)

### Community 6 - "queue.py"
Cohesion: 0.03
Nodes (59): get_token_meter(), get_archivist(), get_brain(), EventStatus, aligner_pending_items(), apply_lessons(), ApproveRequest, close_event_by_user() (+51 more)

### Community 7 - "Archivist"
Cohesion: 0.04
Nodes (5): Archivist, _sanitize_lesson_text(), _decode_cursor(), _encode_cursor(), VectorStore

### Community 8 - "GitLabPlatform"
Cohesion: 0.05
Nodes (6): _get_allowed_mention_authors(), GitLabPlatform, _reconcile_synthetic(), _check_one(), _valid_positive_int(), PlatformQueueItem

### Community 9 - "EventSidebar.tsx"
Cohesion: 0.05
Nodes (88): getAlignerPending(), getClosedEvents(), getHeadhunterPending(), getHeadhunterStatus(), getJenkinsPending(), getJiraMissions(), getWaitingApprovalEvents(), headhunterItemAction() (+80 more)

### Community 10 - "client.ts"
Cohesion: 0.04
Nodes (72): bulkDeleteObservations(), createSchedule(), deleteObservation(), deleteSchedule(), exportObservations(), ExtractedCorrection, ExtractedLesson, ExtractionResult (+64 more)

### Community 11 - "WorkspaceInspector.tsx"
Cohesion: 0.05
Nodes (68): getEventDocument(), getEvents(), updateEventTitle(), CiContext, TokenUsageDict, ActivityStream(), ChatInput(), ChatInputProps (+60 more)

### Community 12 - "colors.ts"
Cohesion: 0.05
Nodes (55): getReport(), getReports(), ReportFull, ReportMeta, SubjectType, PulseTimelineProps, CompactCardStrip(), EventHistory() (+47 more)

### Community 13 - "tool_gates.py"
Cohesion: 0.05
Nodes (79): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+71 more)

### Community 14 - "Headhunter"
Cohesion: 0.05
Nodes (11): Headhunter, _maybe_refresh_snapshot(), _notify_phase_b(), _prune_from_snapshot(), _skip_phase_b(), _on_gh_phase_b_settled(), _iref(), _process_issue() (+3 more)

### Community 16 - "useCortexData.ts"
Cohesion: 0.06
Nodes (65): getCognitiveGraph(), getCortexActivity(), getEventPulses(), getKGServiceDetail(), getKGServices(), getKGStats(), getKnowledgeById(), getMemory() (+57 more)

### Community 17 - "App.tsx"
Cohesion: 0.05
Nodes (60): dismissProposals(), EnhancementProposal, getConfig(), getHandoffReports(), getProposals(), getWSAuthFailureCallback(), HandoffReport, setOnUnauthorized() (+52 more)

### Community 19 - "EventEvidence"
Cohesion: 0.04
Nodes (19): _format_bounded_journal(), _safe_seconds(), _clamp_confidence(), _prepare_console_tail(), _redact_build_parameters(), _redact_match(), _redact_secrets_in_text(), _sanitize_analysis_text() (+11 more)

### Community 20 - "http-handler.js"
Cohesion: 0.07
Nodes (63): is429Error(), registerMCPsAndHooks(), resolveCommand(), writeAgyHooks(), writeAgyMcpServer(), writeClaudeMcpServer(), buildArgoCDMcpConfig(), createAppJWT() (+55 more)

### Community 21 - "ref_react"
Cohesion: 0.07
Nodes (59): applyLessons(), approveEvent(), correctMemory(), createKnowledge(), createLesson(), deleteKnowledge(), deleteLesson(), deleteNote() (+51 more)

### Community 22 - "api/types.ts"
Cohesion: 0.04
Nodes (60): getAgents(), getKargoStages(), Agent, AgentRegistryEntry, AlignerPendingItem, AppConfig, AppNode, ApprovalEffect (+52 more)

### Community 23 - "._run_agent_task"
Cohesion: 0.06
Nodes (7): on_huddle(), on_progress(), on_huddle(), on_progress(), _is_external_input_turn(), _select_dispatch_tier(), get_registry_and_bridge()

### Community 24 - "ReconcileScheduler"
Cohesion: 0.04
Nodes (6): FairQueue, ReconcileScheduler, Trigger, QueueTrigger, ResyncTrigger, StalenessGuard

### Community 25 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 26 - "CortexGraph.tsx"
Cohesion: 0.06
Nodes (50): KGServiceDetail, KGServiceEntity, AGENTS, DOMAINS, eventColor(), getExecutiveNeurons(), getStructuralEdges(), HEMISPHERE_X (+42 more)

### Community 27 - "Service"
Cohesion: 0.05
Nodes (8): GraphResponse, Service, get_graph_data(), get_mermaid_diagram(), get_service_details(), get_topology(), list_services(), calculate_health_from_argocd()

### Community 28 - "ToolContext"
Cohesion: 0.07
Nodes (15): _consecutive_tpm_defers(), get_registry_and_bridge(), handle_message_agent(), handle_reply_to_agent(), handle_report_incident(), handle_select_agent(), _max_tpm_reserve_defers(), _resolve_escalation_scope() (+7 more)

### Community 30 - "._process_with_llm"
Cohesion: 0.04
Nodes (6): _BatchContext, _ensure_recall_tool_if_needed(), _is_close_phase_fc(), _QuotaShedState, RepetitionCollapse, _retry_backoff_delay()

### Community 31 - "Any"
Cohesion: 0.08
Nodes (23): _build_active_overlay(), _build_transient_overlays(), _build_turn0_anchor(), _call_anchor_get(), _call_anchor_set_nx(), _collect_turn_overlay_part(), _extract_accepted_domain(), _extract_accepted_phase() (+15 more)

### Community 33 - "KargoObserver"
Cohesion: 0.09
Nodes (9): build_verification_dedup_key(), extract_latest_verification(), is_verification_stale(), _parse_ts(), project_stage_status(), resolve_stage_freight(), _s(), KargoObserver (+1 more)

### Community 34 - "cli-executor.js"
Cohesion: 0.09
Nodes (40): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, MAX_TASK_WALL_MS, MAX_TIMER_MS, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS, STORAGE_PRETASK_TIMEOUT_MS, resolveStorageRoot }, buildCLICommand(), buildTimeoutResult(), { checkAndRecycleStorage, pinTaskCwd, unpinTaskCwd }, CLAUDE_JSON_PATH, cp, createInactivityWatchdog(), createLineUsageEmitter() (+32 more)

### Community 35 - "storage-recycler.js"
Cohesion: 0.07
Nodes (38): withTaskStorage(), MAX_TASK_WALL_MS, parsePositiveInt(), parseTimerMs(), resolveStorageRoot(), resolveTimeoutMs(), ROLE_TIMEOUTS, STORAGE_ACTIVITY_HEARTBEAT_MS (+30 more)

### Community 36 - "LiveAPIAdapter"
Cohesion: 0.07
Nodes (3): _is_event_closed_or_missing(), LiveAPIAdapter, _resolve_phase()

### Community 37 - "StreamGrid.tsx"
Cohesion: 0.08
Nodes (35): getFlowMetrics(), FlowMetrics, AgentStreamCard(), AgentStreamCardProps, MessageCards(), Dashboard(), FlowHealthWidget(), queueColor() (+27 more)

### Community 39 - "VcsPlatformPort"
Cohesion: 0.06
Nodes (3): PlatformSnapshot, VcsWorkItem, VcsPlatformPort

### Community 40 - "ConversationTurn"
Cohesion: 0.08
Nodes (32): ApiError, submitApprovalDecision(), ApprovalOption, ConversationTurn, DecisionPayload, ApprovalDecisionCard(), ErrState, Props (+24 more)

### Community 41 - "handlers_integration.py"
Cohesion: 0.09
Nodes (20): _do_retrigger(), _get_jira_reporter(), handle_refresh_github_context(), _emit(), handle_refresh_gitlab_context(), handle_refresh_kargo_context(), _is_darwin_reentrant_caller(), _is_positive_int() (+12 more)

### Community 42 - "formatter.py"
Cohesion: 0.07
Nodes (18): build_access_denied_home_view(), build_home_tab_view(), _context_line(), create_feedback_block(), _replace(), format_event_summary(), format_plan_block(), format_task_card() (+10 more)

### Community 43 - "KnowledgeGraphStore"
Cohesion: 0.09
Nodes (9): _format_graph_context(), get_graph_context(), _parse_props(), _sanitize(), translate_to_lookups(), _acquire(), KnowledgeGraphStore, _sanitize() (+1 more)

### Community 44 - "observations_mgmt.py"
Cohesion: 0.08
Nodes (19): get_blackboard(), get_pulse_tracker(), get_report_client(), render_pdf(), dismiss_proposals(), DismissRequest, get_all_shadow_interventions(), get_cognitive_graph() (+11 more)

### Community 45 - "._process_event_inner"
Cohesion: 0.05
Nodes (7): _compute_processed_up_to(), _has_non_user_turns(), _is_automated_nudge(), _is_participant_turn(), _is_seed_turn(), _is_steering_turn(), _sanitize_error_text()

### Community 46 - "SlackChannel"
Cohesion: 0.08
Nodes (4): extract_tables(), get_agent_notification_text(), get_turn_attachment_color(), SlackChannel

### Community 47 - "ConversationTurn"
Cohesion: 0.14
Nodes (26): emit_tool_result(), _safe_int(), handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_ask_release_ai(), handle_comment_jira_issue(), handle_fetch_jira_issue() (+18 more)

### Community 48 - "ArchitectureGraph.tsx"
Cohesion: 0.09
Nodes (27): HealthStatus, NodeType, AppNodeData, applyDagreLayout(), applyGridLayout(), applyLayout(), ArchitectureGraph(), ArchitectureGraphInner() (+19 more)

### Community 49 - "TurnBubble.tsx"
Cohesion: 0.12
Nodes (26): closeEvent(), enforceCasualDomain(), getEventReport(), submitFeedback(), ApprovalResolution, MessageStatus, ApprovalResolvedSummary(), Props (+18 more)

### Community 50 - "sanitize_untrusted_line"
Cohesion: 0.11
Nodes (19): _clean_lines(), format_event_state_tail(), _build_closed_block(), build_event_header(), _build_identity_block(), build_immutable_event_anchor(), _build_journal_block(), _build_mermaid_block() (+11 more)

### Community 51 - "ws-client.js"
Cohesion: 0.10
Nodes (28): clearIdleTimer(), {
  DEFAULT_WORK_DIR, AGENT_CLI, AGENT_MODEL, AGENT_ROLE,
  EVENT_ID, EPHEMERAL, IDLE_TIMEOUT_MS,
  CLI_429_MAX_RETRIES, CLI_429_INITIAL_DELAY_MS, CLI_429_BACKOFF_MULTIPLIER,
  resolveTimeoutMs, parsePositiveInt, MAX_TASK_WALL_MS, MAX_TIMER_MS,
}, { ensureEventDocument }, { executeCLIStreaming, prepareResultsDir, is429Error }, { filterSkillsByRole, filterSkillsByMode, swapActiveRules, restoreAllSkills }, fs, handleCancel(), handleServerMessage() (+20 more)

### Community 54 - "._poll_pr_feedback"
Cohesion: 0.07
Nodes (9): _bot_login(), _csv_env(), _consider(), _is_slash_command_only(), _iso(), _mention_pattern(), _parse_ts(), _review_ignore_logins() (+1 more)

### Community 55 - "ClaudeAdapter"
Cohesion: 0.09
Nodes (3): ClaudeAdapter, FunctionCall, LLMChunk

### Community 56 - "observations_reporter.py"
Cohesion: 0.11
Nodes (15): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship, acquire_raw_genai(), finalize_raw_genai(), rollback_raw_genai() (+7 more)

### Community 57 - "create_schedule"
Cohesion: 0.06
Nodes (6): create_schedule(), delete_schedule(), get_schedule(), list_schedules(), toggle_schedule(), update_schedule()

### Community 58 - "Any"
Cohesion: 0.10
Nodes (13): _append_user_turn(), _attach_signature_to_parts(), _clone_part_with_sig(), _clone_part_with_text(), _coerce_part(), _decode_sig_bytes(), _extract_part_signature(), _is_empty_sig_carrier() (+5 more)

### Community 59 - "TokenMeter"
Cohesion: 0.08
Nodes (5): BoundedTeamCounter, normalize_team_id(), _zero_bucket(), TokenMeter, TokenUsageDict

### Community 60 - "spawn_event_namer_task"
Cohesion: 0.13
Nodes (8): spawn_event_namer_task(), handle_app_home_opened(), handle_app_mention(), handle_create_event_modal(), handle_darwin_command(), handle_home_create_event(), on_dm_message(), fallback_title()

### Community 61 - "Any"
Cohesion: 0.11
Nodes (3): VcsContext, _NoAliasSafeLoader, _validate_plan_yaml()

### Community 62 - "approve_event"
Cohesion: 0.11
Nodes (13): PendingApproval, _acquire_hh_poll_lock(), approve_event(), _busy_lock_response(), _get_headhunter_or_503(), headhunter_item_action(), _map_decision_error_response(), post_approval_decision() (+5 more)

### Community 63 - "NodeInspector.tsx"
Cohesion: 0.11
Nodes (26): getService(), getTopology(), ArchitectureEvent, ArgoCDOperation, Service, TopologyResponse, EVENT_LABELS, EventItem() (+18 more)

### Community 64 - ".list_observations"
Cohesion: 0.07
Nodes (5): get_all_journal(), get_service_journal(), get_event_observations(), get_global_observations(), export_observations()

### Community 67 - "TopologyRepository"
Cohesion: 0.08
Nodes (3): Snapshot, TopologySnapshot, TopologyRepository

### Community 68 - "httpx"
Cohesion: 0.13
Nodes (10): approve_mission(), dismiss_mission(), _infer_phase(), _jira_config(), list_missions(), reanalyze_mission(), retry_mission(), _validate_jira_key() (+2 more)

### Community 69 - "start_headhunter_task"
Cohesion: 0.08
Nodes (3): redact_error_text(), on_headhunter_done(), start_headhunter_task()

### Community 70 - "WorkspaceCenterStage.tsx"
Cohesion: 0.13
Nodes (17): createChatEvent(), ErrorBoundary, ErrorBoundaryProps, ErrorBoundaryState, STARTER_CHIPS, StarterChip, useSafeNavigate(), WorkspaceCenterStage() (+9 more)

### Community 71 - "llm_error_classifier.py"
Cohesion: 0.13
Nodes (9): _extract_status_code(), _has_non_retryable_cause(), _is_google_auth_transport_error(), is_rate_limit(), is_transient(), is_transient_llm_error_turn(), _iter_exception_chain(), _matches_mro() (+1 more)

### Community 72 - "server.js"
Cohesion: 0.09
Nodes (18): { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, ensureEventDocument(), fs, path, stageEventDocument(), fetchEventDocument(), fs, { handleRequest } (+10 more)

### Community 74 - "PulseBatch"
Cohesion: 0.10
Nodes (4): PulseBatch, PulsePort, PulseObserver, PulseTracker

### Community 77 - "reconcile.py"
Cohesion: 0.15
Nodes (11): sanitize_redis_port(), generate_phase_tool_map(), _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers() (+3 more)

### Community 78 - "StateWatcher"
Cohesion: 0.11
Nodes (3): _QueueEntry, StateWatcher, _Subscription

### Community 79 - "TokenUtilizationPage.tsx"
Cohesion: 0.20
Nodes (17): getFlowHistory(), getLlmTelemetry(), FlowSnapshot, LlmTelemetryBreakdown, FlowHistoryPage(), RANGES, SparkCard(), SparkCardProps (+9 more)

### Community 83 - "claude-guard.js"
Cohesion: 0.14
Nodes (17): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+9 more)

### Community 84 - "tool_router.py"
Cohesion: 0.10
Nodes (5): handle_classify_event(), handle_request_user_approval(), IdleTimeoutPort, IncidentAdapterPort, StateWatcherPort

### Community 85 - "gemini_client.py"
Cohesion: 0.12
Nodes (10): _extract_call_syntax(), _parse_drain_timeout(), is_partial_control_token(), process_stream_call_syntax_buffer(), sanitize_call_syntax(), scan_call_syntax(), _split_partial_control_token(), split_stream_call_syntax() (+2 more)

### Community 86 - "AsyncGitHubClient"
Cohesion: 0.17
Nodes (5): AsyncGitHubClient, _handle_rate_limit(), _paginate_github_get(), parse_github_next_link(), _safe_parse_int()

### Community 88 - "_build_event_state_tail_block"
Cohesion: 0.10
Nodes (4): _build_event_state_tail_block(), _init_tool_names(), _safe_bb_call(), _strip_tool_names()

### Community 91 - "slack_approvals.py"
Cohesion: 0.22
Nodes (10): extract_action_context(), extract_action_fields(), extract_selected_option(), extract_view_fields(), get_slack_user_context(), post_slack_ephemeral_error(), split_approval_value(), register_approval_handlers() (+2 more)

### Community 92 - "cli-setup.js"
Cohesion: 0.13
Nodes (17): { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync }, filterSkillsByMode() (+9 more)

### Community 97 - "get_report"
Cohesion: 0.11
Nodes (6): get_report(), list_reports(), reports_spa_no_slash(), reports_spa_with_slash(), search_reports(), _serve_spa()

### Community 98 - "catalog-skills.js"
Cohesion: 0.15
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 101 - "_process_decision"
Cohesion: 0.17
Nodes (6): get_user_from_slack(), _process_decision(), _PlanDecision, handle_approve(), handle_approve_sha(), handle_reject()

### Community 103 - "JenkinsPlatformPort"
Cohesion: 0.12
Nodes (4): BuildDetails, JenkinsPlatformPort, JobRunState, ViewScanResult

### Community 107 - "ShiftsPage.tsx"
Cohesion: 0.25
Nodes (15): getCurrentShift(), getShiftDetail(), getShiftsList(), ShiftReportFull, ShiftReportSummary, FailedClusterBadge(), getISOWeek(), getWeekDates() (+7 more)

### Community 109 - "maintainers.py"
Cohesion: 0.20
Nodes (8): _resolve_maintainer_enum(), _dedupe(), _extract_evidence_maintainer_emails(), is_slack_recipient_allowed(), maintainer_env_key(), _resolve_evidence_env_maintainer_emails(), resolve_maintainer_emails(), _resolve_static_env_emails()

### Community 110 - "EventType"
Cohesion: 0.15
Nodes (5): EventType, HealthStatus, MessageStatus, NodeType, infer_node_type()

### Community 120 - "prefix_builder.py"
Cohesion: 0.22
Nodes (5): build_global_core_si(), canonical_wire_tools(), compute_prefix_hashes(), sha8_json(), sha8_text()

### Community 121 - "_batch_is_terminal_for_flush"
Cohesion: 0.14
Nodes (7): _batch_is_terminal_for_flush(), _wait_for_user_admissible(), build_gate_context(), conversation_has_decayed_turns(), _decay_payload_len(), is_wait_for_user_admissible_after_response(), decay_cutoff_index()

### Community 122 - "handlers_planning.py"
Cohesion: 0.23
Nodes (7): _auto_complete_step(), _canonical_role(), handle_create_plan(), handle_get_plan_progress(), _is_failed_turn(), _is_orchestrator_turn(), _normalize_step_id()

### Community 127 - "generate_map.py"
Cohesion: 0.19
Nodes (5): _enumerate_gates(), _GateInfo, _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 128 - "._extract_context_flags"
Cohesion: 0.15
Nodes (3): compute_dispatch_backpressure(), ContextFlags, _safe_int_env()

### Community 130 - "FlowSnapshot"
Cohesion: 0.21
Nodes (3): FlowSnapshot, FlowCollector, get_flow_history()

### Community 131 - "usage-tracker.js"
Cohesion: 0.26
Nodes (10): ALL_KEYS, createTaskUsageAccumulator(), startSpawn(), diffAndAdd(), emptyUsage(), extractStreamUsage(), inferProvider(), normalizeUsage() (+2 more)

### Community 136 - "approval_blocks.py"
Cohesion: 0.40
Nodes (8): build_approval_blocks(), build_writein_modal(), _derive_writein_hmac_key(), _escape_mrkdwn(), format_frozen_approval_blocks(), _safe_text(), sign_writein_metadata(), verify_writein_metadata()

### Community 137 - "evaluate_gates"
Cohesion: 0.18
Nodes (6): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 139 - "._process_message"
Cohesion: 0.24
Nodes (4): _build_skill_refs(), extract_genai_usage(), _int_field(), record_raw_genai_post_hoc()

### Community 144 - "has_unevaluated_close_blocker"
Cohesion: 0.22
Nodes (5): has_unevaluated_close_blocker(), _pred_jarvis_response(), _pred_unevaluated_close(), is_jarvis_acknowledgment(), is_stabilization_wake()

### Community 148 - "create_chat_event"
Cohesion: 0.25
Nodes (3): ChatEventRequest, ChatEventResponse, create_chat_event()

### Community 152 - "handle_notify_user_slack"
Cohesion: 0.25
Nodes (4): _alert_wrapper_retrigger(), handle_notify_user_slack(), _resolve_slack_user(), build_event_report_md()

### Community 157 - "adf_to_markdown"
Cohesion: 0.57
Nodes (7): adf_to_markdown(), _apply_marks(), _children(), _render(), _render_list(), _render_list_item(), _render_table_like()

### Community 163 - "state.js"
Cohesion: 0.33
Nodes (4): { AGENT_ROLE }, _blackboardTurns, _inboundMessages, _teammateMessages

### Community 180 - "handle_recall_pruned_turns"
Cohesion: 0.50
Nodes (3): _coerce_turn_int(), handle_recall_pruned_turns(), _parse_turn_int()

## Knowledge Gaps
- **124 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `logging`, `models.py`, `os`, `brain.py`, `nightwatcher_tools.py`, `queue.py`, `FlowSnapshot`, `Brain`, `EventEvidence`, `create_chat_event`, `get_event_document`, `list_shifts`, `ConversationMessage`, `Service`, `._update_event_vcs_context`, `Any`, `KargoObserver`, `update_notebook_note`, `LiveAPIAdapter`, `EventDocument`, `observations_mgmt.py`, `rename_observation`, `._restage_pending_signal`, `ConversationTurn`, `._stage_pending_signal`, `.__init__`, `submit_feedback`, `get_notebook`, `observations_reporter.py`, `create_schedule`, `delete_notebook_note`, `delete_observation`, `.cleanup_stale_services`, `._commit_pending_signal`, `approve_event`, `._count_pending`, `.list_observations`, `._downsample_snapshots`, `.drain_notes`, `TopologyRepository`, `report_tampering`, `httpx`, `.get_edge_metadata`, `DashboardWSAdapter`, `tool_router.py`, `.delete_slack_mapping`, `.record_observation`, `get_report`, `HeadhunterJira`, `EventType`, `._validate_gitlab_ids`, `state/ports.py`, `ScheduleRepository`?**
  _High betweenness centrality (0.137) - this node is a cross-community bridge._
- **Are the 86 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 86 INFERRED edges - model-reasoned connections that need verification._
- **Should `logging` be split into smaller, more focused modules?**
  _Cohesion score 0.017140396210163653 - nodes in this community are weakly interconnected._
- **Why does `ConversationTurn` connect `ConversationTurn` to `BlackboardState`, `models.py`, `os`, `brain.py`, `nightwatcher_tools.py`, `queue.py`, `GitLabPlatform`, `approval_blocks.py`, `EventRepository`, `Brain`, `EventEvidence`, `create_chat_event`, `._run_agent_task`, `handle_notify_user_slack`, `ToolContext`, `Aligner`, `._process_with_llm`, `Any`, `LiveAPIAdapter`, `EventDocument`, `handlers_integration.py`, `formatter.py`, `._process_event_inner`, `SlackChannel`, `handle_recall_pruned_turns`, `GitHubPlatform`, `._poll_pr_feedback`, `spawn_event_namer_task`, `approve_event`, `IdleTimeoutManager`, `DashboardWSAdapter`, `tool_router.py`, `.resolve_approval_decision`, `_process_decision`, `BrainLifecyclePort`, `handlers_planning.py`, `state/ports.py`?**
  _High betweenness centrality (0.077) - this node is a cross-community bridge._
- **Are the 20 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.011040193203381059 - nodes in this community are weakly interconnected._
- **Why does `Brain` connect `Brain` to `._extract_context_flags`, `BlackboardState`, `models.py`, `FlowSnapshot`, `brain.py`, `logging`, `queue.py`, `._resolve_llm_params`, `EventEvidence`, `._run_agent_task`, `ReconcileScheduler`, `._process_with_llm`, `Any`, `EventDocument`, `._process_event_inner`, `ConversationTurn`, `.__init__`, `sanitize_untrusted_line`, `IdleTimeoutManager`, `BrainSkillLoader`, `PulseBatch`, `StateWatcher`, `DashboardWSAdapter`, `_build_event_state_tail_block`, `ReflexSearcher`, `JarvisPeerPort`, `EventType`, `BrainLifecyclePort`?**
  _High betweenness centrality (0.074) - this node is a cross-community bridge._