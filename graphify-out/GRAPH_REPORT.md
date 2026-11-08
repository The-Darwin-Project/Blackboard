# Graph Report - Blackboard  (2026-11-08)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 5093 nodes · 11372 edges · 206 communities (100 shown, 106 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 939 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `7f32874a`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BlackboardState
- logging
- brain.py
- client.ts
- auth.py
- OpsStateContext.tsx
- EventEvidence
- tool_gates.py
- EventDocument
- Brain
- Archivist
- ReconcileScheduler
- App.tsx
- ._run_agent_task
- EventSidebar.tsx
- WorkspaceInspector.tsx
- http-handler.js
- colors.ts
- BrainSkillLoader
- jenkins-mcp.js
- react
- nightwatcher_tools.py
- SlackChannel
- TurnBubble.tsx
- AgentRegistry
- jenkins_observer.py
- _BrainToolContext
- merge-guard.js
- ToolContext
- handlers_integration.py
- ui/package.json
- cli-executor.js
- httpx
- storage-recycler.js
- JenkinsAdapter
- EventRepository
- Aligner
- GitHubPlatform
- WorkspaceTaskItem.tsx
- formatter.py
- ._process_with_llm
- ConversationTurn
- GitLabPlatform
- AgentClient
- TimeKeeperPage.tsx
- gemini_client.py
- ArchitectureGraph.tsx
- lifespan
- Headhunter
- main.py
- NodeInspector.tsx
- ws-client.js
- useCortexData.ts
- StreamGrid.tsx
- EventDrillDown.tsx
- queue.py
- server.js
- ._close_and_broadcast
- cognitive_graph.py
- KnowledgeGraphStore
- LiveAPIAdapter
- StateWatcher
- adf_to_markdown
- IdleTimeoutManager
- NightwatcherObserver
- CortexGraph.tsx
- ArgoCDObserver
- reconcile.py
- VectorStore
- ._get_manager
- GeminiAdapter
- get_archivist
- KargoObserver
- TopologyRepository
- dependencies
- quota_tracker.py
- compilerOptions
- claude-guard.js
- .get_event
- GitHubAppAuth
- cli-setup.js
- VcsPlatformPort
- PulseBatch
- observations_reporter.py
- DashboardWSAdapter
- ReflexSearcher
- devDependencies
- compilerOptions
- EphemeralProvisioner
- get_report
- gemini-sidecar/package.json
- tool_router.py
- ObservationRepository
- ShiftsPage.tsx
- cortex/types.ts
- catalog-skills.js
- OIDCKeyAdapter
- ClaudeAdapter
- EscalationRepository
- update_event_title
- list_active_events
- generate_map.py
- KubernetesSpawnHealthAdapter
- graph_recall.py
- JenkinsObserver
- RedisClient
- _append_user_turn
- ScheduleRepository
- MultiInstallationManager
- analyzeTokens
- FilterRule
- .scroll
- ._extract_context_flags
- TokenMeter
- ScheduleCreateRequest
- NeuronInfoPanel.tsx
- _resolve_phase
- HeadhunterJira
- SlackAccessGate
- CortexLiveFeed.tsx
- handle_classify_event
- is_defer_event_available
- cortex-constants.ts
- spawn_health.py
- gitGuard
- parseShell
- approve_event
- ._post_agent_recall
- entity_extractor.py
- ._process_candidates
- ._triage_and_build_evidence
- ._drain_once
- has_unevaluated_close_blocker
- knowledge_graph_api.py
- close_event_by_user
- classifyTool
- get_quota_tracker
- SpawnPollResult
- SmartsheetMaintainerCache
- .has_reeval_signal
- create_schedule
- AsyncGitHubClient
- GitLabTokenAuth
- _is_event_closed_or_missing
- ._evaluate_health
- ConversationMessage
- TimeKeeperObserver
- CortexRepository
- validate-mutations.sh
- handle_report_incident
- scripts
- state.js
- ._process_message
- DispatchMetrics
- list_failed_stages
- ._wait_for_registration
- classify
- derive_llm_priority
- _patch_enum_fields
- headhunter_pending_todos
- require-results.sh
- _env_flag
- TokenUsageDict
- findDuplicateJsonKeys.ts
- tsconfig.json
- gh-wrapper.sh
- check-inbox.sh
- cluster-context.sh
- validate-reviewer-bash.sh
- huddleSendMessage.sh
- update-agy.sh
- sendResults.sh
- build_gate_context
- diagnose_rejection
- GateDefinition
- _pred_dispatch_defer
- _pred_hard_strip_defer
- _pred_jarvis_wait
- _pred_obs_plateau
- _pred_silent_park
- _tools_wait_loop

