# Graph Report - Blackboard  (2026-11-06)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 5045 nodes · 11265 edges · 202 communities (102 shown, 100 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 938 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `495db818`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BlackboardState
- logging
- queue.py
- react
- client.ts
- Archivist
- main.py
- nightwatcher_tools.py
- EventEvidence
- Brain
- tool_gates.py
- EventSidebar.tsx
- merge-guard.js
- EventDocument
- AgentRegistry
- App.tsx
- ._run_agent_task
- http-handler.js
- cognitive_graph.py
- jenkins-mcp.js
- TurnBubble.tsx
- BrainSkillLoader
- Service
- fetchApi
- EventHistory.tsx
- httpx
- Aligner
- _BrainToolContext
- models.py
- auth.py
- brain.py
- ToolContext
- cli-executor.js
- ._process_with_llm
- KubernetesSpawnHealthAdapter
- storage-recycler.js
- JenkinsAdapter
- EventRepository
- agents/__init__.py
- GitHubPlatform
- ConversationTurn
- GitLabPlatform
- Headhunter
- TimeKeeperPage.tsx
- ScheduleRepository
- ws-client.js
- ui/package.json
- OpsStateContext.tsx
- ActiveStreamsContext.tsx
- handlers_integration.py
- event_to_markdown
- EphemeralProvisioner
- useCortexData.ts
- server.js
- SlackChannel
- HeadhunterJira
- KnowledgeGraphStore
- TopologyRepository
- ArchitectureGraph.tsx
- CortexGraph.tsx
- EventDrillDown.tsx
- observations_mgmt.py
- types.py
- ReconcileScheduler
- NodeInspector.tsx
- ArgoCDObserver
- create_schedule
- ._get_manager
- KargoObserver
- GitHubAppAuth
- dependencies
- StateWatcher
- GeminiAdapter
- formatter.py
- compilerOptions
- claude-guard.js
- _sanitize_analysis_text
- TokenUtilizationPage.tsx
- DashboardWSAdapter
- cli-setup.js
- tool_router.py
- VcsPlatformPort
- ReflexSearcher
- ArchitectureEvent
- FairQueue
- devDependencies
- compilerOptions
- LiveAPIAdapter
- ClaudeAdapter
- get_report
- gemini-sidecar/package.json
- ._build_contents
- JenkinsObserver
- ObservationRepository
- ShiftsPage.tsx
- _reconcile
- catalog-skills.js
- gemini_client.py
- EscalationRepository
- cortex/types.ts
- generate_map.py
- ._normalize_issue
- OIDCKeyAdapter
- IdleTimeoutManager
- ServiceNode.tsx
- observations_reporter.py
- MultiInstallationManager
- ._extract_context_flags
- BrainLifecyclePort
- QuotaTracker
- TokenMeter
- .list_observations
- NeuronInfoPanel.tsx
- .start_event_loop
- handle_report_incident
- format_jira_for_llm
- state/ports.py
- testSetup.ts
- resolve_maintainer_emails
- is_defer_event_available
- SlackAccessGate
- CiContextCard.tsx
- cortex-constants.ts
- _md_table_to_text
- _is_event_closed_or_missing
- ._post_agent_recall
- entity_extractor.py
- ._github_poll_and_process
- ._process_candidates
- ._triage_and_build_evidence
- ._drain_once
- sanitize_call_syntax
- has_unevaluated_close_blocker
- ._send_turn_to_thread
- knowledge_graph_api.py
- CortexDevPage.tsx
- get_quota_tracker
- SmartsheetMaintainerCache
- .has_reeval_signal
- Any
- Trigger
- AsyncGitHubClient
- GitLabTokenAuth
- useDeferCountdown.ts
- ConversationMessage
- TimeKeeperObserver
- CortexRepository
- adf_to_markdown
- _format_graph_context
- scripts
- state.js
- validate-mutations.sh
- io
- ._process_message
- PollFn
- ._publish_home_tab
- ._post_to_thread
- require-results.sh
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

## Communities (202 total, 100 thin omitted)

