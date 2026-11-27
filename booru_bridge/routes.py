"""HTTP routes under /booru_bridge. Only aiohttp is imported here."""
import json
import logging

from aiohttp import web

from .storage import WorkflowStore
from .version import __version__

log = logging.getLogger("booru_prompt_gallery")

MAX_BODY = 20 * 1024 * 1024


class BridgeState:
    def __init__(self, allowed, middleware_status, user_dir):
        self.allowed = frozenset(allowed)
        self.middleware_status = middleware_status
        self.store = WorkflowStore(user_dir)


def _err(status, message):
    return web.json_response({"error": message}, status=status)


def is_same_origin_or_absent(request):
    """True when there is no Origin header, or Origin equals this server's own Host."""
    origin = request.headers.get("Origin")
    if origin is None:
        return True
    host = request.headers.get("Host", "").lower()
    if not host:
        return False
    return origin.lower() in ("http://" + host, "https://" + host)


def validate_workflow(body):
    """Returns an error message, or None when the body is valid."""
    if not isinstance(body, dict):
        return "Body must be a JSON object."
    name = body.get("name")
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 120:
        return "name must be a string of 1-120 characters."
    api = body.get("api")
    if not isinstance(api, dict) or not api:
        return "api must be a non-empty object."
    for key, node in api.items():
        if not isinstance(node, dict) or not isinstance(node.get("class_type"), str):
            return "api node %r must be an object with a string class_type." % (key,)
    ui = body.get("ui")
    if ui is not None and not isinstance(ui, dict):
        return "ui must be an object or null."
    return None


def register(routes, state):
    @routes.get("/booru_bridge/info")
    async def info(request):
        return web.json_response({
            "version": __version__,
            "origins": sorted(state.allowed),
            "middleware": state.middleware_status,
        })

    @routes.get("/booru_bridge/workflows")
    async def list_workflows(request):
        return web.json_response({"workflows": state.store.list()})

    @routes.get("/booru_bridge/workflows/{id}")
    async def get_workflow(request):
        rec = state.store.get(request.match_info["id"])
        if rec is None:
            return _err(404, "Workflow not found.")
        return web.json_response({k: rec.get(k) for k in ("id", "name", "updated", "ui", "api")})

    @routes.post("/booru_bridge/workflows")
    async def save_workflow(request):
        # Allowlisted web origins may read but not write: the bridge middleware skips
        # ComfyUI's own origin check for them, so the check lives here.
        if not is_same_origin_or_absent(request):
            return _err(403, "Writing workflows from another origin is not allowed.")
        if request.content_length is not None and request.content_length > MAX_BODY:
            return _err(413, "Body is larger than 20 MB.")
        raw = await request.read()
        if len(raw) > MAX_BODY:
            return _err(413, "Body is larger than 20 MB.")
        try:
            body = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return _err(400, "Body is not valid JSON.")
        problem = validate_workflow(body)
        if problem:
            return _err(400, problem)
        try:
            saved = state.store.save(body["name"].strip(), body.get("ui"), body["api"])
        except OSError as e:
            log.error("Could not save workflow: %s", e)
            return _err(500, "Could not save the workflow.")
        return web.json_response(saved)
