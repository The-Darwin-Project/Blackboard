# Architectural Constraints

## 1. The Blackboard Pattern

* **Rule:** Agents NEVER communicate directly.
* **Implementation:** Agents communicate via shared event documents in Redis. The Conversation Queue (`darwin:queue`, `darwin:event:{id}`) replaces the old per-agent task queues.

## 2. Separation of Concerns (The "Air Gap")

* **Rule:** Soft enforcement via architectural patterns and safety checks:
  * **Brain** (`brain.py`) uses Vertex AI SDK. May access Redis. Contains ZERO routing logic.
  * **Architect** (`architect.py`) is a thin HTTP client. Sidecar can clone+read repos. NEVER commits/pushes. Enforced by GEMINI.md rules.
  * **SysAdmin** (`sysadmin.py`) is a thin HTTP client. Sidecar has full git + kubectl. Safety via FORBIDDEN_PATTERNS in security.py.
  * **Developer** (`developer.py`) is the pair programming manager. Fires Dev + QE sidecars concurrently via `asyncio.gather()`. Flash Manager (Gemini Flash) reviews outputs. See `04-developer-qe-pair.md` for invariants.
  * **Aligner** (`aligner.py`) keeps Vertex AI Flash for filter config. Creates events, does NOT route to agents.

## 3. The Conversation Queue Protocol

* **Event Creation:** Events are created by Aligner (anomaly) or Chat (user request)
* **Triage:** Brain triages events via LLM function calling
* **Conversation:** Conversation is an append-only log of turns in the event document
* **Plans:** Plans are Markdown turns, not JSON
* **Event Lifecycle:** `new` -> `active` -> `waiting_approval` -> `resolved` -> `closed`

## 4. The Telemetry Protocol

* **Pattern:** We accept POST requests to `/telemetry` with this rich JSON schema:

    ```json
    {
      "service": "string",
      "version": "string",
      "metrics": { "cpu": float, "error_rate": float },
      "topology": { "dependencies": [{ "target": "string", "type": "db|http" }] }
    }
    ```
