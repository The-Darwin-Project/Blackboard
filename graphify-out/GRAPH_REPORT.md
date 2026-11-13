# Graph Report - Blackboard  (2026-11-13)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 5179 nodes · 11612 edges · 214 communities (105 shown, 109 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 950 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `bb5d0a25`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BlackboardState
- client.ts
- queue.py
- ConversationTurn
- Archivist
- WorkspaceInspector.tsx
- brain.py
- os
- Brain
- logging
- App.tsx
- tool_gates.py
- EventSidebar.tsx
- AgentRegistry
- auth.py
- ._process_with_llm
- ReconcileScheduler
- main.py
- react
- http-handler.js
- jenkins-mcp.js
- useMemory.ts
- EventDocument
- Service
- BrainSkillLoader
- FastAPI
- _BrainToolContext
- slack.py
- lucide-react
- merge-guard.js
- KnowledgeGraphStore
- cli-executor.js
- storage-recycler.js
- SlackChannel
- JenkinsAdapter
- EventRepository
- EventHistory.tsx
- create_adapter
- Aligner
- GitHubPlatform
- AgentClient
- GeminiAdapter
- JarvisMemoryPage.tsx
- GitLabPlatform
- llm/__init__.py
- TimeKeeperPage.tsx
- Headhunter
- ws-client.js
- event_to_markdown
- ui/package.json
- ._build_contents
- StateWatcher
- EventDrillDown.tsx
- ._authorize_plan_decision
- useCortexData.ts
- jenkins_observer.py
- CortexGraph.tsx
- server.js
- adf_to_markdown
- ._close_and_broadcast
- context_parts.py
- cognitive_graph.py
- .list_observations
- state/__init__.py
- quota_tracker.py
- types.py
- ArgoCDObserver
- TokenUtilizationPage.tsx
- ._get_manager
- JenkinsObserver
- KargoObserver
- TopologyRepository
- dependencies
- NodeInspector.tsx
- nightwatcher_tools.py
- GitHubAppAuth
- compilerOptions
- claude-guard.js
- DashboardWSAdapter
- BrainIntrospectionPort
- NightwatcherObserver
- NeuronInfoPanel.tsx
- reconcile.py
- VcsPlatformPort
- reports.py
- OpsStateContext.tsx
- observations_mgmt.py
- cli-setup.js
- EventEvidence
- ScheduleCreateRequest
- ReflexSearcher
- devDependencies
- compilerOptions
- nightwatcher.py
- gemini-sidecar/package.json
- ArchitectureGraph.tsx
- ServiceNode.tsx
- LiveAPIAdapter
- EphemeralProvisioner
- gemini_client.py
- TokenMeter
- ObservationRepository
- cortex/types.ts
- catalog-skills.js
- EscalationRepository
- ShiftsPage.tsx
- nightwatcher_prompt.py
- generate_map.py
- OIDCKeyAdapter
- KubernetesSpawnHealthAdapter
- IdleTimeoutManager
- observations_reporter.py
- ScheduleRepository
- SlackAccessGate
- ephemeral_provisioner.py
- analyzeTokens
- FilterRule
- handlers_planning.py
- IncidentAdapterPort
- MultiInstallationManager
- HeadhunterJira
- CortexLiveFeed.tsx
- testSetup.ts
- is_defer_event_available
- gitGuard
- parseShell
- scheduling/__init__.py
- _is_event_closed_or_missing
- ._post_agent_recall
- entity_extractor.py
- ._process_candidates
- ._triage_and_build_evidence
- ._drain_once
- classifyTool
- SpawnPollResult
- SmartsheetMaintainerCache
- .has_reeval_signal
- shifts.py
- AsyncGitHubClient
- GitLabTokenAuth
- ._evaluate_health
- LLMStreamInterChunkTimeoutError
- ConversationMessage
- ._run_report_cart
- TimeKeeperObserver
- CortexRepository
- validate-mutations.sh
- ._detect_repetition_collapse
- ._run_analysis_loop
- scripts
- state.js
- io
- ._process_message
- DispatchMetrics
- is_jarvis_acknowledgment
- incidents.py
- rename_observation
- _BatchContext
- ._wait_for_registration
- get_notebook
- TicketNode.tsx
- classify
- require-results.sh
- _PlanDecision
- report_tampering
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
- _pred_unevaluated_close
- _tools_wait_loop

