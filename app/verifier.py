import asyncio
import shlex
import shutil
import subprocess
import urllib.request
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from . import db
from .incidents import synthetic_container_check, synthetic_health_check

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


async def _run_health_check(health_url: Optional[str]) -> Dict[str, Any]:
    synthetic = synthetic_health_check(health_url)
    if synthetic:
        return synthetic
    if not health_url:
        return {
            "name": "health_check",
            "status": "skipped",
            "stdout": "no health_url provided",
            "stderr": "",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    if not health_url.startswith(("http://", "https://")):
        return {
            "name": "health_check",
            "target": health_url,
            "status": "failed",
            "returncode": 1,
            "stdout": "",
            "stderr": "unsupported health check URL",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _run():
        try:
            with urllib.request.urlopen(health_url, timeout=5) as response:
                body = response.read(256).decode("utf-8", errors="replace")
                code = int(response.status)
            passed = 200 <= code < 300
            return {
                "name": "health_check",
                "target": health_url,
                "status": "passed" if passed else "failed",
                "returncode": 0 if passed else 1,
                "stdout": body,
                "stderr": "",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as exc:
            return {
                "name": "health_check",
                "target": health_url,
                "status": "failed",
                "returncode": 1,
                "stdout": "",
                "stderr": repr(exc),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    return await asyncio.to_thread(_run)


async def _run_container_check(
    container_name: Optional[str],
) -> Dict[str, Any]:
    synthetic = synthetic_container_check(container_name)
    if synthetic:
        return synthetic
    if not container_name:
        return {
            "name": "container_status",
            "status": "skipped",
            "stdout": "no container_name provided",
            "stderr": "",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    docker_bin = shutil.which("docker")
    if docker_bin is None:
        return {
            "name": "container_status",
            "target": container_name,
            "status": "degraded",
            "returncode": None,
            "stdout": "",
            "stderr": "docker not available",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _run():
        status_template = (
            "{{if .State.Health}}"
            "{{.State.Health.Status}}"
            "{{else}}"
            "{{.State.Status}}"
            "{{end}}"
        )
        completed = subprocess.run(
            [
                docker_bin,
                "inspect",
                "--format",
                status_template,
                container_name,
            ],
            shell=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        state = completed.stdout.strip()
        passed = completed.returncode == 0 and state in {"healthy", "running"}
        return {
            "name": "container_status",
            "target": container_name,
            "status": "passed" if passed else "failed",
            "returncode": completed.returncode,
            "stdout": state,
            "stderr": completed.stderr,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    return await asyncio.to_thread(_run)


async def run_verification(
    task_id: str,
    repo_path: Optional[str] = None,
    commands: Optional[List[str]] = None,
    health_url: Optional[str] = None,
    container_name: Optional[str] = None,
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

        health_result = await _run_health_check(health_url)
        container_result = await _run_container_check(container_name)
        results.extend([health_result, container_result])
        if health_result.get("status") == "degraded":
            degraded = True
        if container_result.get("status") == "degraded":
            degraded = True

        failed = any(
            r.get("returncode") not in (0, None)
            or r.get("status") == "failed"
            for r in results
        )
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
