# Graph Report - Blackboard  (2026-11-25)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 5969 nodes · 14128 edges · 207 communities (100 shown, 107 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 1079 edges (avg confidence: 0.89)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `bcdbabfd`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BlackboardState
- brain.py
- slack.py
- auth.py
- queue.py
- Archivist
- os
- EventChatPanel.tsx
- client.ts
- WorkspaceInspector.tsx
- nightwatcher_tools.py
- tool_gates.py
- EventSidebar.tsx
- EventRepository
- Headhunter
- App.tsx
- gemini_client.py
- GitLabPlatform
- http-handler.js
- Brain
- api/types.ts
- llm/__init__.py
- ._run_agent_task
- main.py
- dispatch.py
- jenkins-mcp.js
- SlackChannel
- Any
- ToolContext
- useMemory.ts
- hooks/index.ts
- ref_react
- Aligner
- ReconcileScheduler
- ._process_with_llm
- _BrainToolContext
- cli-executor.js
- create_adapter
- KnowledgeGraphStore
- EventDocument
- storage-recycler.js
- ._process_event_inner
- ArchitectureGraph.tsx
- AgentClient
- context_parts.py
- get_quota_registry
- BoolOutcome
- ConversationTurn
- CortexGraph.tsx
- ConversationTurn
- VcsPlatformPort
- ws-client.js
- handlers_integration.py
- TokenMeter
- sanitize_untrusted_line
- TimeKeeperPage.tsx
- observations_reporter.py
- KubernetesSpawnHealthAdapter
- EphemeralProvisioner
- GitHubPlatform
- .poll_work_items
- headhunter_item_action
- JenkinsObserver
- useOpsControl
- ._poll_pr_feedback
- ._github_poll_and_process
- useCortexData.ts
- types.py
- EventDrillDown.tsx
- BrainSkillLoader
- dependencies.py
- LiveAPIAdapter
- PulseBatch
- llm_error_classifier.py
- server.js
- StateWatcher
- ._poll_issues
- cognitive_graph.py
- state/__init__.py
- JenkinsAdapter
- start_headhunter_task
- ArgoCDObserver
- TopologyRepository
- claude-guard.js
- _sanitize_analysis_text
- KargoObserver
- GitHubAppAuth
- OpsStateContext.tsx
- reconcile.py
- IdleTimeoutManager
- observers/kargo.py
- ReflexSearcher
- .create_platform_event
- HeadhunterCircuitBreaker
- cli-setup.js
- DashboardWSAdapter
- handle_report_incident
- get_report
- catalog-skills.js
- JiraIncidentAdapter
- JarvisPeerPort
- ObservationRepository
- ShiftsPage.tsx
- HeadhunterJira
- EscalationRepository
- maintainers.py
- NightwatcherObserver
- MultiInstallationManager
- JenkinsPlatformPort
- ._poll_and_stage
- OIDCKeyAdapter
- BrainLifecyclePort
- ._discover
- quota_registry.py
- AsyncGitHubClient
- prefix_builder.py
- ._connect
- handlers_planning.py
- has_unevaluated_close_blocker
- ScheduleRepository
- generate_map.py
- ._extract_context_flags
- evaluate_gates
- ScheduleCreateRequest
- NeuronInfoPanel.tsx
- usage-tracker.js
- ._process_message
- _batch_is_terminal_for_flush
- .fetch_context
- CortexLiveFeed.tsx
- FlowCollector
- _paginate_github_get
- ._latest_bot_comment
- SlackAccessGate
- GitLabTokenAuth
- cortex-constants.ts
- ._tool_send_event_message
- ._post_agent_recall
- handle_notify_user_slack
- ._clear_recovered_group_flags
- BrainIntrospectionPort
- _get_canonical_or_alias
- MetricsRepository
- _is_event_closed_or_missing
- .start_event_loop
- ._triage_and_build_evidence
- ConversationMessage
- TimeKeeperObserver
- CortexRepository
- adf_to_markdown
- update_schedule
- ._detect_repetition_collapse
- llm_stats
- cortex/types.ts
- state.js
- get_event_flow
- list_failed_stages
- dex_proxy
- .__init__
- handle_recall_pruned_turns
- _compute_processed_up_to
- _env_flag
- get_intermediate_tools
- findDuplicateJsonKeys.ts
- gh-wrapper.sh
- huddleSendMessage.sh
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
- `FlowCollector` --uses--> `FlowSnapshot`  [INFERRED]
  src/observers/flow_collector.py → src/models.py
