import json
from pathlib import Path

from packages.intelligence.brand_reconstruction import build_brand_profile, write_brand_profile


def test_vnext_03_acceptance(tmp_path):
    run_id = "test-run-123"
    bus_profile = {
        "business_slug": "test-bus",
        "verified_facts": {"category": {"value": "Plumber"}},
        "inferred_strategy": {"niche": {"value": ""}},
    }
    market_profile = {
        "competition": {"strategy_hints": ["Reliable"]}
    }
    config = {}

    profile = build_brand_profile(bus_profile, market_profile, config, run_id=run_id)
    
    output_dir = tmp_path / "runs" / run_id / "04_7_brand"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    out_file = write_brand_profile(profile, output_dir, "test-bus")
    
    assert Path(out_file).exists()
    assert Path(out_file).name == "brand_profile.json"
    
    with open(out_file) as f:
        data = json.load(f)
        
    assert data["run_id"] == run_id
    assert "brand_tone" in data
    assert "trust_posture" in data
    assert "forbidden_public_claims" in data

    # Deterministic output check
    profile2 = build_brand_profile(bus_profile, market_profile, config, run_id=run_id)
    assert profile == profile2
    
    # Safety of claims check
    assert len(profile["forbidden_public_claims"]) > 0
    assert "guarantees" in profile["forbidden_public_claims"]
