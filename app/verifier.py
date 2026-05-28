import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
from . import db


async def _run_command(cmd: str, cwd: Optional[str] = None, timeout: Optional[int] = None) -> Dict[str, Any]:
    """Run a shell command asynchronously and capture output."""
    import subprocess, traceback

    def run_sync():
        try:
            completed = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=timeout)
            return {
                "cmd": cmd,
                "returncode": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            return {
                "cmd": cmd,
                "returncode": None,
                "stdout": "",
                "stderr": repr(e) + "\n" + traceback.format_exc(),
                "timestamp": datetime.utcnow().isoformat(),
            }

    return await asyncio.to_thread(run_sync)


async def run_verification(task_id: str, repo_path: Optional[str] = None, commands: Optional[List[str]] = None) -> Dict[str, Any]:
    """Run verification commands (tests, linters) and persist results.

    By default will run `pytest -q` and `flake8` if commands not provided.
    """
    # Use platform-friendly commands. Avoid shell-only constructs like `|| true`.
    commands = commands or ["pytest -q", "flake8 --max-line-length=120"]
    results: List[Dict[str, Any]] = []
    status = "running"
    db.save_verification(task_id, status, None)

    try:
            for cmd in commands:
                res = await _run_command(cmd, cwd=repo_path, timeout=60)
            results.append(res)
        # determine overall status
        failed = any(r["returncode"] != 0 for r in results if r["returncode"] is not None)
        status = "failed" if failed else "passed"
    except Exception as e:
        status = "error"
        results.append({"error": str(e)})

    db.save_verification(task_id, status, results)
    return {"task_id": task_id, "status": status, "results": results}
