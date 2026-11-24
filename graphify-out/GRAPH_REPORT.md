# Graph Report - Blackboard  (2026-11-23)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 5884 nodes · 13305 edges · 242 communities (120 shown, 122 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 1009 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `125ba7d4`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BlackboardState
- ConversationTurn
- client.ts
- models.py
- queue.py
- GitLabPlatform
- os
- brain.py
- App.tsx
- ._run_agent_task
- Brain
- Headhunter
- tool_gates.py
- EventRepository
- EventSidebar.tsx
- WorkspaceInspector.tsx
- colors.ts
- main.py
- http-handler.js
- Archivist
- jenkins-mcp.js
- react
- VcsPlatformPort
- nightwatcher_tools.py
- TurnBubble.tsx
- Service
- headhunter_github.py
- BrainSkillLoader
- EventDocument
- _BrainToolContext
- auth.py
- ._process_with_llm
- merge-guard.js
- GeminiAdapter
- cli-executor.js
- storage-recycler.js
- slack.py
- agents/__init__.py
- KnowledgeGraphStore
- llm/__init__.py
- OpsStateContext.tsx
- handlers_integration.py
- headhunter_gitlab.py
- hooks/index.ts
- headhunter.py
- httpx
- get_brain
- TimeKeeperPage.tsx
- Aligner
- SlackChannel
- ws-client.js
- observations_reporter.py
- types.py
- DashboardWSAdapter
- event_to_markdown
- dispatch.py
- ui/package.json
- NightwatcherObserver
- useOpsControl
- useCortexData.ts
- .list_observations
- VectorStore
- LiveAPIAdapter
- AgentRegistry
- BoolOutcome
- PlatformBreakerStatus
- llm_error_classifier.py
- server.js
- CortexGraph.tsx
- spawn_event_namer_task
- ._poll_issues
- cognitive_graph.py
- EventChatPanel.tsx
- gemini_client.py
- lifespan
- JenkinsAdapter
- PulseBatch
- ArgoCDObserver
- NeuronInfoPanel.tsx
- BrainIntrospectionPort
- GitHubPlatform
- JenkinsObserver
- quota_tracker.py
- KargoObserver
- create_schedule
- TopologyRepository
- dependencies
- create_adapter
- ._poll_pr_feedback
- GitHubAppAuth
- cortex/types.ts
- compilerOptions
- reconcile.py
- claude-guard.js
- ._build_contents
- AsyncGitHubClient
- ArchitectureGraph.tsx
- FlowHistoryPage.tsx
- ._feedback_reject_reason
- cli-setup.js
- StateWatcher
- ReflexSearcher
- HeadhunterJira
- ArchitectureEvent
- FairQueue
- devDependencies
- compilerOptions
- gemini-sidecar/package.json
- EphemeralProvisioner
- get_report
- JiraIncidentAdapter
- ObservationRepository
- ShiftsPage.tsx
- catalog-skills.js
- JarvisPeerPort
- EscalationRepository
- feedback.py
- TokenMeter
- JenkinsPlatformPort
- OIDCKeyAdapter
- KubernetesSpawnHealthAdapter
- MultiInstallationManager
- ServiceNode.tsx
- ._connect
- .poll_review_feedback_all_installations
- ._process_candidates
- ScheduleRepository
- analyzeTokens
- generate_map.py
- EventDrillDown.tsx
- ._poll_and_stage
- FilterRule
- ._extract_context_flags
- handlers_planning.py
- ._fetch_checks_and_legacy_status
- IncidentAdapterPort
- IdleTimeoutManager
- ReconcileScheduler
- generate_event_title
- ._process_message
- CortexLiveFeed.tsx
- testSetup.ts
- .start_event_loop
- ._latest_bot_comment
- is_defer_event_available
- ._authorize_plan_decision
- Any
- ScheduleCreateRequest
- SlackAccessGate
- GitLabTokenAuth
- gitGuard
- parseShell
- ._post_agent_recall
- FlowCollector
- entity_extractor.py
- ._triage_and_build_evidence
- has_unevaluated_close_blocker
- knowledge_graph_api.py
- HeadhunterItemActionRequest
- PulseBatch
- spawn_health.py
- SecurityError
- classifyTool
- SpawnPollResult
- _get_canonical_or_alias
- get_quota_tracker
- Trigger
- useDeferCountdown.ts
- _is_event_closed_or_missing
- ._evaluate_health
- ConversationMessage
- TimeKeeperObserver
- CortexRepository
- adf_to_markdown
- validate-mutations.sh
- update_schedule
- ._detect_repetition_collapse
- scripts
- state.js
- DispatchMetrics
- build_gate_context
- rename_observation
- PollFn
- ._wait_for_registration
- extract_tables
- agent_ws_endpoint
- QueueTrigger
- classify
- format_event_summary
- list_incidents
- require-results.sh
- get_intermediate_tools
- report_tampering
- get_event_flow
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
1. `BlackboardState` - 322 edges
2. `Brain` - 168 edges
3. `ConversationTurn` - 136 edges
4. `ToolContext` - 103 edges
5. `GateContext` - 99 edges
6. `GitHubPlatform` - 99 edges
7. `Headhunter` - 89 edges
8. `EventRepository` - 87 edges
9. `EventDocument` - 87 edges
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

