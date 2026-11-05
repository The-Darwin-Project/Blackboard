# Graph Report - Blackboard  (2026-11-05)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 5022 nodes · 11222 edges · 214 communities (95 shown, 119 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 938 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `24b142cb`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- brain.py
- logging
- ConversationTurn
- BlackboardState
- queue.py
- lucide-react
- client.ts
- nightwatcher_tools.py
- main.py
- EventDocument
- tool_gates.py
- Brain
- EventSidebar.tsx
- colors.ts
- merge-guard.js
- hooks/index.ts
- SlackChannel
- ReconcileScheduler
- http-handler.js
- BrainSkillLoader
- slack.py
- ._run_agent_task
- jenkins-mcp.js
- HeadhunterJira
- Service
- GitHubPlatform
- fetchApi
- react
- GitLabPlatform
- App.tsx
- _BrainToolContext
- Headhunter
- cli-executor.js
- storage-recycler.js
- JenkinsAdapter
- KnowledgeGraphStore
- EventRepository
- Aligner
- ._process_with_llm
- AgentClient
- TimeKeeperPage.tsx
- ScheduleCreateRequest
- useCortexData.ts
- ws-client.js
- TopologyRepository
- ActiveStreamsContext.tsx
- dispatch.py
- ui/package.json
- UserContext
- EventDrillDown.tsx
- AgentRegistry
- server.js
- LiveAPIAdapter
- CortexGraph.tsx
- IdleTimeoutManager
- GeminiAdapter
- cognitive_graph.py
- .list_observations
- types.py
- auth.py
- ArgoCDObserver
- useQueue.ts
- reconcile.py
- ._close_and_broadcast
- KargoObserver
- dependencies
- StateWatcher
- compilerOptions
- claude-guard.js
- TokenUtilizationPage.tsx
- DashboardWSAdapter
- GitHubAppAuth
- NeuronInfoPanel.tsx
- cli-setup.js
- VcsPlatformPort
- PulseBatch
- observations_mgmt.py
- ReflexSearcher
- lifespan
- ArchitectureEvent
- devDependencies
- compilerOptions
- ServiceNode.tsx
- EphemeralProvisioner
- ClaudeAdapter
- jira.py
- get_report
- EscalationRepository
- gemini-sidecar/package.json
- JenkinsObserver
- ObservationRepository
- catalog-skills.js
- ArchitectureGraph.tsx
- Archivist
- VectorStore
- cortex/types.ts
- observations_reporter.py
- SlackAccessGate
- generate_map.py
- ._normalize_issue
- OIDCKeyAdapter
- KubernetesSpawnHealthAdapter
- QuotaTracker
- PlanProgress.tsx
- ScheduleRepository
- MultiInstallationManager
- FilterRule
- .scroll
- ._extract_context_flags
- TokenMeter
- IncidentAdapterPort
- create_chat_event
- RedisClient
- JarvisMemoryPage.tsx
- _sanitize_analysis_text
- CortexLiveFeed.tsx
- testSetup.ts
- resolve_maintainer_emails
- is_defer_event_available
- spawn_health.py
- ._post_agent_recall
- entity_extractor.py
- ._process_candidates
- _prepare_console_tail
- _extract_call_syntax
- knowledge_graph_api.py
- SecurityError
- get_quota_tracker
- SpawnPollResult
- SmartsheetMaintainerCache
- list_shifts
- AsyncGitHubClient
- GitLabTokenAuth
- _is_event_closed_or_missing
- ._evaluate_health
- ._triage_and_build_evidence
- ._drain_once
- ConversationMessage
- TimeKeeperObserver
- CortexRepository
- adf_to_markdown
- update_notebook_note
- scripts
- state.js
- validate-mutations.sh
- io
- ._process_message
- DispatchMetrics
- list_failed_stages
- rename_observation
- PollFn
- dex_proxy
- ._wait_for_registration
- agent_ws_endpoint
- submit_feedback
- get_notebook
- TicketNode.tsx
- derive_llm_priority
- _patch_enum_fields
- require-results.sh
- _WSFrameFilter
- _walk_adf_mentions
- TokenUsageDict
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
1. `BlackboardState` - 285 edges
2. `Brain` - 151 edges
3. `ConversationTurn` - 122 edges
4. `ToolContext` - 103 edges
5. `GateContext` - 94 edges
6. `react` - 82 edges
7. `EventDocument` - 79 edges
8. `fetchApi()` - 66 edges
9. `lifespan()` - 65 edges
10. `LiveAPIAdapter` - 58 edges

