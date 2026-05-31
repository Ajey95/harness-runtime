import uuid
import asyncio
from datetime import datetime
from typing import Dict, List, Optional

from .models import TraceEntry, TaskResult
from .middleware import ApprovalMiddleware
from . import db
from .codex_adapter import adapter as codex
from .verifier import run_verification


class ExecutionRuntime:
    """
    Minimal execution runtime for orchestrating tasks and
    capturing traces.
    """

    def __init__(self) -> None:
        self.traces: Dict[str, List[TraceEntry]] = {}
        self.middleware = ApprovalMiddleware()

    async def start_task(
        self,
        description: str,
        repo_path: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> TaskResult:
        task_id = task_id or str(uuid.uuid4())
        traces: List[TraceEntry] = []

        def add(step: str, detail: Optional[str] = None) -> None:
            traces.append(
                TraceEntry(
                    timestamp=datetime.utcnow(),
                    step=step,
                    detail=detail,
                )
            )

        add("task_started", description)
        start_time = datetime.utcnow()

        # Analysis phase (simulated)
        add(
            "analysis",
            f"Inspecting repo: {repo_path or 'local'}",
        )
        # call adapter analysis
        analysis = await codex.run_analysis(repo_path or "local", description)
        add("analysis_result", str(analysis))
        await asyncio.sleep(0.05)

        # Risk classification via middleware
        risk = self.middleware.classify_risk(description)
        add("risk_classified", risk)

        # Approval flow
        if self.middleware.require_approval(risk):
            add("approval_requested")
            req = {"task_id": task_id, "description": description}
            approved = self.middleware.request_approval(req)
            add("approval_response", str(approved))
            if not approved:
                approval_state = db.get_approval(task_id)
                rejected = bool(approval_state and not approval_state["approved"])
                status = "rejected" if rejected else "pending_approval"
                add(status, "Task halted by approval policy")
                traces_list = [t.dict() for t in traces]
                db.save_traces(task_id, traces_list, status=status)
                db.save_report(
                    task_id,
                    status,
                    {
                        "task_id": task_id,
                        "status": status,
                        "risk": risk,
                        "approval_required": True,
                        "approval_state": approval_state,
                        "verification_status": "not_started",
                        "duration_ms": int(
                            (datetime.utcnow() - start_time).total_seconds()
                            * 1000
                        ),
                    },
                )
                self.traces[task_id] = traces
                return TaskResult(
                    task_id=task_id,
                    status=status,
                    traces=traces,
                )

        # Propose and apply patch (simulated)
        proposal = await codex.propose_patch(description)
        add("propose_patch", str(proposal))
        await asyncio.sleep(0.05)
        applied = await codex.apply_patch(proposal, cwd=repo_path)
        # applied may be a dict with command output
        add("apply_patch", str(applied))
        # record tool call detail if available
        try:
            if isinstance(applied, dict):
                out_snippet = (applied.get("stdout") or "")[:200]
                tool_call = (
                    "cmd={cmd} returncode={rc} stdout={out}"
                    .format(
                        cmd=applied.get("cmd"),
                        rc=applied.get("returncode"),
                        out=out_snippet,
                    )
                )
                add("tool_call", tool_call)
        except Exception:
            # best-effort recording; ignore failures here
            pass

        add("verification_started", "Running verification checks")
        verification = await run_verification(task_id, repo_path=repo_path)
        verification_status = verification["status"]
        add("verification_result", verification_status)
        final_status = (
            "completed" if verification_status == "passed"
            else "verification_failed"
        )
        add(final_status, "Task execution finished")
        result = TaskResult(
            task_id=task_id,
            status=final_status,
            traces=traces,
        )
        self.traces[task_id] = traces
        # persist traces
        traces_list = [t.dict() for t in traces]
        db.save_traces(task_id, traces_list, status=final_status)
        db.save_report(
            task_id,
            final_status,
            {
                "task_id": task_id,
                "status": final_status,
                "risk": risk,
                "approval_required": self.middleware.require_approval(risk),
                "verification_status": verification_status,
                "verification": verification.get("results"),
                "duration_ms": int(
                    (datetime.utcnow() - start_time).total_seconds() * 1000
                ),
            },
        )
        return result

    def get_traces(self, task_id: Optional[str] = None):
        if task_id:
            return self.traces.get(task_id)
        return self.traces