- `get_flow_history()` --uses--> `FlowSnapshot`  [INFERRED]
  src/routes/flow.py → src/models.py
- `DashboardWSAdapter` --uses--> `BlackboardState`  [INFERRED]
  src/adapters/dashboard_ws.py → src/state/blackboard.py
- `LiveAPIAdapter` --uses--> `BlackboardState`  [INFERRED]
  src/adapters/live_api_adapter.py → src/state/blackboard.py
- `Brain` --uses--> `BlackboardState`  [INFERRED]
  src/agents/brain.py → src/state/blackboard.py

## Import Cycles
- None detected.

## Communities (207 total, 107 thin omitted)

### Community 0 - "BlackboardState"
Cohesion: 0.01
Nodes (21): FlowSnapshot, list_events(), get_all_journal(), get_service_journal(), get_notebook(), get_event_observations(), get_global_observations(), rename_observation() (+13 more)

### Community 1 - "brain.py"
Cohesion: 0.02
Nodes (57): _annotation_replace(), _strip_pipeline_annotations(), _sanitize_lesson_text(), _close_unanswered_fc(), _is_external_input_turn(), _is_seed_turn(), build_function_response(), _sanitize_recalled() (+49 more)

### Community 2 - "slack.py"
Cohesion: 0.03
Nodes (55): can_approve_event(), get_user_from_slack(), resolve_approval_identity(), build_approval_blocks(), build_writein_modal(), _derive_writein_hmac_key(), _escape_mrkdwn(), format_frozen_approval_blocks() (+47 more)

### Community 3 - "auth.py"
Cohesion: 0.03
Nodes (39): can_append_message(), can_override_domain(), _claims_to_user(), get_user_from_request(), get_user_from_websocket(), _normalize_email(), prompt_display_name(), require_auth() (+31 more)

### Community 4 - "queue.py"
Cohesion: 0.03
Nodes (55): redact_error_text(), get_token_meter(), can_rename_event(), get_archivist(), get_brain(), get_event_document(), report_tampering(), aligner_pending_items() (+47 more)

### Community 5 - "Archivist"
Cohesion: 0.04
Nodes (4): Archivist, _decode_cursor(), _encode_cursor(), VectorStore

### Community 6 - "os"
Cohesion: 0.04
Nodes (31): _load_name_mapping(), list_incidents(), approve_mission(), dismiss_mission(), _infer_phase(), _jira_config(), list_missions(), reanalyze_mission() (+23 more)

### Community 7 - "EventChatPanel.tsx"
Cohesion: 0.05
Nodes (58): getReport(), getReports(), ReportSearchParams, searchReports(), ActiveEvent, ReportFull, ReportMeta, ReportSearchResponse (+50 more)

### Community 8 - "client.ts"
Cohesion: 0.05
Nodes (71): ApiError, approveEvent(), bulkDeleteObservations(), deleteNote(), deleteObservation(), exportObservations(), ExtractionResult, fetchApi() (+63 more)

### Community 9 - "WorkspaceInspector.tsx"
Cohesion: 0.05
Nodes (64): createChatEvent(), updateEventTitle(), EventEvidence, TokenUsageDict, AgentStreamCard(), AgentStreamCardProps, MessageCards(), ChatInput() (+56 more)

### Community 10 - "nightwatcher_tools.py"
Cohesion: 0.05
Nodes (34): record_token_usage(), PulseContext, ShiftIncident, ShiftInvestigation, ShiftReport, _append_user_turn(), _env_float(), _env_int() (+26 more)

### Community 11 - "tool_gates.py"
Cohesion: 0.05
Nodes (79): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+71 more)

### Community 12 - "EventSidebar.tsx"
Cohesion: 0.06
Nodes (72): getJiraMissions(), HeadhunterTodo, postJiraAction(), CiContext, JiraMission, CiContextCard(), CiContextCardProps, ConsoleTailBlock() (+64 more)

