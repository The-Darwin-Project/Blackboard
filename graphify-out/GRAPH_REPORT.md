# Graph Report - Blackboard  (2026-11-15)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 5237 nodes · 11771 edges · 238 communities (107 shown, 131 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 952 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `d4f110f4`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BlackboardState
- logging
- main.py
- httpx
- queue.py
- client.ts
- Archivist
- WorkspaceInspector.tsx
- Brain
- EventSidebar.tsx
- EventDocument
- auth.py
- tool_gates.py
- react
- http-handler.js
- hooks/index.ts
- jenkins-mcp.js
- EventHistory.tsx
- App.tsx
- BrainSkillLoader
- ._process_with_llm
- components/index.ts
- ToolContext
- ScheduleRepository
- _BrainToolContext
- EventRepository
- TurnBubble.tsx
- observations_mgmt.py
- merge-guard.js
- KnowledgeGraphStore
- GeminiAdapter
- cli-executor.js
- storage-recycler.js
- handlers_integration.py
- KubernetesSpawnHealthAdapter
- JenkinsAdapter
- llm/__init__.py
- GitHubPlatform
- CortexGraph.tsx
- ConversationTurn
- GitLabPlatform
- Headhunter
- TimeKeeperPage.tsx
- gemini_client.py
- Aligner
- ws-client.js
- handlers_cross_event.py
- useCortexData.ts
- nightwatcher_tools.py
- ui/package.json
- .__init__
- SlackChannel
- ._process_event_inner
- EphemeralProvisioner
- context_parts.py
- brain.py
- NightwatcherObserver
- formatter.py
- server.js
- adf_to_markdown
- ArgoCDObserver
- NodeInspector.tsx
- reconcile.py
- ._get_manager
- KargoObserver
- TopologyRepository
- GitHubAppAuth
- dependencies
- handlers_dispatch.py
- compilerOptions
- claude-guard.js
- DashboardWSAdapter
- PulseBatch
- tool_router.py
- VcsPlatformPort
- cortex/types.ts
- cli-setup.js
- ReflexSearcher
- StateWatcher
- get_token_meter
- devDependencies
- compilerOptions
- gemini-sidecar/package.json
- ServiceNode.tsx
- ArchitectureGraph.tsx
- JenkinsObserver
- QuotaTracker
- ObservationRepository
- ShiftsPage.tsx
- catalog-skills.js
- SlackAccessGate
- EventDrillDown.tsx
- ._authorize_plan_decision
- EscalationRepository
- FloatingWindow.tsx
- LiveAPIAdapter
- FairQueue
- generate_map.py
- _resolve_phase
- OIDCKeyAdapter
- NightwatcherContext
- .start_event_loop
- handlers_planning.py
- MultiInstallationManager
- analyzeTokens
- FilterRule
- ArchitectureEvent
- IdleTimeoutManager
- ReconcileScheduler
- _sanitize_analysis_text
- testSetup.ts
- ._extract_context_flags
- is_defer_event_available
- ._register_handlers
- CortexDevPage.tsx
- NeuronInfoPanel.tsx
- gitGuard
- parseShell
- _md_table_to_text
- generate_event_title
- entity_extractor.py
- ._github_poll_and_process
- ._process_candidates
- _prepare_console_tail
- has_unevaluated_close_blocker
- ._send_turn_to_thread
- knowledge_graph_api.py
- classifyTool
- get_quota_tracker
- _is_event_closed_or_missing
- SmartsheetMaintainerCache
- .has_reeval_signal
- Trigger
- AsyncGitHubClient
- GitLabTokenAuth
- ._post_agent_recall
- HeadhunterJira
- ._triage_and_build_evidence
- ._drain_once
- TimeKeeperObserver
- CortexRepository
- validate-mutations.sh
- list_events
- scripts
- Neuron
- state.js
- ._process_message
- _append_user_turn
- build_gate_context
- list_failed_stages
- dex_proxy
- ._run_analysis_loop
- StalenessGuard
- ResyncTrigger
- TicketNode.tsx
- classify
- derive_llm_priority
- ShiftIncident
- require-results.sh
- _WSFrameFilter
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
- _patch_enum_fields
- diagnose_rejection
- GateDefinition
- _pred_dispatch_defer
- _pred_hard_strip_defer
- _pred_jarvis_wait
- _pred_obs_plateau
- _pred_silent_park
- _tools_wait_loop
- build_report_iteration_prompt

