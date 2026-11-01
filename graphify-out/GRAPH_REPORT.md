# Graph Report - Blackboard  (2026-11-01)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 4903 nodes · 10927 edges · 220 communities (82 shown, 138 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 927 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `f773f99b`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BlackboardState
- logging
- brain.py
- queue.py
- client.ts
- EventChatPanel.tsx
- tool_gates.py
- colors.ts
- Brain
- EventDocument
- SlackChannel
- merge-guard.js
- lucide-react
- nightwatcher_tools.py
- EventSidebar.tsx
- App.tsx
- react
- credentials.js
- jenkins-mcp.js
- ._run_agent_task
- observations_mgmt.py
- auth.py
- ArchitectureGraph.tsx
- ToolContext
- _BrainToolContext
- GitLabPlatform
- BrainSkillLoader
- cli-executor.js
- KnowledgeGraphStore
- storage-recycler.js
- JenkinsAdapter
- ui/package.json
- ._process_with_llm
- EventRepository
- GitHubPlatform
- ActiveStreamsContext.tsx
- slack.py
- EventDrillDown.tsx
- ConversationTurn
- TimeKeeperPage.tsx
- CortexGraph.tsx
- Headhunter
- ws-client.js
- Aligner
- useCortexData.ts
- ._build_system_prompt
- server.js
- LiveAPIAdapter
- ._close_and_broadcast
- adf_to_markdown
- GeminiAdapter
- WorkspaceCenterStage.tsx
- scheduling/__init__.py
- ArgoCDObserver
- NeuronInfoPanel.tsx
- reconcile.py
- llm/__init__.py
- AgentRegistry
- context_parts.py
- EphemeralProvisioner
- ._get_manager
- KargoObserver
- TopologyRepository
- dependencies
- http-handler.js
- KubernetesSpawnHealthAdapter
- PlanProgress.tsx
- compilerOptions
- claude-guard.js
- handlers_integration.py
- GitHubAppAuth
- VcsPlatformPort
- PulseBatch
- ReflexSearcher
- StateWatcher
- devDependencies
- compilerOptions
- dispatch_to_agent
- DashboardWSAdapter
- JenkinsObserver
- get_report
- gemini-sidecar/package.json
- ObservationRepository
- ShiftsPage.tsx
- QuotaTracker
- Archivist
- ClaudeAdapter
- catalog-skills.js
- VectorStore
- FairQueue
- SlackAccessGate
- generate_map.py
- OIDCKeyAdapter
- SpawnPollResult
- IdleTimeoutManager
- .list_observations
- EscalationRepository
- ServiceNode.tsx
- agent_websocket_handler
- .start_event_loop
- ScheduleRepository
- MultiInstallationManager
- ScheduleCreateRequest
- _sanitize_analysis_text
- .scroll
- ._extract_context_flags
- BrainLifecyclePort
- HeadhunterJira
- TokenMeter
- ReconcileScheduler
- JarvisMemoryPage.tsx
- tool_router.py
- ._github_poll_and_process
- CortexLiveFeed.tsx
- handle_classify_event
- is_defer_event_available
- CiContextCard.tsx
- entity_extractor.py
- _resolve_phase
- _validate_analysis
- has_unevaluated_close_blocker
- delete_schedule
- get_quota_tracker
- SmartsheetMaintainerCache
- .has_reeval_signal
- list_shifts
- Trigger
- MetricsRepository
- AsyncGitHubClient
- GitLabTokenAuth
- io
- _is_event_closed_or_missing
- IncidentAdapterPort
- ._triage_and_build_evidence
- ConversationMessage
- TimeKeeperObserver
- CortexRepository
- update_schedule
- FilterRule
- get_all_journal
- create_schedule
- scripts
- state.js
- validate-mutations.sh
- ._process_message
- SpawnStatus
- list_failed_stages
- dex_proxy
- submit_feedback
- get_notebook
- toggle_schedule
- StalenessGuard
- ResyncTrigger
- _patch_enum_fields
- list_incidents
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
- `MetricsRepository` --uses--> `ArchitectureEvent`  [INFERRED]
  src/state/ports.py → src/models.py
- `LiveAPIAdapter` --uses--> `EventStatus`  [INFERRED]
  src/adapters/live_api_adapter.py → src/models.py
