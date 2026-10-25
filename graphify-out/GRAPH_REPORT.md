# Graph Report - BlackBoard  (2026-10-22)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 4751 nodes · 10472 edges · 208 communities (94 shown, 114 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 902 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `269e2535`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Community 0
- Community 1
- Community 2
- Community 3
- Community 4
- Community 5
- Community 6
- Community 7
- Community 8
- Community 9
- Community 10
- Community 11
- Community 12
- Community 13
- Community 14
- Community 15
- Community 16
- Community 17
- Community 18
- Community 19
- Community 20
- Community 21
- Community 22
- Community 23
- Community 24
- Community 25
- Community 26
- Community 27
- Community 28
- Community 29
- Community 30
- Community 31
- Community 32
- Community 33
- Community 34
- Community 35
- Community 36
- Community 37
- Community 38
- Community 39
- Community 40
- Community 41
- Community 42
- Community 43
- Community 44
- Community 45
- Community 46
- Community 47
- Community 48
- Community 49
- Community 50
- Community 51
- Community 52
- Community 53
- Community 54
- Community 55
- Community 56
- Community 57
- Community 58
- Community 59
- Community 60
- Community 61
- Community 62
- Community 63
- Community 64
- Community 65
- Community 66
- Community 67
- Community 68
- Community 69
- Community 70
- Community 71
- Community 72
- Community 73
- Community 74
- Community 75
- Community 76
- Community 77
- Community 78
- Community 79
- Community 80
- Community 81
- Community 82
- Community 83
- Community 84
- Community 85
- Community 86
- Community 87
- Community 88
- Community 89
- Community 90
- Community 91
- Community 92
- Community 93
- Community 94
- Community 95
- Community 96
- Community 97
- Community 98
- Community 99
- Community 100
- Community 101
- Community 103
- Community 104
- Community 105
- Community 106
- Community 107
- Community 108
- Community 109
- Community 110
- Community 112
- Community 113
- Community 114
- Community 115
- Community 116
- Community 117
- Community 118
- Community 119
- Community 120
- Community 124
- Community 125
- Community 126
- Community 127
- Community 128
- Community 130
- Community 131
- Community 132
- Community 133
- Community 135
- Community 136
- Community 137
- Community 138
- Community 139
- Community 140
- Community 141
- Community 146
- Community 147
- Community 148
- Community 149
- Community 150
- Community 151
- Community 152
- Community 154
- Community 155
- Community 156
- Community 157
- Community 158
- Community 162
- Community 163
- Community 164
- Community 165
- Community 168
- Community 169
- Community 170
- Community 171
- Community 172
- Community 176
- Community 180
- Community 183
- Community 184
- Community 186
- Community 187
- Community 188
- Community 189
- Community 190
- Community 191
- Community 193
- Community 194
- Community 195
- Community 196
- Community 197
- Community 198
- Community 199
- Community 200
- Community 201

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

### Community 1 - "Community 1"
Cohesion: 0.04
Nodes (12): _heartbeat(), _sanitize_lesson_text(), _check_security(), _safe_int(), safe_execution(), wrapper(), SecurityError, PulseContext (+4 more)

### Community 2 - "Community 2"
Cohesion: 0.03
Nodes (30): get_blackboard(), AppNode, ChatRequest, ChatResponse, EventInput, EventMetrics, EventStatus, EventType (+22 more)

### Community 3 - "Community 3"
Cohesion: 0.04
Nodes (4): Archivist, _decode_cursor(), _encode_cursor(), VectorStore

### Community 4 - "Community 4"
Cohesion: 0.04
Nodes (78): ApiError, bulkDeleteObservations(), deleteObservation(), exportObservations(), ExtractedCorrection, ExtractedLesson, ExtractionResult, generateObservationsReport() (+70 more)

### Community 5 - "Community 5"
Cohesion: 0.04
Nodes (41): get_archivist(), get_brain(), aligner_pending_items(), apply_lessons(), approve_event(), close_event_by_user(), CloseRequest, correct_memory() (+33 more)

