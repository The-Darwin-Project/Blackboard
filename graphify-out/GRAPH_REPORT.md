# Graph Report - Blackboard  (2026-10-26)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 4762 nodes · 10517 edges · 189 communities (97 shown, 92 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 903 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `fe3ba77d`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BlackboardState
- queue.py
- client.ts
- Archivist
- Brain
- dependencies.py
- tool_gates.py
- models.py
- create_adapter
- jenkins_observer.py
- brain.py
- merge-guard.js
- OpsStateContext.tsx
- logging
- AgentRegistry
- nightwatcher_tools.py
- ._run_agent_task
- ReconcileScheduler
- os
- jenkins-mcp.js
- BrainSkillLoader
- App.tsx
- EventSidebar.tsx
- EventChatPanel.tsx
- fetchApi
- TurnBubble.tsx
- TopologyRepository
- EventDocument
- Aligner
- ._process_with_llm
- _BrainToolContext
- GitLabPlatform
- credentials.js
- colors.ts
- ToolContext
- EventRepository
- JenkinsObserver
- cli-executor.js
- JenkinsAdapter
- react
- GitHubPlatform
- AgentClient
- ConversationTurn
- TimeKeeperPage.tsx
- time
- lifespan
- .get_service
- main.py
- DashboardWSAdapter
- ui/package.json
- Headhunter
- SlackChannel
- useCortexData.ts
- ws-client.js
- .list_observations
- EventDrillDown.tsx
- ._build_system_prompt
- KnowledgeGraphStore
- http-handler.js
- server.js
- CortexGraph.tsx
- StateWatcher
- cognitive_graph.py
- update_schedule
- ArgoCDObserver
- json
- ._get_manager
- ._gate_check
- KargoObserver
- GitHubAppAuth
- dependencies
- NeuronInfoPanel.tsx
- VcsPlatformPort
- formatter.py
- compilerOptions
- reconcile.py
- ArchitectureGraph.tsx
- TokenUtilizationPage.tsx
- slack.py
- state/__init__.py
- cli-setup.js
- claude-guard.js
- observations_reporter.py
- ReflexSearcher
- devDependencies
- compilerOptions
- QuotaTracker
- LiveAPIAdapter
- generate_observations_report
- get_report
- gemini-sidecar/package.json
- JiraIncidentAdapter
- ObservationRepository
- InsightsPage.tsx
- ShiftsPage.tsx
- catalog-skills.js
- OIDCKeyAdapter
- .next_turn_number
- SlackAccessGate
- generate_map.py
- KubernetesSpawnHealthAdapter
- IdleTimeoutManager
- EphemeralProvisioner
- EscalationRepository
- cortex/types.ts
- ServiceNode.tsx
- .poll_and_process
- ScheduleRepository
- MultiInstallationManager
- ScheduleCreateRequest
- _resolve_phase
- HeadhunterJira
- TokenMeter
- IncidentAdapterPort
- get_current_shift
- ._github_poll_and_process
- CiContextCard.tsx
- CortexLiveFeed.tsx
- is_defer_event_available
- adf_to_markdown
- _is_event_closed_or_missing
- entity_extractor.py
- has_unevaluated_close_blocker
- knowledge_graph_api.py
- SpawnPollResult
- handle_retrigger_jenkins_build
- SmartsheetMaintainerCache
- .has_reeval_signal
- get_event_document
- AsyncGitHubClient
- GitLabTokenAuth
- TimeKeeperObserver
- CortexRepository
- llm_stats
- _md_table_to_text
- vite.config.ts
- update_notebook_note
- scripts
- validate-mutations.sh
- ._process_message
- ._evaluate_health
- ._cleanup_stale_events
- DispatchMetrics
- incidents.py
- list_failed_stages
- ._wait_for_registration
- format_event_summary
- submit_feedback
- get_notebook
- _patch_enum_fields
- require-results.sh
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
1. `BlackboardState` - 279 edges
2. `Brain` - 148 edges
3. `ConversationTurn` - 122 edges
4. `ToolContext` - 102 edges
5. `GateContext` - 94 edges
6. `EventDocument` - 78 edges
7. `react` - 71 edges
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

## Communities (189 total, 92 thin omitted)

### Community 1 - "queue.py"
Cohesion: 0.04
Nodes (49): get_token_meter(), get_archivist(), get_brain(), aligner_pending_items(), apply_lessons(), approve_event(), close_event_by_user(), CloseRequest (+41 more)

