#!/usr/bin/env python3
"""Wire a document into the provenance-tracked corpus in one step.

Given a file (already downloaded — this environment cannot fetch it for you) and
its metadata, this computes the SHA-256, copies it into ``example_schedules/``,
and upserts a ``manifest.json`` entry. With ``--check`` it also runs the document
through the pipeline (no semantic provider) and reports whether it reaches Gate A
via a deterministic profile or routes to classification review, so you can set
``--route`` correctly.

Examples
--------
Real unknown-layout schedule (e.g. a Clearstream or Fed haircut PDF):

    python scripts/add_corpus_document.py path/to/clearstream-criteria.pdf \\
        --title "Clearstream collateral criteria and allocation profiles" \\
        --source-url "https://www.clearstream.com/.../collateral-criteria.pdf" \\
        --route classification_review --profile unknown --check

Document that matches an existing deterministic profile:

    python scripts/add_corpus_document.py path/to/schedule.pdf \\
        --title "..." --source-url "https://..." \\
        --route deterministic --profile cme --expected-records 17 --check
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from document_refinery.golden import corpus  # noqa: E402

CORPUS_DIR = REPO_ROOT / "example_schedules"
MANIFEST_PATH = CORPUS_DIR / "manifest.json"


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    source = Path(args.file)
    if not source.exists():
        print(f"error: file not found: {source}")
        return 2

    target = CORPUS_DIR / source.name
    if source.resolve() != target.resolve():
        shutil.copy2(source, target)
        print(f"copied {source} -> {target}")

    entry = corpus.build_entry(
        path=target.name,
        title=args.title,
        source_url=args.source_url,
        sha256=corpus.sha256_of(target),
        profile=args.profile,
        expected_route=args.route,
        expected_minimum_eligibility_records=args.expected_records,
        synthetic=args.synthetic,
        note=args.note,
    )

    if args.check:
        observed = _observe_route(target)
        print(f"observed pipeline route: {observed}")
        if observed != args.route:
            print(
                f"warning: --route {args.route} but the pipeline routed as {observed}; "
                "adjust --route (and --expected-records) to match."
            )

    manifest = corpus.load_manifest(MANIFEST_PATH)
    manifest["documents"] = corpus.upsert_entry(manifest["documents"], entry)
    corpus.save_manifest(MANIFEST_PATH, manifest)
    print(f"updated {MANIFEST_PATH} with entry for {target.name}")
    return 0


def _observe_route(document: Path) -> str:
    from document_refinery.application.pipeline import RefineryPipeline
    from document_refinery.infrastructure.tasks import TaskStatus

    workspace = Path(tempfile.mkdtemp()) / "check"
    pipeline = RefineryPipeline(workspace)
    try:
        result = pipeline.run(document, source="corpus-check")
        status = pipeline.tasks.get(result.document.doc_id).status
        return "deterministic" if status is TaskStatus.GATE_A_PENDING else "unexpected"
    except ValueError as error:
        if "classification requires owner review" in str(error):
            return "classification_review"
        raise
    finally:
        pipeline.close()


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Add a document to the test corpus.")
    parser.add_argument("file", help="path to the downloaded document")
    parser.add_argument("--title", required=True)
    parser.add_argument("--source-url", required=True, dest="source_url")
    parser.add_argument("--profile", default="unknown")
    parser.add_argument(
        "--route",
        choices=("deterministic", "classification_review"),
        default="classification_review",
    )
    parser.add_argument("--expected-records", type=int, default=0, dest="expected_records")
    parser.add_argument("--synthetic", action="store_true")
    parser.add_argument("--note")
    parser.add_argument(
        "--check",
        action="store_true",
        help="run the pipeline to observe the actual route before writing",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
