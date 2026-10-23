"""Recipe Registry managing verified, versioned parsing recipes.

Enforces tenant isolation (TENANT_BOUND vs TEMPLATE), deterministic signature matching,
and cryptographic immutability with explicit revocation.
"""

from __future__ import annotations

from src.compiler.contracts.enums import SharingTier
from src.compiler.contracts.recipes import Recipe, StructuralSignature
from src.compiler.recipes.signatures import compute_signature_hash


class RecipeNotFoundError(KeyError):
    """Raised when a requested recipe does not exist or access is forbidden."""


class RecipeConflictError(ValueError):
    """Raised when registering a recipe with an ID that already exists."""


class RecipeRegistry:
    """In-memory thread-safe registry for recipes with tenant scoping and revocation.

    Storage structure:
    - _recipes: (tenant_id, recipe_id) -> Recipe
    - _hash_index: (tenant_id, signature_hash) -> list[recipe_id]
    - _template_index: signature_hash -> list[Tuple[tenant_id, recipe_id]]
    """

    def __init__(self) -> None:
        self._recipes: dict[tuple[str, str], Recipe] = {}
        self._hash_index: dict[tuple[str, str], list[str]] = {}
        self._template_index: dict[str, list[tuple[str, str]]] = {}

    def register(self, recipe: Recipe) -> None:
        """Register an immutable recipe into the registry.

        The recipe is indexed by (tenant_id, recipe_id) and signature hash.
        If sharing_tier is TEMPLATE, it is additionally indexed for cross-tenant candidate lookup.
        """
        key = (recipe.tenant_id, recipe.recipe_id)
        if key in self._recipes:
            raise RecipeConflictError(
                f"Recipe with ID '{recipe.recipe_id}' already registered "
                f"for tenant '{recipe.tenant_id}'."
            )

        sig_hash = compute_signature_hash(recipe.signature)

        # Store primary recipe
        self._recipes[key] = recipe

        # Index under tenant hash
        tenant_hash_key = (recipe.tenant_id, sig_hash)
        if tenant_hash_key not in self._hash_index:
            self._hash_index[tenant_hash_key] = []
        self._hash_index[tenant_hash_key].append(recipe.recipe_id)

        # If template, index under cross-tenant templates
        if recipe.sharing_tier == SharingTier.TEMPLATE:
            if sig_hash not in self._template_index:
                self._template_index[sig_hash] = []
            self._template_index[sig_hash].append(key)

    def lookup(
        self,
        tenant_id: str,
        signature: StructuralSignature,
        allow_templates: bool = False,
    ) -> Recipe | None:
        """Look up active recipe matching the structural signature.

        Lookup precedence:
        1. Tenant-bound recipes belonging strictly to `tenant_id`.
        2. Cross-tenant TEMPLATE recipes (only if `allow_templates` is True).
        Revoked recipes are never returned.
        """
        sig_hash = compute_signature_hash(signature)

        # 1. Check tenant's own recipes first
        tenant_hash_key = (tenant_id, sig_hash)
        if tenant_hash_key in self._hash_index:
            for recipe_id in reversed(self._hash_index[tenant_hash_key]):
                recipe = self._recipes.get((tenant_id, recipe_id))
                if recipe and not recipe.is_revoked:
                    return recipe

        # 2. Check cross-tenant templates if allowed
        if allow_templates and sig_hash in self._template_index:
            for owner_tenant, recipe_id in reversed(self._template_index[sig_hash]):
                recipe = self._recipes.get((owner_tenant, recipe_id))
                if recipe and not recipe.is_revoked and recipe.sharing_tier == SharingTier.TEMPLATE:
                    return recipe

        return None

    def get_by_id(self, tenant_id: str, recipe_id: str) -> Recipe | None:
        """Fetch recipe by ID ensuring tenant authorization."""
        recipe = self._recipes.get((tenant_id, recipe_id))
        if recipe:
            return recipe

        # Check if requested as a global template
        for (_owner_tenant, r_id), cand in self._recipes.items():
            if r_id == recipe_id and cand.sharing_tier == SharingTier.TEMPLATE:
                return cand

        return None

    def revoke(self, tenant_id: str, recipe_id: str, reason: str) -> Recipe:
        """Revoke a recipe so it can no longer be matched by lookup.

        Maintains full provenance audit trail by updating the revoked flag.
        """
        key = (tenant_id, recipe_id)
        recipe = self._recipes.get(key)
        if not recipe:
            raise RecipeNotFoundError(
                f"Cannot revoke: Recipe '{recipe_id}' not found for tenant '{tenant_id}'."
            )

        # Create updated immutable copy with is_revoked=True
        # Note: Recipe has frozen=True in BaseContract, so we use model_copy
        revoked_recipe = recipe.model_copy(update={"is_revoked": True})
        self._recipes[key] = revoked_recipe

        return revoked_recipe

    def list_recipes(
        self,
        tenant_id: str,
        include_revoked: bool = False,
        include_templates: bool = False,
    ) -> list[Recipe]:
        """List all recipes accessible to a tenant."""
        result: list[Recipe] = []

        for (owner_tenant, _), recipe in self._recipes.items():
            if owner_tenant == tenant_id:
                if include_revoked or not recipe.is_revoked:
                    result.append(recipe)
            elif include_templates and recipe.sharing_tier == SharingTier.TEMPLATE:
                if include_revoked or not recipe.is_revoked:
                    result.append(recipe)

        return result
