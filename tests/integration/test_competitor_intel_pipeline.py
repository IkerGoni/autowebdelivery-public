import json
from unittest.mock import patch
from packages.pipeline.vnext_integration import run_vnext_post_phase_03_competitor_intel

def test_run_vnext_post_phase_03_competitor_intel_no_flag():
    result = run_vnext_post_phase_03_competitor_intel(
        run_id="test",
        workspace="/tmp",
        selected_leads=[{"business_slug": "test"}],
        config={"vnext_flags": {"use_competitor_intelligence": False}}
    )
    assert result == []

@patch("packages.intelligence.competitor_intelligence.build_competitor_profile")
@patch("packages.intelligence.competitor_intelligence.write_competitor_profile")
def test_run_vnext_post_phase_03_competitor_intel_with_flag(mock_write, mock_build, tmp_path):
    mock_build.return_value = {"competitors": []}
    mock_write.return_value = str(tmp_path / "competitor_profile.json")

    run_id = "test_run"
    workspace = str(tmp_path)
    
    # Setup briefs dir
    briefs_dir = tmp_path / "runs" / run_id / "04_briefs"
    briefs_dir.mkdir(parents=True)
    slug = "my-test-business"
    lead_dir = briefs_dir / slug
    lead_dir.mkdir()
    
    # Write mock business profile
    with open(lead_dir / "business_profile.json", "w") as f:
        json.dump({
            "overview": {"industry": "Software"},
            "location": {"region": "Global"}
        }, f)
        
    result = run_vnext_post_phase_03_competitor_intel(
        run_id=run_id,
        workspace=workspace,
        selected_leads=[{"business_slug": slug}],
        config={"vnext_flags": {"use_competitor_intelligence": True}}
    )
    
    assert len(result) == 1
    assert result[0] == str(tmp_path / "competitor_profile.json")
    
    mock_build.assert_called_once()
    kwargs = mock_build.call_args.kwargs
    assert kwargs["category"] == "Software"
    assert kwargs["area"] == "Global"
