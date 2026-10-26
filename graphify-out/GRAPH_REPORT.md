# Graph Report - Blackboard  (2026-10-26)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 4867 nodes · 10808 edges · 210 communities (92 shown, 118 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 920 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `46a858da`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- ConversationTurn
- BlackboardState
- client.ts
- logging
- queue.py
- brain.py
- Archivist
- lucide-react
- models.py
- os
- App.tsx
- tool_gates.py
- merge-guard.js
- api/types.ts
- main.py
- dependencies.py
- colors.ts
- Brain
- jenkins-mcp.js
- EventSidebar.tsx
- Service
- TurnBubble.tsx
- BrainSkillLoader
- ArchitectureGraph.tsx
- AgentRegistry
- Aligner
- ._run_agent_task
- _BrainToolContext
- GitLabPlatform
- EventRepository
- credentials.js
- EventDocument
- storage-recycler.js
- JenkinsAdapter
- cli-executor.js
- KnowledgeGraphStore
- ActiveStreamsContext.tsx
- GitHubPlatform
- JenkinsObserver
- ._process_with_llm
- Headhunter
- CortexGraph.tsx
- TimeKeeperPage.tsx
- ws-client.js
- ui/package.json
- ._gate_check
- SlackChannel
- useCortexData.ts
- EventDrillDown.tsx
- server.js
- LiveAPIAdapter
- auth.py
- GeminiAdapter
- cognitive_graph.py
- ScheduleCreateRequest
- ArgoCDObserver
- llm/__init__.py
- ._build_system_prompt
- ._get_manager
- KargoObserver
- nightwatcher.py
- TopologyRepository
- dependencies
- http-handler.js
- slack.py
- StateWatcher
- compilerOptions
- claude-guard.js
- observations_reporter.py
- DashboardWSAdapter
- format_event_summary
- nightwatcher_tools.py
- state/__init__.py
- GitHubAppAuth
- cli-setup.js
- VcsPlatformPort
- PulseBatch
- ReflexSearcher
- FairQueue
- devDependencies
- compilerOptions
- ServiceNode.tsx
- get_report
- gemini-sidecar/package.json
- JiraIncidentAdapter
- ._build_contents
- prompt.py
- delete_schedule
- ReconcileScheduler
- ObservationRepository
- ShiftsPage.tsx
- _reconcile
- QuotaTracker
- catalog-skills.js
- EphemeralProvisioner
- ClaudeAdapter
- generate_observations_report
- .list_observations
- FlowSnapshot
- generate_map.py
- OIDCKeyAdapter
- KubernetesSpawnHealthAdapter
- EscalationRepository
- ScheduleRepository
- MultiInstallationManager
- CortexDevPage.tsx
- ._extract_context_flags
- HeadhunterJira
- TokenMeter
- IncidentAdapterPort
- chat.py
- ._send_turn_to_thread
- ArchitectureEvent
- NightwatcherObserver
- .persist_report
- IdleTimeoutManager
- JarvisMemoryPage.tsx
- ._github_poll_and_process
- SlackAccessGate
- CiContextCard.tsx
- NeuronInfoPanel.tsx
- .start_event_loop
- is_defer_event_available
- cortex-constants.ts
- spawn_health.py
- scheduling/__init__.py
- vite.config.ts
- SpawnPollResult
- entity_extractor.py
- has_unevaluated_close_blocker
- knowledge_graph_api.py
- get_quota_tracker
- SmartsheetMaintainerCache
- .has_reeval_signal
- Trigger
- AsyncGitHubClient
- GitLabTokenAuth
- useDeferCountdown.ts
- _is_event_closed_or_missing
- TimeKeeperObserver
- CortexRepository
- adf_to_markdown
- list_events
- update_notebook_note
- scripts
- validate-mutations.sh
- ._process_message
- ._evaluate_health
- list_failed_stages
- PollFn
- BrainCore
- DispatchMetrics
- _resolve_slack_user
- submit_feedback
- get_notebook
- delete_notebook_note
- PulseTimeline.tsx
- require-results.sh
- math
- SpawnFailed
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
1. `BlackboardState` - 279 edges
2. `Brain` - 148 edges
3. `ConversationTurn` - 122 edges
4. `ToolContext` - 102 edges
5. `GateContext` - 94 edges
6. `react` - 79 edges
7. `EventDocument` - 78 edges
8. `fetchApi()` - 65 edges
9. `lifespan()` - 64 edges
10. `LiveAPIAdapter` - 58 edges

