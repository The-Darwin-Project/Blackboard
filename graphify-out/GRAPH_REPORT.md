# Graph Report - Blackboard  (2026-11-23)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 5735 nodes · 12914 edges · 269 communities (104 shown, 165 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 980 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `0c7dd707`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- brain.py
- client.ts
- BlackboardState
- main.py
- queue.py
- nightwatcher_tools.py
- auth.py
- WorkspaceInspector.tsx
- lucide-react
- App.tsx
- Brain
- GitLabPlatform
- useCortexData.ts
- tool_gates.py
- ._run_agent_task
- EventSidebar.tsx
- AgentRegistry
- ReconcileScheduler
- EventRepository
- http-handler.js
- Headhunter
- context_parts.py
- colors.ts
- jenkins-mcp.js
- headhunter_github.py
- TurnBubble.tsx
- prompt_sanitize.py
- ._process_with_llm
- Aligner
- _BrainToolContext
- ToolContext
- StreamGrid.tsx
- merge-guard.js
- EventDocument
- cli-executor.js
- storage-recycler.js
- .get_graph_data
- handlers_integration.py
- BrainSkillLoader
- GeminiAdapter
- ArchitectureGraph.tsx
- react
- llm/__init__.py
- slack.py
- ConversationTurn
- types.py
- TopologyRepository
- VcsPlatformPort
- ws-client.js
- observations_reporter.py
- HeadhunterCircuitBreaker
- ui/package.json
- CortexGraph.tsx
- KnowledgeGraphStore
- event_to_markdown
- LiveAPIAdapter
- BoolOutcome
- llm_error_classifier.py
- server.js
- StateWatcher
- HeadhunterJira
- JenkinsAdapter
- PulseBatch
- ArgoCDObserver
- create_schedule
- NodeInspector.tsx
- reconcile.py
- JenkinsObserver
- gemini_client.py
- KargoObserver
- dependencies
- compilerOptions
- claude-guard.js
- DashboardWSAdapter
- ._build_contents
- JarvisPeerPort
- GitHubPlatform
- sanitize_untrusted_line
- AsyncGitHubClient
- GitHubAppAuth
- FlowHistoryPage.tsx
- tool_router.py
- SlackChannel
- cli-setup.js
- ReflexSearcher
- ArchitectureEvent
- devDependencies
- compilerOptions
- gemini-sidecar/package.json
- EphemeralProvisioner
- ._poll_pr_feedback
- jira.py
- get_report
- .list_observations
- get_quota_tracker
- _sanitize_analysis_text
- ObservationRepository
- ShiftsPage.tsx
- catalog-skills.js
- Archivist
- ._feedback_reject_reason
- .fetch_context
- ._poll_issues
- EscalationRepository
- VectorStore
- .__init__
- TokenMeter
- MultiInstallationManager
- JenkinsPlatformPort
- ._normalize_issue
- OIDCKeyAdapter
- KubernetesSpawnHealthAdapter
- IdleTimeoutManager
- QuotaTracker
- ._send_turn_to_thread
- ._connect
- handlers_planning.py
- .poll_review_feedback_all_installations
- ._process_candidates
- ._register_handlers
- ScheduleRepository
- analyzeTokens
- generate_map.py
- ._poll_and_stage
- .scroll
- ._extract_context_flags
- ._get_client_for_repo
- ScheduleCreateRequest
- cortex-pulse-handler.ts
- ._process_message
- adf_to_markdown
- testSetup.ts
- is_defer_event_available
- ._authorize_plan_decision
- SlackAccessGate
- GitLabTokenAuth
- NeuronInfoPanel.tsx
- gitGuard
- parseShell
- entity_extractor.py
- ._triage_and_build_evidence
- has_unevaluated_close_blocker
- Any
- knowledge_graph_api.py
- spawn_health.py
- classifyTool
- SpawnPollResult
- get_all_journal
- list_shifts
- _is_event_closed_or_missing
- ._evaluate_health
- ConversationMessage
- TimeKeeperObserver
- CortexRepository
- validate-mutations.sh
- update_schedule
- ._detect_repetition_collapse
- _format_graph_context
- .has_reeval_signal
- update_notebook_note
- scripts
- state.js
- DispatchMetrics
- build_gate_context
- list_failed_stages
- rename_observation
- dex_proxy
- ._wait_for_registration
- handle_recall_pruned_turns
- handle_report_incident
- get_notebook
- classify
- _has_non_user_turns
- require-results.sh
- _WSFrameFilter
- _resolve_slack_user
- get_intermediate_tools
- get_event_flow
- report_tampering
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
1. `BlackboardState` - 316 edges
2. `Brain` - 168 edges
3. `ConversationTurn` - 136 edges
4. `ToolContext` - 103 edges
5. `GateContext` - 99 edges
6. `EventDocument` - 87 edges
7. `GitHubPlatform` - 87 edges
8. `react` - 85 edges
9. `EventRepository` - 82 edges
10. `fetchApi()` - 66 edges

