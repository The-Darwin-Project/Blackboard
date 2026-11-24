# Graph Report - Blackboard  (2026-11-24)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 5985 nodes · 13626 edges · 213 communities (106 shown, 107 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 1038 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `6bd1ed55`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BlackboardState
- Brain
- WorkspaceInspector.tsx
- client.ts
- queue.py
- logging
- dependencies.py
- ConversationTurn
- EventDocument
- Archivist
- brain.py
- GitLabPlatform
- fetchApi
- auth.py
- tool_gates.py
- EventRepository
- os
- models.py
- ReconcileScheduler
- Headhunter
- .get_event
- colors.ts
- http-handler.js
- .get_graph_data
- ._process_with_llm
- main.py
- jenkins-mcp.js
- App.tsx
- GitHubAppAuth
- AgentRegistry
- nightwatcher_tools.py
- handlers_integration.py
- react
- headhunter.py
- Aligner
- TurnBubble.tsx
- agents/__init__.py
- context_parts.py
- _BrainToolContext
- GeminiAdapter
- StreamGrid.tsx
- merge-guard.js
- HeadhunterJira
- KnowledgeGraphStore
- ui/package.json
- gemini_client.py
- cli-executor.js
- storage-recycler.js
- llm/__init__.py
- ArchitectureGraph.tsx
- useCortexData.ts
- record_token_usage
- EventDrillDown.tsx
- formatter.py
- TimeKeeperPage.tsx
- VcsPlatformPort
- SlackChannel
- JenkinsObserver
- ws-client.js
- CortexGraph.tsx
- LiveAPIAdapter
- BrainSkillLoader
- ._poll_pr_feedback
- BoolOutcome
- ._github_poll_and_process
- PlanProgress.tsx
- llm_error_classifier.py
- observations_mgmt.py
- server.js
- JenkinsAdapter
- PulseBatch
- spawn_event_namer_task
- jira.py
- ArgoCDObserver
- NeuronInfoPanel.tsx
- handlers_cross_event.py
- GitHubPlatform
- KargoObserver
- state/__init__.py
- TopologyRepository
- dependencies
- NodeInspector.tsx
- HeadhunterCircuitBreaker
- compilerOptions
- claude-guard.js
- handlers_lookup.py
- reconcile.py
- FlowHistoryPage.tsx
- DashboardWSAdapter
- ._fetch_checks_and_legacy_status
- cli-setup.js
- observations_reporter.py
- ReflexSearcher
- utils/__init__.py
- .create_platform_event
- QuotaTracker
- TokenMeter
- devDependencies
- compilerOptions
- gemini-sidecar/package.json
- JarvisPeerPort
- EphemeralProvisioner
- get_report
- JiraIncidentAdapter
- ._feedback_reject_reason
- ObservationRepository
- ShiftsPage.tsx
- catalog-skills.js
- slack.py
- ._authorize_plan_decision
- EscalationRepository
- .poll_review_feedback_all_installations
- generate_map.py
- JenkinsPlatformPort
- OIDCKeyAdapter
- KubernetesSpawnHealthAdapter
- ._discover
- ._get
- ._process_candidates
- .list_observations
- ._connect
- BrainLifecyclePort
- ScheduleRepository
- SlackAccessGate
- analyzeTokens
- ._extract_context_flags
- evaluate_gates
- ScheduleCreateRequest
- IdleTimeoutManager
- ._process_message
- adf_to_markdown
- has_unevaluated_close_blocker
- GitLabTokenAuth
- CiContextCard.tsx
- CortexLiveFeed.tsx
- gitGuard
- parseShell
- generate_event_title
- ._tool_send_event_message
- ._post_agent_recall
- entity_extractor.py
- ._triage_and_build_evidence
- BrainIntrospectionPort
- spawn_health.py
- classifyTool
- SpawnPollResult
- get_all_journal
- list_shifts
- _is_event_closed_or_missing
- ._evaluate_health
- ConversationMessage
- CortexRepository
- validate-mutations.sh
- ._detect_repetition_collapse
- ._get_manager
- scripts
- state.js
- DispatchMetrics
- _append_user_turn
- build_gate_context
- dex_proxy
- ._wait_for_registration
- can_transition_to_close
- get_notebook
- classify
- derive_llm_priority
- _patch_enum_fields
- require-results.sh
- get_intermediate_tools
- findDuplicateJsonKeys.ts
- tsconfig.json
- gh-wrapper.sh
- check-inbox.sh
- cluster-context.sh
- validate-reviewer-bash.sh
- huddleSendMessage.sh
- update-agy.sh
- sendResults.sh
- _parse_drain_timeout
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
1. `BlackboardState` - 325 edges
2. `Brain` - 169 edges
3. `ConversationTurn` - 139 edges
4. `ToolContext` - 103 edges
5. `GateContext` - 100 edges
6. `GitHubPlatform` - 99 edges
7. `EventDocument` - 97 edges
8. `EventRepository` - 90 edges
9. `Headhunter` - 89 edges
10. `react` - 86 edges

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