## Surprising Connections (you probably didn't know these)
- `Archivist` --uses--> `PulseContext`  [INFERRED]
  src/agents/archivist.py → src/memory/pulse.py
- `DashboardWSAdapter` --uses--> `ConversationTurn`  [INFERRED]
  src/adapters/dashboard_ws.py → src/models.py
- `LiveAPIAdapter` --uses--> `ConversationTurn`  [INFERRED]
  src/adapters/live_api_adapter.py → src/models.py
- `Aligner` --uses--> `ConversationTurn`  [INFERRED]
  src/agents/aligner.py → src/models.py
- `Brain` --uses--> `ConversationTurn`  [INFERRED]
  src/agents/brain.py → src/models.py

## Import Cycles
- None detected.

## Communities (210 total, 118 thin omitted)

### Community 0 - "ConversationTurn"
Cohesion: 0.05
Nodes (55): emit_tool_result(), _safe_int(), handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_recall_pruned_turns(), handle_message_agent(), handle_reply_to_agent() (+47 more)

### Community 2 - "client.ts"
Cohesion: 0.04
Nodes (99): react, applyLessons(), bulkDeleteObservations(), correctMemory(), createChatEvent(), createKnowledge(), createLesson(), deleteKnowledge() (+91 more)

### Community 3 - "logging"
Cohesion: 0.04
Nodes (8): _heartbeat(), _sanitize_lesson_text(), get_blackboard(), _encode_cursor(), _load_name_mapping(), get_current_shift(), get_shift_detail(), list_shifts()

### Community 4 - "queue.py"
Cohesion: 0.04
Nodes (50): get_token_meter(), resolve_approval_identity(), get_archivist(), get_brain(), aligner_pending_items(), apply_lessons(), approve_event(), close_event_by_user() (+42 more)

### Community 5 - "brain.py"
Cohesion: 0.03
Nodes (37): _annotation_replace(), _strip_pipeline_annotations(), _compute_processed_up_to(), _has_non_user_turns(), _is_seed_turn(), _apply_sibling_signature(), build_function_response(), build_single_function_response() (+29 more)

### Community 6 - "Archivist"
Cohesion: 0.04
Nodes (3): Archivist, _decode_cursor(), VectorStore

### Community 7 - "lucide-react"
Cohesion: 0.05
Nodes (76): lucide-react, react-router-dom, getKargoStages(), AgentRegistryEntry, ConversationTurn, EventEvidence, KargoStageStatus, ChatInput() (+68 more)

### Community 8 - "models.py"
Cohesion: 0.04
Nodes (34): AppNode, ChatRequest, ChatResponse, EventInput, EventMetrics, EventStatus, EventType, FlowMetricsResponse (+26 more)

### Community 9 - "os"
Cohesion: 0.04
Nodes (18): _get_static_maintainer_emails(), _get_allowed_mention_authors(), _get_static_maintainer_emails(), _safe_int(), dex_proxy(), list_incidents(), approve_mission(), dismiss_mission() (+10 more)

### Community 10 - "App.tsx"
Cohesion: 0.05
Nodes (60): oidc-client-ts, @tanstack/react-query, getConfig(), getEventDocument(), getEvents(), getIncidents(), getWSAuthFailureCallback(), Incident (+52 more)

### Community 11 - "tool_gates.py"
Cohesion: 0.05
Nodes (78): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+70 more)

### Community 12 - "merge-guard.js"
Cohesion: 0.05
Nodes (69): analyzeString(), analyzeTokens(), API_VALUED, apiTokens(), apiWriteNeedsGuard(), assignName(), bareBranchProtected(), base() (+61 more)