## Surprising Connections (you probably didn't know these)
- `Archivist` --uses--> `Pulse`  [INFERRED]
  src/agents/archivist.py → src/memory/pulse.py
- `Brain` --uses--> `Pulse`  [INFERRED]
  src/agents/brain.py → src/memory/pulse.py
- `BlackboardState` --uses--> `AppNode`  [INFERRED]
  src/state/blackboard.py → src/models.py
- `DashboardWSAdapter` --uses--> `EventEvidence`  [INFERRED]
  src/adapters/dashboard_ws.py → src/models.py
- `LiveAPIAdapter` --uses--> `EventEvidence`  [INFERRED]
  src/adapters/live_api_adapter.py → src/models.py

## Import Cycles
- None detected.

## Communities (269 total, 165 thin omitted)

### Community 0 - "brain.py"
Cohesion: 0.02
Nodes (49): _annotation_replace(), _strip_pipeline_annotations(), _sanitize_lesson_text(), _batch_is_terminal_for_flush(), _is_close_phase_fc(), _is_external_input_turn(), get_graph_context(), translate_to_lookups() (+41 more)

### Community 1 - "client.ts"
Cohesion: 0.03
Nodes (124): @tanstack/react-query, ApiError, applyLessons(), bulkDeleteObservations(), correctMemory(), createKnowledge(), createLesson(), deleteKnowledge() (+116 more)

### Community 3 - "main.py"
Cohesion: 0.02
Nodes (37): Architect, AgentClient, Developer, SysAdmin, set_oidc_adapter(), get_aligner(), get_architect(), get_argocd_observer() (+29 more)

### Community 4 - "queue.py"
Cohesion: 0.03
Nodes (55): can_approve_event(), can_override_domain(), can_rename_event(), _normalize_email(), resolve_approval_identity(), get_archivist(), get_brain(), EventStatus (+47 more)

### Community 5 - "nightwatcher_tools.py"
Cohesion: 0.04
Nodes (38): JiraIncidentAdapter, record_token_usage(), QuotaExhaustedError, RequestExceedsBurstError, PulseContext, ShiftIncident, ShiftInvestigation, ShiftReport (+30 more)

### Community 6 - "auth.py"
Cohesion: 0.04
Nodes (29): _claims_to_user(), get_user_from_request(), get_user_from_slack(), get_user_from_websocket(), require_auth(), require_obs_admin(), UserContext, _validate_jwt() (+21 more)

### Community 7 - "WorkspaceInspector.tsx"
Cohesion: 0.05
Nodes (75): updateEventTitle(), AgentRegistryEntry, CiContext, ConversationTurn, TokenUsageDict, CiContextCard(), CiContextCardProps, ConsoleTailBlock() (+67 more)

### Community 8 - "lucide-react"
Cohesion: 0.05
Nodes (66): lucide-react, react-router-dom, createChatEvent(), getAgents(), getEventDocument(), getEvents(), getKargoStages(), AppConfig (+58 more)

### Community 9 - "App.tsx"
Cohesion: 0.04
Nodes (68): oidc-client-ts, react-dom, createSchedule(), dismissProposals(), EnhancementProposal, getConfig(), getHandoffReports(), getProposals() (+60 more)

