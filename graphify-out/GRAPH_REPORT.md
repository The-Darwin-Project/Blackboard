# Graph Report - BlackBoard  (2026-10-25)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 4751 nodes · 10472 edges · 208 communities (94 shown, 114 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 902 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `162109cb`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BlackboardState
- brain.py
- EventDocument
- queue.py
- client.ts
- useCortexData.ts
- Archivist
- Brain
- tool_gates.py
- AgentRegistry
- merge-guard.js
- nightwatcher_tools.py
- auth.py
- colors.ts
- .get_graph_data
- jenkins-mcp.js
- SlackChannel
- EventChatPanel.tsx
- EventSidebar.tsx
- react
- App.tsx
- jenkins_observer.py
- slack.py
- OpsStateContext.tsx
- Aligner
- ReconcileScheduler
- ephemeral_provisioner.py
- ._run_agent_task
- _BrainToolContext
- GitLabPlatform
- KnowledgeGraphStore
- credentials.js
- httpx
- EventRepository
- ActiveStreamsContext.tsx
- cli-executor.js
- JenkinsAdapter
- ._process_with_llm
- JenkinsObserver
- GitHubPlatform
- ui/package.json
- TurnBubble.tsx
- AgentClient
- ToolContext
- ArchitectureGraph.tsx
- handlers_integration.py
- ConversationTurn
- TimeKeeperPage.tsx
- ScheduleRepository
- lifespan
- Headhunter
- observations_mgmt.py
- main.py
- ws-client.js
- dependencies.py
- GeminiAdapter
- http-handler.js
- server.js
- LiveAPIAdapter
- StateWatcher
- CortexGraph.tsx
- adf_to_markdown
- ._close_and_broadcast
- ArgoCDObserver
- llm/__init__.py
- BrainSkillLoader
- ._get_manager
- KargoObserver
- TopologyRepository
- dependencies
- NodeInspector.tsx
- reconcile.py
- IdleTimeoutManager
- compilerOptions
- scheduling/__init__.py
- state/__init__.py
- GitHubAppAuth
- cli-setup.js
- VcsPlatformPort
- PulseBatch
- claude-guard.js
- ._build_system_prompt
- ReflexSearcher
- context_parts.py
- EphemeralProvisioner
- devDependencies
- compilerOptions
- DashboardWSAdapter
- get_report
- gemini-sidecar/package.json
- ._connect
- ObservationRepository
- ShiftsPage.tsx
- QuotaTracker
- catalog-skills.js
- OIDCKeyAdapter
- ClaudeAdapter
- handle_classify_event
- .fetch_context
- FairQueue
- SlackAccessGate
- generate_map.py
- ._discover
- EscalationRepository
- .append_and_broadcast
- .poll_and_process
- MultiInstallationManager
- .scroll
- ._extract_context_flags
- HeadhunterJira
- JarvisMemoryPage.tsx
- ._idle_watchdog
- ._cleanup_session_state
- .run
- ._github_poll_and_process
- is_defer_event_available
- cortex-constants.ts
- NeuronInfoPanel.tsx
- entity_extractor.py
- SmartsheetMaintainerCache
- .has_reeval_signal
- MetricsRepository
- AsyncGitHubClient
- GitLabTokenAuth
- .analyze_and_comment
- TimeKeeperObserver
- CortexRepository
- .extract_gitlab_state_key
- scripts
- validate-mutations.sh
- ._process_message
- .send_pulse
- ._get
- ._run_brain_plan
- ._jql_search
- submit_feedback
- ._count_pending
- .__init__
- .extract_github_state_key
- list_incidents
- require-results.sh
- .next_turn_number
- tsconfig.json
- gh-wrapper.sh
- git-credential-darwin
- check-inbox.sh
- cluster-context.sh
- sendResults.sh
- .on_meta_event_closed
- .receive_brain_response
- _patch_enum_fields
- GateDefinition
- _pred_dispatch_defer
- _pred_hard_strip_defer
- _pred_jarvis_wait
- _pred_obs_plateau
- memory/__init__.py
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

## Communities (208 total, 114 thin omitted)

### Community 1 - "brain.py"
Cohesion: 0.04
Nodes (12): _heartbeat(), _sanitize_lesson_text(), _check_security(), _safe_int(), safe_execution(), wrapper(), SecurityError, PulseContext (+4 more)

