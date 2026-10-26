# Graph Report - Blackboard  (2026-10-26)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 4866 nodes · 10807 edges · 210 communities (91 shown, 119 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 920 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `3b2015b5`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BlackboardState
- brain.py
- models.py
- ConversationTurn
- EventChatPanel.tsx
- client.ts
- nightwatcher_tools.py
- useCortexData.ts
- tool_gates.py
- OpsStateContext.tsx
- App.tsx
- merge-guard.js
- Brain
- react
- EventHistory.tsx
- jenkins-mcp.js
- EventSidebar.tsx
- EventDocument
- ._run_agent_task
- Aligner
- _BrainToolContext
- GitLabPlatform
- JarvisMemoryPage.tsx
- queue.py
- EventRepository
- credentials.js
- JenkinsObserver
- storage-recycler.js
- JenkinsAdapter
- .get_event
- cli-executor.js
- KnowledgeGraphStore
- hooks/index.ts
- GitHubPlatform
- AgentClient
- observations_reporter.py
- ArchitectureGraph.tsx
- lifespan
- ._process_with_llm
- .get_service
- main.py
- TimeKeeperPage.tsx
- Headhunter
- ui/package.json
- ws-client.js
- auth.py
- ._gate_check
- SlackChannel
- handlers_dispatch.py
- server.js
- CortexGraph.tsx
- LiveAPIAdapter
- ChatInput.tsx
- StateWatcher
- adf_to_markdown
- KubernetesSpawnHealthAdapter
- GeminiAdapter
- ArgoCDObserver
- ReconcileScheduler
- BrainSkillLoader
- ._get_manager
- KargoObserver
- TopologyRepository
- dependencies
- reconcile.py
- http-handler.js
- cognitive_graph.py
- compilerOptions
- llm/__init__.py
- claude-guard.js
- slack.py
- TokenUtilizationPage.tsx
- AgentRegistry
- ._build_system_prompt
- _sanitize_analysis_text
- format_event_summary
- GitHubAppAuth
- cli-setup.js
- VcsPlatformPort
- PulseBatch
- jira.py
- ._process_event_inner
- ReflexSearcher
- EphemeralProvisioner
- UserContext
- FairQueue
- devDependencies
- compilerOptions
- dispatch_to_agent
- DashboardWSAdapter
- ClaudeAdapter
- get_report
- gemini-sidecar/package.json
- ._build_contents
- ObservationRepository
- catalog-skills.js
- OIDCKeyAdapter
- Archivist
- VectorStore
- SlackAccessGate
- generate_map.py
- approve_event
- src/ports.py
- ._discover
- EscalationRepository
- ._execute_function_call
- .start_event_loop
- QuotaTracker
- ScheduleRepository
- close_event_by_user
- vcs_approval.py
- RedisClient
- MultiInstallationManager
- scheduling/__init__.py
- .scroll
- ._extract_context_flags
- HeadhunterJira
- TokenMeter
- IncidentAdapterPort
- ._send_turn_to_thread
- IdleTimeoutManager
- ._github_poll_and_process
- is_defer_event_available
- cortex-constants.ts
- NeuronInfoPanel.tsx
- spawn_health.py
- vite.config.ts
- entity_extractor.py
- SpawnHealthPort
- has_unevaluated_close_blocker
- knowledge_graph_api.py
- parseReport.ts
- get_quota_tracker
- agent_websocket_handler
- SmartsheetMaintainerCache
- .has_reeval_signal
- create_chat_event
- Trigger
- AsyncGitHubClient
- GitLabTokenAuth
- _is_event_closed_or_missing
- TimeKeeperObserver
- CortexRepository
- BrainIntrospectionPort
- update_notebook_note
- scripts
- validate-mutations.sh
- ._process_message
- enforce_casual_domain
- list_failed_stages
- dex_proxy
- _has_non_user_turns
- list_incidents
- require-results.sh
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

## Communities (210 total, 119 thin omitted)

### Community 0 - "BlackboardState"
Cohesion: 0.01
Nodes (22): get_report_client(), render_pdf(), get_all_journal(), get_service_journal(), delete_notebook_note(), get_notebook(), bulk_delete_observations(), BulkDeleteRequest (+14 more)

