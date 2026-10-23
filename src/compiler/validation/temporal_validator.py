"""Temporal validation: timezone normalization, cadence regularity, and duplicate policies."""

from __future__ import annotations

import datetime
from collections import defaultdict

import pyarrow as pa

from src.compiler.contracts.client import ClientContract
from src.compiler.contracts.enums import DuplicatePolicy, ErrorCode, ErrorSeverity
from src.compiler.contracts.validation import ValidationErrorItem


def validate_temporal_characteristics(
    measurements: pa.Table,
    contract: ClientContract,
) -> tuple[list[ValidationErrorItem], list[ValidationErrorItem]]:
    """Validate timezone compliance, cadence regularity, and duplicate timestamp policies.

    Returns (errors, warnings).
    """
    errors: list[ValidationErrorItem] = []
    warnings: list[ValidationErrorItem] = []

    if measurements.num_rows == 0:
        return errors, warnings

    timestamps = measurements.column("timestamp_utc").to_pylist()
    assets = measurements.column("asset_id").to_pylist()
    signals = measurements.column("signal_id").to_pylist()
    values = measurements.column("value").to_pylist()

    # 1. Timezone inspection
    # Ensure timestamps are valid UTC datetimes
    for idx, ts in enumerate(timestamps):
        if ts is None:
            errors.append(
                ValidationErrorItem(
                    code=ErrorCode.ERR_VAL_TIMEZONE_AMBIGUOUS,
                    severity=ErrorSeverity.ERROR,
                    message=f"Row {idx + 1} contains null or unresolvable timestamp.",
                    remediation="Ensure all telemetry rows contain a valid parseable timestamp.",
                )
            )
            break
        elif isinstance(ts, datetime.datetime) and ts.tzinfo is None:
            errors.append(
                ValidationErrorItem(
                    code=ErrorCode.ERR_VAL_TIMEZONE_AMBIGUOUS,
                    severity=ErrorSeverity.ERROR,
                    message="Extracted timestamp is naive (lacks UTC timezone indicator).",
                    remediation="Normalize workbook timestamps to UTC.",
                )
            )
            break

    # Group timestamps and values by (asset, signal) to verify cadence and duplicates
    times_by_asset: dict[str, list[datetime.datetime]] = defaultdict(list)
    values_by_asset_time_sig: dict[tuple[str, datetime.datetime, str], list[float | None]] = (
        defaultdict(list)
    )

    for a, t, s, v in zip(assets, timestamps, signals, values, strict=False):
        if t is not None:
            times_by_asset[a].append(t)
            values_by_asset_time_sig[(a, t, s)].append(v)

    # 2. Duplicate timestamp policy check
    if contract.duplicate_timestamp_policy == DuplicatePolicy.ERROR_ON_DISAGREEMENT:
        for (a, t, s), val_list in values_by_asset_time_sig.items():
            if len(val_list) > 1:
                # Check if all values agree
                distinct_vals = {v for v in val_list if v is not None}
                if len(distinct_vals) > 1:
                    errors.append(
                        ValidationErrorItem(
                            code=ErrorCode.ERR_VAL_CROSS_FILE_DISAGREEMENT,
                            severity=ErrorSeverity.ERROR,
                            message=(
                                f"Duplicate timestamp '{t.isoformat()}' on asset '{a}' "
                                f"signal '{s}' contains conflicting values {distinct_vals}."
                            ),
                            signal_path=s,
                            remediation=(
                                "Resolve conflicting source records in data steward review."
                            ),
                        )
                    )
                    break

    # 3. Cadence regularity check
    if contract.expected_cadence_seconds:
        expected = float(contract.expected_cadence_seconds)
        for a, ts_list in times_by_asset.items():
            # Get unique sorted timestamps for this asset
            unique_ts = sorted(set(ts_list))
            if len(unique_ts) < 2:
                continue

            gaps_found = 0
            for i in range(len(unique_ts) - 1):
                delta_sec = (unique_ts[i + 1] - unique_ts[i]).total_seconds()
                # Check for significant irregularity (> 2x expected cadence or < 0.5x expected)
                if delta_sec > 2.0 * expected or delta_sec < 0.5 * expected:
                    gaps_found += 1

            if gaps_found > 0:
                warnings.append(
                    ValidationErrorItem(
                        code=ErrorCode.ERR_VAL_CADENCE_IRREGULAR,
                        severity=ErrorSeverity.WARNING,
                        message=(
                            f"Asset '{a}' exhibits {gaps_found} cadence irregularities "
                            f"(expected sampling interval: {expected}s)."
                        ),
                        remediation=(
                            "Verify sampling interval consistency or adjust contract cadence."
                        ),
                    )
                )

    return errors, warnings
