# Graph Report - Blackboard  (2026-11-25)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 6019 nodes · 13724 edges · 230 communities (118 shown, 112 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 1038 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `7d1076d0`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BlackboardState
- Brain
- os
- queue.py
- gemini_client.py
- client.ts
- models.py
- EventDocument
- Archivist
- EventSidebar.tsx
- nightwatcher_tools.py
- WorkspaceInspector.tsx
- App.tsx
- brain.py
- Headhunter
- tool_gates.py
- EventRepository
- GitHubPlatform
- SlackChannel
- http-handler.js
- react
- ._process_with_llm
- ReconcileScheduler
- TopologyRepository
- colors.ts
- jenkins-mcp.js
- AgentRegistry
- TurnBubble.tsx
- main.py
- BoolOutcome
- ToolContext
- Aligner
- agents/__init__.py
- handlers_integration.py
- _BrainToolContext
- KargoObserver
- merge-guard.js
- headhunter.py
- ScheduleCreateRequest
- cli-executor.js
- storage-recycler.js
- headhunter_github.py
- EventChatPanel.tsx
- ConversationTurn
- WebSocketContext.tsx
- CortexGraph.tsx
- observations_mgmt.py
- formatter.py
- create_adapter
- TimeKeeperPage.tsx
- jenkins_observer.py
- ws-client.js
- handlers_lookup.py
- slack.py
- NodeInspector.tsx
- UserContext
- ._github_poll_and_process
- KnowledgeGraphStore
- useCortexData.ts
- auth.py
- prompt_sanitize.py
- EventDrillDown.tsx
- state/__init__.py
- ui/package.json
- lifespan
- LiveAPIAdapter
- BrainSkillLoader
- llm_error_classifier.py
- server.js
- StateWatcher
- cognitive_graph.py
- PulseBatch
- context_parts.py
- JenkinsObserver
- ArgoCDObserver
- GitHubAppAuth
- dependencies
- JenkinsAdapter
- compilerOptions
- claude-guard.js
- FlowHistoryPage.tsx
- .create_platform_event
- ._api_url
- HeadhunterJira
- VcsWorkItem
- AsyncGitHubClient
- reconcile.py
- cli-setup.js
- event_to_markdown
- ReflexSearcher
- GitLabPlatform
- devDependencies
- compilerOptions
- gemini-sidecar/package.json
- entity_extractor.py
- ServiceNode.tsx
- EphemeralProvisioner
- ._get
- get_report
- resolve_live_head_sha
- GridTile.tsx
- ArchitectureGraph.tsx
- DashboardWSAdapter
- maintainers.py
- HeadhunterCircuitBreaker
- TokenMeter
- ObservationRepository
- ShiftsPage.tsx
- catalog-skills.js
- JenkinsPlatformPort
- JarvisPeerPort
- EscalationRepository
- JiraIncidentAdapter
- _valid_positive_int
- MultiInstallationManager
- generate_map.py
- OIDCKeyAdapter
- KubernetesSpawnHealthAdapter
- ._discover
- graph_recall.py
- redact_pii
- .list_observations
- ._connect
- BrainLifecyclePort
- compress_contents
- handlers_planning.py
- ._github_poll_review_feedback
- ._process_candidates
- ScheduleRepository
- analyzeTokens
- ._poll_and_stage
- ._extract_context_flags
- build_gate_context
- evaluate_gates
- IdleTimeoutManager
- NeuronInfoPanel.tsx
- ._process_message
- format_jira_for_llm
- has_unevaluated_close_blocker
- CortexLiveFeed.tsx
- testSetup.ts
- GitLabTokenAuth
- cortex-constants.ts
- gitGuard
- parseShell
- adf_to_markdown
- ._tool_send_event_message
- FlowCollector
- knowledge_graph_api.py
- BrainIntrospectionPort
- flow.py
- spawn_health.py
- classifyTool
- SpawnPollResult
- _is_event_closed_or_missing
- ._evaluate_health
- ._cleanup_stale_events
- TimeKeeperObserver
- HeadhunterItemActionRequest
- CortexRepository
- validate-mutations.sh
- ._detect_repetition_collapse
- .has_reeval_signal
- get_all_journal
- update_notebook_note
- scripts
- cortex/types.ts
- state.js
- _compute_processed_up_to
- DispatchMetrics
- dex_proxy
- ._wait_for_registration
- extract_jira_context
- submit_feedback
- get_notebook
- TicketNode.tsx
- classify
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