### Community 2 - "client.ts"
Cohesion: 0.03
Nodes (87): @tanstack/react-query, ApiError, deleteNote(), ExtractedCorrection, ExtractedLesson, ExtractionResult, getActiveEvents(), getAlignerPending() (+79 more)

### Community 3 - "Archivist"
Cohesion: 0.04
Nodes (3): Archivist, Pulse, VectorStore

### Community 5 - "dependencies.py"
Cohesion: 0.04
Nodes (24): can_append_message(), can_approve_event(), can_override_domain(), _claims_to_user(), get_user_from_request(), get_user_from_websocket(), _normalize_email(), require_auth() (+16 more)

### Community 6 - "tool_gates.py"
Cohesion: 0.05
Nodes (78): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+70 more)

### Community 7 - "models.py"
Cohesion: 0.04
Nodes (25): AppNode, ChatRequest, ChatResponse, EventInput, EventMetrics, EventStatus, FlowMetricsResponse, FlowSnapshot (+17 more)

### Community 8 - "create_adapter"
Cohesion: 0.05
Nodes (10): ClaudeAdapter, GeminiAdapter, _parse_drain_timeout(), create_adapter(), TokenUsageDict, FunctionCall, LLMChunk, LLMPort (+2 more)

### Community 9 - "jenkins_observer.py"
Cohesion: 0.04
Nodes (19): _sanitize_lesson_text(), _clamp_confidence(), _parse_job_metadata(), _prepare_console_tail(), _redact_build_parameters(), _redact_match(), _redact_secrets_in_text(), _sanitize_analysis_text() (+11 more)

### Community 10 - "brain.py"
Cohesion: 0.05
Nodes (28): _apply_sibling_signature(), build_function_response(), build_single_function_response(), compress_contents(), estimate_msg_tokens(), estimate_tokens(), extract_model_parts(), normalize_response_parts() (+20 more)

### Community 11 - "merge-guard.js"
Cohesion: 0.05
Nodes (69): analyzeString(), analyzeTokens(), API_VALUED, apiTokens(), apiWriteNeedsGuard(), assignName(), bareBranchProtected(), base() (+61 more)

### Community 12 - "OpsStateContext.tsx"
Cohesion: 0.06
Nodes (54): createChatEvent(), getAgents(), getKargoStages(), AgentRegistryEntry, KargoStageStatus, AgentRegistryPanel(), formatConnectedSince(), AgentStreamCard() (+46 more)

### Community 13 - "logging"
Cohesion: 0.05
Nodes (3): _annotation_replace(), _strip_pipeline_annotations(), SpawnStatus

### Community 14 - "AgentRegistry"
Cohesion: 0.05
Nodes (17): AgentConnection, AgentRegistry, agent_websocket_handler(), _heartbeat(), _build_prompt(), _check_security(), consume_wake_task(), _consume() (+9 more)

### Community 15 - "nightwatcher_tools.py"
Cohesion: 0.06
Nodes (27): ShiftIncident, ShiftInvestigation, ShiftReport, NightwatcherObserver, build_manifest_table(), build_report_iteration_prompt(), build_summary_prompt(), build_system_prompt() (+19 more)

### Community 16 - "._run_agent_task"
Cohesion: 0.06
Nodes (8): on_huddle(), on_progress(), on_huddle(), on_progress(), _compute_processed_up_to(), _sanitize_error_text(), _sanitize_override_reason(), get_registry_and_bridge()

### Community 17 - "ReconcileScheduler"
Cohesion: 0.04
Nodes (7): FlowCollector, FairQueue, ReconcileScheduler, Trigger, QueueTrigger, ResyncTrigger, StalenessGuard

### Community 18 - "os"
Cohesion: 0.06
Nodes (17): _get_static_maintainer_emails(), _get_allowed_mention_authors(), _get_static_maintainer_emails(), _safe_int(), dex_proxy(), approve_mission(), dismiss_mission(), _infer_phase() (+9 more)

### Community 19 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 20 - "BrainSkillLoader"
Cohesion: 0.04
Nodes (5): BrainSkillLoader, _SkillCorpus, BrainIntrospectionPort, BrainLifecyclePort, BroadcastPort

### Community 21 - "App.tsx"
Cohesion: 0.06
Nodes (46): oidc-client-ts, react-dom, dismissProposals(), EnhancementProposal, getConfig(), getHandoffReports(), getProposals(), getWSAuthFailureCallback() (+38 more)

