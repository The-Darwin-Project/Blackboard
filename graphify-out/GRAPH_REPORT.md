# Graph Report - Blackboard  (2026-11-01)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 4893 nodes · 10906 edges · 210 communities (98 shown, 112 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 927 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `1ed4897d`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BlackboardState
- logging
- client.ts
- auth.py
- tool_gates.py
- App.tsx
- Brain
- JenkinsObserver
- merge-guard.js
- EventChatPanel.tsx
- credentials.js
- EventSidebar.tsx
- colors.ts
- jenkins-mcp.js
- ._run_agent_task
- GitHubPlatform
- HeadhunterJira
- react
- SlackChannel
- BrainSkillLoader
- useMemory.ts
- GitLabPlatform
- slack.py
- EventDocument
- agents/__init__.py
- Archivist
- _BrainToolContext
- lucide-react
- ._process_with_llm
- ToolContext
- cli-executor.js
- EventRepository
- storage-recycler.js
- JenkinsAdapter
- nightwatcher_tools.py
- DashboardWSAdapter
- brain.py
- observations_reporter.py
- ._ensure_initialized
- ScheduleCreateRequest
- handlers_integration.py
- ConversationTurn
- Aligner
- hooks/index.ts
- Headhunter
- TimeKeeperPage.tsx
- httpx
- CortexGraph.tsx
- main.py
- ws-client.js
- dispatch.py
- ui/package.json
- lifespan
- dependencies.py
- EventDrillDown.tsx
- GeminiAdapter
- queue.py
- KnowledgeGraphStore
- server.js
- get_brain
- LiveAPIAdapter
- AgentRegistry
- event_to_markdown
- adf_to_markdown
- NodeInspector.tsx
- ArgoCDObserver
- .get_event
- reconcile.py
- llm/__init__.py
- get_archivist
- KargoObserver
- TopologyRepository
- dependencies
- http-handler.js
- IdleTimeoutManager
- GitHubAppAuth
- compilerOptions
- claude-guard.js
- ArchitectureGraph.tsx
- VcsPlatformPort
- PulseBatch
- WorkspaceTaskItem.tsx
- TokenUtilizationPage.tsx
- ReflexSearcher
- StateWatcher
- context_parts.py
- ._poll_issues
- devDependencies
- compilerOptions
- EphemeralProvisioner
- get_report
- redis_client.py
- gemini-sidecar/package.json
- ._build_contents
- ObservationRepository
- useCortexData.ts
- ShiftsPage.tsx
- QuotaTracker
- OIDCKeyAdapter
- handle_request_user_approval
- ClaudeAdapter
- .list_observations
- catalog-skills.js
- FairQueue
- generate_map.py
- KubernetesSpawnHealthAdapter
- graph_recall.py
- EscalationRepository
- ServiceNode.tsx
- .start_event_loop
- close_event_by_user
- nightwatcher_prompt.py
- vcs_approval.py
- NeuronInfoPanel.tsx
- FilterRule
- ._extract_context_flags
- BrainLifecyclePort
- TokenMeter
- NightwatcherObserver
- ReconcileScheduler
- MultiInstallationManager
- ._github_poll_and_process
- SlackAccessGate
- cortex/types.ts
- resolve_maintainer_emails
- is_defer_event_available
- cortex-constants.ts
- CortexLiveFeed.tsx
- spawn_health.py
- vite.config.ts
- ._post_agent_recall
- entity_extractor.py
- MessageStatus
- get_quota_tracker
- SpawnPollResult
- SmartsheetMaintainerCache
- list_shifts
- Trigger
- MetricsRepository
- AsyncGitHubClient
- GitLabTokenAuth
- _is_event_closed_or_missing
- ._evaluate_health
- TimeKeeperObserver
- update_knowledge
- CortexRepository
- handle_report_incident
- scripts
- state.js
- validate-mutations.sh
- ._process_message
- DispatchMetrics
- is_jarvis_acknowledgment
- list_failed_stages
- ._wait_for_registration
- submit_feedback
- get_notebook
- StalenessGuard
- ResyncTrigger
- list_incidents
- rebuild_deep_memory
- require-results.sh
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
- `MetricsRepository` --uses--> `ArchitectureEvent`  [INFERRED]
  src/state/ports.py → src/models.py
