import sys
from pathlib import Path

# Ensure repo root is on sys.path so `import app` works under CI
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.main import health  # noqa: E402


def test_health_endpoint():
    """Verify the `/health` handler returns OK when invoked."""
    import asyncio

    resp = asyncio.run(health())
    assert resp == {"status": "ok"}