## Surprising Connections (you probably didn't know these)
- `BlackboardState` --uses--> `AppNode`  [INFERRED]
  src/state/blackboard.py → src/models.py
- `BlackboardState` --uses--> `EventInput`  [INFERRED]
  src/state/blackboard.py → src/models.py
- `LiveAPIAdapter` --uses--> `EventStatus`  [INFERRED]
  src/adapters/live_api_adapter.py → src/models.py
- `Brain` --uses--> `EventStatus`  [INFERRED]
  src/agents/brain.py → src/models.py
- `handle_classify_event()` --uses--> `EventStatus`  [INFERRED]
  src/agents/handlers_state.py → src/models.py

## Import Cycles
- None detected.

## Communities (214 total, 119 thin omitted)

### Community 0 - "brain.py"
Cohesion: 0.03
Nodes (51): _compute_processed_up_to(), _has_non_user_turns(), _is_seed_turn(), _apply_sibling_signature(), build_function_response(), build_single_function_response(), compress_contents(), estimate_msg_tokens() (+43 more)

### Community 1 - "logging"
Cohesion: 0.04
Nodes (14): _annotation_replace(), _strip_pipeline_annotations(), _sanitize_lesson_text(), _get_static_maintainer_emails(), _get_allowed_mention_authors(), _get_static_maintainer_emails(), _safe_int(), _parse_job_metadata() (+6 more)

### Community 2 - "ConversationTurn"
Cohesion: 0.05
Nodes (58): emit_tool_result(), handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_recall_pruned_turns(), handle_message_agent(), handle_reply_to_agent(), handle_report_incident() (+50 more)

### Community 4 - "queue.py"
Cohesion: 0.03
Nodes (54): can_approve_event(), can_override_domain(), can_rename_event(), _normalize_email(), get_archivist(), get_brain(), aligner_pending_items(), apply_lessons() (+46 more)

### Community 5 - "lucide-react"
Cohesion: 0.04
Nodes (80): lucide-react, react-router-dom, getAgents(), getKargoStages(), updateEventTitle(), AgentRegistryEntry, EventEvidence, KargoStageStatus (+72 more)

### Community 6 - "client.ts"
Cohesion: 0.03
Nodes (94): bulkDeleteObservations(), deleteNote(), deleteObservation(), exportObservations(), ExtractedCorrection, ExtractedLesson, ExtractionResult, generateObservationsReport() (+86 more)

### Community 7 - "nightwatcher_tools.py"
Cohesion: 0.04
Nodes (36): JiraIncidentAdapter, record_token_usage(), QuotaExhaustedError, RequestExceedsBurstError, PulseContext, ShiftIncident, ShiftInvestigation, ShiftReport (+28 more)

### Community 8 - "main.py"
Cohesion: 0.03
Nodes (27): get_aligner(), get_architect(), get_argocd_observer(), get_blackboard(), get_developer(), get_kargo_observer(), get_sysadmin(), set_agents() (+19 more)

### Community 9 - "EventDocument"
Cohesion: 0.03
Nodes (11): _close_unanswered_fc(), _build_closed_block(), build_event_header(), _build_identity_block(), _build_journal_block(), _build_mermaid_block(), _build_related_block(), _build_subject_block() (+3 more)

### Community 10 - "tool_gates.py"
Cohesion: 0.05
Nodes (78): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+70 more)

### Community 12 - "EventSidebar.tsx"
Cohesion: 0.07
Nodes (64): getHeadhunterPending(), getJiraMissions(), HeadhunterTodo, postJiraAction(), CiContext, CiContextCard(), CiContextCardProps, ConsoleTailBlock() (+56 more)

