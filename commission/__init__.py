"""commission: discovery, address table verification, health scan,
rule based fault localization, and a small ML fault classifier."""

from commission.discovery import discover, DiscoveryResult
from commission.table import verify_table, TableDiff
from commission.health import health_scan, HealthReport, NodeHealth
from commission.localize import diagnose, Diagnosis
from commission.classify import FEATURE_NAMES, extract_features, train_classifier
from commission.episode import run_episode

__all__ = [
    "discover",
    "DiscoveryResult",
    "verify_table",
    "TableDiff",
    "health_scan",
    "HealthReport",
    "NodeHealth",
    "diagnose",
    "Diagnosis",
    "FEATURE_NAMES",
    "extract_features",
    "train_classifier",
    "run_episode",
]
