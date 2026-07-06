"""Production semantic provider adapters and approval policy."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from document_refinery.agents.semantic import SemanticModel, SemanticRequest, SemanticResponse


@dataclass(frozen=True, slots=True)
class DataRetentionPolicy:
    provider: str
    retention_tier: str
    geographic_processing: str
    logging: str
    credential_policy: str
    approved_for_production_calls: bool
    policy_version: str = "semantic-provider-policy-2026-07-06"

    def require_approved(self) -> None:
        if not self.approved_for_production_calls:
            raise ValueError("semantic provider policy is not approved for production calls")
        if self.provider != "openai":
            raise ValueError(f"unapproved semantic provider: {self.provider}")
        if self.retention_tier != "zero-data-retention":
            raise ValueError("production semantic calls require zero-data-retention")


APPROVED_OPENAI_POLICY = DataRetentionPolicy(
    provider="openai",
    retention_tier="zero-data-retention",
    geographic_processing=(
        "US processing preferred; no production call unless account/project "
        "retention settings are verified before deployment."
    ),
    logging=(
        "Application stores only request/response hashes and encrypted response "
        "artifacts; provider-side prompt/completion logging must be disabled by "
        "zero-data-retention."
    ),
    credential_policy=(
        "Use per-environment service-account API keys from OPENAI_API_KEY; never "
        "persist keys in artifacts, domain rows, or review packets."
    ),
    approved_for_production_calls=True,
)


class OpenAISemanticModel(SemanticModel):
    """OpenAI Responses API adapter behind the provider-neutral SemanticModel protocol."""

    def __init__(
        self,
        *,
        model: str,
        api_key: str | None = None,
        session_id: str | None = None,
        base_url: str = "https://api.openai.com/v1/responses",
        timeout_seconds: float = 60.0,
        max_retries: int = 2,
        retry_base_delay_seconds: float = 1.0,
        policy: DataRetentionPolicy = APPROVED_OPENAI_POLICY,
    ) -> None:
        policy.require_approved()
        self._model = model
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self._api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAI semantic calls")
        self._session_id = session_id or f"openai-{uuid4()}"
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds
        if max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if retry_base_delay_seconds < 0:
            raise ValueError("retry_base_delay_seconds must be non-negative")
        self.max_retries = max_retries
        self.retry_base_delay_seconds = retry_base_delay_seconds

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def provider(self) -> str:
        return "openai"

    @property
    def model(self) -> str:
        return self._model

    def generate(self, request: SemanticRequest) -> SemanticResponse:
        payload = {
            "model": self._model,
            "input": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_payload},
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "document_refinery_semantic_response",
                    "schema": request.response_schema,
                    "strict": True,
                }
            },
            "metadata": {
                "document_refinery_session_id": request.session_id,
                "document_refinery_prompt_version": request.prompt_version,
            },
        }
        data = json.dumps(payload).encode("utf-8")
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            started = time.monotonic()
            try:
                http_request = urllib.request.Request(
                    self.base_url,
                    data=data,
                    method="POST",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                )
                with urllib.request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                    body = json.loads(response.read().decode("utf-8"))
                return SemanticResponse(
                    content=_response_text(body),
                    provider=self.provider,
                    model=self._model,
                    response_id=str(body.get("id") or "unknown-response"),
                    created_at=datetime.now(UTC),
                    latency_ms=int((time.monotonic() - started) * 1000),
                    usage=_usage(body),
                )
            except urllib.error.HTTPError as error:
                last_error = error
                if error.code not in {408, 409, 429, 500, 502, 503, 504}:
                    break
            except (TimeoutError, urllib.error.URLError) as error:
                last_error = error
            if attempt < self.max_retries:
                time.sleep(self.retry_base_delay_seconds * (2**attempt))
        raise RuntimeError("OpenAI semantic call failed closed") from last_error


def _response_text(body: dict[str, object]) -> str:
    text = body.get("output_text")
    if isinstance(text, str):
        return text
    chunks: list[str] = []
    output = body.get("output")
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            contents = item.get("content")
            if not isinstance(contents, list):
                continue
            for content in contents:
                if isinstance(content, dict) and isinstance(content.get("text"), str):
                    chunks.append(content["text"])
    if chunks:
        return "".join(chunks)
    raise ValueError("OpenAI response did not contain output text")


def _usage(body: dict[str, object]) -> dict[str, int]:
    usage = body.get("usage")
    if not isinstance(usage, dict):
        return {}
    output: dict[str, int] = {}
    for key in ("input_tokens", "output_tokens", "total_tokens"):
        value = usage.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            output[key] = value
    return output