### Community 13 - "colors.ts"
Cohesion: 0.07
Nodes (45): getReport(), getReports(), ReportFull, ReportMeta, DeferCountdownBar(), CompactCardStrip(), EventHistory(), TimeRange (+37 more)

### Community 14 - "merge-guard.js"
Cohesion: 0.05
Nodes (69): analyzeString(), analyzeTokens(), API_VALUED, apiTokens(), apiWriteNeedsGuard(), assignName(), bareBranchProtected(), base() (+61 more)

### Community 15 - "hooks/index.ts"
Cohesion: 0.05
Nodes (53): @tanstack/react-query, ApiError, createChatEvent(), getClosedEvents(), getConfig(), getEvents(), getService(), getTopology() (+45 more)

### Community 16 - "SlackChannel"
Cohesion: 0.05
Nodes (12): get_user_from_slack(), extract_tables(), _replace(), get_agent_notification_text(), get_turn_attachment_color(), _md_table_to_block_kit(), SlackChannel, handle_app_home_opened() (+4 more)

### Community 17 - "ReconcileScheduler"
Cohesion: 0.04
Nodes (7): FlowCollector, FairQueue, ReconcileScheduler, Trigger, QueueTrigger, ResyncTrigger, StalenessGuard

### Community 18 - "http-handler.js"
Cohesion: 0.09
Nodes (58): resolveCommand(), writeAgyMcpServer(), writeClaudeMcpServer(), buildArgoCDMcpConfig(), createAppJWT(), discoverAndGenerateTokens(), _discoverAndGenerateTokensInner(), discoverInstallations() (+50 more)

### Community 19 - "BrainSkillLoader"
Cohesion: 0.04
Nodes (4): BrainSkillLoader, _SkillCorpus, _wrap_section(), BrainIntrospectionPort

### Community 20 - "slack.py"
Cohesion: 0.05
Nodes (24): generate_event_title(), get_adapter(), _get_semaphore(), spawn_event_namer_task(), build_access_denied_home_view(), build_home_tab_view(), _context_line(), create_feedback_block() (+16 more)

### Community 21 - "._run_agent_task"
Cohesion: 0.06
Nodes (9): on_huddle(), on_progress(), on_huddle(), on_progress(), _is_automated_nudge(), _sanitize_error_text(), _sanitize_override_reason(), _select_dispatch_tier() (+1 more)

### Community 22 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 24 - "Service"
Cohesion: 0.05
Nodes (8): Service, get_event_document(), get_graph_data(), get_mermaid_diagram(), get_service_details(), get_topology(), list_services(), calculate_health_from_argocd()

### Community 25 - "GitHubPlatform"
Cohesion: 0.05
Nodes (3): GitHubPlatform, _poll_one(), _poll_one()

### Community 26 - "fetchApi"
Cohesion: 0.09
Nodes (47): applyLessons(), correctMemory(), createKnowledge(), createLesson(), deleteKnowledge(), deleteLesson(), extractLessons(), fetchApi() (+39 more)

### Community 27 - "react"
Cohesion: 0.09
Nodes (40): react, @uiw/react-markdown-preview, approveEvent(), closeEvent(), enforceCasualDomain(), getEventReport(), rejectEvent(), submitFeedback() (+32 more)

### Community 29 - "App.tsx"
Cohesion: 0.07
Nodes (37): oidc-client-ts, getIncidents(), getWSAuthFailureCallback(), Incident, setOnUnauthorized(), setTokenGetter(), setWSAuthFailureCallback(), AuthConfig (+29 more)

### Community 31 - "Headhunter"
Cohesion: 0.06
Nodes (3): Headhunter, _raise_if_systemic_failure(), _sanitize_xml_fence()