### Community 6 - "Community 6"
Cohesion: 0.05
Nodes (22): _get_static_maintainer_emails(), _get_allowed_mention_authors(), _get_static_maintainer_emails(), _safe_int(), create_adapter(), record_token_usage(), RefineRequest, RefineResponse (+14 more)

### Community 7 - "Community 7"
Cohesion: 0.05
Nodes (78): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+70 more)

### Community 8 - "Community 8"
Cohesion: 0.04
Nodes (30): _is_event_closed_or_missing(), _apply_sibling_signature(), build_function_response(), build_single_function_response(), compress_contents(), estimate_msg_tokens(), estimate_tokens(), extract_model_parts() (+22 more)

### Community 9 - "Community 9"
Cohesion: 0.06
Nodes (55): createChatEvent(), getActiveEvents(), getAlignerPending(), getEventDocument(), getJenkinsPending(), getKargoStages(), getWaitingApprovalEvents(), EventDocument (+47 more)

### Community 10 - "Community 10"
Cohesion: 0.05
Nodes (69): analyzeString(), analyzeTokens(), API_VALUED, apiTokens(), apiWriteNeedsGuard(), assignName(), bareBranchProtected(), base() (+61 more)

### Community 12 - "Community 12"
Cohesion: 0.07
Nodes (56): lucide-react, react, applyLessons(), correctMemory(), createKnowledge(), createLesson(), deleteKnowledge(), deleteLesson() (+48 more)

### Community 13 - "Community 13"
Cohesion: 0.05
Nodes (10): ClaudeAdapter, _parse_drain_timeout(), get_token_meter(), TokenMeter, TokenUsageDict, FunctionCall, LLMChunk, LLMPort (+2 more)

### Community 14 - "Community 14"
Cohesion: 0.07
Nodes (49): @uiw/react-markdown-preview, approveEvent(), closeEvent(), enforceCasualDomain(), getEventReport(), rejectEvent(), submitFeedback(), CiContext (+41 more)

### Community 15 - "Community 15"
Cohesion: 0.04
Nodes (22): set_oidc_adapter(), get_aligner(), get_architect(), get_argocd_observer(), get_developer(), get_kargo_observer(), get_kg_store(), get_report_client() (+14 more)

### Community 16 - "Community 16"
Cohesion: 0.06
Nodes (8): on_huddle(), on_progress(), on_huddle(), on_progress(), _compute_processed_up_to(), _sanitize_error_text(), _sanitize_override_reason(), get_registry_and_bridge()

### Community 17 - "Community 17"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 18 - "Community 18"
Cohesion: 0.06
Nodes (47): oidc-client-ts, react-dom, dismissProposals(), EnhancementProposal, getConfig(), getHandoffReports(), getProposals(), getWSAuthFailureCallback() (+39 more)

### Community 19 - "Community 19"
Cohesion: 0.05
Nodes (4): BrainSkillLoader, _SkillCorpus, _wrap_section(), BrainIntrospectionPort

### Community 20 - "Community 20"
Cohesion: 0.08
Nodes (43): react-router-dom, @tanstack/react-table, getReport(), getReports(), ReportFull, ReportMeta, SubjectType, CompactCardStrip() (+35 more)

### Community 22 - "Community 22"
Cohesion: 0.08
Nodes (33): getJiraMissions(), postJiraAction(), JenkinsPendingItem, JiraMission, ContextMenu(), ContextMenuItem, ContextMenuProps, EventSidebar() (+25 more)

### Community 23 - "Community 23"
Cohesion: 0.07
Nodes (19): build_access_denied_home_view(), build_home_tab_view(), _context_line(), create_feedback_block(), extract_tables(), _replace(), format_plan_block(), format_task_card() (+11 more)

### Community 28 - "Community 28"
Cohesion: 0.13
Nodes (44): resolveCommand(), writeAgyMcpServer(), writeClaudeMcpServer(), buildArgoCDMcpConfig(), createAppJWT(), discoverAndGenerateTokens(), _discoverAndGenerateTokensInner(), discoverInstallations() (+36 more)

