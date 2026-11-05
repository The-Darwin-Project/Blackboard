# Graph Report - Blackboard  (2026-11-05)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 5029 nodes · 11237 edges · 188 communities (95 shown, 93 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 938 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `3f1c8992`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BlackboardState
- logging
- main.py
- nightwatcher_tools.py
- cognitive_graph.py
- queue.py
- client.ts
- slack.py
- EventDocument
- Brain
- tool_gates.py
- EventChatPanel.tsx
- LiveAPIAdapter
- merge-guard.js
- App.tsx
- ReconcileScheduler
- EventSidebar.tsx
- hooks/index.ts
- http-handler.js
- react
- ._run_agent_task
- jenkins-mcp.js
- HeadhunterJira
- lucide-react
- fetchApi
- agents/__init__.py
- BrainSkillLoader
- GitHubPlatform
- Aligner
- _BrainToolContext
- ToolContext
- GitLabPlatform
- EventEvidence
- observations_mgmt.py
- Headhunter
- CortexGraph.tsx
- Archivist
- EventRepository
- cli-executor.js
- ._process_with_llm
- KnowledgeGraphStore
- storage-recycler.js
- JenkinsAdapter
- ConversationTurn
- EventHistory.tsx
- handlers_integration.py
- EventDrillDown.tsx
- live_api_adapter.py
- brain.py
- ._embed
- TimeKeeperPage.tsx
- ScheduleRepository
- ActiveStreamsContext.tsx
- ws-client.js
- dispatch.py
- useCortexData.ts
- server.js
- auth.py
- get_brain
- ui/package.json
- VectorStore
- StateWatcher
- ._close_and_broadcast
- context_parts.py
- tool_router.py
- AgentRegistry
- ArgoCDObserver
- useQueue.ts
- KargoObserver
- TopologyRepository
- GitHubAppAuth
- dependencies
- DashboardWSAdapter
- adf_to_markdown
- GeminiAdapter
- compilerOptions
- gemini_client.py
- claude-guard.js
- BrainIntrospectionPort
- handlers_state.py
- ._gate_check
- reconcile.py
- cli-setup.js
- VcsPlatformPort
- reports.py
- ReflexSearcher
- devDependencies
- compilerOptions
- ServiceNode.tsx
- EphemeralProvisioner
- gemini-sidecar/package.json
- ArchitectureGraph.tsx
- TokenUtilizationPage.tsx
- JenkinsObserver
- ObservationRepository
- ShiftsPage.tsx
- catalog-skills.js
- ClaudeAdapter
- observations.py
- EscalationRepository
- colors.ts
- SlackAccessGate
- generate_map.py
- OIDCKeyAdapter
- KubernetesSpawnHealthAdapter
- delete_schedule
- MultiInstallationManager
- ._extract_context_flags
- TokenMeter
- IdleTimeoutManager
- JarvisMemoryPage.tsx
- _sanitize_analysis_text
- close_event_by_user
- testSetup.ts
- ._convert_structured
- is_defer_event_available
- CortexDevPage.tsx
- SpawnPollResult
- ._post_agent_recall
- entity_extractor.py
- ._process_candidates
- _prepare_console_tail
- _extract_call_syntax
- knowledge_graph_api.py
- SmartsheetMaintainerCache
- QuotaTracker
- list_shifts
- MetricsRepository
- AsyncGitHubClient
- GitLabTokenAuth
- ._evaluate_health
- ._triage_and_build_evidence
- ._drain_once
- TimeKeeperObserver
- CortexRepository
- scripts
- state.js
- validate-mutations.sh
- DispatchMetrics
- ._wait_for_registration
- TicketNode.tsx
- Reservation
- derive_llm_priority
- has_unevaluated_close_blocker
- require-results.sh
- math
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
- _pred_jarvis_wait
- _pred_obs_plateau
- _pred_silent_park
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

## Communities (188 total, 93 thin omitted)

### Community 0 - "BlackboardState"
Cohesion: 0.01
Nodes (38): AppNode, ArchitectureEvent, ChatRequest, ChatResponse, ConversationMessage, EventInput, EventMetrics, FlowMetricsResponse (+30 more)

### Community 1 - "logging"
Cohesion: 0.03
Nodes (23): _annotation_replace(), _strip_pipeline_annotations(), _heartbeat(), _get_static_maintainer_emails(), _get_allowed_mention_authors(), _get_static_maintainer_emails(), _safe_int(), _parse_job_metadata() (+15 more)