### Community 32 - "cli-executor.js"
Cohesion: 0.09
Nodes (36): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS, STORAGE_PRETASK_TIMEOUT_MS, resolveStorageRoot }, buildCLICommand(), { checkAndRecycleStorage, pinTaskCwd, unpinTaskCwd }, CLAUDE_JSON_PATH, cp, executeCLI(), executeCLIStreaming(), FALLBACK_MODEL (+28 more)

### Community 33 - "storage-recycler.js"
Cohesion: 0.08
Nodes (34): withTaskStorage(), resolveStorageRoot(), ROLE_TIMEOUTS, STORAGE_ACTIVITY_HEARTBEAT_MS, STORAGE_MAX_TIER3_DELETIONS, STORAGE_PRETASK_TIMEOUT_MS, STORAGE_RESULTS_TTL_MS, STORAGE_STALE_MS (+26 more)

### Community 34 - "JenkinsAdapter"
Cohesion: 0.06
Nodes (6): BuildDetails, JenkinsAdapter, JenkinsPlatformPort, JobResult, JobRunState, ViewScanResult

### Community 35 - "KnowledgeGraphStore"
Cohesion: 0.09
Nodes (9): _format_graph_context(), get_graph_context(), _parse_props(), _sanitize(), translate_to_lookups(), _acquire(), KnowledgeGraphStore, _sanitize() (+1 more)

### Community 39 - "AgentClient"
Cohesion: 0.07
Nodes (4): Architect, AgentClient, Developer, SysAdmin

### Community 40 - "TimeKeeperPage.tsx"
Cohesion: 0.11
Nodes (25): react-dom, createSchedule(), deleteSchedule(), getSchedules(), refineInstructions(), ScheduleCreatePayload, ScheduleItem, toggleSchedule() (+17 more)

### Community 41 - "ScheduleCreateRequest"
Cohesion: 0.08
Nodes (5): ScheduleCreateRequest, create_schedule(), get_schedule(), list_schedules(), update_schedule()

### Community 42 - "useCortexData.ts"
Cohesion: 0.15
Nodes (30): getCognitiveGraph(), getCortexActivity(), getKGServiceDetail(), getKGServices(), getKGStats(), getKnowledgeById(), getLessonById(), getMemory() (+22 more)

### Community 43 - "ws-client.js"
Cohesion: 0.09
Nodes (26): is429Error(), {
  DEFAULT_WORK_DIR, AGENT_CLI, AGENT_MODEL, AGENT_ROLE,
  EVENT_ID, EPHEMERAL, IDLE_TIMEOUT_MS,
  CLI_429_MAX_RETRIES, CLI_429_INITIAL_DELAY_MS, CLI_429_BACKOFF_MULTIPLIER,
}, { ensureEventDocument }, { executeCLIStreaming, prepareResultsDir, is429Error }, { filterSkillsByRole, filterSkillsByMode, swapActiveRules, restoreAllSkills }, fs, handleCancel(), resetTimer() (+18 more)

### Community 44 - "TopologyRepository"
Cohesion: 0.07
Nodes (4): GraphResponse, Snapshot, TopologySnapshot, TopologyRepository

### Community 45 - "ActiveStreamsContext.tsx"
Cohesion: 0.13
Nodes (26): AgentStreamCard(), AgentStreamCardProps, FloatingWindow(), MessageCards(), Dashboard(), GridTile(), GridTileProps, TileType (+18 more)

### Community 46 - "dispatch.py"
Cohesion: 0.11
Nodes (10): _build_prompt(), _check_security(), consume_wake_task(), _consume(), _dispatch_timeout_s(), dispatch_to_agent(), _consume_queue(), _sanitize_stdout() (+2 more)

### Community 47 - "ui/package.json"
Cohesion: 0.08
Nodes (29): autoprefixer, cronstrue, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, graphology-layout-forceatlas2 (+21 more)

### Community 48 - "UserContext"
Cohesion: 0.08
Nodes (10): _claims_to_user(), get_user_from_request(), get_user_from_websocket(), require_auth(), require_obs_admin(), UserContext, _validate_jwt(), delete_notebook_note() (+2 more)

