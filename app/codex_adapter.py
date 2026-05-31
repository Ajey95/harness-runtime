import asyncio
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, Sequence, List


class CodexAdapter:
    """Constrained adapter for Codex CLI-style subprocess integration."""

    ALLOWED_COMMANDS = {
        "echo Applying patch",
        "git status --short",
        "git diff --stat",
        "codex --version",
    }
    SANDBOX_ROOT = Path(__file__).resolve().parents[1]

    def _validate_cwd(self, cwd: Optional[str]) -> Path:
        sandbox = self.SANDBOX_ROOT.resolve()
        # Treat None or empty as the sandbox root. Allow any path that is
        # the sandbox root or a subpath under it.
        if not cwd:
            return sandbox
        try:
            p = Path(cwd).resolve()
        except Exception:
            raise ValueError(f"invalid path: {cwd}")
        # allow paths that are equal to sandbox or are inside it
        try:
            if p == sandbox or sandbox in p.parents:
                return sandbox
        except Exception:
            pass
        raise ValueError(
            "path '{}' outside sandbox root '{}'".format(
                cwd,
                sandbox,
            )
        )

    @staticmethod
    def _normalize_parts(parts: Sequence[str]) -> List[str]:
        return [p for p in parts if p]

    def _validate_command(self, cmd: str) -> Sequence[str]:
        parts = self._normalize_parts(shlex.split(cmd))
        normalized = " ".join(parts)
        if normalized not in self.ALLOWED_COMMANDS:
            raise ValueError("command not allowlisted")
        binary = parts[0] if parts else ""
        # Allow certain shell builtins like `echo` even when `shutil.which`
        # cannot find an external binary (Windows shells often implement
        # these as builtins). Treat `echo` as a special-case.
        if not binary or (
            shutil.which(binary) is None and binary not in {"echo"}
        ):
            raise ValueError("allowlisted command binary not available")
        return parts

    async def run_analysis(
        self,
        repo_path: str,
        description: str,
    ) -> Dict[str, Any]:
        await asyncio.sleep(0.01)
        safe_cwd = self._validate_cwd(repo_path)
        signals = []
        for cmd in ("git status --short", "git diff --stat"):
            result = await self.run_command(cmd, cwd=str(safe_cwd), timeout=15)
            signals.append(result)

        codex_available = shutil.which("codex") is not None
        codex_probe = None
        if codex_available:
            codex_probe = await self.run_command(
                "codex --version",
                cwd=str(safe_cwd),
                timeout=15,
            )

        return {
            "repo_path": str(safe_cwd),
            "description": description,
            "signals": signals,
            "codex_available": codex_available,
            "codex_probe": codex_probe,
            "degraded_mode": not codex_available,
        }

    async def propose_patch(self, description: str) -> Dict[str, Any]:
        await asyncio.sleep(0.05)
        patch_text = (
            "--- a/file.txt\n"
            "+++ b/file.txt\n"
            "@@ -1 +1 @@\n"
            "-Hello\n"
            "+Hello, fixed\n"
        )
        return {"patch": patch_text}

    async def run_command(
        self,
        cmd: str,
        cwd: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:
        # Validate working directory first so sandbox violations are
        # reported before binary availability errors.
        try:
            safe_cwd = str(self._validate_cwd(cwd))
        except ValueError as exc:
            return {
                "cmd": cmd,
                "returncode": None,
                "stdout": "",
                "stderr": str(exc),
            }
        try:
            argv = self._validate_command(cmd)
        except ValueError as exc:
            return {
                "cmd": cmd,
                "returncode": None,
                "stdout": "",
                "stderr": str(exc),
            }

        def run_sync():
            try:
                # Some platforms (Windows) implement `echo` as a shell
                # builtin without an external binary. If `echo` is requested
                # and not present as an external binary, fall back to
                # invoking via the shell so the builtin works.
                if argv and argv[0] == "echo" and shutil.which("echo") is None:
                    completed = subprocess.run(
                        cmd,
                        shell=True,
                        cwd=safe_cwd,
                        capture_output=True,
                        text=True,
                        timeout=timeout,
                    )
                else:
                    completed = subprocess.run(
                        argv,
                        shell=False,
                        cwd=safe_cwd,
                        capture_output=True,
                        text=True,
                        timeout=timeout,
                    )

                return {
                    "cmd": cmd,
                    "argv": list(argv),
                    "returncode": completed.returncode,
                    "stdout": completed.stdout,
                    "stderr": completed.stderr,
                }
            except subprocess.TimeoutExpired as e:
                return {
                    "cmd": cmd,
                    "returncode": None,
                    "stdout": "",
                    "stderr": f"Timeout: {e}",
                }
            except Exception as e:
                return {
                    "cmd": cmd,
                    "returncode": None,
                    "stdout": "",
                    "stderr": repr(e),
                }

        return await asyncio.to_thread(run_sync)

    async def apply_patch(
        self,
        patch: Dict[str, Any],
        cwd: Optional[str] = None,
    ) -> Dict[str, Any]:
        # Simulate applying a patch via a simple shell command and capture
        # output. This is a placeholder for a real patch apply flow.
        cmd = "echo Applying patch"
        return await self.run_command(cmd, cwd=cwd)


adapter = CodexAdapter()
