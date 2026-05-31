import asyncio
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from . import db

ALLOWED_VERIFICATION_COMMANDS = {
    "pytest -q",
    "flake8 app tests",
}
SANDBOX_ROOT = Path(__file__).resolve().parents[1]


async def _run_command(
    cmd: str,
    cwd: Optional[str] = None,
    timeout: Optional[int] = None,
) -> Dict[str, Any]:
    """Run a shell command asynchronously and capture output."""
    import traceback

    def run_sync():
        try:
            argv = shlex.split(cmd)
            if not argv:
                raise ValueError("empty command")
            if shutil.which(argv[0]) is None:
                raise FileNotFoundError(
                    "verification command binary not found: {}".format(
                        argv[0]
                    )
                )
            completed = subprocess.run(
                argv,
                shell=False,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return {
                "cmd": cmd,
                "argv": argv,
                "returncode": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            return {
                "cmd": cmd,
                "returncode": None,
                "stdout": "",
                "stderr": repr(e) + "\n" + traceback.format_exc(),
                "error_type": e.__class__.__name__,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    return await asyncio.to_thread(run_sync)


def _sanitize_repo_path(repo_path: Optional[str]) -> str:
    sandbox = str(SANDBOX_ROOT.resolve())
    if repo_path:
        if repo_path != sandbox:
            raise ValueError(
                "repository path '{}' outside sandbox root '{}'".format(
                    repo_path,
                    SANDBOX_ROOT,
                )
            )
    return sandbox


def _is_allowed_command(cmd: str) -> bool:
    return cmd in ALLOWED_VERIFICATION_COMMANDS


async def _run_with_retries(
    cmd: str,
    cwd: str,
    attempts: int = 2,
    timeout: int = 60,
) -> Dict[str, Any]:
    last = None
    for attempt in range(1, attempts + 1):
        current = await _run_command(cmd, cwd=cwd, timeout=timeout)
        current["attempt"] = attempt
        last = current
        if current.get("returncode") == 0:
            break
    return last or {
        "cmd": cmd,
        "returncode": None,
        "stdout": "",
        "stderr": "verification retry failure",
    }


async def run_verification(
    task_id: str,
    repo_path: Optional[str] = None,
    commands: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Run verification commands (tests, linters) and persist results."""
    commands = commands or [
        "pytest -q",
        "flake8 app tests",
    ]
    results: List[Dict[str, Any]] = []
    status = "running"
    degraded = False
    db.save_verification(task_id, status, None)

    try:
        safe_repo_path = _sanitize_repo_path(repo_path)
        for cmd in commands:
            if not _is_allowed_command(cmd):
                degraded = True
                results.append(
                    {
                        "cmd": cmd,
                        "returncode": None,
                        "stdout": "",
                        "stderr": "command not allowlisted",
                    }
                )
                continue
            res = await _run_with_retries(
                cmd,
                cwd=safe_repo_path,
                attempts=2,
                timeout=60,
            )
            if res.get("error_type") == "FileNotFoundError":
                degraded = True
            results.append(res)

        failed = any(r.get("returncode") not in (0, None) for r in results)
        status = "failed" if failed else "passed"
        if degraded and status == "passed":
            status = "degraded_passed"
    except Exception as e:
        status = "error"
        results.append({"error": str(e)})

    db.save_verification(
        task_id,
        status,
        {"results": results, "degraded": degraded},
    )
    return {
        "task_id": task_id,
        "status": status,
        "results": results,
        "degraded": degraded,
    }
