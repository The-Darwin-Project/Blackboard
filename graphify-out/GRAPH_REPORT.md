# Graph Report - Blackboard  (2026-11-22)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 5583 nodes · 12584 edges · 218 communities (112 shown, 106 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 975 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `b233e434`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BlackboardState
- main.py
- react
- ConversationTurn
- queue.py
- logging
- client.ts
- EventSidebar.tsx
- Brain
- os
- colors.ts
- App.tsx
- GitHubPlatform
- tool_gates.py
- Headhunter
- ._run_agent_task
- GitLabPlatform
- http-handler.js
- ReconcileScheduler
- models.py
- JenkinsObserver
- BrainSkillLoader
- jenkins-mcp.js
- ArchitectureGraph.tsx
- useMemory.ts
- brain.py
- Service
- EventEvidence
- cognitive_graph.py
- Aligner
- EventRepository
- SlackChannel
- ._process_with_llm
- GeminiAdapter
- _BrainToolContext
- merge-guard.js
- observations_mgmt.py
- context_parts.py
- OpsStateContext.tsx
- gemini_client.py
- cli-executor.js
- storage-recycler.js
- ScheduleCreateRequest
- EventDocument
- auth.py
- handlers_integration.py
- llm/__init__.py
- JenkinsAdapter
- jenkins_observer.py
- StreamGrid.tsx
- slack.py
- TimeKeeperPage.tsx
- ws-client.js
- ui/package.json
- AgentRegistry
- prompt.py
- StateWatcher
- TaskBridge
- ._resolve_client
- useCortexData.ts
- EventDrillDown.tsx
- KnowledgeGraphStore
- TopologyRepository
- CortexGraph.tsx
- LiveAPIAdapter
- llm_error_classifier.py
- server.js
- adf_to_markdown
- JarvisPeerPort
- .list_observations
- PulseBatch
- nightwatcher_tools.py
- ArgoCDObserver
- NightwatcherObserver
- KargoObserver
- dependencies
- reconcile.py
- event_to_markdown
- compilerOptions
- claude-guard.js
- DashboardWSAdapter
- ._build_contents
- HeadhunterCircuitBreaker
- AsyncGitHubClient
- GitHubAppAuth
- NeuronInfoPanel.tsx
- FlowHistoryPage.tsx
- .fetch_context
- cli-setup.js
- ReflexSearcher
- devDependencies
- compilerOptions
- nightwatcher.py
- gemini-sidecar/package.json
- Archivist
- EphemeralProvisioner
- start_headhunter_task
- _section
- get_report
- ObservationRepository
- ShiftsPage.tsx
- cortex/types.ts
- FloatingWindow.tsx
- catalog-skills.js
- state/ports.py
- EscalationRepository
- VectorStore
- TokenMeter
- MultiInstallationManager
- generate_map.py
- OIDCKeyAdapter
- KubernetesSpawnHealthAdapter
- IdleTimeoutManager
- graph_recall.py
- create_chat_event
- ServiceNode.tsx
- ._connect
- entity_extractor.py
- ScheduleRepository
- analyzeTokens
- .scroll
- ._extract_context_flags
- handlers_planning.py
- QuotaTracker
- IncidentAdapterPort
- ._process_message
- ._execute_function_call
- ._run_report_cart
- CortexLiveFeed.tsx
- testSetup.ts
- is_defer_event_available
- GitLabTokenAuth
- gitGuard
- parseShell
- ._tool_send_event_message
- ._post_agent_recall
- HeadhunterJira
- has_unevaluated_close_blocker
- knowledge_graph_api.py
- spawn_health.py
- classifyTool
- get_quota_tracker
- SpawnPollResult
- .has_reeval_signal
- _get_canonical_or_alias
- _is_event_closed_or_missing
- ._evaluate_health
- ConversationMessage
- TimeKeeperObserver
- CortexRepository
- validate-mutations.sh
- QuotaExhaustedError
- ._run_analysis_loop
- scripts
- state.js
- DispatchMetrics
- _append_user_turn
- build_gate_context
- ._wait_for_registration
- get_notebook
- refine_instructions
- classify
- _patch_enum_fields
- require-results.sh
- get_intermediate_tools
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
1. `BlackboardState` - 299 edges
2. `Brain` - 168 edges
3. `ConversationTurn` - 131 edges
4. `ToolContext` - 103 edges
5. `GateContext` - 99 edges
6. `EventDocument` - 88 edges
7. `react` - 85 edges
8. `GitHubPlatform` - 73 edges
9. `lifespan()` - 66 edges
10. `fetchApi()` - 66 edges

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

