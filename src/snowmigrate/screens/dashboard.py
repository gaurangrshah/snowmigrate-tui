"""WAR Room Dashboard screen."""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import Button, Label, ProgressBar, Static
from textual.widget import Widget
from textual.reactive import reactive
from textual import work

from snowmigrate.models.migration import Migration, MigrationStatus
from snowmigrate.services.migration_engine import MigrationEngine
from snowmigrate.widgets.migration_row import MigrationRow


class StatsPanel(Widget):
    """Dashboard statistics panel."""

    running_count: reactive[int] = reactive(0)
    queued_count: reactive[int] = reactive(0)
    completed_count: reactive[int] = reactive(0)
    failed_count: reactive[int] = reactive(0)
    total_rows: reactive[int] = reactive(0)

    DEFAULT_CSS = """
    StatsPanel {
        height: 5;
        background: $surface;
        padding: 1;
    }

    StatsPanel Horizontal {
        height: 100%;
    }

    StatsPanel .stat-box {
        width: 1fr;
        content-align: center middle;
    }

    StatsPanel .stat-value {
        text-style: bold;
        text-align: center;
        width: 100%;
    }

    StatsPanel .stat-label {
        color: $text-muted;
        text-align: center;
        width: 100%;
    }

    StatsPanel .stat-running .stat-value {
        color: #2196f3;
    }

    StatsPanel .stat-queued .stat-value {
        color: $text-muted;
    }

    StatsPanel .stat-completed .stat-value {
        color: $success;
    }

    StatsPanel .stat-failed .stat-value {
        color: $error;
    }
    """

    def compose(self) -> ComposeResult:
        """Create the stats layout."""
        with Horizontal():
            with Vertical(classes="stat-box stat-running"):
                yield Label(str(self.running_count), classes="stat-value", id="running-value")
                yield Label("Running", classes="stat-label")

            with Vertical(classes="stat-box stat-queued"):
                yield Label(str(self.queued_count), classes="stat-value", id="queued-value")
                yield Label("Queued", classes="stat-label")

            with Vertical(classes="stat-box stat-completed"):
                yield Label(str(self.completed_count), classes="stat-value", id="completed-value")
                yield Label("Completed", classes="stat-label")

            with Vertical(classes="stat-box stat-failed"):
                yield Label(str(self.failed_count), classes="stat-value", id="failed-value")
                yield Label("Failed", classes="stat-label")

            with Vertical(classes="stat-box"):
                yield Label(self._format_rows(self.total_rows), classes="stat-value", id="rows-value")
                yield Label("Total Rows", classes="stat-label")

    def watch_running_count(self, value: int) -> None:
        """Update running count display."""
        try:
            self.query_one("#running-value", Label).update(str(value))
        except Exception:
            pass

    def watch_queued_count(self, value: int) -> None:
        """Update queued count display."""
        try:
            self.query_one("#queued-value", Label).update(str(value))
        except Exception:
            pass

    def watch_completed_count(self, value: int) -> None:
        """Update completed count display."""
        try:
            self.query_one("#completed-value", Label).update(str(value))
        except Exception:
            pass

    def watch_failed_count(self, value: int) -> None:
        """Update failed count display."""
        try:
            self.query_one("#failed-value", Label).update(str(value))
        except Exception:
            pass

    def watch_total_rows(self, value: int) -> None:
        """Update total rows display."""
        try:
            self.query_one("#rows-value", Label).update(self._format_rows(value))
        except Exception:
            pass

    def _format_rows(self, count: int) -> str:
        """Format row count for display."""
        if count >= 1_000_000:
            return f"{count / 1_000_000:.1f}M"
        if count >= 1_000:
            return f"{count / 1_000:.1f}K"
        return str(count)


