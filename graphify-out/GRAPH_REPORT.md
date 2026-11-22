# Graph Report - Blackboard  (2026-11-22)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 5584 nodes · 12585 edges · 235 communities (113 shown, 122 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 975 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `00cf87ce`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BlackboardState
- ConversationTurn
- main.py
- os
- queue.py
- client.ts
- GitHubPlatform
- logging
- Brain
- OpsStateContext.tsx
- brain.py
- tool_gates.py
- ._run_agent_task
- Headhunter
- GitLabPlatform
- http-handler.js
- EventSidebar.tsx
- colors.ts
- jenkins-mcp.js
- WorkspaceInspector.tsx
- App.tsx
- fetchApi
- auth.py
- Service
- slack.py
- EventDrillDown.tsx
- Aligner
- EventRepository
- react
- GeminiAdapter
- EventDocument
- ScheduleCreateRequest
- _BrainToolContext
- merge-guard.js
- BrainSkillLoader
- ._process_with_llm
- gemini_client.py
- cli-executor.js
- storage-recycler.js
- JenkinsObserver
- WorkspaceTaskItem.tsx
- llm/__init__.py
- CortexGraph.tsx
- jenkins_observer.py
- cognitive_graph.py
- TimeKeeperPage.tsx
- ws-client.js
- HeadhunterCircuitBreaker
- useCortexData.ts
- EventEvidence
- ui/package.json
- JarvisPeerPort
- prompt.py
- SlackChannel
- nightwatcher.py
- TaskBridge
- ._build_system_prompt
- context_parts.py
- JarvisMemoryPage.tsx
- lucide-react
- KnowledgeGraphStore
- TopologyRepository
- NightwatcherObserver
- LiveAPIAdapter
- llm_error_classifier.py
- observations_mgmt.py
- server.js
- adf_to_markdown
- JenkinsAdapter
- PulseBatch
- nightwatcher_tools.py
- ArgoCDObserver
- NodeInspector.tsx
- DashboardWSAdapter
- AgentRegistry
- state/ports.py
- KargoObserver
- dependencies
- sanitize_prompt_text
- GitHubAppAuth
- compilerOptions
- claude-guard.js
- .fetch_context
- AsyncGitHubClient
- FlowHistoryPage.tsx
- reconcile.py
- cli-setup.js
- StateWatcher
- ReflexSearcher
- FairQueue
- devDependencies
- compilerOptions
- gemini-sidecar/package.json
- ServiceNode.tsx
- EphemeralProvisioner
- format_turn
- get_report
- NeuronInfoPanel.tsx
- ._build_contents
- ObservationRepository
- catalog-skills.js
- SlackAccessGate
- ArchitectureGraph.tsx
- Archivist
- EscalationRepository
- VectorStore
- .__init__
- TokenMeter
- RedisClient
- ShiftsPage.tsx
- generate_map.py
- JenkinsPlatformPort
- OIDCKeyAdapter
- KubernetesSpawnHealthAdapter
- IdleTimeoutManager
- graph_recall.py
- ._process_candidates
- .list_observations
- MultiInstallationManager
- observations_reporter.py
- ._connect
- ScheduleRepository
- analyzeTokens
- .scroll
- ._extract_context_flags
- QuotaTracker
- IncidentAdapterPort
- ._send_turn_to_thread
- ReconcileScheduler
- ._process_message
- ._execute_function_call
- testSetup.ts
- .start_event_loop
- is_defer_event_available
- GitLabTokenAuth
- gitGuard
- parseShell
- scheduling/__init__.py
- generate_event_title
- ._tool_send_event_message
- FlowCollector
- entity_extractor.py
- HeadhunterJira
- ._triage_and_build_evidence
- has_unevaluated_close_blocker
- knowledge_graph_api.py
- spawn_health.py
- classifyTool
- get_quota_tracker
- SpawnPollResult
- .has_reeval_signal
- _get_canonical_or_alias
- ._authorize_plan_decision
- ._run_analysis_loop
- get_all_journal
- Trigger
- _is_event_closed_or_missing
- ._evaluate_health
- ._register_handlers
- ConversationMessage
- TimeKeeperObserver
- CortexRepository
- validate-mutations.sh
- math
- ._detect_repetition_collapse
- QuotaExhaustedError
- scripts
- state.js
- DispatchMetrics
- _append_user_turn
- build_gate_context
- list_failed_stages
- PollFn
- dex_proxy
- ._wait_for_registration
- agent_ws_endpoint
- get_notebook
- QueueTrigger
- TicketNode.tsx
- classify
- _patch_enum_fields
- list_incidents
- ApiError
- require-results.sh
- get_intermediate_tools
- get_event_flow
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
- diagnose_rejection
- GateDefinition
- _pred_dispatch_defer
- _pred_hard_strip_defer
- _pred_idle_agent_wait
- _pred_jarvis_wait
- _pred_obs_plateau
- _pred_silent_park
- _tools_wait_loop

