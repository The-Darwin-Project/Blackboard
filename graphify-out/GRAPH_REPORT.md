# Graph Report - Blackboard  (2026-11-04)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 4979 nodes · 11127 edges · 218 communities (94 shown, 124 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 935 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `85cbcca7`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Brain
- BlackboardState
- queue.py
- client.ts
- logging
- react
- dependencies.py
- tool_gates.py
- EventDocument
- brain.py
- App.tsx
- create_adapter
- auth.py
- nightwatcher_tools.py
- merge-guard.js
- EventSidebar.tsx
- fetchApi
- http-handler.js
- jenkins-mcp.js
- .get_graph_data
- os
- HeadhunterJira
- slack.py
- useMemory.ts
- Aligner
- TurnBubble.tsx
- ToolContext
- Headhunter
- GitHubPlatform
- _BrainToolContext
- GitLabPlatform
- handlers_integration.py
- cli-executor.js
- storage-recycler.js
- JenkinsAdapter
- CortexGraph.tsx
- lucide-react
- agents/__init__.py
- ConversationTurn
- ActiveStreamsContext.tsx
- main.py
- lifespan
- TimeKeeperPage.tsx
- spawn_event_namer_task
- ws-client.js
- dispatch.py
- jenkins_observer.py
- ._build_contents
- AgentRegistry
- TopologyRepository
- EventDrillDown.tsx
- NodeInspector.tsx
- server.js
- SlackChannel
- ui/package.json
- KnowledgeGraphStore
- useCortexData.ts
- ArchitectureGraph.tsx
- LiveAPIAdapter
- observations_mgmt.py
- useQueue.ts
- ArgoCDObserver
- reconcile.py
- BrainSkillLoader
- KargoObserver
- GitHubAppAuth
- dependencies
- StateWatcher
- EventEvidence
- tool_router.py
- compilerOptions
- claude-guard.js
- TokenUtilizationPage.tsx
- cli-setup.js
- VcsPlatformPort
- PulseBatch
- observations_reporter.py
- ReflexSearcher
- .start_event_loop
- devDependencies
- compilerOptions
- DashboardWSAdapter
- Archivist
- EphemeralProvisioner
- ArchitectureEvent
- get_report
- gemini-sidecar/package.json
- JiraIncidentAdapter
- VectorStore
- QuotaTracker
- ObservationRepository
- ShiftsPage.tsx
- catalog-skills.js
- OIDCKeyAdapter
- state/__init__.py
- FlowSnapshot
- EscalationRepository
- cortex/types.ts
- generate_map.py
- KubernetesSpawnHealthAdapter
- ._discover
- graph_recall.py
- JenkinsObserver
- BaseModel
- .list_observations
- ServiceNode.tsx
- ScheduleRepository
- MultiInstallationManager
- .scroll
- BrainIntrospectionPort
- TokenMeter
- ScheduleCreateRequest
- IdleTimeoutManager
- SlackAccessGate
- CortexLiveFeed.tsx
- testSetup.ts
- is_defer_event_available
- NeuronInfoPanel.tsx
- spawn_health.py
- generate_event_title
- adf_to_markdown
- SpawnPollResult
- entity_extractor.py
- ._process_candidates
- ._triage_and_build_evidence
- ._drain_once
- has_unevaluated_close_blocker
- knowledge_graph_api.py
- FairQueue
- SecurityError
- SmartsheetMaintainerCache
- create_chat_event
- shifts.py
- Trigger
- AsyncGitHubClient
- GitLabTokenAuth
- _is_event_closed_or_missing
- ._evaluate_health
- TimeKeeperObserver
- ReconcileScheduler
- CortexRepository
- llm_stats
- BrainLifecyclePort
- get_all_journal
- scripts
- state.js
- validate-mutations.sh
- ._process_message
- AppNode
- _resolve_phase
- dex_proxy
- _BatchContext
- DispatchMetrics
- ._wait_for_registration
- handle_report_incident
- submit_feedback
- get_notebook
- StalenessGuard
- .store_lesson
- _patch_enum_fields
- list_incidents
- require-results.sh
- _walk_adf_mentions
- report_tampering
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
1. `BlackboardState` - 284 edges
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
- `DashboardWSAdapter` --uses--> `Brain`  [INFERRED]
  src/adapters/dashboard_ws.py → src/agents/brain.py