- `EventRepository` --uses--> `ConversationMessage`  [INFERRED]
  src/state/ports.py → src/models.py
- `get_flow_metrics()` --uses--> `FlowMetricsResponse`  [INFERRED]
  src/main.py → src/models.py
- `get_flow_history()` --uses--> `FlowSnapshot`  [INFERRED]
  src/main.py → src/models.py
- `FlowCollector` --uses--> `FlowSnapshot`  [INFERRED]
  src/observers/flow_collector.py → src/models.py

## Import Cycles
- None detected.

## Communities (210 total, 112 thin omitted)

### Community 0 - "BlackboardState"
Cohesion: 0.01
Nodes (36): AppNode, ArchitectureEvent, ChatRequest, ChatResponse, CIAnalysis, ConversationMessage, EventInput, EventMetrics (+28 more)

### Community 1 - "logging"
Cohesion: 0.03
Nodes (18): _heartbeat(), _sanitize_lesson_text(), _get_static_maintainer_emails(), _get_allowed_mention_authors(), _get_static_maintainer_emails(), _safe_int(), _parse_job_metadata(), create_adapter() (+10 more)

### Community 2 - "client.ts"
Cohesion: 0.03
Nodes (113): ApiError, bulkDeleteObservations(), closeEvent(), deleteNote(), deleteObservation(), enforceCasualDomain(), exportObservations(), ExtractionResult (+105 more)

### Community 3 - "auth.py"
Cohesion: 0.03
Nodes (28): can_append_message(), can_approve_event(), _claims_to_user(), get_user_from_slack(), get_user_from_websocket(), _normalize_email(), require_auth(), require_obs_admin() (+20 more)

### Community 4 - "tool_gates.py"
Cohesion: 0.05
Nodes (78): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+70 more)

### Community 5 - "App.tsx"
Cohesion: 0.05
Nodes (65): oidc-client-ts, react-dom, dismissProposals(), EnhancementProposal, getConfig(), getHandoffReports(), getProposals(), getWSAuthFailureCallback() (+57 more)

### Community 7 - "JenkinsObserver"
Cohesion: 0.04
Nodes (14): _annotation_replace(), _strip_pipeline_annotations(), _clamp_confidence(), _env_flag(), JenkinsObserver, _prepare_console_tail(), _redact_build_parameters(), _redact_match() (+6 more)

### Community 8 - "merge-guard.js"
Cohesion: 0.05
Nodes (69): analyzeString(), analyzeTokens(), API_VALUED, apiTokens(), apiWriteNeedsGuard(), assignName(), bareBranchProtected(), base() (+61 more)

### Community 9 - "EventChatPanel.tsx"
Cohesion: 0.07
Nodes (56): react-router-dom, CiContext, ConversationTurn, EventEvidence, TokenUsageDict, ChatInput(), CiContextCard(), CiContextCardProps (+48 more)

### Community 10 - "credentials.js"
Cohesion: 0.07
Nodes (58): is429Error(), { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync } (+50 more)

### Community 11 - "EventSidebar.tsx"
Cohesion: 0.08
Nodes (51): getIncidents(), getJiraMissions(), HeadhunterTodo, Incident, postJiraAction(), JenkinsPendingItem, JiraMission, ACTION_BADGE (+43 more)

### Community 12 - "colors.ts"
Cohesion: 0.07
Nodes (39): getReport(), getReports(), ReportFull, ReportMeta, CompactCardStrip(), EventHistory(), TimeRange, ViewMode (+31 more)

### Community 13 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 14 - "._run_agent_task"
Cohesion: 0.06
Nodes (7): on_huddle(), on_progress(), on_huddle(), on_progress(), _sanitize_error_text(), _select_dispatch_tier(), get_registry_and_bridge()

### Community 16 - "HeadhunterJira"
Cohesion: 0.05
Nodes (3): HeadhunterJira, _walk_adf_mentions(), _walk()

