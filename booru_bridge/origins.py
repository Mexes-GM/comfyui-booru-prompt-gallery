"""Allowed web origins: built-in defaults plus an optional user JSON file."""
import json
import logging
import os
import re

log = logging.getLogger("booru_prompt_gallery")

DEFAULT_ORIGINS = (
    "https://booru-prompt-gallery.vercel.app",
    "https://booru-prompt-gallery.netlify.app",
)

CONFIG_NAME = "booru_bridge.json"

_LABEL = r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?"
_HOST = _LABEL + r"(?:\." + _LABEL + r")*"
_IPV6 = r"\[[0-9a-f:]+\]"
_ORIGIN_RE = re.compile(
    r"^(https?)://(" + _HOST + "|" + _IPV6 + r")(:[0-9]{1,5})?$", re.IGNORECASE
)


def normalize_origin(value):
    """Return the canonical origin, or None if `value` is not a plain scheme://host[:port]."""
    if not isinstance(value, str):
        return None
    m = _ORIGIN_RE.match(value.strip())
    if not m:
        return None
    scheme, host, port = m.group(1), m.group(2), m.group(3) or ""
    if port and not 0 < int(port[1:]) <= 65535:
        return None
    return scheme.lower() + "://" + host.lower() + port


def config_path(user_dir):
    return os.path.join(user_dir, "default", CONFIG_NAME)


def load_extra_origins(user_dir):
    path = config_path(user_dir)
    if not os.path.isfile(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        log.warning("Could not read %s: %s", path, e)
        return []
    raw = data.get("extra_origins", []) if isinstance(data, dict) else None
    if not isinstance(raw, list):
        log.warning('%s: expected {"extra_origins": [...]}; ignoring the file', path)
        return []
    out = []
    for entry in raw:
        norm = normalize_origin(entry)
        if norm is None:
            log.warning("%s: skipping invalid origin %r (use scheme://host[:port])", path, entry)
        elif norm not in out:
            out.append(norm)
    return out


def build_allowed(user_dir):
    allowed = set(DEFAULT_ORIGINS)
    if user_dir:
        allowed.update(load_extra_origins(user_dir))
    return frozenset(allowed)
