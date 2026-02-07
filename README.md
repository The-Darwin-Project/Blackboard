# Darwin Blackboard (Brain)

The central nervous system of Darwin -- an autonomous closed-loop cloud operations system.

## Architecture

The Brain orchestrates multi-agent conversations via the **Blackboard Pattern** with bidirectional WebSocket communication:

```
                 ┌──────────────────────────────────────────────────┐
                 │                  Darwin Brain Pod                 │
                 │                                                   │
                 │  ┌─────────┐    ┌──────────┐    ┌───────────┐   │
                 │  │  Brain  │◄──►│  Redis    │◄──►│  Aligner  │   │
                 │  │ Vertex  │    │ (State +  │    │ (In-proc  │   │
                 │  │ AI Pro  │    │  Queue)   │    │  + Flash)  │   │
                 │  └────┬────┘    └──────────┘    └───────────┘   │
                 │       │ WebSocket                                 │
                 │  ┌────┼──────────────┬──────────────┐           │
                 │  ▼    ▼              ▼              ▼           │
                 │ ┌──────────┐  ┌──────────┐  ┌──────────┐       │
                 │ │Architect │  │ sysAdmin │  │Developer │       │
                 │ │  :9091   │  │  :9092   │  │  :9093   │       │
                 │ │Gemini CLI│  │Gemini CLI│  │Gemini CLI│       │
                 │ └──────────┘  └──────────┘  └──────────┘       │
                 │   Same base image, different GEMINI.md rules     │
                 └──────────────────────────────────────────────────┘
```

## Agents

| Agent | Role | Technology | Capabilities |
|-------|------|-----------|--------------|
| **Brain** | Orchestrator | Vertex AI Pro (Gemini 3 Pro, temp >0.7) | Cynefin classification, agent routing, feedback loop verification |
| **Aligner** | Truth Maintenance | In-process Python + Vertex AI Flash | Telemetry processing, LLM signal analysis, event creation |
| **Architect** | Strategy | Gemini CLI sidecar | Code review, Markdown plans, risk assessment. NEVER executes. |
| **sysAdmin** | Execution | Gemini CLI sidecar | GitOps changes, kubectl investigation. Read-only cluster access. |
| **Developer** | Implementation | Gemini CLI sidecar | Source code changes, feature implementation, bug fixes. |

## Key Features

- **Conversation Queue** -- Shared event documents in Redis with append-only conversation turns
- **WebSocket Communication** -- Real-time bidirectional streaming between Brain, agents, and UI
- **Cynefin Decision Framework** -- Brain classifies events into Clear/Complicated/Complex/Chaotic domains
- **LLM Signal Analysis** -- Aligner uses Flash to interpret metrics patterns (not hardcoded thresholds)
- **GitOps-Only Mutations** -- All changes go through git (clone, modify, push). kubectl is read-only.
- **Event Dedup + Defer** -- Prevents event spam, supports deferred re-processing
- **Closed-Loop Verification** -- Brain verifies every change via Aligner before closing events

## Autonomous Remediation Examples

See [docs/autonomous-remediation-example.md](../docs/autonomous-remediation-example.md) for a documented 21-turn multi-agent event where the system autonomously:
1. Detected an over-provisioned service
2. Discovered the GitOps repository by reasoning from the container image URL
3. Produced and executed a scaling plan via GitOps
4. Verified the outcome through independent sources

## Quick Start

### Local Development

```bash
# Start Redis
docker run -d --name redis -p 6379:6379 redis:7

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export REDIS_HOST=localhost
export GCP_PROJECT=your-project-id
export GCP_LOCATION=us-central1

# Run the server
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

### Helm Deployment (OpenShift)

```bash
helm install darwin-brain ./helm \
  --set gcp.project=your-project-id \
  --set gcp.existingSecret=gcp-sa-key

# Verify -- should show 5 containers (brain, redis, architect, sysadmin, developer)
kubectl get pods -l app=darwin-brain
```

## API Endpoints

### Health & Info

```
GET /health         # {"status": "brain_online"}
GET /info           # API information and available endpoints
```

### WebSocket (Real-time UI)

```
WS /ws              # Bidirectional WebSocket for live conversation updates
                    # Receives: turn, progress, event_created, event_closed, attachment
                    # Sends: chat, approve, reject, user_message
```

### Conversation Queue

```
GET  /queue/active             # List active events with metadata
GET  /queue/{event_id}         # Full event document with conversation
POST /queue/{event_id}/approve # Approve a pending plan
POST /queue/{event_id}/reject  # Reject a pending plan with reason
GET  /queue/closed/list        # Recently closed events
```

### Chat

```
POST /chat/
{"message": "Scale darwin-store to 3 replicas", "service": "darwin-store"}

# Response:
{"event_id": "evt-abc123", "status": "created"}
# Brain processes asynchronously -- track via WebSocket or GET /queue/{event_id}
```

### Telemetry

```
POST /telemetry/
{
  "service": "darwin-store",
  "version": "v52",
  "metrics": {"cpu": 75.0, "memory": 60.0, "error_rate": 0.5},
  "topology": {"dependencies": [{"target": "postgres", "type": "db"}]},
  "gitops": {"repo": "The-Darwin-Project/Store", "helm_path": "helm/values.yaml"}
}
```

### Topology & Metrics

```
GET /topology/                 # JSON topology
GET /topology/graph            # Cytoscape.js graph data
GET /topology/mermaid          # Mermaid diagram
GET /metrics/{service}         # Current metrics
GET /metrics/chart             # Time-series chart data
GET /events/                   # Architecture event timeline
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `REDIS_HOST` | Redis hostname | `localhost` |
| `REDIS_PASSWORD` | Redis password | (empty) |
| `GCP_PROJECT` | GCP project ID | (required) |
| `GCP_LOCATION` | Vertex AI location | `global` |
| `VERTEX_MODEL_PRO` | Brain model | `gemini-3-pro-preview` |
| `VERTEX_MODEL_FLASH` | Aligner model | `gemini-3-flash-preview` |
| `ARCHITECT_SIDECAR_URL` | Architect WebSocket | `http://localhost:9091` |
| `SYSADMIN_SIDECAR_URL` | sysAdmin WebSocket | `http://localhost:9092` |
| `DEVELOPER_SIDECAR_URL` | Developer WebSocket | `http://localhost:9093` |
| `DEBUG` | Enable debug logging | `false` |

## Safety

### Air Gap (Soft Enforcement via GEMINI.md)

| Agent | Can Do | Cannot Do |
|-------|--------|-----------|
| Architect | Clone + read repos | Commit, push, kubectl mutations |
| sysAdmin | Git clone/push, kubectl read | kubectl write, invent Helm sections |
| Developer | Git clone/push, read Helm | Modify infrastructure, kubectl scale |

### Security Patterns

- `FORBIDDEN_PATTERNS` in `security.py` blocks: `rm -rf`, `drop database`, `kubectl delete namespace`, `git push --force`, etc.
- Dockerfile safety rules: agents can add `ARG/ENV/COPY/RUN` but cannot change `FROM/CMD/USER/WORKDIR`
- Structural changes require user approval (Brain pauses for confirmation)

## License

See [LICENSE](LICENSE) file.