## Communities (230 total, 112 thin omitted)

### Community 0 - "BlackboardState"
Cohesion: 0.01
Nodes (3): delete_notebook_note(), delete_observation(), BlackboardState

### Community 1 - "Brain"
Cohesion: 0.02
Nodes (9): Brain, on_huddle(), on_progress(), on_huddle(), on_progress(), _is_automated_nudge(), _sanitize_error_text(), get_registry_and_bridge() (+1 more)

### Community 2 - "os"
Cohesion: 0.03
Nodes (16): _sanitize_lesson_text(), get_blackboard(), _load_name_mapping(), build_manifest_table(), extract_event_links(), get_current_shift(), get_shift_detail(), list_shifts() (+8 more)

### Community 3 - "queue.py"
Cohesion: 0.03
Nodes (72): get_token_meter(), can_override_domain(), can_rename_event(), get_archivist(), get_brain(), EventStatus, _acquire_hh_poll_lock(), aligner_pending_items() (+64 more)

### Community 4 - "gemini_client.py"
Cohesion: 0.03
Nodes (42): ClaudeAdapter, _append_user_turn(), _attach_signature_to_parts(), _clone_part_with_sig(), _clone_part_with_text(), _coerce_part(), _decode_sig_bytes(), _extract_call_syntax() (+34 more)

### Community 5 - "client.ts"
Cohesion: 0.03
Nodes (103): @tanstack/react-query, ApiError, bulkDeleteObservations(), deleteObservation(), exportObservations(), ExtractedCorrection, ExtractedLesson, ExtractionResult (+95 more)

### Community 6 - "models.py"
Cohesion: 0.03
Nodes (32): AppNode, ArchitectureEvent, ChatRequest, ChatResponse, ConversationMessage, EventInput, EventMetrics, EventType (+24 more)

### Community 7 - "EventDocument"
Cohesion: 0.03
Nodes (27): _is_close_phase_fc(), _clean_lines(), format_event_state_tail(), _add_fail(), _build_closed_block(), build_event_header(), _build_identity_block(), build_immutable_event_anchor() (+19 more)

### Community 8 - "Archivist"
Cohesion: 0.04
Nodes (4): Archivist, _decode_cursor(), _encode_cursor(), VectorStore

### Community 9 - "EventSidebar.tsx"
Cohesion: 0.05
Nodes (81): getJiraMissions(), getWaitingApprovalEvents(), HeadhunterTodo, postJiraAction(), CiContext, JenkinsPendingItem, JiraMission, ChatInput() (+73 more)

### Community 10 - "nightwatcher_tools.py"
Cohesion: 0.05
Nodes (33): record_token_usage(), PulseContext, ShiftIncident, ShiftInvestigation, ShiftReport, _append_user_turn(), _env_float(), _env_int() (+25 more)

### Community 11 - "WorkspaceInspector.tsx"
Cohesion: 0.05
Nodes (66): createChatEvent(), getAgents(), getKargoStages(), updateEventTitle(), AgentRegistryEntry, ApprovalErrorKind, EventEvidence, KargoStageStatus (+58 more)

### Community 12 - "App.tsx"
Cohesion: 0.05
Nodes (62): oidc-client-ts, react-router-dom, getConfig(), getFlowMetrics(), getReport(), getReports(), setOnUnauthorized(), setTokenGetter() (+54 more)

### Community 13 - "brain.py"
Cohesion: 0.05
Nodes (39): _batch_is_terminal_for_flush(), _build_active_overlay(), _build_event_state_tail_block(), _build_transient_overlays(), _build_turn0_anchor(), _call_anchor_get(), _call_anchor_set_nx(), _close_unanswered_fc() (+31 more)

### Community 14 - "Headhunter"
Cohesion: 0.05
Nodes (4): Headhunter, _process_issue(), VcsContext, VcsPlatformPort

### Community 15 - "tool_gates.py"
Cohesion: 0.05
Nodes (79): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+71 more)

### Community 17 - "GitHubPlatform"
Cohesion: 0.04
Nodes (3): GitHubPlatform, _poll_one(), _poll_one()

