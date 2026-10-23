"""Batch assembly and cross-file reconciliation package (Phase 9.5).

Coordinates multi-file dataset combination, asset completeness verification,
and cross-file conflict detection without speculative manipulation.
"""

from src.compiler.batch.assembler import BatchAssembler
from src.compiler.batch.reconciler import BatchReconciler, ReconciliationReport
from src.compiler.batch.types import BatchAssemblyResult, FileProcessingOutcome

__all__ = [
    "BatchAssembler",
    "BatchReconciler",
    "ReconciliationReport",
    "BatchAssemblyResult",
    "FileProcessingOutcome",
]