### Community 1 - "logging"
Cohesion: 0.03
Nodes (18): _sanitize_lesson_text(), get_graph_context(), translate_to_lookups(), _get_static_maintainer_emails(), _safe_int(), _parse_job_metadata(), create_adapter(), Pulse (+10 more)

### Community 2 - "queue.py"
Cohesion: 0.03
Nodes (58): get_token_meter(), resolve_approval_identity(), get_archivist(), get_brain(), EventStatus, aligner_pending_items(), apply_lessons(), approve_event() (+50 more)

### Community 3 - "react"
Cohesion: 0.04
Nodes (95): lucide-react, react, createChatEvent(), getActiveEvents(), getAlignerPending(), getEventDocument(), getEvents(), getJenkinsPending() (+87 more)

### Community 4 - "client.ts"
Cohesion: 0.03
Nodes (88): @tanstack/react-query, ApiError, bulkDeleteObservations(), deleteNote(), deleteObservation(), exportObservations(), ExtractedCorrection, ExtractedLesson (+80 more)

### Community 5 - "Archivist"
Cohesion: 0.04
Nodes (4): Archivist, _decode_cursor(), _encode_cursor(), VectorStore

### Community 6 - "main.py"
Cohesion: 0.03
Nodes (34): set_incident_options(), set_oidc_adapter(), get_aligner(), get_architect(), get_argocd_observer(), get_developer(), get_kargo_observer(), get_registry_and_bridge() (+26 more)

### Community 7 - "nightwatcher_tools.py"
Cohesion: 0.04
Nodes (34): record_token_usage(), QuotaExhaustedError, RequestExceedsBurstError, ShiftIncident, ShiftInvestigation, ShiftReport, _env_float(), _env_int() (+26 more)

### Community 8 - "EventEvidence"
Cohesion: 0.04
Nodes (22): generate_event_title(), get_adapter(), _get_semaphore(), spawn_event_namer_task(), can_append_message(), _PlanDecision, handle_app_home_opened(), handle_app_mention() (+14 more)

### Community 10 - "tool_gates.py"
Cohesion: 0.05
Nodes (78): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+70 more)

### Community 11 - "EventSidebar.tsx"
Cohesion: 0.07
Nodes (66): getHeadhunterPending(), getJiraMissions(), HeadhunterTodo, postJiraAction(), AgentRegistryEntry, DeferCountdownBar(), ACTION_BADGE, formatAge() (+58 more)

### Community 12 - "merge-guard.js"
Cohesion: 0.05
Nodes (69): analyzeString(), analyzeTokens(), API_VALUED, apiTokens(), apiWriteNeedsGuard(), assignName(), bareBranchProtected(), base() (+61 more)

### Community 13 - "EventDocument"
Cohesion: 0.03
Nodes (11): _build_closed_block(), build_event_header(), _build_identity_block(), _build_journal_block(), _build_mermaid_block(), _build_related_block(), _build_subject_block(), _build_timing_block() (+3 more)

### Community 14 - "AgentRegistry"
Cohesion: 0.05
Nodes (18): AgentConnection, AgentRegistry, agent_websocket_handler(), _heartbeat(), _build_prompt(), _check_security(), consume_wake_task(), _consume() (+10 more)

### Community 15 - "App.tsx"
Cohesion: 0.06
Nodes (48): oidc-client-ts, react-dom, react-router-dom, getConfig(), getWSAuthFailureCallback(), setOnUnauthorized(), setTokenGetter(), setWSAuthFailureCallback() (+40 more)

### Community 16 - "._run_agent_task"
Cohesion: 0.06
Nodes (7): on_huddle(), on_progress(), on_huddle(), on_progress(), _sanitize_error_text(), _sanitize_override_reason(), _select_dispatch_tier()

### Community 17 - "http-handler.js"
Cohesion: 0.09
Nodes (58): resolveCommand(), writeAgyMcpServer(), writeClaudeMcpServer(), buildArgoCDMcpConfig(), createAppJWT(), discoverAndGenerateTokens(), _discoverAndGenerateTokensInner(), discoverInstallations() (+50 more)

