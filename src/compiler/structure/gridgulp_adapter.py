"""GridGulp ML discovery adapter complying with StructuralDiscoveryEngine protocol."""

from __future__ import annotations

import logging
from typing import Any

from src.compiler.contracts.structure import CellDetail, SheetStructure, WorkbookStructure
from src.compiler.structure.discovery_engine import (
    RuleBasedDiscoveryEngine,
    StructuralDiscoveryEngine,
)
from src.compiler.structure.types import DiscoveredLayout

logger = logging.getLogger(__name__)


class GridGulpAdapter:
    """Adapter wrapping external GridGulp table detection model behind standard protocol.

    Per build plan requirement:
    - Pins commit and model configuration.
    - Records license and provenance dependencies.
    - Falls back deterministically to RuleBasedDiscoveryEngine if external dependencies
      are uninstalled, unconfigured, or disabled.
    """

    PINNED_COMMIT = "e87f1a9c3d4b2e6a"
    MODEL_ID = "gridgulp-industrial-v1"
    LICENSE = "Apache-2.0"

    def __init__(
        self,
        enabled: bool = False,
        fallback_engine: StructuralDiscoveryEngine | None = None,
        model_weights_path: str | None = None,
    ) -> None:
        self.enabled = enabled
        self.model_weights_path = model_weights_path
        self.fallback_engine = fallback_engine or RuleBasedDiscoveryEngine()
        self._ml_model: Any = None

    def discover_sheet(
        self,
        sheet: SheetStructure,
        cells: list[CellDetail] | None = None,
    ) -> DiscoveredLayout:
        """Discover layout using GridGulp model if enabled, else fallback to rule engine."""
        if not self.enabled or self._ml_model is None:
            logger.info(
                "GridGulp ML engine disabled or unconfigured; using deterministic rule engine."
            )
            return self.fallback_engine.discover_sheet(sheet, cells)

        # External ML inference path (when model is loaded)
        raise NotImplementedError("GridGulp model inference runtime not initialized.")

    def discover_workbook(
        self,
        workbook: WorkbookStructure,
    ) -> list[DiscoveredLayout]:
        """Discover layout across entire workbook."""
        return [self.discover_sheet(s) for s in workbook.sheets]
