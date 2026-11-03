# Graph Report - Blackboard  (2026-11-03)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 4942 nodes · 11054 edges · 168 communities (87 shown, 81 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 932 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `d254a2ac`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BlackboardState
- logging
- routes/timekeeper.py
- main.py
- EventEvidence
- client.ts
- queue.py
- lucide-react
- Brain
- tool_gates.py
- api/types.ts
- ._run_agent_task
- merge-guard.js
- EventSidebar.tsx
- LiveAPIAdapter
- JenkinsObserver
- ReconcileScheduler
- App.tsx
- EventHistory.tsx
- http-handler.js
- jenkins-mcp.js
- Archivist
- GitHubPlatform
- HeadhunterJira
- BrainSkillLoader
- react
- httpx
- useQueue.ts
- EventDocument
- nightwatcher_tools.py
- GitLabPlatform
- Aligner
- _BrainToolContext
- EventRepository
- ToolContext
- KnowledgeGraphStore
- observations_mgmt.py
- EventDrillDown.tsx
- ._process_with_llm
- cli-executor.js
- storage-recycler.js
- ui/package.json
- ArchitectureGraph.tsx
- JenkinsAdapter
- handlers_integration.py
- ConversationTurn
- ActiveStreamsContext.tsx
- models.py
- live_api_adapter.py
- CortexGraph.tsx
- Headhunter
- TimeKeeperPage.tsx
- VectorStore
- brain.py
- ws-client.js
- state/ports.py
- useCortexData.ts
- server.js
- SlackChannel
- context_parts.py
- TopologyRepository
- GeminiAdapter
- EphemeralProvisioner
- tool_router.py
- ArgoCDObserver
- reconcile.py
- llm/__init__.py
- ._build_system_prompt
- KargoObserver
- GitHubAppAuth
- dependencies
- StateWatcher
- compilerOptions
- claude-guard.js
- cli-setup.js
- VcsPlatformPort
- OpsStateContext.tsx
- ScheduleCreateRequest
- AgentRegistry
- ReflexSearcher
- ._poll_issues
- devDependencies
- compilerOptions
- SpawnPollResult
- gemini-sidecar/package.json
- formatter.py
- ._build_contents
- ObservationRepository
- ShiftsPage.tsx
- QuotaTracker
- catalog-skills.js
- ClaudeAdapter
- prompt.py
- SlackAccessGate
- generate_map.py
- OIDCKeyAdapter
- dispatch_to_agent
- format_event_summary
- .list_observations
- shifts.py
- EscalationRepository
- ScheduleRepository
- MultiInstallationManager
- JarvisMemoryPage.tsx
- ._extract_context_flags
- TokenMeter
- NightwatcherObserver
- IdleTimeoutManager
- ._github_poll_and_process
- CortexLiveFeed.tsx
- event_to_markdown
- is_defer_event_available
- NeuronInfoPanel.tsx
- send_cancel
- entity_extractor.py
- ._send_turn_to_thread
- knowledge_graph_api.py
- vcs_approval.py
- get_quota_tracker
- SmartsheetMaintainerCache
- Any
- MessageStatus
- AsyncGitHubClient
- GitLabTokenAuth
- ._evaluate_health
- Pulse
- get_token_meter
- TimeKeeperObserver
- scripts
- state.js
- validate-mutations.sh
- ._wait_for_registration
- has_unevaluated_close_blocker
- ._post_to_thread
- require-results.sh
- _WSFrameFilter
- math
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
1. `BlackboardState` - 283 edges
2. `Brain` - 148 edges
3. `ConversationTurn` - 122 edges
4. `ToolContext` - 103 edges
5. `GateContext` - 94 edges
6. `react` - 82 edges
7. `EventDocument` - 78 edges
8. `fetchApi()` - 66 edges
9. `lifespan()` - 64 edges
10. `LiveAPIAdapter` - 58 edges

## Surprising Connections (you probably didn't know these)
- `get_flow_history()` --uses--> `FlowSnapshot`  [INFERRED]
  src/main.py → src/models.py
- `FlowCollector` --uses--> `FlowSnapshot`  [INFERRED]
  src/observers/flow_collector.py → src/models.py
- `TopologyRepository` --uses--> `GraphResponse`  [INFERRED]
  src/state/ports.py → src/models.py