## God Nodes (most connected - your core abstractions)
1. `BlackboardState` - 285 edges
2. `Brain` - 156 edges
3. `ConversationTurn` - 125 edges
4. `ToolContext` - 103 edges
5. `GateContext` - 94 edges
6. `react` - 85 edges
7. `EventDocument` - 79 edges
8. `fetchApi()` - 66 edges
9. `lifespan()` - 65 edges
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

## Communities (214 total, 109 thin omitted)

### Community 1 - "client.ts"
Cohesion: 0.04
Nodes (97): ApiError, bulkDeleteObservations(), deleteNote(), deleteObservation(), exportObservations(), ExtractionResult, fetchApi(), generateObservationsReport() (+89 more)

### Community 2 - "queue.py"
Cohesion: 0.03
Nodes (52): resolve_approval_identity(), get_archivist(), get_brain(), get_cognitive_graph(), aligner_pending_items(), apply_lessons(), approve_event(), close_event_by_user() (+44 more)

### Community 3 - "ConversationTurn"
Cohesion: 0.06
Nodes (44): emit_tool_result(), _safe_int(), handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_recall_pruned_turns(), handle_message_agent(), handle_reply_to_agent() (+36 more)

### Community 4 - "Archivist"
Cohesion: 0.04
Nodes (4): Archivist, _decode_cursor(), _encode_cursor(), VectorStore

### Community 5 - "WorkspaceInspector.tsx"
Cohesion: 0.04
Nodes (71): updateEventTitle(), CiContext, ConversationTurn, TokenUsageDict, CiContextCard(), CiContextCardProps, ConsoleTailBlock(), FailedJobRow() (+63 more)

### Community 6 - "brain.py"
Cohesion: 0.04
Nodes (34): _compute_processed_up_to(), _is_seed_turn(), _resolve_escalation_scope(), has_unevaluated_close_blocker(), AppNode, ChatRequest, ChatResponse, EventInput (+26 more)

### Community 7 - "os"
Cohesion: 0.04
Nodes (31): _get_jira_reporter(), handle_ask_release_ai(), handle_comment_jira_issue(), handle_fetch_jira_issue(), handle_greenwave(), handle_transition_jira_issue(), _is_darwin_reentrant_caller(), jenkins_retrigger_cooldown_key() (+23 more)

### Community 9 - "logging"
Cohesion: 0.04
Nodes (8): _sanitize_lesson_text(), PulseBatch, PulseContext, PulsePort, PulseObserver, PulseTracker, _load_name_mapping(), redact_pii()

### Community 10 - "App.tsx"
Cohesion: 0.05
Nodes (61): oidc-client-ts, react-dom, react-router-dom, @tanstack/react-query, createChatEvent(), getConfig(), getEvents(), getIncidents() (+53 more)

### Community 11 - "tool_gates.py"
Cohesion: 0.05
Nodes (78): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+70 more)

### Community 12 - "EventSidebar.tsx"
Cohesion: 0.07
Nodes (68): getJiraMissions(), HeadhunterTodo, postJiraAction(), ChatInput(), DeferCountdownBar(), ACTION_BADGE, formatAge(), HeadhunterQueuePanel() (+60 more)

### Community 13 - "AgentRegistry"
Cohesion: 0.05
Nodes (17): AgentConnection, AgentRegistry, agent_websocket_handler(), _heartbeat(), _build_prompt(), _check_security(), consume_wake_task(), _consume() (+9 more)

