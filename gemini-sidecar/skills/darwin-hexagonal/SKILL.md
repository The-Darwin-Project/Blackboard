---
name: darwin-hexagonal
description: Hexagonal Architecture (Ports & Adapters) patterns for code review and planning. Use when reviewing code structure, planning new features, or evaluating coupling.
---

# Hexagonal Architecture (Ports & Adapters)

## Core Principles

- **Core domain isolation**: Business logic MUST have zero import dependencies on infrastructure. No `import redis`, `import kubernetes`, `import requests` in domain modules.
- **Ports**: Interfaces defined BY the core domain (e.g., `class EventStore(Protocol)`, `class MetricsProvider(Protocol)`). The core says what it needs; adapters provide it.
- **Adapters**: Implementations of ports for specific technologies (e.g., `RedisEventStore`, `K8sMetricsProvider`). Adapters import infrastructure libraries; the core never does.
- **Dependency direction**: Always inward. Adapters depend on ports. Core depends on nothing external.

## When Reviewing Code

- Flag any business logic file that directly imports a database client, HTTP library, or cloud SDK
- Recommend extracting a port (interface) to decouple
- If a change modifies both a port interface and its adapter, flag it in the risk assessment

## When Planning New Features

- Specify which port the new code enters through
- Specify which adapter will implement it
- If the port doesn't exist yet, design it as part of the plan
- Boundary crossings (modifying port + adapter) carry higher risk
