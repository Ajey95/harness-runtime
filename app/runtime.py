import uuid
import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from .models import TraceEntry, TaskResult
from .middleware import ApprovalMiddleware
from . import db
from .codex_adapter import adapter as codex
from .langgraph_adapter import adapter as lg
from .verifier import run_verification
try:
    from prometheus_client import Counter, Histogram
except Exception:
    # Fallback no-op metrics for environments without prometheus_client
    class _NoOpMetric:
        def inc(self, *a, **k):
            return None

        def time(self):
            class _Ctx:
                def __enter__(self):
                    return None

                def __exit__(self, exc_type, exc, tb):
                    return False

            return _Ctx()

    def Counter(*args, **kwargs):
        return _NoOpMetric()

    def Histogram(*args, **kwargs):
        return _NoOpMetric()


# A local no-op metric to use when metrics are already registered
class _NoOpMetricLocal:
    def inc(self, *a, **k):
        return None

    def time(self):
        class _Ctx:
            def __enter__(self):
                return None

            def __exit__(self, exc_type, exc, tb):
                return False

        return _Ctx()


class ExecutionRuntime:
    """
    Minimal execution runtime for orchestrating tasks and
    capturing traces.
    """

    def __init__(self) -> None:
        self.traces: Dict[str, List[TraceEntry]] = {}
        self.middleware = ApprovalMiddleware()
        # Prometheus metrics, guarded for repeated test imports.
        try:
            self.tasks_started = Counter(
                "hr_tasks_started_total",
                "Total tasks started",
            )
            self.tasks_completed = Counter(
                "hr_tasks_completed_total",
                "Total tasks completed",
            )
            self.verification_duration = Histogram(
                "hr_verification_duration_seconds",
                "Verification duration seconds",
            )
        except ValueError:
            # Prometheus already registered these names in this process.
            self.tasks_started = _NoOpMetricLocal()
            self.tasks_completed = _NoOpMetricLocal()
            self.verification_duration = _NoOpMetricLocal()
        except Exception:
            # Any other errors -> fall back to no-op
            self.tasks_started = _NoOpMetricLocal()
            self.tasks_completed = _NoOpMetricLocal()
            self.verification_duration = _NoOpMetricLocal()

    @staticmethod
    def _trace_stage_summary(traces: List[TraceEntry]) -> Dict[str, Any]:
        stage_counts = {
            "reasoning": 0,
            "middleware": 0,
            "tool_call": 0,
            "verification": 0,
        }
        for trace in traces:
            step = str(trace.step)
            if "verification" in step:
                stage_counts["verification"] += 1
            elif "approval" in step or "risk" in step or "middleware" in step:
                stage_counts["middleware"] += 1
            elif (
                "tool_call" in step
                or "propose_patch" in step
                or "apply_patch" in step
                or "rollback" in step
            ):
                stage_counts["tool_call"] += 1
            else:
                stage_counts["reasoning"] += 1
        return {
            "event_count": len(traces),
            "stage_counts": stage_counts,
        }

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

    @staticmethod
    def _trace_to_dict(trace: TraceEntry) -> Dict[str, Any]:
        if hasattr(trace, "model_dump"):
            return trace.model_dump()
        return trace.dict()

    @staticmethod
    def _trace_from_dict(payload: Dict[str, Any]) -> TraceEntry:
        return TraceEntry(
            timestamp=payload["timestamp"],
            step=payload["step"],
            detail=payload.get("detail"),
        )

    @staticmethod
    async def _verify_with_optional_checks(
        task_id: str,
        repo_path: Optional[str],
        health_url: Optional[str],
        container_name: Optional[str],
    ) -> Dict[str, Any]:
        try:
            return await run_verification(
                task_id,
                repo_path=repo_path,
                health_url=health_url,
                container_name=container_name,
            )
        except TypeError:
            return await run_verification(task_id, repo_path=repo_path)

    def _persist_task(
        self,
        task_id: str,
        status: str,
        traces: List[TraceEntry],
        report: Dict[str, Any],
    ) -> None:
        traces_list = [self._trace_to_dict(t) for t in traces]
        db.save_traces(task_id, traces_list, status=status)
        db.save_report(task_id, status, report)
        self.traces[task_id] = traces

    async def _run_allowed_steps(
        self,
        *,
        task_id: str,
        description: str,
        repo_path: Optional[str],
        traces: List[TraceEntry],
        start_time: datetime,
        risk: str,
        middleware_decision: Dict[str, Any],
        incident_id: Optional[str] = None,
        health_url: Optional[str] = None,
        container_name: Optional[str] = None,
    ) -> TaskResult:
        def add(step: str, detail: Optional[str] = None) -> None:
            traces.append(
                TraceEntry(
                    timestamp=datetime.now(timezone.utc),
                    step=step,
                    detail=detail,
                )
            )

        proposal = await codex.propose_patch(description)
        add("propose_patch", str(proposal))
        await asyncio.sleep(0.05)
        applied = await codex.apply_patch(proposal, cwd=repo_path)
        add("apply_patch", str(applied))
        if isinstance(applied, dict):
            tool_call = (
                "cmd={cmd} returncode={rc} ok={ok} workdir={workdir}"
                .format(
                    cmd=applied.get("cmd", "git apply"),
                    rc=applied.get("returncode"),
                    ok=applied.get("ok"),
                    workdir=applied.get("workdir", ""),
                )
            )
            add("tool_call", tool_call)

        add("verification_started", "Running verification checks")
        with self.verification_duration.time():
            verification = await self._verify_with_optional_checks(
                task_id,
                repo_path,
                health_url,
                container_name,
            )
        verification_status = verification["status"]
        add("verification_result", verification_status)

        patch_failed = (
            isinstance(applied, dict) and not applied.get("ok", False)
        )
        rollback = None
        if verification_status in {"failed", "error"} or patch_failed:
            add("rollback_started", "verification_failed_attempting_rollback")
            rollback = await self._attempt_rollback(repo_path=repo_path)
            add("rollback_result", str(rollback))

        final_status = (
            "completed"
            if verification_status in {"passed", "degraded_passed"}
            and not patch_failed
            else "verification_failed"
        )
        add(final_status, "Task execution finished")
        stage_summary = self._trace_stage_summary(traces)
        report = {
            "task_id": task_id,
            "incident_id": incident_id,
            "description": description,
            "repo_path": repo_path,
            "status": final_status,
            "risk": risk,
            "risk_score": middleware_decision["risk_score"],
            "middleware_decision": middleware_decision,
            "approval_required": middleware_decision["approval_required"],
            "approval_state": middleware_decision.get("approval_state"),
            "health_url": health_url,
            "container_name": container_name,
            "patch": applied,
            "verification_status": verification_status,
            "verification": verification.get("results"),
            "verification_degraded": verification.get("degraded"),
            "rollback": rollback,
            "stage_metrics": stage_summary,
            "duration_ms": int(
                (datetime.now(timezone.utc) - start_time).total_seconds()
                * 1000
            ),
        }
        self._persist_task(task_id, final_status, traces, report)
        if incident_id:
            db.update_incident(
                incident_id,
                status="recovered"
                if final_status == "completed"
                else "verification_failed",
                task_id=task_id,
                payload_updates={"verification_status": verification_status},
            )
        try:
            self.tasks_completed.inc()
        except Exception:
            pass
        return TaskResult(task_id=task_id, status=final_status, traces=traces)

    async def start_task(
        self,
        description: str,
        repo_path: Optional[str] = None,
        task_id: Optional[str] = None,
        incident_id: Optional[str] = None,
        health_url: Optional[str] = None,
        container_name: Optional[str] = None,
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
        try:
            self.tasks_started.inc()
        except Exception:
            pass
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
            traces_list = [self._trace_to_dict(t) for t in traces]
            stage_summary = self._trace_stage_summary(traces)
            db.save_traces(task_id, traces_list, status=status)
            db.save_report(
                task_id,
                status,
                {
                    "task_id": task_id,
                    "incident_id": incident_id,
                    "description": description,
                    "repo_path": repo_path,
                    "status": status,
                    "risk": risk,
                    "risk_score": middleware_decision["risk_score"],
                    "middleware_decision": middleware_decision,
                    "approval_required": middleware_decision[
                        "approval_required"
                    ],
                    "approval_state": middleware_decision["approval_state"],
                    "health_url": health_url,
                    "container_name": container_name,
                    "verification_status": "not_started",
                    "stage_metrics": stage_summary,
                    "duration_ms": int(
                        (
                            datetime.now(timezone.utc) - start_time
                        ).total_seconds()
                        * 1000
                    ),
                },
            )
            if incident_id:
                db.update_incident(
                    incident_id,
                    status=status,
                    task_id=task_id,
                    payload_updates={"approval_state": status},
                )
            self.traces[task_id] = traces
            return TaskResult(
                task_id=task_id,
                status=status,
                traces=traces,
            )

        return await self._run_allowed_steps(
            task_id=task_id,
            description=description,
            repo_path=repo_path,
            traces=traces,
            start_time=start_time,
            risk=risk,
            middleware_decision=dict(middleware_decision),
            incident_id=incident_id,
            health_url=health_url,
            container_name=container_name,
        )

    async def resume_task(self, task_id: str) -> TaskResult:
        report_row = db.get_report(task_id)
        if not report_row:
            raise ValueError("task report not found")
        report = report_row["report"] or {}
        if report.get("status") not in {"pending_approval", "rejected"}:
            raise ValueError("task is not waiting for approval")

        traces_payload = db.get_traces(task_id) or []
        traces = [self._trace_from_dict(t) for t in traces_payload]

        def add(step: str, detail: Optional[str] = None) -> None:
            traces.append(
                TraceEntry(
                    timestamp=datetime.now(timezone.utc),
                    step=step,
                    detail=detail,
                )
            )

        middleware_decision = self.middleware.evaluate_task(
            {
                "task_id": task_id,
                "description": report.get("description", ""),
            }
        )
        add(
            "approval_response",
            str(middleware_decision.get("approval_state")),
        )
        if middleware_decision["decision"] != "allowed":
            add("rejected", "Task remains halted by approval policy")
            stage_summary = self._trace_stage_summary(traces)
            report.update(
                {
                    "status": "rejected",
                    "middleware_decision": middleware_decision,
                    "approval_state": middleware_decision.get(
                        "approval_state"
                    ),
                    "stage_metrics": stage_summary,
                }
            )
            self._persist_task(task_id, "rejected", traces, report)
            return TaskResult(
                task_id=task_id,
                status="rejected",
                traces=traces,
            )

        return await self._run_allowed_steps(
            task_id=task_id,
            description=report.get("description", ""),
            repo_path=report.get("repo_path"),
            traces=traces,
            start_time=datetime.now(timezone.utc),
            risk=str(middleware_decision["risk"]),
            middleware_decision=dict(middleware_decision),
            incident_id=report.get("incident_id"),
            health_url=report.get("health_url"),
            container_name=report.get("container_name"),
        )

    def get_traces(self, task_id: Optional[str] = None):
        if task_id:
            return self.traces.get(task_id)
        return self.traces

    async def run_task_graph(
        self,
        description: str,
        repo_path: Optional[str] = None,
        task_id: Optional[str] = None,
    ):
        """Run the task using the LangGraph adapter. This is an alternate
        execution path that demonstrates LangGraph integration. It is not
        invoked by default by `start_task`, but test or orchestration code
        may call it directly.
        """
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

        async def node_analysis(ctx):
            add("analysis", f"Inspecting repo: {repo_path or 'local'}")
            analysis = await codex.run_analysis(
                repo_path or "local",
                description,
            )
            add("analysis_result", str(analysis))
            ctx["analysis"] = analysis
            return ctx

        def node_middleware(ctx):
            middleware_decision = self.middleware.evaluate_task(
                {
                    "task_id": task_id,
                    "description": description,
                }
            )
            add("middleware_decision", str(middleware_decision))
            ctx["middleware_decision"] = middleware_decision
            return ctx

        async def node_propose(ctx):
            proposal = await codex.propose_patch(description)
            add("propose_patch", str(proposal))
            ctx["proposal"] = proposal
            return ctx

        async def node_apply(ctx):
            proposal = ctx.get("proposal")
            applied = await codex.apply_patch(proposal, cwd=repo_path)
            add("apply_patch", str(applied))
            ctx["applied"] = applied
            return ctx

        async def node_verify(ctx):
            add("verification_started", "Running verification checks")
            verification = await run_verification(task_id, repo_path=repo_path)
            add("verification_result", verification.get("status"))
            ctx["verification"] = verification
            return ctx

        lg.add_node("analysis", node_analysis)
        lg.add_node("middleware", node_middleware)
        lg.add_node("propose", node_propose)
        lg.add_node("apply", node_apply)
        lg.add_node("verify", node_verify)
        lg.add_edge("analysis", "middleware")
        lg.add_edge("middleware", "propose")
        lg.add_edge("propose", "apply")
        lg.add_edge("apply", "verify")

        context = {
            "task_id": task_id,
            "description": description,
            "repo_path": repo_path,
        }
        await lg.run("analysis", context)

        # persist traces
        traces_list = [self._trace_to_dict(t) for t in traces]
        stage_summary = self._trace_stage_summary(traces)
        db.save_traces(task_id, traces_list, status="completed")
        db.save_report(
            task_id,
            "completed",
            {
                "task_id": task_id,
                "status": "completed",
                "stage_metrics": stage_summary,
            },
        )
        self.traces[task_id] = traces
        return TaskResult(task_id=task_id, status="completed", traces=traces)
