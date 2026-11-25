# Graph Report - Blackboard  (2026-11-25)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 6098 nodes · 14087 edges · 244 communities (127 shown, 117 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 1062 edges (avg confidence: 0.89)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `734e357e`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BlackboardState
- os
- main.py
- client.ts
- brain.py
- GitLabPlatform
- ConversationTurn
- models.py
- react
- tool_gates.py
- SlackChannel
- Brain
- Headhunter
- EventRepository
- EventSidebar.tsx
- ._run_agent_task
- KargoObserver
- colors.ts
- FastAPI
- http-handler.js
- ReconcileScheduler
- hooks/index.ts
- Archivist
- api/types.ts
- jenkins-mcp.js
- AgentRegistry
- GitHubAppAuth
- topology.py
- nightwatcher_tools.py
- App.tsx
- useMemory.ts
- auth.py
- EventDocument
- ._process_with_llm
- EventEvidence
- slack.py
- StreamGrid.tsx
- _BrainToolContext
- TurnBubble.tsx
- merge-guard.js
- handlers_integration.py
- GeminiAdapter
- cli-executor.js
- storage-recycler.js
- KnowledgeGraphStore
- lucide-react
- llm/__init__.py
- slack_approvals.py
- approval_decision.py
- Aligner
- GitHubPlatform
- reconcile.py
- VcsPlatformPort
- ws-client.js
- DashboardWSAdapter
- ui/package.json
- JenkinsObserver
- types.py
- useCortexData.ts
- start_headhunter_task
- StateWatcher
- VectorStore
- BrainSkillLoader
- BoolOutcome
- Any
- NightwatcherObserver
- ._poll_pr_feedback
- get_blackboard
- CortexGraph.tsx
- LiveAPIAdapter
- llm_error_classifier.py
- observations_mgmt.py
- SecurityError
- server.js
- queue.py
- ._poll_issues
- JenkinsAdapter
- PulseBatch
- NeuronInfoPanel.tsx
- jira.py
- get_archivist
- .get_event
- TopologyRepository
- dependencies
- jira_incident.py
- compilerOptions
- claude-guard.js
- ArchitectureGraph.tsx
- gemini_client.py
- OpsStateContext.tsx
- FlowHistoryPage.tsx
- _sanitize_analysis_text
- IdleTimeoutManager
- _build_active_overlay
- Any
- reports.py
- cortex/types.ts
- cli-setup.js
- ScheduleCreateRequest
- _resolve_phase
- _build_event_state_tail_block
- ReflexSearcher
- utils/__init__.py
- QuotaTracker
- TokenMeter
- devDependencies
- compilerOptions
- gemini-sidecar/package.json
- JarvisPeerPort
- EphemeralProvisioner
- HeadhunterCircuitBreaker
- ArchitectureEvent
- ._feedback_reject_reason
- HeadhunterJira
- headhunter_pending_todos
- ObservationRepository
- ShiftsPage.tsx
- catalog-skills.js
- observations.py
- update_event_title
- EscalationRepository
- list_active_events
- JenkinsPlatformPort
- ._poll_and_stage
- OIDCKeyAdapter
- KubernetesSpawnHealthAdapter
- BrainLifecyclePort
- resolve_live_head_sha
- ServiceNode.tsx
- observations_reporter.py
- ._connect
- get_brain
- ScheduleRepository
- post
- analyzeTokens
- EventDrillDown.tsx
- record_token_usage
- handlers_planning.py
- evaluate_gates
- IncidentAdapterPort
- prefix_builder.py
- ._drain_once
- testSetup.ts
- ._process_message
- .fetch_context
- event_to_markdown
- ._build_contents
- SlackAccessGate
- GitLabTokenAuth
- gitGuard
- parseShell
- generate_event_title
- create_adapter
- ._extract_context_flags
- entity_extractor.py
- ._clear_recovered_group_flags
- has_unevaluated_close_blocker
- BrainIntrospectionPort
- flow.py
- PulseBatch
- CortexDevPage.tsx
- spawn_health.py
- classifyTool
- SpawnPollResult
- .has_reeval_signal
- _get_canonical_or_alias
- build_gate_context
- journal.py
- shifts.py
- _is_event_closed_or_missing
- ._evaluate_health
- LLMStreamInterChunkTimeoutError
- ConversationMessage
- TimeKeeperObserver
- CortexRepository
- adf_to_markdown
- validate-mutations.sh
- scripts
- state.js
- get_token_meter
- DispatchMetrics
- build_manifest_table
- .__init__
- ._wait_for_registration
- classify
- PlatformQueueItem
- delete_notebook_note
- rebuild_deep_memory
- require-results.sh
- _safe_loader_get_body
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
1. `BlackboardState` - 330 edges
2. `Brain` - 170 edges
3. `ConversationTurn` - 157 edges
4. `ToolContext` - 103 edges
5. `EventDocument` - 100 edges
6. `GateContext` - 100 edges
7. `GitHubPlatform` - 99 edges
8. `EventRepository` - 95 edges
9. `Headhunter` - 89 edges
10. `react` - 87 edges

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