### Community 17 - "react"
Cohesion: 0.07
Nodes (44): react, @uiw/react-markdown-preview, approveEvent(), rejectEvent(), submitFeedback(), AgentStreamCard(), AgentStreamCardProps, FloatingWindow() (+36 more)

### Community 18 - "SlackChannel"
Cohesion: 0.06
Nodes (9): SlackChannel, handle_app_home_opened(), handle_app_mention(), handle_approve(), handle_create_event_modal(), handle_darwin_command(), handle_home_create_event(), handle_reject() (+1 more)

### Community 19 - "BrainSkillLoader"
Cohesion: 0.05
Nodes (4): BrainSkillLoader, _SkillCorpus, _wrap_section(), BrainIntrospectionPort

### Community 20 - "useMemory.ts"
Cohesion: 0.07
Nodes (49): applyLessons(), correctMemory(), createKnowledge(), createLesson(), deleteKnowledge(), deleteLesson(), ExtractedCorrection, ExtractedLesson (+41 more)

### Community 22 - "slack.py"
Cohesion: 0.06
Nodes (20): build_access_denied_home_view(), build_home_tab_view(), _context_line(), create_feedback_block(), extract_tables(), _replace(), format_event_summary(), format_plan_block() (+12 more)

### Community 24 - "agents/__init__.py"
Cohesion: 0.06
Nodes (7): Architect, AgentClient, Developer, safe_execution(), wrapper(), SecurityError, SysAdmin

### Community 27 - "lucide-react"
Cohesion: 0.08
Nodes (34): lucide-react, getAgents(), getKargoStages(), AgentRegistryEntry, KargoStageStatus, AgentRegistryPanel(), formatConnectedSince(), ErrorBoundary (+26 more)

### Community 29 - "ToolContext"
Cohesion: 0.09
Nodes (10): handle_message_agent(), handle_reply_to_agent(), handle_select_agent(), _sticky_work_style(), handle_defer_event(), handle_hold_watch(), handle_respond_to_jarvis(), handle_wait_for_agent() (+2 more)

### Community 30 - "cli-executor.js"
Cohesion: 0.09
Nodes (36): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS, STORAGE_PRETASK_TIMEOUT_MS, resolveStorageRoot }, buildCLICommand(), { checkAndRecycleStorage, pinTaskCwd, unpinTaskCwd }, CLAUDE_JSON_PATH, cp, executeCLI(), executeCLIStreaming(), FALLBACK_MODEL (+28 more)

### Community 32 - "storage-recycler.js"
Cohesion: 0.08
Nodes (34): withTaskStorage(), resolveStorageRoot(), ROLE_TIMEOUTS, STORAGE_ACTIVITY_HEARTBEAT_MS, STORAGE_MAX_TIER3_DELETIONS, STORAGE_PRETASK_TIMEOUT_MS, STORAGE_RESULTS_TTL_MS, STORAGE_STALE_MS (+26 more)

### Community 33 - "JenkinsAdapter"
Cohesion: 0.06
Nodes (6): BuildDetails, JenkinsAdapter, JenkinsPlatformPort, JobResult, JobRunState, ViewScanResult

### Community 34 - "nightwatcher_tools.py"
Cohesion: 0.10
Nodes (20): PulseContext, ShiftIncident, ShiftInvestigation, extract_full_links(), build_extend_tool(), build_report_tool(), build_summary_tool(), execute_tool() (+12 more)

### Community 35 - "DashboardWSAdapter"
Cohesion: 0.08
Nodes (12): DashboardWSAdapter, _build_closed_block(), build_event_header(), _build_identity_block(), _build_journal_block(), _build_mermaid_block(), _build_related_block(), _build_subject_block() (+4 more)

### Community 36 - "brain.py"
Cohesion: 0.08
Nodes (12): _compute_processed_up_to(), _has_non_user_turns(), _is_seed_turn(), _safe_int(), handle_classify_event(), handle_close_event(), has_unevaluated_close_blocker(), EventStatus (+4 more)