### Community 1 - "brain.py"
Cohesion: 0.03
Nodes (31): _annotation_replace(), _strip_pipeline_annotations(), _sanitize_lesson_text(), _compute_processed_up_to(), _get_jira_reporter(), handle_ask_release_ai(), _is_darwin_reentrant_caller(), jenkins_retrigger_cooldown_key() (+23 more)

### Community 2 - "models.py"
Cohesion: 0.02
Nodes (44): can_append_message(), get_blackboard(), AppNode, ArchitectureEvent, ChatRequest, ChatResponse, EventEvidence, EventInput (+36 more)

### Community 3 - "ConversationTurn"
Cohesion: 0.06
Nodes (49): emit_tool_result(), _safe_int(), handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_recall_pruned_turns(), handle_message_agent(), handle_reply_to_agent() (+41 more)

### Community 4 - "EventChatPanel.tsx"
Cohesion: 0.05
Nodes (72): @uiw/react-markdown-preview, approveEvent(), closeEvent(), enforceCasualDomain(), getEventReport(), rejectEvent(), submitFeedback(), CiContext (+64 more)

### Community 5 - "client.ts"
Cohesion: 0.04
Nodes (82): bulkDeleteObservations(), deleteObservation(), exportObservations(), ExtractedCorrection, ExtractedLesson, ExtractionResult, generateObservationsReport(), getAgents() (+74 more)

### Community 6 - "nightwatcher_tools.py"
Cohesion: 0.04
Nodes (30): _check_security(), safe_execution(), wrapper(), SecurityError, TaskBridge, PulseContext, ShiftIncident, ShiftInvestigation (+22 more)

### Community 7 - "useCortexData.ts"
Cohesion: 0.06
Nodes (73): three, getCognitiveGraph(), getCortexActivity(), getEventPulses(), getKGServiceDetail(), getKGServices(), getKGStats(), getKnowledgeById() (+65 more)

### Community 8 - "tool_gates.py"
Cohesion: 0.05
Nodes (78): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+70 more)

### Community 9 - "OpsStateContext.tsx"
Cohesion: 0.05
Nodes (59): getActiveEvents(), getAlignerPending(), getEventDocument(), getEvents(), getJenkinsPending(), getKargoStages(), getWaitingApprovalEvents(), ActiveEvent (+51 more)

### Community 10 - "App.tsx"
Cohesion: 0.05
Nodes (53): oidc-client-ts, react-dom, react-router-dom, getConfig(), getIncidents(), getWSAuthFailureCallback(), Incident, setOnUnauthorized() (+45 more)

### Community 11 - "merge-guard.js"
Cohesion: 0.05
Nodes (69): analyzeString(), analyzeTokens(), API_VALUED, apiTokens(), apiWriteNeedsGuard(), assignName(), bareBranchProtected(), base() (+61 more)

### Community 13 - "react"
Cohesion: 0.07
Nodes (58): lucide-react, react, applyLessons(), correctMemory(), createKnowledge(), createLesson(), deleteKnowledge(), deleteLesson() (+50 more)

### Community 14 - "EventHistory.tsx"
Cohesion: 0.06
Nodes (42): @tanstack/react-query, getReport(), getReports(), ReportSearchParams, searchReports(), ReportMeta, ReportSearchResponse, SubjectType (+34 more)

### Community 15 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 16 - "EventSidebar.tsx"
Cohesion: 0.10
Nodes (47): getHeadhunterPending(), getJiraMissions(), HeadhunterTodo, postJiraAction(), ACTION_BADGE, formatAge(), HeadhunterQueuePanel(), renderItem() (+39 more)

### Community 17 - "EventDocument"
Cohesion: 0.05
Nodes (10): _build_closed_block(), build_event_header(), _build_identity_block(), _build_journal_block(), _build_mermaid_block(), _build_related_block(), _build_subject_block(), _build_timing_block() (+2 more)

### Community 18 - "._run_agent_task"
Cohesion: 0.07
Nodes (6): on_huddle(), on_progress(), on_huddle(), on_progress(), _sanitize_override_reason(), get_registry_and_bridge()

