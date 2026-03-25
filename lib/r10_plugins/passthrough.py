"""No-op R10a plugin — always passes. Use as default or as template."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from lib.r10_plugins.base_plugin import R10Plugin


class PassthroughPlugin(R10Plugin):
    def validate(self, output_path: str, reference_data_path: str, step_id: str) -> dict[str, Any]:
        return {
            "step_id": step_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "PASS",
            "checks": [{"id": "PASS-001", "name": "passthrough", "status": "pass", "detail": "No mechanical validation configured."}],
            "errors": [],
        }
