"""VNEXT-11 E2E integration test: vNext artifact chain.

Validates that when all vNext flags are enabled, the integration helpers
produce every expected artifact with correct schema_version, and that the
artifact chain flows correctly from upstream to downstream modules.

Uses lightweight fixture setup — no network calls, no LLM calls.
"""

import json
import tempfile
from pathlib import Path

from packages.pipeline.json_io import read_json
from packages.pipeline.vnext_integration import (
    get_vnext_flags,
    run_vnext_post_phase_03,
    run_vnext_post_phase_04_5,
    run_vnext_post_phase_06,
    run_vnext_post_phase_08,
    run_vnext_post_phase_09,
)


# ---------------------------------------------------------------------------
# Minimal fixtures
# ---------------------------------------------------------------------------

_ALL_FLAGS_ON = {
    "use_business_profile_contract": True,
    "use_market_profile_contract": True,
    "use_brand_reconstruction_contract": True,
    "use_creative_spec": True,
    "use_stitch_compiler": False,  # stitch compiler needs StitchClient, skip in unit test
    "use_structured_evaluation_report": True,
    "use_sales_package_contract": True,
    "use_learning_record_contract": True,
}

_MINIMAL_CONFIG = {
    "niche": "dentists",
    "area": "Test City",
    "country": "US",
    "vnext_flags": _ALL_FLAGS_ON,
}


def _make_lead(slug: str = "bright-smile-clinic-test", name: str = "Bright Smile Clinic") -> dict:
    """Return a minimal selected lead dict compatible with vNext modules."""
    return {
        "run_id": "vnext_test_001",
        "record_id": f"rec_{slug}",
        "business_name": name,
        "business_slug": slug,
        "category": "Dentist",
        "rating": 4.8,
        "review_count": 132,
        "address": "123 Main Street, Test City, US",
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
        "scoring_notes": {
            "value_drivers": ["high_rating", "many_reviews", "missing_website_upgrade"],
        },
    }