### Community 13 - "api/types.ts"
Cohesion: 0.04
Nodes (61): recharts, getFlowHistory(), ActiveEvent, Agent, AlignerPendingItem, AppNode, AuthUser, BulkDeleteRequest (+53 more)

### Community 14 - "main.py"
Cohesion: 0.04
Nodes (23): set_incident_options(), set_oidc_adapter(), set_agents(), set_archivist(), set_argocd_observer(), set_blackboard(), set_brain(), set_kargo_observer() (+15 more)

### Community 15 - "dependencies.py"
Cohesion: 0.04
Nodes (15): Architect, AgentClient, Developer, _check_security(), safe_execution(), wrapper(), SecurityError, SysAdmin (+7 more)

### Community 16 - "colors.ts"
Cohesion: 0.07
Nodes (43): getReport(), getReports(), ReportSearchParams, searchReports(), ReportFull, ReportMeta, ReportSearchResponse, CompactCardStrip() (+35 more)

### Community 18 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 19 - "EventSidebar.tsx"
Cohesion: 0.09
Nodes (52): getHeadhunterPending(), getJiraMissions(), HeadhunterTodo, postJiraAction(), ACTION_BADGE, formatAge(), HeadhunterQueuePanel(), renderItem() (+44 more)

### Community 20 - "Service"
Cohesion: 0.05
Nodes (8): Service, get_event_document(), get_graph_data(), get_mermaid_diagram(), get_service_details(), get_topology(), list_services(), calculate_health_from_argocd()

### Community 21 - "TurnBubble.tsx"
Cohesion: 0.08
Nodes (42): @uiw/react-markdown-preview, approveEvent(), closeEvent(), enforceCasualDomain(), rejectEvent(), submitFeedback(), MessageStatus, CollapsibleSection() (+34 more)

### Community 22 - "BrainSkillLoader"
Cohesion: 0.05
Nodes (5): BrainSkillLoader, _SkillCorpus, BrainIntrospectionPort, BrainLifecyclePort, BroadcastPort

### Community 23 - "ArchitectureGraph.tsx"
Cohesion: 0.06
Nodes (45): ApiError, getClosedEvents(), getGraphData(), getService(), ArchitectureEvent, ArgoCDOperation, GraphResponse, Service (+37 more)

### Community 24 - "AgentRegistry"
Cohesion: 0.06
Nodes (13): AgentConnection, AgentRegistry, agent_websocket_handler(), _build_prompt(), consume_wake_task(), _consume(), _dispatch_timeout_s(), dispatch_to_agent() (+5 more)

### Community 26 - "._run_agent_task"
Cohesion: 0.08
Nodes (7): on_huddle(), on_progress(), on_huddle(), on_progress(), _sanitize_error_text(), _sanitize_override_reason(), get_registry_and_bridge()

### Community 30 - "credentials.js"
Cohesion: 0.12
Nodes (45): resolveCommand(), writeAgyMcpServer(), writeClaudeMcpServer(), buildArgoCDMcpConfig(), createAppJWT(), discoverAndGenerateTokens(), _discoverAndGenerateTokensInner(), discoverInstallations() (+37 more)

### Community 32 - "storage-recycler.js"
Cohesion: 0.08
Nodes (34): withTaskStorage(), resolveStorageRoot(), ROLE_TIMEOUTS, STORAGE_ACTIVITY_HEARTBEAT_MS, STORAGE_MAX_TIER3_DELETIONS, STORAGE_PRETASK_TIMEOUT_MS, STORAGE_RESULTS_TTL_MS, STORAGE_STALE_MS (+26 more)

### Community 33 - "JenkinsAdapter"
Cohesion: 0.06
Nodes (6): BuildDetails, JenkinsAdapter, JenkinsPlatformPort, JobResult, JobRunState, ViewScanResult

### Community 34 - "cli-executor.js"
Cohesion: 0.09
Nodes (34): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS, STORAGE_PRETASK_TIMEOUT_MS, resolveStorageRoot }, buildCLICommand(), { checkAndRecycleStorage, pinTaskCwd, unpinTaskCwd }, CLAUDE_JSON_PATH, cp, executeCLI(), executeCLIStreaming(), FALLBACK_MODEL (+26 more)

