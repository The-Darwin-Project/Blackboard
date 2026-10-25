# Graph Report - Blackboard  (2026-10-25)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 4750 nodes · 10471 edges · 179 communities (82 shown, 97 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 902 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `91ba32eb`
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
- Community 91
- Community 92
- Community 93
- Community 94
- Community 95
- Community 96
- Community 97
- Community 99
- Community 100
- Community 101
- Community 102
- Community 103
- Community 104
- Community 105
- Community 107
- Community 108
- Community 109
- Community 110
- Community 111
- Community 112
- Community 116
- Community 117
- Community 118
- Community 119
- Community 120
- Community 121
- Community 122
- Community 123
- Community 124
- Community 125
- Community 126
- Community 127
- Community 128
- Community 129
- Community 131
- Community 132
- Community 134
- Community 135
- Community 136
- Community 137
- Community 142
- Community 145
- Community 146
- Community 150
- Community 151
- Community 153
- Community 154
- Community 155
- Community 157
- Community 158
- Community 159
- Community 160
- Community 161
- Community 162
- Community 165
- Community 166
- Community 167
- Community 168
- Community 169
- Community 170
- Community 171
- Community 172
- Community 173
- Community 174

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

## Communities (179 total, 97 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.01
Nodes (16): get_all_journal(), get_service_journal(), delete_notebook_note(), get_notebook(), NotePatchRequest, update_notebook_note(), get_event_observations(), get_global_observations() (+8 more)

### Community 1 - "Community 1"
Cohesion: 0.03
Nodes (26): _sanitize_lesson_text(), _get_static_maintainer_emails(), _get_allowed_mention_authors(), _get_static_maintainer_emails(), _safe_int(), create_adapter(), record_token_usage(), get_blackboard() (+18 more)

### Community 2 - "Community 2"
Cohesion: 0.02
Nodes (34): _close_unanswered_fc(), _resolve_escalation_scope(), _build_closed_block(), build_event_header(), _build_identity_block(), _build_journal_block(), _build_mermaid_block(), _build_related_block() (+26 more)

### Community 3 - "Community 3"
Cohesion: 0.03
Nodes (54): get_token_meter(), get_archivist(), get_brain(), get_pulse_tracker(), dismiss_proposals(), DismissRequest, get_all_shadow_interventions(), get_cognitive_graph() (+46 more)

### Community 4 - "Community 4"
Cohesion: 0.03
Nodes (90): recharts, @tanstack/react-query, ApiError, bulkDeleteObservations(), createChatEvent(), deleteNote(), deleteObservation(), exportObservations() (+82 more)

### Community 5 - "Community 5"
Cohesion: 0.05
Nodes (78): three, getCognitiveGraph(), getCortexActivity(), getEventPulses(), getEventReport(), getKGServiceDetail(), getKGServices(), getKGStats() (+70 more)

### Community 8 - "Community 8"
Cohesion: 0.05
Nodes (78): GateContext, _msg_budget_exhausted(), _msg_defer_wake_iter0(), _msg_domain_casual(), _msg_domain_chaotic(), _msg_domain_clear(), _msg_domain_complex(), _msg_hard_strip_defer() (+70 more)

### Community 9 - "Community 9"
Cohesion: 0.05
Nodes (17): AgentConnection, AgentRegistry, agent_websocket_handler(), _heartbeat(), _build_prompt(), _check_security(), consume_wake_task(), _consume() (+9 more)

### Community 10 - "Community 10"
Cohesion: 0.05
Nodes (69): analyzeString(), analyzeTokens(), API_VALUED, apiTokens(), apiWriteNeedsGuard(), assignName(), bareBranchProtected(), base() (+61 more)

### Community 11 - "Community 11"
Cohesion: 0.06
Nodes (28): PulseContext, ShiftIncident, ShiftInvestigation, ShiftReport, NightwatcherObserver, build_manifest_table(), build_report_iteration_prompt(), build_summary_prompt() (+20 more)

### Community 12 - "Community 12"
Cohesion: 0.05
Nodes (23): can_append_message(), can_approve_event(), can_override_domain(), _claims_to_user(), get_user_from_request(), get_user_from_websocket(), _normalize_email(), prompt_display_name() (+15 more)

### Community 13 - "Community 13"
Cohesion: 0.07
Nodes (39): @tanstack/react-table, getReport(), getReports(), ReportFull, ReportMeta, CompactCardStrip(), EventHistory(), TimeRange (+31 more)