## Communities (244 total, 117 thin omitted)

### Community 1 - "os"
Cohesion: 0.04
Nodes (18): _sanitize_lesson_text(), PlatformBreakerStatus, PlatformSnapshot, _safe_int(), _parse_job_metadata(), _encode_cursor(), _load_name_mapping(), get_installation_manager() (+10 more)

### Community 2 - "main.py"
Cohesion: 0.03
Nodes (35): Architect, AgentClient, Developer, set_incident_options(), SysAdmin, TaskBridge, set_oidc_adapter(), get_aligner() (+27 more)

### Community 3 - "client.ts"
Cohesion: 0.04
Nodes (91): @tanstack/react-query, ApiError, approveEvent(), bulkDeleteObservations(), createSchedule(), deleteNote(), deleteObservation(), deleteSchedule() (+83 more)

### Community 4 - "brain.py"
Cohesion: 0.04
Nodes (41): _close_unanswered_fc(), _compute_processed_up_to(), _contents_have_pruned_or_decayed(), _has_non_user_turns(), _is_external_input_turn(), _is_seed_turn(), _is_steering_turn(), _apply_sibling_signature() (+33 more)

### Community 5 - "GitLabPlatform"
Cohesion: 0.05
Nodes (6): _get_allowed_mention_authors(), _get_static_maintainer_emails(), GitLabPlatform, _reconcile_synthetic(), _check_one(), _valid_positive_int()

### Community 6 - "ConversationTurn"
Cohesion: 0.07
Nodes (41): emit_tool_result(), handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_recall_pruned_turns(), handle_message_agent(), handle_reply_to_agent(), handle_report_incident() (+33 more)

### Community 7 - "models.py"
Cohesion: 0.04
Nodes (33): AppNode, ApprovalCommitResult, ApprovalOption, ChatRequest, ChatResponse, EventInput, EventMetrics, EventStatus (+25 more)

### Community 8 - "react"
Cohesion: 0.05
Nodes (69): react, updateEventTitle(), AgentRegistryEntry, CiContext, ConversationTurn, TokenUsageDict, CiContextCard(), CiContextCardProps (+61 more)

### Community 9 - "tool_gates.py"
Cohesion: 0.05
Nodes (79): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+71 more)

### Community 10 - "SlackChannel"
Cohesion: 0.05
Nodes (13): spawn_event_namer_task(), format_event_summary(), SlackChannel, handle_app_home_opened(), handle_app_mention(), handle_approve(), handle_approve_sha(), handle_create_event_modal() (+5 more)

### Community 12 - "Headhunter"
Cohesion: 0.05
Nodes (8): Headhunter, _maybe_refresh_snapshot(), _on_gh_phase_b_created(), _iref(), _process_issue(), _try_queue_issue(), _on_gl_phase_b_created(), HeadhunterOperationError

### Community 14 - "EventSidebar.tsx"
Cohesion: 0.06
Nodes (71): getAlignerPending(), getHeadhunterStatus(), getJiraMissions(), headhunterItemAction(), HeadhunterItemActionPayload, HeadhunterTodo, postJiraAction(), triggerHeadhunterPoll() (+63 more)

### Community 15 - "._run_agent_task"
Cohesion: 0.05
Nodes (10): on_huddle(), on_progress(), on_huddle(), on_progress(), _is_automated_nudge(), _is_participant_turn(), _sanitize_error_text(), _sanitize_override_reason() (+2 more)

### Community 16 - "KargoObserver"
Cohesion: 0.05
Nodes (10): ArgoCDObserver, build_verification_dedup_key(), extract_latest_verification(), is_verification_stale(), _parse_ts(), project_stage_status(), resolve_stage_freight(), _s() (+2 more)

### Community 17 - "colors.ts"
Cohesion: 0.06
Nodes (48): getReport(), getReports(), ReportFull, ReportMeta, DeferCountdownBar(), CompactCardStrip(), EventHistory(), TimeRange (+40 more)

### Community 18 - "FastAPI"
Cohesion: 0.04
Nodes (16): get_kg_store(), dex_proxy(), report_tampering(), FeedbackRequest, submit_feedback(), list_incidents(), KargoStageSnapshot, list_failed_stages() (+8 more)

