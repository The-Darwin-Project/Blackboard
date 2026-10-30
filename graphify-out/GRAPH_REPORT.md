# Graph Report - Blackboard  (2026-10-30)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 4877 nodes · 10872 edges · 207 communities (84 shown, 123 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 927 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `b72456e8`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BlackboardState
- brain.py
- logging
- client.ts
- queue.py
- EventChatPanel.tsx
- EventDocument
- tool_gates.py
- Brain
- App.tsx
- merge-guard.js
- os
- EventSidebar.tsx
- credentials.js
- colors.ts
- jenkins-mcp.js
- BrainSkillLoader
- react
- ._run_agent_task
- AgentRegistry
- Archivist
- auth.py
- ReconcileScheduler
- TurnBubble.tsx
- .get_graph_data
- _BrainToolContext
- ConversationTurn
- GitLabPlatform
- nightwatcher_tools.py
- cli-executor.js
- ToolContext
- EventRepository
- JenkinsAdapter
- KnowledgeGraphStore
- storage-recycler.js
- .start_event_loop
- ._process_with_llm
- GitHubPlatform
- OpsStateContext.tsx
- ws-client.js
- TimeKeeperPage.tsx
- Headhunter
- useCortexData.ts
- ActiveStreamsContext.tsx
- ui/package.json
- ._gate_check
- server.js
- SlackChannel
- handlers_integration.py
- Aligner
- observations_mgmt.py
- CortexGraph.tsx
- adf_to_markdown
- GeminiAdapter
- cognitive_graph.py
- NodeInspector.tsx
- scheduling/__init__.py
- ArgoCDObserver
- llm/__init__.py
- ._get_manager
- KargoObserver
- TopologyRepository
- dependencies
- reconcile.py
- PulseBatch
- compilerOptions
- claude-guard.js
- http-handler.js
- TokenUtilizationPage.tsx
- format_event_summary
- GitHubAppAuth
- lifespan
- VcsPlatformPort
- slack.py
- ArchitectureGraph.tsx
- record_token_usage
- ReflexSearcher
- devDependencies
- compilerOptions
- ServiceNode.tsx
- LiveAPIAdapter
- JenkinsObserver
- get_report
- ScheduleCreateRequest
- catalog-skills.js
- gemini-sidecar/package.json
- handlers_state.py
- ObservationRepository
- ShiftsPage.tsx
- QuotaTracker
- DashboardWSAdapter
- EphemeralProvisioner
- ClaudeAdapter
- VectorStore
- cortex/types.ts
- CortexDevPage.tsx
- SlackAccessGate
- generate_map.py
- OIDCKeyAdapter
- KubernetesSpawnHealthAdapter
- EscalationRepository
- observations_reporter.py
- ScheduleRepository
- MultiInstallationManager
- EventDrillDown.tsx
- .scroll
- ._extract_context_flags
- BrainLifecyclePort
- HeadhunterJira
- TokenMeter
- ._send_turn_to_thread
- NightwatcherObserver
- IdleTimeoutManager
- NeuronInfoPanel.tsx
- ._github_poll_and_process
- _sanitize_analysis_text
- CortexLiveFeed.tsx
- is_defer_event_available
- cortex-constants.ts
- spawn_health.py
- vite.config.ts
- _is_event_closed_or_missing
- SpawnPollResult
- ._post_agent_recall
- entity_extractor.py
- _validate_analysis
- IncidentAdapterPort
- knowledge_graph_api.py
- get_quota_tracker
- SmartsheetMaintainerCache
- .has_reeval_signal
- MetricsRepository
- AsyncGitHubClient
- GitLabTokenAuth
- ._triage_and_build_evidence
- TimeKeeperObserver
- CortexRepository
- FilterRule
- scripts
- validate-mutations.sh
- io
- ._process_message
- ._evaluate_health
- list_failed_stages
- dex_proxy
- DispatchMetrics
- _has_non_user_turns
- _patch_enum_fields
- require-results.sh
- _WSFrameFilter
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
- build_gate_context
- diagnose_rejection
- GateDefinition
- _pred_dispatch_defer
- _pred_hard_strip_defer
- _pred_jarvis_response
- _pred_jarvis_wait
- _pred_obs_plateau
- _pred_silent_park
- _pred_unevaluated_close
- _tools_wait_loop