- `DashboardWSAdapter` --uses--> `BlackboardState`  [INFERRED]
  src/adapters/dashboard_ws.py → src/state/blackboard.py
- `LiveAPIAdapter` --uses--> `BlackboardState`  [INFERRED]
  src/adapters/live_api_adapter.py → src/state/blackboard.py

## Import Cycles
- None detected.

## Communities (168 total, 81 thin omitted)

### Community 0 - "BlackboardState"
Cohesion: 0.01
Nodes (13): FlowSnapshot, GraphResponse, get_all_journal(), get_service_journal(), get_notebook(), get_graph_data(), get_mermaid_diagram(), get_service_details() (+5 more)

### Community 1 - "logging"
Cohesion: 0.04
Nodes (17): _annotation_replace(), _strip_pipeline_annotations(), agent_websocket_handler(), _heartbeat(), _check_security(), _get_static_maintainer_emails(), _get_allowed_mention_authors(), _get_static_maintainer_emails() (+9 more)

### Community 2 - "routes/timekeeper.py"
Cohesion: 0.02
Nodes (37): require_auth(), require_obs_admin(), UserContext, get_blackboard(), get_pulse_tracker(), dismiss_proposals(), DismissRequest, get_all_shadow_interventions() (+29 more)

### Community 3 - "main.py"
Cohesion: 0.02
Nodes (38): KubernetesSpawnHealthAdapter, Architect, AgentClient, Developer, set_incident_options(), SysAdmin, TaskBridge, set_oidc_adapter() (+30 more)

### Community 4 - "EventEvidence"
Cohesion: 0.03
Nodes (34): DashboardWSAdapter, generate_event_title(), get_adapter(), _get_semaphore(), spawn_event_namer_task(), can_append_message(), can_approve_event(), can_override_domain() (+26 more)

### Community 5 - "client.ts"
Cohesion: 0.04
Nodes (96): @tanstack/react-query, ApiError, applyLessons(), bulkDeleteObservations(), correctMemory(), createKnowledge(), createLesson(), deleteKnowledge() (+88 more)

### Community 6 - "queue.py"
Cohesion: 0.03
Nodes (49): get_archivist(), EventStatus, get_event_document(), aligner_pending_items(), apply_lessons(), close_event_by_user(), CloseRequest, correct_memory() (+41 more)

### Community 7 - "lucide-react"
Cohesion: 0.05
Nodes (72): lucide-react, createChatEvent(), updateEventTitle(), CiContext, EventEvidence, TokenUsageDict, ChatInput(), ChatInputProps (+64 more)

### Community 9 - "tool_gates.py"
Cohesion: 0.05
Nodes (78): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+70 more)

### Community 10 - "api/types.ts"
Cohesion: 0.04
Nodes (63): recharts, getFlowHistory(), Agent, AlignerPendingItem, AppNode, AuthUser, BulkDeleteRequest, ChatEventRequest (+55 more)

### Community 11 - "._run_agent_task"
Cohesion: 0.05
Nodes (9): on_huddle(), on_progress(), on_huddle(), on_progress(), _compute_processed_up_to(), _sanitize_error_text(), _sanitize_override_reason(), _select_dispatch_tier() (+1 more)

### Community 12 - "merge-guard.js"
Cohesion: 0.05
Nodes (69): analyzeString(), analyzeTokens(), API_VALUED, apiTokens(), apiWriteNeedsGuard(), assignName(), bareBranchProtected(), base() (+61 more)

### Community 13 - "EventSidebar.tsx"
Cohesion: 0.08
Nodes (60): getHeadhunterPending(), getJiraMissions(), HeadhunterTodo, postJiraAction(), DeferCountdownBar(), ACTION_BADGE, formatAge(), HeadhunterQueuePanel() (+52 more)

### Community 15 - "JenkinsObserver"
Cohesion: 0.04
Nodes (12): _clamp_confidence(), _env_flag(), JenkinsObserver, _prepare_console_tail(), _redact_build_parameters(), _redact_match(), _redact_secrets_in_text(), _sanitize_analysis_text() (+4 more)

### Community 16 - "ReconcileScheduler"
Cohesion: 0.04
Nodes (7): FlowCollector, FairQueue, ReconcileScheduler, Trigger, QueueTrigger, ResyncTrigger, StalenessGuard