### Community 37 - "observations_reporter.py"
Cohesion: 0.07
Nodes (16): _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), render_pdf(), _sample_points(), _summarize() (+8 more)

### Community 39 - "ScheduleCreateRequest"
Cohesion: 0.06
Nodes (6): ScheduleCreateRequest, delete_schedule(), get_schedule(), list_schedules(), toggle_schedule(), update_schedule()

### Community 40 - "handlers_integration.py"
Cohesion: 0.09
Nodes (16): _alert_wrapper_retrigger(), _do_retrigger(), _get_jira_reporter(), handle_refresh_github_context(), handle_refresh_gitlab_context(), handle_refresh_kargo_context(), _is_darwin_reentrant_caller(), jenkins_retrigger_cooldown_key() (+8 more)

### Community 41 - "ConversationTurn"
Cohesion: 0.16
Nodes (28): emit_tool_result(), handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_recall_pruned_turns(), handle_ask_release_ai(), handle_comment_jira_issue(), handle_fetch_jira_issue() (+20 more)

### Community 43 - "hooks/index.ts"
Cohesion: 0.11
Nodes (24): @tanstack/react-query, createChatEvent(), getEvents(), ActivityStream(), EXAMPLE_PROMPTS, GuidePage(), Section(), Header() (+16 more)

### Community 45 - "TimeKeeperPage.tsx"
Cohesion: 0.12
Nodes (24): createSchedule(), deleteSchedule(), getSchedules(), refineInstructions(), ScheduleCreatePayload, ScheduleItem, toggleSchedule(), updateSchedule() (+16 more)

### Community 46 - "httpx"
Cohesion: 0.09
Nodes (8): dex_proxy(), approve_mission(), dismiss_mission(), _infer_phase(), _jira_config(), list_missions(), reanalyze_mission(), retry_mission()

### Community 47 - "CortexGraph.tsx"
Cohesion: 0.12
Nodes (30): graphology, ActiveEvent, KGServiceEntity, eventColor(), getExecutiveNeurons(), getStructuralEdges(), DEFAULT_TYPE_BUDGET, evictLru() (+22 more)

### Community 48 - "main.py"
Cohesion: 0.08
Nodes (12): set_brain(), agent_ws_endpoint(), api_info(), get_config(), get_event_flow(), get_flow_history(), health_check(), list_agents() (+4 more)

### Community 49 - "ws-client.js"
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

### Community 50 - "dispatch.py"
Cohesion: 0.11
Nodes (10): _build_prompt(), _check_security(), consume_wake_task(), _consume(), _dispatch_timeout_s(), dispatch_to_agent(), _consume_queue(), _sanitize_stdout() (+2 more)

### Community 51 - "ui/package.json"
Cohesion: 0.08
Nodes (29): autoprefixer, cronstrue, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, graphology-layout-forceatlas2 (+21 more)

### Community 52 - "lifespan"
Cohesion: 0.07
Nodes (7): set_incident_options(), set_agents(), set_archivist(), set_argocd_observer(), set_blackboard(), set_registry_and_bridge(), lifespan()

### Community 53 - "dependencies.py"
Cohesion: 0.08
Nodes (14): get_aligner(), get_architect(), get_argocd_observer(), get_developer(), get_kargo_observer(), get_kg_store(), get_report_client(), get_sysadmin() (+6 more)

### Community 54 - "EventDrillDown.tsx"
Cohesion: 0.13
Nodes (23): three, getEventPulses(), BrainCore(), CortexDevPage(), devQueryClient, CortexLiveFeedProps, EventDrillDown(), EventDrillDownProps (+15 more)

### Community 56 - "queue.py"
Cohesion: 0.12
Nodes (15): can_override_domain(), apply_lessons(), correct_memory(), CorrectMemoryRequest, create_knowledge(), create_lesson(), enforce_casual_domain(), EnforceCasualRequest (+7 more)

### Community 57 - "KnowledgeGraphStore"
Cohesion: 0.15
Nodes (4): _acquire(), KnowledgeGraphStore, _sanitize(), _with_timeout()