### Community 18 - "SlackChannel"
Cohesion: 0.05
Nodes (13): spawn_event_namer_task(), format_event_summary(), SlackChannel, handle_app_home_opened(), handle_app_mention(), handle_approve(), handle_approve_sha(), handle_create_event_modal() (+5 more)

### Community 19 - "http-handler.js"
Cohesion: 0.08
Nodes (62): is429Error(), registerMCPsAndHooks(), resolveCommand(), writeAgyMcpServer(), writeClaudeMcpServer(), parsePositiveInt(), buildArgoCDMcpConfig(), createAppJWT() (+54 more)

### Community 20 - "react"
Cohesion: 0.07
Nodes (58): lucide-react, react, applyLessons(), correctMemory(), createKnowledge(), createLesson(), deleteKnowledge(), deleteLesson() (+50 more)

### Community 21 - "._process_with_llm"
Cohesion: 0.04
Nodes (9): _BatchContext, _ensure_recall_tool_if_needed(), _QuotaShedState, _retry_backoff_delay(), build_global_core_si(), canonical_wire_tools(), compute_prefix_hashes(), sha8_json() (+1 more)

### Community 22 - "ReconcileScheduler"
Cohesion: 0.04
Nodes (6): FairQueue, ReconcileScheduler, Trigger, QueueTrigger, ResyncTrigger, StalenessGuard

### Community 23 - "TopologyRepository"
Cohesion: 0.04
Nodes (6): Service, get_mermaid_diagram(), get_service_details(), get_topology(), list_services(), TopologyRepository

### Community 24 - "colors.ts"
Cohesion: 0.07
Nodes (38): ActiveEvent, ReportFull, ReportMeta, DeferCountdownBar(), CompactCardStrip(), TimeRange, ViewMode, EventHistoryGrid() (+30 more)

### Community 25 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 26 - "AgentRegistry"
Cohesion: 0.06
Nodes (14): AgentConnection, AgentRegistry, agent_websocket_handler(), _heartbeat(), _build_prompt(), _check_security(), consume_wake_task(), _consume() (+6 more)

### Community 27 - "TurnBubble.tsx"
Cohesion: 0.07
Nodes (48): mermaid, @uiw/react-markdown-preview, approveEvent(), closeEvent(), enforceCasualDomain(), getEventReport(), rejectEvent(), submitFeedback() (+40 more)

### Community 28 - "main.py"
Cohesion: 0.04
Nodes (25): get_aligner(), get_architect(), get_argocd_observer(), get_developer(), get_kargo_observer(), get_report_client(), get_sysadmin(), set_agents() (+17 more)

### Community 30 - "ToolContext"
Cohesion: 0.08
Nodes (12): handle_message_agent(), handle_reply_to_agent(), handle_report_incident(), handle_select_agent(), _resolve_escalation_scope(), _sticky_work_style(), handle_defer_event(), handle_hold_watch() (+4 more)

### Community 32 - "agents/__init__.py"
Cohesion: 0.06
Nodes (7): Architect, AgentClient, Developer, safe_execution(), wrapper(), SecurityError, SysAdmin

### Community 33 - "handlers_integration.py"
Cohesion: 0.07
Nodes (24): _alert_wrapper_retrigger(), _do_retrigger(), _get_jira_reporter(), handle_refresh_github_context(), _emit(), handle_refresh_gitlab_context(), handle_refresh_kargo_context(), _is_darwin_reentrant_caller() (+16 more)

### Community 35 - "KargoObserver"
Cohesion: 0.09
Nodes (9): build_verification_dedup_key(), extract_latest_verification(), is_verification_stale(), _parse_ts(), project_stage_status(), resolve_stage_freight(), _s(), KargoObserver (+1 more)

### Community 36 - "merge-guard.js"
Cohesion: 0.04
Nodes (46): API_VALUED, ARGO_MUTATING, ARGO_READ_SUB, ARGO_READ_TOP, BODY_FLAG, BROWSER_READ, CTX, ENV_BUILTINS (+38 more)

### Community 37 - "headhunter.py"
Cohesion: 0.06
Nodes (8): HeadhunterOperationError, PlatformBreakerStatus, PlatformQueueItem, PlatformSnapshot, _NoAliasSafeLoader, on_headhunter_done(), start_headhunter_task(), _validate_plan_yaml()