## God Nodes (most connected - your core abstractions)
1. `BlackboardState` - 280 edges
2. `Brain` - 148 edges
3. `ConversationTurn` - 122 edges
4. `ToolContext` - 103 edges
5. `GateContext` - 94 edges
6. `react` - 80 edges
7. `EventDocument` - 78 edges
8. `fetchApi()` - 65 edges
9. `lifespan()` - 64 edges
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

## Communities (207 total, 123 thin omitted)

### Community 0 - "BlackboardState"
Cohesion: 0.01
Nodes (16): list_events(), get_all_journal(), get_service_journal(), delete_notebook_note(), get_notebook(), get_event_observations(), get_global_observations(), get_current_shift() (+8 more)

### Community 1 - "brain.py"
Cohesion: 0.02
Nodes (46): _annotation_replace(), _strip_pipeline_annotations(), _sanitize_lesson_text(), _compute_processed_up_to(), _safe_int(), _parse_job_metadata(), create_adapter(), Pulse (+38 more)

### Community 2 - "logging"
Cohesion: 0.02
Nodes (39): Architect, AgentClient, Developer, _check_security(), safe_execution(), wrapper(), SecurityError, SysAdmin (+31 more)

### Community 3 - "client.ts"
Cohesion: 0.03
Nodes (102): @tanstack/react-query, ApiError, bulkDeleteObservations(), createChatEvent(), deleteNote(), deleteObservation(), exportObservations(), ExtractedCorrection (+94 more)

### Community 4 - "queue.py"
Cohesion: 0.03
Nodes (52): get_token_meter(), can_approve_event(), resolve_approval_identity(), get_archivist(), get_brain(), report_tampering(), aligner_pending_items(), apply_lessons() (+44 more)

### Community 5 - "EventChatPanel.tsx"
Cohesion: 0.05
Nodes (78): react-router-dom, ActiveEvent, CiContext, ConversationTurn, EventEvidence, TokenUsageDict, ChatInput(), ChatInputProps (+70 more)

### Community 6 - "EventDocument"
Cohesion: 0.03
Nodes (24): _close_unanswered_fc(), _apply_sibling_signature(), build_function_response(), build_single_function_response(), compress_contents(), estimate_msg_tokens(), estimate_tokens(), extract_model_parts() (+16 more)

### Community 7 - "tool_gates.py"
Cohesion: 0.05
Nodes (78): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+70 more)

### Community 9 - "App.tsx"
Cohesion: 0.05
Nodes (58): oidc-client-ts, dismissProposals(), EnhancementProposal, getHandoffReports(), getIncidents(), getProposals(), getWSAuthFailureCallback(), HandoffReport (+50 more)

### Community 10 - "merge-guard.js"
Cohesion: 0.05
Nodes (69): analyzeString(), analyzeTokens(), API_VALUED, apiTokens(), apiWriteNeedsGuard(), assignName(), bareBranchProtected(), base() (+61 more)

### Community 11 - "os"
Cohesion: 0.05
Nodes (20): _get_static_maintainer_emails(), _get_allowed_mention_authors(), _get_static_maintainer_emails(), _load_name_mapping(), build_manifest_table(), build_system_prompt(), extract_event_links(), list_incidents() (+12 more)

### Community 12 - "EventSidebar.tsx"
Cohesion: 0.08
Nodes (56): getAlignerPending(), getHeadhunterPending(), getJenkinsPending(), getJiraMissions(), getWaitingApprovalEvents(), HeadhunterTodo, postJiraAction(), EventDocument (+48 more)

### Community 13 - "credentials.js"
Cohesion: 0.07
Nodes (59): is429Error(), { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync } (+51 more)

### Community 14 - "colors.ts"
Cohesion: 0.07
Nodes (38): getReport(), getReports(), ReportFull, ReportMeta, SubjectType, CompactCardStrip(), EventHistory(), TimeRange (+30 more)

### Community 15 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 16 - "BrainSkillLoader"
Cohesion: 0.05
Nodes (4): BrainSkillLoader, _SkillCorpus, _wrap_section(), BrainIntrospectionPort

### Community 17 - "react"
Cohesion: 0.08
Nodes (50): lucide-react, react, applyLessons(), correctMemory(), createKnowledge(), createLesson(), deleteKnowledge(), deleteLesson() (+42 more)

