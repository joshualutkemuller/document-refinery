"""Small operational CLI for local validation and SQL discovery."""

from __future__ import annotations

import argparse
import json
from importlib.resources import files
from pathlib import Path

from document_refinery.application.pipeline import RefineryPipeline
from document_refinery.domain.models import SilverExtraction
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
    return parser


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
        )
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
        )
    return 0


def _run_documents(
    paths: tuple[Path, ...],
    *,
    workspace: Path,
    source: str,
    approved_by: str | None,
    language: str,
) -> None:
    pipeline = RefineryPipeline(workspace)
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


if __name__ == "__main__":
    raise SystemExit(main())
