import pytest
from aiohttp import web

from booru_bridge.middleware import install

ALLOWED = frozenset({"https://ok.example"})


@web.middleware
async def origin_only_middleware(request, handler):
    origin = request.headers.get("Origin")
    if origin is not None and origin != "http://" + request.headers["Host"]:
        return web.Response(status=403)
    if request.method == "OPTIONS":
        return web.Response()
    return await handler(request)


def make_app(with_original=True):
    app = web.Application(middlewares=[origin_only_middleware] if with_original else [])

    async def ok(request):
        return web.json_response({"ok": True})

    async def missing(request):
        raise web.HTTPNotFound()

    app.router.add_get("/x", ok)
    app.router.add_post("/x", ok)
    app.router.add_get("/missing", missing)
    return app


@pytest.fixture
async def client(aiohttp_client):
    app = make_app()
    assert install(app, ALLOWED) == "ok"
    return await aiohttp_client(app)


async def test_allowed_origin_get_post_options(client):
    h = {"Origin": "https://ok.example"}
    for method in ("get", "post", "options"):
        r = await getattr(client, method)("/x", headers=h)
        assert r.status == 200, method
        assert r.headers["Access-Control-Allow-Origin"] == "https://ok.example"
        assert r.headers["Vary"] == "Origin"
        assert r.headers["Access-Control-Allow-Methods"] == "GET, POST, OPTIONS"
        assert r.headers["Access-Control-Allow-Headers"] == "Content-Type"
    assert r.headers["Access-Control-Max-Age"] == "600"


async def test_allowed_origin_text_plain_post(client):
    r = await client.post("/x", data="{}", headers={"Origin": "https://ok.example", "Content-Type": "text/plain"})
    assert r.status == 200


async def test_http_errors_still_get_cors_headers(client):
    r = await client.get("/missing", headers={"Origin": "https://ok.example"})
    assert r.status == 404
    assert r.headers["Access-Control-Allow-Origin"] == "https://ok.example"


@pytest.mark.parametrize("origin", [
    "https://evil.example", "https://OK.example", "https://ok.example/", "null", "https://ok.example:8443",
    "http://ok.example",
])
async def test_other_origin_blocked(client, origin):
    for method in ("get", "post", "options"):
        r = await getattr(client, method)("/x", headers={"Origin": origin})
        assert r.status == 403, (method, origin)
        assert "Access-Control-Allow-Origin" not in r.headers


async def test_no_origin_passes(client):
    r = await client.get("/x")
    assert r.status == 200
    assert "Access-Control-Allow-Origin" not in r.headers


async def test_same_origin_still_handled_by_original(client):
    host = f"{client.host}:{client.port}"
    r = await client.get("/x", headers={"Origin": "http://" + host})
    assert r.status == 200


def test_install_results():
    app = make_app()
    assert install(app, ALLOWED) == "ok"
    assert install(app, ALLOWED) == "already"
    assert len(app.middlewares) == 1
    assert install(make_app(with_original=False), ALLOWED) == "missing"


def test_install_frozen_app_does_not_raise():
    class Frozen(list):
        def __setitem__(self, *a):
            raise RuntimeError("frozen")

    class FakeApp:
        middlewares = Frozen([origin_only_middleware])

    assert install(FakeApp(), ALLOWED) == "missing"