## God Nodes (most connected - your core abstractions)
1. `BlackboardState` - 285 edges
2. `Brain` - 159 edges
3. `ConversationTurn` - 125 edges
4. `ToolContext` - 103 edges
5. `GateContext` - 96 edges
6. `react` - 85 edges
7. `EventDocument` - 82 edges
8. `fetchApi()` - 66 edges
9. `lifespan()` - 65 edges
10. `EventEvidence` - 58 edges

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

## Communities (238 total, 131 thin omitted)

### Community 0 - "BlackboardState"
Cohesion: 0.01
Nodes (17): get_event_document(), get_all_journal(), get_service_journal(), get_notebook(), get_event_observations(), get_global_observations(), get_shift_detail(), create_schedule() (+9 more)

### Community 1 - "logging"
Cohesion: 0.02
Nodes (45): _annotation_replace(), _strip_pipeline_annotations(), _sanitize_lesson_text(), _get_static_maintainer_emails(), _get_allowed_mention_authors(), _get_static_maintainer_emails(), _safe_int(), _parse_job_metadata() (+37 more)

### Community 2 - "main.py"
Cohesion: 0.02
Nodes (52): AgentConnection, AgentRegistry, agent_websocket_handler(), _heartbeat(), Architect, AgentClient, Developer, _build_prompt() (+44 more)

### Community 3 - "httpx"
Cohesion: 0.03
Nodes (34): get_blackboard(), get_pulse_tracker(), dismiss_proposals(), DismissRequest, get_all_shadow_interventions(), get_cognitive_graph(), get_cortex_activity(), get_cortex_status() (+26 more)

### Community 4 - "queue.py"
Cohesion: 0.03
Nodes (51): resolve_approval_identity(), get_archivist(), get_brain(), aligner_pending_items(), apply_lessons(), approve_event(), close_event_by_user(), CloseRequest (+43 more)

### Community 5 - "client.ts"
Cohesion: 0.03
Nodes (91): recharts, ApiError, bulkDeleteObservations(), deleteObservation(), exportObservations(), ExtractedCorrection, ExtractedLesson, ExtractionResult (+83 more)

### Community 6 - "Archivist"
Cohesion: 0.04
Nodes (5): Archivist, Pulse, _decode_cursor(), _encode_cursor(), VectorStore

### Community 7 - "WorkspaceInspector.tsx"
Cohesion: 0.05
Nodes (84): updateEventTitle(), AgentRegistryEntry, CiContext, ConversationTurn, EventEvidence, KargoStageStatus, TokenUsageDict, CiContextCard() (+76 more)

### Community 8 - "Brain"
Cohesion: 0.04
Nodes (6): Brain, on_huddle(), on_progress(), on_huddle(), on_progress(), get_registry_and_bridge()

### Community 9 - "EventSidebar.tsx"
Cohesion: 0.06
Nodes (79): getActiveEvents(), getAlignerPending(), getEventDocument(), getHeadhunterPending(), getJenkinsPending(), getJiraMissions(), getWaitingApprovalEvents(), HeadhunterTodo (+71 more)

### Community 10 - "EventDocument"
Cohesion: 0.03
Nodes (16): _close_unanswered_fc(), _build_closed_block(), build_event_header(), _build_identity_block(), _build_journal_block(), _build_mermaid_block(), build_operational_briefing(), _build_related_block() (+8 more)

### Community 11 - "auth.py"
Cohesion: 0.04
Nodes (26): spawn_event_namer_task(), can_append_message(), can_approve_event(), can_override_domain(), can_rename_event(), _claims_to_user(), get_user_from_request(), get_user_from_slack() (+18 more)