### Community 22 - "EventSidebar.tsx"
Cohesion: 0.09
Nodes (49): getHeadhunterPending(), getJiraMissions(), HeadhunterTodo, postJiraAction(), ChatInput(), ChatInputProps, Draft, LastSubmission (+41 more)

### Community 23 - "EventChatPanel.tsx"
Cohesion: 0.07
Nodes (36): ConversationTurn, DeferCountdownBar(), STATUS_COLORS, TICKET_COLORS, TicketNodeComponent(), TicketNodeData, EventChatPanel(), EventChatPanelProps (+28 more)

### Community 24 - "fetchApi"
Cohesion: 0.09
Nodes (48): lucide-react, applyLessons(), correctMemory(), createKnowledge(), createLesson(), deleteKnowledge(), deleteLesson(), extractLessons() (+40 more)

### Community 25 - "TurnBubble.tsx"
Cohesion: 0.08
Nodes (42): @uiw/react-markdown-preview, approveEvent(), closeEvent(), enforceCasualDomain(), getEventReport(), rejectEvent(), submitFeedback(), CollapsibleSection() (+34 more)

### Community 26 - "TopologyRepository"
Cohesion: 0.05
Nodes (8): ArchitectureEvent, EventType, GraphResponse, Service, Snapshot, TopologySnapshot, MetricsRepository, TopologyRepository

### Community 27 - "EventDocument"
Cohesion: 0.04
Nodes (3): _close_unanswered_fc(), ContextFlags, EventDocument

### Community 29 - "._process_with_llm"
Cohesion: 0.04
Nodes (3): _BatchContext, compute_dispatch_backpressure(), _safe_int_env()

### Community 32 - "credentials.js"
Cohesion: 0.13
Nodes (44): resolveCommand(), writeAgyMcpServer(), writeClaudeMcpServer(), buildArgoCDMcpConfig(), createAppJWT(), discoverAndGenerateTokens(), _discoverAndGenerateTokensInner(), discoverInstallations() (+36 more)

### Community 33 - "colors.ts"
Cohesion: 0.11
Nodes (34): react-router-dom, getReport(), getReports(), ReportFull, ReportMeta, CompactCardStrip(), EventHistory(), TimeRange (+26 more)

### Community 34 - "ToolContext"
Cohesion: 0.08
Nodes (10): handle_select_agent(), handle_classify_event(), handle_close_event(), handle_defer_event(), handle_hold_watch(), handle_request_user_approval(), handle_wait_for_agent(), handle_wait_for_jarvis() (+2 more)

### Community 37 - "cli-executor.js"
Cohesion: 0.09
Nodes (35): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS }, buildCLICommand(), CLAUDE_JSON_PATH, cp, executeCLI(), executeCLIStreaming(), FALLBACK_MODEL, fs (+27 more)

### Community 38 - "JenkinsAdapter"
Cohesion: 0.06
Nodes (6): BuildDetails, JenkinsAdapter, JenkinsPlatformPort, JobResult, JobRunState, ViewScanResult

### Community 39 - "react"
Cohesion: 0.09
Nodes (33): react, getClosedEvents(), getEventDocument(), getEvents(), ArchitectureEvent, ArgoCDOperation, ActivityStream(), EVENT_LABELS (+25 more)

### Community 41 - "AgentClient"
Cohesion: 0.07
Nodes (4): Architect, AgentClient, Developer, SysAdmin

### Community 42 - "ConversationTurn"
Cohesion: 0.13
Nodes (20): emit_tool_result(), _safe_int(), handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_recall_pruned_turns(), handle_fetch_jira_issue(), handle_greenwave() (+12 more)

### Community 43 - "TimeKeeperPage.tsx"
Cohesion: 0.12
Nodes (24): createSchedule(), deleteSchedule(), getSchedules(), refineInstructions(), ScheduleCreatePayload, ScheduleItem, toggleSchedule(), updateSchedule() (+16 more)

### Community 44 - "time"
Cohesion: 0.11
Nodes (15): _get_jira_reporter(), handle_ask_release_ai(), handle_comment_jira_issue(), handle_refresh_github_context(), handle_refresh_gitlab_context(), handle_refresh_kargo_context(), _is_darwin_reentrant_caller(), _resolve_maintainer_enum() (+7 more)

### Community 45 - "lifespan"
Cohesion: 0.06
Nodes (8): set_agents(), set_archivist(), set_argocd_observer(), set_blackboard(), set_brain(), set_kargo_observer(), set_registry_and_bridge(), lifespan()

### Community 46 - ".get_service"
Cohesion: 0.07
Nodes (5): get_graph_data(), get_mermaid_diagram(), get_service_details(), get_topology(), list_services()

