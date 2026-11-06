"""Helpers for reading JSON out of model replies."""

from __future__ import annotations

import json
import re


def parse_json_object(text: str) -> dict | None:
    """Parse a JSON object from a model reply, tolerating code fences and extra text."""
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.I)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.S)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return data if isinstance(data, dict) else None
