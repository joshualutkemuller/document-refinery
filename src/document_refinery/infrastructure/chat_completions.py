"""Chat Completions semantic adapters: local Ollama and generic OpenAI-compatible.

Both speak the widely-implemented ``/v1/chat/completions`` API with JSON-schema
structured outputs, behind the provider-neutral ``SemanticModel`` protocol so no
SDK types or credentials leak into the domain layer.

Security posture (why Ollama is the default):

- ``ollama`` runs a local model server (default ``http://localhost:11434``);
  document text never leaves the machine, so it is zero-data-retention by
  construction and the right default for confidential agreements.
- ``openai-compatible`` points at a third-party endpoint (Groq, Together,
  OpenRouter, …). Document text is sent off-machine; retention/ZDR is that
  provider's responsibility and is NOT covered by the approved OpenAI ZDR
  policy. Use it for non-confidential test documents unless you have verified
  the provider's retention terms.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from uuid import uuid4

from document_refinery.agents.semantic import SemanticRequest, SemanticResponse

_TRANSIENT_STATUS = {408, 409, 429, 500, 502, 503, 504}
DEFAULT_OLLAMA_URL = "http://localhost:11434/v1/chat/completions"


class ChatCompletionsSemanticModel:
    """Adapter for any OpenAI-compatible ``/v1/chat/completions`` endpoint."""

    def __init__(
        self,
        *,
        model: str,
        base_url: str,
        provider: str,
        session_id: str,
        api_key: str | None = None,
        timeout_seconds: float = 60.0,
        max_retries: int = 2,
        retry_base_delay_seconds: float = 1.0,
    ) -> None:
        if not model:
            raise ValueError("a model name is required")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        if retry_base_delay_seconds < 0:
            raise ValueError("retry_base_delay_seconds must be non-negative")
        self._model = model
        self._provider = provider
        self._session_id = session_id
        self.base_url = base_url
        self._api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.retry_base_delay_seconds = retry_base_delay_seconds

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def provider(self) -> str:
        return self._provider

    @property
    def model(self) -> str:
        return self._model

    def generate(self, request: SemanticRequest) -> SemanticResponse:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_payload},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "document_refinery_semantic_response",
                    "schema": request.response_schema,
                    "strict": True,
                },
            },
            "temperature": 0,
        }
        data = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            started = time.monotonic()
            try:
                http_request = urllib.request.Request(
                    self.base_url, data=data, method="POST", headers=headers
                )
                with urllib.request.urlopen(
                    http_request, timeout=self.timeout_seconds
                ) as response:
                    body = json.loads(response.read().decode("utf-8"))
                return SemanticResponse(
                    content=_message_content(body),
                    provider=self._provider,
                    model=self._model,
                    response_id=str(body.get("id") or "unknown-response"),
                    created_at=datetime.now(UTC),
                    latency_ms=int((time.monotonic() - started) * 1000),
                    usage=_usage(body),
                )
            except urllib.error.HTTPError as error:
                last_error = error
                if error.code not in _TRANSIENT_STATUS:
                    break
            except (TimeoutError, urllib.error.URLError) as error:
                last_error = error
            if attempt < self.max_retries:
                time.sleep(self.retry_base_delay_seconds * (2**attempt))
        raise RuntimeError(f"{self._provider} semantic call failed closed") from last_error


def build_ollama_model(
    *,
    model: str,
    session_id: str,
    base_url: str = DEFAULT_OLLAMA_URL,
    timeout_seconds: float = 60.0,
    max_retries: int = 2,
) -> ChatCompletionsSemanticModel:
    """Local Ollama server; no API key, data stays on the machine."""
    return ChatCompletionsSemanticModel(
        model=model,
        base_url=base_url,
        provider="ollama",
        session_id=session_id,
        api_key=None,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
    )


def build_openai_compatible_model(
    *,
    model: str,
    base_url: str,
    session_id: str,
    api_key_env: str = "OPENAI_COMPATIBLE_API_KEY",
    timeout_seconds: float = 60.0,
    max_retries: int = 2,
) -> ChatCompletionsSemanticModel:
    """Generic third-party OpenAI-compatible endpoint (data leaves the machine)."""
    if not base_url:
        raise ValueError("--semantic-base-url is required for the openai-compatible provider")
    api_key = os.environ.get(api_key_env)
    if not api_key:
        raise ValueError(f"{api_key_env} is required for the openai-compatible provider")
    return ChatCompletionsSemanticModel(
        model=model,
        base_url=base_url,
        provider="openai-compatible",
        session_id=session_id or f"openai-compatible-{uuid4()}",
        api_key=api_key,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
    )


def _message_content(body: dict[str, object]) -> str:
    choices = body.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            message = first.get("message")
            if isinstance(message, dict):
                content = message.get("content")
                if isinstance(content, str):
                    return content
    raise ValueError("chat completion response did not contain message content")


def _usage(body: dict[str, object]) -> dict[str, int]:
    usage = body.get("usage")
    if not isinstance(usage, dict):
        return {}
    mapping = {
        "prompt_tokens": "input_tokens",
        "completion_tokens": "output_tokens",
        "total_tokens": "total_tokens",
    }
    output: dict[str, int] = {}
    for source_key, target_key in mapping.items():
        value = usage.get(source_key)
        if isinstance(value, int) and not isinstance(value, bool):
            output[target_key] = value
    return output
