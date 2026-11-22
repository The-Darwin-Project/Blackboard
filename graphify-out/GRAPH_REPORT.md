# Graph Report - Blackboard  (2026-11-22)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 5727 nodes · 12895 edges · 211 communities (122 shown, 89 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 980 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `880569fc`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BlackboardState
- queue.py
- client.ts
- os
- tool_gates.py
- Brain
- EventSidebar.tsx
- models.py
- WorkspaceInspector.tsx
- GitLabPlatform
- GitHubPlatform
- ._run_agent_task
- AgentRegistry
- EventRepository
- BrainSkillLoader
- http-handler.js
- ReconcileScheduler
- Headhunter
- main.py
- react
- App.tsx
- Archivist
- jenkins-mcp.js
- colors.ts
- JenkinsObserver
- EventDocument
- Aligner
- headhunter.py
- ._process_with_llm
- auth.py
- TurnBubble.tsx
- hooks/index.ts
- _BrainToolContext
- ToolContext
- merge-guard.js
- ConversationTurn
- BoolOutcome
- nightwatcher_tools.py
- EventEvidence
- OpsStateContext.tsx
- context_parts.py
- KnowledgeGraphStore
- cli-executor.js
- storage-recycler.js
- AgentClient
- asyncio
- ephemeral_provisioner.py
- time
- GeminiAdapter
- brain.py
- topology.py
- llm/__init__.py
- SlackChannel
- jenkins_observer.py
- reconcile.py
- TimeKeeperPage.tsx
- ws-client.js
- ._build_contents
- headhunter_github.py
- record_token_usage
- useCortexData.ts
- live_api_adapter.py
- formatter.py
- state/__init__.py
- ui/package.json
- StreamGrid.tsx
- EphemeralProvisioner
- vcs_approval.py
- VcsPlatformPort
- quota_tracker.py
- VectorStore
- types.py
- handlers_lookup.py
- CortexGraph.tsx
- llm_error_classifier.py
- server.js
- adf_to_markdown
- gemini_client.py
- TopologyRepository
- httpx
- JenkinsAdapter
- spawn_event_namer_task
- handlers_state.py
- ArgoCDObserver
- KargoObserver
- dependencies
- LiveAPIAdapter
- ._build_system_prompt
- EventDrillDown.tsx
- compilerOptions
- claude-guard.js
- DashboardWSAdapter
- HeadhunterCircuitBreaker
- AsyncGitHubClient
- FlowHistoryPage.tsx
- slack.py
- cli-setup.js
- StateWatcher
- OIDCKeyAdapter
- ScheduleCreateRequest
- jenkins.py
- ReflexSearcher
- .create_platform_event
- ._authorize_plan_decision
- ArchitectureEvent
- devDependencies
- FloatingWindow.tsx
- compilerOptions
- gemini-sidecar/package.json
- ServiceNode.tsx
- start_headhunter_task
- get_report
- GitHubAppAuth
- ArchitectureGraph.tsx
- CortexDevPage.tsx
- ObservationRepository
- ShiftsPage.tsx
- github_app.py
- catalog-skills.js
- EscalationRepository
- TokenMeter
- tool_router.py
- .list_observations
- MultiInstallationManager
- ._connect
- ScheduleRepository
- archivist.py
- analyzeTokens
- utils/__init__.py
- create_chat_event
- get_current_shift
- IdleTimeoutManager
- NeuronInfoPanel.tsx
- ._process_message
- jarvis_ack.py
- nightwatcher_prompt.py
- CortexLiveFeed.tsx
- testSetup.ts
- ._extract_context_flags
- get_quota_tracker
- is_defer_event_available
- GitLabTokenAuth
- cortex-constants.ts
- gitGuard
- parseShell
- _is_event_closed_or_missing
- ._tool_send_event_message
- entity_extractor.py
- HeadhunterJira
- knowledge_graph_api.py
- classifyTool
- .has_reeval_signal
- _get_canonical_or_alias
- get_all_journal
- useDeferCountdown.ts
- TimeKeeperObserver
- CortexRepository
- validate-mutations.sh
- llm_stats
- scripts
- state.js
- build_gate_context
- list_failed_stages
- extract_tables
- submit_feedback
- get_notebook
- TicketNode.tsx
- classify
- delete_observation
- require-results.sh
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
- GateDefinition

