"""Spreadsheet readers and structural extraction baseline."""

from pathlib import Path

from src.compiler.readers.base import ExcelReader, ProbeResult
from src.compiler.readers.calamine_reader import CalamineReader
from src.compiler.readers.date_duration import (
    is_duration_format,
    parse_duration_to_seconds,
    parse_excel_date,
)
from src.compiler.readers.formula_handler import (
    FormulaInspection,
    extract_external_references,
    inspect_formula_cell,
)
from src.compiler.readers.openpyxl_reader import OpenpyxlReader


def get_reader(
    source: bytes | Path | None = None,
    prefer_calamine: bool = True,
) -> ExcelReader:
    """Factory returning high-throughput Calamine reader first, with Openpyxl as fallback."""
    if not prefer_calamine:
        return OpenpyxlReader()
    try:
        reader = CalamineReader()
        if source is not None:
            reader.probe(source)
        return reader
    except Exception:
        return OpenpyxlReader()


__all__ = [
    "CalamineReader",
    "ExcelReader",
    "FormulaInspection",
    "OpenpyxlReader",
    "ProbeResult",
    "extract_external_references",
    "get_reader",
    "inspect_formula_cell",
    "is_duration_format",
    "parse_duration_to_seconds",
    "parse_excel_date",
]
