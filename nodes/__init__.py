"""Collects the nodes of this pack.

To add a node, create one file in this folder (for example `my_node.py`) that defines
the node class and its own `NODE_CLASS_MAPPINGS` and `NODE_DISPLAY_NAME_MAPPINGS`
dicts. Nothing else needs to change: every `nodes/*.py` file is imported and its
mappings are merged. A file that fails to import is logged and skipped, so one broken
node never takes the pack down.
"""
import importlib
import logging
import pkgutil

log = logging.getLogger("booru_prompt_gallery")


def collect(package_name, package_path):
    """Import every module of the package and merge their node mappings."""
    classes, names = {}, {}
    for info in pkgutil.iter_modules(package_path):
        if info.name.startswith("_"):
            continue
        try:
            module = importlib.import_module(package_name + "." + info.name)
            module_classes = dict(getattr(module, "NODE_CLASS_MAPPINGS", {}))
            module_names = dict(getattr(module, "NODE_DISPLAY_NAME_MAPPINGS", {}))
        except Exception:
            log.exception("Could not load node module %s; skipping it.", info.name)
            continue
        classes.update(module_classes)
        names.update(module_names)
    return classes, names


NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS = collect(__name__, __path__)
