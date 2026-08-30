"""Phase 05.5 — browser render capture for Phase 05 preview sites."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime

try:  # Python 3.11+ provides the UTC alias; project declares >=3.10
    from datetime import UTC  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover — behavior-identical: datetime.UTC is timezone.utc
    from datetime import timezone

    UTC = timezone.utc
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import unquote, urlsplit

try:
    from pipeline.json_io import write_json
    from pipeline.result_envelope import ResultEnvelope, Status
except ModuleNotFoundError:  # pragma: no cover - CLI fallback
    from packages.pipeline.json_io import write_json
    from packages.pipeline.result_envelope import ResultEnvelope, Status

PHASE_NAME = "phase_05_5_browser_render_capture"
PHASE_SLUG = "05_5_render_capture"
PHASE_05_SLUG = "05_sites"
SAFE_RUN_ID_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?$")
SECRET_VALUE_RE = re.compile(
    r"(?i)\b(token|password|passwd|pwd|secret|api[_-]?key|access[_-]?key|auth|credential)(\s*[:=]\s*)([^\s&;,'\"]+)"
)
ABSOLUTE_LOCAL_PATH_RE = re.compile(r"(?<![A-Za-z0-9_.-])(?:/[A-Za-z0-9._ -]+){2,}")

VIEWPORTS = {
    "desktop": {"width": 1280, "height": 800},
    "mobile": {"width": 390, "height": 844},
}

ARTIFACTS = {
    "desktop_screenshot": "screenshot_desktop.png",
    "mobile_screenshot": "screenshot_mobile.png",
    "render_capture": "render_capture.json",
    "dom_metrics": "dom_metrics.json",
    "asset_load_log": "asset_load_log.json",
    "console_log": "console_log.json",
    "layout_summary": "layout_summary.json",
}


def _path_is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _sanitize_request_url(url: str, *, max_length: int = 240) -> str:
    """Return a safe-to-log URL without secrets, query strings, fragments, or local paths."""
    raw = str(url)
    parsed = urlsplit(raw)
    if parsed.scheme == "file":
        filename = Path(unquote(parsed.path)).name or "[file]"
        sanitized = f"file:///[local-file]/{filename}"
    elif parsed.scheme:
        host = parsed.netloc or "[host]"
        path = ABSOLUTE_LOCAL_PATH_RE.sub("/[local-path]", unquote(parsed.path))
        sanitized = f"{parsed.scheme}://{host}{path}"
    else:
        sanitized = ABSOLUTE_LOCAL_PATH_RE.sub("/[local-path]", raw.split("?", 1)[0].split("#", 1)[0])
    sanitized = SECRET_VALUE_RE.sub(lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]", sanitized)
    if len(sanitized) > max_length:
        return sanitized[: max_length - 1] + "…"
    return sanitized


def _sanitize_log_text(text: str, *, max_length: int = 500) -> str:
    """Redact credential-like values and absolute local paths from log text."""
    sanitized = SECRET_VALUE_RE.sub(lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]", str(text))
    sanitized = ABSOLUTE_LOCAL_PATH_RE.sub("/[local-path]", sanitized)
    sanitized = re.sub(r"file://[^\s)]+", lambda match: _sanitize_request_url(match.group(0)), sanitized)
    if len(sanitized) > max_length:
        return sanitized[: max_length - 1] + "…"
    return sanitized


def _is_file_url_under_site_dir(url: str, site_dir: Path) -> bool:
    """Allow browser loading only for file:// URLs resolving under the approved site dir."""
    parsed = urlsplit(str(url))
    if parsed.scheme != "file":
        return False
    try:
        requested = Path(unquote(parsed.path)).resolve()
        approved_root = site_dir.resolve()
    except (OSError, ValueError):
        return False
    return requested == approved_root or _path_is_relative_to(requested, approved_root)


class CaptureBackend(Protocol):
    """Browser capture backend protocol used by Phase 05.5."""

    def capture(
        self,
        *,
        site_dir: Path,
        output_dir: Path,
        source_url: str,
        viewports: dict[str, dict[str, int]],
    ) -> dict[str, Any]:
        """Capture screenshots and return render telemetry."""
        ...


