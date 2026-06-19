import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from packages.generation.stitch_adapter import (
    CommandResult,
    HttpStitchClient,
    McpStitchClient,
    McporterStitchClient,
    StitchAdapter,
    StitchGenerationRequest,
)


class FakeStitchClient:
    def __init__(self, *, fail_generate=False, fail_download=False):
        self.fail_generate = fail_generate
        self.fail_download = fail_download
        self.calls = []

    def create_project(self, *, title):
        self.calls.append(("create_project", title))
        return {"project_id": "project_fake"}

    def generate_screen_from_text(self, *, project_id, prompt, design_system=None, device_type="DESKTOP", model_id=None):
        self.calls.append(("generate_screen_from_text", project_id, prompt, design_system, device_type, model_id))
        if self.fail_generate:
            raise RuntimeError("secret-token-abc generation exploded")
        # Return the full Stitch response format — screen lives in outputComponents
        return {
            "structuredContent": {
                "outputComponents": [{
                    "design": {
                        "screens": [{
                            "name": f"projects/{project_id}/screens/screen_fake",
                            "htmlCode": {"downloadUrl": "https://stitch.example/html"},
                            "screenshot": {"downloadUrl": "https://stitch.example/screenshot"},
                        }]
                    }
                }]
            }
        }

    def list_screens(self, *, project_id):
        self.calls.append(("list_screens", project_id))
        return {"screens": []}

    def get_project(self, *, project_id):
        self.calls.append(("get_project", project_id))
        return {"project_id": project_id}

    def get_screen(self, *, project_id, screen_id):
        self.calls.append(("get_screen", project_id, screen_id))
        return {
            "screen_id": screen_id,
            "htmlCode": {"downloadUrl": "https://stitch.example/html"},
            "screenshot": {"downloadUrl": "https://stitch.example/screenshot"},
        }

    def download_assets(self, *, project_id, output_dir, html_url=None):
        self.calls.append(("download_assets", project_id, str(output_dir), html_url))
        if self.fail_download:
            raise RuntimeError("download failed")
        path = Path(output_dir) / "index.html"
        # Write HTML large enough to pass the MIN_HTML_SIZE validation (≥ 2000 bytes)
        path.write_text(
            "<html><body>Premium page " + ("x" * 2000) + "</body></html>",
            encoding="utf-8",
        )
        return {"status": "downloaded", "path": str(output_dir)}


def _request(tmp_path, **overrides):
    values = {
        "run_id": "run_001",
        "record_id": "rec_001",
        "business_slug": "frisco-mobile-detailing",
        "business_name": "Frisco Mobile Detailing",
        "prompt": "Design a premium page",
        "prompt_contract": {"prompt_version": "premium_stitch_prompt_v1", "prompt_sha256": "abc"},
        "output_dir": tmp_path / "out",
        "project_title": "Premium test project",
        "design_system": "assets/design_fake",
    }
    values.update(overrides)
    return StitchGenerationRequest(**values)


def test_adapter_uses_injected_fake_client_and_writes_metadata(tmp_path):
    client = FakeStitchClient()
    result = StitchAdapter(client).generate(_request(tmp_path))

    assert result.status == "done"
    assert result.project_id == "project_fake"
    assert result.screen_id == "screen_fake"
    assert result.html_path.endswith("index.html")
    assert (tmp_path / "out" / "stitch_generation_metadata.json").exists()
    assert (tmp_path / "out" / "stitch_prompt_contract.json").exists()
    assert client.calls[0][0] == "create_project"
    assert client.calls[-1][0] == "download_assets"


def test_adapter_uses_existing_project_id_without_create_project(tmp_path):
    client = FakeStitchClient()
    result = StitchAdapter(client).generate(_request(tmp_path, project_id="project_existing"))

    assert result.status == "done"
    assert result.project_id == "project_existing"
    assert "create_project" not in [call[0] for call in client.calls]


def test_adapter_fails_cleanly_on_generate_error(tmp_path):
    result = StitchAdapter(FakeStitchClient(fail_generate=True)).generate(_request(tmp_path))

    assert result.status == "failed"
    assert result.errors
    assert "\n" not in result.errors[0]
    assert "secret-token-abc" not in result.errors[0]
    assert "redacted" in result.errors[0]
    assert "premium_stitch_generation_failed" in result.risks


def test_adapter_fails_when_screen_not_in_response(tmp_path):
    """When generate_screen_from_text returns no outputComponents/screens, adapter fails cleanly."""
    class NoScreenClient(FakeStitchClient):
        def generate_screen_from_text(self, *, project_id, prompt, design_system=None, device_type="DESKTOP", model_id=None):
            return {"structuredContent": {"outputComponents": []}}

    result = StitchAdapter(NoScreenClient()).generate(_request(tmp_path))

    assert result.status == "failed"
    assert any("No screen found" in err for err in result.errors)