### Community 38 - "ScheduleCreateRequest"
Cohesion: 0.05
Nodes (7): ScheduleCreateRequest, create_schedule(), delete_schedule(), get_schedule(), list_schedules(), toggle_schedule(), update_schedule()

### Community 39 - "cli-executor.js"
Cohesion: 0.09
Nodes (37): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, MAX_TASK_WALL_MS, MAX_TIMER_MS, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS, STORAGE_PRETASK_TIMEOUT_MS, resolveStorageRoot }, buildCLICommand(), buildTimeoutResult(), { checkAndRecycleStorage, pinTaskCwd, unpinTaskCwd }, CLAUDE_JSON_PATH, cp, createInactivityWatchdog(), executeCLI() (+29 more)

### Community 40 - "storage-recycler.js"
Cohesion: 0.08
Nodes (37): withTaskStorage(), MAX_TASK_WALL_MS, parseTimerMs(), resolveStorageRoot(), resolveTimeoutMs(), ROLE_TIMEOUTS, STORAGE_ACTIVITY_HEARTBEAT_MS, STORAGE_MAX_TIER3_DELETIONS (+29 more)

### Community 41 - "headhunter_github.py"
Cohesion: 0.06
Nodes (11): _bot_login(), _csv_env(), _consider(), _is_slash_command_only(), _iso(), _mention_pattern(), _parse_ts(), _review_ignore_logins() (+3 more)

### Community 42 - "EventChatPanel.tsx"
Cohesion: 0.10
Nodes (33): ConversationTurn, EventChatPanel(), EventChatPanelProps, TOKEN_SEGMENTS, TokenUsageMini(), MockConversationFeed(), MOCK_CLOSED_EVENTS, MOCK_EVENT_DOC (+25 more)

### Community 43 - "ConversationTurn"
Cohesion: 0.15
Nodes (25): emit_tool_result(), handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_ask_release_ai(), handle_comment_jira_issue(), handle_fetch_jira_issue(), handle_greenwave() (+17 more)

### Community 44 - "WebSocketContext.tsx"
Cohesion: 0.09
Nodes (33): dismissProposals(), EnhancementProposal, getHandoffReports(), getProposals(), getWSAuthFailureCallback(), HandoffReport, FilterMode, formatDate() (+25 more)

### Community 45 - "CortexGraph.tsx"
Cohesion: 0.10
Nodes (35): graphology, @react-sigma/core, @react-sigma/layout-forceatlas2, sigma, @sigma/node-square, KGServiceEntity, eventColor(), getStructuralEdges() (+27 more)

### Community 46 - "observations_mgmt.py"
Cohesion: 0.09
Nodes (16): _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), render_pdf(), _sample_points(), _summarize() (+8 more)

### Community 47 - "formatter.py"
Cohesion: 0.08
Nodes (17): build_access_denied_home_view(), build_home_tab_view(), _context_line(), create_feedback_block(), extract_tables(), _replace(), format_plan_block(), format_task_card() (+9 more)

### Community 48 - "create_adapter"
Cohesion: 0.06
Nodes (11): create_adapter(), get_quota_tracker(), _parse_tpm_limit(), QuotaExhaustedError, QuotaTracker, RequestExceedsBurstError, _stale_reservation_ttl_s(), llm_stats() (+3 more)

### Community 49 - "TimeKeeperPage.tsx"
Cohesion: 0.12
Nodes (24): createSchedule(), deleteSchedule(), getSchedules(), refineInstructions(), ScheduleCreatePayload, ScheduleItem, toggleSchedule(), updateSchedule() (+16 more)

### Community 50 - "jenkins_observer.py"
Cohesion: 0.08
Nodes (13): _annotation_replace(), _strip_pipeline_annotations(), _clamp_confidence(), _env_flag(), _parse_job_metadata(), _prepare_console_tail(), _redact_match(), _redact_secrets_in_text() (+5 more)

### Community 51 - "ws-client.js"
Cohesion: 0.10
Nodes (26): clearIdleTimer(), {
  DEFAULT_WORK_DIR, AGENT_CLI, AGENT_MODEL, AGENT_ROLE,
  EVENT_ID, EPHEMERAL, IDLE_TIMEOUT_MS,
  CLI_429_MAX_RETRIES, CLI_429_INITIAL_DELAY_MS, CLI_429_BACKOFF_MULTIPLIER,
  resolveTimeoutMs, parsePositiveInt, MAX_TASK_WALL_MS, MAX_TIMER_MS,
}, { ensureEventDocument }, { executeCLIStreaming, prepareResultsDir, is429Error }, { filterSkillsByRole, filterSkillsByMode, swapActiveRules, restoreAllSkills }, fs, handleCancel(), handleTask() (+18 more)