### Community 14 - "Headhunter"
Cohesion: 0.05
Nodes (6): Headhunter, _process_issue(), HeadhunterOperationError, VcsContext, _NoAliasSafeLoader, _validate_plan_yaml()

### Community 15 - "App.tsx"
Cohesion: 0.05
Nodes (56): dismissProposals(), EnhancementProposal, getConfig(), getHandoffReports(), getProposals(), getWSAuthFailureCallback(), HandoffReport, setOnUnauthorized() (+48 more)

### Community 16 - "gemini_client.py"
Cohesion: 0.06
Nodes (24): _append_user_turn(), _attach_signature_to_parts(), _clone_part_with_sig(), _clone_part_with_text(), _coerce_part(), _decode_sig_bytes(), _extract_call_syntax(), _extract_part_signature() (+16 more)

### Community 17 - "GitLabPlatform"
Cohesion: 0.06
Nodes (4): GitLabPlatform, _reconcile_synthetic(), _check_one(), _parse_ts_epoch()

### Community 18 - "http-handler.js"
Cohesion: 0.07
Nodes (63): is429Error(), registerMCPsAndHooks(), resolveCommand(), writeAgyHooks(), writeAgyMcpServer(), writeClaudeMcpServer(), buildArgoCDMcpConfig(), createAppJWT() (+55 more)

### Community 20 - "api/types.ts"
Cohesion: 0.04
Nodes (59): getFlowHistory(), getLlmTelemetry(), Agent, AlignerPendingItem, AppNode, ApprovalEffect, ApprovalResolution, AuthUser (+51 more)

### Community 21 - "llm/__init__.py"
Cohesion: 0.05
Nodes (10): ClaudeAdapter, QuotaExhaustedError, QuotaTracker, RequestExceedsBurstError, Reservation, _stale_reservation_ttl_s(), FunctionCall, LLMChunk (+2 more)

### Community 22 - "._run_agent_task"
Cohesion: 0.06
Nodes (7): on_huddle(), on_progress(), on_huddle(), on_progress(), _sanitize_override_reason(), _select_dispatch_tier(), get_registry_and_bridge()

### Community 23 - "main.py"
Cohesion: 0.04
Nodes (22): _patch_enum_fields(), set_incident_options(), set_oidc_adapter(), set_agents(), set_archivist(), set_argocd_observer(), set_blackboard(), set_brain() (+14 more)

### Community 24 - "dispatch.py"
Cohesion: 0.06
Nodes (14): AgentConnection, AgentRegistry, agent_websocket_handler(), _heartbeat(), _build_prompt(), _check_security(), consume_wake_task(), _dispatch_timeout_s() (+6 more)

### Community 25 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 26 - "SlackChannel"
Cohesion: 0.05
Nodes (8): extract_tables(), _replace(), get_agent_notification_text(), get_turn_attachment_color(), _md_table_to_block_kit(), _md_table_to_text(), _parse_md_table(), SlackChannel

### Community 27 - "Any"
Cohesion: 0.06
Nodes (24): _build_active_overlay(), _build_event_state_tail_block(), _build_transient_overlays(), _build_turn0_anchor(), _call_anchor_get(), _call_anchor_set_nx(), _collect_turn_overlay_part(), _extract_accepted_domain() (+16 more)

### Community 28 - "ToolContext"
Cohesion: 0.07
Nodes (15): _consecutive_tpm_defers(), get_registry_and_bridge(), handle_message_agent(), handle_reply_to_agent(), handle_select_agent(), _max_tpm_reserve_defers(), _sticky_work_style(), handle_classify_event() (+7 more)

### Community 29 - "useMemory.ts"
Cohesion: 0.07
Nodes (49): applyLessons(), correctMemory(), createKnowledge(), createLesson(), deleteKnowledge(), deleteLesson(), ExtractedCorrection, ExtractedLesson (+41 more)

### Community 30 - "hooks/index.ts"
Cohesion: 0.07
Nodes (43): getClosedEvents(), getEventDocument(), getEvents(), getWaitingApprovalEvents(), ArchitectureEvent, ArgoCDOperation, ActivityStream(), ArchitectureGraph() (+35 more)

