from app.prompts import render_system_prompt


def test_render_injects_date_and_states_scope():
    text = render_system_prompt("2026-06-13")
    assert "2026-06-13" in text
    lower = text.lower()
    assert "creator" in lower and "qc" in lower and "article" in lower and "product" in lower
    assert "tool" in lower
    assert "user's language" in lower or "user language" in lower
    assert "decline" in lower or "cannot" in lower or "only" in lower


def test_render_is_idempotent_for_same_date():
    assert render_system_prompt("2026-01-01") == render_system_prompt("2026-01-01")