## Communities (213 total, 107 thin omitted)

### Community 1 - "Brain"
Cohesion: 0.02
Nodes (9): Brain, on_huddle(), on_progress(), on_huddle(), on_progress(), _is_automated_nudge(), _is_participant_turn(), _sanitize_error_text() (+1 more)

### Community 2 - "WorkspaceInspector.tsx"
Cohesion: 0.04
Nodes (92): lucide-react, react-router-dom, createChatEvent(), getEvents(), getKargoStages(), updateEventTitle(), AgentRegistryEntry, AppConfig (+84 more)

### Community 3 - "client.ts"
Cohesion: 0.03
Nodes (104): @tanstack/react-query, ApiError, bulkDeleteObservations(), deleteNote(), deleteObservation(), exportObservations(), ExtractedCorrection, ExtractedLesson (+96 more)

### Community 4 - "queue.py"
Cohesion: 0.03
Nodes (56): get_token_meter(), get_archivist(), EventStatus, aligner_pending_items(), apply_lessons(), ApproveRequest, CloseRequest, correct_memory() (+48 more)

### Community 5 - "logging"
Cohesion: 0.04
Nodes (17): _annotation_replace(), _strip_pipeline_annotations(), _heartbeat(), _clamp_confidence(), _parse_job_metadata(), _prepare_console_tail(), _redact_match(), _redact_secrets_in_text() (+9 more)

### Community 6 - "dependencies.py"
Cohesion: 0.03
Nodes (34): get_aligner(), get_architect(), get_argocd_observer(), get_blackboard(), get_developer(), get_kargo_observer(), get_kg_store(), get_pulse_tracker() (+26 more)

### Community 7 - "ConversationTurn"
Cohesion: 0.06
Nodes (47): emit_tool_result(), handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_message_agent(), handle_reply_to_agent(), handle_report_incident(), handle_select_agent() (+39 more)

### Community 8 - "EventDocument"
Cohesion: 0.03
Nodes (27): _is_close_phase_fc(), _clean_lines(), format_event_state_tail(), _build_closed_block(), build_event_header(), _build_identity_block(), build_immutable_event_anchor(), _build_journal_block() (+19 more)

### Community 9 - "Archivist"
Cohesion: 0.04
Nodes (5): Archivist, Pulse, _decode_cursor(), _encode_cursor(), VectorStore

### Community 10 - "brain.py"
Cohesion: 0.04
Nodes (41): _build_active_overlay(), _build_event_state_tail_block(), _build_transient_overlays(), _build_turn0_anchor(), _call_anchor_get(), _call_anchor_set_nx(), _close_unanswered_fc(), _collect_turn_overlay_part() (+33 more)

### Community 11 - "GitLabPlatform"
Cohesion: 0.05
Nodes (6): _get_allowed_mention_authors(), GitLabPlatform, _reconcile_synthetic(), _check_one(), _parse_ts_epoch(), _valid_positive_int()

