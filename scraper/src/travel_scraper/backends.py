"""Run backend/ (Aayush's data layer) and apps/api (ingestion) CLIs in their own environments.

Each package keeps its own uv environment, so we call them as subprocesses with
`uv run` instead of importing them. `PYTHONUTF8=1` makes them read and write UTF-8 on
Windows too (apps/api's ingest opens files with the platform default encoding).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from travel_scraper.config import REPO_ROOT


class BackendError(Exception):
    pass


@dataclass(frozen=True)
class RunResult:
    returncode: int
    stdout: str
    stderr: str


def uv_executable() -> str:
    found = os.environ.get("SCRAPER_UV") or shutil.which("uv")
    if not found:
        raise BackendError("uv not found on PATH (set SCRAPER_UV to its full path)")
    return found


def run_in(project: Path, *args: str, env: dict[str, str] | None = None) -> RunResult:
    """`uv run python <args>` inside `project` (e.g. backend/ or apps/api)."""
    full_env = {**os.environ, "PYTHONUTF8": "1", **(env or {})}
    full_env.pop("VIRTUAL_ENV", None)  # don't leak this package's venv into theirs
    proc = subprocess.run(
        [uv_executable(), "run", "--quiet", "python", *args],
        cwd=project,
        env=full_env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return RunResult(proc.returncode, proc.stdout, proc.stderr)


def backend_dir() -> Path:
    return REPO_ROOT / "backend"


def api_dir() -> Path:
    return REPO_ROOT / "apps" / "api"


def mock_api_env() -> dict[str, str]:
    """apps/api in mock mode: deterministic embeddings, in-memory vector store."""
    return {"EMBEDDING_PROVIDER": "mock", "VECTOR_STORE_PROVIDER": "memory", "LLM_PROVIDER": "mock"}
