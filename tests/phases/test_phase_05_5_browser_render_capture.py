import tempfile
from pathlib import Path

from packages.phases.phase_05_5_browser_render_capture import (
    _is_file_url_under_site_dir,
    _sanitize_log_text,
    _sanitize_request_url,
    run_phase_05_5,
)
from pipeline.json_io import read_json


class FakeBrowserCaptureBackend:
    browser = "fake-browser"

    def capture(self, *, site_dir, output_dir, source_url, viewports):
        (output_dir / "screenshot_desktop.png").write_bytes(b"fake desktop png")
        (output_dir / "screenshot_mobile.png").write_bytes(b"fake mobile png")
        return {
            "browser": self.browser,
            "source_url": source_url,
            "viewports": viewports,
            "dom_metrics": {
                "title": "Example Business",
                "heading_count": 2,
                "cta_count": 1,
                "link_count": 2,
                "image_count": 1,
                "broken_image_count": 0,
                "visible_text_length": 120,
                "body_word_count": 20,
                "document_height": 900,
                "document_width": 1280,
                "horizontal_overflow": False,
            },
            "asset_load_log": {
                "requests": [source_url, "styles.css"],
                "failed_requests": [],
                "stylesheet_count": 1,
                "missing_stylesheet": False,
            },
            "console_log": {"messages": [], "errors": []},
            "layout_summary": {
                "desktop": {
                    "viewport": viewports["desktop"],
                    "screenshot_path": "screenshot_desktop.png",
                    "horizontal_overflow": False,
                },
                "mobile": {
                    "viewport": viewports["mobile"],
                    "screenshot_path": "screenshot_mobile.png",
                    "horizontal_overflow": False,
                },
            },
        }


class MissingStylesheetCaptureBackend(FakeBrowserCaptureBackend):
    def capture(self, *, site_dir, output_dir, source_url, viewports):
        payload = super().capture(site_dir=site_dir, output_dir=output_dir, source_url=source_url, viewports=viewports)
        payload["asset_load_log"]["stylesheet_count"] = 0
        payload["asset_load_log"]["missing_stylesheet"] = True
        return payload


def _write_site(root: Path, run_id: str, business_slug: str = "example-business") -> Path:
    site_dir = root / "runs" / run_id / "05_sites" / business_slug / "site"
    site_dir.mkdir(parents=True, exist_ok=True)
    (site_dir / "index.html").write_text(
        """
        <!doctype html>
        <html>
          <head><title>Example Business</title><link rel="stylesheet" href="styles.css"></head>
          <body>
            <header><h1>Example Business</h1><a class="btn" href="tel:+155****1212">Call</a></header>
            <main>
              <section id="services"><h2>Services</h2><a href="#missing">Details</a></section>
              <section><h2>Services</h2><button>Book Now</button></section>
            </main>
            <footer><a href="#">Footer Link</a></footer>
          </body>
        </html>
        """,
        encoding="utf-8",
    )
    (site_dir / "styles.css").write_text("body { font-family: sans-serif; }", encoding="utf-8")
    return site_dir


def test_run_phase_05_5_blocks_when_05_sites_missing():
    with tempfile.TemporaryDirectory() as tmp:
        result = run_phase_05_5("missing_sites", tmp, capture_backend=FakeBrowserCaptureBackend())

        assert result["status"] == "blocked"
        assert "05_sites" in result["missing_fields"]
        assert "Phase 05 sites required before Phase 05.5" in result["errors"]


def test_run_phase_05_5_blocks_when_site_index_missing():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_id = "missing_index"
        (root / "runs" / run_id / "05_sites" / "example-business" / "site").mkdir(parents=True)

        result = run_phase_05_5(run_id, root, capture_backend=FakeBrowserCaptureBackend())

        assert result["status"] == "blocked"
        assert "business site/index.html" in result["missing_fields"]
        assert "No business site/index.html files found in Phase 05 outputs" in result["errors"]


