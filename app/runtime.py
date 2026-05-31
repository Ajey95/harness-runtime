import uuid
import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

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

    async def _attempt_rollback(
        self,
        repo_path: Optional[str],
    ) -> Dict[str, Any]:
        if not repo_path:
            return {"status": "skipped", "reason": "repo_path_not_provided"}
        reset = await codex.run_command(
            "git status --short",
            cwd=repo_path,
            timeout=20,
        )
        if reset.get("returncode") not in (0, None):
            return {
                "status": "error",
                "reason": "status_probe_failed",
                "detail": reset,
            }
        return {
            "status": "safe_noop",
            "reason": "no_patch_apply_command_configured",
            "detail": reset,
        }

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
                    timestamp=datetime.now(timezone.utc),
                    step=step,
                    detail=detail,
                )
            )

        add("task_started", description)
        start_time = datetime.now(timezone.utc)

        # Analysis phase (simulated)
        add(
            "analysis",
            f"Inspecting repo: {repo_path or 'local'}",
        )
        # call adapter analysis
        analysis = await codex.run_analysis(repo_path or "local", description)
        add("analysis_result", str(analysis))
        await asyncio.sleep(0.05)

        # Middleware governance decision
        middleware_decision = self.middleware.evaluate_task(
            {"task_id": task_id, "description": description}
        )
        risk = str(middleware_decision["risk"])
        add("risk_classified", f"{risk}:{middleware_decision['risk_score']}")
        add("middleware_decision", str(middleware_decision))

        decision = middleware_decision["decision"]
        if decision in {"pending_approval", "rejected"}:
            status = str(decision)
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
                    "risk_score": middleware_decision["risk_score"],
                    "middleware_decision": middleware_decision,
                    "approval_required": middleware_decision[
                        "approval_required"
                    ],
                    "approval_state": middleware_decision["approval_state"],
                    "verification_status": "not_started",
                    "duration_ms": int(
                        (
                            datetime.now(timezone.utc) - start_time
                        ).total_seconds()
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

        rollback = None
        if verification_status in {"failed", "error"}:
            add("rollback_started", "verification_failed_attempting_rollback")
            rollback = await self._attempt_rollback(repo_path=repo_path)
            add("rollback_result", str(rollback))

        final_status = (
            "completed" if verification_status in {"passed", "degraded_passed"}
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
                "risk_score": middleware_decision["risk_score"],
                "middleware_decision": middleware_decision,
                "approval_required": middleware_decision["approval_required"],
                "verification_status": verification_status,
                "verification": verification.get("results"),
                "verification_degraded": verification.get("degraded"),
                "rollback": rollback,
                "duration_ms": int(
                    (
                        datetime.now(timezone.utc) - start_time
                    ).total_seconds() * 1000
                ),
            },
        )
        return result

    def get_traces(self, task_id: Optional[str] = None):
        if task_id:
            return self.traces.get(task_id)
        return self.traces