### Community 2 - "EventDocument"
Cohesion: 0.03
Nodes (30): get_blackboard(), AppNode, ChatRequest, ChatResponse, EventInput, EventMetrics, EventStatus, EventType (+22 more)

### Community 3 - "queue.py"
Cohesion: 0.04
Nodes (4): Archivist, _decode_cursor(), _encode_cursor(), VectorStore

### Community 4 - "client.ts"
Cohesion: 0.04
Nodes (78): ApiError, bulkDeleteObservations(), deleteObservation(), exportObservations(), ExtractedCorrection, ExtractedLesson, ExtractionResult, generateObservationsReport() (+70 more)

### Community 5 - "useCortexData.ts"
Cohesion: 0.04
Nodes (41): get_archivist(), get_brain(), aligner_pending_items(), apply_lessons(), approve_event(), close_event_by_user(), CloseRequest, correct_memory() (+33 more)

### Community 6 - "Archivist"
Cohesion: 0.05
Nodes (22): _get_static_maintainer_emails(), _get_allowed_mention_authors(), _get_static_maintainer_emails(), _safe_int(), create_adapter(), record_token_usage(), RefineRequest, RefineResponse (+14 more)

### Community 7 - "Brain"
Cohesion: 0.05
Nodes (78): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+70 more)

### Community 8 - "tool_gates.py"
Cohesion: 0.04
Nodes (30): _is_event_closed_or_missing(), _apply_sibling_signature(), build_function_response(), build_single_function_response(), compress_contents(), estimate_msg_tokens(), estimate_tokens(), extract_model_parts() (+22 more)

### Community 9 - "AgentRegistry"
Cohesion: 0.06
Nodes (55): createChatEvent(), getActiveEvents(), getAlignerPending(), getEventDocument(), getJenkinsPending(), getKargoStages(), getWaitingApprovalEvents(), EventDocument (+47 more)

### Community 10 - "merge-guard.js"
Cohesion: 0.05
Nodes (69): analyzeString(), analyzeTokens(), API_VALUED, apiTokens(), apiWriteNeedsGuard(), assignName(), bareBranchProtected(), base() (+61 more)

### Community 12 - "auth.py"
Cohesion: 0.07
Nodes (56): lucide-react, react, applyLessons(), correctMemory(), createKnowledge(), createLesson(), deleteKnowledge(), deleteLesson() (+48 more)

### Community 13 - "colors.ts"
Cohesion: 0.05
Nodes (10): ClaudeAdapter, _parse_drain_timeout(), get_token_meter(), TokenMeter, TokenUsageDict, FunctionCall, LLMChunk, LLMPort (+2 more)

### Community 14 - ".get_graph_data"
Cohesion: 0.07
Nodes (49): @uiw/react-markdown-preview, approveEvent(), closeEvent(), enforceCasualDomain(), getEventReport(), rejectEvent(), submitFeedback(), CiContext (+41 more)

### Community 15 - "jenkins-mcp.js"
Cohesion: 0.04
Nodes (22): set_oidc_adapter(), get_aligner(), get_architect(), get_argocd_observer(), get_developer(), get_kargo_observer(), get_kg_store(), get_report_client() (+14 more)

### Community 16 - "SlackChannel"
Cohesion: 0.06
Nodes (8): on_huddle(), on_progress(), on_huddle(), on_progress(), _compute_processed_up_to(), _sanitize_error_text(), _sanitize_override_reason(), get_registry_and_bridge()

### Community 17 - "EventChatPanel.tsx"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 18 - "EventSidebar.tsx"
Cohesion: 0.06
Nodes (47): oidc-client-ts, react-dom, dismissProposals(), EnhancementProposal, getConfig(), getHandoffReports(), getProposals(), getWSAuthFailureCallback() (+39 more)

### Community 19 - "react"
Cohesion: 0.05
Nodes (4): BrainSkillLoader, _SkillCorpus, _wrap_section(), BrainIntrospectionPort

### Community 20 - "App.tsx"
Cohesion: 0.08
Nodes (43): react-router-dom, @tanstack/react-table, getReport(), getReports(), ReportFull, ReportMeta, SubjectType, CompactCardStrip() (+35 more)

### Community 22 - "slack.py"
Cohesion: 0.08
Nodes (33): getJiraMissions(), postJiraAction(), JenkinsPendingItem, JiraMission, ContextMenu(), ContextMenuItem, ContextMenuProps, EventSidebar() (+25 more)

