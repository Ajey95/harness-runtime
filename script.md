# Demo Script & Presentation Narration

This file contains the demo script (what to say and do) and the narration for each slide in the 4-slide pitch deck. Use this as your speaking notes during the demo.

## Demo flow (2–4 minutes)

1. Start the backend server and show health endpoint.
2. Trigger a remediation task using `POST /tasks` and show trace capture in `GET /traces`.
3. Start verification `POST /verify/{task_id}` and poll `GET /verify/{task_id}`.
4. Show the dashboard and the approvals list; demonstrate approving a medium-risk action.

Keep the demo concise: highlight supervision, traceability, and verification.

---

## Slide narration (per slide)

Slide 1 — Problem (pain point):

- "Modern autonomous coding agents are powerful but risky: they can make unsafe repo changes, hallucinate fixes, and run unrestricted commands. Teams lack runtime supervision, traceability, and easy approval controls. This causes operational risk and slow remediation cycles."

Slide 2 — Solution & User Journey:

- "Harness Runtime supervises AI engineers: it triggers agent tasks, captures all tool calls and reasoning traces, enforces middleware policies, requests approval for risky actions, applies verified patches, and records verification outcomes. The user journey: an infra alert -> runtime creates a task -> agent proposes fix -> middleware asks for approval (if needed) -> runtime applies patch -> verification runs -> dashboard displays trace and result."

Slide 3 — Tools & Tech Stack:

- "Backend: FastAPI for async orchestration. Runtime DB: SQLite for MVP (Postgres optional). Verification: PyTest / Flake8 runner. Frontend: Next.js for dashboard. Agent integration: Codex CLI adapter (simulated). Observability: structured traces persisted and exposed via HTTP. CI: GitHub Actions. Containerization: Dockerfile provided."

Slide 4 — Target Audience:

- "Platform engineers, SREs, DevOps teams, and security teams who need governed automation. Also researchers who want reproducible traces of agent reasoning."

---

## Commands and notes

- Start server: `uvicorn app.main:app --reload --port 8000`
- Trigger task (PowerShell example):

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/tasks -Method POST -Body (@{description='Demo run'} | ConvertTo-Json) -ContentType 'application/json'
```

- Start verification:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/verify/<task_id> -Method POST
```

---

End of script.