### Community 47 - "main.py"
Cohesion: 0.08
Nodes (14): set_kg_store(), set_pulse_tracker(), agent_ws_endpoint(), api_info(), get_config(), get_event_flow(), get_flow_history(), get_flow_metrics() (+6 more)

### Community 48 - "DashboardWSAdapter"
Cohesion: 0.09
Nodes (5): DashboardWSAdapter, prompt_display_name(), ChatEventRequest, ChatEventResponse, create_chat_event()

### Community 49 - "ui/package.json"
Cohesion: 0.07
Nodes (30): autoprefixer, cronstrue, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, graphology-layout-forceatlas2 (+22 more)

### Community 52 - "useCortexData.ts"
Cohesion: 0.16
Nodes (28): getCognitiveGraph(), getCortexActivity(), getKGServiceDetail(), getKGServices(), getKGStats(), getKnowledgeById(), getLessonById(), getMemory() (+20 more)

### Community 53 - "ws-client.js"
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

### Community 54 - ".list_observations"
Cohesion: 0.07
Nodes (5): get_all_journal(), get_service_journal(), get_event_observations(), get_global_observations(), export_observations()

### Community 55 - "EventDrillDown.tsx"
Cohesion: 0.13
Nodes (23): three, getEventPulses(), BrainCore(), CortexDevPage(), devQueryClient, CortexLiveFeedProps, EventDrillDown(), EventDrillDownProps (+15 more)

### Community 56 - "._build_system_prompt"
Cohesion: 0.07
Nodes (3): _init_tool_names(), _strip_tool_names(), _wrap_section()

### Community 57 - "KnowledgeGraphStore"
Cohesion: 0.15
Nodes (4): _acquire(), KnowledgeGraphStore, _sanitize(), _with_timeout()

### Community 58 - "http-handler.js"
Cohesion: 0.08
Nodes (21): ROLE_TIMEOUTS, SUPPORTED_AGENT_CLIS, getRemoteClustersMeta(), { AGENT_CLI, AGENT_MODEL, DEFAULT_WORK_DIR, PORT, BRAIN_HTTP_URL }, { claudeMergeGuard }, { executeCLI }, fs, {
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
} (+13 more)

### Community 59 - "server.js"
Cohesion: 0.09
Nodes (17): hasRegistryCredentials(), { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, fs, path, stageEventDocument(), fetchEventDocument(), fs, { handleRequest } (+9 more)

### Community 60 - "CortexGraph.tsx"
Cohesion: 0.14
Nodes (25): graphology, eventColor(), getExecutiveNeurons(), getStructuralEdges(), DEFAULT_TYPE_BUDGET, evictLru(), KNOWLEDGE_RING, KNOWLEDGE_RING_TYPES (+17 more)

### Community 61 - "StateWatcher"
Cohesion: 0.10
Nodes (3): _QueueEntry, StateWatcher, _Subscription

### Community 62 - "cognitive_graph.py"
Cohesion: 0.11
Nodes (11): get_pulse_tracker(), dismiss_proposals(), DismissRequest, get_all_shadow_interventions(), get_cognitive_graph(), get_cortex_activity(), get_cortex_status(), get_event_shadow_interventions() (+3 more)

### Community 63 - "update_schedule"
Cohesion: 0.08
Nodes (5): delete_schedule(), get_schedule(), list_schedules(), toggle_schedule(), update_schedule()

### Community 65 - "json"
Cohesion: 0.12
Nodes (8): _format_graph_context(), get_graph_context(), _parse_props(), _sanitize(), translate_to_lookups(), _decode_cursor(), _encode_cursor(), _load_name_mapping()

### Community 67 - "._gate_check"
Cohesion: 0.16
Nodes (8): get_user_from_slack(), handle_app_home_opened(), handle_app_mention(), handle_approve(), handle_darwin_command(), handle_home_create_event(), handle_reject(), on_dm_message()

### Community 69 - "GitHubAppAuth"
Cohesion: 0.11
Nodes (3): _find_pem_file(), get_github_auth(), GitHubAppAuth

### Community 70 - "dependencies"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 71 - "NeuronInfoPanel.tsx"
Cohesion: 0.11
Nodes (22): KGServiceDetail, AGENTS, DOMAINS, HEMISPHERE_X, NEURON_DESCRIPTIONS, PHASE_SKILL_FOLDERS, PHASE_TOOL_PRIORITY, PHASES (+14 more)

### Community 73 - "formatter.py"
Cohesion: 0.13
Nodes (10): build_access_denied_home_view(), build_home_tab_view(), _context_line(), create_feedback_block(), format_plan_block(), format_task_card(), format_turn(), resolve_source_emoji() (+2 more)

### Community 74 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 75 - "reconcile.py"
Cohesion: 0.16
Nodes (9): _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers(), main(), _parse_frontmatter() (+1 more)

### Community 76 - "ArchitectureGraph.tsx"
Cohesion: 0.14
Nodes (18): @dagrejs/dagre, @xyflow/react, applyDagreLayout(), applyGridLayout(), applyLayout(), ArchitectureGraph(), ArchitectureGraphInner(), buildGraph() (+10 more)

### Community 77 - "TokenUtilizationPage.tsx"
Cohesion: 0.16
Nodes (17): recharts, getFlowHistory(), FlowSnapshot, ObservationSeries, FlowHistoryPage(), formatTime(), RANGES, SparkCard() (+9 more)

### Community 78 - "slack.py"
Cohesion: 0.12
Nodes (6): extract_tables(), _replace(), get_agent_notification_text(), get_turn_attachment_color(), _md_table_to_block_kit(), table_block_to_code_block()

### Community 79 - "state/__init__.py"
Cohesion: 0.12
Nodes (3): close_redis(), get_redis(), RedisClient

### Community 80 - "cli-setup.js"
Cohesion: 0.13
Nodes (19): { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync }, filterSkillsByMode() (+11 more)

### Community 81 - "claude-guard.js"
Cohesion: 0.14
Nodes (16): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+8 more)