### Community 18 - "._run_agent_task"
Cohesion: 0.07
Nodes (7): on_huddle(), on_progress(), on_huddle(), on_progress(), _sanitize_error_text(), _sanitize_override_reason(), get_registry_and_bridge()

### Community 19 - "AgentRegistry"
Cohesion: 0.05
Nodes (14): AgentConnection, AgentRegistry, agent_websocket_handler(), _heartbeat(), _build_prompt(), consume_wake_task(), _consume(), _dispatch_timeout_s() (+6 more)

### Community 21 - "auth.py"
Cohesion: 0.05
Nodes (20): can_append_message(), can_override_domain(), _claims_to_user(), get_user_from_request(), get_user_from_websocket(), _normalize_email(), prompt_display_name(), require_auth() (+12 more)

### Community 22 - "ReconcileScheduler"
Cohesion: 0.05
Nodes (6): FairQueue, ReconcileScheduler, Trigger, QueueTrigger, ResyncTrigger, StalenessGuard

### Community 23 - "TurnBubble.tsx"
Cohesion: 0.09
Nodes (39): @uiw/react-markdown-preview, approveEvent(), closeEvent(), enforceCasualDomain(), getEventReport(), rejectEvent(), submitFeedback(), ConversationFeed() (+31 more)

### Community 24 - ".get_graph_data"
Cohesion: 0.05
Nodes (7): get_graph_data(), get_mermaid_diagram(), get_service_details(), get_topology(), list_services(), calculate_health_from_argocd(), infer_node_type()

### Community 26 - "ConversationTurn"
Cohesion: 0.11
Nodes (23): emit_tool_result(), _safe_int(), handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_recall_pruned_turns(), handle_notify_gitlab_result(), handle_consult_deep_memory() (+15 more)

### Community 28 - "nightwatcher_tools.py"
Cohesion: 0.08
Nodes (23): PulseContext, ShiftIncident, ShiftInvestigation, build_report_iteration_prompt(), build_summary_prompt(), extract_full_links(), _normalize_gitlab_host(), build_extend_tool() (+15 more)

### Community 29 - "cli-executor.js"
Cohesion: 0.09
Nodes (36): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS, STORAGE_PRETASK_TIMEOUT_MS, resolveStorageRoot }, buildCLICommand(), { checkAndRecycleStorage, pinTaskCwd, unpinTaskCwd }, CLAUDE_JSON_PATH, cp, executeCLI(), executeCLIStreaming(), FALLBACK_MODEL (+28 more)

### Community 30 - "ToolContext"
Cohesion: 0.09
Nodes (11): handle_message_agent(), handle_reply_to_agent(), handle_report_incident(), handle_select_agent(), _sticky_work_style(), handle_search_open_incidents(), handle_defer_event(), handle_respond_to_jarvis() (+3 more)

### Community 32 - "JenkinsAdapter"
Cohesion: 0.06
Nodes (6): BuildDetails, JenkinsAdapter, JenkinsPlatformPort, JobResult, JobRunState, ViewScanResult

### Community 33 - "KnowledgeGraphStore"
Cohesion: 0.09
Nodes (9): _format_graph_context(), get_graph_context(), _parse_props(), _sanitize(), translate_to_lookups(), _acquire(), KnowledgeGraphStore, _sanitize() (+1 more)

### Community 34 - "storage-recycler.js"
Cohesion: 0.09
Nodes (32): withTaskStorage(), resolveStorageRoot(), ROLE_TIMEOUTS, STORAGE_ACTIVITY_HEARTBEAT_MS, STORAGE_MAX_TIER3_DELETIONS, STORAGE_PRETASK_TIMEOUT_MS, STORAGE_RESULTS_TTL_MS, STORAGE_STALE_MS (+24 more)

### Community 35 - ".start_event_loop"
Cohesion: 0.07
Nodes (4): FlowCollector, _QueueEntry, StateWatcher, _Subscription

### Community 38 - "OpsStateContext.tsx"
Cohesion: 0.10
Nodes (29): getAgents(), getKargoStages(), AgentRegistryEntry, KargoStageStatus, AgentRegistryPanel(), formatConnectedSince(), STARTER_CHIPS, StarterChip (+21 more)