### Community 12 - "tool_gates.py"
Cohesion: 0.05
Nodes (77): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+69 more)

### Community 13 - "react"
Cohesion: 0.07
Nodes (60): lucide-react, react, applyLessons(), correctMemory(), createKnowledge(), createLesson(), deleteKnowledge(), deleteLesson() (+52 more)

### Community 14 - "http-handler.js"
Cohesion: 0.08
Nodes (62): is429Error(), registerMCPsAndHooks(), resolveCommand(), writeAgyMcpServer(), writeClaudeMcpServer(), parsePositiveInt(), buildArgoCDMcpConfig(), createAppJWT() (+54 more)

### Community 15 - "hooks/index.ts"
Cohesion: 0.06
Nodes (46): react-router-dom, @tanstack/react-query, createChatEvent(), getEvents(), getKargoStages(), AppConfig, ActivityStream(), ChatInput() (+38 more)

### Community 16 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 17 - "EventHistory.tsx"
Cohesion: 0.07
Nodes (37): getReport(), getReports(), ReportFull, ReportMeta, SubjectType, CompactCardStrip(), EventHistory(), TimeRange (+29 more)

### Community 18 - "App.tsx"
Cohesion: 0.06
Nodes (43): oidc-client-ts, react-dom, getConfig(), getIncidents(), getWSAuthFailureCallback(), Incident, setOnUnauthorized(), setTokenGetter() (+35 more)

### Community 19 - "BrainSkillLoader"
Cohesion: 0.05
Nodes (3): BrainSkillLoader, _SkillCorpus, BrainIntrospectionPort

### Community 20 - "._process_with_llm"
Cohesion: 0.04
Nodes (4): _contents_have_pruned_or_decayed(), _ensure_recall_tool_if_needed(), _QuotaShedState, _retry_backoff_delay()

### Community 21 - "components/index.ts"
Cohesion: 0.07
Nodes (43): dismissProposals(), EnhancementProposal, getFlowMetrics(), getHandoffReports(), getProposals(), HandoffReport, FlowMetrics, Dashboard() (+35 more)

### Community 22 - "ToolContext"
Cohesion: 0.07
Nodes (12): handle_message_agent(), handle_reply_to_agent(), handle_select_agent(), _sticky_work_style(), handle_classify_event(), handle_defer_event(), handle_hold_watch(), handle_wait_for_agent() (+4 more)

### Community 23 - "ScheduleRepository"
Cohesion: 0.05
Nodes (7): ScheduleCreateRequest, ScheduledEvent, delete_schedule(), get_schedule(), toggle_schedule(), update_schedule(), ScheduleRepository

### Community 26 - "TurnBubble.tsx"
Cohesion: 0.09
Nodes (38): @uiw/react-markdown-preview, approveEvent(), closeEvent(), enforceCasualDomain(), getEventReport(), rejectEvent(), submitFeedback(), ConversationFeed() (+30 more)

### Community 27 - "observations_mgmt.py"
Cohesion: 0.06
Nodes (18): get_report_client(), _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), render_pdf(), _sample_points() (+10 more)

### Community 28 - "merge-guard.js"
Cohesion: 0.04
Nodes (46): API_VALUED, ARGO_MUTATING, ARGO_READ_SUB, ARGO_READ_TOP, BODY_FLAG, BROWSER_READ, CTX, ENV_BUILTINS (+38 more)

### Community 29 - "KnowledgeGraphStore"
Cohesion: 0.08
Nodes (9): _format_graph_context(), get_graph_context(), _parse_props(), _sanitize(), translate_to_lookups(), _acquire(), KnowledgeGraphStore, _sanitize() (+1 more)

### Community 30 - "GeminiAdapter"
Cohesion: 0.09
Nodes (9): _attach_signature_to_parts(), _clone_part_with_sig(), _coerce_part(), _decode_sig_bytes(), _extract_part_signature(), GeminiAdapter, _is_empty_sig_carrier(), _part_has_fc() (+1 more)