### Community 12 - "fetchApi"
Cohesion: 0.06
Nodes (84): fetchApi(), getActiveEvents(), getAlignerPending(), getClosedEvents(), getEventDocument(), getHeadhunterPending(), getHeadhunterStatus(), getJenkinsPending() (+76 more)

### Community 13 - "auth.py"
Cohesion: 0.03
Nodes (24): can_append_message(), can_approve_event(), can_override_domain(), can_rename_event(), _claims_to_user(), get_user_from_slack(), get_user_from_websocket(), _normalize_email() (+16 more)

### Community 14 - "tool_gates.py"
Cohesion: 0.05
Nodes (79): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+71 more)

### Community 16 - "os"
Cohesion: 0.05
Nodes (23): _iso(), _parse_ts(), _env_flag(), build_manifest_table(), extract_event_links(), get_current_shift(), get_installation_manager(), is_shared_installation_manager() (+15 more)

### Community 17 - "models.py"
Cohesion: 0.04
Nodes (28): AppNode, ArchitectureEvent, ChatRequest, ChatResponse, EventInput, EventMetrics, EventType, FlowMetricsResponse (+20 more)

### Community 18 - "ReconcileScheduler"
Cohesion: 0.04
Nodes (7): FlowCollector, FairQueue, ReconcileScheduler, Trigger, QueueTrigger, ResyncTrigger, StalenessGuard

### Community 19 - "Headhunter"
Cohesion: 0.06
Nodes (3): Headhunter, _process_issue(), VcsContext

### Community 20 - ".get_event"
Cohesion: 0.04
Nodes (21): get_user_from_request(), get_brain(), ChatEventRequest, ChatEventResponse, create_chat_event(), report_tampering(), _require_jira_mutation_auth(), _acquire_hh_poll_lock() (+13 more)

### Community 21 - "colors.ts"
Cohesion: 0.07
Nodes (44): getReport(), getReports(), ReportFull, ReportMeta, DeferCountdownBar(), CompactCardStrip(), EventHistory(), TimeRange (+36 more)

### Community 22 - "http-handler.js"
Cohesion: 0.08
Nodes (62): is429Error(), registerMCPsAndHooks(), resolveCommand(), writeAgyMcpServer(), writeClaudeMcpServer(), parsePositiveInt(), buildArgoCDMcpConfig(), createAppJWT() (+54 more)

### Community 23 - ".get_graph_data"
Cohesion: 0.04
Nodes (9): GraphResponse, get_event_document(), list_events(), get_graph_data(), get_mermaid_diagram(), get_service_details(), get_topology(), list_services() (+1 more)

### Community 24 - "._process_with_llm"
Cohesion: 0.04
Nodes (9): _batch_is_terminal_for_flush(), _BatchContext, _retry_backoff_delay(), _wait_for_user_admissible(), build_global_core_si(), canonical_wire_tools(), compute_prefix_hashes(), sha8_json() (+1 more)

### Community 25 - "main.py"
Cohesion: 0.04
Nodes (22): set_oidc_adapter(), set_agents(), set_archivist(), set_argocd_observer(), set_brain(), set_kargo_observer(), set_kg_store(), set_pulse_tracker() (+14 more)

### Community 26 - "jenkins-mcp.js"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 27 - "App.tsx"
Cohesion: 0.06
Nodes (48): oidc-client-ts, dismissProposals(), EnhancementProposal, getConfig(), getHandoffReports(), getProposals(), getWSAuthFailureCallback(), HandoffReport (+40 more)

### Community 28 - "GitHubAppAuth"
Cohesion: 0.05
Nodes (8): AsyncGitHubClient, _find_pem_file(), GitHubAppAuth, _handle_rate_limit(), MultiInstallationManager, _paginate_github_get(), parse_github_next_link(), _safe_parse_int()

### Community 29 - "AgentRegistry"
Cohesion: 0.06
Nodes (13): AgentConnection, AgentRegistry, agent_websocket_handler(), _build_prompt(), _check_security(), consume_wake_task(), _consume(), _dispatch_timeout_s() (+5 more)