### Community 31 - "ref_react"
Cohesion: 0.09
Nodes (38): closeEvent(), enforceCasualDomain(), getEventReport(), submitFeedback(), ApprovalResolvedSummary(), CollapsibleSection(), CollapsibleSectionProps, ConversationFeed() (+30 more)

### Community 33 - "ReconcileScheduler"
Cohesion: 0.05
Nodes (6): FairQueue, ReconcileScheduler, Trigger, QueueTrigger, ResyncTrigger, StalenessGuard

### Community 34 - "._process_with_llm"
Cohesion: 0.05
Nodes (7): _BatchContext, _contents_have_pruned_or_decayed(), _ensure_recall_tool_if_needed(), _is_close_phase_fc(), _QuotaShedState, _retry_backoff_delay(), Pulse

### Community 36 - "cli-executor.js"
Cohesion: 0.09
Nodes (40): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, MAX_TASK_WALL_MS, MAX_TIMER_MS, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS, STORAGE_PRETASK_TIMEOUT_MS, resolveStorageRoot }, buildCLICommand(), buildTimeoutResult(), { checkAndRecycleStorage, pinTaskCwd, unpinTaskCwd }, CLAUDE_JSON_PATH, cp, createInactivityWatchdog(), createLineUsageEmitter() (+32 more)

### Community 37 - "create_adapter"
Cohesion: 0.07
Nodes (14): generate_event_title(), get_adapter(), _get_semaphore(), spawn_event_namer_task(), create_adapter(), handle_app_home_opened(), handle_app_mention(), handle_create_event_modal() (+6 more)

### Community 38 - "KnowledgeGraphStore"
Cohesion: 0.08
Nodes (9): _format_graph_context(), get_graph_context(), _parse_props(), _sanitize(), translate_to_lookups(), _acquire(), KnowledgeGraphStore, _sanitize() (+1 more)

### Community 40 - "storage-recycler.js"
Cohesion: 0.07
Nodes (38): withTaskStorage(), MAX_TASK_WALL_MS, parsePositiveInt(), parseTimerMs(), resolveStorageRoot(), resolveTimeoutMs(), ROLE_TIMEOUTS, STORAGE_ACTIVITY_HEARTBEAT_MS (+30 more)

### Community 41 - "._process_event_inner"
Cohesion: 0.05
Nodes (4): _has_non_user_turns(), _is_automated_nudge(), _is_participant_turn(), _sanitize_error_text()

### Community 42 - "ArchitectureGraph.tsx"
Cohesion: 0.07
Nodes (30): HealthStatus, NodeType, AppNodeData, applyDagreLayout(), applyGridLayout(), applyLayout(), ArchitectureGraphInner(), buildGraph() (+22 more)

### Community 43 - "AgentClient"
Cohesion: 0.07
Nodes (4): Architect, AgentClient, Developer, SysAdmin

### Community 44 - "context_parts.py"
Cohesion: 0.09
Nodes (18): _apply_sibling_signature(), build_single_function_response(), compress_contents(), _compress_single_msg_parts(), contents_have_pruned_or_decayed(), estimate_msg_tokens(), estimate_tokens(), extract_model_parts() (+10 more)

### Community 45 - "get_quota_registry"
Cohesion: 0.10
Nodes (18): _commit_with_task_cap(), _consume(), _consume_queue(), _reconcile_terminal_token_usage(), _record_live_token_usage(), _sanitize_stdout(), get_quota_registry(), extract_genai_usage() (+10 more)

### Community 47 - "ConversationTurn"
Cohesion: 0.09
Nodes (31): submitApprovalDecision(), ApprovalOption, ConversationTurn, DecisionPayload, ApprovalDecisionCard(), ErrState, Props, ApprovalWriteInBox() (+23 more)

### Community 48 - "CortexGraph.tsx"
Cohesion: 0.10
Nodes (30): KGServiceEntity, eventColor(), getStructuralEdges(), DEFAULT_TYPE_BUDGET, evictLru(), KNOWLEDGE_RING, KNOWLEDGE_RING_TYPES, KnowledgeNodeAttributes (+22 more)

