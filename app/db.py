import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Any

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
    conn.commit()
    conn.close()


def save_traces(task_id: str, traces: Any, status: str = "running") -> None:
    conn = _conn()
    cur = conn.cursor()
    now = datetime.utcnow().isoformat()
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
    now = datetime.utcnow().isoformat()
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
    now = datetime.utcnow().isoformat()
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


init_db()
