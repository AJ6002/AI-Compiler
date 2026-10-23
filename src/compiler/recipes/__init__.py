"""Recipes, Structural Signatures, Drift Detection, and Review Queue (Phase 9).

This module manages the caching, versioning, drift detection, and steward promotion
of verified spreadsheet parse plans.
"""

from src.compiler.contracts.enums import SharingTier
from src.compiler.contracts.recipes import Recipe, StructuralSignature
from src.compiler.recipes.registry import (
    RecipeConflictError,
    RecipeNotFoundError,
    RecipeRegistry,
)
from src.compiler.recipes.review import (
    ReviewItem,
    ReviewQueue,
    ReviewStatus,
)
from src.compiler.recipes.signatures import (
    DriftDetector,
    DriftReport,
    DriftType,
    SignatureGenerator,
    compute_signature_hash,
)

__all__ = [
    # Contracts
    "Recipe",
    "StructuralSignature",
    "SharingTier",
    # Signatures & Drift
    "DriftType",
    "DriftReport",
    "SignatureGenerator",
    "compute_signature_hash",
    "DriftDetector",
    # Registry
    "RecipeRegistry",
    "RecipeConflictError",
    "RecipeNotFoundError",
    # Review Queue
    "ReviewStatus",
    "ReviewItem",
    "ReviewQueue",
]