## God Nodes (most connected - your core abstractions)
1. `BlackboardState` - 285 edges
2. `Brain` - 151 edges
3. `ConversationTurn` - 123 edges
4. `ToolContext` - 103 edges
5. `GateContext` - 94 edges
6. `react` - 85 edges
7. `EventDocument` - 79 edges
8. `fetchApi()` - 66 edges
9. `lifespan()` - 65 edges
10. `LiveAPIAdapter` - 58 edges

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

## Communities (206 total, 106 thin omitted)

### Community 0 - "BlackboardState"
Cohesion: 0.01
Nodes (12): get_event_document(), get_all_journal(), get_service_journal(), get_notebook(), get_event_observations(), get_global_observations(), get_graph_data(), get_mermaid_diagram() (+4 more)

### Community 1 - "logging"
Cohesion: 0.03
Nodes (21): _heartbeat(), _check_security(), _get_static_maintainer_emails(), _get_allowed_mention_authors(), _get_static_maintainer_emails(), _safe_int(), safe_execution(), wrapper() (+13 more)

### Community 2 - "brain.py"
Cohesion: 0.03
Nodes (46): _apply_sibling_signature(), build_function_response(), build_single_function_response(), compress_contents(), estimate_msg_tokens(), estimate_tokens(), extract_model_parts(), normalize_response_parts() (+38 more)

### Community 3 - "client.ts"
Cohesion: 0.03
Nodes (102): recharts, @tanstack/react-query, ApiError, bulkDeleteObservations(), deleteNote(), deleteObservation(), exportObservations(), ExtractedCorrection (+94 more)

### Community 4 - "auth.py"
Cohesion: 0.03
Nodes (31): record_token_usage(), _claims_to_user(), get_user_from_request(), get_user_from_websocket(), require_auth(), require_obs_admin(), UserContext, _validate_jwt() (+23 more)

### Community 5 - "OpsStateContext.tsx"
Cohesion: 0.04
Nodes (80): react-router-dom, createChatEvent(), getActiveEvents(), getAgents(), getAlignerPending(), getEventDocument(), getJenkinsPending(), getKargoStages() (+72 more)

### Community 6 - "EventEvidence"
Cohesion: 0.04
Nodes (25): generate_event_title(), get_adapter(), _get_semaphore(), spawn_event_namer_task(), create_adapter(), can_append_message(), can_approve_event(), get_user_from_slack() (+17 more)

### Community 7 - "tool_gates.py"
Cohesion: 0.05
Nodes (78): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+70 more)

### Community 8 - "EventDocument"
Cohesion: 0.03
Nodes (11): _close_unanswered_fc(), _build_closed_block(), build_event_header(), _build_identity_block(), _build_journal_block(), _build_mermaid_block(), _build_related_block(), _build_subject_block() (+3 more)

### Community 11 - "ReconcileScheduler"
Cohesion: 0.04
Nodes (7): FlowCollector, FairQueue, ReconcileScheduler, Trigger, QueueTrigger, ResyncTrigger, StalenessGuard

### Community 12 - "App.tsx"
Cohesion: 0.06
Nodes (52): oidc-client-ts, react-dom, dismissProposals(), EnhancementProposal, getConfig(), getHandoffReports(), getProposals(), getWSAuthFailureCallback() (+44 more)

### Community 13 - "._run_agent_task"
Cohesion: 0.06
Nodes (10): on_huddle(), on_progress(), on_huddle(), on_progress(), _compute_processed_up_to(), _is_automated_nudge(), _sanitize_error_text(), _sanitize_override_reason() (+2 more)

### Community 14 - "EventSidebar.tsx"
Cohesion: 0.08
Nodes (56): getHeadhunterPending(), getJiraMissions(), HeadhunterTodo, postJiraAction(), AgentRegistryEntry, ACTION_BADGE, formatAge(), HeadhunterQueuePanel() (+48 more)

