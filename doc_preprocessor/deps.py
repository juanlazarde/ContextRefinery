"""Dependency remediation utilities (opt-in, allowlisted)."""

from __future__ import annotations

from dataclasses import dataclass
import importlib
import subprocess
import sys
import threading
from time import perf_counter

ALLOWLIST_MAP = {
    "fitz": "pymupdf",
    "pymupdf": "pymupdf",
    "markitdown": "markitdown",
    "llmlingua": "llmlingua",
}

TAIL_LIMIT = 2000


@dataclass
class DependencyEvent:
    package: str
    reason: str
    command: str
    package_manager: str
    success: bool
    exit_code: int
    duration_ms: int
    stderr_tail: str
    stdout_tail: str
    installed_version_after: str | None
    retry_attempted: bool
    retry_succeeded: bool

    def to_dict(self) -> dict:
        return {
            "package": self.package,
            "reason": self.reason,
            "command": self.command,
            "package_manager": self.package_manager,
            "success": self.success,
            "exit_code": self.exit_code,
            "duration_ms": self.duration_ms,
            "stderr_tail": self.stderr_tail,
            "stdout_tail": self.stdout_tail,
            "installed_version_after": self.installed_version_after,
            "retry_attempted": self.retry_attempted,
            "retry_succeeded": self.retry_succeeded,
        }


class DependencyRegistry:
    def __init__(self):
        self.lock = threading.Lock()
        self.attempted_packages: set[str] = set()
        self.successful_packages: set[str] = set()
        self.failed_packages: set[str] = set()


GLOBAL_DEP_REGISTRY = DependencyRegistry()


def canonical_package(dep_key: str) -> str | None:
    return ALLOWLIST_MAP.get(dep_key)


def get_installed_version(package: str) -> str | None:
    try:
        mod = importlib.import_module(package)
    except Exception:
        return None
    return getattr(mod, "__version__", None)


def install_package(
    package: str,
    reason: str,
    dry_run: bool,
    registry: DependencyRegistry,
) -> DependencyEvent:
    cmd_parts = [sys.executable, "-m", "pip", "install", package]
    cmd_str = " ".join(cmd_parts)

    with registry.lock:
        if package in registry.successful_packages:
            return DependencyEvent(
                package=package,
                reason=reason,
                command=cmd_str,
                package_manager="pip",
                success=True,
                exit_code=0,
                duration_ms=0,
                stderr_tail="",
                stdout_tail="already installed in this run",
                installed_version_after=get_installed_version(package),
                retry_attempted=False,
                retry_succeeded=False,
            )
        if package in registry.failed_packages:
            return DependencyEvent(
                package=package,
                reason=reason,
                command=cmd_str,
                package_manager="pip",
                success=False,
                exit_code=1,
                duration_ms=0,
                stderr_tail="",
                stdout_tail="previous install attempt failed in this run",
                installed_version_after=get_installed_version(package),
                retry_attempted=False,
                retry_succeeded=False,
            )
        if package in registry.attempted_packages:
            # Another thread already started this install; don't run a duplicate subprocess.
            return DependencyEvent(
                package=package,
                reason=reason,
                command=cmd_str,
                package_manager="pip",
                success=False,
                exit_code=1,
                duration_ms=0,
                stderr_tail="",
                stdout_tail="install already in progress in another thread",
                installed_version_after=get_installed_version(package),
                retry_attempted=False,
                retry_succeeded=False,
            )
        registry.attempted_packages.add(package)

    if dry_run:
        return DependencyEvent(
            package=package,
            reason=reason,
            command=cmd_str,
            package_manager="pip",
            success=False,
            exit_code=0,
            duration_ms=0,
            stderr_tail="",
            stdout_tail="dry-run: would install",
            installed_version_after=get_installed_version(package),
            retry_attempted=False,
            retry_succeeded=False,
        )

    t0 = perf_counter()
    proc = subprocess.run(cmd_parts, capture_output=True, text=True)
    duration_ms = int((perf_counter() - t0) * 1000)
    success = proc.returncode == 0
    if success:
        with registry.lock:
            registry.successful_packages.add(package)
    else:
        with registry.lock:
            registry.failed_packages.add(package)

    return DependencyEvent(
        package=package,
        reason=reason,
        command=cmd_str,
        package_manager="pip",
        success=success,
        exit_code=proc.returncode,
        duration_ms=duration_ms,
        stderr_tail=(proc.stderr or "")[-TAIL_LIMIT:],
        stdout_tail=(proc.stdout or "")[-TAIL_LIMIT:],
        installed_version_after=get_installed_version(package),
        retry_attempted=False,
        retry_succeeded=False,
    )