### Community 49 - "ConversationTurn"
Cohesion: 0.14
Nodes (25): emit_tool_result(), _safe_int(), handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_ask_release_ai(), handle_fetch_jira_issue(), handle_greenwave() (+17 more)

### Community 50 - "VcsPlatformPort"
Cohesion: 0.08
Nodes (5): _notify_phase_b(), _prune_from_snapshot(), _skip_phase_b(), VcsWorkItem, VcsPlatformPort

### Community 51 - "ws-client.js"
Cohesion: 0.10
Nodes (28): clearIdleTimer(), {
  DEFAULT_WORK_DIR, AGENT_CLI, AGENT_MODEL, AGENT_ROLE,
  EVENT_ID, EPHEMERAL, IDLE_TIMEOUT_MS,
  CLI_429_MAX_RETRIES, CLI_429_INITIAL_DELAY_MS, CLI_429_BACKOFF_MULTIPLIER,
  resolveTimeoutMs, parsePositiveInt, MAX_TASK_WALL_MS, MAX_TIMER_MS,
}, { ensureEventDocument }, { executeCLIStreaming, prepareResultsDir, is429Error }, { filterSkillsByRole, filterSkillsByMode, swapActiveRules, restoreAllSkills }, fs, handleCancel(), handleServerMessage() (+20 more)

### Community 52 - "handlers_integration.py"
Cohesion: 0.10
Nodes (19): _get_jira_reporter(), handle_comment_jira_issue(), handle_refresh_github_context(), _emit(), handle_refresh_gitlab_context(), handle_refresh_kargo_context(), _is_darwin_reentrant_caller(), _is_positive_int() (+11 more)

### Community 53 - "TokenMeter"
Cohesion: 0.07
Nodes (5): BoundedTeamCounter, normalize_team_id(), _zero_bucket(), TokenMeter, TokenUsageDict

### Community 54 - "sanitize_untrusted_line"
Cohesion: 0.12
Nodes (20): _clean_lines(), format_event_state_tail(), _build_closed_block(), build_event_header(), _build_identity_block(), build_immutable_event_anchor(), _build_journal_block(), _build_mermaid_block() (+12 more)

### Community 55 - "TimeKeeperPage.tsx"
Cohesion: 0.12
Nodes (24): createSchedule(), deleteSchedule(), getSchedules(), refineInstructions(), ScheduleCreatePayload, ScheduleItem, toggleSchedule(), updateSchedule() (+16 more)

### Community 56 - "observations_reporter.py"
Cohesion: 0.10
Nodes (15): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship, acquire_raw_genai(), rollback_raw_genai(), _analyze_series() (+7 more)

### Community 57 - "KubernetesSpawnHealthAdapter"
Cohesion: 0.08
Nodes (4): KubernetesSpawnHealthAdapter, _PodHealthState, SpawnPollResult, SpawnStatus

### Community 58 - "EphemeralProvisioner"
Cohesion: 0.07
Nodes (4): DispatchMetrics, EphemeralProvisioner, SpawnFailed, SpawnHealthPort

### Community 60 - ".poll_work_items"
Cohesion: 0.09
Nodes (3): _get_allowed_mention_authors(), _valid_positive_int(), PlatformQueueItem

### Community 61 - "headhunter_item_action"
Cohesion: 0.10
Nodes (17): _acquire_hh_poll_lock(), _busy_lock_response(), _extract_snapshot_items(), _get_headhunter_or_503(), _github_active_item(), headhunter_item_action(), headhunter_pending_todos(), _normalized_row_keys() (+9 more)

### Community 63 - "useOpsControl"
Cohesion: 0.14
Nodes (25): Dashboard(), GridTile(), GridTileProps, TileType, InlineMarkdownViewer(), EmptyState(), LayoutMode, StreamGrid() (+17 more)

### Community 64 - "._poll_pr_feedback"
Cohesion: 0.08
Nodes (9): _bot_login(), _csv_env(), _consider(), _is_slash_command_only(), _iso(), _mention_pattern(), _parse_ts(), _review_ignore_logins() (+1 more)

### Community 65 - "._github_poll_and_process"
Cohesion: 0.10
Nodes (5): _maybe_refresh_snapshot(), _on_gh_phase_b_settled(), _iref(), _try_queue_issue(), _on_gl_phase_b_settled()