### Community 29 - "Community 29"
Cohesion: 0.06
Nodes (6): Service, get_event_document(), get_mermaid_diagram(), get_service_details(), get_topology(), list_services()

### Community 30 - "Community 30"
Cohesion: 0.09
Nodes (35): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS }, buildCLICommand(), CLAUDE_JSON_PATH, cp, executeCLI(), executeCLIStreaming(), FALLBACK_MODEL, fs (+27 more)

### Community 31 - "Community 31"
Cohesion: 0.06
Nodes (6): BuildDetails, JenkinsAdapter, JenkinsPlatformPort, JobResult, JobRunState, ViewScanResult

### Community 32 - "Community 32"
Cohesion: 0.09
Nodes (9): handle_message_agent(), handle_reply_to_agent(), handle_select_agent(), handle_defer_event(), handle_hold_watch(), handle_respond_to_jarvis(), handle_wait_for_agent(), handle_wait_for_jarvis() (+1 more)

### Community 33 - "Community 33"
Cohesion: 0.07
Nodes (4): Architect, AgentClient, Developer, SysAdmin

### Community 34 - "Community 34"
Cohesion: 0.09
Nodes (9): _format_graph_context(), get_graph_context(), _parse_props(), _sanitize(), translate_to_lookups(), _acquire(), KnowledgeGraphStore, _sanitize() (+1 more)

### Community 36 - "Community 36"
Cohesion: 0.10
Nodes (31): getFlowMetrics(), FlowMetrics, AgentStreamCard(), AgentStreamCardProps, FloatingWindow(), MessageCards(), Dashboard(), FlowHealthWidget() (+23 more)

### Community 38 - "Community 38"
Cohesion: 0.16
Nodes (28): emit_tool_result(), handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_recall_pruned_turns(), handle_ask_release_ai(), handle_fetch_jira_issue(), handle_greenwave() (+20 more)

### Community 40 - "Community 40"
Cohesion: 0.08
Nodes (14): _annotation_replace(), _strip_pipeline_annotations(), _clamp_confidence(), _env_flag(), _parse_job_metadata(), _prepare_console_tail(), _redact_build_parameters(), _redact_match() (+6 more)

### Community 41 - "Community 41"
Cohesion: 0.07
Nodes (14): _patch_enum_fields(), set_incident_options(), agent_ws_endpoint(), api_info(), get_config(), get_event_flow(), get_flow_history(), get_flow_metrics() (+6 more)

### Community 42 - "Community 42"
Cohesion: 0.12
Nodes (24): createSchedule(), deleteSchedule(), getSchedules(), refineInstructions(), ScheduleCreatePayload, ScheduleItem, toggleSchedule(), updateSchedule() (+16 more)

### Community 43 - "Community 43"
Cohesion: 0.11
Nodes (15): _do_retrigger(), _get_jira_reporter(), handle_comment_jira_issue(), handle_refresh_github_context(), handle_refresh_gitlab_context(), handle_refresh_kargo_context(), _is_darwin_reentrant_caller(), jenkins_retrigger_cooldown_key() (+7 more)

### Community 44 - "Community 44"
Cohesion: 0.09
Nodes (12): can_append_message(), can_approve_event(), can_override_domain(), _claims_to_user(), get_user_from_request(), get_user_from_websocket(), _normalize_email(), require_auth() (+4 more)

### Community 45 - "Community 45"
Cohesion: 0.12
Nodes (16): ShiftIncident, ShiftInvestigation, build_summary_tool(), execute_tool(), get_phase_tools(), _handle_consult_deep_memory(), _handle_declare_clusters(), _handle_dispatch_investigation() (+8 more)

### Community 46 - "Community 46"
Cohesion: 0.11
Nodes (10): get_user_from_slack(), format_event_summary(), handle_app_home_opened(), handle_app_mention(), handle_approve(), handle_create_event_modal(), handle_darwin_command(), handle_home_create_event() (+2 more)