## God Nodes (most connected - your core abstractions)
1. `BlackboardState` - 299 edges
2. `Brain` - 168 edges
3. `ConversationTurn` - 131 edges
4. `ToolContext` - 103 edges
5. `GateContext` - 99 edges
6. `EventDocument` - 88 edges
7. `react` - 85 edges
8. `GitHubPlatform` - 73 edges
9. `lifespan()` - 66 edges
10. `fetchApi()` - 66 edges

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

## Communities (235 total, 122 thin omitted)

### Community 1 - "ConversationTurn"
Cohesion: 0.05
Nodes (54): emit_tool_result(), _safe_int(), handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_recall_pruned_turns(), handle_message_agent(), handle_reply_to_agent() (+46 more)

### Community 2 - "main.py"
Cohesion: 0.02
Nodes (37): Architect, AgentClient, Developer, _check_security(), safe_execution(), wrapper(), SecurityError, SysAdmin (+29 more)

### Community 3 - "os"
Cohesion: 0.03
Nodes (36): _get_jira_reporter(), handle_ask_release_ai(), handle_comment_jira_issue(), handle_fetch_jira_issue(), _is_darwin_reentrant_caller(), _resolve_maintainer_enum(), _resolve_slack_user(), _get_allowed_mention_authors() (+28 more)

### Community 4 - "queue.py"
Cohesion: 0.03
Nodes (52): get_token_meter(), get_archivist(), get_brain(), get_event_document(), aligner_pending_items(), apply_lessons(), approve_event(), close_event_by_user() (+44 more)

### Community 5 - "client.ts"
Cohesion: 0.03
Nodes (95): @tanstack/react-query, bulkDeleteObservations(), deleteNote(), deleteObservation(), exportObservations(), ExtractionResult, generateObservationsReport(), getEventObservations() (+87 more)

### Community 6 - "GitHubPlatform"
Cohesion: 0.03
Nodes (6): _get_static_maintainer_emails(), GitHubPlatform, _poll_one(), _one(), _poll_one(), _LabelResult

### Community 7 - "logging"
Cohesion: 0.05
Nodes (9): _heartbeat(), create_adapter(), _stale_reservation_ttl_s(), FlowSnapshot, get_current_shift(), get_shift_detail(), list_shifts(), _load_brain_context() (+1 more)

### Community 9 - "OpsStateContext.tsx"
Cohesion: 0.05
Nodes (66): getActiveEvents(), getAgents(), getClosedEvents(), getEventDocument(), getKargoStages(), getWaitingApprovalEvents(), updateEventTitle(), AgentRegistryEntry (+58 more)

### Community 10 - "brain.py"
Cohesion: 0.04
Nodes (37): _batch_is_terminal_for_flush(), _compute_processed_up_to(), _has_non_user_turns(), _is_close_phase_fc(), _is_external_input_turn(), _is_seed_turn(), _is_steering_turn(), jenkins_retrigger_cooldown_key() (+29 more)

### Community 11 - "tool_gates.py"
Cohesion: 0.05
Nodes (79): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+71 more)

### Community 12 - "._run_agent_task"
Cohesion: 0.05
Nodes (10): on_huddle(), on_progress(), on_huddle(), on_progress(), _is_automated_nudge(), _is_participant_turn(), _sanitize_error_text(), _sanitize_override_reason() (+2 more)