### Community 11 - "GitLabPlatform"
Cohesion: 0.05
Nodes (5): _get_allowed_mention_authors(), GitLabPlatform, _reconcile_synthetic(), _check_one(), _valid_positive_int()

### Community 12 - "useCortexData.ts"
Cohesion: 0.06
Nodes (72): three, getCognitiveGraph(), getCortexActivity(), getEventPulses(), getKGServiceDetail(), getKGServices(), getKGStats(), getRecentPulses() (+64 more)

### Community 13 - "tool_gates.py"
Cohesion: 0.05
Nodes (79): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+71 more)

### Community 14 - "._run_agent_task"
Cohesion: 0.05
Nodes (12): on_huddle(), on_progress(), on_huddle(), on_progress(), _compute_processed_up_to(), _is_automated_nudge(), _is_participant_turn(), _is_steering_turn() (+4 more)

### Community 15 - "EventSidebar.tsx"
Cohesion: 0.07
Nodes (67): getJiraMissions(), HeadhunterTodo, postJiraAction(), ActiveEvent, DeferCountdownBar(), ACTION_BADGE, formatAge(), HeadhunterQueuePanel() (+59 more)

### Community 16 - "AgentRegistry"
Cohesion: 0.05
Nodes (17): AgentConnection, AgentRegistry, agent_websocket_handler(), _heartbeat(), _build_prompt(), _check_security(), consume_wake_task(), _consume() (+9 more)

### Community 17 - "ReconcileScheduler"
Cohesion: 0.04
Nodes (8): get_token_meter(), FlowCollector, FairQueue, ReconcileScheduler, Trigger, QueueTrigger, ResyncTrigger, StalenessGuard

### Community 19 - "http-handler.js"
Cohesion: 0.08
Nodes (62): is429Error(), registerMCPsAndHooks(), resolveCommand(), writeAgyMcpServer(), writeClaudeMcpServer(), parsePositiveInt(), buildArgoCDMcpConfig(), createAppJWT() (+54 more)

### Community 20 - "Headhunter"
Cohesion: 0.06
Nodes (6): Headhunter, _iref(), _process_issue(), _try_queue_issue(), VcsContext, _NoAliasSafeLoader

### Community 21 - "context_parts.py"
Cohesion: 0.05
Nodes (25): _close_unanswered_fc(), _contents_have_pruned_or_decayed(), _apply_sibling_signature(), build_function_response(), build_single_function_response(), compress_contents(), contents_have_pruned_or_decayed(), estimate_msg_tokens() (+17 more)

### Community 22 - "colors.ts"
Cohesion: 0.07
Nodes (38): getReport(), getReports(), ReportFull, ReportMeta, CompactCardStrip(), EventHistory(), TimeRange, ViewMode (+30 more)

### Community 23 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 24 - "headhunter_github.py"
Cohesion: 0.06
Nodes (19): _iso(), _parse_ts(), _github_active_item(), headhunter_pending_todos(), get_installation_manager(), is_shared_installation_manager(), reset_installation_manager(), get_gitlab_auth() (+11 more)

### Community 25 - "TurnBubble.tsx"
Cohesion: 0.08
Nodes (44): @uiw/react-markdown-preview, approveEvent(), closeEvent(), enforceCasualDomain(), getEventReport(), rejectEvent(), submitFeedback(), ConversationFeed() (+36 more)

### Community 26 - "prompt_sanitize.py"
Cohesion: 0.07
Nodes (17): generate_event_title(), get_adapter(), _get_semaphore(), spawn_event_namer_task(), create_adapter(), can_append_message(), format_event_summary(), handle_app_mention() (+9 more)

### Community 27 - "._process_with_llm"
Cohesion: 0.04
Nodes (4): _BatchContext, _ensure_recall_tool_if_needed(), _QuotaShedState, _retry_backoff_delay()

### Community 30 - "ToolContext"
Cohesion: 0.08
Nodes (11): handle_message_agent(), handle_reply_to_agent(), handle_select_agent(), _sticky_work_style(), handle_defer_event(), handle_hold_watch(), handle_request_user_approval(), handle_respond_to_jarvis() (+3 more)