### Community 58 - "server.js"
Cohesion: 0.09
Nodes (19): hasRegistryCredentials(), { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, ensureEventDocument(), fs, path, stageEventDocument(), fetchEventDocument(), fs (+11 more)

### Community 59 - "get_brain"
Cohesion: 0.10
Nodes (9): get_user_from_request(), get_brain(), ChatEventRequest, ChatEventResponse, create_chat_event(), get_cognitive_graph(), approve_event(), reject_event() (+1 more)

### Community 61 - "AgentRegistry"
Cohesion: 0.10
Nodes (3): AgentConnection, AgentRegistry, agent_websocket_handler()

### Community 62 - "event_to_markdown"
Cohesion: 0.09
Nodes (6): get_event_document(), get_all_journal(), get_service_journal(), _esc(), _esc_join(), event_to_markdown()

### Community 63 - "adf_to_markdown"
Cohesion: 0.12
Nodes (10): _adf_to_text(), _escape_jql_string(), JiraIncidentAdapter, adf_to_markdown(), _apply_marks(), _children(), _render(), _render_list() (+2 more)

### Community 64 - "NodeInspector.tsx"
Cohesion: 0.13
Nodes (23): getClosedEvents(), ArchitectureEvent, ArgoCDOperation, ArchitectureGraph(), EVENT_LABELS, EventItem(), EventItemProps, healthTone() (+15 more)

### Community 66 - ".get_event"
Cohesion: 0.09
Nodes (8): report_tampering(), _defer_timeline_fields(), get_event_report(), _has_active_subscription(), list_active_events(), list_closed_events(), list_waiting_approval_events(), _serialize_evidence()

### Community 67 - "reconcile.py"
Cohesion: 0.15
Nodes (10): sanitize_redis_port(), _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers(), main() (+2 more)

### Community 68 - "llm/__init__.py"
Cohesion: 0.16
Nodes (5): FunctionCall, LLMChunk, LLMPort, LLMResponse, TokenUsage

### Community 69 - "get_archivist"
Cohesion: 0.11
Nodes (11): get_archivist(), delete_knowledge(), delete_lesson(), get_event_approval(), get_event_turns(), get_knowledge(), get_lesson(), get_memory() (+3 more)

### Community 72 - "dependencies"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 73 - "http-handler.js"
Cohesion: 0.12
Nodes (19): getRemoteClustersMeta(), hasGitLabCredentials(), setupGitLabCredentials(), setupRegistryCredentials(), { AGENT_CLI, AGENT_MODEL, DEFAULT_WORK_DIR, PORT, BRAIN_HTTP_URL }, { claudeMergeGuard }, { executeCLI }, fs (+11 more)

### Community 76 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 77 - "claude-guard.js"
Cohesion: 0.14
Nodes (18): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+10 more)

### Community 78 - "ArchitectureGraph.tsx"
Cohesion: 0.14
Nodes (17): @dagrejs/dagre, @xyflow/react, applyDagreLayout(), applyGridLayout(), applyLayout(), ArchitectureGraphInner(), buildGraph(), computeIdHash() (+9 more)

### Community 80 - "PulseBatch"
Cohesion: 0.12
Nodes (4): PulseBatch, PulsePort, PulseObserver, PulseTracker

### Community 81 - "WorkspaceTaskItem.tsx"
Cohesion: 0.18
Nodes (16): DeferCountdownBar(), STATUS_COLORS, TICKET_COLORS, TicketNodeComponent(), TicketNodeData, EventNode(), relativeAge(), WorkspaceTaskItem() (+8 more)

### Community 82 - "TokenUtilizationPage.tsx"
Cohesion: 0.17
Nodes (16): recharts, getFlowHistory(), FlowSnapshot, ObservationSeries, FlowHistoryPage(), formatTime(), RANGES, SparkCard() (+8 more)

### Community 84 - "StateWatcher"
Cohesion: 0.13
Nodes (3): _QueueEntry, StateWatcher, _Subscription

