# Graph Report - Blackboard  (2026-11-22)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 5496 nodes · 12350 edges · 229 communities (101 shown, 128 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 973 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `9d4d44f1`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BlackboardState
- queue.py
- ConversationTurn
- os
- models.py
- Brain
- client.ts
- api/types.ts
- EventSidebar.tsx
- brain.py
- tool_gates.py
- Archivist
- App.tsx
- ReconcileScheduler
- http-handler.js
- hooks/index.ts
- main.py
- GitHubPlatform
- TurnBubble.tsx
- BrainSkillLoader
- EventDocument
- Headhunter
- OpsStateContext.tsx
- nightwatcher_tools.py
- lucide-react
- GitLabPlatform
- EventRepository
- jenkins-mcp.js
- GeminiAdapter
- ._process_with_llm
- _BrainToolContext
- merge-guard.js
- storage-recycler.js
- cli-executor.js
- dispatch.py
- EventHistory.tsx
- llm/__init__.py
- gemini_client.py
- slack.py
- AgentClient
- CortexGraph.tsx
- Aligner
- ws-client.js
- TimeKeeperPage.tsx
- react
- JarvisPeerPort
- NightwatcherObserver
- SlackChannel
- ui/package.json
- EventDrillDown.tsx
- StateWatcher
- AgentRegistry
- IdleTimeoutManager
- ._resolve_client
- KnowledgeGraphStore
- LiveAPIAdapter
- llm_error_classifier.py
- catalog-skills.js
- server.js
- ._build_contents
- ._triage_and_build_evidence
- JenkinsObserver
- cognitive_graph.py
- useCortexData.ts
- quota_tracker.py
- JenkinsAdapter
- PulseBatch
- VectorStore
- spawn_event_namer_task
- ArgoCDObserver
- reconcile.py
- KargoObserver
- dependencies
- compilerOptions
- claude-guard.js
- ArchitectureGraph.tsx
- DashboardWSAdapter
- .fetch_context
- ._github_poll_issues
- TopologyRepository
- GitHubAppAuth
- VcsPlatformPort
- cli-setup.js
- ReflexSearcher
- devDependencies
- compilerOptions
- gemini-sidecar/package.json
- EphemeralProvisioner
- get_report
- ObservationRepository
- ShiftsPage.tsx
- EscalationRepository
- JiraIncidentAdapter
- prompt.py
- TokenMeter
- MultiInstallationManager
- cortex/types.ts
- generate_map.py
- JenkinsPlatformPort
- ._poll_and_stage
- OIDCKeyAdapter
- KubernetesSpawnHealthAdapter
- RedisClient
- ServiceNode.tsx
- observations_reporter.py
- ._connect
- ScheduleRepository
- SlackAccessGate
- analyzeTokens
- FilterRule
- ._extract_context_flags
- IncidentAdapterPort
- ._send_turn_to_thread
- ScheduleCreateRequest
- create_schedule
- ._drain_once
- ._process_message
- ._authorize_plan_decision
- delete_schedule
- CortexLiveFeed.tsx
- testSetup.ts
- is_defer_event_available
- NeuronInfoPanel.tsx
- gitGuard
- parseShell
- generate_event_title
- adf_to_markdown
- ._post_agent_recall
- entity_extractor.py
- ._clear_recovered_group_flags
- has_unevaluated_close_blocker
- knowledge_graph_api.py
- classifyTool
- SpawnPollResult
- SmartsheetMaintainerCache
- .has_reeval_signal
- MetricsRepository
- AsyncGitHubClient
- GitLabTokenAuth
- _is_event_closed_or_missing
- ._evaluate_health
- HeadhunterJira
- Any
- ConversationMessage
- Service
- nightwatcher_prompt.py
- TimeKeeperObserver
- CortexRepository
- validate-mutations.sh
- llm_stats
- update_schedule
- ._detect_repetition_collapse
- _format_graph_context
- scripts
- DispatchMetrics
- _append_user_turn
- build_gate_context
- SpawnStatus
- list_failed_stages
- dex_proxy
- ._wait_for_registration
- agent_ws_endpoint
- get_notebook
- classify
- derive_llm_priority
- list_incidents
- require-results.sh
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
- _select_dispatch_tier
- _sanitize_override_reason
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
1. `BlackboardState` - 300 edges
2. `Brain` - 168 edges
3. `ConversationTurn` - 132 edges
4. `ToolContext` - 104 edges
5. `GateContext` - 99 edges
6. `react` - 85 edges
7. `EventDocument` - 84 edges
8. `GitHubPlatform` - 72 edges
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