### Community 15 - "WorkspaceInspector.tsx"
Cohesion: 0.07
Nodes (50): CiContext, ConversationTurn, EventEvidence, TokenUsageDict, CiContextCard(), CiContextCardProps, ConsoleTailBlock(), FailedJobRow() (+42 more)

### Community 16 - "http-handler.js"
Cohesion: 0.09
Nodes (58): resolveCommand(), writeAgyMcpServer(), writeClaudeMcpServer(), buildArgoCDMcpConfig(), createAppJWT(), discoverAndGenerateTokens(), _discoverAndGenerateTokensInner(), discoverInstallations() (+50 more)

### Community 17 - "colors.ts"
Cohesion: 0.07
Nodes (39): @tanstack/react-table, getReport(), getReports(), ReportFull, ReportMeta, CompactCardStrip(), EventHistory(), TimeRange (+31 more)

### Community 18 - "BrainSkillLoader"
Cohesion: 0.04
Nodes (4): BrainSkillLoader, _SkillCorpus, _wrap_section(), BrainIntrospectionPort

### Community 19 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 20 - "react"
Cohesion: 0.08
Nodes (53): lucide-react, react, applyLessons(), correctMemory(), createKnowledge(), createLesson(), deleteKnowledge(), deleteLesson() (+45 more)

### Community 21 - "nightwatcher_tools.py"
Cohesion: 0.07
Nodes (25): PulseContext, ShiftIncident, ShiftInvestigation, build_report_iteration_prompt(), build_summary_prompt(), extract_full_links(), _normalize_gitlab_host(), build_extend_tool() (+17 more)

### Community 22 - "SlackChannel"
Cohesion: 0.05
Nodes (7): extract_tables(), _replace(), _md_table_to_block_kit(), SlackChannel, handle_app_home_opened(), handle_home_create_event(), handle_reject()

### Community 23 - "TurnBubble.tsx"
Cohesion: 0.08
Nodes (41): @uiw/react-markdown-preview, approveEvent(), closeEvent(), enforceCasualDomain(), getEventReport(), rejectEvent(), submitFeedback(), MessageStatus (+33 more)

### Community 24 - "AgentRegistry"
Cohesion: 0.06
Nodes (12): AgentConnection, AgentRegistry, agent_websocket_handler(), _build_prompt(), consume_wake_task(), _consume(), _dispatch_timeout_s(), dispatch_to_agent() (+4 more)

### Community 25 - "jenkins_observer.py"
Cohesion: 0.06
Nodes (17): _annotation_replace(), _strip_pipeline_annotations(), _sanitize_lesson_text(), _clamp_confidence(), _parse_job_metadata(), _prepare_console_tail(), _redact_match(), _redact_secrets_in_text() (+9 more)

### Community 27 - "merge-guard.js"
Cohesion: 0.04
Nodes (46): API_VALUED, ARGO_MUTATING, ARGO_READ_SUB, ARGO_READ_TOP, BODY_FLAG, BROWSER_READ, CTX, ENV_BUILTINS (+38 more)

### Community 28 - "ToolContext"
Cohesion: 0.09
Nodes (10): handle_message_agent(), handle_reply_to_agent(), handle_select_agent(), _sticky_work_style(), handle_defer_event(), handle_hold_watch(), handle_respond_to_jarvis(), handle_wait_for_agent() (+2 more)

### Community 29 - "handlers_integration.py"
Cohesion: 0.08
Nodes (19): _alert_wrapper_retrigger(), _do_retrigger(), _get_jira_reporter(), handle_notify_user_slack(), handle_refresh_github_context(), handle_refresh_gitlab_context(), handle_refresh_kargo_context(), _is_darwin_reentrant_caller() (+11 more)

### Community 30 - "ui/package.json"
Cohesion: 0.05
Nodes (36): autoprefixer, cronstrue, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, graphology-layout-forceatlas2 (+28 more)

### Community 31 - "cli-executor.js"
Cohesion: 0.09
Nodes (36): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS, STORAGE_PRETASK_TIMEOUT_MS, resolveStorageRoot }, buildCLICommand(), { checkAndRecycleStorage, pinTaskCwd, unpinTaskCwd }, CLAUDE_JSON_PATH, cp, executeCLI(), executeCLIStreaming(), FALLBACK_MODEL (+28 more)