### Community 18 - "cognitive_graph.py"
Cohesion: 0.05
Nodes (17): get_blackboard(), get_pulse_tracker(), dismiss_proposals(), DismissRequest, get_all_shadow_interventions(), get_cognitive_graph(), get_cortex_activity(), get_cortex_status() (+9 more)

### Community 19 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 20 - "TurnBubble.tsx"
Cohesion: 0.08
Nodes (44): @uiw/react-markdown-preview, approveEvent(), closeEvent(), enforceCasualDomain(), getEventReport(), rejectEvent(), submitFeedback(), ReportFull (+36 more)

### Community 21 - "BrainSkillLoader"
Cohesion: 0.05
Nodes (4): BrainSkillLoader, _SkillCorpus, _wrap_section(), BrainIntrospectionPort

### Community 22 - "Service"
Cohesion: 0.05
Nodes (8): GraphResponse, Service, get_graph_data(), get_mermaid_diagram(), get_service_details(), get_topology(), list_services(), calculate_health_from_argocd()

### Community 23 - "fetchApi"
Cohesion: 0.08
Nodes (49): applyLessons(), correctMemory(), createKnowledge(), createLesson(), deleteKnowledge(), deleteLesson(), extractLessons(), fetchApi() (+41 more)

### Community 24 - "EventHistory.tsx"
Cohesion: 0.07
Nodes (35): getReport(), getReports(), ReportMeta, SubjectType, CompactCardStrip(), EventHistory(), TimeRange, ViewMode (+27 more)

### Community 25 - "httpx"
Cohesion: 0.06
Nodes (11): JiraIncidentAdapter, _get_allowed_mention_authors(), _get_static_maintainer_emails(), dex_proxy(), approve_mission(), dismiss_mission(), _infer_phase(), _jira_config() (+3 more)

### Community 28 - "models.py"
Cohesion: 0.06
Nodes (21): AppNode, ChatRequest, ChatResponse, EventInput, EventMetrics, FlowMetricsResponse, FlowSnapshot, GraphEdge (+13 more)

### Community 29 - "auth.py"
Cohesion: 0.06
Nodes (16): can_approve_event(), can_override_domain(), can_rename_event(), _claims_to_user(), get_user_from_request(), get_user_from_slack(), get_user_from_websocket(), _normalize_email() (+8 more)

### Community 30 - "brain.py"
Cohesion: 0.06
Nodes (19): _compute_processed_up_to(), _has_non_user_turns(), _is_automated_nudge(), _is_seed_turn(), _apply_sibling_signature(), build_function_response(), build_single_function_response(), compress_contents() (+11 more)

### Community 31 - "ToolContext"
Cohesion: 0.09
Nodes (10): handle_message_agent(), handle_reply_to_agent(), handle_select_agent(), _sticky_work_style(), handle_defer_event(), handle_hold_watch(), handle_respond_to_jarvis(), handle_wait_for_agent() (+2 more)

### Community 32 - "cli-executor.js"
Cohesion: 0.09
Nodes (36): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS, STORAGE_PRETASK_TIMEOUT_MS, resolveStorageRoot }, buildCLICommand(), { checkAndRecycleStorage, pinTaskCwd, unpinTaskCwd }, CLAUDE_JSON_PATH, cp, executeCLI(), executeCLIStreaming(), FALLBACK_MODEL (+28 more)

### Community 34 - "KubernetesSpawnHealthAdapter"
Cohesion: 0.07
Nodes (5): KubernetesSpawnHealthAdapter, _PodHealthState, SpawnHealthPort, SpawnPollResult, SpawnStatus

### Community 35 - "storage-recycler.js"
Cohesion: 0.08
Nodes (34): withTaskStorage(), resolveStorageRoot(), ROLE_TIMEOUTS, STORAGE_ACTIVITY_HEARTBEAT_MS, STORAGE_MAX_TIER3_DELETIONS, STORAGE_PRETASK_TIMEOUT_MS, STORAGE_RESULTS_TTL_MS, STORAGE_STALE_MS (+26 more)

### Community 36 - "JenkinsAdapter"
Cohesion: 0.06
Nodes (6): BuildDetails, JenkinsAdapter, JenkinsPlatformPort, JobResult, JobRunState, ViewScanResult

