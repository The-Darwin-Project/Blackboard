# Graph Report - Blackboard  (2026-11-03)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 4963 nodes · 11101 edges · 205 communities (89 shown, 116 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 935 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `a8b8a076`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BlackboardState
- brain.py
- logging
- queue.py
- client.ts
- EventChatPanel.tsx
- Brain
- EventSidebar.tsx
- tool_gates.py
- auth.py
- colors.ts
- main.py
- App.tsx
- EventDocument
- merge-guard.js
- ReconcileScheduler
- http-handler.js
- jenkins-mcp.js
- ._run_agent_task
- react
- TurnBubble.tsx
- BrainSkillLoader
- AgentRegistry
- _BrainToolContext
- OpsStateContext.tsx
- KnowledgeGraphStore
- Archivist
- handlers_integration.py
- ToolContext
- nightwatcher_tools.py
- EventRepository
- cli-executor.js
- ._process_with_llm
- storage-recycler.js
- JenkinsAdapter
- state/__init__.py
- httpx
- agents/__init__.py
- Aligner
- GitHubPlatform
- EventDrillDown.tsx
- ConversationTurn
- slack.py
- CortexGraph.tsx
- GitLabPlatform
- TimeKeeperPage.tsx
- SlackChannel
- Headhunter
- ws-client.js
- VectorStore
- spawn_event_namer_task
- ActiveStreamsContext.tsx
- cognitive_graph.py
- useCortexData.ts
- NodeInspector.tsx
- ._build_contents
- server.js
- ui/package.json
- LiveAPIAdapter
- StateWatcher
- adf_to_markdown
- GeminiAdapter
- llm/__init__.py
- JenkinsObserver
- NeuronInfoPanel.tsx
- ._get_manager
- ArgoCDObserver
- KargoObserver
- TopologyRepository
- dependencies
- IdleTimeoutManager
- GitHubAppAuth
- compilerOptions
- claude-guard.js
- reconcile.py
- cli-setup.js
- ArchitectureGraph.tsx
- VcsPlatformPort
- PulseBatch
- lifespan
- ReflexSearcher
- devDependencies
- compilerOptions
- DashboardWSAdapter
- EphemeralProvisioner
- ClaudeAdapter
- get_report
- gemini-sidecar/package.json
- tool_router.py
- QuotaTracker
- ObservationRepository
- ShiftsPage.tsx
- catalog-skills.js
- .scroll
- handlers_state.py
- generate_map.py
- OIDCKeyAdapter
- KubernetesSpawnHealthAdapter
- EscalationRepository
- ServiceNode.tsx
- observations_reporter.py
- _sanitize_analysis_text
- nightwatcher_prompt.py
- RedisClient
- FilterRule
- BrainLifecyclePort
- TokenMeter
- MultiInstallationManager
- HeadhunterJira
- SlackAccessGate
- testSetup.ts
- is_defer_event_available
- NightwatcherObserver
- CortexLiveFeed.tsx
- SecurityError
- generate_event_title
- ._post_agent_recall
- entity_extractor.py
- has_unevaluated_close_blocker
- get_quota_tracker
- SpawnPollResult
- SmartsheetMaintainerCache
- .has_reeval_signal
- AsyncGitHubClient
- GitLabTokenAuth
- useDeferCountdown.ts
- _is_event_closed_or_missing
- ._evaluate_health
- handlers_lookup.py
- _validate_analysis
- ._triage_and_build_evidence
- TimeKeeperObserver
- CortexRepository
- scripts
- state.js
- validate-mutations.sh
- io
- ._process_message
- ._cleanup_stale_events
- DispatchMetrics
- SpawnStatus
- list_failed_stages
- dex_proxy
- ._wait_for_registration
- extract_tables
- agent_ws_endpoint
- submit_feedback
- _patch_enum_fields
- require-results.sh
- _WSFrameFilter
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
1. `BlackboardState` - 283 edges
2. `Brain` - 150 edges
3. `ConversationTurn` - 122 edges
4. `ToolContext` - 103 edges
5. `GateContext` - 94 edges
6. `react` - 82 edges
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

## Communities (205 total, 116 thin omitted)

### Community 0 - "BlackboardState"
Cohesion: 0.01
Nodes (21): render_pdf(), get_all_journal(), get_service_journal(), get_notebook(), get_event_observations(), get_global_observations(), bulk_delete_observations(), BulkDeleteRequest (+13 more)

