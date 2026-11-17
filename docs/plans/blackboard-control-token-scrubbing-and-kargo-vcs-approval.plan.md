---
name: blackboard-control-token-scrubbing-and-kargo-vcs-approval
overview: Strip Gemini multimodal control tokens in streaming, memory, and syntax sanitizers, enforce context-aligned steering recovery in Brain with Slack isolation, and resolve Kargo MR VCS approval SHA with corporate TLS in Darwin BlackBoard
jira: VMER-2398
jira_url: https://redhat.atlassian.net/browse/VMER-2398
docs_hub_plan: null
docs_hub_mr: null
todos:
  - id: step-1
    content: "[Complicated] Model Control Token Scrubbing & Streaming Holdback in types.py & prompt_sanitize.py: Define _CONTROL_TOKENS_RE and comprehensive _CONTROL_TOKEN_PREFIXES including closing tags (</thought>, </think>, </image>), integrate multi-pass stripping into prompt_sanitize.py to defeat nested token injection, and update split_stream_call_syntax to hold back partial '<' prefix tails across chunk boundaries up to 32 chars without disturbing [!call:...!] holdback or wire heartbeat semantics"
    status: completed
  - id: step-2
    content: "[Complex] Stream, Stop Sequences & Memory Part Sanitization in gemini_client.py: Configure stop_sequences=['<end_of_image>'] in GenerateContentConfig (internal to GeminiAdapter), scrub stream_text_buffer before yielding LLMChunk, discard partial prefix tails in stream tail flush (lines 1294-1305), and sanitize candidate text parts on a copy in generate_stream and unary generate, strictly preserving thought_signature carriers and preventing empty text parts from entering model replay"
    status: completed
  - id: step-3
    content: "[Complex] Brain Context-Aligned Steering Recovery & Slack Isolation in brain.py & slack.py: In slack.py, add ('system', 'steering') to _INTERNAL_TURNS. In brain.py, when clean_text strips to empty/None without tool calls, bypass response turn and _waiting_for_user park, inject internal steering turn using turn=0 and _append_and_broadcast, and enforce bounded retry limit (<= 2) with lifecycle reset on successful turns, event close, and stale cleanup"
    status: completed
  - id: step-4
    content: "[Complicated] Canonical Kargo Promotion MR Ingestion Seeding in aligner.py & handlers_integration.py: Standardize on canonical GitLabPlatform.parse_mr_url with 2-tuple unpacking (project_id, mr_iid = parsed) in handle_failed_promotion and handle_refresh_kargo_context (using bb = ctx.get_blackboard()), eliminating duplicate URL parsers and seeding evidence.gitlab_context with target_url, mr_iid, and project_id upon event creation and promotion refresh"
    status: completed
  - id: step-5
    content: "[Complicated] Headhunter GitLab SHA Persistence & URL Encoding in headhunter_gitlab.py: In both create_event (lines 353-371) and refresh_mr_state (lines 500-549), extract head_sha from sha or diff_refs.head_sha and include in gitlab_context update payload; URL-encode project_id with quote(safe='') in REST API paths"
    status: completed
  - id: step-6
    content: "[Complicated] VCS Approval Live SHA Resolution & Corporate TLS in vcs_approval.py & Helm: URL-encode project path namespaces with urllib.parse.quote(safe='') in _resolve_gitlab_head, return (mr_iid, None) on live query failure to preserve MR ID while failing closed on SHA, add fallback to evidence.kargo_context.mr_url when gitlab_context is missing (unpacked as 2-tuple), implement _resolve_ca_bundle probing OpenShift mount path /etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem with fail-closed semantics (never verify=False), and mount OpenShift config-trusted-cabundle in BlackBoard/helm/templates/deployment.yaml"
    status: completed
  - id: step-7
    content: "[Complicated] Comprehensive ATDD Unit & Integration Verification: Add test scenarios in tests/test_vcs_approval.py (URL encoding with quote(safe=''), corporate CA resolution without verify=False, fail-closed approval, 168-case JS/Python parity, refactoring 5 existing fallback assertions from 'stale-sha' to None), tests/test_gemini_client_quota.py (control token stripping, closing tag holdback, thought_signature preservation, stream tail flush with prefix discard, unary generate sanitization), tests/test_headhunter.py (SHA persistence in create_event and refresh_mr_state), tests/test_aligner_escalation_gate.py (canonical URL parsing with tuple unpacking), tests/test_brain_steering_recovery.py (steering turn injection, turn=0 broadcast, retry counter lifecycle, Slack isolation)"
    status: completed
isProject: false
---

# Architecture & Implementation Plan: BlackBoard Control Token Scrubbing & Kargo MR VCS Approval SHA Resolution