### Community 31 - "StreamGrid.tsx"
Cohesion: 0.08
Nodes (39): AgentStreamCard(), AgentStreamCardProps, MessageCards(), Dashboard(), GridTile(), GridTileProps, TileType, InlineMarkdownViewer() (+31 more)

### Community 32 - "merge-guard.js"
Cohesion: 0.04
Nodes (46): API_VALUED, ARGO_MUTATING, ARGO_READ_SUB, ARGO_READ_TOP, BODY_FLAG, BROWSER_READ, CTX, ENV_BUILTINS (+38 more)

### Community 33 - "EventDocument"
Cohesion: 0.05
Nodes (5): _inject_evidence_paths(), _init_tool_names(), _strip_tool_names(), _wrap_section(), EventDocument

### Community 34 - "cli-executor.js"
Cohesion: 0.09
Nodes (37): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, MAX_TASK_WALL_MS, MAX_TIMER_MS, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS, STORAGE_PRETASK_TIMEOUT_MS, resolveStorageRoot }, buildCLICommand(), buildTimeoutResult(), { checkAndRecycleStorage, pinTaskCwd, unpinTaskCwd }, CLAUDE_JSON_PATH, cp, createInactivityWatchdog(), executeCLI() (+29 more)

### Community 35 - "storage-recycler.js"
Cohesion: 0.08
Nodes (37): withTaskStorage(), MAX_TASK_WALL_MS, parseTimerMs(), resolveStorageRoot(), resolveTimeoutMs(), ROLE_TIMEOUTS, STORAGE_ACTIVITY_HEARTBEAT_MS, STORAGE_MAX_TIER3_DELETIONS (+29 more)

### Community 36 - ".get_graph_data"
Cohesion: 0.06
Nodes (7): _defer_timeline_fields(), get_graph_data(), get_mermaid_diagram(), get_service_details(), get_topology(), list_services(), calculate_health_from_argocd()

### Community 37 - "handlers_integration.py"
Cohesion: 0.08
Nodes (21): _alert_wrapper_retrigger(), _do_retrigger(), _get_jira_reporter(), handle_refresh_github_context(), _emit(), handle_refresh_gitlab_context(), handle_refresh_kargo_context(), _is_darwin_reentrant_caller() (+13 more)

### Community 38 - "BrainSkillLoader"
Cohesion: 0.06
Nodes (3): BrainSkillLoader, _SkillCorpus, BrainIntrospectionPort

### Community 39 - "GeminiAdapter"
Cohesion: 0.10
Nodes (8): _attach_signature_to_parts(), _extract_call_syntax(), _extract_part_signature(), GeminiAdapter, _is_empty_sig_carrier(), _part_has_fc(), _sanitize_candidate_parts(), strip_control_tokens()

### Community 40 - "ArchitectureGraph.tsx"
Cohesion: 0.07
Nodes (33): @dagrejs/dagre, @xyflow/react, HealthStatus, NodeType, AppNodeData, applyDagreLayout(), applyGridLayout(), applyLayout() (+25 more)

### Community 41 - "react"
Cohesion: 0.10
Nodes (35): react, ExtractedCorrection, ExtractedLesson, KnowledgeScope, ExtractWizard(), ReviewItem, Step, ConfidenceBadge() (+27 more)

### Community 42 - "llm/__init__.py"
Cohesion: 0.08
Nodes (7): ClaudeAdapter, _parse_tpm_limit(), FunctionCall, LLMChunk, LLMPort, LLMResponse, TokenUsage

### Community 43 - "slack.py"
Cohesion: 0.08
Nodes (15): build_access_denied_home_view(), build_home_tab_view(), _context_line(), create_feedback_block(), format_plan_block(), format_task_card(), format_tool_result_blocks(), format_turn() (+7 more)

### Community 44 - "ConversationTurn"
Cohesion: 0.16
Nodes (27): _safe_int(), handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_ask_release_ai(), handle_comment_jira_issue(), handle_fetch_jira_issue(), handle_greenwave() (+19 more)