### Community 2 - "main.py"
Cohesion: 0.03
Nodes (36): JiraIncidentAdapter, _patch_enum_fields(), set_incident_options(), set_oidc_adapter(), get_aligner(), get_architect(), get_argocd_observer(), get_developer() (+28 more)

### Community 3 - "nightwatcher_tools.py"
Cohesion: 0.04
Nodes (34): record_token_usage(), QuotaExhaustedError, RequestExceedsBurstError, ShiftIncident, ShiftInvestigation, ShiftReport, _env_float(), _env_int() (+26 more)

### Community 4 - "cognitive_graph.py"
Cohesion: 0.03
Nodes (25): get_quota_tracker(), get_blackboard(), get_pulse_tracker(), dismiss_proposals(), DismissRequest, get_all_shadow_interventions(), get_cognitive_graph(), get_cortex_activity() (+17 more)

### Community 5 - "queue.py"
Cohesion: 0.04
Nodes (42): get_archivist(), report_tampering(), aligner_pending_items(), apply_lessons(), correct_memory(), CorrectMemoryRequest, create_knowledge(), create_lesson() (+34 more)

### Community 6 - "client.ts"
Cohesion: 0.04
Nodes (80): bulkDeleteObservations(), deleteNote(), deleteObservation(), exportObservations(), ExtractedCorrection, ExtractedLesson, ExtractionResult, generateObservationsReport() (+72 more)

### Community 7 - "slack.py"
Cohesion: 0.04
Nodes (21): build_access_denied_home_view(), build_home_tab_view(), _context_line(), create_feedback_block(), extract_tables(), _replace(), format_event_summary(), format_plan_block() (+13 more)

### Community 8 - "EventDocument"
Cohesion: 0.03
Nodes (12): _close_unanswered_fc(), _build_closed_block(), build_event_header(), _build_identity_block(), _build_journal_block(), _build_mermaid_block(), _build_related_block(), _build_subject_block() (+4 more)

### Community 10 - "tool_gates.py"
Cohesion: 0.05
Nodes (78): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+70 more)

### Community 11 - "EventChatPanel.tsx"
Cohesion: 0.06
Nodes (54): closeEvent(), enforceCasualDomain(), getEventReport(), updateEventTitle(), ConversationTurn, TokenUsageDict, ConversationFeed(), ConversationFeedProps (+46 more)

### Community 13 - "merge-guard.js"
Cohesion: 0.05
Nodes (69): analyzeString(), analyzeTokens(), API_VALUED, apiTokens(), apiWriteNeedsGuard(), assignName(), bareBranchProtected(), base() (+61 more)

### Community 14 - "App.tsx"
Cohesion: 0.06
Nodes (48): oidc-client-ts, react-dom, getConfig(), getIncidents(), getWSAuthFailureCallback(), Incident, setOnUnauthorized(), setTokenGetter() (+40 more)

### Community 15 - "ReconcileScheduler"
Cohesion: 0.04
Nodes (7): FlowCollector, FairQueue, ReconcileScheduler, Trigger, QueueTrigger, ResyncTrigger, StalenessGuard

### Community 16 - "EventSidebar.tsx"
Cohesion: 0.08
Nodes (58): getClosedEvents(), getHeadhunterPending(), getJiraMissions(), HeadhunterTodo, postJiraAction(), AgentRegistryEntry, ACTION_BADGE, formatAge() (+50 more)

### Community 17 - "hooks/index.ts"
Cohesion: 0.06
Nodes (47): @tanstack/react-query, ApiError, createChatEvent(), getEvents(), getService(), getTopology(), ArchitectureEvent, ArgoCDOperation (+39 more)

### Community 18 - "http-handler.js"
Cohesion: 0.09
Nodes (58): resolveCommand(), writeAgyMcpServer(), writeClaudeMcpServer(), buildArgoCDMcpConfig(), createAppJWT(), discoverAndGenerateTokens(), _discoverAndGenerateTokensInner(), discoverInstallations() (+50 more)

### Community 19 - "react"
Cohesion: 0.07
Nodes (47): react, @uiw/react-markdown-preview, approveEvent(), rejectEvent(), submitFeedback(), CiContext, ReportFull, CiContextCard() (+39 more)

### Community 20 - "._run_agent_task"
Cohesion: 0.06
Nodes (9): on_huddle(), on_progress(), on_huddle(), on_progress(), _is_automated_nudge(), _sanitize_error_text(), _sanitize_override_reason(), _select_dispatch_tier() (+1 more)

