from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from apartment_agents.adk.root_agent import (  # noqa: E402
    build_google_adk_root_agent,
    build_root_agent_definition,
    serialize_agent_tree,
)
from apartment_agents.adk.runner import GoogleAdkAnalysisRunner, validate_runner_startup  # noqa: E402
from apartment_agents.app.services import AnalyzeApartmentRequest, AnalyzeApartmentService  # noqa: E402
from apartment_agents.config import AppConfig  # noqa: E402


DEFAULT_LISTING_URL = "https://www.boligsiden.dk/adresse/frederiks-alle-12-3-th-8000-aarhus-c"
DEFAULT_BUYER_PROFILE_ID = "solo_engineer"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify that the installed Google ADK runtime can delegate to sub-agents."
    )
    parser.add_argument("--listing-url", default=DEFAULT_LISTING_URL)
    parser.add_argument("--buyer-profile-id", default=DEFAULT_BUYER_PROFILE_ID)
    parser.add_argument("--adk-model", default=os.getenv("ADK_MODEL", "gemini-2.5-pro"))
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=int(os.getenv("ADK_TIMEOUT_SECONDS", "30")),
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=None,
        help="Path for the evidence JSON file. Defaults to output/adk_delegation_verification_<timestamp>.json.",
    )
    parser.add_argument(
        "--stdout-json",
        action="store_true",
        help="Print the evidence JSON to stdout after writing it.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = datetime.now(timezone.utc)
    output_json = args.output_json or (
        Path("output")
        / f"adk_delegation_verification_{generated_at.strftime('%Y%m%dT%H%M%SZ')}.json"
    )
    report: dict[str, Any] = {
        "generated_at": generated_at.isoformat(),
        "status": "pending",
        "listing_url": args.listing_url,
        "buyer_profile_id": args.buyer_profile_id,
        "adk_backend": "google_adk",
        "adk_model": args.adk_model,
        "runtime": runtime_evidence(args.adk_model),
        "credentials": {"google_api_key": "present" if os.getenv("GOOGLE_API_KEY") else "missing"},
        "execution": {},
    }

    google_api_key = os.getenv("GOOGLE_API_KEY")
    if not google_api_key:
        report["status"] = "blocked_missing_credentials"
        report["execution"] = {
            "attempted": False,
            "reason": "GOOGLE_API_KEY is required for a live Google ADK model call.",
        }
        return write_report(report, output_json, args.stdout_json)

    try:
        config = AppConfig(
            output_dir=output_json.parent,
            adk_backend="google_adk",
            adk_model=args.adk_model,
            adk_timeout_seconds=args.timeout_seconds,
            google_api_key=google_api_key,
        )
        validate_runner_startup(config)
        runner = GoogleAdkAnalysisRunner(config)
        service = AnalyzeApartmentService(config=config, adk_runner=runner)
        result = service.analyze(
            AnalyzeApartmentRequest(
                listing_url=args.listing_url,
                buyer_profile_id=args.buyer_profile_id,
            )
        )
    except Exception as exc:
        report["status"] = "runtime_failed"
        report["execution"] = {
            "attempted": True,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
        return write_report(report, output_json, args.stdout_json)

    delegation_evidence = runner.delegation_evidence()
    runtime_error = delegation_evidence["runtime_error"]
    missing_agents = delegation_evidence["missing_agents"]
    if runtime_error:
        report["status"] = "runtime_failed"
    else:
        report["status"] = "verified" if not missing_agents else "delegation_incomplete"
    report["execution"] = {
        "attempted": True,
        "report_id": result.report.report_id,
        "report_path": str(result.report_path),
        "recommendation": result.report.recommendation.value,
        "delegation": delegation_evidence,
    }
    return write_report(report, output_json, args.stdout_json)


def runtime_evidence(adk_model: str) -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "google_adk_version": package_version("google-adk"),
        "imports": {},
        "root_agent_definition": serialize_agent_tree(build_root_agent_definition()),
        "google_agent_tree": None,
    }

    try:
        from google.adk.runners import Runner  # noqa: F401
    except Exception as exc:
        evidence["imports"]["google.adk.runners.Runner"] = import_failure(exc)
    else:
        evidence["imports"]["google.adk.runners.Runner"] = {"status": "ok"}

    try:
        from google.adk.sessions import InMemorySessionService  # noqa: F401
    except Exception as exc:
        evidence["imports"]["google.adk.sessions.InMemorySessionService"] = import_failure(exc)
    else:
        evidence["imports"]["google.adk.sessions.InMemorySessionService"] = {"status": "ok"}

    try:
        root_agent = build_google_adk_root_agent(adk_model)
    except Exception as exc:
        evidence["google_agent_tree"] = import_failure(exc)
    else:
        evidence["google_agent_tree"] = {
            "name": getattr(root_agent, "name", None),
            "sub_agents": [
                getattr(agent, "name", None) for agent in getattr(root_agent, "sub_agents", [])
            ],
        }

    placeholder_config = AppConfig(
        output_dir=Path("output"),
        adk_backend="google_adk",
        adk_model=adk_model,
        google_api_key=os.getenv("GOOGLE_API_KEY") or "verification-placeholder",
    )
    try:
        validate_runner_startup(placeholder_config)
    except Exception as exc:
        evidence["startup_validation"] = import_failure(exc)
    else:
        evidence["startup_validation"] = {
            "status": "ok",
            "used_placeholder_credentials": not bool(os.getenv("GOOGLE_API_KEY")),
        }

    return evidence


def package_version(package_name: str) -> str | None:
    try:
        return metadata.version(package_name)
    except metadata.PackageNotFoundError:
        return None


def import_failure(exc: Exception) -> dict[str, str]:
    return {
        "status": "failed",
        "error_type": type(exc).__name__,
        "error": str(exc),
    }


def write_report(report: dict[str, Any], output_json: Path, stdout_json: bool) -> int:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(report, indent=2, sort_keys=True)
    output_json.write_text(f"{rendered}\n", encoding="utf-8")
    print(f"Wrote ADK delegation evidence to {output_json}")
    print(f"Status: {report['status']}")
    if stdout_json:
        print(rendered)
    return 0 if report["status"] in {"verified", "blocked_missing_credentials"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