### Community 1 - "brain.py"
Cohesion: 0.02
Nodes (55): _apply_sibling_signature(), build_function_response(), build_single_function_response(), compress_contents(), estimate_msg_tokens(), estimate_tokens(), extract_model_parts(), normalize_response_parts() (+47 more)

### Community 2 - "logging"
Cohesion: 0.03
Nodes (15): _annotation_replace(), _strip_pipeline_annotations(), _sanitize_lesson_text(), _get_static_maintainer_emails(), _get_allowed_mention_authors(), _get_static_maintainer_emails(), _safe_int(), _parse_job_metadata() (+7 more)

### Community 3 - "queue.py"
Cohesion: 0.03
Nodes (57): get_token_meter(), can_approve_event(), can_override_domain(), can_rename_event(), _normalize_email(), resolve_approval_identity(), get_archivist(), get_brain() (+49 more)

### Community 4 - "client.ts"
Cohesion: 0.03
Nodes (96): @tanstack/react-query, ApiError, bulkDeleteObservations(), deleteNote(), deleteObservation(), exportObservations(), ExtractedCorrection, ExtractedLesson (+88 more)

### Community 5 - "EventChatPanel.tsx"
Cohesion: 0.05
Nodes (72): react-router-dom, getEventDocument(), updateEventTitle(), AppConfig, CiContext, ConversationTurn, TokenUsageDict, CiContextCard() (+64 more)

### Community 7 - "EventSidebar.tsx"
Cohesion: 0.06
Nodes (76): getActiveEvents(), getAlignerPending(), getClosedEvents(), getHeadhunterPending(), getJenkinsPending(), getJiraMissions(), getWaitingApprovalEvents(), HeadhunterTodo (+68 more)

### Community 8 - "tool_gates.py"
Cohesion: 0.05
Nodes (78): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+70 more)

### Community 9 - "auth.py"
Cohesion: 0.04
Nodes (20): _claims_to_user(), get_user_from_request(), get_user_from_slack(), get_user_from_websocket(), require_auth(), require_obs_admin(), set_oidc_adapter(), UserContext (+12 more)

### Community 10 - "colors.ts"
Cohesion: 0.06
Nodes (48): getReport(), getReports(), ReportFull, ReportMeta, DeferCountdownBar(), CompactCardStrip(), EventHistory(), TimeRange (+40 more)

### Community 11 - "main.py"
Cohesion: 0.04
Nodes (31): get_aligner(), get_architect(), get_argocd_observer(), get_developer(), get_kargo_observer(), get_kg_store(), get_report_client(), get_sysadmin() (+23 more)

### Community 12 - "App.tsx"
Cohesion: 0.05
Nodes (59): oidc-client-ts, react-dom, recharts, dismissProposals(), EnhancementProposal, getConfig(), getFlowHistory(), getHandoffReports() (+51 more)

### Community 13 - "EventDocument"
Cohesion: 0.04
Nodes (14): _close_unanswered_fc(), _resolve_escalation_scope(), _build_closed_block(), build_event_header(), _build_identity_block(), _build_journal_block(), _build_mermaid_block(), _build_related_block() (+6 more)

### Community 14 - "merge-guard.js"
Cohesion: 0.05
Nodes (69): analyzeString(), analyzeTokens(), API_VALUED, apiTokens(), apiWriteNeedsGuard(), assignName(), bareBranchProtected(), base() (+61 more)

### Community 15 - "ReconcileScheduler"
Cohesion: 0.04
Nodes (7): FlowCollector, FairQueue, ReconcileScheduler, Trigger, QueueTrigger, ResyncTrigger, StalenessGuard

### Community 16 - "http-handler.js"
Cohesion: 0.09
Nodes (58): resolveCommand(), writeAgyMcpServer(), writeClaudeMcpServer(), buildArgoCDMcpConfig(), createAppJWT(), discoverAndGenerateTokens(), _discoverAndGenerateTokensInner(), discoverInstallations() (+50 more)

### Community 17 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 18 - "._run_agent_task"
Cohesion: 0.06
Nodes (9): on_huddle(), on_progress(), on_huddle(), on_progress(), _compute_processed_up_to(), _is_automated_nudge(), _sanitize_error_text(), _select_dispatch_tier() (+1 more)