## Communities (218 total, 106 thin omitted)

### Community 1 - "main.py"
Cohesion: 0.02
Nodes (37): Architect, AgentClient, Developer, SysAdmin, set_oidc_adapter(), get_aligner(), get_architect(), get_argocd_observer() (+29 more)

### Community 2 - "react"
Cohesion: 0.05
Nodes (84): lucide-react, react, updateEventTitle(), AgentRegistryEntry, CiContext, ConversationTurn, ChatInput(), ChatInputProps (+76 more)

### Community 3 - "ConversationTurn"
Cohesion: 0.06
Nodes (43): emit_tool_result(), _safe_int(), handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_recall_pruned_turns(), handle_message_agent(), handle_reply_to_agent() (+35 more)

### Community 4 - "queue.py"
Cohesion: 0.04
Nodes (51): get_token_meter(), get_user_from_request(), get_archivist(), aligner_pending_items(), apply_lessons(), approve_event(), close_event_by_user(), CloseRequest (+43 more)

### Community 5 - "logging"
Cohesion: 0.04
Nodes (11): _sanitize_lesson_text(), _check_security(), _validate_plan_yaml(), safe_execution(), wrapper(), SecurityError, create_feedback_block(), _md_table_to_text() (+3 more)

### Community 6 - "client.ts"
Cohesion: 0.04
Nodes (86): ApiError, bulkDeleteObservations(), createChatEvent(), deleteNote(), deleteObservation(), exportObservations(), ExtractionResult, fetchApi() (+78 more)

### Community 7 - "EventSidebar.tsx"
Cohesion: 0.05
Nodes (88): getActiveEvents(), getAlignerPending(), getEventDocument(), getHeadhunterPending(), getIncidents(), getJenkinsPending(), getJiraMissions(), getWaitingApprovalEvents() (+80 more)

### Community 9 - "os"
Cohesion: 0.04
Nodes (27): _get_allowed_mention_authors(), _get_static_maintainer_emails(), _safe_int(), _stale_reservation_ttl_s(), handle_approve(), build_manifest_table(), extract_event_links(), dex_proxy() (+19 more)

### Community 10 - "colors.ts"
Cohesion: 0.05
Nodes (64): @uiw/react-markdown-preview, approveEvent(), closeEvent(), enforceCasualDomain(), getEventReport(), rejectEvent(), submitFeedback(), ReportFull (+56 more)

### Community 11 - "App.tsx"
Cohesion: 0.04
Nodes (71): oidc-client-ts, react-dom, react-router-dom, @tanstack/react-query, dismissProposals(), EnhancementProposal, getConfig(), getHandoffReports() (+63 more)

### Community 12 - "GitHubPlatform"
Cohesion: 0.03
Nodes (6): _get_static_maintainer_emails(), GitHubPlatform, _poll_one(), _one(), _poll_one(), _is_slash_command_only()

### Community 13 - "tool_gates.py"
Cohesion: 0.05
Nodes (79): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+71 more)

### Community 14 - "Headhunter"
Cohesion: 0.04
Nodes (8): Headhunter, PlatformQueueItem, PlatformSnapshot, _redact_error_text(), VcsContext, VcsWorkItem, _NoAliasSafeLoader, VcsPlatformPort

### Community 15 - "._run_agent_task"
Cohesion: 0.05
Nodes (10): on_huddle(), on_progress(), on_huddle(), on_progress(), _is_automated_nudge(), _is_participant_turn(), _sanitize_error_text(), _sanitize_override_reason() (+2 more)