## God Nodes (most connected - your core abstractions)
1. `BlackboardState` - 316 edges
2. `Brain` - 168 edges
3. `ConversationTurn` - 136 edges
4. `ToolContext` - 103 edges
5. `GateContext` - 99 edges
6. `GitHubPlatform` - 87 edges
7. `EventDocument` - 87 edges
8. `react` - 85 edges
9. `EventRepository` - 82 edges
10. `lifespan()` - 66 edges

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

## Communities (211 total, 89 thin omitted)

### Community 1 - "queue.py"
Cohesion: 0.03
Nodes (56): can_approve_event(), can_override_domain(), can_rename_event(), _normalize_email(), resolve_approval_identity(), get_archivist(), get_event_document(), aligner_pending_items() (+48 more)

### Community 2 - "client.ts"
Cohesion: 0.03
Nodes (98): oidc-client-ts, @tanstack/react-query, ApiError, bulkDeleteObservations(), deleteObservation(), exportObservations(), ExtractedCorrection, ExtractedLesson (+90 more)

### Community 3 - "os"
Cohesion: 0.04
Nodes (25): can_append_message(), get_aligner(), get_architect(), get_argocd_observer(), get_blackboard(), get_brain(), get_developer(), get_kargo_observer() (+17 more)

### Community 4 - "tool_gates.py"
Cohesion: 0.04
Nodes (85): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+77 more)

### Community 6 - "EventSidebar.tsx"
Cohesion: 0.06
Nodes (80): getActiveEvents(), getAlignerPending(), getClosedEvents(), getEventDocument(), getHeadhunterPending(), getJenkinsPending(), getJiraMissions(), getWaitingApprovalEvents() (+72 more)

### Community 7 - "models.py"
Cohesion: 0.04
Nodes (31): AppNode, ChatRequest, ChatResponse, ConversationMessage, EventInput, EventMetrics, EventStatus, EventType (+23 more)

### Community 8 - "WorkspaceInspector.tsx"
Cohesion: 0.06
Nodes (71): updateEventTitle(), AgentRegistryEntry, CiContext, ConversationTurn, EventEvidence, TokenUsageDict, ChatInput(), CiContextCard() (+63 more)

### Community 9 - "GitLabPlatform"
Cohesion: 0.05
Nodes (6): _get_allowed_mention_authors(), GitLabPlatform, _reconcile_synthetic(), _check_one(), _valid_positive_int(), get_gitlab_auth()

### Community 10 - "GitHubPlatform"
Cohesion: 0.04
Nodes (5): GitHubPlatform, _add_fail(), _poll_one(), _one(), _poll_one()

### Community 11 - "._run_agent_task"
Cohesion: 0.05
Nodes (10): on_huddle(), on_progress(), on_huddle(), on_progress(), _has_non_user_turns(), _is_automated_nudge(), _is_participant_turn(), _sanitize_error_text() (+2 more)

### Community 12 - "AgentRegistry"
Cohesion: 0.05
Nodes (18): AgentConnection, AgentRegistry, agent_websocket_handler(), _heartbeat(), _build_prompt(), _check_security(), consume_wake_task(), _consume() (+10 more)

### Community 14 - "BrainSkillLoader"
Cohesion: 0.04
Nodes (7): _parse_positive_int_env(), BrainSkillLoader, _SkillCorpus, BrainIntrospectionPort, BrainLifecyclePort, BroadcastPort, JarvisPeerPort

### Community 15 - "http-handler.js"
Cohesion: 0.08
Nodes (62): is429Error(), registerMCPsAndHooks(), resolveCommand(), writeAgyMcpServer(), writeClaudeMcpServer(), parsePositiveInt(), buildArgoCDMcpConfig(), createAppJWT() (+54 more)

### Community 16 - "ReconcileScheduler"
Cohesion: 0.04
Nodes (7): FlowCollector, FairQueue, ReconcileScheduler, Trigger, QueueTrigger, ResyncTrigger, StalenessGuard

### Community 17 - "Headhunter"
Cohesion: 0.05
Nodes (6): Headhunter, _iref(), _process_issue(), _try_queue_issue(), VcsContext, _NoAliasSafeLoader

### Community 18 - "main.py"
Cohesion: 0.04
Nodes (26): set_incident_options(), set_oidc_adapter(), set_agents(), set_archivist(), set_argocd_observer(), set_blackboard(), set_brain(), set_kargo_observer() (+18 more)

