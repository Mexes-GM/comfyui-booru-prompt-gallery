"""Workflow files under <user dir>/default/booru_bridge/workflows/<id>.json."""
import hashlib
import json
import logging
import os
import re
import tempfile
import time

log = logging.getLogger("booru_prompt_gallery")

ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,88}$")


def make_id(name):
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:80].strip("-") or "workflow"
    return slug + "-" + hashlib.sha1(name.encode("utf-8")).hexdigest()[:8]


def is_valid_id(wf_id):
    return isinstance(wf_id, str) and ID_RE.match(wf_id) is not None


def _is_record(d):
    return (isinstance(d, dict) and isinstance(d.get("id"), str) and isinstance(d.get("name"), str)
            and isinstance(d.get("updated"), int) and isinstance(d.get("api"), dict))


class WorkflowStore:
    def __init__(self, user_dir):
        self.dir = os.path.join(user_dir, "default", "booru_bridge", "workflows")

    def _path(self, wf_id):
        return os.path.join(self.dir, wf_id + ".json")

    def save(self, name, ui, api):
        wf_id = make_id(name)
        record = {"id": wf_id, "name": name, "updated": int(time.time() * 1000), "ui": ui, "api": api}
        os.makedirs(self.dir, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.dir, prefix=".tmp-", suffix=".part")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(record, f, ensure_ascii=False)
            os.replace(tmp, self._path(wf_id))
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        return {"id": wf_id, "name": name, "updated": record["updated"]}

    def get(self, wf_id):
        if not is_valid_id(wf_id):
            return None
        path = self._path(wf_id)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            return None
        except (OSError, ValueError) as e:
            log.warning("Skipping unreadable workflow file %s: %s", path, e)
            return None
        return data if _is_record(data) else None

    def list(self):
        try:
            names = os.listdir(self.dir)
        except FileNotFoundError:
            return []
        items = []
        for fname in names:
            if not fname.endswith(".json"):
                continue
            data = self.get(fname[:-5])
            if data is None:
                log.warning("Skipping corrupt or invalid workflow file %s", fname)
                continue
            items.append({"id": data["id"], "name": data["name"], "updated": data["updated"]})
        items.sort(key=lambda w: w["updated"], reverse=True)
        return items