### Community 17 - "http-handler.js"
Cohesion: 0.08
Nodes (62): is429Error(), registerMCPsAndHooks(), resolveCommand(), writeAgyMcpServer(), writeClaudeMcpServer(), parsePositiveInt(), buildArgoCDMcpConfig(), createAppJWT() (+54 more)

### Community 18 - "ReconcileScheduler"
Cohesion: 0.04
Nodes (7): FlowCollector, FairQueue, ReconcileScheduler, Trigger, QueueTrigger, ResyncTrigger, StalenessGuard

### Community 19 - "models.py"
Cohesion: 0.05
Nodes (27): _resolve_escalation_scope(), _iso(), _parse_ts(), AppNode, ChatRequest, ChatResponse, EventMetrics, EventStatus (+19 more)

### Community 20 - "JenkinsObserver"
Cohesion: 0.05
Nodes (5): JobResult, _flood_service_key(), JenkinsObserver, _outage_service_key(), _service_key()

### Community 21 - "BrainSkillLoader"
Cohesion: 0.04
Nodes (6): _inject_evidence_paths(), _parse_positive_int_env(), BrainSkillLoader, _SkillCorpus, _wrap_section(), BrainIntrospectionPort

### Community 22 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 23 - "ArchitectureGraph.tsx"
Cohesion: 0.06
Nodes (47): @dagrejs/dagre, @xyflow/react, getClosedEvents(), getEvents(), ArchitectureEvent, ArgoCDOperation, ActivityStream(), applyDagreLayout() (+39 more)

### Community 24 - "useMemory.ts"
Cohesion: 0.07
Nodes (50): applyLessons(), correctMemory(), createKnowledge(), createLesson(), deleteKnowledge(), deleteLesson(), ExtractedCorrection, ExtractedLesson (+42 more)

### Community 25 - "brain.py"
Cohesion: 0.05
Nodes (19): _batch_is_terminal_for_flush(), _compute_processed_up_to(), _has_non_user_turns(), _is_close_phase_fc(), _is_external_input_turn(), _is_seed_turn(), _is_steering_turn(), _coerce_turn_int() (+11 more)

### Community 26 - "Service"
Cohesion: 0.05
Nodes (8): GraphResponse, Service, get_graph_data(), get_mermaid_diagram(), get_service_details(), get_topology(), list_services(), calculate_health_from_argocd()

### Community 27 - "EventEvidence"
Cohesion: 0.07
Nodes (16): generate_event_title(), get_adapter(), _get_semaphore(), spawn_event_namer_task(), create_adapter(), format_event_summary(), handle_app_home_opened(), handle_app_mention() (+8 more)

### Community 28 - "cognitive_graph.py"
Cohesion: 0.06
Nodes (17): get_blackboard(), get_brain(), get_pulse_tracker(), dismiss_proposals(), DismissRequest, get_all_shadow_interventions(), get_cognitive_graph(), get_cortex_activity() (+9 more)

### Community 31 - "SlackChannel"
Cohesion: 0.06
Nodes (7): extract_tables(), _replace(), format_turn(), get_agent_notification_text(), get_turn_attachment_color(), _md_table_to_block_kit(), SlackChannel

### Community 32 - "._process_with_llm"
Cohesion: 0.04
Nodes (5): _BatchContext, _ensure_recall_tool_if_needed(), _QuotaShedState, RepetitionCollapse, _retry_backoff_delay()

### Community 33 - "GeminiAdapter"
Cohesion: 0.08
Nodes (12): _attach_signature_to_parts(), _clone_part_with_sig(), _clone_part_with_text(), _coerce_part(), _decode_sig_bytes(), _extract_part_signature(), GeminiAdapter, _is_empty_sig_carrier() (+4 more)

### Community 35 - "merge-guard.js"
Cohesion: 0.04
Nodes (46): API_VALUED, ARGO_MUTATING, ARGO_READ_SUB, ARGO_READ_TOP, BODY_FLAG, BROWSER_READ, CTX, ENV_BUILTINS (+38 more)