class PlaywrightCaptureBackend:
    """Playwright-backed browser capture implementation."""

    browser = "playwright-chromium"

    def __init__(self) -> None:
        from playwright.sync_api import sync_playwright

        self._sync_playwright = sync_playwright

    def capture(
        self,
        *,
        site_dir: Path,
        output_dir: Path,
        source_url: str,
        viewports: dict[str, dict[str, int]],
    ) -> dict[str, Any]:
        requests: list[str] = []
        failed_requests: list[dict[str, str]] = []
        blocked_requests: list[dict[str, str]] = []
        console_messages: list[dict[str, str]] = []
        console_errors: list[dict[str, str]] = []

        with self._sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                context = browser.new_context(viewport=viewports["desktop"], java_script_enabled=False)
                page = context.new_page()

                def _route_request(route: Any) -> None:
                    request_url = str(route.request.url)
                    if _is_file_url_under_site_dir(request_url, site_dir):
                        route.continue_()
                        return
                    blocked_requests.append({
                        "url": _sanitize_request_url(request_url),
                        "reason": "blocked_non_local_file_request",
                    })
                    route.abort()

                page.route("**/*", _route_request)
                page.on("request", lambda request: requests.append(_sanitize_request_url(str(request.url))))
                page.on(
                    "requestfailed",
                    lambda request: failed_requests.append({
                        "url": _sanitize_request_url(str(request.url)),
                        "failure": _sanitize_log_text(str(request.failure or "request failed")),
                    }),
                )

                def _record_console(message: Any) -> None:
                    entry = {
                        "type": _sanitize_log_text(str(message.type), max_length=80),
                        "text": _sanitize_log_text(str(message.text)),
                    }
                    console_messages.append(entry)
                    if message.type in {"error", "warning"}:
                        console_errors.append(entry)

                page.on("console", _record_console)
                page.goto(source_url, wait_until="networkidle")
                page.screenshot(path=str(output_dir / ARTIFACTS["desktop_screenshot"]), full_page=True)
                desktop_layout = _layout_for_page(page, viewports["desktop"], ARTIFACTS["desktop_screenshot"])
                page.set_viewport_size(viewports["mobile"])
                page.screenshot(path=str(output_dir / ARTIFACTS["mobile_screenshot"]), full_page=True)
                mobile_layout = _layout_for_page(page, viewports["mobile"], ARTIFACTS["mobile_screenshot"])
                dom_metrics = _dom_metrics_for_page(page)
                stylesheet_count = page.locator('link[rel="stylesheet"]').count()
            finally:
                browser.close()

        return {
            "browser": self.browser,
            "source_url": _sanitize_request_url(source_url),
            "viewports": viewports,
            "dom_metrics": dom_metrics,
            "asset_load_log": {
                "requests": requests,
                "failed_requests": failed_requests,
                "blocked_requests": blocked_requests,
                "stylesheet_count": stylesheet_count,
                "missing_stylesheet": stylesheet_count == 0,
            },
            "console_log": {"messages": console_messages, "errors": console_errors},
            "layout_summary": {"desktop": desktop_layout, "mobile": mobile_layout},
        }


def _layout_for_page(page: Any, viewport: dict[str, int], screenshot_path: str) -> dict[str, Any]:
    overflow = page.evaluate("() => document.documentElement.scrollWidth > window.innerWidth")
    return {
        "viewport": viewport,
        "screenshot_dimensions": _screenshot_dimensions_from_viewport(viewport),
        "screenshot_path": screenshot_path,
        "horizontal_overflow": bool(overflow),
    }