- `Brain` --uses--> `EventStatus`  [INFERRED]
  src/agents/brain.py → src/models.py
- `handle_classify_event()` --uses--> `EventStatus`  [INFERRED]
  src/agents/handlers_state.py → src/models.py
- `handle_defer_event()` --uses--> `EventStatus`  [INFERRED]
  src/agents/handlers_state.py → src/models.py

## Import Cycles
- None detected.

## Communities (220 total, 138 thin omitted)

### Community 0 - "BlackboardState"
Cohesion: 0.01
Nodes (45): AppNode, ArchitectureEvent, ChatRequest, ChatResponse, CIAnalysis, EventInput, EventMetrics, EventStatus (+37 more)

### Community 1 - "logging"
Cohesion: 0.02
Nodes (54): Architect, AgentClient, Developer, _check_security(), safe_execution(), wrapper(), SecurityError, SysAdmin (+46 more)

### Community 2 - "brain.py"
Cohesion: 0.03
Nodes (23): _sanitize_lesson_text(), _get_static_maintainer_emails(), _get_allowed_mention_authors(), _get_static_maintainer_emails(), _safe_int(), _parse_job_metadata(), create_adapter(), record_token_usage() (+15 more)

### Community 3 - "queue.py"
Cohesion: 0.03
Nodes (49): get_token_meter(), can_approve_event(), resolve_approval_identity(), get_archivist(), aligner_pending_items(), apply_lessons(), approve_event(), close_event_by_user() (+41 more)

### Community 4 - "client.ts"
Cohesion: 0.04
Nodes (77): recharts, ApiError, bulkDeleteObservations(), deleteObservation(), exportObservations(), ExtractionResult, generateObservationsReport(), getEventObservations() (+69 more)

### Community 5 - "EventChatPanel.tsx"
Cohesion: 0.06
Nodes (68): react-router-dom, getEventDocument(), getEvents(), getKargoStages(), AgentRegistryEntry, EventEvidence, KargoStageStatus, TokenUsageDict (+60 more)

### Community 6 - "tool_gates.py"
Cohesion: 0.05
Nodes (78): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+70 more)

### Community 7 - "colors.ts"
Cohesion: 0.06
Nodes (50): @tanstack/react-query, getReport(), getReports(), ReportSearchParams, searchReports(), ReportFull, ReportMeta, ReportSearchResponse (+42 more)

### Community 9 - "EventDocument"
Cohesion: 0.03
Nodes (11): _close_unanswered_fc(), _build_closed_block(), build_event_header(), _build_identity_block(), _build_journal_block(), _build_mermaid_block(), _build_related_block(), _build_subject_block() (+3 more)

### Community 10 - "SlackChannel"
Cohesion: 0.05
Nodes (15): get_user_from_slack(), extract_tables(), _replace(), get_agent_notification_text(), get_turn_attachment_color(), _md_table_to_block_kit(), SlackChannel, handle_app_home_opened() (+7 more)

### Community 11 - "merge-guard.js"
Cohesion: 0.05
Nodes (69): analyzeString(), analyzeTokens(), API_VALUED, apiTokens(), apiWriteNeedsGuard(), assignName(), bareBranchProtected(), base() (+61 more)

### Community 12 - "lucide-react"
Cohesion: 0.06
Nodes (60): lucide-react, applyLessons(), correctMemory(), createKnowledge(), createLesson(), deleteKnowledge(), deleteLesson(), deleteNote() (+52 more)

### Community 13 - "nightwatcher_tools.py"
Cohesion: 0.06
Nodes (28): PulseContext, ShiftIncident, ShiftInvestigation, ShiftReport, NightwatcherObserver, build_manifest_table(), build_report_iteration_prompt(), build_summary_prompt() (+20 more)

### Community 14 - "EventSidebar.tsx"
Cohesion: 0.07
Nodes (62): getAlignerPending(), getClosedEvents(), getHeadhunterPending(), getJenkinsPending(), getJiraMissions(), getWaitingApprovalEvents(), HeadhunterTodo, postJiraAction() (+54 more)

### Community 15 - "App.tsx"
Cohesion: 0.06
Nodes (50): oidc-client-ts, react-dom, getConfig(), getFlowHistory(), getWSAuthFailureCallback(), setOnUnauthorized(), setTokenGetter(), setWSAuthFailureCallback() (+42 more)