### Community 36 - "observations_mgmt.py"
Cohesion: 0.06
Nodes (18): get_report_client(), _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), render_pdf(), _sample_points() (+10 more)

### Community 37 - "context_parts.py"
Cohesion: 0.07
Nodes (21): _close_unanswered_fc(), _contents_have_pruned_or_decayed(), _apply_sibling_signature(), build_function_response(), build_single_function_response(), compress_contents(), contents_have_pruned_or_decayed(), estimate_msg_tokens() (+13 more)

### Community 38 - "OpsStateContext.tsx"
Cohesion: 0.08
Nodes (32): getAgents(), getKargoStages(), KargoStageStatus, AgentRegistryPanel(), formatConnectedSince(), ErrorBoundary, ErrorBoundaryProps, ErrorBoundaryState (+24 more)

### Community 39 - "gemini_client.py"
Cohesion: 0.07
Nodes (20): _extract_call_syntax(), _parse_drain_timeout(), derive_llm_priority(), _get_timeout_env_warned(), _get_timeout_order_warned(), is_partial_control_token(), LLMStreamInterChunkTimeoutError, LLMStreamTimeoutError (+12 more)

### Community 40 - "cli-executor.js"
Cohesion: 0.09
Nodes (37): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, MAX_TASK_WALL_MS, MAX_TIMER_MS, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS, STORAGE_PRETASK_TIMEOUT_MS, resolveStorageRoot }, buildCLICommand(), buildTimeoutResult(), { checkAndRecycleStorage, pinTaskCwd, unpinTaskCwd }, CLAUDE_JSON_PATH, cp, createInactivityWatchdog(), executeCLI() (+29 more)

### Community 41 - "storage-recycler.js"
Cohesion: 0.08
Nodes (37): withTaskStorage(), MAX_TASK_WALL_MS, parseTimerMs(), resolveStorageRoot(), resolveTimeoutMs(), ROLE_TIMEOUTS, STORAGE_ACTIVITY_HEARTBEAT_MS, STORAGE_MAX_TIER3_DELETIONS (+29 more)

### Community 42 - "ScheduleCreateRequest"
Cohesion: 0.06
Nodes (7): ScheduleCreateRequest, create_schedule(), delete_schedule(), get_schedule(), list_schedules(), toggle_schedule(), update_schedule()

### Community 44 - "auth.py"
Cohesion: 0.07
Nodes (15): can_append_message(), can_approve_event(), can_override_domain(), can_rename_event(), _claims_to_user(), get_user_from_slack(), get_user_from_websocket(), _normalize_email() (+7 more)

### Community 45 - "handlers_integration.py"
Cohesion: 0.08
Nodes (19): _alert_wrapper_retrigger(), _do_retrigger(), _get_jira_reporter(), handle_refresh_github_context(), handle_refresh_gitlab_context(), handle_refresh_kargo_context(), _is_darwin_reentrant_caller(), jenkins_retrigger_cooldown_key() (+11 more)

### Community 46 - "llm/__init__.py"
Cohesion: 0.08
Nodes (7): ClaudeAdapter, _parse_tpm_limit(), FunctionCall, LLMChunk, LLMPort, LLMResponse, TokenUsage

### Community 47 - "JenkinsAdapter"
Cohesion: 0.07
Nodes (5): BuildDetails, JenkinsAdapter, JenkinsPlatformPort, JobRunState, ViewScanResult

### Community 48 - "jenkins_observer.py"
Cohesion: 0.07
Nodes (16): _annotation_replace(), _strip_pipeline_annotations(), _safe_seconds(), _clamp_confidence(), _env_flag(), _parse_job_metadata(), _prepare_console_tail(), _redact_build_parameters() (+8 more)

### Community 49 - "StreamGrid.tsx"
Cohesion: 0.11
Nodes (29): getFlowMetrics(), FlowMetrics, Dashboard(), FlowHealthWidget(), queueColor(), wipColor(), GridTile(), GridTileProps (+21 more)

### Community 50 - "slack.py"
Cohesion: 0.07
Nodes (6): resolve_approval_identity(), table_block_to_code_block(), _PlanDecision, handle_reject(), _mask_email(), SlackAccessGate