### Community 31 - "cli-executor.js"
Cohesion: 0.09
Nodes (37): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, MAX_TASK_WALL_MS, MAX_TIMER_MS, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS, STORAGE_PRETASK_TIMEOUT_MS, resolveStorageRoot }, buildCLICommand(), buildTimeoutResult(), { checkAndRecycleStorage, pinTaskCwd, unpinTaskCwd }, CLAUDE_JSON_PATH, cp, createInactivityWatchdog(), executeCLI() (+29 more)

### Community 32 - "storage-recycler.js"
Cohesion: 0.08
Nodes (37): withTaskStorage(), MAX_TASK_WALL_MS, parseTimerMs(), resolveStorageRoot(), resolveTimeoutMs(), ROLE_TIMEOUTS, STORAGE_ACTIVITY_HEARTBEAT_MS, STORAGE_MAX_TIER3_DELETIONS (+29 more)

### Community 33 - "handlers_integration.py"
Cohesion: 0.08
Nodes (18): _alert_wrapper_retrigger(), _do_retrigger(), _get_jira_reporter(), handle_refresh_github_context(), handle_refresh_gitlab_context(), handle_refresh_kargo_context(), _is_darwin_reentrant_caller(), jenkins_retrigger_cooldown_key() (+10 more)

### Community 34 - "KubernetesSpawnHealthAdapter"
Cohesion: 0.07
Nodes (5): KubernetesSpawnHealthAdapter, _PodHealthState, SpawnHealthPort, SpawnPollResult, SpawnStatus

### Community 35 - "JenkinsAdapter"
Cohesion: 0.06
Nodes (6): BuildDetails, JenkinsAdapter, JenkinsPlatformPort, JobResult, JobRunState, ViewScanResult

### Community 36 - "llm/__init__.py"
Cohesion: 0.08
Nodes (7): ClaudeAdapter, create_adapter(), FunctionCall, LLMChunk, LLMPort, LLMResponse, TokenUsage

### Community 38 - "CortexGraph.tsx"
Cohesion: 0.09
Nodes (35): graphology, AGENTS, DOMAINS, eventColor(), getExecutiveNeurons(), getStructuralEdges(), HEMISPHERE_X, NEURON_DESCRIPTIONS (+27 more)

### Community 39 - "ConversationTurn"
Cohesion: 0.17
Nodes (27): emit_tool_result(), handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_report_incident(), handle_ask_release_ai(), handle_comment_jira_issue(), handle_fetch_jira_issue() (+19 more)

### Community 42 - "TimeKeeperPage.tsx"
Cohesion: 0.12
Nodes (24): createSchedule(), deleteSchedule(), getSchedules(), refineInstructions(), ScheduleCreatePayload, ScheduleItem, toggleSchedule(), updateSchedule() (+16 more)

### Community 43 - "gemini_client.py"
Cohesion: 0.10
Nodes (13): _extract_call_syntax(), _parse_drain_timeout(), Reservation, _stale_reservation_ttl_s(), _get_timeout_env_warned(), _get_timeout_order_warned(), parse_timeout_env(), process_stream_call_syntax_buffer() (+5 more)

### Community 45 - "ws-client.js"
Cohesion: 0.10
Nodes (26): clearIdleTimer(), {
  DEFAULT_WORK_DIR, AGENT_CLI, AGENT_MODEL, AGENT_ROLE,
  EVENT_ID, EPHEMERAL, IDLE_TIMEOUT_MS,
  CLI_429_MAX_RETRIES, CLI_429_INITIAL_DELAY_MS, CLI_429_BACKOFF_MULTIPLIER,
  resolveTimeoutMs, parsePositiveInt, MAX_TASK_WALL_MS, MAX_TIMER_MS,
}, { ensureEventDocument }, { executeCLIStreaming, prepareResultsDir, is429Error }, { filterSkillsByRole, filterSkillsByMode, swapActiveRules, restoreAllSkills }, fs, handleCancel(), handleTask() (+18 more)

