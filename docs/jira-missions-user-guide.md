# Jira Missions: A User Guide (Jira Side)

This guide explains how to use the **Headhunter Jira** integration from the
perspective of a Jira user — no BlackBoard/Darwin internals required. It
covers how to submit a mission, what happens automatically, how to review and
approve FRIDAY's plan, how to steer work while it's running, and what the
final result looks like.

> Source: `src/agents/headhunter_jira.py` (the polling daemon) and
> `src/agents/brain_skills/source/headhunter_jira.md` (FRIDAY's behavioral
> contract for these events). If behavior described here ever seems to
> diverge from what you observe in Jira, treat this doc as possibly stale and
> the source files as ground truth.

## 1. What This Integration Does

Darwin's Headhunter Jira daemon polls Jira on a schedule, looking for issues
that are:
- **Assigned to the Darwin bot account**, and
- **Labeled** with the configured base label (default: `darwin`)

It runs a **two-phase flow** driven entirely by the issue's **Status**:

| Status | What happens |
|---|---|
| `Planning` | Bot analyzes the issue and posts a validation/execution plan as a **comment**. No autonomous work starts yet. |
| `To Do` | Bot treats your move to this status as approval and creates a live Darwin event — FRIDAY (the orchestrator) begins dispatching agents. |
| `In Progress` | Set automatically by FRIDAY once she starts working the approved plan. |
| `Dev Complete` | Set automatically by FRIDAY when the work finishes (success, or failure/escalation with findings attached). |

You never need to open a dashboard — the Jira issue itself is the entire
control surface and the entire communication channel.

## 2. Creating a Mission

1. Create a Jira issue as you normally would (bug, task, story — whatever
   your project uses).
2. **Assign it to the Darwin bot account.**
3. **Add the base label** (ask your Darwin admin what it's configured to —
   defaults to `darwin`).
4. Optionally add a **second label** to route the issue to a specialized
   analysis prompt (see §3). If you don't add one, the bot uses its built-in
   default analyst persona.
5. **Set Status to `Planning`.**

That's it — no special fields, no custom issue type is required beyond what
your project already uses. The bot picks up issues on its next poll cycle.

## 3. Labels Are Routing, Not Decoration

Beyond the required base label (`darwin`), any **additional label** you add
can select a different analysis "skill" — a domain-specific system prompt
maintained by your team in your own git repo (e.g., a QE-specific analyst
persona vs. a security-audit persona vs. a generic one).

- If your label matches a configured skill, the bot fetches that team's
  custom prompt and uses it for analysis.
- If it doesn't match anything configured, the bot falls back to its
  built-in default (a general QE/business-analyst persona).
- You can find out from your Darwin admin which labels are wired to which
  skills — this is a per-deployment configuration, not something visible in
  Jira itself.

**Practical implication**: pick your second label deliberately if your team
has a specialized skill configured (e.g., `qe_testing`, `darwin_audit`) —
it materially changes the quality and focus of the plan you get back.

## 4. The Planning Phase: Review the Bot's Comment

Once your issue is in `Planning` with the right assignee/label, on the next
poll cycle the bot will:

1. Read the issue (summary, description, comments, linked issues, parent,
   components, fix versions).
2. Run an analysis pass against the domain-specific or default prompt.
3. **Post a comment** on the issue containing a structured plan: issue
   summary, validation points, test strategy, preconditions, suggested
   priority/tier, risk assessment, and environment constraints.

**This comment is not autonomous work — it's a proposal for you to review.**
Nothing executes yet. Read it like you'd read a plan from a colleague.

### If you disagree or need changes

**@mention the bot account** in a comment. Any comment where you (a
*watcher* on the issue) tag the bot will trigger a **re-analysis** — the bot
re-reads the issue (including your new comment) and posts an updated plan.
This is the feedback loop: keep @mentioning with clarifications until the
plan looks right.

> Only comments from users who are **watchers on the issue** trigger
> re-analysis. If your @mention doesn't seem to register, make sure you're
> watching the issue.

### If the plan looks right

Move the **Status to `To Do`**. This is the explicit human approval gate —
nothing autonomous happens until you do this.

