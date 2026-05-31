from typing import Any, Mapping

from . import db


class ApprovalMiddleware:
    """Policy-driven middleware for risk classification and approvals."""

    def __init__(self) -> None:
        self.policy = {
            "approval_threshold": "medium",
            "medium_risk_score": 2,
            "high_risk_score": 4,
        }
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

    def _extract_text(self, task: Any) -> str:
        if isinstance(task, dict):
            return str(task.get("description", "")).lower()
        return str(task or "").lower()

    def risk_score(self, task: Any) -> int:
        text = self._extract_text(task)
        medium_hits = sum(
            1 for token in self.medium_risk_keywords if token in text
        )
        high_hits = sum(
            1 for token in self.high_risk_keywords if token in text
        )
        return medium_hits + (high_hits * 2)

    def classify_risk(self, task: Any) -> str:
        text = self._extract_text(task)
        if any(token in text for token in self.high_risk_keywords):
            return "high"
        if any(token in text for token in self.medium_risk_keywords):
            return "medium"
        return "low"

    def require_approval(self, risk: str) -> bool:
        threshold = self.policy["approval_threshold"]
        if threshold == "high":
            return risk == "high"
        return risk in {"medium", "high"}

    def request_approval(self, task: Mapping[str, Any]) -> bool:
        task_id = str(task.get("task_id", ""))
        if not task_id:
            return False
        approval = db.get_approval(task_id)
        if not approval:
            return False
        return bool(approval.get("approved"))

    def evaluate_task(self, task: Mapping[str, Any]) -> Mapping[str, Any]:
        task_id = str(task.get("task_id", ""))
        description = task.get("description", "")
        risk = self.classify_risk(description)
        score = self.risk_score(description)
        approval_required = self.require_approval(risk)
        approval_state = db.get_approval(task_id) if task_id else None

        if not approval_required:
            decision = "allowed"
            reason = "risk_below_threshold"
        elif not approval_state:
            decision = "pending_approval"
            reason = "approval_required_missing"
        elif approval_state.get("approved"):
            decision = "allowed"
            reason = "approved_by_operator"
        else:
            decision = "rejected"
            reason = "approval_denied"

        return {
            "task_id": task_id,
            "risk": risk,
            "risk_score": score,
            "approval_required": approval_required,
            "approval_state": approval_state,
            "decision": decision,
            "reason": reason,
        }