### Community 39 - "ws-client.js"
Cohesion: 0.08
Nodes (27): { AGENT_ROLE }, _blackboardTurns, _inboundMessages, _teammateMessages, {
  DEFAULT_WORK_DIR, AGENT_CLI, AGENT_MODEL, AGENT_ROLE,
  EVENT_ID, EPHEMERAL, IDLE_TIMEOUT_MS,
  CLI_429_MAX_RETRIES, CLI_429_INITIAL_DELAY_MS, CLI_429_BACKOFF_MULTIPLIER,
}, { ensureEventDocument }, { executeCLIStreaming, prepareResultsDir, is429Error }, { filterSkillsByRole, filterSkillsByMode, swapActiveRules, restoreAllSkills } (+19 more)

### Community 40 - "TimeKeeperPage.tsx"
Cohesion: 0.12
Nodes (24): createSchedule(), deleteSchedule(), getSchedules(), refineInstructions(), ScheduleCreatePayload, ScheduleItem, toggleSchedule(), updateSchedule() (+16 more)

### Community 42 - "useCortexData.ts"
Cohesion: 0.15
Nodes (29): getCognitiveGraph(), getCortexActivity(), getKGServiceDetail(), getKGServices(), getKGStats(), getKnowledgeById(), getLessonById(), getMemory() (+21 more)

### Community 43 - "ActiveStreamsContext.tsx"
Cohesion: 0.13
Nodes (26): AgentStreamCard(), AgentStreamCardProps, FloatingWindow(), MessageCards(), Dashboard(), GridTile(), GridTileProps, TileType (+18 more)

### Community 44 - "ui/package.json"
Cohesion: 0.08
Nodes (29): autoprefixer, cronstrue, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, graphology-layout-forceatlas2 (+21 more)

### Community 45 - "._gate_check"
Cohesion: 0.13
Nodes (8): get_user_from_slack(), handle_app_home_opened(), handle_app_mention(), handle_approve(), handle_create_event_modal(), handle_home_create_event(), handle_reject(), on_dm_message()

### Community 46 - "server.js"
Cohesion: 0.08
Nodes (21): hasRegistryCredentials(), { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, ensureEventDocument(), fs, path, stageEventDocument(), fetchEventDocument(), fs (+13 more)

### Community 48 - "handlers_integration.py"
Cohesion: 0.09
Nodes (15): _alert_wrapper_retrigger(), _get_jira_reporter(), handle_ask_release_ai(), handle_comment_jira_issue(), handle_fetch_jira_issue(), handle_greenwave(), handle_notify_user_slack(), handle_retrigger_jenkins_build() (+7 more)

### Community 50 - "observations_mgmt.py"
Cohesion: 0.10
Nodes (10): get_report_client(), render_pdf(), bulk_delete_observations(), BulkDeleteRequest, delete_observation(), export_observations(), generate_observations_report(), rename_observation() (+2 more)

### Community 51 - "CortexGraph.tsx"
Cohesion: 0.15
Nodes (24): graphology, eventColor(), getExecutiveNeurons(), getStructuralEdges(), DEFAULT_TYPE_BUDGET, evictLru(), KNOWLEDGE_RING, KNOWLEDGE_RING_TYPES (+16 more)

### Community 52 - "adf_to_markdown"
Cohesion: 0.12
Nodes (10): _adf_to_text(), _escape_jql_string(), JiraIncidentAdapter, adf_to_markdown(), _apply_marks(), _children(), _render(), _render_list() (+2 more)

### Community 54 - "cognitive_graph.py"
Cohesion: 0.11
Nodes (11): get_pulse_tracker(), dismiss_proposals(), DismissRequest, get_all_shadow_interventions(), get_cognitive_graph(), get_cortex_activity(), get_cortex_status(), get_event_shadow_interventions() (+3 more)

### Community 55 - "NodeInspector.tsx"
Cohesion: 0.13
Nodes (23): getClosedEvents(), ArchitectureEvent, ArgoCDOperation, ArchitectureGraph(), EVENT_LABELS, EventItem(), EventItemProps, healthTone() (+15 more)

### Community 56 - "scheduling/__init__.py"
Cohesion: 0.13
Nodes (11): _do_retrigger(), handle_refresh_github_context(), handle_refresh_gitlab_context(), handle_refresh_kargo_context(), StateWatcherPort, GitHubPrRef, GitLabMrRef, GitLabPipelineRef (+3 more)

### Community 58 - "llm/__init__.py"
Cohesion: 0.16
Nodes (5): FunctionCall, LLMChunk, LLMPort, LLMResponse, TokenUsage

### Community 62 - "dependencies"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 63 - "reconcile.py"
Cohesion: 0.15
Nodes (9): _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers(), main(), _parse_frontmatter() (+1 more)

### Community 64 - "PulseBatch"
Cohesion: 0.11
Nodes (4): PulseBatch, PulsePort, PulseObserver, PulseTracker

### Community 65 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 66 - "claude-guard.js"
Cohesion: 0.14
Nodes (18): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+10 more)

