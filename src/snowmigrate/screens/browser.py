"""Source database browser screen."""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import Button, DataTable, Label, Select, Static, Tree
from textual.widgets.tree import TreeNode
from textual.widget import Widget
from textual.message import Message
from textual import work

from snowmigrate.models.connection import SourceConnection
from snowmigrate.models.migration import TableSelection
from snowmigrate.services.connection_manager import ConnectionManager
from snowmigrate.services.metadata_service import MetadataService, TableInfo
from snowmigrate.widgets.staging_selector import StagingSelector


class SchemaTree(Widget):
    """Tree widget for browsing database schemas."""

    class TableSelected(Message):
        """A table was selected/deselected."""

        def __init__(self, table: TableInfo, selected: bool) -> None:
            super().__init__()
            self.table = table
            self.selected = selected

    class TableFocused(Message):
        """A table was focused for preview."""

        def __init__(self, table: TableInfo) -> None:
            super().__init__()
            self.table = table

    DEFAULT_CSS = """
    SchemaTree {
        width: 100%;
        height: 100%;
    }

    SchemaTree Tree {
        width: 100%;
        height: 100%;
    }
    """

    def __init__(
        self,
        connection_id: str,
        metadata_service: MetadataService,
    ) -> None:
        super().__init__()
        self.connection_id = connection_id
        self.metadata_service = metadata_service
        self.selected_tables: set[str] = set()
        self._table_map: dict[str, TableInfo] = {}

    def compose(self) -> ComposeResult:
        """Create the tree layout."""
        yield Tree("Database", id="schema-tree")

    def on_mount(self) -> None:
        """Load schemas on mount."""
        self._load_schemas()

    @work(thread=True)
    async def _load_schemas(self) -> None:
        """Load schemas in background."""
        tree = self.query_one("#schema-tree", Tree)

        schemas = await self.metadata_service.get_schemas(
            self.connection_id, ""
        )

        def add_schemas():
            tree.root.expand()
            for schema in schemas:
                label = f"{schema.name}"
                if schema.table_count:
                    label += f" ({schema.table_count})"
                node = tree.root.add(label, data={"type": "schema", "name": schema.name})
                node.add("Loading...", data={"type": "loading"})

        self.call_from_thread(add_schemas)

    def on_tree_node_expanded(self, event: Tree.NodeExpanded) -> None:
        """Handle node expansion."""
        node = event.node
        data = node.data or {}

        if data.get("type") == "schema":
            self._load_tables(node, data["name"])

    @work(thread=True)
    async def _load_tables(self, node: TreeNode, schema_name: str) -> None:
        """Load tables for a schema."""
        tables = await self.metadata_service.get_tables(
            self.connection_id, "", schema_name
        )

        def update_node():
            node.remove_children()
            for table in tables:
                full_name = table.full_name
                self._table_map[full_name] = table

                prefix = "[x]" if full_name in self.selected_tables else "[ ]"
                rows = f" ({table.row_count:,})" if table.row_count else ""
                label = f"{prefix} {table.name}{rows}"

                node.add(label, data={"type": "table", "table": table})

        self.call_from_thread(update_node)

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Handle node selection (toggle table)."""
        node = event.node
        data = node.data or {}

        if data.get("type") == "table":
            table = data["table"]
            full_name = table.full_name

            if full_name in self.selected_tables:
                self.selected_tables.discard(full_name)
                self.post_message(self.TableSelected(table, False))
            else:
                self.selected_tables.add(full_name)
                self.post_message(self.TableSelected(table, True))

            prefix = "[x]" if full_name in self.selected_tables else "[ ]"
            rows = f" ({table.row_count:,})" if table.row_count else ""
            node.set_label(f"{prefix} {table.name}{rows}")

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted) -> None:
        """Handle node highlight for preview."""
        node = event.node
        data = node.data or {}

        if data.get("type") == "table":
            self.post_message(self.TableFocused(data["table"]))

    def select_all_in_schema(self, schema_name: str) -> None:
        """Select all tables in a schema."""
        for full_name, table in self._table_map.items():
            if table.schema_name == schema_name and full_name not in self.selected_tables:
                self.selected_tables.add(full_name)
                self.post_message(self.TableSelected(table, True))
        self._refresh_tree_labels()

    def deselect_all(self) -> None:
        """Deselect all tables."""
        for full_name in list(self.selected_tables):
            table = self._table_map.get(full_name)
            if table:
                self.post_message(self.TableSelected(table, False))
        self.selected_tables.clear()
        self._refresh_tree_labels()

    def _refresh_tree_labels(self) -> None:
        """Refresh all table labels to show selection state."""
        tree = self.query_one("#schema-tree", Tree)

        def update_labels(node: TreeNode) -> None:
            data = node.data or {}
            if data.get("type") == "table":
                table = data["table"]
                full_name = table.full_name
                prefix = "[x]" if full_name in self.selected_tables else "[ ]"
                rows = f" ({table.row_count:,})" if table.row_count else ""
                node.set_label(f"{prefix} {table.name}{rows}")

            for child in node.children:
                update_labels(child)

        update_labels(tree.root)

    def get_selected_tables(self) -> list[TableSelection]:
        """Get list of selected tables."""
        return [
            TableSelection(
                schema_name=table.schema_name,
                table_name=table.name,
                row_count=table.row_count,
            )
            for full_name, table in self._table_map.items()
            if full_name in self.selected_tables
        ]


class TablePreview(Widget):
    """Preview panel for selected table."""

    DEFAULT_CSS = """
    TablePreview {
        width: 100%;
        height: 100%;
        border: solid $primary;
        padding: 1;
    }

    TablePreview .preview-title {
        text-style: bold;
        margin-bottom: 1;
    }

    TablePreview DataTable {
        height: 1fr;
    }
    """

    def __init__(self, metadata_service: MetadataService) -> None:
        super().__init__()
        self.metadata_service = metadata_service
        self.current_table: TableInfo | None = None
        self.connection_id: str | None = None

    def compose(self) -> ComposeResult:
        """Create the preview layout."""
        yield Label("Select a table to preview", classes="preview-title", id="preview-title")
        yield DataTable(id="preview-table")

    def set_connection(self, connection_id: str) -> None:
        """Set the connection ID."""
        self.connection_id = connection_id

    def show_table(self, table: TableInfo) -> None:
        """Show preview for a table."""
        self.current_table = table
        self.query_one("#preview-title", Label).update(f"Columns: {table.full_name}")
        self._load_columns()

    @work(thread=True)
    async def _load_columns(self) -> None:
        """Load columns in background."""
        if not self.current_table or not self.connection_id:
            return

        columns = await self.metadata_service.get_columns(
            self.connection_id,
            "",
            self.current_table.schema_name,
            self.current_table.name,
        )

        def update_table():
            dt = self.query_one("#preview-table", DataTable)
            dt.clear(columns=True)
            dt.add_columns("Column", "Type", "Nullable", "PK")

            for col in columns:
                dt.add_row(
                    col.name,
                    col.data_type,
                    "Yes" if col.nullable else "No",
                    "*" if col.is_primary_key else "",
                )

        self.call_from_thread(update_table)


class BrowserPane(Widget):
    """Source database browser pane."""

    def __init__(self, connection_manager: ConnectionManager) -> None:
        super().__init__()
        self.connection_manager = connection_manager
        self.metadata_service = MetadataService(connection_manager)
        self.selected_connection_id: str | None = None
        self.selected_tables: list[TableSelection] = []

    def compose(self) -> ComposeResult:
        """Create the browser layout."""
        with Container(classes="pane-container"):
            with Horizontal(id="browser-header"):
                yield Label("Source:", classes="form-label")
                yield Select(
                    [(c.name, c.id) for c in self.connection_manager.list_source_connections()],
                    id="source-select",
                    prompt="Select a connection...",
                )
                yield Label("", id="selection-count")

            with Horizontal(id="browser-content"):
                with Vertical(id="browser-tree-container"):
                    yield Static("Select a source connection", id="tree-placeholder")

                with Vertical(id="browser-preview-container"):
                    yield TablePreview(self.metadata_service, id="table-preview")

            with Horizontal(id="browser-actions"):
                yield Button("Select All", variant="default", id="select-all")
                yield Button("Deselect All", variant="default", id="deselect-all")
                yield Button("Configure Migration", variant="primary", id="configure-migration")

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle connection selection."""
        if event.select.id != "source-select":
            return

        self.selected_connection_id = str(event.value) if event.value else None
        self._load_browser()

    def _load_browser(self) -> None:
        """Load the schema browser for selected connection."""
        container = self.query_one("#browser-tree-container", Vertical)

        for child in list(container.children):
            child.remove()

        if not self.selected_connection_id:
            container.mount(Static("Select a source connection", id="tree-placeholder"))
            return

        tree = SchemaTree(self.selected_connection_id, self.metadata_service)
        container.mount(tree)

        preview = self.query_one("#table-preview", TablePreview)
        preview.set_connection(self.selected_connection_id)

    def on_schema_tree_table_selected(self, event: SchemaTree.TableSelected) -> None:
        """Handle table selection."""
        if event.selected:
            self.selected_tables.append(
                TableSelection(
                    schema_name=event.table.schema_name,
                    table_name=event.table.name,
                    row_count=event.table.row_count,
                )
            )
        else:
            self.selected_tables = [
                t for t in self.selected_tables
                if not (t.schema_name == event.table.schema_name and t.table_name == event.table.name)
            ]

        self._update_selection_count()

    def on_schema_tree_table_focused(self, event: SchemaTree.TableFocused) -> None:
        """Handle table focus for preview."""
        preview = self.query_one("#table-preview", TablePreview)
        preview.show_table(event.table)

    def _update_selection_count(self) -> None:
        """Update selection count label."""
        count = len(self.selected_tables)
        label = self.query_one("#selection-count", Label)
        label.update(f"Selected: {count} table{'s' if count != 1 else ''}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "select-all":
            self._select_all()
        elif event.button.id == "deselect-all":
            self._deselect_all()
        elif event.button.id == "configure-migration":
            self._show_migration_config()

    def _select_all(self) -> None:
        """Select all visible tables."""
        try:
            tree = self.query_one(SchemaTree)
            for node in tree.query_one("#schema-tree", Tree).root.children:
                data = node.data or {}
                if data.get("type") == "schema":
                    tree.select_all_in_schema(data["name"])
            self.selected_tables = tree.get_selected_tables()
            self._update_selection_count()
        except Exception:
            pass

    def _deselect_all(self) -> None:
        """Deselect all tables."""
        try:
            tree = self.query_one(SchemaTree)
            tree.deselect_all()
            self.selected_tables = []
            self._update_selection_count()
        except Exception:
            pass

    def _show_migration_config(self) -> None:
        """Show migration configuration modal."""
        if not self.selected_tables:
            self.notify("Please select at least one table", severity="warning")
            return

        if not self.selected_connection_id:
            self.notify("Please select a source connection", severity="warning")
            return

        from snowmigrate.screens.migration_config import MigrationConfigModal

        self.app.push_screen(
            MigrationConfigModal(
                source_connection_id=self.selected_connection_id,
                tables=self.selected_tables,
                connection_manager=self.connection_manager,
            )
        )
