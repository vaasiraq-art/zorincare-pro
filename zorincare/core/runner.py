"""Command execution engine with C.UTF-8 locale normalization, activity logging, and Polkit elevation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
import json
import os
import shutil
import subprocess
import sys


@dataclass
class CmdResult:
    returncode: int
    stdout: str
    stderr: str
    command: list[str]

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    @property
    def combined_output(self) -> str:
        parts = [p.strip() for p in (self.stdout, self.stderr) if p and p.strip()]
        return "\n".join(parts)


class ActivityLogBus:
    """Thread-safe simple event bus for streaming command logs to the UI drawer."""

    def __init__(self) -> None:
        self._entries: list[str] = []
        self._listeners: list[Callable[[str], None]] = []

    def emit(self, message: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{stamp}] {message}"
        self._entries.append(line)
        if len(self._entries) > 500:
            self._entries = self._entries[-500:]
        for cb in list(self._listeners):
            try:
                cb(line)
            except Exception:
                pass

    def subscribe(self, callback: Callable[[str], None]) -> None:
        if callback not in self._listeners:
            self._listeners.append(callback)

    @property
    def entries(self) -> list[str]:
        return list(self._entries)


LOG_BUS = ActivityLogBus()


def which_bin(name: str) -> str | None:
    return shutil.which(name)


def run_cmd(
    args: list[str],
    timeout: int = 90,
    env_extra: dict[str, str] | None = None,
    log: bool = False,
) -> CmdResult:
    """Run a non-privileged command safely with deterministic English locale for parsing."""
    if not args:
        return CmdResult(1, "", "Empty command", [])

    env = os.environ.copy()
    env["LC_ALL"] = "C.UTF-8"
    env["LANG"] = "C.UTF-8"
    if env_extra:
        env.update(env_extra)

    if log:
        LOG_BUS.emit(f"$ {' '.join(args)}")

    try:
        completed = subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env,
        )
        res = CmdResult(
            returncode=completed.returncode,
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
            command=args,
        )
        if log and not res.ok and res.stderr.strip():
            LOG_BUS.emit(f"  ! {res.stderr.strip().splitlines()[0]}")
        return res
    except FileNotFoundError:
        return CmdResult(127, "", f"Command not found: {args[0]}", args)
    except subprocess.TimeoutExpired:
        LOG_BUS.emit(f"  ! Timeout expired ({timeout}s): {' '.join(args)}")
        return CmdResult(124, "", f"Command timed out after {timeout}s", args)
    except Exception as exc:
        return CmdResult(1, "", str(exc), args)


def _locate_root_helper() -> list[str]:
    installed_helper = Path("/usr/lib/zorincare-pro/zorincare-root-helper")
    if installed_helper.exists():
        return [str(installed_helper)]
    local_helper = Path(__file__).resolve().parent / "root_helper.py"
    py_exec = sys.executable or "/usr/bin/python3"
    return [py_exec, str(local_helper)]


def run_privileged(action: str, payload: dict[str, Any] | None = None, timeout: int = 600) -> CmdResult:
    """Execute a whitelisted privileged action via Polkit pkexec root helper."""
    payload_json = json.dumps(payload or {}, ensure_ascii=False)
    LOG_BUS.emit(f"[elevated] {action}")

    if os.name != "posix":
        return CmdResult(
            1,
            "",
            "Privileged Linux operations require running on Zorin OS / Linux.",
            ["pkexec", action],
        )

    helper_cmd = _locate_root_helper() + [action, payload_json]

    if hasattr(os, "geteuid") and os.geteuid() == 0:
        return run_cmd(helper_cmd, timeout=timeout, log=True)

    pkexec_path = which_bin("pkexec")
    if not pkexec_path:
        return CmdResult(127, "", "pkexec (Polkit) is not installed on this system.", ["pkexec"])

    return run_cmd([pkexec_path] + helper_cmd, timeout=timeout, log=True)