## Communities (242 total, 122 thin omitted)

### Community 1 - "ConversationTurn"
Cohesion: 0.05
Nodes (57): _batch_is_terminal_for_flush(), _is_close_phase_fc(), emit_tool_result(), _safe_int(), _coerce_turn_int(), handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes() (+49 more)

### Community 2 - "client.ts"
Cohesion: 0.03
Nodes (115): @tanstack/react-query, ApiError, bulkDeleteObservations(), createChatEvent(), deleteNote(), deleteObservation(), exportObservations(), ExtractedCorrection (+107 more)

### Community 3 - "models.py"
Cohesion: 0.03
Nodes (32): get_blackboard(), AppNode, ChatRequest, ChatResponse, EventEvidence, EventInput, EventMetrics, EventStatus (+24 more)

### Community 4 - "queue.py"
Cohesion: 0.03
Nodes (54): get_token_meter(), get_archivist(), aligner_pending_items(), apply_lessons(), ApproveRequest, close_event_by_user(), CloseRequest, correct_memory() (+46 more)

### Community 5 - "GitLabPlatform"
Cohesion: 0.05
Nodes (6): _get_allowed_mention_authors(), GitLabPlatform, _reconcile_synthetic(), _check_one(), _valid_positive_int(), get_gitlab_auth()

### Community 6 - "os"
Cohesion: 0.05
Nodes (12): _annotation_replace(), _strip_pipeline_annotations(), _heartbeat(), _parse_job_metadata(), _prepare_console_tail(), _redact_match(), _redact_secrets_in_text(), _sanitize_console_tail() (+4 more)

### Community 7 - "brain.py"
Cohesion: 0.04
Nodes (34): _sanitize_lesson_text(), _close_unanswered_fc(), _compute_processed_up_to(), _contents_have_pruned_or_decayed(), _has_non_user_turns(), _is_external_input_turn(), _is_seed_turn(), _is_steering_turn() (+26 more)

### Community 8 - "App.tsx"
Cohesion: 0.05
Nodes (66): oidc-client-ts, react-dom, react-router-dom, dismissProposals(), EnhancementProposal, getConfig(), getEventDocument(), getHandoffReports() (+58 more)

### Community 9 - "._run_agent_task"
Cohesion: 0.04
Nodes (10): on_huddle(), on_progress(), on_huddle(), on_progress(), _is_automated_nudge(), _is_participant_turn(), _sanitize_error_text(), _sanitize_override_reason() (+2 more)

### Community 11 - "Headhunter"
Cohesion: 0.05
Nodes (9): Headhunter, _maybe_refresh_snapshot(), _on_gh_phase_b_created(), _iref(), _process_issue(), _try_queue_issue(), _on_gl_phase_b_created(), redact_error_text() (+1 more)

### Community 12 - "tool_gates.py"
Cohesion: 0.05
Nodes (79): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+71 more)

### Community 14 - "EventSidebar.tsx"
Cohesion: 0.07
Nodes (67): getJiraMissions(), HeadhunterTodo, postJiraAction(), ChatInput(), ChatInputProps, Draft, LastSubmission, ContextMenu() (+59 more)

### Community 15 - "WorkspaceInspector.tsx"
Cohesion: 0.06
Nodes (61): updateEventTitle(), AgentRegistryEntry, ConversationTurn, AgentStreamCard(), AgentStreamCardProps, MessageCards(), AgentGroups, BORDER_COLOR (+53 more)

