import asyncio
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import db  # noqa: E402
from app.codex_adapter import adapter  # noqa: E402
from app.main import list_metrics, list_traces  # noqa: E402
from app.middleware import ApprovalMiddleware  # noqa: E402
from app import runtime as runtime_module  # noqa: E402
from app.runtime import ExecutionRuntime  # noqa: E402
from app.verifier import run_verification  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "runtime.db")
    db.init_db()
    yield


@pytest.fixture(autouse=True)
def stub_runtime_verification(monkeypatch):
    async def fake_verification(task_id, repo_path=None):
        return {
            "task_id": task_id,
            "status": "passed",
            "results": [],
            "degraded": False,
        }

    monkeypatch.setattr(runtime_module, "run_verification", fake_verification)


def _run_low_risk_task(task_id: str = "acceptance-low"):
    runtime = ExecutionRuntime()
    return asyncio.run(
        runtime.start_task(
            "update docs only",
            repo_path=str(ROOT),
            task_id=task_id,
        )
    )


def test_acceptance_matrix_file_is_complete():
    matrix_path = ROOT / "acceptance_matrix.json"
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    ids = [item["id"] for item in matrix["requirements"]]
    assert ids == [
        "FR-1",
        "FR-2",
        "FR-3",
        "FR-4",
        "FR-5",
        "FR-6",
        "FR-7",
        "FR-8",
        "FR-9",
        "FR-10",
    ]
    assert all("automated_check" in item for item in matrix["requirements"])


def test_fr1_triggers_task_runtime():
    result = _run_low_risk_task(task_id="fr1-trigger")
    assert result.task_id == "fr1-trigger"
    assert result.status in {"completed", "verification_failed"}


def test_fr2_captures_tool_call_trace():
    _run_low_risk_task(task_id="fr2-tools")
    traces = db.get_traces("fr2-tools")
    assert traces is not None
    assert any(t["step"] == "tool_call" for t in traces)


def test_fr3_records_execution_workflow_trace():
    _run_low_risk_task(task_id="fr3-trace")
    traces = db.get_traces("fr3-trace")
    steps = [t["step"] for t in traces]
    assert "task_started" in steps
    assert "analysis" in steps
    assert "risk_classified" in steps
    assert "verification_result" in steps


def test_fr4_classifies_execution_risk():
    middleware = ApprovalMiddleware()
    assert middleware.classify_risk("update docs only") == "low"
    assert middleware.classify_risk("restart docker service") == "medium"
    assert middleware.classify_risk("delete production secret") == "high"


def test_fr5_requires_approval_for_medium_risk():
    middleware = ApprovalMiddleware()
    decision = middleware.evaluate_task(
        {"task_id": "fr5-approval", "description": "restart docker service"}
    )
    assert decision["risk"] == "medium"
    assert decision["approval_required"] is True
    assert decision["decision"] == "pending_approval"


def test_fr6_runs_verification_pipeline():
    result = asyncio.run(
        run_verification(
            task_id="fr6-verification",
            repo_path=str(ROOT),
            commands=["flake8 app tests"],
        )
    )
    assert result["status"] in {"passed", "failed", "degraded_passed"}
    saved = db.get_verification("fr6-verification")
    assert saved is not None
    assert saved["status"] == result["status"]


def test_fr7_exposes_reasoning_trace_api():
    _run_low_risk_task(task_id="fr7-visual")
    payload = asyncio.run(list_traces())
    assert isinstance(payload, list)
    assert any(item["task_id"] == "fr7-visual" for item in payload)


def test_fr8_persists_execution_report():
    _run_low_risk_task(task_id="fr8-report")
    report = db.get_report("fr8-report")
    assert report is not None
    assert report["report"]["status"] in {"completed", "verification_failed"}
    assert report["report"]["duration_ms"] >= 0


def test_fr9_enforces_sandbox_execution(tmp_path):
    result = asyncio.run(
        adapter.run_command("echo Applying patch", cwd=str(tmp_path))
    )
    assert result["returncode"] is None
    assert "outside sandbox root" in result["stderr"]


def test_fr10_exposes_monitoring_metrics():
    _run_low_risk_task(task_id="fr10-monitor")
    payload = asyncio.run(list_metrics())
    assert payload["summary"]["total_tasks"] >= 1
    assert "status_counts" in payload["summary"]
    assert any(item["task_id"] == "fr10-monitor" for item in payload["tasks"])
