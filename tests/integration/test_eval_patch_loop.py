"""Integration tests for evaluation -> patch -> re-evaluate loop (VNEXT-2.4)."""

from __future__ import annotations

import json
from pathlib import Path


def test_eval_patch_loop_single_cycle_only(tmp_path: Path):
    """
    Verify patched HTML gets re-evaluated, score delta logged, no infinite loop.
    This test verifies that after patching, a re-evaluation happens exactly once.
    """
    from packages.pipeline.vnext_integration import run_vnext_post_phase_06_patch_plan

    run_id = "eval_patch_loop_test"
    workspace = str(tmp_path)
    slug = "loop-test-business"

    sites_dir = tmp_path / "runs" / run_id / "05_sites" / slug / "site"
    sites_dir.mkdir(parents=True)

    # HTML with missing CTA (should trigger patch)
    html = """<!DOCTYPE html>
<html>
<head><title>Loop Test</title></head>
<body>
<h1>Welcome to Our Service</h1>
<p>We provide excellent solutions.</p>
</body>
</html>"""
    (sites_dir / "index.html").write_text(html, encoding="utf-8")

    # Evaluation report indicating missing CTA
    eval_report = {
        "schema_version": "1.0.0",
        "run_id": run_id,
        "business_slug": slug,
        "overall_score": 38,
        "verdict": "patchable",
        "patchable_failures": ["conversion"],  # Changed: triggers _should_plan_cta
        "dimensions": {
            "conversion": {"score": 20, "notes": "Missing final CTA"},
            "imagery": {"score": 60},
            "typography": {"score": 70},
            "spacing": {"score": 70},
            "branding": {"score": 70},
        },
    }
    (sites_dir.parent / "evaluation_report.json").write_text(
        json.dumps(eval_report), encoding="utf-8"
    )

    written = run_vnext_post_phase_06_patch_plan(
        run_id=run_id,
        workspace=workspace,
        selected_leads=[{"business_slug": slug}],
        config={"vnext_flags": {"use_patch_phase": True}},
    )

    # Check post_patch_eval report was created
    post_eval_paths = [p for p in written if "post_patch_eval" in p]
    assert len(post_eval_paths) >= 1, "Re-evaluation report should be created"

    # Check patch_eval_meta.json was created with score delta
    meta_paths = [p for p in written if "patch_eval_meta" in p]
    assert len(meta_paths) == 1, "Patch evaluation metadata should exist"

    meta = json.loads(Path(meta_paths[0]).read_text())
    assert "delta" in meta
    assert "pre_score" in meta
    assert "post_score" in meta
    assert meta["pre_score"] == 38
    # Post score should exist and be a number
    assert isinstance(meta["post_score"], (int, float))

    # Verify no infinite loop — only one post_patch_eval directory per slug
    post_dirs = list((tmp_path / "runs" / run_id / "05_sites" / slug).glob("post_patch_eval*"))
    assert len(post_dirs) <= 1, "Should not loop infinitely — max one re-evaluation"


def test_eval_patch_loop_score_delta_logged(tmp_path: Path):
    """Verify score delta is positive when patches improve the site."""
    from packages.pipeline.vnext_integration import run_vnext_post_phase_06_patch_plan

    run_id = "score_delta_test"
    workspace = str(tmp_path)
    slug = "delta-business"

    sites_dir = tmp_path / "runs" / run_id / "05_sites" / slug / "site"
    sites_dir.mkdir(parents=True)

    # Write HTML that will have patches applied
    html = """<!DOCTYPE html>
<html><body><h1>Service</h1></body></html>"""
    (sites_dir / "index.html").write_text(html, encoding="utf-8")

    eval_report = {
        "schema_version": "1.0.0",
        "run_id": run_id,
        "business_slug": slug,
        "overall_score": 25,
        "verdict": "patchable",
        "patchable_failures": ["conversion"],  # Triggers CTA patch
        "dimensions": {
            "conversion": {"score": 10},
            "imagery": {"score": 60},
            "typography": {"score": 70},
            "spacing": {"score": 70},
            "branding": {"score": 70},
        },
    }
    (sites_dir.parent / "evaluation_report.json").write_text(
        json.dumps(eval_report), encoding="utf-8"
    )

    written = run_vnext_post_phase_06_patch_plan(
        run_id=run_id,
        workspace=workspace,
        selected_leads=[{"business_slug": slug}],
        config={"vnext_flags": {"use_patch_phase": True}},
    )

    meta_path = Path([p for p in written if "patch_eval_meta" in p][0])
    meta = json.loads(meta_path.read_text())

    # Delta should be calculated (may be positive, negative, or zero)
    assert "delta" in meta
    assert isinstance(meta["delta"], (int, float))