### Community 19 - "react"
Cohesion: 0.08
Nodes (51): lucide-react, react, applyLessons(), correctMemory(), createKnowledge(), createLesson(), deleteKnowledge(), deleteLesson() (+43 more)

### Community 20 - "TurnBubble.tsx"
Cohesion: 0.08
Nodes (43): @uiw/react-markdown-preview, approveEvent(), closeEvent(), enforceCasualDomain(), getEventReport(), rejectEvent(), submitFeedback(), MessageStatus (+35 more)

### Community 21 - "BrainSkillLoader"
Cohesion: 0.05
Nodes (4): BrainSkillLoader, _SkillCorpus, _wrap_section(), BrainIntrospectionPort

### Community 22 - "AgentRegistry"
Cohesion: 0.06
Nodes (13): AgentConnection, AgentRegistry, agent_websocket_handler(), _heartbeat(), _build_prompt(), consume_wake_task(), _consume(), _dispatch_timeout_s() (+5 more)

### Community 24 - "OpsStateContext.tsx"
Cohesion: 0.08
Nodes (35): createChatEvent(), getAgents(), getKargoStages(), AgentRegistryEntry, EventEvidence, KargoStageStatus, AgentRegistryPanel(), formatConnectedSince() (+27 more)

### Community 25 - "KnowledgeGraphStore"
Cohesion: 0.08
Nodes (9): _format_graph_context(), get_graph_context(), _parse_props(), _sanitize(), translate_to_lookups(), _acquire(), KnowledgeGraphStore, _sanitize() (+1 more)

### Community 27 - "handlers_integration.py"
Cohesion: 0.08
Nodes (20): _alert_wrapper_retrigger(), _do_retrigger(), _get_jira_reporter(), handle_fetch_jira_issue(), handle_notify_user_slack(), handle_refresh_github_context(), handle_refresh_gitlab_context(), handle_refresh_kargo_context() (+12 more)

### Community 28 - "ToolContext"
Cohesion: 0.09
Nodes (11): handle_message_agent(), handle_reply_to_agent(), handle_report_incident(), handle_select_agent(), _sticky_work_style(), handle_search_open_incidents(), handle_hold_watch(), handle_respond_to_jarvis() (+3 more)

### Community 29 - "nightwatcher_tools.py"
Cohesion: 0.09
Nodes (20): PulseContext, ShiftIncident, ShiftInvestigation, extract_full_links(), build_extend_tool(), build_report_tool(), build_summary_tool(), execute_tool() (+12 more)

### Community 31 - "cli-executor.js"
Cohesion: 0.09
Nodes (36): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS, STORAGE_PRETASK_TIMEOUT_MS, resolveStorageRoot }, buildCLICommand(), { checkAndRecycleStorage, pinTaskCwd, unpinTaskCwd }, CLAUDE_JSON_PATH, cp, executeCLI(), executeCLIStreaming(), FALLBACK_MODEL (+28 more)

### Community 33 - "storage-recycler.js"
Cohesion: 0.08
Nodes (34): withTaskStorage(), resolveStorageRoot(), ROLE_TIMEOUTS, STORAGE_ACTIVITY_HEARTBEAT_MS, STORAGE_MAX_TIER3_DELETIONS, STORAGE_PRETASK_TIMEOUT_MS, STORAGE_RESULTS_TTL_MS, STORAGE_STALE_MS (+26 more)

### Community 34 - "JenkinsAdapter"
Cohesion: 0.06
Nodes (6): BuildDetails, JenkinsAdapter, JenkinsPlatformPort, JobResult, JobRunState, ViewScanResult

### Community 35 - "state/__init__.py"
Cohesion: 0.06
Nodes (7): ArchitectureEvent, ScheduledEvent, get_event_document(), list_events(), sanitize_redis_port(), MetricsRepository, ScheduleRepository

### Community 36 - "httpx"
Cohesion: 0.08
Nodes (12): approve_mission(), dismiss_mission(), _infer_phase(), _jira_config(), list_missions(), reanalyze_mission(), retry_mission(), get_gitlab_auth() (+4 more)

### Community 37 - "agents/__init__.py"
Cohesion: 0.07
Nodes (4): Architect, AgentClient, Developer, SysAdmin