### Community 17 - "App.tsx"
Cohesion: 0.06
Nodes (48): oidc-client-ts, react-router-dom, getConfig(), getEventDocument(), getWSAuthFailureCallback(), setOnUnauthorized(), setTokenGetter(), setWSAuthFailureCallback() (+40 more)

### Community 18 - "EventHistory.tsx"
Cohesion: 0.06
Nodes (42): getReport(), getReports(), ReportSearchParams, searchReports(), ReportFull, ReportMeta, ReportSearchResponse, SubjectType (+34 more)

### Community 19 - "http-handler.js"
Cohesion: 0.09
Nodes (58): resolveCommand(), writeAgyMcpServer(), writeClaudeMcpServer(), buildArgoCDMcpConfig(), createAppJWT(), discoverAndGenerateTokens(), _discoverAndGenerateTokensInner(), discoverInstallations() (+50 more)

### Community 20 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 23 - "HeadhunterJira"
Cohesion: 0.05
Nodes (3): HeadhunterJira, _walk_adf_mentions(), _walk()

### Community 24 - "BrainSkillLoader"
Cohesion: 0.04
Nodes (5): BrainSkillLoader, _SkillCorpus, BrainIntrospectionPort, BrainLifecyclePort, BroadcastPort

### Community 25 - "react"
Cohesion: 0.08
Nodes (43): react, react-dom, @uiw/react-markdown-preview, approveEvent(), closeEvent(), enforceCasualDomain(), getEventReport(), rejectEvent() (+35 more)

### Community 26 - "httpx"
Cohesion: 0.06
Nodes (18): _adf_to_text(), _escape_jql_string(), JiraIncidentAdapter, dex_proxy(), approve_mission(), dismiss_mission(), _infer_phase(), _jira_config() (+10 more)

### Community 27 - "useQueue.ts"
Cohesion: 0.07
Nodes (48): getActiveEvents(), getAlignerPending(), getClosedEvents(), getEvents(), getJenkinsPending(), getWaitingApprovalEvents(), ActiveEvent, ArchitectureEvent (+40 more)

### Community 29 - "nightwatcher_tools.py"
Cohesion: 0.07
Nodes (25): ShiftIncident, ShiftInvestigation, build_manifest_table(), build_report_iteration_prompt(), build_summary_prompt(), build_system_prompt(), extract_event_links(), extract_full_links() (+17 more)

### Community 34 - "ToolContext"
Cohesion: 0.09
Nodes (11): handle_message_agent(), handle_reply_to_agent(), handle_report_incident(), handle_select_agent(), _resolve_escalation_scope(), _sticky_work_style(), handle_defer_event(), handle_respond_to_jarvis() (+3 more)

### Community 35 - "KnowledgeGraphStore"
Cohesion: 0.08
Nodes (9): _format_graph_context(), get_graph_context(), _parse_props(), _sanitize(), translate_to_lookups(), _acquire(), KnowledgeGraphStore, _sanitize() (+1 more)

### Community 36 - "observations_mgmt.py"
Cohesion: 0.06
Nodes (18): get_report_client(), _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), render_pdf(), _sample_points() (+10 more)

### Community 37 - "EventDrillDown.tsx"
Cohesion: 0.09
Nodes (38): three, getEventPulses(), EventSource, KGServiceEntity, BrainCore(), CortexDevPage(), devQueryClient, CortexGraphProps (+30 more)

### Community 39 - "cli-executor.js"
Cohesion: 0.09
Nodes (36): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS, STORAGE_PRETASK_TIMEOUT_MS, resolveStorageRoot }, buildCLICommand(), { checkAndRecycleStorage, pinTaskCwd, unpinTaskCwd }, CLAUDE_JSON_PATH, cp, executeCLI(), executeCLIStreaming(), FALLBACK_MODEL (+28 more)

### Community 40 - "storage-recycler.js"
Cohesion: 0.08
Nodes (34): withTaskStorage(), resolveStorageRoot(), ROLE_TIMEOUTS, STORAGE_ACTIVITY_HEARTBEAT_MS, STORAGE_MAX_TIER3_DELETIONS, STORAGE_PRETASK_TIMEOUT_MS, STORAGE_RESULTS_TTL_MS, STORAGE_STALE_MS (+26 more)