### Community 46 - "handlers_cross_event.py"
Cohesion: 0.09
Nodes (15): build_function_response(), build_single_function_response(), format_evidence_decay_reference(), _safe_int(), _coerce_turn_int(), handle_recall_pruned_turns(), _parse_turn_int(), _sanitize_recalled() (+7 more)

### Community 47 - "useCortexData.ts"
Cohesion: 0.15
Nodes (29): getCognitiveGraph(), getCortexActivity(), getKGServiceDetail(), getKGServices(), getKGStats(), getKnowledgeById(), getMemory(), getRecentPulses() (+21 more)

### Community 48 - "nightwatcher_tools.py"
Cohesion: 0.11
Nodes (12): extract_full_links(), _normalize_gitlab_host(), build_extend_tool(), build_report_tool(), build_summary_tool(), _fallback_platform(), get_phase_tools(), _handle_declare_clusters() (+4 more)

### Community 49 - "ui/package.json"
Cohesion: 0.08
Nodes (29): autoprefixer, cronstrue, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, graphology-layout-forceatlas2 (+21 more)

### Community 50 - ".__init__"
Cohesion: 0.07
Nodes (4): _incr_flow_counter_safely(), _parse_positive_int_env(), BrainLifecyclePort, BroadcastPort

### Community 52 - "._process_event_inner"
Cohesion: 0.07
Nodes (5): _compute_processed_up_to(), _has_non_user_turns(), _is_automated_nudge(), _is_seed_turn(), _sanitize_error_text()

### Community 53 - "EphemeralProvisioner"
Cohesion: 0.09
Nodes (3): DispatchMetrics, EphemeralProvisioner, SpawnFailed

### Community 54 - "context_parts.py"
Cohesion: 0.12
Nodes (13): _apply_sibling_signature(), compress_contents(), contents_have_pruned_or_decayed(), estimate_msg_tokens(), estimate_tokens(), extract_model_parts(), format_prune_notice(), _get_part_sig() (+5 more)

### Community 55 - "brain.py"
Cohesion: 0.08
Nodes (11): _BatchContext, compute_dispatch_backpressure(), _init_tool_names(), RepetitionCollapse, _sanitize_override_reason(), _select_dispatch_tier(), _wrap_section(), LLMStreamInterChunkTimeoutError (+3 more)

### Community 56 - "NightwatcherObserver"
Cohesion: 0.12
Nodes (5): ShiftReport, _env_float(), _env_int(), NightwatcherObserver, build_summary_prompt()

### Community 57 - "formatter.py"
Cohesion: 0.12
Nodes (12): build_home_tab_view(), _context_line(), create_feedback_block(), format_event_summary(), format_plan_block(), format_task_card(), format_tool_result_blocks(), format_turn() (+4 more)

### Community 58 - "server.js"
Cohesion: 0.09
Nodes (18): { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, ensureEventDocument(), fs, path, stageEventDocument(), fetchEventDocument(), fs, { handleRequest } (+10 more)

### Community 59 - "adf_to_markdown"
Cohesion: 0.12
Nodes (10): _adf_to_text(), _escape_jql_string(), JiraIncidentAdapter, adf_to_markdown(), _apply_marks(), _children(), _render(), _render_list() (+2 more)

### Community 61 - "NodeInspector.tsx"
Cohesion: 0.13
Nodes (22): getClosedEvents(), ArchitectureEvent, ArgoCDOperation, EVENT_LABELS, EventItem(), EventItemProps, healthTone(), lastOperationSummary() (+14 more)

### Community 62 - "reconcile.py"
Cohesion: 0.15
Nodes (10): sanitize_redis_port(), _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers(), main() (+2 more)

### Community 66 - "GitHubAppAuth"
Cohesion: 0.11
Nodes (3): _find_pem_file(), get_github_auth(), GitHubAppAuth

### Community 67 - "dependencies"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 68 - "handlers_dispatch.py"
Cohesion: 0.13
Nodes (7): _resolve_escalation_scope(), CIAnalysis, _esc(), _esc_join(), event_to_markdown(), maintainer_env_key(), resolve_maintainer_emails()

### Community 69 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 70 - "claude-guard.js"
Cohesion: 0.14
Nodes (18): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+10 more)

