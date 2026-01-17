"""Connection management screen."""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import Button, Input, Label, Select, Static
from textual.widget import Widget
from textual.message import Message
from textual import work

from snowmigrate.models.connection import (
    ConnectionStatus,
    SnowflakeConnection,
    SourceConnection,
    SourceType,
)
from snowmigrate.services.connection_manager import ConnectionManager
from snowmigrate.widgets.connection_card import ConnectionCard


class ConnectionForm(Widget):
    """Form for adding/editing connections."""

    class Submitted(Message):
        """Form was submitted."""

        def __init__(self, connection: SourceConnection | SnowflakeConnection) -> None:
            super().__init__()
            self.connection = connection

    class Cancelled(Message):
        """Form was cancelled."""

    def __init__(
        self,
        connection_type: str = "source",
        connection: SourceConnection | SnowflakeConnection | None = None,
    ) -> None:
        super().__init__()
        self.connection_type = connection_type
        self.existing_connection = connection

    def compose(self) -> ComposeResult:
        """Create the form layout."""
        is_source = self.connection_type == "source"
        title = "Edit" if self.existing_connection else "Add"
        title += " Source Connection" if is_source else " Snowflake Connection"

        with Container(classes="form-container"):
            yield Label(title, classes="section-header")

            with Vertical(classes="form-row"):
                yield Label("Name:", classes="form-label")
                yield Input(
                    placeholder="Connection name",
                    id="name",
                    value=self.existing_connection.name if self.existing_connection else "",
                )

            if is_source:
                with Vertical(classes="form-row"):
                    yield Label("Type:", classes="form-label")
                    yield Select(
                        [(t.value.title(), t.value) for t in SourceType],
                        id="source_type",
                        value=(
                            self.existing_connection.type.value
                            if self.existing_connection and isinstance(self.existing_connection, SourceConnection)
                            else SourceType.POSTGRES.value
                        ),
                    )

                with Vertical(classes="form-row"):
                    yield Label("Host:", classes="form-label")
                    yield Input(
                        placeholder="database.example.com",
                        id="host",
                        value=(
                            self.existing_connection.host
                            if self.existing_connection and isinstance(self.existing_connection, SourceConnection)
                            else ""
                        ),
                    )

                with Vertical(classes="form-row"):
                    yield Label("Port:", classes="form-label")
                    yield Input(
                        placeholder="5432",
                        id="port",
                        value=(
                            str(self.existing_connection.port)
                            if self.existing_connection and isinstance(self.existing_connection, SourceConnection)
                            else "5432"
                        ),
                    )

                with Vertical(classes="form-row"):
                    yield Label("Database:", classes="form-label")
                    yield Input(
                        placeholder="mydb",
                        id="database",
                        value=(
                            self.existing_connection.database
                            if self.existing_connection and isinstance(self.existing_connection, SourceConnection)
                            else ""
                        ),
                    )
            else:
                with Vertical(classes="form-row"):
                    yield Label("Account:", classes="form-label")
                    yield Input(
                        placeholder="account.region",
                        id="account",
                        value=(
                            self.existing_connection.account
                            if self.existing_connection and isinstance(self.existing_connection, SnowflakeConnection)
                            else ""
                        ),
                    )

                with Vertical(classes="form-row"):
                    yield Label("Warehouse:", classes="form-label")
                    yield Input(
                        placeholder="COMPUTE_WH",
                        id="warehouse",
                        value=(
                            self.existing_connection.warehouse
                            if self.existing_connection and isinstance(self.existing_connection, SnowflakeConnection)
                            else ""
                        ),
                    )

                with Vertical(classes="form-row"):
                    yield Label("Database:", classes="form-label")
                    yield Input(
                        placeholder="MY_DATABASE",
                        id="database",
                        value=(
                            self.existing_connection.database
                            if self.existing_connection and isinstance(self.existing_connection, SnowflakeConnection)
                            else ""
                        ),
                    )

                with Vertical(classes="form-row"):
                    yield Label("Schema:", classes="form-label")
                    yield Input(
                        placeholder="PUBLIC",
                        id="schema",
                        value=(
                            self.existing_connection.schema_name
                            if self.existing_connection and isinstance(self.existing_connection, SnowflakeConnection)
                            else "PUBLIC"
                        ),
                    )

                with Vertical(classes="form-row"):
                    yield Label("Role:", classes="form-label")
                    yield Input(
                        placeholder="ACCOUNTADMIN (optional)",
                        id="role",
                        value=(
                            self.existing_connection.role or ""
                            if self.existing_connection and isinstance(self.existing_connection, SnowflakeConnection)
                            else ""
                        ),
                    )

            with Vertical(classes="form-row"):
                yield Label("Username:", classes="form-label")
                yield Input(
                    placeholder="username",
                    id="username",
                    value=self.existing_connection.username if self.existing_connection else "",
                )

            with Vertical(classes="form-row"):
                yield Label("Password:", classes="form-label")
                yield Input(placeholder="********", id="password", password=True)

            with Horizontal(classes="modal-buttons"):
                yield Button("Cancel", variant="default", id="cancel")
                yield Button("Save", variant="primary", id="save")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "cancel":
            self.post_message(self.Cancelled())
        elif event.button.id == "save":
            self._submit_form()

    def _submit_form(self) -> None:
        """Validate and submit the form."""
        from pydantic import SecretStr

        try:
            name = self.query_one("#name", Input).value.strip()
            username = self.query_one("#username", Input).value.strip()
            password = self.query_one("#password", Input).value

            if not name or not username:
                self.notify("Name and username are required", severity="error")
                return

            if not password and not self.existing_connection:
                self.notify("Password is required", severity="error")
                return

            if self.connection_type == "source":
                source_type = SourceType(self.query_one("#source_type", Select).value)
                host = self.query_one("#host", Input).value.strip()
                port_str = self.query_one("#port", Input).value.strip()
                database = self.query_one("#database", Input).value.strip()

                if not host or not database:
                    self.notify("Host and database are required", severity="error")
                    return

                try:
                    port = int(port_str)
                except ValueError:
                    self.notify("Port must be a number", severity="error")
                    return

                if not 1 <= port <= 65535:
                    self.notify("Port must be between 1 and 65535", severity="error")
                    return

                connection = SourceConnection(
                    id=self.existing_connection.id if self.existing_connection else None,
                    name=name,
                    type=source_type,
                    host=host,
                    port=port,
                    database=database,
                    username=username,
                    password=SecretStr(password) if password else self.existing_connection.password,
                )
            else:
                account = self.query_one("#account", Input).value.strip()
                warehouse = self.query_one("#warehouse", Input).value.strip()
                database = self.query_one("#database", Input).value.strip()
                schema = self.query_one("#schema", Input).value.strip() or "PUBLIC"
                role = self.query_one("#role", Input).value.strip() or None

                if not account or not warehouse or not database:
                    self.notify("Account, warehouse, and database are required", severity="error")
                    return

                connection = SnowflakeConnection(
                    id=self.existing_connection.id if self.existing_connection else None,
                    name=name,
                    account=account,
                    warehouse=warehouse,
                    database=database,
                    schema_name=schema,
                    username=username,
                    password=SecretStr(password) if password else self.existing_connection.password,
                    role=role,
                )

            self.post_message(self.Submitted(connection))

        except Exception as e:
            self.notify(f"Error: {e}", severity="error")