- `Brain` --uses--> `ReflexSearcher`  [INFERRED]
  src/agents/brain.py → src/agents/brain_reflex.py
- `Brain` --uses--> `SentenceChunker`  [INFERRED]
  src/agents/brain.py → src/agents/brain_reflex.py
- `Brain` --uses--> `BrainSkillLoader`  [INFERRED]
  src/agents/brain.py → src/agents/brain_skill_loader.py
- `Brain` --uses--> `QuotaExhaustedError`  [INFERRED]
  src/agents/brain.py → src/agents/llm/quota_tracker.py

## Import Cycles
- None detected.

## Communities (218 total, 124 thin omitted)

### Community 0 - "Brain"
Cohesion: 0.02
Nodes (8): Brain, on_huddle(), on_progress(), on_huddle(), on_progress(), _is_automated_nudge(), _sanitize_error_text(), get_registry_and_bridge()

### Community 2 - "queue.py"
Cohesion: 0.03
Nodes (56): get_token_meter(), can_append_message(), can_approve_event(), can_override_domain(), can_rename_event(), _normalize_email(), resolve_approval_identity(), get_archivist() (+48 more)

### Community 3 - "client.ts"
Cohesion: 0.04
Nodes (89): @tanstack/react-query, ApiError, bulkDeleteObservations(), createChatEvent(), deleteNote(), deleteObservation(), exportObservations(), ExtractionResult (+81 more)

### Community 4 - "logging"
Cohesion: 0.05
Nodes (3): PulseContext, _load_name_mapping(), redact_pii()

### Community 5 - "react"
Cohesion: 0.05
Nodes (70): react, updateEventTitle(), CiContext, ConversationTurn, TokenUsageDict, ChatInput(), ChatInputProps, Draft (+62 more)

### Community 6 - "dependencies.py"
Cohesion: 0.04
Nodes (23): get_aligner(), get_architect(), get_argocd_observer(), get_blackboard(), get_brain(), get_developer(), get_kargo_observer(), get_pulse_tracker() (+15 more)

### Community 7 - "tool_gates.py"
Cohesion: 0.05
Nodes (78): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+70 more)

### Community 8 - "EventDocument"
Cohesion: 0.03
Nodes (7): _init_tool_names(), _strip_tool_names(), _wrap_section(), ConversationMessage, EventDocument, EventInput, EventRepository

### Community 9 - "brain.py"
Cohesion: 0.04
Nodes (29): _compute_processed_up_to(), _has_non_user_turns(), _is_seed_turn(), _sanitize_override_reason(), _select_dispatch_tier(), _apply_sibling_signature(), build_function_response(), build_single_function_response() (+21 more)

### Community 10 - "App.tsx"
Cohesion: 0.05
Nodes (61): react-dom, react-router-dom, dismissProposals(), EnhancementProposal, getConfig(), getHandoffReports(), getIncidents(), getProposals() (+53 more)

### Community 11 - "create_adapter"
Cohesion: 0.05
Nodes (11): ClaudeAdapter, GeminiAdapter, _parse_drain_timeout(), create_adapter(), Reservation, TokenUsageDict, FunctionCall, LLMChunk (+3 more)

### Community 12 - "auth.py"
Cohesion: 0.04
Nodes (21): _claims_to_user(), get_user_from_request(), get_user_from_slack(), get_user_from_websocket(), require_auth(), require_obs_admin(), UserContext, _validate_jwt() (+13 more)

