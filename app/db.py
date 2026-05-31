import sqlite3
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Any, Dict, List

DB_PATH = Path(__file__).resolve().parents[1] / "runtime.db"


def _conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = _conn()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS traces (
            task_id TEXT PRIMARY KEY,
            traces TEXT,
            status TEXT,
            created_at TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS approvals (
            task_id TEXT PRIMARY KEY,
            approved INTEGER,
            approver TEXT,
            note TEXT,
            requested_at TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS verifications (
            task_id TEXT PRIMARY KEY,
            status TEXT,
            result TEXT,
            executed_at TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS reports (
            task_id TEXT PRIMARY KEY,
            status TEXT,
            report TEXT,
            created_at TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS incidents (
            incident_id TEXT PRIMARY KEY,
            task_id TEXT,
            status TEXT,
            payload TEXT,
            created_at TEXT,
            updated_at TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def save_traces(task_id: str, traces: Any, status: str = "running") -> None:
    conn = _conn()
    cur = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    sql = (
        "INSERT OR REPLACE INTO traces (task_id, traces, "
        "status, created_at) VALUES (?, ?, ?, ?)"
    )
    cur.execute(
        sql,
        (
            task_id,
            json.dumps(traces, default=str),
            status,
            now,
        ),
    )
    conn.commit()
    conn.close()


def get_traces(task_id: Optional[str] = None):
    conn = _conn()
    cur = conn.cursor()
    if task_id:
        cur.execute(
            "SELECT * FROM traces WHERE task_id = ?",
            (task_id,),
        )
        row = cur.fetchone()
        conn.close()
        if not row:
            return None
        return json.loads(row["traces"])
    else:
        cur.execute(
            "SELECT * FROM traces ORDER BY created_at DESC",
        )
        rows = cur.fetchall()
        conn.close()
        return [
            {
                "task_id": r["task_id"],
                "traces": json.loads(r["traces"]),
                "status": r["status"],
            }
            for r in rows
        ]


def save_approval(
    task_id: str,
    approved: bool,
    approver: Optional[str] = None,
    note: Optional[str] = None,
) -> None:
    conn = _conn()
    cur = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    sql = (
        "INSERT OR REPLACE INTO approvals (task_id, approved, approver, note, "
        "requested_at) VALUES (?, ?, ?, ?, ?)"
    )
    cur.execute(
        sql,
        (
            task_id,
            int(bool(approved)),
            approver or "",
            note or "",
            now,
        ),
    )
    conn.commit()
    conn.close()


def get_approval(task_id: str):
    conn = _conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM approvals WHERE task_id = ?",
        (task_id,),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "task_id": row["task_id"],
        "approved": bool(row["approved"]),
        "approver": row["approver"],
        "note": row["note"],
        "requested_at": row["requested_at"],
    }


def get_all_approvals():
    conn = _conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM approvals ORDER BY requested_at DESC",
    )
    rows = cur.fetchall()
    conn.close()
    return [
        {
            "task_id": r["task_id"],
            "approved": bool(r["approved"]),
            "approver": r["approver"],
            "note": r["note"],
            "requested_at": r["requested_at"],
        }
        for r in rows
    ]


def save_verification(task_id: str, status: str, result: Any = None) -> None:
    conn = _conn()
    cur = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    sql = (
        "INSERT OR REPLACE INTO verifications (task_id, status, result, "
        "executed_at) VALUES (?, ?, ?, ?)"
    )
    result_json = (
        json.dumps(result, default=str) if result is not None else None
    )
    cur.execute(
        sql,
        (task_id, status, result_json, now),
    )
    conn.commit()
    conn.close()


def get_verification(task_id: str):
    conn = _conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM verifications WHERE task_id = ?",
        (task_id,),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "task_id": row["task_id"],
        "status": row["status"],
        "result": json.loads(row["result"]) if row["result"] else None,
        "executed_at": row["executed_at"],
    }


def save_report(task_id: str, status: str, report: Any) -> None:
    conn = _conn()
    cur = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    sql = (
        "INSERT OR REPLACE INTO reports (task_id, status, report, created_at) "
        "VALUES (?, ?, ?, ?)"
    )
    cur.execute(
        sql,
        (
            task_id,
            status,
            json.dumps(report, default=str),
            now,
        ),
    )
    conn.commit()
    conn.close()


def update_report(task_id: str, status: str, updates: Dict[str, Any]) -> None:
    existing = get_report(task_id)
    report = existing["report"] if existing else {}
    if not isinstance(report, dict):
        report = {"value": report}
    report.update(updates)
    save_report(task_id, status, report)


def get_report(task_id: str):
    conn = _conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM reports WHERE task_id = ?",
        (task_id,),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "task_id": row["task_id"],
        "status": row["status"],
        "report": json.loads(row["report"]) if row["report"] else None,
        "created_at": row["created_at"],
    }


def get_reports():
    conn = _conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM reports ORDER BY created_at DESC",
    )
    rows = cur.fetchall()
    conn.close()
    return [
        {
            "task_id": r["task_id"],
            "status": r["status"],
            "report": json.loads(r["report"]) if r["report"] else None,
            "created_at": r["created_at"],
        }
        for r in rows
    ]