def _setup_minimal_run_dir(root: Path, run_id: str, leads: list[dict]) -> None:
    """Create the minimal directory structure for a vNext pipeline test."""
    # Config
    config_dir = root / "runs" / run_id / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    config = {**_MINIMAL_CONFIG, "run_id": run_id}
    (config_dir / "input_config.json").write_text(json.dumps(config, indent=2))

    # Phase 03 scoring output
    scoring_dir = root / "runs" / run_id / "04_briefs"
    scoring_dir.mkdir(parents=True, exist_ok=True)
    (scoring_dir / "selected_for_preview.json").write_text(json.dumps(leads, indent=2))

    # Phase 04 briefs dir
    briefs_dir = root / "runs" / run_id / "04_briefs"
    briefs_dir.mkdir(parents=True, exist_ok=True)

    # Phase 05 sites dir with minimal HTML
    for lead in leads:
        slug = lead["business_slug"]
        site_dir = root / "runs" / run_id / "05_sites" / slug / "site"
        site_dir.mkdir(parents=True, exist_ok=True)
        (site_dir / "index.html").write_text(
            "<!DOCTYPE html><html><head><title>Test Site</title></head>"
            "<body><h1>Welcome to Bright Smile</h1><p>Test content</p></body></html>"
        )
        # Also add a minimal render_capture.json for sales package screenshots
        render_dir = root / "runs" / run_id / "05_sites" / slug
        (render_dir / "render_capture.json").write_text(json.dumps({
            "desktop_screenshot": "screenshots/desktop.png",
            "mobile_screenshot": "screenshots/mobile.png",
        }))

    # Phase 07 deployments dir
    for lead in leads:
        slug = lead["business_slug"]
        deploy_dir = root / "runs" / run_id / "07_deployments" / slug
        deploy_dir.mkdir(parents=True, exist_ok=True)
        (deploy_dir / "deployment_record.json").write_text(json.dumps({
            "preview_url": f"https://{slug}.example.com",
            "status": "live",
        }))

    # Phase 08 outreach dir
    outreach_dir = root / "runs" / run_id / "08_outreach"
    outreach_dir.mkdir(parents=True, exist_ok=True)
    drafts = [
        {
            "run_id": run_id,
            "record_id": f"out_{lead['business_slug']}",
            "business_slug": lead["business_slug"],
            "business_name": lead["business_name"],
            "recipient_channel": "email",
            "recipient_value": f"contact@{lead['business_slug']}.example.com",
            "subject": f"Website preview for {lead['business_name']}",
            "body": "Test outreach body",
            "preview_url": f"https://{lead['business_slug']}.example.com",
            "price_offer": "$299 setup",
            "draft_status": "ready_for_review",
        }
        for lead in leads
    ]
    (outreach_dir / "outreach_drafts.json").write_text(json.dumps(drafts, indent=2))
    (outreach_dir / "result.json").write_text(json.dumps({
        "phase": "phase_08_outreach_generation",
        "status": "done",
        "run_id": run_id,
        "records_processed": len(drafts),
    }))

    # Phase 09 review dir
    review_dir = root / "runs" / run_id / "09_review"
    review_dir.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_vnext_chain_all_flags_on():
    """Full chain: all vNext flags on → all artifacts produced."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_id = "vnext_test_001"
        leads = [_make_lead()]

        _setup_minimal_run_dir(root, run_id, leads)
        config = _MINIMAL_CONFIG
        slug = leads[0]["business_slug"]

        # Phase 03 → VNEXT-02 market profile
        written_03 = run_vnext_post_phase_03(run_id, str(root), leads, config)
        assert len(written_03) == 1
        mp_path = root / "runs" / run_id / "04_briefs" / slug / "market_profile.json"
        assert mp_path.exists()
        mp = read_json(str(mp_path))
        assert mp["schema_version"] == "1.1.0"
        assert "sellability" in mp

        # Phase 04.5 → VNEXT-01 business_profile + VNEXT-03 brand_profile + VNEXT-04 creative_spec
        written_04_5 = run_vnext_post_phase_04_5(run_id, str(root), leads, config)
        assert len(written_04_5) >= 3  # bp + brand + creative_spec

        bp_path = root / "runs" / run_id / "04_briefs" / slug / "business_profile.json"
        assert bp_path.exists()
        bp = read_json(str(bp_path))
        assert bp["schema_version"] == "1.1.0"  # VNEXT-16 enrichment update

        brand_path = root / "runs" / run_id / "04_briefs" / slug / "brand_profile.json"
        assert brand_path.exists()
        brand = read_json(str(brand_path))
        assert brand["schema_version"] == "1.1.0"
        assert "brand_tone" in brand

        cs_path = root / "runs" / run_id / "04_briefs" / slug / "creative_spec.json"
        assert cs_path.exists()
        cs = read_json(str(cs_path))
        assert cs["schema_version"] == "1.0.0"

        # Phase 06 → VNEXT-06 evaluation report
        written_06 = run_vnext_post_phase_06(run_id, str(root), leads, config)
        assert len(written_06) == 1
        er_path = root / "runs" / run_id / "05_sites" / slug / "evaluation_report.json"
        assert er_path.exists()
        er = read_json(str(er_path))
        assert er["schema_version"] == "1.0.0"
        assert "dimensions" in er

        # Phase 08 → VNEXT-08 sales package
        written_08 = run_vnext_post_phase_08(run_id, str(root), leads, config)
        assert len(written_08) == 1
        sp_path = root / "runs" / run_id / "08_outreach" / slug / "sales_package.json"
        assert sp_path.exists()
        sp = read_json(str(sp_path))
        assert sp["schema_version"] == "1.0.0"

        # Phase 09 → VNEXT-09 learning record
        written_09 = run_vnext_post_phase_09(run_id, str(root), leads, config)
        assert len(written_09) == 1
        lr_path = root / "runs" / run_id / "09_review" / slug / "learning_record.json"
        assert lr_path.exists()
        lr = read_json(str(lr_path))
        assert lr["schema_version"] == "1.0.0"
        assert "analytics_keys" in lr


def test_vnext_chain_market_profile_creates_artifact():
    """VNEXT-02 alone: market_profile artifact created."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_id = "test_mp_001"
        leads = [_make_lead()]
        _setup_minimal_run_dir(root, run_id, leads)
        config = {
            "niche": "dentists",
            "area": "Test City",
            "vnext_flags": {"use_market_profile_contract": True},
        }

        written = run_vnext_post_phase_03(run_id, str(root), leads, config)
        assert len(written) == 1

        slug = leads[0]["business_slug"]
        mp = read_json(str(root / "runs" / run_id / "04_briefs" / slug / "market_profile.json"))
        assert mp["schema_version"] == "1.1.0"
        assert mp["business_slug"] == slug


def test_vnext_chain_brand_profile_creates_artifact():
    """VNEXT-03 alone: brand_profile artifact created."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_id = "test_bp_001"
        leads = [_make_lead()]
        _setup_minimal_run_dir(root, run_id, leads)

        # Need market_profile + business_profile first (brand_profile depends on business_profile)
        config = {
            "niche": "dentists",
            "area": "Test City",
            "vnext_flags": {
                "use_business_profile_contract": True,
                "use_market_profile_contract": True,
                "use_brand_reconstruction_contract": True,
            },
        }
        run_vnext_post_phase_03(run_id, str(root), leads, config)
        run_vnext_post_phase_04_5(run_id, str(root), leads, config)

        slug = leads[0]["business_slug"]
        brand_path = root / "runs" / run_id / "04_briefs" / slug / "brand_profile.json"
        assert brand_path.exists()
        brand = read_json(str(brand_path))
        assert brand["schema_version"] == "1.1.0"
        assert "brand_tone" in brand


def test_vnext_chain_creative_spec_creates_artifact():
    """VNEXT-04: creative_spec artifact created."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_id = "test_cs_001"
        leads = [_make_lead()]
        _setup_minimal_run_dir(root, run_id, leads)

        config = {
            "niche": "dentists",
            "area": "Test City",
            "vnext_flags": {
                "use_business_profile_contract": True,
                "use_market_profile_contract": True,
                "use_brand_reconstruction_contract": True,
                "use_creative_spec": True,
            },
        }
        run_vnext_post_phase_03(run_id, str(root), leads, config)
        run_vnext_post_phase_04_5(run_id, str(root), leads, config)

        slug = leads[0]["business_slug"]
        cs_path = root / "runs" / run_id / "04_briefs" / slug / "creative_spec.json"
        assert cs_path.exists()
        cs = read_json(str(cs_path))
        assert cs["schema_version"] == "1.0.0"