### Community 13 - "nightwatcher_tools.py"
Cohesion: 0.06
Nodes (29): record_token_usage(), ShiftIncident, ShiftInvestigation, ShiftReport, StagedEscalation, NightwatcherObserver, build_manifest_table(), build_report_iteration_prompt() (+21 more)

### Community 14 - "merge-guard.js"
Cohesion: 0.05
Nodes (69): analyzeString(), analyzeTokens(), API_VALUED, apiTokens(), apiWriteNeedsGuard(), assignName(), bareBranchProtected(), base() (+61 more)

### Community 15 - "EventSidebar.tsx"
Cohesion: 0.07
Nodes (61): getClosedEvents(), getHeadhunterPending(), getJiraMissions(), HeadhunterTodo, postJiraAction(), AgentRegistryEntry, ACTION_BADGE, formatAge() (+53 more)

### Community 16 - "fetchApi"
Cohesion: 0.06
Nodes (43): fetchApi(), getCognitiveGraph(), getKGServiceDetail(), getKGServices(), getKGStats(), getReport(), getReports(), getSchedule() (+35 more)

### Community 17 - "http-handler.js"
Cohesion: 0.09
Nodes (58): resolveCommand(), writeAgyMcpServer(), writeClaudeMcpServer(), buildArgoCDMcpConfig(), createAppJWT(), discoverAndGenerateTokens(), _discoverAndGenerateTokensInner(), discoverInstallations() (+50 more)

### Community 18 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 19 - ".get_graph_data"
Cohesion: 0.04
Nodes (11): GraphNode, GraphResponse, TicketNode, get_event_document(), get_graph_data(), get_mermaid_diagram(), get_service_details(), get_topology() (+3 more)

### Community 20 - "os"
Cohesion: 0.07
Nodes (15): _get_static_maintainer_emails(), _get_allowed_mention_authors(), _get_static_maintainer_emails(), _safe_int(), approve_mission(), dismiss_mission(), _infer_phase(), _jira_config() (+7 more)

### Community 22 - "slack.py"
Cohesion: 0.06
Nodes (20): build_access_denied_home_view(), build_home_tab_view(), _context_line(), create_feedback_block(), extract_tables(), _replace(), format_event_summary(), format_plan_block() (+12 more)

### Community 23 - "useMemory.ts"
Cohesion: 0.08
Nodes (47): applyLessons(), correctMemory(), createKnowledge(), createLesson(), deleteKnowledge(), deleteLesson(), ExtractedCorrection, ExtractedLesson (+39 more)

### Community 25 - "TurnBubble.tsx"
Cohesion: 0.09
Nodes (40): @uiw/react-markdown-preview, approveEvent(), closeEvent(), enforceCasualDomain(), getEventReport(), rejectEvent(), submitFeedback(), CollapsibleSection() (+32 more)

### Community 26 - "ToolContext"
Cohesion: 0.08
Nodes (13): handle_message_agent(), handle_reply_to_agent(), handle_select_agent(), _sticky_work_style(), handle_classify_event(), handle_defer_event(), handle_hold_watch(), handle_request_user_approval() (+5 more)

### Community 27 - "Headhunter"
Cohesion: 0.05
Nodes (3): Headhunter, _raise_if_systemic_failure(), _sanitize_xml_fence()

### Community 28 - "GitHubPlatform"
Cohesion: 0.06
Nodes (3): GitHubPlatform, _poll_one(), _poll_one()

### Community 31 - "handlers_integration.py"
Cohesion: 0.08
Nodes (19): _alert_wrapper_retrigger(), _do_retrigger(), _get_jira_reporter(), handle_notify_user_slack(), handle_refresh_github_context(), handle_refresh_gitlab_context(), handle_refresh_kargo_context(), _is_darwin_reentrant_caller() (+11 more)

### Community 32 - "cli-executor.js"
Cohesion: 0.09
Nodes (36): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS, STORAGE_PRETASK_TIMEOUT_MS, resolveStorageRoot }, buildCLICommand(), { checkAndRecycleStorage, pinTaskCwd, unpinTaskCwd }, CLAUDE_JSON_PATH, cp, executeCLI(), executeCLIStreaming(), FALLBACK_MODEL (+28 more)