def test_adapter_fails_cleanly_on_download_error(tmp_path):
    result = StitchAdapter(FakeStitchClient(fail_download=True)).generate(_request(tmp_path))

    assert result.status == "failed"
    assert result.errors == ["download failed"]


def test_mcp_client_uses_injected_callables():
    calls = []

    def record(name):
        def inner(**kwargs):
            calls.append((name, kwargs))
            if name == "create_project":
                return {"project_id": "p1"}
            if name == "generate":
                return {
                    "structuredContent": {
                        "outputComponents": [{
                            "design": {
                                "screens": [{"name": "projects/p1/screens/s1"}]
                            }
                        }]
                    }
                }
            return {}

        return inner

    client = McpStitchClient(
        create_project=record("create_project"),
        generate_screen_from_text=record("generate"),
        list_screens=record("list_screens"),
        get_project=record("get_project"),
        get_screen=record("get_screen"),
        download_assets=record("download_assets"),
    )

    assert client.create_project(title="Title") == {"project_id": "p1"}
    assert client.generate_screen_from_text(project_id="p1", prompt="prompt") == {
        "structuredContent": {
            "outputComponents": [{"design": {"screens": [{"name": "projects/p1/screens/s1"}]}}]
        }
    }
    client.download_assets(project_id="p1", output_dir="/tmp/out", html_url="https://stitch.example/dl")

    assert calls[0] == ("create_project", {"title": "Title"})
    assert calls[1][1]["projectId"] == "p1"
    assert calls[2][1]["outputDir"] == "/tmp/out"


class FakeRunner:
    def __init__(self, stdout=None, exit_code=0, stderr=""):
        self.stdout = stdout or json.dumps({"project_id": "p1"})
        self.exit_code = exit_code
        self.stderr = stderr
        self.calls = []

    def run(self, args, cwd=None, timeout=None):
        self.calls.append((args, cwd, timeout))
        return CommandResult(exit_code=self.exit_code, stdout=self.stdout, stderr=self.stderr)


def test_mcporter_client_uses_injected_runner_and_config_path(tmp_path):
    runner = FakeRunner(stdout=json.dumps({"screen_id": "screen_1"}))
    client = McporterStitchClient(runner=runner, config_path=tmp_path / "mcporter.json", command=("mcporter",))

    assert client.generate_screen_from_text(project_id="project_1", prompt="prompt") == {"screen_id": "screen_1"}
    args, cwd, timeout = runner.calls[0]

    assert args[:3] == ["mcporter", "--config", str(tmp_path / "mcporter.json")]
    assert "stitch.generate_screen_from_text" in args
    assert cwd is None
    assert timeout == 300


def test_mcporter_client_raises_on_runner_failure():
    client = McporterStitchClient(runner=FakeRunner(exit_code=1, stderr="401 unauthorized"))

    with pytest.raises(RuntimeError, match="401 unauthorized"):
        client.get_project(project_id="project_1")


# ---------------------------------------------------------------------------
# HttpStitchClient tests
# ---------------------------------------------------------------------------

def _make_rpc_response(result: dict) -> bytes:
    return json.dumps({"jsonrpc": "2.0", "id": 1, "result": result}).encode("utf-8")


def _make_rpc_error(message: str, code: int = -1) -> bytes:
    return json.dumps({"jsonrpc": "2.0", "id": 1, "error": {"code": code, "message": message}}).encode("utf-8")


def _mock_urlopen(response_body: bytes, status: int = 200):
    """Return a context-manager mock for urllib.request.urlopen."""
    mock_resp = MagicMock()
    mock_resp.read.return_value = response_body
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)
    return patch("urllib.request.urlopen", return_value=mock_resp)


def test_http_client_create_project_parses_project_id():
    client = HttpStitchClient(api_key="test-key")
    # Real API returns structuredContent.name
    response = _make_rpc_response({
        "structuredContent": {"name": "projects/12345"},
        "content": [{"text": '{"name": "projects/12345"}'}]
    })

    with _mock_urlopen(response):
        result = client.create_project(title="Test Project")

    assert result["project_id"] == "12345"
    assert result["projectName"] == "projects/12345"


def test_http_client_create_project_handles_bare_id():
    client = HttpStitchClient(api_key="test-key")
    response = _make_rpc_response({
        "structuredContent": {"name": "bare-id"},
        "content": [{"text": '{"name": "bare-id"}'}]
    })

    with _mock_urlopen(response):
        result = client.create_project(title="Test")

    assert result["project_id"] == "bare-id"


