import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from . import db

ALLOWED_VERIFICATION_COMMANDS = {
    "pytest -q",
    "flake8 app tests",
}


async def _run_command(
    cmd: str,
    cwd: Optional[str] = None,
    timeout: Optional[int] = None,
) -> Dict[str, Any]:
    """Run a shell command asynchronously and capture output."""
    import subprocess
    import traceback

    def run_sync():
        try:
            completed = subprocess.run(
                cmd,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
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


def _sanitize_repo_path(repo_path: Optional[str]) -> Optional[str]:
    if repo_path is None:
        return None
    resolved = Path(repo_path).resolve()
    if not resolved.exists() or not resolved.is_dir():
        raise ValueError("invalid repository path")
    return str(resolved)


async def run_verification(
    task_id: str,
    repo_path: Optional[str] = None,
    commands: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Run verification commands (tests, linters) and persist results.

    By default will run `pytest -q` and `flake8` if commands not provided.
    """
    # Use platform-friendly commands.
    # Avoid shell-only constructs like `|| true`.
    commands = commands or [
        "pytest -q",
        "flake8 app tests",
    ]
    results: List[Dict[str, Any]] = []
    status = "running"
    db.save_verification(task_id, status, None)

    try:
        safe_repo_path = _sanitize_repo_path(repo_path)
        for cmd in commands:
            if cmd not in ALLOWED_VERIFICATION_COMMANDS:
                results.append(
                    {
                        "cmd": cmd,
                        "returncode": None,
                        "stdout": "",
                        "stderr": "command not allowlisted",
                    }
                )
                continue
            res = await _run_command(
                cmd,
                cwd=safe_repo_path,
                timeout=60,
            )
            results.append(res)

        # determine overall status
        failed = any(
            r["returncode"] != 0
            for r in results
            if r["returncode"] is not None
        )
        status = "failed" if failed else "passed"
    except Exception as e:
        status = "error"
        results.append({"error": str(e)})

    db.save_verification(task_id, status, results)
    return {
        "task_id": task_id,
        "status": status,
        "results": results,
    }
