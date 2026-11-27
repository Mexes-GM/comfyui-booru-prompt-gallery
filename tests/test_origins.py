import json

import pytest

from booru_bridge.origins import DEFAULT_ORIGINS, build_allowed, load_extra_origins, normalize_origin


@pytest.mark.parametrize("value,expected", [
    ("https://example.com", "https://example.com"),
    ("HTTPS://Example.COM", "https://example.com"),
    ("http://localhost:3000", "http://localhost:3000"),
    ("https://sub.example.co.uk:8443", "https://sub.example.co.uk:8443"),
    ("http://127.0.0.1:8080", "http://127.0.0.1:8080"),
    ("http://[::1]:3000", "http://[::1]:3000"),
    ("  https://example.com  ", "https://example.com"),
])
def test_valid(value, expected):
    assert normalize_origin(value) == expected


@pytest.mark.parametrize("value", [
    "*", "null", "", "https://", "https://example.com/", "https://example.com/path",
    "https://example.com?x=1", "https://example.com#frag", "https://*.example.com",
    "*.example.com", "ftp://example.com", "example.com", "//example.com",
    "https://example.com:99999", "https://example.com:0", "https://user@example.com",
    "https://exa mple.com", "https://-bad.com", "https://example..com", None, 5, ["https://a.com"],
])
def test_invalid(value):
    assert normalize_origin(value) is None


def _write_config(tmp_path, content):
    d = tmp_path / "default"
    d.mkdir()
    (d / "booru_bridge.json").write_text(content, encoding="utf-8")


def test_missing_file(tmp_path):
    assert load_extra_origins(str(tmp_path)) == []
    assert build_allowed(str(tmp_path)) == frozenset(DEFAULT_ORIGINS)


def test_extra_origins_filtered_and_deduped(tmp_path):
    _write_config(tmp_path, json.dumps({"extra_origins": [
        "https://Extra.example", "https://extra.example", "*", "null", "https://x.com/path", 7]}))
    assert load_extra_origins(str(tmp_path)) == ["https://extra.example"]
    assert "https://extra.example" in build_allowed(str(tmp_path))


@pytest.mark.parametrize("content", ["not json", "[]", '{"extra_origins": "https://a.com"}'])
def test_bad_file_ignored(tmp_path, content):
    _write_config(tmp_path, content)
    assert load_extra_origins(str(tmp_path)) == []