### Community 14 - "Community 14"
Cohesion: 0.04
Nodes (13): GraphNode, TicketNode, get_event_document(), _defer_timeline_fields(), _has_active_subscription(), list_active_events(), get_graph_data(), get_mermaid_diagram() (+5 more)

### Community 15 - "Community 15"
Cohesion: 0.05
Nodes (46): handleToolCall(), http, httpGet(), httpPost(), readline, rl, syncHighwater(), TOOLS (+38 more)

### Community 16 - "Community 16"
Cohesion: 0.06
Nodes (11): get_user_from_slack(), format_event_summary(), SlackChannel, handle_app_home_opened(), handle_app_mention(), handle_approve(), handle_create_event_modal(), handle_darwin_command() (+3 more)

### Community 17 - "Community 17"
Cohesion: 0.07
Nodes (48): closeEvent(), enforceCasualDomain(), CiContext, ConversationTurn, CiContextCard(), CiContextCardProps, ConsoleTailBlock(), FailedJobRow() (+40 more)

### Community 18 - "Community 18"
Cohesion: 0.07
Nodes (50): getAlignerPending(), getHeadhunterPending(), getJenkinsPending(), getJiraMissions(), getWaitingApprovalEvents(), HeadhunterTodo, postJiraAction(), EventDocument (+42 more)

### Community 19 - "Community 19"
Cohesion: 0.08
Nodes (52): lucide-react, react, applyLessons(), correctMemory(), createKnowledge(), createLesson(), deleteKnowledge(), deleteLesson() (+44 more)

### Community 20 - "Community 20"
Cohesion: 0.06
Nodes (44): oidc-client-ts, getFlowHistory(), getWSAuthFailureCallback(), setOnUnauthorized(), setTokenGetter(), setWSAuthFailureCallback(), AuthConfig, FlowSnapshot (+36 more)

### Community 21 - "Community 21"
Cohesion: 0.06
Nodes (19): _annotation_replace(), _strip_pipeline_annotations(), _clamp_confidence(), _parse_job_metadata(), _prepare_console_tail(), _redact_build_parameters(), _redact_match(), _redact_secrets_in_text() (+11 more)

### Community 22 - "Community 22"
Cohesion: 0.06
Nodes (19): build_access_denied_home_view(), build_home_tab_view(), _context_line(), create_feedback_block(), extract_tables(), _replace(), format_plan_block(), format_task_card() (+11 more)

### Community 23 - "Community 23"
Cohesion: 0.08
Nodes (38): react-router-dom, getActiveEvents(), getAgents(), getConfig(), getEventDocument(), getEvents(), getKargoStages(), AgentRegistryEntry (+30 more)

### Community 25 - "Community 25"
Cohesion: 0.05
Nodes (6): FlowCollector, ReconcileScheduler, Trigger, QueueTrigger, ResyncTrigger, StalenessGuard

### Community 26 - "Community 26"
Cohesion: 0.06
Nodes (6): KubernetesSpawnHealthAdapter, _PodHealthState, DispatchMetrics, SpawnHealthPort, SpawnPollResult, SpawnStatus

### Community 27 - "Community 27"
Cohesion: 0.08
Nodes (7): on_huddle(), on_progress(), on_huddle(), on_progress(), _compute_processed_up_to(), _sanitize_error_text(), get_registry_and_bridge()

### Community 30 - "Community 30"
Cohesion: 0.08
Nodes (9): _format_graph_context(), get_graph_context(), _parse_props(), _sanitize(), translate_to_lookups(), _acquire(), KnowledgeGraphStore, _sanitize() (+1 more)

### Community 31 - "Community 31"
Cohesion: 0.13
Nodes (44): resolveCommand(), writeAgyMcpServer(), writeClaudeMcpServer(), buildArgoCDMcpConfig(), createAppJWT(), discoverAndGenerateTokens(), _discoverAndGenerateTokensInner(), discoverInstallations() (+36 more)

### Community 32 - "Community 32"
Cohesion: 0.08
Nodes (14): _analyze_series(), _assemble_report(), generate_report(), _render_chart_svg(), _render_chart_with_timeout(), _sample_points(), _summarize(), approve_mission() (+6 more)

### Community 34 - "Community 34"
Cohesion: 0.09
Nodes (35): getFlowMetrics(), FlowMetrics, AgentStreamCard(), AgentStreamCardProps, FloatingWindow(), MessageCards(), Dashboard(), FlowHealthWidget() (+27 more)