### Community 33 - "storage-recycler.js"
Cohesion: 0.08
Nodes (34): withTaskStorage(), resolveStorageRoot(), ROLE_TIMEOUTS, STORAGE_ACTIVITY_HEARTBEAT_MS, STORAGE_MAX_TIER3_DELETIONS, STORAGE_PRETASK_TIMEOUT_MS, STORAGE_RESULTS_TTL_MS, STORAGE_STALE_MS (+26 more)

### Community 34 - "JenkinsAdapter"
Cohesion: 0.06
Nodes (6): BuildDetails, JenkinsAdapter, JenkinsPlatformPort, JobResult, JobRunState, ViewScanResult

### Community 35 - "CortexGraph.tsx"
Cohesion: 0.08
Nodes (38): graphology, @react-sigma/core, @react-sigma/layout-forceatlas2, sigma, @sigma/node-square, AGENTS, DOMAINS, eventColor() (+30 more)

### Community 36 - "lucide-react"
Cohesion: 0.09
Nodes (29): lucide-react, getAgents(), EventEvidence, KargoStageStatus, AgentRegistryPanel(), formatConnectedSince(), ErrorBoundary, ErrorBoundaryProps (+21 more)

### Community 37 - "agents/__init__.py"
Cohesion: 0.07
Nodes (4): Architect, AgentClient, Developer, SysAdmin

### Community 38 - "ConversationTurn"
Cohesion: 0.14
Nodes (25): emit_tool_result(), handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_recall_pruned_turns(), handle_ask_release_ai(), handle_comment_jira_issue(), handle_fetch_jira_issue() (+17 more)

### Community 39 - "ActiveStreamsContext.tsx"
Cohesion: 0.10
Nodes (33): getFlowMetrics(), FlowMetrics, AgentStreamCard(), AgentStreamCardProps, FloatingWindow(), MessageCards(), Dashboard(), FlowHealthWidget() (+25 more)

### Community 40 - "main.py"
Cohesion: 0.07
Nodes (15): set_pulse_tracker(), agent_ws_endpoint(), api_info(), get_config(), get_event_flow(), get_flow_history(), get_flow_metrics(), health_check() (+7 more)

### Community 41 - "lifespan"
Cohesion: 0.06
Nodes (9): set_agents(), set_archivist(), set_argocd_observer(), set_blackboard(), set_brain(), set_kargo_observer(), set_kg_store(), lifespan() (+1 more)

### Community 42 - "TimeKeeperPage.tsx"
Cohesion: 0.12
Nodes (24): createSchedule(), deleteSchedule(), getSchedules(), refineInstructions(), ScheduleCreatePayload, ScheduleItem, toggleSchedule(), updateSchedule() (+16 more)

### Community 43 - "spawn_event_namer_task"
Cohesion: 0.13
Nodes (10): spawn_event_namer_task(), handle_app_home_opened(), handle_app_mention(), handle_approve(), handle_create_event_modal(), handle_darwin_command(), handle_home_create_event(), handle_reject() (+2 more)

### Community 44 - "ws-client.js"
Cohesion: 0.09
Nodes (26): is429Error(), {
  DEFAULT_WORK_DIR, AGENT_CLI, AGENT_MODEL, AGENT_ROLE,
  EVENT_ID, EPHEMERAL, IDLE_TIMEOUT_MS,
  CLI_429_MAX_RETRIES, CLI_429_INITIAL_DELAY_MS, CLI_429_BACKOFF_MULTIPLIER,
}, { ensureEventDocument }, { executeCLIStreaming, prepareResultsDir, is429Error }, { filterSkillsByRole, filterSkillsByMode, swapActiveRules, restoreAllSkills }, fs, handleCancel(), resetTimer() (+18 more)

