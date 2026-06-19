"""Unit tests for Task 1C.4 — Artifact path fix: 03_scoring/ → 04_briefs/.

Verifies that:
1. market_profile is written to 04_briefs/ (not 03_scoring/)
2. No writes to 03_scoring/ for vNext artifacts
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from packages.pipeline.vnext_integration import run_vnext_post_phase_03


def _make_lead(slug: str = "test-biz") -> dict:
    return {
        "run_id": "path_test_001",
        "record_id": f"rec_{slug}",
        "business_name": "Test Business",
        "business_slug": slug,
        "category": "Dentist",
        "rating": 4.5,
        "review_count": 100,
        "address": "123 Main St",
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


class TestArtifactPaths:
    def test_market_profile_written_to_04_briefs(self):
        """market_profile.json is written under 04_briefs/, not 03_scoring/."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_id = "path_test_001"
            leads = [_make_lead()]
            slug = leads[0]["business_slug"]

            # Setup minimal run dir
            config_dir = root / "runs" / run_id / "config"
            config_dir.mkdir(parents=True, exist_ok=True)

            config = {
                "niche": "dentists",
                "area": "Test City",
                "vnext_flags": {"use_market_profile_contract": True},
            }
            (config_dir / "input_config.json").write_text(json.dumps(config, indent=2))

            briefs_dir = root / "runs" / run_id / "04_briefs"
            briefs_dir.mkdir(parents=True, exist_ok=True)

            written = run_vnext_post_phase_03(run_id, str(root), leads, config)

            # Written path contains 04_briefs
            assert len(written) == 1
            assert "04_briefs" in written[0]

            # File exists at 04_briefs path
            expected_path = briefs_dir / slug / "market_profile.json"
            assert expected_path.exists()

            # File does NOT exist at 03_scoring path
            wrong_path = root / "runs" / run_id / "03_scoring" / slug / "market_profile.json"
            assert not wrong_path.exists()

    def test_no_writes_to_03_scoring(self):
        """No vNext artifacts are written under 03_scoring/."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_id = "path_test_001"
            leads = [_make_lead()]
            slug = leads[0]["business_slug"]

            config_dir = root / "runs" / run_id / "config"
            config_dir.mkdir(parents=True, exist_ok=True)

            config = {
                "niche": "dentists",
                "area": "Test City",
                "vnext_flags": {"use_market_profile_contract": True},
            }
            (config_dir / "input_config.json").write_text(json.dumps(config, indent=2))

            briefs_dir = root / "runs" / run_id / "04_briefs"
            briefs_dir.mkdir(parents=True, exist_ok=True)

            run_vnext_post_phase_03(run_id, str(root), leads, config)

            # Check no market_profile under 03_scoring
            scoring_path = root / "runs" / run_id / "03_scoring" / slug / "market_profile.json"
            assert not scoring_path.exists()
