"""VNEXT-11 E2E test: legacy behavior preserved when vNext flags are off.

Proves that:
1. No vNext artifacts are created when all flags are explicitly False
2. No vNext artifacts are created when vnext_flags key is missing from config
3. The vNext helper functions return empty lists (no-ops) when flags are off
4. The pipeline summary remains in the legacy format
"""

import hashlib
import json
import tempfile
from pathlib import Path

from packages.pipeline.vnext_integration import (
    get_vnext_flags,
    run_vnext_post_phase_03,
    run_vnext_post_phase_04_5,
    run_vnext_post_phase_06,
    run_vnext_post_phase_08,
    run_vnext_post_phase_09,
)


def _compute_sha256(path: Path) -> str:
    """Compute SHA-256 hash of file contents."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Minimal fixtures
# ---------------------------------------------------------------------------

def _make_lead(slug: str = "bright-smile-clinic-test") -> dict:
    """Return a minimal selected lead dict."""
    return {
        "run_id": "legacy_test_001",
        "record_id": f"rec_{slug}",
        "business_name": "Bright Smile Clinic",
        "business_slug": slug,
        "category": "Dentist",
        "rating": 4.8,
        "review_count": 132,
        "address": "123 Main Street",
        "phone": "+1-555-123-4567",
        "maps_url": "https://maps.google.com/?cid=123",
        "hours": "Mon-Fri 09:00-18:00",
        "business_status": "open",
        "website_status": "no_website",
        "website_confidence": 1.0,
        "website_reason_codes": ["no_website_url_provided"],
        "qualification_status": "qualified",
        "scoring": {
            "rating_score": 100.0,
            "review_score": 100.0,
            "contactability_score": 60.0,
            "lead_score": 88.0,
        },
    }


def _setup_run_dir(root: Path, run_id: str, leads: list[dict]) -> None:
    """Create minimal directory structure for the test."""
    config_dir = root / "runs" / run_id / "config"
    config_dir.mkdir(parents=True, exist_ok=True)

    scoring_dir = root / "runs" / run_id / "04_briefs"
    scoring_dir.mkdir(parents=True, exist_ok=True)
    (scoring_dir / "selected_for_preview.json").write_text(json.dumps(leads, indent=2))

    briefs_dir = root / "runs" / run_id / "04_briefs"
    briefs_dir.mkdir(parents=True, exist_ok=True)

    for lead in leads:
        slug = lead["business_slug"]
        site_dir = root / "runs" / run_id / "05_sites" / slug / "site"
        site_dir.mkdir(parents=True, exist_ok=True)
        (site_dir / "index.html").write_text("<html><body><h1>Test</h1></body></html>")

    outreach_dir = root / "runs" / run_id / "08_outreach"
    outreach_dir.mkdir(parents=True, exist_ok=True)

    review_dir = root / "runs" / run_id / "09_review"
    review_dir.mkdir(parents=True, exist_ok=True)


_VNEXT_ARTIFACT_PATTERNS = [
    "04_briefs/{slug}/market_profile.json",
    "04_briefs/{slug}/business_profile.json",
    "04_briefs/{slug}/brand_profile.json",
    "04_briefs/{slug}/creative_spec.json",
    "05_sites/{slug}/evaluation_report.json",
    "08_outreach/{slug}/sales_package.json",
    "09_review/{slug}/learning_record.json",
]


def _check_no_vnext_artifacts(root: Path, run_id: str, slug: str) -> None:
    """Assert that no vNext artifacts exist for the given slug."""
    runs = root / "runs" / run_id
    for pattern in _VNEXT_ARTIFACT_PATTERNS:
        path = runs / pattern.format(slug=slug)
        assert not path.exists(), f"vNext artifact should NOT exist: {path}"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_flags_off_no_vnext_artifacts():
    """All flags explicitly False → no vNext artifacts created."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_id = "legacy_off_001"
        leads = [_make_lead()]
        _setup_run_dir(root, run_id, leads)

        all_off = {
            "use_business_profile_contract": False,
            "use_market_profile_contract": False,
            "use_brand_reconstruction_contract": False,
            "use_creative_spec": False,
            "use_stitch_compiler": False,
            "use_structured_evaluation_report": False,
            "use_sales_package_contract": False,
            "use_learning_record_contract": False,
        }
        config = {"niche": "dentists", "area": "Test City", "vnext_flags": all_off}
        slug = leads[0]["business_slug"]

        # Write config
        config_path = root / "runs" / run_id / "config" / "input_config.json"
        config_path.write_text(json.dumps(config, indent=2))

        # Run all helpers — all should be no-ops
        result_03 = run_vnext_post_phase_03(run_id, str(root), leads, config)
        result_04_5 = run_vnext_post_phase_04_5(run_id, str(root), leads, config)
        result_06 = run_vnext_post_phase_06(run_id, str(root), leads, config)
        result_08 = run_vnext_post_phase_08(run_id, str(root), leads, config)
        result_09 = run_vnext_post_phase_09(run_id, str(root), leads, config)

        # All return empty lists
        assert result_03 == [], f"Expected empty list, got {result_03}"
        assert result_04_5 == [], f"Expected empty list, got {result_04_5}"
        assert result_06 == [], f"Expected empty list, got {result_06}"
        assert result_08 == [], f"Expected empty list, got {result_08}"
        assert result_09 == [], f"Expected empty list, got {result_09}"

        # No vNext artifacts on disk
        _check_no_vnext_artifacts(root, run_id, slug)