### Community 30 - "nightwatcher_tools.py"
Cohesion: 0.07
Nodes (24): _sanitize_lesson_text(), PulseContext, ShiftIncident, ShiftInvestigation, extract_full_links(), build_extend_tool(), build_report_tool(), build_summary_tool() (+16 more)

### Community 31 - "handlers_integration.py"
Cohesion: 0.06
Nodes (22): _get_jira_reporter(), handle_ask_release_ai(), handle_comment_jira_issue(), handle_fetch_jira_issue(), _is_darwin_reentrant_caller(), _is_positive_int(), jenkins_retrigger_cooldown_key(), _parse_poll_interval() (+14 more)

### Community 32 - "react"
Cohesion: 0.08
Nodes (47): react, applyLessons(), correctMemory(), createKnowledge(), createLesson(), deleteKnowledge(), deleteLesson(), extractLessons() (+39 more)

### Community 33 - "headhunter.py"
Cohesion: 0.05
Nodes (10): HeadhunterOperationError, PlatformBreakerStatus, PlatformQueueItem, PlatformSnapshot, redact_error_text(), _NoAliasSafeLoader, on_headhunter_done(), start_headhunter_task() (+2 more)

### Community 35 - "TurnBubble.tsx"
Cohesion: 0.08
Nodes (40): @uiw/react-markdown-preview, approveEvent(), rejectEvent(), submitFeedback(), MessageStatus, CollapsibleSection(), CollapsibleSectionProps, MermaidBlock() (+32 more)

### Community 36 - "agents/__init__.py"
Cohesion: 0.06
Nodes (7): Architect, AgentClient, Developer, safe_execution(), wrapper(), SecurityError, SysAdmin

### Community 37 - "context_parts.py"
Cohesion: 0.07
Nodes (21): _apply_sibling_signature(), build_function_response(), build_single_function_response(), compress_contents(), _compress_single_msg_parts(), estimate_msg_tokens(), estimate_tokens(), extract_model_parts() (+13 more)

### Community 39 - "GeminiAdapter"
Cohesion: 0.08
Nodes (11): _attach_signature_to_parts(), _clone_part_with_sig(), _clone_part_with_text(), _coerce_part(), _decode_sig_bytes(), _extract_part_signature(), GeminiAdapter, _is_empty_sig_carrier() (+3 more)

### Community 40 - "StreamGrid.tsx"
Cohesion: 0.08
Nodes (40): AgentStreamCard(), AgentStreamCardProps, MessageCards(), Dashboard(), GridTile(), GridTileProps, TileType, InlineMarkdownViewer() (+32 more)

### Community 41 - "merge-guard.js"
Cohesion: 0.04
Nodes (46): API_VALUED, ARGO_MUTATING, ARGO_READ_SUB, ARGO_READ_TOP, BODY_FLAG, BROWSER_READ, CTX, ENV_BUILTINS (+38 more)

### Community 43 - "KnowledgeGraphStore"
Cohesion: 0.08
Nodes (9): _format_graph_context(), get_graph_context(), _parse_props(), _sanitize(), translate_to_lookups(), _acquire(), KnowledgeGraphStore, _sanitize() (+1 more)

### Community 44 - "ui/package.json"
Cohesion: 0.05
Nodes (37): autoprefixer, cronstrue, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, graphology-layout-forceatlas2 (+29 more)

### Community 45 - "gemini_client.py"
Cohesion: 0.08
Nodes (19): _extract_call_syntax(), _stale_reservation_ttl_s(), _get_timeout_env_warned(), _get_timeout_order_warned(), is_partial_control_token(), LLMStreamInterChunkTimeoutError, LLMStreamTimeoutError, LLMStreamTotalTimeoutError (+11 more)

### Community 46 - "cli-executor.js"
Cohesion: 0.09
Nodes (37): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, MAX_TASK_WALL_MS, MAX_TIMER_MS, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS, STORAGE_PRETASK_TIMEOUT_MS, resolveStorageRoot }, buildCLICommand(), buildTimeoutResult(), { checkAndRecycleStorage, pinTaskCwd, unpinTaskCwd }, CLAUDE_JSON_PATH, cp, createInactivityWatchdog(), executeCLI() (+29 more)

