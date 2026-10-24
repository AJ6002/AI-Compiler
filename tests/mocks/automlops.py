"""Mock AutoMLOps consumer simulating downstream production model training ingestion."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from src.compiler.contracts.enums import JobResultState
from src.compiler.contracts.manifests import HandoffManifest
from src.compiler.storage.object_store import ObjectStore


class ConsumptionReport(BaseModel):
    """Result of downstream AutoMLOps evaluation of a published dataset."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    accepted_for_training: bool
    dataset_id: str
    rejection_reason: str | None = None
    staged_records_count: int = Field(default=0, ge=0)


class MockAutoMLOpsConsumer:
    """Simulates automated downstream ML consumer enforcing data quality and verification gates."""

    def __init__(self, store: ObjectStore) -> None:
        self.store = store

    def consume(self, handoff: HandoffManifest) -> ConsumptionReport:
        """Evaluate handoff manifest and determine eligibility for automated model training."""
        # 1. Gate on result state: strictly reject unverified datasets
        if handoff.result_state != JobResultState.ACCEPTED:
            return ConsumptionReport(
                accepted_for_training=False,
                dataset_id=handoff.dataset_id,
                rejection_reason=(
                    f"ERR_AUTOMLOPS_UNVERIFIED_DATASET: State '{handoff.result_state}'. "
                    "Unverified datasets are blocked from model training."
                ),
            )

        # 2. Gate on missing equipment coverage
        if handoff.assets_missing:
            return ConsumptionReport(
                accepted_for_training=False,
                dataset_id=handoff.dataset_id,
                rejection_reason=(
                    f"ERR_AUTOMLOPS_INCOMPLETE_ASSETS: Missing assets: {handoff.assets_missing}."
                ),
            )

        # 3. Check table references exist in object storage
        for table_uri in handoff.measurement_tables:
            if table_uri != "none" and not self.store.exists(table_uri):
                return ConsumptionReport(
                    accepted_for_training=False,
                    dataset_id=handoff.dataset_id,
                    rejection_reason=(
                        f"ERR_AUTOMLOPS_MISSING_TABLE: Table missing at '{table_uri}'."
                    ),
                )

        return ConsumptionReport(
            accepted_for_training=True,
            dataset_id=handoff.dataset_id,
            staged_records_count=handoff.assets_accepted * 40,
        )