### Community 16 - "colors.ts"
Cohesion: 0.06
Nodes (47): getReport(), getReports(), ReportFull, ReportMeta, DeferCountdownBar(), CompactCardStrip(), EventHistory(), TimeRange (+39 more)

### Community 17 - "main.py"
Cohesion: 0.04
Nodes (28): get_aligner(), get_architect(), get_argocd_observer(), get_developer(), get_kargo_observer(), get_report_client(), get_sysadmin(), set_agents() (+20 more)

### Community 18 - "http-handler.js"
Cohesion: 0.08
Nodes (62): is429Error(), registerMCPsAndHooks(), resolveCommand(), writeAgyMcpServer(), writeClaudeMcpServer(), parsePositiveInt(), buildArgoCDMcpConfig(), createAppJWT() (+54 more)

### Community 20 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 21 - "react"
Cohesion: 0.08
Nodes (51): lucide-react, react, applyLessons(), correctMemory(), createKnowledge(), createLesson(), deleteKnowledge(), deleteLesson() (+43 more)

### Community 22 - "VcsPlatformPort"
Cohesion: 0.05
Nodes (4): HeadhunterOperationError, PlatformSnapshot, VcsWorkItem, VcsPlatformPort

### Community 23 - "nightwatcher_tools.py"
Cohesion: 0.07
Nodes (25): PulseContext, ShiftIncident, ShiftInvestigation, build_report_iteration_prompt(), build_summary_prompt(), extract_full_links(), build_extend_tool(), build_report_tool() (+17 more)

### Community 24 - "TurnBubble.tsx"
Cohesion: 0.08
Nodes (44): @uiw/react-markdown-preview, approveEvent(), closeEvent(), enforceCasualDomain(), getEventReport(), rejectEvent(), submitFeedback(), ConversationFeed() (+36 more)

### Community 25 - "Service"
Cohesion: 0.05
Nodes (8): Service, get_event_document(), get_graph_data(), get_mermaid_diagram(), get_service_details(), get_topology(), list_services(), calculate_health_from_argocd()

### Community 26 - "headhunter_github.py"
Cohesion: 0.06
Nodes (18): _iso(), _parse_ts(), build_manifest_table(), extract_event_links(), get_installation_manager(), is_shared_installation_manager(), reset_installation_manager(), normalize_gitlab_host() (+10 more)

### Community 27 - "BrainSkillLoader"
Cohesion: 0.05
Nodes (5): _inject_evidence_paths(), _parse_positive_int_env(), BrainSkillLoader, _SkillCorpus, _wrap_section()

### Community 30 - "auth.py"
Cohesion: 0.06
Nodes (16): can_append_message(), can_approve_event(), can_override_domain(), can_rename_event(), _claims_to_user(), get_user_from_slack(), get_user_from_websocket(), _normalize_email() (+8 more)

### Community 31 - "._process_with_llm"
Cohesion: 0.05
Nodes (4): _BatchContext, _ensure_recall_tool_if_needed(), _QuotaShedState, _retry_backoff_delay()

### Community 32 - "merge-guard.js"
Cohesion: 0.04
Nodes (46): API_VALUED, ARGO_MUTATING, ARGO_READ_SUB, ARGO_READ_TOP, BODY_FLAG, BROWSER_READ, CTX, ENV_BUILTINS (+38 more)

### Community 33 - "GeminiAdapter"
Cohesion: 0.09
Nodes (10): _attach_signature_to_parts(), _clone_part_with_sig(), _clone_part_with_text(), _coerce_part(), _decode_sig_bytes(), _extract_part_signature(), GeminiAdapter, _is_empty_sig_carrier() (+2 more)

### Community 34 - "cli-executor.js"
Cohesion: 0.09
Nodes (37): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, MAX_TASK_WALL_MS, MAX_TIMER_MS, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS, STORAGE_PRETASK_TIMEOUT_MS, resolveStorageRoot }, buildCLICommand(), buildTimeoutResult(), { checkAndRecycleStorage, pinTaskCwd, unpinTaskCwd }, CLAUDE_JSON_PATH, cp, createInactivityWatchdog(), executeCLI() (+29 more)

### Community 35 - "storage-recycler.js"
Cohesion: 0.08
Nodes (37): withTaskStorage(), MAX_TASK_WALL_MS, parseTimerMs(), resolveStorageRoot(), resolveTimeoutMs(), ROLE_TIMEOUTS, STORAGE_ACTIVITY_HEARTBEAT_MS, STORAGE_MAX_TIER3_DELETIONS (+29 more)