### Community 19 - "http-handler.js"
Cohesion: 0.08
Nodes (62): is429Error(), registerMCPsAndHooks(), resolveCommand(), writeAgyMcpServer(), writeClaudeMcpServer(), parsePositiveInt(), buildArgoCDMcpConfig(), createAppJWT() (+54 more)

### Community 20 - "ReconcileScheduler"
Cohesion: 0.04
Nodes (7): FlowCollector, FairQueue, ReconcileScheduler, Trigger, QueueTrigger, ResyncTrigger, StalenessGuard

### Community 21 - "hooks/index.ts"
Cohesion: 0.06
Nodes (52): react-router-dom, getActiveEvents(), getClosedEvents(), getEventDocument(), getEvents(), getWaitingApprovalEvents(), ArchitectureEvent, ArgoCDOperation (+44 more)

### Community 23 - "api/types.ts"
Cohesion: 0.04
Nodes (54): submitApprovalDecision(), Agent, AlignerPendingItem, AppConfig, AppNode, ApprovalEffect, ApprovalOption, ApprovalResolution (+46 more)

### Community 24 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 25 - "AgentRegistry"
Cohesion: 0.05
Nodes (15): AgentConnection, AgentRegistry, agent_websocket_handler(), _heartbeat(), _build_prompt(), _check_security(), consume_wake_task(), _consume() (+7 more)

### Community 26 - "GitHubAppAuth"
Cohesion: 0.05
Nodes (8): AsyncGitHubClient, _find_pem_file(), GitHubAppAuth, _handle_rate_limit(), MultiInstallationManager, _paginate_github_get(), parse_github_next_link(), _safe_parse_int()

### Community 27 - "topology.py"
Cohesion: 0.05
Nodes (7): get_event_document(), get_graph_data(), get_mermaid_diagram(), get_service_details(), get_topology(), list_services(), calculate_health_from_argocd()

### Community 28 - "nightwatcher_tools.py"
Cohesion: 0.07
Nodes (25): PulseContext, ShiftIncident, ShiftInvestigation, build_report_iteration_prompt(), build_summary_prompt(), extract_full_links(), build_extend_tool(), build_report_tool() (+17 more)

### Community 29 - "App.tsx"
Cohesion: 0.07
Nodes (44): oidc-client-ts, react-dom, dismissProposals(), EnhancementProposal, getConfig(), getHandoffReports(), getProposals(), getWSAuthFailureCallback() (+36 more)

### Community 30 - "useMemory.ts"
Cohesion: 0.08
Nodes (47): applyLessons(), correctMemory(), createKnowledge(), createLesson(), deleteKnowledge(), deleteLesson(), ExtractedCorrection, ExtractedLesson (+39 more)

### Community 31 - "auth.py"
Cohesion: 0.06
Nodes (15): _claims_to_user(), get_user_from_request(), get_user_from_websocket(), require_auth(), require_obs_admin(), UserContext, _validate_jwt(), _require_jira_mutation_auth() (+7 more)

### Community 33 - "._process_with_llm"
Cohesion: 0.04
Nodes (5): _BatchContext, _ensure_recall_tool_if_needed(), _QuotaShedState, RepetitionCollapse, _retry_backoff_delay()

### Community 34 - "EventEvidence"
Cohesion: 0.08
Nodes (23): _clean_lines(), format_event_state_tail(), _build_closed_block(), build_event_header(), _build_identity_block(), build_immutable_event_anchor(), _build_journal_block(), _build_mermaid_block() (+15 more)

### Community 35 - "slack.py"
Cohesion: 0.06
Nodes (20): build_access_denied_home_view(), build_home_tab_view(), _context_line(), create_feedback_block(), extract_tables(), _replace(), format_plan_block(), format_task_card() (+12 more)

### Community 36 - "StreamGrid.tsx"
Cohesion: 0.07
Nodes (41): getFlowMetrics(), FlowMetrics, AgentStreamCard(), AgentStreamCardProps, MessageCards(), Dashboard(), GridTile(), GridTileProps (+33 more)

### Community 38 - "TurnBubble.tsx"
Cohesion: 0.09
Nodes (37): @uiw/react-markdown-preview, closeEvent(), enforceCasualDomain(), submitFeedback(), MessageStatus, ApprovalResolvedSummary(), ConversationFeed(), ConversationFeedProps (+29 more)

### Community 39 - "merge-guard.js"
Cohesion: 0.04
Nodes (46): API_VALUED, ARGO_MUTATING, ARGO_READ_SUB, ARGO_READ_TOP, BODY_FLAG, BROWSER_READ, CTX, ENV_BUILTINS (+38 more)

### Community 40 - "handlers_integration.py"
Cohesion: 0.07
Nodes (24): _alert_wrapper_retrigger(), _do_retrigger(), _get_jira_reporter(), handle_refresh_github_context(), _emit(), handle_refresh_gitlab_context(), handle_refresh_kargo_context(), _is_darwin_reentrant_caller() (+16 more)

