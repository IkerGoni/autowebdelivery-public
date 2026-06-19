"""Injected Stitch generation adapter for premium website previews."""

from __future__ import annotations

import json
import logging
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol

logger = logging.getLogger(__name__)

STITCH_MCP_ENDPOINT = "https://stitch.googleapis.com/mcp"
STITCH_API_KEY_ENV = "STITCH_API_KEY"


class StitchClient(Protocol):
    """Protocol implemented by fake, MCP-backed, or mcporter-backed Stitch clients."""

    def create_project(self, *, title: str) -> dict[str, Any]: ...

    def generate_screen_from_text(
        self,
        *,
        project_id: str,
        prompt: str,
        design_system: str | None = None,
        device_type: str = "DESKTOP",
        model_id: str | None = None,
    ) -> dict[str, Any]: ...

    def list_screens(self, *, project_id: str) -> dict[str, Any]: ...

    def get_project(self, *, project_id: str) -> dict[str, Any]: ...

    def get_screen(self, *, project_id: str, screen_id: str) -> dict[str, Any]: ...

    def download_assets(
        self, *, project_id: str, output_dir: Path | str, html_url: str | None = None
    ) -> dict[str, Any]: ...


@dataclass(frozen=True)
class StitchGenerationRequest:
    run_id: str
    record_id: str
    business_slug: str
    business_name: str
    prompt: str
    prompt_contract: dict[str, Any]
    output_dir: Path
    project_title: str
    project_id: str | None = None
    design_system: str | None = None
    device_type: str = "MOBILE"
    model_id: str = "GEMINI_3_1_PRO"
    adapter_mode: str = "injected"


@dataclass(frozen=True)
class StitchGenerationResult:
    status: str
    run_id: str
    record_id: str
    business_slug: str
    project_id: str | None
    screen_id: str | None
    design_system: str | None
    downloaded_assets_dir: str | None
    html_path: str | None
    screenshot_url: str | None
    html_download_url: str | None
    outputs_created: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CommandResult:
    exit_code: int
    stdout: str
    stderr: str = ""


class CommandRunner(Protocol):
    def run(self, args: list[str], cwd: Path | None = None, timeout: int | None = None) -> CommandResult: ...


def _sanitize_error(error: Exception) -> str:
    text = str(error).replace("\n", " ").strip()
    for marker in ("STITCH_API_KEY", "token", "api_key", "apikey", "authorization", "bearer", "secret", "password"):
        lowered = text.lower()
        index = lowered.find(marker.lower())
        while index != -1:
            text = text[:index] + f"[redacted:{marker}]" + text[index + len(marker):]
            # Skip past the replacement to avoid finding marker inside [redacted:...]
            lowered = text.lower()
            index = lowered.find(marker.lower(), index + len(marker) + 20)
    return text[:500] or error.__class__.__name__