### Community 36 - "slack.py"
Cohesion: 0.07
Nodes (17): build_access_denied_home_view(), build_home_tab_view(), _context_line(), create_feedback_block(), format_plan_block(), format_task_card(), format_tool_result_blocks(), format_turn() (+9 more)

### Community 37 - "agents/__init__.py"
Cohesion: 0.07
Nodes (4): Architect, AgentClient, Developer, SysAdmin

### Community 38 - "KnowledgeGraphStore"
Cohesion: 0.09
Nodes (9): _format_graph_context(), get_graph_context(), _parse_props(), _sanitize(), translate_to_lookups(), _acquire(), KnowledgeGraphStore, _sanitize() (+1 more)

### Community 39 - "llm/__init__.py"
Cohesion: 0.08
Nodes (7): ClaudeAdapter, _parse_tpm_limit(), FunctionCall, LLMChunk, LLMPort, LLMResponse, TokenUsage

### Community 40 - "OpsStateContext.tsx"
Cohesion: 0.09
Nodes (31): getAgents(), getKargoStages(), ApprovalErrorKind, EventEvidence, KargoStageStatus, AgentRegistryPanel(), formatConnectedSince(), STARTER_CHIPS (+23 more)

### Community 41 - "handlers_integration.py"
Cohesion: 0.07
Nodes (18): _alert_wrapper_retrigger(), _do_retrigger(), _get_jira_reporter(), handle_ask_release_ai(), _is_darwin_reentrant_caller(), _is_positive_int(), jenkins_retrigger_cooldown_key(), _parse_poll_interval() (+10 more)

### Community 42 - "headhunter_gitlab.py"
Cohesion: 0.09
Nodes (17): _get_static_maintainer_emails(), _parse_ts_epoch(), _build_closed_block(), build_event_header(), _build_identity_block(), _build_journal_block(), _build_mermaid_block(), build_operational_briefing() (+9 more)

### Community 43 - "hooks/index.ts"
Cohesion: 0.10
Nodes (31): getClosedEvents(), getEvents(), ArchitectureEvent, ArgoCDOperation, ActivityStream(), ArchitectureGraph(), EVENT_LABELS, EventItem() (+23 more)

### Community 44 - "headhunter.py"
Cohesion: 0.07
Nodes (7): HeadhunterCircuitBreaker, _NoAliasSafeLoader, on_headhunter_done(), _raise_if_systemic_failure(), start_headhunter_task(), _safe_int(), _validate_plan_yaml()

### Community 45 - "httpx"
Cohesion: 0.09
Nodes (8): dex_proxy(), approve_mission(), dismiss_mission(), _infer_phase(), _jira_config(), list_missions(), reanalyze_mission(), retry_mission()

### Community 46 - "get_brain"
Cohesion: 0.10
Nodes (15): get_user_from_request(), get_brain(), _acquire_hh_poll_lock(), approve_event(), _busy_lock_response(), enforce_casual_domain(), EnforceCasualRequest, _get_headhunter_or_503() (+7 more)

### Community 47 - "TimeKeeperPage.tsx"
Cohesion: 0.12
Nodes (24): createSchedule(), deleteSchedule(), getSchedules(), refineInstructions(), ScheduleCreatePayload, ScheduleItem, toggleSchedule(), updateSchedule() (+16 more)

### Community 50 - "ws-client.js"
Cohesion: 0.10
Nodes (26): clearIdleTimer(), {
  DEFAULT_WORK_DIR, AGENT_CLI, AGENT_MODEL, AGENT_ROLE,
  EVENT_ID, EPHEMERAL, IDLE_TIMEOUT_MS,
  CLI_429_MAX_RETRIES, CLI_429_INITIAL_DELAY_MS, CLI_429_BACKOFF_MULTIPLIER,
  resolveTimeoutMs, parsePositiveInt, MAX_TASK_WALL_MS, MAX_TIMER_MS,
}, { ensureEventDocument }, { executeCLIStreaming, prepareResultsDir, is429Error }, { filterSkillsByRole, filterSkillsByMode, swapActiveRules, restoreAllSkills }, fs, handleCancel(), handleTask() (+18 more)

### Community 51 - "observations_reporter.py"
Cohesion: 0.08
Nodes (15): _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), render_pdf(), _sample_points(), _summarize() (+7 more)

