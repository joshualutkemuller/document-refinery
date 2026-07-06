"""Small operational CLI for local validation and SQL discovery."""

from __future__ import annotations

import argparse
import json
from importlib.resources import files
from pathlib import Path

from document_refinery.agents.semantic import SemanticExtractor, SemanticValidator
from document_refinery.application.corrections import CorrectionAction, CorrectionRequest
from document_refinery.application.pipeline import RefineryPipeline
from document_refinery.domain.models import SilverExtraction
from document_refinery.infrastructure.semantic_providers import OpenAISemanticModel
from document_refinery.infrastructure.watcher import LandingZoneWatcher
from document_refinery.quality.regression import run_packaged_regression
from document_refinery.quality.reporting import QualityReporter


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="document-refinery")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("ddl", help="print the packaged Delta DDL")
    regression = subcommands.add_parser(
        "regression",
        help="run the packaged ten-document synthetic golden corpus",
    )
    regression.add_argument("--json", action="store_true", dest="as_json")

    run = subcommands.add_parser("run", help="process one eligibility schedule")
    run.add_argument("document", type=Path)
    run.add_argument("--workspace", type=Path, required=True)
    run.add_argument("--source", default="local")
    run.add_argument("--approved-by")
    run.add_argument("--language", default="und")
    _add_semantic_options(run)

    review = subcommands.add_parser(
        "review",
        help="apply owner confirm/correct/dispute actions to a Gate A packet",
    )
    review.add_argument("doc_id")
    review.add_argument("--workspace", type=Path, required=True)
    review.add_argument(
        "--corrections",
        type=Path,
        required=True,
        help="corrections JSON exported from the review packet",
    )
    review.add_argument("--reviewer", required=True)

    approve = subcommands.add_parser(
        "approve",
        help="approve a reviewed Gate A packet and land gold",
    )
    approve.add_argument("doc_id")
    approve.add_argument("--workspace", type=Path, required=True)
    approve.add_argument("--approved-by", required=True)

    watch = subcommands.add_parser("watch", help="process supported landing-zone files")
    watch.add_argument("landing_zone", type=Path)
    watch.add_argument("--workspace", type=Path, required=True)
    watch.add_argument("--source", default="local")
    watch.add_argument("--approved-by")
    watch.add_argument("--language", default="und")
    _add_semantic_options(watch)
    return parser


def _add_semantic_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--semantic-provider",
        choices=("openai",),
        help="enable semantic routing for unknown templates with an approved provider",
    )
    parser.add_argument("--semantic-extractor-model")
    parser.add_argument("--semantic-validator-model")
    parser.add_argument("--semantic-schema-version", default="eligibility-1.0.0")
    parser.add_argument("--semantic-constitution-version", default="eligibility-1.1.0")
    parser.add_argument(
        "--semantic-timeout-seconds",
        type=float,
        default=60.0,
    )
    parser.add_argument("--semantic-max-retries", type=int, default=2)


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "ddl":
        sql_root = files("document_refinery.sql")
        for resource in sorted(
            (item for item in sql_root.iterdir() if item.name.endswith(".sql")),
            key=lambda item: item.name,
        ):
            print(f"-- {resource.name}")
            print(resource.read_text())
    elif args.command == "regression":
        result = run_packaged_regression()
        payload = {
            "document_count": result.report.document_count,
            "owner_verified_document_count": result.report.owner_verified_document_count,
            "field_accuracy": result.report.field_accuracy,
            "disputed_fields": result.disputed_fields,
            "technical_regression_ready": result.report.technical_regression_ready(),
            "phase_one_release_ready": result.report.phase_one_release_ready(),
        }
        if args.as_json:
            print(json.dumps(payload, indent=2))
        else:
            print(
                f"Synthetic regression: {payload['field_accuracy']:.1%} field accuracy "
                f"across {payload['document_count']} documents; "
                f"owner-verified documents: {payload['owner_verified_document_count']}."
            )
    elif args.command == "run":
        _run_documents(
            (args.document,),
            workspace=args.workspace,
            source=args.source,
            approved_by=args.approved_by,
            language=args.language,
            semantic_provider=args.semantic_provider,
            semantic_extractor_model=args.semantic_extractor_model,
            semantic_validator_model=args.semantic_validator_model,
            semantic_schema_version=args.semantic_schema_version,
            semantic_constitution_version=args.semantic_constitution_version,
            semantic_timeout_seconds=args.semantic_timeout_seconds,
            semantic_max_retries=args.semantic_max_retries,
        )
    elif args.command == "review":
        pipeline = RefineryPipeline(args.workspace)
        try:
            requests = _load_corrections(args.corrections)
            outcome = pipeline.apply_corrections(
                args.doc_id,
                requests=requests,
                reviewer=args.reviewer,
            )
            counts: dict[str, int] = {}
            for record in outcome.records:
                counts[record.action.value] = counts.get(record.action.value, 0) + 1
            print(
                json.dumps(
                    {
                        "doc_id": args.doc_id,
                        "applied": len(outcome.records),
                        "actions": counts,
                    }
                )
            )
        finally:
            pipeline.close()
    elif args.command == "approve":
        pipeline = RefineryPipeline(args.workspace)
        try:
            gold_rows = pipeline.approve(args.doc_id, approved_by=args.approved_by)
            print(
                json.dumps(
                    {
                        "doc_id": args.doc_id,
                        "task_status": "gold_landed",
                        "gold_records": len(gold_rows),
                    }
                )
            )
        finally:
            pipeline.close()
    elif args.command == "watch":
        candidates = LandingZoneWatcher(args.landing_zone, source=args.source).discover()
        _run_documents(
            tuple(candidate.path for candidate in candidates),
            workspace=args.workspace,
            source=args.source,
            approved_by=args.approved_by,
            language=args.language,
            semantic_provider=args.semantic_provider,
            semantic_extractor_model=args.semantic_extractor_model,
            semantic_validator_model=args.semantic_validator_model,
            semantic_schema_version=args.semantic_schema_version,
            semantic_constitution_version=args.semantic_constitution_version,
            semantic_timeout_seconds=args.semantic_timeout_seconds,
            semantic_max_retries=args.semantic_max_retries,
        )
    return 0