### Community 35 - "Community 35"
Cohesion: 0.09
Nodes (35): { AGENT_CLI, AGY_CLI, AGENT_MODEL, AGENT_ROLE, AGENT_EFFORT_LEVEL, resolveTimeoutMs, DEFAULT_WORK_DIR, FINDINGS_FRESHNESS_MS }, buildCLICommand(), CLAUDE_JSON_PATH, cp, executeCLI(), executeCLIStreaming(), FALLBACK_MODEL, fs (+27 more)

### Community 36 - "Community 36"
Cohesion: 0.06
Nodes (6): BuildDetails, JenkinsAdapter, JenkinsPlatformPort, JobResult, JobRunState, ViewScanResult

### Community 40 - "Community 40"
Cohesion: 0.06
Nodes (34): autoprefixer, cronstrue, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, graphology-layout-forceatlas2 (+26 more)

### Community 41 - "Community 41"
Cohesion: 0.11
Nodes (29): @uiw/react-markdown-preview, approveEvent(), rejectEvent(), submitFeedback(), MarkdownViewer(), MermaidBlock(), InlineMarkdownViewerProps, JournalRow() (+21 more)

### Community 42 - "Community 42"
Cohesion: 0.07
Nodes (4): Architect, AgentClient, Developer, SysAdmin

### Community 43 - "Community 43"
Cohesion: 0.09
Nodes (7): handle_select_agent(), handle_close_event(), handle_defer_event(), handle_hold_watch(), handle_wait_for_jarvis(), handle_wait_for_user(), ToolContext

### Community 44 - "Community 44"
Cohesion: 0.09
Nodes (28): @dagrejs/dagre, @xyflow/react, HealthStatus, NodeType, AppNodeData, applyDagreLayout(), applyGridLayout(), applyLayout() (+20 more)

### Community 45 - "Community 45"
Cohesion: 0.08
Nodes (18): _alert_wrapper_retrigger(), _do_retrigger(), _get_jira_reporter(), handle_ask_release_ai(), handle_comment_jira_issue(), handle_fetch_jira_issue(), handle_greenwave(), handle_notify_user_slack() (+10 more)

### Community 46 - "Community 46"
Cohesion: 0.14
Nodes (17): emit_tool_result(), _safe_int(), handle_inspect_event(), handle_post_sticky_note(), handle_read_sticky_notes(), handle_recall_pruned_turns(), handle_consult_deep_memory(), handle_google_web_search() (+9 more)

### Community 47 - "Community 47"
Cohesion: 0.12
Nodes (24): createSchedule(), deleteSchedule(), getSchedules(), refineInstructions(), ScheduleCreatePayload, ScheduleItem, toggleSchedule(), updateSchedule() (+16 more)

### Community 48 - "Community 48"
Cohesion: 0.08
Nodes (4): ScheduleCreateRequest, ScheduledEvent, update_schedule(), ScheduleRepository

### Community 49 - "Community 49"
Cohesion: 0.06
Nodes (7): set_incident_options(), set_agents(), set_blackboard(), set_brain(), set_kargo_observer(), set_registry_and_bridge(), lifespan()

### Community 51 - "Community 51"
Cohesion: 0.09
Nodes (10): render_pdf(), bulk_delete_observations(), BulkDeleteRequest, delete_observation(), export_observations(), generate_observations_report(), rename_observation(), RenameRequest (+2 more)

### Community 52 - "Community 52"
Cohesion: 0.09
Nodes (12): set_archivist(), agent_ws_endpoint(), api_info(), get_config(), get_event_flow(), get_flow_history(), health_check(), list_agents() (+4 more)

### Community 53 - "Community 53"
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

### Community 54 - "Community 54"
Cohesion: 0.08
Nodes (14): get_aligner(), get_architect(), get_argocd_observer(), get_developer(), get_kargo_observer(), get_kg_store(), get_report_client(), get_sysadmin() (+6 more)

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

### Community 59 - "Community 59"
Cohesion: 0.10
Nodes (3): _QueueEntry, StateWatcher, _Subscription

### Community 60 - "Community 60"
Cohesion: 0.15
Nodes (24): graphology, eventColor(), getExecutiveNeurons(), getStructuralEdges(), DEFAULT_TYPE_BUDGET, evictLru(), KNOWLEDGE_RING, KNOWLEDGE_RING_TYPES (+16 more)

