---
description: "GitHub Issue event environment, data structure, and lifecycle"
tag_type: rule
tags: [headhunter, github, issue]
---
# GitHub Issue Source Environment

## Data Available

GitHub Issue events carry an LLM-generated work plan in the reason field and structured issue
context in the evidence. The plan includes domain classification, risk assessment, and step
assignments derived from the issue body and labels.

The issue context includes: issue number and title, repository coordinates (owner/repo),
issue body (the specification — the primary source of intent), labels (may indicate routing
or skill domain), assignees, and a direct link to the GitHub issue.

There is no deployment metadata, no pipeline state, no branch, no CI status. Service lookup
against K8s annotations will not find deployment data for this event type — the repository
is the relevant scope, not a running workload.

## Specification vs Conversation

The issue body is the specification written by the person requesting the work. It describes
desired behavior, acceptance criteria, or a problem to solve — not a failure that occurred.

This is categorically different from an aligner anomaly or a pipeline failure: there is no
broken system to stabilize. The objective is to understand the specification and produce a
work plan that delivers the requested outcome.

When the body is ambiguous or under-specified, prefer a clarifying investigation step over
assuming intent. The author is reachable via the issue comment posted at event creation.

## Label Routing

Labels drive skill selection. When an issue carries a label that maps to a known skill domain
(e.g., `darwin-work:security`, `darwin-work:infra`), the triage instruction loaded for this
event encodes domain-specific behavior. If no skill-mapped label is present, the embedded
plan reflects a general triage pass.

Labels are author intent signals — treat them as steering, not hard constraints. An issue
labelled "refactor" might reveal a security gap during investigation; the label says where
to start, not where to stop.

## Execution Scope

GitHub Issues represent autonomous work delegated to Darwin. The scope boundary is the
repository: agents may read and write files, create commits, open pull requests, and run
tests within the repository. Cross-repository side effects require explicit instructions
in the issue body.

The darwin-active label on the issue is the in-flight signal. The darwin-done label is
posted on completion. The issue comment thread is the feedback channel back to the author.

## Close Protocol

GitHub Issue events are closed when the work described in the body is complete or when
a clear blocker requires human decision. Before closing:

- Verify the deliverable matches the issue specification (not just the plan steps).
- Post a resolution comment on the GitHub issue summarizing what was done.
- If the work produced a pull request, include the PR link in the close comment.

Do not close on partial completion. If scope is larger than one event, close what is done
and open a follow-up issue for the remainder.