### Community 21 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 23 - "lucide-react"
Cohesion: 0.07
Nodes (44): lucide-react, react-router-dom, getAgents(), getKargoStages(), EventEvidence, KargoStageStatus, AgentRegistryPanel(), formatConnectedSince() (+36 more)

### Community 24 - "fetchApi"
Cohesion: 0.08
Nodes (49): applyLessons(), correctMemory(), createKnowledge(), createLesson(), deleteKnowledge(), deleteLesson(), extractLessons(), fetchApi() (+41 more)

### Community 25 - "agents/__init__.py"
Cohesion: 0.06
Nodes (7): Architect, AgentClient, Developer, safe_execution(), wrapper(), SecurityError, SysAdmin

### Community 26 - "BrainSkillLoader"
Cohesion: 0.05
Nodes (3): BrainSkillLoader, _SkillCorpus, _wrap_section()

### Community 27 - "GitHubPlatform"
Cohesion: 0.05
Nodes (3): GitHubPlatform, _poll_one(), _poll_one()

### Community 30 - "ToolContext"
Cohesion: 0.08
Nodes (12): handle_message_agent(), handle_reply_to_agent(), handle_report_incident(), handle_select_agent(), _sticky_work_style(), handle_search_open_incidents(), handle_defer_event(), handle_hold_watch() (+4 more)

### Community 32 - "EventEvidence"
Cohesion: 0.07
Nodes (16): generate_event_title(), get_adapter(), _get_semaphore(), spawn_event_namer_task(), can_append_message(), handle_app_mention(), handle_create_event_modal(), handle_darwin_command() (+8 more)

### Community 33 - "observations_mgmt.py"
Cohesion: 0.06
Nodes (18): get_report_client(), _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), render_pdf(), _sample_points() (+10 more)

### Community 34 - "Headhunter"
Cohesion: 0.06
Nodes (3): Headhunter, _raise_if_systemic_failure(), _sanitize_xml_fence()

### Community 35 - "CortexGraph.tsx"
Cohesion: 0.07
Nodes (42): graphology, @react-sigma/core, @react-sigma/layout-forceatlas2, sigma, @sigma/node-square, KGServiceEntity, AGENTS, DOMAINS (+34 more)

### Community 38 - "cli-executor.js"
Cohesion: 0.09
Nodes (36): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS, STORAGE_PRETASK_TIMEOUT_MS, resolveStorageRoot }, buildCLICommand(), { checkAndRecycleStorage, pinTaskCwd, unpinTaskCwd }, CLAUDE_JSON_PATH, cp, executeCLI(), executeCLIStreaming(), FALLBACK_MODEL (+28 more)

### Community 40 - "KnowledgeGraphStore"
Cohesion: 0.09
Nodes (9): _format_graph_context(), get_graph_context(), _parse_props(), _sanitize(), translate_to_lookups(), _acquire(), KnowledgeGraphStore, _sanitize() (+1 more)

### Community 41 - "storage-recycler.js"
Cohesion: 0.08
Nodes (34): withTaskStorage(), resolveStorageRoot(), ROLE_TIMEOUTS, STORAGE_ACTIVITY_HEARTBEAT_MS, STORAGE_MAX_TIER3_DELETIONS, STORAGE_PRETASK_TIMEOUT_MS, STORAGE_RESULTS_TTL_MS, STORAGE_STALE_MS (+26 more)

### Community 42 - "JenkinsAdapter"
Cohesion: 0.06
Nodes (6): BuildDetails, JenkinsAdapter, JenkinsPlatformPort, JobResult, JobRunState, ViewScanResult

### Community 43 - "ConversationTurn"
Cohesion: 0.15
Nodes (28): handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_recall_pruned_turns(), handle_ask_release_ai(), handle_comment_jira_issue(), handle_fetch_jira_issue(), handle_greenwave() (+20 more)

### Community 44 - "EventHistory.tsx"
Cohesion: 0.11
Nodes (32): getReport(), getReports(), ReportMeta, SubjectType, CompactCardStrip(), EventHistory(), TimeRange, ViewMode (+24 more)

### Community 45 - "handlers_integration.py"
Cohesion: 0.09
Nodes (16): _alert_wrapper_retrigger(), _do_retrigger(), _get_jira_reporter(), handle_refresh_github_context(), handle_refresh_gitlab_context(), handle_refresh_kargo_context(), _is_darwin_reentrant_caller(), _resolve_maintainer_enum() (+8 more)