### Community 52 - "types.py"
Cohesion: 0.08
Nodes (16): derive_llm_priority(), _get_timeout_env_warned(), _get_timeout_order_warned(), is_partial_control_token(), LLMStreamInterChunkTimeoutError, LLMStreamTimeoutError, LLMStreamTotalTimeoutError, LLMStreamTTFBTimeoutError (+8 more)

### Community 53 - "DashboardWSAdapter"
Cohesion: 0.10
Nodes (6): DashboardWSAdapter, prompt_display_name(), resolve_approval_identity(), ChatEventRequest, ChatEventResponse, create_chat_event()

### Community 54 - "event_to_markdown"
Cohesion: 0.09
Nodes (12): _clamp_confidence(), _sanitize_analysis_text(), _strip_newlines(), _validate_analysis(), _validate_triage_entry(), CIAnalysis, _esc(), _esc_join() (+4 more)

### Community 55 - "dispatch.py"
Cohesion: 0.11
Nodes (10): _build_prompt(), _check_security(), consume_wake_task(), _consume(), _dispatch_timeout_s(), dispatch_to_agent(), _consume_queue(), _sanitize_stdout() (+2 more)

### Community 56 - "ui/package.json"
Cohesion: 0.08
Nodes (29): autoprefixer, cronstrue, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, graphology-layout-forceatlas2 (+21 more)

### Community 57 - "NightwatcherObserver"
Cohesion: 0.10
Nodes (7): ShiftReport, _append_user_turn(), _env_float(), _env_int(), NightwatcherObserver, _finalize_analysis_handover(), build_system_prompt()

### Community 58 - "useOpsControl"
Cohesion: 0.14
Nodes (25): Dashboard(), GridTile(), GridTileProps, TileType, InlineMarkdownViewer(), EmptyState(), LayoutMode, StreamGrid() (+17 more)

### Community 59 - "useCortexData.ts"
Cohesion: 0.17
Nodes (27): getCognitiveGraph(), getCortexActivity(), getKGServiceDetail(), getKGServices(), getKGStats(), getKnowledgeById(), getMemory(), getRecentPulses() (+19 more)

### Community 60 - ".list_observations"
Cohesion: 0.07
Nodes (5): get_all_journal(), get_service_journal(), get_event_observations(), get_global_observations(), export_observations()

### Community 61 - "VectorStore"
Cohesion: 0.09
Nodes (3): _decode_cursor(), _encode_cursor(), VectorStore

### Community 63 - "AgentRegistry"
Cohesion: 0.10
Nodes (3): AgentConnection, AgentRegistry, agent_websocket_handler()

### Community 66 - "llm_error_classifier.py"
Cohesion: 0.13
Nodes (9): _extract_status_code(), _has_non_retryable_cause(), _is_google_auth_transport_error(), is_rate_limit(), is_transient(), is_transient_llm_error_turn(), _iter_exception_chain(), _matches_mro() (+1 more)