def test_run_phase_05_5_blocks_when_capture_backend_unavailable(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_id = "backend_unavailable"
        _write_site(root, run_id)

        import packages.phases.phase_05_5_browser_render_capture as phase_05_5

        monkeypatch.setattr(phase_05_5, "_build_default_backend", lambda: None)
        result = run_phase_05_5(run_id, root)

        assert result["status"] == "blocked"
        assert "capture_backend" in result["missing_fields"]
        assert "No browser capture backend available" in result["errors"]


def test_run_phase_05_5_writes_render_artifacts_with_injected_fake_backend():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_id = "capture_ok"
        business_slug = "example-business"
        _write_site(root, run_id, business_slug)

        result = run_phase_05_5(run_id, root, capture_backend=FakeBrowserCaptureBackend())

        assert result["status"] == "done"
        business_dir = root / "runs" / run_id / "05_sites" / business_slug
        for filename in [
            "screenshot_desktop.png",
            "screenshot_mobile.png",
            "render_capture.json",
            "dom_metrics.json",
            "asset_load_log.json",
            "console_log.json",
            "layout_summary.json",
        ]:
            assert (business_dir / filename).exists(), filename

        render_capture = read_json(str(business_dir / "render_capture.json"))
        assert render_capture["run_id"] == run_id
        assert render_capture["record_id"] == business_slug
        assert render_capture["business_slug"] == business_slug
        assert render_capture["desktop_screenshot_path"] == "screenshot_desktop.png"
        assert render_capture["mobile_screenshot_path"] == "screenshot_mobile.png"
        assert render_capture["dom_metrics"]["title"] == "Example Business"
        assert render_capture["asset_load_log"]["missing_stylesheet"] is False
        assert render_capture["console_log"] == {"messages": [], "errors": []}
        assert render_capture["layout_summary"]["desktop"]["screenshot_path"] == "screenshot_desktop.png"
        assert render_capture["render_timestamp"]
        assert render_capture["capture_status"] == "done"
        assert render_capture["capture_mode"] == "browser"
        assert render_capture["browser"] == "fake-browser"
        assert render_capture["source_url"].startswith("file://")
        assert render_capture["viewports"]["desktop"] == {"width": 1280, "height": 800}
        assert render_capture["viewports"]["mobile"] == {"width": 390, "height": 844}
        assert render_capture["screenshot_dimensions"]["desktop"] == {"width": 1280, "height": 800}
        assert render_capture["screenshot_dimensions"]["mobile"] == {"width": 390, "height": 844}
        assert render_capture["artifacts"]["dom_metrics"] == "dom_metrics.json"
        assert render_capture["errors"] == []

        dom_metrics = read_json(str(business_dir / "dom_metrics.json"))
        assert dom_metrics["title"] == "Example Business"
        assert dom_metrics["horizontal_overflow"] is False
        assert dom_metrics["viewport_overflow"] is False
        assert dom_metrics["visible_cta_count"] == 1
        assert dom_metrics["visible_text_density_estimate"] > 0
        assert dom_metrics["text_density_estimate"] > 0
        assert dom_metrics["section_count"] == 5
        assert dom_metrics["section_order"] == ["header", "main", "section", "section", "footer"]
        assert dom_metrics["duplicate_text_signals"] == 1
        assert dom_metrics["broken_link_count"] == 2
        assert dom_metrics["missing_stylesheet"] is False

        layout_summary = read_json(str(business_dir / "layout_summary.json"))
        assert layout_summary["desktop"]["screenshot_dimensions"] == {"width": 1280, "height": 800}
        assert layout_summary["mobile"]["screenshot_dimensions"] == {"width": 390, "height": 844}


def test_aggregate_result_envelope_lists_outputs_created():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_id = "result_outputs"
        business_slug = "example-business"
        _write_site(root, run_id, business_slug)

        result = run_phase_05_5(run_id, root, capture_backend=FakeBrowserCaptureBackend())
        aggregate_path = root / "runs" / run_id / "05_5_render_capture" / "result.json"
        aggregate = read_json(str(aggregate_path))

        expected_outputs = {
            f"runs/{run_id}/05_sites/{business_slug}/screenshot_desktop.png",
            f"runs/{run_id}/05_sites/{business_slug}/screenshot_mobile.png",
            f"runs/{run_id}/05_sites/{business_slug}/render_capture.json",
            f"runs/{run_id}/05_sites/{business_slug}/dom_metrics.json",
            f"runs/{run_id}/05_sites/{business_slug}/asset_load_log.json",
            f"runs/{run_id}/05_sites/{business_slug}/console_log.json",
            f"runs/{run_id}/05_sites/{business_slug}/layout_summary.json",
            f"runs/{run_id}/05_5_render_capture/result.json",
        }
        assert result == aggregate
        assert expected_outputs.issubset(set(result["outputs_created"]))
        assert result["records_created"] == 1
        assert result["records_processed"] == 1


def test_missing_stylesheet_is_recorded_in_dom_metrics_and_render_capture():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_id = "missing_stylesheet"
        business_slug = "example-business"
        _write_site(root, run_id, business_slug)

        result = run_phase_05_5(run_id, root, capture_backend=MissingStylesheetCaptureBackend())

        assert result["status"] == "done"
        business_dir = root / "runs" / run_id / "05_sites" / business_slug
        dom_metrics = read_json(str(business_dir / "dom_metrics.json"))
        render_capture = read_json(str(business_dir / "render_capture.json"))
        assert dom_metrics["missing_stylesheet"] is True
        assert render_capture["dom_metrics"]["missing_stylesheet"] is True
        assert render_capture["asset_load_log"]["missing_stylesheet"] is True


def test_run_phase_05_5_blocks_unsafe_run_id_without_outside_write():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        outside_result = root / "outside" / "05_5_render_capture" / "result.json"

        result = run_phase_05_5("../../outside", root, capture_backend=FakeBrowserCaptureBackend())

        assert result["status"] == "blocked"
        assert "run_id" in result["missing_fields"]
        assert any("Unsafe run_id" in error for error in result["errors"])
        assert not outside_result.exists()


def test_run_phase_05_5_blocks_dot_run_id_without_runs_root_write():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        runs_root = root / "runs"
        site_dir = runs_root / "05_sites" / "example-business" / "site"
        site_dir.mkdir(parents=True)
        (site_dir / "index.html").write_text("<html><body><h1>Bad root run</h1></body></html>", encoding="utf-8")

        result = run_phase_05_5(".", root, capture_backend=FakeBrowserCaptureBackend())

        assert result["status"] == "blocked"
        assert "run_id" in result["missing_fields"]
        assert any("Unsafe run_id" in error for error in result["errors"])
        assert not (runs_root / "05_5_render_capture" / "result.json").exists()


def test_run_phase_05_5_rejects_symlinked_output_root_without_external_result_write():
    with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as external_tmp:
        root = Path(tmp)
        external = Path(external_tmp)
        run_id = "symlinked_output_root"
        run_root = root / "runs" / run_id
        _write_site(root, run_id)
        (run_root / "05_5_render_capture").symlink_to(external, target_is_directory=True)

        result = run_phase_05_5(run_id, root, capture_backend=FakeBrowserCaptureBackend())

        assert result["status"] == "blocked"
        assert "05_5_render_capture" in result["missing_fields"]
        assert any("Unsafe 05_5_render_capture" in error for error in result["errors"])
        assert not (external / "result.json").exists()


def test_run_phase_05_5_rejects_symlinked_sites_root_without_external_artifacts():
    with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as external_tmp:
        root = Path(tmp)
        external = Path(external_tmp)
        run_id = "symlinked_sites_root"
        run_root = root / "runs" / run_id
        run_root.mkdir(parents=True)
        external_site = external / "evil" / "site"
        external_site.mkdir(parents=True)
        (external_site / "index.html").write_text("<html><body><h1>Evil</h1></body></html>", encoding="utf-8")
        (run_root / "05_sites").symlink_to(external, target_is_directory=True)

        result = run_phase_05_5(run_id, root, capture_backend=FakeBrowserCaptureBackend())

        assert result["status"] == "blocked"
        assert "05_sites" in result["missing_fields"]
        assert any("Unsafe 05_sites" in error for error in result["errors"])
        assert not (external / "evil" / "render_capture.json").exists()
        assert not (external / "evil" / "screenshot_desktop.png").exists()


def test_run_phase_05_5_rejects_symlinked_business_dir_without_external_artifacts():
    with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as external_tmp:
        root = Path(tmp)
        external = Path(external_tmp)
        run_id = "symlink_escape"
        sites_root = root / "runs" / run_id / "05_sites"
        sites_root.mkdir(parents=True)
        external_site = external / "site"
        external_site.mkdir()
        (external_site / "index.html").write_text("<html><body><h1>Evil</h1></body></html>", encoding="utf-8")
        (sites_root / "evil").symlink_to(external, target_is_directory=True)

        result = run_phase_05_5(run_id, root, capture_backend=FakeBrowserCaptureBackend())

        assert result["status"] == "blocked"
        assert "business site/index.html" in result["missing_fields"]
        assert not (external / "render_capture.json").exists()
        assert not (external / "screenshot_desktop.png").exists()


def test_sanitize_request_url_strips_secret_values_query_fragment_and_local_paths():
    unsafe = "file:///Users/demo/Workspace/Dev/autowebdelivery/runs/run/05_sites/acme/site/index.html?token=abc123&next=/Users/demo/private#frag"

    sanitized = _sanitize_request_url(unsafe)

    assert sanitized == "file:///[local-file]/index.html"
    assert "abc123" not in sanitized
    assert "token" not in sanitized
    assert "/Users/demo" not in sanitized
    assert "frag" not in sanitized


def test_sanitize_log_text_redacts_secrets_and_truncates_local_paths_and_large_values():
    text = "failed /Users/demo/private/index.html password=hunter2 api_key=abcdef1234567890 token: secret-token " + ("x" * 400)

    sanitized = _sanitize_log_text(text, max_length=160)

    assert "hunter2" not in sanitized
    assert "abcdef1234567890" not in sanitized
    assert "secret-token" not in sanitized
    assert "/Users/demo/private" not in sanitized
    assert "[REDACTED]" in sanitized
    assert len(sanitized) <= 160


def test_file_url_guard_allows_only_files_under_site_dir():
    with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside_tmp:
        site_dir = Path(tmp) / "site"
        site_dir.mkdir()
        allowed = site_dir / "asset.css"
        allowed.write_text("body{}", encoding="utf-8")
        outside = Path(outside_tmp) / "secret.css"
        outside.write_text("body{}", encoding="utf-8")

        assert _is_file_url_under_site_dir(allowed.resolve().as_uri(), site_dir)
        assert not _is_file_url_under_site_dir(outside.resolve().as_uri(), site_dir)
        assert not _is_file_url_under_site_dir("https://example.com/style.css", site_dir)
