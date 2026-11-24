# Graph Report - Blackboard  (2026-11-24)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 5904 nodes · 13361 edges · 245 communities (106 shown, 139 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 1018 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `334f05f8`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BlackboardState
- models.py
- client.ts
- brain.py
- EventSidebar.tsx
- time
- queue.py
- logging
- GitLabPlatform
- useCortexData.ts
- tool_gates.py
- os
- EventRepository
- Brain
- main.py
- ReconcileScheduler
- ._run_agent_task
- auth.py
- http-handler.js
- App.tsx
- jenkins-mcp.js
- colors.ts
- lucide-react
- react
- Headhunter
- BrainSkillLoader
- TurnBubble.tsx
- ToolContext
- ._process_event_inner
- EventDocument
- WorkspaceInspector.tsx
- StreamGrid.tsx
- slack.py
- _BrainToolContext
- merge-guard.js
- Service
- ._process_with_llm
- cli-executor.js
- storage-recycler.js
- GeminiAdapter
- llm/__init__.py
- dispatch.py
- AgentClient
- BoolOutcome
- types.py
- ArchitectureGraph.tsx
- GitHubPlatform
- TimeKeeperPage.tsx
- Aligner
- SlackChannel
- ws-client.js
- .append_and_broadcast
- VcsPlatformPort
- ui/package.json
- CortexGraph.tsx
- handlers_integration.py
- NodeInspector.tsx
- .list_observations
- IdleTimeoutManager
- Any
- ._drain_platform_phase_ab
- KnowledgeGraphStore
- LiveAPIAdapter
- AgentRegistry
- llm_error_classifier.py
- server.js
- StateWatcher
- ConversationTurn
- JenkinsObserver
- cognitive_graph.py
- JenkinsAdapter
- PulseBatch
- ArgoCDObserver
- create_schedule
- reconcile.py
- JarvisPeerPort
- ._poll_issues
- gemini_client.py
- KargoObserver
- TopologyRepository
- dependencies
- lifespan
- compilerOptions
- claude-guard.js
- ._build_contents
- .poll_and_process
- AsyncGitHubClient
- GitHubAppAuth
- FlowHistoryPage.tsx
- ._authorize_plan_decision
- cli-setup.js
- ReflexSearcher
- spawn_event_namer_task
- start_headhunter_task
- HeadhunterJira
- devDependencies
- compilerOptions
- gemini-sidecar/package.json
- Archivist
- EphemeralProvisioner
- .fetch_context
- HeadhunterCircuitBreaker
- generate_observations_report
- get_report
- handle_classify_event
- headhunter_pending_todos
- ObservationRepository
- ShiftsPage.tsx
- catalog-skills.js
- handle_notify_user_slack
- ._feedback_reject_reason
- EscalationRepository
- DashboardWSAdapter
- VectorStore
- TokenMeter
- MultiInstallationManager
- JenkinsPlatformPort
- ._poll_and_stage
- ._normalize_issue
- OIDCKeyAdapter
- KubernetesSpawnHealthAdapter
- QuotaTracker
- observations_reporter.py
- ._connect
- ScheduleRepository
- SlackAccessGate
- analyzeTokens
- generate_map.py
- FilterRule
- .scroll
- ._extract_context_flags
- ._poll_pr_feedback
- NeuronInfoPanel.tsx
- ._drain_once
- ._process_message
- testSetup.ts
- is_defer_event_available
- ScheduleCreateRequest
- create_chat_event
- GitLabTokenAuth
- CiContextCard.tsx
- cortex-constants.ts
- gitGuard
- parseShell
- generate_event_title
- ._post_agent_recall
- entity_extractor.py
- ._clear_recovered_group_flags
- has_unevaluated_close_blocker
- knowledge_graph_api.py
- HeadhunterItemActionRequest
- spawn_health.py
- classifyTool
- SpawnPollResult
- _get_canonical_or_alias
- _is_event_closed_or_missing
- ._evaluate_health
- ._register_handlers
- ConversationMessage
- TimeKeeperObserver
- CortexRepository
- adf_to_markdown
- validate-mutations.sh
- update_schedule
- ._detect_repetition_collapse
- .has_reeval_signal
- update_notebook_note
- get_current_shift
- llm_stats
- scripts
- state.js
- DispatchMetrics
- build_gate_context
- list_failed_stages
- ._wait_for_registration
- agent_ws_endpoint
- submit_feedback
- get_notebook
- classify
- require-results.sh
- get_intermediate_tools
- report_tampering
- get_event_flow
- _require_jira_mutation_auth
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
1. `BlackboardState` - 322 edges
2. `Brain` - 170 edges
3. `ConversationTurn` - 136 edges
4. `ToolContext` - 103 edges
5. `GateContext` - 99 edges
6. `GitHubPlatform` - 99 edges
7. `Headhunter` - 89 edges
8. `EventDocument` - 89 edges
9. `EventRepository` - 87 edges
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