**Jira Issue:** [VMER-2398](https://redhat.atlassian.net/browse/VMER-2398) (linked to incident [VMER-2397](https://redhat.atlassian.net/browse/VMER-2397)) | **Docs-Hub Plan:** N/A (Internal BlackBoard service bugfix & contract alignment)

---

## 1. Problem Statement & Architecture Context

During production event `evt-d0a04eb2` (investigating Kargo promotion timeout on MR !25 for `kargo-updater`), two systemic failures crippled autonomous resolution:

1. **Multimodal Model Control Token Leakage (`<end_of_image>...`)**:
   - In `BlackBoard/src/agents/llm/gemini_client.py` and `BlackBoard/src/agents/llm/types.py`, streaming chunks from `gemini-4-carbon` (with extended thoughts) emitted raw control tokens (`<end_of_image>`).
   - Token ID `256000` is the reserved End-of-Image (EOI) boundary delimiter in Google's multimodal architecture. Under high-temperature thinking without image inputs, the text decoder occasionally sampled token `256000`, autoregressively repeating it 23 times in Turn 7 and 15 times in Turn 17.
   - `sanitize_call_syntax()` only stripped `[!call:...!]` syntax. Brain treated the 23-repetition control token string (322 chars) as valid user-facing text.
   - Because `_REPETITION_MIN_CHARS = 2000`, runaway repetition collapse never triggered.
   - Brain emitted a public `actor="brain", action="response"` turn containing `<end_of_image>`, parked chat/slack in `_waiting_for_user`, and stalled the event loop for ~80 seconds until the scheduler re-triggered.

2. **Kargo MR Ingestion Disconnect & VCS Approval SHA Lock**:
   - In `BlackBoard/src/agents/aligner.py:handle_failed_promotion`, Kargo promotion failure extracted `mr_url` to `evidence.kargo_context`, but left `evidence.gitlab_context` as `None`.
   - When FRIDAY called `refresh_gitlab_context` on MR !25 (Turn 14), `headhunter_gitlab.py:refresh_mr_state` queried the GitLab API (obtaining `sha="d461a00c..."`), but dropped `sha` and `head_sha` from the update payload passed to `update_event_gitlab_context`.
   - When human approval arrived (Turn 39), `vcs_approval.py:resolve_live_head_sha` invoked `_resolve_gitlab_head`. The query failed because:
     a. `project_id` was unencoded in the GitLab REST path (`/projects/openshift-virtualization/downstream-configuration/...`), causing GitLab's router to return HTTP 404.
     b. `httpx.AsyncClient` defaulted to `verify=True` (`certifi`), failing TLS verification against internal Red Hat GitLab (`gitlab.cee.redhat.com`) with `SSLCertVerificationError` (`[SSL: CERTIFICATE_VERIFY_FAILED] self-signed certificate in certificate chain`).
     c. `fallback_sha` in `evidence.gitlab_context` was `None`.
   - Consequently, `approved_mr_sha` was stamped as `null`/`None`.
   - At Turn 46, when the developer agent invoked `glab mr merge 25`, the sidecar hook `merge-guard.js` evaluated `approvalVerdict`:
     `Merge REFUSED: live HEAD (d461a00c...) differs from authenticated approval SHA (null)`.
   - The developer was blocked, forcing human intervention.

---

## 2. Architecture Map (Data Flow & Boundaries)

```mermaid
sequenceDiagram
    autonumber
    participant K as Kargo / Aligner
    participant B as Brain (FRIDAY)
    participant L as Slack Channel
    participant G as Gemini Client (LLM)
    participant H as Headhunter (GitLab)
    participant V as VCS Approval Util
    participant S as Sidecar (merge-guard)

    Note over K,B: Step 4: Canonical Ingestion Seeding
    K->>B: Promotion failed event (mr_url present)
    Note over K: Canonical GitLabPlatform.parse_mr_url -> 2-tuple unpack -> seed gitlab_context

    Note over B,G: Steps 1-3: Stream Scrubbing, Safety & Steering Recovery
    B->>G: Generate turns (stop_sequences=["<end_of_image>"])
    G-->>B: Stream chunks
    Note over G,B: types.py + gemini_client.py scrub control tokens (open + close tags), discard prefix tails & preserve thought_signatures; brain.py injects internal steering turn (turn=0, broadcasted)
    Note over B,L: slack.py filters ("system", "steering") via _INTERNAL_TURNS

    Note over B,H: Step 5: Context Refresh & Head SHA Persistence
    B->>H: refresh_gitlab_context (URL-encoded project_id)
    H-->>B: MR State fetched from GitLab API
    Note over H: Persist head_sha & sha into gitlab_context

    Note over B,V: Step 6: Maintainer Approval Live VCS Resolution
    B->>V: resolve_live_head_sha(event)
    Note over V: URL-encoded project path + OpenShift CA trust bundle (fail-closed (mr_iid, None), never verify=False)
    V-->>B: Return (mr_iid="25", approved_mr_sha="d461a00c...")
    B->>B: Store approval with valid approved_mr_sha

    Note over B,S: Step 7: Dispatch Developer Agent
    B->>S: glab mr merge 25
    S->>S: merge-guard verifies live HEAD == approved_mr_sha
    S-->>B: Merge ALLOWED
```

---

## 3. Affected Files & Strict Constraints

1. **`BlackBoard/src/agents/llm/types.py`**:
   - `scan_call_syntax`, `sanitize_call_syntax`, `split_stream_call_syntax`.
   - `@ai-rules`: Provider-agnostic plain dicts. Parse fallback syntax via single linear pass, NO lazy dotall regex ReDoS. Holdback buffer overflow (`> 16384` chars) discards fragment. Bare `LLMChunk()` heartbeat protocol must not be disrupted. Hold back both open (`<thought>`, `<end_of_image>`) and closing (`</thought>`, `</think>`) control token prefixes up to 32 chars. In `sanitize_call_syntax`, run control token regex in a bounded convergence loop (`<= 4` passes).

2. **`BlackBoard/src/utils/prompt_sanitize.py`**:
   - Add control token stripping to `strip_xml_fences` with multi-pass convergence loop (`_FENCE_MAX_PASSES = 8`) to eliminate nested control token reassembly (`<end_<end_of_image>of_image>`). Preserves pure sync, dependency-free boundary.

3. **`BlackBoard/src/agents/llm/gemini_client.py`**:
   - `_stream_chunks` (lines 1266–1305), `generate` (lines 927–961), `raw_parts` packaging (lines 1337+), `GenerateContentConfig` generation.
   - `@ai-rules`: Only import `google.genai` inside this file. Add `stop_sequences=["<end_of_image>"]` internal to `GeminiAdapter` config. In `_stream_chunks`, scrub `stream_text_buffer` with `_CONTROL_TOKENS_RE` in tail flush (lines 1294–1305); if `stream_text_buffer` begins with any prefix in `_CONTROL_TOKEN_PREFIXES`, discard it before calling `scan_call_syntax`. Sanitize candidate text parts on a copy in `generate_stream` and unary `generate`, strictly preserving parts carrying `thought_signature` and preventing empty text parts from being packaged.

4. **`BlackBoard/src/channels/slack.py`**:
   - `_INTERNAL_TURNS`: Add `("system", "steering")` to prevent internal recovery turns from broadcasting into user Slack threads.

5. **`BlackBoard/src/agents/brain.py`**:
   - Lines 2619, 2849, 2969–3004.
   - `@ai-rules`: `_waiting_for_user` stops the event loop without idle timeout backstop. When `clean_text` is empty and no tool calls occurred, bypass public turn and park. Inject internal context-aligned steering turn referencing phase, domain, and eligible tools. Use `turn=0` for atomic turn assignment and persist via `await self._append_and_broadcast(event_id, turn)`. Track retries in `self._empty_output_retries[event_id]` (capping at `<= 2`), resetting on valid text or tool turn and on event close / stale cleanup.

6. **`BlackBoard/src/agents/aligner.py` & `BlackBoard/src/agents/handlers_integration.py`**:
   - Standardize on canonical `GitLabPlatform.parse_mr_url` to parse `mr_url`, unpacking as 2-tuple `project_id, mr_iid = parsed`. In `handlers_integration.py:handle_refresh_kargo_context`, obtain blackboard handle via `bb = ctx.get_blackboard()`. Seed `evidence.gitlab_context` with `project_id`, `mr_iid`, and `target_url`.
   - `@ai-rules`: AIR GAP: NO `kubernetes` or `git` imports allowed in aligner.

7. **`BlackBoard/src/agents/headhunter_gitlab.py`**:
   - In `create_event` (lines 353–371) and `refresh_mr_state` (lines 500–549), extract `head_sha = mr_data.get("sha") or (mr_data.get("diff_refs") or {}).get("head_sha")` and persist into `gitlab_context`. URL-encode `project_id` using `urllib.parse.quote(..., safe="")` in REST API paths.

8. **`BlackBoard/src/utils/vcs_approval.py`**:
   - `resolve_live_head_sha`, `_resolve_gitlab_head`, `verify_merge_guard`.
   - `@ai-rules` Rule 3: TLS verification is NEVER disabled on live approval calls. `_resolve_ca_bundle` probes env vars and `/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem`, falling back to `True` (system store) or failing closed. Never return `False`. Live VCS resolution fails closed returning `(mr_iid, None)` if live API query fails or context is missing. Maintain 100% lockstep parity with `gemini-sidecar/hooks/merge-guard.js:approvalVerdict`.

9. **`BlackBoard/helm/templates/deployment.yaml` & `helm/values.yaml`**:
   - Mount OpenShift's managed `config-trusted-cabundle` ConfigMap to `/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem` (subPath: `ca-bundle.crt`) on both the Brain container and the `skill-reconciler` container.
   - Export `SSL_CERT_FILE` and `REQUESTS_CA_BUNDLE` pointing to `/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem`.

10. **`BlackBoard/tests/test_brain_steering_recovery.py` & `tests/test_vcs_approval.py`**:
    - Dedicated test suite for Brain empty-output steering recovery, atomic `turn=0` broadcast, retry counter lifecycle, and Slack internal turn isolation.
    - In `tests/test_vcs_approval.py`, update 5 existing fallback assertions (lines 83, 101, 116, 129, 139) from `assert sha == "stale-sha"` to `assert sha is None`.

---

## 4. Implementation Strategy

1. **Defense-in-Depth Control Token Sanitization & Model Safety**:
   - **Tier 1 (Decoder constraint)**: Configure `stop_sequences=["<end_of_image>"]` in `types.GenerateContentConfig` in `gemini_client.py` (internal to adapter).
   - **Tier 2 (Adapter wire sanitization & memory hygiene)**: `types.py:sanitize_call_syntax` strips complete tokens using precompiled `_CONTROL_TOKENS_RE` in a bounded loop. `split_stream_call_syntax` holds back `<` suffixes matching open and closing control token prefixes (`_CONTROL_TOKEN_PREFIXES`) across SSE chunks up to 32 chars. In `gemini_client.py`, stream tail flush (lines 1294–1305) scrubs `stream_text_buffer` and discards any partial prefix tail matching `_CONTROL_TOKEN_PREFIXES`. `gemini_client.py` sanitizes `raw_parts` on a copy across both streaming and unary `generate()`, strictly preserving parts carrying `thought_signature` and omitting empty text parts to prevent model 400 replay crashes. Multi-pass loop in `prompt_sanitize.py` prevents nested token injection.
   - **Tier 3 (Context-aligned controller recovery & Slack isolation)**: `brain.py:_process_with_llm` guards against empty/falsy text responses, avoiding spurious public turns and event loop stalling. It injects a context-aligned steering turn referencing `phase`, `domain`, and `eligible_tools`, using `turn=0` and `_append_and_broadcast`. Retries are bounded (`<= 2`) and reset on subsequent successful turns, event close, or stale cleanup. `slack.py` adds `("system", "steering")` to `_INTERNAL_TURNS` to prevent user-facing Slack notifications.

2. **End-to-End MR Context Pipeline & Fail-Closed VCS Security**:
   - **Ingestion**: `aligner.py:handle_failed_promotion` uses `GitLabPlatform.parse_mr_url`, unpacking as 2-tuple `project_id, mr_iid = parsed` to seed `evidence.gitlab_context`.
   - **Synchronization**: `handlers_integration.py:handle_refresh_kargo_context` updates `gitlab_context` using `bb = ctx.get_blackboard()` and canonical 2-tuple unpacking if a new promotion yields an updated `mr_url`.
   - **Refresh & Creation**: `headhunter_gitlab.py` captures `sha` and `head_sha` in both `create_event` and `refresh_mr_state`, encoding project paths with `quote(safe="")`.
   - **Approval Security**: `vcs_approval.py:resolve_live_head_sha` handles URL-encoded project paths (`quote(safe="")`), resolves corporate CA bundles safely without `verify=False` fallback, falls back to `kargo_context.mr_url` (unpacked as 2-tuple) if needed, and returns the verified HEAD SHA. If live query fails, it logs an explicit security warning and fails closed: returns `(mr_iid, None)`, preserving MR IID while denying merge approval.
   - **Infrastructure**: `BlackBoard/helm` mounts OpenShift's `config-trusted-cabundle` ConfigMap to `/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem` on Brain and skill-reconciler containers and configures `SSL_CERT_FILE`/`REQUESTS_CA_BUNDLE`.
   - **Sidecar Gate**: `gemini-sidecar/hooks/merge-guard.js` receives `approved_mr_sha` matching live git HEAD, authorizing clean developer merges.

---

## 5. Atomic Execution Steps

### Step 1: [Complicated] Model Control Token Scrubbing & Streaming Holdback in `types.py` & `prompt_sanitize.py`
- **Files**:
  - `BlackBoard/src/agents/llm/types.py`
  - `BlackBoard/src/utils/prompt_sanitize.py`
- **Action**:
  1. In `types.py`:
     ```python
     _CONTROL_TOKENS_RE = re.compile(
         r"<\/?(?:end_of_image|image|start_of_turn|end_of_turn|thought|think|internal_model_call)>",
         re.IGNORECASE,
     )
     _CONTROL_TOKEN_PREFIXES = (
         "<end_", "<image", "<start_", "<thought", "<think", "<internal_",
         "</end_", "</image", "</start_", "</thought", "</think", "</internal_",
     )
     ```
  2. In `sanitize_call_syntax(text, *, warn=True)`:
     - Run `_CONTROL_TOKENS_RE.sub("", text)` in a bounded loop (`<= 4` passes) until convergence.
     - Perform `scan_call_syntax()`.
     - Strip whitespace. If empty, return `None`.
  3. In `split_stream_call_syntax(buffer)`:
     - Clean complete control tokens with `_CONTROL_TOKENS_RE.sub("", buffer)`.
     - Detect partial trailing control tokens: if `clean` ends with `<` or any prefix of `_CONTROL_TOKEN_PREFIXES` up to 32 chars, hold back the suffix in `held_back`.
     - On stream completion, any held-back `<` suffix that does not form a valid control token prefix is flushed as clean text.
     - Preserve existing `_CALL_OPEN = "[!call:"` holdback and `MAX_STREAM_CALL_SYNTAX_BUFFER` overflow checks.
  4. In `src/utils/prompt_sanitize.py`:
     - Update `strip_xml_fences` to include control tokens in the multi-pass convergence loop (`_FENCE_MAX_PASSES = 8`), preventing nested token reassembly (`<end_<end_of_image>of_image>`). Define the control token pattern locally or extend `_FENCE_TAGS` with literal tokens rather than importing from `src.agents.llm.types`, strictly preserving `prompt_sanitize.py`'s pure, dependency-free boundary.
- **Verification**: Run `cd BlackBoard && ./venv/bin/pytest tests/test_gemini_client_quota.py`.

### Step 2: [Complex] Stream, Stop Sequences & Memory Part Sanitization in `gemini_client.py`
- **File**: `BlackBoard/src/agents/llm/gemini_client.py`
- **Action**:
  1. In `_build_config()` or `GenerateContentConfig` construction:
     - Add `stop_sequences=["<end_of_image>"]` (kept strictly internal to `GeminiAdapter`).
  2. In `_stream_chunks()` (lines 1266–1305):
     - Scrub control tokens before buffering and yielding `LLMChunk(text=to_yield)`.
     - In stream tail flush (lines 1294–1305):
       - If `stream_text_buffer` starts with any prefix in `_CONTROL_TOKEN_PREFIXES`, discard it: `stream_text_buffer = ""`.
       - Scrub `stream_text_buffer` with `_CONTROL_TOKENS_RE.sub("", stream_text_buffer)` before delegating to `scan_call_syntax`.
       - Ensure bare `LLMChunk()` wire heartbeats are never dropped.
  3. In `generate_stream()` (line 1337) and unary `generate()` (line 960):
     - Sanitize candidate parts on a deep copy of candidate parts.
     - Strictly preserve parts that carry `thought_signature`.
     - For pure text parts, strip control tokens. If stripped text is empty, drop the part; if all parts are empty, retain one benign text part to prevent Gemini API 400 errors during model replay via `context_parts.py`.
- **Verification**: Run `cd BlackBoard && ./venv/bin/pytest tests/test_gemini_client_quota.py`.

### Step 3: [Complex] Brain Context-Aligned Steering Recovery & Slack Isolation in `brain.py` & `slack.py`
- **Files**:
  - `BlackBoard/src/channels/slack.py`
  - `BlackBoard/src/agents/brain.py`
- **Action**:
  1. In `BlackBoard/src/channels/slack.py`:
     - Add `("system", "steering")` to `_INTERNAL_TURNS` set.
  2. In `BlackBoard/src/agents/brain.py`:
     - In lines 2969–3004 (`_process_with_llm`):
       - `clean_text = sanitize_call_syntax(accumulated_text)`
       - If `clean_text` is `None` / empty and no function call occurred:
         - Bypass `response` turn emission and `_waiting_for_user` park.
         - Track empty retries: `retries = self._empty_output_retries.get(event_id, 0) + 1`.
         - If `retries <= 2`:
           - `self._empty_output_retries[event_id] = retries`
           - Determine eligible tools for current phase and domain.
           - Inject internal steering turn:
             ```python
             steering_msg = (
                 f"System Notice: Turn produced no actionable output or tool calls in phase '{phase}' "
                 f"(domain: {domain}). Eligible tools for this phase are: {eligible_tools}. "
                 f"Select an action to advance event objective or transition phase."
             )
             turn = ConversationTurn(
                 turn=0,  # Atomic assignment in append_turn
                 actor="system",
                 action="steering",
                 thoughts=steering_msg,
             )
             await self._append_and_broadcast(event_id, turn)
             return True  # Re-enter processing loop immediately with steering guidance
             ```
         - Else (`retries > 2`):
           - `self._empty_output_retries.pop(event_id, None)`
           - Log warning and return `False`.
       - If `clean_text` is non-empty or function call occurred (including in the function-call return path at ~line 2950):
         - Reset counter: `self._empty_output_retries.pop(event_id, None)`.
     - In `_cleanup_stale_events` and event closing handlers (`_close_and_broadcast`), clear `self._empty_output_retries.pop(event_id, None)`.
- **Verification**: Run `cd BlackBoard && ./venv/bin/pytest tests/test_brain_steering_recovery.py`.

### Step 4: [Complicated] Canonical Kargo Promotion MR Ingestion Seeding in `aligner.py` & `handlers_integration.py`
- **Files**:
  - `BlackBoard/src/agents/aligner.py`
  - `BlackBoard/src/agents/handlers_integration.py`
- **Action**:
  1. In `aligner.py:handle_failed_promotion`:
     - If `mr_url` is non-empty:
       ```python
       gitlab_context = None
       if mr_url:
           parsed = GitLabPlatform.parse_mr_url(mr_url)
           if parsed:
               project_id, mr_iid = parsed
               gitlab_context = {
                   "target_url": mr_url,
                   "project_id": str(project_id),
                   "mr_iid": int(mr_iid),
               }
       ```
     - Pass `gitlab_context=gitlab_context` to `EventEvidence(...)`.
  2. In `handlers_integration.py:handle_refresh_kargo_context`:
     - Obtain blackboard handle via `bb = ctx.get_blackboard()`.
     - If new `mr_url` arrives and `evidence.gitlab_context` is missing or has a different URL:
       ```python
       if mr_url:
           parsed = GitLabPlatform.parse_mr_url(mr_url)
           if parsed:
               project_id, mr_iid = parsed
               await bb.update_event_gitlab_context(event_id, {
                   "target_url": mr_url,
                   "project_id": str(project_id),
                   "mr_iid": int(mr_iid),
               })
       ```
- **Verification**: Run `cd BlackBoard && ./venv/bin/pytest tests/test_aligner_escalation_gate.py`.

### Step 5: [Complicated] Headhunter GitLab SHA Persistence & URL Encoding in `headhunter_gitlab.py`
- **File**: `BlackBoard/src/agents/headhunter_gitlab.py`
- **Action**:
  1. In `create_event` (lines 353–371):
     - Extract `head_sha = target.get("sha") or (target.get("diff_refs") or {}).get("head_sha")`.
     - Include `head_sha` in initial `gitlab_context` payload.
  2. In `refresh_mr_state` (lines 500–549):
     - Capture `head_sha` into a local variable within `if mr_resp.is_success:`:
       ```python
       mr_data = mr_resp.json()
       head_sha = mr_data.get("sha") or (mr_data.get("diff_refs") or {}).get("head_sha")
       ```
     - Include in `result` payload passed to `update_event_gitlab_context`:
       ```python
       if head_sha:
           result["head_sha"] = head_sha
           result["sha"] = head_sha
       ```
  3. In `refresh_mr_state` lines 485 & 519, URL-encode `project_id`:
     ```python
     encoded_project = urllib.parse.quote(urllib.parse.unquote(str(project_id)), safe="")
     ```
- **Verification**: Run `cd BlackBoard && ./venv/bin/pytest tests/test_headhunter.py -k test_refresh_mr_state`.

### Step 6: [Complicated] VCS Approval Live SHA Resolution & Corporate TLS in `vcs_approval.py` & Helm
- **Files**:
  - `BlackBoard/src/utils/vcs_approval.py`
  - `BlackBoard/helm/templates/deployment.yaml`
  - `BlackBoard/helm/values.yaml`
- **Action**:
  1. In `vcs_approval.py`:
     - Implement secure corporate CA bundle discovery with zero `verify=False` fallbacks:
       ```python
       def _resolve_ca_bundle(host: str) -> str | bool:
           verify_env = os.getenv("GITLAB_SSL_VERIFY")
           if verify_env is not None:
               if verify_env.lower() in ("0", "false", "no"):
                   raise ValueError("Insecure TLS verification (GITLAB_SSL_VERIFY=0) forbidden on VCS approval calls")
               if os.path.exists(verify_env):
                   return verify_env
           for path in (
               os.getenv("SSL_CERT_FILE"),
               os.getenv("REQUESTS_CA_BUNDLE"),
               "/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem",
               "/etc/pki/tls/certs/ca-bundle.crt",
               "/etc/ssl/certs/ca-certificates.crt",
           ):
               if path and os.path.exists(path):
                   return path
           return True  # Fall back to standard certifi/system store; NEVER return False
       ```
     - In `_resolve_gitlab_head(gl_ctx)`:
       - Extract `project_id` and `mr_iid`:
         ```python
         project_id = gl_ctx.get("project_id")
         mr_iid = gl_ctx.get("mr_iid")
         if not project_id or not mr_iid:
             return (mr_iid or None, None)  # Fail closed: never return fallback_sha
         ```
       - URL-encode project path:
         ```python
         encoded_project = urllib.parse.quote(urllib.parse.unquote(str(project_id)), safe="")
         ```
       - Use `ca_bundle = _resolve_ca_bundle(host)` for `httpx.AsyncClient(timeout=10, verify=ca_bundle)`.
       - On API request failure/exception or non-2xx:
         ```python
         logger.warning(f"Failed to resolve live GitLab HEAD for MR !{mr_iid} in {project_id}")
         return (mr_iid, None)  # Retain MR IID, fail closed on approved SHA
         ```
     - In `resolve_live_head_sha(event)`:
       - If `gitlab_context` is missing or incomplete, inspect `evidence.kargo_context.get("mr_url")`. If present:
         ```python
         parsed = GitLabPlatform.parse_mr_url(kargo_mr)
         if parsed:
             project_id, mr_iid = parsed
             return await _resolve_gitlab_head({
                 "project_id": str(project_id),
                 "mr_iid": int(mr_iid),
             })
         ```
  2. In `BlackBoard/helm/templates/deployment.yaml`:
     - Add volumeMount for `config-trusted-cabundle` to both Brain container and `skill-reconciler` container when `trustedCaBundle.enabled` is true:
       - mountPath: `/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem`
       - subPath: `ca-bundle.crt`
     - Export `SSL_CERT_FILE` and `REQUESTS_CA_BUNDLE` pointing to `/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem`.
  3. In `BlackBoard/helm/values.yaml`:
     - Add `trustedCaBundle: { enabled: true, configMapName: "config-trusted-cabundle" }`.
- **Verification**: Run `cd BlackBoard && ./venv/bin/pytest tests/test_vcs_approval.py`.

### Step 7: [Complicated] Comprehensive ATDD Unit & Integration Verification
- **Files**:
  - `BlackBoard/tests/test_vcs_approval.py`
  - `BlackBoard/tests/test_gemini_client_quota.py`
  - `BlackBoard/tests/test_headhunter.py`
  - `BlackBoard/tests/test_aligner_escalation_gate.py`
  - `BlackBoard/tests/test_brain_steering_recovery.py`
- **Action**:
  1. In `tests/test_vcs_approval.py`:
     - Update 5 existing fallback assertions (lines 83, 101, 116, 129, 139) from `assert sha == "stale-sha"` to `assert sha is None` in alignment with the fail-closed security contract.
     - Add test scenarios for URL encoding with `quote(safe="")`, corporate CA resolution without `verify=False`, fail-closed `(mr_iid, None)` return, and 168-case JS/Python verdict parity matrix.
  2. In `tests/test_gemini_client_quota.py`:
     - Add tests for control token regex multi-pass, streaming holdback with closing tags, partial prefix drop in tail flush, `thought_signature` preservation on deep copy, and unary `generate()` sanitization.
  3. In `tests/test_headhunter.py`:
     - Test `head_sha` persistence in both `create_event` and `refresh_mr_state`.
  4. In `tests/test_aligner_escalation_gate.py`:
     - Test canonical 2-tuple URL parsing and gitlab_context seeding.
  5. In `tests/test_brain_steering_recovery.py`:
     - Implement test suite for Brain empty-output steering recovery, atomic `turn=0` broadcast, retry counter lifecycle, and Slack isolation.
- **Verification**: Run `cd BlackBoard && ./venv/bin/pytest tests/test_vcs_approval.py tests/test_gemini_client_quota.py tests/test_headhunter.py tests/test_aligner_escalation_gate.py tests/test_brain_steering_recovery.py`.

---

## 6. Verification & Test Specification (Definition of Done — 4-Layer ATDD Model)

### 6a. Executable Scenarios & Test Specification Table

| ID | Scenario (Given/When/Then) | DSL Operation / Driver | SUT Target | Expected Output / Assertion | Category |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **T-1** | Given raw LLM text with 23 repetitions of `<end_of_image>`<br>When `sanitize_call_syntax()` runs<br>Then all control tokens are removed and result is `None` | `sanitize_call_syntax(text)` | `types.py` | `cleaned is None` | unit |
| **T-2** | Given stream buffer ending in partial `<end_of_` or `</thought`<br>When `split_stream_call_syntax()` processes buffer<br>Then partial prefix is held back and not yielded | `split_stream_call_syntax(buf)` | `types.py` | `to_yield == ""` and `held in ("<end_of_", "</thought")` | unit |
| **T-2b** | Given stream tail flush buffer starting with partial prefix `<end_of_`<br>When stream tail flushes<br>Then prefix is discarded and not emitted into `scan_call_syntax` | `_stream_chunks` tail flush | `gemini_client.py` | `stream_text_buffer == ""` | unit |
| **T-3** | Given stream chunk stream yielding only control tokens<br>When Brain `_process_with_llm` completes without tool calls<br>Then no public `response` turn is emitted, event is not parked, and internal steering turn is injected with `turn=0` and broadcast | `_process_with_llm(event)` | `brain.py` | `public_response == None`, `parked == False`, `last_turn.action == "steering"`, `last_turn.turn == 0` | acceptance |
| **T-4** | Given `("system", "steering")` turn emitted by Brain<br>When Slack channel handler processes turn<br>Then turn is suppressed by `_INTERNAL_TURNS` and not posted to Slack | `_INTERNAL_TURNS` check | `slack.py` | `("system", "steering") in _INTERNAL_TURNS` | unit / security |
| **T-5** | Given candidate parts containing both a `thought_signature` carrier and `<end_of_image>` text<br>When `gemini_client` packages `raw_parts`<br>Then `thought_signature` part is preserved and text is scrubbed without producing an empty part | `_stream_chunks` packaging | `gemini_client.py` | `any(hasattr(p, 'thought_signature') for p in raw_parts)` and no empty text parts | unit / regression |
| **T-6** | Given Kargo promotion failure with `mr_url=".../org/group/repo/-/merge_requests/25"`<br>When `handle_failed_promotion` runs<br>Then `evidence.gitlab_context` contains `project_id="org/group/repo"` and `mr_iid=25` via canonical 2-tuple parser | `handle_failed_promotion(...)` | `aligner.py` | `evt.evidence.gitlab_context["mr_iid"] == 25` | acceptance |
| **T-7** | Given GitLab MR API returns `{"sha": "d461a00c...", "state": "opened"}`<br>When `create_event` or `refresh_mr_state` runs<br>Then `gitlab_context` contains `head_sha="d461a00c..."` | `refresh_mr_state(eid)` | `headhunter_gitlab.py` | `gl_ctx["head_sha"] == "d461a00c..."` | integration |
| **T-8** | Given `project_id="openshift-virtualization/downstream-configuration"`<br>When `_resolve_gitlab_head` formats API request<br>Then URL uses encoded `openshift-virtualization%2Fdownstream-configuration` (`safe=""`) | `_resolve_gitlab_head(ctx)` | `vcs_approval.py` | `req.url.path.contains("%2F")` | unit |
| **T-9** | Given corporate host `gitlab.cee.redhat.com`<br>When `_resolve_ca_bundle` evaluates trust<br>Then it detects corporate CA path or falls back to system store `True`, NEVER `False` | `_resolve_ca_bundle(host)` | `vcs_approval.py` | `verify is not False` and `verify != False` | unit / security |
| **T-10** | Given event with missing `gitlab_context` but valid `kargo_context.mr_url`<br>When `resolve_live_head_sha(event)` runs<br>Then it extracts MR ID and live HEAD SHA from Kargo context | `resolve_live_head_sha(evt)` | `vcs_approval.py` | `(approved_mr_id, approved_mr_sha) == ("25", "d461a00c...")` | acceptance |
| **T-10b** | Given GitLab live API returns HTTP 500 or timeout<br>When `_resolve_gitlab_head` runs<br>Then it returns `(mr_iid, None)`, failing closed on SHA while preserving MR ID | `_resolve_gitlab_head(ctx)` | `vcs_approval.py` | `res == (25, None)` | unit / security |
| **T-11** | Given `approved=True` and `approved_mr_sha="d461a00c..."`<br>When `merge-guard.js --verdict` and `verify_merge_guard` evaluate live HEAD `"d461a00c..."`<br>Then both permit merge with 100% parity across 168 cases | `TestJsPythonVerdictParity` | `vcs_approval.py` / `merge-guard.js` | `allow == True` in both Python and JS | acceptance / regression |

### 6b. Test Infrastructure & Driver Notes
- Test runner: Python `pytest` via `./venv/bin/pytest` executed within `BlackBoard/` working directory.
- Mock boundary: `httpx.AsyncClient` mocked via `pytest-mock` / `respx` in `tests/test_vcs_approval.py` and `tests/test_headhunter.py`.
- Dedicated steering recovery suite: `BlackBoard/tests/test_brain_steering_recovery.py`.
- JS/Python Parity Harness: `node BlackBoard/gemini-sidecar/hooks/merge-guard.js --verdict` executed via subprocess in `test_vcs_approval.py:TestJsPythonVerdictParity`.

---

## 7. Revision History & Amendment Ledger

### Amendment Ledger (Converge Round 1)

| ID | Source | Class | Amendment | Target | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **A-1** | Security Lane & PtG #1 | `plan-text` | Purge `verify=False` fallback in `_resolve_ca_bundle`; enforce fail-closed live VCS resolution without stale SHA binding. | Step 6, Table 6a (T-9) | applied |
| **A-2** | Auditor A/B & PtG #2 | `scope` | Add `BlackBoard/src/channels/slack.py` to affected files; add `("system", "steering")` to `_INTERNAL_TURNS`; enforce `turn=0` and `_append_and_broadcast` in `brain.py`; reset `_empty_output_retries` on clean turns/event close. | Step 3, Section 3, Table 6a (T-4) | applied |
| **A-3** | Auditor C & PtG #3 | `plan-text` | De-risk `raw_parts` sanitization: sanitize on copy, preserve parts carrying `thought_signature`, prevent empty text parts; scrub `stream_text_buffer` in tail flush (lines 1294–1305); keep `stop_sequences` internal to adapter. | Step 2, Table 6a (T-5) | applied |
| **A-4** | Auditor B/C & PtG #4 | `plan-text` | Expand `_CONTROL_TOKEN_PREFIXES` to include closing tags (`</thought>`, `</image>`, etc.); incorporate multi-pass loop (`_FENCE_MAX_PASSES = 8`) in `prompt_sanitize.py` against nested token injection. | Step 1, Table 6a (T-2) | applied |
| **A-5** | Auditor A/C & PtG #5 | `plan-text` | Reclassify Step 4 and Step 5 to `[Complicated]`; replace naive split with canonical `GitLabPlatform.parse_mr_url`; seed `head_sha` in `create_event` as well as `refresh_mr_state`; URL-encode `project_id` via `quote(safe="")`. | Steps 4 and 5, frontmatter | applied |
| **A-6** | Auditor A & PtG #6 | `plan-text` | Align Helm mount path and env vars to `/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem`; add mount to `skill-reconciler` container. | Step 6, Section 3 | applied |
| **A-7** | Auditor A/B/C & PtG #7 | `scope` | Replace non-existent `tests/test_brain.py` with `tests/test_brain_steering_recovery.py`; specify execution from `BlackBoard/` via `./venv/bin/pytest`. | Step 7, Section 6b | applied |

### Amendment Ledger (Converge Round 2)

| ID | Source | Class | Amendment | Target | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **A-8** | Auditor A/B & Security Lane | `interface` | Fix `GitLabPlatform.parse_mr_url` snippet return handling: unpack 2-tuple `project_id, mr_iid = parsed` rather than indexing as dict. | Steps 4 and 6, Table 6a (T-6) | applied |
| **A-9** | Auditor A | `interface` | In `handlers_integration.py:handle_refresh_kargo_context`, obtain blackboard handle via `bb = ctx.get_blackboard()` rather than `self.blackboard`. | Step 4 | applied |
| **A-10** | Auditor A/B & Security Lane | `security` | Refine fail-closed return signature in `_resolve_gitlab_head`: on API failure or non-2xx, return `(mr_iid, None)`, preserving MR IID while failing closed on SHA. Update line 58 guard as well. | Step 6, Table 6a (T-10b) | applied |
| **A-11** | Auditor B/C | `correctness` | In `gemini_client.py:1294-1305` stream tail flush, discard buffer if it begins with any `_CONTROL_TOKEN_PREFIXES`; thread control token scrubbing through unary `generate()`. | Step 2, Table 6a (T-2b) | applied |
| **A-12** | Auditor A/B | `test-spec` | Update Step 7 to explicitly include updating 5 existing fallback assertions in `BlackBoard/tests/test_vcs_approval.py` from `assert sha == "stale-sha"` to `assert sha is None`. | Step 7, Section 3 | applied |
| **A-13** | Auditor C / Environment | `infrastructure` | Mirror plan to `BlackBoard/docs/plans/blackboard-control-token-scrubbing-and-kargo-vcs-approval.plan.md` for workspace-scoped sandbox visibility. | Step 7, Section 3 | applied |

### Amendment Ledger (Converge Round 3)

| ID | Source | Class | Amendment | Target | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **A-14** | Auditor C / R1 (Opus 4.8) | `precision` | Clarify GitHub PR approval out-of-scope for VMER-2398; define local regex in `prompt_sanitize.py` preserving dependency-free boundary; pop `_empty_output_retries` in function-call return path (~:2950); remove dead `fallback_sha` at `vcs_approval.py:55`; wrap `_resolve_ca_bundle` in `try:` block. | Steps 1, 3, 6, Section 7 | applied |

### Revision History Log

| Update | Source pre-flight | Confidence then | Summary |
| :--- | :--- | :--- | :--- |
| **2026-11-17 13:30** | `blackboard-control-token-scrubbing-and-kargo-vcs-approval-Pre-Flight-Review_2026-11-17_1330.md` | 60% (Caution) | Converge Round 1: Applied A-1 (purged insecure TLS bypass), A-2 (Slack steering isolation & turn=0 broadcast), A-3 (raw_parts thought_signature safety & tail flush scrub), A-4 (closing token prefixes & multi-pass fence strip), A-5 (canonical GitLabPlatform.parse_mr_url & quote(safe="")), A-6 (Helm CA mount alignment for Brain & skill-reconciler), A-7 (redirected test suite to test_brain_steering_recovery.py). |
| **2026-11-17 13:45** | `blackboard-control-token-scrubbing-and-kargo-vcs-approval-Pre-Flight-Review_2026-11-17_1345.md` | 72% (Caution) | Converge Round 2: Applied A-8 (2-tuple unpacking for GitLabPlatform.parse_mr_url), A-9 (bb = ctx.get_blackboard() in handlers_integration.py), A-10 (fail-closed (mr_iid, None) return signature in _resolve_gitlab_head), A-11 (partial prefix discard in stream tail flush & unary generate coverage), A-12 (refactored 5 existing fallback assertions in test_vcs_approval.py to expect None), A-13 (mirrored plan into workspace docs/plans). |
| **2026-11-17 14:00** | `blackboard-control-token-scrubbing-and-kargo-vcs-approval-Pre-Flight-Review_2026-11-17_1400.md` | 87% (Caution -> Ready with A-14) | Converge Round 3: Applied A-14 (GitHub PR approval documented out-of-scope for GitLab incident VMER-2398; pure boundary preserved in prompt_sanitize.py; _empty_output_retries cleared in FC path; dead fallback_sha removed; ca_bundle resolution guarded in try:). |