### Community 72 - "PulseBatch"
Cohesion: 0.11
Nodes (4): PulseBatch, PulsePort, PulseObserver, PulseTracker

### Community 73 - "tool_router.py"
Cohesion: 0.10
Nodes (4): IdleTimeoutPort, IncidentAdapterPort, StateWatcherPort, resolve_event_domain()

### Community 76 - "cortex/types.ts"
Cohesion: 0.17
Nodes (18): CortexHeartbeat(), CortexHeartbeatProps, ensureKeyframes(), CortexLiveFeed(), CortexLiveFeedProps, FILTER_PILLS, FilterKey, getStoredFilter() (+10 more)

### Community 77 - "cli-setup.js"
Cohesion: 0.13
Nodes (18): { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync }, filterSkillsByMode() (+10 more)

### Community 79 - "StateWatcher"
Cohesion: 0.13
Nodes (3): _QueueEntry, StateWatcher, _Subscription

### Community 80 - "get_token_meter"
Cohesion: 0.10
Nodes (3): get_token_meter(), TokenMeter, TokenUsageDict

### Community 81 - "devDependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 82 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 83 - "gemini-sidecar/package.json"
Cohesion: 0.11
Nodes (18): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+10 more)

### Community 84 - "ServiceNode.tsx"
Cohesion: 0.15
Nodes (13): @xyflow/react, HealthStatus, NodeType, AppNodeData, ARGOCD_HEALTH_COLORS, SYNC_ICONS, NamespaceGroupNodeData, GENERIC_TAGS (+5 more)

### Community 85 - "ArchitectureGraph.tsx"
Cohesion: 0.17
Nodes (16): @dagrejs/dagre, applyDagreLayout(), applyGridLayout(), applyLayout(), ArchitectureGraph(), ArchitectureGraphInner(), buildGraph(), computeIdHash() (+8 more)

### Community 87 - "QuotaTracker"
Cohesion: 0.14
Nodes (3): QuotaExhaustedError, QuotaTracker, RequestExceedsBurstError

### Community 89 - "ShiftsPage.tsx"
Cohesion: 0.23
Nodes (16): getCurrentShift(), getShiftDetail(), getShiftsList(), ShiftReportFull, ShiftReportSummary, FailedClusterBadge(), getISOWeek(), getWeekDates() (+8 more)

### Community 90 - "catalog-skills.js"
Cohesion: 0.16
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 92 - "EventDrillDown.tsx"
Cohesion: 0.18
Nodes (13): three, getEventPulses(), EventSource, BrainCore(), EventDrillDown(), FRICTION_COLORS, WHISPER_COLORS, PulseTimeline() (+5 more)

### Community 94 - "._authorize_plan_decision"
Cohesion: 0.13
Nodes (3): _PlanDecision, handle_approve(), handle_reject()

### Community 96 - "FloatingWindow.tsx"
Cohesion: 0.20
Nodes (14): AgentStreamCard(), AgentStreamCardProps, MessageCards(), DEFAULT_POS, DEFAULT_SIZE, EMPTY_MESSAGES, FloatingWindow(), FloatingWindowProps (+6 more)

### Community 99 - "generate_map.py"
Cohesion: 0.19
Nodes (6): _enumerate_gates(), _GateInfo, generate_phase_tool_map(), _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 103 - "NightwatcherContext"
Cohesion: 0.20
Nodes (9): ShiftInvestigation, execute_tool(), _handle_consult_deep_memory(), _handle_dispatch_investigation(), _handle_get_event_report(), _handle_post_shift_summary(), _handle_search_existing_incidents(), _handle_search_journal() (+1 more)