def _extract_id(payload: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value.split("/")[-1]
    name = payload.get("name")
    if isinstance(name, str) and "/" in name:
        return name.split("/")[-1]
    return None


def _extract_download_urls(screen: dict[str, Any]) -> tuple[str | None, str | None]:
    html_url = None
    screenshot_url = None
    # Stitch returns data in structuredContent for get_screen responses
    sc = screen.get("structuredContent", {}) or screen
    html = sc.get("htmlCode") or sc.get("html_code") or screen.get("htmlCode") or screen.get("html_code") or {}
    screenshot = sc.get("screenshot") or screen.get("screenshot") or {}
    if isinstance(html, dict):
        html_url = html.get("downloadUrl") or html.get("download_url")
    if isinstance(screenshot, dict):
        screenshot_url = screenshot.get("downloadUrl") or screenshot.get("download_url")
    return html_url, screenshot_url


def _extract_screen_from_response(response: dict[str, Any]) -> dict[str, Any] | None:
    """Extract the generated screen from a generate_screen_from_text response.

    Screens live in structuredContent.outputComponents[i].design.screens[0].
    The MCP response wraps data in structuredContent, not at top-level.
    """
    # Try structuredContent.outputComponents (MCP wrapper format)
    sc = response.get("structuredContent", {})
    for comp in sc.get("outputComponents", []):
        if not isinstance(comp, dict):
            continue
        design = comp.get("design")
        if isinstance(design, dict):
            screens = design.get("screens", [])
            if screens and isinstance(screens, list) and screens[0]:
                return screens[0]
    # Fallback: try response.outputComponents directly
    for comp in response.get("outputComponents", []):
        if not isinstance(comp, dict):
            continue
        design = comp.get("design")
        if isinstance(design, dict):
            screens = design.get("screens", [])
            if screens and isinstance(screens, list) and screens[0]:
                return screens[0]
    return None


class StitchAdapter:
    """Premium Stitch adapter — extracts screen inline from generate_screen_from_text.

    Generation flow:
      1. Create project (if no project_id provided)
      2. Call generate_screen_from_text — returns screen in outputComponents[].design.screens[0]
      3. Extract screen inline (no polling needed)
      4. Download HTML + screenshot
    """

    def __init__(self, client: StitchClient) -> None:
        self.client = client

    def generate(self, request: StitchGenerationRequest) -> StitchGenerationResult:
        outputs: list[str] = []
        try:
            request.output_dir.mkdir(parents=True, exist_ok=True)
            project_id = request.project_id
            if not project_id:
                created = self.client.create_project(title=request.project_title)
                project_id = _extract_id(created, ("project_id", "projectId", "id", "name"))
            if not project_id:
                raise RuntimeError("Stitch project id missing")

            # Step 1: generate the screen (inline screen in outputComponents, ~90s)
            logger.info("Calling generate_screen_from_text...")
            gen_response = self.client.generate_screen_from_text(
                project_id=project_id,
                prompt=request.prompt,
                design_system=request.design_system,
                device_type=request.device_type,
                model_id=request.model_id,
            )

            # Step 2: extract screen from inline response
            screen = _extract_screen_from_response(gen_response)
            if not screen:
                raise RuntimeError(
                    "No screen found in generate_screen_from_text response. "
                    "Stitch returned outputComponents but no design.screens entry."
                )

            screen_id = _extract_id(screen, ("name", "id", "screenId"))
            html_url, screenshot_url = _extract_download_urls(screen)

            # Step 3: download HTML
            downloaded = self.client.download_assets(
                project_id=project_id, output_dir=request.output_dir, html_url=html_url
            )
            html_path = self._find_html_path(request.output_dir)

            # Step 4: validate HTML is a real page (not SVG-only junk)
            validation_error = self._validate_html(html_path)
            if validation_error:
                logger.warning("HTML validation failed: %s", validation_error)
                return StitchGenerationResult(
                    status="retryable_error",
                    run_id=request.run_id,
                    record_id=request.record_id,
                    business_slug=request.business_slug,
                    project_id=project_id,
                    screen_id=screen_id,
                    design_system=request.design_system,
                    downloaded_assets_dir=str(request.output_dir),
                    html_path=str(html_path) if html_path else None,
                    screenshot_url=screenshot_url,
                    html_download_url=html_url,
                    outputs_created=outputs,
                    errors=[validation_error],
                    risks=["stitch_html_too_small"],
                )

            metadata = {
                "run_id": request.run_id,
                "record_id": request.record_id,
                "business_slug": request.business_slug,
                "business_name": request.business_name,
                "generation_mode": "premium_stitch",
                "adapter_mode": request.adapter_mode,
                "project_id": project_id,
                "screen_id": screen_id,
                "design_system": request.design_system,
                "device_type": request.device_type,
                "model_id": request.model_id,
                "html_download_url": html_url,
                "screenshot_url": screenshot_url,
                "downloaded_assets_dir": str(request.output_dir),
                "download_response": downloaded,
            }
            outputs.extend(self.write_metadata(request=request, result_metadata=metadata))
            return StitchGenerationResult(
                status="done",
                run_id=request.run_id,
                record_id=request.record_id,
                business_slug=request.business_slug,
                project_id=project_id,
                screen_id=screen_id,
                design_system=request.design_system,
                downloaded_assets_dir=str(request.output_dir),
                html_path=str(html_path) if html_path else None,
                screenshot_url=screenshot_url,
                html_download_url=html_url,
                outputs_created=outputs,
                metadata=metadata,
            )
        except Exception as error:  # noqa: BLE001
            return StitchGenerationResult(
                status="failed",
                run_id=request.run_id,
                record_id=request.record_id,
                business_slug=request.business_slug,
                project_id=request.project_id,
                screen_id=None,
                design_system=request.design_system,
                downloaded_assets_dir=str(request.output_dir),
                html_path=None,
                screenshot_url=None,
                html_download_url=None,
                outputs_created=outputs,
                errors=[_sanitize_error(error)],
                risks=["premium_stitch_generation_failed"],
            )

    # Minimum size (bytes) for a valid full HTML page.
    # Stitch sometimes returns SVG-only output (~383 bytes) instead of a full
    # page (~18 KB).  Anything under this threshold is treated as retryable.
    MIN_HTML_SIZE = 2000

    def _find_html_path(self, output_dir: Path) -> Path | None:
        candidates = [output_dir / "index.html", output_dir / "site" / "index.html"]
        candidates.extend(sorted(output_dir.rglob("*.html")))
        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                return candidate
        return None

    @staticmethod
    def _validate_html(html_path: Path | None) -> str | None:
        """Return an error string if *html_path* fails validation, else ``None``.

        A valid page must:
        * exist and be larger than ``MIN_HTML_SIZE`` bytes; and
        * contain ``<!DOCTYPE html>`` or ``<html`` (case-insensitive).
        """
        if html_path is None or not html_path.exists():
            return "No HTML file found in downloaded assets"
        content_bytes = html_path.read_bytes()
        if len(content_bytes) < StitchAdapter.MIN_HTML_SIZE:
            return (
                f"Downloaded HTML is only {len(content_bytes)} bytes "
                f"(minimum {StitchAdapter.MIN_HTML_SIZE}) — "
                "likely SVG-only output from Stitch"
            )
        text = content_bytes.decode("utf-8", errors="replace").lower()
        if "<!doctype html" not in text and "<html" not in text:
            return (
                "Downloaded HTML does not contain <!DOCTYPE html> or <html> — "
                "likely not a full HTML page"
            )
        return None

    def write_metadata(self, *, request: StitchGenerationRequest, result_metadata: dict[str, Any]) -> list[str]:
        metadata_path = request.output_dir / "stitch_generation_metadata.json"
        contract_path = request.output_dir / "stitch_prompt_contract.json"
        metadata_path.write_text(json.dumps(result_metadata, indent=2, sort_keys=True), encoding="utf-8")
        contract_path.write_text(json.dumps(request.prompt_contract, indent=2, sort_keys=True), encoding="utf-8")
        return [str(metadata_path), str(contract_path)]


class McpStitchClient:
    """Thin wrapper around injected MCP tool callables."""

    def __init__(
        self,
        *,
        create_project: Callable[..., dict[str, Any]],
        generate_screen_from_text: Callable[..., dict[str, Any]],
        list_screens: Callable[..., dict[str, Any]],
        get_project: Callable[..., dict[str, Any]],
        get_screen: Callable[..., dict[str, Any]],
        download_assets: Callable[..., dict[str, Any]],
    ) -> None:
        self._create_project = create_project
        self._generate_screen_from_text = generate_screen_from_text
        self._list_screens = list_screens
        self._get_project = get_project
        self._get_screen = get_screen
        self._download_assets = download_assets

    def create_project(self, *, title: str) -> dict[str, Any]:
        return self._create_project(title=title)

    def generate_screen_from_text(
        self,
        *,
        project_id: str,
        prompt: str,
        design_system: str | None = None,
        device_type: str = "DESKTOP",
        model_id: str | None = None,
    ) -> dict[str, Any]:
        return self._generate_screen_from_text(
            projectId=project_id,
            prompt=prompt,
            designSystem=design_system,
            deviceType=device_type,
            modelId=model_id,
        )

    def list_screens(self, *, project_id: str) -> dict[str, Any]:
        return self._list_screens(projectId=project_id)

    def get_project(self, *, project_id: str) -> dict[str, Any]:
        return self._get_project(name=f"projects/{project_id}")

    def get_screen(self, *, project_id: str, screen_id: str) -> dict[str, Any]:
        return self._get_screen(
            name=f"projects/{project_id}/screens/{screen_id}",
            projectId=project_id,
            screenId=screen_id,
        )

    def download_assets(
        self, *, project_id: str, output_dir: Path | str, html_url: str | None = None
    ) -> dict[str, Any]:
        return self._download_assets(projectId=project_id, outputDir=str(output_dir))


class McporterStitchClient:
    """mcporter fallback client using an injected command runner."""

    def __init__(
        self,
        *,
        runner: CommandRunner,
        config_path: Path | None = None,
        timeout_seconds: int = 300,
        command: tuple[str, ...] = ("mcporter",),
    ) -> None:
        self.runner = runner
        self.config_path = config_path
        self.timeout_seconds = timeout_seconds
        self.command = command

    def _call(self, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        command = [*self.command]
        if self.config_path:
            command.extend(["--config", str(self.config_path)])
        command.extend(["call", f"stitch.{tool_name}", "--args", json.dumps(args), "--output", "json"])
        result = self.runner.run(command, timeout=self.timeout_seconds)
        if result.exit_code != 0:
            raise RuntimeError(result.stderr or result.stdout or f"mcporter {tool_name} failed")
        return json.loads(result.stdout or "{}")

    def create_project(self, *, title: str) -> dict[str, Any]:
        return self._call("create_project", {"title": title})

    def generate_screen_from_text(
        self,
        *,
        project_id: str,
        prompt: str,
        design_system: str | None = None,
        device_type: str = "DESKTOP",
        model_id: str | None = None,
    ) -> dict[str, Any]:
        args = {"projectId": project_id, "prompt": prompt, "deviceType": device_type}
        if design_system:
            args["designSystem"] = design_system
        if model_id:
            args["modelId"] = model_id
        return self._call("generate_screen_from_text", args)

    def list_screens(self, *, project_id: str) -> dict[str, Any]:
        return self._call("list_screens", {"projectId": project_id})

    def get_project(self, *, project_id: str) -> dict[str, Any]:
        return self._call("get_project", {"name": f"projects/{project_id}"})

    def get_screen(self, *, project_id: str, screen_id: str) -> dict[str, Any]:
        return self._call(
            "get_screen",
            {"name": f"projects/{project_id}/screens/{screen_id}", "projectId": project_id, "screenId": screen_id},
        )

    def download_assets(
        self, *, project_id: str, output_dir: Path | str, html_url: str | None = None
    ) -> dict[str, Any]:
        return self._call("download_assets", {"projectId": project_id, "outputDir": str(output_dir)})


class HttpStitchClient:
    """HTTP JSON-RPC 2.0 client for the Stitch MCP endpoint.

    Calls ``https://stitch.googleapis.com/mcp`` directly — no mcporter or
    MCP SDK required.  Implements the ``StitchClient`` protocol.
    """

    def __init__(
        self,
        *,
        api_key: str,
        endpoint: str = STITCH_MCP_ENDPOINT,
        timeout: int = 300,
    ) -> None:
        self._api_key = api_key
        self._endpoint = endpoint
        self._timeout = timeout

    # -- internal helpers ---------------------------------------------------

    def _rpc(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Send a JSON-RPC 2.0 call and return the ``result`` payload."""
        payload: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": id(self),  # unique per-instance; server does not require monotonic
            "method": method,
        }
        if params:
            payload["params"] = params

        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self._endpoint,
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": self._api_key,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Stitch MCP HTTP {exc.code}: {raw[:300]}") from exc

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Stitch MCP bad JSON: {raw[:300]}") from exc

        if "error" in data:
            err = data["error"]
            raise RuntimeError(f"Stitch MCP error: {err.get('message', str(err))}")
        
        result_data = data.get("result", {})
        # MCP returns JSON string in content[0].text for some calls
        # Only parse if structuredContent doesn't have outputComponents
        if "content" in result_data and isinstance(result_data.get("content"), list):
            has_structured_oc = (
                result_data.get("structuredContent")
                and isinstance(result_data["structuredContent"], dict)
                and "outputComponents" in result_data["structuredContent"]
            )
            if not has_structured_oc:
                content = result_data["content"]
                if content and isinstance(content[0], dict) and "text" in content[0]:
                    try:
                        parsed = json.loads(content[0]["text"])
                        if isinstance(parsed, dict):
                            # Preserve original structuredContent if present
                            orig_sc = result_data.get("structuredContent")
                            if orig_sc:
                                parsed["structuredContent"] = orig_sc
                            result_data = parsed
                    except (json.JSONDecodeError, IndexError):
                        pass
        return result_data

    def _fetch_url(self, url: str, dest: Path) -> None:
        """Download a file from *url* to *dest*."""
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=self._timeout) as resp:
            dest.write_bytes(resp.read())

    # -- StitchClient protocol ----------------------------------------------

    def create_project(self, *, title: str) -> dict[str, Any]:
        result = self._rpc(
            "tools/call",
            {
                "name": "create_project",
                "arguments": {"title": title},
            },
        )
        # Stitch returns result with structuredContent.name = "projects/12345"
        structured = result.get("structuredContent", {})
        project_name = structured.get("name", "")
        project_id = project_name.split("/")[-1] if "/" in project_name else project_name
        return {"project_id": project_id, "projectName": project_name}

    def generate_screen_from_text(
        self,
        *,
        project_id: str,
        prompt: str,
        design_system: str | None = None,
        device_type: str = "DESKTOP",
        model_id: str | None = None,
    ) -> dict[str, Any]:
        arguments: dict[str, Any] = {
            "projectId": project_id,
            "prompt": prompt,
            "deviceType": device_type,
        }
        if design_system:
            arguments["designSystem"] = design_system
        if model_id:
            arguments["modelId"] = model_id

        return self._rpc(
            "tools/call",
            {"name": "generate_screen_from_text", "arguments": arguments},
        )

    def get_project(self, *, project_id: str) -> dict[str, Any]:
        return self._rpc(
            "tools/call",
            {"name": "get_project", "arguments": {"name": f"projects/{project_id}"}},
        )

    def get_screen(self, *, project_id: str, screen_id: str) -> dict[str, Any]:
        result = self._rpc(
            "tools/call",
            {
                "name": "get_screen",
                "arguments": {
                    "name": f"projects/{project_id}/screens/{screen_id}",
                    "projectId": project_id,
                    "screenId": screen_id,
                },
            },
        )
        return result

    def list_screens(self, *, project_id: str) -> dict[str, Any]:
        """List screens in a project."""
        return self._rpc(
            "tools/call",
            {"name": "list_screens", "arguments": {"projectId": project_id}},
        )

    def download_assets(
        self, *, project_id: str, output_dir: Path | str, html_url: str | None = None
    ) -> dict[str, Any]:
        """Fetch the HTML via the downloadUrl and save to *output_dir*."""
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        # If caller already provides the download URL from get_screen, use it directly
        if not html_url:
            try:
                screens = self._rpc(
                    "tools/call",
                    {"name": "list_screens", "arguments": {"projectId": project_id}},
                )
                items = screens.get("screens", []) or screens.get("items", [])
                if items and isinstance(items, list):
                    latest = items[-1] if isinstance(items[-1], dict) else {}
                    html = latest.get("htmlCode") or latest.get("html_code") or {}
                    if isinstance(html, dict):
                        html_url = html.get("downloadUrl") or html.get("download_url")
            except Exception as exc:
                logger.warning("HttpStitchClient list_screens fallback failed: %s", exc)

        status = "no_html_url"
        if html_url:
            dest = out / "index.html"
            try:
                self._fetch_url(html_url, dest)
                status = "downloaded"
            except Exception as exc:
                logger.warning("HttpStitchClient download failed: %s", exc)
                status = f"download_failed: {exc}"

        return {"status": status, "path": str(out), "html_url": html_url}
