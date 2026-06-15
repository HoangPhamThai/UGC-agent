# app/review_parse.py
import json
import re

_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
_OBJ_RE = re.compile(r"\{.*\}", re.DOTALL)


def parse_buckets(raw: str) -> dict:
    """Extract {"text": [...], "image": [...]} from a model reply, tolerating fences."""
    text = raw.strip()
    m = _FENCE_RE.search(text) or _OBJ_RE.search(text)
    candidate = m.group(1) if (m and m.re is _FENCE_RE) else (m.group(0) if m else text)
    try:
        data = json.loads(candidate)
    except (ValueError, TypeError):
        return {"text": [], "image": []}
    return {
        "text": [str(x) for x in (data.get("text") or [])],
        "image": [str(x) for x in (data.get("image") or [])],
    }
