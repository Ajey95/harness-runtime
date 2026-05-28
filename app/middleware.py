from typing import Any


class ApprovalMiddleware:
    """Simple middleware stub for risk classification and approval.

    This will be extended to include allowlists, risk scoring, and
    approval workflows (human-in-the-loop) in later steps.
    """

    def __init__(self) -> None:
        pass

    def classify_risk(self, task: Any) -> str:
        # Placeholder: always low risk currently
        return "low"

    def require_approval(self, risk: str) -> bool:
        # Only medium/high require approval in future
        return False

    def request_approval(self, task: Any) -> bool:
        # Placeholder: auto-approve
        return True