### Community 38 - "agents/__init__.py"
Cohesion: 0.07
Nodes (4): Architect, AgentClient, Developer, SysAdmin

### Community 40 - "ConversationTurn"
Cohesion: 0.16
Nodes (27): emit_tool_result(), handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_recall_pruned_turns(), handle_ask_release_ai(), handle_comment_jira_issue(), handle_fetch_jira_issue() (+19 more)

### Community 43 - "TimeKeeperPage.tsx"
Cohesion: 0.12
Nodes (24): createSchedule(), deleteSchedule(), getSchedules(), refineInstructions(), ScheduleCreatePayload, ScheduleItem, toggleSchedule(), updateSchedule() (+16 more)

### Community 44 - "ScheduleRepository"
Cohesion: 0.08
Nodes (4): ScheduleCreateRequest, ScheduledEvent, update_schedule(), ScheduleRepository

### Community 45 - "ws-client.js"
Cohesion: 0.09
Nodes (26): is429Error(), {
  DEFAULT_WORK_DIR, AGENT_CLI, AGENT_MODEL, AGENT_ROLE,
  EVENT_ID, EPHEMERAL, IDLE_TIMEOUT_MS,
  CLI_429_MAX_RETRIES, CLI_429_INITIAL_DELAY_MS, CLI_429_BACKOFF_MULTIPLIER,
}, { ensureEventDocument }, { executeCLIStreaming, prepareResultsDir, is429Error }, { filterSkillsByRole, filterSkillsByMode, swapActiveRules, restoreAllSkills }, fs, handleCancel(), resetTimer() (+18 more)

### Community 46 - "ui/package.json"
Cohesion: 0.07
Nodes (30): autoprefixer, cronstrue, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, graphology-layout-forceatlas2 (+22 more)

### Community 47 - "OpsStateContext.tsx"
Cohesion: 0.11
Nodes (28): dismissProposals(), EnhancementProposal, getAgents(), getHandoffReports(), getKargoStages(), getProposals(), HandoffReport, KargoStageStatus (+20 more)

### Community 48 - "ActiveStreamsContext.tsx"
Cohesion: 0.13
Nodes (26): AgentStreamCard(), AgentStreamCardProps, FloatingWindow(), MessageCards(), Dashboard(), GridTile(), GridTileProps, TileType (+18 more)

### Community 49 - "handlers_integration.py"
Cohesion: 0.11
Nodes (14): _alert_wrapper_retrigger(), _do_retrigger(), _get_jira_reporter(), handle_refresh_github_context(), handle_refresh_gitlab_context(), handle_refresh_kargo_context(), _is_darwin_reentrant_caller(), jenkins_retrigger_cooldown_key() (+6 more)

### Community 50 - "event_to_markdown"
Cohesion: 0.08
Nodes (7): get_event_document(), report_tampering(), get_all_journal(), get_service_journal(), _esc(), _esc_join(), event_to_markdown()

### Community 51 - "EphemeralProvisioner"
Cohesion: 0.09
Nodes (3): DispatchMetrics, EphemeralProvisioner, SpawnFailed

### Community 52 - "useCortexData.ts"
Cohesion: 0.17
Nodes (26): getCognitiveGraph(), getCortexActivity(), getKGServiceDetail(), getKGServices(), getKGStats(), getKnowledgeById(), getMemory(), getRecentPulses() (+18 more)