def test_http_client_generate_screen_returns_full_result():
    """HttpStitchClient returns the full RPC result — caller extracts screen from outputComponents."""
    client = HttpStitchClient(api_key="test-key")
    expected = {
        "structuredContent": {
            "projectId": "12345",
            "sessionId": "sess_abc",
            "outputComponents": [{
                "design": {
                    "screens": [{"name": "projects/12345/screens/sc_1"}]
                }
            }]
        },
        "content": [{"text": '{"projectId": "12345"}'}]
    }
    response = _make_rpc_response(expected)

    with _mock_urlopen(response):
        result = client.generate_screen_from_text(project_id="12345", prompt="Make a site")

    assert result["structuredContent"]["projectId"] == "12345"
    assert result["structuredContent"]["outputComponents"][0]["design"]["screens"][0]["name"] == "projects/12345/screens/sc_1"


def test_http_client_generate_screen_passes_optional_args():
    client = HttpStitchClient(api_key="test-key")
    captured_request = {}

    def capture(req, **kwargs):
        captured_request["data"] = json.loads(req.data)
        mock_resp = MagicMock()
        mock_resp.read.return_value = _make_rpc_response({"screenName": "projects/1/screens/x"})
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    with patch("urllib.request.urlopen", side_effect=capture):
        client.generate_screen_from_text(
            project_id="1",
            prompt="prompt",
            design_system="assets/xyz",
            device_type="MOBILE",
            model_id="GEMINI_3_PRO",
        )

    args = captured_request["data"]["params"]["arguments"]
    assert args["projectId"] == "1"
    assert args["designSystem"] == "assets/xyz"
    assert args["deviceType"] == "MOBILE"
    assert args["modelId"] == "GEMINI_3_PRO"


def test_http_client_get_screen_returns_result():
    client = HttpStitchClient(api_key="test-key")
    screen_data = {
        "htmlCode": {"downloadUrl": "https://stitch.example/dl/html123"},
        "screenshot": {"downloadUrl": "https://stitch.example/dl/ss123"},
    }
    response = _make_rpc_response(screen_data)

    with _mock_urlopen(response):
        result = client.get_screen(project_id="12345", screen_id="abcd")

    assert result["htmlCode"]["downloadUrl"] == "https://stitch.example/dl/html123"


def test_http_client_raises_on_rpc_error():
    client = HttpStitchClient(api_key="test-key")
    response = _make_rpc_error("Project not found", code=404)

    with _mock_urlopen(response):
        with pytest.raises(RuntimeError, match="Project not found"):
            client.get_project(project_id="nonexistent")


def test_http_client_raises_on_http_error():
    import urllib.error
    client = HttpStitchClient(api_key="test-key")

    def raise_http_error(req, **kwargs):
        raise urllib.error.HTTPError("url", 403, "Forbidden", {}, None)

    with patch("urllib.request.urlopen", side_effect=raise_http_error):
        with pytest.raises(RuntimeError, match="HTTP 403"):
            client.create_project(title="Fail")


def test_http_client_download_assets_fetches_html_with_url(tmp_path):
    """download_assets uses html_url directly when provided — skips list_screens."""
    client = HttpStitchClient(api_key="test-key")
    html_content = b"<html><body>Stitched page</body></html>"

    call_count = [0]

    def single_fetch(req, **kwargs):
        call_count[0] += 1
        mock_resp = MagicMock()
        mock_resp.read.return_value = html_content
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    with patch("urllib.request.urlopen", side_effect=single_fetch):
        result = client.download_assets(
            project_id="12345",
            output_dir=tmp_path / "out",
            html_url="https://stitch.example/dl/html",
        )

    assert result["status"] == "downloaded"
    assert (tmp_path / "out" / "index.html").exists()
    assert (tmp_path / "out" / "index.html").read_bytes() == html_content
    # Only one HTTP call — no list_screens
    assert call_count[0] == 1


def test_http_client_download_assets_fallback_to_list_screens(tmp_path):
    """Without html_url, download_assets falls back to list_screens."""
    client = HttpStitchClient(api_key="test-key")

    list_screens_response = _make_rpc_response({
        "screens": [{
            "htmlCode": {"downloadUrl": "https://stitch.example/dl/html"},
        }]
    })
    html_content = b"<html><body>Stitched page</body></html>"

    call_count = [0]

    def multi_response(req, **kwargs):
        call_count[0] += 1
        mock_resp = MagicMock()
        if call_count[0] == 1:
            mock_resp.read.return_value = list_screens_response
        else:
            mock_resp.read.return_value = html_content
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    with patch("urllib.request.urlopen", side_effect=multi_response):
        result = client.download_assets(project_id="12345", output_dir=tmp_path / "out")

    assert result["status"] == "downloaded"
    assert (tmp_path / "out" / "index.html").exists()
    assert (tmp_path / "out" / "index.html").read_bytes() == html_content
    # Two HTTP calls — list_screens then fetch
    assert call_count[0] == 2