### Community 19 - "react"
Cohesion: 0.07
Nodes (55): lucide-react, react, applyLessons(), correctMemory(), createKnowledge(), createLesson(), deleteKnowledge(), deleteLesson() (+47 more)

### Community 20 - "App.tsx"
Cohesion: 0.06
Nodes (47): react-dom, react-router-dom, dismissProposals(), EnhancementProposal, getHandoffReports(), getProposals(), getWSAuthFailureCallback(), HandoffReport (+39 more)

### Community 22 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 23 - "colors.ts"
Cohesion: 0.07
Nodes (36): getReport(), getReports(), ReportFull, ReportMeta, CompactCardStrip(), EventHistory(), TimeRange, ViewMode (+28 more)

### Community 24 - "JenkinsObserver"
Cohesion: 0.05
Nodes (5): JobResult, _flood_service_key(), JenkinsObserver, _outage_service_key(), _service_key()

### Community 27 - "headhunter.py"
Cohesion: 0.05
Nodes (13): _sanitize_lesson_text(), generate_event_title(), get_adapter(), _get_semaphore(), PlatformQueueItem, PlatformSnapshot, _redact_error_text(), _validate_plan_yaml() (+5 more)

### Community 29 - "auth.py"
Cohesion: 0.06
Nodes (18): _claims_to_user(), get_user_from_request(), get_user_from_slack(), get_user_from_websocket(), require_auth(), require_obs_admin(), UserContext, _validate_jwt() (+10 more)

### Community 30 - "TurnBubble.tsx"
Cohesion: 0.08
Nodes (40): @uiw/react-markdown-preview, approveEvent(), rejectEvent(), submitFeedback(), MessageStatus, MarkdownViewer(), MermaidBlock(), InlineMarkdownViewerProps (+32 more)

### Community 31 - "hooks/index.ts"
Cohesion: 0.07
Nodes (38): createChatEvent(), getEvents(), ArchitectureEvent, ArgoCDOperation, ActivityStream(), ChatInputProps, Draft, LastSubmission (+30 more)

### Community 33 - "ToolContext"
Cohesion: 0.08
Nodes (12): handle_message_agent(), handle_reply_to_agent(), handle_report_incident(), handle_select_agent(), _resolve_escalation_scope(), _sticky_work_style(), handle_defer_event(), handle_hold_watch() (+4 more)

### Community 34 - "merge-guard.js"
Cohesion: 0.04
Nodes (46): API_VALUED, ARGO_MUTATING, ARGO_READ_SUB, ARGO_READ_TOP, BODY_FLAG, BROWSER_READ, CTX, ENV_BUILTINS (+38 more)

### Community 35 - "ConversationTurn"
Cohesion: 0.11
Nodes (29): emit_tool_result(), handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_ask_release_ai(), handle_fetch_jira_issue(), handle_greenwave(), handle_notify_user_slack() (+21 more)

### Community 37 - "nightwatcher_tools.py"
Cohesion: 0.09
Nodes (22): ShiftIncident, ShiftInvestigation, extract_full_links(), build_extend_tool(), build_report_tool(), build_summary_tool(), execute_tool(), _fallback_platform() (+14 more)

### Community 38 - "EventEvidence"
Cohesion: 0.08
Nodes (19): _parse_ts_epoch(), _build_closed_block(), build_event_header(), _build_identity_block(), _build_journal_block(), _build_mermaid_block(), build_operational_briefing(), _build_related_block() (+11 more)

### Community 39 - "OpsStateContext.tsx"
Cohesion: 0.08
Nodes (36): closeEvent(), enforceCasualDomain(), getAgents(), getKargoStages(), ApprovalErrorKind, KargoStageStatus, AgentRegistryPanel(), formatConnectedSince() (+28 more)

### Community 40 - "context_parts.py"
Cohesion: 0.07
Nodes (19): _apply_sibling_signature(), build_function_response(), build_single_function_response(), compress_contents(), contents_have_pruned_or_decayed(), estimate_msg_tokens(), estimate_tokens(), extract_model_parts() (+11 more)

### Community 41 - "KnowledgeGraphStore"
Cohesion: 0.09
Nodes (9): _format_graph_context(), get_graph_context(), _parse_props(), _sanitize(), translate_to_lookups(), _acquire(), KnowledgeGraphStore, _sanitize() (+1 more)

