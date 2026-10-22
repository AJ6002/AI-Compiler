"""Observation identity contract and deterministic key generator."""

import hashlib
from datetime import datetime

from pydantic import Field, model_validator

from src.compiler.contracts.base import BaseContract


class ObservationId(BaseContract):
    """Represents the canonical identity of a single source observation row."""

    asset_id: str = Field(
        ...,
        description="Canonical asset identifier associated with this observation.",
    )
    timestamp_utc: datetime | None = Field(
        default=None,
        description="Resolved UTC timestamp. Null only under non-temporal contracts.",
    )
    raw_source_row: int = Field(
        ...,
        ge=1,
        description="Original 1-indexed spreadsheet row number.",
    )
    source_file: str = Field(
        ...,
        description="Relative source filename within the upload archive.",
    )
    observation_key: str = Field(
        default="",
        description="Deterministic hash uniquely identifying this observation.",
    )

    @model_validator(mode="after")
    def _compute_key(self) -> "ObservationId":
        """Compute SHA-256 observation key if not provided."""
        if not self.observation_key:
            ts_str = self.timestamp_utc.isoformat() if self.timestamp_utc else "NONE"
            raw_token = (
                f"{self.tenant_id}|{self.project_id}|{self.asset_id}|"
                f"{ts_str}|{self.source_file}|{self.raw_source_row}"
            )
            object.__setattr__(
                self,
                "observation_key",
                hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
            )
        return self