## Communities (245 total, 139 thin omitted)

### Community 1 - "models.py"
Cohesion: 0.03
Nodes (38): require_auth(), require_obs_admin(), get_blackboard(), AppNode, ArchitectureEvent, ChatRequest, ChatResponse, EventInput (+30 more)

### Community 2 - "client.ts"
Cohesion: 0.03
Nodes (116): @tanstack/react-query, ApiError, bulkDeleteObservations(), createChatEvent(), deleteNote(), deleteObservation(), exportObservations(), ExtractedCorrection (+108 more)

### Community 3 - "brain.py"
Cohesion: 0.03
Nodes (55): _batch_is_terminal_for_flush(), _close_unanswered_fc(), _contents_have_pruned_or_decayed(), _is_close_phase_fc(), _apply_sibling_signature(), build_function_response(), build_single_function_response(), compress_contents() (+47 more)

### Community 4 - "EventSidebar.tsx"
Cohesion: 0.04
Nodes (113): getActiveEvents(), getAlignerPending(), getClosedEvents(), getEventDocument(), getHeadhunterPending(), getHeadhunterStatus(), getJenkinsPending(), getWaitingApprovalEvents() (+105 more)

### Community 5 - "time"
Cohesion: 0.03
Nodes (41): JiraIncidentAdapter, _heartbeat(), QuotaExhaustedError, RequestExceedsBurstError, _stale_reservation_ttl_s(), Pulse, PulseContext, ShiftIncident (+33 more)

### Community 6 - "queue.py"
Cohesion: 0.03
Nodes (60): can_rename_event(), get_user_from_request(), resolve_approval_identity(), get_archivist(), get_brain(), EventStatus, _acquire_hh_poll_lock(), aligner_pending_items() (+52 more)

### Community 7 - "logging"
Cohesion: 0.03
Nodes (24): _annotation_replace(), _strip_pipeline_annotations(), _sanitize_lesson_text(), _format_graph_context(), get_graph_context(), _parse_props(), _sanitize(), translate_to_lookups() (+16 more)

### Community 8 - "GitLabPlatform"
Cohesion: 0.05
Nodes (5): _get_allowed_mention_authors(), GitLabPlatform, _reconcile_synthetic(), _check_one(), _valid_positive_int()

### Community 9 - "useCortexData.ts"
Cohesion: 0.06
Nodes (71): getCognitiveGraph(), getCortexActivity(), getEventPulses(), getKGServiceDetail(), getKGServices(), getKGStats(), getKnowledgeById(), getMemory() (+63 more)

### Community 10 - "tool_gates.py"
Cohesion: 0.05
Nodes (79): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+71 more)

### Community 11 - "os"
Cohesion: 0.05
Nodes (24): _iso(), _parse_ts(), _get_static_maintainer_emails(), PlatformBreakerStatus, PlatformQueueItem, PlatformSnapshot, _safe_int(), list_incidents() (+16 more)

### Community 14 - "main.py"
Cohesion: 0.04
Nodes (27): get_aligner(), get_architect(), get_argocd_observer(), get_developer(), get_kargo_observer(), get_report_client(), get_sysadmin(), set_agents() (+19 more)

### Community 15 - "ReconcileScheduler"
Cohesion: 0.04
Nodes (8): get_quota_tracker(), FlowCollector, FairQueue, ReconcileScheduler, Trigger, QueueTrigger, ResyncTrigger, StalenessGuard

### Community 16 - "._run_agent_task"
Cohesion: 0.05
Nodes (7): on_huddle(), on_progress(), on_huddle(), on_progress(), _is_external_input_turn(), _select_dispatch_tier(), get_registry_and_bridge()

