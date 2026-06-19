"""Integration tests for VNEXT-07 patch planner post-phase-06."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile

from packages.pipeline.vnext_integration import run_vnext_post_phase_06_patch_plan


def test_patch_planner_pipeline_no_flag():
    """When use_patch_phase flag is OFF, function should return empty list (no-op)."""
    result = run_vnext_post_phase_06_patch_plan(
        run_id="test",
        workspace="/tmp",
        selected_leads=[],
        config={"vnext_flags": {"use_patch_phase": False}},
    )
    assert result == []


def test_patch_planner_pipeline_with_flag_no_site():
    """When flag is ON but no site HTML exists, should skip gracefully."""
    with tempfile.TemporaryDirectory() as tmp:
        result = run_vnext_post_phase_06_patch_plan(
            run_id="test_run",
            workspace=tmp,
            selected_leads=[{"business_slug": "unknown"}],
            config={"vnext_flags": {"use_patch_phase": True}},
        )
        # Should be empty because No site HTML
        assert result == []


def test_patch_planner_pipeline_creates_artifacts(tmp_path: Path):
    """When flag is ON with site HTML, should create patch_plan.json and patched HTML."""
    run_id = "test_run"
    workspace = str(tmp_path)

    slug = "test-business"
    sites_dir = tmp_path / "runs" / run_id / "05_sites" / slug / "site"
    sites_dir.mkdir(parents=True)

    # Write minimal HTML with a CTA issue
    html = """<!DOCTYPE html>
<html>
<head><title>Test</title></head>
<body>
<h1>Welcome</h1>
<p>No CTA here, just content.</p>
</body>
</html>"""
    (sites_dir / "index.html").write_text(html, encoding="utf-8")

    # Write minimal evaluation report
    eval_report = {
        "schema_version": "1.0.0",
        "run_id": run_id,
        "business_slug": slug,
        "overall_score": 35,
        "verdict": "patchable",
        "patchable_failures": ["missing_final_cta"],
        "dimensions": {
            "conversion": {"score": 20, "notes": "Missing CTA"},
            "imagery": {"score": 60},
            "typography": {"score": 70},
            "spacing": {"score": 70},
            "branding": {"score": 70},
        },
    }
    (sites_dir.parent / "evaluation_report.json").write_text(
        json.dumps(eval_report), encoding="utf-8"
    )

    result = run_vnext_post_phase_06_patch_plan(
        run_id=run_id,
        workspace=workspace,
        selected_leads=[{"business_slug": slug}],
        config={"vnext_flags": {"use_patch_phase": True}},
    )

    # Should have created patch_plan.json
    assert any("patch_plan.json" in p for p in result), "patch_plan.json should be in output"

    # Verify patch_plan.json exists and is valid
    patch_plan_path = sites_dir.parent / "patch_plan.json"
    assert patch_plan_path.exists(), "patch_plan.json should exist"
    plan = json.loads(patch_plan_path.read_text())
    assert "patches" in plan
    assert isinstance(plan["patches"], list)

    # If patches were generated, check patched HTML exists
    if plan["patches"]:
        assert any("index_patched.html" in p for p in result), \
            "index_patched.html should be in output when patches exist"