### Community 41 - "ui/package.json"
Cohesion: 0.06
Nodes (34): autoprefixer, cronstrue, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, graphology-layout-forceatlas2 (+26 more)

### Community 42 - "ArchitectureGraph.tsx"
Cohesion: 0.07
Nodes (33): @dagrejs/dagre, @xyflow/react, HealthStatus, NodeType, AppNodeData, applyDagreLayout(), applyGridLayout(), applyLayout() (+25 more)

### Community 43 - "JenkinsAdapter"
Cohesion: 0.06
Nodes (6): BuildDetails, JenkinsAdapter, JenkinsPlatformPort, JobResult, JobRunState, ViewScanResult

### Community 44 - "handlers_integration.py"
Cohesion: 0.08
Nodes (17): _alert_wrapper_retrigger(), _do_retrigger(), _get_jira_reporter(), handle_refresh_github_context(), handle_refresh_gitlab_context(), handle_refresh_kargo_context(), _is_darwin_reentrant_caller(), _resolve_maintainer_enum() (+9 more)

### Community 45 - "ConversationTurn"
Cohesion: 0.14
Nodes (28): emit_tool_result(), handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_recall_pruned_turns(), handle_ask_release_ai(), handle_comment_jira_issue(), handle_fetch_jira_issue() (+20 more)

### Community 46 - "ActiveStreamsContext.tsx"
Cohesion: 0.10
Nodes (33): getFlowMetrics(), FlowMetrics, AgentStreamCard(), AgentStreamCardProps, FloatingWindow(), MessageCards(), Dashboard(), FlowHealthWidget() (+25 more)

### Community 47 - "models.py"
Cohesion: 0.07
Nodes (18): AppNode, ChatRequest, ChatResponse, EventInput, EventMetrics, FlowMetricsResponse, GraphEdge, GraphNode (+10 more)

### Community 48 - "live_api_adapter.py"
Cohesion: 0.07
Nodes (7): _build_skill_refs(), PulseBatch, PulseContext, PulsePort, PulseObserver, PulseTracker, redact_pii()

### Community 49 - "CortexGraph.tsx"
Cohesion: 0.09
Nodes (34): graphology, AGENTS, DOMAINS, eventColor(), getExecutiveNeurons(), getStructuralEdges(), HEMISPHERE_X, NEURON_DESCRIPTIONS (+26 more)

### Community 51 - "TimeKeeperPage.tsx"
Cohesion: 0.12
Nodes (24): createSchedule(), deleteSchedule(), getSchedules(), refineInstructions(), ScheduleCreatePayload, ScheduleItem, toggleSchedule(), updateSchedule() (+16 more)

### Community 52 - "VectorStore"
Cohesion: 0.08
Nodes (3): _decode_cursor(), _encode_cursor(), VectorStore

### Community 53 - "brain.py"
Cohesion: 0.09
Nodes (10): jenkins_retrigger_cooldown_key(), handle_classify_event(), handle_hold_watch(), handle_set_phase(), EventType, _resolve_domain(), resolve_event_domain(), _resolve_phase() (+2 more)

### Community 54 - "ws-client.js"
Cohesion: 0.09
Nodes (26): is429Error(), {
  DEFAULT_WORK_DIR, AGENT_CLI, AGENT_MODEL, AGENT_ROLE,
  EVENT_ID, EPHEMERAL, IDLE_TIMEOUT_MS,
  CLI_429_MAX_RETRIES, CLI_429_INITIAL_DELAY_MS, CLI_429_BACKOFF_MULTIPLIER,
}, { ensureEventDocument }, { executeCLIStreaming, prepareResultsDir, is429Error }, { filterSkillsByRole, filterSkillsByMode, swapActiveRules, restoreAllSkills }, fs, handleCancel(), resetTimer() (+18 more)

### Community 55 - "state/ports.py"
Cohesion: 0.08
Nodes (4): ArchitectureEvent, list_events(), CortexRepository, MetricsRepository

### Community 56 - "useCortexData.ts"
Cohesion: 0.17
Nodes (26): getCognitiveGraph(), getCortexActivity(), getKGServiceDetail(), getKGServices(), getKGStats(), getKnowledgeById(), getMemory(), getRecentPulses() (+18 more)

