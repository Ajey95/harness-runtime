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
from app.main import get_report  # noqa: E402
from app.middleware import ApprovalMiddleware  # noqa: E402
from app.runtime import ExecutionRuntime  # noqa: E402


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
