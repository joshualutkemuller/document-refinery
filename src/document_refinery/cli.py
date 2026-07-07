"""Small operational CLI for local validation and SQL discovery."""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
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
from document_refinery.application.limit_consistency import LimitConsistencyError
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
from document_refinery.infrastructure.layout import (
    LayoutAdapter,
    OcrLayoutAdapter,
    PdfPlumberLayoutAdapter,
    TextLineLayoutAdapter,
)
from document_refinery.infrastructure.layout_benchmark import (
    LayoutBenchmarkCase,
    run_layout_benchmark,
)
from document_refinery.infrastructure.local_semantic import LocalHeuristicSemanticModel
from document_refinery.infrastructure.memory_store import CorrectionMemoryStore
from document_refinery.infrastructure.records import (
    GoldLimitStore,
    GoldMarginRequirementStore,
)
from document_refinery.infrastructure.semantic_providers import OpenAISemanticModel
from document_refinery.infrastructure.watcher import LandingZoneWatcher
from document_refinery.quality.accuracy import (
    TokenCostModel,
    load_corpus,
    score_corpus,
    semantic_row_provider,
)
from document_refinery.quality.dashboard import render_dashboard
from document_refinery.quality.regression import run_packaged_regression
from document_refinery.quality.reporting import QualityReporter
from document_refinery.semantic_schemas import schemas as semantic_schemas


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
    approve.add_argument(
        "--land-limits",
        action="store_true",
        help=(
            "also promote validated limit[i] rows to gold_collateral_limits "
            "(behind Gate S; for collateral_rule_schedule documents). Writes "
            "<workspace>/gold/collateral_limits.jsonl"
        ),
    )
    approve.add_argument(
        "--land-margin",
        action="store_true",
        help=(
            "also promote validated requirement[i] rows to gold_margin_requirements "
            "(behind Gate S; for margin_requirement documents). Writes "
            "<workspace>/gold/margin_requirements.jsonl"
        ),
    )
    _add_storage_options(approve)

    memory = subcommands.add_parser(
        "memory",
        help="inspect what the system has learned from past corrections",
    )
    memory.add_argument("--workspace", type=Path, required=True)
    memory.add_argument("--json", action="store_true", dest="as_json")

    accuracy = subcommands.add_parser(
        "accuracy",
        help="measure extraction accuracy against a golden corpus + ground truth",
    )
    accuracy.add_argument(
        "--corpus",
        type=Path,
        default=Path("examples/golden_corpus"),
        help="directory of *.txt schedules + ground_truth.json",
    )
    accuracy.add_argument("--json", action="store_true", dest="as_json")
    accuracy.add_argument(
        "--language",
        default="und",
        help="language tag passed to the semantic route when --semantic-provider is set",
    )
    accuracy.add_argument(
        "--cost-per-1k-input",
        type=float,
        help="USD per 1k input tokens; folds an estimated semantic cost into the report",
    )
    accuracy.add_argument(
        "--cost-per-1k-output",
        type=float,
        help="USD per 1k output tokens (pairs with --cost-per-1k-input)",
    )
    _add_semantic_options(accuracy)

    benchmark = subcommands.add_parser(
        "benchmark",
        help="run the reproducible N2 OCR/layout benchmark over a document manifest",
    )
    benchmark.add_argument(
        "manifest",
        type=Path,
        help="JSON manifest of benchmark cases (see docs/toolchain-evaluation.md)",
    )
    benchmark.add_argument("--workspace", type=Path, required=True)
    benchmark.add_argument(
        "--adapter",
        choices=("text-line", "pdfplumber", "ocr"),
        default="pdfplumber",
        help=(
            "layout adapter under test: 'pdfplumber' (text-bearing PDFs, default), "
            "'ocr' (scanned/image-only PDFs, needs the 'ocr' extra), or 'text-line' "
            "(deterministic text/Markdown fallback)"
        ),
    )
    benchmark.add_argument("--json", action="store_true", dest="as_json")

    distill = subcommands.add_parser(
        "distill",
        help="replay owner corrections into constitution-rule and golden-case proposals",
    )
    distill.add_argument("--workspace", type=Path, required=True)
    distill.add_argument(
        "--min-occurrences",
        type=int,
        default=2,
        help="minimum repeated corrections before proposing a normalization rule",
    )
    distill.add_argument(
        "--ground-truth-out",
        type=Path,
        help="write the golden-case proposals as a ground_truth.json fragment for a corpus",
    )
    distill.add_argument("--json", action="store_true", dest="as_json")

    review_time = subcommands.add_parser(
        "review-time",
        help="report measured owner review time against the 15-minute N4 target",
    )
    review_time.add_argument("--workspace", type=Path, required=True)
    review_time.add_argument("--json", action="store_true", dest="as_json")

    corpus_check = subcommands.add_parser(
        "corpus-check",
        help="validate an owner-verified accuracy corpus and report release readiness",
    )
    corpus_check.add_argument(
        "--corpus",
        type=Path,
        default=Path("examples/golden_corpus"),
        help="directory of *.txt schedules + ground_truth.json",
    )
    corpus_check.add_argument("--json", action="store_true", dest="as_json")

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
    parser.add_argument(
        "--semantic-max-output-tokens",
        type=int,
        help=(
            "optional output token cap for chat-completions providers such as "
            "ollama and openai-compatible"
        ),
    )
    parser.add_argument(
        "--semantic-chunk-concurrency",
        type=int,
        default=1,
        help="maximum parallel semantic extraction chunks per document",
    )


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
            semantic_max_output_tokens=args.semantic_max_output_tokens,
            semantic_chunk_concurrency=args.semantic_chunk_concurrency,
            gold_store=args.gold_store,
            gold_uri=args.gold_uri,
        )
    elif args.command == "review":
        return _run_review(args)
    elif args.command == "memory":
        return _run_memory(args)
    elif args.command == "accuracy":
        return _run_accuracy(args)
    elif args.command == "benchmark":
        return _run_benchmark(args)
    elif args.command == "distill":
        return _run_distill(args)
    elif args.command == "review-time":
        return _run_review_time(args)
    elif args.command == "corpus-check":
        return _run_corpus_check(args)
    elif args.command == "approve":
        limit_store = None
        if args.land_limits:
            limit_store = GoldLimitStore(
                args.workspace / "gold" / "collateral_limits.jsonl"
            )
        margin_store = None
        if args.land_margin:
            margin_store = GoldMarginRequirementStore(
                args.workspace / "gold" / "margin_requirements.jsonl"
            )
        pipeline = RefineryPipeline(
            args.workspace,
            gold_store=_build_gold_store(args.gold_store, args.gold_uri, args.workspace),
            limit_store=limit_store,
            margin_store=margin_store,
        )
        try:
            try:
                gold_rows = pipeline.approve(args.doc_id, approved_by=args.approved_by)
            except (PromotionError, LimitConsistencyError) as error:
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
                        "limit_records": len(pipeline.last_landed_limits),
                        "margin_records": len(pipeline.last_landed_margin),
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
            semantic_max_output_tokens=args.semantic_max_output_tokens,
            semantic_chunk_concurrency=args.semantic_chunk_concurrency,
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
    semantic_max_output_tokens: int | None,
    semantic_chunk_concurrency: int,
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
        max_output_tokens=semantic_max_output_tokens,
        chunk_concurrency=semantic_chunk_concurrency,
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
            print(render_review(rows, suggestions=pipeline.memory_suggestions(rows)))
            return 0
        if not args.reviewer:
            print("error: --reviewer is required to apply review actions")
            return 2
        review_seconds: float | None = None
        if args.corrections is not None:
            requests, review_seconds = _load_corrections(args.corrections)
        else:
            rows = pipeline.review_rows(args.doc_id)
            started = time.perf_counter()
            requests = build_review_requests(
                rows,
                prompt=input,
                echo=print,
                pending_only=args.pending_only,
                suggestions=pipeline.memory_suggestions(rows),
            )
            # Wall-clock of the actual interactive walk — the N4 review-time metric.
            review_seconds = time.perf_counter() - started
        if not requests:
            print(json.dumps({"doc_id": args.doc_id, "applied": 0, "actions": {}}))
            return 0
        outcome = pipeline.apply_corrections(
            args.doc_id,
            requests=requests,
            reviewer=args.reviewer,
            review_seconds=review_seconds,
        )
        print(json.dumps(_review_summary(args.doc_id, outcome)))
        return 0
    finally:
        pipeline.close()