### Community 23 - "OpsStateContext.tsx"
Cohesion: 0.07
Nodes (19): build_access_denied_home_view(), build_home_tab_view(), _context_line(), create_feedback_block(), extract_tables(), _replace(), format_plan_block(), format_task_card() (+11 more)

### Community 28 - "_BrainToolContext"
Cohesion: 0.13
Nodes (44): resolveCommand(), writeAgyMcpServer(), writeClaudeMcpServer(), buildArgoCDMcpConfig(), createAppJWT(), discoverAndGenerateTokens(), _discoverAndGenerateTokensInner(), discoverInstallations() (+36 more)

### Community 29 - "GitLabPlatform"
Cohesion: 0.06
Nodes (6): Service, get_event_document(), get_mermaid_diagram(), get_service_details(), get_topology(), list_services()

### Community 30 - "KnowledgeGraphStore"
Cohesion: 0.09
Nodes (35): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS }, buildCLICommand(), CLAUDE_JSON_PATH, cp, executeCLI(), executeCLIStreaming(), FALLBACK_MODEL, fs (+27 more)

### Community 31 - "credentials.js"
Cohesion: 0.06
Nodes (6): BuildDetails, JenkinsAdapter, JenkinsPlatformPort, JobResult, JobRunState, ViewScanResult

### Community 32 - "httpx"
Cohesion: 0.09
Nodes (9): handle_message_agent(), handle_reply_to_agent(), handle_select_agent(), handle_defer_event(), handle_hold_watch(), handle_respond_to_jarvis(), handle_wait_for_agent(), handle_wait_for_jarvis() (+1 more)

### Community 33 - "EventRepository"
Cohesion: 0.07
Nodes (4): Architect, AgentClient, Developer, SysAdmin

### Community 34 - "ActiveStreamsContext.tsx"
Cohesion: 0.09
Nodes (9): _format_graph_context(), get_graph_context(), _parse_props(), _sanitize(), translate_to_lookups(), _acquire(), KnowledgeGraphStore, _sanitize() (+1 more)

### Community 36 - "JenkinsAdapter"
Cohesion: 0.10
Nodes (31): getFlowMetrics(), FlowMetrics, AgentStreamCard(), AgentStreamCardProps, FloatingWindow(), MessageCards(), Dashboard(), FlowHealthWidget() (+23 more)

### Community 38 - "JenkinsObserver"
Cohesion: 0.16
Nodes (28): emit_tool_result(), handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_recall_pruned_turns(), handle_ask_release_ai(), handle_fetch_jira_issue(), handle_greenwave() (+20 more)

### Community 40 - "ui/package.json"
Cohesion: 0.08
Nodes (14): _annotation_replace(), _strip_pipeline_annotations(), _clamp_confidence(), _env_flag(), _parse_job_metadata(), _prepare_console_tail(), _redact_build_parameters(), _redact_match() (+6 more)

### Community 41 - "TurnBubble.tsx"
Cohesion: 0.07
Nodes (14): _patch_enum_fields(), set_incident_options(), agent_ws_endpoint(), api_info(), get_config(), get_event_flow(), get_flow_history(), get_flow_metrics() (+6 more)

### Community 42 - "AgentClient"
Cohesion: 0.12
Nodes (24): createSchedule(), deleteSchedule(), getSchedules(), refineInstructions(), ScheduleCreatePayload, ScheduleItem, toggleSchedule(), updateSchedule() (+16 more)

### Community 43 - "ToolContext"
Cohesion: 0.11
Nodes (15): _do_retrigger(), _get_jira_reporter(), handle_comment_jira_issue(), handle_refresh_github_context(), handle_refresh_gitlab_context(), handle_refresh_kargo_context(), _is_darwin_reentrant_caller(), jenkins_retrigger_cooldown_key() (+7 more)

### Community 44 - "ArchitectureGraph.tsx"
Cohesion: 0.09
Nodes (12): can_append_message(), can_approve_event(), can_override_domain(), _claims_to_user(), get_user_from_request(), get_user_from_websocket(), _normalize_email(), require_auth() (+4 more)

### Community 45 - "handlers_integration.py"
Cohesion: 0.12
Nodes (16): ShiftIncident, ShiftInvestigation, build_summary_tool(), execute_tool(), get_phase_tools(), _handle_consult_deep_memory(), _handle_declare_clusters(), _handle_dispatch_investigation() (+8 more)