class DashboardPane(Widget):
    """WAR Room dashboard pane."""

    def __init__(self, migration_engine: MigrationEngine) -> None:
        super().__init__()
        self.migration_engine = migration_engine
        self._refresh_interval = 1.0

    def compose(self) -> ComposeResult:
        """Create the dashboard layout."""
        with Container(classes="pane-container dashboard-container"):
            yield StatsPanel(id="stats-panel")

            with Horizontal(id="dashboard-header"):
                yield Label("Active Migrations", classes="section-header")
                yield Button("+ New Migration", variant="primary", id="new-migration")
                yield Button("Refresh", variant="default", id="refresh")

            yield ScrollableContainer(id="migration-list")

    def on_mount(self) -> None:
        """Start refresh loop on mount."""
        self._refresh_dashboard()
        self.set_interval(self._refresh_interval, self._refresh_dashboard)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "new-migration":
            self._show_new_migration_wizard()
        elif event.button.id == "refresh":
            self._refresh_dashboard()

    def _refresh_dashboard(self) -> None:
        """Refresh the migration list and stats."""
        migrations = self.migration_engine.list_migrations()
        migration_list = self.query_one("#migration-list", ScrollableContainer)

        stats = self.query_one("#stats-panel", StatsPanel)
        stats.running_count = sum(1 for m in migrations if m.status == MigrationStatus.RUNNING)
        stats.queued_count = sum(1 for m in migrations if m.status == MigrationStatus.QUEUED)
        stats.completed_count = sum(1 for m in migrations if m.status == MigrationStatus.COMPLETED)
        stats.failed_count = sum(1 for m in migrations if m.status == MigrationStatus.FAILED)
        stats.total_rows = sum(m.progress.migrated_rows for m in migrations)

        existing_ids = {child.migration.id for child in migration_list.query(MigrationRow)}
        current_ids = {m.id for m in migrations}

        for child in list(migration_list.query(MigrationRow)):
            if child.migration.id not in current_ids:
                child.remove()
            else:
                migration = next(m for m in migrations if m.id == child.migration.id)
                child.migration = migration
                child.refresh()

        for migration in migrations:
            if migration.id not in existing_ids:
                row = MigrationRow(migration, self.migration_engine)
                migration_list.mount(row)

        if not migrations:
            if not migration_list.query(".empty-state"):
                migration_list.mount(
                    Static("No migrations. Click '+ New Migration' to start.", classes="empty-state")
                )
        else:
            for empty in migration_list.query(".empty-state"):
                empty.remove()

    def _show_new_migration_wizard(self) -> None:
        """Show the new migration wizard."""
        self.app.action_switch_tab("browser")
        self.notify("Select tables from the Browser tab to start a migration")

    def on_migration_row_pause_requested(self, event: "MigrationRow.PauseRequested") -> None:
        """Handle pause request."""
        self._pause_migration(event.migration_id)

    def on_migration_row_resume_requested(self, event: "MigrationRow.ResumeRequested") -> None:
        """Handle resume request."""
        self._resume_migration(event.migration_id)

    def on_migration_row_cancel_requested(self, event: "MigrationRow.CancelRequested") -> None:
        """Handle cancel request."""
        self._cancel_migration(event.migration_id)

    @work(thread=True)
    async def _pause_migration(self, migration_id: str) -> None:
        """Pause a migration."""
        try:
            await self.migration_engine.pause_migration(migration_id)
            self.call_from_thread(self.notify, "Migration paused")
        except Exception as e:
            self.call_from_thread(self.notify, f"Failed to pause: {e}", severity="error")

    @work(thread=True)
    async def _resume_migration(self, migration_id: str) -> None:
        """Resume a migration."""
        try:
            await self.migration_engine.resume_migration(migration_id)
            self.call_from_thread(self.notify, "Migration resumed")
        except Exception as e:
            self.call_from_thread(self.notify, f"Failed to resume: {e}", severity="error")

    @work(thread=True)
    async def _cancel_migration(self, migration_id: str) -> None:
        """Cancel a migration."""
        try:
            await self.migration_engine.cancel_migration(migration_id)
            self.call_from_thread(self.notify, "Migration cancelled")
        except Exception as e:
            self.call_from_thread(self.notify, f"Failed to cancel: {e}", severity="error")