### Community 47 - "storage-recycler.js"
Cohesion: 0.08
Nodes (37): withTaskStorage(), MAX_TASK_WALL_MS, parseTimerMs(), resolveStorageRoot(), resolveTimeoutMs(), ROLE_TIMEOUTS, STORAGE_ACTIVITY_HEARTBEAT_MS, STORAGE_MAX_TIER3_DELETIONS (+29 more)

### Community 48 - "llm/__init__.py"
Cohesion: 0.08
Nodes (8): ClaudeAdapter, create_adapter(), _parse_tpm_limit(), FunctionCall, LLMChunk, LLMPort, LLMResponse, TokenUsage

### Community 49 - "ArchitectureGraph.tsx"
Cohesion: 0.07
Nodes (33): @dagrejs/dagre, @xyflow/react, HealthStatus, NodeType, AppNodeData, applyDagreLayout(), applyGridLayout(), applyLayout() (+25 more)

### Community 50 - "useCortexData.ts"
Cohesion: 0.11
Nodes (37): closeEvent(), enforceCasualDomain(), getCognitiveGraph(), getCortexActivity(), getEventReport(), getKGServiceDetail(), getKGServices(), getKGStats() (+29 more)

### Community 51 - "record_token_usage"
Cohesion: 0.08
Nodes (10): record_token_usage(), ShiftReport, _append_user_turn(), _env_float(), _env_int(), NightwatcherObserver, _finalize_analysis_handover(), build_report_iteration_prompt() (+2 more)

### Community 52 - "EventDrillDown.tsx"
Cohesion: 0.10
Nodes (33): three, getEventPulses(), EventSource, BrainCore(), CortexDevPage(), devQueryClient, CortexLiveFeedProps, EventDrillDown() (+25 more)

### Community 53 - "formatter.py"
Cohesion: 0.09
Nodes (15): build_access_denied_home_view(), build_home_tab_view(), _context_line(), create_feedback_block(), format_event_summary(), format_plan_block(), format_task_card(), format_tool_result_blocks() (+7 more)

### Community 54 - "TimeKeeperPage.tsx"
Cohesion: 0.11
Nodes (25): react-dom, createSchedule(), deleteSchedule(), getSchedules(), refineInstructions(), ScheduleCreatePayload, ScheduleItem, toggleSchedule() (+17 more)

### Community 55 - "VcsPlatformPort"
Cohesion: 0.07
Nodes (3): _get_canonical_or_alias(), VcsWorkItem, VcsPlatformPort

### Community 58 - "ws-client.js"
Cohesion: 0.10
Nodes (26): clearIdleTimer(), {
  DEFAULT_WORK_DIR, AGENT_CLI, AGENT_MODEL, AGENT_ROLE,
  EVENT_ID, EPHEMERAL, IDLE_TIMEOUT_MS,
  CLI_429_MAX_RETRIES, CLI_429_INITIAL_DELAY_MS, CLI_429_BACKOFF_MULTIPLIER,
  resolveTimeoutMs, parsePositiveInt, MAX_TASK_WALL_MS, MAX_TIMER_MS,
}, { ensureEventDocument }, { executeCLIStreaming, prepareResultsDir, is429Error }, { filterSkillsByRole, filterSkillsByMode, swapActiveRules, restoreAllSkills }, fs, handleCancel(), handleTask() (+18 more)

### Community 59 - "CortexGraph.tsx"
Cohesion: 0.12
Nodes (30): graphology, ActiveEvent, KGServiceEntity, eventColor(), getExecutiveNeurons(), getStructuralEdges(), DEFAULT_TYPE_BUDGET, evictLru() (+22 more)

### Community 64 - "._github_poll_and_process"
Cohesion: 0.11
Nodes (5): _maybe_refresh_snapshot(), _on_gh_phase_b_created(), _iref(), _try_queue_issue(), _on_gl_phase_b_created()

