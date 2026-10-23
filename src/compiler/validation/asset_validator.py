"""Asset roster compliance validation against ClientContract."""

from __future__ import annotations

import pyarrow as pa

from src.compiler.contracts.client import ClientContract
from src.compiler.contracts.enums import ErrorCode, ErrorSeverity
from src.compiler.contracts.validation import ValidationErrorItem


def validate_asset_roster(
    measurements: pa.Table,
    contract: ClientContract,
) -> tuple[list[ValidationErrorItem], list[ValidationErrorItem]]:
    """Validate that extracted assets conform to the client's expected asset roster.

    Returns (errors, warnings).
    """
    errors: list[ValidationErrorItem] = []
    warnings: list[ValidationErrorItem] = []

    if measurements.num_rows == 0:
        return errors, warnings

    present_assets = set(measurements.column("asset_id").to_pylist())
    expected_assets = set(contract.expected_assets)

    # 1. Unexpected assets in data
    unexpected = present_assets - expected_assets
    for unexp in sorted(unexpected):
        errors.append(
            ValidationErrorItem(
                code=ErrorCode.ERR_VAL_MISSING_ASSET,
                severity=ErrorSeverity.ERROR,
                message=(
                    f"Extracted asset '{unexp}' is not present in approved client asset roster "
                    f"{sorted(expected_assets)}."
                ),
                remediation=(
                    f"Map raw equipment tag for '{unexp}' to canonical asset_id "
                    "or add asset to ClientContract expected_assets."
                ),
            )
        )

    # 2. Missing expected assets from data (informational/warning per file)
    missing = expected_assets - present_assets
    for mis in sorted(missing):
        warnings.append(
            ValidationErrorItem(
                code=ErrorCode.ERR_VAL_MISSING_ASSET,
                severity=ErrorSeverity.INFO,
                message=f"Expected asset '{mis}' is absent from this workbook.",
                remediation="Expected asset will be reconciled across the broader batch.",
            )
        )

    return errors, warnings
