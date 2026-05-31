# Harness Runtime (HR Runtime) — MVP

Harness Runtime is a supervisory orchestration layer for autonomous AI engineering agents (Codex CLI-style). It provides supervised execution, trace capture, approval workflows, verification, and observability for automated remediation tasks.

This repository contains the Hackathon MVP described in `prd.md`.

## Repository layout

- `app/` — FastAPI backend runtime and modules (runtime, middleware, db, verifier, codex adapter)
- `frontend/` — Next.js dashboard scaffold (minimal)
- `dashboard/` — simple static dashboard placeholder (HTML)
- `presentation/` — 4-slide HTML pitch deck (open in browser)
- `requirements.txt` — Python dependencies
- `Dockerfile` — container image for the backend
- `demo_trigger.sh` / `demo_trigger.ps1` — demo scripts to trigger tasks + verification
- `runtime.db` — SQLite runtime DB (created at runtime)

## Quick start (local)

1. Create a virtualenv and install dependencies (Windows PowerShell shown):

```powershell
python -m venv .venv
. .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Start the FastAPI server:

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

3. Trigger a demo task (PowerShell):

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/tasks -Method POST -Body (@{description='Demo remediation: fix config'} | ConvertTo-Json) -ContentType 'application/json'
```

4. Start verification for a task (replace `<task_id>`):

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/verify/<task_id> -Method POST
Invoke-RestMethod -Uri http://127.0.0.1:8000/verify/<task_id> -Method GET
```

## API Endpoints

- `GET /health` — health check
- `POST /tasks` — start an execution task (payload: `{"description":"...","repo_path":"..."}`)
- `GET /traces` — list stored traces
- `POST /verify/{task_id}` — start verification runner (background)
- `GET /verify/{task_id}` — get verification result
- `POST /approvals/{task_id}` — set approval for a task (`approved`, `approver`, `note`)
- `GET /approvals` — list approvals
- `GET /reports` — list execution reports
- `GET /reports/{task_id}` — get one execution report
- `GET /metrics` — aggregated live observability metrics across tasks
- `GET /metrics/{task_id}` — task-level lifecycle and stage metrics

## Architecture and features

- **Execution Runtime**: orchestrates tasks, records trace entries across phases (analysis, propose, apply, verify).
- **Middleware**: keyword-based risk classification and approval-gated execution for medium/high-risk tasks.
- **Codex Adapter**: constrained subprocess adapter with explicit command allowlist, sandbox-path enforcement, and degraded-mode signaling when Codex CLI is unavailable.
- **Verification Runner**: executes allowlisted checks (`pytest -q`, `flake8 app tests`) with retries, strict command validation, and persisted status metadata.
- **Execution Reports**: each task writes a lifecycle report with middleware decision metadata, verification summary, rollback attempt details, and runtime duration.
- **Observability**: traces, verification, reports, and stage-level metrics are persisted/derived from SQLite (`runtime.db`) and can be queried via HTTP.
- **Dashboard**: Next.js runtime dashboard with task list, reasoning lifecycle graph, middleware/approval visibility, and timeline filtering.
- **CI**: GitHub Actions workflow runs lint, full tests, and a dedicated PRD acceptance matrix gate (`tests/test_acceptance_matrix.py`).

## Security notes and limitations

- Verification and Codex command execution are allowlisted to prevent unrestricted shell commands.
- Repository paths are validated before command execution.

## Files created for this deliverable

- `script.md` — demo script and presentation narration (see root)
- `presentation/slide_deck.html` — 4-slide pitch deck (open in browser)

## Publish to GitHub (automated)

1. Ensure `gh` CLI is installed and authenticated (`gh auth login`).
2. From the repository root run:

```bash
gh repo create <your-username>/harness-runtime --public --source=. --remote=origin --push
```

When the repository is public, the presentation file `presentation/slide_deck.html` will be accessible via the repository file URL and can be shared broadly.

## PRD coverage snapshot (MVP)

- Implemented now:
  - Codex task orchestration flow with governance checkpoints
  - tool-call capture in execution traces
  - policy-driven risk + approval middleware decisions
  - allowlisted verification execution with persisted outcomes
  - execution reports and observability endpoints
  - live metrics pipeline (`/metrics`) for status, latency, stage transitions, and degraded-mode tracking
  - explicit FR-1..FR-10 acceptance matrix (`acceptance_matrix.json`) with CI-gated automated checks
  - dashboard drill-down for reasoning timeline and middleware states
- Still explicitly deferred (matches PRD deferred scope):
  - Kubernetes/distributed runtime
  - multi-agent orchestration
  - RL/advanced autonomy optimization
  - enterprise multi-tenancy/RBAC hardening

## Contact / Credits

- Created as an MVP scaffolding for the Harness Runtime PRD. Use and adapt freely for demos and hackathons.
