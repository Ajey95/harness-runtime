# Harness Runtime — Pitch Deck

Author: Harness Runtime Team
Date: 2026-05-28

---

## Slide 1 — Problem (Pain Point)

- Autonomous AI coding agents can edit repositories and run commands with minimal supervision.
- Teams lack runtime supervision, traceability, and enforced approval workflows.
- Risks: hallucinated fixes, unsafe changes, invisible tool calls, and operational instability.

**Speaker notes:**

- Introduce the core pain: agents are powerful but act like black boxes.
- Give one short example: an agent replaces a config causing service outage because it applied an unverified patch.

---

## Slide 2 — Proposed Solution & User Journey

- Harness Runtime: a supervisory orchestration layer that treats AI agents as supervised operational workers.
- Key functions:
  - Orchestrate agent tasks (triggered by alerts or issues)
  - Capture reasoning traces and tool calls
  - Classify risk and require approval when needed
  - Apply patches in a constrained environment
  - Run verification checks (tests, linters)
  - Expose traces and decisions via a dashboard

**User journey (short):**

1. Alert triggers a task
2. Runtime runs Codex agent analysis and proposes a patch
3. Middleware classifies risk and optionally requests approval
4. Patch is applied in sandbox and verification runs
5. Dashboard shows trace, verification result, and final report

**Speaker notes:**

- Walk through the five-step journey with emphasis on human-in-loop approval and verification.

---

## Slide 3 — Tools & Tech Stack

- Backend: FastAPI (async orchestration)
- Runtime graph / Orchestration: Execution runtime + middleware
- Agent: Codex CLI adapter (pluggable, currently simulated)
- Verification: PyTest + Flake8 runner (configurable)
- Storage: SQLite for MVP; Postgres for scale
- Frontend: Next.js dashboard (observability + approvals)
- CI / Automation: GitHub Actions
- Container: Dockerfile provided for deployment

**Speaker notes:**

- Explain why these choices: FastAPI for async tasks, Next.js for quick dashboard, and SQLite for fast local demos.

---

## Slide 4 — Target Audience

- Platform Engineers & SREs: safe automated remediation with verification
- DevOps Teams: governed automation and reduced toil
- Security & Compliance: auditable tool-call traces and approval records
- Researchers: reproducible traces to analyze agent reasoning and behavior

**Speaker notes:**

- Describe specific benefits for each audience and an example workflow for platform engineers.

---

## Appendix — Demo Callouts

- Demo endpoints: `POST /tasks`, `GET /traces`, `POST /verify/{task_id}`, `GET /verify/{task_id}`, `POST /approvals/{task_id}`
- Demo flow: start server → trigger task → start verification → inspect traces → approve if required