### Community 13 - "Headhunter"
Cohesion: 0.04
Nodes (7): Headhunter, PlatformQueueItem, PlatformSnapshot, VcsContext, VcsWorkItem, _NoAliasSafeLoader, VcsPlatformPort

### Community 15 - "http-handler.js"
Cohesion: 0.08
Nodes (62): is429Error(), registerMCPsAndHooks(), resolveCommand(), writeAgyMcpServer(), writeClaudeMcpServer(), parsePositiveInt(), buildArgoCDMcpConfig(), createAppJWT() (+54 more)

### Community 16 - "EventSidebar.tsx"
Cohesion: 0.08
Nodes (56): getHeadhunterPending(), getJiraMissions(), HeadhunterTodo, postJiraAction(), ACTION_BADGE, formatAge(), HeadhunterQueuePanel(), renderItem() (+48 more)

### Community 17 - "colors.ts"
Cohesion: 0.07
Nodes (40): getReport(), getReports(), ReportFull, ReportMeta, SubjectType, CompactCardStrip(), EventHistory(), TimeRange (+32 more)

### Community 18 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 19 - "WorkspaceInspector.tsx"
Cohesion: 0.07
Nodes (49): CiContext, ConversationTurn, TokenUsageDict, CiContextCard(), CiContextCardProps, ConsoleTailBlock(), FailedJobRow(), CollapsibleSection() (+41 more)

### Community 20 - "App.tsx"
Cohesion: 0.06
Nodes (43): oidc-client-ts, react-dom, react-router-dom, getConfig(), getWSAuthFailureCallback(), setOnUnauthorized(), setTokenGetter(), setWSAuthFailureCallback() (+35 more)

### Community 21 - "fetchApi"
Cohesion: 0.07
Nodes (52): applyLessons(), correctMemory(), createKnowledge(), createLesson(), deleteKnowledge(), deleteLesson(), ExtractedCorrection, ExtractedLesson (+44 more)

### Community 22 - "auth.py"
Cohesion: 0.05
Nodes (19): can_append_message(), can_approve_event(), can_override_domain(), can_rename_event(), _claims_to_user(), get_user_from_request(), get_user_from_slack(), get_user_from_websocket() (+11 more)

### Community 23 - "Service"
Cohesion: 0.05
Nodes (8): GraphResponse, Service, get_graph_data(), get_mermaid_diagram(), get_service_details(), get_topology(), list_services(), calculate_health_from_argocd()

### Community 24 - "slack.py"
Cohesion: 0.05
Nodes (14): _sanitize_lesson_text(), _coerce_turn_int(), _parse_turn_int(), _sanitize_recalled(), build_access_denied_home_view(), build_event_report_md(), create_feedback_block(), _md_table_to_text() (+6 more)

### Community 25 - "EventDrillDown.tsx"
Cohesion: 0.07
Nodes (43): three, getEventPulses(), EventSource, BrainCore(), CortexDevPage(), devQueryClient, CortexHeartbeat(), CortexHeartbeatProps (+35 more)

### Community 28 - "react"
Cohesion: 0.09
Nodes (39): react, @uiw/react-markdown-preview, approveEvent(), closeEvent(), enforceCasualDomain(), rejectEvent(), submitFeedback(), CollapsibleSectionProps (+31 more)

### Community 29 - "GeminiAdapter"
Cohesion: 0.08
Nodes (12): _attach_signature_to_parts(), _clone_part_with_sig(), _clone_part_with_text(), _coerce_part(), _decode_sig_bytes(), _extract_part_signature(), GeminiAdapter, _is_empty_sig_carrier() (+4 more)

### Community 31 - "ScheduleCreateRequest"
Cohesion: 0.05
Nodes (8): EventInput, ScheduleCreateRequest, create_schedule(), delete_schedule(), get_schedule(), list_schedules(), toggle_schedule(), update_schedule()

### Community 33 - "merge-guard.js"
Cohesion: 0.04
Nodes (46): API_VALUED, ARGO_MUTATING, ARGO_READ_SUB, ARGO_READ_TOP, BODY_FLAG, BROWSER_READ, CTX, ENV_BUILTINS (+38 more)

