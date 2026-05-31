from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


DEFAULT_INCIDENT_DESCRIPTION = (
    "restart docker service after invalid Docker config health check failure"
)
DEFAULT_HEALTH_URL = "internal://demo-service/health"
DEFAULT_CONTAINER_NAME = "hr-demo-api"


def build_demo_incident(
    repo_path: Optional[str] = None,
    description: Optional[str] = None,
    health_url: Optional[str] = None,
    container_name: Optional[str] = None,
) -> Dict[str, Any]:
    root = Path(__file__).resolve().parents[1]
    return {
        "title": "Docker service health check failure",
        "description": description or DEFAULT_INCIDENT_DESCRIPTION,
        "repo_path": repo_path or str(root),
        "health_url": health_url or DEFAULT_HEALTH_URL,
        "container_name": container_name or DEFAULT_CONTAINER_NAME,
        "detected_at": datetime.now(timezone.utc).isoformat(),
        "status": "detected",
        "signals": {
            "service": "api",
            "container_status": "unhealthy",
            "health_check": "503 Service Unavailable",
            "suspected_cause": "invalid Docker config",
        },
    }


def synthetic_health_check(
    health_url: Optional[str],
) -> Optional[Dict[str, Any]]:
    if health_url != DEFAULT_HEALTH_URL:
        return None
    return {
        "name": "health_check",
        "target": health_url,
        "status": "passed",
        "returncode": 0,
        "stdout": "200 OK after sandbox remediation",
        "stderr": "",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def synthetic_container_check(
    container_name: Optional[str],
) -> Optional[Dict[str, Any]]:
    if container_name != DEFAULT_CONTAINER_NAME:
        return None
    return {
        "name": "container_status",
        "target": container_name,
        "status": "passed",
        "returncode": 0,
        "stdout": "healthy",
        "stderr": "",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