### Community 53 - "server.js"
Cohesion: 0.08
Nodes (18): hasRegistryCredentials(), { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, fs, path, stageEventDocument(), fetchEventDocument(), fs, { handleRequest } (+10 more)

### Community 56 - "KnowledgeGraphStore"
Cohesion: 0.15
Nodes (4): _acquire(), KnowledgeGraphStore, _sanitize(), _with_timeout()

### Community 57 - "TopologyRepository"
Cohesion: 0.08
Nodes (3): Snapshot, TopologySnapshot, TopologyRepository

### Community 58 - "ArchitectureGraph.tsx"
Cohesion: 0.11
Nodes (22): @dagrejs/dagre, @xyflow/react, applyDagreLayout(), applyGridLayout(), applyLayout(), ArchitectureGraph(), ArchitectureGraphInner(), buildGraph() (+14 more)

### Community 59 - "CortexGraph.tsx"
Cohesion: 0.14
Nodes (25): graphology, eventColor(), getExecutiveNeurons(), getStructuralEdges(), DEFAULT_TYPE_BUDGET, evictLru(), KNOWLEDGE_RING, KNOWLEDGE_RING_TYPES (+17 more)

### Community 60 - "EventDrillDown.tsx"
Cohesion: 0.13
Nodes (22): getEventPulses(), BrainCore(), CortexDevPage(), CortexHeartbeat(), CortexHeartbeatProps, ensureKeyframes(), CortexLiveFeed(), CortexLiveFeedProps (+14 more)

### Community 61 - "observations_mgmt.py"
Cohesion: 0.10
Nodes (10): get_report_client(), render_pdf(), bulk_delete_observations(), BulkDeleteRequest, delete_observation(), export_observations(), generate_observations_report(), rename_observation() (+2 more)

### Community 62 - "types.py"
Cohesion: 0.12
Nodes (7): TokenUsageDict, derive_llm_priority(), LLMChunk, LLMPort, LLMResponse, TokenUsage, _turn_field()

### Community 63 - "ReconcileScheduler"
Cohesion: 0.12
Nodes (4): ReconcileScheduler, QueueTrigger, ResyncTrigger, StalenessGuard

### Community 64 - "NodeInspector.tsx"
Cohesion: 0.13
Nodes (23): getClosedEvents(), ArchitectureEvent, ArgoCDOperation, EVENT_LABELS, EventItem(), EventItemProps, healthTone(), lastOperationSummary() (+15 more)

### Community 66 - "create_schedule"
Cohesion: 0.08
Nodes (5): create_schedule(), delete_schedule(), get_schedule(), list_schedules(), toggle_schedule()

### Community 69 - "GitHubAppAuth"
Cohesion: 0.11
Nodes (3): _find_pem_file(), get_github_auth(), GitHubAppAuth

### Community 70 - "dependencies"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 71 - "StateWatcher"
Cohesion: 0.11
Nodes (3): _QueueEntry, StateWatcher, _Subscription

### Community 73 - "formatter.py"
Cohesion: 0.14
Nodes (10): build_home_tab_view(), _context_line(), create_feedback_block(), format_plan_block(), format_task_card(), format_tool_result_blocks(), format_turn(), resolve_source_emoji() (+2 more)

### Community 74 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 75 - "claude-guard.js"
Cohesion: 0.14
Nodes (18): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+10 more)

### Community 76 - "_sanitize_analysis_text"
Cohesion: 0.10
Nodes (11): _annotation_replace(), _strip_pipeline_annotations(), _clamp_confidence(), _prepare_console_tail(), _redact_match(), _redact_secrets_in_text(), _sanitize_analysis_text(), _sanitize_console_tail() (+3 more)

### Community 77 - "TokenUtilizationPage.tsx"
Cohesion: 0.16
Nodes (17): recharts, getFlowHistory(), FlowSnapshot, ObservationSeries, FlowHistoryPage(), formatTime(), RANGES, SparkCard() (+9 more)

### Community 79 - "cli-setup.js"
Cohesion: 0.13
Nodes (19): { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync }, filterSkillsByMode() (+11 more)

### Community 80 - "tool_router.py"
Cohesion: 0.11
Nodes (6): _safe_int(), handle_consult_deep_memory(), handle_google_web_search(), handle_request_user_approval(), IdleTimeoutPort, StateWatcherPort

### Community 84 - "ArchitectureEvent"
Cohesion: 0.13
Nodes (3): ArchitectureEvent, list_events(), MetricsRepository

### Community 86 - "devDependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 87 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 90 - "get_report"
Cohesion: 0.11
Nodes (6): get_report(), list_reports(), reports_spa_no_slash(), reports_spa_with_slash(), search_reports(), _serve_spa()

### Community 91 - "gemini-sidecar/package.json"
Cohesion: 0.11
Nodes (17): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+9 more)

