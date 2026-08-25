import subprocess

from packages.deployers.vercel import deploy_to_vercel
from packages.phases.phase_07_deployment import run_phase_07
from packages.pipeline.json_io import read_json, write_json


class MockCompletedProcess:
    def __init__(self, returncode, stdout, stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

def test_vercel_deployer_success(tmp_path, monkeypatch):
    site_path = tmp_path / "test_site"
    site_dir = site_path / "site"
    site_dir.mkdir(parents=True)
    (site_dir / "index.html").write_text("<html></html>", encoding="utf-8")
    
    def mock_run(*args, **kwargs):
        return MockCompletedProcess(0, "my-vercel-project.vercel.app")
        
    monkeypatch.setattr(subprocess, "run", mock_run)
    
    res = deploy_to_vercel(str(site_path), project_name="my-project")
    assert res["deployment_status"] == "live"
    assert res["preview_url"] == "https://my-vercel-project.vercel.app"
    assert res["provider"] == "vercel"
    assert res["http_status"] == 200

def test_vercel_deployer_failure(tmp_path, monkeypatch):
    site_path = tmp_path / "test_site"
    site_dir = site_path / "site"
    site_dir.mkdir(parents=True)
    (site_dir / "index.html").write_text("<html></html>", encoding="utf-8")
    
    def mock_run(*args, **kwargs):
        return MockCompletedProcess(1, "", "Vercel CLI Error")
        
    monkeypatch.setattr(subprocess, "run", mock_run)
    
    res = deploy_to_vercel(str(site_path))
    assert res["deployment_status"] == "failed"
    assert res["preview_url"] == ""
    assert res["error"] == "Vercel CLI Error"

def test_phase_07_vercel_integration(tmp_path, monkeypatch):
    run_id = "test_run_vercel"
    workspace = tmp_path
    
    # Setup config
    config_dir = tmp_path / "runs" / run_id / "config"
    config_dir.mkdir(parents=True)
    write_json(str(config_dir / "input_config.json"), {
        "niche": "test",
        "area": "test",
        "price_offer": "$499",
        "deploy_provider": "vercel"
    })
    
    # Setup site & quality
    site_subdir = tmp_path / "runs" / run_id / "05_sites" / "test-business"
    (site_subdir / "site").mkdir(parents=True)
    (site_subdir / "site" / "index.html").write_text("<html></html>", encoding="utf-8")
    
    # Create legacy quality report
    q_dir = tmp_path / "runs" / run_id / "06_quality" / "test-business"
    q_dir.mkdir(parents=True)
    import json
    (q_dir / "site_quality_report.json").write_text(json.dumps({
        "status": "approved_for_deploy"
    }), encoding="utf-8")
    
    def mock_run(*args, **kwargs):
        return MockCompletedProcess(0, "test-business.vercel.app")
        
    monkeypatch.setattr(subprocess, "run", mock_run)
    
    res = run_phase_07(run_id, str(workspace))
    assert res["status"] == "done"
    
    # Verify deployments.json and public_url_manifest.json exist and match
    deployments_path = tmp_path / "runs" / run_id / "07_deployments" / "deployments.json"
    manifest_path = tmp_path / "runs" / run_id / "07_deployments" / "public_url_manifest.json"
    assert deployments_path.exists()
    assert manifest_path.exists()
    
    deps = read_json(str(deployments_path))
    manifest = read_json(str(manifest_path))
    
    assert deps[0]["preview_url"] == "https://test-business.vercel.app"
    assert deps[0]["provider"] == "vercel"
    assert deps[0]["deployment_status"] == "live"
    
    assert "test-business" in manifest
    assert manifest["test-business"]["preview_url"] == "https://test-business.vercel.app"
