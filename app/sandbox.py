import asyncio
import subprocess
import shutil
from typing import Dict, Any, Optional
from pathlib import Path


async def run_in_docker(cmd: str, repo_path: str, image: str = "python:3.11-slim", timeout: Optional[int] = None) -> Dict[str, Any]:
    """Run a command inside a disposable Docker container mounting the repo.

    Requires `docker` to be available on PATH. Returns a dict with stdout/stderr/returncode.
    """
    if shutil.which("docker") is None:
        return {"ok": False, "error": "docker not available"}

    # Ensure repo_path exists
    path = Path(repo_path)
    if not path.exists():
        return {"ok": False, "error": "repo_path not found"}

    # Build docker run command
    # Mount the repo at /work and run the command via sh -c
    docker_cmd = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{str(path.resolve())}:/work",
        "-w",
        "/work",
        image,
        "sh",
        "-c",
        cmd,
    ]

    def _run():
        try:
            p = subprocess.run(docker_cmd, capture_output=True, text=True, timeout=timeout)
            return {"ok": True, "returncode": p.returncode, "stdout": p.stdout, "stderr": p.stderr}
        except subprocess.TimeoutExpired as e:
            return {"ok": False, "error": f"timeout: {e}"}
        except Exception as e:
            return {"ok": False, "error": repr(e)}

    return await asyncio.to_thread(_run)
