<!-- @ai-rules:
1. [Pattern]: Keep a Changelog format (https://keepachangelog.com). Sections: Added, Changed, Fixed, Removed.
2. [Constraint]: New entries go at the TOP, under ## [Unreleased] until version is tagged.
3. [Constraint]: SemVer. Breaking changes = major bump.
-->
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-03-20

### Added

- Multi-agent orchestration via Blackboard pattern with Brain (Vertex AI Pro) as orchestrator
- Progressive skill loading system with phase-specific Markdown skills and dependency resolution
- Cynefin decision framework for event classification (Clear/Complicated/Complex/Chaotic)
- Agent sidecars: Architect, SysAdmin, Developer, QE with Gemini CLI and Claude Code
- Deep memory via Qdrant vector store with event summarization and similarity search
- Bidirectional Slack integration (Socket Mode, DM notifications, thread mirroring)
- Headhunter agent for GitLab MR lifecycle automation with two-tier triage
- TimeKeeper for scheduled one-shot and recurring tasks with LLM instruction refinement
- Ephemeral agents via Tekton TaskRun with circuit breaker and prune trigger
- React Dashboard with architecture graph, conversation feed, agent streaming cards
- Dex OIDC identity integration with cert-manager TLS
- Kubernetes observer with darwin.io annotation-based service discovery
- Structured plan tracking with YAML frontmatter step assignments
- Helm chart for Kubernetes/OpenShift deployment
- GitHub Actions CI for container image and Helm chart publishing
