# BlackBoard/Makefile
# @ai-rules:
# 1. [Pattern]: Targets mirror CONTRIBUTING.md "Common targets" section. Keep both in sync.
# 2. [Constraint]: `dev` depends on deps-up (docker compose). Requires Docker running.
# 3. [Constraint]: `test` uses requirements-dev.txt deps. Runs pytest from repo root.

.PHONY: dev ui build lint test docker deps-up deps-down

deps-up:
	docker compose up -d

deps-down:
	docker compose down

dev: deps-up
	REDIS_HOST=localhost uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

ui:
	cd ui && npm run dev

build:
	cd ui && npm ci && npm run build

lint:
	cd ui && npm run lint

test:
	python -m pytest tests/ -v

docker:
	docker build -t darwin-brain .