### Community 45 - "dispatch.py"
Cohesion: 0.10
Nodes (10): _build_prompt(), _check_security(), consume_wake_task(), _consume(), _dispatch_timeout_s(), dispatch_to_agent(), _consume_queue(), _sanitize_stdout() (+2 more)

### Community 46 - "jenkins_observer.py"
Cohesion: 0.09
Nodes (13): _annotation_replace(), _strip_pipeline_annotations(), _clamp_confidence(), _env_flag(), _parse_job_metadata(), _prepare_console_tail(), _redact_match(), _redact_secrets_in_text() (+5 more)

### Community 47 - "._build_contents"
Cohesion: 0.07
Nodes (4): _close_unanswered_fc(), compute_dispatch_backpressure(), ContextFlags, _safe_int_env()

### Community 48 - "AgentRegistry"
Cohesion: 0.09
Nodes (5): AgentConnection, AgentRegistry, agent_websocket_handler(), _heartbeat(), set_registry_and_bridge()

### Community 50 - "TopologyRepository"
Cohesion: 0.08
Nodes (4): Service, Snapshot, TopologySnapshot, TopologyRepository

### Community 51 - "EventDrillDown.tsx"
Cohesion: 0.13
Nodes (23): three, getEventPulses(), BrainCore(), CortexDevPage(), devQueryClient, CortexLiveFeedProps, EventDrillDown(), EventDrillDownProps (+15 more)

### Community 52 - "NodeInspector.tsx"
Cohesion: 0.12
Nodes (24): getEvents(), ArchitectureEvent, ArgoCDOperation, ActivityStream(), EVENT_LABELS, EventItem(), EventItemProps, healthTone() (+16 more)

### Community 53 - "server.js"
Cohesion: 0.08
Nodes (18): hasRegistryCredentials(), { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, fs, path, stageEventDocument(), fetchEventDocument(), fs, { handleRequest } (+10 more)

### Community 55 - "ui/package.json"
Cohesion: 0.08
Nodes (26): autoprefixer, cronstrue, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, graphology-layout-forceatlas2 (+18 more)

### Community 56 - "KnowledgeGraphStore"
Cohesion: 0.15
Nodes (4): _acquire(), KnowledgeGraphStore, _sanitize(), _with_timeout()

### Community 57 - "useCortexData.ts"
Cohesion: 0.18
Nodes (25): getCortexActivity(), getKnowledgeById(), getLessonById(), getMemory(), getRecentPulses(), getExecutiveNeurons(), CortexPage(), fetchOffRingNeuron() (+17 more)

### Community 58 - "ArchitectureGraph.tsx"
Cohesion: 0.11
Nodes (22): @dagrejs/dagre, @xyflow/react, applyDagreLayout(), applyGridLayout(), applyLayout(), ArchitectureGraph(), ArchitectureGraphInner(), buildGraph() (+14 more)

### Community 60 - "observations_mgmt.py"
Cohesion: 0.10
Nodes (10): get_report_client(), render_pdf(), bulk_delete_observations(), BulkDeleteRequest, delete_observation(), export_observations(), generate_observations_report(), rename_observation() (+2 more)

### Community 61 - "useQueue.ts"
Cohesion: 0.14
Nodes (23): getActiveEvents(), getAlignerPending(), getEventDocument(), getJenkinsPending(), getWaitingApprovalEvents(), ActiveEvent, EventDocument, MessageStatus (+15 more)

### Community 63 - "reconcile.py"
Cohesion: 0.15
Nodes (10): sanitize_redis_port(), _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers(), main() (+2 more)

### Community 66 - "GitHubAppAuth"
Cohesion: 0.11
Nodes (3): _find_pem_file(), get_github_auth(), GitHubAppAuth

### Community 67 - "dependencies"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 68 - "StateWatcher"
Cohesion: 0.11
Nodes (3): _QueueEntry, StateWatcher, _Subscription

### Community 69 - "EventEvidence"
Cohesion: 0.14
Nodes (12): _build_closed_block(), build_event_header(), _build_identity_block(), _build_journal_block(), _build_mermaid_block(), _build_related_block(), _build_subject_block(), _build_timing_block() (+4 more)

### Community 70 - "tool_router.py"
Cohesion: 0.11
Nodes (6): _safe_int(), handle_consult_deep_memory(), handle_google_web_search(), IdleTimeoutPort, IncidentAdapterPort, StateWatcherPort

### Community 71 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 72 - "claude-guard.js"
Cohesion: 0.14
Nodes (18): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+10 more)

