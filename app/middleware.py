from typing import Any

from . import db


class ApprovalMiddleware:
    """Simple middleware stub for risk classification and approval.

    This will be extended to include allowlists, risk scoring, and
    approval workflows (human-in-the-loop) in later steps.
    """

    def __init__(self) -> None:
        self.medium_risk_keywords = {
            "modify",
            "restart",
            "dependency",
            "docker",
            "config",
            "migrate",
        }
        self.high_risk_keywords = {
            "delete",
            "drop",
            "credential",
            "secret",
            "production",
            "shutdown",
        }

    def classify_risk(self, task: Any) -> str:
        text = str(task or "").lower()
        if any(token in text for token in self.high_risk_keywords):
            return "high"
        if any(token in text for token in self.medium_risk_keywords):
            return "medium"
        return "low"

    def require_approval(self, risk: str) -> bool:
        return risk in {"medium", "high"}

    def request_approval(self, task: Any) -> bool:
        task_id = str(task.get("task_id", "")) if isinstance(task, dict) else ""
        if not task_id:
            return False
        approval = db.get_approval(task_id)
        if not approval:
            return False
        return bool(approval.get("approved"))
