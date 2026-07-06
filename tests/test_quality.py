from document_refinery.quality.golden import GoldenField, evaluate_golden_set


def test_phase_one_gate_requires_ten_documents_and_95_percent() -> None:
    expected = [
        GoldenField(
            f"doc-{index}",
            "eligibility[0].eligible",
            "true",
            owner_verified=True,
        )
        for index in range(10)
    ]
    actual = {(field.doc_id, field.field_path): "true" for field in expected}
    report = evaluate_golden_set(expected, actual)
    assert report.field_accuracy == 1.0
    assert report.phase_one_release_ready()


def test_small_golden_set_cannot_release() -> None:
    expected = [GoldenField("doc-1", "eligibility[0].eligible", "true")]
    report = evaluate_golden_set(expected, {("doc-1", "eligibility[0].eligible"): "true"})
    assert not report.phase_one_release_ready()


def test_synthetic_set_can_pass_technical_gate_but_not_owner_gate() -> None:
    expected = [
        GoldenField(f"doc-{index}", "eligibility[0].eligible", "true")
        for index in range(10)
    ]
    actual = {(field.doc_id, field.field_path): "true" for field in expected}
    report = evaluate_golden_set(expected, actual)
    assert report.technical_regression_ready()
    assert not report.phase_one_release_ready()
