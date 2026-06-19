"""Phase 07 — local-only deployment for preview sites."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    from pipeline.json_io import read_json, write_json
    from pipeline.result_envelope import ResultEnvelope
    from deployers.local_only import deploy_local_site
except ModuleNotFoundError:  # pragma: no cover - CLI fallback
    from packages.pipeline.json_io import read_json, write_json
    from packages.pipeline.result_envelope import ResultEnvelope
    from packages.deployers.local_only import deploy_local_site

PHASE_NAME = "phase_07_deployment"
PHASE_SLUG = "07_deployments"
DEFAULT_TAKEDOWN_AFTER_DAYS = 30


def _utc_now_dt() -> datetime:
    return datetime.now(timezone.utc)


def _iso_due_at(days: int) -> str:
    return (_utc_now_dt() + timedelta(days=days)).isoformat()


def _write_log(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _read_public_url_manifest(deploy_dir: Path) -> dict[str, dict[str, Any]]:
    manifest_path = deploy_dir / "public_url_manifest.json"
    if not manifest_path.exists():
        return {}

    manifest = read_json(str(manifest_path))
    raw_urls = manifest
    if isinstance(manifest, dict):
        raw_urls = manifest.get("public_urls", manifest)
    if isinstance(raw_urls, dict):
        return {
            str(slug): {"preview_url": str(url), "provider": "manual_manifest", "verified_at": "", "http_status": 0}
            for slug, url in raw_urls.items()
            if url
        }
    if isinstance(raw_urls, list):
        urls: dict[str, dict[str, Any]] = {}
        for item in raw_urls:
            if not isinstance(item, dict):
                continue
            slug = item.get("business_slug") or item.get("slug")
            url = item.get("preview_url") or item.get("public_url") or item.get("url")
            if slug and url:
                urls[str(slug)] = {
                    "preview_url": str(url),
                    "provider": str(item.get("provider") or "manual_manifest"),
                    "verified_at": str(item.get("verified_at") or ""),
                    "http_status": item.get("http_status") or 0,
                }
        return urls
    return {}


def _preview_metadata(preview_url: str, public_url_source: str) -> dict[str, Any]:
    preview_url_type = "missing"
    if preview_url.startswith("https://"):
        preview_url_type = "public_https"
    elif preview_url.startswith("file://"):
        preview_url_type = "local_file"

    return {
        "preview_url_type": preview_url_type,
        "public_url_source": public_url_source,
        "outward_send_allowed": public_url_source in {"manual_manifest", "provider"} and preview_url.startswith("https://"),
    }


def run_phase_07(run_id: str, workspace: str) -> dict[str, Any]:
    root = Path(workspace)
    sites_dir = root / "runs" / run_id / "05_sites"
    quality_dir = root / "runs" / run_id / "06_quality"

    missing_fields: list[str] = []
    if not sites_dir.exists():
        missing_fields.append("runs/{run_id}/05_sites")
    if not quality_dir.exists():
        missing_fields.append("runs/{run_id}/06_quality")
    if missing_fields:
        return ResultEnvelope.blocked(
            phase=PHASE_NAME,
            run_id=run_id,
            missing_fields=missing_fields,
            errors=["Phase 05 sites and Phase 06 quality outputs required before Phase 07"],
            inputs_used=[],
        ).to_dict()

    deploy_dir = root / "runs" / run_id / PHASE_SLUG
    deploy_dir.mkdir(parents=True, exist_ok=True)
    public_url_manifest = _read_public_url_manifest(deploy_dir)

    deployments: list[dict[str, Any]] = []
    live_count = 0
    skipped_count = 0
    failed_count = 0

    for site_subdir in sorted(sites_dir.iterdir()):
        if not site_subdir.is_dir():
            continue

        business_slug = site_subdir.name
        quality_path = quality_dir / business_slug / "site_quality_report.json"
        business_deploy_dir = deploy_dir / business_slug
        business_deploy_dir.mkdir(parents=True, exist_ok=True)
        log_path = business_deploy_dir / "deployment_logs.txt"
        record_path = business_deploy_dir / "deployment_record.json"

        if not quality_path.exists():
            record = {
                "run_id": run_id,
                "record_id": f"dep_{business_slug}",
                "business_slug": business_slug,
                "site_path": f"runs/{run_id}/05_sites/{business_slug}",
                "provider": "local_only",
                "deployment_status": "needs_review",
                "preview_url": "",
                **_preview_metadata("", "none"),
                "verified_at": "",
                "http_status": 0,
                "deployment_logs_ref": f"runs/{run_id}/{PHASE_SLUG}/{business_slug}/deployment_logs.txt",
                "cleanup_required": True,
                "takedown_after_days": DEFAULT_TAKEDOWN_AFTER_DAYS,
                "takedown_due_at": _iso_due_at(DEFAULT_TAKEDOWN_AFTER_DAYS),
                "takedown_status": "not_due",
            }
            _write_log(log_path, [
                f"phase={PHASE_NAME}",
                f"business_slug={business_slug}",
                "status=needs_review",
                f"reason=missing quality report: {quality_path}",
            ])
            write_json(str(record_path), record)
            deployments.append(record)
            skipped_count += 1
            continue

        quality = read_json(str(quality_path))
        quality_status = quality.get("status", "unknown")
        if quality_status != "approved_for_deploy":
            record = {
                "run_id": run_id,
                "record_id": f"dep_{business_slug}",
                "business_slug": business_slug,
                "site_path": f"runs/{run_id}/05_sites/{business_slug}",
                "provider": "local_only",
                "deployment_status": "needs_review",
                "preview_url": "",
                **_preview_metadata("", "none"),
                "verified_at": "",
                "http_status": 0,
                "deployment_logs_ref": f"runs/{run_id}/{PHASE_SLUG}/{business_slug}/deployment_logs.txt",
                "cleanup_required": True,
                "takedown_after_days": DEFAULT_TAKEDOWN_AFTER_DAYS,
                "takedown_due_at": _iso_due_at(DEFAULT_TAKEDOWN_AFTER_DAYS),
                "takedown_status": "not_due",
            }
            _write_log(log_path, [
                f"phase={PHASE_NAME}",
                f"business_slug={business_slug}",
                "status=needs_review",
                f"reason=quality status not approved_for_deploy: {quality_status}",
            ])
            write_json(str(record_path), record)
            deployments.append(record)
            skipped_count += 1
            continue

        # Read input config to determine deploy provider
        config_path = root / "runs" / run_id / "config" / "input_config.json"
        deploy_provider = "local_only"
        if config_path.exists():
            try:
                inp_conf = read_json(str(config_path))
                deploy_provider = inp_conf.get("deploy_provider", "local_only")
            except Exception:
                pass

        if deploy_provider == "vercel":
            from packages.deployers.vercel import deploy_to_vercel
            # Use business_slug as Vercel project name to keep url consistent
            deployed = deploy_to_vercel(str(site_subdir), project_name=business_slug)
        elif deploy_provider == "nginx_local":
            from packages.deployers.nginx_local import deploy_nginx_local
            deployed = deploy_nginx_local(str(site_subdir))
        else:
            deployed = deploy_local_site(str(site_subdir))

        manifest_record = public_url_manifest.get(business_slug, {})
        public_url = str(manifest_record.get("preview_url") or "") if manifest_record else ""
        has_https_public_url = public_url.startswith("https://")
        preview_url = public_url if has_https_public_url else deployed["preview_url"]
        public_url_source = "manual_manifest" if has_https_public_url else "none"
        now = _utc_now_dt().isoformat() if deployed["deployment_status"] == "live" else ""
        record = {
            "run_id": run_id,
            "record_id": f"dep_{business_slug}",
            "business_slug": business_slug,
            "site_path": f"runs/{run_id}/05_sites/{business_slug}",
            "provider": manifest_record.get("provider") if has_https_public_url else deployed["provider"],
            "deployment_status": deployed["deployment_status"],
            "preview_url": preview_url,
            **_preview_metadata(preview_url, public_url_source),
            "verified_at": manifest_record.get("verified_at") if has_https_public_url else now,
            "http_status": manifest_record.get("http_status") if has_https_public_url else deployed["http_status"],
            "deployment_logs_ref": f"runs/{run_id}/{PHASE_SLUG}/{business_slug}/deployment_logs.txt",
            "cleanup_required": True,
            "takedown_after_days": DEFAULT_TAKEDOWN_AFTER_DAYS,
            "takedown_due_at": _iso_due_at(DEFAULT_TAKEDOWN_AFTER_DAYS),
            "takedown_status": "not_due",
        }
        _write_log(log_path, [
            f"phase={PHASE_NAME}",
            f"business_slug={business_slug}",
            f"status={record['deployment_status']}",
            f"provider={record['provider']}",
            f"preview_url={record['preview_url']}",
            f"http_status={record['http_status']}",
            f"error={deployed.get('error', '')}",
        ])
        write_json(str(record_path), record)
        deployments.append(record)

        if record["deployment_status"] == "live":
            live_count += 1
        else:
            failed_count += 1

    write_json(str(deploy_dir / "deployments.json"), deployments)
    
    # Write public_url_manifest.json to support down-stream outreach preview embeds
    manifest = {}
    for dep in deployments:
        if dep.get("deployment_status") == "live" and dep.get("preview_url"):
            manifest[dep["business_slug"]] = {
                "preview_url": dep["preview_url"],
                "provider": dep["provider"],
                "verified_at": dep.get("verified_at", ""),
                "http_status": dep.get("http_status", 200),
            }
    write_json(str(deploy_dir / "public_url_manifest.json"), manifest)

    result = ResultEnvelope(
        phase=PHASE_NAME,
        status="done",
        run_id=run_id,
        inputs_used=[
            f"runs/{run_id}/05_sites",
            f"runs/{run_id}/06_quality",
        ],
        outputs_created=[
            f"runs/{run_id}/{PHASE_SLUG}/{d['business_slug']}/deployment_record.json" for d in deployments
        ] + [
            f"runs/{run_id}/{PHASE_SLUG}/{d['business_slug']}/deployment_logs.txt" for d in deployments
        ] + [
            f"runs/{run_id}/{PHASE_SLUG}/deployments.json",
            f"runs/{run_id}/{PHASE_SLUG}/result.json",
        ],
        records_processed=len(deployments),
        records_created=live_count,
        records_skipped=skipped_count,
        decisions=[
            f"Verified local deployment for {live_count} sites",
            f"Needs review: {skipped_count}",
            f"Failed: {failed_count}",
        ],
        next_tasks=["Phase 08 — Outreach Draft Generation"] if live_count > 0 else [],
    ).model_dump(exclude_none=True, by_alias=True)
    write_json(str(deploy_dir / "result.json"), result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 07 — Deployment")
    parser.add_argument("--run-id", default="fixture_001", help="Run ID (default: fixture_001)")
    parser.add_argument("--project-root", default=".", help="Project root (default: current directory)")
    args = parser.parse_args()

    result = run_phase_07(args.run_id, args.project_root)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()