### Community 41 - "GeminiAdapter"
Cohesion: 0.09
Nodes (9): _attach_signature_to_parts(), _coerce_part(), _decode_sig_bytes(), _extract_part_signature(), GeminiAdapter, _is_empty_sig_carrier(), _part_has_fc(), _sanitize_candidate_parts() (+1 more)

### Community 42 - "cli-executor.js"
Cohesion: 0.09
Nodes (37): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, MAX_TASK_WALL_MS, MAX_TIMER_MS, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS, STORAGE_PRETASK_TIMEOUT_MS, resolveStorageRoot }, buildCLICommand(), buildTimeoutResult(), { checkAndRecycleStorage, pinTaskCwd, unpinTaskCwd }, CLAUDE_JSON_PATH, cp, createInactivityWatchdog(), executeCLI() (+29 more)

### Community 43 - "storage-recycler.js"
Cohesion: 0.08
Nodes (37): withTaskStorage(), MAX_TASK_WALL_MS, parseTimerMs(), resolveStorageRoot(), resolveTimeoutMs(), ROLE_TIMEOUTS, STORAGE_ACTIVITY_HEARTBEAT_MS, STORAGE_MAX_TIER3_DELETIONS (+29 more)

### Community 44 - "KnowledgeGraphStore"
Cohesion: 0.09
Nodes (9): _format_graph_context(), get_graph_context(), _parse_props(), _sanitize(), translate_to_lookups(), _acquire(), KnowledgeGraphStore, _sanitize() (+1 more)

### Community 45 - "lucide-react"
Cohesion: 0.09
Nodes (26): lucide-react, createChatEvent(), ApprovalWriteInBox(), Props, ChatInput(), ChatInputProps, Draft, LastSubmission (+18 more)

### Community 46 - "llm/__init__.py"
Cohesion: 0.08
Nodes (6): ClaudeAdapter, FunctionCall, LLMChunk, LLMPort, LLMResponse, TokenUsage

### Community 47 - "slack_approvals.py"
Cohesion: 0.12
Nodes (22): get_user_from_slack(), build_approval_blocks(), build_writein_modal(), _derive_writein_hmac_key(), _escape_mrkdwn(), format_frozen_approval_blocks(), _safe_text(), sign_writein_metadata() (+14 more)

### Community 48 - "approval_decision.py"
Cohesion: 0.10
Nodes (14): can_approve_event(), resolve_approval_identity(), ApprovalResolution, execute_approval_decision(), ApprovalDecisionOutcome, DecisionRequest, resolve_selected_option(), validate_image_attachment() (+6 more)

### Community 51 - "reconcile.py"
Cohesion: 0.10
Nodes (15): _enumerate_gates(), _GateInfo, generate_phase_tool_map(), _load_gate_registry(), _render_markdown(), _render_ooda_overlay(), _build_redis_client(), _fetch_commit_sha() (+7 more)

### Community 53 - "ws-client.js"
Cohesion: 0.10
Nodes (26): clearIdleTimer(), {
  DEFAULT_WORK_DIR, AGENT_CLI, AGENT_MODEL, AGENT_ROLE,
  EVENT_ID, EPHEMERAL, IDLE_TIMEOUT_MS,
  CLI_429_MAX_RETRIES, CLI_429_INITIAL_DELAY_MS, CLI_429_BACKOFF_MULTIPLIER,
  resolveTimeoutMs, parsePositiveInt, MAX_TASK_WALL_MS, MAX_TIMER_MS,
}, { ensureEventDocument }, { executeCLIStreaming, prepareResultsDir, is429Error }, { filterSkillsByRole, filterSkillsByMode, swapActiveRules, restoreAllSkills }, fs, handleCancel(), handleTask() (+18 more)

### Community 54 - "DashboardWSAdapter"
Cohesion: 0.09
Nodes (6): DashboardWSAdapter, can_append_message(), prompt_display_name(), ChatEventRequest, ChatEventResponse, create_chat_event()

### Community 55 - "ui/package.json"
Cohesion: 0.08
Nodes (29): autoprefixer, cronstrue, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, graphology-layout-forceatlas2 (+21 more)

### Community 57 - "types.py"
Cohesion: 0.09
Nodes (14): _stale_reservation_ttl_s(), derive_llm_priority(), _get_timeout_env_warned(), _get_timeout_order_warned(), is_partial_control_token(), parse_timeout_env(), _patch_enum_fields(), process_stream_call_syntax_buffer() (+6 more)

### Community 58 - "useCortexData.ts"
Cohesion: 0.15
Nodes (28): getCognitiveGraph(), getCortexActivity(), getEventReport(), getKGServiceDetail(), getKGServices(), getKGStats(), getRecentPulses(), CortexPage() (+20 more)