### Community 45 - "types.py"
Cohesion: 0.08
Nodes (18): derive_llm_priority(), _get_timeout_env_warned(), _get_timeout_order_warned(), is_partial_control_token(), LLMStreamInterChunkTimeoutError, LLMStreamTimeoutError, LLMStreamTotalTimeoutError, LLMStreamTTFBTimeoutError (+10 more)

### Community 47 - "VcsPlatformPort"
Cohesion: 0.07
Nodes (3): _get_canonical_or_alias(), VcsWorkItem, VcsPlatformPort

### Community 48 - "ws-client.js"
Cohesion: 0.10
Nodes (26): clearIdleTimer(), {
  DEFAULT_WORK_DIR, AGENT_CLI, AGENT_MODEL, AGENT_ROLE,
  EVENT_ID, EPHEMERAL, IDLE_TIMEOUT_MS,
  CLI_429_MAX_RETRIES, CLI_429_INITIAL_DELAY_MS, CLI_429_BACKOFF_MULTIPLIER,
  resolveTimeoutMs, parsePositiveInt, MAX_TASK_WALL_MS, MAX_TIMER_MS,
}, { ensureEventDocument }, { executeCLIStreaming, prepareResultsDir, is429Error }, { filterSkillsByRole, filterSkillsByMode, swapActiveRules, restoreAllSkills }, fs, handleCancel(), handleTask() (+18 more)

### Community 49 - "observations_reporter.py"
Cohesion: 0.08
Nodes (15): _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), render_pdf(), _sample_points(), _summarize() (+7 more)

### Community 50 - "HeadhunterCircuitBreaker"
Cohesion: 0.07
Nodes (6): HeadhunterCircuitBreaker, PlatformBreakerStatus, _redact_error_text(), on_headhunter_done(), _raise_if_systemic_failure(), start_headhunter_task()

### Community 51 - "ui/package.json"
Cohesion: 0.08
Nodes (28): autoprefixer, cronstrue, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, graphology-layout-forceatlas2 (+20 more)

### Community 52 - "CortexGraph.tsx"
Cohesion: 0.10
Nodes (28): @react-sigma/core, @react-sigma/layout-forceatlas2, sigma, @sigma/node-square, AGENTS, DOMAINS, eventColor(), getExecutiveNeurons() (+20 more)

### Community 53 - "KnowledgeGraphStore"
Cohesion: 0.15
Nodes (4): _acquire(), KnowledgeGraphStore, _sanitize(), _with_timeout()

### Community 54 - "event_to_markdown"
Cohesion: 0.11
Nodes (9): _resolve_maintainer_enum(), CIAnalysis, get_event_document(), _esc(), _esc_join(), event_to_markdown(), get_github_auth(), maintainer_env_key() (+1 more)

### Community 57 - "llm_error_classifier.py"
Cohesion: 0.13
Nodes (9): _extract_status_code(), _has_non_retryable_cause(), _is_google_auth_transport_error(), is_rate_limit(), is_transient(), is_transient_llm_error_turn(), _iter_exception_chain(), _matches_mro() (+1 more)

### Community 58 - "server.js"
Cohesion: 0.09
Nodes (18): { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, ensureEventDocument(), fs, path, stageEventDocument(), fetchEventDocument(), fs, { handleRequest } (+10 more)

### Community 59 - "StateWatcher"
Cohesion: 0.10
Nodes (4): PollFn, _QueueEntry, StateWatcher, _Subscription

### Community 62 - "PulseBatch"
Cohesion: 0.10
Nodes (4): PulseBatch, PulsePort, PulseObserver, PulseTracker

### Community 64 - "create_schedule"
Cohesion: 0.08
Nodes (5): create_schedule(), delete_schedule(), get_schedule(), list_schedules(), toggle_schedule()

### Community 65 - "NodeInspector.tsx"
Cohesion: 0.13
Nodes (22): getClosedEvents(), ArchitectureEvent, ArgoCDOperation, EVENT_LABELS, EventItem(), EventItemProps, healthTone(), lastOperationSummary() (+14 more)

### Community 66 - "reconcile.py"
Cohesion: 0.15
Nodes (11): sanitize_redis_port(), generate_phase_tool_map(), _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers() (+3 more)

### Community 68 - "gemini_client.py"
Cohesion: 0.10
Nodes (11): _append_user_turn(), _clone_part_with_sig(), _clone_part_with_text(), _coerce_part(), _decode_sig_bytes(), _is_function_response_part(), _parse_drain_timeout(), _strip_user_thought_signature() (+3 more)

### Community 70 - "dependencies"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 72 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 73 - "claude-guard.js"
Cohesion: 0.14
Nodes (18): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+10 more)

