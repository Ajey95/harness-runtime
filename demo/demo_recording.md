# Demo Recording Runbook

This runbook is the source artifact for recording the required MVP demo video.

## Setup

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
cd frontend
npm run dev
```

Open `http://localhost:3000`.

## Recording Flow

1. Show the empty operations console.
2. Click `Trigger Demo Incident`.
3. Open the incident monitor and task list.
4. Show the pending approval state and medium-risk middleware decision.
5. Click `Approve Task`.
6. Wait for the task to complete.
7. Show the reasoning graph, tool-call panel, verification result, incident
   status, and report metrics.
8. Open `/reports/{task_id}` in the API to show the persisted execution report.

## Expected Result

- Incident status moves from `detected` to `pending_approval` to `recovered`.
- Task traces include `risk_classified`, `approval_response`, `tool_call`,
  `verification_started`, and `verification_result`.
- The report includes patch details, health check result, container status,
  middleware decision, and duration.