def save_incident(
    incident_id: str,
    payload: Dict[str, Any],
    status: str = "detected",
    task_id: Optional[str] = None,
) -> None:
    conn = _conn()
    cur = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    sql = (
        "INSERT OR REPLACE INTO incidents (incident_id, task_id, status, "
        "payload, created_at, updated_at) VALUES (?, ?, ?, ?, "
        "COALESCE((SELECT created_at FROM incidents "
        "WHERE incident_id = ?), ?), ?)"
    )
    cur.execute(
        sql,
        (
            incident_id,
            task_id,
            status,
            json.dumps(payload, default=str),
            incident_id,
            now,
            now,
        ),
    )
    conn.commit()
    conn.close()


def update_incident(
    incident_id: str,
    status: Optional[str] = None,
    task_id: Optional[str] = None,
    payload_updates: Optional[Dict[str, Any]] = None,
):
    incident = get_incident(incident_id)
    if not incident:
        return None
    payload = incident["payload"]
    if payload_updates:
        payload.update(payload_updates)
    save_incident(
        incident_id,
        payload,
        status=status or incident["status"],
        task_id=task_id if task_id is not None else incident.get("task_id"),
    )
    return get_incident(incident_id)


def get_incident(incident_id: str):
    conn = _conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM incidents WHERE incident_id = ?",
        (incident_id,),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "incident_id": row["incident_id"],
        "task_id": row["task_id"],
        "status": row["status"],
        "payload": json.loads(row["payload"]) if row["payload"] else {},
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def get_incidents():
    conn = _conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM incidents ORDER BY created_at DESC")
    rows = cur.fetchall()
    conn.close()
    return [
        {
            "incident_id": r["incident_id"],
            "task_id": r["task_id"],
            "status": r["status"],
            "payload": json.loads(r["payload"]) if r["payload"] else {},
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
        }
        for r in rows
    ]