### Community 35 - "KnowledgeGraphStore"
Cohesion: 0.09
Nodes (9): _format_graph_context(), get_graph_context(), _parse_props(), _sanitize(), translate_to_lookups(), _acquire(), KnowledgeGraphStore, _sanitize() (+1 more)

### Community 36 - "ActiveStreamsContext.tsx"
Cohesion: 0.10
Nodes (33): getFlowMetrics(), FlowMetrics, AgentStreamCard(), AgentStreamCardProps, FloatingWindow(), MessageCards(), Dashboard(), FlowHealthWidget() (+25 more)

### Community 41 - "CortexGraph.tsx"
Cohesion: 0.11
Nodes (29): graphology, @react-sigma/core, @react-sigma/layout-forceatlas2, sigma, @sigma/node-square, eventColor(), getStructuralEdges(), DEFAULT_TYPE_BUDGET (+21 more)

### Community 42 - "TimeKeeperPage.tsx"
Cohesion: 0.13
Nodes (20): createSchedule(), getSchedules(), ScheduleCreatePayload, ScheduleItem, Props, ScheduleForm(), TEMPLATES, formatNextFire() (+12 more)

### Community 43 - "ws-client.js"
Cohesion: 0.10
Nodes (24): is429Error(), {
  DEFAULT_WORK_DIR, AGENT_CLI, AGENT_MODEL, AGENT_ROLE,
  EVENT_ID, EPHEMERAL, IDLE_TIMEOUT_MS,
  CLI_429_MAX_RETRIES, CLI_429_INITIAL_DELAY_MS, CLI_429_BACKOFF_MULTIPLIER,
}, { ensureEventDocument }, { executeCLIStreaming, prepareResultsDir, is429Error }, { filterSkillsByRole, filterSkillsByMode, swapActiveRules, restoreAllSkills }, handleCancel(), resetTimer(), {
  hasGitHubCredentials, discoverAndGenerateTokens, setupGitCredentials, setupGitHubTooling,
  hasGitLabCredentials, readGitLabToken, setupGitLabCredentials, setupGitLabTooling,
  setupArgoCDMCP, setupCLILogins, setupRemoteK8sMCPs, setupRegistryCredentials, GITLAB_HOST,
  hasJenkinsCredentials, setupJenkinsMCP, hasGoogleServiceAccount, setupGoogleAuthForAgy,
} (+16 more)

### Community 44 - "ui/package.json"
Cohesion: 0.08
Nodes (27): autoprefixer, cronstrue, @dagrejs/dagre, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals (+19 more)

### Community 45 - "._gate_check"
Cohesion: 0.13
Nodes (8): get_user_from_slack(), handle_app_home_opened(), handle_app_mention(), handle_approve(), handle_create_event_modal(), handle_home_create_event(), handle_reject(), on_dm_message()

### Community 47 - "useCortexData.ts"
Cohesion: 0.18
Nodes (25): getCognitiveGraph(), getCortexActivity(), getEventReport(), getKGServiceDetail(), getKGServices(), getKGStats(), getRecentPulses(), getExecutiveNeurons() (+17 more)

### Community 48 - "EventDrillDown.tsx"
Cohesion: 0.13
Nodes (24): CortexHeartbeat(), CortexHeartbeatProps, ensureKeyframes(), CortexLiveFeed(), CortexLiveFeedProps, FILTER_PILLS, FilterKey, getStoredFilter() (+16 more)