### Community 50 - "EventDrillDown.tsx"
Cohesion: 0.13
Nodes (23): three, getEventPulses(), BrainCore(), CortexDevPage(), devQueryClient, CortexLiveFeedProps, EventDrillDown(), EventDrillDownProps (+15 more)

### Community 51 - "AgentRegistry"
Cohesion: 0.09
Nodes (4): AgentConnection, AgentRegistry, agent_websocket_handler(), _heartbeat()

### Community 52 - "server.js"
Cohesion: 0.08
Nodes (18): hasRegistryCredentials(), { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, fs, path, stageEventDocument(), fetchEventDocument(), fs, { handleRequest } (+10 more)

### Community 54 - "CortexGraph.tsx"
Cohesion: 0.15
Nodes (24): graphology, eventColor(), getStructuralEdges(), DEFAULT_TYPE_BUDGET, evictLru(), KNOWLEDGE_RING, KNOWLEDGE_RING_TYPES, KnowledgeNodeAttributes (+16 more)

### Community 55 - "IdleTimeoutManager"
Cohesion: 0.08
Nodes (3): BrainLifecyclePort, BroadcastPort, IdleTimeoutManager

### Community 57 - "cognitive_graph.py"
Cohesion: 0.11
Nodes (11): get_pulse_tracker(), dismiss_proposals(), DismissRequest, get_all_shadow_interventions(), get_cognitive_graph(), get_cortex_activity(), get_cortex_status(), get_event_shadow_interventions() (+3 more)

### Community 58 - ".list_observations"
Cohesion: 0.08
Nodes (4): get_all_journal(), get_service_journal(), get_event_observations(), get_global_observations()

### Community 59 - "types.py"
Cohesion: 0.14
Nodes (5): _parse_drain_timeout(), LLMChunk, LLMPort, LLMResponse, TokenUsage

### Community 60 - "auth.py"
Cohesion: 0.10
Nodes (8): can_append_message(), resolve_approval_identity(), set_oidc_adapter(), get_gitlab_auth(), _resolve_github_head(), _resolve_gitlab_head(), resolve_live_head_sha(), verify_merge_guard()

### Community 62 - "useQueue.ts"
Cohesion: 0.14
Nodes (22): getActiveEvents(), getAlignerPending(), getEventDocument(), getJenkinsPending(), getWaitingApprovalEvents(), ActiveEvent, EventDocument, MessageStatus (+14 more)

### Community 63 - "reconcile.py"
Cohesion: 0.15
Nodes (10): sanitize_redis_port(), _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers(), main() (+2 more)

### Community 66 - "dependencies"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 67 - "StateWatcher"
Cohesion: 0.11
Nodes (3): _QueueEntry, StateWatcher, _Subscription

### Community 69 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 70 - "claude-guard.js"
Cohesion: 0.14
Nodes (18): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+10 more)

### Community 71 - "TokenUtilizationPage.tsx"
Cohesion: 0.16
Nodes (17): recharts, getFlowHistory(), FlowSnapshot, ObservationSeries, FlowHistoryPage(), formatTime(), RANGES, SparkCard() (+9 more)

### Community 74 - "NeuronInfoPanel.tsx"
Cohesion: 0.12
Nodes (20): AGENTS, DOMAINS, HEMISPHERE_X, NEURON_DESCRIPTIONS, PHASE_SKILL_FOLDERS, PHASE_TOOL_PRIORITY, PHASES, StructuralEdge (+12 more)

### Community 75 - "cli-setup.js"
Cohesion: 0.13
Nodes (19): { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync }, filterSkillsByMode() (+11 more)

### Community 77 - "PulseBatch"
Cohesion: 0.12
Nodes (4): PulseBatch, PulsePort, PulseObserver, PulseTracker

### Community 78 - "observations_mgmt.py"
Cohesion: 0.14
Nodes (9): get_report_client(), render_pdf(), bulk_delete_observations(), BulkDeleteRequest, delete_observation(), export_observations(), generate_observations_report(), RenameRequest (+1 more)

### Community 81 - "ArchitectureEvent"
Cohesion: 0.13
Nodes (3): ArchitectureEvent, list_events(), MetricsRepository

