"""Frozen Pydantic contracts and domain specifications for AICONNEX Compiler."""

from src.compiler.contracts.base import BaseContract
from src.compiler.contracts.client import ClientContract
from src.compiler.contracts.enums import (
    ArchiveType,
    DateEpoch,
    DuplicatePolicy,
    ErrorCode,
    ErrorSeverity,
    JobExecutionState,
    JobResultState,
    PartialBatchPolicy,
    PlanOperationType,
    SharingTier,
    UnitSource,
)
from src.compiler.contracts.investigation import InvestigationResult, UnresolvedIssue
from src.compiler.contracts.manifests import FileEntry, HandoffManifest, UploadManifest
from src.compiler.contracts.observation import ObservationId
from src.compiler.contracts.plans import ParsePlan, PlanOperation
from src.compiler.contracts.recipes import Recipe, StructuralSignature
from src.compiler.contracts.signals import AssetMap, SignalDefinition, SignalDictionary
from src.compiler.contracts.structure import (
    CellDetail,
    RegionBoundary,
    SheetStructure,
    WorkbookStructure,
)
from src.compiler.contracts.validation import (
    BatchValidationReport,
    ValidationErrorItem,
    ValidationReport,
)

__all__ = [
    "BaseContract",
    "JobExecutionState",
    "JobResultState",
    "ErrorSeverity",
    "ErrorCode",
    "UnitSource",
    "PlanOperationType",
    "SharingTier",
    "ArchiveType",
    "DuplicatePolicy",
    "PartialBatchPolicy",
    "DateEpoch",
    "ObservationId",
    "SignalDefinition",
    "SignalDictionary",
    "AssetMap",
    "RegionBoundary",
    "CellDetail",
    "SheetStructure",
    "WorkbookStructure",
    "PlanOperation",
    "ParsePlan",
    "StructuralSignature",
    "Recipe",
    "ClientContract",
    "ValidationErrorItem",
    "ValidationReport",
    "BatchValidationReport",
    "FileEntry",
    "UploadManifest",
    "HandoffManifest",
    "InvestigationResult",
    "UnresolvedIssue",
]
