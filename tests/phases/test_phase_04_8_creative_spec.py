from unittest.mock import patch
from packages.phases.phase_04_8_creative_spec import run_phase_04_8
from packages.creative.creative_spec_models import SCHEMA_VERSION

def test_phase_04_8_creative_spec_success(tmp_path):
    run_id = "test_run"
    runs_dir = tmp_path / "runs" / run_id
    config_dir = runs_dir / "config"
    briefs_dir = runs_dir / "04_briefs"
    
    config_dir.mkdir(parents=True)
    briefs_dir.mkdir(parents=True)
    
    config_path = config_dir / "input_config.json"
    config_path.write_text('{"use_creative_spec": true}')
    
    briefs_index_path = briefs_dir / "briefs_index.json"
    briefs_index_path.write_text('[{"business_slug": "test_business"}]')
    
    with patch('packages.phases.phase_04_8_creative_spec.build_creative_spec') as mock_build, \
         patch('packages.phases.phase_04_8_creative_spec.validate_creative_spec') as mock_validate, \
         patch('packages.phases.phase_04_8_creative_spec.write_creative_spec') as mock_write:
        
        mock_build.return_value = {
            "schema_version": SCHEMA_VERSION,
            "generated_at": "2026-06-08T00:00:00Z"
        }
        mock_validate.return_value = []
        
        result = run_phase_04_8(run_id, str(tmp_path))
        
        assert result["status"] == "done"
        assert result["records_processed"] == 1
        assert result["records_created"] == 1
        assert mock_build.called
        assert mock_validate.called
        assert mock_write.called