### Community 76 - "JarvisPeerPort"
Cohesion: 0.09
Nodes (3): BrainLifecyclePort, BroadcastPort, JarvisPeerPort

### Community 78 - "sanitize_untrusted_line"
Cohesion: 0.17
Nodes (14): _build_closed_block(), build_event_header(), _build_identity_block(), _build_journal_block(), _build_mermaid_block(), build_operational_briefing(), _build_related_block(), _build_subject_block() (+6 more)

### Community 79 - "AsyncGitHubClient"
Cohesion: 0.17
Nodes (5): AsyncGitHubClient, _handle_rate_limit(), _paginate_github_get(), parse_github_next_link(), _safe_parse_int()

### Community 81 - "FlowHistoryPage.tsx"
Cohesion: 0.23
Nodes (16): recharts, getFlowHistory(), FlowSnapshot, FlowHistoryPage(), RANGES, SparkCard(), SparkCardProps, formatTime() (+8 more)

### Community 82 - "tool_router.py"
Cohesion: 0.10
Nodes (4): emit_tool_result(), IdleTimeoutPort, IncidentAdapterPort, StateWatcherPort

### Community 84 - "cli-setup.js"
Cohesion: 0.13
Nodes (18): { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync }, filterSkillsByMode() (+10 more)

### Community 86 - "ArchitectureEvent"
Cohesion: 0.13
Nodes (3): ArchitectureEvent, list_events(), MetricsRepository

### Community 87 - "devDependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 88 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 89 - "gemini-sidecar/package.json"
Cohesion: 0.11
Nodes (18): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+10 more)

### Community 92 - "jira.py"
Cohesion: 0.16
Nodes (7): approve_mission(), dismiss_mission(), _infer_phase(), _jira_config(), list_missions(), reanalyze_mission(), retry_mission()

### Community 93 - "get_report"
Cohesion: 0.11
Nodes (6): get_report(), list_reports(), reports_spa_no_slash(), reports_spa_with_slash(), search_reports(), _serve_spa()

### Community 94 - ".list_observations"
Cohesion: 0.12
Nodes (3): get_event_observations(), get_global_observations(), export_observations()

### Community 95 - "get_quota_tracker"
Cohesion: 0.11
Nodes (3): get_quota_tracker(), llm_stats(), receive_telemetry()

### Community 96 - "_sanitize_analysis_text"
Cohesion: 0.12
Nodes (9): _clamp_confidence(), _prepare_console_tail(), _redact_match(), _redact_secrets_in_text(), _sanitize_analysis_text(), _sanitize_console_tail(), _strip_newlines(), _validate_analysis() (+1 more)

### Community 98 - "ShiftsPage.tsx"
Cohesion: 0.23
Nodes (16): getCurrentShift(), getShiftDetail(), getShiftsList(), ShiftReportFull, ShiftReportSummary, FailedClusterBadge(), getISOWeek(), getWeekDates() (+8 more)

### Community 99 - "catalog-skills.js"
Cohesion: 0.16
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 102 - "._feedback_reject_reason"
Cohesion: 0.14
Nodes (6): _bot_login(), _csv_env(), _consider(), _mention_pattern(), _review_ignore_logins(), _review_trusted_associations()

### Community 111 - "JenkinsPlatformPort"
Cohesion: 0.13
Nodes (4): BuildDetails, JenkinsPlatformPort, JobRunState, ViewScanResult

