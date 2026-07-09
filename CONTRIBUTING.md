<!-- @ai-rules:
1. [Constraint]: No internal employer references, hostnames, or email addresses. Use descriptive words.
2. [Pattern]: Makefile targets mirror this doc. If a target changes, update both.
3. [Constraint]: requirements-dev.txt for test deps, requirements.txt for production only.
4. [Pattern]: UBI9 base images are intentional and public. Document alternatives, don't replace.
5. [Pattern]: Sidecar CLI "latest" is a design decision. Document it, don't pin.
-->
# Contributing to Darwin Blackboard

Thank you for your interest in contributing to Darwin. This guide covers the development setup and contribution process.

## Prerequisites

- Python 3.12+
- Node.js 22+
- Docker and Docker Compose
- Redis 7+ (provided via docker-compose for local dev)

## Local Development

### 1. Start dependencies

```bash
docker compose up -d
```

This starts Redis and Qdrant containers for local development.

### 2. Install Python dependencies

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

### 3. Run the Brain server

```bash
export REDIS_HOST=localhost
export GCP_PROJECT=your-project-id
export GCP_LOCATION=us-central1

uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Run the UI (separate terminal)

```bash
cd ui
npm ci
npm run dev
```

The Vite dev server starts on port 5174 with hot reload.

### 5. Build the sidecar image (optional)

The sidecar image contains all agent CLIs (Gemini, Claude, kubectl, oc, argocd, kargo, tkn, helm, gh, glab) plus MCP servers and Playwright/Chromium. Only needed when modifying `gemini-sidecar/` code or testing agent dispatch locally.

```bash
cd gemini-sidecar
docker build -t darwin-sidecar:local .
# or: podman build -t darwin-sidecar:local .
```

Run a sidecar against a local Brain (reverse WS mode):

```bash
export AGENT_WS_MODE=reverse
export BRAIN_WS_URL=ws://localhost:8000/agent/ws
export AGENT_ROLE=developer
export AGENT_PORT=9093
node server.js
```

The sidecar Dockerfile is large (~170 lines) because it installs multiple CLIs and browser dependencies. First build takes ~10 minutes. CI builds and pushes to GHCR via `.github/workflows/build-gemini-sidecar.yaml`.

Agent rules live in `gemini-sidecar/rules/` (architect, developer, sysadmin, qe, security_analyst). Skills live in `gemini-sidecar/skills/` (31 skills, role/mode filtered).

### Common targets

A `Makefile` is provided for convenience:

```bash
make dev      # Start deps + Brain server
make ui       # Start Vite dev server
make build    # Production UI build
make lint     # ESLint for UI
make test     # Run pytest
make docker   # Build Docker image locally
```

### Running Tests

```bash
# Python tests (Brain, agents, observers)
python -m pytest tests/ -v

# Specific test file
python -m pytest tests/test_brain_progressive_skills.py -v

# Specific test areas
python -m pytest tests/test_headhunter_jira.py -v   # Jira QE mission head
python -m pytest tests/test_trusted_proxy_auth.py -v  # BFF trusted-proxy auth

# UI lint
cd ui && npm run lint

# Helm validation
helm lint ./helm
helm template darwin-brain ./helm
```

Tests use `fakeredis` for Redis mocking. See `tests/conftest.py` for shared fixtures.

## Code Style

- **Python:** Follow existing patterns. No enforced formatter yet -- this is a future improvement.
- **TypeScript:** ESLint config is provided. Run `npm run lint` in `ui/`.
- **File size:** Keep files under 100 lines where practical. Each file should have the relative file path at the top as a comment.
- **Modules:** ES Modules syntax (`import ... from ...`), not CommonJS.

## Pull Request Process

1. Fork the repository
2. Create a feature branch from `main`
3. Make your changes in small, focused commits
4. Ensure `npm run build` passes in `ui/`
5. Open a PR with a clear description of what and why

### Commit Messages

Follow the existing convention:

- `feat(scope): description` -- new feature
- `fix(scope): description` -- bug fix
- `ci: description` -- CI/CD changes
- `docs: description` -- documentation only

## Architecture

See the [Architecture Guide](docs/architecture.md) for the full architecture overview, the [Agent System](docs/agents.md) for agent details, and the [API Reference](docs/api-reference.md) for all endpoints.

## Dockerfile Base Images

The Dockerfiles use Red Hat UBI 9 base images (`registry.access.redhat.com/ubi9/*`), which are publicly accessible and require no subscription. Contributors who prefer standard images can substitute `node:22-slim` and `python:3.12-slim` for local builds.

## Sidecar CLI Versions

The sidecar Dockerfile downloads `latest` for all CLI tools (kubectl, oc, argocd, kargo, tkn, helm, etc.). This is intentional -- agents need current CLI versions to work with real clusters. This is a design decision, not an oversight.

## Documentation Maintenance

When changing code, update the corresponding living doc:

| Change area | Update |
| :--- | :--- |
| New/changed REST or WS route | `docs/api-reference.md` |
| New agent, sidecar, or observer | `docs/agents.md`, `docs/architecture.md` mermaid |
| New Helm value or env var | `docs/deployment.md`, `helm/README.md` integrations table |
| New brain skill phase or file | `docs/brain-skills.md` |
| New Dashboard page | `ui/README.md` |

See [docs/TABLE-OF-CONTENTS.md](docs/TABLE-OF-CONTENTS.md) for the full doc index.

## Documentation Structure

| Document | Content |
| :--- | :--- |
| [README.md](README.md) | Project overview and quick start |
| [docs/TABLE-OF-CONTENTS.md](docs/TABLE-OF-CONTENTS.md) | Full documentation index |
| [docs/architecture.md](docs/architecture.md) | Architecture, WebSocket protocol, Cortex/JARVIS, safety model |
| [docs/agents.md](docs/agents.md) | Agent system (9 specialists), sidecars, skills, MCP servers |
| [docs/api-reference.md](docs/api-reference.md) | All REST and WebSocket API endpoints |
| [docs/deployment.md](docs/deployment.md) | Environment variables, Helm deployment |
| [docs/brain-skills.md](docs/brain-skills.md) | Progressive skill system, phases, configuration |
| [ui/README.md](ui/README.md) | Dashboard pages and components |
| [helm/README.md](helm/README.md) | Helm chart installation and values |

## Questions?

Open a GitHub issue or start a discussion. We're happy to help.
