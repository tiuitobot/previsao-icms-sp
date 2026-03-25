"""Base interface for R10a mechanical validation plugins."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class R10Plugin(ABC):
    """Abstract plugin API for mechanical validations.

    Implement validate() to check step output against reference data.
    Return {"status": "PASS"|"FAIL", "checks": [...], "errors": [...]}.
    """

    @abstractmethod
    def validate(
        self,
        output_path: str,
        reference_data_path: str,
        step_id: str,
    ) -> dict[str, Any]:
        raise NotImplementedError