### Community 14 - "auth.py"
Cohesion: 0.04
Nodes (22): can_approve_event(), can_override_domain(), can_rename_event(), _claims_to_user(), get_user_from_request(), get_user_from_slack(), get_user_from_websocket(), _normalize_email() (+14 more)

### Community 15 - "._process_with_llm"
Cohesion: 0.05
Nodes (10): on_huddle(), on_progress(), on_huddle(), on_progress(), _is_automated_nudge(), _sanitize_error_text(), _sanitize_override_reason(), _select_dispatch_tier() (+2 more)

### Community 16 - "ReconcileScheduler"
Cohesion: 0.04
Nodes (8): FlowSnapshot, FlowCollector, FairQueue, ReconcileScheduler, Trigger, QueueTrigger, ResyncTrigger, StalenessGuard

### Community 17 - "main.py"
Cohesion: 0.04
Nodes (31): set_incident_options(), set_oidc_adapter(), get_aligner(), get_architect(), get_argocd_observer(), get_developer(), get_kargo_observer(), get_sysadmin() (+23 more)

### Community 18 - "react"
Cohesion: 0.07
Nodes (54): react, @uiw/react-markdown-preview, approveEvent(), closeEvent(), enforceCasualDomain(), getEventReport(), rejectEvent(), submitFeedback() (+46 more)

### Community 19 - "http-handler.js"
Cohesion: 0.08
Nodes (62): is429Error(), registerMCPsAndHooks(), resolveCommand(), writeAgyMcpServer(), writeClaudeMcpServer(), parsePositiveInt(), buildArgoCDMcpConfig(), createAppJWT() (+54 more)

### Community 20 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 21 - "useMemory.ts"
Cohesion: 0.07
Nodes (50): applyLessons(), correctMemory(), createKnowledge(), createLesson(), deleteKnowledge(), deleteLesson(), ExtractedCorrection, ExtractedLesson (+42 more)

### Community 23 - "Service"
Cohesion: 0.05
Nodes (7): Service, get_graph_data(), get_mermaid_diagram(), get_service_details(), get_topology(), list_services(), calculate_health_from_argocd()

### Community 24 - "BrainSkillLoader"
Cohesion: 0.05
Nodes (4): _parse_positive_int_env(), BrainSkillLoader, _SkillCorpus, _wrap_section()

### Community 25 - "FastAPI"
Cohesion: 0.05
Nodes (11): get_kg_store(), dex_proxy(), FeedbackRequest, submit_feedback(), KargoStageSnapshot, list_failed_stages(), get_service_detail(), get_stats() (+3 more)

### Community 27 - "slack.py"
Cohesion: 0.06
Nodes (20): build_access_denied_home_view(), build_event_report_md(), build_home_tab_view(), _context_line(), create_feedback_block(), extract_tables(), _replace(), format_plan_block() (+12 more)

### Community 28 - "lucide-react"
Cohesion: 0.08
Nodes (34): lucide-react, AgentStreamCard(), AgentStreamCardProps, MessageCards(), ErrorBoundary, ErrorBoundaryProps, ErrorBoundaryState, CopyButton() (+26 more)

### Community 29 - "merge-guard.js"
Cohesion: 0.04
Nodes (46): API_VALUED, ARGO_MUTATING, ARGO_READ_SUB, ARGO_READ_TOP, BODY_FLAG, BROWSER_READ, CTX, ENV_BUILTINS (+38 more)

### Community 30 - "KnowledgeGraphStore"
Cohesion: 0.08
Nodes (9): _format_graph_context(), get_graph_context(), _parse_props(), _sanitize(), translate_to_lookups(), _acquire(), KnowledgeGraphStore, _sanitize() (+1 more)