## 5. The To Do Phase: Approval Triggers Execution

The moment an issue lands in `To Do` (with bot assignee + label still set),
on the next poll cycle the bot:

1. Takes the (already-approved) analysis and runs a second pass to produce a
   **structured execution plan** — concrete steps, each assigned to a
   specific agent role (`developer`, `qe`, `architect`, `sysadmin`,
   `security_analyst`, `code_reviewer`) with an execution mode
   (`investigate`, `test`, `implement`, `execute`, `review`).
2. Creates a Darwin event and hands it to FRIDAY (the orchestrator).
3. FRIDAY translates the embedded plan into her own tracked execution plan
   and begins dispatching agents.

From this point, you'll see:
- **Status → `In Progress`** as soon as FRIDAY starts working the plan.
- **Progress comments at meaningful milestones** — not after every internal
  step. Expect a comment when a major phase finishes with real findings
  (e.g., "audit complete", "MR opened"), when an unexpected blocker changes
  the plan, or when work is deferred waiting on something external (like a
  CI pipeline). You will **not** get a comment for every routine
  agent handoff — that's intentional, to avoid notification fatigue (each
  comment is a Jira email to watchers).

### If work produces a pull/merge request

If a plan step results in a PR/MR with a running pipeline, the event won't
close until that pipeline resolves. FRIDAY will defer and check back rather
than closing prematurely just because "code was written." You may see a
comment referencing the PR/MR link.

### Re-steering mid-execution

The same @mention re-evaluation gate is watched continuously, not just during
`Planning`. If you (as a watcher) @mention the bot with new information while
work is in progress, expect it to be picked up as a signal — though the
primary approval/re-plan loop is designed around the `Planning` phase.
Practical implication: comment naturally, tag the bot when you need attention.

## 6. Completion

When the work finishes, the bot enforces a strict, single-shot close
sequence so your inbox isn't flooded:

1. **Status transitions to `Dev Complete`** — used for both success and
   failure/escalation outcomes. (There is no separate "failed" status; check
   the closing comment for the actual outcome.)
2. **Exactly one final summary comment** is posted, and the **issue
   reporter is @mentioned** in it so they get notified.
3. No further comments are posted after that — the event is done.

If something couldn't be resolved automatically, the closing comment
contains findings/escalation details instead of a "done" confirmation — read
the comment text, not just the status, to know the real outcome.

## 7. Quick Reference

| You do this in Jira | Bot does this |
|---|---|
| Assign to bot + add base label + set `Planning` | Analyzes issue, posts plan as a comment |
| @mention bot in a comment (as a watcher) | Re-analyzes, posts an updated plan comment |
| Add a second label matching a configured skill | Uses that team's custom analysis persona instead of the default |
| Move Status to `To Do` | Approval — generates execution plan, creates live event, FRIDAY starts dispatching agents |
| (automatic) | Status → `In Progress` when execution starts |
| (automatic) | Milestone comments during execution (not every step) |
| (automatic) | Status → `Dev Complete` + one final comment mentioning you, when finished |

## 8. Things That Won't Happen (By Design)

- The bot will **not** start any work while the issue is in `Planning` —
  that phase is analysis-only, no side effects.
- The bot will **not** act on @mentions from non-watchers.
- The bot will **not** post a comment for every internal agent handoff —
  only meaningful milestones.
- The bot will **not** close the issue while a produced PR/MR's pipeline is
  still running.
- The bot will **not** post more than one comment after the final close —
  if you see continued chatter after "Dev Complete," that's unexpected
  behavior worth flagging to your Darwin admin.

## 9. If Nothing Seems to Happen

Check with your Darwin admin (this is deployment configuration, not
something you can see from Jira):
- Is the bot account and base label correctly set on your issue?
- Is the global work-in-progress cap currently full? (The bot backs off
  creating new events, though not new analysis, when the system is at
  capacity — it will pick your issue up once capacity frees.)
- Is the Jira integration itself enabled for this environment?

Analysis-phase (`Planning`) comments are not gated by capacity — if you're
not even getting a first plan comment, the issue is more likely a
label/assignee mismatch than a capacity problem.