def test_vnext_chain_evaluation_report_creates_artifact():
    """VNEXT-06: evaluation_report artifact created from HTML."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_id = "test_er_001"
        leads = [_make_lead()]
        _setup_minimal_run_dir(root, run_id, leads)

        config = {
            "niche": "dentists",
            "area": "Test City",
            "vnext_flags": {"use_structured_evaluation_report": True},
        }
        written = run_vnext_post_phase_06(run_id, str(root), leads, config)
        assert len(written) == 1

        slug = leads[0]["business_slug"]
        er = read_json(str(root / "runs" / run_id / "05_sites" / slug / "evaluation_report.json"))
        assert er["schema_version"] == "1.0.0"
        assert "dimensions" in er
        assert "overall_score" in er


def test_vnext_chain_sales_package_creates_artifact():
    """VNEXT-08: sales_package artifact created."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_id = "test_sp_001"
        leads = [_make_lead()]
        _setup_minimal_run_dir(root, run_id, leads)

        config = {
            "niche": "dentists",
            "area": "Test City",
            "price_offer": "$499 one-time",
            "vnext_flags": {
                "use_business_profile_contract": True,
                "use_sales_package_contract": True,
            },
        }

        # Pre-build business_profile (required by sales_package)
        run_vnext_post_phase_04_5(run_id, str(root), leads, config)

        written = run_vnext_post_phase_08(run_id, str(root), leads, config)
        assert len(written) == 1

        slug = leads[0]["business_slug"]
        sp = read_json(str(root / "runs" / run_id / "08_outreach" / slug / "sales_package.json"))
        assert sp["schema_version"] == "1.0.0"


def test_vnext_chain_learning_record_creates_artifact():
    """VNEXT-09: learning_record artifact created."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_id = "test_lr_001"
        leads = [_make_lead()]
        _setup_minimal_run_dir(root, run_id, leads)

        config = {
            "niche": "dentists",
            "area": "Test City",
            "vnext_flags": {"use_learning_record_contract": True},
        }
        written = run_vnext_post_phase_09(run_id, str(root), leads, config)
        assert len(written) == 1

        slug = leads[0]["business_slug"]
        lr = read_json(str(root / "runs" / run_id / "09_review" / slug / "learning_record.json"))
        assert lr["schema_version"] == "1.0.0"
        assert lr["business_slug"] == slug


def test_vnext_chain_multi_lead():
    """Test vNext chain with multiple leads."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_id = "vnext_multi_001"
        leads = [
            _make_lead("bright-smile-clinic", "Bright Smile Clinic"),
            _make_lead("great-coffee-shop", "Great Coffee Shop"),
        ]
        _setup_minimal_run_dir(root, run_id, leads)
        config = _MINIMAL_CONFIG

        # Run full chain
        run_vnext_post_phase_03(run_id, str(root), leads, config)
        run_vnext_post_phase_04_5(run_id, str(root), leads, config)
        run_vnext_post_phase_06(run_id, str(root), leads, config)
        run_vnext_post_phase_08(run_id, str(root), leads, config)
        run_vnext_post_phase_09(run_id, str(root), leads, config)

        # Verify each lead has all artifacts
        for lead in leads:
            slug = lead["business_slug"]
            scoring = root / "runs" / run_id / "04_briefs" / slug
            assert (scoring / "market_profile.json").exists(), f"Missing market_profile for {slug}"
            assert (scoring / "business_profile.json").exists(), f"Missing business_profile for {slug}"
            assert (scoring / "brand_profile.json").exists(), f"Missing brand_profile for {slug}"

            assert (root / "runs" / run_id / "04_briefs" / slug / "creative_spec.json").exists()
            assert (root / "runs" / run_id / "05_sites" / slug / "evaluation_report.json").exists()
            assert (root / "runs" / run_id / "08_outreach" / slug / "sales_package.json").exists()
            assert (root / "runs" / run_id / "09_review" / slug / "learning_record.json").exists()


def test_get_vnext_flags_defaults():
    """Verify all flags default to False when not in config."""
    flags = get_vnext_flags({})
    assert all(v is False for v in flags.values())
    assert len(flags) == 14


def test_get_vnext_flags_partial():
    """Partial flags: only specified keys set, rest False."""
    flags = get_vnext_flags({"vnext_flags": {"use_market_profile_contract": True}})
    assert flags["use_market_profile_contract"] is True
    assert flags["use_brand_reconstruction_contract"] is False