### Community 61 - "Community 61"
Cohesion: 0.12
Nodes (10): _adf_to_text(), _escape_jql_string(), JiraIncidentAdapter, adf_to_markdown(), _apply_marks(), _children(), _render(), _render_list() (+2 more)

### Community 64 - "Community 64"
Cohesion: 0.16
Nodes (5): FunctionCall, LLMChunk, LLMPort, LLMResponse, TokenUsage

### Community 69 - "Community 69"
Cohesion: 0.08
Nodes (24): dependencies, cronstrue, @dagrejs/dagre, graphology, graphology-layout-forceatlas2, lucide-react, mermaid, oidc-client-ts (+16 more)

### Community 70 - "Community 70"
Cohesion: 0.13
Nodes (22): getClosedEvents(), ArchitectureEvent, ArgoCDOperation, EVENT_LABELS, EventItem(), EventItemProps, healthTone(), lastOperationSummary() (+14 more)

### Community 71 - "Community 71"
Cohesion: 0.15
Nodes (9): _build_redis_client(), _fetch_commit_sha(), _fetch_file_content(), _fetch_tree(), _get_github_headers(), _get_gitlab_headers(), main(), _parse_frontmatter() (+1 more)

### Community 73 - "Community 73"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 74 - "Community 74"
Cohesion: 0.15
Nodes (10): handle_refresh_github_context(), handle_refresh_gitlab_context(), handle_refresh_kargo_context(), StateWatcherPort, GitHubPrRef, GitLabMrRef, GitLabPipelineRef, KargoStageRef (+2 more)

### Community 75 - "Community 75"
Cohesion: 0.12
Nodes (3): close_redis(), get_redis(), RedisClient

### Community 77 - "Community 77"
Cohesion: 0.13
Nodes (19): { AGENT_CLI }, AGY_HOOKS_PATH, AGY_MCP_PATH, AGY_SKILLS_DIR, CLAUDE_JSON_PATH, CLAUDE_SKILLS_DIR, { execFileSync }, filterSkillsByMode() (+11 more)

### Community 79 - "Community 79"
Cohesion: 0.12
Nodes (4): PulseBatch, PulsePort, PulseObserver, PulseTracker

### Community 80 - "Community 80"
Cohesion: 0.14
Nodes (16): classifyInChild(), claudeMergeGuard(), { execFile, spawn }, gitHead(), GUARD_SCRIPT, { isReadOnlyRoleName, isMutatingRoleName, normalizeRole }, mergeGuard, path (+8 more)

### Community 81 - "Community 81"
Cohesion: 0.11
Nodes (3): _init_tool_names(), _strip_tool_names(), _wrap_section()

### Community 83 - "Community 83"
Cohesion: 0.13
Nodes (9): _apply_sibling_signature(), build_function_response(), build_single_function_response(), compress_contents(), estimate_msg_tokens(), estimate_tokens(), extract_model_parts(), normalize_response_parts() (+1 more)

### Community 85 - "Community 85"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom (+12 more)

### Community 86 - "Community 86"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 88 - "Community 88"
Cohesion: 0.11
Nodes (6): get_report(), list_reports(), reports_spa_no_slash(), reports_spa_with_slash(), search_reports(), _serve_spa()

### Community 89 - "Community 89"
Cohesion: 0.11
Nodes (17): dependencies, adm-zip, jsonwebtoken, ws, description, engines, node, main (+9 more)

### Community 92 - "Community 92"
Cohesion: 0.23
Nodes (16): getCurrentShift(), getShiftDetail(), getShiftsList(), ShiftReportFull, ShiftReportSummary, FailedClusterBadge(), getISOWeek(), getWeekDates() (+8 more)

### Community 94 - "Community 94"
Cohesion: 0.16
Nodes (13): AdmZip, AGY_SKILLS_DIR, CLAUDE_SKILLS_DIR, downloadAndExtract(), fs, http, httpGet(), https (+5 more)

### Community 97 - "Community 97"
Cohesion: 0.14
Nodes (4): handle_classify_event(), handle_request_user_approval(), IdleTimeoutPort, IncidentAdapterPort

### Community 101 - "Community 101"
Cohesion: 0.19
Nodes (6): _enumerate_gates(), _GateInfo, generate_phase_tool_map(), _load_gate_registry(), _render_markdown(), _render_ooda_overlay()