### Community 117 - "._send_turn_to_thread"
Cohesion: 0.17
Nodes (5): extract_tables(), _replace(), get_agent_notification_text(), get_turn_attachment_color(), _md_table_to_block_kit()

### Community 120 - "handlers_planning.py"
Cohesion: 0.23
Nodes (7): _auto_complete_step(), _canonical_role(), handle_create_plan(), handle_get_plan_progress(), _is_failed_turn(), _is_orchestrator_turn(), _normalize_step_id()

### Community 123 - "._process_candidates"
Cohesion: 0.15
Nodes (3): _flood_service_key(), _outage_service_key(), _service_key()

### Community 124 - "._register_handlers"
Cohesion: 0.19
Nodes (4): handle_approve(), handle_approve_sha(), handle_home_create_event(), handle_reject()

### Community 126 - "analyzeTokens"
Cohesion: 0.19
Nodes (13): analyzeString(), analyzeTokens(), assignName(), base(), combineCategories(), configEnvGuard(), configFileWriteGuard(), hasSubseq() (+5 more)

### Community 127 - "generate_map.py"
Cohesion: 0.19
Nodes (5): _enumerate_gates(), _GateInfo, _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 130 - "._extract_context_flags"
Cohesion: 0.15
Nodes (3): compute_dispatch_backpressure(), ContextFlags, _safe_int_env()

### Community 134 - "cortex-pulse-handler.ts"
Cohesion: 0.21
Nodes (11): graphology, DEFAULT_TYPE_BUDGET, evictLru(), KNOWLEDGE_RING, KNOWLEDGE_RING_TYPES, KnowledgeNodeAttributes, knowledgeRingColor(), knowledgeRingLabel() (+3 more)

### Community 140 - "adf_to_markdown"
Cohesion: 0.32
Nodes (7): adf_to_markdown(), _apply_marks(), _children(), _render(), _render_list(), _render_list_item(), _render_table_like()

### Community 141 - "testSetup.ts"
Cohesion: 0.18
Nodes (5): @tailwindcss/vite, @testing-library/react, vite, @vitejs/plugin-react, vitest

### Community 143 - "is_defer_event_available"
Cohesion: 0.18
Nodes (6): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 147 - "NeuronInfoPanel.tsx"
Cohesion: 0.29
Nodes (10): asNumber(), asString(), asStringArray(), Badge(), describeNeuron(), Hdr(), NeuronInfoPanel(), AGENT_NEURON_COLORS (+2 more)

### Community 148 - "gitGuard"
Cohesion: 0.29
Nodes (10): bareBranchProtected(), configWriteGuard(), externalGitCommand(), gitGuard(), gitQuery(), isProtected(), normRef(), pushGuard() (+2 more)

### Community 149 - "parseShell"
Cohesion: 0.33
Nodes (10): bodySubstitutions(), decodeAnsiC(), isArrayAssignPrefix(), isWordStart(), matchBacktick(), matchParen(), parseShell(), readHeredocStart() (+2 more)

### Community 152 - "entity_extractor.py"
Cohesion: 0.33
Nodes (5): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship

### Community 154 - "has_unevaluated_close_blocker"
Cohesion: 0.22
Nodes (5): has_unevaluated_close_blocker(), _pred_jarvis_response(), _pred_unevaluated_close(), is_jarvis_acknowledgment(), is_stabilization_wake()

### Community 156 - "knowledge_graph_api.py"
Cohesion: 0.31
Nodes (4): get_kg_store(), get_service_detail(), get_stats(), list_services()

### Community 158 - "classifyTool"
Cohesion: 0.31
Nodes (9): apiTokens(), apiWriteNeedsGuard(), branchValues(), classifyTool(), hasOpaqueTarget(), httpGuard(), httpMethod(), isReadMethod() (+1 more)

### Community 171 - "validate-mutations.sh"
Cohesion: 0.57
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

### Community 174 - "_format_graph_context"
Cohesion: 0.38
Nodes (3): _format_graph_context(), _parse_props(), _sanitize()

### Community 178 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 179 - "state.js"
Cohesion: 0.33
Nodes (4): { AGENT_ROLE }, _blackboardTurns, _inboundMessages, _teammateMessages