## Communities (229 total, 128 thin omitted)

### Community 0 - "BlackboardState"
Cohesion: 0.01
Nodes (45): get_aligner(), get_architect(), get_argocd_observer(), get_blackboard(), get_developer(), get_kargo_observer(), get_report_client(), get_sysadmin() (+37 more)

### Community 1 - "queue.py"
Cohesion: 0.02
Nodes (78): get_token_meter(), can_append_message(), can_approve_event(), can_override_domain(), can_rename_event(), _claims_to_user(), get_user_from_request(), get_user_from_slack() (+70 more)

### Community 2 - "ConversationTurn"
Cohesion: 0.04
Nodes (73): _is_close_phase_fc(), emit_tool_result(), _safe_int(), _coerce_turn_int(), handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_recall_pruned_turns() (+65 more)

### Community 3 - "os"
Cohesion: 0.03
Nodes (20): _annotation_replace(), _strip_pipeline_annotations(), _sanitize_lesson_text(), get_graph_context(), translate_to_lookups(), _get_static_maintainer_emails(), _mention_pattern(), _get_allowed_mention_authors() (+12 more)

### Community 4 - "models.py"
Cohesion: 0.02
Nodes (41): _batch_is_terminal_for_flush(), _resolve_escalation_scope(), _iso(), get_flow_metrics(), AppNode, ArchitectureEvent, ChatRequest, ChatResponse (+33 more)

### Community 5 - "Brain"
Cohesion: 0.03
Nodes (8): Brain, on_huddle(), on_progress(), on_huddle(), on_progress(), _is_automated_nudge(), _sanitize_error_text(), get_registry_and_bridge()

### Community 6 - "client.ts"
Cohesion: 0.04
Nodes (100): @tanstack/react-query, ApiError, applyLessons(), bulkDeleteObservations(), correctMemory(), createKnowledge(), createLesson(), deleteKnowledge() (+92 more)

### Community 7 - "api/types.ts"
Cohesion: 0.03
Nodes (96): updateEventTitle(), Agent, AlignerPendingItem, AppNode, AuthUser, BulkDeleteRequest, ChatEventRequest, ChatEventResponse (+88 more)

### Community 8 - "EventSidebar.tsx"
Cohesion: 0.05
Nodes (71): getHeadhunterPending(), getJiraMissions(), HeadhunterTodo, postJiraAction(), ActiveEvent, DeferCountdownBar(), STATUS_COLORS, TICKET_COLORS (+63 more)

### Community 9 - "brain.py"
Cohesion: 0.04
Nodes (36): _compute_processed_up_to(), _contents_have_pruned_or_decayed(), _has_non_user_turns(), _is_external_input_turn(), _is_seed_turn(), _is_steering_turn(), _apply_sibling_signature(), build_function_response() (+28 more)

### Community 10 - "tool_gates.py"
Cohesion: 0.05
Nodes (79): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+71 more)

### Community 12 - "App.tsx"
Cohesion: 0.06
Nodes (58): oidc-client-ts, react-dom, recharts, dismissProposals(), EnhancementProposal, getFlowHistory(), getHandoffReports(), getProposals() (+50 more)

### Community 13 - "ReconcileScheduler"
Cohesion: 0.04
Nodes (7): FlowCollector, FairQueue, ReconcileScheduler, Trigger, QueueTrigger, ResyncTrigger, StalenessGuard

### Community 14 - "http-handler.js"
Cohesion: 0.07
Nodes (63): is429Error(), registerMCPsAndHooks(), resolveCommand(), writeAgyMcpServer(), writeClaudeMcpServer(), buildArgoCDMcpConfig(), createAppJWT(), discoverAndGenerateTokens() (+55 more)