### Community 105 - "handlers_planning.py"
Cohesion: 0.23
Nodes (7): _auto_complete_step(), _canonical_role(), handle_create_plan(), handle_get_plan_progress(), _is_failed_turn(), _is_orchestrator_turn(), _normalize_step_id()

### Community 108 - "analyzeTokens"
Cohesion: 0.19
Nodes (13): analyzeString(), analyzeTokens(), assignName(), base(), combineCategories(), configEnvGuard(), configFileWriteGuard(), hasSubseq() (+5 more)

### Community 116 - "_sanitize_analysis_text"
Cohesion: 0.20
Nodes (5): _clamp_confidence(), _sanitize_analysis_text(), _strip_newlines(), _validate_analysis(), _validate_triage_entry()

### Community 117 - "testSetup.ts"
Cohesion: 0.18
Nodes (5): @tailwindcss/vite, @testing-library/react, vite, @vitejs/plugin-react, vitest

### Community 119 - "is_defer_event_available"
Cohesion: 0.18
Nodes (6): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 120 - "._register_handlers"
Cohesion: 0.18
Nodes (3): build_access_denied_home_view(), handle_app_home_opened(), handle_home_create_event()

### Community 121 - "CortexDevPage.tsx"
Cohesion: 0.31
Nodes (9): CortexDevPage(), devQueryClient, MOCK_CORTEX_STATUS, MOCK_EVENT_ID, MOCK_NEURONS, MOCK_PULSE_BATCHES, MOCK_SHADOW, MOCK_THINKING (+1 more)

### Community 122 - "NeuronInfoPanel.tsx"
Cohesion: 0.29
Nodes (10): asNumber(), asString(), asStringArray(), Badge(), describeNeuron(), Hdr(), NeuronInfoPanel(), AGENT_NEURON_COLORS (+2 more)

### Community 123 - "gitGuard"
Cohesion: 0.29
Nodes (10): bareBranchProtected(), configWriteGuard(), externalGitCommand(), gitGuard(), gitQuery(), isProtected(), normRef(), pushGuard() (+2 more)

### Community 124 - "parseShell"
Cohesion: 0.33
Nodes (10): bodySubstitutions(), decodeAnsiC(), isArrayAssignPrefix(), isWordStart(), matchBacktick(), matchParen(), parseShell(), readHeredocStart() (+2 more)

### Community 125 - "_md_table_to_text"
Cohesion: 0.20
Nodes (5): _replace(), _md_table_to_block_kit(), _md_table_to_text(), _md_to_mrkdwn(), _parse_md_table()

### Community 126 - "generate_event_title"
Cohesion: 0.22
Nodes (3): generate_event_title(), get_adapter(), _get_semaphore()

### Community 128 - "entity_extractor.py"
Cohesion: 0.33
Nodes (5): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship

### Community 132 - "_prepare_console_tail"
Cohesion: 0.20
Nodes (4): _prepare_console_tail(), _redact_match(), _redact_secrets_in_text(), _sanitize_console_tail()

### Community 133 - "has_unevaluated_close_blocker"
Cohesion: 0.20
Nodes (4): has_unevaluated_close_blocker(), _pred_jarvis_response(), _pred_unevaluated_close(), is_jarvis_acknowledgment()

### Community 134 - "._send_turn_to_thread"
Cohesion: 0.27
Nodes (3): extract_tables(), get_agent_notification_text(), get_turn_attachment_color()

### Community 135 - "knowledge_graph_api.py"
Cohesion: 0.31
Nodes (4): get_kg_store(), get_service_detail(), get_stats(), list_services()

### Community 136 - "classifyTool"
Cohesion: 0.31
Nodes (9): apiTokens(), apiWriteNeedsGuard(), branchValues(), classifyTool(), hasOpaqueTarget(), httpGuard(), httpMethod(), isReadMethod() (+1 more)

### Community 137 - "get_quota_tracker"
Cohesion: 0.22
Nodes (3): get_quota_tracker(), llm_stats(), receive_telemetry()