### Community 34 - "BrainSkillLoader"
Cohesion: 0.06
Nodes (3): BrainSkillLoader, _SkillCorpus, BrainIntrospectionPort

### Community 35 - "._process_with_llm"
Cohesion: 0.05
Nodes (5): _BatchContext, _contents_have_pruned_or_decayed(), _ensure_recall_tool_if_needed(), _QuotaShedState, _retry_backoff_delay()

### Community 36 - "gemini_client.py"
Cohesion: 0.07
Nodes (20): _extract_call_syntax(), _parse_drain_timeout(), derive_llm_priority(), _get_timeout_env_warned(), _get_timeout_order_warned(), is_partial_control_token(), LLMStreamInterChunkTimeoutError, LLMStreamTimeoutError (+12 more)

### Community 37 - "cli-executor.js"
Cohesion: 0.09
Nodes (37): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, MAX_TASK_WALL_MS, MAX_TIMER_MS, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS, STORAGE_PRETASK_TIMEOUT_MS, resolveStorageRoot }, buildCLICommand(), buildTimeoutResult(), { checkAndRecycleStorage, pinTaskCwd, unpinTaskCwd }, CLAUDE_JSON_PATH, cp, createInactivityWatchdog(), executeCLI() (+29 more)

### Community 38 - "storage-recycler.js"
Cohesion: 0.08
Nodes (37): withTaskStorage(), MAX_TASK_WALL_MS, parseTimerMs(), resolveStorageRoot(), resolveTimeoutMs(), ROLE_TIMEOUTS, STORAGE_ACTIVITY_HEARTBEAT_MS, STORAGE_MAX_TIER3_DELETIONS (+29 more)

### Community 40 - "WorkspaceTaskItem.tsx"
Cohesion: 0.09
Nodes (34): AgentStreamCard(), AgentStreamCardProps, MessageCards(), DeferCountdownBar(), GridTile(), GridTileProps, TileType, InlineMarkdownViewer() (+26 more)

### Community 41 - "llm/__init__.py"
Cohesion: 0.08
Nodes (7): ClaudeAdapter, _parse_tpm_limit(), FunctionCall, LLMChunk, LLMPort, LLMResponse, TokenUsage

### Community 42 - "CortexGraph.tsx"
Cohesion: 0.10
Nodes (34): graphology, AGENTS, DOMAINS, eventColor(), getExecutiveNeurons(), getStructuralEdges(), HEMISPHERE_X, PHASE_SKILL_FOLDERS (+26 more)

### Community 43 - "jenkins_observer.py"
Cohesion: 0.08
Nodes (13): _annotation_replace(), _strip_pipeline_annotations(), _clamp_confidence(), _env_flag(), _prepare_console_tail(), _redact_match(), _redact_secrets_in_text(), _sanitize_analysis_text() (+5 more)

### Community 44 - "cognitive_graph.py"
Cohesion: 0.09
Nodes (14): get_blackboard(), get_pulse_tracker(), dismiss_proposals(), DismissRequest, get_all_shadow_interventions(), get_cognitive_graph(), get_cortex_activity(), get_cortex_status() (+6 more)

### Community 45 - "TimeKeeperPage.tsx"
Cohesion: 0.12
Nodes (24): createSchedule(), deleteSchedule(), getSchedules(), refineInstructions(), ScheduleCreatePayload, ScheduleItem, toggleSchedule(), updateSchedule() (+16 more)

### Community 46 - "ws-client.js"
Cohesion: 0.10
Nodes (26): clearIdleTimer(), {
  DEFAULT_WORK_DIR, AGENT_CLI, AGENT_MODEL, AGENT_ROLE,
  EVENT_ID, EPHEMERAL, IDLE_TIMEOUT_MS,
  CLI_429_MAX_RETRIES, CLI_429_INITIAL_DELAY_MS, CLI_429_BACKOFF_MULTIPLIER,
  resolveTimeoutMs, parsePositiveInt, MAX_TASK_WALL_MS, MAX_TIMER_MS,
}, { ensureEventDocument }, { executeCLIStreaming, prepareResultsDir, is429Error }, { filterSkillsByRole, filterSkillsByMode, swapActiveRules, restoreAllSkills }, fs, handleCancel(), handleTask() (+18 more)