### Community 22 - "JarvisMemoryPage.tsx"
Cohesion: 0.08
Nodes (42): dismissProposals(), EnhancementProposal, getFlowMetrics(), getHandoffReports(), getProposals(), HandoffReport, FlowMetrics, AgentStreamCard() (+34 more)

### Community 23 - "queue.py"
Cohesion: 0.07
Nodes (23): get_archivist(), apply_lessons(), correct_memory(), CorrectMemoryRequest, create_knowledge(), create_lesson(), delete_knowledge(), delete_lesson() (+15 more)

### Community 25 - "credentials.js"
Cohesion: 0.12
Nodes (45): resolveCommand(), writeAgyMcpServer(), writeClaudeMcpServer(), buildArgoCDMcpConfig(), createAppJWT(), discoverAndGenerateTokens(), _discoverAndGenerateTokensInner(), discoverInstallations() (+37 more)

### Community 26 - "JenkinsObserver"
Cohesion: 0.06
Nodes (3): _env_flag(), JenkinsObserver, _redact_build_parameters()

### Community 27 - "storage-recycler.js"
Cohesion: 0.08
Nodes (34): withTaskStorage(), resolveStorageRoot(), ROLE_TIMEOUTS, STORAGE_ACTIVITY_HEARTBEAT_MS, STORAGE_MAX_TIER3_DELETIONS, STORAGE_PRETASK_TIMEOUT_MS, STORAGE_RESULTS_TTL_MS, STORAGE_STALE_MS (+26 more)

### Community 28 - "JenkinsAdapter"
Cohesion: 0.06
Nodes (6): BuildDetails, JenkinsAdapter, JenkinsPlatformPort, JobResult, JobRunState, ViewScanResult

### Community 29 - ".get_event"
Cohesion: 0.06
Nodes (17): FeedbackRequest, submit_feedback(), aligner_pending_items(), _defer_timeline_fields(), get_event_approval(), get_event_document(), get_event_turns(), get_memory() (+9 more)

### Community 30 - "cli-executor.js"
Cohesion: 0.09
Nodes (34): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS, STORAGE_PRETASK_TIMEOUT_MS, resolveStorageRoot }, buildCLICommand(), { checkAndRecycleStorage, pinTaskCwd, unpinTaskCwd }, CLAUDE_JSON_PATH, cp, executeCLI(), executeCLIStreaming(), FALLBACK_MODEL (+26 more)

### Community 31 - "KnowledgeGraphStore"
Cohesion: 0.09
Nodes (9): _format_graph_context(), get_graph_context(), _parse_props(), _sanitize(), translate_to_lookups(), _acquire(), KnowledgeGraphStore, _sanitize() (+1 more)

### Community 32 - "hooks/index.ts"
Cohesion: 0.08
Nodes (32): ApiError, getClosedEvents(), getService(), getTopology(), ArchitectureEvent, ArgoCDOperation, Service, TopologyResponse (+24 more)

### Community 34 - "AgentClient"
Cohesion: 0.07
Nodes (4): Architect, AgentClient, Developer, SysAdmin

### Community 35 - "observations_reporter.py"
Cohesion: 0.07
Nodes (11): _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), _sample_points(), _summarize(), get_event_observations() (+3 more)

### Community 36 - "ArchitectureGraph.tsx"
Cohesion: 0.09
Nodes (29): @dagrejs/dagre, @xyflow/react, HealthStatus, NodeType, AppNodeData, applyDagreLayout(), applyGridLayout(), applyLayout() (+21 more)

### Community 37 - "lifespan"
Cohesion: 0.06
Nodes (9): set_incident_options(), set_agents(), set_archivist(), set_argocd_observer(), set_blackboard(), set_brain(), set_kargo_observer(), lifespan() (+1 more)

### Community 39 - ".get_service"
Cohesion: 0.07
Nodes (4): get_mermaid_diagram(), get_service_details(), get_topology(), list_services()

### Community 40 - "main.py"
Cohesion: 0.07
Nodes (15): set_kg_store(), set_pulse_tracker(), set_registry_and_bridge(), agent_ws_endpoint(), api_info(), get_config(), get_event_flow(), get_flow_history() (+7 more)

