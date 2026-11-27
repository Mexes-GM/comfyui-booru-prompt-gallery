import json
import os

import pytest

from booru_bridge.storage import WorkflowStore, is_valid_id, make_id

API = {"1": {"class_type": "EmptyImage", "inputs": {}}}


def test_id_is_stable_and_safe():
    assert make_id("My Flow!") == make_id("My Flow!")
    assert make_id("My Flow!") != make_id("my flow")  # same slug, different hash
    assert is_valid_id(make_id("My Flow!"))
    assert make_id("My Flow!").startswith("my-flow-")


def test_id_edge_cases():
    long_id = make_id("a" * 500)
    assert len(long_id) <= 89 and is_valid_id(long_id)
    assert is_valid_id(make_id("日本語"))  # empty slug falls back
    assert is_valid_id(make_id("---"))


@pytest.mark.parametrize("bad", ["../x", "a/b", "a\\b", "..", "", "A", "a.json", "-a", "x" * 90, None, 3])
def test_invalid_ids(bad):
    assert not is_valid_id(bad)


def test_save_get_list_overwrite(tmp_path):
    s = WorkflowStore(str(tmp_path))
    assert s.list() == []
    a = s.save("First", {"nodes": []}, API)
    b = s.save("Second", None, API)
    assert s.get(a["id"])["ui"] == {"nodes": []}
    assert s.get(b["id"])["ui"] is None
    again = s.save("First", None, {"2": {"class_type": "X"}})
    assert again["id"] == a["id"]
    assert len(s.list()) == 2
    assert s.get(a["id"])["api"] == {"2": {"class_type": "X"}}
    assert s.list()[0]["id"] == a["id"]  # newest first or equal; overwritten is >= other
    assert not [f for f in os.listdir(s.dir) if f.startswith(".tmp-")]


def test_traversal_rejected(tmp_path):
    s = WorkflowStore(str(tmp_path))
    (tmp_path / "secret.json").write_text("{}")
    assert s.get("../../secret") is None
    assert s.get("..") is None


def test_corrupt_files_skipped(tmp_path):
    s = WorkflowStore(str(tmp_path))
    good = s.save("Good", None, API)
    os.makedirs(s.dir, exist_ok=True)
    with open(os.path.join(s.dir, "broken.json"), "w") as f:
        f.write("{not json")
    with open(os.path.join(s.dir, "wrong-shape.json"), "w") as f:
        json.dump({"id": "x"}, f)
    assert [w["id"] for w in s.list()] == [good["id"]]
    assert s.get("broken") is None