### Community 67 - "http-handler.js"
Cohesion: 0.12
Nodes (18): getRemoteClustersMeta(), setupCLILogins(), setupRegistryCredentials(), { AGENT_CLI, AGENT_MODEL, DEFAULT_WORK_DIR, PORT, BRAIN_HTTP_URL }, { claudeMergeGuard }, { executeCLI }, fs, handleRequest() (+10 more)

### Community 68 - "TokenUtilizationPage.tsx"
Cohesion: 0.16
Nodes (17): recharts, getFlowHistory(), FlowSnapshot, ObservationSeries, FlowHistoryPage(), formatTime(), RANGES, SparkCard() (+9 more)

### Community 71 - "format_event_summary"
Cohesion: 0.11
Nodes (10): build_home_tab_view(), _context_line(), format_event_summary(), format_plan_block(), format_task_card(), format_turn(), resolve_source_emoji(), _section() (+2 more)

### Community 75 - "slack.py"
Cohesion: 0.12
Nodes (6): build_access_denied_home_view(), create_feedback_block(), _md_table_to_text(), _md_to_mrkdwn(), _parse_md_table(), table_block_to_code_block()

### Community 76 - "ArchitectureGraph.tsx"
Cohesion: 0.14
Nodes (16): @dagrejs/dagre, applyDagreLayout(), applyGridLayout(), applyLayout(), ArchitectureGraphInner(), buildGraph(), computeIdHash(), edgeTypes (+8 more)

### Community 79 - "devDependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 80 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 81 - "ServiceNode.tsx"
Cohesion: 0.15
Nodes (13): react-dom, @xyflow/react, HealthStatus, NodeType, AppNodeData, ARGOCD_HEALTH_COLORS, SYNC_ICONS, GENERIC_TAGS (+5 more)

### Community 84 - "get_report"
Cohesion: 0.11
Nodes (6): get_report(), list_reports(), reports_spa_no_slash(), reports_spa_with_slash(), search_reports(), _serve_spa()

### Community 86 - "catalog-skills.js"
Cohesion: 0.15
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 87 - "gemini-sidecar/package.json"
Cohesion: 0.11
Nodes (17): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+9 more)

### Community 88 - "handlers_state.py"
Cohesion: 0.15
Nodes (7): handle_classify_event(), handle_close_event(), handle_request_user_approval(), handle_wait_for_user(), has_unevaluated_close_blocker(), _resolve_domain(), resolve_event_domain()

### Community 90 - "ShiftsPage.tsx"
Cohesion: 0.23
Nodes (16): getCurrentShift(), getShiftDetail(), getShiftsList(), ShiftReportFull, ShiftReportSummary, FailedClusterBadge(), getISOWeek(), getWeekDates() (+8 more)

### Community 98 - "cortex/types.ts"
Cohesion: 0.17
Nodes (14): EventSource, KGServiceEntity, CortexGraphProps, GraphLoaderProps, PulseTimelineProps, CognitiveGraphResponse, CortexHeartbeatMessage, FrictionIndicator (+6 more)

### Community 99 - "CortexDevPage.tsx"
Cohesion: 0.23
Nodes (14): devQueryClient, CortexLiveFeedProps, EventDrillDownProps, MOCK_CORTEX_STATUS, MOCK_EVENT_ID, MOCK_NEURONS, MOCK_PULSE_BATCHES, MOCK_SHADOW (+6 more)

### Community 101 - "generate_map.py"
Cohesion: 0.19
Nodes (6): _enumerate_gates(), _GateInfo, generate_phase_tool_map(), _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 105 - "observations_reporter.py"
Cohesion: 0.21
Nodes (7): _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), _sample_points(), _summarize()

### Community 109 - "EventDrillDown.tsx"
Cohesion: 0.22
Nodes (10): three, getEventPulses(), BrainCore(), CortexDevPage(), EventDrillDown(), FRICTION_COLORS, WHISPER_COLORS, PulseTimeline() (+2 more)

