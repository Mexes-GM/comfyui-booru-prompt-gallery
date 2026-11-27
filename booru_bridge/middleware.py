"""Replaces ComfyUI's origin_only_middleware with one that admits exact allowlisted origins."""
import logging

from aiohttp import web

log = logging.getLogger("booru_prompt_gallery")

ORIGINAL_NAME = "origin_only_middleware"


def _add_cors(resp, origin):
    resp.headers["Access-Control-Allow-Origin"] = origin
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    resp.headers["Vary"] = "Origin"


def make_bridge(original, allowed):
    @web.middleware
    async def bridge(request, handler):
        origin = request.headers.get("Origin")
        if origin is not None and origin in allowed:
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
