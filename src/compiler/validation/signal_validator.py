"""Signal and unit validation against ClientContract."""

from __future__ import annotations

import pyarrow as pa

from src.compiler.contracts.client import ClientContract
from src.compiler.contracts.enums import ErrorCode, ErrorSeverity
from src.compiler.contracts.validation import ValidationErrorItem
from src.compiler.structure.types import DiscoveredLayout


def validate_signals_and_units(
    measurements: pa.Table,
    contract: ClientContract,
    layout: DiscoveredLayout | None = None,
) -> tuple[list[ValidationErrorItem], list[ValidationErrorItem], dict[str, float]]:
    """Validate required signal presence and authorized engineering units.

    Returns (errors, warnings, signal_coverage_map).
    """
    errors: list[ValidationErrorItem] = []
    warnings: list[ValidationErrorItem] = []
    coverage: dict[str, float] = {}

    if measurements.num_rows == 0:
        errors.append(
            ValidationErrorItem(
                code=ErrorCode.ERR_VAL_MISSING_SIGNAL,
                severity=ErrorSeverity.ERROR,
                message="Emitted measurement table is completely empty; zero signals present.",
                remediation="Inspect workbook extraction plan and ensure data rows are not empty.",
            )
        )
        return errors, warnings, coverage

    # Extract present unique signals
    present_signals = set(measurements.column("signal_id").to_pylist())

    # 1. Required signals check
    for req_sig in contract.required_signals:
        # Match exact signal_id or leaf name or path suffix
        is_present = req_sig in present_signals or any(
            s.endswith(f".{req_sig}") or req_sig.endswith(f".{s}") for s in present_signals
        )
        coverage[req_sig] = 1.0 if is_present else 0.0

        if not is_present:
            errors.append(
                ValidationErrorItem(
                    code=ErrorCode.ERR_VAL_MISSING_SIGNAL,
                    severity=ErrorSeverity.ERROR,
                    message=f"Mandatory signal '{req_sig}' is missing from extracted dataset.",
                    signal_path=req_sig,
                    remediation=(
                        f"Verify that workbook contains header '{req_sig}' "
                        "or update ClientContract required_signals."
                    ),
                )
            )

    # 2. Optional signals check
    for opt_sig in contract.optional_signals:
        is_present = opt_sig in present_signals or any(
            s.endswith(f".{opt_sig}") or opt_sig.endswith(f".{s}") for s in present_signals
        )
        coverage[opt_sig] = 1.0 if is_present else 0.0
        if not is_present:
            warnings.append(
                ValidationErrorItem(
                    code=ErrorCode.ERR_VAL_MISSING_SIGNAL,
                    severity=ErrorSeverity.INFO,
                    message=f"Optional signal '{opt_sig}' is not present in extracted dataset.",
                    signal_path=opt_sig,
                    remediation="Informational: optional signal absent from current source.",
                )
            )

    # 3. Unit validation against allowed_units
    # Check if layout contains units in metadata or column headers
    if layout and contract.allowed_units:
        for meta in layout.metadata_entries:
            key_upper = meta.key.upper()
            if "UNIT" in key_upper:
                # Compare found unit to allowed units
                unit_str = str(meta.value).strip()
                # Check if this matches any allowed unit for the relevant signals
                all_allowed = {u for u_list in contract.allowed_units.values() for u in u_list}
                if all_allowed and unit_str not in all_allowed:
                    errors.append(
                        ValidationErrorItem(
                            code=ErrorCode.ERR_VAL_UNRESOLVED_UNIT,
                            severity=ErrorSeverity.ERROR,
                            message=(
                                f"Metadata unit '{unit_str}' is not in approved contract units "
                                f"{sorted(all_allowed)}."
                            ),
                            cell_coordinate=meta.key_coordinate,
                            remediation=(
                                "Update ClientContract allowed_units or correct workbook unit."
                            ),
                        )
                    )

    return errors, warnings, coverage
