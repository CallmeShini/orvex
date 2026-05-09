from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


STRUCTURED_EVENT_SCHEMA_VERSION = "orvex-structured-event-v1"


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def append_structured_event(
    path: Path,
    *,
    event: str,
    job_id: str | None = None,
    **fields: Any,
) -> dict[str, Any]:
    payload = {
        "schema_version": STRUCTURED_EVENT_SCHEMA_VERSION,
        "event": event,
        "timestamp": utc_now(),
    }
    if job_id is not None:
        payload["job_id"] = job_id
    payload.update({key: value for key, value in fields.items() if value is not None})

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")
    return payload


def load_structured_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