### Community 40 - "EventDrillDown.tsx"
Cohesion: 0.10
Nodes (32): three, getEventPulses(), EventSource, BrainCore(), CortexDevPage(), devQueryClient, CortexLiveFeedProps, EventDrillDown() (+24 more)

### Community 41 - "ConversationTurn"
Cohesion: 0.16
Nodes (25): emit_tool_result(), handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_recall_pruned_turns(), handle_ask_release_ai(), handle_comment_jira_issue(), handle_greenwave() (+17 more)

### Community 42 - "slack.py"
Cohesion: 0.08
Nodes (14): build_access_denied_home_view(), build_home_tab_view(), _context_line(), create_feedback_block(), format_plan_block(), format_task_card(), format_turn(), _md_table_to_text() (+6 more)

### Community 43 - "CortexGraph.tsx"
Cohesion: 0.10
Nodes (34): graphology, @react-sigma/core, @react-sigma/layout-forceatlas2, sigma, @sigma/node-square, ActiveEvent, KGServiceEntity, eventColor() (+26 more)

### Community 45 - "TimeKeeperPage.tsx"
Cohesion: 0.12
Nodes (24): createSchedule(), deleteSchedule(), getSchedules(), refineInstructions(), ScheduleCreatePayload, ScheduleItem, toggleSchedule(), updateSchedule() (+16 more)

### Community 46 - "SlackChannel"
Cohesion: 0.09
Nodes (3): get_agent_notification_text(), get_turn_attachment_color(), SlackChannel

### Community 47 - "Headhunter"
Cohesion: 0.08
Nodes (3): Headhunter, _raise_if_systemic_failure(), _sanitize_xml_fence()

### Community 48 - "ws-client.js"
Cohesion: 0.09
Nodes (26): is429Error(), {
  DEFAULT_WORK_DIR, AGENT_CLI, AGENT_MODEL, AGENT_ROLE,
  EVENT_ID, EPHEMERAL, IDLE_TIMEOUT_MS,
  CLI_429_MAX_RETRIES, CLI_429_INITIAL_DELAY_MS, CLI_429_BACKOFF_MULTIPLIER,
}, { ensureEventDocument }, { executeCLIStreaming, prepareResultsDir, is429Error }, { filterSkillsByRole, filterSkillsByMode, swapActiveRules, restoreAllSkills }, fs, handleCancel(), resetTimer() (+18 more)

### Community 50 - "spawn_event_namer_task"
Cohesion: 0.12
Nodes (11): spawn_event_namer_task(), format_event_summary(), handle_app_home_opened(), handle_app_mention(), handle_approve(), handle_create_event_modal(), handle_darwin_command(), handle_home_create_event() (+3 more)

### Community 51 - "ActiveStreamsContext.tsx"
Cohesion: 0.13
Nodes (26): AgentStreamCard(), AgentStreamCardProps, FloatingWindow(), MessageCards(), Dashboard(), GridTile(), GridTileProps, TileType (+18 more)

### Community 52 - "cognitive_graph.py"
Cohesion: 0.10
Nodes (12): get_blackboard(), get_pulse_tracker(), dismiss_proposals(), DismissRequest, get_all_shadow_interventions(), get_cognitive_graph(), get_cortex_activity(), get_cortex_status() (+4 more)

### Community 53 - "useCortexData.ts"
Cohesion: 0.17
Nodes (27): getCognitiveGraph(), getCortexActivity(), getKGServiceDetail(), getKGServices(), getKGStats(), getKnowledgeById(), getMemory(), getRecentPulses() (+19 more)

### Community 54 - "NodeInspector.tsx"
Cohesion: 0.11
Nodes (25): getEvents(), ArchitectureEvent, ArgoCDOperation, ActivityStream(), ArchitectureGraph(), EVENT_LABELS, EventItem(), EventItemProps (+17 more)

### Community 55 - "._build_contents"
Cohesion: 0.07
Nodes (3): compute_dispatch_backpressure(), ContextFlags, _safe_int_env()