def _dom_metrics_for_page(page: Any) -> dict[str, Any]:
    return page.evaluate(
        r"""
        () => {
          const text = document.body ? document.body.innerText || '' : '';
          const links = Array.from(document.querySelectorAll('a'));
          const images = Array.from(document.images || []);
          const sections = Array.from(document.querySelectorAll('header,nav,main,section,article,footer'));
          const ctas = links.filter((link) => {
            const value = `${link.innerText || ''} ${link.className || ''} ${link.getAttribute('href') || ''}`.toLowerCase();
            return value.includes('call') || value.includes('contact') || value.includes('direction') || value.includes('btn') || value.startsWith('tel:');
          });
          const normalize = (value) => (value || '').toLowerCase().replace(/\s+/g, ' ').trim();
          const labels = Array.from(document.querySelectorAll('h1,h2,h3,h4,h5,h6,a,button')).map((node) => normalize(node.innerText)).filter((value) => value.length >= 4);
          const duplicateTextSignals = labels.length - new Set(labels).size;
          const brokenLinks = links.filter((link) => {
            const href = (link.getAttribute('href') || '').trim();
            if (!href || href === '#') return true;
            if (href.startsWith('#')) {
              try {
                return !document.querySelector(href);
              } catch (_error) {
                return false;
              }
            }
            return false;
          });
          const docHeight = Math.max(document.body ? document.body.scrollHeight : 0, document.documentElement.scrollHeight);
          const docWidth = Math.max(document.body ? document.body.scrollWidth : 0, document.documentElement.scrollWidth);
          const area = Math.max(1, docHeight * docWidth);
          return {
            title: document.title || '',
            heading_count: document.querySelectorAll('h1,h2,h3,h4,h5,h6').length,
            cta_count: ctas.length,
            visible_cta_count: ctas.length,
            link_count: links.length,
            image_count: images.length,
            broken_image_count: images.filter((img) => !img.complete || img.naturalWidth === 0).length,
            broken_link_count: brokenLinks.length,
            visible_text_length: text.length,
            body_word_count: text.trim() ? text.trim().split(/\s+/).length : 0,
            document_height: docHeight,
            document_width: docWidth,
            horizontal_overflow: document.documentElement.scrollWidth > window.innerWidth,
            viewport_overflow: document.documentElement.scrollWidth > window.innerWidth,
            visible_text_density_estimate: text.length / area,
            text_density_estimate: text.length / area,
            section_count: sections.length,
            section_order: sections.map((section) => section.tagName.toLowerCase()),
            duplicate_text_signals: duplicateTextSignals,
          };
        }
        """
    )


def _build_default_backend() -> CaptureBackend | None:
    try:
        backend = PlaywrightCaptureBackend()
        with backend._sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                return backend
            finally:
                browser.close()
    except Exception:  # pragma: no cover - environment-dependent optional dependency
        return None


def _safe_run_context(run_id: str, workspace: Path | str) -> tuple[Path, Path, Path] | dict[str, Any]:
    root = Path(workspace).resolve()
    runs_root = (root / "runs").resolve()
    run_id_parts = re.split(r"[/\\]+", run_id)
    if (
        not SAFE_RUN_ID_RE.fullmatch(run_id)
        or any(part in {".", "..", ""} for part in run_id_parts)
        or run_id in {".", ".."}
    ):
        return ResultEnvelope.blocked(
            phase=PHASE_NAME,
            run_id=run_id,
            missing_fields=["run_id"],
            errors=[
                "Unsafe run_id: use a single segment that starts and ends with a letter or number; dots, underscores, and hyphens are allowed inside"
            ],
        ).to_dict()
    run_root = (runs_root / run_id).resolve()
    if not _path_is_relative_to(run_root, runs_root):
        return ResultEnvelope.blocked(
            phase=PHASE_NAME,
            run_id=run_id,
            missing_fields=["run_id"],
            errors=["Unsafe run_id: resolved run path escapes workspace/runs"],
        ).to_dict()
    return root, run_root, runs_root


def _site_index_paths(sites_root: Path) -> list[Path]:
    safe_indexes: list[Path] = []
    sites_root_resolved = sites_root.resolve()
    for candidate in sorted(sites_root.glob("*/site/index.html")):
        if not candidate.is_file():
            continue
        business_dir = candidate.parent.parent
        try:
            resolved_business = business_dir.resolve()
            resolved_index = candidate.resolve()
        except OSError:
            continue
        if not _path_is_relative_to(resolved_business, sites_root_resolved):
            continue
        if not _path_is_relative_to(resolved_index, sites_root_resolved):
            continue
        safe_indexes.append(candidate)
    return safe_indexes