### Community 51 - "TimeKeeperPage.tsx"
Cohesion: 0.12
Nodes (24): createSchedule(), deleteSchedule(), getSchedules(), refineInstructions(), ScheduleCreatePayload, ScheduleItem, toggleSchedule(), updateSchedule() (+16 more)

### Community 52 - "ws-client.js"
Cohesion: 0.10
Nodes (26): clearIdleTimer(), {
  DEFAULT_WORK_DIR, AGENT_CLI, AGENT_MODEL, AGENT_ROLE,
  EVENT_ID, EPHEMERAL, IDLE_TIMEOUT_MS,
  CLI_429_MAX_RETRIES, CLI_429_INITIAL_DELAY_MS, CLI_429_BACKOFF_MULTIPLIER,
  resolveTimeoutMs, parsePositiveInt, MAX_TASK_WALL_MS, MAX_TIMER_MS,
}, { ensureEventDocument }, { executeCLIStreaming, prepareResultsDir, is429Error }, { filterSkillsByRole, filterSkillsByMode, swapActiveRules, restoreAllSkills }, fs, handleCancel(), handleTask() (+18 more)

### Community 53 - "ui/package.json"
Cohesion: 0.08
Nodes (29): autoprefixer, cronstrue, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, graphology-layout-forceatlas2 (+21 more)

### Community 54 - "AgentRegistry"
Cohesion: 0.08
Nodes (6): AgentConnection, AgentRegistry, agent_websocket_handler(), _heartbeat(), agent_ws_endpoint(), websocket_endpoint()

### Community 55 - "prompt.py"
Cohesion: 0.12
Nodes (17): _attr(), _build_closed_block(), build_event_header(), _build_identity_block(), _build_journal_block(), _build_mermaid_block(), build_operational_briefing(), _build_related_block() (+9 more)

### Community 56 - "StateWatcher"
Cohesion: 0.09
Nodes (4): PollFn, _QueueEntry, StateWatcher, _Subscription

### Community 57 - "TaskBridge"
Cohesion: 0.10
Nodes (9): _build_prompt(), consume_wake_task(), _consume(), _dispatch_timeout_s(), dispatch_to_agent(), _consume_queue(), _sanitize_stdout(), send_cancel() (+1 more)

### Community 59 - "useCortexData.ts"
Cohesion: 0.17
Nodes (26): getCognitiveGraph(), getCortexActivity(), getKGServiceDetail(), getKGServices(), getKGStats(), getKnowledgeById(), getMemory(), getRecentPulses() (+18 more)

### Community 60 - "EventDrillDown.tsx"
Cohesion: 0.13
Nodes (23): three, getEventPulses(), BrainCore(), CortexDevPage(), devQueryClient, CortexLiveFeedProps, EventDrillDown(), EventDrillDownProps (+15 more)

### Community 61 - "KnowledgeGraphStore"
Cohesion: 0.15
Nodes (4): _acquire(), KnowledgeGraphStore, _sanitize(), _with_timeout()

### Community 62 - "TopologyRepository"
Cohesion: 0.08
Nodes (3): Snapshot, TopologySnapshot, TopologyRepository

### Community 63 - "CortexGraph.tsx"
Cohesion: 0.14
Nodes (25): graphology, eventColor(), getExecutiveNeurons(), getStructuralEdges(), DEFAULT_TYPE_BUDGET, evictLru(), KNOWLEDGE_RING, KNOWLEDGE_RING_TYPES (+17 more)

### Community 65 - "llm_error_classifier.py"
Cohesion: 0.13
Nodes (9): _extract_status_code(), _has_non_retryable_cause(), _is_google_auth_transport_error(), is_rate_limit(), is_transient(), is_transient_llm_error_turn(), _iter_exception_chain(), _matches_mro() (+1 more)