### Community 16 - "react"
Cohesion: 0.07
Nodes (49): react, @uiw/react-markdown-preview, approveEvent(), closeEvent(), enforceCasualDomain(), fetchApi(), getAgents(), getEventReport() (+41 more)

### Community 17 - "credentials.js"
Cohesion: 0.07
Nodes (58): is429Error(), { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync } (+50 more)

### Community 18 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 19 - "._run_agent_task"
Cohesion: 0.06
Nodes (9): on_huddle(), on_progress(), on_huddle(), on_progress(), _compute_processed_up_to(), _sanitize_error_text(), _sanitize_override_reason(), _select_dispatch_tier() (+1 more)

### Community 20 - "observations_mgmt.py"
Cohesion: 0.05
Nodes (24): get_report_client(), _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), render_pdf(), _sample_points() (+16 more)

### Community 21 - "auth.py"
Cohesion: 0.05
Nodes (19): can_append_message(), can_override_domain(), _claims_to_user(), get_user_from_request(), get_user_from_websocket(), _normalize_email(), prompt_display_name(), require_auth() (+11 more)

### Community 22 - "ArchitectureGraph.tsx"
Cohesion: 0.06
Nodes (43): @dagrejs/dagre, @xyflow/react, ArchitectureEvent, ArgoCDOperation, applyDagreLayout(), applyGridLayout(), applyLayout(), ArchitectureGraph() (+35 more)

### Community 23 - "ToolContext"
Cohesion: 0.08
Nodes (12): handle_message_agent(), handle_reply_to_agent(), handle_report_incident(), handle_select_agent(), _resolve_escalation_scope(), _sticky_work_style(), handle_defer_event(), handle_hold_watch() (+4 more)

### Community 26 - "BrainSkillLoader"
Cohesion: 0.05
Nodes (3): BrainSkillLoader, _SkillCorpus, BrainIntrospectionPort

### Community 27 - "cli-executor.js"
Cohesion: 0.09
Nodes (36): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS, STORAGE_PRETASK_TIMEOUT_MS, resolveStorageRoot }, buildCLICommand(), { checkAndRecycleStorage, pinTaskCwd, unpinTaskCwd }, CLAUDE_JSON_PATH, cp, executeCLI(), executeCLIStreaming(), FALLBACK_MODEL (+28 more)

### Community 28 - "KnowledgeGraphStore"
Cohesion: 0.09
Nodes (9): _format_graph_context(), get_graph_context(), _parse_props(), _sanitize(), translate_to_lookups(), _acquire(), KnowledgeGraphStore, _sanitize() (+1 more)

### Community 29 - "storage-recycler.js"
Cohesion: 0.08
Nodes (34): withTaskStorage(), resolveStorageRoot(), ROLE_TIMEOUTS, STORAGE_ACTIVITY_HEARTBEAT_MS, STORAGE_MAX_TIER3_DELETIONS, STORAGE_PRETASK_TIMEOUT_MS, STORAGE_RESULTS_TTL_MS, STORAGE_STALE_MS (+26 more)

### Community 30 - "JenkinsAdapter"
Cohesion: 0.06
Nodes (6): BuildDetails, JenkinsAdapter, JenkinsPlatformPort, JobResult, JobRunState, ViewScanResult

### Community 31 - "ui/package.json"
Cohesion: 0.06
Nodes (34): autoprefixer, cronstrue, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, graphology-layout-forceatlas2 (+26 more)

### Community 35 - "ActiveStreamsContext.tsx"
Cohesion: 0.10
Nodes (32): getFlowMetrics(), FlowMetrics, AgentStreamCard(), AgentStreamCardProps, FloatingWindow(), MessageCards(), Dashboard(), FlowHealthWidget() (+24 more)

### Community 36 - "slack.py"
Cohesion: 0.08
Nodes (15): build_access_denied_home_view(), build_home_tab_view(), _context_line(), create_feedback_block(), format_event_summary(), format_plan_block(), format_task_card(), format_turn() (+7 more)

### Community 37 - "EventDrillDown.tsx"
Cohesion: 0.10
Nodes (32): three, getEventPulses(), EventSource, BrainCore(), CortexDevPage(), devQueryClient, CortexLiveFeedProps, EventDrillDown() (+24 more)

