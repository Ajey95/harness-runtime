import uuid
import asyncio
from datetime import datetime
from typing import Dict, List, Optional

from .models import TraceEntry, TaskResult
from .middleware import ApprovalMiddleware
from . import db
from .codex_adapter import adapter as codex


class ExecutionRuntime:
    """Minimal execution runtime for orchestrating tasks and capturing traces."""

    def __init__(self) -> None:
        self.traces: Dict[str, List[TraceEntry]] = {}
        self.middleware = ApprovalMiddleware()

    async def start_task(self, description: str, repo_path: Optional[str] = None, task_id: Optional[str] = None) -> TaskResult:
        task_id = task_id or str(uuid.uuid4())
        traces: List[TraceEntry] = []

        def add(step: str, detail: Optional[str] = None) -> None:
            traces.append(TraceEntry(timestamp=datetime.utcnow(), step=step, detail=detail))

        add("task_started", description)

        # Analysis phase (simulated)
        add("analysis", f"Inspecting repo: {repo_path or 'local'}")
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
            approved = self.middleware.request_approval({"task_id": task_id, "description": description})
            add("approval_response", str(approved))
            if not approved:
                db.save_traces(task_id, [t.dict() for t in traces], status="rejected")
                self.traces[task_id] = traces
                return TaskResult(task_id=task_id, status="rejected", traces=traces)

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
                add("tool_call", f"cmd={applied.get('cmd')} returncode={applied.get('returncode')} stdout={applied.get('stdout')[:200]}")
        except Exception:
            pass

        # Verification (simulated)
        add("verification", "Running verification checks (simulated)")
        # TODO: hook up real verification runner (tests, linters)
        await asyncio.sleep(0.05)

        add("completed", "Task completed successfully")
        result = TaskResult(task_id=task_id, status="completed", traces=traces)
        self.traces[task_id] = traces
        # persist traces
        db.save_traces(task_id, [t.dict() for t in traces], status="completed")
        return result

    def get_traces(self, task_id: Optional[str] = None):
        if task_id:
            return self.traces.get(task_id)
        return self.traces