### Community 48 - "Community 48"
Cohesion: 0.10
Nodes (27): getClosedEvents(), getEvents(), ActiveEvent, ArchitectureEvent, ArgoCDOperation, ActivityStream(), ArchitectureGraph(), EVENT_LABELS (+19 more)

### Community 49 - "Community 49"
Cohesion: 0.08
Nodes (29): autoprefixer, cronstrue, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, graphology-layout-forceatlas2 (+21 more)

### Community 50 - "Community 50"
Cohesion: 0.11
Nodes (25): three, getEventPulses(), BrainCore(), CortexDevPage(), CortexHeartbeat(), CortexHeartbeatProps, ensureKeyframes(), CortexLiveFeed() (+17 more)

### Community 51 - "Community 51"
Cohesion: 0.16
Nodes (28): getCognitiveGraph(), getCortexActivity(), getKGServiceDetail(), getKGServices(), getKGStats(), getKnowledgeById(), getLessonById(), getMemory() (+20 more)

### Community 52 - "Community 52"
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

### Community 53 - "Community 53"
Cohesion: 0.11
Nodes (13): _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), render_pdf(), _sample_points(), _summarize() (+5 more)

### Community 54 - "Community 54"
Cohesion: 0.10
Nodes (9): _build_prompt(), consume_wake_task(), _consume(), _dispatch_timeout_s(), dispatch_to_agent(), _consume_queue(), _sanitize_stdout(), send_cancel() (+1 more)

### Community 56 - "Community 56"
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

### Community 57 - "Community 57"
Cohesion: 0.09
Nodes (17): hasRegistryCredentials(), { BRAIN_HTTP_URL, DEFAULT_WORK_DIR }, fs, path, stageEventDocument(), fetchEventDocument(), fs, { handleRequest } (+9 more)

### Community 58 - "Community 58"
Cohesion: 0.14
Nodes (25): graphology, eventColor(), getExecutiveNeurons(), getStructuralEdges(), DEFAULT_TYPE_BUDGET, evictLru(), KNOWLEDGE_RING, KNOWLEDGE_RING_TYPES (+17 more)

### Community 59 - "Community 59"
Cohesion: 0.09
Nodes (5): Pulse, PulseBatch, PulsePort, PulseObserver, PulseTracker

### Community 61 - "Community 61"
Cohesion: 0.09
Nodes (5): get_quota_tracker(), QuotaExhaustedError, QuotaTracker, llm_stats(), receive_telemetry()

### Community 63 - "Community 63"
Cohesion: 0.11
Nodes (11): get_pulse_tracker(), dismiss_proposals(), DismissRequest, get_all_shadow_interventions(), get_cognitive_graph(), get_cortex_activity(), get_cortex_status(), get_event_shadow_interventions() (+3 more)

### Community 64 - "Community 64"
Cohesion: 0.15
Nodes (21): @tanstack/react-query, getCurrentShift(), getIncidents(), getShiftDetail(), getShiftsList(), Incident, ShiftReportFull, ShiftReportSummary (+13 more)

### Community 66 - "Community 66"
Cohesion: 0.08
Nodes (5): create_schedule(), delete_schedule(), get_schedule(), list_schedules(), toggle_schedule()

### Community 67 - "Community 67"
Cohesion: 0.14
Nodes (3): DashboardWSAdapter, prompt_display_name(), resolve_approval_identity()

### Community 71 - "Community 71"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 72 - "Community 72"
Cohesion: 0.15
Nodes (9): _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers(), main(), _parse_frontmatter() (+1 more)

### Community 73 - "Community 73"
Cohesion: 0.11
Nodes (3): _QueueEntry, StateWatcher, _Subscription

### Community 74 - "Community 74"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 75 - "Community 75"
Cohesion: 0.16
Nodes (17): recharts, getFlowHistory(), FlowSnapshot, ObservationSeries, formatTime(), RANGES, SparkCard(), SparkCardProps (+9 more)