### Community 66 - "server.js"
Cohesion: 0.09
Nodes (18): { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, ensureEventDocument(), fs, path, stageEventDocument(), fetchEventDocument(), fs, { handleRequest } (+10 more)

### Community 67 - "adf_to_markdown"
Cohesion: 0.12
Nodes (10): _adf_to_text(), _escape_jql_string(), JiraIncidentAdapter, adf_to_markdown(), _apply_marks(), _children(), _render(), _render_list() (+2 more)

### Community 68 - "JarvisPeerPort"
Cohesion: 0.08
Nodes (3): BrainLifecyclePort, BroadcastPort, JarvisPeerPort

### Community 69 - ".list_observations"
Cohesion: 0.08
Nodes (4): get_all_journal(), get_service_journal(), get_event_observations(), get_global_observations()

### Community 70 - "PulseBatch"
Cohesion: 0.10
Nodes (4): PulseBatch, PulsePort, PulseObserver, PulseTracker

### Community 71 - "nightwatcher_tools.py"
Cohesion: 0.15
Nodes (13): ShiftIncident, ShiftInvestigation, extract_full_links(), execute_tool(), _handle_consult_deep_memory(), _handle_dispatch_investigation(), _handle_extend_incident(), _handle_get_event_report() (+5 more)

### Community 73 - "NightwatcherObserver"
Cohesion: 0.13
Nodes (4): ShiftReport, _env_float(), _env_int(), NightwatcherObserver

### Community 75 - "dependencies"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 76 - "reconcile.py"
Cohesion: 0.16
Nodes (10): sanitize_redis_port(), _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers(), main() (+2 more)

### Community 77 - "event_to_markdown"
Cohesion: 0.12
Nodes (6): get_event_document(), list_events(), report_tampering(), _esc(), _esc_join(), event_to_markdown()

### Community 78 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 79 - "claude-guard.js"
Cohesion: 0.14
Nodes (18): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+10 more)

### Community 82 - "HeadhunterCircuitBreaker"
Cohesion: 0.11
Nodes (3): HeadhunterCircuitBreaker, PlatformBreakerStatus, _raise_if_systemic_failure()

### Community 83 - "AsyncGitHubClient"
Cohesion: 0.17
Nodes (5): AsyncGitHubClient, _handle_rate_limit(), _paginate_github_get(), parse_github_next_link(), _safe_parse_int()

### Community 85 - "NeuronInfoPanel.tsx"
Cohesion: 0.12
Nodes (20): AGENTS, DOMAINS, HEMISPHERE_X, NEURON_DESCRIPTIONS, PHASE_SKILL_FOLDERS, PHASE_TOOL_PRIORITY, PHASES, StructuralEdge (+12 more)

### Community 86 - "FlowHistoryPage.tsx"
Cohesion: 0.23
Nodes (16): recharts, getFlowHistory(), FlowSnapshot, FlowHistoryPage(), RANGES, SparkCard(), SparkCardProps, formatTime() (+8 more)

### Community 87 - ".fetch_context"
Cohesion: 0.11
Nodes (6): _bot_login(), _csv_env(), _consider(), _mention_pattern(), _review_ignore_logins(), _review_trusted_associations()

### Community 88 - "cli-setup.js"
Cohesion: 0.13
Nodes (18): { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync }, filterSkillsByMode() (+10 more)

### Community 90 - "devDependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 91 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 92 - "nightwatcher.py"
Cohesion: 0.15
Nodes (7): record_token_usage(), build_system_prompt(), _fallback_platform(), _handle_declare_clusters(), reconcile_cluster_plan(), salvage_cluster_plan(), validate_cluster_plan()

### Community 93 - "gemini-sidecar/package.json"
Cohesion: 0.11
Nodes (18): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+10 more)

### Community 97 - "_section"
Cohesion: 0.12
Nodes (9): build_access_denied_home_view(), build_home_tab_view(), _context_line(), format_plan_block(), format_task_card(), format_tool_result_blocks(), resolve_source_emoji(), _section() (+1 more)

### Community 98 - "get_report"
Cohesion: 0.11
Nodes (6): get_report(), list_reports(), reports_spa_no_slash(), reports_spa_with_slash(), search_reports(), _serve_spa()

