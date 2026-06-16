from app.rules_parse import parse_rule_ir


def test_parses_fenced_json():
    raw = '```json\n{"version": 1, "rules": [], "warnings": []}\n```'
    out = parse_rule_ir(raw)
    assert out["ir"] == {"version": 1, "rules": []}
    assert out["warnings"] == []


def test_bad_json_returns_warning():
    out = parse_rule_ir("not json at all")
    assert out["ir"] == {"version": 1, "rules": []}
    assert out["warnings"] and "phân tích" in out["warnings"][0]["message"].lower()


def test_splits_rules_and_warnings():
    raw = '{"rules": [{"id": "x"}], "warnings": [{"rule_hint": "h", "message": "m"}]}'
    out = parse_rule_ir(raw)
    assert out["ir"]["rules"] == [{"id": "x"}]
    assert out["warnings"][0]["message"] == "m"