### Community 15 - "hooks/index.ts"
Cohesion: 0.06
Nodes (53): react-router-dom, getClosedEvents(), getConfig(), getEvents(), getService(), getTopology(), AppConfig, ArchitectureEvent (+45 more)

### Community 16 - "main.py"
Cohesion: 0.04
Nodes (24): _patch_enum_fields(), set_incident_options(), set_oidc_adapter(), set_agents(), set_archivist(), set_argocd_observer(), set_blackboard(), set_brain() (+16 more)

### Community 18 - "TurnBubble.tsx"
Cohesion: 0.08
Nodes (44): mermaid, @uiw/react-markdown-preview, approveEvent(), closeEvent(), enforceCasualDomain(), getEventReport(), rejectEvent(), submitFeedback() (+36 more)

### Community 19 - "BrainSkillLoader"
Cohesion: 0.05
Nodes (5): _inject_evidence_paths(), BrainSkillLoader, _SkillCorpus, _wrap_section(), BrainIntrospectionPort

### Community 22 - "OpsStateContext.tsx"
Cohesion: 0.07
Nodes (47): getAgents(), getFlowMetrics(), getKargoStages(), AgentRegistryEntry, FlowMetrics, KargoStageStatus, AgentRegistryPanel(), formatConnectedSince() (+39 more)

### Community 23 - "nightwatcher_tools.py"
Cohesion: 0.07
Nodes (26): PulseContext, ShiftIncident, ShiftInvestigation, build_report_iteration_prompt(), build_summary_prompt(), extract_full_links(), _normalize_gitlab_host(), build_extend_tool() (+18 more)

### Community 24 - "lucide-react"
Cohesion: 0.07
Nodes (40): lucide-react, createChatEvent(), AgentStreamCard(), AgentStreamCardProps, MessageCards(), ChatInput(), ChatInputProps, Draft (+32 more)

### Community 27 - "jenkins-mcp.js"
Cohesion: 0.06
Nodes (40): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+32 more)

### Community 28 - "GeminiAdapter"
Cohesion: 0.08
Nodes (12): _attach_signature_to_parts(), _clone_part_with_sig(), _clone_part_with_text(), _coerce_part(), _decode_sig_bytes(), _extract_part_signature(), GeminiAdapter, _is_empty_sig_carrier() (+4 more)

### Community 29 - "._process_with_llm"
Cohesion: 0.04
Nodes (4): _BatchContext, _ensure_recall_tool_if_needed(), _QuotaShedState, _retry_backoff_delay()

### Community 31 - "merge-guard.js"
Cohesion: 0.04
Nodes (46): API_VALUED, ARGO_MUTATING, ARGO_READ_SUB, ARGO_READ_TOP, BODY_FLAG, BROWSER_READ, CTX, ENV_BUILTINS (+38 more)

### Community 32 - "storage-recycler.js"
Cohesion: 0.07
Nodes (38): withTaskStorage(), MAX_TASK_WALL_MS, parsePositiveInt(), parseTimerMs(), resolveStorageRoot(), resolveTimeoutMs(), ROLE_TIMEOUTS, STORAGE_ACTIVITY_HEARTBEAT_MS (+30 more)

### Community 33 - "cli-executor.js"
Cohesion: 0.09
Nodes (37): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, MAX_TASK_WALL_MS, MAX_TIMER_MS, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS, STORAGE_PRETASK_TIMEOUT_MS, resolveStorageRoot }, buildCLICommand(), buildTimeoutResult(), { checkAndRecycleStorage, pinTaskCwd, unpinTaskCwd }, CLAUDE_JSON_PATH, cp, createInactivityWatchdog(), executeCLI() (+29 more)

### Community 34 - "dispatch.py"
Cohesion: 0.08
Nodes (13): _build_prompt(), _check_security(), consume_wake_task(), _consume(), _dispatch_timeout_s(), dispatch_to_agent(), _consume_queue(), _sanitize_stdout() (+5 more)

### Community 35 - "EventHistory.tsx"
Cohesion: 0.11
Nodes (33): getReport(), getReports(), ReportMeta, SubjectType, CompactCardStrip(), EventHistory(), TimeRange, ViewMode (+25 more)

