import sys
from pathlib import Path

from fastapi.testclient import TestClient

# Ensure repo root is on sys.path so `import app` works under CI
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.main import app


client = TestClient(app)


def test_health_endpoint():
    """Verify the `/health` endpoint returns OK."""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
