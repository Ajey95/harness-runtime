import sys
from pathlib import Path

# Ensure repo root is on sys.path so `import app` works under CI
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.main import health  # noqa: E402
from app.main import app  # noqa: E402


def test_cors_allows_vercel_frontend():
    from fastapi.testclient import TestClient

    client = TestClient(app)
    resp = client.options(
        "/reports",
        headers={
            "Origin": "https://frontend-three-ivory-52.vercel.app",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code == 200
    assert (
        resp.headers["access-control-allow-origin"]
        == "https://frontend-three-ivory-52.vercel.app"
    )


def test_health_endpoint():
    """Verify the `/health` handler returns OK when invoked."""
    import asyncio

    resp = asyncio.run(health())
    assert resp == {"status": "ok"}
