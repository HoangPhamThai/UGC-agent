from app.tools import build_tools


class FakeBackend:
    def __init__(self):
        self.calls = []

    async def get_summary(self, key, *, from_=None, to=None, product=None):
        self.calls.append(("get_summary", key, from_, to, product)); return {"total": 1}

    async def get_qc_breakdown(self, key, *, from_=None, to=None, product=None):
        self.calls.append(("get_qc_breakdown", key, from_, to, product)); return {"items": []}

    async def list_creators(self, key, *, q=None, from_=None, to=None, product=None, page=1, limit=20):
        self.calls.append(("list_creators", key, q, from_, to, product, page, limit)); return {"items": [], "total": 0}

    async def list_creator_articles(self, key, *, creator_id, from_=None, to=None, product=None, page=1, limit=20):
        self.calls.append(("list_creator_articles", key, creator_id, from_, to, product, page, limit)); return {"items": [], "total": 0}


def test_build_tools_returns_six_documented_callables():
    tools = build_tools(FakeBackend(), "k1")
    assert len(tools) == 6
    for fn in tools:
        assert callable(fn)
        assert fn.__doc__ and fn.__doc__.strip()


async def test_summary_tool_forwards_key_and_params():
    backend = FakeBackend()
    tools = {fn.__name__: fn for fn in build_tools(backend, "k1")}
    out = await tools["get_statistics_summary"](date_from="2026-05-01", date_to="2026-06-01", product="CL")
    assert out == {"total": 1}
    assert backend.calls == [("get_summary", "k1", "2026-05-01", "2026-06-01", "CL")]


async def test_creator_articles_tool_forwards_creator_id():
    backend = FakeBackend()
    tools = {fn.__name__: fn for fn in build_tools(backend, "k1")}
    await tools["list_creator_articles"](creator_id="u_1", page=2, limit=5)
    assert backend.calls[0] == ("list_creator_articles", "k1", "u_1", None, None, None, 2, 5)


async def test_build_tools_includes_new_statistics_tools():
    from app.tools import build_tools

    class _B:
        async def get_summary(self, *a, **k): return {}
        async def get_qc_breakdown(self, *a, **k): return {}
        async def list_creators(self, *a, **k): return {}
        async def list_creator_articles(self, *a, **k): return {}
        async def list_all_articles(self, *a, **k): return {"ok": "articles"}
        async def list_qc_articles(self, *a, **k): return {"ok": "qc"}

    tools = build_tools(_B(), "k1")
    names = {t.__name__ for t in tools}
    assert {"list_all_articles", "list_qc_articles"} <= names
    by_name = {t.__name__: t for t in tools}
    assert await by_name["list_all_articles"]() == {"ok": "articles"}
    assert await by_name["list_qc_articles"](qc_id="u_qc") == {"ok": "qc"}
