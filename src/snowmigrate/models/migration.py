"""Migration job models."""

from datetime import datetime
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field


class MigrationStatus(str, Enum):
    """Migration job status."""

    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TableSelection(BaseModel):
    """A selected table for migration."""

    schema_name: str
    table_name: str
    row_count: int | None = None
    size_bytes: int | None = None

    @property
    def full_name(self) -> str:
        """Return fully qualified table name."""
        return f"{self.schema_name}.{self.table_name}"


class MigrationProgress(BaseModel):
    """Progress tracking for a migration job."""

    total_tables: int = 0
    completed_tables: int = 0
    current_table: str | None = None
    current_table_progress: float = 0.0
    total_rows: int = 0
    migrated_rows: int = 0
    rows_per_second: float = 0.0
    eta_seconds: int | None = None

    @property
    def percentage(self) -> float:
        """Calculate overall completion percentage."""
        if self.total_rows == 0:
            if self.total_tables == 0:
                return 0.0
            return (self.completed_tables / self.total_tables) * 100
        return (self.migrated_rows / self.total_rows) * 100

    @property
    def eta_display(self) -> str:
        """Format ETA for display."""
        if self.eta_seconds is None:
            return "Calculating..."
        if self.eta_seconds < 60:
            return f"{self.eta_seconds}s"
        if self.eta_seconds < 3600:
            minutes = self.eta_seconds // 60
            seconds = self.eta_seconds % 60
            return f"{minutes}m {seconds}s"
        hours = self.eta_seconds // 3600
        minutes = (self.eta_seconds % 3600) // 60
        return f"{hours}h {minutes}m"


class MigrationConfig(BaseModel):
    """Configuration for a new migration job."""

    source_connection_id: str
    target_connection_id: str
    staging_area_id: str
    tables: list[TableSelection]
    target_schema: str | None = None
    table_prefix: str = ""
    table_suffix: str = ""


class Migration(BaseModel):
    """A migration job instance."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    source_connection_id: str
    target_connection_id: str
    staging_area_id: str
    tables: list[TableSelection]
    target_schema: str | None = None
    status: MigrationStatus = MigrationStatus.QUEUED
    progress: MigrationProgress = Field(default_factory=MigrationProgress)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    cli_process_id: int | None = None

    @property
    def duration_seconds(self) -> int | None:
        """Calculate elapsed time."""
        if self.started_at is None:
            return None
        end = self.completed_at or datetime.now()
        return int((end - self.started_at).total_seconds())

    @property
    def duration_display(self) -> str:
        """Format duration for display."""
        seconds = self.duration_seconds
        if seconds is None:
            return "--:--"
        hours, remainder = divmod(seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"

    @property
    def source_display(self) -> str:
        """Brief source description for display."""
        if not self.tables:
            return "No tables"
        if len(self.tables) == 1:
            return self.tables[0].full_name
        return f"{len(self.tables)} tables"
