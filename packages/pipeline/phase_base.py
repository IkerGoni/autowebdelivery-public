"""Base phase executor class."""

from abc import ABC, abstractmethod
from typing import Any


class PhaseBase(ABC):
    """Abstract base class for phase executors."""

    def __init__(self, workspace: str, run_id: str):
        self.workspace = workspace
        self.run_id = run_id

    @property
    @abstractmethod
    def name(self) -> str:
        """Phase name identifier."""
        ...

    @abstractmethod
    def validate_inputs(self) -> list[str]:
        """Check required inputs exist. Returns list of missing fields."""
        ...

    @abstractmethod
    def execute(self) -> dict[str, Any]:
        """Run phase logic. Returns result dict for result.json."""
        ...

    def run(self) -> dict[str, Any]:
        """Full phase execution: validate, execute, return result."""
        from pipeline.result_envelope import ResultEnvelope

        missing = self.validate_inputs()
        if missing:
            return ResultEnvelope.blocked(
                phase=self.name,
                run_id=self.run_id,
                missing_fields=missing,
            ).to_dict()

        result = self.execute()
        return result

    def write_result(self, result: dict[str, Any]) -> str:
        """Write result.json to workspace. Returns path."""
        from pipeline.json_io import write_result

        result_path = f"{self.workspace}/{self.name}/result.json"
        return write_result(result_path, result)