import sys
from pathlib import Path

# Ensure repo root is on sys.path so `import app` works under CI
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.main import health  # noqa: E402
from app.main import app  # noqa: E402


def test_cors_allows_vercel_frontend():
    cors = next(
        middleware
        for middleware in app.user_middleware
        if middleware.cls.__name__ == "CORSMiddleware"
    )
    assert (
        "https://frontend-three-ivory-52.vercel.app"
        in cors.kwargs["allow_origins"]
    )
    assert cors.kwargs["allow_origin_regex"] == r"https://.*\.vercel\.app"


def test_health_endpoint():
    """Verify the `/health` handler returns OK when invoked."""
    import asyncio

    resp = asyncio.run(health())
    assert resp == {"status": "ok"}