### Community 66 - "useCortexData.ts"
Cohesion: 0.17
Nodes (27): getCognitiveGraph(), getCortexActivity(), getKGServiceDetail(), getKGServices(), getKGStats(), getKnowledgeById(), getMemory(), getRecentPulses() (+19 more)

### Community 67 - "types.py"
Cohesion: 0.09
Nodes (13): _safe_seconds(), _parse_priority_aging_sec(), derive_llm_priority(), _get_timeout_env_warned(), _get_timeout_order_warned(), is_partial_control_token(), parse_timeout_env(), process_stream_call_syntax_buffer() (+5 more)

### Community 68 - "EventDrillDown.tsx"
Cohesion: 0.13
Nodes (22): getEventPulses(), BrainCore(), CortexDevPage(), devQueryClient, CortexLiveFeedProps, EventDrillDown(), EventDrillDownProps, FRICTION_COLORS (+14 more)

### Community 70 - "dependencies.py"
Cohesion: 0.09
Nodes (13): get_aligner(), get_architect(), get_argocd_observer(), get_developer(), get_kargo_observer(), get_kg_store(), get_report_client(), get_sysadmin() (+5 more)

### Community 72 - "PulseBatch"
Cohesion: 0.09
Nodes (4): PulseBatch, PulsePort, PulseObserver, PulseTracker

### Community 73 - "llm_error_classifier.py"
Cohesion: 0.13
Nodes (9): _extract_status_code(), _has_non_retryable_cause(), _is_google_auth_transport_error(), is_rate_limit(), is_transient(), is_transient_llm_error_turn(), _iter_exception_chain(), _matches_mro() (+1 more)

### Community 74 - "server.js"
Cohesion: 0.09
Nodes (18): { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, ensureEventDocument(), fs, path, stageEventDocument(), fetchEventDocument(), fs, { handleRequest } (+10 more)

### Community 75 - "StateWatcher"
Cohesion: 0.10
Nodes (4): PollFn, _QueueEntry, StateWatcher, _Subscription

### Community 77 - "cognitive_graph.py"
Cohesion: 0.11
Nodes (11): get_pulse_tracker(), dismiss_proposals(), DismissRequest, get_all_shadow_interventions(), get_cognitive_graph(), get_cortex_activity(), get_cortex_status(), get_event_shadow_interventions() (+3 more)

### Community 78 - "state/__init__.py"
Cohesion: 0.11
Nodes (4): sanitize_redis_port(), close_redis(), get_redis(), RedisClient

### Community 83 - "claude-guard.js"
Cohesion: 0.14
Nodes (17): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+9 more)

### Community 84 - "_sanitize_analysis_text"
Cohesion: 0.10
Nodes (9): _clamp_confidence(), _prepare_console_tail(), _redact_match(), _redact_secrets_in_text(), _sanitize_analysis_text(), _sanitize_console_tail(), _strip_newlines(), _validate_analysis() (+1 more)

### Community 87 - "OpsStateContext.tsx"
Cohesion: 0.15
Nodes (19): getAgents(), getKargoStages(), AgentRegistryEntry, ApprovalErrorKind, KargoStageStatus, AgentRegistryPanel(), formatConnectedSince(), AgentGroups (+11 more)

### Community 88 - "reconcile.py"
Cohesion: 0.18
Nodes (10): generate_phase_tool_map(), _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers(), main() (+2 more)

### Community 90 - "observers/kargo.py"
Cohesion: 0.18
Nodes (7): build_verification_dedup_key(), extract_latest_verification(), is_verification_stale(), _parse_ts(), project_stage_status(), resolve_stage_freight(), _s()

### Community 94 - "cli-setup.js"
Cohesion: 0.13
Nodes (17): { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync }, filterSkillsByMode() (+9 more)

### Community 96 - "handle_report_incident"
Cohesion: 0.11
Nodes (5): handle_report_incident(), _resolve_escalation_scope(), IdleTimeoutPort, IncidentAdapterPort, StateWatcherPort

### Community 98 - "get_report"
Cohesion: 0.11
Nodes (6): get_report(), list_reports(), reports_spa_no_slash(), reports_spa_with_slash(), search_reports(), _serve_spa()

