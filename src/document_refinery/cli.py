"""Small operational CLI for local validation and SQL discovery."""

from __future__ import annotations

import argparse
import json
import sys
from importlib.resources import files
from pathlib import Path

from document_refinery.agents.semantic import (
    SemanticExtractor,
    SemanticModel,
    SemanticValidator,
)
from document_refinery.application.corrections import (
    CorrectionAction,
    CorrectionOutcome,
    CorrectionRequest,
)
from document_refinery.application.pipeline import (
    ClassificationReviewRequired,
    GoldRepository,
    RefineryPipeline,
)
from document_refinery.application.promotion import PromotionError
from document_refinery.application.review_session import build_review_requests, render_review
from document_refinery.domain.models import SilverExtraction
from document_refinery.infrastructure.chat_completions import (
    DEFAULT_OLLAMA_URL,
    build_ollama_model,
    build_openai_compatible_model,
)
from document_refinery.infrastructure.local_semantic import LocalHeuristicSemanticModel
from document_refinery.infrastructure.semantic_providers import OpenAISemanticModel
from document_refinery.infrastructure.watcher import LandingZoneWatcher
from document_refinery.quality.dashboard import render_dashboard
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
    _add_storage_options(run)

    review = subcommands.add_parser(
        "review",
        help="review a Gate A packet in the terminal (confirm/correct/dispute)",
    )
    review.add_argument("doc_id")
    review.add_argument("--workspace", type=Path, required=True)
    review.add_argument("--reviewer", help="identified reviewer (required to apply changes)")
    review.add_argument(
        "--list",
        action="store_true",
        dest="list_only",
        help="print the packet read-only and exit; no reviewer needed",
    )
    review.add_argument(
        "--pending-only",
        action="store_true",
        dest="pending_only",
        help="walk only fields needing attention (skip already-confirmed ones)",
    )
    review.add_argument(
        "--corrections",
        type=Path,
        help="apply actions non-interactively from a corrections JSON file",
    )

    approve = subcommands.add_parser(
        "approve",
        help="approve a reviewed Gate A packet and land gold",
    )
    approve.add_argument("doc_id")
    approve.add_argument("--workspace", type=Path, required=True)
    approve.add_argument("--approved-by", required=True)
    _add_storage_options(approve)

    watch = subcommands.add_parser("watch", help="process supported landing-zone files")
    watch.add_argument("landing_zone", type=Path)
    watch.add_argument("--workspace", type=Path, required=True)
    watch.add_argument("--source", default="local")
    watch.add_argument("--approved-by")
    watch.add_argument("--language", default="und")
    _add_semantic_options(watch)
    _add_storage_options(watch)
    return parser


def _add_semantic_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--semantic-provider",
        nargs="?",
        const="ollama",
        choices=("ollama", "openai", "openai-compatible", "local"),
        help=(
            "enable semantic routing for unknown templates. Bare flag defaults to "
            "'ollama' (local model, data stays on your machine — most secure). "
            "'openai' is the approved ZDR production provider (OPENAI_API_KEY + "
            "network); 'openai-compatible' targets a third-party endpoint via "
            "--semantic-base-url (data leaves your machine); 'local' is an offline "
            "heuristic double for pipeline testing"
        ),
    )
    parser.add_argument(
        "--semantic-base-url",
        help=(
            "endpoint URL; required for 'openai-compatible', optional override for "
            "'ollama' (default http://localhost:11434/v1/chat/completions)"
        ),
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


def _add_storage_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--gold-store",
        choices=("jsonl", "delta"),
        default="jsonl",
        help="gold storage backend: 'jsonl' (default, local) or 'delta' (Delta Lake)",
    )
    parser.add_argument(
        "--gold-uri",
        help=(
            "Delta table URI for --gold-store delta: a local path or object store "
            "(s3://, az://, gs://). Defaults to <workspace>/gold/eligibility_terms.delta"
        ),
    )