### Community 52 - "handlers_lookup.py"
Cohesion: 0.08
Nodes (10): _safe_int(), _format_bounded_journal(), handle_consult_deep_memory(), handle_google_web_search(), handle_lookup_journal(), _safe_seconds(), IdleTimeoutPort, IncidentAdapterPort (+2 more)

### Community 53 - "slack.py"
Cohesion: 0.07
Nodes (7): get_user_from_slack(), get_agent_notification_text(), get_turn_attachment_color(), table_block_to_code_block(), _PlanDecision, _mask_email(), SlackAccessGate

### Community 54 - "NodeInspector.tsx"
Cohesion: 0.11
Nodes (26): getClosedEvents(), getEvents(), ArchitectureEvent, ArgoCDOperation, ActivityStream(), EVENT_LABELS, EventItem(), EventItemProps (+18 more)

### Community 55 - "UserContext"
Cohesion: 0.13
Nodes (11): UserContext, approve_mission(), dismiss_mission(), _infer_phase(), _jira_config(), list_missions(), reanalyze_mission(), _require_jira_mutation_auth() (+3 more)

### Community 56 - "._github_poll_and_process"
Cohesion: 0.10
Nodes (6): _maybe_refresh_snapshot(), _on_gh_phase_b_created(), _iref(), _try_queue_issue(), _on_gl_phase_b_created(), redact_error_text()

### Community 57 - "KnowledgeGraphStore"
Cohesion: 0.14
Nodes (4): _acquire(), KnowledgeGraphStore, _sanitize(), _with_timeout()

### Community 58 - "useCortexData.ts"
Cohesion: 0.17
Nodes (27): getCognitiveGraph(), getCortexActivity(), getKGServiceDetail(), getKGServices(), getKGStats(), getKnowledgeById(), getMemory(), getRecentPulses() (+19 more)

### Community 59 - "auth.py"
Cohesion: 0.10
Nodes (10): can_append_message(), can_approve_event(), _claims_to_user(), get_user_from_request(), get_user_from_websocket(), _normalize_email(), require_auth(), require_obs_admin() (+2 more)

### Community 60 - "prompt_sanitize.py"
Cohesion: 0.10
Nodes (8): generate_event_title(), get_adapter(), _get_semaphore(), ChatEventRequest, ChatEventResponse, create_chat_event(), sanitize_prompt_text(), sanitize_title()

### Community 61 - "EventDrillDown.tsx"
Cohesion: 0.13
Nodes (23): three, getEventPulses(), BrainCore(), CortexDevPage(), devQueryClient, CortexLiveFeedProps, EventDrillDown(), EventDrillDownProps (+15 more)

### Community 62 - "state/__init__.py"
Cohesion: 0.11
Nodes (4): sanitize_redis_port(), close_redis(), get_redis(), RedisClient

### Community 63 - "ui/package.json"
Cohesion: 0.09
Nodes (25): autoprefixer, cronstrue, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, graphology-layout-forceatlas2 (+17 more)

### Community 64 - "lifespan"
Cohesion: 0.08
Nodes (5): _patch_enum_fields(), set_incident_options(), set_oidc_adapter(), lifespan(), close_installation_manager()

### Community 67 - "llm_error_classifier.py"
Cohesion: 0.13
Nodes (9): _extract_status_code(), _has_non_retryable_cause(), _is_google_auth_transport_error(), is_rate_limit(), is_transient(), is_transient_llm_error_turn(), _iter_exception_chain(), _matches_mro() (+1 more)