### Community 42 - "cli-executor.js"
Cohesion: 0.09
Nodes (37): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, MAX_TASK_WALL_MS, MAX_TIMER_MS, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS, STORAGE_PRETASK_TIMEOUT_MS, resolveStorageRoot }, buildCLICommand(), buildTimeoutResult(), { checkAndRecycleStorage, pinTaskCwd, unpinTaskCwd }, CLAUDE_JSON_PATH, cp, createInactivityWatchdog(), executeCLI() (+29 more)

### Community 43 - "storage-recycler.js"
Cohesion: 0.08
Nodes (37): withTaskStorage(), MAX_TASK_WALL_MS, parseTimerMs(), resolveStorageRoot(), resolveTimeoutMs(), ROLE_TIMEOUTS, STORAGE_ACTIVITY_HEARTBEAT_MS, STORAGE_MAX_TIER3_DELETIONS (+29 more)

### Community 44 - "AgentClient"
Cohesion: 0.06
Nodes (4): Architect, AgentClient, Developer, SysAdmin

### Community 45 - "asyncio"
Cohesion: 0.07
Nodes (17): get_report_client(), _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), render_pdf(), _sample_points() (+9 more)

### Community 46 - "ephemeral_provisioner.py"
Cohesion: 0.07
Nodes (5): KubernetesSpawnHealthAdapter, _PodHealthState, SpawnHealthPort, SpawnPollResult, SpawnStatus

### Community 47 - "time"
Cohesion: 0.09
Nodes (20): _alert_wrapper_retrigger(), _do_retrigger(), handle_refresh_github_context(), _emit(), handle_refresh_gitlab_context(), handle_refresh_kargo_context(), _is_darwin_reentrant_caller(), _is_positive_int() (+12 more)

### Community 48 - "GeminiAdapter"
Cohesion: 0.10
Nodes (7): _attach_signature_to_parts(), _extract_part_signature(), GeminiAdapter, _is_empty_sig_carrier(), _part_has_fc(), _sanitize_candidate_parts(), strip_control_tokens()

### Community 49 - "brain.py"
Cohesion: 0.05
Nodes (16): _BatchContext, compute_dispatch_backpressure(), _compute_processed_up_to(), _contents_have_pruned_or_decayed(), _ensure_recall_tool_if_needed(), _init_tool_names(), _is_external_input_turn(), _is_seed_turn() (+8 more)

### Community 50 - "topology.py"
Cohesion: 0.07
Nodes (5): get_graph_data(), get_mermaid_diagram(), get_service_details(), get_topology(), list_services()

### Community 51 - "llm/__init__.py"
Cohesion: 0.09
Nodes (6): ClaudeAdapter, FunctionCall, LLMChunk, LLMPort, LLMResponse, TokenUsage

### Community 52 - "SlackChannel"
Cohesion: 0.08
Nodes (3): get_agent_notification_text(), get_turn_attachment_color(), SlackChannel

### Community 53 - "jenkins_observer.py"
Cohesion: 0.08
Nodes (12): _clamp_confidence(), _env_flag(), _parse_job_metadata(), _prepare_console_tail(), _redact_build_parameters(), _redact_match(), _redact_secrets_in_text(), _sanitize_analysis_text() (+4 more)

### Community 54 - "reconcile.py"
Cohesion: 0.10
Nodes (15): _enumerate_gates(), _GateInfo, generate_phase_tool_map(), _load_gate_registry(), _render_markdown(), _render_ooda_overlay(), _build_redis_client(), _fetch_commit_sha() (+7 more)

### Community 55 - "TimeKeeperPage.tsx"
Cohesion: 0.12
Nodes (24): createSchedule(), deleteSchedule(), getSchedules(), refineInstructions(), ScheduleCreatePayload, ScheduleItem, toggleSchedule(), updateSchedule() (+16 more)

### Community 56 - "ws-client.js"
Cohesion: 0.10
Nodes (26): clearIdleTimer(), {
  DEFAULT_WORK_DIR, AGENT_CLI, AGENT_MODEL, AGENT_ROLE,
  EVENT_ID, EPHEMERAL, IDLE_TIMEOUT_MS,
  CLI_429_MAX_RETRIES, CLI_429_INITIAL_DELAY_MS, CLI_429_BACKOFF_MULTIPLIER,
  resolveTimeoutMs, parsePositiveInt, MAX_TASK_WALL_MS, MAX_TIMER_MS,
}, { ensureEventDocument }, { executeCLIStreaming, prepareResultsDir, is429Error }, { filterSkillsByRole, filterSkillsByMode, swapActiveRules, restoreAllSkills }, fs, handleCancel(), handleTask() (+18 more)