### Community 36 - "llm/__init__.py"
Cohesion: 0.08
Nodes (7): ClaudeAdapter, _parse_tpm_limit(), FunctionCall, LLMChunk, LLMPort, LLMResponse, TokenUsage

### Community 37 - "gemini_client.py"
Cohesion: 0.08
Nodes (18): _extract_call_syntax(), _parse_drain_timeout(), _get_timeout_env_warned(), _get_timeout_order_warned(), is_partial_control_token(), LLMStreamInterChunkTimeoutError, LLMStreamTimeoutError, LLMStreamTotalTimeoutError (+10 more)

### Community 38 - "slack.py"
Cohesion: 0.08
Nodes (15): build_access_denied_home_view(), build_home_tab_view(), _context_line(), create_feedback_block(), format_plan_block(), format_task_card(), format_tool_result_blocks(), format_turn() (+7 more)

### Community 39 - "AgentClient"
Cohesion: 0.07
Nodes (4): Architect, AgentClient, Developer, SysAdmin

### Community 40 - "CortexGraph.tsx"
Cohesion: 0.09
Nodes (35): graphology, AGENTS, DOMAINS, eventColor(), getExecutiveNeurons(), getStructuralEdges(), HEMISPHERE_X, NEURON_DESCRIPTIONS (+27 more)

### Community 42 - "ws-client.js"
Cohesion: 0.08
Nodes (28): { AGENT_ROLE }, _blackboardTurns, _inboundMessages, _teammateMessages, clearIdleTimer(), {
  DEFAULT_WORK_DIR, AGENT_CLI, AGENT_MODEL, AGENT_ROLE,
  EVENT_ID, EPHEMERAL, IDLE_TIMEOUT_MS,
  CLI_429_MAX_RETRIES, CLI_429_INITIAL_DELAY_MS, CLI_429_BACKOFF_MULTIPLIER,
  resolveTimeoutMs, parsePositiveInt, MAX_TASK_WALL_MS, MAX_TIMER_MS,
}, { ensureEventDocument }, { executeCLIStreaming, prepareResultsDir, is429Error } (+20 more)

### Community 43 - "TimeKeeperPage.tsx"
Cohesion: 0.12
Nodes (24): createSchedule(), deleteSchedule(), getSchedules(), refineInstructions(), ScheduleCreatePayload, ScheduleItem, toggleSchedule(), updateSchedule() (+16 more)

### Community 44 - "react"
Cohesion: 0.12
Nodes (27): react, getActiveEvents(), getAlignerPending(), getEventDocument(), getJenkinsPending(), getWaitingApprovalEvents(), EventDocument, MessageStatus (+19 more)

### Community 45 - "JarvisPeerPort"
Cohesion: 0.06
Nodes (4): get_quota_tracker(), BrainLifecyclePort, BroadcastPort, JarvisPeerPort

### Community 46 - "NightwatcherObserver"
Cohesion: 0.10
Nodes (6): ShiftReport, _append_user_turn(), _env_float(), _env_int(), NightwatcherObserver, _finalize_analysis_handover()

### Community 48 - "ui/package.json"
Cohesion: 0.08
Nodes (28): autoprefixer, cronstrue, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, graphology-layout-forceatlas2 (+20 more)

### Community 49 - "EventDrillDown.tsx"
Cohesion: 0.12
Nodes (24): three, getEventPulses(), BrainCore(), CortexDevPage(), devQueryClient, CortexLiveFeedProps, EventDrillDown(), EventDrillDownProps (+16 more)

### Community 50 - "StateWatcher"
Cohesion: 0.09
Nodes (4): PollFn, _QueueEntry, StateWatcher, _Subscription

### Community 51 - "AgentRegistry"
Cohesion: 0.09
Nodes (4): AgentConnection, AgentRegistry, agent_websocket_handler(), _heartbeat()

### Community 54 - "KnowledgeGraphStore"
Cohesion: 0.15
Nodes (4): _acquire(), KnowledgeGraphStore, _sanitize(), _with_timeout()

### Community 56 - "llm_error_classifier.py"
Cohesion: 0.13
Nodes (9): _extract_status_code(), _has_non_retryable_cause(), _is_google_auth_transport_error(), is_rate_limit(), is_transient(), is_transient_llm_error_turn(), _iter_exception_chain(), _matches_mro() (+1 more)