### Community 17 - "auth.py"
Cohesion: 0.05
Nodes (22): can_append_message(), can_approve_event(), can_override_domain(), _claims_to_user(), get_user_from_slack(), get_user_from_websocket(), _normalize_email(), prompt_display_name() (+14 more)

### Community 18 - "http-handler.js"
Cohesion: 0.08
Nodes (62): is429Error(), registerMCPsAndHooks(), resolveCommand(), writeAgyMcpServer(), writeClaudeMcpServer(), parsePositiveInt(), buildArgoCDMcpConfig(), createAppJWT() (+54 more)

### Community 19 - "App.tsx"
Cohesion: 0.06
Nodes (48): oidc-client-ts, react-dom, dismissProposals(), EnhancementProposal, getHandoffReports(), getProposals(), getWSAuthFailureCallback(), HandoffReport (+40 more)

### Community 20 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 21 - "colors.ts"
Cohesion: 0.07
Nodes (36): getReport(), getReports(), ReportFull, ReportMeta, CompactCardStrip(), EventHistory(), TimeRange, ViewMode (+28 more)

### Community 22 - "lucide-react"
Cohesion: 0.07
Nodes (44): lucide-react, react-router-dom, getAgents(), getKargoStages(), updateEventTitle(), AgentRegistryEntry, ApprovalErrorKind, KargoStageStatus (+36 more)

### Community 23 - "react"
Cohesion: 0.08
Nodes (51): react, applyLessons(), correctMemory(), createKnowledge(), createLesson(), deleteKnowledge(), deleteLesson(), extractLessons() (+43 more)

### Community 24 - "Headhunter"
Cohesion: 0.06
Nodes (3): Headhunter, HeadhunterOperationError, redact_error_text()

### Community 25 - "BrainSkillLoader"
Cohesion: 0.05
Nodes (5): _inject_evidence_paths(), BrainSkillLoader, _SkillCorpus, _wrap_section(), BrainIntrospectionPort

### Community 26 - "TurnBubble.tsx"
Cohesion: 0.08
Nodes (46): @uiw/react-markdown-preview, approveEvent(), closeEvent(), enforceCasualDomain(), getEventReport(), rejectEvent(), submitFeedback(), MessageStatus (+38 more)

### Community 27 - "ToolContext"
Cohesion: 0.08
Nodes (15): handle_message_agent(), handle_reply_to_agent(), handle_report_incident(), handle_select_agent(), _resolve_escalation_scope(), _sticky_work_style(), handle_search_open_incidents(), handle_close_event() (+7 more)

### Community 28 - "._process_event_inner"
Cohesion: 0.04
Nodes (8): _compute_processed_up_to(), _has_non_user_turns(), _is_automated_nudge(), _is_participant_turn(), _is_seed_turn(), _is_steering_turn(), _sanitize_error_text(), get_token_meter()

### Community 30 - "WorkspaceInspector.tsx"
Cohesion: 0.08
Nodes (41): ConversationTurn, TokenUsageDict, BORDER_COLOR, PlanProgress(), PlanProgressProps, STATUS_ICON, DiffFile, DiffHunk (+33 more)

### Community 31 - "StreamGrid.tsx"
Cohesion: 0.08
Nodes (41): AgentStreamCard(), AgentStreamCardProps, MessageCards(), Dashboard(), GridTile(), GridTileProps, TileType, InlineMarkdownViewer() (+33 more)

### Community 32 - "slack.py"
Cohesion: 0.06
Nodes (20): build_access_denied_home_view(), build_home_tab_view(), _context_line(), create_feedback_block(), extract_tables(), _replace(), format_plan_block(), format_task_card() (+12 more)

### Community 34 - "merge-guard.js"
Cohesion: 0.04
Nodes (46): API_VALUED, ARGO_MUTATING, ARGO_READ_SUB, ARGO_READ_TOP, BODY_FLAG, BROWSER_READ, CTX, ENV_BUILTINS (+38 more)

### Community 35 - "Service"
Cohesion: 0.06
Nodes (7): Service, get_event_document(), list_events(), get_mermaid_diagram(), get_service_details(), get_topology(), list_services()

### Community 36 - "._process_with_llm"
Cohesion: 0.05
Nodes (4): _BatchContext, _ensure_recall_tool_if_needed(), _QuotaShedState, _retry_backoff_delay()