### Community 41 - "TimeKeeperPage.tsx"
Cohesion: 0.12
Nodes (24): createSchedule(), deleteSchedule(), getSchedules(), refineInstructions(), ScheduleCreatePayload, ScheduleItem, toggleSchedule(), updateSchedule() (+16 more)

### Community 43 - "ui/package.json"
Cohesion: 0.08
Nodes (29): autoprefixer, cronstrue, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, graphology-layout-forceatlas2 (+21 more)

### Community 44 - "ws-client.js"
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

### Community 45 - "auth.py"
Cohesion: 0.09
Nodes (10): _apply_sibling_signature(), build_function_response(), build_single_function_response(), compress_contents(), estimate_msg_tokens(), estimate_tokens(), extract_model_parts(), normalize_response_parts() (+2 more)

### Community 46 - "._gate_check"
Cohesion: 0.13
Nodes (8): get_user_from_slack(), handle_app_home_opened(), handle_app_mention(), handle_approve(), handle_create_event_modal(), handle_home_create_event(), handle_reject(), on_dm_message()

### Community 48 - "handlers_dispatch.py"
Cohesion: 0.11
Nodes (7): _resolve_escalation_scope(), CIAnalysis, get_event_document(), list_events(), _esc(), _esc_join(), event_to_markdown()

### Community 49 - "server.js"
Cohesion: 0.09
Nodes (18): hasRegistryCredentials(), { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, fs, path, stageEventDocument(), fetchEventDocument(), fs, { handleRequest } (+10 more)

### Community 50 - "CortexGraph.tsx"
Cohesion: 0.14
Nodes (25): graphology, eventColor(), getExecutiveNeurons(), getStructuralEdges(), DEFAULT_TYPE_BUDGET, evictLru(), KNOWLEDGE_RING, KNOWLEDGE_RING_TYPES (+17 more)

### Community 52 - "ChatInput.tsx"
Cohesion: 0.14
Nodes (19): createChatEvent(), ChatInput(), ChatInputProps, Draft, LastSubmission, STARTER_CHIPS, StarterChip, useSafeNavigate() (+11 more)

### Community 53 - "StateWatcher"
Cohesion: 0.10
Nodes (3): _QueueEntry, StateWatcher, _Subscription

### Community 54 - "adf_to_markdown"
Cohesion: 0.12
Nodes (10): _adf_to_text(), _escape_jql_string(), JiraIncidentAdapter, adf_to_markdown(), _apply_marks(), _children(), _render(), _render_list() (+2 more)

### Community 55 - "KubernetesSpawnHealthAdapter"
Cohesion: 0.11
Nodes (3): KubernetesSpawnHealthAdapter, _PodHealthState, SpawnPollResult

### Community 58 - "ReconcileScheduler"
Cohesion: 0.11
Nodes (4): ReconcileScheduler, QueueTrigger, ResyncTrigger, StalenessGuard

### Community 63 - "dependencies"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 64 - "reconcile.py"
Cohesion: 0.15
Nodes (9): _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers(), main(), _parse_frontmatter() (+1 more)

### Community 65 - "http-handler.js"
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

### Community 67 - "cognitive_graph.py"
Cohesion: 0.13
Nodes (10): get_brain(), get_pulse_tracker(), get_all_shadow_interventions(), get_cognitive_graph(), get_cortex_activity(), get_cortex_status(), get_event_shadow_interventions(), get_handoff_reports() (+2 more)

### Community 68 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 69 - "llm/__init__.py"
Cohesion: 0.17
Nodes (4): LLMChunk, LLMPort, LLMResponse, TokenUsage

### Community 70 - "claude-guard.js"
Cohesion: 0.14
Nodes (18): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+10 more)

### Community 71 - "slack.py"
Cohesion: 0.11
Nodes (7): build_access_denied_home_view(), build_event_report_md(), create_feedback_block(), _md_table_to_text(), _md_to_mrkdwn(), _parse_md_table(), table_block_to_code_block()

