"""Starts one isolated ComfyUI (port 8191, CPU, only this custom node) and talks to it over HTTP.

Set COMFYUI_PATH to a ComfyUI checkout (the folder with main.py) to run these tests; they are
skipped otherwise. The Python that runs ComfyUI is COMFYUI_PYTHON if set, else the checkout's
own .venv, else the interpreter running pytest.
"""
import asyncio
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import aiohttp
import pytest
import pytest_asyncio


def _comfy_dir():
    value = os.environ.get("COMFYUI_PATH", "").strip()
    return Path(value) if value else None


def _comfy_python(comfy_dir):
    value = os.environ.get("COMFYUI_PYTHON", "").strip()
    if value:
        return value
    for candidate in (comfy_dir / ".venv" / "Scripts" / "python.exe", comfy_dir / ".venv" / "bin" / "python"):
        if candidate.exists():
            return str(candidate)
    return sys.executable


COMFY_DIR = _comfy_dir()
PORT = 8191
BASE = f"http://127.0.0.1:{PORT}"
REPO = Path(__file__).resolve().parent.parent

VERCEL = "https://booru-prompt-gallery.vercel.app"
EXTRA = "https://extra.example"
EVIL = "https://evil.example"

PROMPT = {
    "1": {"class_type": "EmptyImage", "inputs": {"width": 64, "height": 64, "batch_size": 1, "color": 0}},
    "2": {"class_type": "PreviewImage", "inputs": {"images": ["1", 0]}},
}

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(COMFY_DIR is None or not (COMFY_DIR / "main.py").exists(),
                       reason="Set COMFYUI_PATH to a ComfyUI folder to run the integration tests"),
]


def _port_in_use():
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", PORT)) == 0


@pytest.fixture(scope="session")
def comfy(tmp_path_factory):
    if _port_in_use():
        pytest.fail(f"Port {PORT} is already in use; refusing to start the isolated ComfyUI.")
    tmp = tmp_path_factory.mktemp("comfy")
    (tmp / "user" / "default").mkdir(parents=True)
    (tmp / "user" / "default" / "booru_bridge.json").write_text(
        json.dumps({"extra_origins": [EXTRA]}), encoding="utf-8")
    (tmp / "extra.yaml").write_text(
        "bridge_tests:\n  custom_nodes: " + REPO.parent.as_posix() + "\n", encoding="utf-8")
    for d in ("temp", "output", "input"):
        (tmp / d).mkdir()
    log_path = tmp / "comfy.log"
    cmd = [
        _comfy_python(COMFY_DIR), "main.py", "--listen", "127.0.0.1", "--port", str(PORT), "--cpu",
        "--disable-all-custom-nodes", "--whitelist-custom-nodes", "comfyui-booru-prompt-gallery",
        "--extra-model-paths-config", str(tmp / "extra.yaml"),
        "--temp-directory", str(tmp / "temp"), "--output-directory", str(tmp / "output"),
        "--input-directory", str(tmp / "input"), "--user-directory", str(tmp / "user"),
        "--database-url", "sqlite:///" + (tmp / "db.sqlite").as_posix(),
    ]
    env = dict(os.environ, CUDA_VISIBLE_DEVICES="-1", HIP_VISIBLE_DEVICES="-1")
    logf = open(log_path, "wb")
    proc = subprocess.Popen(cmd, cwd=str(COMFY_DIR), env=env, stdout=logf, stderr=subprocess.STDOUT)
    try:
        import urllib.request
        deadline = time.time() + 120
        ready = False
        while time.time() < deadline:
            if proc.poll() is not None:
                break
            try:
                with urllib.request.urlopen(BASE + "/system_stats", timeout=2) as r:
                    if r.status == 200:
                        ready = True
                        break
            except Exception:
                time.sleep(1)
        if not ready:
            logf.flush()
            tail = log_path.read_text(errors="replace").splitlines()[-50:]
            print("\n".join(tail), file=sys.stderr)
            pytest.fail("Isolated ComfyUI did not become ready within 120 s")
        yield {"tmp": tmp, "log": log_path}
    finally:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            proc.kill()
        proc.wait(timeout=30)
        logf.close()


@pytest_asyncio.fixture
async def http(comfy):
    async with aiohttp.ClientSession() as s:
        yield s