### Community 59 - "start_headhunter_task"
Cohesion: 0.07
Nodes (3): redact_error_text(), on_headhunter_done(), start_headhunter_task()

### Community 60 - "StateWatcher"
Cohesion: 0.09
Nodes (4): PollFn, _QueueEntry, StateWatcher, _Subscription

### Community 64 - "Any"
Cohesion: 0.12
Nodes (3): VcsContext, _NoAliasSafeLoader, _validate_plan_yaml()

### Community 65 - "NightwatcherObserver"
Cohesion: 0.11
Nodes (6): ShiftReport, _append_user_turn(), _env_float(), _env_int(), NightwatcherObserver, _finalize_analysis_handover()

### Community 66 - "._poll_pr_feedback"
Cohesion: 0.08
Nodes (3): _get_static_maintainer_emails(), _iso(), _parse_ts()

### Community 67 - "get_blackboard"
Cohesion: 0.11
Nodes (12): get_blackboard(), get_pulse_tracker(), dismiss_proposals(), DismissRequest, get_all_shadow_interventions(), get_cognitive_graph(), get_cortex_activity(), get_cortex_status() (+4 more)

### Community 68 - "CortexGraph.tsx"
Cohesion: 0.14
Nodes (25): graphology, eventColor(), getExecutiveNeurons(), getStructuralEdges(), DEFAULT_TYPE_BUDGET, evictLru(), KNOWLEDGE_RING, KNOWLEDGE_RING_TYPES (+17 more)

### Community 70 - "llm_error_classifier.py"
Cohesion: 0.13
Nodes (9): _extract_status_code(), _has_non_retryable_cause(), _is_google_auth_transport_error(), is_rate_limit(), is_transient(), is_transient_llm_error_turn(), _iter_exception_chain(), _matches_mro() (+1 more)

### Community 71 - "observations_mgmt.py"
Cohesion: 0.10
Nodes (10): get_report_client(), render_pdf(), bulk_delete_observations(), BulkDeleteRequest, delete_observation(), export_observations(), generate_observations_report(), rename_observation() (+2 more)

### Community 72 - "SecurityError"
Cohesion: 0.08
Nodes (3): safe_execution(), wrapper(), SecurityError

### Community 73 - "server.js"
Cohesion: 0.09
Nodes (18): { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, ensureEventDocument(), fs, path, stageEventDocument(), fetchEventDocument(), fs, { handleRequest } (+10 more)

### Community 74 - "queue.py"
Cohesion: 0.12
Nodes (14): apply_lessons(), ApproveRequest, correct_memory(), CorrectMemoryRequest, create_knowledge(), create_lesson(), extract_lessons(), KnowledgeRequest (+6 more)

### Community 77 - "PulseBatch"
Cohesion: 0.10
Nodes (4): PulseBatch, PulsePort, PulseObserver, PulseTracker

### Community 78 - "NeuronInfoPanel.tsx"
Cohesion: 0.11
Nodes (23): KGServiceDetail, AGENTS, DOMAINS, HEMISPHERE_X, NEURON_DESCRIPTIONS, PHASE_SKILL_FOLDERS, PHASE_TOOL_PRIORITY, PHASES (+15 more)

### Community 80 - "jira.py"
Cohesion: 0.15
Nodes (9): approve_mission(), dismiss_mission(), _infer_phase(), _jira_config(), list_missions(), reanalyze_mission(), retry_mission(), _validate_jira_key() (+1 more)

### Community 81 - "get_archivist"
Cohesion: 0.11
Nodes (11): get_archivist(), aligner_pending_items(), delete_knowledge(), delete_lesson(), get_knowledge(), get_lesson(), get_memory(), jenkins_pending_items() (+3 more)

### Community 82 - ".get_event"
Cohesion: 0.09
Nodes (6): close_event_by_user(), CloseRequest, get_event_approval(), get_event_document(), get_event_report(), get_event_turns()

### Community 84 - "dependencies"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 85 - "jira_incident.py"
Cohesion: 0.12
Nodes (3): _adf_to_text(), _escape_jql_string(), JiraIncidentAdapter

### Community 86 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 87 - "claude-guard.js"
Cohesion: 0.14
Nodes (18): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+10 more)

### Community 88 - "ArchitectureGraph.tsx"
Cohesion: 0.14
Nodes (18): @dagrejs/dagre, @xyflow/react, applyDagreLayout(), applyGridLayout(), applyLayout(), ArchitectureGraph(), ArchitectureGraphInner(), buildGraph() (+10 more)