### Community 38 - "ConversationTurn"
Cohesion: 0.15
Nodes (23): handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_recall_pruned_turns(), handle_ask_release_ai(), handle_comment_jira_issue(), handle_greenwave(), handle_notify_gitlab_result() (+15 more)

### Community 39 - "TimeKeeperPage.tsx"
Cohesion: 0.12
Nodes (24): createSchedule(), deleteSchedule(), getSchedules(), refineInstructions(), ScheduleCreatePayload, ScheduleItem, toggleSchedule(), updateSchedule() (+16 more)

### Community 40 - "CortexGraph.tsx"
Cohesion: 0.12
Nodes (30): graphology, ActiveEvent, KGServiceEntity, eventColor(), getExecutiveNeurons(), getStructuralEdges(), DEFAULT_TYPE_BUDGET, evictLru() (+22 more)

### Community 42 - "ws-client.js"
Cohesion: 0.10
Nodes (25): {
  DEFAULT_WORK_DIR, AGENT_CLI, AGENT_MODEL, AGENT_ROLE,
  EVENT_ID, EPHEMERAL, IDLE_TIMEOUT_MS,
  CLI_429_MAX_RETRIES, CLI_429_INITIAL_DELAY_MS, CLI_429_BACKOFF_MULTIPLIER,
}, { ensureEventDocument }, { executeCLIStreaming, prepareResultsDir, is429Error }, { filterSkillsByRole, filterSkillsByMode, swapActiveRules, restoreAllSkills }, fs, handleCancel(), resetTimer(), {
  hasGitHubCredentials, discoverAndGenerateTokens, setupGitCredentials, setupGitHubTooling,
  hasGitLabCredentials, readGitLabToken, setupGitLabCredentials, setupGitLabTooling,
  setupArgoCDMCP, setupCLILogins, setupRemoteK8sMCPs, setupRegistryCredentials, GITLAB_HOST,
  hasJenkinsCredentials, setupJenkinsMCP, hasGoogleServiceAccount, setupGoogleAuthForAgy,
} (+17 more)

### Community 44 - "useCortexData.ts"
Cohesion: 0.17
Nodes (27): getActiveEvents(), getCognitiveGraph(), getCortexActivity(), getKGServiceDetail(), getKGServices(), getKnowledgeById(), getMemory(), getRecentPulses() (+19 more)

### Community 45 - "._build_system_prompt"
Cohesion: 0.07
Nodes (3): _init_tool_names(), _strip_tool_names(), _wrap_section()

### Community 46 - "server.js"
Cohesion: 0.09
Nodes (19): hasRegistryCredentials(), { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, ensureEventDocument(), fs, path, stageEventDocument(), fetchEventDocument(), fs (+11 more)

### Community 49 - "adf_to_markdown"
Cohesion: 0.12
Nodes (10): _adf_to_text(), _escape_jql_string(), JiraIncidentAdapter, adf_to_markdown(), _apply_marks(), _children(), _render(), _render_list() (+2 more)

### Community 51 - "WorkspaceCenterStage.tsx"
Cohesion: 0.14
Nodes (17): createChatEvent(), ErrorBoundary, ErrorBoundaryProps, ErrorBoundaryState, STARTER_CHIPS, StarterChip, useSafeNavigate(), WorkspaceCenterStage() (+9 more)

### Community 52 - "scheduling/__init__.py"
Cohesion: 0.13
Nodes (11): _do_retrigger(), handle_refresh_github_context(), handle_refresh_gitlab_context(), handle_refresh_kargo_context(), StateWatcherPort, GitHubPrRef, GitLabMrRef, GitLabPipelineRef (+3 more)

### Community 54 - "NeuronInfoPanel.tsx"
Cohesion: 0.11
Nodes (23): KGServiceDetail, AGENTS, DOMAINS, HEMISPHERE_X, NEURON_DESCRIPTIONS, PHASE_SKILL_FOLDERS, PHASE_TOOL_PRIORITY, PHASES (+15 more)

### Community 55 - "reconcile.py"
Cohesion: 0.15
Nodes (10): sanitize_redis_port(), _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers(), main() (+2 more)

### Community 56 - "llm/__init__.py"
Cohesion: 0.16
Nodes (5): FunctionCall, LLMChunk, LLMPort, LLMResponse, TokenUsage

### Community 57 - "AgentRegistry"
Cohesion: 0.11
Nodes (3): AgentConnection, AgentRegistry, send_cancel()

### Community 58 - "context_parts.py"
Cohesion: 0.11
Nodes (10): _apply_sibling_signature(), build_function_response(), build_single_function_response(), compress_contents(), estimate_msg_tokens(), estimate_tokens(), extract_model_parts(), normalize_response_parts() (+2 more)

### Community 63 - "dependencies"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 64 - "http-handler.js"
Cohesion: 0.12
Nodes (19): getRemoteClustersMeta(), hasGitLabCredentials(), setupGitLabCredentials(), setupRegistryCredentials(), { AGENT_CLI, AGENT_MODEL, DEFAULT_WORK_DIR, PORT, BRAIN_HTTP_URL }, { claudeMergeGuard }, { executeCLI }, fs (+11 more)

### Community 67 - "PlanProgress.tsx"
Cohesion: 0.14
Nodes (18): ConversationTurn, BORDER_COLOR, PlanProgressProps, PlanStep, STATUS_ICON, DiffFile, DiffHunk, DiffLine (+10 more)

### Community 68 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 69 - "claude-guard.js"
Cohesion: 0.14
Nodes (18): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+10 more)