### Community 31 - "cli-executor.js"
Cohesion: 0.09
Nodes (37): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, MAX_TASK_WALL_MS, MAX_TIMER_MS, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS, STORAGE_PRETASK_TIMEOUT_MS, resolveStorageRoot }, buildCLICommand(), buildTimeoutResult(), { checkAndRecycleStorage, pinTaskCwd, unpinTaskCwd }, CLAUDE_JSON_PATH, cp, createInactivityWatchdog(), executeCLI() (+29 more)

### Community 32 - "storage-recycler.js"
Cohesion: 0.08
Nodes (37): withTaskStorage(), MAX_TASK_WALL_MS, parseTimerMs(), resolveStorageRoot(), resolveTimeoutMs(), ROLE_TIMEOUTS, STORAGE_ACTIVITY_HEARTBEAT_MS, STORAGE_MAX_TIER3_DELETIONS (+29 more)

### Community 34 - "JenkinsAdapter"
Cohesion: 0.06
Nodes (6): BuildDetails, JenkinsAdapter, JenkinsPlatformPort, JobResult, JobRunState, ViewScanResult

### Community 36 - "EventHistory.tsx"
Cohesion: 0.11
Nodes (33): getReport(), getReports(), ReportMeta, SubjectType, CompactCardStrip(), EventHistory(), TimeRange, ViewMode (+25 more)

### Community 37 - "create_adapter"
Cohesion: 0.08
Nodes (12): generate_event_title(), get_adapter(), _get_semaphore(), spawn_event_namer_task(), create_adapter(), can_append_message(), ChatEventRequest, ChatEventResponse (+4 more)

### Community 40 - "AgentClient"
Cohesion: 0.07
Nodes (4): Architect, AgentClient, Developer, SysAdmin

### Community 41 - "GeminiAdapter"
Cohesion: 0.10
Nodes (6): _attach_signature_to_parts(), _extract_call_syntax(), _extract_part_signature(), GeminiAdapter, _is_empty_sig_carrier(), _part_has_fc()

### Community 42 - "JarvisMemoryPage.tsx"
Cohesion: 0.11
Nodes (31): dismissProposals(), EnhancementProposal, getHandoffReports(), getProposals(), HandoffReport, Dashboard(), FilterMode, formatDate() (+23 more)

### Community 44 - "llm/__init__.py"
Cohesion: 0.10
Nodes (6): ClaudeAdapter, FunctionCall, LLMChunk, LLMPort, LLMResponse, TokenUsage

### Community 45 - "TimeKeeperPage.tsx"
Cohesion: 0.12
Nodes (24): createSchedule(), deleteSchedule(), getSchedules(), refineInstructions(), ScheduleCreatePayload, ScheduleItem, toggleSchedule(), updateSchedule() (+16 more)

### Community 46 - "Headhunter"
Cohesion: 0.08
Nodes (3): Headhunter, _raise_if_systemic_failure(), _sanitize_xml_fence()

### Community 47 - "ws-client.js"
Cohesion: 0.10
Nodes (26): clearIdleTimer(), {
  DEFAULT_WORK_DIR, AGENT_CLI, AGENT_MODEL, AGENT_ROLE,
  EVENT_ID, EPHEMERAL, IDLE_TIMEOUT_MS,
  CLI_429_MAX_RETRIES, CLI_429_INITIAL_DELAY_MS, CLI_429_BACKOFF_MULTIPLIER,
  resolveTimeoutMs, parsePositiveInt, MAX_TASK_WALL_MS, MAX_TIMER_MS,
}, { ensureEventDocument }, { executeCLIStreaming, prepareResultsDir, is429Error }, { filterSkillsByRole, filterSkillsByMode, swapActiveRules, restoreAllSkills }, fs, handleCancel(), handleTask() (+18 more)

### Community 48 - "event_to_markdown"
Cohesion: 0.08
Nodes (7): ArchitectureEvent, get_event_document(), list_events(), MetricsRepository, _esc(), _esc_join(), event_to_markdown()