### Community 67 - "server.js"
Cohesion: 0.09
Nodes (18): { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, ensureEventDocument(), fs, path, stageEventDocument(), fetchEventDocument(), fs, { handleRequest } (+10 more)

### Community 68 - "CortexGraph.tsx"
Cohesion: 0.15
Nodes (24): graphology, eventColor(), getExecutiveNeurons(), getStructuralEdges(), DEFAULT_TYPE_BUDGET, evictLru(), KNOWLEDGE_RING, KNOWLEDGE_RING_TYPES (+16 more)

### Community 69 - "spawn_event_namer_task"
Cohesion: 0.15
Nodes (8): spawn_event_namer_task(), handle_app_home_opened(), handle_app_mention(), handle_create_event_modal(), handle_darwin_command(), handle_home_create_event(), on_dm_message(), fallback_title()

### Community 71 - "cognitive_graph.py"
Cohesion: 0.11
Nodes (11): get_pulse_tracker(), dismiss_proposals(), DismissRequest, get_all_shadow_interventions(), get_cognitive_graph(), get_cortex_activity(), get_cortex_status(), get_event_shadow_interventions() (+3 more)

### Community 72 - "EventChatPanel.tsx"
Cohesion: 0.14
Nodes (21): CiContext, TokenUsageDict, CiContextCard(), CiContextCardProps, ConsoleTailBlock(), FailedJobRow(), CollapsibleSection(), EventChatPanel() (+13 more)

### Community 73 - "gemini_client.py"
Cohesion: 0.10
Nodes (11): _append_user_turn(), _extract_call_syntax(), _is_function_response_part(), _parse_drain_timeout(), _strip_user_thought_signature(), _validated_parts(), process_stream_call_syntax_buffer(), sanitize_call_syntax() (+3 more)

### Community 76 - "PulseBatch"
Cohesion: 0.10
Nodes (4): PulseBatch, PulsePort, PulseObserver, PulseTracker

### Community 78 - "NeuronInfoPanel.tsx"
Cohesion: 0.11
Nodes (23): KGServiceDetail, AGENTS, DOMAINS, HEMISPHERE_X, NEURON_DESCRIPTIONS, PHASE_SKILL_FOLDERS, PHASE_TOOL_PRIORITY, PHASES (+15 more)

### Community 79 - "BrainIntrospectionPort"
Cohesion: 0.08
Nodes (3): BrainIntrospectionPort, BrainLifecyclePort, BroadcastPort

### Community 82 - "quota_tracker.py"
Cohesion: 0.12
Nodes (5): QuotaExhaustedError, QuotaTracker, RequestExceedsBurstError, Reservation, _stale_reservation_ttl_s()

### Community 84 - "create_schedule"
Cohesion: 0.08
Nodes (5): create_schedule(), delete_schedule(), get_schedule(), list_schedules(), toggle_schedule()

### Community 86 - "dependencies"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 87 - "create_adapter"
Cohesion: 0.11
Nodes (4): create_adapter(), record_token_usage(), _load_brain_context(), refine_instructions()

### Community 90 - "cortex/types.ts"
Cohesion: 0.15
Nodes (20): devQueryClient, CortexLiveFeedProps, EventDrillDownProps, MOCK_CORTEX_STATUS, MOCK_EVENT_ID, MOCK_NEURONS, MOCK_PULSE_BATCHES, MOCK_SHADOW (+12 more)

### Community 91 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 92 - "reconcile.py"
Cohesion: 0.17
Nodes (10): generate_phase_tool_map(), _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers(), main() (+2 more)

### Community 93 - "claude-guard.js"
Cohesion: 0.14
Nodes (18): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+10 more)

### Community 95 - "AsyncGitHubClient"
Cohesion: 0.17
Nodes (5): AsyncGitHubClient, _handle_rate_limit(), _paginate_github_get(), parse_github_next_link(), _safe_parse_int()

### Community 96 - "ArchitectureGraph.tsx"
Cohesion: 0.14
Nodes (17): @dagrejs/dagre, @xyflow/react, applyDagreLayout(), applyGridLayout(), applyLayout(), ArchitectureGraphInner(), buildGraph(), computeIdHash() (+9 more)

### Community 97 - "FlowHistoryPage.tsx"
Cohesion: 0.23
Nodes (16): recharts, getFlowHistory(), FlowSnapshot, FlowHistoryPage(), RANGES, SparkCard(), SparkCardProps, formatTime() (+8 more)

### Community 98 - "._feedback_reject_reason"
Cohesion: 0.11
Nodes (7): _bot_login(), _csv_env(), _consider(), _is_slash_command_only(), _mention_pattern(), _review_ignore_logins(), _review_trusted_associations()

### Community 99 - "cli-setup.js"
Cohesion: 0.13
Nodes (18): { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync }, filterSkillsByMode() (+10 more)

### Community 100 - "StateWatcher"
Cohesion: 0.13
Nodes (3): _QueueEntry, StateWatcher, _Subscription

### Community 103 - "ArchitectureEvent"
Cohesion: 0.13
Nodes (3): ArchitectureEvent, list_events(), MetricsRepository

### Community 105 - "devDependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 106 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 107 - "gemini-sidecar/package.json"
Cohesion: 0.11
Nodes (18): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+10 more)

### Community 109 - "get_report"
Cohesion: 0.11
Nodes (6): get_report(), list_reports(), reports_spa_no_slash(), reports_spa_with_slash(), search_reports(), _serve_spa()

### Community 110 - "JiraIncidentAdapter"
Cohesion: 0.15
Nodes (3): _adf_to_text(), _escape_jql_string(), JiraIncidentAdapter

