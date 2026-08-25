"""Phase result envelope matching pipeline_data_contract.md."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Status(str, Enum):
    """Phase result status values."""
    DONE = "done"
    BLOCKED = "blocked"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"
    SKIPPED = "skipped"


class ResultEnvelope(BaseModel):
    """Standard phase result envelope per pipeline_data_contract.md."""
    phase: str
    status: Status = Status.DONE
    run_id: str = ""
    inputs_used: list[str] = Field(default_factory=list)
    outputs_created: list[str] = Field(default_factory=list)
    records_processed: int = 0
    records_created: int = 0
    records_skipped: int = 0
    missing_fields: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    next_tasks: list[str] = Field(default_factory=list)
    hard_block: bool = False

    model_config = ConfigDict(use_enum_values=True)

    @classmethod
    def done(
        cls,
        phase: str,
        run_id: str = "",
        inputs_used: list[str] | None = None,
        outputs_created: list[str] | None = None,
        records_processed: int = 0,
        records_created: int = 0,
        decisions: list[str] | None = None,
    ) -> "ResultEnvelope":
        """Create a successful result envelope."""
        return cls(
            phase=phase,
            status=Status.DONE,
            run_id=run_id,
            inputs_used=inputs_used or [],
            outputs_created=outputs_created or [],
            records_processed=records_processed,
            records_created=records_created,
            decisions=decisions or [],
        )

    @classmethod
    def blocked(
        cls,
        phase: str,
        run_id: str = "",
        missing_fields: list[str] | None = None,
        errors: list[str] | None = None,
        inputs_used: list[str] | None = None,
    ) -> "ResultEnvelope":
        """Create a blocked result envelope for missing inputs."""
        return cls(
            phase=phase,
            status=Status.BLOCKED,
            run_id=run_id,
            inputs_used=inputs_used or [],
            missing_fields=missing_fields or [],
            errors=errors or [f"Missing required input: {f}" for f in (missing_fields or [])],
        )

    @classmethod
    def failed(
        cls,
        phase: str,
        run_id: str = "",
        errors: list[str] | None = None,
        inputs_used: list[str] | None = None,
        hard_block: bool = False,
    ) -> "ResultEnvelope":
        """Create a failed result envelope."""
        return cls(
            phase=phase,
            status=Status.FAILED,
            run_id=run_id,
            inputs_used=inputs_used or [],
            errors=errors or [],
            hard_block=hard_block,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to plain dict for JSON serialization."""
        return self.model_dump(exclude_none=True, by_alias=True)