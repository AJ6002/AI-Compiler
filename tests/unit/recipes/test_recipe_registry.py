"""Unit tests for RecipeRegistry scoping, tenant isolation, and revocation."""

from datetime import UTC, datetime

import pytest

from src.compiler.contracts.enums import PlanOperationType, SharingTier
from src.compiler.contracts.plans import ParsePlan, PlanOperation
from src.compiler.contracts.recipes import Recipe
from src.compiler.recipes.registry import (
    RecipeConflictError,
    RecipeNotFoundError,
    RecipeRegistry,
)
from src.compiler.recipes.signatures import SignatureGenerator


def _make_dummy_recipe(
    recipe_id: str,
    tenant_id: str,
    headers: list[str],
    sharing_tier: SharingTier = SharingTier.TENANT_BOUND,
) -> Recipe:
    sig = SignatureGenerator.create(
        sheet_names=["Sheet1"],
        header_patterns=headers,
        merge_fingerprint=["A1:B1"],
    )
    plan = ParsePlan(
        tenant_id=tenant_id,
        project_id="proj_1",
        plan_id=f"plan_{recipe_id}",
        target_sheet="Sheet1",
        operations=[
            PlanOperation(op=PlanOperationType.SELECT_REGION, params={"min_row": 1, "max_row": 50})
        ],
    )
    return Recipe(
        recipe_id=recipe_id,
        tenant_id=tenant_id,
        project_id="proj_1",
        version="1.0.0",
        generation_system="scada_exporter",
        sharing_tier=sharing_tier,
        signature=sig,
        plan=plan,
        approved_by="steward@aiconnex.com",
        approved_at=datetime.now(UTC),
        is_revoked=False,
    )


def test_register_and_lookup_tenant_bound():
    """Verify tenant-bound recipe lookup matches within same tenant."""
    registry = RecipeRegistry()
    recipe_a = _make_dummy_recipe("rcp_a", "tenant_alpha", ["TIME", "VAL"])
    registry.register(recipe_a)

    matched = registry.lookup("tenant_alpha", recipe_a.signature)
    assert matched is not None
    assert matched.recipe_id == "rcp_a"
    assert matched.tenant_id == "tenant_alpha"


def test_tenant_isolation_boundary():
    """Verify tenant B cannot lookup or access tenant A's TENANT_BOUND recipe."""
    registry = RecipeRegistry()
    recipe_a = _make_dummy_recipe("rcp_a", "tenant_alpha", ["TIME", "VAL"])
    registry.register(recipe_a)

    # Tenant Beta has an identical signature
    matched = registry.lookup("tenant_beta", recipe_a.signature, allow_templates=False)
    assert matched is None, "Tenant Beta must not see Tenant Alpha's tenant-bound recipe."

    # Direct ID lookup also enforces tenant boundaries
    assert registry.get_by_id("tenant_beta", "rcp_a") is None


def test_template_sharing_with_explicit_permission():
    """Verify TEMPLATE recipe is returned across tenants only when allow_templates is True."""
    registry = RecipeRegistry()
    template_recipe = _make_dummy_recipe(
        "rcp_template",
        "system_admin",
        ["TIME", "COMMON_METRIC"],
        sharing_tier=SharingTier.TEMPLATE,
    )
    registry.register(template_recipe)

    # Lookup by Tenant Beta with allow_templates=False
    matched_denied = registry.lookup(
        "tenant_beta", template_recipe.signature, allow_templates=False
    )
    assert matched_denied is None

    # Lookup by Tenant Beta with allow_templates=True
    matched_allowed = registry.lookup(
        "tenant_beta", template_recipe.signature, allow_templates=True
    )
    assert matched_allowed is not None
    assert matched_allowed.recipe_id == "rcp_template"
    assert matched_allowed.sharing_tier == SharingTier.TEMPLATE


def test_revocation_suppresses_lookups():
    """Revoking a recipe ensures it is never returned by subsequent lookups."""
    registry = RecipeRegistry()
    recipe = _make_dummy_recipe("rcp_active", "tenant_alpha", ["TIME", "SIGNAL_1"])
    registry.register(recipe)

    # Initial lookup succeeds
    assert registry.lookup("tenant_alpha", recipe.signature) is not None

    # Revoke recipe
    revoked = registry.revoke("tenant_alpha", "rcp_active", reason="Deprecated by SCADA upgrade")
    assert revoked.is_revoked is True

    # Subsequent lookup returns None
    assert registry.lookup("tenant_alpha", recipe.signature) is None


def test_register_duplicate_conflict_rejection():
    """Attempting to register a duplicate recipe ID under the same tenant raises error."""
    registry = RecipeRegistry()
    recipe1 = _make_dummy_recipe("rcp_dup", "tenant_alpha", ["TIME", "V1"])
    recipe2 = _make_dummy_recipe("rcp_dup", "tenant_alpha", ["TIME", "V2"])

    registry.register(recipe1)
    with pytest.raises(RecipeConflictError):
        registry.register(recipe2)


def test_revoke_nonexistent_recipe_raises():
    """Revoking a nonexistent recipe raises RecipeNotFoundError."""
    registry = RecipeRegistry()
    with pytest.raises(RecipeNotFoundError):
        registry.revoke("tenant_alpha", "rcp_nonexistent", reason="Audit")