def _run_accuracy(args: argparse.Namespace) -> int:
    if not (args.corpus / "ground_truth.json").exists():
        print(f"error: no ground_truth.json in {args.corpus}")
        return 2
    row_provider = None
    if args.semantic_provider is not None:
        extractor, validator = _build_semantic_components(
            provider=args.semantic_provider,
            base_url=args.semantic_base_url,
            extractor_model=args.semantic_extractor_model,
            validator_model=args.semantic_validator_model,
            schema_version=args.semantic_schema_version,
            constitution_version=args.semantic_constitution_version,
            timeout_seconds=args.semantic_timeout_seconds,
            max_retries=args.semantic_max_retries,
            max_output_tokens=args.semantic_max_output_tokens,
            chunk_concurrency=args.semantic_chunk_concurrency,
        )
        if extractor is None or validator is None:
            print("error: semantic scoring requires a configured --semantic-provider")
            return 2
        if args.semantic_provider == "openai-compatible":
            print(
                "notice: corpus text will be sent to the configured endpoint; "
                "retention/ZDR is the provider's responsibility.",
                file=sys.stderr,
            )
        row_provider = semantic_row_provider(extractor, validator, language=args.language)
    cost_model = None
    if args.cost_per_1k_input is not None or args.cost_per_1k_output is not None:
        cost_model = TokenCostModel(
            input_per_1k=args.cost_per_1k_input or 0.0,
            output_per_1k=args.cost_per_1k_output or 0.0,
        )
    report = score_corpus(
        load_corpus(args.corpus), row_provider=row_provider, cost_model=cost_model
    )
    if args.as_json:
        print(json.dumps(report.to_dict(), indent=2))
        return 0
    print(
        f"Field accuracy: {report.field_accuracy:.2%} "
        f"({report.correct_fields}/{report.total_fields}) "
        f"across {report.document_count} documents "
        f"({report.owner_verified_document_count} owner-verified)."
    )
    print(f"Found-value accuracy: {report.found_accuracy:.2%}")
    print(f"Locator coverage:     {report.locator_coverage:.2%}")
    print(f"Disputes:             {report.dispute_count}")
    perf = report.performance
    if perf.semantic_call_count:
        print("Semantic performance:")
        print(
            f"  Latency: {perf.total_latency_ms} ms total, "
            f"{perf.mean_latency_ms_per_document(report.document_count):.0f} ms/doc "
            f"across {perf.semantic_call_count} calls"
        )
        print(
            f"  Tokens:  {perf.total_input_tokens} in / {perf.total_output_tokens} out "
            f"({perf.total_tokens} total)"
        )
        if perf.estimated_cost_usd is not None:
            print(f"  Est. cost: ${perf.estimated_cost_usd:.4f}")
    weakest = sorted(
        ((c / t if t else 0.0, name) for name, (c, t) in report.per_field.items())
    )[:5]
    print("Weakest fields:")
    for acc, name in weakest:
        print(f"  {name}: {acc:.1%}")
    if report.mismatches:
        print(f"Mismatches ({len(report.mismatches)}):")
        for m in report.mismatches[:15]:
            print(f"  {m.case_id} {m.field_path}: got {m.actual!r}, want {m.expected!r}")
    ready = "READY" if report.release_ready() else "NOT READY"
    print(
        f"Phase-1 release gate: {ready} "
        "(needs >=95% accuracy, >=10 docs, >=10 owner-verified)."
    )
    return 0