### Community 37 - "cli-executor.js"
Cohesion: 0.09
Nodes (37): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, MAX_TASK_WALL_MS, MAX_TIMER_MS, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS, STORAGE_PRETASK_TIMEOUT_MS, resolveStorageRoot }, buildCLICommand(), buildTimeoutResult(), { checkAndRecycleStorage, pinTaskCwd, unpinTaskCwd }, CLAUDE_JSON_PATH, cp, createInactivityWatchdog(), executeCLI() (+29 more)

### Community 38 - "storage-recycler.js"
Cohesion: 0.08
Nodes (37): withTaskStorage(), MAX_TASK_WALL_MS, parseTimerMs(), resolveStorageRoot(), resolveTimeoutMs(), ROLE_TIMEOUTS, STORAGE_ACTIVITY_HEARTBEAT_MS, STORAGE_MAX_TIER3_DELETIONS (+29 more)

### Community 39 - "GeminiAdapter"
Cohesion: 0.10
Nodes (8): _attach_signature_to_parts(), _extract_call_syntax(), _extract_part_signature(), GeminiAdapter, _is_empty_sig_carrier(), _part_has_fc(), _sanitize_candidate_parts(), strip_control_tokens()

### Community 40 - "llm/__init__.py"
Cohesion: 0.08
Nodes (7): ClaudeAdapter, _parse_tpm_limit(), FunctionCall, LLMChunk, LLMPort, LLMResponse, TokenUsage

### Community 41 - "dispatch.py"
Cohesion: 0.09
Nodes (13): _build_prompt(), _check_security(), consume_wake_task(), _consume(), _dispatch_timeout_s(), dispatch_to_agent(), _consume_queue(), _sanitize_stdout() (+5 more)

### Community 42 - "AgentClient"
Cohesion: 0.07
Nodes (4): Architect, AgentClient, Developer, SysAdmin

### Community 44 - "types.py"
Cohesion: 0.08
Nodes (18): derive_llm_priority(), _get_timeout_env_warned(), _get_timeout_order_warned(), is_partial_control_token(), LLMStreamInterChunkTimeoutError, LLMStreamTimeoutError, LLMStreamTotalTimeoutError, LLMStreamTTFBTimeoutError (+10 more)

### Community 45 - "ArchitectureGraph.tsx"
Cohesion: 0.09
Nodes (28): @dagrejs/dagre, @xyflow/react, HealthStatus, NodeType, AppNodeData, applyDagreLayout(), applyGridLayout(), applyLayout() (+20 more)

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

### Community 51 - ".append_and_broadcast"
Cohesion: 0.13
Nodes (22): _safe_int(), _coerce_turn_int(), handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_recall_pruned_turns(), _parse_turn_int(), handle_ask_release_ai() (+14 more)

### Community 53 - "ui/package.json"
Cohesion: 0.08
Nodes (29): autoprefixer, cronstrue, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, graphology-layout-forceatlas2 (+21 more)

### Community 54 - "CortexGraph.tsx"
Cohesion: 0.11
Nodes (29): graphology, @react-sigma/core, @react-sigma/layout-forceatlas2, sigma, @sigma/node-square, eventColor(), getStructuralEdges(), DEFAULT_TYPE_BUDGET (+21 more)

### Community 55 - "handlers_integration.py"
Cohesion: 0.14
Nodes (16): _get_jira_reporter(), handle_comment_jira_issue(), handle_refresh_github_context(), _emit(), handle_refresh_gitlab_context(), handle_refresh_kargo_context(), _is_positive_int(), _parse_poll_interval() (+8 more)

### Community 56 - "NodeInspector.tsx"
Cohesion: 0.11
Nodes (25): getEvents(), ArchitectureEvent, ArgoCDOperation, ActivityStream(), ArchitectureGraph(), EVENT_LABELS, EventItem(), EventItemProps (+17 more)

### Community 57 - ".list_observations"
Cohesion: 0.07
Nodes (5): get_all_journal(), get_service_journal(), get_event_observations(), get_global_observations(), export_observations()

### Community 59 - "Any"
Cohesion: 0.12
Nodes (3): VcsContext, _NoAliasSafeLoader, _validate_plan_yaml()