### Community 89 - "gemini_client.py"
Cohesion: 0.11
Nodes (10): _append_user_turn(), _clone_part_with_sig(), _clone_part_with_text(), _extract_call_syntax(), _is_function_response_part(), _parse_drain_timeout(), _strip_user_thought_signature(), _validated_parts() (+2 more)

### Community 90 - "OpsStateContext.tsx"
Cohesion: 0.15
Nodes (19): getAgents(), getKargoStages(), ApprovalErrorKind, EventEvidence, KargoStageStatus, AgentRegistryPanel(), formatConnectedSince(), AGENTS (+11 more)

### Community 91 - "FlowHistoryPage.tsx"
Cohesion: 0.23
Nodes (16): recharts, getFlowHistory(), FlowSnapshot, FlowHistoryPage(), RANGES, SparkCard(), SparkCardProps, formatTime() (+8 more)

### Community 92 - "_sanitize_analysis_text"
Cohesion: 0.10
Nodes (11): _annotation_replace(), _strip_pipeline_annotations(), _clamp_confidence(), _prepare_console_tail(), _redact_match(), _redact_secrets_in_text(), _sanitize_analysis_text(), _sanitize_console_tail() (+3 more)

### Community 94 - "_build_active_overlay"
Cohesion: 0.13
Nodes (8): _build_active_overlay(), _build_transient_overlays(), _collect_turn_overlay_part(), _get_global_core_paths(), _safe_loader_paths(), _safe_loader_resolve(), _safe_loader_tag_type(), _wrap_section()

### Community 95 - "Any"
Cohesion: 0.17
Nodes (12): _build_turn0_anchor(), _call_anchor_get(), _call_anchor_set_nx(), _FrozenAnchor, _hydrate_anchor_dict(), _incr_flow_counter_safely(), _l1_get_anchor(), _l1_put_anchor() (+4 more)

### Community 96 - "reports.py"
Cohesion: 0.12
Nodes (6): get_report(), list_reports(), reports_spa_no_slash(), reports_spa_with_slash(), search_reports(), _serve_spa()

### Community 97 - "cortex/types.ts"
Cohesion: 0.17
Nodes (18): CortexHeartbeat(), CortexHeartbeatProps, ensureKeyframes(), CortexLiveFeed(), CortexLiveFeedProps, FILTER_PILLS, FilterKey, getStoredFilter() (+10 more)

### Community 98 - "cli-setup.js"
Cohesion: 0.13
Nodes (18): { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync }, filterSkillsByMode() (+10 more)

### Community 100 - "_resolve_phase"
Cohesion: 0.12
Nodes (9): _batch_is_terminal_for_flush(), _extract_accepted_domain(), _extract_accepted_phase(), _is_close_phase_fc(), _wait_for_user_admissible(), can_transition_to_close(), _resolve_domain(), resolve_event_domain() (+1 more)

### Community 101 - "_build_event_state_tail_block"
Cohesion: 0.11
Nodes (3): _build_event_state_tail_block(), _init_tool_names(), _strip_tool_names()

### Community 103 - "utils/__init__.py"
Cohesion: 0.16
Nodes (9): _resolve_maintainer_enum(), get_github_auth(), _dedupe(), _extract_evidence_maintainer_emails(), is_slack_recipient_allowed(), maintainer_env_key(), _resolve_evidence_env_maintainer_emails(), resolve_maintainer_emails() (+1 more)

### Community 104 - "QuotaTracker"
Cohesion: 0.13
Nodes (4): QuotaExhaustedError, QuotaTracker, RequestExceedsBurstError, Reservation

### Community 106 - "devDependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 107 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 108 - "gemini-sidecar/package.json"
Cohesion: 0.11
Nodes (18): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+10 more)

### Community 112 - "ArchitectureEvent"
Cohesion: 0.13
Nodes (3): ArchitectureEvent, list_events(), MetricsRepository

### Community 113 - "._feedback_reject_reason"
Cohesion: 0.13
Nodes (7): _bot_login(), _csv_env(), _consider(), _is_slash_command_only(), _mention_pattern(), _review_ignore_logins(), _review_trusted_associations()

### Community 115 - "headhunter_pending_todos"
Cohesion: 0.18
Nodes (12): _extract_snapshot_items(), _github_active_item(), headhunter_pending_todos(), _normalized_row_keys(), headhunter_platform_status(), _match_snapshot_item(), _pending_row_keys(), _read_headhunter_snapshot_safe() (+4 more)

### Community 117 - "ShiftsPage.tsx"
Cohesion: 0.23
Nodes (16): getCurrentShift(), getShiftDetail(), getShiftsList(), ShiftReportFull, ShiftReportSummary, FailedClusterBadge(), getISOWeek(), getWeekDates() (+8 more)