### Community 85 - "context_parts.py"
Cohesion: 0.13
Nodes (9): _apply_sibling_signature(), build_function_response(), build_single_function_response(), compress_contents(), estimate_msg_tokens(), estimate_tokens(), extract_model_parts(), normalize_response_parts() (+1 more)

### Community 87 - "devDependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 88 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 90 - "get_report"
Cohesion: 0.11
Nodes (6): get_report(), list_reports(), reports_spa_no_slash(), reports_spa_with_slash(), search_reports(), _serve_spa()

### Community 91 - "redis_client.py"
Cohesion: 0.13
Nodes (3): close_redis(), get_redis(), RedisClient

### Community 92 - "gemini-sidecar/package.json"
Cohesion: 0.11
Nodes (17): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+9 more)

### Community 96 - "useCortexData.ts"
Cohesion: 0.29
Nodes (16): getCognitiveGraph(), getCortexActivity(), getRecentPulses(), CortexPage(), isOffRingCollection(), OffRingCollection, useWSMessage(), useCortexGraph() (+8 more)

### Community 97 - "ShiftsPage.tsx"
Cohesion: 0.23
Nodes (16): getCurrentShift(), getShiftDetail(), getShiftsList(), ShiftReportFull, ShiftReportSummary, FailedClusterBadge(), getISOWeek(), getWeekDates() (+8 more)

### Community 100 - "handle_request_user_approval"
Cohesion: 0.12
Nodes (4): handle_request_user_approval(), IdleTimeoutPort, IncidentAdapterPort, StateWatcherPort

### Community 102 - ".list_observations"
Cohesion: 0.13
Nodes (3): get_event_observations(), get_global_observations(), export_observations()

### Community 103 - "catalog-skills.js"
Cohesion: 0.17
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 105 - "generate_map.py"
Cohesion: 0.19
Nodes (6): _enumerate_gates(), _GateInfo, generate_phase_tool_map(), _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 107 - "graph_recall.py"
Cohesion: 0.19
Nodes (5): _format_graph_context(), get_graph_context(), _parse_props(), _sanitize(), translate_to_lookups()

### Community 109 - "ServiceNode.tsx"
Cohesion: 0.20
Nodes (11): HealthStatus, NodeType, AppNodeData, ARGOCD_HEALTH_COLORS, SYNC_ICONS, GENERIC_TAGS, HEALTH_COLORS, NODE_ICONS (+3 more)

### Community 111 - "close_event_by_user"
Cohesion: 0.14
Nodes (4): get_token_meter(), close_event_by_user(), CloseRequest, get_event_document()

### Community 112 - "nightwatcher_prompt.py"
Cohesion: 0.16
Nodes (6): build_manifest_table(), build_report_iteration_prompt(), build_summary_prompt(), build_system_prompt(), extract_event_links(), _normalize_gitlab_host()

### Community 113 - "vcs_approval.py"
Cohesion: 0.19
Nodes (7): _github_active_item(), headhunter_pending_todos(), get_gitlab_auth(), _resolve_github_head(), _resolve_gitlab_head(), resolve_live_head_sha(), verify_merge_guard()

### Community 114 - "NeuronInfoPanel.tsx"
Cohesion: 0.23
Nodes (13): KGServiceDetail, asNumber(), asString(), asStringArray(), Badge(), describeNeuron(), Hdr(), NeuronInfoPanel() (+5 more)

### Community 116 - "._extract_context_flags"
Cohesion: 0.15
Nodes (3): compute_dispatch_backpressure(), ContextFlags, _safe_int_env()

### Community 127 - "cortex/types.ts"
Cohesion: 0.21
Nodes (10): EventSource, PulseTimelineProps, CognitiveGraphResponse, CortexHeartbeatMessage, FrictionIndicator, FrictionPattern, MessageClass, NeuronVisual (+2 more)

### Community 128 - "resolve_maintainer_emails"
Cohesion: 0.20
Nodes (4): _resolve_maintainer_enum(), _resolve_slack_user(), maintainer_env_key(), resolve_maintainer_emails()