### Community 56 - "server.js"
Cohesion: 0.08
Nodes (18): hasRegistryCredentials(), { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, fs, path, stageEventDocument(), fetchEventDocument(), fs, { handleRequest } (+10 more)

### Community 57 - "ui/package.json"
Cohesion: 0.09
Nodes (25): autoprefixer, cronstrue, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, graphology-layout-forceatlas2 (+17 more)

### Community 59 - "StateWatcher"
Cohesion: 0.10
Nodes (3): _QueueEntry, StateWatcher, _Subscription

### Community 60 - "adf_to_markdown"
Cohesion: 0.12
Nodes (10): _adf_to_text(), _escape_jql_string(), JiraIncidentAdapter, adf_to_markdown(), _apply_marks(), _children(), _render(), _render_list() (+2 more)

### Community 62 - "llm/__init__.py"
Cohesion: 0.14
Nodes (5): _parse_drain_timeout(), LLMChunk, LLMPort, LLMResponse, TokenUsage

### Community 64 - "NeuronInfoPanel.tsx"
Cohesion: 0.11
Nodes (23): KGServiceDetail, AGENTS, DOMAINS, HEMISPHERE_X, NEURON_DESCRIPTIONS, PHASE_SKILL_FOLDERS, PHASE_TOOL_PRIORITY, PHASES (+15 more)

### Community 69 - "dependencies"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 72 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 73 - "claude-guard.js"
Cohesion: 0.14
Nodes (18): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+10 more)

### Community 74 - "reconcile.py"
Cohesion: 0.18
Nodes (9): _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers(), main(), _parse_frontmatter() (+1 more)

### Community 75 - "cli-setup.js"
Cohesion: 0.13
Nodes (19): { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync }, filterSkillsByMode() (+11 more)

### Community 76 - "ArchitectureGraph.tsx"
Cohesion: 0.14
Nodes (17): @dagrejs/dagre, @xyflow/react, applyDagreLayout(), applyGridLayout(), applyLayout(), ArchitectureGraphInner(), buildGraph(), computeIdHash() (+9 more)

### Community 79 - "PulseBatch"
Cohesion: 0.12
Nodes (4): PulseBatch, PulsePort, PulseObserver, PulseTracker

### Community 82 - "devDependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 83 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 88 - "get_report"
Cohesion: 0.11
Nodes (6): get_report(), list_reports(), reports_spa_no_slash(), reports_spa_with_slash(), search_reports(), _serve_spa()

### Community 89 - "gemini-sidecar/package.json"
Cohesion: 0.11
Nodes (17): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+9 more)

### Community 91 - "tool_router.py"
Cohesion: 0.12
Nodes (3): IdleTimeoutPort, IncidentAdapterPort, StateWatcherPort

### Community 92 - "QuotaTracker"
Cohesion: 0.14
Nodes (3): QuotaExhaustedError, QuotaTracker, Reservation

### Community 94 - "ShiftsPage.tsx"
Cohesion: 0.23
Nodes (16): getCurrentShift(), getShiftDetail(), getShiftsList(), ShiftReportFull, ShiftReportSummary, FailedClusterBadge(), getISOWeek(), getWeekDates() (+8 more)

### Community 95 - "catalog-skills.js"
Cohesion: 0.16
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 97 - "handlers_state.py"
Cohesion: 0.15
Nodes (5): handle_classify_event(), handle_defer_event(), handle_request_user_approval(), _resolve_domain(), resolve_event_domain()

### Community 98 - "generate_map.py"
Cohesion: 0.19
Nodes (6): _enumerate_gates(), _GateInfo, generate_phase_tool_map(), _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 102 - "ServiceNode.tsx"
Cohesion: 0.20
Nodes (11): HealthStatus, NodeType, AppNodeData, ARGOCD_HEALTH_COLORS, SYNC_ICONS, GENERIC_TAGS, HEALTH_COLORS, NODE_ICONS (+3 more)

### Community 103 - "observations_reporter.py"
Cohesion: 0.21
Nodes (7): _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), _sample_points(), _summarize()

### Community 106 - "_sanitize_analysis_text"
Cohesion: 0.15
Nodes (6): _prepare_console_tail(), _redact_match(), _redact_secrets_in_text(), _sanitize_analysis_text(), _sanitize_console_tail(), _strip_newlines()

### Community 107 - "nightwatcher_prompt.py"
Cohesion: 0.16
Nodes (6): build_manifest_table(), build_report_iteration_prompt(), build_summary_prompt(), build_system_prompt(), extract_event_links(), _normalize_gitlab_host()