### Community 46 - "ConversationTurn"
Cohesion: 0.11
Nodes (10): get_user_from_slack(), format_event_summary(), handle_app_home_opened(), handle_app_mention(), handle_approve(), handle_create_event_modal(), handle_darwin_command(), handle_home_create_event() (+2 more)

### Community 48 - "ScheduleRepository"
Cohesion: 0.10
Nodes (27): getClosedEvents(), getEvents(), ActiveEvent, ArchitectureEvent, ArgoCDOperation, ActivityStream(), ArchitectureGraph(), EVENT_LABELS (+19 more)

### Community 49 - "lifespan"
Cohesion: 0.08
Nodes (29): autoprefixer, cronstrue, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, graphology-layout-forceatlas2 (+21 more)

### Community 50 - "Headhunter"
Cohesion: 0.11
Nodes (25): three, getEventPulses(), BrainCore(), CortexDevPage(), CortexHeartbeat(), CortexHeartbeatProps, ensureKeyframes(), CortexLiveFeed() (+17 more)

### Community 51 - "observations_mgmt.py"
Cohesion: 0.16
Nodes (28): getCognitiveGraph(), getCortexActivity(), getKGServiceDetail(), getKGServices(), getKGStats(), getKnowledgeById(), getLessonById(), getMemory() (+20 more)

### Community 52 - "main.py"
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

### Community 53 - "ws-client.js"
Cohesion: 0.11
Nodes (13): _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), render_pdf(), _sample_points(), _summarize() (+5 more)

### Community 54 - "dependencies.py"
Cohesion: 0.10
Nodes (9): _build_prompt(), consume_wake_task(), _consume(), _dispatch_timeout_s(), dispatch_to_agent(), _consume_queue(), _sanitize_stdout(), send_cancel() (+1 more)

### Community 56 - "http-handler.js"
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

### Community 57 - "server.js"
Cohesion: 0.09
Nodes (17): hasRegistryCredentials(), { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, fs, path, stageEventDocument(), fetchEventDocument(), fs, { handleRequest } (+9 more)

### Community 58 - "LiveAPIAdapter"
Cohesion: 0.14
Nodes (25): graphology, eventColor(), getExecutiveNeurons(), getStructuralEdges(), DEFAULT_TYPE_BUDGET, evictLru(), KNOWLEDGE_RING, KNOWLEDGE_RING_TYPES (+17 more)

### Community 59 - "StateWatcher"
Cohesion: 0.09
Nodes (5): Pulse, PulseBatch, PulsePort, PulseObserver, PulseTracker

### Community 61 - "adf_to_markdown"
Cohesion: 0.09
Nodes (5): get_quota_tracker(), QuotaExhaustedError, QuotaTracker, llm_stats(), receive_telemetry()

### Community 63 - "ArgoCDObserver"
Cohesion: 0.11
Nodes (11): get_pulse_tracker(), dismiss_proposals(), DismissRequest, get_all_shadow_interventions(), get_cognitive_graph(), get_cortex_activity(), get_cortex_status(), get_event_shadow_interventions() (+3 more)

### Community 64 - "llm/__init__.py"
Cohesion: 0.15
Nodes (21): @tanstack/react-query, getCurrentShift(), getIncidents(), getShiftDetail(), getShiftsList(), Incident, ShiftReportFull, ShiftReportSummary (+13 more)

### Community 66 - "._get_manager"
Cohesion: 0.08
Nodes (5): create_schedule(), delete_schedule(), get_schedule(), list_schedules(), toggle_schedule()

### Community 67 - "KargoObserver"
Cohesion: 0.14
Nodes (3): DashboardWSAdapter, prompt_display_name(), resolve_approval_identity()

### Community 71 - "reconcile.py"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 72 - "IdleTimeoutManager"
Cohesion: 0.15
Nodes (9): _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers(), main(), _parse_frontmatter() (+1 more)

### Community 73 - "compilerOptions"
Cohesion: 0.11
Nodes (3): _QueueEntry, StateWatcher, _Subscription

### Community 74 - "scheduling/__init__.py"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 75 - "state/__init__.py"
Cohesion: 0.16
Nodes (17): recharts, getFlowHistory(), FlowSnapshot, ObservationSeries, formatTime(), RANGES, SparkCard(), SparkCardProps (+9 more)

### Community 76 - "GitHubAppAuth"
Cohesion: 0.12
Nodes (3): AgentConnection, AgentRegistry, agent_websocket_handler()

### Community 77 - "cli-setup.js"
Cohesion: 0.12
Nodes (3): close_redis(), get_redis(), RedisClient

### Community 79 - "PulseBatch"
Cohesion: 0.13
Nodes (19): { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync }, filterSkillsByMode() (+11 more)

### Community 80 - "claude-guard.js"
Cohesion: 0.14
Nodes (17): @dagrejs/dagre, @xyflow/react, applyDagreLayout(), applyGridLayout(), applyLayout(), ArchitectureGraphInner(), buildGraph(), computeIdHash() (+9 more)

### Community 83 - "context_parts.py"
Cohesion: 0.17
Nodes (16): ConversationTurn, DeferCountdownBar(), STATUS_COLORS, TICKET_COLORS, TicketNodeComponent(), TicketNodeData, PlanProgressProps, PlanStep (+8 more)

### Community 84 - "EphemeralProvisioner"
Cohesion: 0.13
Nodes (19): KGServiceDetail, AGENTS, DOMAINS, HEMISPHERE_X, NEURON_DESCRIPTIONS, PHASE_SKILL_FOLDERS, PHASE_TOOL_PRIORITY, PHASES (+11 more)

### Community 85 - "devDependencies"
Cohesion: 0.14
Nodes (16): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+8 more)