### Community 32 - "httpx"
Cohesion: 0.07
Nodes (14): handle_approve(), dex_proxy(), approve_mission(), dismiss_mission(), _infer_phase(), _jira_config(), list_missions(), reanalyze_mission() (+6 more)

### Community 33 - "storage-recycler.js"
Cohesion: 0.08
Nodes (34): withTaskStorage(), resolveStorageRoot(), ROLE_TIMEOUTS, STORAGE_ACTIVITY_HEARTBEAT_MS, STORAGE_MAX_TIER3_DELETIONS, STORAGE_PRETASK_TIMEOUT_MS, STORAGE_RESULTS_TTL_MS, STORAGE_STALE_MS (+26 more)

### Community 34 - "JenkinsAdapter"
Cohesion: 0.06
Nodes (6): BuildDetails, JenkinsAdapter, JenkinsPlatformPort, JobResult, JobRunState, ViewScanResult

### Community 38 - "WorkspaceTaskItem.tsx"
Cohesion: 0.09
Nodes (31): AgentStreamCard(), AgentStreamCardProps, MessageCards(), DeferCountdownBar(), STATUS_COLORS, TICKET_COLORS, TicketNodeComponent(), TicketNodeData (+23 more)

### Community 39 - "formatter.py"
Cohesion: 0.08
Nodes (17): build_access_denied_home_view(), build_home_tab_view(), _context_line(), create_feedback_block(), format_plan_block(), format_task_card(), format_tool_result_blocks(), format_turn() (+9 more)

### Community 41 - "ConversationTurn"
Cohesion: 0.15
Nodes (25): emit_tool_result(), handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_ask_release_ai(), handle_comment_jira_issue(), handle_fetch_jira_issue(), handle_greenwave() (+17 more)

### Community 43 - "AgentClient"
Cohesion: 0.08
Nodes (4): Architect, AgentClient, Developer, SysAdmin

### Community 44 - "TimeKeeperPage.tsx"
Cohesion: 0.12
Nodes (24): createSchedule(), deleteSchedule(), getSchedules(), refineInstructions(), ScheduleCreatePayload, ScheduleItem, toggleSchedule(), updateSchedule() (+16 more)

### Community 45 - "gemini_client.py"
Cohesion: 0.11
Nodes (10): _extract_call_syntax(), FunctionCall, LLMChunk, LLMPort, LLMResponse, process_stream_call_syntax_buffer(), sanitize_call_syntax(), scan_call_syntax() (+2 more)

### Community 46 - "ArchitectureGraph.tsx"
Cohesion: 0.09
Nodes (26): @dagrejs/dagre, @xyflow/react, HealthStatus, NodeType, AppNodeData, applyDagreLayout(), applyGridLayout(), applyLayout() (+18 more)

### Community 47 - "lifespan"
Cohesion: 0.06
Nodes (9): set_agents(), set_archivist(), set_argocd_observer(), set_blackboard(), set_brain(), set_kargo_observer(), set_registry_and_bridge(), lifespan() (+1 more)

### Community 48 - "Headhunter"
Cohesion: 0.08
Nodes (3): Headhunter, _raise_if_systemic_failure(), _sanitize_xml_fence()

### Community 49 - "main.py"
Cohesion: 0.08
Nodes (14): set_kg_store(), set_pulse_tracker(), agent_ws_endpoint(), api_info(), get_config(), get_event_flow(), get_flow_history(), get_flow_metrics() (+6 more)

### Community 50 - "NodeInspector.tsx"
Cohesion: 0.10
Nodes (28): getClosedEvents(), getEvents(), ArchitectureEvent, ArgoCDOperation, ActivityStream(), ArchitectureGraph(), ArchitectureGraphInner(), computeIdHash() (+20 more)

### Community 51 - "ws-client.js"
Cohesion: 0.09
Nodes (26): is429Error(), {
  DEFAULT_WORK_DIR, AGENT_CLI, AGENT_MODEL, AGENT_ROLE,
  EVENT_ID, EPHEMERAL, IDLE_TIMEOUT_MS,
  CLI_429_MAX_RETRIES, CLI_429_INITIAL_DELAY_MS, CLI_429_BACKOFF_MULTIPLIER,
}, { ensureEventDocument }, { executeCLIStreaming, prepareResultsDir, is429Error }, { filterSkillsByRole, filterSkillsByMode, swapActiveRules, restoreAllSkills }, fs, handleCancel(), resetTimer() (+18 more)