### Community 57 - "catalog-skills.js"
Cohesion: 0.10
Nodes (19): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+11 more)

### Community 58 - "server.js"
Cohesion: 0.09
Nodes (18): { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, ensureEventDocument(), fs, path, stageEventDocument(), fetchEventDocument(), fs, { handleRequest } (+10 more)

### Community 59 - "._build_contents"
Cohesion: 0.08
Nodes (3): _close_unanswered_fc(), _incr_flow_counter_safely(), _is_participant_turn()

### Community 60 - "._triage_and_build_evidence"
Cohesion: 0.09
Nodes (10): _clamp_confidence(), _prepare_console_tail(), _redact_build_parameters(), _redact_match(), _redact_secrets_in_text(), _sanitize_analysis_text(), _sanitize_console_tail(), _strip_newlines() (+2 more)

### Community 62 - "cognitive_graph.py"
Cohesion: 0.11
Nodes (11): get_pulse_tracker(), dismiss_proposals(), DismissRequest, get_all_shadow_interventions(), get_cognitive_graph(), get_cortex_activity(), get_cortex_status(), get_event_shadow_interventions() (+3 more)

### Community 63 - "useCortexData.ts"
Cohesion: 0.20
Nodes (23): getCognitiveGraph(), getCortexActivity(), getKGServiceDetail(), getKGServices(), getKGStats(), getRecentPulses(), CortexPage(), isOffRingCollection() (+15 more)

### Community 64 - "quota_tracker.py"
Cohesion: 0.11
Nodes (5): QuotaExhaustedError, QuotaTracker, RequestExceedsBurstError, Reservation, _stale_reservation_ttl_s()

### Community 66 - "PulseBatch"
Cohesion: 0.10
Nodes (4): PulseBatch, PulsePort, PulseObserver, PulseTracker

### Community 67 - "VectorStore"
Cohesion: 0.12
Nodes (3): _decode_cursor(), _encode_cursor(), VectorStore

### Community 68 - "spawn_event_namer_task"
Cohesion: 0.16
Nodes (8): spawn_event_namer_task(), format_event_summary(), handle_app_mention(), handle_create_event_modal(), handle_darwin_command(), handle_home_create_event(), on_dm_message(), fallback_title()

### Community 70 - "reconcile.py"
Cohesion: 0.15
Nodes (10): sanitize_redis_port(), _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers(), main() (+2 more)

### Community 72 - "dependencies"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 73 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 74 - "claude-guard.js"
Cohesion: 0.14
Nodes (18): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+10 more)

### Community 75 - "ArchitectureGraph.tsx"
Cohesion: 0.14
Nodes (18): @dagrejs/dagre, @xyflow/react, applyDagreLayout(), applyGridLayout(), applyLayout(), ArchitectureGraph(), ArchitectureGraphInner(), buildGraph() (+10 more)

### Community 77 - ".fetch_context"
Cohesion: 0.10
Nodes (7): _bot_login(), _csv_env(), _consider(), _is_slash_command_only(), _parse_ts(), _review_ignore_logins(), _review_trusted_associations()

### Community 78 - "._github_poll_issues"
Cohesion: 0.10
Nodes (3): _poll_one(), _poll_one(), _raise_if_systemic_failure()

### Community 82 - "cli-setup.js"
Cohesion: 0.13
Nodes (18): { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync }, filterSkillsByMode() (+10 more)

### Community 84 - "devDependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 85 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 86 - "gemini-sidecar/package.json"
Cohesion: 0.11
Nodes (18): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+10 more)

### Community 88 - "get_report"
Cohesion: 0.11
Nodes (6): get_report(), list_reports(), reports_spa_no_slash(), reports_spa_with_slash(), search_reports(), _serve_spa()

### Community 90 - "ShiftsPage.tsx"
Cohesion: 0.23
Nodes (16): getCurrentShift(), getShiftDetail(), getShiftsList(), ShiftReportFull, ShiftReportSummary, FailedClusterBadge(), getISOWeek(), getWeekDates() (+8 more)