def _build_layout_adapter(name: str) -> LayoutAdapter:
    if name == "text-line":
        return TextLineLayoutAdapter()
    if name == "pdfplumber":
        return PdfPlumberLayoutAdapter()
    if name == "ocr":
        return OcrLayoutAdapter()
    raise ValueError(f"unsupported layout adapter: {name}")


def _load_benchmark_cases(manifest: Path) -> tuple[LayoutBenchmarkCase, ...]:
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    entries = payload.get("cases") if isinstance(payload, dict) else payload
    if not isinstance(entries, list) or not entries:
        raise ValueError("manifest must contain a non-empty 'cases' list")
    base = manifest.resolve().parent
    cases: list[LayoutBenchmarkCase] = []
    for entry in entries:
        raw_path = Path(str(entry["path"]))
        path = raw_path if raw_path.is_absolute() else base / raw_path
        expected = entry.get("expected_locator_count")
        cases.append(
            LayoutBenchmarkCase(
                name=str(entry["name"]),
                path=path,
                minimum_text_characters=int(entry.get("minimum_text_characters", 1)),
                minimum_table_cells=int(entry.get("minimum_table_cells", 0)),
                expected_locator_count=None if expected is None else int(expected),
            )
        )
    return tuple(cases)


def _run_benchmark(args: argparse.Namespace) -> int:
    if not args.manifest.exists():
        print(f"error: manifest not found: {args.manifest}")
        return 2
    cases = _load_benchmark_cases(args.manifest)
    results = run_layout_benchmark(
        workspace=args.workspace,
        cases=cases,
        layout_adapter=_build_layout_adapter(args.adapter),
    )
    output = args.workspace / "layout_benchmark_results.json"
    if args.as_json:
        print(json.dumps([asdict(result) for result in results], indent=2))
    else:
        for result in results:
            marker = "PASS" if result.status == "passed" else "FAIL"
            print(
                f"[{marker}] {result.name}: {result.adapter} v{result.adapter_version} — "
                f"{result.text_characters} chars, {result.table_cell_count} cells, "
                f"conf {result.mean_confidence:.2f}, {result.reading_order_locators} locators, "
                f"reproducibility {result.locator_reproducibility:.0%}, {result.latency_ms}ms"
            )
            if result.issues:
                print(f"        issues: {', '.join(result.issues)}")
        print(f"Benchmark results: {output}")
    return 0 if all(result.status == "passed" for result in results) else 1