### Community 47 - "HeadhunterCircuitBreaker"
Cohesion: 0.07
Nodes (6): HeadhunterCircuitBreaker, PlatformBreakerStatus, _redact_error_text(), on_headhunter_done(), _raise_if_systemic_failure(), start_headhunter_task()

### Community 48 - "useCortexData.ts"
Cohesion: 0.15
Nodes (29): getCognitiveGraph(), getCortexActivity(), getEventReport(), getKGServiceDetail(), getKGServices(), getKGStats(), getKnowledgeById(), getLessonById() (+21 more)

### Community 49 - "EventEvidence"
Cohesion: 0.13
Nodes (9): spawn_event_namer_task(), format_event_summary(), handle_app_mention(), handle_create_event_modal(), handle_darwin_command(), handle_home_create_event(), on_dm_message(), EventEvidence (+1 more)

### Community 50 - "ui/package.json"
Cohesion: 0.08
Nodes (29): autoprefixer, cronstrue, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, graphology-layout-forceatlas2 (+21 more)

### Community 51 - "JarvisPeerPort"
Cohesion: 0.06
Nodes (3): BrainLifecyclePort, BroadcastPort, JarvisPeerPort

### Community 52 - "prompt.py"
Cohesion: 0.12
Nodes (17): _attr(), _build_closed_block(), build_event_header(), _build_identity_block(), _build_journal_block(), _build_mermaid_block(), build_operational_briefing(), _build_related_block() (+9 more)

### Community 54 - "nightwatcher.py"
Cohesion: 0.10
Nodes (11): record_token_usage(), build_report_iteration_prompt(), build_summary_prompt(), build_extend_tool(), build_report_tool(), build_summary_tool(), _fallback_platform(), _handle_declare_clusters() (+3 more)

### Community 55 - "TaskBridge"
Cohesion: 0.10
Nodes (9): _build_prompt(), consume_wake_task(), _consume(), _dispatch_timeout_s(), dispatch_to_agent(), _consume_queue(), _sanitize_stdout(), send_cancel() (+1 more)

### Community 56 - "._build_system_prompt"
Cohesion: 0.07
Nodes (4): _inject_evidence_paths(), _init_tool_names(), _strip_tool_names(), _wrap_section()

### Community 57 - "context_parts.py"
Cohesion: 0.12
Nodes (13): _apply_sibling_signature(), compress_contents(), contents_have_pruned_or_decayed(), estimate_msg_tokens(), estimate_tokens(), extract_model_parts(), format_prune_notice(), _get_part_sig() (+5 more)

### Community 58 - "JarvisMemoryPage.tsx"
Cohesion: 0.14
Nodes (25): dismissProposals(), EnhancementProposal, getHandoffReports(), getProposals(), HandoffReport, FilterMode, formatDate(), formatTime() (+17 more)

### Community 59 - "lucide-react"
Cohesion: 0.15
Nodes (20): lucide-react, createChatEvent(), ChatInput(), ChatInputProps, Draft, LastSubmission, STARTER_CHIPS, StarterChip (+12 more)

### Community 60 - "KnowledgeGraphStore"
Cohesion: 0.15
Nodes (4): _acquire(), KnowledgeGraphStore, _sanitize(), _with_timeout()

### Community 61 - "TopologyRepository"
Cohesion: 0.08
Nodes (3): Snapshot, TopologySnapshot, TopologyRepository

### Community 62 - "NightwatcherObserver"
Cohesion: 0.10
Nodes (7): ShiftReport, _env_float(), _env_int(), NightwatcherObserver, build_manifest_table(), build_system_prompt(), extract_event_links()

### Community 64 - "llm_error_classifier.py"
Cohesion: 0.13
Nodes (9): _extract_status_code(), _has_non_retryable_cause(), _is_google_auth_transport_error(), is_rate_limit(), is_transient(), is_transient_llm_error_turn(), _iter_exception_chain(), _matches_mro() (+1 more)