### Community 113 - "ShiftsPage.tsx"
Cohesion: 0.23
Nodes (16): getCurrentShift(), getShiftDetail(), getShiftsList(), ShiftReportFull, ShiftReportSummary, FailedClusterBadge(), getISOWeek(), getWeekDates() (+8 more)

### Community 114 - "catalog-skills.js"
Cohesion: 0.16
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 119 - "feedback.py"
Cohesion: 0.14
Nodes (4): FeedbackRequest, submit_feedback(), KargoStageSnapshot, list_failed_stages()

### Community 121 - "JenkinsPlatformPort"
Cohesion: 0.13
Nodes (4): BuildDetails, JenkinsPlatformPort, JobRunState, ViewScanResult

### Community 126 - "ServiceNode.tsx"
Cohesion: 0.20
Nodes (11): HealthStatus, NodeType, AppNodeData, ARGOCD_HEALTH_COLORS, SYNC_ICONS, GENERIC_TAGS, HEALTH_COLORS, NODE_ICONS (+3 more)

### Community 130 - "._process_candidates"
Cohesion: 0.15
Nodes (3): _flood_service_key(), _outage_service_key(), _service_key()

### Community 132 - "analyzeTokens"
Cohesion: 0.19
Nodes (13): analyzeString(), analyzeTokens(), assignName(), base(), combineCategories(), configEnvGuard(), configFileWriteGuard(), hasSubseq() (+5 more)

### Community 133 - "generate_map.py"
Cohesion: 0.19
Nodes (5): _enumerate_gates(), _GateInfo, _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 134 - "EventDrillDown.tsx"
Cohesion: 0.22
Nodes (10): three, getEventPulses(), BrainCore(), CortexDevPage(), EventDrillDown(), FRICTION_COLORS, WHISPER_COLORS, PulseTimeline() (+2 more)

### Community 137 - "._extract_context_flags"
Cohesion: 0.15
Nodes (3): compute_dispatch_backpressure(), ContextFlags, _safe_int_env()

### Community 138 - "handlers_planning.py"
Cohesion: 0.24
Nodes (6): _auto_complete_step(), _canonical_role(), handle_get_plan_progress(), _is_failed_turn(), _is_orchestrator_turn(), _normalize_step_id()

### Community 140 - "IncidentAdapterPort"
Cohesion: 0.15
Nodes (3): IdleTimeoutPort, IncidentAdapterPort, StateWatcherPort

### Community 143 - "generate_event_title"
Cohesion: 0.18
Nodes (4): generate_event_title(), get_adapter(), _get_semaphore(), sanitize_title()

### Community 148 - "CortexLiveFeed.tsx"
Cohesion: 0.24
Nodes (10): CortexHeartbeat(), CortexHeartbeatProps, ensureKeyframes(), CortexLiveFeed(), FILTER_PILLS, FilterKey, getStoredFilter(), MESSAGE_STYLES (+2 more)

### Community 149 - "testSetup.ts"
Cohesion: 0.18
Nodes (5): @tailwindcss/vite, @testing-library/react, vite, @vitejs/plugin-react, vitest

### Community 152 - "is_defer_event_available"
Cohesion: 0.18
Nodes (6): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 154 - "Any"
Cohesion: 0.25
Nodes (3): handle_approve(), handle_approve_sha(), handle_reject()

### Community 158 - "gitGuard"
Cohesion: 0.29
Nodes (10): bareBranchProtected(), configWriteGuard(), externalGitCommand(), gitGuard(), gitQuery(), isProtected(), normRef(), pushGuard() (+2 more)

### Community 159 - "parseShell"
Cohesion: 0.33
Nodes (10): bodySubstitutions(), decodeAnsiC(), isArrayAssignPrefix(), isWordStart(), matchBacktick(), matchParen(), parseShell(), readHeredocStart() (+2 more)

### Community 163 - "entity_extractor.py"
Cohesion: 0.33
Nodes (5): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship

### Community 166 - "has_unevaluated_close_blocker"
Cohesion: 0.22
Nodes (5): has_unevaluated_close_blocker(), _pred_jarvis_response(), _pred_unevaluated_close(), is_jarvis_acknowledgment(), is_stabilization_wake()

### Community 167 - "knowledge_graph_api.py"
Cohesion: 0.31
Nodes (4): get_kg_store(), get_service_detail(), get_stats(), list_services()

