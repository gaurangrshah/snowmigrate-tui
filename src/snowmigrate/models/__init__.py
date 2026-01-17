"""Data models for SnowMigrate TUI."""

from snowmigrate.models.connection import (
    ConnectionStatus,
    ConnectionTestResult,
    SnowflakeConnection,
    SourceConnection,
    SourceType,
)
from snowmigrate.models.migration import (
    Migration,
    MigrationConfig,
    MigrationProgress,
    MigrationStatus,
    TableSelection,
)
from snowmigrate.models.staging import StagingArea, StagingType

__all__ = [
    "ConnectionStatus",
    "ConnectionTestResult",
    "Migration",
    "MigrationConfig",
    "MigrationProgress",
    "MigrationStatus",
    "SnowflakeConnection",
    "SourceConnection",
    "SourceType",
    "StagingArea",
    "StagingType",
    "TableSelection",
]
