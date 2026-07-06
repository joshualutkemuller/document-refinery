"""Terminal-driven Gate A review: no web app, pure CLI.

``build_review_requests`` walks silver rows and collects owner confirm/correct/
dispute actions through injected ``prompt``/``echo`` callables, which keeps the
loop unit-testable without real stdin. ``render_review`` produces a read-only
plain-text view for `review --list`.
"""

from __future__ import annotations

from collections.abc import Callable

from document_refinery.application.corrections import CorrectionAction, CorrectionRequest
from document_refinery.domain.models import SilverExtraction, ValidatorStatus

Prompt = Callable[[str], str]
Echo = Callable[[str], None]

_MENU = "  [c]onfirm  c[o]rrect  [d]ispute  [s]kip  [q]uit: "


def render_review(rows: tuple[SilverExtraction, ...]) -> str:
    lines: list[str] = []
    for index, row in enumerate(rows, start=1):
        marker = "  << disputed" if row.validator_status is ValidatorStatus.DISPUTED else ""
        lines.append(f"[{index:>2}] {row.field_path}{marker}")
        lines.append(f"      value:   {row.effective_value}")
        lines.append(f"      status:  {row.validator_status.value}")
        lines.append(f"      locator: {row.source_locator}")
        lines.append(f"      clause:  {row.source_clause}")
    return "\n".join(lines)


def build_review_requests(
    rows: tuple[SilverExtraction, ...],
    *,
    prompt: Prompt,
    echo: Echo,
    pending_only: bool = False,
) -> tuple[CorrectionRequest, ...]:
    """Interactively collect reviewer actions for the given rows.

    Gate A means the owner reviews every value, so all rows are walked by default.
    ``pending_only`` narrows the walk to rows still needing attention
    (non-confirmed) for faster re-review passes. Returns immediately on quit,
    keeping the actions collected so far.
    """
    requests: list[CorrectionRequest] = []
    total = len(rows)
    for index, row in enumerate(rows, start=1):
        if pending_only and row.validator_status is ValidatorStatus.CONFIRMED:
            continue
        echo("")
        echo(f"({index}/{total}) {row.field_path}")
        echo(f"      value:   {row.effective_value}")
        echo(f"      status:  {row.validator_status.value}")
        echo(f"      locator: {row.source_locator}")
        echo(f"      clause:  {row.source_clause}")
        action = _prompt_row(row, prompt=prompt, echo=echo)
        if action is _QUIT:
            break
        if action is not None:
            requests.append(action)
    return tuple(requests)


# Sentinel distinguishing "quit the whole review" from "skip this row" (None).
_QUIT = CorrectionRequest(extraction_id="__quit__", action=CorrectionAction.CONFIRM)


def _prompt_row(
    row: SilverExtraction,
    *,
    prompt: Prompt,
    echo: Echo,
) -> CorrectionRequest | None:
    while True:
        choice = prompt(_MENU).strip().lower()
        if choice in {"c", "confirm"}:
            return CorrectionRequest(row.extraction_id, CorrectionAction.CONFIRM)
        if choice in {"o", "correct"}:
            value = prompt("      corrected value: ").strip()
            if not value:
                echo("      a correction needs a value; try again")
                continue
            note = prompt("      note (optional): ").strip() or None
            return CorrectionRequest(
                row.extraction_id,
                CorrectionAction.CORRECT,
                corrected_value=value,
                note=note,
            )
        if choice in {"d", "dispute"}:
            note = prompt("      dispute reason: ").strip()
            if not note:
                echo("      a dispute needs a reason; try again")
                continue
            return CorrectionRequest(
                row.extraction_id,
                CorrectionAction.DISPUTE,
                note=note,
            )
        if choice in {"s", "skip", ""}:
            return None
        if choice in {"q", "quit"}:
            return _QUIT
        echo("      unrecognized choice; enter c, o, d, s, or q")