### Community 99 - "catalog-skills.js"
Cohesion: 0.15
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 100 - "JiraIncidentAdapter"
Cohesion: 0.15
Nodes (3): _adf_to_text(), _escape_jql_string(), JiraIncidentAdapter

### Community 104 - "ShiftsPage.tsx"
Cohesion: 0.23
Nodes (16): getCurrentShift(), getShiftDetail(), getShiftsList(), ShiftReportFull, ShiftReportSummary, FailedClusterBadge(), getISOWeek(), getWeekDates() (+8 more)

### Community 107 - "maintainers.py"
Cohesion: 0.20
Nodes (8): _resolve_maintainer_enum(), _dedupe(), _extract_evidence_maintainer_emails(), is_slack_recipient_allowed(), maintainer_env_key(), _resolve_evidence_env_maintainer_emails(), resolve_maintainer_emails(), _resolve_static_env_emails()

### Community 110 - "JenkinsPlatformPort"
Cohesion: 0.13
Nodes (4): BuildDetails, JenkinsPlatformPort, JobRunState, ViewScanResult

### Community 116 - "quota_registry.py"
Cohesion: 0.17
Nodes (5): is_enmaas_enabled(), _parse_ceiling_ratio(), parse_tpm_limit(), QuotaPoolRegistry, reset_quota_registry()

### Community 119 - "prefix_builder.py"
Cohesion: 0.23
Nodes (5): build_global_core_si(), canonical_wire_tools(), compute_prefix_hashes(), sha8_json(), sha8_text()

### Community 121 - "handlers_planning.py"
Cohesion: 0.23
Nodes (7): _auto_complete_step(), _canonical_role(), handle_create_plan(), handle_get_plan_progress(), _is_failed_turn(), _is_orchestrator_turn(), _normalize_step_id()

### Community 122 - "has_unevaluated_close_blocker"
Cohesion: 0.16
Nodes (6): has_unevaluated_close_blocker(), _pred_jarvis_response(), _pred_unevaluated_close(), is_jarvis_acknowledgment(), is_stabilization_wake(), safe_score()

### Community 124 - "generate_map.py"
Cohesion: 0.19
Nodes (5): _enumerate_gates(), _GateInfo, _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 125 - "._extract_context_flags"
Cohesion: 0.15
Nodes (3): compute_dispatch_backpressure(), ContextFlags, _safe_int_env()