### Community 57 - "._build_contents"
Cohesion: 0.06
Nodes (3): _close_unanswered_fc(), _incr_flow_counter_safely(), _QuotaShedState

### Community 58 - "headhunter_github.py"
Cohesion: 0.09
Nodes (10): _bot_login(), _csv_env(), _consider(), _is_slash_command_only(), _iso(), _mention_pattern(), _parse_ts(), _review_ignore_logins() (+2 more)

### Community 59 - "record_token_usage"
Cohesion: 0.10
Nodes (6): record_token_usage(), _append_user_turn(), _env_float(), _env_int(), NightwatcherObserver, _finalize_analysis_handover()

### Community 60 - "useCortexData.ts"
Cohesion: 0.14
Nodes (30): getCognitiveGraph(), getCortexActivity(), getEventReport(), getKGServiceDetail(), getKGServices(), getKGStats(), getKnowledgeById(), getMemory() (+22 more)

### Community 61 - "live_api_adapter.py"
Cohesion: 0.09
Nodes (4): PulseBatch, PulsePort, PulseObserver, PulseTracker

### Community 62 - "formatter.py"
Cohesion: 0.10
Nodes (14): build_access_denied_home_view(), build_home_tab_view(), _context_line(), create_feedback_block(), format_event_summary(), format_plan_block(), format_task_card(), format_tool_result_blocks() (+6 more)

### Community 63 - "state/__init__.py"
Cohesion: 0.09
Nodes (3): sanitize_redis_port(), get_redis(), RedisClient

### Community 64 - "ui/package.json"
Cohesion: 0.08
Nodes (29): autoprefixer, cronstrue, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, graphology-layout-forceatlas2 (+21 more)

### Community 65 - "StreamGrid.tsx"
Cohesion: 0.13
Nodes (25): Dashboard(), GridTile(), GridTileProps, TileType, InlineMarkdownViewer(), EmptyState(), LayoutMode, StreamGrid() (+17 more)

### Community 66 - "EphemeralProvisioner"
Cohesion: 0.09
Nodes (3): DispatchMetrics, EphemeralProvisioner, SpawnFailed

### Community 67 - "vcs_approval.py"
Cohesion: 0.11
Nodes (12): get_installation_manager(), normalize_gitlab_host(), resolve_ca_bundle(), _usable_ca_file(), ApprovalDriftResult, check_approval_sha_drift(), _is_vcs_backed_event(), parse_mr_url() (+4 more)

### Community 69 - "quota_tracker.py"
Cohesion: 0.09
Nodes (8): QuotaExhaustedError, QuotaTracker, RequestExceedsBurstError, Reservation, _stale_reservation_ttl_s(), _get_timeout_env_warned(), parse_timeout_env(), resolve_stream_timeouts()

### Community 70 - "VectorStore"
Cohesion: 0.09
Nodes (3): _decode_cursor(), _encode_cursor(), VectorStore

### Community 71 - "types.py"
Cohesion: 0.09
Nodes (14): derive_llm_priority(), _get_timeout_order_warned(), is_partial_control_token(), LLMStreamInterChunkTimeoutError, LLMStreamTimeoutError, LLMStreamTotalTimeoutError, LLMStreamTTFBTimeoutError, _patch_enum_fields() (+6 more)

### Community 72 - "handlers_lookup.py"
Cohesion: 0.12
Nodes (12): _safe_int(), _coerce_turn_int(), handle_recall_pruned_turns(), _parse_turn_int(), _sanitize_recalled(), _format_bounded_journal(), handle_consult_deep_memory(), handle_lookup_journal() (+4 more)

### Community 73 - "CortexGraph.tsx"
Cohesion: 0.13
Nodes (26): graphology, eventColor(), getExecutiveNeurons(), getStructuralEdges(), DEFAULT_TYPE_BUDGET, evictLru(), KNOWLEDGE_RING, KNOWLEDGE_RING_TYPES (+18 more)

### Community 74 - "llm_error_classifier.py"
Cohesion: 0.13
Nodes (9): _extract_status_code(), _has_non_retryable_cause(), _is_google_auth_transport_error(), is_rate_limit(), is_transient(), is_transient_llm_error_turn(), _iter_exception_chain(), _matches_mro() (+1 more)

