"""ComfyUI entry point. Must never raise: a failure here only disables that part of the pack."""
import logging

log = logging.getLogger("booru_prompt_gallery")

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
# ComfyUI serves the .js files in this folder as frontend extensions.
WEB_DIRECTORY = "./web"

try:
    from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
except Exception:
    log.exception("Could not load the nodes of comfyui-booru-prompt-gallery; no nodes are available.")

try:
    import folder_paths
    from server import PromptServer

    from .booru_bridge.middleware import install
    from .booru_bridge.origins import build_allowed
    from .booru_bridge.routes import BridgeState, register

    _user_dir = folder_paths.get_user_directory()
    _allowed = build_allowed(_user_dir)
    _status = install(PromptServer.instance.app, _allowed)
    register(PromptServer.instance.routes, BridgeState(_allowed, _status, _user_dir))
except Exception:
    log.exception("comfyui-booru-prompt-gallery could not start the bridge; it is disabled.")

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