### Community 118 - "catalog-skills.js"
Cohesion: 0.16
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 123 - "update_event_title"
Cohesion: 0.12
Nodes (5): demote_lesson(), HeadhunterItemActionRequest, TitleUpdateRequest, update_event_title(), verify_lesson()

### Community 125 - "list_active_events"
Cohesion: 0.12
Nodes (6): _defer_timeline_fields(), _has_active_subscription(), list_active_events(), list_closed_events(), list_waiting_approval_events(), _serialize_evidence()

### Community 126 - "JenkinsPlatformPort"
Cohesion: 0.13
Nodes (4): BuildDetails, JenkinsPlatformPort, JobRunState, ViewScanResult

### Community 131 - "resolve_live_head_sha"
Cohesion: 0.20
Nodes (7): _effective_gitlab_context(), _effective_kargo_context(), extract_context_head_sha(), is_stale_verification_gitlab_mirror(), _is_vcs_backed_event(), resolve_live_head_sha(), verify_merge_guard()

### Community 132 - "ServiceNode.tsx"
Cohesion: 0.20
Nodes (11): HealthStatus, NodeType, AppNodeData, ARGOCD_HEALTH_COLORS, SYNC_ICONS, GENERIC_TAGS, HEALTH_COLORS, NODE_ICONS (+3 more)

### Community 133 - "observations_reporter.py"
Cohesion: 0.21
Nodes (7): _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), _sample_points(), _summarize()

### Community 135 - "get_brain"
Cohesion: 0.14
Nodes (8): can_override_domain(), can_rename_event(), _normalize_email(), get_brain(), enforce_casual_domain(), EnforceCasualRequest, PlanStepRequest, update_plan_step()

### Community 137 - "post"
Cohesion: 0.26
Nodes (7): _acquire_hh_poll_lock(), _busy_lock_response(), _get_headhunter_or_503(), headhunter_item_action(), _require_headhunter_operator(), reset_headhunter_breaker(), trigger_headhunter_poll()

### Community 138 - "analyzeTokens"
Cohesion: 0.19
Nodes (13): analyzeString(), analyzeTokens(), assignName(), base(), combineCategories(), configEnvGuard(), configFileWriteGuard(), hasSubseq() (+5 more)

### Community 139 - "EventDrillDown.tsx"
Cohesion: 0.22
Nodes (9): three, getEventPulses(), BrainCore(), CortexDevPage(), EventDrillDown(), FRICTION_COLORS, WHISPER_COLORS, PulseTimeline() (+1 more)

### Community 141 - "handlers_planning.py"
Cohesion: 0.24
Nodes (6): _auto_complete_step(), _canonical_role(), handle_get_plan_progress(), _is_failed_turn(), _is_orchestrator_turn(), _normalize_step_id()