### Community 65 - "observations_mgmt.py"
Cohesion: 0.10
Nodes (10): get_report_client(), render_pdf(), bulk_delete_observations(), BulkDeleteRequest, delete_observation(), export_observations(), generate_observations_report(), rename_observation() (+2 more)

### Community 66 - "server.js"
Cohesion: 0.09
Nodes (18): { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, ensureEventDocument(), fs, path, stageEventDocument(), fetchEventDocument(), fs, { handleRequest } (+10 more)

### Community 67 - "adf_to_markdown"
Cohesion: 0.12
Nodes (10): _adf_to_text(), _escape_jql_string(), JiraIncidentAdapter, adf_to_markdown(), _apply_marks(), _children(), _render(), _render_list() (+2 more)

### Community 69 - "PulseBatch"
Cohesion: 0.10
Nodes (4): PulseBatch, PulsePort, PulseObserver, PulseTracker

### Community 70 - "nightwatcher_tools.py"
Cohesion: 0.15
Nodes (13): ShiftIncident, ShiftInvestigation, extract_full_links(), execute_tool(), _handle_consult_deep_memory(), _handle_dispatch_investigation(), _handle_extend_incident(), _handle_get_event_report() (+5 more)

### Community 72 - "NodeInspector.tsx"
Cohesion: 0.14
Nodes (22): ArgoCDOperation, ArchitectureGraph(), EVENT_LABELS, EventItem(), EventItemProps, healthTone(), lastOperationSummary(), NodeInspector() (+14 more)

### Community 73 - "DashboardWSAdapter"
Cohesion: 0.14
Nodes (3): DashboardWSAdapter, prompt_display_name(), resolve_approval_identity()

### Community 74 - "AgentRegistry"
Cohesion: 0.11
Nodes (3): AgentConnection, AgentRegistry, agent_websocket_handler()

### Community 75 - "state/ports.py"
Cohesion: 0.11
Nodes (3): ArchitectureEvent, list_events(), MetricsRepository

### Community 77 - "dependencies"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 78 - "sanitize_prompt_text"
Cohesion: 0.10
Nodes (10): _close_unanswered_fc(), build_function_response(), build_single_function_response(), format_evidence_decay_reference(), _format_bounded_journal(), _esc(), _esc_join(), _finalize_untrusted() (+2 more)

### Community 81 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 82 - "claude-guard.js"
Cohesion: 0.14
Nodes (18): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+10 more)

### Community 83 - ".fetch_context"
Cohesion: 0.10
Nodes (7): _bot_login(), _csv_env(), _consider(), _is_slash_command_only(), _mention_pattern(), _review_ignore_logins(), _review_trusted_associations()

### Community 84 - "AsyncGitHubClient"
Cohesion: 0.17
Nodes (5): AsyncGitHubClient, _handle_rate_limit(), _paginate_github_get(), parse_github_next_link(), _safe_parse_int()

### Community 85 - "FlowHistoryPage.tsx"
Cohesion: 0.21
Nodes (17): recharts, FlowSnapshot, FlowHistoryPage(), RANGES, SparkCard(), SparkCardProps, TokenUsageMini(), formatTime() (+9 more)

### Community 86 - "reconcile.py"
Cohesion: 0.19
Nodes (9): _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers(), main(), _parse_frontmatter() (+1 more)

### Community 87 - "cli-setup.js"
Cohesion: 0.13
Nodes (18): { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync }, filterSkillsByMode() (+10 more)

### Community 88 - "StateWatcher"
Cohesion: 0.13
Nodes (3): _QueueEntry, StateWatcher, _Subscription

### Community 91 - "devDependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 92 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 93 - "gemini-sidecar/package.json"
Cohesion: 0.11
Nodes (18): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+10 more)

### Community 94 - "ServiceNode.tsx"
Cohesion: 0.15
Nodes (13): @xyflow/react, HealthStatus, NodeType, AppNodeData, ARGOCD_HEALTH_COLORS, SYNC_ICONS, NamespaceGroupNodeData, GENERIC_TAGS (+5 more)

### Community 96 - "format_turn"
Cohesion: 0.13
Nodes (9): build_home_tab_view(), _context_line(), format_plan_block(), format_task_card(), format_tool_result_blocks(), format_turn(), resolve_source_emoji(), _section() (+1 more)