### Community 129 - "is_defer_event_available"
Cohesion: 0.18
Nodes (6): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 130 - "cortex-constants.ts"
Cohesion: 0.18
Nodes (10): AGENTS, DOMAINS, HEMISPHERE_X, NEURON_DESCRIPTIONS, PHASE_SKILL_FOLDERS, PHASE_TOOL_PRIORITY, PHASES, StructuralEdge (+2 more)

### Community 131 - "CortexLiveFeed.tsx"
Cohesion: 0.27
Nodes (9): CortexHeartbeat(), CortexHeartbeatProps, ensureKeyframes(), CortexLiveFeed(), FILTER_PILLS, FilterKey, getStoredFilter(), MESSAGE_STYLES (+1 more)

### Community 133 - "vite.config.ts"
Cohesion: 0.20
Nodes (5): @tailwindcss/vite, @testing-library/react, vite, @vitejs/plugin-react, vitest

### Community 135 - "entity_extractor.py"
Cohesion: 0.33
Nodes (5): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship

### Community 137 - "MessageStatus"
Cohesion: 0.24
Nodes (4): HealthStatus, MessageStatus, NodeType, infer_node_type()

### Community 138 - "get_quota_tracker"
Cohesion: 0.22
Nodes (3): get_quota_tracker(), llm_stats(), receive_telemetry()

### Community 149 - "update_knowledge"
Cohesion: 0.25
Nodes (4): demote_lesson(), KnowledgeUpdateRequest, update_knowledge(), verify_lesson()

### Community 151 - "handle_report_incident"
Cohesion: 0.29
Nodes (3): handle_report_incident(), _resolve_escalation_scope(), handle_search_open_incidents()

### Community 152 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 153 - "state.js"
Cohesion: 0.33
Nodes (4): { AGENT_ROLE }, _blackboardTurns, _inboundMessages, _teammateMessages

### Community 154 - "validate-mutations.sh"
Cohesion: 0.73
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

## Knowledge Gaps
- **13 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+8 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2137 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **112 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `logging`, `auth.py`, `Brain`, `MessageStatus`, `list_shifts`, `HeadhunterJira`, `_is_event_closed_or_missing`, `BrainSkillLoader`, `slack.py`, `EventDocument`, `._restage_pending_signal`, `._stage_pending_signal`, `nightwatcher_tools.py`, `DashboardWSAdapter`, `brain.py`, `observations_reporter.py`, `submit_feedback`, `get_notebook`, `ScheduleCreateRequest`, `ConversationTurn`, `._count_pending`, `rebuild_deep_memory`, `httpx`, `.cleanup_stale_services`, `main.py`, `._commit_pending_signal`, `._drain_pending`, `.drain_notes`, `lifespan`, `dependencies.py`, `.get_edge_metadata`, `queue.py`, `get_brain`, `LiveAPIAdapter`, `event_to_markdown`, `.get_event`, `get_archivist`, `get_report`, `.list_observations`, `close_event_by_user`, `NightwatcherObserver`?**
  _High betweenness centrality (0.118) - this node is a cross-community bridge._
- **Are the 79 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 79 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.012311809969889596 - nodes in this community are weakly interconnected._
- **Why does `Brain` connect `Brain` to `BlackboardState`, `logging`, `auth.py`, `._post_agent_recall`, `MessageStatus`, `._run_agent_task`, `BrainSkillLoader`, `slack.py`, `EventDocument`, `agents/__init__.py`, `._process_with_llm`, `DashboardWSAdapter`, `brain.py`, `StalenessGuard`, `ResyncTrigger`, `._format_merge_evidence`, `ConversationTurn`, `main.py`, `lifespan`, `.next_turn_number`, `dependencies.py`, `IdleTimeoutManager`, `PulseBatch`, `ReflexSearcher`, `StateWatcher`, `._build_contents`, `QuotaTracker`, `.start_event_loop`, `._extract_context_flags`, `BrainLifecyclePort`, `ReconcileScheduler`?**
  _High betweenness centrality (0.074) - this node is a cross-community bridge._
- **Are the 20 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Should `logging` be split into smaller, more focused modules?**
  _Cohesion score 0.034275583571358216 - nodes in this community are weakly interconnected._