def _parse_timestamp(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _step_category(step: Optional[str]) -> str:
    text = str(step or "")
    if "verification" in text:
        return "verification"
    if "approval" in text or "risk" in text or "middleware" in text:
        return "middleware"
    if (
        "tool_call" in text
        or "propose_patch" in text
        or "apply_patch" in text
        or "rollback" in text
    ):
        return "tool_call"
    return "reasoning"


def _stage_metrics(traces: List[Dict[str, Any]]) -> Dict[str, Any]:
    stage_counts = {
        "reasoning": 0,
        "middleware": 0,
        "tool_call": 0,
        "verification": 0,
    }
    stage_latency_ms = {
        "reasoning": 0,
        "middleware": 0,
        "tool_call": 0,
        "verification": 0,
    }
    degraded_signal_count = 0
    approval_transitions = 0
    verification_transitions = 0

    for index, item in enumerate(traces):
        category = _step_category(item.get("step"))
        stage_counts[category] += 1
        detail = str(item.get("detail", "")).lower()
        if "degraded" in detail:
            degraded_signal_count += 1
        if "approval" in str(item.get("step", "")):
            approval_transitions += 1
        if "verification" in str(item.get("step", "")):
            verification_transitions += 1

        prev = traces[index - 1] if index > 0 else None
        prev_ts = _parse_timestamp(prev.get("timestamp")) if prev else None
        current_ts = _parse_timestamp(item.get("timestamp"))
        if prev_ts and current_ts:
            delta = int(max((current_ts - prev_ts).total_seconds() * 1000, 0))
            stage_latency_ms[category] += delta

    started_at = (
        _parse_timestamp(traces[0].get("timestamp")) if traces else None
    )
    finished_at = (
        _parse_timestamp(traces[-1].get("timestamp")) if traces else None
    )
    total_runtime_ms = None
    if started_at and finished_at:
        total_runtime_ms = int(
            max((finished_at - started_at).total_seconds() * 1000, 0)
        )

    return {
        "event_count": len(traces),
        "stage_counts": stage_counts,
        "stage_latency_ms": stage_latency_ms,
        "approval_transitions": approval_transitions,
        "verification_transitions": verification_transitions,
        "degraded_signal_count": degraded_signal_count,
        "trace_runtime_ms": total_runtime_ms,
    }


def get_metrics(task_id: Optional[str] = None) -> Dict[str, Any]:
    conn = _conn()
    cur = conn.cursor()

    if task_id:
        cur.execute("SELECT * FROM traces WHERE task_id = ?", (task_id,))
    else:
        cur.execute("SELECT * FROM traces ORDER BY created_at DESC")
    trace_rows = cur.fetchall()

    report_rows = {}
    if task_id:
        cur.execute("SELECT * FROM reports WHERE task_id = ?", (task_id,))
    else:
        cur.execute("SELECT * FROM reports")
    for row in cur.fetchall():
        report_rows[row["task_id"]] = row

    conn.close()

    tasks: List[Dict[str, Any]] = []
    summary_status_counts: Dict[str, int] = {}
    completed_duration_samples: List[int] = []
    degraded_tasks = 0
    pending_approval = 0
    verification_failed = 0

    for row in trace_rows:
        task_key = row["task_id"]
        traces = json.loads(row["traces"]) if row["traces"] else []
        report_row = report_rows.get(task_key)
        report = {}
        if report_row and report_row["report"]:
            report = json.loads(report_row["report"])

        metrics = _stage_metrics(traces)
        status = row["status"] or report.get("status") or "unknown"
        summary_status_counts[status] = (
            summary_status_counts.get(status, 0) + 1
        )

        duration_ms = report.get("duration_ms")
        if isinstance(duration_ms, int):
            completed_duration_samples.append(duration_ms)

        if bool(report.get("verification_degraded")) or metrics[
            "degraded_signal_count"
        ] > 0:
            degraded_tasks += 1
        if status == "pending_approval":
            pending_approval += 1
        if status == "verification_failed":
            verification_failed += 1

        tasks.append(
            {
                "task_id": task_key,
                "status": status,
                "created_at": row["created_at"],
                "risk": report.get("risk", "unknown"),
                "verification_status": report.get("verification_status"),
                "approval_required": report.get("approval_required"),
                "middleware_decision": report.get("middleware_decision", {}),
                "duration_ms": duration_ms,
                "metrics": metrics,
            }
        )

    avg_duration_ms = None
    if completed_duration_samples:
        avg_duration_ms = int(
            sum(completed_duration_samples) / len(completed_duration_samples)
        )

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_tasks": len(tasks),
            "status_counts": summary_status_counts,
            "pending_approvals": pending_approval,
            "verification_failed": verification_failed,
            "degraded_tasks": degraded_tasks,
            "average_duration_ms": avg_duration_ms,
        },
        "tasks": tasks,
    }

    if task_id and not tasks:
        return {}
    return payload


init_db()