### Community 75 - "server.js"
Cohesion: 0.09
Nodes (18): { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, ensureEventDocument(), fs, path, stageEventDocument(), fetchEventDocument(), fs, { handleRequest } (+10 more)

### Community 76 - "adf_to_markdown"
Cohesion: 0.12
Nodes (10): _adf_to_text(), _escape_jql_string(), JiraIncidentAdapter, adf_to_markdown(), _apply_marks(), _children(), _render(), _render_list() (+2 more)

### Community 77 - "gemini_client.py"
Cohesion: 0.09
Nodes (12): _append_user_turn(), _clone_part_with_sig(), _clone_part_with_text(), _coerce_part(), _decode_sig_bytes(), _extract_call_syntax(), _is_function_response_part(), _parse_drain_timeout() (+4 more)

### Community 79 - "httpx"
Cohesion: 0.11
Nodes (8): _get_jira_reporter(), handle_comment_jira_issue(), dex_proxy(), approve_mission(), dismiss_mission(), _jira_config(), reanalyze_mission(), retry_mission()

### Community 81 - "spawn_event_namer_task"
Cohesion: 0.17
Nodes (7): spawn_event_namer_task(), handle_app_home_opened(), handle_app_mention(), handle_create_event_modal(), handle_darwin_command(), on_dm_message(), fallback_title()

### Community 82 - "handlers_state.py"
Cohesion: 0.12
Nodes (9): _batch_is_terminal_for_flush(), handle_classify_event(), handle_request_user_approval(), can_transition_to_close(), handle_set_phase(), _resolve_domain(), resolve_event_domain(), _resolve_phase() (+1 more)

### Community 85 - "dependencies"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 87 - "._build_system_prompt"
Cohesion: 0.09
Nodes (3): _inject_evidence_paths(), _strip_tool_names(), _wrap_section()

### Community 88 - "EventDrillDown.tsx"
Cohesion: 0.18
Nodes (20): ActiveEvent, EventSource, KGServiceEntity, CortexGraphProps, GraphLoaderProps, CortexLiveFeedProps, EventDrillDownProps, FRICTION_COLORS (+12 more)

### Community 89 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 90 - "claude-guard.js"
Cohesion: 0.14
Nodes (18): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+10 more)

### Community 92 - "HeadhunterCircuitBreaker"
Cohesion: 0.11
Nodes (3): HeadhunterCircuitBreaker, PlatformBreakerStatus, _raise_if_systemic_failure()

### Community 93 - "AsyncGitHubClient"
Cohesion: 0.17
Nodes (5): AsyncGitHubClient, _handle_rate_limit(), _paginate_github_get(), parse_github_next_link(), _safe_parse_int()

### Community 94 - "FlowHistoryPage.tsx"
Cohesion: 0.23
Nodes (16): recharts, getFlowHistory(), FlowSnapshot, FlowHistoryPage(), RANGES, SparkCard(), SparkCardProps, formatTime() (+8 more)

### Community 95 - "slack.py"
Cohesion: 0.11
Nodes (3): table_block_to_code_block(), _mask_email(), SlackAccessGate

### Community 96 - "cli-setup.js"
Cohesion: 0.13
Nodes (18): { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync }, filterSkillsByMode() (+10 more)

### Community 97 - "StateWatcher"
Cohesion: 0.13
Nodes (4): PollFn, _QueueEntry, StateWatcher, _Subscription

### Community 100 - "jenkins.py"
Cohesion: 0.12
Nodes (6): _annotation_replace(), BuildDetails, JenkinsPlatformPort, JobRunState, _strip_pipeline_annotations(), ViewScanResult

### Community 103 - "._authorize_plan_decision"
Cohesion: 0.12
Nodes (5): _PlanDecision, handle_approve(), handle_approve_sha(), handle_home_create_event(), handle_reject()

### Community 104 - "ArchitectureEvent"
Cohesion: 0.13
Nodes (3): ArchitectureEvent, list_events(), MetricsRepository

### Community 105 - "devDependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 106 - "FloatingWindow.tsx"
Cohesion: 0.17
Nodes (16): AgentStreamCard(), AgentStreamCardProps, MessageCards(), CopyButtonProps, DEFAULT_POS, DEFAULT_SIZE, EMPTY_MESSAGES, FloatingWindow() (+8 more)

### Community 107 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 108 - "gemini-sidecar/package.json"
Cohesion: 0.11
Nodes (18): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+10 more)