def _empty_dom_metrics() -> dict[str, Any]:
    return {
        "title": "",
        "heading_count": 0,
        "cta_count": 0,
        "visible_cta_count": 0,
        "link_count": 0,
        "image_count": 0,
        "broken_image_count": 0,
        "broken_link_count": 0,
        "visible_text_length": 0,
        "body_word_count": 0,
        "document_height": 0,
        "document_width": 0,
        "horizontal_overflow": False,
        "viewport_overflow": False,
        "visible_text_density_estimate": 0.0,
        "text_density_estimate": 0.0,
        "section_count": 0,
        "section_order": [],
        "duplicate_text_signals": 0,
    }


def _html_visible_text(html_text: str) -> str:
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", html_text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _tag_texts(html_text: str, tags: str) -> list[str]:
    values: list[str] = []
    for match in re.finditer(rf"<({tags})\b[^>]*>(.*?)</\1>", html_text, flags=re.IGNORECASE | re.DOTALL):
        text = _html_visible_text(match.group(2)).lower()
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) >= 4:
            values.append(text)
    return values


def _duplicate_text_signals_from_html(html_text: str) -> int:
    values = _tag_texts(html_text, r"h[1-6]|a|button")
    return max(0, len(values) - len(set(values)))


def _broken_link_count_from_html(html_text: str) -> int:
    count = 0
    ids = set(re.findall(r"\bid=[\"']([^\"']+)[\"']", html_text, flags=re.IGNORECASE))
    for href in re.findall(r"<a\b[^>]*\bhref=[\"']?([^\"'\s>]+)", html_text, flags=re.IGNORECASE):
        value = href.strip()
        if not value or value == "#" or value.startswith("#") and value[1:] not in ids:
            count += 1
    count += len(re.findall(r"<a\b(?![^>]*\bhref=)", html_text, flags=re.IGNORECASE))
    return count


def _section_order_from_html(html_text: str) -> list[str]:
    return [
        match.group(1).lower()
        for match in re.finditer(r"<(header|nav|main|section|article|footer)\b", html_text, flags=re.IGNORECASE)
    ]


def _screenshot_dimensions_from_viewport(viewport: dict[str, Any]) -> dict[str, int]:
    return {"width": int(viewport.get("width", 0) or 0), "height": int(viewport.get("height", 0) or 0)}


def _text_density_estimate(metrics: dict[str, Any]) -> float:
    visible_text_length = int(metrics.get("visible_text_length", 0) or 0)
    document_width = int(metrics.get("document_width", 0) or 0) or VIEWPORTS["desktop"]["width"]
    document_height = int(metrics.get("document_height", 0) or 0) or VIEWPORTS["desktop"]["height"]
    area = max(1, document_width * document_height)
    return round(visible_text_length / area, 6)


def _basic_dom_metrics_from_html(html_text: str) -> dict[str, Any]:
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html_text, flags=re.IGNORECASE | re.DOTALL)
    body_text = _html_visible_text(html_text)
    section_order = _section_order_from_html(html_text)
    cta_count = len(re.findall(r"<(?:a|button)\b[^>]*(?:btn|call|contact|tel:)", html_text, flags=re.IGNORECASE))
    metrics = _empty_dom_metrics()
    metrics.update({
        "title": re.sub(r"\s+", " ", title_match.group(1)).strip() if title_match else "",
        "heading_count": len(re.findall(r"<h[1-6]\b", html_text, flags=re.IGNORECASE)),
        "cta_count": cta_count,
        "visible_cta_count": cta_count,
        "link_count": len(re.findall(r"<a\b", html_text, flags=re.IGNORECASE)),
        "image_count": len(re.findall(r"<img\b", html_text, flags=re.IGNORECASE)),
        "broken_link_count": _broken_link_count_from_html(html_text),
        "visible_text_length": len(body_text),
        "body_word_count": len(body_text.split()) if body_text else 0,
        "section_count": len(section_order),
        "section_order": section_order,
        "duplicate_text_signals": _duplicate_text_signals_from_html(html_text),
    })
    metrics["visible_text_density_estimate"] = _text_density_estimate(metrics)
    metrics["text_density_estimate"] = metrics["visible_text_density_estimate"]
    return metrics


