"""Structured logging for memory operations.

Each CLI command produces a structured log at .omo/logs/{command}-{id}.log
in the same frontmatter + markdown format as memories.
"""

import uuid
import yaml
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List


@dataclass
class LogEntry:
    id: str
    command: str
    started: str
    trigger: str = ""
    status: str = "running"
    duration_ms: int = 0
    body: str = ""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log_id(command: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    suffix = uuid.uuid4().hex[:6]
    return f"{command}-{ts}-{suffix}"


class LogStore:
    """Structured log store at base_path/logs/."""

    def __init__(self, base_path: Path):
        self.base_path = Path(base_path) / "logs"
        self.base_path.mkdir(parents=True, exist_ok=True)

    def create_log(
        self,
        command: str,
        body: str = "",
        trigger: str = "",
    ) -> LogEntry:
        log = LogEntry(
            id=_log_id(command),
            command=command,
            started=_now(),
            trigger=trigger,
            body=body,
        )
        self._write_log(log)
        return log

    def get_log(self, log_id: str) -> Optional[LogEntry]:
        log_file = self.base_path / f"{log_id}.log"
        if not log_file.exists():
            return None
        return self._parse_log(log_file)

    def update_log(
        self,
        log_id: str,
        status: Optional[str] = None,
        duration_ms: Optional[int] = None,
        body: Optional[str] = None,
    ) -> Optional[LogEntry]:
        log = self.get_log(log_id)
        if log is None:
            return None
        if status is not None:
            log.status = status
        if duration_ms is not None:
            log.duration_ms = duration_ms
        if body is not None:
            log.body = body
        self._write_log(log)
        return log

    def list_logs(self) -> List[LogEntry]:
        logs = []
        for f in sorted(self.base_path.glob("*.log"), reverse=True):
            logs.append(self._parse_log(f))
        return logs

    def _write_log(self, log: LogEntry):
        fm = {
            "command": log.command,
            "started": log.started,
            "trigger": log.trigger,
            "status": log.status,
            "duration_ms": log.duration_ms,
        }
        fm_yaml = yaml.dump(fm, default_flow_style=False, allow_unicode=True).strip()
        lines = [f"---\n{fm_yaml}\n---\n"]
        if log.body:
            lines.append(log.body)
            if not log.body.endswith("\n"):
                lines.append("\n")
        (self.base_path / f"{log.id}.log").write_text("".join(lines))

    def _parse_log(self, path: Path) -> LogEntry:
        text = path.read_text()
        if not text.startswith("---\n"):
            return LogEntry(id=path.stem, command="unknown", started="", body=text)
        parts = text.split("---\n", 2)
        try:
            fm = yaml.safe_load(parts[1]) or {}
        except yaml.YAMLError:
            fm = {}
        body = parts[2].strip() if len(parts) >= 3 else ""
        return LogEntry(
            id=path.stem,
            command=fm.get("command", "unknown"),
            started=fm.get("started", ""),
            trigger=fm.get("trigger", ""),
            status=fm.get("status", "running"),
            duration_ms=fm.get("duration_ms", 0),
            body=body,
        )