### Community 82 - "observations_reporter.py"
Cohesion: 0.15
Nodes (8): _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), _sample_points(), _summarize(), download_skill_md()

### Community 84 - "devDependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 85 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 86 - "QuotaTracker"
Cohesion: 0.12
Nodes (3): get_quota_tracker(), QuotaExhaustedError, QuotaTracker

### Community 88 - "generate_observations_report"
Cohesion: 0.11
Nodes (8): render_pdf(), bulk_delete_observations(), BulkDeleteRequest, delete_observation(), generate_observations_report(), rename_observation(), RenameRequest, ReportRequest

### Community 89 - "get_report"
Cohesion: 0.11
Nodes (6): get_report(), list_reports(), reports_spa_no_slash(), reports_spa_with_slash(), search_reports(), _serve_spa()

### Community 90 - "gemini-sidecar/package.json"
Cohesion: 0.11
Nodes (17): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+9 more)

### Community 93 - "InsightsPage.tsx"
Cohesion: 0.23
Nodes (15): bulkDeleteObservations(), deleteObservation(), exportObservations(), generateObservationsReport(), getEventObservations(), getGlobalObservations(), renameObservation(), ObservationsResponse (+7 more)

### Community 94 - "ShiftsPage.tsx"
Cohesion: 0.23
Nodes (16): getCurrentShift(), getShiftDetail(), getShiftsList(), ShiftReportFull, ShiftReportSummary, FailedClusterBadge(), getISOWeek(), getWeekDates() (+8 more)

### Community 95 - "catalog-skills.js"
Cohesion: 0.16
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 97 - ".next_turn_number"
Cohesion: 0.21
Nodes (8): handle_message_agent(), handle_reply_to_agent(), handle_report_incident(), handle_notify_gitlab_result(), handle_notify_user_slack(), handle_search_open_incidents(), handle_respond_to_jarvis(), build_event_report_md()

### Community 100 - "generate_map.py"
Cohesion: 0.19
Nodes (6): _enumerate_gates(), _GateInfo, generate_phase_tool_map(), _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 105 - "cortex/types.ts"
Cohesion: 0.19
Nodes (13): EventSource, KGServiceEntity, CortexGraphProps, GraphLoaderProps, PulseTimelineProps, CognitiveGraphResponse, CortexHeartbeatMessage, FrictionIndicator (+5 more)

### Community 106 - "ServiceNode.tsx"
Cohesion: 0.20
Nodes (11): HealthStatus, NodeType, AppNodeData, ARGOCD_HEALTH_COLORS, SYNC_ICONS, GENERIC_TAGS, HEALTH_COLORS, NODE_ICONS (+3 more)

### Community 111 - "_resolve_phase"
Cohesion: 0.19
Nodes (5): handle_re_trigger_aligner(), handle_set_phase(), handle_wait_for_verification(), resolve_event_domain(), _resolve_phase()