### Community 109 - "ServiceNode.tsx"
Cohesion: 0.15
Nodes (13): @xyflow/react, HealthStatus, NodeType, AppNodeData, ARGOCD_HEALTH_COLORS, SYNC_ICONS, NamespaceGroupNodeData, GENERIC_TAGS (+5 more)

### Community 111 - "get_report"
Cohesion: 0.11
Nodes (6): get_report(), list_reports(), reports_spa_no_slash(), reports_spa_with_slash(), search_reports(), _serve_spa()

### Community 113 - "ArchitectureGraph.tsx"
Cohesion: 0.17
Nodes (16): @dagrejs/dagre, applyDagreLayout(), applyGridLayout(), applyLayout(), ArchitectureGraph(), ArchitectureGraphInner(), buildGraph(), computeIdHash() (+8 more)

### Community 114 - "CortexDevPage.tsx"
Cohesion: 0.16
Nodes (14): three, getEventPulses(), BrainCore(), CortexDevPage(), devQueryClient, EventDrillDown(), MOCK_CORTEX_STATUS, MOCK_EVENT_ID (+6 more)

### Community 116 - "ShiftsPage.tsx"
Cohesion: 0.23
Nodes (16): getCurrentShift(), getShiftDetail(), getShiftsList(), ShiftReportFull, ShiftReportSummary, FailedClusterBadge(), getISOWeek(), getWeekDates() (+8 more)

### Community 117 - "github_app.py"
Cohesion: 0.12
Nodes (4): _find_pem_file(), get_github_auth(), is_shared_installation_manager(), reset_installation_manager()

### Community 118 - "catalog-skills.js"
Cohesion: 0.16
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 121 - "tool_router.py"
Cohesion: 0.14
Nodes (3): IdleTimeoutPort, IncidentAdapterPort, StateWatcherPort

### Community 128 - "analyzeTokens"
Cohesion: 0.19
Nodes (13): analyzeString(), analyzeTokens(), assignName(), base(), combineCategories(), configEnvGuard(), configFileWriteGuard(), hasSubseq() (+5 more)

### Community 129 - "utils/__init__.py"
Cohesion: 0.19
Nodes (4): _resolve_maintainer_enum(), _resolve_slack_user(), maintainer_env_key(), resolve_maintainer_emails()

### Community 130 - "create_chat_event"
Cohesion: 0.17
Nodes (3): ChatEventRequest, ChatEventResponse, create_chat_event()

### Community 131 - "get_current_shift"
Cohesion: 0.15
Nodes (3): get_current_shift(), get_shift_detail(), list_shifts()

### Community 134 - "NeuronInfoPanel.tsx"
Cohesion: 0.24
Nodes (12): KGServiceDetail, asNumber(), asString(), asStringArray(), Badge(), describeNeuron(), Hdr(), NeuronInfoPanel() (+4 more)

### Community 138 - "jarvis_ack.py"
Cohesion: 0.20
Nodes (5): has_unevaluated_close_blocker(), _pred_jarvis_response(), _pred_unevaluated_close(), is_jarvis_acknowledgment(), is_stabilization_wake()

### Community 139 - "nightwatcher_prompt.py"
Cohesion: 0.20
Nodes (5): build_manifest_table(), build_report_iteration_prompt(), build_summary_prompt(), build_system_prompt(), extract_event_links()

### Community 140 - "CortexLiveFeed.tsx"
Cohesion: 0.24
Nodes (10): CortexHeartbeat(), CortexHeartbeatProps, ensureKeyframes(), CortexLiveFeed(), FILTER_PILLS, FilterKey, getStoredFilter(), MESSAGE_STYLES (+2 more)

### Community 141 - "testSetup.ts"
Cohesion: 0.18
Nodes (5): @tailwindcss/vite, @testing-library/react, vite, @vitejs/plugin-react, vitest

### Community 144 - "is_defer_event_available"
Cohesion: 0.18
Nodes (6): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 146 - "cortex-constants.ts"
Cohesion: 0.18
Nodes (10): AGENTS, DOMAINS, HEMISPHERE_X, NEURON_DESCRIPTIONS, PHASE_SKILL_FOLDERS, PHASE_TOOL_PRIORITY, PHASES, StructuralEdge (+2 more)

### Community 147 - "gitGuard"
Cohesion: 0.29
Nodes (10): bareBranchProtected(), configWriteGuard(), externalGitCommand(), gitGuard(), gitQuery(), isProtected(), normRef(), pushGuard() (+2 more)