### Community 46 - "EventDrillDown.tsx"
Cohesion: 0.10
Nodes (32): three, getEventPulses(), EventSource, BrainCore(), CortexHeartbeat(), CortexHeartbeatProps, ensureKeyframes(), CortexLiveFeed() (+24 more)

### Community 47 - "live_api_adapter.py"
Cohesion: 0.08
Nodes (7): _build_skill_refs(), PulseBatch, PulseContext, PulsePort, PulseObserver, PulseTracker, redact_pii()

### Community 48 - "brain.py"
Cohesion: 0.09
Nodes (11): _compute_processed_up_to(), _is_seed_turn(), _resolve_escalation_scope(), jenkins_retrigger_cooldown_key(), EventType, get_event_document(), _esc(), _esc_join() (+3 more)

### Community 50 - "TimeKeeperPage.tsx"
Cohesion: 0.12
Nodes (24): createSchedule(), deleteSchedule(), getSchedules(), refineInstructions(), ScheduleCreatePayload, ScheduleItem, toggleSchedule(), updateSchedule() (+16 more)

### Community 51 - "ScheduleRepository"
Cohesion: 0.08
Nodes (4): ScheduleCreateRequest, ScheduledEvent, update_schedule(), ScheduleRepository

### Community 52 - "ActiveStreamsContext.tsx"
Cohesion: 0.12
Nodes (27): AgentStreamCard(), AgentStreamCardProps, FloatingWindow(), MessageCards(), Dashboard(), GridTile(), GridTileProps, TileType (+19 more)

### Community 53 - "ws-client.js"
Cohesion: 0.09
Nodes (26): is429Error(), {
  DEFAULT_WORK_DIR, AGENT_CLI, AGENT_MODEL, AGENT_ROLE,
  EVENT_ID, EPHEMERAL, IDLE_TIMEOUT_MS,
  CLI_429_MAX_RETRIES, CLI_429_INITIAL_DELAY_MS, CLI_429_BACKOFF_MULTIPLIER,
}, { ensureEventDocument }, { executeCLIStreaming, prepareResultsDir, is429Error }, { filterSkillsByRole, filterSkillsByMode, swapActiveRules, restoreAllSkills }, fs, handleCancel(), resetTimer() (+18 more)

### Community 54 - "dispatch.py"
Cohesion: 0.11
Nodes (10): _build_prompt(), _check_security(), consume_wake_task(), _consume(), _dispatch_timeout_s(), dispatch_to_agent(), _consume_queue(), _sanitize_stdout() (+2 more)

### Community 56 - "useCortexData.ts"
Cohesion: 0.17
Nodes (27): getCognitiveGraph(), getCortexActivity(), getKGServiceDetail(), getKGServices(), getKGStats(), getKnowledgeById(), getMemory(), getRecentPulses() (+19 more)

### Community 57 - "server.js"
Cohesion: 0.08
Nodes (18): hasRegistryCredentials(), { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, fs, path, stageEventDocument(), fetchEventDocument(), fs, { handleRequest } (+10 more)

### Community 58 - "auth.py"
Cohesion: 0.11
Nodes (11): can_approve_event(), can_override_domain(), can_rename_event(), _claims_to_user(), get_user_from_request(), get_user_from_websocket(), _normalize_email(), require_auth() (+3 more)

### Community 59 - "get_brain"
Cohesion: 0.08
Nodes (9): resolve_approval_identity(), get_brain(), KargoStageSnapshot, list_failed_stages(), approve_event(), reject_event(), RejectRequest, TitleUpdateRequest (+1 more)

### Community 60 - "ui/package.json"
Cohesion: 0.09
Nodes (25): autoprefixer, cronstrue, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, graphology-layout-forceatlas2 (+17 more)

### Community 61 - "VectorStore"
Cohesion: 0.10
Nodes (3): _decode_cursor(), _encode_cursor(), VectorStore

### Community 62 - "StateWatcher"
Cohesion: 0.10
Nodes (3): _QueueEntry, StateWatcher, _Subscription

### Community 64 - "context_parts.py"
Cohesion: 0.10
Nodes (11): _apply_sibling_signature(), build_function_response(), build_single_function_response(), compress_contents(), estimate_msg_tokens(), estimate_tokens(), extract_model_parts(), normalize_response_parts() (+3 more)

### Community 65 - "tool_router.py"
Cohesion: 0.09
Nodes (6): emit_tool_result(), _safe_int(), handle_google_web_search(), IdleTimeoutPort, IncidentAdapterPort, StateWatcherPort

### Community 66 - "AgentRegistry"
Cohesion: 0.11
Nodes (3): AgentConnection, AgentRegistry, agent_websocket_handler()

### Community 68 - "useQueue.ts"
Cohesion: 0.14
Nodes (22): getActiveEvents(), getAlignerPending(), getEventDocument(), getJenkinsPending(), getWaitingApprovalEvents(), ActiveEvent, EventDocument, MessageStatus (+14 more)

### Community 71 - "GitHubAppAuth"
Cohesion: 0.11
Nodes (3): _find_pem_file(), get_github_auth(), GitHubAppAuth

### Community 72 - "dependencies"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 74 - "adf_to_markdown"
Cohesion: 0.13
Nodes (9): _adf_to_text(), _escape_jql_string(), adf_to_markdown(), _apply_marks(), _children(), _render(), _render_list(), _render_list_item() (+1 more)

### Community 76 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 77 - "gemini_client.py"
Cohesion: 0.17
Nodes (5): FunctionCall, LLMChunk, LLMPort, LLMResponse, TokenUsage

### Community 78 - "claude-guard.js"
Cohesion: 0.14
Nodes (18): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+10 more)

