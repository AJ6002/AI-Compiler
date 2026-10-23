"""Admission Gate and secure raw storage package."""

from src.compiler.admission.config import AdmissionConfig
from src.compiler.admission.gate import AdmissionGate
from src.compiler.admission.inspector import inspect_archive
from src.compiler.admission.models import AdmissionResult, InspectionOutcome

__all__ = [
    "AdmissionConfig",
    "AdmissionGate",
    "AdmissionResult",
    "InspectionOutcome",
    "inspect_archive",
]
