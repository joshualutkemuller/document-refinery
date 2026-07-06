"""Terminal-driven Gate A review: no web app, pure CLI.

``build_review_requests`` walks silver rows and collects owner confirm/correct/
dispute actions through injected ``prompt``/``echo`` callables, which keeps the
loop unit-testable without real stdin. ``render_review`` produces a read-only
plain-text view for `review --list`.
"""

from __future__ import annotations

from collections.abc import Callable

from document_refinery.application.correction_memory import LearnedCorrection
from document_refinery.application.corrections import CorrectionAction, CorrectionRequest
from document_refinery.domain.models import SilverExtraction, ValidatorStatus

Prompt = Callable[[str], str]
Echo = Callable[[str], None]
Suggestions = dict[str, LearnedCorrection]

_MENU = "  [c]onfirm  c[o]rrect  [d]ispute  [s]kip  [q]uit: "


def _memory_hint(suggestion: LearnedCorrection | None) -> str | None:
    if suggestion is None:
        return None
    if suggestion.is_fix:
        return (
            f"      ↳ memory: previously corrected to '{suggestion.corrected_value}' "
            f"({suggestion.occurrences}×)"
        )
    return f"      ↳ memory: previously disputed ({suggestion.occurrences}×) — review carefully"


def render_review(
    rows: tuple[SilverExtraction, ...],
    *,
    suggestions: Suggestions | None = None,
) -> str:
    suggestions = suggestions or {}
    lines: list[str] = []
    for index, row in enumerate(rows, start=1):
        marker = "  << disputed" if row.validator_status is ValidatorStatus.DISPUTED else ""
        lines.append(f"[{index:>2}] {row.field_path}{marker}")
        lines.append(f"      value:   {row.effective_value}")
        lines.append(f"      status:  {row.validator_status.value}")
        lines.append(f"      locator: {row.source_locator}")
        lines.append(f"      clause:  {row.source_clause}")
        hint = _memory_hint(suggestions.get(row.extraction_id))
        if hint:
            lines.append(hint)
    return "\n".join(lines)


def build_review_requests(
    rows: tuple[SilverExtraction, ...],
    *,
    prompt: Prompt,
    echo: Echo,
    pending_only: bool = False,
    suggestions: Suggestions | None = None,
) -> tuple[CorrectionRequest, ...]:
    """Interactively collect reviewer actions for the given rows.

    Gate A means the owner reviews every value, so all rows are walked by default.
    ``pending_only`` narrows the walk to rows still needing attention
    (non-confirmed) for faster re-review passes. Learned corrections from
    ``suggestions`` are shown, and a remembered fix pre-fills a blank correction.
    Returns immediately on quit, keeping the actions collected so far.
    """
    suggestions = suggestions or {}
    requests: list[CorrectionRequest] = []
    total = len(rows)
    for index, row in enumerate(rows, start=1):
        if pending_only and row.validator_status is ValidatorStatus.CONFIRMED:
            continue
        suggestion = suggestions.get(row.extraction_id)
        echo("")
        echo(f"({index}/{total}) {row.field_path}")
        echo(f"      value:   {row.effective_value}")
        echo(f"      status:  {row.validator_status.value}")
        echo(f"      locator: {row.source_locator}")
        echo(f"      clause:  {row.source_clause}")
        hint = _memory_hint(suggestion)
        if hint:
            echo(hint)
        action = _prompt_row(row, prompt=prompt, echo=echo, suggestion=suggestion)
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
    suggestion: LearnedCorrection | None = None,
) -> CorrectionRequest | None:
    remembered = suggestion.corrected_value if suggestion and suggestion.is_fix else None
    while True:
        choice = prompt(_MENU).strip().lower()
        if choice in {"c", "confirm"}:
            return CorrectionRequest(row.extraction_id, CorrectionAction.CONFIRM)
        if choice in {"o", "correct"}:
            hint = f" [enter=memory '{remembered}']" if remembered else ""
            value = prompt(f"      corrected value{hint}: ").strip() or (remembered or "")
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