class ConnectionsPane(Widget):
    """Connection management pane."""

    def __init__(self, connection_manager: ConnectionManager) -> None:
        super().__init__()
        self.connection_manager = connection_manager
        self._show_form = False
        self._form_type = "source"
        self._editing_connection = None

    def compose(self) -> ComposeResult:
        """Create the connections layout."""
        with Container(classes="pane-container"):
            with Horizontal(id="connection-buttons"):
                yield Button("+ Source", variant="primary", id="add-source")
                yield Button("+ Snowflake", variant="primary", id="add-snowflake")

            with Horizontal(id="connection-lists"):
                with Vertical(id="source-connections"):
                    yield Label("Source Connections", classes="section-header")
                    yield ScrollableContainer(id="source-list")

                with Vertical(id="snowflake-connections"):
                    yield Label("Snowflake Connections", classes="section-header")
                    yield ScrollableContainer(id="snowflake-list")

    def on_mount(self) -> None:
        """Refresh connections on mount."""
        self._refresh_connections()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "add-source":
            self._show_add_form("source")
        elif event.button.id == "add-snowflake":
            self._show_add_form("snowflake")

    def _show_add_form(self, connection_type: str) -> None:
        """Show the add connection form."""
        from textual.screen import ModalScreen

        class FormModal(ModalScreen):
            def __init__(self, conn_type: str, pane: "ConnectionsPane") -> None:
                super().__init__()
                self.conn_type = conn_type
                self.pane = pane

            def compose(self) -> ComposeResult:
                with Container(classes="modal-container"):
                    with Container(classes="modal-dialog"):
                        yield ConnectionForm(connection_type=self.conn_type)

            def on_connection_form_submitted(self, event: ConnectionForm.Submitted) -> None:
                if isinstance(event.connection, SourceConnection):
                    self.pane.connection_manager.add_source_connection(event.connection)
                else:
                    self.pane.connection_manager.add_snowflake_connection(event.connection)
                self.pane._refresh_connections()
                self.dismiss()

            def on_connection_form_cancelled(self, event: ConnectionForm.Cancelled) -> None:
                self.dismiss()

        self.app.push_screen(FormModal(connection_type, self))

    def _refresh_connections(self) -> None:
        """Refresh the connection lists."""
        source_list = self.query_one("#source-list", ScrollableContainer)
        snowflake_list = self.query_one("#snowflake-list", ScrollableContainer)

        source_list.remove_children()
        snowflake_list.remove_children()

        for conn in self.connection_manager.list_source_connections():
            card = ConnectionCard(conn, self.connection_manager)
            source_list.mount(card)

        for conn in self.connection_manager.list_snowflake_connections():
            card = ConnectionCard(conn, self.connection_manager)
            snowflake_list.mount(card)

        if not self.connection_manager.list_source_connections():
            source_list.mount(Static("No source connections", classes="empty-state"))

        if not self.connection_manager.list_snowflake_connections():
            snowflake_list.mount(Static("No Snowflake connections", classes="empty-state"))

    def on_connection_card_test_requested(self, event: "ConnectionCard.TestRequested") -> None:
        """Handle connection test request."""
        self._test_connection(event.connection_id, event.is_snowflake)

    @work(thread=True)
    async def _test_connection(self, connection_id: str, is_snowflake: bool) -> None:
        """Test a connection in the background."""
        if is_snowflake:
            result = await self.connection_manager.test_snowflake_connection(connection_id)
        else:
            result = await self.connection_manager.test_source_connection(connection_id)

        self.call_from_thread(self._refresh_connections)

        if result.success:
            self.call_from_thread(
                self.notify, f"Connection successful ({result.latency_ms:.0f}ms)"
            )
        else:
            self.call_from_thread(self.notify, f"Connection failed: {result.message}", severity="error")

    def on_connection_card_delete_requested(self, event: "ConnectionCard.DeleteRequested") -> None:
        """Handle connection delete request."""
        if event.is_snowflake:
            self.connection_manager.delete_snowflake_connection(event.connection_id)
        else:
            self.connection_manager.delete_source_connection(event.connection_id)
        self._refresh_connections()
        self.notify("Connection deleted")