### Community 60 - "._drain_platform_phase_ab"
Cohesion: 0.10
Nodes (6): _maybe_refresh_snapshot(), _on_gh_phase_b_created(), _iref(), _process_issue(), _try_queue_issue(), _on_gl_phase_b_created()

### Community 61 - "KnowledgeGraphStore"
Cohesion: 0.15
Nodes (4): _acquire(), KnowledgeGraphStore, _sanitize(), _with_timeout()

### Community 63 - "AgentRegistry"
Cohesion: 0.10
Nodes (3): AgentConnection, AgentRegistry, agent_websocket_handler()

### Community 64 - "llm_error_classifier.py"
Cohesion: 0.13
Nodes (9): _extract_status_code(), _has_non_retryable_cause(), _is_google_auth_transport_error(), is_rate_limit(), is_transient(), is_transient_llm_error_turn(), _iter_exception_chain(), _matches_mro() (+1 more)

### Community 65 - "server.js"
Cohesion: 0.09
Nodes (18): { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, ensureEventDocument(), fs, path, stageEventDocument(), fetchEventDocument(), fs, { handleRequest } (+10 more)

### Community 66 - "StateWatcher"
Cohesion: 0.10
Nodes (4): PollFn, _QueueEntry, StateWatcher, _Subscription

### Community 67 - "ConversationTurn"
Cohesion: 0.12
Nodes (10): emit_tool_result(), handle_google_web_search(), _auto_complete_step(), _canonical_role(), handle_create_plan(), handle_get_plan_progress(), _is_failed_turn(), _is_orchestrator_turn() (+2 more)

### Community 69 - "cognitive_graph.py"
Cohesion: 0.11
Nodes (11): get_pulse_tracker(), dismiss_proposals(), DismissRequest, get_all_shadow_interventions(), get_cognitive_graph(), get_cortex_activity(), get_cortex_status(), get_event_shadow_interventions() (+3 more)

### Community 71 - "PulseBatch"
Cohesion: 0.10
Nodes (4): PulseBatch, PulsePort, PulseObserver, PulseTracker

### Community 73 - "create_schedule"
Cohesion: 0.08
Nodes (5): create_schedule(), delete_schedule(), get_schedule(), list_schedules(), toggle_schedule()

### Community 74 - "reconcile.py"
Cohesion: 0.15
Nodes (11): sanitize_redis_port(), generate_phase_tool_map(), _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers() (+3 more)

### Community 75 - "JarvisPeerPort"
Cohesion: 0.08
Nodes (3): BrainLifecyclePort, BroadcastPort, JarvisPeerPort

### Community 77 - "gemini_client.py"
Cohesion: 0.10
Nodes (11): _append_user_turn(), _clone_part_with_sig(), _clone_part_with_text(), _coerce_part(), _decode_sig_bytes(), _is_function_response_part(), _parse_drain_timeout(), _strip_user_thought_signature() (+3 more)

### Community 80 - "dependencies"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 82 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 83 - "claude-guard.js"
Cohesion: 0.14
Nodes (18): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+10 more)

### Community 86 - "AsyncGitHubClient"
Cohesion: 0.17
Nodes (5): AsyncGitHubClient, _handle_rate_limit(), _paginate_github_get(), parse_github_next_link(), _safe_parse_int()

### Community 88 - "FlowHistoryPage.tsx"
Cohesion: 0.23
Nodes (16): recharts, getFlowHistory(), FlowSnapshot, FlowHistoryPage(), RANGES, SparkCard(), SparkCardProps, formatTime() (+8 more)

### Community 89 - "._authorize_plan_decision"
Cohesion: 0.12
Nodes (4): _PlanDecision, handle_approve(), handle_approve_sha(), handle_reject()

### Community 90 - "cli-setup.js"
Cohesion: 0.13
Nodes (18): { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync }, filterSkillsByMode() (+10 more)

### Community 92 - "spawn_event_namer_task"
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

### Community 102 - "generate_observations_report"
Cohesion: 0.11
Nodes (8): render_pdf(), bulk_delete_observations(), BulkDeleteRequest, delete_observation(), generate_observations_report(), rename_observation(), RenameRequest, ReportRequest

### Community 103 - "get_report"
Cohesion: 0.11
Nodes (6): get_report(), list_reports(), reports_spa_no_slash(), reports_spa_with_slash(), search_reports(), _serve_spa()