### Community 100 - "ShiftsPage.tsx"
Cohesion: 0.23
Nodes (16): getCurrentShift(), getShiftDetail(), getShiftsList(), ShiftReportFull, ShiftReportSummary, FailedClusterBadge(), getISOWeek(), getWeekDates() (+8 more)

### Community 101 - "cortex/types.ts"
Cohesion: 0.16
Nodes (16): ActiveEvent, EventSource, KGServiceEntity, CortexGraphProps, GraphLoaderProps, NeuronInfoPanelProps, PulseTimelineProps, CognitiveGraphResponse (+8 more)

### Community 102 - "FloatingWindow.tsx"
Cohesion: 0.19
Nodes (15): AgentStreamCard(), AgentStreamCardProps, MessageCards(), DEFAULT_POS, DEFAULT_SIZE, EMPTY_MESSAGES, FloatingWindow(), FloatingWindowProps (+7 more)

### Community 103 - "catalog-skills.js"
Cohesion: 0.16
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 109 - "generate_map.py"
Cohesion: 0.19
Nodes (6): _enumerate_gates(), _GateInfo, generate_phase_tool_map(), _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 114 - "graph_recall.py"
Cohesion: 0.19
Nodes (5): _format_graph_context(), get_graph_context(), _parse_props(), _sanitize(), translate_to_lookups()

### Community 116 - "create_chat_event"
Cohesion: 0.14
Nodes (4): EventInput, ChatEventRequest, ChatEventResponse, create_chat_event()

### Community 117 - "ServiceNode.tsx"
Cohesion: 0.20
Nodes (11): HealthStatus, NodeType, AppNodeData, ARGOCD_HEALTH_COLORS, SYNC_ICONS, GENERIC_TAGS, HEALTH_COLORS, NODE_ICONS (+3 more)

### Community 121 - "entity_extractor.py"
Cohesion: 0.21
Nodes (5): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship

### Community 124 - "analyzeTokens"
Cohesion: 0.19
Nodes (13): analyzeString(), analyzeTokens(), assignName(), base(), combineCategories(), configEnvGuard(), configFileWriteGuard(), hasSubseq() (+5 more)

### Community 126 - "._extract_context_flags"
Cohesion: 0.15
Nodes (3): compute_dispatch_backpressure(), ContextFlags, _safe_int_env()

### Community 127 - "handlers_planning.py"
Cohesion: 0.24
Nodes (6): _auto_complete_step(), _canonical_role(), handle_get_plan_progress(), _is_failed_turn(), _is_orchestrator_turn(), _normalize_step_id()

### Community 129 - "IncidentAdapterPort"
Cohesion: 0.15
Nodes (3): IdleTimeoutPort, IncidentAdapterPort, StateWatcherPort

### Community 135 - "._run_report_cart"
Cohesion: 0.17
Nodes (5): build_report_iteration_prompt(), build_summary_prompt(), build_extend_tool(), build_report_tool(), build_summary_tool()

### Community 136 - "CortexLiveFeed.tsx"
Cohesion: 0.24
Nodes (10): CortexHeartbeat(), CortexHeartbeatProps, ensureKeyframes(), CortexLiveFeed(), FILTER_PILLS, FilterKey, getStoredFilter(), MESSAGE_STYLES (+2 more)

### Community 137 - "testSetup.ts"
Cohesion: 0.18
Nodes (5): @tailwindcss/vite, @testing-library/react, vite, @vitejs/plugin-react, vitest

### Community 138 - "is_defer_event_available"
Cohesion: 0.18
Nodes (6): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 140 - "gitGuard"
Cohesion: 0.29
Nodes (10): bareBranchProtected(), configWriteGuard(), externalGitCommand(), gitGuard(), gitQuery(), isProtected(), normRef(), pushGuard() (+2 more)

### Community 141 - "parseShell"
Cohesion: 0.33
Nodes (10): bodySubstitutions(), decodeAnsiC(), isArrayAssignPrefix(), isWordStart(), matchBacktick(), matchParen(), parseShell(), readHeredocStart() (+2 more)

