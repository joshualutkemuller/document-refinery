"""Run the packaged eligibility golden corpus."""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib.resources import files

from document_refinery.agents.eligibility import (
    EligibilityAdversarialValidator,
    EligibilityScheduleExtractor,
)
from document_refinery.quality.golden import GoldenField, GoldenSetReport, evaluate_golden_set


@dataclass(frozen=True, slots=True)
class RegressionResult:
    report: GoldenSetReport
    disputed_fields: int


def run_packaged_regression() -> RegressionResult:
    corpus_text = files("document_refinery.golden").joinpath("eligibility_v1.json").read_text()
    cases = json.loads(corpus_text)
    extractor = EligibilityScheduleExtractor()
    validator = EligibilityAdversarialValidator()
    expected: list[GoldenField] = []
    actual: dict[tuple[str, str], str] = {}
    disputed = 0
    for case in cases:
        case_id = str(case["case_id"])
        rows = extractor.extract(doc_id=case_id, text=str(case["text"]))
        validated = validator.validate(text=str(case["text"]), extractions=rows)
        disputed += sum(row.validator_status.value == "disputed" for row in validated)
        for row in validated:
            actual[(case_id, row.field_path)] = row.normalized_value
        for field_path, value in case["expected"].items():
            expected.append(
                GoldenField(
                    doc_id=case_id,
                    field_path=field_path,
                    expected_value=str(value),
                    owner_verified=bool(case["owner_verified"]),
                )
            )
    return RegressionResult(
        report=evaluate_golden_set(expected, actual),
        disputed_fields=disputed,
    )