### Community 70 - "handlers_integration.py"
Cohesion: 0.11
Nodes (10): _alert_wrapper_retrigger(), _get_jira_reporter(), handle_fetch_jira_issue(), handle_notify_user_slack(), _is_darwin_reentrant_caller(), jenkins_retrigger_cooldown_key(), _resolve_maintainer_enum(), _resolve_slack_user() (+2 more)

### Community 73 - "PulseBatch"
Cohesion: 0.12
Nodes (4): PulseBatch, PulsePort, PulseObserver, PulseTracker

### Community 75 - "StateWatcher"
Cohesion: 0.13
Nodes (3): _QueueEntry, StateWatcher, _Subscription

### Community 76 - "devDependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 77 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 78 - "dispatch_to_agent"
Cohesion: 0.13
Nodes (7): _build_prompt(), consume_wake_task(), _consume(), _dispatch_timeout_s(), dispatch_to_agent(), _consume_queue(), _sanitize_stdout()

### Community 81 - "get_report"
Cohesion: 0.11
Nodes (6): get_report(), list_reports(), reports_spa_no_slash(), reports_spa_with_slash(), search_reports(), _serve_spa()

### Community 82 - "gemini-sidecar/package.json"
Cohesion: 0.11
Nodes (17): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+9 more)

### Community 85 - "ShiftsPage.tsx"
Cohesion: 0.23
Nodes (16): getCurrentShift(), getShiftDetail(), getShiftsList(), ShiftReportFull, ShiftReportSummary, FailedClusterBadge(), getISOWeek(), getWeekDates() (+8 more)

### Community 90 - "catalog-skills.js"
Cohesion: 0.17
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 95 - "generate_map.py"
Cohesion: 0.19
Nodes (6): _enumerate_gates(), _GateInfo, generate_phase_tool_map(), _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 97 - "SpawnPollResult"
Cohesion: 0.14
Nodes (3): DispatchMetrics, SpawnHealthPort, SpawnPollResult

### Community 101 - "ServiceNode.tsx"
Cohesion: 0.20
Nodes (11): HealthStatus, NodeType, AppNodeData, ARGOCD_HEALTH_COLORS, SYNC_ICONS, GENERIC_TAGS, HEALTH_COLORS, NODE_ICONS (+3 more)

### Community 102 - "agent_websocket_handler"
Cohesion: 0.15
Nodes (4): agent_websocket_handler(), _heartbeat(), agent_ws_endpoint(), websocket_endpoint()

### Community 109 - "_sanitize_analysis_text"
Cohesion: 0.17
Nodes (7): _annotation_replace(), _strip_pipeline_annotations(), _prepare_console_tail(), _redact_match(), _redact_secrets_in_text(), _sanitize_analysis_text(), _sanitize_console_tail()

### Community 111 - "._extract_context_flags"
Cohesion: 0.15
Nodes (3): compute_dispatch_backpressure(), ContextFlags, _safe_int_env()