### Community 72 - "TokenUtilizationPage.tsx"
Cohesion: 0.16
Nodes (17): recharts, getFlowHistory(), FlowSnapshot, ObservationSeries, FlowHistoryPage(), formatTime(), RANGES, SparkCard() (+9 more)

### Community 73 - "AgentRegistry"
Cohesion: 0.12
Nodes (3): AgentConnection, AgentRegistry, send_cancel()

### Community 74 - "._build_system_prompt"
Cohesion: 0.10
Nodes (3): _init_tool_names(), _strip_tool_names(), _wrap_section()

### Community 75 - "_sanitize_analysis_text"
Cohesion: 0.10
Nodes (9): _clamp_confidence(), _prepare_console_tail(), _redact_match(), _redact_secrets_in_text(), _sanitize_analysis_text(), _sanitize_console_tail(), _strip_newlines(), _validate_analysis() (+1 more)

### Community 76 - "format_event_summary"
Cohesion: 0.11
Nodes (10): build_home_tab_view(), _context_line(), format_event_summary(), format_plan_block(), format_task_card(), format_turn(), resolve_source_emoji(), _section() (+2 more)

### Community 78 - "cli-setup.js"
Cohesion: 0.13
Nodes (19): { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync }, filterSkillsByMode() (+11 more)

### Community 80 - "PulseBatch"
Cohesion: 0.12
Nodes (4): PulseBatch, PulsePort, PulseObserver, PulseTracker

### Community 81 - "jira.py"
Cohesion: 0.16
Nodes (7): approve_mission(), dismiss_mission(), _infer_phase(), _jira_config(), list_missions(), reanalyze_mission(), retry_mission()

### Community 85 - "UserContext"
Cohesion: 0.13
Nodes (9): _claims_to_user(), get_user_from_request(), get_user_from_websocket(), require_auth(), require_obs_admin(), UserContext, _validate_jwt(), dismiss_proposals() (+1 more)

### Community 87 - "devDependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 88 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 89 - "dispatch_to_agent"
Cohesion: 0.13
Nodes (7): _build_prompt(), consume_wake_task(), _consume(), _dispatch_timeout_s(), dispatch_to_agent(), _consume_queue(), _sanitize_stdout()

### Community 92 - "get_report"
Cohesion: 0.11
Nodes (6): get_report(), list_reports(), reports_spa_no_slash(), reports_spa_with_slash(), search_reports(), _serve_spa()

### Community 93 - "gemini-sidecar/package.json"
Cohesion: 0.11
Nodes (17): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+9 more)

### Community 97 - "catalog-skills.js"
Cohesion: 0.16
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 103 - "generate_map.py"
Cohesion: 0.19
Nodes (6): _enumerate_gates(), _GateInfo, generate_phase_tool_map(), _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 104 - "approve_event"
Cohesion: 0.17
Nodes (4): can_approve_event(), resolve_approval_identity(), approve_event(), reject_event()

### Community 114 - "close_event_by_user"
Cohesion: 0.14
Nodes (3): close_event_by_user(), CloseRequest, get_event_report()

### Community 115 - "vcs_approval.py"
Cohesion: 0.19
Nodes (7): _github_active_item(), headhunter_pending_todos(), get_gitlab_auth(), _resolve_github_head(), _resolve_gitlab_head(), resolve_live_head_sha(), verify_merge_guard()

### Community 118 - "scheduling/__init__.py"
Cohesion: 0.22
Nodes (5): GitHubPrRef, GitLabMrRef, GitLabPipelineRef, KargoStageRef, PollFn

### Community 120 - "._extract_context_flags"
Cohesion: 0.15
Nodes (3): compute_dispatch_backpressure(), ContextFlags, _safe_int_env()

### Community 123 - "IncidentAdapterPort"
Cohesion: 0.15
Nodes (3): IdleTimeoutPort, IncidentAdapterPort, StateWatcherPort

### Community 124 - "._send_turn_to_thread"
Cohesion: 0.19
Nodes (5): extract_tables(), _replace(), get_agent_notification_text(), get_turn_attachment_color(), _md_table_to_block_kit()