### Community 49 - "ui/package.json"
Cohesion: 0.08
Nodes (29): autoprefixer, cronstrue, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, graphology-layout-forceatlas2 (+21 more)

### Community 50 - "._build_contents"
Cohesion: 0.07
Nodes (4): _close_unanswered_fc(), compute_dispatch_backpressure(), ContextFlags, _safe_int_env()

### Community 51 - "StateWatcher"
Cohesion: 0.09
Nodes (4): PollFn, _QueueEntry, StateWatcher, _Subscription

### Community 52 - "EventDrillDown.tsx"
Cohesion: 0.13
Nodes (23): three, getEventPulses(), BrainCore(), CortexDevPage(), devQueryClient, CortexLiveFeedProps, EventDrillDown(), EventDrillDownProps (+15 more)

### Community 53 - "._authorize_plan_decision"
Cohesion: 0.12
Nodes (8): format_event_summary(), handle_app_home_opened(), handle_app_mention(), handle_create_event_modal(), handle_darwin_command(), handle_home_create_event(), handle_reject(), on_dm_message()

### Community 54 - "useCortexData.ts"
Cohesion: 0.17
Nodes (26): getCognitiveGraph(), getCortexActivity(), getKGServiceDetail(), getKGServices(), getKGStats(), getKnowledgeById(), getMemory(), getRecentPulses() (+18 more)

### Community 55 - "jenkins_observer.py"
Cohesion: 0.11
Nodes (11): _annotation_replace(), _strip_pipeline_annotations(), _clamp_confidence(), _prepare_console_tail(), _redact_match(), _redact_secrets_in_text(), _sanitize_analysis_text(), _sanitize_console_tail() (+3 more)

### Community 56 - "CortexGraph.tsx"
Cohesion: 0.14
Nodes (25): graphology, eventColor(), getExecutiveNeurons(), getStructuralEdges(), DEFAULT_TYPE_BUDGET, evictLru(), KNOWLEDGE_RING, KNOWLEDGE_RING_TYPES (+17 more)

### Community 57 - "server.js"
Cohesion: 0.09
Nodes (18): { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, ensureEventDocument(), fs, path, stageEventDocument(), fetchEventDocument(), fs, { handleRequest } (+10 more)

### Community 58 - "adf_to_markdown"
Cohesion: 0.12
Nodes (10): _adf_to_text(), _escape_jql_string(), JiraIncidentAdapter, adf_to_markdown(), _apply_marks(), _children(), _render(), _render_list() (+2 more)

### Community 60 - "context_parts.py"
Cohesion: 0.13
Nodes (12): _apply_sibling_signature(), build_function_response(), build_single_function_response(), compress_contents(), estimate_msg_tokens(), estimate_tokens(), extract_model_parts(), _get_part_sig() (+4 more)

### Community 61 - "cognitive_graph.py"
Cohesion: 0.12
Nodes (11): get_blackboard(), get_pulse_tracker(), dismiss_proposals(), DismissRequest, get_all_shadow_interventions(), get_cortex_activity(), get_cortex_status(), get_event_shadow_interventions() (+3 more)

### Community 62 - ".list_observations"
Cohesion: 0.08
Nodes (4): get_all_journal(), get_service_journal(), get_event_observations(), get_global_observations()

### Community 63 - "state/__init__.py"
Cohesion: 0.11
Nodes (4): sanitize_redis_port(), close_redis(), get_redis(), RedisClient

### Community 64 - "quota_tracker.py"
Cohesion: 0.11
Nodes (5): get_quota_tracker(), QuotaExhaustedError, QuotaTracker, RequestExceedsBurstError, Reservation

### Community 65 - "types.py"
Cohesion: 0.11
Nodes (12): derive_llm_priority(), _get_timeout_env_warned(), _get_timeout_order_warned(), parse_timeout_env(), _patch_enum_fields(), process_stream_call_syntax_buffer(), resolve_stream_timeouts(), sanitize_call_syntax() (+4 more)

### Community 67 - "TokenUtilizationPage.tsx"
Cohesion: 0.14
Nodes (19): recharts, getFlowHistory(), FlowSnapshot, ObservationSeries, FlowHistoryPage(), formatTime(), RANGES, SparkCard() (+11 more)

### Community 72 - "dependencies"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 73 - "NodeInspector.tsx"
Cohesion: 0.13
Nodes (21): ArchitectureEvent, ArgoCDOperation, EVENT_LABELS, EventItem(), EventItemProps, healthTone(), lastOperationSummary(), NodeInspector() (+13 more)

### Community 74 - "nightwatcher_tools.py"
Cohesion: 0.17
Nodes (12): ShiftIncident, ShiftInvestigation, execute_tool(), _handle_consult_deep_memory(), _handle_dispatch_investigation(), _handle_extend_incident(), _handle_get_event_report(), _handle_post_shift_summary() (+4 more)

### Community 76 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 77 - "claude-guard.js"
Cohesion: 0.14
Nodes (18): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+10 more)