def _build_gold_store(
    gold_store: str, gold_uri: str | None, workspace: Path
) -> GoldRepository | None:
    if gold_store != "delta":
        return None
    from document_refinery.infrastructure.delta_store import DeltaGoldStore

    uri = gold_uri or str(workspace / "gold" / "eligibility_terms.delta")
    return DeltaGoldStore(uri)


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
            semantic_base_url=args.semantic_base_url,
            semantic_extractor_model=args.semantic_extractor_model,
            semantic_validator_model=args.semantic_validator_model,
            semantic_schema_version=args.semantic_schema_version,
            semantic_constitution_version=args.semantic_constitution_version,
            semantic_timeout_seconds=args.semantic_timeout_seconds,
            semantic_max_retries=args.semantic_max_retries,
            gold_store=args.gold_store,
            gold_uri=args.gold_uri,
        )
    elif args.command == "review":
        return _run_review(args)
    elif args.command == "approve":
        pipeline = RefineryPipeline(
            args.workspace,
            gold_store=_build_gold_store(args.gold_store, args.gold_uri, args.workspace),
        )
        try:
            try:
                gold_rows = pipeline.approve(args.doc_id, approved_by=args.approved_by)
            except PromotionError as error:
                print(
                    json.dumps(
                        {
                            "doc_id": args.doc_id,
                            "task_status": "gold_promotion_blocked",
                            "reason": str(error),
                        }
                    )
                )
                return 1
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
            semantic_base_url=args.semantic_base_url,
            semantic_extractor_model=args.semantic_extractor_model,
            semantic_validator_model=args.semantic_validator_model,
            semantic_schema_version=args.semantic_schema_version,
            semantic_constitution_version=args.semantic_constitution_version,
            semantic_timeout_seconds=args.semantic_timeout_seconds,
            semantic_max_retries=args.semantic_max_retries,
            gold_store=args.gold_store,
            gold_uri=args.gold_uri,
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
    semantic_base_url: str | None,
    semantic_extractor_model: str | None,
    semantic_validator_model: str | None,
    semantic_schema_version: str,
    semantic_constitution_version: str,
    semantic_timeout_seconds: float,
    semantic_max_retries: int,
    gold_store: str = "jsonl",
    gold_uri: str | None = None,
) -> None:
    semantic_extractor, semantic_validator = _build_semantic_components(
        provider=semantic_provider,
        base_url=semantic_base_url,
        extractor_model=semantic_extractor_model,
        validator_model=semantic_validator_model,
        schema_version=semantic_schema_version,
        constitution_version=semantic_constitution_version,
        timeout_seconds=semantic_timeout_seconds,
        max_retries=semantic_max_retries,
    )
    if semantic_provider == "openai-compatible":
        print(
            f"notice: document text will be sent to {semantic_base_url}; retention/ZDR "
            "is the provider's responsibility and is NOT covered by the approved OpenAI "
            "ZDR policy. Use only for non-confidential documents unless verified.",
            file=sys.stderr,
        )
    pipeline = RefineryPipeline(
        workspace,
        semantic_extractor=semantic_extractor,
        semantic_validator=semantic_validator,
        gold_store=_build_gold_store(gold_store, gold_uri, workspace),
    )
    all_rows: list[SilverExtraction] = []
    try:
        for path in paths:
            try:
                result = pipeline.run(
                    path,
                    source=source,
                    approved_by=approved_by,
                    language=language,
                )
            except ClassificationReviewRequired as review:
                # Unknown layout with no semantic extractor configured: report and
                # keep processing the batch instead of aborting on one document.
                print(
                    json.dumps(
                        {
                            "path": str(path),
                            "task_status": "classification_review_required",
                            "confidence": round(review.confidence, 2),
                        }
                    )
                )
                continue
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
            dashboard_path = workspace / "quality_dashboard.html"
            dashboard_path.write_text(render_dashboard(report), encoding="utf-8")
            print(f"Quality report: {quality_path}")
            print(f"Quality dashboard: {dashboard_path}")
    finally:
        pipeline.close()


def _run_review(args: argparse.Namespace) -> int:
    pipeline = RefineryPipeline(args.workspace)
    try:
        if args.list_only:
            rows = pipeline.review_rows(args.doc_id)
            print(render_review(rows))
            return 0
        if not args.reviewer:
            print("error: --reviewer is required to apply review actions")
            return 2
        if args.corrections is not None:
            requests = _load_corrections(args.corrections)
        else:
            rows = pipeline.review_rows(args.doc_id)
            requests = build_review_requests(
                rows,
                prompt=input,
                echo=print,
                pending_only=args.pending_only,
            )
        if not requests:
            print(json.dumps({"doc_id": args.doc_id, "applied": 0, "actions": {}}))
            return 0
        outcome = pipeline.apply_corrections(
            args.doc_id,
            requests=requests,
            reviewer=args.reviewer,
        )
        print(json.dumps(_review_summary(args.doc_id, outcome)))
        return 0
    finally:
        pipeline.close()