### Community 105 - "Community 105"
Cohesion: 0.26
Nodes (7): handle_message_agent(), handle_reply_to_agent(), handle_report_incident(), handle_notify_gitlab_result(), handle_search_open_incidents(), handle_respond_to_jarvis(), handle_wait_for_agent()

### Community 109 - "Community 109"
Cohesion: 0.15
Nodes (3): compute_dispatch_backpressure(), ContextFlags, _safe_int_env()

### Community 112 - "Community 112"
Cohesion: 0.27
Nodes (12): dismissProposals(), EnhancementProposal, getHandoffReports(), getProposals(), HandoffReport, FilterMode, formatDate(), formatTime() (+4 more)

### Community 117 - "Community 117"
Cohesion: 0.18
Nodes (6): count_agent_waits_in_dispatch_epoch(), evaluate_gates(), is_defer_event_available(), _msg_wait_loop(), _pred_wait_loop(), _single_tool_survives_gates()

### Community 118 - "Community 118"
Cohesion: 0.18
Nodes (10): AGENTS, DOMAINS, HEMISPHERE_X, NEURON_DESCRIPTIONS, PHASE_SKILL_FOLDERS, PHASE_TOOL_PRIORITY, PHASES, StructuralEdge (+2 more)

### Community 119 - "Community 119"
Cohesion: 0.29
Nodes (10): asNumber(), asString(), asStringArray(), Badge(), describeNeuron(), Hdr(), NeuronInfoPanel(), AGENT_NEURON_COLORS (+2 more)

### Community 120 - "Community 120"
Cohesion: 0.33
Nodes (5): Entity, extract_entities(), _get_client(), KnowledgeGraphEntities, Relationship

### Community 121 - "Community 121"
Cohesion: 0.20
Nodes (4): has_unevaluated_close_blocker(), _pred_jarvis_response(), _pred_unevaluated_close(), is_jarvis_acknowledgment()

### Community 122 - "Community 122"
Cohesion: 0.22
Nodes (3): get_quota_tracker(), llm_stats(), receive_telemetry()

### Community 123 - "Community 123"
Cohesion: 0.28
Nodes (4): handle_re_trigger_aligner(), handle_set_phase(), handle_wait_for_verification(), resolve_event_domain()

### Community 135 - "Community 135"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, preview, test, test:watch

### Community 136 - "Community 136"
Cohesion: 0.73
Nodes (5): deny_budget(), in_list(), is_readonly_role(), validate-mutations.sh script, tmo()

## Knowledge Gaps
- **14 isolated node(s):** `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2`, `jsdom`, `postcss` (+9 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2088 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **97 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BlackboardState` connect `Community 0` to `Community 1`, `Community 129`, `Community 2`, `Community 3`, `Community 7`, `Community 9`, `Community 11`, `Community 12`, `Community 14`, `Community 143`, `Community 144`, `Community 146`, `Community 147`, `Community 148`, `Community 21`, `Community 22`, `Community 32`, `Community 46`, `Community 48`, `Community 49`, `Community 51`, `Community 52`, `Community 54`, `Community 58`, `Community 75`, `Community 87`, `Community 88`, `Community 110`?**
  _High betweenness centrality (0.118) - this node is a cross-community bridge._
- **Are the 78 inferred relationships involving `BlackboardState` (e.g. with `DashboardWSAdapter` and `LiveAPIAdapter`) actually correct?**
  _`BlackboardState` has 78 INFERRED edges - model-reasoned connections that need verification._
- **What connects `autoprefixer`, `cronstrue`, `graphology-layout-forceatlas2` to the rest of the system?**
  _14 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.010680363621540092 - nodes in this community are weakly interconnected._
- **Why does `Brain` connect `Community 7` to `Community 0`, `Community 1`, `Community 2`, `Community 9`, `Community 12`, `Community 148`, `Community 22`, `Community 152`, `Community 25`, `Community 27`, `Community 37`, `Community 46`, `Community 49`, `Community 52`, `Community 54`, `Community 59`, `Community 62`, `Community 65`, `Community 72`, `Community 79`, `Community 81`, `Community 82`, `Community 87`, `Community 93`, `Community 102`, `Community 109`?**
  _High betweenness centrality (0.081) - this node is a cross-community bridge._
- **Are the 20 inferred relationships involving `Brain` (e.g. with `DashboardWSAdapter` and `ReflexSearcher`) actually correct?**
  _`Brain` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.03020295837633299 - nodes in this community are weakly interconnected._