### Community 49 - "server.js"
Cohesion: 0.09
Nodes (18): hasRegistryCredentials(), { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, fs, path, stageEventDocument(), fetchEventDocument(), fs, { handleRequest } (+10 more)

### Community 51 - "auth.py"
Cohesion: 0.12
Nodes (10): can_approve_event(), can_override_domain(), _claims_to_user(), get_user_from_request(), get_user_from_websocket(), _normalize_email(), require_auth(), require_obs_admin() (+2 more)

### Community 53 - "cognitive_graph.py"
Cohesion: 0.11
Nodes (11): get_pulse_tracker(), dismiss_proposals(), DismissRequest, get_all_shadow_interventions(), get_cognitive_graph(), get_cortex_activity(), get_cortex_status(), get_event_shadow_interventions() (+3 more)

### Community 54 - "ScheduleCreateRequest"
Cohesion: 0.11
Nodes (3): ScheduleCreateRequest, create_schedule(), update_schedule()

### Community 56 - "llm/__init__.py"
Cohesion: 0.16
Nodes (5): FunctionCall, LLMChunk, LLMPort, LLMResponse, TokenUsage

### Community 57 - "._build_system_prompt"
Cohesion: 0.09
Nodes (3): _init_tool_names(), _strip_tool_names(), _wrap_section()

### Community 61 - "nightwatcher.py"
Cohesion: 0.11
Nodes (10): build_report_iteration_prompt(), build_summary_prompt(), extract_full_links(), _normalize_gitlab_host(), build_extend_tool(), build_report_tool(), build_summary_tool(), get_phase_tools() (+2 more)

### Community 63 - "dependencies"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 64 - "http-handler.js"
Cohesion: 0.09
Nodes (18): { AGENT_CLI, AGENT_MODEL, DEFAULT_WORK_DIR, PORT, BRAIN_HTTP_URL }, { claudeMergeGuard }, { executeCLI }, fs, {
  hasGitHubCredentials,
  discoverAndGenerateTokens,
  setupGitCredentials,
  setupGitHubTooling,
  hasGitLabCredentials,
  readGitLabToken,
  setupGitLabCredentials,
  setupGitLabTooling,
  setupArgoCDMCP,
  setupCLILogins,
  setupRegistryCredentials,
  setupRemoteK8sMCPs,
  getRemoteClustersMeta,
  GITLAB_HOST,
}, http, isLoopbackAddress(), { isReadOnlyRoleName } (+10 more)

### Community 65 - "slack.py"
Cohesion: 0.10
Nodes (7): build_access_denied_home_view(), build_event_report_md(), create_feedback_block(), _md_table_to_text(), _md_to_mrkdwn(), _parse_md_table(), table_block_to_code_block()

### Community 66 - "StateWatcher"
Cohesion: 0.11
Nodes (3): _QueueEntry, StateWatcher, _Subscription

### Community 67 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 68 - "claude-guard.js"
Cohesion: 0.14
Nodes (18): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+10 more)

### Community 69 - "observations_reporter.py"
Cohesion: 0.13
Nodes (9): _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), render_pdf(), _sample_points(), _summarize() (+1 more)

### Community 71 - "format_event_summary"
Cohesion: 0.11
Nodes (10): build_home_tab_view(), _context_line(), format_event_summary(), format_plan_block(), format_task_card(), format_turn(), resolve_source_emoji(), _section() (+2 more)

### Community 72 - "nightwatcher_tools.py"
Cohesion: 0.18
Nodes (12): ShiftIncident, ShiftInvestigation, execute_tool(), _handle_consult_deep_memory(), _handle_declare_clusters(), _handle_dispatch_investigation(), _handle_get_event_report(), _handle_post_shift_summary() (+4 more)

### Community 73 - "state/__init__.py"
Cohesion: 0.12
Nodes (3): close_redis(), get_redis(), RedisClient

### Community 75 - "cli-setup.js"
Cohesion: 0.13
Nodes (19): { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync }, filterSkillsByMode() (+11 more)

### Community 77 - "PulseBatch"
Cohesion: 0.12
Nodes (4): PulseBatch, PulsePort, PulseObserver, PulseTracker

### Community 80 - "devDependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 81 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 82 - "ServiceNode.tsx"
Cohesion: 0.15
Nodes (13): @xyflow/react, HealthStatus, NodeType, AppNodeData, ARGOCD_HEALTH_COLORS, SYNC_ICONS, NamespaceGroupNodeData, GENERIC_TAGS (+5 more)

### Community 83 - "get_report"
Cohesion: 0.11
Nodes (6): get_report(), list_reports(), reports_spa_no_slash(), reports_spa_with_slash(), search_reports(), _serve_spa()

### Community 84 - "gemini-sidecar/package.json"
Cohesion: 0.11
Nodes (17): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+9 more)