### Community 104 - "handle_classify_event"
Cohesion: 0.12
Nodes (5): handle_classify_event(), handle_request_user_approval(), IdleTimeoutPort, IncidentAdapterPort, StateWatcherPort

### Community 107 - "headhunter_pending_todos"
Cohesion: 0.18
Nodes (12): _extract_snapshot_items(), _github_active_item(), headhunter_pending_todos(), _normalized_row_keys(), headhunter_platform_status(), _match_snapshot_item(), _pending_row_keys(), _read_headhunter_snapshot_safe() (+4 more)

### Community 109 - "ShiftsPage.tsx"
Cohesion: 0.23
Nodes (16): getCurrentShift(), getShiftDetail(), getShiftsList(), ShiftReportFull, ShiftReportSummary, FailedClusterBadge(), getISOWeek(), getWeekDates() (+8 more)

### Community 110 - "catalog-skills.js"
Cohesion: 0.16
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 112 - "handle_notify_user_slack"
Cohesion: 0.12
Nodes (8): _alert_wrapper_retrigger(), _do_retrigger(), handle_notify_user_slack(), handle_retrigger_jenkins_build(), jenkins_retrigger_cooldown_key(), _resolve_maintainer_enum(), _resolve_slack_user(), build_event_report_md()

### Community 113 - "._feedback_reject_reason"
Cohesion: 0.14
Nodes (6): _bot_login(), _csv_env(), _consider(), _mention_pattern(), _review_ignore_logins(), _review_trusted_associations()

### Community 120 - "JenkinsPlatformPort"
Cohesion: 0.13
Nodes (4): BuildDetails, JenkinsPlatformPort, JobRunState, ViewScanResult

### Community 128 - "observations_reporter.py"
Cohesion: 0.21
Nodes (7): _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), _sample_points(), _summarize()

### Community 134 - "analyzeTokens"
Cohesion: 0.19
Nodes (13): analyzeString(), analyzeTokens(), assignName(), base(), combineCategories(), configEnvGuard(), configFileWriteGuard(), hasSubseq() (+5 more)

### Community 135 - "generate_map.py"
Cohesion: 0.19
Nodes (5): _enumerate_gates(), _GateInfo, _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 138 - "._extract_context_flags"
Cohesion: 0.15
Nodes (3): compute_dispatch_backpressure(), ContextFlags, _safe_int_env()

### Community 140 - "NeuronInfoPanel.tsx"
Cohesion: 0.24
Nodes (12): KGServiceDetail, asNumber(), asString(), asStringArray(), Badge(), describeNeuron(), Hdr(), NeuronInfoPanel() (+4 more)

### Community 147 - "testSetup.ts"
Cohesion: 0.18
Nodes (5): @tailwindcss/vite, @testing-library/react, vite, @vitejs/plugin-react, vitest

### Community 148 - "is_defer_event_available"
Cohesion: 0.18
Nodes (6): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 150 - "create_chat_event"
Cohesion: 0.20
Nodes (3): ChatEventRequest, ChatEventResponse, create_chat_event()

### Community 152 - "CiContextCard.tsx"
Cohesion: 0.31
Nodes (9): CiContext, CiContextCardProps, ConsoleTailBlock(), FailedJobRow(), annotationReplacer(), PIPELINE_ANNOTATION_RE, REDACTION_TRIGGER_KEYWORDS, stripAnsi() (+1 more)

### Community 153 - "cortex-constants.ts"
Cohesion: 0.18
Nodes (10): AGENTS, DOMAINS, HEMISPHERE_X, NEURON_DESCRIPTIONS, PHASE_SKILL_FOLDERS, PHASE_TOOL_PRIORITY, PHASES, StructuralEdge (+2 more)

### Community 154 - "gitGuard"
Cohesion: 0.29
Nodes (10): bareBranchProtected(), configWriteGuard(), externalGitCommand(), gitGuard(), gitQuery(), isProtected(), normRef(), pushGuard() (+2 more)

### Community 155 - "parseShell"
Cohesion: 0.33
Nodes (10): bodySubstitutions(), decodeAnsiC(), isArrayAssignPrefix(), isWordStart(), matchBacktick(), matchParen(), parseShell(), readHeredocStart() (+2 more)