def _run_documents(
    paths: tuple[Path, ...],
    *,
    workspace: Path,
    source: str,
    approved_by: str | None,
    language: str,
    semantic_provider: str | None,
    semantic_extractor_model: str | None,
    semantic_validator_model: str | None,
    semantic_schema_version: str,
    semantic_constitution_version: str,
    semantic_timeout_seconds: float,
    semantic_max_retries: int,
) -> None:
    semantic_extractor, semantic_validator = _build_semantic_components(
        provider=semantic_provider,
        extractor_model=semantic_extractor_model,
        validator_model=semantic_validator_model,
        schema_version=semantic_schema_version,
        constitution_version=semantic_constitution_version,
        timeout_seconds=semantic_timeout_seconds,
        max_retries=semantic_max_retries,
    )
    pipeline = RefineryPipeline(
        workspace,
        semantic_extractor=semantic_extractor,
        semantic_validator=semantic_validator,
    )
    all_rows: list[SilverExtraction] = []
    try:
        for path in paths:
            result = pipeline.run(
                path,
                source=source,
                approved_by=approved_by,
                language=language,
            )
            all_rows.extend(result.silver_rows)
            print(
                json.dumps(
                    {
                        "doc_id": result.document.doc_id,
                        "task_status": (
                            "gold_landed" if result.gold_rows else "gate_a_pending"
                        ),
                        "silver_fields": len(result.silver_rows),
                        "gold_records": len(result.gold_rows),
                        "review_html": str(result.review_html),
                    }
                )
            )
        if all_rows:
            report = QualityReporter().build(tuple(all_rows))
            quality_path = workspace / "quality_report.json"
            quality_path.write_text(
                json.dumps(
                    {
                        "executive_briefing": report.executive_briefing,
                        "dashboard_payload": report.dashboard_payload,
                        "audit_appendix": report.audit_appendix,
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            print(f"Quality report: {quality_path}")
    finally:
        pipeline.close()


def _load_corrections(path: Path) -> tuple[CorrectionRequest, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    entries = payload.get("corrections") if isinstance(payload, dict) else payload
    if not isinstance(entries, list) or not entries:
        raise ValueError("corrections file must contain a non-empty 'corrections' list")
    requests: list[CorrectionRequest] = []
    for entry in entries:
        requests.append(
            CorrectionRequest(
                extraction_id=str(entry["extraction_id"]),
                action=CorrectionAction(str(entry["action"])),
                corrected_value=(
                    None if entry.get("corrected_value") is None
                    else str(entry["corrected_value"])
                ),
                note=None if entry.get("note") is None else str(entry["note"]),
            )
        )
    return tuple(requests)


def _build_semantic_components(
    *,
    provider: str | None,
    extractor_model: str | None,
    validator_model: str | None,
    schema_version: str,
    constitution_version: str,
    timeout_seconds: float,
    max_retries: int,
) -> tuple[SemanticExtractor | None, SemanticValidator | None]:
    if provider is None:
        if extractor_model or validator_model:
            raise ValueError("--semantic-provider is required when semantic models are set")
        return None, None
    if provider != "openai":
        raise ValueError(f"unsupported semantic provider: {provider}")
    if not extractor_model or not validator_model:
        raise ValueError("both extractor and validator semantic models are required")
    if max_retries < 0:
        raise ValueError("semantic max retries must be non-negative")
    schema_dictionary = (
        "eligibility[].asset_criterion, eligible, haircut_pct, concentration_limit_pct, "
        "concentration_basis, currency_scope, rating_floor, tenor_cap_days, valid_from, valid_to"
    )
    constitution = (
        "Extract collateral eligibility schedule terms only. Preserve original-language "
        "evidence, emit explicit not_found fields, and never emit system-controlled fields."
    )
    extractor = SemanticExtractor(
        OpenAISemanticModel(
            model=extractor_model,
            session_id="openai-extractor-session",
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        ),
        constitution=constitution,
        schema_dictionary=schema_dictionary,
        schema_version=schema_version,
        constitution_version=constitution_version,
        extractor_version=f"openai-{extractor_model}-{constitution_version}",
    )
    validator = SemanticValidator(
        OpenAISemanticModel(
            model=validator_model,
            session_id="openai-validator-session",
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        ),
        schema_dictionary=schema_dictionary,
        schema_version=schema_version,
        constitution_version=constitution_version,
    )
    return extractor, validator


if __name__ == "__main__":
    raise SystemExit(main())