@pytest.mark.parametrize("origin", [VERCEL, EXTRA])
async def test_allowed_origin_full_flow(comfy, http, origin):
    h = {"Origin": origin}
    client_id = "cid-" + origin.split("//")[1][:5]

    r = await http.options(BASE + "/prompt", headers={**h, "Access-Control-Request-Method": "POST"})
    assert r.status == 200
    assert r.headers["Access-Control-Allow-Origin"] == origin

    async with http.ws_connect(f"{BASE}/ws?clientId={client_id}", headers=h) as ws:
        r = await http.post(BASE + "/prompt", headers={**h, "Content-Type": "text/plain"},
                            data=json.dumps({"prompt": PROMPT, "client_id": client_id}))
        assert r.status == 200, await r.text()
        assert r.headers["Access-Control-Allow-Origin"] == origin
        prompt_id = (await r.json())["prompt_id"]
        assert prompt_id

        seen, image = [], None
        deadline = time.time() + 30
        while time.time() < deadline and "execution_success" not in seen:
            msg = await ws.receive(timeout=max(0.1, deadline - time.time()))
            if msg.type != aiohttp.WSMsgType.TEXT:
                continue
            data = json.loads(msg.data)
            seen.append(data["type"])
            if data["type"] == "executed":
                image = data["data"]["output"]["images"][0]
        assert "executed" in seen and "execution_success" in seen, seen
        assert seen.index("executed") < seen.index("execution_success")

    r = await http.get(BASE + "/view", headers=h,
                       params={"filename": image["filename"], "subfolder": image["subfolder"], "type": image["type"]})
    assert r.status == 200
    assert r.headers["Access-Control-Allow-Origin"] == origin


async def test_evil_origin_blocked(comfy, http):
    h = {"Origin": EVIL}
    r = await http.post(BASE + "/prompt", headers={**h, "Content-Type": "text/plain"},
                        data=json.dumps({"prompt": PROMPT}))
    assert r.status == 403
    r = await http.options(BASE + "/prompt", headers={**h, "Access-Control-Request-Method": "POST"})
    assert r.status == 403
    with pytest.raises(aiohttp.WSServerHandshakeError) as e:
        async with http.ws_connect(f"{BASE}/ws?clientId=x", headers=h):
            pass
    assert e.value.status == 403


async def test_no_origin_unchanged(comfy, http):
    r = await http.get(BASE + "/system_stats")
    assert r.status == 200
    assert "Access-Control-Allow-Origin" not in r.headers


async def test_info(comfy, http):
    r = await http.get(BASE + "/booru_bridge/info", headers={"Origin": VERCEL})
    assert r.status == 200
    d = await r.json()
    assert d["middleware"] == "ok"
    for o in (VERCEL, "https://booru-prompt-gallery.netlify.app", EXTRA):
        assert o in d["origins"]
    assert "http://localhost:3000" not in d["origins"]


async def test_workflows(comfy, http):
    body = {"name": "Integration Flow", "ui": None, "api": PROMPT}
    r = await http.post(BASE + "/booru_bridge/workflows", json=body)
    assert r.status == 200
    saved = await r.json()

    for origin in (VERCEL, EVIL):
        r = await http.post(BASE + "/booru_bridge/workflows", json=body, headers={"Origin": origin})
        assert r.status == 403, origin

    h = {"Origin": VERCEL}
    r = await http.get(BASE + "/booru_bridge/workflows", headers=h)
    assert r.status == 200
    assert r.headers["Access-Control-Allow-Origin"] == VERCEL
    assert saved["id"] in [w["id"] for w in (await r.json())["workflows"]]

    r = await http.get(BASE + "/booru_bridge/workflows/" + saved["id"], headers=h)
    assert r.status == 200
    assert r.headers["Access-Control-Allow-Origin"] == VERCEL
    assert (await r.json())["api"] == PROMPT

    r = await http.get(BASE + "/booru_bridge/workflows/does-not-exist", headers=h)
    assert r.status == 404

    r = await http.post(BASE + "/booru_bridge/workflows", json={"name": "", "api": {}})
    assert r.status == 400


@pytest.mark.parametrize("method,path,kwargs", [
    ("post", "/userdata/booru_bridge%2Fworkflows%2Finjected.json", {"data": "{}"}),
    ("post", "/api/userdata/comfy.settings.json", {"data": "{}"}),
    ("post", "/upload/image", {"data": {"image": b"x"}}),
    ("get", "/settings", {}),
    ("get", "/userdata?dir=workflows", {}),
    ("post", "/free", {"data": "{}"}),
])
async def test_allowed_origin_cannot_reach_other_routes(comfy, http, method, path, kwargs):
    r = await getattr(http, method)(BASE + path, headers={"Origin": VERCEL}, **kwargs)
    assert r.status == 403, (path, r.status)
    assert "Access-Control-Allow-Origin" not in r.headers
    assert not (comfy["tmp"] / "user" / "default" / "booru_bridge" / "workflows" / "injected.json").exists()


async def test_frontend_extension_served(comfy, http):
    r = await http.get(BASE + "/extensions/comfyui-booru-prompt-gallery/booru_bridge.js")
    assert r.status == 200
    assert "javascript" in r.headers["Content-Type"]
    assert "BooruPromptGallery.Publish" in await r.text()
