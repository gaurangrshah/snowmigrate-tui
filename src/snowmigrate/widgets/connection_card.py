"""Connection card widget."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Label, Static
from textual.widget import Widget
from textual.message import Message

from snowmigrate.models.connection import (
    ConnectionStatus,
    SnowflakeConnection,
    SourceConnection,
)
from snowmigrate.services.connection_manager import ConnectionManager


class ConnectionCard(Widget):
    """Display card for a connection."""

    class TestRequested(Message):
        """Request to test a connection."""

        def __init__(self, connection_id: str, is_snowflake: bool) -> None:
            super().__init__()
            self.connection_id = connection_id
            self.is_snowflake = is_snowflake

    class DeleteRequested(Message):
        """Request to delete a connection."""

        def __init__(self, connection_id: str, is_snowflake: bool) -> None:
            super().__init__()
            self.connection_id = connection_id
            self.is_snowflake = is_snowflake

    class EditRequested(Message):
        """Request to edit a connection."""

        def __init__(
            self, connection: SourceConnection | SnowflakeConnection, is_snowflake: bool
        ) -> None:
            super().__init__()
            self.connection = connection
            self.is_snowflake = is_snowflake

    DEFAULT_CSS = """
    ConnectionCard {
        height: auto;
        margin: 0 0 1 0;
        padding: 1;
        border: solid $primary;
    }

    ConnectionCard:focus {
        border: solid $accent;
    }

    ConnectionCard .card-header {
        height: auto;
    }

    ConnectionCard .card-title {
        text-style: bold;
    }

    ConnectionCard .card-info {
        color: $text-muted;
    }

    ConnectionCard .card-status {
        dock: right;
    }

    ConnectionCard .card-buttons {
        margin-top: 1;
    }

    ConnectionCard .card-buttons Button {
        margin-right: 1;
    }
    """

    def __init__(
        self,
        connection: SourceConnection | SnowflakeConnection,
        connection_manager: ConnectionManager,
    ) -> None:
        super().__init__()
        self.connection = connection
        self.connection_manager = connection_manager
        self.is_snowflake = isinstance(connection, SnowflakeConnection)

    def compose(self) -> ComposeResult:
        """Create the card layout."""
        with Vertical():
            with Horizontal(classes="card-header"):
                yield Label(self.connection.name, classes="card-title")
                yield Label(self._status_text, classes=f"card-status status-{self.connection.status.value}")

            if self.is_snowflake:
                conn = self.connection
                yield Label(f"Account: {conn.account}", classes="card-info")
                yield Label(f"Warehouse: {conn.warehouse}", classes="card-info")
                yield Label(f"Database: {conn.database}.{conn.schema_name}", classes="card-info")
            else:
                conn = self.connection
                yield Label(f"Type: {conn.type.value.title()}", classes="card-info")
                yield Label(f"Host: {conn.display_host}", classes="card-info")
                yield Label(f"Database: {conn.database}", classes="card-info")

            if self.connection.error_message:
                yield Label(f"Error: {self.connection.error_message}", classes="card-info status-failed")

            with Horizontal(classes="card-buttons"):
                yield Button("Test", variant="primary", id="test")
                yield Button("Edit", variant="default", id="edit")
                yield Button("Delete", variant="error", id="delete")

    @property
    def _status_text(self) -> str:
        """Get status display text."""
        status_labels = {
            ConnectionStatus.UNKNOWN: "[?]",
            ConnectionStatus.CONNECTED: "[OK]",
            ConnectionStatus.FAILED: "[FAIL]",
            ConnectionStatus.TESTING: "[...]",
        }
        return status_labels.get(self.connection.status, "[?]")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        event.stop()
        if event.button.id == "test":
            self.post_message(self.TestRequested(self.connection.id, self.is_snowflake))
        elif event.button.id == "edit":
            self.post_message(self.EditRequested(self.connection, self.is_snowflake))
        elif event.button.id == "delete":
            self.post_message(self.DeleteRequested(self.connection.id, self.is_snowflake))