### Community 73 - "TokenUtilizationPage.tsx"
Cohesion: 0.16
Nodes (17): recharts, getFlowHistory(), FlowSnapshot, ObservationSeries, FlowHistoryPage(), formatTime(), RANGES, SparkCard() (+9 more)

### Community 74 - "cli-setup.js"
Cohesion: 0.13
Nodes (19): { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync }, filterSkillsByMode() (+11 more)

### Community 76 - "PulseBatch"
Cohesion: 0.12
Nodes (4): PulseBatch, PulsePort, PulseObserver, PulseTracker

### Community 77 - "observations_reporter.py"
Cohesion: 0.15
Nodes (8): _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), _sample_points(), _summarize(), download_skill_md()

### Community 80 - "devDependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 81 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 86 - "ArchitectureEvent"
Cohesion: 0.13
Nodes (3): ArchitectureEvent, list_events(), MetricsRepository

### Community 87 - "get_report"
Cohesion: 0.11
Nodes (6): get_report(), list_reports(), reports_spa_no_slash(), reports_spa_with_slash(), search_reports(), _serve_spa()

### Community 88 - "gemini-sidecar/package.json"
Cohesion: 0.11
Nodes (17): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+9 more)

### Community 93 - "QuotaTracker"
Cohesion: 0.13
Nodes (3): get_quota_tracker(), QuotaExhaustedError, QuotaTracker

### Community 95 - "ShiftsPage.tsx"
Cohesion: 0.23
Nodes (16): getCurrentShift(), getShiftDetail(), getShiftsList(), ShiftReportFull, ShiftReportSummary, FailedClusterBadge(), getISOWeek(), getWeekDates() (+8 more)

### Community 96 - "catalog-skills.js"
Cohesion: 0.16
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 101 - "cortex/types.ts"
Cohesion: 0.17
Nodes (14): EventSource, KGServiceEntity, CortexGraphProps, GraphLoaderProps, NeuronInfoPanelProps, PulseTimelineProps, CognitiveGraphResponse, CortexHeartbeatMessage (+6 more)

### Community 102 - "generate_map.py"
Cohesion: 0.19
Nodes (6): _enumerate_gates(), _GateInfo, generate_phase_tool_map(), _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 105 - "graph_recall.py"
Cohesion: 0.19
Nodes (5): _format_graph_context(), get_graph_context(), _parse_props(), _sanitize(), translate_to_lookups()

### Community 107 - "BaseModel"
Cohesion: 0.13
Nodes (7): ChatRequest, ChatResponse, EventMetrics, GraphEdge, Metrics, ReportMeta, ReportSearchResponse

### Community 109 - "ServiceNode.tsx"
Cohesion: 0.20
Nodes (11): HealthStatus, NodeType, AppNodeData, ARGOCD_HEALTH_COLORS, SYNC_ICONS, GENERIC_TAGS, HEALTH_COLORS, NODE_ICONS (+3 more)

### Community 120 - "CortexLiveFeed.tsx"
Cohesion: 0.24
Nodes (10): CortexHeartbeat(), CortexHeartbeatProps, ensureKeyframes(), CortexLiveFeed(), FILTER_PILLS, FilterKey, getStoredFilter(), MESSAGE_STYLES (+2 more)

### Community 121 - "testSetup.ts"
Cohesion: 0.18
Nodes (5): @tailwindcss/vite, @testing-library/react, vite, @vitejs/plugin-react, vitest