### Community 117 - "testSetup.ts"
Cohesion: 0.18
Nodes (5): @tailwindcss/vite, @testing-library/react, vite, @vitejs/plugin-react, vitest

### Community 118 - "is_defer_event_available"
Cohesion: 0.18
Nodes (6): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 121 - "CortexLiveFeed.tsx"
Cohesion: 0.27
Nodes (9): CortexHeartbeat(), CortexHeartbeatProps, ensureKeyframes(), CortexLiveFeed(), FILTER_PILLS, FilterKey, getStoredFilter(), MESSAGE_STYLES (+1 more)

### Community 122 - "SecurityError"
Cohesion: 0.24
Nodes (4): _check_security(), safe_execution(), wrapper(), SecurityError

### Community 123 - "generate_event_title"
Cohesion: 0.22
Nodes (3): generate_event_title(), get_adapter(), _get_semaphore()

### Community 125 - "entity_extractor.py"
Cohesion: 0.33
Nodes (5): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship

### Community 126 - "has_unevaluated_close_blocker"
Cohesion: 0.20
Nodes (4): has_unevaluated_close_blocker(), _pred_jarvis_response(), _pred_unevaluated_close(), is_jarvis_acknowledgment()

### Community 127 - "get_quota_tracker"
Cohesion: 0.22
Nodes (3): get_quota_tracker(), llm_stats(), receive_telemetry()

### Community 133 - "useDeferCountdown.ts"
Cohesion: 0.47
Nodes (7): DeferCountdownState, useDeferCountdown(), computeDeferProgress(), DeferTimeline, formatDeferRemaining(), inferDeferFromConversation(), resolveDeferTimeline()

### Community 136 - "handlers_lookup.py"
Cohesion: 0.32
Nodes (3): _safe_int(), handle_consult_deep_memory(), handle_google_web_search()

### Community 138 - "_validate_analysis"
Cohesion: 0.29
Nodes (3): _clamp_confidence(), _validate_analysis(), _validate_triage_entry()

### Community 144 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 145 - "state.js"
Cohesion: 0.33
Nodes (4): { AGENT_ROLE }, _blackboardTurns, _inboundMessages, _teammateMessages

### Community 146 - "validate-mutations.sh"
Cohesion: 0.73
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

### Community 163 - "extract_tables"
Cohesion: 0.40
Nodes (3): extract_tables(), _replace(), _md_table_to_block_kit()

## Knowledge Gaps
- **13 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+8 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2169 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **116 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `brain.py`, `logging`, `queue.py`, `_is_event_closed_or_missing`, `Brain`, `auth.py`, `main.py`, `EventDocument`, `BrainSkillLoader`, `nightwatcher_tools.py`, `._restage_pending_signal`, `._stage_pending_signal`, `state/__init__.py`, `httpx`, `submit_feedback`, `._count_pending`, `ConversationTurn`, `slack.py`, `._commit_pending_signal`, `._drain_pending`, `cognitive_graph.py`, `LiveAPIAdapter`, `lifespan`, `DashboardWSAdapter`, `get_report`, `tool_router.py`, `observations_reporter.py`, `HeadhunterJira`, `NightwatcherObserver`, `generate_event_title`?**
  _High betweenness centrality (0.111) - this node is a cross-community bridge._
- **Are the 80 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 80 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.010977615676178217 - nodes in this community are weakly interconnected._
- **Why does `Brain` connect `Brain` to `BlackboardState`, `brain.py`, `main.py`, `EventDocument`, `ReconcileScheduler`, `._run_agent_task`, `BrainSkillLoader`, `._cleanup_stale_events`, `._process_with_llm`, `agents/__init__.py`, `ConversationTurn`, `slack.py`, `.clear_jarvis_wait`, `._build_contents`, `StateWatcher`, `.create_kargo_event`, `IdleTimeoutManager`, `PulseBatch`, `lifespan`, `ReflexSearcher`, `DashboardWSAdapter`, `QuotaTracker`, `BrainLifecyclePort`, `._post_agent_recall`?**
  _High betweenness centrality (0.066) - this node is a cross-community bridge._
- **Are the 20 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Should `brain.py` be split into smaller, more focused modules?**
  _Cohesion score 0.02368120202515107 - nodes in this community are weakly interconnected._