### Community 68 - "server.js"
Cohesion: 0.09
Nodes (18): { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, ensureEventDocument(), fs, path, stageEventDocument(), fetchEventDocument(), fs, { handleRequest } (+10 more)

### Community 69 - "StateWatcher"
Cohesion: 0.10
Nodes (3): _QueueEntry, StateWatcher, _Subscription

### Community 70 - "cognitive_graph.py"
Cohesion: 0.11
Nodes (11): get_pulse_tracker(), dismiss_proposals(), DismissRequest, get_all_shadow_interventions(), get_cognitive_graph(), get_cortex_activity(), get_cortex_status(), get_event_shadow_interventions() (+3 more)

### Community 71 - "PulseBatch"
Cohesion: 0.10
Nodes (4): PulseBatch, PulsePort, PulseObserver, PulseTracker

### Community 72 - "context_parts.py"
Cohesion: 0.14
Nodes (11): _apply_sibling_signature(), build_function_response(), build_single_function_response(), extract_model_parts(), format_evidence_decay_reference(), _get_part_sig(), _is_empty_carrier_dict(), normalize_response_parts() (+3 more)

### Community 75 - "GitHubAppAuth"
Cohesion: 0.11
Nodes (3): _find_pem_file(), get_github_auth(), GitHubAppAuth

### Community 76 - "dependencies"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 78 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 79 - "claude-guard.js"
Cohesion: 0.14
Nodes (18): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+10 more)

### Community 80 - "FlowHistoryPage.tsx"
Cohesion: 0.21
Nodes (17): recharts, getFlowHistory(), FlowSnapshot, FlowHistoryPage(), RANGES, SparkCard(), SparkCardProps, formatTime() (+9 more)

### Community 85 - "AsyncGitHubClient"
Cohesion: 0.17
Nodes (5): AsyncGitHubClient, _handle_rate_limit(), _paginate_github_get(), parse_github_next_link(), _safe_parse_int()

### Community 86 - "reconcile.py"
Cohesion: 0.18
Nodes (9): _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers(), main(), _parse_frontmatter() (+1 more)

### Community 87 - "cli-setup.js"
Cohesion: 0.13
Nodes (18): { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync }, filterSkillsByMode() (+10 more)

### Community 88 - "event_to_markdown"
Cohesion: 0.13
Nodes (5): get_event_document(), list_events(), _esc(), _esc_join(), event_to_markdown()

### Community 91 - "devDependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 92 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 93 - "gemini-sidecar/package.json"
Cohesion: 0.11
Nodes (18): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+10 more)

### Community 94 - "entity_extractor.py"
Cohesion: 0.15
Nodes (7): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship, KargoStageSnapshot, list_failed_stages()

### Community 95 - "ServiceNode.tsx"
Cohesion: 0.15
Nodes (13): @xyflow/react, HealthStatus, NodeType, AppNodeData, ARGOCD_HEALTH_COLORS, SYNC_ICONS, NamespaceGroupNodeData, GENERIC_TAGS (+5 more)

### Community 99 - "get_report"
Cohesion: 0.11
Nodes (6): get_report(), list_reports(), reports_spa_no_slash(), reports_spa_with_slash(), search_reports(), _serve_spa()

### Community 100 - "resolve_live_head_sha"
Cohesion: 0.15
Nodes (9): ApprovalDriftResult, check_approval_sha_drift(), _effective_gitlab_context(), _effective_kargo_context(), extract_context_head_sha(), is_stale_verification_gitlab_mirror(), _is_vcs_backed_event(), resolve_live_head_sha() (+1 more)

### Community 101 - "GridTile.tsx"
Cohesion: 0.18
Nodes (16): AgentStreamCard(), AgentStreamCardProps, MessageCards(), GridTile(), GridTileProps, TileType, InlineMarkdownViewer(), DEFAULT_POS (+8 more)

### Community 102 - "ArchitectureGraph.tsx"
Cohesion: 0.17
Nodes (16): @dagrejs/dagre, applyDagreLayout(), applyGridLayout(), applyLayout(), ArchitectureGraph(), ArchitectureGraphInner(), buildGraph(), computeIdHash() (+8 more)

### Community 104 - "maintainers.py"
Cohesion: 0.17
Nodes (8): _resolve_maintainer_enum(), _dedupe(), _extract_evidence_maintainer_emails(), is_slack_recipient_allowed(), maintainer_env_key(), _resolve_evidence_env_maintainer_emails(), resolve_maintainer_emails(), _resolve_static_env_emails()

### Community 109 - "ShiftsPage.tsx"
Cohesion: 0.23
Nodes (16): getCurrentShift(), getShiftDetail(), getShiftsList(), ShiftReportFull, ShiftReportSummary, FailedClusterBadge(), getISOWeek(), getWeekDates() (+8 more)