### Community 82 - "devDependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 83 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 84 - "ServiceNode.tsx"
Cohesion: 0.15
Nodes (13): @xyflow/react, HealthStatus, NodeType, AppNodeData, ARGOCD_HEALTH_COLORS, SYNC_ICONS, NamespaceGroupNodeData, GENERIC_TAGS (+5 more)

### Community 87 - "jira.py"
Cohesion: 0.16
Nodes (7): approve_mission(), dismiss_mission(), _infer_phase(), _jira_config(), list_missions(), reanalyze_mission(), retry_mission()

### Community 88 - "get_report"
Cohesion: 0.11
Nodes (6): get_report(), list_reports(), reports_spa_no_slash(), reports_spa_with_slash(), search_reports(), _serve_spa()

### Community 90 - "gemini-sidecar/package.json"
Cohesion: 0.11
Nodes (17): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+9 more)

### Community 94 - "catalog-skills.js"
Cohesion: 0.16
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 95 - "ArchitectureGraph.tsx"
Cohesion: 0.18
Nodes (15): @dagrejs/dagre, applyDagreLayout(), applyGridLayout(), applyLayout(), ArchitectureGraphInner(), buildGraph(), computeIdHash(), edgeTypes (+7 more)

### Community 98 - "cortex/types.ts"
Cohesion: 0.17
Nodes (14): EventSource, KGServiceEntity, CortexGraphProps, GraphLoaderProps, NeuronInfoPanelProps, PulseTimelineProps, CognitiveGraphResponse, CortexHeartbeatMessage (+6 more)

### Community 99 - "observations_reporter.py"
Cohesion: 0.20
Nodes (7): _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), _sample_points(), _summarize()

### Community 101 - "generate_map.py"
Cohesion: 0.19
Nodes (6): _enumerate_gates(), _GateInfo, generate_phase_tool_map(), _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 106 - "PlanProgress.tsx"
Cohesion: 0.24
Nodes (12): ConversationTurn, BORDER_COLOR, PlanProgressProps, PlanStep, STATUS_ICON, DeferCountdownState, useDeferCountdown(), computeDeferProgress() (+4 more)

### Community 112 - "._extract_context_flags"
Cohesion: 0.15
Nodes (3): compute_dispatch_backpressure(), ContextFlags, _safe_int_env()

### Community 114 - "IncidentAdapterPort"
Cohesion: 0.15
Nodes (3): IdleTimeoutPort, IncidentAdapterPort, StateWatcherPort

### Community 115 - "create_chat_event"
Cohesion: 0.17
Nodes (3): ChatEventRequest, ChatEventResponse, create_chat_event()

### Community 117 - "JarvisMemoryPage.tsx"
Cohesion: 0.27
Nodes (12): dismissProposals(), EnhancementProposal, getHandoffReports(), getProposals(), HandoffReport, FilterMode, formatDate(), formatTime() (+4 more)

### Community 120 - "_sanitize_analysis_text"
Cohesion: 0.20
Nodes (5): _clamp_confidence(), _sanitize_analysis_text(), _strip_newlines(), _validate_analysis(), _validate_triage_entry()

### Community 121 - "CortexLiveFeed.tsx"
Cohesion: 0.24
Nodes (10): CortexHeartbeat(), CortexHeartbeatProps, ensureKeyframes(), CortexLiveFeed(), FILTER_PILLS, FilterKey, getStoredFilter(), MESSAGE_STYLES (+2 more)

### Community 122 - "testSetup.ts"
Cohesion: 0.18
Nodes (5): @tailwindcss/vite, @testing-library/react, vite, @vitejs/plugin-react, vitest

### Community 123 - "resolve_maintainer_emails"
Cohesion: 0.20
Nodes (4): _resolve_maintainer_enum(), _resolve_slack_user(), maintainer_env_key(), resolve_maintainer_emails()

### Community 124 - "is_defer_event_available"
Cohesion: 0.18
Nodes (6): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 129 - "entity_extractor.py"
Cohesion: 0.33
Nodes (5): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship

