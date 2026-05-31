import sys
import asyncio
from pathlib import Path

# ensure repo root on path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.codex_adapter import adapter

res = asyncio.run(adapter.run_command('echo Applying patch', cwd=str(ROOT)))
print(res)