### Community 57 - "server.js"
Cohesion: 0.08
Nodes (18): hasRegistryCredentials(), { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, fs, path, stageEventDocument(), fetchEventDocument(), fs, { handleRequest } (+10 more)

### Community 59 - "context_parts.py"
Cohesion: 0.09
Nodes (12): _apply_sibling_signature(), build_function_response(), build_single_function_response(), compress_contents(), estimate_msg_tokens(), estimate_tokens(), extract_model_parts(), normalize_response_parts() (+4 more)

### Community 60 - "TopologyRepository"
Cohesion: 0.08
Nodes (3): Snapshot, TopologySnapshot, TopologyRepository

### Community 63 - "tool_router.py"
Cohesion: 0.10
Nodes (6): _safe_int(), handle_consult_deep_memory(), handle_google_web_search(), IdleTimeoutPort, IncidentAdapterPort, StateWatcherPort

### Community 65 - "reconcile.py"
Cohesion: 0.15
Nodes (10): sanitize_redis_port(), _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers(), main() (+2 more)

### Community 66 - "llm/__init__.py"
Cohesion: 0.16
Nodes (5): FunctionCall, LLMChunk, LLMPort, LLMResponse, TokenUsage

### Community 68 - "._build_system_prompt"
Cohesion: 0.09
Nodes (3): _init_tool_names(), _strip_tool_names(), _wrap_section()

### Community 70 - "GitHubAppAuth"
Cohesion: 0.11
Nodes (3): _find_pem_file(), get_github_auth(), GitHubAppAuth

### Community 71 - "dependencies"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 72 - "StateWatcher"
Cohesion: 0.11
Nodes (3): _QueueEntry, StateWatcher, _Subscription

### Community 73 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 74 - "claude-guard.js"
Cohesion: 0.14
Nodes (18): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+10 more)

### Community 75 - "cli-setup.js"
Cohesion: 0.13
Nodes (19): { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync }, filterSkillsByMode() (+11 more)

### Community 77 - "OpsStateContext.tsx"
Cohesion: 0.16
Nodes (18): getAgents(), getKargoStages(), AgentRegistryEntry, KargoStageStatus, AgentRegistryPanel(), formatConnectedSince(), AgentGroups, AGENTS (+10 more)

### Community 82 - "devDependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 83 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 85 - "gemini-sidecar/package.json"
Cohesion: 0.11
Nodes (17): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+9 more)

### Community 86 - "formatter.py"
Cohesion: 0.13
Nodes (8): create_feedback_block(), _replace(), format_task_card(), _md_table_to_block_kit(), _md_table_to_text(), _md_to_mrkdwn(), _parse_md_table(), resolve_source_emoji()

### Community 89 - "ShiftsPage.tsx"
Cohesion: 0.23
Nodes (16): getCurrentShift(), getShiftDetail(), getShiftsList(), ShiftReportFull, ShiftReportSummary, FailedClusterBadge(), getISOWeek(), getWeekDates() (+8 more)

### Community 91 - "catalog-skills.js"
Cohesion: 0.16
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 94 - "prompt.py"
Cohesion: 0.22
Nodes (10): _build_closed_block(), build_event_header(), _build_identity_block(), _build_journal_block(), _build_mermaid_block(), _build_related_block(), _build_subject_block(), _build_timing_block() (+2 more)

### Community 96 - "generate_map.py"
Cohesion: 0.19
Nodes (6): _enumerate_gates(), _GateInfo, generate_phase_tool_map(), _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 98 - "dispatch_to_agent"
Cohesion: 0.16
Nodes (7): _build_prompt(), consume_wake_task(), _consume(), _dispatch_timeout_s(), dispatch_to_agent(), _consume_queue(), _sanitize_stdout()

### Community 99 - "format_event_summary"
Cohesion: 0.18
Nodes (7): build_home_tab_view(), _context_line(), format_event_summary(), format_plan_block(), format_turn(), _section(), _truncate()

### Community 101 - "shifts.py"
Cohesion: 0.15
Nodes (3): get_current_shift(), get_shift_detail(), list_shifts()

