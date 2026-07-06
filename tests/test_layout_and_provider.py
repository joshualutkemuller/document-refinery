from __future__ import annotations

import json
from pathlib import Path

import pytest

from document_refinery.agents.semantic import (
    SemanticExtractor,
    SemanticRequest,
    SemanticResponse,
    SemanticValidator,
)
from document_refinery.application.pipeline import RefineryPipeline
from document_refinery.infrastructure.artifacts import ArtifactStore
from document_refinery.infrastructure.layout import LayoutArtifact, LayoutPage, LayoutQualityReport
from document_refinery.infrastructure.layout_benchmark import (
    LayoutBenchmarkCase,
    run_layout_benchmark,
)
from document_refinery.infrastructure.semantic_providers import (
    APPROVED_OPENAI_POLICY,
    DataRetentionPolicy,
    OpenAISemanticModel,
)


def test_text_artifact_persists_coordinate_layout_layer(tmp_path: Path) -> None:
    source = tmp_path / "schedule.txt"
    source.write_text("Line one\nLine two", encoding="utf-8")
    store = ArtifactStore(tmp_path / "artifacts")
    document = store.ingest(source, source="test")
    enriched, artifact = store.extract_text(document)

    layout = json.loads(Path(artifact.layout_uri).read_text(encoding="utf-8"))
    assert enriched.layout_artifact_uri == artifact.layout_uri
    assert layout["adapter"] == "text-line-layout"
    assert layout["pages"][0]["lines"][0]["locator"] == "page=1;line=1"
    assert layout["pages"][0]["lines"][0]["bbox"] == {
        "x0": 0.0,
        "y0": 0.0,
        "x1": 8.0,
        "y1": 1.0,
    }
    assert layout["pages"][0]["reading_order"] == ["page=1;line=1", "page=1;line=2"]


def test_openai_policy_requires_zero_data_retention() -> None:
    policy = DataRetentionPolicy(
        provider="openai",
        retention_tier="standard-retention",
        geographic_processing="US",
        logging="standard",
        credential_policy="env",
        approved_for_production_calls=True,
    )
    with pytest.raises(ValueError, match="zero-data-retention"):
        policy.require_approved()
    APPROVED_OPENAI_POLICY.require_approved()


def test_openai_adapter_maps_responses_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps({
                "id": "resp-1",
                "output_text": '{"extractions": []}',
                "usage": {"input_tokens": 11, "output_tokens": 7, "total_tokens": 18},
            }).encode()

    def fake_urlopen(request: object, timeout: float) -> FakeResponse:
        captured["timeout"] = timeout
        captured["body"] = json.loads(request.data.decode("utf-8"))  # type: ignore[attr-defined]
        return FakeResponse()

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    model = OpenAISemanticModel(
        model="gpt-5.5", session_id="extractor-session", retry_base_delay_seconds=0
    )
    response = model.generate(
        SemanticRequest(
            session_id="extractor-session",
            system_prompt="system",
            user_payload="payload",
            response_schema={"type": "object"},
            prompt_version="v1",
        )
    )

    assert response.provider == "openai"
    assert response.model == "gpt-5.5"
    assert response.response_id == "resp-1"
    assert response.usage == {"input_tokens": 11, "output_tokens": 7, "total_tokens": 18}
    assert response.latency_ms is not None
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["text"]["format"]["strict"] is True  # type: ignore[index]
    assert body["metadata"]["document_refinery_session_id"] == "extractor-session"  # type: ignore[index]


def test_openai_adapter_retries_transient_errors_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = 0

    class FakeResponse:
        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps({"id": "resp-2", "output_text": '{"judgments": []}'}).encode()

    def fake_urlopen(request: object, timeout: float) -> FakeResponse:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise TimeoutError("transient timeout")
        return FakeResponse()

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    model = OpenAISemanticModel(
        model="gpt-5.5",
        session_id="validator-session",
        max_retries=1,
        retry_base_delay_seconds=0,
    )

    response = model.generate(
        SemanticRequest(
            session_id="validator-session",
            system_prompt="system",
            user_payload="payload",
            response_schema={"type": "object"},
            prompt_version="v1",
        )
    )

    assert attempts == 2
    assert response.response_id == "resp-2"


class FailingLayoutAdapter:
    adapter_name = "failing-layout"
    adapter_version = "1.0.0"

    def analyze(self, *, doc_id: str, path: Path, pages: tuple[str, ...]) -> LayoutArtifact:
        return LayoutArtifact(
            doc_id,
            self.adapter_name,
            self.adapter_version,
            (LayoutPage(1, None, None, (), (), ()),),
            LayoutQualityReport("failed", 0.0, 0, 0, ("no_text_coordinates",)),
        )


class UncalledSemanticModel:
    session_id = "session-a"
    provider = "scripted"
    model = "test-model"

    def generate(self, request: SemanticRequest) -> SemanticResponse:
        raise AssertionError("semantic model must not run when layout quality fails")


def test_structurally_failed_layout_blocks_semantic_extraction(tmp_path: Path) -> None:
    source = tmp_path / "unknown.txt"
    source.write_text("This is an unseen template.", encoding="utf-8")
    model = UncalledSemanticModel()
    pipeline = RefineryPipeline(
        tmp_path / "workspace",
        semantic_extractor=SemanticExtractor(
            model,
            constitution="Extract eligibility terms.",
            schema_dictionary="eligibility[].asset_criterion: criterion",
            schema_version="eligibility-1.0.0",
            constitution_version="constitution-1.0.0",
            extractor_version="extractor-1.0.0",
        ),
        semantic_validator=SemanticValidator(
            model,
            schema_dictionary="eligibility[].asset_criterion: criterion",
            schema_version="eligibility-1.0.0",
            constitution_version="constitution-1.0.0",
        ),
        layout_adapter=FailingLayoutAdapter(),
    )

    with pytest.raises(ValueError, match="layout artifact failed structural quality gates"):
        pipeline.run(source, source="test")
    pipeline.close()


def test_layout_benchmark_publishes_threshold_results(tmp_path: Path) -> None:
    source = tmp_path / "benchmark.txt"
    source.write_text("Header\nCell A | Cell B", encoding="utf-8")

    results = run_layout_benchmark(
        workspace=tmp_path / "benchmark-workspace",
        cases=(LayoutBenchmarkCase("multi-column-smoke", source, minimum_text_characters=5),),
        layout_adapter=ArtifactStore(tmp_path / "unused").layout_adapter,
    )

    assert results[0].status == "passed"
    output = tmp_path / "benchmark-workspace" / "layout_benchmark_results.json"
    assert json.loads(output.read_text(encoding="utf-8"))[0]["reading_order_locators"] == 2
