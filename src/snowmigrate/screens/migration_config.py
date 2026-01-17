"""Migration configuration screen/modal."""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static
from textual import work

from snowmigrate.models.migration import MigrationConfig, TableSelection
from snowmigrate.models.staging import StagingArea
from snowmigrate.services.connection_manager import ConnectionManager
from snowmigrate.widgets.staging_selector import StagingSelector


class MigrationConfigModal(ModalScreen):
    """Modal for configuring a new migration."""

    DEFAULT_CSS = """
    MigrationConfigModal {
        align: center middle;
    }

    MigrationConfigModal .modal-container {
        width: 80;
        height: auto;
        max-height: 90%;
        background: $surface;
        border: solid $primary;
        padding: 1 2;
    }

    MigrationConfigModal .modal-title {
        text-style: bold;
        margin-bottom: 1;
        text-align: center;
        width: 100%;
    }

    MigrationConfigModal .form-section {
        margin-bottom: 1;
        height: auto;
    }

    MigrationConfigModal .section-title {
        text-style: bold;
        margin-bottom: 1;
    }

    MigrationConfigModal .form-row {
        height: auto;
        margin-bottom: 1;
    }

    MigrationConfigModal .form-label {
        width: 20;
    }

    MigrationConfigModal Input {
        width: 40;
    }

    MigrationConfigModal Select {
        width: 40;
    }

    MigrationConfigModal .table-summary {
        color: $text-muted;
        margin-bottom: 1;
    }

    MigrationConfigModal .modal-buttons {
        margin-top: 1;
        align: right middle;
        height: auto;
    }
    """

    def __init__(
        self,
        source_connection_id: str,
        tables: list[TableSelection],
        connection_manager: ConnectionManager,
    ) -> None:
        super().__init__()
        self.source_connection_id = source_connection_id
        self.tables = tables
        self.connection_manager = connection_manager
        self.staging_areas: list[StagingArea] = []
        self.selected_staging: StagingArea | None = None
        self.selected_target_id: str | None = None

    def compose(self) -> ComposeResult:
        """Create the modal layout."""
        with Container(classes="modal-container"):
            yield Label("Configure Migration", classes="modal-title")

            source = self.connection_manager.get_source_connection(self.source_connection_id)
            source_name = source.name if source else "Unknown"
            total_rows = sum(t.row_count or 0 for t in self.tables)

            yield Label(
                f"Source: {source_name} | Tables: {len(self.tables)} | Rows: {total_rows:,}",
                classes="table-summary",
            )

            with Vertical(classes="form-section"):
                yield Label("Target Connection", classes="section-title")

                targets = self.connection_manager.list_snowflake_connections()
                if targets:
                    yield Select(
                        [(t.name, t.id) for t in targets],
                        id="target-select",
                        prompt="Select Snowflake target...",
                    )
                else:
                    yield Static("No Snowflake connections configured", classes="empty-state")

            with Vertical(classes="form-section"):
                yield Label("Target Schema (optional)", classes="section-title")
                yield Input(placeholder="Leave blank to use connection default", id="target-schema")

            with Vertical(classes="form-section", id="staging-section"):
                yield Static("Loading staging areas...", id="staging-loading")

            with Horizontal(classes="modal-buttons"):
                yield Button("Cancel", variant="default", id="cancel")
                yield Button("Start Migration", variant="primary", id="start")

    def on_mount(self) -> None:
        """Load staging areas on mount."""
        self._load_staging_areas()

    @work(thread=True)
    async def _load_staging_areas(self) -> None:
        """Load staging areas in background."""
        from snowmigrate.services.migration_engine import MigrationEngine

        engine = MigrationEngine(self.connection_manager)
        self.staging_areas = await engine.list_staging_areas()

        def update_ui():
            section = self.query_one("#staging-section", Vertical)
            loading = self.query_one("#staging-loading", Static)
            loading.remove()

            selector = StagingSelector(self.staging_areas)
            section.mount(selector)

        self.call_from_thread(update_ui)

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle target selection."""
        if event.select.id == "target-select":
            self.selected_target_id = str(event.value) if event.value else None

    def on_staging_selector_selected(self, event: StagingSelector.Selected) -> None:
        """Handle staging area selection."""
        self.selected_staging = event.staging_area

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "cancel":
            self.dismiss()
        elif event.button.id == "start":
            self._start_migration()

    def _start_migration(self) -> None:
        """Validate and start the migration."""
        if not self.selected_target_id:
            self.notify("Please select a target connection", severity="error")
            return

        if not self.selected_staging:
            self.notify("Please select a staging area", severity="error")
            return

        target_schema = self.query_one("#target-schema", Input).value.strip() or None

        config = MigrationConfig(
            source_connection_id=self.source_connection_id,
            target_connection_id=self.selected_target_id,
            staging_area_id=self.selected_staging.id,
            tables=self.tables,
            target_schema=target_schema,
        )

        self._create_and_start_migration(config)

    @work(thread=True)
    async def _create_and_start_migration(self, config: MigrationConfig) -> None:
        """Create and start migration in background."""
        from snowmigrate.services.migration_engine import MigrationEngine

        try:
            engine = MigrationEngine(self.connection_manager)
            migration = engine.create_migration(config)
            await engine.start_migration(migration.id)

            def on_success():
                self.notify(f"Migration started: {migration.id[:8]}")
                self.dismiss()
                self.app.action_switch_tab("dashboard")

            self.call_from_thread(on_success)

        except Exception as e:
            self.call_from_thread(
                self.notify, f"Failed to start migration: {e}", severity="error"
            )