### Community 79 - "BrainIntrospectionPort"
Cohesion: 0.10
Nodes (3): BrainIntrospectionPort, BrainLifecyclePort, BroadcastPort

### Community 80 - "NightwatcherObserver"
Cohesion: 0.14
Nodes (3): ShiftReport, _env_float(), NightwatcherObserver

### Community 81 - "NeuronInfoPanel.tsx"
Cohesion: 0.12
Nodes (20): AGENTS, DOMAINS, HEMISPHERE_X, NEURON_DESCRIPTIONS, PHASE_SKILL_FOLDERS, PHASE_TOOL_PRIORITY, PHASES, StructuralEdge (+12 more)

### Community 82 - "reconcile.py"
Cohesion: 0.18
Nodes (9): _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers(), main(), _parse_frontmatter() (+1 more)

### Community 85 - "reports.py"
Cohesion: 0.12
Nodes (6): get_report(), list_reports(), reports_spa_no_slash(), reports_spa_with_slash(), search_reports(), _serve_spa()

### Community 86 - "OpsStateContext.tsx"
Cohesion: 0.16
Nodes (18): getAgents(), getKargoStages(), AgentRegistryEntry, EventEvidence, KargoStageStatus, AgentRegistryPanel(), formatConnectedSince(), AgentGroups (+10 more)

### Community 87 - "observations_mgmt.py"
Cohesion: 0.14
Nodes (9): get_report_client(), render_pdf(), bulk_delete_observations(), BulkDeleteRequest, delete_observation(), export_observations(), generate_observations_report(), RenameRequest (+1 more)

### Community 88 - "cli-setup.js"
Cohesion: 0.13
Nodes (18): { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync }, filterSkillsByMode() (+10 more)

### Community 89 - "EventEvidence"
Cohesion: 0.17
Nodes (11): _build_closed_block(), build_event_header(), _build_identity_block(), _build_journal_block(), _build_mermaid_block(), _build_related_block(), _build_subject_block(), _build_timing_block() (+3 more)

### Community 92 - "devDependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 93 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 94 - "nightwatcher.py"
Cohesion: 0.15
Nodes (7): record_token_usage(), _env_int(), _fallback_platform(), _handle_declare_clusters(), reconcile_cluster_plan(), salvage_cluster_plan(), validate_cluster_plan()

### Community 95 - "gemini-sidecar/package.json"
Cohesion: 0.11
Nodes (18): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+10 more)

### Community 96 - "ArchitectureGraph.tsx"
Cohesion: 0.16
Nodes (17): @dagrejs/dagre, applyDagreLayout(), applyGridLayout(), applyLayout(), ArchitectureGraph(), ArchitectureGraphInner(), buildGraph(), computeIdHash() (+9 more)