### Community 156 - "generate_event_title"
Cohesion: 0.22
Nodes (3): generate_event_title(), get_adapter(), _get_semaphore()

### Community 158 - "entity_extractor.py"
Cohesion: 0.33
Nodes (5): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship

### Community 161 - "has_unevaluated_close_blocker"
Cohesion: 0.22
Nodes (5): has_unevaluated_close_blocker(), _pred_jarvis_response(), _pred_unevaluated_close(), is_jarvis_acknowledgment(), is_stabilization_wake()

### Community 162 - "knowledge_graph_api.py"
Cohesion: 0.31
Nodes (4): get_kg_store(), get_service_detail(), get_stats(), list_services()

### Community 165 - "classifyTool"
Cohesion: 0.31
Nodes (9): apiTokens(), apiWriteNeedsGuard(), branchValues(), classifyTool(), hasOpaqueTarget(), httpGuard(), httpMethod(), isReadMethod() (+1 more)

### Community 176 - "adf_to_markdown"
Cohesion: 0.57
Nodes (7): adf_to_markdown(), _apply_marks(), _children(), _render(), _render_list(), _render_list_item(), _render_table_like()

### Community 177 - "validate-mutations.sh"
Cohesion: 0.57
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

### Community 183 - "get_current_shift"
Cohesion: 0.29
Nodes (3): get_current_shift(), get_shift_detail(), list_shifts()

### Community 185 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 186 - "state.js"
Cohesion: 0.33
Nodes (4): { AGENT_ROLE }, _blackboardTurns, _inboundMessages, _teammateMessages

### Community 192 - "build_gate_context"
Cohesion: 0.33
Nodes (3): build_gate_context(), conversation_has_decayed_turns(), _decay_payload_len()

### Community 203 - "classify"
Cohesion: 0.50
Nodes (4): classify(), main(), shellCategory(), shellNeedsGuard()

## Knowledge Gaps
- **13 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+8 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2595 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **139 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `observations_reporter.py`, `models.py`, `brain.py`, `ScheduleRepository`, `time`, `queue.py`, `logging`, `os`, `Brain`, `main.py`, `auth.py`, `create_chat_event`, `generate_event_title`, `EventDocument`, `slack.py`, `Service`, `_is_event_closed_or_missing`, `ConversationMessage`, `._update_event_vcs_context`, `update_schedule`, `.append_and_broadcast`, `update_notebook_note`, `get_current_shift`, `.list_observations`, `IdleTimeoutManager`, `LiveAPIAdapter`, `._get_ticket_nodes`, `ConversationTurn`, `._restage_pending_signal`, `._stage_pending_signal`, `submit_feedback`, `get_notebook`, `create_schedule`, `._downsample_snapshots`, `.is_github_pr_feedback_seen`, `.cleanup_stale_services`, `._commit_pending_signal`, `.drain_notes`, `.get_edge_metadata`, `lifespan`, `report_tampering`, `HeadhunterJira`, `generate_observations_report`, `get_report`, `headhunter_pending_todos`, `.append_journal`, `.record_observation`, `DashboardWSAdapter`, `._validate_gitlab_ids`?**
  _High betweenness centrality (0.080) - this node is a cross-community bridge._
- **Are the 81 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 81 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.01174884437596302 - nodes in this community are weakly interconnected._
- **Why does `ConversationTurn` connect `ConversationTurn` to `BlackboardState`, `models.py`, `brain.py`, `queue.py`, `logging`, `GitLabPlatform`, `os`, `._poll_pr_feedback`, `Brain`, `EventRepository`, `._run_agent_task`, `auth.py`, `create_chat_event`, `ToolContext`, `._process_event_inner`, `slack.py`, `._process_with_llm`, `GitHubPlatform`, `Aligner`, `SlackChannel`, `.append_and_broadcast`, `handlers_integration.py`, `LiveAPIAdapter`, `._build_contents`, `._authorize_plan_decision`, `spawn_event_namer_task`, `handle_classify_event`, `._tool_send_event_message`, `handle_notify_user_slack`, `DashboardWSAdapter`?**
  _High betweenness centrality (0.062) - this node is a cross-community bridge._
- **Are the 20 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Should `models.py` be split into smaller, more focused modules?**
  _Cohesion score 0.026470882029767256 - nodes in this community are weakly interconnected._