### Community 76 - "Community 76"
Cohesion: 0.12
Nodes (3): AgentConnection, AgentRegistry, agent_websocket_handler()

### Community 77 - "Community 77"
Cohesion: 0.12
Nodes (3): close_redis(), get_redis(), RedisClient

### Community 79 - "Community 79"
Cohesion: 0.13
Nodes (19): { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync }, filterSkillsByMode() (+11 more)

### Community 80 - "Community 80"
Cohesion: 0.14
Nodes (17): @dagrejs/dagre, @xyflow/react, applyDagreLayout(), applyGridLayout(), applyLayout(), ArchitectureGraphInner(), buildGraph(), computeIdHash() (+9 more)

### Community 83 - "Community 83"
Cohesion: 0.17
Nodes (16): ConversationTurn, DeferCountdownBar(), STATUS_COLORS, TICKET_COLORS, TicketNodeComponent(), TicketNodeData, PlanProgressProps, PlanStep (+8 more)

### Community 84 - "Community 84"
Cohesion: 0.13
Nodes (19): KGServiceDetail, AGENTS, DOMAINS, HEMISPHERE_X, NEURON_DESCRIPTIONS, PHASE_SKILL_FOLDERS, PHASE_TOOL_PRIORITY, PHASES (+11 more)

### Community 85 - "Community 85"
Cohesion: 0.14
Nodes (16): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+8 more)

### Community 87 - "Community 87"
Cohesion: 0.10
Nodes (6): _defer_timeline_fields(), _has_active_subscription(), list_active_events(), list_closed_events(), list_waiting_approval_events(), _serialize_evidence()

### Community 88 - "Community 88"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 89 - "Community 89"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 91 - "Community 91"
Cohesion: 0.13
Nodes (3): ArchitectureEvent, list_events(), MetricsRepository

### Community 92 - "Community 92"
Cohesion: 0.16
Nodes (4): ShiftReport, NightwatcherObserver, build_extend_tool(), build_report_tool()

### Community 93 - "Community 93"
Cohesion: 0.11
Nodes (6): get_report(), list_reports(), reports_spa_no_slash(), reports_spa_with_slash(), search_reports(), _serve_spa()

### Community 94 - "Community 94"
Cohesion: 0.11
Nodes (17): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+9 more)

### Community 95 - "Community 95"
Cohesion: 0.15
Nodes (3): _adf_to_text(), _escape_jql_string(), JiraIncidentAdapter

### Community 98 - "Community 98"
Cohesion: 0.16
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 99 - "Community 99"
Cohesion: 0.12
Nodes (4): handle_request_user_approval(), IdleTimeoutPort, IncidentAdapterPort, StateWatcherPort

### Community 100 - "Community 100"
Cohesion: 0.13
Nodes (3): get_event_observations(), get_global_observations(), export_observations()

### Community 103 - "Community 103"
Cohesion: 0.15
Nodes (7): build_manifest_table(), build_report_iteration_prompt(), build_summary_prompt(), build_system_prompt(), extract_event_links(), extract_full_links(), _normalize_gitlab_host()

### Community 104 - "Community 104"
Cohesion: 0.19
Nodes (6): _enumerate_gates(), _GateInfo, generate_phase_tool_map(), _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 107 - "Community 107"
Cohesion: 0.13
Nodes (3): get_all_journal(), get_service_journal(), get_event_report()

### Community 109 - "Community 109"
Cohesion: 0.19
Nodes (13): EventSource, KGServiceEntity, CortexGraphProps, GraphLoaderProps, PulseTimelineProps, CognitiveGraphResponse, CortexHeartbeatMessage, FrictionIndicator (+5 more)

### Community 110 - "Community 110"
Cohesion: 0.20
Nodes (11): HealthStatus, NodeType, AppNodeData, ARGOCD_HEALTH_COLORS, SYNC_ICONS, GENERIC_TAGS, HEALTH_COLORS, NODE_ICONS (+3 more)