### Community 65 - "PlanProgress.tsx"
Cohesion: 0.15
Nodes (22): ConversationTurn, BORDER_COLOR, PlanProgressProps, STATUS_ICON, DeferCountdownState, useDeferCountdown(), EMPTY_CONVERSATION, computeDeferProgress() (+14 more)

### Community 66 - "llm_error_classifier.py"
Cohesion: 0.13
Nodes (9): _extract_status_code(), _has_non_retryable_cause(), _is_google_auth_transport_error(), is_rate_limit(), is_transient(), is_transient_llm_error_turn(), _iter_exception_chain(), _matches_mro() (+1 more)

### Community 67 - "observations_mgmt.py"
Cohesion: 0.10
Nodes (10): get_report_client(), render_pdf(), bulk_delete_observations(), BulkDeleteRequest, delete_observation(), export_observations(), generate_observations_report(), rename_observation() (+2 more)

### Community 68 - "server.js"
Cohesion: 0.09
Nodes (18): { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, ensureEventDocument(), fs, path, stageEventDocument(), fetchEventDocument(), fs, { handleRequest } (+10 more)

### Community 70 - "PulseBatch"
Cohesion: 0.10
Nodes (4): PulseBatch, PulsePort, PulseObserver, PulseTracker

### Community 71 - "spawn_event_namer_task"
Cohesion: 0.17
Nodes (7): spawn_event_namer_task(), handle_app_home_opened(), handle_app_mention(), handle_create_event_modal(), handle_darwin_command(), on_dm_message(), fallback_title()

### Community 72 - "jira.py"
Cohesion: 0.14
Nodes (9): approve_mission(), dismiss_mission(), _infer_phase(), _jira_config(), list_missions(), reanalyze_mission(), retry_mission(), _validate_jira_key() (+1 more)

### Community 74 - "NeuronInfoPanel.tsx"
Cohesion: 0.11
Nodes (23): KGServiceDetail, AGENTS, DOMAINS, HEMISPHERE_X, NEURON_DESCRIPTIONS, PHASE_SKILL_FOLDERS, PHASE_TOOL_PRIORITY, PHASES (+15 more)

### Community 75 - "handlers_cross_event.py"
Cohesion: 0.11
Nodes (7): _coerce_turn_int(), handle_recall_pruned_turns(), _parse_turn_int(), _sanitize_recalled(), IdleTimeoutPort, IncidentAdapterPort, StateWatcherPort

### Community 78 - "state/__init__.py"
Cohesion: 0.12
Nodes (3): sanitize_redis_port(), get_redis(), RedisClient

### Community 80 - "dependencies"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 81 - "NodeInspector.tsx"
Cohesion: 0.13
Nodes (21): ArchitectureEvent, ArgoCDOperation, EVENT_LABELS, EventItem(), EventItemProps, healthTone(), lastOperationSummary(), NodeInspector() (+13 more)

### Community 83 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 84 - "claude-guard.js"
Cohesion: 0.14
Nodes (18): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+10 more)

### Community 85 - "handlers_lookup.py"
Cohesion: 0.12
Nodes (8): _safe_int(), _format_bounded_journal(), _safe_seconds(), _auto_complete_step(), _canonical_role(), _is_orchestrator_turn(), _normalize_step_id(), safe_score()

### Community 86 - "reconcile.py"
Cohesion: 0.18
Nodes (9): _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers(), main(), _parse_frontmatter() (+1 more)

### Community 87 - "FlowHistoryPage.tsx"
Cohesion: 0.23
Nodes (16): recharts, getFlowHistory(), FlowSnapshot, FlowHistoryPage(), RANGES, SparkCard(), SparkCardProps, formatTime() (+8 more)

### Community 90 - "cli-setup.js"
Cohesion: 0.13
Nodes (18): { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync }, filterSkillsByMode() (+10 more)

### Community 91 - "observations_reporter.py"
Cohesion: 0.15
Nodes (8): _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), _sample_points(), _summarize(), download_skill_md()

