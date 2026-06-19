import json
from pathlib import Path

from packages.phases.phase_06_strict_quality_gate import (
    run_strict_quality_check,
    _compute_visual_quality_score,
)

def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")

def test_visual_quality_score_calculation():
    # perfect score 100
    metrics = {
        "heading_count": 5,
        "cta_count": 2,
        "section_count": 4,
        "body_word_count": 120,
        "broken_image_count": 0,
        "broken_link_count": 0,
        "missing_stylesheet": False,
        "stylesheet_count": 1,
        "visible_text_density_estimate": 0.2,
    }
    
    score = _compute_visual_quality_score(metrics, None, None, None)
    assert score == 100

    # test penalties
    metrics_penalty = {
        "heading_count": 1,         # -15
        "cta_count": 0,             # -25
        "section_count": 2,         # -10
        "body_word_count": 50,      # -15
        "broken_image_count": 1,    # -10
        "broken_link_count": 1,     # -5
        "missing_stylesheet": True, # -30
        "visible_text_density_estimate": 0.9, # -10 (out of range 0.05-0.80)
    }
    score_penalty = _compute_visual_quality_score(metrics_penalty, None, None, None)
    # 100 - 15 - 25 - 10 - 15 - 10 - 5 - 30 - 10 = 0 (max(0, negative))
    assert score_penalty == 0

def test_visual_score_in_report(tmp_path):
    site_dir = tmp_path / "site"
    brief_dir = tmp_path / "brief"
    
    brief_dir.mkdir(parents=True)
    site_dir.mkdir(parents=True)
    
    # FACTS.md
    (brief_dir / "FACTS.md").write_text("# FACTS\n\n- business_name: Test Detailing\n- category: Auto\n", encoding="utf-8")
    
    # site
    (site_dir / "site").mkdir(parents=True)
    (site_dir / "site" / "index.html").write_text("<html><h1>Test Detailing</h1></html>", encoding="utf-8")
    
    _write_json(site_dir / "build_status.json", {"status": "done"})
    _write_json(site_dir / "render_capture.json", {
        "capture_status": "done",
        "capture_mode": "browser",
    })
    _write_json(site_dir / "dom_metrics.json", {
        "heading_count": 4,
        "cta_count": 1,
        "section_count": 3,
        "body_word_count": 100,
        "broken_image_count": 0,
        "broken_link_count": 0,
        "missing_stylesheet": False,
        "stylesheet_count": 1,
        "visible_text_density_estimate": 0.3,
    })
    
    (site_dir / "screenshot_desktop.png").write_bytes(b"png")
    (site_dir / "screenshot_mobile.png").write_bytes(b"png")
    
    report = run_strict_quality_check(site_dir, brief_dir, strict=True)
    assert report["status"] == "approved_for_deploy"
    assert "visual_quality_score" in report
    assert report["visual_quality_score"] == 100
