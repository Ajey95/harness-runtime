import asyncio
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

# Ensure repo root is on sys.path so `import app` works under CI
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import db  # noqa: E402
from app.codex_adapter import adapter  # noqa: E402
from app.main import get_report, get_metrics, list_metrics  # noqa: E402
from app.middleware import ApprovalMiddleware  # noqa: E402
from app import runtime as runtime_module  # noqa: E402
from app.runtime import ExecutionRuntime  # noqa: E402
from app.verifier import run_verification  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "runtime.db")
    db.init_db()
    yield


def test_risk_classification_and_approval_threshold():
    middleware = ApprovalMiddleware()
    assert middleware.classify_risk("update docs only") == "low"
    assert middleware.classify_risk("restart docker service") == "medium"
    assert middleware.classify_risk("delete production secret") == "high"
    assert middleware.require_approval("medium") is True
    assert middleware.require_approval("high") is True


def test_command_allowlist_blocks_disallowed_commands():
    result = asyncio.run(adapter.run_command("ls -la", cwd=str(ROOT)))
    assert result["returncode"] is None
    assert "allowlisted" in result["stderr"]


def test_command_allowlist_allows_expected_commands():
    result = asyncio.run(
        adapter.run_command("echo Applying patch", cwd=str(ROOT))
    )
    assert result["returncode"] == 0


def test_command_blocks_paths_outside_sandbox(tmp_path):
    result = asyncio.run(
        adapter.run_command("echo Applying patch", cwd=str(tmp_path))
    )
    assert result["returncode"] is None
    assert "outside sandbox root" in result["stderr"]


def test_runtime_pauses_when_approval_missing():
    runtime = ExecutionRuntime()
    result = asyncio.run(
        runtime.start_task(
            "restart docker service",
            repo_path=str(ROOT),
            task_id="task-needs-approval",
        )
    )
    assert result.status == "pending_approval"
    report = db.get_report("task-needs-approval")
    assert report is not None
    assert report["report"]["approval_required"] is True
    assert report["report"]["verification_status"] == "not_started"
    assert (
        report["report"]["middleware_decision"]["decision"]
        == "pending_approval"
    )


def test_runtime_rejects_when_explicitly_denied():
    db.save_approval("task-denied", approved=False, approver="ops", note="no")
    runtime = ExecutionRuntime()
    result = asyncio.run(
        runtime.start_task(
            "restart docker service",
            repo_path=str(ROOT),
            task_id="task-denied",
        )
    )
    assert result.status == "rejected"


def test_middleware_evaluate_task_states():
    middleware = ApprovalMiddleware()
    pending = middleware.evaluate_task(
        {"task_id": "task-pending", "description": "restart docker service"}
    )
    assert pending["decision"] == "pending_approval"
    db.save_approval("task-approved", approved=True, approver="ops")
    allowed = middleware.evaluate_task(
        {"task_id": "task-approved", "description": "restart docker service"}
    )
    assert allowed["decision"] == "allowed"
    assert allowed["approval_required"] is True


def test_verifier_reports_degraded_on_non_allowlisted_command():
    result = asyncio.run(
        run_verification(
            task_id="verify-degraded",
            repo_path=str(ROOT),
            commands=["echo not-allowed"],
        )
    )
    assert result["status"] == "degraded_passed"
    assert result["degraded"] is True


def test_runtime_report_includes_rollback_and_verification(monkeypatch):
    async def fake_verification(task_id, repo_path=None):
        return {
            "task_id": task_id,
            "status": "failed",
            "results": [],
            "degraded": False,
        }

    monkeypatch.setattr(runtime_module, "run_verification", fake_verification)
    runtime = ExecutionRuntime()
    result = asyncio.run(
        runtime.start_task(
            "update docs only",
            repo_path=str(ROOT),
            task_id="task-fail-roll",
        )
    )
    assert result.status == "verification_failed"
    report = db.get_report("task-fail-roll")
    assert report is not None
    payload = report["report"]
    assert payload["middleware_decision"]["decision"] == "allowed"
    assert payload["rollback"]["status"] in {
        "rolled_back",
        "safe_noop",
        "error",
        "skipped",
    }


def test_reports_endpoint_returns_report():
    db.save_report("task-1", "completed", {"status": "completed"})
    payload = asyncio.run(get_report("task-1"))
    assert payload["task_id"] == "task-1"
    assert payload["status"] == "completed"
    assert payload["report"]["status"] == "completed"
    assert payload["created_at"]


def test_reports_endpoint_raises_for_missing_report():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(get_report("missing-task"))
    assert exc.value.status_code == 404


def test_metrics_endpoints_return_summary_and_task_data():
    db.save_traces(
        "task-metrics",
        [{"timestamp": "2026-01-01T00:00:00+00:00", "step": "task_started"}],
        status="completed",
    )
    db.save_report(
        "task-metrics",
        "completed",
        {
            "status": "completed",
            "risk": "low",
            "duration_ms": 10,
            "verification_status": "passed",
        },
    )
    all_metrics = asyncio.run(list_metrics())
    assert all_metrics["summary"]["total_tasks"] == 1
    assert all_metrics["summary"]["status_counts"]["completed"] == 1
    one_metrics = asyncio.run(get_metrics("task-metrics"))
    assert one_metrics["tasks"][0]["task_id"] == "task-metrics"


def test_metrics_endpoint_raises_for_missing_task():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(get_metrics("missing-task"))
    assert exc.value.status_code == 404