### Community 97 - "ServiceNode.tsx"
Cohesion: 0.15
Nodes (13): @xyflow/react, HealthStatus, NodeType, AppNodeData, ARGOCD_HEALTH_COLORS, SYNC_ICONS, NamespaceGroupNodeData, GENERIC_TAGS (+5 more)

### Community 101 - "gemini_client.py"
Cohesion: 0.13
Nodes (8): _append_user_turn(), _clone_part_with_sig(), _coerce_part(), _decode_sig_bytes(), _is_function_response_part(), _parse_drain_timeout(), _strip_user_thought_signature(), _validated_parts()

### Community 104 - "cortex/types.ts"
Cohesion: 0.16
Nodes (16): ActiveEvent, EventSource, KGServiceEntity, CortexGraphProps, GraphLoaderProps, NeuronInfoPanelProps, PulseTimelineProps, CognitiveGraphResponse (+8 more)

### Community 105 - "catalog-skills.js"
Cohesion: 0.16
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 107 - "ShiftsPage.tsx"
Cohesion: 0.25
Nodes (15): getCurrentShift(), getShiftDetail(), getShiftsList(), ShiftReportFull, ShiftReportSummary, FailedClusterBadge(), getISOWeek(), getWeekDates() (+7 more)

### Community 108 - "nightwatcher_prompt.py"
Cohesion: 0.15
Nodes (7): build_manifest_table(), build_report_iteration_prompt(), build_summary_prompt(), build_system_prompt(), extract_event_links(), extract_full_links(), _normalize_gitlab_host()

### Community 109 - "generate_map.py"
Cohesion: 0.19
Nodes (6): _enumerate_gates(), _GateInfo, generate_phase_tool_map(), _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 113 - "observations_reporter.py"
Cohesion: 0.21
Nodes (7): _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), _sample_points(), _summarize()

### Community 119 - "analyzeTokens"
Cohesion: 0.19
Nodes (13): analyzeString(), analyzeTokens(), assignName(), base(), combineCategories(), configEnvGuard(), configFileWriteGuard(), hasSubseq() (+5 more)

### Community 121 - "handlers_planning.py"
Cohesion: 0.24
Nodes (6): _auto_complete_step(), _canonical_role(), handle_get_plan_progress(), _is_failed_turn(), _is_orchestrator_turn(), _normalize_step_id()

### Community 122 - "IncidentAdapterPort"
Cohesion: 0.15
Nodes (3): IdleTimeoutPort, IncidentAdapterPort, StateWatcherPort

### Community 127 - "CortexLiveFeed.tsx"
Cohesion: 0.24
Nodes (10): CortexHeartbeat(), CortexHeartbeatProps, ensureKeyframes(), CortexLiveFeed(), FILTER_PILLS, FilterKey, getStoredFilter(), MESSAGE_STYLES (+2 more)

### Community 128 - "testSetup.ts"
Cohesion: 0.18
Nodes (5): @tailwindcss/vite, @testing-library/react, vite, @vitejs/plugin-react, vitest

### Community 129 - "is_defer_event_available"
Cohesion: 0.18
Nodes (6): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 130 - "gitGuard"
Cohesion: 0.29
Nodes (10): bareBranchProtected(), configWriteGuard(), externalGitCommand(), gitGuard(), gitQuery(), isProtected(), normRef(), pushGuard() (+2 more)

### Community 131 - "parseShell"
Cohesion: 0.33
Nodes (10): bodySubstitutions(), decodeAnsiC(), isArrayAssignPrefix(), isWordStart(), matchBacktick(), matchParen(), parseShell(), readHeredocStart() (+2 more)

### Community 132 - "scheduling/__init__.py"
Cohesion: 0.29
Nodes (4): GitHubPrRef, GitLabMrRef, GitLabPipelineRef, KargoStageRef

### Community 137 - "entity_extractor.py"
Cohesion: 0.33
Nodes (5): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship

