"""Failure semantics taxonomy for the AutoWebDelivery pipeline (Sprint S2).

Models the six classes from PROJECT_CONTEXT "Failure semantics":
``retryable`` / ``optional`` / ``degraded_success`` / ``hard_failure`` /
``blocked`` / ``not_verified``.

Rule: do not hide mandatory failures as warnings. This module is the
canonical home for classification helpers used at the points S2 touches
(Phase-06 decision parsing U-09, quality scorecard verdicts U-06) so every
missing-evidence / malformed-input case degrades to an explicit, classifiable
outcome instead of a silent default.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class FailureClass(str, Enum):
    """Canonical failure classes for the pipeline."""

    RETRYABLE = "retryable"
    OPTIONAL = "optional"
    DEGRADED_SUCCESS = "degraded_success"
    HARD_FAILURE = "hard_failure"
    BLOCKED = "blocked"
    NOT_VERIFIED = "not_verified"


@dataclass(frozen=True)
class FailureSemantics:
    """Semantics attached to a failure class.

    Attributes:
        failure_class: The taxonomy class.
        blocks_deployment: Whether this outcome forbids deployment.
        retryable: Whether retrying may change the outcome.
        detail: Human-readable context.
    """

    failure_class: FailureClass
    blocks_deployment: bool = False
    retryable: bool = False
    detail: str = ""


# ResultEnvelope.Status values -> failure semantics.
# "done" is a clean success (None); everything else is classified here.
_PHASE_STATUS_SEMANTICS: dict[str, FailureSemantics] = {
    "blocked": FailureSemantics(FailureClass.BLOCKED, blocks_deployment=True, retryable=False),
    "failed": FailureSemantics(FailureClass.HARD_FAILURE, blocks_deployment=True, retryable=False),
    "needs_review": FailureSemantics(FailureClass.BLOCKED, blocks_deployment=True, retryable=False),
    "skipped": FailureSemantics(FailureClass.OPTIONAL, blocks_deployment=False, retryable=True),
}


def classify_phase_status(status: str, *, hard_block: bool = False) -> FailureSemantics | None:
    """Map a phase result-envelope status onto the taxonomy.

    Returns ``None`` for a clean ``"done"``; otherwise a ``FailureSemantics``
    whose ``detail`` records the observed status.
    """
    if not status:
        return FailureSemantics(
            FailureClass.BLOCKED,
            blocks_deployment=True,
            detail="phase returned no status",
        )
    normalized = status.lower()
    if normalized == "done":
        if hard_block:
            return FailureSemantics(
                FailureClass.HARD_FAILURE,
                blocks_deployment=True,
                detail="phase done but hard_block set",
            )
        return None
    if normalized in _PHASE_STATUS_SEMANTICS:
        base = _PHASE_STATUS_SEMANTICS[normalized]
        return FailureSemantics(
            base.failure_class,
            blocks_deployment=base.blocks_deployment,
            retryable=base.retryable or hard_block,
            detail=f"phase status '{status}'",
        )
    return FailureSemantics(
        FailureClass.HARD_FAILURE,
        blocks_deployment=True,
        detail=f"unknown phase status '{status}'",
    )


def classify_scorecard_verdict(verdict: str, *, production: bool = True) -> FailureSemantics | None:
    """Map a quality-scorecard overall verdict onto the taxonomy.

    ``NOT_VERIFIED`` never passes; in production it blocks deployment, in
    preview mode the outcome is recorded but does not block the phase
    (PROJECT_CONTEXT: preview/non-production behavior may remain more permissive).
    Returns ``None`` for ``PASS`` (clean success).
    """
    normalized = (verdict or "").upper()
    if normalized == "PASS":
        return None
    if normalized == "NOT_VERIFIED":
        return FailureSemantics(
            FailureClass.NOT_VERIFIED,
            blocks_deployment=production,
            retryable=False,
            detail=f"scorecard verdict '{verdict}' - mandatory evidence not verified",
        )
    if normalized == "NEEDS_EDIT":
        return FailureSemantics(
            FailureClass.DEGRADED_SUCCESS,
            blocks_deployment=production,
            retryable=True,
            detail=f"scorecard verdict '{verdict}' - degraded success",
        )
    if normalized == "REJECT":
        return FailureSemantics(
            FailureClass.HARD_FAILURE,
            blocks_deployment=True,
            retryable=False,
            detail=f"scorecard verdict '{verdict}'",
        )
    return FailureSemantics(
        FailureClass.HARD_FAILURE,
        blocks_deployment=True,
        detail=f"unknown scorecard verdict '{verdict}'",
    )


@dataclass(frozen=True)
class FailureContext:
    """Structured context for one orchestrator-level phase failure (R1-04).

    Carries enough detail to classify and audit a failure after the fact:
    where it happened (``phase``/``run_id``/``artifact``), what went wrong
    (``error``), and how it classifies. The category reuses the canonical
    :class:`FailureClass` taxonomy — no parallel classification scheme.

    Attributes:
        phase: Phase key (e.g. ``"04"``) that failed.
        error: Human-readable error message (joined envelope errors).
        run_id: Run the failure belongs to, when known.
        artifact: Path to the failing phase's artifact directory, when known.
        retryable: Whether retrying may change the outcome.
        category: Canonical :class:`FailureClass` for this failure.
    """

    phase: str
    error: str
    run_id: str | None = None
    artifact: str | None = None
    retryable: bool = False
    category: FailureClass = FailureClass.HARD_FAILURE

    def to_dict(self) -> dict:
        """JSON-safe dict for summaries, logs and recorded result payloads."""
        return {
            "phase": self.phase,
            "run_id": self.run_id,
            "artifact": self.artifact,
            "error": self.error,
            "retryable": self.retryable,
            "category": self.category.value if isinstance(self.category, FailureClass) else str(self.category),
        }


def classify_failure(
    phase: str,
    *,
    status: str | None = None,
    error: str = "",
    run_id: str | None = None,
    artifact: str | None = None,
) -> FailureContext:
    """Combine :func:`classify_phase_status` with an error message (R1-04).

    Args:
        phase: Phase key that failed.
        status: Observed result-envelope status; ``None`` means the failure was
            detected without an envelope (e.g. an exception), classified as
            :attr:`FailureClass.HARD_FAILURE`.
        error: Error message; falls back to the semantics-derived detail when
            empty.
        run_id: Optional run id for the context.
        artifact: Optional artifact path for the context.

    Returns:
        A :class:`FailureContext` in the canonical taxonomy.
    """
    semantics = classify_phase_status(status) if status else FailureSemantics(FailureClass.HARD_FAILURE)
    return FailureContext(
        phase=phase,
        error=error or semantics.detail,
        run_id=run_id,
        artifact=artifact,
        retryable=semantics.retryable,
        category=semantics.failure_class,
    )


@dataclass(frozen=True)
class Phase06Counts:
    """Structured Phase-06 gate counts parsed from the decisions line."""

    approved: int
    needs_edit: int
    rejected: int

    @property
    def total(self) -> int:
        return self.approved + self.needs_edit + self.rejected

    def to_tuple(self) -> tuple[int, int, int]:
        return (self.approved, self.needs_edit, self.rejected)


class Phase06DecisionError(ValueError):
    """Raised when Phase-06 decisions do not match the expected structured line.

    Sprint S2 (U-09): the orchestrator must never silently fall back to a
    count of 0 when the decision line is malformed or missing.
    """


# Canonical producer format (phase_06_strict_quality_gate.py:442,
# phase_06_quality_gate.py:487): "Approved: X, Needs edit: Y, Rejected: Z"
_PHASE06_DECISION_RE = re.compile(
    r"^\s*Approved:\s*(\d+)\s*,\s*Needs edit:\s*(\d+)\s*,\s*Rejected:\s*(\d+)\s*$",
    re.IGNORECASE,
)


def parse_phase_06_decisions(decisions: list[str]) -> Phase06Counts:
    """Parse the canonical Phase-06 gate decision line.

    Args:
        decisions: envelope ``decisions`` list, e.g. from ``run_strict_phase_06``.

    Returns:
        Structured counts.

    Raises:
        Phase06DecisionError: if no decision line matches the expected
            ``"Approved: X, Needs edit: Y, Rejected: Z"`` format.
    """
    observed: list[str] = []
    for line in decisions or []:
        observed.append(str(line))
        match = _PHASE06_DECISION_RE.match(str(line))
        if match:
            return Phase06Counts(
                approved=int(match.group(1)),
                needs_edit=int(match.group(2)),
                rejected=int(match.group(3)),
            )
    raise Phase06DecisionError(
        "Phase-06 decisions did not contain the expected "
        "'Approved: X, Needs edit: Y, Rejected: Z' line (U-09, fail-closed). "
        f"Observed decisions: {observed!r}"
    )