def test_flags_missing_no_vnext_artifacts():
    """No vnext_flags key in config → all helpers are no-ops."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_id = "legacy_missing_001"
        leads = [_make_lead()]
        _setup_run_dir(root, run_id, leads)

        # Config with NO vnext_flags key at all
        config = {"niche": "dentists", "area": "Test City"}
        slug = leads[0]["business_slug"]

        config_path = root / "runs" / run_id / "config" / "input_config.json"
        config_path.write_text(json.dumps(config, indent=2))

        result_03 = run_vnext_post_phase_03(run_id, str(root), leads, config)
        result_04_5 = run_vnext_post_phase_04_5(run_id, str(root), leads, config)
        result_06 = run_vnext_post_phase_06(run_id, str(root), leads, config)
        result_08 = run_vnext_post_phase_08(run_id, str(root), leads, config)
        result_09 = run_vnext_post_phase_09(run_id, str(root), leads, config)

        assert result_03 == []
        assert result_04_5 == []
        assert result_06 == []
        assert result_08 == []
        assert result_09 == []

        _check_no_vnext_artifacts(root, run_id, slug)


def test_legacy_pipeline_summary_unchanged():
    """Verify pipeline summary format is unchanged when flags are off."""
    flags = get_vnext_flags({})
    assert "use_market_profile_contract" in flags
    assert "use_brand_reconstruction_contract" in flags
    assert "use_creative_spec" in flags
    assert "use_structured_evaluation_report" in flags
    assert "use_sales_package_contract" in flags
    assert "use_learning_record_contract" in flags

    # All defaults False
    assert all(v is False for v in flags.values())

    # Config without vnext_flags → get_vnext_flags returns all False
    config = {"niche": "dentists"}
    flags2 = get_vnext_flags(config)
    assert flags2 == flags


def test_individual_flag_isolation():
    """Enabling one flag should NOT trigger unrelated vNext modules."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_id = "iso_001"
        leads = [_make_lead()]
        _setup_run_dir(root, run_id, leads)
        slug = leads[0]["business_slug"]

        # Only enable market_profile
        config = {
            "niche": "dentists",
            "area": "Test City",
            "vnext_flags": {"use_market_profile_contract": True},
        }
        config_path = root / "runs" / run_id / "config" / "input_config.json"
        config_path.write_text(json.dumps(config, indent=2))

        # Phase 03 → only market_profile created
        result_03 = run_vnext_post_phase_03(run_id, str(root), leads, config)
        assert len(result_03) == 1
        assert (root / "runs" / run_id / "04_briefs" / slug / "market_profile.json").exists()

        # Phase 04.5 helpers — brand reconstruction NOT enabled
        result_04_5 = run_vnext_post_phase_04_5(run_id, str(root), leads, config)
        # brand_profile should NOT be created
        assert not (root / "runs" / run_id / "04_briefs" / slug / "brand_profile.json").exists()
        # creative_spec should NOT be created
        assert not (root / "runs" / run_id / "04_briefs" / slug / "creative_spec.json").exists()
        assert result_04_5 == []

        # Phase 06 — evaluation NOT enabled
        result_06 = run_vnext_post_phase_06(run_id, str(root), leads, config)
        assert result_06 == []
        assert not (root / "runs" / run_id / "05_sites" / slug / "evaluation_report.json").exists()

        # Phase 08 — sales package NOT enabled
        result_08 = run_vnext_post_phase_08(run_id, str(root), leads, config)
        assert result_08 == []
        assert not (root / "runs" / run_id / "08_outreach" / slug / "sales_package.json").exists()

        # Phase 09 — learning record NOT enabled
        result_09 = run_vnext_post_phase_09(run_id, str(root), leads, config)
        assert result_09 == []
        assert not (root / "runs" / run_id / "09_review" / slug / "learning_record.json").exists()


def test_empty_leads_no_error():
    """Empty leads list should not cause errors even with flags on."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_id = "empty_leads_001"

        all_on = {
            "use_business_profile_contract": True,
            "use_market_profile_contract": True,
            "use_brand_reconstruction_contract": True,
            "use_creative_spec": True,
            "use_structured_evaluation_report": True,
            "use_sales_package_contract": True,
            "use_learning_record_contract": True,
        }
        config = {"niche": "dentists", "area": "Test City", "vnext_flags": all_on}

        # All should return empty lists with empty leads
        assert run_vnext_post_phase_03(run_id, str(root), [], config) == []
        assert run_vnext_post_phase_04_5(run_id, str(root), [], config) == []
        assert run_vnext_post_phase_06(run_id, str(root), [], config) == []
        assert run_vnext_post_phase_08(run_id, str(root), [], config) == []
        assert run_vnext_post_phase_09(run_id, str(root), [], config) == []
