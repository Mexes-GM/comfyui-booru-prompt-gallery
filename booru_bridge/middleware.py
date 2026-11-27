"""Replaces ComfyUI's origin_only_middleware with one that admits exact allowlisted origins.

An allowlisted origin is admitted only on the routes the gallery uses (BRIDGED_ROUTES).
Every other request, including any other route called from an allowlisted origin, goes
through ComfyUI's own check unchanged, which blocks it when it comes from another site.
"""
import logging

from aiohttp import web

log = logging.getLogger("booru_prompt_gallery")

ORIGINAL_NAME = "origin_only_middleware"

# (method, route pattern) pairs an allowlisted origin may call. Patterns are aiohttp's
# canonical route strings; ComfyUI also serves each route under /api, which is accepted.
BRIDGED_ROUTES = frozenset({
    ("GET", "/system_stats"),
    ("GET", "/object_info"),
    ("GET", "/queue"),
    ("GET", "/history/{prompt_id}"),
    ("GET", "/view"),
    ("GET", "/ws"),
    ("GET", "/booru_bridge/info"),
    ("GET", "/booru_bridge/workflows"),
    ("GET", "/booru_bridge/workflows/{id}"),
    ("POST", "/prompt"),
    ("POST", "/queue"),
    ("POST", "/interrupt"),
})

_METHODS = frozenset(method for method, _ in BRIDGED_ROUTES)


def _add_cors(resp, origin):
    resp.headers["Access-Control-Allow-Origin"] = origin
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    resp.headers["Vary"] = "Origin"


def _pattern(match_info):
    """The canonical pattern of the matched route, without the /api prefix, or None."""
    route = getattr(match_info, "route", None)
    resource = getattr(route, "resource", None) if route is not None else None
    canonical = getattr(resource, "canonical", None)
    if not isinstance(canonical, str):
        return None
    if canonical.startswith("/api/"):
        canonical = canonical[4:]
    return canonical


async def is_bridged(request):
    """True when the request (or, for a preflight, the request it announces) hits a bridged route.

    The check uses the route aiohttp resolved, not the raw path, so encoded or
    dot-segment paths cannot reach another handler than the one checked here.
    """
    if request.method == "OPTIONS":
        method = request.headers.get("Access-Control-Request-Method", "").strip().upper()
        if method not in _METHODS:
            return False
        try:
            match_info = await request.app.router.resolve(request.clone(method=method))
        except Exception:
            return False
    else:
        method = request.method
        match_info = request.match_info
    if getattr(match_info, "http_exception", None) is not None:
        return False
    return (method, _pattern(match_info)) in BRIDGED_ROUTES


def make_bridge(original, allowed):
    @web.middleware
    async def bridge(request, handler):
        origin = request.headers.get("Origin")
        if origin is not None and origin in allowed and await is_bridged(request):
            if request.method == "OPTIONS":
                resp = web.Response()
                resp.headers["Access-Control-Max-Age"] = "600"
            else:
                try:
                    resp = await handler(request)
                except web.HTTPException as exc:
                    _add_cors(exc, origin)
                    raise
            _add_cors(resp, origin)
            return resp
        return await original(request, handler)

    bridge._booru_bridge = True
    return bridge


def install(app, allowed):
    """Returns "ok", "already" or "missing"."""
    try:
        middlewares = app.middlewares
        for mw in middlewares:
            if getattr(mw, "_booru_bridge", False):
                return "already"
        for i, mw in enumerate(list(middlewares)):
            if getattr(mw, "__name__", "") == ORIGINAL_NAME:
                middlewares[i] = make_bridge(mw, allowed)
                log.info("Booru Prompt Gallery bridge installed; allowed origins: %s", ", ".join(sorted(allowed)))
                return "ok"
    except Exception as e:  # frozen app, unexpected container type, ...
        log.warning("Could not modify the middleware list (%s: %s); the bridge is not active.",
                    type(e).__name__, e)
        return "missing"
    log.warning("%s not found. ComfyUI may be running with --enable-cors-header, "
                "or its server code changed; the bridge is not active.", ORIGINAL_NAME)
    return "missing"