### Community 79 - "BrainIntrospectionPort"
Cohesion: 0.10
Nodes (3): BrainIntrospectionPort, BrainLifecyclePort, BroadcastPort

### Community 80 - "handlers_state.py"
Cohesion: 0.13
Nodes (8): handle_classify_event(), handle_request_user_approval(), EventStatus, HealthStatus, MessageStatus, NodeType, _resolve_domain(), resolve_event_domain()

### Community 81 - "._gate_check"
Cohesion: 0.13
Nodes (7): get_user_from_slack(), handle_app_home_opened(), handle_approve(), handle_home_create_event(), handle_reject(), resolve_live_head_sha(), verify_merge_guard()

### Community 82 - "reconcile.py"
Cohesion: 0.18
Nodes (9): _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers(), main(), _parse_frontmatter() (+1 more)

### Community 83 - "cli-setup.js"
Cohesion: 0.13
Nodes (19): { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync }, filterSkillsByMode() (+11 more)

### Community 85 - "reports.py"
Cohesion: 0.12
Nodes (6): get_report(), list_reports(), reports_spa_no_slash(), reports_spa_with_slash(), search_reports(), _serve_spa()

### Community 88 - "devDependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 89 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 90 - "ServiceNode.tsx"
Cohesion: 0.15
Nodes (13): @xyflow/react, HealthStatus, NodeType, AppNodeData, ARGOCD_HEALTH_COLORS, SYNC_ICONS, NamespaceGroupNodeData, GENERIC_TAGS (+5 more)

### Community 92 - "gemini-sidecar/package.json"
Cohesion: 0.11
Nodes (17): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+9 more)

### Community 93 - "ArchitectureGraph.tsx"
Cohesion: 0.17
Nodes (16): @dagrejs/dagre, applyDagreLayout(), applyGridLayout(), applyLayout(), ArchitectureGraph(), ArchitectureGraphInner(), buildGraph(), computeIdHash() (+8 more)

### Community 94 - "TokenUtilizationPage.tsx"
Cohesion: 0.22
Nodes (14): recharts, getFlowHistory(), FlowSnapshot, FlowHistoryPage(), formatTime(), RANGES, SparkCard(), SparkCardProps (+6 more)

### Community 97 - "ShiftsPage.tsx"
Cohesion: 0.23
Nodes (16): getCurrentShift(), getShiftDetail(), getShiftsList(), ShiftReportFull, ShiftReportSummary, FailedClusterBadge(), getISOWeek(), getWeekDates() (+8 more)

### Community 98 - "catalog-skills.js"
Cohesion: 0.16
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 102 - "colors.ts"
Cohesion: 0.22
Nodes (14): KGServiceDetail, asNumber(), asString(), asStringArray(), Badge(), describeNeuron(), Hdr(), NeuronInfoPanel() (+6 more)

### Community 104 - "generate_map.py"
Cohesion: 0.19
Nodes (6): _enumerate_gates(), _GateInfo, generate_phase_tool_map(), _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 107 - "delete_schedule"
Cohesion: 0.13
Nodes (3): delete_schedule(), get_schedule(), toggle_schedule()

### Community 109 - "._extract_context_flags"
Cohesion: 0.15
Nodes (3): compute_dispatch_backpressure(), ContextFlags, _safe_int_env()

