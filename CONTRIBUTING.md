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

See [README.md](README.md) for the full architecture overview, including the Blackboard pattern, agent system, and progressive skill loading.

## Dockerfile Base Images

The Dockerfiles use Red Hat UBI 9 base images (`registry.access.redhat.com/ubi9/*`), which are publicly accessible and require no subscription. Contributors who prefer standard images can substitute `node:22-slim` and `python:3.12-slim` for local builds.

## Sidecar CLI Versions

The sidecar Dockerfile downloads `latest` for all CLI tools (kubectl, oc, argocd, kargo, tkn, helm, etc.). This is intentional -- agents need current CLI versions to work with real clusters. This is a design decision, not an oversight.

## Questions?

Open a GitHub issue or start a discussion. We're happy to help.