### Community 93 - "utils/__init__.py"
Cohesion: 0.16
Nodes (9): _resolve_maintainer_enum(), get_github_auth(), _dedupe(), _extract_evidence_maintainer_emails(), is_slack_recipient_allowed(), maintainer_env_key(), _resolve_evidence_env_maintainer_emails(), resolve_maintainer_emails() (+1 more)

### Community 95 - "QuotaTracker"
Cohesion: 0.13
Nodes (4): QuotaExhaustedError, QuotaTracker, RequestExceedsBurstError, Reservation

### Community 97 - "devDependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 98 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 99 - "gemini-sidecar/package.json"
Cohesion: 0.11
Nodes (18): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+10 more)

### Community 102 - "get_report"
Cohesion: 0.11
Nodes (6): get_report(), list_reports(), reports_spa_no_slash(), reports_spa_with_slash(), search_reports(), _serve_spa()

### Community 103 - "JiraIncidentAdapter"
Cohesion: 0.15
Nodes (3): _adf_to_text(), _escape_jql_string(), JiraIncidentAdapter

### Community 104 - "._feedback_reject_reason"
Cohesion: 0.13
Nodes (7): _bot_login(), _csv_env(), _consider(), _is_slash_command_only(), _mention_pattern(), _review_ignore_logins(), _review_trusted_associations()

### Community 107 - "ShiftsPage.tsx"
Cohesion: 0.23
Nodes (16): getCurrentShift(), getShiftDetail(), getShiftsList(), ShiftReportFull, ShiftReportSummary, FailedClusterBadge(), getISOWeek(), getWeekDates() (+8 more)

### Community 108 - "catalog-skills.js"
Cohesion: 0.16
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 109 - "slack.py"
Cohesion: 0.12
Nodes (6): extract_tables(), _replace(), get_turn_attachment_color(), _md_table_to_block_kit(), table_block_to_code_block(), _PlanDecision

### Community 111 - "._authorize_plan_decision"
Cohesion: 0.15
Nodes (4): handle_approve(), handle_approve_sha(), handle_home_create_event(), handle_reject()

### Community 114 - "generate_map.py"
Cohesion: 0.19
Nodes (6): _enumerate_gates(), _GateInfo, generate_phase_tool_map(), _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 115 - "JenkinsPlatformPort"
Cohesion: 0.13
Nodes (4): BuildDetails, JenkinsPlatformPort, JobRunState, ViewScanResult

### Community 120 - "._process_candidates"
Cohesion: 0.13
Nodes (3): _flood_service_key(), _outage_service_key(), _service_key()

### Community 126 - "analyzeTokens"
Cohesion: 0.19
Nodes (13): analyzeString(), analyzeTokens(), assignName(), base(), combineCategories(), configEnvGuard(), configFileWriteGuard(), hasSubseq() (+5 more)

### Community 127 - "._extract_context_flags"
Cohesion: 0.15
Nodes (3): compute_dispatch_backpressure(), ContextFlags, _safe_int_env()