### Community 95 - "ShiftsPage.tsx"
Cohesion: 0.23
Nodes (16): getCurrentShift(), getShiftDetail(), getShiftsList(), ShiftReportFull, ShiftReportSummary, FailedClusterBadge(), getISOWeek(), getWeekDates() (+8 more)

### Community 96 - "_reconcile"
Cohesion: 0.18
Nodes (9): _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers(), main(), _parse_frontmatter() (+1 more)

### Community 97 - "catalog-skills.js"
Cohesion: 0.16
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 98 - "gemini_client.py"
Cohesion: 0.18
Nodes (6): _append_user_turn(), _coerce_part(), _is_function_response_part(), _parse_drain_timeout(), _strip_user_thought_signature(), _validated_parts()

### Community 100 - "cortex/types.ts"
Cohesion: 0.16
Nodes (15): EventSource, KGServiceEntity, CortexGraphProps, GraphLoaderProps, PulseTimeline(), PulseTimelineProps, CognitiveGraphResponse, CortexHeartbeatMessage (+7 more)

### Community 101 - "generate_map.py"
Cohesion: 0.19
Nodes (6): _enumerate_gates(), _GateInfo, generate_phase_tool_map(), _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 106 - "ServiceNode.tsx"
Cohesion: 0.20
Nodes (11): HealthStatus, NodeType, AppNodeData, ARGOCD_HEALTH_COLORS, SYNC_ICONS, GENERIC_TAGS, HEALTH_COLORS, NODE_ICONS (+3 more)

### Community 107 - "observations_reporter.py"
Cohesion: 0.21
Nodes (7): _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), _sample_points(), _summarize()

### Community 109 - "._extract_context_flags"
Cohesion: 0.15
Nodes (3): compute_dispatch_backpressure(), ContextFlags, _safe_int_env()

### Community 114 - "NeuronInfoPanel.tsx"
Cohesion: 0.24
Nodes (12): KGServiceDetail, asNumber(), asString(), asStringArray(), Badge(), describeNeuron(), Hdr(), NeuronInfoPanel() (+4 more)

### Community 118 - "handle_report_incident"
Cohesion: 0.17
Nodes (3): handle_report_incident(), _resolve_escalation_scope(), IncidentAdapterPort

### Community 121 - "state/ports.py"
Cohesion: 0.20
Nodes (4): HealthStatus, MessageStatus, NodeType, infer_node_type()

### Community 122 - "testSetup.ts"
Cohesion: 0.18
Nodes (5): @tailwindcss/vite, @testing-library/react, vite, @vitejs/plugin-react, vitest

### Community 123 - "resolve_maintainer_emails"
Cohesion: 0.20
Nodes (4): _resolve_maintainer_enum(), _resolve_slack_user(), maintainer_env_key(), resolve_maintainer_emails()

### Community 124 - "is_defer_event_available"
Cohesion: 0.18
Nodes (6): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 126 - "CiContextCard.tsx"
Cohesion: 0.31
Nodes (9): CiContext, CiContextCardProps, ConsoleTailBlock(), FailedJobRow(), annotationReplacer(), PIPELINE_ANNOTATION_RE, REDACTION_TRIGGER_KEYWORDS, stripAnsi() (+1 more)

### Community 127 - "cortex-constants.ts"
Cohesion: 0.18
Nodes (10): AGENTS, DOMAINS, HEMISPHERE_X, NEURON_DESCRIPTIONS, PHASE_SKILL_FOLDERS, PHASE_TOOL_PRIORITY, PHASES, StructuralEdge (+2 more)

### Community 128 - "_md_table_to_text"
Cohesion: 0.20
Nodes (5): _replace(), _md_table_to_block_kit(), _md_table_to_text(), _md_to_mrkdwn(), _parse_md_table()

### Community 132 - "entity_extractor.py"
Cohesion: 0.33
Nodes (5): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship

### Community 138 - "sanitize_call_syntax"
Cohesion: 0.20
Nodes (5): _extract_call_syntax(), process_stream_call_syntax_buffer(), sanitize_call_syntax(), scan_call_syntax(), split_stream_call_syntax()

