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

    # Bridged routes, registered with and without /api as ComfyUI does.
    for prefix in ("", "/api"):
        app.router.add_get(prefix + "/system_stats", ok)
        app.router.add_get(prefix + "/history/{prompt_id}", ok)
        app.router.add_post(prefix + "/prompt", ok)
        app.router.add_get(prefix + "/booru_bridge/workflows/{id}", missing)
        # Not bridged.
        app.router.add_post(prefix + "/userdata/{file}", ok)
        app.router.add_post(prefix + "/upload/image", ok)
        app.router.add_get(prefix + "/settings", ok)
        app.router.add_post(prefix + "/booru_bridge/workflows", ok)
    return app


@pytest.fixture
async def client(aiohttp_client):
    app = make_app()
    assert install(app, ALLOWED) == "ok"
    return await aiohttp_client(app)


OK = {"Origin": "https://ok.example"}


@pytest.mark.parametrize("prefix", ["", "/api"])
async def test_allowed_origin_on_bridged_routes(client, prefix):
    cases = [("get", "/system_stats", None), ("get", "/history/abc", None), ("post", "/prompt", None),
             ("options", "/prompt", "POST"), ("options", "/system_stats", "GET")]
    for method, path, preflight in cases:
        h = dict(OK)
        if preflight:
            h["Access-Control-Request-Method"] = preflight
        r = await getattr(client, method)(prefix + path, headers=h)
        assert r.status == 200, (method, path)
        assert r.headers["Access-Control-Allow-Origin"] == "https://ok.example"
        assert r.headers["Vary"] == "Origin"
        assert r.headers["Access-Control-Allow-Methods"] == "GET, POST, OPTIONS"
        assert r.headers["Access-Control-Allow-Headers"] == "Content-Type"
        if method == "options":
            assert r.headers["Access-Control-Max-Age"] == "600"


async def test_allowed_origin_text_plain_post(client):
    r = await client.post("/prompt", data="{}", headers={**OK, "Content-Type": "text/plain"})
    assert r.status == 200


async def test_http_errors_still_get_cors_headers(client):
    r = await client.get("/booru_bridge/workflows/nope", headers=OK)
    assert r.status == 404
    assert r.headers["Access-Control-Allow-Origin"] == "https://ok.example"


@pytest.mark.parametrize("method,path,preflight", [
    ("post", "/userdata/comfy.settings.json", None),
    ("post", "/api/userdata/booru_bridge%2Fworkflows%2Fx.json", None),
    ("post", "/upload/image", None),
    ("get", "/settings", None),
    ("post", "/booru_bridge/workflows", None),
    ("get", "/prompt", None),             # wrong method for a bridged path
    ("post", "/system_stats", None),
    ("get", "/unknown", None),
    ("options", "/userdata/x", "POST"),
    ("options", "/prompt", "DELETE"),
    ("options", "/prompt", None),
    ("options", "/system_stats", "POST"),
])
async def test_allowed_origin_on_other_routes_goes_to_original(client, method, path, preflight):
    h = dict(OK)
    if preflight:
        h["Access-Control-Request-Method"] = preflight
    r = await getattr(client, method)(path, headers=h)
    assert r.status == 403, (method, path, preflight)
    assert "Access-Control-Allow-Origin" not in r.headers


async def test_dot_segments_do_not_reach_other_routes(client):
    # yarl removes dot segments before routing, so this resolves to /userdata/x.
    r = await client.post("/history/../userdata/x", headers=OK)
    assert r.status == 403
    assert "Access-Control-Allow-Origin" not in r.headers


@pytest.mark.parametrize("origin", [
    "https://evil.example", "https://OK.example", "https://ok.example/", "null", "https://ok.example:8443",
    "http://ok.example",
])
async def test_other_origin_blocked(client, origin):
    for method, path in (("get", "/system_stats"), ("post", "/prompt"), ("options", "/prompt")):
        h = {"Origin": origin, "Access-Control-Request-Method": "POST"}
        r = await getattr(client, method)(path, headers=h)
        assert r.status == 403, (method, origin)
        assert "Access-Control-Allow-Origin" not in r.headers


async def test_no_origin_passes(client):
    for method, path in (("get", "/system_stats"), ("post", "/userdata/x")):
        r = await getattr(client, method)(path)
        assert r.status == 200
        assert "Access-Control-Allow-Origin" not in r.headers


async def test_same_origin_still_handled_by_original(client):
    host = f"{client.host}:{client.port}"
    for method, path in (("get", "/system_stats"), ("post", "/userdata/x")):
        r = await getattr(client, method)(path, headers={"Origin": "http://" + host})
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