### Community 146 - "has_unevaluated_close_blocker"
Cohesion: 0.22
Nodes (5): has_unevaluated_close_blocker(), _pred_jarvis_response(), _pred_unevaluated_close(), is_jarvis_acknowledgment(), is_stabilization_wake()

### Community 147 - "knowledge_graph_api.py"
Cohesion: 0.31
Nodes (4): get_kg_store(), get_service_detail(), get_stats(), list_services()

### Community 149 - "classifyTool"
Cohesion: 0.31
Nodes (9): apiTokens(), apiWriteNeedsGuard(), branchValues(), classifyTool(), hasOpaqueTarget(), httpGuard(), httpMethod(), isReadMethod() (+1 more)

### Community 150 - "get_quota_tracker"
Cohesion: 0.22
Nodes (3): get_quota_tracker(), llm_stats(), receive_telemetry()

### Community 161 - "validate-mutations.sh"
Cohesion: 0.57
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

### Community 164 - "._run_analysis_loop"
Cohesion: 0.33
Nodes (3): _append_user_turn(), _finalize_analysis_handover(), get_phase_tools()

### Community 165 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 166 - "state.js"
Cohesion: 0.33
Nodes (4): { AGENT_ROLE }, _blackboardTurns, _inboundMessages, _teammateMessages

### Community 173 - "_append_user_turn"
Cohesion: 0.33
Nodes (3): _append_user_turn(), _is_function_response_part(), _validated_parts()

### Community 174 - "build_gate_context"
Cohesion: 0.33
Nodes (3): build_gate_context(), conversation_has_decayed_turns(), _decay_payload_len()

### Community 181 - "classify"
Cohesion: 0.50
Nodes (4): classify(), main(), shellCategory(), shellNeedsGuard()

### Community 192 - "overrides"
Cohesion: 0.67
Nodes (3): overrides, @typescript-eslint/typescript-estree, minimatch

## Knowledge Gaps
- **13 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+8 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2456 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **106 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `main.py`, `ConversationTurn`, `queue.py`, `logging`, `Brain`, `os`, `HeadhunterJira`, `models.py`, `BrainSkillLoader`, `brain.py`, `Service`, `EventEvidence`, `_is_event_closed_or_missing`, `cognitive_graph.py`, `ConversationMessage`, `observations_mgmt.py`, `ScheduleCreateRequest`, `EventDocument`, `auth.py`, `._restage_pending_signal`, `jenkins_observer.py`, `._stage_pending_signal`, `slack.py`, `get_notebook`, `._count_pending`, `._downsample_snapshots`, `.drain_notes`, `.get_edge_metadata`, `TopologyRepository`, `LiveAPIAdapter`, `.list_observations`, `nightwatcher_tools.py`, `NightwatcherObserver`, `event_to_markdown`, `DashboardWSAdapter`, `nightwatcher.py`, `get_report`, `state/ports.py`, `create_chat_event`, `ScheduleRepository`?**
  _High betweenness centrality (0.143) - this node is a cross-community bridge._
- **Are the 80 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 80 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.01327639751552795 - nodes in this community are weakly interconnected._
- **Why does `Brain` connect `Brain` to `BlackboardState`, `main.py`, `ConversationTurn`, `logging`, `._execute_function_call`, `os`, `._run_agent_task`, `._resolve_llm_params`, `._post_agent_recall`, `ReconcileScheduler`, `models.py`, `BrainSkillLoader`, `brain.py`, `EventEvidence`, `._process_with_llm`, `EventDocument`, `slack.py`, `StateWatcher`, `.clear_jarvis_wait`, `.next_turn_number`, `JarvisPeerPort`, `PulseBatch`, `DashboardWSAdapter`, `._build_contents`, `ReflexSearcher`, `IdleTimeoutManager`, `entity_extractor.py`, `._extract_context_flags`?**
  _High betweenness centrality (0.082) - this node is a cross-community bridge._
- **Are the 20 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Should `main.py` be split into smaller, more focused modules?**
  _Cohesion score 0.022003596741775096 - nodes in this community are weakly interconnected._