### Community 183 - "build_gate_context"
Cohesion: 0.33
Nodes (3): build_gate_context(), conversation_has_decayed_turns(), _decay_payload_len()

### Community 191 - "handle_recall_pruned_turns"
Cohesion: 0.50
Nodes (3): _coerce_turn_int(), handle_recall_pruned_turns(), _parse_turn_int()

### Community 196 - "classify"
Cohesion: 0.50
Nodes (4): classify(), main(), shellCategory(), shellNeedsGuard()

## Knowledge Gaps
- **13 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+8 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2525 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **165 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `brain.py`, `main.py`, `queue.py`, `nightwatcher_tools.py`, `auth.py`, `Brain`, `AgentRegistry`, `headhunter_github.py`, `prompt_sanitize.py`, `EventDocument`, `.get_graph_data`, `slack.py`, `ConversationTurn`, `TopologyRepository`, `observations_reporter.py`, `event_to_markdown`, `LiveAPIAdapter`, `HeadhunterJira`, `create_schedule`, `DashboardWSAdapter`, `tool_router.py`, `ArchitectureEvent`, `jira.py`, `get_report`, `.list_observations`, `.__init__`, `ScheduleRepository`, `._validate_gitlab_ids`, `get_all_journal`, `list_shifts`, `_is_event_closed_or_missing`, `ConversationMessage`, `._update_event_vcs_context`, `update_schedule`, `update_notebook_note`, `rename_observation`, `._restage_pending_signal`, `._stage_pending_signal`, `get_notebook`, `._count_pending`, `.is_github_pr_feedback_seen`, `.cleanup_stale_services`, `._downsample_snapshots`, `._drain_pending`, `.drain_notes`, `.get_edge_metadata`, `report_tampering`, `.add_edge_with_metadata`, `.clear_drained_notes`, `.clear_escalation_flag`, `.clear_event_approval`, `.clear_jenkins_last_outage_fingerprint`, `.create_conversation`, `.dequeue_event`, `.get_active_events_with_status`, `.get_all_gitlab_mr_shas`, `.get_escalation_flag`, `.get_event_by_slack_thread`, `.get_flow_metrics`, `.get_github_issue_processed`, `.get_handoff_reports`, `.get_jenkins_last_outage_fingerprint`, `.get_latest_flow_snapshot`, `.get_or_set_github_review_response_watermark`, `.get_recent_closed_for_service`, `.get_shadow_event_ids`, `.get_shadow_interventions`, `.has_wakeup_notes_cursor`, `.is_feedback_sent`, `.is_wakeup_note_seen`, `.mark_github_pr_feedback_cap_notified`, `.mark_turns_status`, `.persist_flow_snapshot`, `.pop_due_schedule`, `.refresh_inflight_ttl`, `.requeue_inflight`, `.set_escalation_flag`, `.set_github_pr_feedback_cursor`, `.set_slack_mapping`?**
  _High betweenness centrality (0.115) - this node is a cross-community bridge._
- **Are the 80 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 80 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `brain.py` be split into smaller, more focused modules?**
  _Cohesion score 0.023040482342807925 - nodes in this community are weakly interconnected._
- **Why does `Brain` connect `Brain` to `brain.py`, `._extract_context_flags`, `BlackboardState`, `queue.py`, `main.py`, `._run_agent_task`, `AgentRegistry`, `ReconcileScheduler`, `prompt_sanitize.py`, `._process_with_llm`, `EventDocument`, `BrainSkillLoader`, `slack.py`, `ConversationTurn`, `._detect_repetition_collapse`, `StateWatcher`, `PulseBatch`, `DashboardWSAdapter`, `._build_contents`, `JarvisPeerPort`, `ReflexSearcher`, `get_quota_tracker`, `.__init__`, `IdleTimeoutManager`?**
  _High betweenness centrality (0.061) - this node is a cross-community bridge._
- **Are the 20 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Should `client.ts` be split into smaller, more focused modules?**
  _Cohesion score 0.029350930759381465 - nodes in this community are weakly interconnected._