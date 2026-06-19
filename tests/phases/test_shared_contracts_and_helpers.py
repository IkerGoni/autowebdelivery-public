"""Tests for shared contracts and helpers per pipeline_data_contract.md."""

import tempfile
from pathlib import Path

from pipeline.contracts import RunMeta, utc_now
from pipeline.result_envelope import ResultEnvelope, Status
from pipeline.artifact_paths import artifact_path, input_path, output_path, cache_path
from pipeline.json_io import read_json, write_json, write_result
from pipeline.slug import make_slug, make_uuid_slug


class TestRunMeta:
    def test_run_meta_defaults(self):
        meta = RunMeta(run_id="test-123")
        assert meta.run_id == "test-123"
        assert meta.phase is None
        assert meta.status == "pending"
        assert meta.created_at is not None

    def test_run_meta_timestamp(self):
        before = utc_now()
        meta = RunMeta(run_id="test-456")
        after = utc_now()
        assert before <= meta.created_at <= after


class TestResultEnvelope:
    def test_done_factory(self):
        env = ResultEnvelope.done(
            phase="phase_01",
            run_id="run-abc",
            inputs_used=["file1.json"],
            outputs_created=["output.json"],
        )
        assert env.phase == "phase_01"
        assert env.status == Status.DONE
        assert env.inputs_used == ["file1.json"]
        assert env.outputs_created == ["output.json"]

    def test_blocked_factory_missing_fields(self):
        env = ResultEnvelope.blocked(
            phase="phase_02",
            run_id="run-def",
            missing_fields=["url", "token"],
        )
        assert env.status == Status.BLOCKED
        assert "url" in env.missing_fields
        assert any("url" in e for e in env.errors)

    def test_failed_factory(self):
        env = ResultEnvelope.failed(
            phase="phase_03",
            run_id="run-ghi",
            errors=["connection timeout"],
        )
        assert env.status == Status.FAILED
        assert env.errors == ["connection timeout"]

    def test_to_dict(self):
        env = ResultEnvelope.done(phase="test_phase")
        d = env.to_dict()
        assert d["phase"] == "test_phase"
        assert d["status"] == "done"


class TestArtifactPaths:
    def test_artifact_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = artifact_path(
                workspace=tmp,
                phase="phase_01",
                run_id="run-1",
                artifact_type="inputs",
                filename="data.json",
            )
            assert path.endswith("inputs/data.json")
            assert Path(path).parent.exists()

    def test_input_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = input_path(tmp, "phase_01", "run-1", "in.json")
            assert path.endswith("inputs/in.json")

    def test_output_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = output_path(tmp, "phase_01", "run-1", "out.json")
            assert path.endswith("outputs/out.json")

    def test_cache_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = cache_path(tmp, "phase_01", "run-1", "cache.json")
            assert path.endswith("cache/cache.json")


class TestJsonIo:
    def test_write_and_read_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = f"{tmp}/test.json"
            data = {"key": "value", "num": 42}
            result_path = write_json(path, data)
            assert Path(result_path).exists()
            loaded = read_json(result_path)
            assert loaded == data

    def test_write_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = ResultEnvelope.done(phase="test").to_dict()
            path = write_result(f"{tmp}/result.json", result)
            loaded = read_json(path)
            assert loaded["phase"] == "test"


class TestSlug:
    def test_make_slug_simple(self):
        assert make_slug("Hello World") == "hello-world"
        assert make_slug("Test 123") == "test-123"

    def test_make_slug_special_chars(self):
        assert make_slug("Hello!@#$%World") == "hello-world"

    def test_make_slug_truncates(self):
        long = "a" * 100
        assert len(make_slug(long)) == 64

    def test_make_slug_empty_fallback(self):
        slug = make_slug("")
        assert len(slug) > 0

    def test_make_uuid_slug(self):
        slug = make_uuid_slug("Test")
        assert slug.startswith("test-")
        assert len(slug.split("-")[-1]) == 8