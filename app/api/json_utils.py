from __future__ import annotations

import json
import re
from typing import Any


JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)


class JsonExtractionError(ValueError):
    """Raised when a model response cannot be parsed into a JSON object."""


def extract_json_object(raw_text: str) -> dict[str, Any]:
    text = raw_text.strip()
    if not text:
        raise JsonExtractionError("Empty model output.")

    block_match = JSON_BLOCK_RE.search(text)
    candidate = block_match.group(1).strip() if block_match else text

    if not candidate.startswith("{"):
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise JsonExtractionError("No JSON object found in model output.")
        candidate = candidate[start : end + 1]

    try:
        loaded = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise JsonExtractionError(f"Invalid JSON object: {exc}") from exc

    if not isinstance(loaded, dict):
        raise JsonExtractionError("Model output JSON is not an object.")

    return loaded

