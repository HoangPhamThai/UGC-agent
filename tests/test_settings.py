def test_settings_read_from_env(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://llm/v1")
    monkeypatch.setenv("LLM_API_KEY", "key123")
    monkeypatch.setenv("LLM_MODEL", "m1")
    monkeypatch.setenv("BACKEND_URL", "http://backend:8000")
    monkeypatch.setenv("REQUEST_TIMEOUT", "30")
    from app.settings import Settings
    s = Settings()
    assert s.llm_base_url == "http://llm/v1"
    assert s.llm_api_key == "key123"
    assert s.llm_model == "m1"
    assert s.backend_url == "http://backend:8000"
    assert s.request_timeout == 30.0


def test_settings_defaults():
    from app.settings import Settings
    s = Settings(_env_file=None)
    assert s.request_timeout == 60.0