### Community 114 - "IncidentAdapterPort"
Cohesion: 0.15
Nodes (3): IdleTimeoutPort, IncidentAdapterPort, StateWatcherPort

### Community 115 - "get_current_shift"
Cohesion: 0.15
Nodes (3): get_current_shift(), get_shift_detail(), list_shifts()

### Community 120 - "CiContextCard.tsx"
Cohesion: 0.29
Nodes (10): CiContext, CiContextCard(), CiContextCardProps, ConsoleTailBlock(), FailedJobRow(), annotationReplacer(), PIPELINE_ANNOTATION_RE, REDACTION_TRIGGER_KEYWORDS (+2 more)

### Community 121 - "CortexLiveFeed.tsx"
Cohesion: 0.24
Nodes (10): CortexHeartbeat(), CortexHeartbeatProps, ensureKeyframes(), CortexLiveFeed(), FILTER_PILLS, FilterKey, getStoredFilter(), MESSAGE_STYLES (+2 more)

### Community 122 - "is_defer_event_available"
Cohesion: 0.18
Nodes (6): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 123 - "adf_to_markdown"
Cohesion: 0.40
Nodes (8): _adf_to_text(), adf_to_markdown(), _apply_marks(), _children(), _render(), _render_list(), _render_list_item(), _render_table_like()

### Community 127 - "entity_extractor.py"
Cohesion: 0.33
Nodes (5): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship

### Community 128 - "has_unevaluated_close_blocker"
Cohesion: 0.20
Nodes (4): has_unevaluated_close_blocker(), _pred_jarvis_response(), _pred_unevaluated_close(), is_jarvis_acknowledgment()

### Community 129 - "knowledge_graph_api.py"
Cohesion: 0.31
Nodes (4): get_kg_store(), get_service_detail(), get_stats(), list_services()

### Community 131 - "handle_retrigger_jenkins_build"
Cohesion: 0.22
Nodes (4): _alert_wrapper_retrigger(), _do_retrigger(), handle_retrigger_jenkins_build(), jenkins_retrigger_cooldown_key()

### Community 145 - "_md_table_to_text"
Cohesion: 0.29
Nodes (3): _md_table_to_text(), _md_to_mrkdwn(), _parse_md_table()

### Community 146 - "vite.config.ts"
Cohesion: 0.29
Nodes (4): @tailwindcss/vite, vite, @vitejs/plugin-react, vitest

### Community 149 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 150 - "validate-mutations.sh"
Cohesion: 0.73
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

## Knowledge Gaps
- **14 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+9 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2090 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **92 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `queue.py`, `Brain`, `dependencies.py`, `get_event_document`, `models.py`, `jenkins_observer.py`, `brain.py`, `logging`, `AgentRegistry`, `nightwatcher_tools.py`, `os`, `BrainSkillLoader`, `update_notebook_note`, `TopologyRepository`, `EventDocument`, `submit_feedback`, `get_notebook`, `EventRepository`, `ConversationTurn`, `lifespan`, `.get_service`, `main.py`, `DashboardWSAdapter`, `.list_observations`, `update_schedule`, `VcsPlatformPort`, `slack.py`, `state/__init__.py`, `observations_reporter.py`, `LiveAPIAdapter`, `generate_observations_report`, `get_report`, `ScheduleRepository`, `_resolve_phase`, `HeadhunterJira`, `get_current_shift`, `_is_event_closed_or_missing`?**
  _High betweenness centrality (0.121) - this node is a cross-community bridge._
- **Are the 78 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 78 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _14 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.014208721215090642 - nodes in this community are weakly interconnected._
- **Why does `Brain` connect `Brain` to `BlackboardState`, `Archivist`, `dependencies.py`, `models.py`, `jenkins_observer.py`, `brain.py`, `AgentRegistry`, `._run_agent_task`, `ReconcileScheduler`, `BrainSkillLoader`, `._cleanup_stale_events`, `TopologyRepository`, `EventDocument`, `._process_with_llm`, `.clear_jarvis_wait`, `ConversationTurn`, `lifespan`, `main.py`, `DashboardWSAdapter`, `._build_system_prompt`, `StateWatcher`, `slack.py`, `ReflexSearcher`, `QuotaTracker`, `IdleTimeoutManager`, `._execute_function_call`?**
  _High betweenness centrality (0.071) - this node is a cross-community bridge._
- **Are the 20 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Should `queue.py` be split into smaller, more focused modules?**
  _Cohesion score 0.03696788648244959 - nodes in this community are weakly interconnected._