### Community 153 - "validate-mutations.sh"
Cohesion: 0.57
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

### Community 155 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 156 - "Neuron"
Cohesion: 0.38
Nodes (7): ActiveEvent, KGServiceEntity, CortexGraphProps, GraphLoaderProps, NeuronInfoPanelProps, Neuron, WorkspaceTaskItemProps

### Community 157 - "state.js"
Cohesion: 0.33
Nodes (4): { AGENT_ROLE }, _blackboardTurns, _inboundMessages, _teammateMessages

### Community 165 - "_append_user_turn"
Cohesion: 0.33
Nodes (3): _append_user_turn(), _is_function_response_part(), _validated_parts()

### Community 166 - "build_gate_context"
Cohesion: 0.33
Nodes (3): build_gate_context(), conversation_has_decayed_turns(), _decay_payload_len()

### Community 175 - "TicketNode.tsx"
Cohesion: 0.40
Nodes (4): STATUS_COLORS, TICKET_COLORS, TicketNodeComponent(), TicketNodeData

### Community 176 - "classify"
Cohesion: 0.50
Nodes (4): classify(), main(), shellCategory(), shellNeedsGuard()

### Community 195 - "overrides"
Cohesion: 0.67
Nodes (3): overrides, @typescript-eslint/typescript-estree, minimatch

## Knowledge Gaps
- **13 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+8 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2299 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **131 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `logging`, `main.py`, `httpx`, `queue.py`, `Brain`, `EventDocument`, `auth.py`, `HeadhunterJira`, `ToolContext`, `ScheduleRepository`, `EventRepository`, `list_events`, `observations_mgmt.py`, `ConversationTurn`, `._restage_pending_signal`, `._stage_pending_signal`, `._count_pending`, `nightwatcher_tools.py`, `.__init__`, `brain.py`, `NightwatcherObserver`, `._commit_pending_signal`, `._drain_pending`, `DashboardWSAdapter`, `PulseBatch`, `tool_router.py`, `LiveAPIAdapter`, `_resolve_phase`, `ArchitectureEvent`, `generate_event_title`?**
  _High betweenness centrality (0.115) - this node is a cross-community bridge._
- **Are the 80 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 80 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.010785191819674578 - nodes in this community are weakly interconnected._
- **Why does `Brain` connect `Brain` to `BlackboardState`, `logging`, `main.py`, `httpx`, `Archivist`, `EventDocument`, `._post_agent_recall`, `BrainSkillLoader`, `._process_with_llm`, `ToolContext`, `ConversationTurn`, `StalenessGuard`, `ResyncTrigger`, `._sweep_waiting_approval_zombies`, `.__init__`, `._process_event_inner`, `brain.py`, `.append_and_broadcast`, `.broadcast`, `.clear_jarvis_wait`, `.next_turn_number`, `.set_headhunter_close_signal`, `DashboardWSAdapter`, `PulseBatch`, `._check_chat_staleness`, `._check_jarvis_staleness`, `.clear_cycle_id`, `.create_kargo_event`, `ReflexSearcher`, `._determine_thinking_params_legacy`, `StateWatcher`, `.get_ephemeral_provisioner`, `.get_incident_adapter`, `._get_jira_reporter`, `.get_skill_loader`, `.get_staleness_guard_metrics`, `.has_jarvis_waiters`, `._is_event_deferred`, `.is_task_running`, `.last_processed_time`, `.pending_jarvis_event_ids`, `.set_ephemeral_provisioner`, `.set_live_adapter`, `.start_event_loop`, `IdleTimeoutManager`, `ReconcileScheduler`, `._extract_context_flags`?**
  _High betweenness centrality (0.076) - this node is a cross-community bridge._
- **Are the 19 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 19 INFERRED edges - model-reasoned connections that need verification._
- **Should `logging` be split into smaller, more focused modules?**
  _Cohesion score 0.022297449785601445 - nodes in this community are weakly interconnected._