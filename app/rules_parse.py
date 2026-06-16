# agents/app/rules_parse.py
"""Tolerant parser for the rule-analysis LLM reply. Returns {"ir": {...}, "warnings": [...]}.
Mirrors review_parse: tolerate code fences and surrounding prose."""
import json
import re

_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.DOTALL)
_OBJ_RE = re.compile(r"\{.*\}", re.DOTALL)


def parse_rule_ir(raw: str) -> dict:
    text = (raw or "").strip()
    m = _FENCE_RE.search(text)
    candidate = m.group(1) if m else (_OBJ_RE.search(text).group(0) if _OBJ_RE.search(text) else text)
    try:
        data = json.loads(candidate)
    except (ValueError, TypeError):
        return {"ir": {"version": 1, "rules": []},
                "warnings": [{"rule_hint": "parse",
                              "message": "Không phân tích được kết quả của agent (JSON không hợp lệ)."}]}
    rules = data.get("rules") or []
    warnings = data.get("warnings") or []
    return {"ir": {"version": int(data.get("version", 1)), "rules": rules}, "warnings": warnings}