### Community 130 - "is_defer_event_available"
Cohesion: 0.18
Nodes (6): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 131 - "cortex-constants.ts"
Cohesion: 0.18
Nodes (10): AGENTS, DOMAINS, HEMISPHERE_X, NEURON_DESCRIPTIONS, PHASE_SKILL_FOLDERS, PHASE_TOOL_PRIORITY, PHASES, StructuralEdge (+2 more)

### Community 132 - "NeuronInfoPanel.tsx"
Cohesion: 0.29
Nodes (10): asNumber(), asString(), asStringArray(), Badge(), describeNeuron(), Hdr(), NeuronInfoPanel(), AGENT_NEURON_COLORS (+2 more)

### Community 134 - "vite.config.ts"
Cohesion: 0.20
Nodes (5): @tailwindcss/vite, @testing-library/react, vite, @vitejs/plugin-react, vitest

### Community 137 - "entity_extractor.py"
Cohesion: 0.33
Nodes (5): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship

### Community 139 - "has_unevaluated_close_blocker"
Cohesion: 0.20
Nodes (4): has_unevaluated_close_blocker(), _pred_jarvis_response(), _pred_unevaluated_close(), is_jarvis_acknowledgment()

### Community 140 - "knowledge_graph_api.py"
Cohesion: 0.31
Nodes (4): get_kg_store(), get_service_detail(), get_stats(), list_services()

### Community 141 - "parseReport.ts"
Cohesion: 0.24
Nodes (9): JournalEntry, KNOWN_SECTIONS, ParsedReport, ParsedSection, ParsedTurn, parseJournal(), parseReportMarkdown(), parseTurns() (+1 more)

### Community 143 - "get_quota_tracker"
Cohesion: 0.22
Nodes (3): get_quota_tracker(), llm_stats(), receive_telemetry()

### Community 147 - "create_chat_event"
Cohesion: 0.25
Nodes (3): ChatEventRequest, ChatEventResponse, create_chat_event()

### Community 158 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 159 - "validate-mutations.sh"
Cohesion: 0.73
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

### Community 165 - "enforce_casual_domain"
Cohesion: 0.33
Nodes (4): can_override_domain(), _normalize_email(), enforce_casual_domain(), EnforceCasualRequest

## Knowledge Gaps
- **13 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+8 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2125 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **119 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `brain.py`, `models.py`, `ConversationTurn`, `nightwatcher_tools.py`, `Brain`, `EventDocument`, `create_chat_event`, `_is_event_closed_or_missing`, `queue.py`, `EventRepository`, `update_notebook_note`, `.get_event`, `observations_reporter.py`, `lifespan`, `enforce_casual_domain`, `.get_service`, `main.py`, `._restage_pending_signal`, `._count_pending`, `._stage_pending_signal`, `.__init__`, `handlers_dispatch.py`, `._commit_pending_signal`, `._drain_pending`, `LiveAPIAdapter`, `slack.py`, `jira.py`, `DashboardWSAdapter`, `get_report`, `approve_event`, `ScheduleRepository`, `close_event_by_user`, `HeadhunterJira`?**
  _High betweenness centrality (0.103) - this node is a cross-community bridge._
- **Are the 78 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 78 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.011284134506883321 - nodes in this community are weakly interconnected._
- **Why does `Brain` connect `Brain` to `BlackboardState`, `brain.py`, `models.py`, `ConversationTurn`, `nightwatcher_tools.py`, `EventDocument`, `._run_agent_task`, `lifespan`, `._process_with_llm`, `main.py`, `._idle_timeout_warn`, `.__init__`, `.append_and_broadcast`, `.broadcast`, `StateWatcher`, `.next_turn_number`, `ReconcileScheduler`, `BrainSkillLoader`, `slack.py`, `._build_system_prompt`, `PulseBatch`, `._process_event_inner`, `ReflexSearcher`, `DashboardWSAdapter`, `._build_contents`, `src/ports.py`, `._execute_function_call`, `.start_event_loop`, `QuotaTracker`, `._extract_context_flags`, `IdleTimeoutManager`?**
  _High betweenness centrality (0.064) - this node is a cross-community bridge._
- **Are the 20 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Should `brain.py` be split into smaller, more focused modules?**
  _Cohesion score 0.028138974888200895 - nodes in this community are weakly interconnected._