### Community 116 - "JarvisMemoryPage.tsx"
Cohesion: 0.27
Nodes (12): dismissProposals(), EnhancementProposal, getHandoffReports(), getProposals(), HandoffReport, FilterMode, formatDate(), formatTime() (+4 more)

### Community 119 - "tool_router.py"
Cohesion: 0.21
Nodes (4): emit_tool_result(), _safe_int(), handle_consult_deep_memory(), handle_google_web_search()

### Community 122 - "CortexLiveFeed.tsx"
Cohesion: 0.24
Nodes (10): CortexHeartbeat(), CortexHeartbeatProps, ensureKeyframes(), CortexLiveFeed(), FILTER_PILLS, FilterKey, getStoredFilter(), MESSAGE_STYLES (+2 more)

### Community 123 - "handle_classify_event"
Cohesion: 0.22
Nodes (3): handle_classify_event(), handle_request_user_approval(), IdleTimeoutPort

### Community 124 - "is_defer_event_available"
Cohesion: 0.18
Nodes (6): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 125 - "CiContextCard.tsx"
Cohesion: 0.31
Nodes (9): CiContext, CiContextCardProps, ConsoleTailBlock(), FailedJobRow(), annotationReplacer(), PIPELINE_ANNOTATION_RE, REDACTION_TRIGGER_KEYWORDS, stripAnsi() (+1 more)

### Community 128 - "entity_extractor.py"
Cohesion: 0.33
Nodes (5): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship

### Community 129 - "_resolve_phase"
Cohesion: 0.24
Nodes (4): handle_set_phase(), _resolve_domain(), resolve_event_domain(), _resolve_phase()

### Community 130 - "_validate_analysis"
Cohesion: 0.22
Nodes (4): _clamp_confidence(), _strip_newlines(), _validate_analysis(), _validate_triage_entry()

### Community 131 - "has_unevaluated_close_blocker"
Cohesion: 0.20
Nodes (4): has_unevaluated_close_blocker(), _pred_jarvis_response(), _pred_unevaluated_close(), is_jarvis_acknowledgment()

### Community 133 - "get_quota_tracker"
Cohesion: 0.22
Nodes (3): get_quota_tracker(), llm_stats(), receive_telemetry()

### Community 154 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 155 - "state.js"
Cohesion: 0.33
Nodes (4): { AGENT_ROLE }, _blackboardTurns, _inboundMessages, _teammateMessages

### Community 156 - "validate-mutations.sh"
Cohesion: 0.73
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

## Knowledge Gaps
- **13 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+8 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2140 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **138 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `logging`, `brain.py`, `queue.py`, `delete_schedule`, `Brain`, `list_shifts`, `EventDocument`, `nightwatcher_tools.py`, `_is_event_closed_or_missing`, `ConversationMessage`, `observations_mgmt.py`, `auth.py`, `update_schedule`, `get_all_journal`, `create_schedule`, `BrainSkillLoader`, `slack.py`, `ConversationTurn`, `._restage_pending_signal`, `._stage_pending_signal`, `submit_feedback`, `get_notebook`, `toggle_schedule`, `LiveAPIAdapter`, `._count_pending`, `.cleanup_stale_services`, `._commit_pending_signal`, `._drain_pending`, `.drain_notes`, `.get_edge_metadata`, `DashboardWSAdapter`, `get_report`, `.list_observations`, `ScheduleRepository`, `HeadhunterJira`, `tool_router.py`?**
  _High betweenness centrality (0.114) - this node is a cross-community bridge._
- **Are the 79 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 79 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.01231759418520779 - nodes in this community are weakly interconnected._
- **Why does `EventEvidence` connect `brain.py` to `BlackboardState`, `logging`, `queue.py`, `Brain`, `EventDocument`, `SlackChannel`, `_is_event_closed_or_missing`, `._triage_and_build_evidence`, `TimeKeeperObserver`, `auth.py`, `GitLabPlatform`, `EventRepository`, `GitHubPlatform`, `slack.py`, `Aligner`, `LiveAPIAdapter`, `DashboardWSAdapter`, `JenkinsObserver`, `Archivist`, `ScheduleCreateRequest`, `HeadhunterJira`?**
  _High betweenness centrality (0.064) - this node is a cross-community bridge._
- **Are the 20 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Should `logging` be split into smaller, more focused modules?**
  _Cohesion score 0.018865345181134655 - nodes in this community are weakly interconnected._