### Community 85 - "JiraIncidentAdapter"
Cohesion: 0.15
Nodes (3): _adf_to_text(), _escape_jql_string(), JiraIncidentAdapter

### Community 89 - "prompt.py"
Cohesion: 0.18
Nodes (10): _build_closed_block(), build_event_header(), _build_identity_block(), _build_journal_block(), _build_mermaid_block(), _build_related_block(), _build_subject_block(), _build_timing_block() (+2 more)

### Community 90 - "delete_schedule"
Cohesion: 0.11
Nodes (4): delete_schedule(), get_schedule(), list_schedules(), toggle_schedule()

### Community 91 - "ReconcileScheduler"
Cohesion: 0.14
Nodes (3): ReconcileScheduler, QueueTrigger, StalenessGuard

### Community 93 - "ShiftsPage.tsx"
Cohesion: 0.23
Nodes (16): getCurrentShift(), getShiftDetail(), getShiftsList(), ShiftReportFull, ShiftReportSummary, FailedClusterBadge(), getISOWeek(), getWeekDates() (+8 more)

### Community 94 - "_reconcile"
Cohesion: 0.18
Nodes (9): _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers(), main(), _parse_frontmatter() (+1 more)

### Community 96 - "catalog-skills.js"
Cohesion: 0.16
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 99 - "generate_observations_report"
Cohesion: 0.12
Nodes (7): bulk_delete_observations(), BulkDeleteRequest, delete_observation(), generate_observations_report(), rename_observation(), RenameRequest, ReportRequest

### Community 100 - ".list_observations"
Cohesion: 0.13
Nodes (3): get_event_observations(), get_global_observations(), export_observations()

### Community 103 - "generate_map.py"
Cohesion: 0.19
Nodes (6): _enumerate_gates(), _GateInfo, generate_phase_tool_map(), _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 110 - "CortexDevPage.tsx"
Cohesion: 0.23
Nodes (12): getEventPulses(), CortexDevPage(), devQueryClient, EventDrillDown(), MOCK_CORTEX_STATUS, MOCK_EVENT_ID, MOCK_NEURONS, MOCK_PULSE_BATCHES (+4 more)

### Community 111 - "._extract_context_flags"
Cohesion: 0.15
Nodes (3): compute_dispatch_backpressure(), ContextFlags, _safe_int_env()

### Community 114 - "IncidentAdapterPort"
Cohesion: 0.15
Nodes (3): IdleTimeoutPort, IncidentAdapterPort, StateWatcherPort

### Community 115 - "chat.py"
Cohesion: 0.21
Nodes (4): can_append_message(), ChatEventRequest, ChatEventResponse, create_chat_event()

### Community 116 - "._send_turn_to_thread"
Cohesion: 0.19
Nodes (5): extract_tables(), _replace(), get_agent_notification_text(), get_turn_attachment_color(), _md_table_to_block_kit()

### Community 121 - "JarvisMemoryPage.tsx"
Cohesion: 0.27
Nodes (12): dismissProposals(), EnhancementProposal, getHandoffReports(), getProposals(), HandoffReport, FilterMode, formatDate(), formatTime() (+4 more)

### Community 127 - "CiContextCard.tsx"
Cohesion: 0.29
Nodes (10): CiContext, CiContextCard(), CiContextCardProps, ConsoleTailBlock(), FailedJobRow(), annotationReplacer(), PIPELINE_ANNOTATION_RE, REDACTION_TRIGGER_KEYWORDS (+2 more)

### Community 128 - "NeuronInfoPanel.tsx"
Cohesion: 0.27
Nodes (11): KGServiceDetail, asNumber(), asString(), asStringArray(), Badge(), describeNeuron(), Hdr(), NeuronInfoPanel() (+3 more)

### Community 130 - "is_defer_event_available"
Cohesion: 0.18
Nodes (6): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 131 - "cortex-constants.ts"
Cohesion: 0.18
Nodes (10): AGENTS, DOMAINS, HEMISPHERE_X, NEURON_DESCRIPTIONS, PHASE_SKILL_FOLDERS, PHASE_TOOL_PRIORITY, PHASES, StructuralEdge (+2 more)