### Community 122 - "is_defer_event_available"
Cohesion: 0.18
Nodes (6): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 123 - "NeuronInfoPanel.tsx"
Cohesion: 0.29
Nodes (10): asNumber(), asString(), asStringArray(), Badge(), describeNeuron(), Hdr(), NeuronInfoPanel(), AGENT_NEURON_COLORS (+2 more)

### Community 125 - "generate_event_title"
Cohesion: 0.22
Nodes (3): generate_event_title(), get_adapter(), _get_semaphore()

### Community 126 - "adf_to_markdown"
Cohesion: 0.40
Nodes (8): _adf_to_text(), adf_to_markdown(), _apply_marks(), _children(), _render(), _render_list(), _render_list_item(), _render_table_like()

### Community 129 - "entity_extractor.py"
Cohesion: 0.33
Nodes (5): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship

### Community 134 - "has_unevaluated_close_blocker"
Cohesion: 0.20
Nodes (4): has_unevaluated_close_blocker(), _pred_jarvis_response(), _pred_unevaluated_close(), is_jarvis_acknowledgment()

### Community 135 - "knowledge_graph_api.py"
Cohesion: 0.31
Nodes (4): get_kg_store(), get_service_detail(), get_stats(), list_services()

### Community 137 - "SecurityError"
Cohesion: 0.28
Nodes (3): safe_execution(), wrapper(), SecurityError

### Community 139 - "create_chat_event"
Cohesion: 0.25
Nodes (3): ChatEventRequest, ChatEventResponse, create_chat_event()

### Community 140 - "shifts.py"
Cohesion: 0.28
Nodes (3): get_current_shift(), get_shift_detail(), list_shifts()

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
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2178 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **124 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `Brain`, `queue.py`, `logging`, `dependencies.py`, `EventDocument`, `brain.py`, `create_chat_event`, `auth.py`, `nightwatcher_tools.py`, `shifts.py`, `_is_event_closed_or_missing`, `.get_graph_data`, `os`, `HeadhunterJira`, `slack.py`, `get_all_journal`, `AppNode`, `_resolve_phase`, `._restage_pending_signal`, `ConversationTurn`, `._stage_pending_signal`, `main.py`, `lifespan`, `jenkins_observer.py`, `submit_feedback`, `get_notebook`, `._count_pending`, `TopologyRepository`, `.__init__`, `.cleanup_stale_services`, `LiveAPIAdapter`, `observations_mgmt.py`, `._drain_pending`, `.drain_notes`, `.get_edge_metadata`, `report_tampering`, `EventEvidence`, `tool_router.py`, `observations_reporter.py`, `DashboardWSAdapter`, `ArchitectureEvent`, `get_report`, `state/__init__.py`, `FlowSnapshot`, `BaseModel`, `.list_observations`, `ScheduleRepository`, `generate_event_title`?**
  _High betweenness centrality (0.125) - this node is a cross-community bridge._
- **Are the 80 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 80 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Brain` be split into smaller, more focused modules?**
  _Cohesion score 0.020862401169357517 - nodes in this community are weakly interconnected._
- **Why does `Brain` connect `Brain` to `BlackboardState`, `queue.py`, `dependencies.py`, `EventDocument`, `brain.py`, `slack.py`, `._resolve_llm_params`, `agents/__init__.py`, `ConversationTurn`, `main.py`, `lifespan`, `._is_transient`, `._resolve_maintainer_enum`, `._build_contents`, `StalenessGuard`, `.__init__`, `BrainSkillLoader`, `StateWatcher`, `EventEvidence`, `PulseBatch`, `ReflexSearcher`, `.start_event_loop`, `DashboardWSAdapter`, `Archivist`, `QuotaTracker`, `FlowSnapshot`, `BrainIntrospectionPort`, `IdleTimeoutManager`?**
  _High betweenness centrality (0.059) - this node is a cross-community bridge._
- **Are the 20 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.012814465408805032 - nodes in this community are weakly interconnected._