### Community 110 - "catalog-skills.js"
Cohesion: 0.16
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 111 - "JenkinsPlatformPort"
Cohesion: 0.12
Nodes (4): BuildDetails, JenkinsPlatformPort, JobRunState, ViewScanResult

### Community 117 - "generate_map.py"
Cohesion: 0.19
Nodes (6): _enumerate_gates(), _GateInfo, generate_phase_tool_map(), _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 121 - "graph_recall.py"
Cohesion: 0.19
Nodes (5): _format_graph_context(), get_graph_context(), _parse_props(), _sanitize(), translate_to_lookups()

### Community 122 - "redact_pii"
Cohesion: 0.20
Nodes (6): _coerce_turn_int(), handle_recall_pruned_turns(), _parse_turn_int(), _sanitize_recalled(), _redact_pem_private_keys(), redact_pii()

### Community 127 - "compress_contents"
Cohesion: 0.18
Nodes (7): compress_contents(), _compress_single_msg_parts(), estimate_msg_tokens(), estimate_tokens(), format_prune_notice(), _is_event_state_msg(), prune_notice_count()

### Community 128 - "handlers_planning.py"
Cohesion: 0.23
Nodes (7): _auto_complete_step(), _canonical_role(), handle_create_plan(), handle_get_plan_progress(), _is_failed_turn(), _is_orchestrator_turn(), _normalize_step_id()

### Community 131 - "._process_candidates"
Cohesion: 0.15
Nodes (3): _flood_service_key(), _outage_service_key(), _service_key()

### Community 133 - "analyzeTokens"
Cohesion: 0.19
Nodes (13): analyzeString(), analyzeTokens(), assignName(), base(), combineCategories(), configEnvGuard(), configFileWriteGuard(), hasSubseq() (+5 more)

### Community 135 - "._extract_context_flags"
Cohesion: 0.15
Nodes (3): compute_dispatch_backpressure(), ContextFlags, _safe_int_env()

### Community 136 - "build_gate_context"
Cohesion: 0.17
Nodes (5): build_gate_context(), conversation_has_decayed_turns(), _decay_payload_len(), decay_cutoff_index(), get_decay_epoch_size()