### Community 87 - "DashboardWSAdapter"
Cohesion: 0.10
Nodes (6): _defer_timeline_fields(), _has_active_subscription(), list_active_events(), list_closed_events(), list_waiting_approval_events(), _serialize_evidence()

### Community 88 - "get_report"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 89 - "gemini-sidecar/package.json"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 91 - "ObservationRepository"
Cohesion: 0.13
Nodes (3): ArchitectureEvent, list_events(), MetricsRepository

### Community 92 - "ShiftsPage.tsx"
Cohesion: 0.16
Nodes (4): ShiftReport, NightwatcherObserver, build_extend_tool(), build_report_tool()

### Community 93 - "QuotaTracker"
Cohesion: 0.11
Nodes (6): get_report(), list_reports(), reports_spa_no_slash(), reports_spa_with_slash(), search_reports(), _serve_spa()

### Community 94 - "catalog-skills.js"
Cohesion: 0.11
Nodes (17): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+9 more)

### Community 95 - "OIDCKeyAdapter"
Cohesion: 0.15
Nodes (3): _adf_to_text(), _escape_jql_string(), JiraIncidentAdapter

### Community 98 - ".fetch_context"
Cohesion: 0.16
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 99 - "FairQueue"
Cohesion: 0.12
Nodes (4): handle_request_user_approval(), IdleTimeoutPort, IncidentAdapterPort, StateWatcherPort

### Community 100 - "SlackAccessGate"
Cohesion: 0.13
Nodes (3): get_event_observations(), get_global_observations(), export_observations()

### Community 103 - "._discover"
Cohesion: 0.15
Nodes (7): build_manifest_table(), build_report_iteration_prompt(), build_summary_prompt(), build_system_prompt(), extract_event_links(), extract_full_links(), _normalize_gitlab_host()

### Community 104 - "EscalationRepository"
Cohesion: 0.19
Nodes (6): _enumerate_gates(), _GateInfo, generate_phase_tool_map(), _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 107 - "MultiInstallationManager"
Cohesion: 0.13
Nodes (3): get_all_journal(), get_service_journal(), get_event_report()

### Community 109 - "._extract_context_flags"
Cohesion: 0.19
Nodes (13): EventSource, KGServiceEntity, CortexGraphProps, GraphLoaderProps, PulseTimelineProps, CognitiveGraphResponse, CortexHeartbeatMessage, FrictionIndicator (+5 more)

### Community 110 - "HeadhunterJira"
Cohesion: 0.20
Nodes (11): HealthStatus, NodeType, AppNodeData, ARGOCD_HEALTH_COLORS, SYNC_ICONS, GENERIC_TAGS, HEALTH_COLORS, NODE_ICONS (+3 more)

### Community 115 - ".run"
Cohesion: 0.15
Nodes (3): compute_dispatch_backpressure(), ContextFlags, _safe_int_env()

### Community 118 - "cortex-constants.ts"
Cohesion: 0.17
Nodes (3): ChatEventRequest, ChatEventResponse, create_chat_event()