### Community 132 - "_prepare_console_tail"
Cohesion: 0.20
Nodes (4): _prepare_console_tail(), _redact_match(), _redact_secrets_in_text(), _sanitize_console_tail()

### Community 133 - "_extract_call_syntax"
Cohesion: 0.20
Nodes (5): _extract_call_syntax(), process_stream_call_syntax_buffer(), sanitize_call_syntax(), scan_call_syntax(), split_stream_call_syntax()

### Community 134 - "knowledge_graph_api.py"
Cohesion: 0.31
Nodes (4): get_kg_store(), get_service_detail(), get_stats(), list_services()

### Community 135 - "SecurityError"
Cohesion: 0.28
Nodes (3): safe_execution(), wrapper(), SecurityError

### Community 136 - "get_quota_tracker"
Cohesion: 0.22
Nodes (3): get_quota_tracker(), llm_stats(), receive_telemetry()

### Community 149 - "adf_to_markdown"
Cohesion: 0.57
Nodes (7): adf_to_markdown(), _apply_marks(), _children(), _render(), _render_list(), _render_list_item(), _render_table_like()

### Community 152 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 153 - "state.js"
Cohesion: 0.33
Nodes (4): { AGENT_ROLE }, _blackboardTurns, _inboundMessages, _teammateMessages

### Community 154 - "validate-mutations.sh"
Cohesion: 0.73
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

### Community 172 - "TicketNode.tsx"
Cohesion: 0.40
Nodes (4): STATUS_COLORS, TICKET_COLORS, TicketNodeComponent(), TicketNodeData

### Community 186 - "overrides"
Cohesion: 0.67
Nodes (3): overrides, @typescript-eslint/typescript-estree, minimatch

## Knowledge Gaps
- **13 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+8 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2199 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **119 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `brain.py`, `logging`, `ConversationTurn`, `queue.py`, `nightwatcher_tools.py`, `main.py`, `EventDocument`, `Brain`, `list_shifts`, `_is_event_closed_or_missing`, `ConversationMessage`, `BrainSkillLoader`, `slack.py`, `HeadhunterJira`, `Service`, `update_notebook_note`, `rename_observation`, `._restage_pending_signal`, `._stage_pending_signal`, `submit_feedback`, `get_notebook`, `ScheduleCreateRequest`, `TopologyRepository`, `._count_pending`, `UserContext`, `.cleanup_stale_services`, `._downsample_snapshots`, `.drain_notes`, `LiveAPIAdapter`, `.get_edge_metadata`, `.list_observations`, `auth.py`, `DashboardWSAdapter`, `observations_mgmt.py`, `lifespan`, `ArchitectureEvent`, `jira.py`, `get_report`, `EscalationRepository`, `observations_reporter.py`, `ScheduleRepository`, `create_chat_event`?**
  _High betweenness centrality (0.110) - this node is a cross-community bridge._
- **Are the 80 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 80 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `brain.py` be split into smaller, more focused modules?**
  _Cohesion score 0.026002055498458375 - nodes in this community are weakly interconnected._
- **Why does `Brain` connect `Brain` to `brain.py`, `._post_agent_recall`, `ConversationTurn`, `logging`, `BlackboardState`, `nightwatcher_tools.py`, `main.py`, `EventDocument`, `ReconcileScheduler`, `BrainSkillLoader`, `slack.py`, `._run_agent_task`, `._process_with_llm`, `dispatch.py`, `IdleTimeoutManager`, `auth.py`, `._close_and_broadcast`, `StateWatcher`, `DashboardWSAdapter`, `PulseBatch`, `ReflexSearcher`, `lifespan`, `._extract_context_flags`?**
  _High betweenness centrality (0.060) - this node is a cross-community bridge._
- **Are the 21 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 21 INFERRED edges - model-reasoned connections that need verification._
- **Should `logging` be split into smaller, more focused modules?**
  _Cohesion score 0.03804286836494221 - nodes in this community are weakly interconnected._