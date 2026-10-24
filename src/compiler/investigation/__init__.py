"""Bounded agent investigation module with data residency enforcement."""

from src.compiler.investigation.agent import (
    InvestigationAgent,
    InvestigationAudit,
    InvestigationBudget,
    InvestigationResult,
)
from src.compiler.investigation.container_spec import HardenedContainerConfig
from src.compiler.investigation.contract import to_review_item, unwrap_for_executor
from src.compiler.investigation.model_client import (
    DeterministicFakeModelClient,
    ModelClient,
    ModelMessage,
    ModelResponse,
)
from src.compiler.investigation.residency import (
    ModelResidency,
    ResidencyPolicy,
    check_model_residency_permission,
)
from src.compiler.investigation.supervisor import (
    SandboxMetadata,
    SandboxOutcome,
    SandboxSupervisor,
)
from src.compiler.investigation.tools import InvestigationToolbox

__all__ = [
    "DeterministicFakeModelClient",
    "InvestigationAgent",
    "InvestigationAudit",
    "InvestigationBudget",
    "InvestigationResult",
    "InvestigationToolbox",
    "HardenedContainerConfig",
    "SandboxSupervisor",
    "SandboxOutcome",
    "SandboxMetadata",
    "ModelClient",
    "ModelMessage",
    "ModelResidency",
    "ModelResponse",
    "ResidencyPolicy",
    "check_model_residency_permission",
    "to_review_item",
    "unwrap_for_executor",
]
