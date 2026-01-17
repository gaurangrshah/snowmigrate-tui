"""Migration row widget for dashboard."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Label, ProgressBar
from textual.widget import Widget
from textual.message import Message
from textual.reactive import reactive

from snowmigrate.models.migration import Migration, MigrationStatus
from snowmigrate.services.migration_engine import MigrationEngine


class MigrationRow(Widget):
    """Display row for a migration job."""

    class PauseRequested(Message):
        """Request to pause a migration."""

        def __init__(self, migration_id: str) -> None:
            super().__init__()
            self.migration_id = migration_id

    class ResumeRequested(Message):
        """Request to resume a migration."""

        def __init__(self, migration_id: str) -> None:
            super().__init__()
            self.migration_id = migration_id

    class CancelRequested(Message):
        """Request to cancel a migration."""

        def __init__(self, migration_id: str) -> None:
            super().__init__()
            self.migration_id = migration_id

    class ViewLogsRequested(Message):
        """Request to view migration logs."""

        def __init__(self, migration_id: str) -> None:
            super().__init__()
            self.migration_id = migration_id

    DEFAULT_CSS = """
    MigrationRow {
        height: auto;
        padding: 1;
        margin-bottom: 1;
        border: solid $primary;
    }

    MigrationRow:focus {
        border: solid $accent;
    }

    MigrationRow .migration-header {
        height: auto;
        margin-bottom: 1;
    }

    MigrationRow .migration-source {
        text-style: bold;
    }

    MigrationRow .migration-target {
        color: $text-muted;
    }

    MigrationRow .migration-status {
        dock: right;
        padding: 0 1;
    }

    MigrationRow .migration-progress {
        height: auto;
        margin-bottom: 1;
    }

    MigrationRow .migration-stats {
        color: $text-muted;
    }

    MigrationRow .migration-controls {
        height: auto;
    }

    MigrationRow .migration-controls Button {
        margin-right: 1;
    }

    MigrationRow.status-running {
        border: solid #2196f3;
    }

    MigrationRow.status-completed {
        border: solid $success;
    }

    MigrationRow.status-failed {
        border: solid $error;
    }

    MigrationRow.status-paused {
        border: solid $warning;
    }
    """

    migration: reactive[Migration]

    def __init__(self, migration: Migration, engine: MigrationEngine) -> None:
        super().__init__()
        self.migration = migration
        self.engine = engine
        self._update_class()

    def _update_class(self) -> None:
        """Update CSS class based on status."""
        for status in MigrationStatus:
            self.remove_class(f"status-{status.value}")
        self.add_class(f"status-{self.migration.status.value}")

    def compose(self) -> ComposeResult:
        """Create the row layout."""
        with Vertical():
            with Horizontal(classes="migration-header"):
                yield Label(self.migration.source_display, classes="migration-source")
                yield Label(" → ", classes="migration-target")
                yield Label(self._target_display, classes="migration-target")
                yield Label(self._status_badge, classes=f"migration-status status-{self.migration.status.value}")

            if self.migration.status == MigrationStatus.RUNNING:
                with Vertical(classes="migration-progress"):
                    yield ProgressBar(total=100, show_eta=False, id="progress-bar")
                    yield Label(self._progress_text, classes="migration-stats", id="progress-text")

            elif self.migration.status == MigrationStatus.FAILED:
                yield Label(f"Error: {self.migration.error or 'Unknown'}", classes="status-failed")

            with Horizontal(classes="migration-controls"):
                if self.migration.status == MigrationStatus.RUNNING:
                    yield Button("Pause", variant="warning", id="pause")
                    yield Button("Cancel", variant="error", id="cancel")
                elif self.migration.status == MigrationStatus.PAUSED:
                    yield Button("Resume", variant="primary", id="resume")
                    yield Button("Cancel", variant="error", id="cancel")
                elif self.migration.status == MigrationStatus.QUEUED:
                    yield Button("Cancel", variant="error", id="cancel")

                if self.migration.status in (MigrationStatus.RUNNING, MigrationStatus.COMPLETED, MigrationStatus.FAILED):
                    yield Button("Logs", variant="default", id="logs")

    @property
    def _target_display(self) -> str:
        """Get target display text."""
        target_conn = self.engine._connection_manager.get_snowflake_connection(
            self.migration.target_connection_id
        )
        if target_conn:
            return f"{target_conn.database}.{self.migration.target_schema or target_conn.schema_name}"
        return "Unknown target"

    @property
    def _status_badge(self) -> str:
        """Get status badge text."""
        badges = {
            MigrationStatus.QUEUED: "[QUEUED]",
            MigrationStatus.RUNNING: "[RUNNING]",
            MigrationStatus.PAUSED: "[PAUSED]",
            MigrationStatus.COMPLETED: "[DONE]",
            MigrationStatus.FAILED: "[FAILED]",
            MigrationStatus.CANCELLED: "[CANCELLED]",
        }
        return badges.get(self.migration.status, "[?]")

    @property
    def _progress_text(self) -> str:
        """Get progress text."""
        p = self.migration.progress
        rows = f"{p.migrated_rows:,} / {p.total_rows:,} rows" if p.total_rows else "Calculating..."
        tables = f"{p.completed_tables}/{p.total_tables} tables"
        eta = f"ETA: {p.eta_display}" if p.eta_seconds else ""
        duration = self.migration.duration_display
        return f"{rows} | {tables} | {duration} | {eta}"

    def on_mount(self) -> None:
        """Update progress bar on mount."""
        self._update_progress()

    def watch_migration(self, migration: Migration) -> None:
        """React to migration changes."""
        self._update_class()
        self._update_progress()

    def _update_progress(self) -> None:
        """Update progress display."""
        if self.migration.status != MigrationStatus.RUNNING:
            return

        try:
            bar = self.query_one("#progress-bar", ProgressBar)
            bar.progress = self.migration.progress.percentage

            text = self.query_one("#progress-text", Label)
            text.update(self._progress_text)
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        event.stop()
        if event.button.id == "pause":
            self.post_message(self.PauseRequested(self.migration.id))
        elif event.button.id == "resume":
            self.post_message(self.ResumeRequested(self.migration.id))
        elif event.button.id == "cancel":
            self.post_message(self.CancelRequested(self.migration.id))
        elif event.button.id == "logs":
            self.post_message(self.ViewLogsRequested(self.migration.id))