### Community 137 - "evaluate_gates"
Cohesion: 0.15
Nodes (7): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), is_wait_for_user_admissible_after_response(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 139 - "NeuronInfoPanel.tsx"
Cohesion: 0.24
Nodes (12): KGServiceDetail, asNumber(), asString(), asStringArray(), Badge(), describeNeuron(), Hdr(), NeuronInfoPanel() (+4 more)

### Community 145 - "has_unevaluated_close_blocker"
Cohesion: 0.20
Nodes (5): has_unevaluated_close_blocker(), _pred_jarvis_response(), _pred_unevaluated_close(), is_jarvis_acknowledgment(), is_stabilization_wake()

### Community 146 - "CortexLiveFeed.tsx"
Cohesion: 0.24
Nodes (10): CortexHeartbeat(), CortexHeartbeatProps, ensureKeyframes(), CortexLiveFeed(), FILTER_PILLS, FilterKey, getStoredFilter(), MESSAGE_STYLES (+2 more)

### Community 147 - "testSetup.ts"
Cohesion: 0.18
Nodes (5): @tailwindcss/vite, @testing-library/react, vite, @vitejs/plugin-react, vitest

### Community 149 - "cortex-constants.ts"
Cohesion: 0.18
Nodes (10): AGENTS, DOMAINS, HEMISPHERE_X, NEURON_DESCRIPTIONS, PHASE_SKILL_FOLDERS, PHASE_TOOL_PRIORITY, PHASES, StructuralEdge (+2 more)

### Community 150 - "gitGuard"
Cohesion: 0.29
Nodes (10): bareBranchProtected(), configWriteGuard(), externalGitCommand(), gitGuard(), gitQuery(), isProtected(), normRef(), pushGuard() (+2 more)

### Community 151 - "parseShell"
Cohesion: 0.33
Nodes (10): bodySubstitutions(), decodeAnsiC(), isArrayAssignPrefix(), isWordStart(), matchBacktick(), matchParen(), parseShell(), readHeredocStart() (+2 more)

### Community 152 - "adf_to_markdown"
Cohesion: 0.40
Nodes (8): _adf_to_text(), adf_to_markdown(), _apply_marks(), _children(), _render(), _render_list(), _render_list_item(), _render_table_like()

### Community 156 - "knowledge_graph_api.py"
Cohesion: 0.31
Nodes (4): get_kg_store(), get_service_detail(), get_stats(), list_services()

### Community 158 - "flow.py"
Cohesion: 0.24
Nodes (4): get_event_flow(), delta(), get_flow_history(), get_flow_metrics()

### Community 160 - "classifyTool"
Cohesion: 0.31
Nodes (9): apiTokens(), apiWriteNeedsGuard(), branchValues(), classifyTool(), hasOpaqueTarget(), httpGuard(), httpMethod(), isReadMethod() (+1 more)

### Community 171 - "validate-mutations.sh"
Cohesion: 0.57
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

### Community 177 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 178 - "cortex/types.ts"
Cohesion: 0.29
Nodes (6): EventSource, CognitiveGraphResponse, CortexHeartbeatMessage, FrictionIndicator, FrictionPattern, NeuronVisual

### Community 179 - "state.js"
Cohesion: 0.33
Nodes (4): { AGENT_ROLE }, _blackboardTurns, _inboundMessages, _teammateMessages

### Community 181 - "_compute_processed_up_to"
Cohesion: 0.33
Nodes (3): _compute_processed_up_to(), _is_participant_turn(), _is_steering_turn()

### Community 189 - "TicketNode.tsx"
Cohesion: 0.40
Nodes (4): STATUS_COLORS, TICKET_COLORS, TicketNodeComponent(), TicketNodeData

### Community 190 - "classify"
Cohesion: 0.50
Nodes (4): classify(), main(), shellCategory(), shellNeedsGuard()

### Community 200 - "overrides"
Cohesion: 0.67
Nodes (3): overrides, @typescript-eslint/typescript-estree, minimatch

## Knowledge Gaps
- **13 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+8 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2638 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **112 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `Brain`, `os`, `queue.py`, `ScheduleRepository`, `models.py`, `EventDocument`, `nightwatcher_tools.py`, `brain.py`, `TopologyRepository`, `AgentRegistry`, `main.py`, `_is_event_closed_or_missing`, `KargoObserver`, `headhunter.py`, `ScheduleCreateRequest`, `headhunter_github.py`, `._update_event_vcs_context`, `ConversationTurn`, `observations_mgmt.py`, `get_all_journal`, `update_notebook_note`, `jenkins_observer.py`, `handlers_lookup.py`, `slack.py`, `UserContext`, `auth.py`, `prompt_sanitize.py`, `submit_feedback`, `get_notebook`, `state/__init__.py`, `lifespan`, `LiveAPIAdapter`, `BrainSkillLoader`, `report_tampering`, `HeadhunterJira`, `event_to_markdown`, `get_report`, `DashboardWSAdapter`, `.list_observations`?**
  _High betweenness centrality (0.102) - this node is a cross-community bridge._
- **Are the 81 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 81 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.009749670619235836 - nodes in this community are weakly interconnected._
- **Why does `Brain` connect `Brain` to `BlackboardState`, `queue.py`, `models.py`, `EventDocument`, `._extract_context_flags`, `IdleTimeoutManager`, `brain.py`, `._process_with_llm`, `ReconcileScheduler`, `._resolve_llm_params`, `FlowCollector`, `main.py`, `agents/__init__.py`, `._cleanup_stale_events`, `ConversationTurn`, `._detect_repetition_collapse`, `._escalation_blocked`, `slack.py`, `auth.py`, `lifespan`, `BrainSkillLoader`, `.append_and_broadcast`, `._github_pr_differs`, `StateWatcher`, `PulseBatch`, `._determine_thinking_params_legacy`, `.get_incident_adapter`, `._get_jira_reporter`, `._is_event_deferred`, `.last_processed_time`, `ReflexSearcher`, `DashboardWSAdapter`, `maintainers.py`, `JarvisPeerPort`, `BrainLifecyclePort`?**
  _High betweenness centrality (0.081) - this node is a cross-community bridge._
- **Are the 20 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Should `Brain` be split into smaller, more focused modules?**
  _Cohesion score 0.02498896247240618 - nodes in this community are weakly interconnected._