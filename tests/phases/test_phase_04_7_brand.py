from pathlib import Path

from packages.pipeline.result_envelope import Status
from packages.phases.phase_04_7_brand import run_phase_04_7
from packages.pipeline.json_io import write_json, read_json

def test_phase_04_7_skipped_when_flag_off(tmp_path: Path):
    run_id = "run_test_04_7_off"
    runs_dir = tmp_path / "runs"
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True)
    
    config_dir = run_dir / "config"
    config_dir.mkdir()
    write_json(str(config_dir / "input_config.json"), {
        "use_brand_reconstruction_contract": False
    })
    
    result = run_phase_04_7(run_id, tmp_path)
    assert result.status == Status.SKIPPED
    assert len(result.decisions) > 0
    assert "Skipped" in result.decisions[0]

def test_phase_04_7_success(tmp_path: Path):
    run_id = "run_test_04_7_on"
    runs_dir = tmp_path / "runs"
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True)
    
    config_dir = run_dir / "config"
    config_dir.mkdir()
    write_json(str(config_dir / "input_config.json"), {
        "use_brand_reconstruction_contract": True
    })
    
    # Mock inputs
    briefs_dir = run_dir / "04_briefs"
    briefs_dir.mkdir()
    business_slug = "test_business_slug"
    write_json(str(briefs_dir / "briefs_index.json"), {business_slug: []})
    
    business_dir = briefs_dir / business_slug
    business_dir.mkdir()
    write_json(str(business_dir / "business_profile.json"), {
        "business_slug": business_slug,
        "verified_facts": {
            "category": {"value": "auto detailing"}
        }
    })
    
    scoring_dir = run_dir / "03_scoring"
    scoring_dir.mkdir()
    write_json(str(scoring_dir / "leads_scored.json"), {
        "scored_leads": [{"business_slug": business_slug}]
    })
    
    scoring_biz_dir = scoring_dir / business_slug
    scoring_biz_dir.mkdir()
    write_json(str(scoring_biz_dir / "market_profile.json"), {
        "strategy_hints": {"competitiveness": "high"}
    })
    
    result = run_phase_04_7(run_id, tmp_path)
    assert result.status == Status.DONE
    assert result.records_created == 1
    
    # Assert output exists and check a key from the schema
    brand_profile_path = run_dir / "04_7_brand" / business_slug / "brand_profile.json"
    assert brand_profile_path.exists()
    
    brand_profile = read_json(str(brand_profile_path))
    assert brand_profile["business_slug"] == business_slug
    assert "brand_tone" in brand_profile
    assert "trust_posture" in brand_profile