### Community 142 - "evaluate_gates"
Cohesion: 0.15
Nodes (7): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), is_wait_for_user_admissible_after_response(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 143 - "IncidentAdapterPort"
Cohesion: 0.15
Nodes (3): IdleTimeoutPort, IncidentAdapterPort, StateWatcherPort

### Community 144 - "prefix_builder.py"
Cohesion: 0.27
Nodes (5): build_global_core_si(), canonical_wire_tools(), compute_prefix_hashes(), sha8_json(), sha8_text()

### Community 146 - "testSetup.ts"
Cohesion: 0.17
Nodes (5): @tailwindcss/vite, @testing-library/react, vite, @vitejs/plugin-react, vitest

### Community 151 - "event_to_markdown"
Cohesion: 0.27
Nodes (4): CIAnalysis, _esc(), _esc_join(), event_to_markdown()

### Community 156 - "gitGuard"
Cohesion: 0.29
Nodes (10): bareBranchProtected(), configWriteGuard(), externalGitCommand(), gitGuard(), gitQuery(), isProtected(), normRef(), pushGuard() (+2 more)

### Community 157 - "parseShell"
Cohesion: 0.33
Nodes (10): bodySubstitutions(), decodeAnsiC(), isArrayAssignPrefix(), isWordStart(), matchBacktick(), matchParen(), parseShell(), readHeredocStart() (+2 more)

### Community 158 - "generate_event_title"
Cohesion: 0.22
Nodes (3): generate_event_title(), get_adapter(), _get_semaphore()

### Community 163 - "entity_extractor.py"
Cohesion: 0.33
Nodes (5): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship

### Community 165 - "has_unevaluated_close_blocker"
Cohesion: 0.22
Nodes (5): has_unevaluated_close_blocker(), _pred_jarvis_response(), _pred_unevaluated_close(), is_jarvis_acknowledgment(), is_stabilization_wake()

### Community 167 - "flow.py"
Cohesion: 0.24
Nodes (4): get_event_flow(), delta(), get_flow_history(), get_flow_metrics()

### Community 168 - "PulseBatch"
Cohesion: 0.27
Nodes (9): ActiveEvent, EventSource, KGServiceEntity, CortexGraphProps, GraphLoaderProps, PulseTimelineProps, PulseBatch, WorkspaceTaskItemProps (+1 more)

### Community 169 - "CortexDevPage.tsx"
Cohesion: 0.36
Nodes (8): devQueryClient, MOCK_CORTEX_STATUS, MOCK_EVENT_ID, MOCK_NEURONS, MOCK_PULSE_BATCHES, MOCK_SHADOW, MOCK_THINKING, MOCK_WHISPERS

### Community 171 - "classifyTool"
Cohesion: 0.31
Nodes (9): apiTokens(), apiWriteNeedsGuard(), branchValues(), classifyTool(), hasOpaqueTarget(), httpGuard(), httpMethod(), isReadMethod() (+1 more)

### Community 175 - "build_gate_context"
Cohesion: 0.22
Nodes (4): build_gate_context(), conversation_has_decayed_turns(), _decay_payload_len(), decay_cutoff_index()

### Community 177 - "shifts.py"
Cohesion: 0.28
Nodes (3): get_current_shift(), get_shift_detail(), list_shifts()

### Community 182 - "LLMStreamInterChunkTimeoutError"
Cohesion: 0.25
Nodes (4): LLMStreamInterChunkTimeoutError, LLMStreamTimeoutError, LLMStreamTotalTimeoutError, LLMStreamTTFBTimeoutError

### Community 187 - "adf_to_markdown"
Cohesion: 0.57
Nodes (7): adf_to_markdown(), _apply_marks(), _children(), _render(), _render_list(), _render_list_item(), _render_table_like()

### Community 188 - "validate-mutations.sh"
Cohesion: 0.57
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

### Community 190 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 191 - "state.js"
Cohesion: 0.33
Nodes (4): { AGENT_ROLE }, _blackboardTurns, _inboundMessages, _teammateMessages

### Community 200 - "build_manifest_table"
Cohesion: 0.33
Nodes (3): build_manifest_table(), build_system_prompt(), extract_event_links()

### Community 205 - "classify"
Cohesion: 0.50
Nodes (4): classify(), main(), shellCategory(), shellNeedsGuard()

### Community 216 - "overrides"
Cohesion: 0.67
Nodes (3): overrides, @typescript-eslint/typescript-estree, minimatch

## Knowledge Gaps
- **13 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+8 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2656 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **117 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `os`, `main.py`, `brain.py`, `observations_reporter.py`, `ConversationTurn`, `get_brain`, `models.py`, `ScheduleRepository`, `Brain`, `KargoObserver`, `FastAPI`, `topology.py`, `nightwatcher_tools.py`, `generate_event_title`, `auth.py`, `EventDocument`, `EventEvidence`, `slack.py`, `journal.py`, `approval_decision.py`, `_is_event_closed_or_missing`, `shifts.py`, `DashboardWSAdapter`, `ConversationMessage`, `._update_event_vcs_context`, `NightwatcherObserver`, `get_blackboard`, `LiveAPIAdapter`, `observations_mgmt.py`, `._stage_pending_signal`, `.__init__`, `queue.py`, `._downsample_snapshots`, `jira.py`, `delete_notebook_note`, `get_archivist`, `.get_event`, `rebuild_deep_memory`, `Any`, `reports.py`, `ScheduleCreateRequest`, `ArchitectureEvent`, `HeadhunterJira`, `headhunter_pending_todos`, `observations.py`, `update_event_title`, `list_active_events`?**
  _High betweenness centrality (0.152) - this node is a cross-community bridge._
- **Are the 85 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 85 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.011071550504804175 - nodes in this community are weakly interconnected._
- **Why does `Brain` connect `Brain` to `BlackboardState`, `os`, `BrainLifecyclePort`, `main.py`, `brain.py`, `ConversationTurn`, `models.py`, `._run_agent_task`, `ReconcileScheduler`, `Archivist`, `._build_contents`, `._extract_context_flags`, `._process_with_llm`, `._resolve_llm_params`, `._execute_function_call`, `EventDocument`, `EventEvidence`, `slack.py`, `DashboardWSAdapter`, `StateWatcher`, `BrainSkillLoader`, `get_token_meter`, `.__init__`, `PulseBatch`, `.next_turn_number`, `IdleTimeoutManager`, `_build_event_state_tail_block`, `ReflexSearcher`, `JarvisPeerPort`?**
  _High betweenness centrality (0.058) - this node is a cross-community bridge._
- **Are the 20 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Should `os` be split into smaller, more focused modules?**
  _Cohesion score 0.03871786734370041 - nodes in this community are weakly interconnected._