### Community 133 - "scheduling/__init__.py"
Cohesion: 0.29
Nodes (4): GitHubPrRef, GitLabMrRef, GitLabPipelineRef, KargoStageRef

### Community 134 - "vite.config.ts"
Cohesion: 0.20
Nodes (5): @tailwindcss/vite, @testing-library/react, vite, @vitejs/plugin-react, vitest

### Community 136 - "entity_extractor.py"
Cohesion: 0.33
Nodes (5): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship

### Community 137 - "has_unevaluated_close_blocker"
Cohesion: 0.20
Nodes (4): has_unevaluated_close_blocker(), _pred_jarvis_response(), _pred_unevaluated_close(), is_jarvis_acknowledgment()

### Community 138 - "knowledge_graph_api.py"
Cohesion: 0.31
Nodes (4): get_kg_store(), get_service_detail(), get_stats(), list_services()

### Community 139 - "get_quota_tracker"
Cohesion: 0.22
Nodes (3): get_quota_tracker(), llm_stats(), receive_telemetry()

### Community 145 - "useDeferCountdown.ts"
Cohesion: 0.47
Nodes (7): DeferCountdownState, useDeferCountdown(), computeDeferProgress(), DeferTimeline, formatDeferRemaining(), inferDeferFromConversation(), resolveDeferTimeline()

### Community 151 - "adf_to_markdown"
Cohesion: 0.57
Nodes (7): adf_to_markdown(), _apply_marks(), _children(), _render(), _render_list(), _render_list_item(), _render_table_like()

### Community 155 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 156 - "validate-mutations.sh"
Cohesion: 0.73
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

### Community 179 - "PulseTimeline.tsx"
Cohesion: 0.50
Nodes (3): PulseTimeline(), PulseTimelineProps, NEURON_COLORS

## Knowledge Gaps
- **13 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+8 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2126 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **118 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `ConversationTurn`, `logging`, `queue.py`, `brain.py`, `models.py`, `os`, `main.py`, `dependencies.py`, `Brain`, `_is_event_closed_or_missing`, `Service`, `list_events`, `update_notebook_note`, `EventRepository`, `EventDocument`, `._restage_pending_signal`, `._stage_pending_signal`, `submit_feedback`, `get_notebook`, `._count_pending`, `.__init__`, `delete_notebook_note`, `.cleanup_stale_services`, `.drain_notes`, `LiveAPIAdapter`, `.get_edge_metadata`, `ScheduleCreateRequest`, `nightwatcher.py`, `slack.py`, `observations_reporter.py`, `DashboardWSAdapter`, `nightwatcher_tools.py`, `state/__init__.py`, `get_report`, `delete_schedule`, `generate_observations_report`, `.list_observations`, `FlowSnapshot`, `ScheduleRepository`, `HeadhunterJira`, `chat.py`, `ArchitectureEvent`, `NightwatcherObserver`, `.persist_report`?**
  _High betweenness centrality (0.105) - this node is a cross-community bridge._
- **Are the 78 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 78 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `ConversationTurn` be split into smaller, more focused modules?**
  _Cohesion score 0.050082918739635156 - nodes in this community are weakly interconnected._
- **Why does `Brain` connect `Brain` to `ConversationTurn`, `.start_event_loop`, `BlackboardState`, `brain.py`, `models.py`, `os`, `main.py`, `dependencies.py`, `._execute_function_call`, `BrainSkillLoader`, `._run_agent_task`, `EventDocument`, `._process_with_llm`, `.__init__`, `._build_system_prompt`, `._close_and_broadcast`, `slack.py`, `StateWatcher`, `DashboardWSAdapter`, `PulseBatch`, `ReflexSearcher`, `._build_contents`, `._process_event_inner`, `ReconcileScheduler`, `QuotaTracker`, `FlowSnapshot`, `._extract_context_flags`, `IdleTimeoutManager`?**
  _High betweenness centrality (0.059) - this node is a cross-community bridge._
- **Are the 20 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.017178075006556517 - nodes in this community are weakly interconnected._