def _run_distill(args: argparse.Namespace) -> int:
    pipeline = RefineryPipeline(args.workspace)
    try:
        report = pipeline.distill(min_rule_occurrences=args.min_occurrences)
    finally:
        pipeline.close()

    output_dir = args.workspace / "distiller"
    output_dir.mkdir(parents=True, exist_ok=True)
    proposals_json = output_dir / "proposals.json"
    proposals_json.write_text(json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8")
    proposals_md = output_dir / "proposals.md"
    proposals_md.write_text(report.to_markdown(), encoding="utf-8")
    if args.ground_truth_out is not None:
        args.ground_truth_out.parent.mkdir(parents=True, exist_ok=True)
        args.ground_truth_out.write_text(
            json.dumps(report.ground_truth_fragment(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    if args.as_json:
        print(json.dumps(report.to_dict(), indent=2))
        return 0
    print(report.to_markdown(), end="")
    print(f"\nProposals: {proposals_json}")
    print(f"Proposals (markdown): {proposals_md}")
    if args.ground_truth_out is not None:
        print(f"Ground-truth fragment: {args.ground_truth_out}")
    return 0


def _run_review_time(args: argparse.Namespace) -> int:
    pipeline = RefineryPipeline(args.workspace)
    try:
        timings, summary = pipeline.review_timings()
    finally:
        pipeline.close()
    if args.as_json:
        print(
            json.dumps(
                {
                    "summary": summary.to_dict(),
                    "reviews": [timing.to_json() for timing in timings],
                },
                indent=2,
            )
        )
        return 0
    if summary.count == 0:
        print("No review-time measurements yet. Run `review` to record them.")
        return 0
    print(
        f"Review time across {summary.count} review(s): "
        f"median {summary.median_minutes:.1f}m, mean {summary.mean_minutes:.1f}m, "
        f"max {summary.max_minutes:.1f}m (target ≤{summary.target_minutes:.0f}m)."
    )
    print(f"Within target: {summary.within_target_count}/{summary.count}")
    over = [t for t in timings if t.minutes > summary.target_minutes]
    for timing in over:
        print(f"  OVER: {timing.doc_id} took {timing.minutes:.1f}m ({timing.action_count} actions)")
    gate = "MEETS" if summary.meets_target else "BELOW"
    print(f"N4 review-time gate: {gate} target.")
    return 0


def _run_corpus_check(args: argparse.Namespace) -> int:
    ground_truth_path = args.corpus / "ground_truth.json"
    if not ground_truth_path.exists():
        print(f"error: no ground_truth.json in {args.corpus}")
        return 2
    ground_truth = json.loads(ground_truth_path.read_text(encoding="utf-8"))
    problems: list[str] = []
    total = owner_verified = 0
    for case_id, meta in sorted(ground_truth.items()):
        total += 1
        if not (args.corpus / f"{case_id}.txt").exists():
            problems.append(f"{case_id}: missing {case_id}.txt")
        expected = meta.get("expected") if isinstance(meta, dict) else None
        if not isinstance(expected, dict) or not expected:
            problems.append(f"{case_id}: empty or missing 'expected' block")
        elif any(not isinstance(v, str) for v in expected.values()):
            problems.append(f"{case_id}: all expected values must be strings")
        if isinstance(meta, dict) and bool(meta.get("owner_verified", False)):
            owner_verified += 1
    orphans = sorted(
        path.stem
        for path in args.corpus.glob("*.txt")
        if path.stem not in ground_truth
    )
    for orphan in orphans:
        problems.append(f"{orphan}.txt: no ground_truth entry")

    needs = []
    if total < 10:
        needs.append(f"{10 - total} more document(s)")
    if owner_verified < 10:
        needs.append(f"{10 - owner_verified} more owner-verified document(s)")
    report = {
        "corpus": str(args.corpus),
        "document_count": total,
        "owner_verified_document_count": owner_verified,
        "problems": problems,
        "release_blockers": needs,
        "structurally_valid": not problems,
    }
    if args.as_json:
        print(json.dumps(report, indent=2))
        return 0 if not problems else 1
    print(f"Corpus: {args.corpus}")
    print(f"Documents: {total} ({owner_verified} owner-verified)")
    if problems:
        print(f"Structural problems ({len(problems)}):")
        for problem in problems:
            print(f"  - {problem}")
    else:
        print("Structure: OK")
    if needs:
        print("Release gate still needs: " + ", ".join(needs))
    else:
        print("Release gate document counts satisfied (run `accuracy` for the score).")
    return 0 if not problems else 1


def _run_memory(args: argparse.Namespace) -> int:
    store = CorrectionMemoryStore(args.workspace / "memory" / "corrections_memory.jsonl")
    entries = store.load().entries()
    if args.as_json:
        print(json.dumps([e.to_json() for e in entries], indent=2))
        return 0
    if not entries:
        print("No corrections learned yet.")
        return 0
    print(f"Learned corrections ({len(entries)}):")
    for e in entries:
        if e.is_fix:
            print(
                f"  [{e.doc_class}] {e.field_suffix}: '{e.original_value}' -> "
                f"'{e.corrected_value}'  ({e.occurrences}×, last by {e.last_reviewer})"
            )
        else:
            print(
                f"  [{e.doc_class}] {e.field_suffix}: '{e.original_value}' "
                f"disputed ({e.occurrences}×, last by {e.last_reviewer})"
            )
    return 0


def _review_summary(doc_id: str, outcome: CorrectionOutcome) -> dict[str, object]:
    counts: dict[str, int] = {}
    for record in outcome.records:
        counts[record.action.value] = counts.get(record.action.value, 0) + 1
    return {"doc_id": doc_id, "applied": len(outcome.records), "actions": counts}


def _load_corrections(
    path: Path,
) -> tuple[tuple[CorrectionRequest, ...], float | None]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    entries = payload.get("corrections") if isinstance(payload, dict) else payload
    review_seconds = (
        payload.get("review_seconds") if isinstance(payload, dict) else None
    )
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
    return tuple(requests), (None if review_seconds is None else float(review_seconds))


def _build_semantic_backends(
    *,
    provider: str,
    base_url: str | None,
    extractor_model: str | None,
    validator_model: str | None,
    timeout_seconds: float,
    max_retries: int,
    max_output_tokens: int | None,
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
                max_output_tokens=max_output_tokens,
            ),
            build_ollama_model(
                model=validator_model, session_id="ollama-validator-session",
                base_url=ollama_url, timeout_seconds=timeout_seconds, max_retries=max_retries,
                max_output_tokens=max_output_tokens,
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
            max_output_tokens=max_output_tokens,
        ),
        build_openai_compatible_model(
            model=validator_model, base_url=base_url, session_id="openai-compatible-validator",
            timeout_seconds=timeout_seconds, max_retries=max_retries,
            max_output_tokens=max_output_tokens,
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
    max_output_tokens: int | None = None,
    chunk_concurrency: int = 1,
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
    if max_output_tokens is not None and max_output_tokens <= 0:
        raise ValueError("semantic max output tokens must be positive")
    if chunk_concurrency <= 0:
        raise ValueError("semantic chunk concurrency must be positive")
    extractor_model_name, validator_model_name, extractor_backend, validator_backend = (
        _build_semantic_backends(
            provider=provider,
            base_url=base_url,
            extractor_model=extractor_model,
            validator_model=validator_model,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            max_output_tokens=max_output_tokens,
        )
    )
    extractor = SemanticExtractor(
        extractor_backend,
        extractor_version=f"{provider}-{extractor_model_name}-{constitution_version}",
        schemas=semantic_schemas(),
        chunk_concurrency=chunk_concurrency,
    )
    validator = SemanticValidator(
        validator_backend,
        schemas=semantic_schemas(),
    )
    return extractor, validator


if __name__ == "__main__":
    raise SystemExit(main())
