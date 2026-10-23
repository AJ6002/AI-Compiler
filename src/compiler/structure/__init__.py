"""Structural discovery, layout recognition, and header reconstruction."""

from src.compiler.structure.ambiguity_scorer import AmbiguityScorer
from src.compiler.structure.discovery_engine import (
    RuleBasedDiscoveryEngine,
    StructuralDiscoveryEngine,
)
from src.compiler.structure.gridgulp_adapter import GridGulpAdapter
from src.compiler.structure.header_reconstructor import HeaderReconstructor
from src.compiler.structure.occupancy_grid import OccupancyGrid
from src.compiler.structure.region_detector import RegionDetector
from src.compiler.structure.types import (
    CellTypeSignature,
    DiscoveredLayout,
    HeaderPath,
    MetadataEntry,
    TableRegionLayout,
)

__all__ = [
    "AmbiguityScorer",
    "CellTypeSignature",
    "DiscoveredLayout",
    "GridGulpAdapter",
    "HeaderPath",
    "HeaderReconstructor",
    "MetadataEntry",
    "OccupancyGrid",
    "RegionDetector",
    "RuleBasedDiscoveryEngine",
    "StructuralDiscoveryEngine",
    "TableRegionLayout",
]