### Community 97 - "get_report"
Cohesion: 0.11
Nodes (6): get_report(), list_reports(), reports_spa_no_slash(), reports_spa_with_slash(), search_reports(), _serve_spa()

### Community 98 - "NeuronInfoPanel.tsx"
Cohesion: 0.16
Nodes (18): ActiveEvent, KGServiceEntity, NEURON_DESCRIPTIONS, CortexGraphProps, GraphLoaderProps, asNumber(), asString(), asStringArray() (+10 more)

### Community 101 - "catalog-skills.js"
Cohesion: 0.16
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 103 - "ArchitectureGraph.tsx"
Cohesion: 0.18
Nodes (15): @dagrejs/dagre, applyDagreLayout(), applyGridLayout(), applyLayout(), ArchitectureGraphInner(), buildGraph(), computeIdHash(), edgeTypes (+7 more)

### Community 111 - "ShiftsPage.tsx"
Cohesion: 0.28
Nodes (14): getCurrentShift(), getShiftDetail(), getShiftsList(), FailedClusterBadge(), getISOWeek(), getWeekDates(), ShiftCard(), ShiftDetailPanel() (+6 more)

### Community 112 - "generate_map.py"
Cohesion: 0.19
Nodes (6): _enumerate_gates(), _GateInfo, generate_phase_tool_map(), _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 113 - "JenkinsPlatformPort"
Cohesion: 0.13
Nodes (4): BuildDetails, JenkinsPlatformPort, JobRunState, ViewScanResult

### Community 117 - "graph_recall.py"
Cohesion: 0.19
Nodes (5): _format_graph_context(), get_graph_context(), _parse_props(), _sanitize(), translate_to_lookups()

### Community 118 - "._process_candidates"
Cohesion: 0.13
Nodes (3): _flood_service_key(), _outage_service_key(), _service_key()

### Community 121 - "observations_reporter.py"
Cohesion: 0.21
Nodes (7): _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), _sample_points(), _summarize()

### Community 126 - "analyzeTokens"
Cohesion: 0.19
Nodes (13): analyzeString(), analyzeTokens(), assignName(), base(), combineCategories(), configEnvGuard(), configFileWriteGuard(), hasSubseq() (+5 more)

### Community 128 - "._extract_context_flags"
Cohesion: 0.15
Nodes (3): compute_dispatch_backpressure(), ContextFlags, _safe_int_env()

### Community 130 - "IncidentAdapterPort"
Cohesion: 0.15
Nodes (3): IdleTimeoutPort, IncidentAdapterPort, StateWatcherPort

### Community 131 - "._send_turn_to_thread"
Cohesion: 0.19
Nodes (5): extract_tables(), _replace(), get_agent_notification_text(), get_turn_attachment_color(), _md_table_to_block_kit()

### Community 137 - "testSetup.ts"
Cohesion: 0.18
Nodes (5): @tailwindcss/vite, @testing-library/react, vite, @vitejs/plugin-react, vitest

### Community 139 - "is_defer_event_available"
Cohesion: 0.18
Nodes (6): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 141 - "gitGuard"
Cohesion: 0.29
Nodes (10): bareBranchProtected(), configWriteGuard(), externalGitCommand(), gitGuard(), gitQuery(), isProtected(), normRef(), pushGuard() (+2 more)

### Community 142 - "parseShell"
Cohesion: 0.33
Nodes (10): bodySubstitutions(), decodeAnsiC(), isArrayAssignPrefix(), isWordStart(), matchBacktick(), matchParen(), parseShell(), readHeredocStart() (+2 more)

### Community 143 - "scheduling/__init__.py"
Cohesion: 0.29
Nodes (4): GitHubPrRef, GitLabMrRef, GitLabPipelineRef, KargoStageRef

### Community 144 - "generate_event_title"
Cohesion: 0.22
Nodes (3): generate_event_title(), get_adapter(), _get_semaphore()

### Community 149 - "entity_extractor.py"
Cohesion: 0.33
Nodes (5): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship

### Community 153 - "has_unevaluated_close_blocker"
Cohesion: 0.22
Nodes (5): has_unevaluated_close_blocker(), _pred_jarvis_response(), _pred_unevaluated_close(), is_jarvis_acknowledgment(), is_stabilization_wake()

### Community 154 - "knowledge_graph_api.py"
Cohesion: 0.31
Nodes (4): get_kg_store(), get_service_detail(), get_stats(), list_services()

### Community 156 - "classifyTool"
Cohesion: 0.31
Nodes (9): apiTokens(), apiWriteNeedsGuard(), branchValues(), classifyTool(), hasOpaqueTarget(), httpGuard(), httpMethod(), isReadMethod() (+1 more)

### Community 157 - "get_quota_tracker"
Cohesion: 0.22
Nodes (3): get_quota_tracker(), llm_stats(), receive_telemetry()

### Community 163 - "._run_analysis_loop"
Cohesion: 0.25
Nodes (3): _append_user_turn(), _finalize_analysis_handover(), get_phase_tools()

### Community 173 - "validate-mutations.sh"
Cohesion: 0.57
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

### Community 178 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 179 - "state.js"
Cohesion: 0.33
Nodes (4): { AGENT_ROLE }, _blackboardTurns, _inboundMessages, _teammateMessages

### Community 187 - "_append_user_turn"
Cohesion: 0.33
Nodes (3): _append_user_turn(), _is_function_response_part(), _validated_parts()

### Community 188 - "build_gate_context"
Cohesion: 0.33
Nodes (3): build_gate_context(), conversation_has_decayed_turns(), _decay_payload_len()

### Community 197 - "TicketNode.tsx"
Cohesion: 0.40
Nodes (4): STATUS_COLORS, TICKET_COLORS, TicketNodeComponent(), TicketNodeData

### Community 198 - "classify"
Cohesion: 0.50
Nodes (4): classify(), main(), shellCategory(), shellNeedsGuard()

### Community 209 - "overrides"
Cohesion: 0.67
Nodes (3): overrides, @typescript-eslint/typescript-estree, minimatch

## Knowledge Gaps
- **13 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+8 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2457 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **122 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `ConversationTurn`, `main.py`, `os`, `queue.py`, `logging`, `Brain`, `brain.py`, `generate_event_title`, `auth.py`, `HeadhunterJira`, `slack.py`, `Service`, `EventDocument`, `ScheduleCreateRequest`, `get_all_journal`, `_is_event_closed_or_missing`, `ConversationMessage`, `jenkins_observer.py`, `cognitive_graph.py`, `EventEvidence`, `nightwatcher.py`, `TopologyRepository`, `NightwatcherObserver`, `LiveAPIAdapter`, `._stage_pending_signal`, `observations_mgmt.py`, `get_notebook`, `nightwatcher_tools.py`, `DashboardWSAdapter`, `state/ports.py`, `report_tampering`, `get_report`, `.__init__`, `.list_observations`, `observations_reporter.py`, `ScheduleRepository`?**
  _High betweenness centrality (0.138) - this node is a cross-community bridge._
- **Are the 80 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 80 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.011998099311000238 - nodes in this community are weakly interconnected._
- **Why does `Brain` connect `Brain` to `._extract_context_flags`, `ConversationTurn`, `BlackboardState`, `os`, `ReconcileScheduler`, `main.py`, `._execute_function_call`, `brain.py`, `.start_event_loop`, `._run_agent_task`, `FlowCollector`, `slack.py`, `EventDocument`, `BrainSkillLoader`, `._process_with_llm`, `._detect_repetition_collapse`, `EventEvidence`, `JarvisPeerPort`, `._escalation_blocked`, `._build_system_prompt`, `QueueTrigger`, `PulseBatch`, `DashboardWSAdapter`, `.clear_jarvis_wait`, `.next_turn_number`, `StateWatcher`, `ReflexSearcher`, `._build_contents`, `.__init__`, `IdleTimeoutManager`?**
  _High betweenness centrality (0.071) - this node is a cross-community bridge._
- **Are the 20 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Should `ConversationTurn` be split into smaller, more focused modules?**
  _Cohesion score 0.04897240164415737 - nodes in this community are weakly interconnected._