### Community 169 - "PulseBatch"
Cohesion: 0.27
Nodes (9): ActiveEvent, EventSource, KGServiceEntity, CortexGraphProps, GraphLoaderProps, PulseTimelineProps, PulseBatch, WorkspaceTaskItemProps (+1 more)

### Community 171 - "SecurityError"
Cohesion: 0.28
Nodes (3): safe_execution(), wrapper(), SecurityError

### Community 172 - "classifyTool"
Cohesion: 0.31
Nodes (9): apiTokens(), apiWriteNeedsGuard(), branchValues(), classifyTool(), hasOpaqueTarget(), httpGuard(), httpMethod(), isReadMethod() (+1 more)

### Community 176 - "get_quota_tracker"
Cohesion: 0.22
Nodes (3): get_quota_tracker(), llm_stats(), receive_telemetry()

### Community 178 - "useDeferCountdown.ts"
Cohesion: 0.47
Nodes (7): DeferCountdownState, useDeferCountdown(), computeDeferProgress(), DeferTimeline, formatDeferRemaining(), inferDeferFromConversation(), resolveDeferTimeline()

### Community 185 - "adf_to_markdown"
Cohesion: 0.57
Nodes (7): adf_to_markdown(), _apply_marks(), _children(), _render(), _render_list(), _render_list_item(), _render_table_like()

### Community 186 - "validate-mutations.sh"
Cohesion: 0.57
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

### Community 190 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 191 - "state.js"
Cohesion: 0.33
Nodes (4): { AGENT_ROLE }, _blackboardTurns, _inboundMessages, _teammateMessages

### Community 198 - "build_gate_context"
Cohesion: 0.33
Nodes (3): build_gate_context(), conversation_has_decayed_turns(), _decay_payload_len()

### Community 204 - "extract_tables"
Cohesion: 0.40
Nodes (3): extract_tables(), _replace(), _md_table_to_block_kit()

### Community 209 - "classify"
Cohesion: 0.50
Nodes (4): classify(), main(), shellCategory(), shellNeedsGuard()

### Community 217 - "overrides"
Cohesion: 0.67
Nodes (3): overrides, @typescript-eslint/typescript-estree, minimatch

## Knowledge Gaps
- **13 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+8 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2584 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **122 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `ConversationTurn`, `models.py`, `queue.py`, `ScheduleRepository`, `os`, `brain.py`, `Brain`, `generate_event_title`, `main.py`, `nightwatcher_tools.py`, `Service`, `headhunter_github.py`, `BrainSkillLoader`, `EventDocument`, `auth.py`, `slack.py`, `headhunter_gitlab.py`, `headhunter.py`, `httpx`, `get_brain`, `_is_event_closed_or_missing`, `observations_reporter.py`, `DashboardWSAdapter`, `ConversationMessage`, `._update_event_vcs_context`, `NightwatcherObserver`, `update_schedule`, `.list_observations`, `LiveAPIAdapter`, `rename_observation`, `._restage_pending_signal`, `lifespan`, `._stage_pending_signal`, `._count_pending`, `._downsample_snapshots`, `create_schedule`, `report_tampering`, `HeadhunterJira`, `ArchitectureEvent`, `get_report`, `feedback.py`, `._validate_gitlab_ids`?**
  _High betweenness centrality (0.114) - this node is a cross-community bridge._
- **Are the 81 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 81 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.011442700247254326 - nodes in this community are weakly interconnected._
- **Why does `Brain` connect `Brain` to `BlackboardState`, `ConversationTurn`, `models.py`, `brain.py`, `._run_agent_task`, `._extract_context_flags`, `IdleTimeoutManager`, `ReconcileScheduler`, `main.py`, `Archivist`, `.start_event_loop`, `headhunter_github.py`, `BrainSkillLoader`, `EventDocument`, `._process_with_llm`, `._resolve_llm_params`, `._post_agent_recall`, `FlowCollector`, `slack.py`, `agents/__init__.py`, `headhunter_gitlab.py`, `DashboardWSAdapter`, `._detect_repetition_collapse`, `lifespan`, `PulseBatch`, `QueueTrigger`, `BrainIntrospectionPort`, `._build_contents`, `StateWatcher`, `ReflexSearcher`, `JarvisPeerPort`?**
  _High betweenness centrality (0.072) - this node is a cross-community bridge._
- **Are the 20 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Should `ConversationTurn` be split into smaller, more focused modules?**
  _Cohesion score 0.04665561083471531 - nodes in this community are weakly interconnected._