### Community 52 - "useCortexData.ts"
Cohesion: 0.16
Nodes (28): getCognitiveGraph(), getCortexActivity(), getKGServiceDetail(), getKGServices(), getKGStats(), getKnowledgeById(), getMemory(), getRecentPulses() (+20 more)

### Community 53 - "StreamGrid.tsx"
Cohesion: 0.13
Nodes (25): Dashboard(), GridTile(), GridTileProps, TileType, InlineMarkdownViewer(), EmptyState(), LayoutMode, StreamGrid() (+17 more)

### Community 54 - "EventDrillDown.tsx"
Cohesion: 0.12
Nodes (24): three, getEventPulses(), BrainCore(), CortexDevPage(), devQueryClient, CortexLiveFeedProps, EventDrillDown(), EventDrillDownProps (+16 more)

### Community 55 - "queue.py"
Cohesion: 0.11
Nodes (16): can_override_domain(), apply_lessons(), correct_memory(), CorrectMemoryRequest, create_knowledge(), create_lesson(), enforce_casual_domain(), EnforceCasualRequest (+8 more)

### Community 56 - "server.js"
Cohesion: 0.08
Nodes (18): hasRegistryCredentials(), { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, fs, path, stageEventDocument(), fetchEventDocument(), fs, { handleRequest } (+10 more)

### Community 57 - "._close_and_broadcast"
Cohesion: 0.08
Nodes (3): _has_non_user_turns(), _is_seed_turn(), get_token_meter()

### Community 58 - "cognitive_graph.py"
Cohesion: 0.10
Nodes (12): get_brain(), get_pulse_tracker(), dismiss_proposals(), DismissRequest, get_all_shadow_interventions(), get_cognitive_graph(), get_cortex_activity(), get_cortex_status() (+4 more)

### Community 59 - "KnowledgeGraphStore"
Cohesion: 0.15
Nodes (4): _acquire(), KnowledgeGraphStore, _sanitize(), _with_timeout()

### Community 61 - "StateWatcher"
Cohesion: 0.10
Nodes (3): _QueueEntry, StateWatcher, _Subscription

### Community 62 - "adf_to_markdown"
Cohesion: 0.12
Nodes (10): _adf_to_text(), _escape_jql_string(), JiraIncidentAdapter, adf_to_markdown(), _apply_marks(), _children(), _render(), _render_list() (+2 more)

### Community 63 - "IdleTimeoutManager"
Cohesion: 0.08
Nodes (3): BrainLifecyclePort, BroadcastPort, IdleTimeoutManager

### Community 64 - "NightwatcherObserver"
Cohesion: 0.11
Nodes (5): ShiftReport, _env_float(), _env_int(), NightwatcherObserver, build_system_prompt()

### Community 65 - "CortexGraph.tsx"
Cohesion: 0.15
Nodes (23): graphology, eventColor(), getStructuralEdges(), DEFAULT_TYPE_BUDGET, evictLru(), KNOWLEDGE_RING, KNOWLEDGE_RING_TYPES, KnowledgeNodeAttributes (+15 more)

### Community 67 - "reconcile.py"
Cohesion: 0.15
Nodes (10): sanitize_redis_port(), _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers(), main() (+2 more)

### Community 71 - "get_archivist"
Cohesion: 0.11
Nodes (11): get_archivist(), aligner_pending_items(), delete_knowledge(), delete_lesson(), get_knowledge(), get_lesson(), get_memory(), jenkins_pending_items() (+3 more)

### Community 74 - "dependencies"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 75 - "quota_tracker.py"
Cohesion: 0.12
Nodes (4): QuotaExhaustedError, QuotaTracker, RequestExceedsBurstError, Reservation

### Community 76 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 77 - "claude-guard.js"
Cohesion: 0.14
Nodes (18): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+10 more)

