import pytest
from aiohttp import web

from booru_bridge.routes import BridgeState, register

API = {"1": {"class_type": "EmptyImage", "inputs": {}}}


@pytest.fixture
async def client(aiohttp_client, tmp_path):
    routes = web.RouteTableDef()
    register(routes, BridgeState(["https://ok.example"], "ok", str(tmp_path)))
    app = web.Application()
    app.add_routes(routes)
    return await aiohttp_client(app)


async def test_info(client):
    d = await (await client.get("/booru_bridge/info")).json()
    assert d["middleware"] == "ok" and d["origins"] == ["https://ok.example"] and d["version"]


async def test_roundtrip_and_validation(client):
    r = await client.post("/booru_bridge/workflows", json={"name": " Hi ", "ui": None, "api": API})
    assert r.status == 200
    saved = await r.json()
    got = await (await client.get("/booru_bridge/workflows/" + saved["id"])).json()
    assert got["name"] == "Hi" and got["api"] == API and got["ui"] is None
    assert (await (await client.get("/booru_bridge/workflows")).json())["workflows"][0]["id"] == saved["id"]
    assert (await client.get("/booru_bridge/workflows/nope")).status == 404
    assert (await client.get("/booru_bridge/workflows/..%2f..%2fx")).status == 404
    for bad in ({}, {"name": "", "api": API}, {"name": "x" * 121, "api": API}, {"name": "a", "api": {}},
                {"name": "a", "api": {"1": {"inputs": {}}}}, {"name": "a", "api": API, "ui": []},
                {"name": "a", "api": {"1": 5}}):
        r = await client.post("/booru_bridge/workflows", json=bad)
        assert r.status == 400 and "error" in await r.json(), bad
    r = await client.post("/booru_bridge/workflows", data="not json")
    assert r.status == 400


async def test_oversize_rejected(client):
    r = await client.post("/booru_bridge/workflows", data=b"x" * (20 * 1024 * 1024 + 1))
    assert r.status == 413


async def test_write_protection(client):
    body = {"name": "a", "api": API}
    host = f"{client.host}:{client.port}"
    assert (await client.post("/booru_bridge/workflows", json=body, headers={"Origin": "https://ok.example"})).status == 403
    assert (await client.post("/booru_bridge/workflows", json=body, headers={"Origin": "https://evil.example"})).status == 403
    assert (await client.post("/booru_bridge/workflows", json=body, headers={"Origin": "http://" + host})).status == 200