### Community 94 - "prompt.py"
Cohesion: 0.21
Nodes (11): _build_closed_block(), build_event_header(), _build_identity_block(), _build_journal_block(), _build_mermaid_block(), _build_related_block(), _build_subject_block(), _build_timing_block() (+3 more)

### Community 97 - "cortex/types.ts"
Cohesion: 0.17
Nodes (14): EventSource, KGServiceEntity, CortexGraphProps, GraphLoaderProps, NeuronInfoPanelProps, PulseTimelineProps, CognitiveGraphResponse, CortexHeartbeatMessage (+6 more)

### Community 98 - "generate_map.py"
Cohesion: 0.19
Nodes (6): _enumerate_gates(), _GateInfo, generate_phase_tool_map(), _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 99 - "JenkinsPlatformPort"
Cohesion: 0.13
Nodes (4): BuildDetails, JenkinsPlatformPort, JobRunState, ViewScanResult

### Community 104 - "RedisClient"
Cohesion: 0.16
Nodes (3): skills_version(), get_redis(), RedisClient

### Community 105 - "ServiceNode.tsx"
Cohesion: 0.20
Nodes (11): HealthStatus, NodeType, AppNodeData, ARGOCD_HEALTH_COLORS, SYNC_ICONS, GENERIC_TAGS, HEALTH_COLORS, NODE_ICONS (+3 more)

### Community 106 - "observations_reporter.py"
Cohesion: 0.21
Nodes (7): _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), _sample_points(), _summarize()

### Community 111 - "analyzeTokens"
Cohesion: 0.19
Nodes (13): analyzeString(), analyzeTokens(), assignName(), base(), combineCategories(), configEnvGuard(), configFileWriteGuard(), hasSubseq() (+5 more)

### Community 113 - "._extract_context_flags"
Cohesion: 0.15
Nodes (3): compute_dispatch_backpressure(), ContextFlags, _safe_int_env()

### Community 114 - "IncidentAdapterPort"
Cohesion: 0.15
Nodes (3): IdleTimeoutPort, IncidentAdapterPort, StateWatcherPort

### Community 115 - "._send_turn_to_thread"
Cohesion: 0.19
Nodes (5): extract_tables(), _replace(), get_agent_notification_text(), get_turn_attachment_color(), _md_table_to_block_kit()

### Community 117 - "create_schedule"
Cohesion: 0.15
Nodes (3): create_schedule(), get_schedule(), list_schedules()

### Community 122 - "._authorize_plan_decision"
Cohesion: 0.18
Nodes (3): _PlanDecision, handle_approve(), handle_reject()

### Community 124 - "CortexLiveFeed.tsx"
Cohesion: 0.24
Nodes (10): CortexHeartbeat(), CortexHeartbeatProps, ensureKeyframes(), CortexLiveFeed(), FILTER_PILLS, FilterKey, getStoredFilter(), MESSAGE_STYLES (+2 more)

### Community 125 - "testSetup.ts"
Cohesion: 0.18
Nodes (5): @tailwindcss/vite, @testing-library/react, vite, @vitejs/plugin-react, vitest

### Community 126 - "is_defer_event_available"
Cohesion: 0.18
Nodes (6): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 127 - "NeuronInfoPanel.tsx"
Cohesion: 0.29
Nodes (10): asNumber(), asString(), asStringArray(), Badge(), describeNeuron(), Hdr(), NeuronInfoPanel(), AGENT_NEURON_COLORS (+2 more)

### Community 128 - "gitGuard"
Cohesion: 0.29
Nodes (10): bareBranchProtected(), configWriteGuard(), externalGitCommand(), gitGuard(), gitQuery(), isProtected(), normRef(), pushGuard() (+2 more)

### Community 129 - "parseShell"
Cohesion: 0.33
Nodes (10): bodySubstitutions(), decodeAnsiC(), isArrayAssignPrefix(), isWordStart(), matchBacktick(), matchParen(), parseShell(), readHeredocStart() (+2 more)

### Community 130 - "generate_event_title"
Cohesion: 0.22
Nodes (3): generate_event_title(), get_adapter(), _get_semaphore()

### Community 131 - "adf_to_markdown"
Cohesion: 0.40
Nodes (8): _adf_to_text(), adf_to_markdown(), _apply_marks(), _children(), _render(), _render_list(), _render_list_item(), _render_table_like()