def _review_summary(doc_id: str, outcome: CorrectionOutcome) -> dict[str, object]:
    counts: dict[str, int] = {}
    for record in outcome.records:
        counts[record.action.value] = counts.get(record.action.value, 0) + 1
    return {"doc_id": doc_id, "applied": len(outcome.records), "actions": counts}


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


def _build_semantic_backends(
    *,
    provider: str,
    base_url: str | None,
    extractor_model: str | None,
    validator_model: str | None,
    timeout_seconds: float,
    max_retries: int,
) -> tuple[str, str, SemanticModel, SemanticModel]:
    """Construct the two provider-specific model sessions (extractor, validator)."""
    if provider == "local":
        extractor_name = extractor_model or "local-heuristic-v1"
        validator_name = validator_model or "local-heuristic-v1"
        return (
            extractor_name,
            validator_name,
            LocalHeuristicSemanticModel(model=extractor_name, session_id="local-extractor-session"),
            LocalHeuristicSemanticModel(model=validator_name, session_id="local-validator-session"),
        )
    if not extractor_model or not validator_model:
        raise ValueError("both extractor and validator semantic models are required")
    if provider == "openai":
        return (
            extractor_model,
            validator_model,
            OpenAISemanticModel(
                model=extractor_model, session_id="openai-extractor-session",
                timeout_seconds=timeout_seconds, max_retries=max_retries,
            ),
            OpenAISemanticModel(
                model=validator_model, session_id="openai-validator-session",
                timeout_seconds=timeout_seconds, max_retries=max_retries,
            ),
        )
    if provider == "ollama":
        ollama_url = base_url or DEFAULT_OLLAMA_URL
        return (
            extractor_model,
            validator_model,
            build_ollama_model(
                model=extractor_model, session_id="ollama-extractor-session",
                base_url=ollama_url, timeout_seconds=timeout_seconds, max_retries=max_retries,
            ),
            build_ollama_model(
                model=validator_model, session_id="ollama-validator-session",
                base_url=ollama_url, timeout_seconds=timeout_seconds, max_retries=max_retries,
            ),
        )
    # openai-compatible: third-party endpoint, data leaves the machine.
    if not base_url:
        raise ValueError("--semantic-base-url is required for the openai-compatible provider")
    return (
        extractor_model,
        validator_model,
        build_openai_compatible_model(
            model=extractor_model, base_url=base_url, session_id="openai-compatible-extractor",
            timeout_seconds=timeout_seconds, max_retries=max_retries,
        ),
        build_openai_compatible_model(
            model=validator_model, base_url=base_url, session_id="openai-compatible-validator",
            timeout_seconds=timeout_seconds, max_retries=max_retries,
        ),
    )


def _build_semantic_components(
    *,
    provider: str | None,
    extractor_model: str | None,
    validator_model: str | None,
    schema_version: str,
    constitution_version: str,
    timeout_seconds: float,
    max_retries: int,
    base_url: str | None = None,
) -> tuple[SemanticExtractor | None, SemanticValidator | None]:
    if provider is None:
        if extractor_model or validator_model:
            raise ValueError("--semantic-provider is required when semantic models are set")
        return None, None
    if provider not in {"ollama", "openai", "openai-compatible", "local"}:
        raise ValueError(f"unsupported semantic provider: {provider}")
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
    extractor_model_name, validator_model_name, extractor_backend, validator_backend = (
        _build_semantic_backends(
            provider=provider,
            base_url=base_url,
            extractor_model=extractor_model,
            validator_model=validator_model,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )
    )
    extractor = SemanticExtractor(
        extractor_backend,
        constitution=constitution,
        schema_dictionary=schema_dictionary,
        schema_version=schema_version,
        constitution_version=constitution_version,
        extractor_version=f"{provider}-{extractor_model_name}-{constitution_version}",
    )
    validator = SemanticValidator(
        validator_backend,
        schema_dictionary=schema_dictionary,
        schema_version=schema_version,
        constitution_version=constitution_version,
    )
    return extractor, validator


if __name__ == "__main__":
    raise SystemExit(main())