### Community 142 - "classifyTool"
Cohesion: 0.31
Nodes (9): apiTokens(), apiWriteNeedsGuard(), branchValues(), classifyTool(), hasOpaqueTarget(), httpGuard(), httpMethod(), isReadMethod() (+1 more)

### Community 146 - "shifts.py"
Cohesion: 0.28
Nodes (3): get_current_shift(), get_shift_detail(), list_shifts()

### Community 154 - "LLMStreamInterChunkTimeoutError"
Cohesion: 0.25
Nodes (4): LLMStreamInterChunkTimeoutError, LLMStreamTimeoutError, LLMStreamTotalTimeoutError, LLMStreamTTFBTimeoutError

### Community 156 - "._run_report_cart"
Cohesion: 0.25
Nodes (3): build_extend_tool(), build_report_tool(), build_summary_tool()

### Community 159 - "validate-mutations.sh"
Cohesion: 0.57
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

### Community 163 - "._run_analysis_loop"
Cohesion: 0.33
Nodes (3): _append_user_turn(), _finalize_analysis_handover(), get_phase_tools()

### Community 164 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 165 - "state.js"
Cohesion: 0.33
Nodes (4): { AGENT_ROLE }, _blackboardTurns, _inboundMessages, _teammateMessages

### Community 180 - "TicketNode.tsx"
Cohesion: 0.40
Nodes (4): STATUS_COLORS, TICKET_COLORS, TicketNodeComponent(), TicketNodeData

### Community 181 - "classify"
Cohesion: 0.50
Nodes (4): classify(), main(), shellCategory(), shellNeedsGuard()

### Community 189 - "overrides"
Cohesion: 0.67
Nodes (3): overrides, @typescript-eslint/typescript-estree, minimatch

## Knowledge Gaps
- **13 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+8 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2270 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **109 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `queue.py`, `ConversationTurn`, `_is_event_closed_or_missing`, `brain.py`, `os`, `Brain`, `logging`, `AgentRegistry`, `auth.py`, `ReconcileScheduler`, `main.py`, `shifts.py`, `EventDocument`, `Service`, `BrainSkillLoader`, `FastAPI`, `slack.py`, `ConversationMessage`, `create_adapter`, `rename_observation`, `._restage_pending_signal`, `event_to_markdown`, `._stage_pending_signal`, `get_notebook`, `jenkins_observer.py`, `.cleanup_stale_services`, `report_tampering`, `cognitive_graph.py`, `.list_observations`, `state/__init__.py`, `nightwatcher_tools.py`, `DashboardWSAdapter`, `NightwatcherObserver`, `reports.py`, `observations_mgmt.py`, `EventEvidence`, `ScheduleCreateRequest`, `nightwatcher.py`, `LiveAPIAdapter`, `observations_reporter.py`, `ScheduleRepository`, `HeadhunterJira`?**
  _High betweenness centrality (0.123) - this node is a cross-community bridge._
- **Are the 80 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 80 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.015501519756838906 - nodes in this community are weakly interconnected._
- **Why does `Brain` connect `Brain` to `BlackboardState`, `ConversationTurn`, `brain.py`, `._resolve_llm_params`, `._post_agent_recall`, `logging`, `AgentRegistry`, `._process_with_llm`, `ReconcileScheduler`, `main.py`, `EventDocument`, `BrainSkillLoader`, `slack.py`, `._detect_repetition_collapse`, `._is_rate_limit`, `._build_contents`, `StateWatcher`, `._resolve_grounding_urls`, `._close_and_broadcast`, `DashboardWSAdapter`, `BrainIntrospectionPort`, `EventEvidence`, `ReflexSearcher`, `IdleTimeoutManager`?**
  _High betweenness centrality (0.044) - this node is a cross-community bridge._
- **Are the 19 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 19 INFERRED edges - model-reasoned connections that need verification._
- **Should `client.ts` be split into smaller, more focused modules?**
  _Cohesion score 0.035398230088495575 - nodes in this community are weakly interconnected._