def _normalize_dom_metric_contract(metrics: dict[str, Any]) -> dict[str, Any]:
    metrics["visible_cta_count"] = int(metrics.get("visible_cta_count", metrics.get("cta_count", 0)) or 0)
    metrics["cta_count"] = int(metrics.get("cta_count", metrics["visible_cta_count"]) or 0)
    metrics["section_order"] = list(metrics.get("section_order", []) or [])
    metrics["section_count"] = int(metrics.get("section_count", len(metrics["section_order"])) or 0)
    metrics["duplicate_text_signals"] = int(metrics.get("duplicate_text_signals", 0) or 0)
    metrics["broken_link_count"] = int(metrics.get("broken_link_count", 0) or 0)
    metrics["viewport_overflow"] = bool(metrics.get("viewport_overflow", metrics.get("horizontal_overflow", False)))
    metrics["horizontal_overflow"] = bool(metrics.get("horizontal_overflow", metrics["viewport_overflow"]))
    metrics["visible_text_density_estimate"] = float(
        metrics.get("visible_text_density_estimate", metrics.get("text_density_estimate", _text_density_estimate(metrics)))
    )
    metrics["text_density_estimate"] = float(metrics.get("text_density_estimate", metrics["visible_text_density_estimate"]))
    return metrics


def _normalize_layout_summary(layout_summary: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(layout_summary)
    for name, viewport in VIEWPORTS.items():
        current = dict(normalized.get(name, {}) or {})
        current.setdefault("viewport", viewport)
        current.setdefault("screenshot_path", ARTIFACTS[f"{name}_screenshot"])
        current.setdefault("screenshot_dimensions", _screenshot_dimensions_from_viewport(current["viewport"]))
        current.setdefault("horizontal_overflow", False)
        normalized[name] = current
    return normalized


def _sanitize_failed_request(entry: Any) -> dict[str, str]:
    if isinstance(entry, dict):
        return {
            "url": _sanitize_request_url(str(entry.get("url", ""))),
            "failure": _sanitize_log_text(str(entry.get("failure", "request failed"))),
        }
    return {"url": _sanitize_request_url(str(entry)), "failure": "request failed"}


def _sanitize_console_entry(entry: Any) -> dict[str, str]:
    if isinstance(entry, dict):
        return {
            "type": _sanitize_log_text(str(entry.get("type", "log")), max_length=80),
            "text": _sanitize_log_text(str(entry.get("text", ""))),
        }
    return {"type": "log", "text": _sanitize_log_text(str(entry))}


def _normalize_capture_payload(payload: dict[str, Any], site_dir: Path, source_url: str) -> dict[str, Any]:
    html_text = (site_dir / "index.html").read_text(encoding="utf-8")
    dom_metrics = _normalize_dom_metric_contract({**_basic_dom_metrics_from_html(html_text), **payload.get("dom_metrics", {})})
    raw_asset_load_log = payload.get("asset_load_log", {})
    asset_load_log = {
        "requests": [_sanitize_request_url(str(url)) for url in raw_asset_load_log.get("requests", [])],
        "failed_requests": [_sanitize_failed_request(entry) for entry in raw_asset_load_log.get("failed_requests", [])],
        "blocked_requests": [_sanitize_failed_request(entry) for entry in raw_asset_load_log.get("blocked_requests", [])],
        "stylesheet_count": raw_asset_load_log.get(
            "stylesheet_count",
            len(re.findall(r"<link\b[^>]*rel=[\"']?stylesheet", html_text, flags=re.IGNORECASE)),
        ),
        "missing_stylesheet": raw_asset_load_log.get("missing_stylesheet", "stylesheet" not in html_text.lower()),
    }
    dom_metrics["missing_stylesheet"] = bool(asset_load_log["missing_stylesheet"])
    raw_console_log = payload.get("console_log", {})
    console_log = {
        "messages": [_sanitize_console_entry(entry) for entry in raw_console_log.get("messages", [])],
        "errors": [_sanitize_console_entry(entry) for entry in raw_console_log.get("errors", [])],
    }
    layout_summary = _normalize_layout_summary({
        "desktop": {
            "viewport": VIEWPORTS["desktop"],
            "screenshot_path": ARTIFACTS["desktop_screenshot"],
            "screenshot_dimensions": _screenshot_dimensions_from_viewport(VIEWPORTS["desktop"]),
            "horizontal_overflow": bool(dom_metrics.get("horizontal_overflow", False)),
        },
        "mobile": {
            "viewport": VIEWPORTS["mobile"],
            "screenshot_path": ARTIFACTS["mobile_screenshot"],
            "screenshot_dimensions": _screenshot_dimensions_from_viewport(VIEWPORTS["mobile"]),
            "horizontal_overflow": bool(dom_metrics.get("horizontal_overflow", False)),
        },
        **payload.get("layout_summary", {}),
    })
    return {
        "browser": payload.get("browser", "unknown"),
        "source_url": _sanitize_request_url(str(payload.get("source_url", source_url))),
        "viewports": payload.get("viewports", VIEWPORTS),
        "dom_metrics": dom_metrics,
        "asset_load_log": asset_load_log,
        "console_log": console_log,
        "layout_summary": layout_summary,
    }


def _relative_run_path(run_id: str, *parts: str) -> str:
    return "/".join(["runs", run_id, *parts])


def _write_blocked_result(
    *,
    run_id: str,
    output_root: Path,
    missing_fields: list[str],
    errors: list[str],
    inputs_used: list[str] | None = None,
) -> dict[str, Any]:
    result = ResultEnvelope.blocked(
        phase=PHASE_NAME,
        run_id=run_id,
        missing_fields=missing_fields,
        errors=errors,
        inputs_used=inputs_used or [],
    ).to_dict()
    write_json(str(output_root / "result.json"), result)
    return result


def _blocked_result_without_write(
    *,
    run_id: str,
    missing_fields: list[str],
    errors: list[str],
    inputs_used: list[str] | None = None,
) -> dict[str, Any]:
    """Return a blocked envelope when the configured output path is unsafe to write."""
    return ResultEnvelope.blocked(
        phase=PHASE_NAME,
        run_id=run_id,
        missing_fields=missing_fields,
        errors=errors,
        inputs_used=inputs_used or [],
    ).to_dict()


def run_phase_05_5(
    run_id: str,
    workspace: Path | str,
    capture_backend: CaptureBackend | None = None,
) -> dict[str, Any]:
    """Capture real browser render artifacts for every Phase 05 generated site."""
    context = _safe_run_context(run_id, workspace)
    if isinstance(context, dict):
        return context
    _root, run_root, _runs_root = context
    sites_root = run_root / PHASE_05_SLUG
    output_root = run_root / PHASE_SLUG
    try:
        resolved_output_root = output_root.resolve()
        resolved_run_root = run_root.resolve()
    except OSError:
        return _blocked_result_without_write(
            run_id=run_id,
            missing_fields=[PHASE_SLUG],
            errors=["Unsafe 05_5_render_capture path: unable to resolve output directory"],
        )
    if output_root.is_symlink() or not _path_is_relative_to(resolved_output_root, resolved_run_root):
        return _blocked_result_without_write(
            run_id=run_id,
            missing_fields=[PHASE_SLUG],
            errors=["Unsafe 05_5_render_capture path: resolved directory must stay under the run root and cannot be a symlink"],
        )
    output_root.mkdir(parents=True, exist_ok=True)

    if not sites_root.exists():
        return _write_blocked_result(
            run_id=run_id,
            output_root=output_root,
            missing_fields=[PHASE_05_SLUG],
            errors=["Phase 05 sites required before Phase 05.5"],
        )

    try:
        resolved_sites_root = sites_root.resolve()
        resolved_run_root = run_root.resolve()
    except OSError:
        return _write_blocked_result(
            run_id=run_id,
            output_root=output_root,
            missing_fields=[PHASE_05_SLUG],
            errors=["Unsafe 05_sites path: unable to resolve Phase 05 sites directory"],
        )

    if sites_root.is_symlink() or not _path_is_relative_to(resolved_sites_root, resolved_run_root):
        return _write_blocked_result(
            run_id=run_id,
            output_root=output_root,
            missing_fields=[PHASE_05_SLUG],
            errors=["Unsafe 05_sites path: resolved directory must stay under the run root and cannot be a symlink"],
        )

    site_indexes = _site_index_paths(sites_root)
    if not site_indexes:
        return _write_blocked_result(
            run_id=run_id,
            output_root=output_root,
            missing_fields=["business site/index.html"],
            errors=["No business site/index.html files found in Phase 05 outputs"],
            inputs_used=[_relative_run_path(run_id, PHASE_05_SLUG)],
        )

    backend = capture_backend if capture_backend is not None else _build_default_backend()
    if backend is None:
        return _write_blocked_result(
            run_id=run_id,
            output_root=output_root,
            missing_fields=["capture_backend"],
            errors=["No browser capture backend available"],
            inputs_used=[_relative_run_path(run_id, PHASE_05_SLUG)],
        )

    outputs_created: list[str] = []
    inputs_used = [_relative_run_path(run_id, PHASE_05_SLUG)]
    errors: list[str] = []
    records_created = 0

    for index_path in site_indexes:
        site_dir = index_path.parent
        business_dir = site_dir.parent
        business_slug = business_dir.name
        source_url = index_path.resolve().as_uri()
        try:
            payload = _normalize_capture_payload(
                backend.capture(
                    site_dir=site_dir,
                    output_dir=business_dir,
                    source_url=source_url,
                    viewports=VIEWPORTS,
                ),
                site_dir,
                source_url,
            )
            capture_errors: list[str] = []
            capture_status = "done"
            records_created += 1
        except Exception as exc:  # pragma: no cover - defensive handling
            payload = _normalize_capture_payload({}, site_dir, source_url)
            capture_errors = [_sanitize_log_text(f"{business_slug}: {exc.__class__.__name__}: {exc}")]
            capture_status = "failed"
            errors.extend(capture_errors)

        render_capture = {
            "run_id": run_id,
            "record_id": business_slug,
            "business_slug": business_slug,
            "desktop_screenshot_path": ARTIFACTS["desktop_screenshot"],
            "mobile_screenshot_path": ARTIFACTS["mobile_screenshot"],
            "dom_metrics": payload["dom_metrics"],
            "asset_load_log": payload["asset_load_log"],
            "console_log": payload["console_log"],
            "layout_summary": payload["layout_summary"],
            "render_timestamp": datetime.now(UTC).isoformat(),
            "capture_status": capture_status,
            "capture_mode": "browser" if capture_status == "done" else "failed",
            "browser": payload["browser"],
            "source_url": payload["source_url"],
            "viewports": payload["viewports"],
            "screenshot_dimensions": {
                "desktop": payload["layout_summary"]["desktop"]["screenshot_dimensions"],
                "mobile": payload["layout_summary"]["mobile"]["screenshot_dimensions"],
            },
            "artifacts": ARTIFACTS,
            "errors": capture_errors,
        }
        write_json(str(business_dir / ARTIFACTS["render_capture"]), render_capture)
        write_json(str(business_dir / ARTIFACTS["dom_metrics"]), payload["dom_metrics"])
        write_json(str(business_dir / ARTIFACTS["asset_load_log"]), payload["asset_load_log"])
        write_json(str(business_dir / ARTIFACTS["console_log"]), payload["console_log"])
        write_json(str(business_dir / ARTIFACTS["layout_summary"]), payload["layout_summary"])

        for artifact_path in ARTIFACTS.values():
            outputs_created.append(_relative_run_path(run_id, PHASE_05_SLUG, business_slug, artifact_path))

    outputs_created.append(_relative_run_path(run_id, PHASE_SLUG, "result.json"))
    status = Status.DONE if not errors else Status.FAILED
    result = ResultEnvelope(
        phase=PHASE_NAME,
        status=status,
        run_id=run_id,
        inputs_used=inputs_used,
        outputs_created=outputs_created,
        records_processed=len(site_indexes),
        records_created=records_created,
        records_skipped=len(site_indexes) - records_created,
        decisions=[f"Captured browser render artifacts for {records_created} Phase 05 site(s)"],
        risks=[] if not errors else ["One or more browser render captures failed"],
        errors=errors,
        next_tasks=["Phase 06 — Quality Gate"],
    ).model_dump(exclude_none=True, by_alias=True)
    write_json(str(output_root / "result.json"), result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 05.5 — Browser Render Capture")
    parser.add_argument("--run-id", default="fixture_001", help="Run ID (default: fixture_001)")
    parser.add_argument("--project-root", default=".", help="Project root (default: current directory)")
    args = parser.parse_args()

    result = run_phase_05_5(args.run_id, args.project_root)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