### Community 111 - "._extract_context_flags"
Cohesion: 0.15
Nodes (3): compute_dispatch_backpressure(), ContextFlags, _safe_int_env()

### Community 115 - "._send_turn_to_thread"
Cohesion: 0.19
Nodes (5): extract_tables(), _replace(), get_agent_notification_text(), get_turn_attachment_color(), _md_table_to_block_kit()

### Community 118 - "NeuronInfoPanel.tsx"
Cohesion: 0.24
Nodes (12): KGServiceDetail, asNumber(), asString(), asStringArray(), Badge(), describeNeuron(), Hdr(), NeuronInfoPanel() (+4 more)

### Community 124 - "_sanitize_analysis_text"
Cohesion: 0.18
Nodes (5): _prepare_console_tail(), _redact_match(), _redact_secrets_in_text(), _sanitize_analysis_text(), _sanitize_console_tail()

### Community 125 - "CortexLiveFeed.tsx"
Cohesion: 0.24
Nodes (10): CortexHeartbeat(), CortexHeartbeatProps, ensureKeyframes(), CortexLiveFeed(), FILTER_PILLS, FilterKey, getStoredFilter(), MESSAGE_STYLES (+2 more)

### Community 126 - "is_defer_event_available"
Cohesion: 0.18
Nodes (6): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 127 - "cortex-constants.ts"
Cohesion: 0.18
Nodes (10): AGENTS, DOMAINS, HEMISPHERE_X, NEURON_DESCRIPTIONS, PHASE_SKILL_FOLDERS, PHASE_TOOL_PRIORITY, PHASES, StructuralEdge (+2 more)

### Community 129 - "vite.config.ts"
Cohesion: 0.20
Nodes (5): @tailwindcss/vite, @testing-library/react, vite, @vitejs/plugin-react, vitest

### Community 134 - "entity_extractor.py"
Cohesion: 0.33
Nodes (5): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship

### Community 135 - "_validate_analysis"
Cohesion: 0.22
Nodes (4): _clamp_confidence(), _strip_newlines(), _validate_analysis(), _validate_triage_entry()

### Community 137 - "knowledge_graph_api.py"
Cohesion: 0.31
Nodes (4): get_kg_store(), get_service_detail(), get_stats(), list_services()

### Community 138 - "get_quota_tracker"
Cohesion: 0.22
Nodes (3): get_quota_tracker(), llm_stats(), receive_telemetry()

### Community 153 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 154 - "validate-mutations.sh"
Cohesion: 0.73
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

## Knowledge Gaps
- **13 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+8 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2129 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **123 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `brain.py`, `logging`, `_is_event_closed_or_missing`, `queue.py`, `EventDocument`, `Brain`, `os`, `BrainSkillLoader`, `auth.py`, `.get_graph_data`, `ConversationTurn`, `nightwatcher_tools.py`, `._restage_pending_signal`, `._stage_pending_signal`, `._count_pending`, `.cleanup_stale_services`, `.get_edge_metadata`, `observations_mgmt.py`, `lifespan`, `slack.py`, `LiveAPIAdapter`, `get_report`, `ScheduleCreateRequest`, `DashboardWSAdapter`, `observations_reporter.py`, `ScheduleRepository`, `HeadhunterJira`, `NightwatcherObserver`?**
  _High betweenness centrality (0.107) - this node is a cross-community bridge._
- **Are the 79 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 79 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.011409642988590356 - nodes in this community are weakly interconnected._
- **Why does `Brain` connect `Brain` to `BlackboardState`, `brain.py`, `logging`, `._post_agent_recall`, `EventDocument`, `BrainSkillLoader`, `._run_agent_task`, `ReconcileScheduler`, `ConversationTurn`, `.start_event_loop`, `._process_with_llm`, `PulseBatch`, `._build_contents`, `._close_and_broadcast`, `lifespan`, `slack.py`, `ReflexSearcher`, `QuotaTracker`, `DashboardWSAdapter`, `._extract_context_flags`, `BrainLifecyclePort`, `IdleTimeoutManager`?**
  _High betweenness centrality (0.067) - this node is a cross-community bridge._
- **Are the 20 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Should `brain.py` be split into smaller, more focused modules?**
  _Cohesion score 0.02393034560119652 - nodes in this community are weakly interconnected._