### Community 112 - "JarvisMemoryPage.tsx"
Cohesion: 0.27
Nodes (12): dismissProposals(), EnhancementProposal, getHandoffReports(), getProposals(), HandoffReport, FilterMode, formatDate(), formatTime() (+4 more)

### Community 113 - "_sanitize_analysis_text"
Cohesion: 0.20
Nodes (5): _clamp_confidence(), _sanitize_analysis_text(), _strip_newlines(), _validate_analysis(), _validate_triage_entry()

### Community 115 - "testSetup.ts"
Cohesion: 0.18
Nodes (5): @tailwindcss/vite, @testing-library/react, vite, @vitejs/plugin-react, vitest

### Community 116 - "._convert_structured"
Cohesion: 0.24
Nodes (4): _append_user_turn(), _coerce_part(), _is_function_response_part(), _validated_parts()

### Community 117 - "is_defer_event_available"
Cohesion: 0.18
Nodes (6): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 118 - "CortexDevPage.tsx"
Cohesion: 0.31
Nodes (9): CortexDevPage(), devQueryClient, MOCK_CORTEX_STATUS, MOCK_EVENT_ID, MOCK_NEURONS, MOCK_PULSE_BATCHES, MOCK_SHADOW, MOCK_THINKING (+1 more)

### Community 121 - "entity_extractor.py"
Cohesion: 0.33
Nodes (5): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship

### Community 124 - "_prepare_console_tail"
Cohesion: 0.20
Nodes (4): _prepare_console_tail(), _redact_match(), _redact_secrets_in_text(), _sanitize_console_tail()

### Community 125 - "_extract_call_syntax"
Cohesion: 0.20
Nodes (5): _extract_call_syntax(), process_stream_call_syntax_buffer(), sanitize_call_syntax(), scan_call_syntax(), split_stream_call_syntax()

### Community 126 - "knowledge_graph_api.py"
Cohesion: 0.31
Nodes (4): get_kg_store(), get_service_detail(), get_stats(), list_services()

### Community 139 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 140 - "state.js"
Cohesion: 0.33
Nodes (4): { AGENT_ROLE }, _blackboardTurns, _inboundMessages, _teammateMessages

### Community 141 - "validate-mutations.sh"
Cohesion: 0.73
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

### Community 149 - "TicketNode.tsx"
Cohesion: 0.40
Nodes (4): STATUS_COLORS, TICKET_COLORS, TicketNodeComponent(), TicketNodeData

### Community 164 - "overrides"
Cohesion: 0.67
Nodes (3): overrides, @typescript-eslint/typescript-estree, minimatch

## Knowledge Gaps
- **13 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+8 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2201 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **93 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `logging`, `main.py`, `nightwatcher_tools.py`, `cognitive_graph.py`, `queue.py`, `list_shifts`, `slack.py`, `EventDocument`, `Brain`, `LiveAPIAdapter`, `._restage_pending_signal`, `._stage_pending_signal`, `._count_pending`, `HeadhunterJira`, `BrainSkillLoader`, `.cleanup_stale_services`, `._commit_pending_signal`, `.drain_notes`, `.get_edge_metadata`, `EventEvidence`, `observations_mgmt.py`, `ConversationTurn`, `live_api_adapter.py`, `brain.py`, `ScheduleRepository`, `get_brain`, `tool_router.py`, `DashboardWSAdapter`, `handlers_state.py`, `reports.py`, `observations.py`, `delete_schedule`, `close_event_by_user`?**
  _High betweenness centrality (0.105) - this node is a cross-community bridge._
- **Are the 80 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 80 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.012142646625405247 - nodes in this community are weakly interconnected._
- **Why does `Brain` connect `Brain` to `BlackboardState`, `main.py`, `nightwatcher_tools.py`, `slack.py`, `EventDocument`, `ReconcileScheduler`, `._run_agent_task`, `agents/__init__.py`, `BrainSkillLoader`, `EventEvidence`, `Archivist`, `._process_with_llm`, `ConversationTurn`, `live_api_adapter.py`, `brain.py`, `StateWatcher`, `._close_and_broadcast`, `DashboardWSAdapter`, `BrainIntrospectionPort`, `handlers_state.py`, `ReflexSearcher`, `._extract_context_flags`, `IdleTimeoutManager`, `._post_agent_recall`?**
  _High betweenness centrality (0.047) - this node is a cross-community bridge._
- **Are the 21 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 21 INFERRED edges - model-reasoned connections that need verification._
- **Should `logging` be split into smaller, more focused modules?**
  _Cohesion score 0.03398010440263961 - nodes in this community are weakly interconnected._