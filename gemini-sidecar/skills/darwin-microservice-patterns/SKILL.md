---
name: darwin-microservice-patterns
description: Microservice technical patterns for infrastructure and API design. Use when planning service changes, reviewing API contracts, or evaluating deployment strategies.
roles: [architect]
modes: [plan]
---

# Microservice Technical Patterns

## Deployment & Independence

- **Independently deployable**: Each service MUST deploy without coordinating with others. If a plan requires simultaneous deployment, redesign with backward-compatible contracts first.
- **Feature flags over deploy coordination**: Use feature flags for progressive enablement rather than synchronized rollouts.

## API & Data Contracts

- **Backward-compatible API changes**: Always additive. New fields are optional. Old fields never removed in the same release.
- **API versioning**: If breaking changes are unavoidable, version the API (`/v1/`, `/v2/`).
- **API contracts first**: Specify the contract (REST endpoint, event schema) before implementation details.
- **Database schema independence**: Each service owns its data store. No shared databases. Migrations must be backward-compatible.

## Resilience

- **Circuit breakers**: Any inter-service call should have timeout + retry + fallback. Flag plans missing resilience patterns.
- **Idempotency**: Any state-modifying operation must be safe to retry. Specify how duplicate calls are handled.
- **Health endpoints**: Every service must expose `/health` (liveness) and `/ready` (readiness) with meaningful checks.

## Operational Hygiene

- **Observability**: Plans must include how changes will be monitored (metrics, logs, alerts).
- **Configuration via environment**: No hardcoded URLs, credentials, or feature flags in code. Everything via env vars or ConfigMaps.
- **Stateless services**: Flag any in-process state that breaks horizontal scaling (caches without TTL, sessions, in-memory queues). Externalize to Redis/DB.