### Community 126 - "evaluate_gates"
Cohesion: 0.15
Nodes (7): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), is_wait_for_user_admissible_after_response(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 128 - "NeuronInfoPanel.tsx"
Cohesion: 0.24
Nodes (12): KGServiceDetail, asNumber(), asString(), asStringArray(), Badge(), describeNeuron(), Hdr(), NeuronInfoPanel() (+4 more)

### Community 129 - "usage-tracker.js"
Cohesion: 0.26
Nodes (10): ALL_KEYS, createTaskUsageAccumulator(), startSpawn(), diffAndAdd(), emptyUsage(), extractStreamUsage(), inferProvider(), normalizeUsage() (+2 more)

### Community 133 - "_batch_is_terminal_for_flush"
Cohesion: 0.17
Nodes (6): _batch_is_terminal_for_flush(), _wait_for_user_admissible(), build_gate_context(), conversation_has_decayed_turns(), _decay_payload_len(), decay_cutoff_index()

### Community 137 - "CortexLiveFeed.tsx"
Cohesion: 0.24
Nodes (10): CortexHeartbeat(), CortexHeartbeatProps, ensureKeyframes(), CortexLiveFeed(), FILTER_PILLS, FilterKey, getStoredFilter(), MESSAGE_STYLES (+2 more)

### Community 139 - "_paginate_github_get"
Cohesion: 0.20
Nodes (4): is_shared_installation_manager(), _paginate_github_get(), parse_github_next_link(), _safe_parse_int()

### Community 143 - "cortex-constants.ts"
Cohesion: 0.18
Nodes (10): AGENTS, DOMAINS, HEMISPHERE_X, NEURON_DESCRIPTIONS, PHASE_SKILL_FOLDERS, PHASE_TOOL_PRIORITY, PHASES, StructuralEdge (+2 more)

### Community 147 - "handle_notify_user_slack"
Cohesion: 0.20
Nodes (5): _alert_wrapper_retrigger(), _do_retrigger(), handle_notify_user_slack(), _resolve_slack_user(), build_event_report_md()

### Community 162 - "adf_to_markdown"
Cohesion: 0.57
Nodes (7): adf_to_markdown(), _apply_marks(), _children(), _render(), _render_list(), _render_list_item(), _render_table_like()

### Community 167 - "cortex/types.ts"
Cohesion: 0.29
Nodes (6): EventSource, CognitiveGraphResponse, CortexHeartbeatMessage, FrictionIndicator, FrictionPattern, NeuronVisual

### Community 168 - "state.js"
Cohesion: 0.33
Nodes (4): { AGENT_ROLE }, _blackboardTurns, _inboundMessages, _teammateMessages

### Community 172 - "get_event_flow"
Cohesion: 0.33
Nodes (3): get_event_flow(), delta(), get_flow_history()

### Community 178 - "handle_recall_pruned_turns"
Cohesion: 0.50
Nodes (3): _coerce_turn_int(), handle_recall_pruned_turns(), _parse_turn_int()

## Knowledge Gaps
- **107 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `brain.py`, `slack.py`, `auth.py`, `queue.py`, `os`, `nightwatcher_tools.py`, `Brain`, `main.py`, `_is_event_closed_or_missing`, `Any`, `ConversationMessage`, `._update_event_vcs_context`, `update_schedule`, `create_adapter`, `EventDocument`, `._restage_pending_signal`, `._stage_pending_signal`, `.__init__`, `ConversationTurn`, `._count_pending`, `._commit_pending_signal`, `._drain_pending`, `observations_reporter.py`, `.drain_notes`, `.get_edge_metadata`, `dependencies.py`, `LiveAPIAdapter`, `state/__init__.py`, `observers/kargo.py`, `DashboardWSAdapter`, `get_report`, `HeadhunterJira`, `._validate_gitlab_ids`, `ScheduleRepository`?**
  _High betweenness centrality (0.142) - this node is a cross-community bridge._
- **Are the 86 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 86 INFERRED edges - model-reasoned connections that need verification._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.007692151156875115 - nodes in this community are weakly interconnected._
- **Why does `ConversationTurn` connect `ConversationTurn` to `BlackboardState`, `brain.py`, `slack.py`, `auth.py`, `queue.py`, `EventRepository`, `._tool_send_event_message`, `GitLabPlatform`, `Brain`, `handle_notify_user_slack`, `._run_agent_task`, `SlackChannel`, `Any`, `ToolContext`, `Aligner`, `._process_with_llm`, `create_adapter`, `EventDocument`, `._process_event_inner`, `context_parts.py`, `handle_recall_pruned_turns`, `handlers_integration.py`, `_compute_processed_up_to`, `GitHubPlatform`, `._poll_pr_feedback`, `LiveAPIAdapter`, `DashboardWSAdapter`, `handle_report_incident`, `BrainLifecyclePort`, `handlers_planning.py`?**
  _High betweenness centrality (0.059) - this node is a cross-community bridge._
- **Are the 20 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Should `brain.py` be split into smaller, more focused modules?**
  _Cohesion score 0.02280334728033473 - nodes in this community are weakly interconnected._
- **Why does `Brain` connect `Brain` to `BlackboardState`, `brain.py`, `slack.py`, `FlowCollector`, `._resolve_llm_params`, `._post_agent_recall`, `._run_agent_task`, `main.py`, `dispatch.py`, `Any`, `.start_event_loop`, `ReconcileScheduler`, `._process_with_llm`, `._detect_repetition_collapse`, `EventDocument`, `._process_event_inner`, `ConversationTurn`, `.__init__`, `BrainSkillLoader`, `dependencies.py`, `PulseBatch`, `StateWatcher`, `IdleTimeoutManager`, `ReflexSearcher`, `DashboardWSAdapter`, `JarvisPeerPort`, `BrainLifecyclePort`, `prefix_builder.py`, `._extract_context_flags`?**
  _High betweenness centrality (0.045) - this node is a cross-community bridge._