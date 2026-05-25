from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


def _base_url(value: str) -> str:
    return value.rstrip("/")


def http_json(method: str, url: str, payload: dict[str, Any] | None = None) -> Any:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Accept": "application/json"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    request = Request(url, data=data, headers=headers, method=method.upper())
    with urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def load_domains_from_file(path: str) -> list[str]:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Missing domains file: {file_path}")
    domains = []
    for line in file_path.read_text(encoding="utf-8").splitlines():
        value = line.strip()
        if value and not value.startswith("#"):
            domains.append(value)
    return domains


def normalize_domain(value: str) -> str:
    candidate = value.strip().lower()
    if candidate.startswith("http://") or candidate.startswith("https://"):
        candidate = urlparse(candidate).netloc or candidate
    return candidate.removeprefix("www.")


def resolve_source(sources: list[dict[str, Any]], domain: str) -> dict[str, Any] | None:
    wanted = normalize_domain(domain)
    for source in sources:
        source_domains = {
            normalize_domain(str(source.get("domain") or "")),
            normalize_domain(str(source.get("url") or "")),
            normalize_domain(str(source.get("base_url") or "")),
        }
        if wanted in source_domains:
            return source
    return None


def analyze_domain(base_url: str, domain: str, source: dict[str, Any]) -> dict[str, Any]:
    try:
        discovery = http_json("GET", f"{base_url}/api/sources/{source['id']}/discovery")
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else ""
        return {
            "domain": domain,
            "source_id": source.get("id"),
            "source_name": source.get("name"),
            "status": "error",
            "error": f"HTTP {exc.code}: {error_body or exc.reason}",
        }
    except URLError as exc:
        return {
            "domain": domain,
            "source_id": source.get("id"),
            "source_name": source.get("name"),
            "status": "error",
            "error": str(exc.reason),
        }

    artifacts = discovery.get("raw_artifacts") or []
    if not artifacts:
        return {
            "domain": domain,
            "source_id": source.get("id"),
            "source_name": source.get("name"),
            "status": "error",
            "error": "No raw artifacts found for source",
        }

    target_hint = (discovery.get("rule", {}) or {}).get("targets", [])
    payload = {
        "domain": discovery.get("domain") or domain,
        "raw_artifact_id": artifacts[0].get("id"),
        "target_hint": target_hint[0] if target_hint else "auto",
    }
    try:
        analysis = http_json("POST", f"{base_url}/api/extraction/ai/analyze", payload)
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else ""
        return {
            "domain": domain,
            "source_id": source.get("id"),
            "source_name": source.get("name"),
            "status": "error",
            "error": f"HTTP {exc.code}: {error_body or exc.reason}",
        }
    except URLError as exc:
        return {
            "domain": domain,
            "source_id": source.get("id"),
            "source_name": source.get("name"),
            "status": "error",
            "error": str(exc.reason),
        }

    return {
        "domain": domain,
        "source_id": source.get("id"),
        "source_name": source.get("name"),
        "status": "ok",
        "raw_artifact_id": payload["raw_artifact_id"],
        "model": analysis.get("model"),
        "accepted": analysis.get("validation", {}).get("accepted"),
        "draft": analysis.get("draft"),
        "validation": analysis.get("validation"),
    }


def run_batch(base_url: str, domains: list[str]) -> list[dict[str, Any]]:
    sources = http_json("GET", f"{base_url}/api/sources")
    results = []
    for domain in domains:
        source = resolve_source(sources, domain)
        if not source:
            results.append({
                "domain": normalize_domain(domain),
                "status": "error",
                "error": "Source not found",
            })
            continue
        results.append(analyze_domain(base_url, domain, source))
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Gemini extraction analysis for multiple domains via Admin Center API.")
    parser.add_argument("--base-url", default="http://localhost", help="Admin Center base URL.")
    parser.add_argument("--domain", action="append", default=[], help="Domain to analyze. Repeatable.")
    parser.add_argument("--domains-file", help="Text file with one domain per line.")
    parser.add_argument("--output", help="Write JSONL results to this file.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    domains = list(args.domain)
    if args.domains_file:
        domains.extend(load_domains_from_file(args.domains_file))
    domains = [normalize_domain(domain) for domain in domains if domain.strip()]
    if not domains:
        print("No domains provided.", file=sys.stderr)
        return 2

    base_url = _base_url(args.base_url)
    results = run_batch(base_url, domains)

    output_lines = [json.dumps(result, ensure_ascii=False) for result in results]
    if args.output:
        Path(args.output).write_text("\n".join(output_lines) + "\n", encoding="utf-8")
    else:
        for line in output_lines:
            print(line)

    return 1 if any(result.get("status") != "ok" for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
