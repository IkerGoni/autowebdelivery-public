"""Tests for packages/shared/artifact_io.py — artifact read/write utilities."""

import json
from pathlib import Path

from packages.shared.artifact_io import read_artifact, write_artifact


class TestWriteArtifact:
    def test_creates_file(self, tmp_path):
        data = {"name": "test"}
        result = write_artifact(data, "out.json", "my-slug", base_dir=tmp_path)
        assert Path(result).exists()

    def test_file_content_is_valid_json(self, tmp_path):
        data = {"key": "value", "num": 42}
        path = write_artifact(data, "out.json", "my-slug", base_dir=tmp_path)
        loaded = json.loads(Path(path).read_text(encoding="utf-8"))
        assert loaded == data

    def test_auto_creates_parent_directories(self, tmp_path):
        deep_dir = tmp_path / "a" / "b" / "c"
        data = {"nested": True}
        path = write_artifact(data, "out.json", "slug", base_dir=deep_dir)
        assert Path(path).exists()
        assert deep_dir.exists()

    def test_returns_absolute_path(self, tmp_path):
        result = write_artifact({"x": 1}, "f.json", "slug", base_dir=tmp_path)
        assert Path(result).is_absolute()


class TestReadArtifact:
    def test_round_trip(self, tmp_path):
        data = {"hello": "world", "num": [1, 2, 3]}
        write_artifact(data, "artifact.json", "slug", base_dir=tmp_path)
        result = read_artifact("artifact.json", "slug", base_dir=tmp_path)
        assert result == data

    def test_missing_file_returns_none(self, tmp_path):
        result = read_artifact("nope.json", "slug", base_dir=tmp_path)
        assert result is None

    def test_invalid_json_returns_none(self, tmp_path):
        slug_dir = tmp_path / "slug"
        slug_dir.mkdir()
        bad_file = slug_dir / "bad.json"
        bad_file.write_text("not valid json {{{", encoding="utf-8")
        result = read_artifact("bad.json", "slug", base_dir=tmp_path)
        assert result is None

    def test_read_from_subdirectory(self, tmp_path):
        data = {"a": 1}
        write_artifact(data, "sub.json", "deep/slug", base_dir=tmp_path)
        result = read_artifact("sub.json", "deep/slug", base_dir=tmp_path)
        assert result == data