### Community 115 - "Community 115"
Cohesion: 0.15
Nodes (3): compute_dispatch_backpressure(), ContextFlags, _safe_int_env()

### Community 118 - "Community 118"
Cohesion: 0.17
Nodes (3): ChatEventRequest, ChatEventResponse, create_chat_event()

### Community 127 - "Community 127"
Cohesion: 0.18
Nodes (5): _alert_wrapper_retrigger(), handle_notify_user_slack(), _resolve_maintainer_enum(), _resolve_slack_user(), build_event_report_md()

### Community 128 - "Community 128"
Cohesion: 0.18
Nodes (6): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 131 - "Community 131"
Cohesion: 0.33
Nodes (5): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship

### Community 132 - "Community 132"
Cohesion: 0.20
Nodes (4): has_unevaluated_close_blocker(), _pred_jarvis_response(), _pred_unevaluated_close(), is_jarvis_acknowledgment()

### Community 135 - "Community 135"
Cohesion: 0.36
Nodes (8): devQueryClient, MOCK_CORTEX_STATUS, MOCK_EVENT_ID, MOCK_NEURONS, MOCK_PULSE_BATCHES, MOCK_SHADOW, MOCK_THINKING, MOCK_WHISPERS

### Community 148 - "Community 148"
Cohesion: 0.57
Nodes (7): adf_to_markdown(), _apply_marks(), _children(), _render(), _render_list(), _render_list_item(), _render_table_like()

### Community 149 - "Community 149"
Cohesion: 0.32
Nodes (7): getHeadhunterPending(), HeadhunterTodo, ACTION_BADGE, formatAge(), HeadhunterQueuePanel(), renderItem(), PIPELINE_DOT

### Community 151 - "Community 151"
Cohesion: 0.29
Nodes (4): @tailwindcss/vite, vite, @vitejs/plugin-react, vitest

### Community 152 - "Community 152"
Cohesion: 0.29
Nodes (3): handle_report_incident(), _resolve_escalation_scope(), handle_search_open_incidents()

### Community 155 - "Community 155"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 156 - "Community 156"
Cohesion: 0.73
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

## Knowledge Gaps
- **14 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+9 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2089 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **114 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `Community 0` to `Community 1`, `Community 2`, `Community 5`, `Community 6`, `Community 8`, `Community 11`, `Community 15`, `Community 19`, `Community 21`, `Community 150`, `Community 23`, `Community 154`, `Community 27`, `Community 29`, `Community 164`, `Community 165`, `Community 38`, `Community 166`, `Community 40`, `Community 41`, `Community 170`, `Community 171`, `Community 44`, `Community 45`, `Community 173`, `Community 167`, `Community 177`, `Community 178`, `Community 179`, `Community 53`, `Community 66`, `Community 67`, `Community 203`, `Community 204`, `Community 77`, `Community 87`, `Community 90`, `Community 91`, `Community 92`, `Community 93`, `Community 100`, `Community 101`, `Community 107`, `Community 112`, `Community 117`, `Community 118`?**
  _High betweenness centrality (0.148) - this node is a cross-community bridge._
- **Are the 78 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 78 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _14 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.018108068955526583 - nodes in this community are weakly interconnected._
- **Why does `Brain` connect `Community 11` to `Community 0`, `Community 130`, `Community 2`, `Community 6`, `Community 8`, `Community 15`, `Community 16`, `Community 19`, `Community 21`, `Community 23`, `Community 33`, `Community 37`, `Community 38`, `Community 41`, `Community 172`, `Community 181`, `Community 182`, `Community 59`, `Community 60`, `Community 61`, `Community 67`, `Community 73`, `Community 86`, `Community 96`, `Community 101`, `Community 115`, `Community 116`, `Community 119`, `Community 120`, `Community 126`?**
  _High betweenness centrality (0.065) - this node is a cross-community bridge._
- **Are the 20 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.0388748419721871 - nodes in this community are weakly interconnected._