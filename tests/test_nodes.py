import importlib.util
import sys
import types
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _load_nodes_package():
    spec = importlib.util.spec_from_file_location(
        "bpg_nodes_under_test", REPO / "nodes" / "__init__.py",
        submodule_search_locations=[str(REPO / "nodes")])
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_collect_merges_modules_and_skips_broken(tmp_path):
    pkg_dir = tmp_path / "fakenodes"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("", encoding="utf-8")
    (pkg_dir / "one.py").write_text(
        "NODE_CLASS_MAPPINGS = {'One': object}\nNODE_DISPLAY_NAME_MAPPINGS = {'One': 'Node one'}\n",
        encoding="utf-8")
    (pkg_dir / "two.py").write_text(
        "NODE_CLASS_MAPPINGS = {'Two': int}\n", encoding="utf-8")
    (pkg_dir / "broken.py").write_text("raise RuntimeError('boom')\n", encoding="utf-8")
    sys.path.insert(0, str(tmp_path))
    try:
        pkg = types.ModuleType("fakenodes")
        pkg.__path__ = [str(pkg_dir)]
        sys.modules["fakenodes"] = pkg
        classes, names = _load_nodes_package().collect("fakenodes", pkg.__path__)
    finally:
        sys.path.remove(str(tmp_path))
        for m in [k for k in sys.modules if k == "fakenodes" or k.startswith("fakenodes.")]:
            del sys.modules[m]
    assert classes == {"One": object, "Two": int}
    assert names == {"One": "Node one"}


def test_real_nodes_package_loads_with_no_nodes_yet():
    mod = _load_nodes_package()
    assert mod.NODE_CLASS_MAPPINGS == {}
    assert mod.NODE_DISPLAY_NAME_MAPPINGS == {}
