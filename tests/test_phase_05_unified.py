import os
from pathlib import Path

from packages.phases.phase_05_unified import run_phase_05_unified
from packages.pipeline.json_io import write_json


class FakeFailingStitchClient:
    def create_project(self, title):
        raise RuntimeError("Stitch API offline")
        
class FakeSuccessStitchClient:
    def create_project(self, title):
        return {"id": "fake_project_123"}
        
    def generate_screen_from_text(self, project_id, prompt, device_type="MOBILE", model_id="", design_system=""):
        # Return full response — screen lives in outputComponents
        return {
            "structuredContent": {
                "outputComponents": [{
                    "design": {
                        "screens": [{
                            "name": "projects/fake_project_123/screens/fake_screen_123",
                            "htmlCode": {"downloadUrl": "https://stitch.example/screen.html"},
                            "screenshot": {"downloadUrl": "https://stitch.example/ss.png"},
                        }]
                    }
                }]
            }
        }
        
    def list_screens(self, project_id):
        return {"screens": [{"name": "projects/fake_project_123/screens/fake_screen_123"}]}
        
    def get_screen(self, project_id, screen_id):
        return {"id": screen_id, "status": "COMPLETED"}
        
    def download_assets(self, project_id, output_dir, **kwargs):
        os.makedirs(output_dir, exist_ok=True)
        site_dir = Path(output_dir) / "site"
        site_dir.mkdir(parents=True, exist_ok=True)
        with open(site_dir / "index.html", "w") as f:
            f.write("<html><body>Stitch Generated " + ("x" * 3000) + "</body></html>")
        with open(site_dir / "styles.css", "w") as f:
            f.write("body { color: blue; }")
        return {"status": "success", "path": str(output_dir)}

def setup_test_workspace(tmp_path: Path, mode: str) -> str:
    """Setup a test workspace with required artifacts from previous phases."""
    run_id = "test_run_unified"
    workspace = str(tmp_path)
    
    # Create Phase 01 config
    config_dir = tmp_path / "runs" / run_id / "config"
    config_dir.mkdir(parents=True)
    write_json(str(config_dir / "input_config.json"), {
        "niche": "test",
        "area": "test",
        "generation_mode": mode
    })
    
    # Create Phase 04 briefs (needs preview_ready_briefs.json)
    briefs_dir = tmp_path / "runs" / run_id / "04_briefs"
    briefs_dir.mkdir(parents=True)
    
    business_brief = {
        "run_id": run_id,
        "business_slug": "test-business",
        "business_name": "Test Business",
        "category": "test",
        "address": "test",
        "phone": "test",
        "primary_contact": "test",
        "differentiators": ["test"],
        "services": ["test"],
        "call_to_action": "test",
        "trust_signals": ["test"]
    }
    write_json(str(briefs_dir / "preview_ready_briefs.json"), [business_brief])
    write_json(str(briefs_dir / "business_test-business.json"), business_brief)
    
    # Create Phase 03 selected leads
    p3_dir = tmp_path / "runs" / run_id / "03_scored"
    p3_dir.mkdir(parents=True)
    write_json(str(p3_dir / "result.json"), {
        "status": "done",
        "selected_leads": ["test-business"]
    })
    
    # Create FACTS.md
    business_dir = briefs_dir / "test-business"
    business_dir.mkdir(parents=True)
    (business_dir / "FACTS.md").write_text("# Test Business\n\n- Fact 1\n")
    
    return workspace, run_id

def test_unified_template_mode(tmp_path):
    workspace, run_id = setup_test_workspace(tmp_path, "template")
    
    res = run_phase_05_unified(run_id, workspace)
    
    assert res["status"] == "done"
    assert res["generation_mode_used"] == "template"
    assert (tmp_path / "runs" / run_id / "05_sites" / "test-business" / "site" / "index.html").exists()
    
    # check that build_status contains render_capture since Phase 05.5 ran/mocked
    status_path = tmp_path / "runs" / run_id / "05_sites" / "test-business" / "build_status.json"
    assert status_path.exists()
    from packages.pipeline.json_io import read_json
    status = read_json(str(status_path))
    assert "render_capture" in status
    assert "render_capture_status" in status

def test_unified_stitch_mode_success(tmp_path):
    workspace, run_id = setup_test_workspace(tmp_path, "stitch")
    
    res = run_phase_05_unified(run_id, workspace, stitch_client=FakeSuccessStitchClient())
    
    assert res["status"] == "done"
    assert res["generation_mode_used"] == "stitch"
    # Note: fake client writes to target_dir which is under 05_sites/test-business/site/
    content = (tmp_path / "runs" / run_id / "05_sites" / "test-business" / "site" / "index.html").read_text()
    assert "Stitch Generated" in content

def test_unified_stitch_mode_no_client_fails(tmp_path):
    workspace, run_id = setup_test_workspace(tmp_path, "stitch")
    
    res = run_phase_05_unified(run_id, workspace, stitch_client=None)
    
    assert res["status"] == "failed"
    assert "required" in res["errors"][0]

def test_unified_auto_mode_success(tmp_path):
    workspace, run_id = setup_test_workspace(tmp_path, "auto")
    
    res = run_phase_05_unified(run_id, workspace, stitch_client=FakeSuccessStitchClient())
    
    assert res["status"] == "done"
    assert res["generation_mode_used"] == "stitch"
    # Note: fake client writes to target_dir which is under 05_sites/test-business/site/
    content = (tmp_path / "runs" / run_id / "05_sites" / "test-business" / "site" / "index.html").read_text()
    assert "Stitch Generated" in content

def test_unified_auto_mode_fallback_on_fail(tmp_path):
    workspace, run_id = setup_test_workspace(tmp_path, "auto")
    
    res = run_phase_05_unified(run_id, workspace, stitch_client=FakeFailingStitchClient())
    
    assert res["status"] == "done"
    assert res["generation_mode_used"] == "template"
    content = (tmp_path / "runs" / run_id / "05_sites" / "test-business" / "site" / "index.html").read_text()
    assert "Stitch Generated" not in content  # should be template content

def test_unified_auto_mode_fallback_no_client(tmp_path):
    workspace, run_id = setup_test_workspace(tmp_path, "auto")
    
    res = run_phase_05_unified(run_id, workspace, stitch_client=None)
    
    assert res["status"] == "done"
    assert res["generation_mode_used"] == "template"