### Community 139 - "has_unevaluated_close_blocker"
Cohesion: 0.20
Nodes (4): has_unevaluated_close_blocker(), _pred_jarvis_response(), _pred_unevaluated_close(), is_jarvis_acknowledgment()

### Community 140 - "._send_turn_to_thread"
Cohesion: 0.27
Nodes (3): extract_tables(), get_agent_notification_text(), get_turn_attachment_color()

### Community 141 - "knowledge_graph_api.py"
Cohesion: 0.31
Nodes (4): get_kg_store(), get_service_detail(), get_stats(), list_services()

### Community 142 - "CortexDevPage.tsx"
Cohesion: 0.36
Nodes (8): devQueryClient, MOCK_CORTEX_STATUS, MOCK_EVENT_ID, MOCK_NEURONS, MOCK_PULSE_BATCHES, MOCK_SHADOW, MOCK_THINKING, MOCK_WHISPERS

### Community 143 - "get_quota_tracker"
Cohesion: 0.22
Nodes (3): get_quota_tracker(), llm_stats(), receive_telemetry()

### Community 150 - "useDeferCountdown.ts"
Cohesion: 0.47
Nodes (7): DeferCountdownState, useDeferCountdown(), computeDeferProgress(), DeferTimeline, formatDeferRemaining(), inferDeferFromConversation(), resolveDeferTimeline()

### Community 157 - "adf_to_markdown"
Cohesion: 0.57
Nodes (7): adf_to_markdown(), _apply_marks(), _children(), _render(), _render_list(), _render_list_item(), _render_table_like()

### Community 158 - "_format_graph_context"
Cohesion: 0.38
Nodes (3): _format_graph_context(), _parse_props(), _sanitize()

### Community 159 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 160 - "state.js"
Cohesion: 0.33
Nodes (4): { AGENT_ROLE }, _blackboardTurns, _inboundMessages, _teammateMessages

### Community 161 - "validate-mutations.sh"
Cohesion: 0.73
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

### Community 177 - "overrides"
Cohesion: 0.67
Nodes (3): overrides, @typescript-eslint/typescript-estree, minimatch

## Knowledge Gaps
- **13 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+8 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2210 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **100 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `logging`, `_is_event_closed_or_missing`, `queue.py`, `main.py`, `nightwatcher_tools.py`, `EventEvidence`, `Brain`, `EventDocument`, `cognitive_graph.py`, `BrainSkillLoader`, `Service`, `httpx`, `ConversationMessage`, `models.py`, `auth.py`, `brain.py`, `ConversationTurn`, `ScheduleRepository`, `event_to_markdown`, `HeadhunterJira`, `TopologyRepository`, `observations_mgmt.py`, `create_schedule`, `DashboardWSAdapter`, `tool_router.py`, `ArchitectureEvent`, `LiveAPIAdapter`, `get_report`, `observations_reporter.py`, `.list_observations`, `state/ports.py`?**
  _High betweenness centrality (0.131) - this node is a cross-community bridge._
- **Are the 80 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 80 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.013709005529046428 - nodes in this community are weakly interconnected._
- **Why does `Brain` connect `Brain` to `BlackboardState`, `logging`, `queue.py`, `._post_agent_recall`, `main.py`, `nightwatcher_tools.py`, `EventEvidence`, `EventDocument`, `._run_agent_task`, `BrainSkillLoader`, `brain.py`, `._process_with_llm`, `agents/__init__.py`, `.stop_event_loop`, `._format_merge_evidence`, `ConversationTurn`, `.clear_jarvis_wait`, `ReconcileScheduler`, `StateWatcher`, `DashboardWSAdapter`, `ReflexSearcher`, `._build_contents`, `IdleTimeoutManager`, `._extract_context_flags`, `BrainLifecyclePort`, `.start_event_loop`, `state/ports.py`?**
  _High betweenness centrality (0.056) - this node is a cross-community bridge._
- **Are the 21 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 21 INFERRED edges - model-reasoned connections that need verification._
- **Should `logging` be split into smaller, more focused modules?**
  _Cohesion score 0.028985507246376812 - nodes in this community are weakly interconnected._