def test_http_client_download_assets_handles_no_html_url(tmp_path):
    client = HttpStitchClient(api_key="test-key")
    response = _make_rpc_response({"screens": []})

    with _mock_urlopen(response):
        result = client.download_assets(project_id="12345", output_dir=tmp_path / "out2")

    assert result["status"] == "no_html_url"


def test_http_client_sends_correct_auth_header():
    client = HttpStitchClient(api_key="my-secret-key")
    captured_headers = {}

    def capture(req, **kwargs):
        captured_headers["X-Goog-Api-Key"] = req.headers.get("X-goog-api-key")
        captured_headers["Content-Type"] = req.headers.get("Content-type")
        mock_resp = MagicMock()
        mock_resp.read.return_value = _make_rpc_response({"projectName": "projects/1"})
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    with patch("urllib.request.urlopen", side_effect=capture):
        client.create_project(title="Auth Test")

    assert captured_headers["X-Goog-Api-Key"] == "my-secret-key"
    assert captured_headers["Content-Type"] == "application/json"


def test_http_client_uses_custom_endpoint():
    client = HttpStitchClient(api_key="key", endpoint="https://custom.example/mcp")
    captured_url = []

    def capture(req, **kwargs):
        captured_url.append(req.full_url)
        mock_resp = MagicMock()
        mock_resp.read.return_value = _make_rpc_response({"projectName": "projects/1"})
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    with patch("urllib.request.urlopen", side_effect=capture):
        client.create_project(title="Endpoint Test")

    assert captured_url[0] == "https://custom.example/mcp"


# ---------------------------------------------------------------------------
# HTML validation tests
# ---------------------------------------------------------------------------

def test_validate_html_rejects_file_below_min_size(tmp_path):
    """HTML under 2000 bytes is treated as retryable (SVG-only)."""
    small_html = tmp_path / "index.html"
    small_html.write_text("<html><body>tiny</body></html>", encoding="utf-8")
    error = StitchAdapter._validate_html(small_html)
    assert error is not None
    assert "only" in error
    assert "bytes" in error
    assert "minimum 2000" in error


def test_validate_html_rejects_non_html_content(tmp_path):
    """Pure SVG (no <html> tag) is rejected even if > 2KB."""
    svg_path = tmp_path / "index.html"
    svg_path.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg">' + ("x" * 3000) + "</svg>",
        encoding="utf-8",
    )
    error = StitchAdapter._validate_html(svg_path)
    assert error is not None
    assert "<!DOCTYPE html>" in error or "<html>" in error


def test_validate_html_accepts_valid_page(tmp_path):
    """Well-formed HTML page > 2KB passes validation."""
    good_path = tmp_path / "index.html"
    good_path.write_text(
        "<!DOCTYPE html><html><body>" + ("x" * 3000) + "</body></html>",
        encoding="utf-8",
    )
    error = StitchAdapter._validate_html(good_path)
    assert error is None


def test_validate_html_accepts_html_without_doctype(tmp_path):
    """HTML with <html> tag (no DOCTYPE) still passes if > 2KB."""
    path = tmp_path / "index.html"
    path.write_text(
        "<html><head></head><body>" + ("x" * 3000) + "</body></html>",
        encoding="utf-8",
    )
    error = StitchAdapter._validate_html(path)
    assert error is None


def test_validate_html_rejects_missing_file(tmp_path):
    """Non-existent file returns validation error."""
    missing = tmp_path / "nonexistent.html"
    error = StitchAdapter._validate_html(missing)
    assert error is not None
    assert "No HTML file" in error


def test_adapter_returns_retryable_error_on_small_html(tmp_path):
    """Adapter returns status='retryable_error' when Stitch returns tiny HTML."""
    class SmallHtmlClient(FakeStitchClient):
        def download_assets(self, *, project_id, output_dir, html_url=None):
            path = Path(output_dir) / "index.html"
            # SVG-only output (~200 bytes)
            path.write_text('<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>', encoding="utf-8")
            return {"status": "downloaded"}

    result = StitchAdapter(SmallHtmlClient()).generate(_request(tmp_path))
    assert result.status == "retryable_error"
    assert any("bytes" in e for e in result.errors)
    assert "stitch_html_too_small" in result.risks