### Community 128 - "evaluate_gates"
Cohesion: 0.15
Nodes (7): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), is_wait_for_user_admissible_after_response(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 134 - "adf_to_markdown"
Cohesion: 0.32
Nodes (7): adf_to_markdown(), _apply_marks(), _children(), _render(), _render_list(), _render_list_item(), _render_table_like()

### Community 135 - "has_unevaluated_close_blocker"
Cohesion: 0.20
Nodes (5): has_unevaluated_close_blocker(), _pred_jarvis_response(), _pred_unevaluated_close(), is_jarvis_acknowledgment(), is_stabilization_wake()

### Community 137 - "CiContextCard.tsx"
Cohesion: 0.31
Nodes (9): CiContext, CiContextCardProps, ConsoleTailBlock(), FailedJobRow(), annotationReplacer(), PIPELINE_ANNOTATION_RE, REDACTION_TRIGGER_KEYWORDS, stripAnsi() (+1 more)

### Community 138 - "CortexLiveFeed.tsx"
Cohesion: 0.27
Nodes (9): CortexHeartbeat(), CortexHeartbeatProps, ensureKeyframes(), CortexLiveFeed(), FILTER_PILLS, FilterKey, getStoredFilter(), MESSAGE_STYLES (+1 more)

### Community 139 - "gitGuard"
Cohesion: 0.29
Nodes (10): bareBranchProtected(), configWriteGuard(), externalGitCommand(), gitGuard(), gitQuery(), isProtected(), normRef(), pushGuard() (+2 more)

### Community 140 - "parseShell"
Cohesion: 0.33
Nodes (10): bodySubstitutions(), decodeAnsiC(), isArrayAssignPrefix(), isWordStart(), matchBacktick(), matchParen(), parseShell(), readHeredocStart() (+2 more)

### Community 141 - "generate_event_title"
Cohesion: 0.22
Nodes (3): generate_event_title(), get_adapter(), _get_semaphore()

### Community 144 - "entity_extractor.py"
Cohesion: 0.33
Nodes (5): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship

### Community 149 - "classifyTool"
Cohesion: 0.31
Nodes (9): apiTokens(), apiWriteNeedsGuard(), branchValues(), classifyTool(), hasOpaqueTarget(), httpGuard(), httpMethod(), isReadMethod() (+1 more)

### Community 161 - "validate-mutations.sh"
Cohesion: 0.57
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

### Community 165 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 166 - "state.js"
Cohesion: 0.33
Nodes (4): { AGENT_ROLE }, _blackboardTurns, _inboundMessages, _teammateMessages

### Community 170 - "_append_user_turn"
Cohesion: 0.33
Nodes (3): _append_user_turn(), _is_function_response_part(), _validated_parts()

### Community 171 - "build_gate_context"
Cohesion: 0.33
Nodes (3): build_gate_context(), conversation_has_decayed_turns(), _decay_payload_len()

### Community 177 - "classify"
Cohesion: 0.50
Nodes (4): classify(), main(), shellCategory(), shellNeedsGuard()

## Knowledge Gaps
- **13 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+8 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2625 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **107 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `BlackboardState` to `Brain`, `queue.py`, `logging`, `dependencies.py`, `ConversationTurn`, `EventDocument`, `brain.py`, `auth.py`, `generate_event_title`, `os`, `models.py`, `.get_event`, `.get_graph_data`, `main.py`, `get_all_journal`, `_is_event_closed_or_missing`, `list_shifts`, `nightwatcher_tools.py`, `ConversationMessage`, `._update_event_vcs_context`, `headhunter.py`, `HeadhunterJira`, `get_notebook`, `._downsample_snapshots`, `record_token_usage`, `LiveAPIAdapter`, `BrainSkillLoader`, `observations_mgmt.py`, `jira.py`, `handlers_cross_event.py`, `state/__init__.py`, `DashboardWSAdapter`, `observations_reporter.py`, `get_report`, `slack.py`, `.list_observations`, `ScheduleRepository`?**
  _High betweenness centrality (0.103) - this node is a cross-community bridge._
- **Are the 81 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 81 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `BlackboardState` be split into smaller, more focused modules?**
  _Cohesion score 0.011047345767575323 - nodes in this community are weakly interconnected._
- **Why does `Brain` connect `Brain` to `BlackboardState`, `IdleTimeoutManager`, `queue.py`, `dependencies.py`, `ConversationTurn`, `EventDocument`, `Archivist`, `brain.py`, `._post_agent_recall`, `os`, `models.py`, `ReconcileScheduler`, `._process_with_llm`, `main.py`, `._detect_repetition_collapse`, `agents/__init__.py`, `.get_active_subscription_count`, `.has_subscription`, `.set_headhunter_close_signal`, `BrainSkillLoader`, `PulseBatch`, `DashboardWSAdapter`, `ReflexSearcher`, `JarvisPeerPort`, `slack.py`, `BrainLifecyclePort`, `._extract_context_flags`?**
  _High betweenness centrality (0.065) - this node is a cross-community bridge._
- **Are the 20 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Should `Brain` be split into smaller, more focused modules?**
  _Cohesion score 0.02004965859714463 - nodes in this community are weakly interconnected._