### Community 148 - "parseShell"
Cohesion: 0.33
Nodes (10): bodySubstitutions(), decodeAnsiC(), isArrayAssignPrefix(), isWordStart(), matchBacktick(), matchParen(), parseShell(), readHeredocStart() (+2 more)

### Community 151 - "entity_extractor.py"
Cohesion: 0.33
Nodes (5): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship

### Community 153 - "knowledge_graph_api.py"
Cohesion: 0.31
Nodes (4): get_kg_store(), get_service_detail(), get_stats(), list_services()

### Community 154 - "classifyTool"
Cohesion: 0.31
Nodes (9): apiTokens(), apiWriteNeedsGuard(), branchValues(), classifyTool(), hasOpaqueTarget(), httpGuard(), httpMethod(), isReadMethod() (+1 more)

### Community 159 - "useDeferCountdown.ts"
Cohesion: 0.47
Nodes (7): DeferCountdownState, useDeferCountdown(), computeDeferProgress(), DeferTimeline, formatDeferRemaining(), inferDeferFromConversation(), resolveDeferTimeline()

### Community 165 - "validate-mutations.sh"
Cohesion: 0.57
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

### Community 168 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 169 - "state.js"
Cohesion: 0.33
Nodes (4): { AGENT_ROLE }, _blackboardTurns, _inboundMessages, _teammateMessages

### Community 175 - "build_gate_context"
Cohesion: 0.33
Nodes (3): build_gate_context(), conversation_has_decayed_turns(), _decay_payload_len()

### Community 181 - "extract_tables"
Cohesion: 0.40
Nodes (3): extract_tables(), _replace(), _md_table_to_block_kit()

### Community 185 - "TicketNode.tsx"
Cohesion: 0.40
Nodes (4): STATUS_COLORS, TICKET_COLORS, TicketNodeComponent(), TicketNodeData

### Community 186 - "classify"
Cohesion: 0.50
Nodes (4): classify(), main(), shellCategory(), shellNeedsGuard()

### Community 193 - "overrides"
Cohesion: 0.67
Nodes (3): overrides, @typescript-eslint/typescript-estree, minimatch

## Knowledge Gaps
- **13 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+8 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2521 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **89 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `queue.py`, `create_chat_event`, `os`, `get_current_shift`, `Brain`, `._validate_gitlab_ids`, `models.py`, `AgentRegistry`, `BrainSkillLoader`, `main.py`, `_is_event_closed_or_missing`, `HeadhunterJira`, `EventDocument`, `headhunter.py`, `auth.py`, `get_all_journal`, `ConversationTurn`, `._update_event_vcs_context`, `nightwatcher_tools.py`, `EventEvidence`, `asyncio`, `brain.py`, `topology.py`, `._get_ticket_nodes`, `._restage_pending_signal`, `jenkins_observer.py`, `submit_feedback`, `get_notebook`, `._count_pending`, `._stage_pending_signal`, `headhunter_github.py`, `delete_observation`, `.cleanup_stale_services`, `live_api_adapter.py`, `.drain_notes`, `.get_edge_metadata`, `report_tampering`, `state/__init__.py`, `TopologyRepository`, `httpx`, `LiveAPIAdapter`, `DashboardWSAdapter`, `slack.py`, `ScheduleCreateRequest`, `ArchitectureEvent`, `get_report`, `tool_router.py`, `.list_observations`, `ScheduleRepository`?**
  _High betweenness centrality (0.116) - this node is a cross-community bridge._
- **Are the 80 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 80 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.011663597298956415 - nodes in this community are weakly interconnected._
- **Why does `Brain` connect `Brain` to `BlackboardState`, `os`, `IdleTimeoutManager`, `models.py`, `._run_agent_task`, `AgentRegistry`, `._extract_context_flags`, `get_quota_tracker`, `ReconcileScheduler`, `BrainSkillLoader`, `main.py`, `EventDocument`, `._process_with_llm`, `ConversationTurn`, `EventEvidence`, `brain.py`, `._build_contents`, `live_api_adapter.py`, `._build_system_prompt`, `DashboardWSAdapter`, `slack.py`, `ReflexSearcher`, `archivist.py`?**
  _High betweenness centrality (0.068) - this node is a cross-community bridge._
- **Are the 20 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Should `queue.py` be split into smaller, more focused modules?**
  _Cohesion score 0.031512605042016806 - nodes in this community are weakly interconnected._