### Community 127 - "AsyncGitHubClient"
Cohesion: 0.18
Nodes (5): _alert_wrapper_retrigger(), handle_notify_user_slack(), _resolve_maintainer_enum(), _resolve_slack_user(), build_event_report_md()

### Community 128 - "GitLabTokenAuth"
Cohesion: 0.18
Nodes (6): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 131 - "TimeKeeperObserver"
Cohesion: 0.33
Nodes (5): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship

### Community 132 - "CortexRepository"
Cohesion: 0.20
Nodes (4): has_unevaluated_close_blocker(), _pred_jarvis_response(), _pred_unevaluated_close(), is_jarvis_acknowledgment()

### Community 135 - "scripts"
Cohesion: 0.36
Nodes (8): devQueryClient, MOCK_CORTEX_STATUS, MOCK_EVENT_ID, MOCK_NEURONS, MOCK_PULSE_BATCHES, MOCK_SHADOW, MOCK_THINKING, MOCK_WHISPERS

### Community 148 - ".__init__"
Cohesion: 0.57
Nodes (7): adf_to_markdown(), _apply_marks(), _children(), _render(), _render_list(), _render_list_item(), _render_table_like()

### Community 149 - ".extract_github_state_key"
Cohesion: 0.32
Nodes (7): getHeadhunterPending(), HeadhunterTodo, ACTION_BADGE, formatAge(), HeadhunterQueuePanel(), renderItem(), PIPELINE_DOT

### Community 151 - "require-results.sh"
Cohesion: 0.29
Nodes (4): @tailwindcss/vite, vite, @vitejs/plugin-react, vitest

### Community 152 - ".next_turn_number"
Cohesion: 0.29
Nodes (3): handle_report_incident(), _resolve_escalation_scope(), handle_search_open_incidents()

### Community 155 - "gh-wrapper.sh"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 156 - "git-credential-darwin"
Cohesion: 0.73
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

## Knowledge Gaps
- **14 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+9 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2089 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **114 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `brain.py`, `EventDocument`, `useCortexData.ts`, `Archivist`, `tool_gates.py`, `nightwatcher_tools.py`, `jenkins-mcp.js`, `react`, `jenkins_observer.py`, `list_incidents`, `OpsStateContext.tsx`, `tsconfig.json`, `._run_agent_task`, `GitLabPlatform`, `.receive_brain_response`, `_patch_enum_fields`, `JenkinsObserver`, `build_gate_context`, `ui/package.json`, `TurnBubble.tsx`, `_pred_hard_strip_defer`, `_pred_jarvis_wait`, `ArchitectureGraph.tsx`, `handlers_integration.py`, `_pred_silent_park`, `diagnose_rejection`, `reports/__init__.py`, `skill_reconciler/__init__.py`, `.get_edge_metadata`, `ws-client.js`, `._get_manager`, `KargoObserver`, `.close_event`, `.record_observation`, `cli-setup.js`, `DashboardWSAdapter`, `._connect`, `ObservationRepository`, `ShiftsPage.tsx`, `QuotaTracker`, `SlackAccessGate`, `generate_map.py`, `MultiInstallationManager`, `JarvisMemoryPage.tsx`, `is_defer_event_available`, `cortex-constants.ts`?**
  _High betweenness centrality (0.148) - this node is a cross-community bridge._
- **Are the 78 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 78 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _14 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.018108068955526583 - nodes in this community are weakly interconnected._
- **Why does `Brain` connect `nightwatcher_tools.py` to `BlackboardState`, `.analyze_and_comment`, `EventDocument`, `Archivist`, `tool_gates.py`, `jenkins-mcp.js`, `SlackChannel`, `react`, `jenkins_observer.py`, `OpsStateContext.tsx`, `EventRepository`, `._process_with_llm`, `JenkinsObserver`, `TurnBubble.tsx`, `_pred_obs_plateau`, `.broadcast`, `.next_turn_number`, `StateWatcher`, `CortexGraph.tsx`, `adf_to_markdown`, `KargoObserver`, `compilerOptions`, `compilerOptions`, `ClaudeAdapter`, `generate_map.py`, `.run`, `._github_poll_and_process`, `NeuronInfoPanel.tsx`, `entity_extractor.py`, `MetricsRepository`?**
  _High betweenness centrality (0.065) - this node is a cross-community bridge._
- **Are the 20 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Should `brain.py` be split into smaller, more focused modules?**
  _Cohesion score 0.0388748419721871 - nodes in this community are weakly interconnected._