### Community 78 - ".get_event"
Cohesion: 0.09
Nodes (8): report_tampering(), FeedbackRequest, submit_feedback(), get_event_approval(), get_event_document(), get_event_report(), get_event_turns(), rebuild_deep_memory()

### Community 80 - "cli-setup.js"
Cohesion: 0.13
Nodes (19): { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync }, filterSkillsByMode() (+11 more)

### Community 83 - "PulseBatch"
Cohesion: 0.12
Nodes (4): PulseBatch, PulsePort, PulseObserver, PulseTracker

### Community 84 - "observations_reporter.py"
Cohesion: 0.15
Nodes (8): _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), _sample_points(), _summarize(), download_skill_md()

### Community 87 - "devDependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 88 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 91 - "get_report"
Cohesion: 0.11
Nodes (6): get_report(), list_reports(), reports_spa_no_slash(), reports_spa_with_slash(), search_reports(), _serve_spa()

### Community 92 - "gemini-sidecar/package.json"
Cohesion: 0.11
Nodes (17): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+9 more)

### Community 94 - "tool_router.py"
Cohesion: 0.14
Nodes (4): _safe_int(), handle_consult_deep_memory(), IncidentAdapterPort, StateWatcherPort

### Community 96 - "ShiftsPage.tsx"
Cohesion: 0.23
Nodes (16): getCurrentShift(), getShiftDetail(), getShiftsList(), ShiftReportFull, ShiftReportSummary, FailedClusterBadge(), getISOWeek(), getWeekDates() (+8 more)

### Community 97 - "cortex/types.ts"
Cohesion: 0.16
Nodes (16): ActiveEvent, EventSource, KGServiceEntity, CortexGraphProps, GraphLoaderProps, PulseTimelineProps, CognitiveGraphResponse, CortexHeartbeatMessage (+8 more)

### Community 98 - "catalog-skills.js"
Cohesion: 0.16
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 102 - "update_event_title"
Cohesion: 0.12
Nodes (7): can_rename_event(), demote_lesson(), KnowledgeUpdateRequest, TitleUpdateRequest, update_event_title(), update_knowledge(), verify_lesson()

### Community 103 - "list_active_events"
Cohesion: 0.12
Nodes (6): _defer_timeline_fields(), _has_active_subscription(), list_active_events(), list_closed_events(), list_waiting_approval_events(), _serialize_evidence()

### Community 104 - "generate_map.py"
Cohesion: 0.19
Nodes (6): _enumerate_gates(), _GateInfo, generate_phase_tool_map(), _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 106 - "graph_recall.py"
Cohesion: 0.19
Nodes (5): _format_graph_context(), get_graph_context(), _parse_props(), _sanitize(), translate_to_lookups()

### Community 111 - "_append_user_turn"
Cohesion: 0.14
Nodes (5): _append_user_turn(), _coerce_part(), _is_function_response_part(), _strip_user_thought_signature(), _validated_parts()

### Community 114 - "analyzeTokens"
Cohesion: 0.19
Nodes (13): analyzeString(), analyzeTokens(), assignName(), base(), combineCategories(), configEnvGuard(), configFileWriteGuard(), hasSubseq() (+5 more)

### Community 117 - "._extract_context_flags"
Cohesion: 0.15
Nodes (3): compute_dispatch_backpressure(), ContextFlags, _safe_int_env()

### Community 120 - "NeuronInfoPanel.tsx"
Cohesion: 0.24
Nodes (12): KGServiceDetail, asNumber(), asString(), asStringArray(), Badge(), describeNeuron(), Hdr(), NeuronInfoPanel() (+4 more)

### Community 123 - "_resolve_phase"
Cohesion: 0.20
Nodes (4): handle_recall_pruned_turns(), handle_set_phase(), resolve_event_domain(), _resolve_phase()

### Community 126 - "CortexLiveFeed.tsx"
Cohesion: 0.24
Nodes (10): CortexHeartbeat(), CortexHeartbeatProps, ensureKeyframes(), CortexLiveFeed(), FILTER_PILLS, FilterKey, getStoredFilter(), MESSAGE_STYLES (+2 more)

### Community 127 - "handle_classify_event"
Cohesion: 0.20
Nodes (4): handle_classify_event(), handle_request_user_approval(), IdleTimeoutPort, _resolve_domain()

