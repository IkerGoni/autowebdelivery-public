"""R0-02 (F-02) — slug validation and safe path construction.

Attack corpus: any untrusted value that reaches a run-directory path
(``business_slug``, ``run_id``) must be rejected before it is joined onto a
filesystem path.
"""

from pathlib import Path

import pytest

from packages.pipeline.slug import (
    UnsafeSlugError,
    make_slug,
    make_uuid_slug,
    safe_path,
    validate_slug,
)


class TestValidateSlug:
    @pytest.mark.parametrize(
        "bad",
        [
            "../etc/passwd",
            "..",
            ".",
            "%2e%2e%2f",
            "foo/bar",
            "foo\\bar",
            "foo;bar",
            "foo\x00bar",
            "foo bar",
            "UPPERCASE",
            "café-berlin",
            "％2e",  # unicode homograph of '%2e'
            "日本レストラン",
            "a" * 74,  # one past the 73-char bound
            "",
            None,
            123,
            ["not-a-string"],
        ],
    )
    def test_rejects_unsafe_values(self, bad):
        with pytest.raises(UnsafeSlugError):
            validate_slug(bad)

    @pytest.mark.parametrize(
        "good",
        [
            "unknown",
            "run_1767139200_8f14e45fceea167a5a36dedd4bea2543",
            "test-business",
            "cafe-berlin",
            "04_briefs",
            "05_sites",
            "a" * 73,  # exact bound: make_uuid_slug max output length
            "a-b_c9",
        ],
    )
    def test_accepts_safe_values(self, good):
        assert validate_slug(good) == good

    def test_raises_value_error_not_assert(self):
        # Validation must survive `python -O` — no assert-based checks.
        assert issubclass(UnsafeSlugError, ValueError)


class TestGeneratorCompatibility:
    """Every output of the generators must pass the validator (D2 bound)."""

    @pytest.mark.parametrize(
        "text",
        [
            "Café Berlin",
            "日本のレストラン",
            "Foo/Bar & Baz!!!",
            "A Very Long Business Name " * 10,
            "normal-business",
        ],
    )
    def test_make_slug_output_validates(self, text):
        # Compute once: the empty-slug fallback embeds a fresh uuid per call.
        slug = make_slug(text)
        assert validate_slug(slug) == slug

    @pytest.mark.parametrize(
        "text",
        [
            "Café Berlin",
            "日本のレストラン",
            "x" * 100,  # base truncates to 64, uuid adds 9 → 73 max
        ],
    )
    def test_make_uuid_slug_output_validates(self, text):
        validate_slug(make_uuid_slug(text))


class TestSafePath:
    def test_builds_expected_path(self, tmp_path):
        result = safe_path(tmp_path, "runs", "run_123_abc", "04_briefs", "some-business")
        assert result == tmp_path / "runs" / "run_123_abc" / "04_briefs" / "some-business"

    @pytest.mark.parametrize(
        "part",
        [
            "..",
            "../escape",
            "%2e%2e",
            "foo\\..\\bar",
            "foo\x00bar",
            "foo/bar",
            "％2e",
            "",
        ],
    )
    def test_rejects_unsafe_parts(self, tmp_path, part):
        with pytest.raises(UnsafeSlugError):
            safe_path(tmp_path, "runs", "run_1", part)

    def test_rejects_path_escape_via_symlink(self, tmp_path):
        # A symlink inside the tree pointing outside must not let the
        # resolved path escape the root.
        outside = tmp_path / "outside"
        outside.mkdir()
        inside_root = tmp_path / "workspace"
        (inside_root / "runs").mkdir(parents=True)
        (inside_root / "runs" / "link").symlink_to(outside)
        with pytest.raises(UnsafeSlugError):
            safe_path(inside_root, "runs", "link", "04_briefs")

    def test_accepts_str_root(self, tmp_path):
        result = safe_path(str(tmp_path), "runs", "run_1")
        assert result == Path(tmp_path) / "runs" / "run_1"


class TestArtifactPaths:
    """R0-02: artifact_paths validates directory parts and filenames."""

    def test_artifact_path_rejects_traversal_run_id(self, tmp_path):
        from packages.pipeline.artifact_paths import artifact_path

        with pytest.raises(UnsafeSlugError):
            artifact_path(str(tmp_path), "phase_01", "../escape", "outputs", "file.json")

    def test_artifact_path_rejects_separator_filename(self, tmp_path):
        from packages.pipeline.artifact_paths import artifact_path

        with pytest.raises(ValueError):
            artifact_path(str(tmp_path), "phase_01", "run_1", "outputs", "../file.json")

    def test_artifact_path_builds_normally(self, tmp_path):
        from packages.pipeline.artifact_paths import artifact_path

        result = artifact_path(str(tmp_path), "phase_01", "run_1", "outputs", "file.json")
        # The artifact directory is created; the file itself is not.
        assert Path(result).parent.exists()
        assert Path(result).name == "file.json"


class TestPhase05TraversalGuard:
    """The F-02 evidence sites must reject traversal before touching disk."""

    def test_slug_to_brief_dir_rejects_traversal(self, tmp_path):
        from packages.phases.phase_05_preview_site_generation import _slug_to_brief_dir

        with pytest.raises(UnsafeSlugError):
            _slug_to_brief_dir(tmp_path, "run_1", "../../etc")

    def test_lead_slug_rejects_traversal(self):
        from packages.pipeline.vnext_integration import _lead_slug

        with pytest.raises(UnsafeSlugError):
            _lead_slug({"business_slug": "../../etc/passwd"})

    def test_lead_slug_accepts_unknown_default(self):
        from packages.pipeline.vnext_integration import _lead_slug

        assert _lead_slug({}) == "unknown"


class TestPhase03OriginNormalization:
    """Incoming discovery slugs are normalized before entering scored output."""

    def test_traversal_slug_normalized(self):
        from packages.phases.phase_03_lead_scoring import score_lead

        lead = {
            "record_id": "r1",
            "business_name": "Evil Corp",
            "business_slug": "../../../etc/passwd",
            "rating": 4.8,
            "review_count": 100,
        }
        scored = score_lead(lead, {}, run_id="run_1")
        assert scored["business_slug"] == "etc-passwd"

    def test_valid_slug_unchanged(self):
        from packages.phases.phase_03_lead_scoring import score_lead

        lead = {
            "record_id": "r1",
            "business_name": "Good Corp",
            "business_slug": "good-corp",
            "rating": 4.8,
            "review_count": 100,
        }
        scored = score_lead(lead, {}, run_id="run_1")
        assert scored["business_slug"] == "good-corp"

    def test_empty_slug_stays_empty_legacy(self):
        from packages.phases.phase_03_lead_scoring import score_lead

        lead = {
            "record_id": "r1",
            "business_name": "No Slug Corp",
            "rating": 4.8,
            "review_count": 100,
        }
        scored = score_lead(lead, {}, run_id="run_1")
        assert scored["business_slug"] == ""
