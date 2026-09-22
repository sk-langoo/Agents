"""Tamper-evident JSONL audit trail for local development."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .security import canonical_checksum, redact


class AuditLog:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _last_hash(self) -> str:
        if not self.path.exists() or self.path.stat().st_size == 0:
            return "GENESIS"
        with self.path.open("rb") as audit_file:
            last_line = list(audit_file)[-1]
        return json.loads(last_line)["event_hash"]

    def append(self, event_type: str, request_id: str, actor_id: str, details: dict[str, Any]) -> dict[str, Any]:
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "request_id": request_id,
            "actor_id": actor_id,
            "details": redact(details),
            "previous_hash": self._last_hash(),
        }
        event["event_hash"] = canonical_checksum(event)
        with self.path.open("a", encoding="utf-8") as audit_file:
            audit_file.write(json.dumps(event, separators=(",", ":"), default=str) + "\n")
            audit_file.flush()
            os.fsync(audit_file.fileno())
        return event

    def verify(self) -> bool:
        previous = "GENESIS"
        if not self.path.exists():
            return True
        for line in self.path.read_text(encoding="utf-8").splitlines():
            event = json.loads(line)
            event_hash = event.pop("event_hash")
            if event["previous_hash"] != previous or canonical_checksum(event) != event_hash:
                return False
            previous = event_hash
        return True