### Community 128 - "is_defer_event_available"
Cohesion: 0.18
Nodes (6): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 129 - "cortex-constants.ts"
Cohesion: 0.18
Nodes (10): AGENTS, DOMAINS, HEMISPHERE_X, NEURON_DESCRIPTIONS, PHASE_SKILL_FOLDERS, PHASE_TOOL_PRIORITY, PHASES, StructuralEdge (+2 more)

### Community 131 - "gitGuard"
Cohesion: 0.29
Nodes (10): bareBranchProtected(), configWriteGuard(), externalGitCommand(), gitGuard(), gitQuery(), isProtected(), normRef(), pushGuard() (+2 more)

### Community 132 - "parseShell"
Cohesion: 0.33
Nodes (10): bodySubstitutions(), decodeAnsiC(), isArrayAssignPrefix(), isWordStart(), matchBacktick(), matchParen(), parseShell(), readHeredocStart() (+2 more)

### Community 135 - "entity_extractor.py"
Cohesion: 0.33
Nodes (5): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship

### Community 139 - "has_unevaluated_close_blocker"
Cohesion: 0.20
Nodes (4): has_unevaluated_close_blocker(), _pred_jarvis_response(), _pred_unevaluated_close(), is_jarvis_acknowledgment()

### Community 140 - "knowledge_graph_api.py"
Cohesion: 0.31
Nodes (4): get_kg_store(), get_service_detail(), get_stats(), list_services()

### Community 142 - "classifyTool"
Cohesion: 0.31
Nodes (9): apiTokens(), apiWriteNeedsGuard(), branchValues(), classifyTool(), hasOpaqueTarget(), httpGuard(), httpMethod(), isReadMethod() (+1 more)

### Community 143 - "get_quota_tracker"
Cohesion: 0.22
Nodes (3): get_quota_tracker(), llm_stats(), receive_telemetry()

### Community 156 - "validate-mutations.sh"
Cohesion: 0.57
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

### Community 157 - "handle_report_incident"
Cohesion: 0.29
Nodes (3): handle_report_incident(), _resolve_escalation_scope(), handle_search_open_incidents()

### Community 159 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 160 - "state.js"
Cohesion: 0.33
Nodes (4): { AGENT_ROLE }, _blackboardTurns, _inboundMessages, _teammateMessages

### Community 171 - "classify"
Cohesion: 0.50
Nodes (4): classify(), main(), shellCategory(), shellNeedsGuard()

## Knowledge Gaps
- **13 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+8 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2238 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **106 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `logging`, `brain.py`, `auth.py`, `approve_event`, `EventEvidence`, `EventDocument`, `Brain`, `close_event_by_user`, `BrainSkillLoader`, `create_schedule`, `nightwatcher_tools.py`, `_is_event_closed_or_missing`, `jenkins_observer.py`, `ConversationMessage`, `httpx`, `ConversationTurn`, `lifespan`, `main.py`, `queue.py`, `LiveAPIAdapter`, `NightwatcherObserver`, `get_archivist`, `.get_event`, `observations_reporter.py`, `DashboardWSAdapter`, `get_report`, `tool_router.py`, `update_event_title`, `list_active_events`, `ScheduleRepository`, `HeadhunterJira`?**
  _High betweenness centrality (0.142) - this node is a cross-community bridge._
- **Are the 80 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 80 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.010838334242589561 - nodes in this community are weakly interconnected._
- **Why does `Brain` connect `Brain` to `BlackboardState`, `logging`, `brain.py`, `EventEvidence`, `._post_agent_recall`, `EventDocument`, `ReconcileScheduler`, `._run_agent_task`, `BrainSkillLoader`, `._process_with_llm`, `ConversationTurn`, `lifespan`, `main.py`, `._close_and_broadcast`, `StateWatcher`, `IdleTimeoutManager`, `quota_tracker.py`, `PulseBatch`, `DashboardWSAdapter`, `ReflexSearcher`, `._extract_context_flags`?**
  _High betweenness centrality (0.071) - this node is a cross-community bridge._
- **Are the 21 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 21 INFERRED edges - model-reasoned connections that need verification._
- **Should `logging` be split into smaller, more focused modules?**
  _Cohesion score 0.030845214798248068 - nodes in this community are weakly interconnected._