### Community 133 - "entity_extractor.py"
Cohesion: 0.33
Nodes (5): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship

### Community 135 - "has_unevaluated_close_blocker"
Cohesion: 0.22
Nodes (5): has_unevaluated_close_blocker(), _pred_jarvis_response(), _pred_unevaluated_close(), is_jarvis_acknowledgment(), is_stabilization_wake()

### Community 136 - "knowledge_graph_api.py"
Cohesion: 0.31
Nodes (4): get_kg_store(), get_service_detail(), get_stats(), list_services()

### Community 137 - "classifyTool"
Cohesion: 0.31
Nodes (9): apiTokens(), apiWriteNeedsGuard(), branchValues(), classifyTool(), hasOpaqueTarget(), httpGuard(), httpMethod(), isReadMethod() (+1 more)

### Community 151 - "nightwatcher_prompt.py"
Cohesion: 0.32
Nodes (3): build_manifest_table(), build_system_prompt(), extract_event_links()

### Community 154 - "validate-mutations.sh"
Cohesion: 0.57
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

### Community 158 - "_format_graph_context"
Cohesion: 0.38
Nodes (3): _format_graph_context(), _parse_props(), _sanitize()

### Community 160 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 168 - "_append_user_turn"
Cohesion: 0.33
Nodes (3): _append_user_turn(), _is_function_response_part(), _validated_parts()

### Community 169 - "build_gate_context"
Cohesion: 0.33
Nodes (3): build_gate_context(), conversation_has_decayed_turns(), _decay_payload_len()

### Community 180 - "classify"
Cohesion: 0.50
Nodes (4): classify(), main(), shellCategory(), shellNeedsGuard()

### Community 195 - "overrides"
Cohesion: 0.67
Nodes (3): overrides, @typescript-eslint/typescript-estree, minimatch

## Knowledge Gaps
- **13 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+8 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2428 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **128 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `queue.py`, `ConversationTurn`, `os`, `models.py`, `Brain`, `generate_event_title`, `brain.py`, `_is_event_closed_or_missing`, `main.py`, `HeadhunterJira`, `EventDocument`, `ConversationMessage`, `Service`, `nightwatcher_tools.py`, `update_schedule`, `slack.py`, `._is_ip_address`, `._restage_pending_signal`, `NightwatcherObserver`, `._stage_pending_signal`, `get_notebook`, `._count_pending`, `IdleTimeoutManager`, `LiveAPIAdapter`, `.cleanup_stale_services`, `._commit_pending_signal`, `._drain_pending`, `.drain_notes`, `.get_edge_metadata`, `DashboardWSAdapter`, `get_report`, `observations_reporter.py`, `ScheduleRepository`, `create_schedule`, `delete_schedule`?**
  _High betweenness centrality (0.140) - this node is a cross-community bridge._
- **Are the 80 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 80 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.009362046304721464 - nodes in this community are weakly interconnected._
- **Why does `Brain` connect `Brain` to `BlackboardState`, `queue.py`, `ConversationTurn`, `os`, `._post_agent_recall`, `models.py`, `brain.py`, `ReconcileScheduler`, `main.py`, `BrainSkillLoader`, `EventDocument`, `._process_with_llm`, `._detect_repetition_collapse`, `._escalation_blocked`, `dispatch.py`, `slack.py`, `JarvisPeerPort`, `StateWatcher`, `IdleTimeoutManager`, `._build_contents`, `.append_and_broadcast`, `.clear_jarvis_wait`, `.next_turn_number`, `PulseBatch`, `DashboardWSAdapter`, `._check_chat_staleness`, `._check_jarvis_staleness`, `.clear_cycle_id`, `.create_kargo_event`, `.get_incident_adapter`, `ReflexSearcher`, `.has_jarvis_waiters`, `._is_event_deferred`, `._extract_context_flags`?**
  _High betweenness centrality (0.063) - this node is a cross-community bridge._
- **Are the 20 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Should `queue.py` be split into smaller, more focused modules?**
  _Cohesion score 0.018817617802389375 - nodes in this community are weakly interconnected._