### Community 105 - "JarvisMemoryPage.tsx"
Cohesion: 0.25
Nodes (13): dismissProposals(), EnhancementProposal, getHandoffReports(), getProposals(), HandoffReport, FilterMode, formatDate(), formatTime() (+5 more)

### Community 106 - "._extract_context_flags"
Cohesion: 0.15
Nodes (3): compute_dispatch_backpressure(), ContextFlags, _safe_int_env()

### Community 111 - "CortexLiveFeed.tsx"
Cohesion: 0.24
Nodes (10): CortexHeartbeat(), CortexHeartbeatProps, ensureKeyframes(), CortexLiveFeed(), FILTER_PILLS, FilterKey, getStoredFilter(), MESSAGE_STYLES (+2 more)

### Community 112 - "event_to_markdown"
Cohesion: 0.27
Nodes (4): CIAnalysis, _esc(), _esc_join(), event_to_markdown()

### Community 113 - "is_defer_event_available"
Cohesion: 0.18
Nodes (6): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 114 - "NeuronInfoPanel.tsx"
Cohesion: 0.29
Nodes (10): asNumber(), asString(), asStringArray(), Badge(), describeNeuron(), Hdr(), NeuronInfoPanel(), AGENT_NEURON_COLORS (+2 more)

### Community 116 - "entity_extractor.py"
Cohesion: 0.33
Nodes (5): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship

### Community 118 - "._send_turn_to_thread"
Cohesion: 0.27
Nodes (3): extract_tables(), get_agent_notification_text(), get_turn_attachment_color()

### Community 119 - "knowledge_graph_api.py"
Cohesion: 0.31
Nodes (4): get_kg_store(), get_service_detail(), get_stats(), list_services()

### Community 120 - "vcs_approval.py"
Cohesion: 0.29
Nodes (5): get_gitlab_auth(), _resolve_github_head(), _resolve_gitlab_head(), resolve_live_head_sha(), verify_merge_guard()

### Community 121 - "get_quota_tracker"
Cohesion: 0.22
Nodes (3): get_quota_tracker(), llm_stats(), receive_telemetry()

### Community 124 - "MessageStatus"
Cohesion: 0.28
Nodes (3): HealthStatus, MessageStatus, NodeType

### Community 130 - "get_token_meter"
Cohesion: 0.25
Nodes (3): _has_non_user_turns(), _is_seed_turn(), get_token_meter()

### Community 132 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 133 - "state.js"
Cohesion: 0.33
Nodes (4): { AGENT_ROLE }, _blackboardTurns, _inboundMessages, _teammateMessages

### Community 134 - "validate-mutations.sh"
Cohesion: 0.73
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

## Knowledge Gaps
- **13 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+8 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2161 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **81 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `logging`, `routes/timekeeper.py`, `main.py`, `EventEvidence`, `queue.py`, `Brain`, `LiveAPIAdapter`, `HeadhunterJira`, `BrainSkillLoader`, `httpx`, `EventDocument`, `nightwatcher_tools.py`, `EventRepository`, `observations_mgmt.py`, `ConversationTurn`, `models.py`, `live_api_adapter.py`, `brain.py`, `state/ports.py`, `TopologyRepository`, `tool_router.py`, `ScheduleCreateRequest`, `prompt.py`, `.list_observations`, `shifts.py`, `ScheduleRepository`, `NightwatcherObserver`, `MessageStatus`?**
  _High betweenness centrality (0.113) - this node is a cross-community bridge._
- **Are the 80 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 80 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.01080361107000148 - nodes in this community are weakly interconnected._
- **Why does `Brain` connect `Brain` to `Pulse`, `BlackboardState`, `get_token_meter`, `logging`, `EventEvidence`, `main.py`, `queue.py`, `._run_agent_task`, `ReconcileScheduler`, `BrainSkillLoader`, `EventDocument`, `._process_with_llm`, `ConversationTurn`, `live_api_adapter.py`, `brain.py`, `._build_system_prompt`, `StateWatcher`, `ReflexSearcher`, `._build_contents`, `QuotaTracker`, `._extract_context_flags`, `IdleTimeoutManager`, `MessageStatus`?**
  _High betweenness centrality (0.064) - this node is a cross-community bridge._
- **Are the 20 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Should `logging` be split into smaller, more focused modules?**
  _Cohesion score 0.03863856589147287 - nodes in this community are weakly interconnected._