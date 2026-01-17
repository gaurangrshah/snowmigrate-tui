"""Main Textual application entry point."""

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header, TabbedContent, TabPane

from snowmigrate.screens.connections import ConnectionsPane
from snowmigrate.screens.dashboard import DashboardPane
from snowmigrate.screens.browser import BrowserPane
from snowmigrate.services.connection_manager import ConnectionManager
from snowmigrate.services.migration_engine import MigrationEngine


class SnowMigrateApp(App):
    """SnowMigrate TUI - Terminal UI for Snowflake data migrations."""

    TITLE = "SnowMigrate"
    SUB_TITLE = "Snowflake Migration Manager"
    CSS_PATH = "styles.tcss"

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("?", "help", "Help", show=True),
        Binding("d", "switch_tab('dashboard')", "Dashboard", show=True),
        Binding("c", "switch_tab('connections')", "Connections", show=True),
        Binding("b", "switch_tab('browser')", "Browser", show=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.connection_manager = ConnectionManager()
        self.migration_engine = MigrationEngine(self.connection_manager)

    def compose(self) -> ComposeResult:
        """Create the application layout."""
        yield Header()
        with TabbedContent(initial="dashboard"):
            with TabPane("Dashboard", id="dashboard"):
                yield DashboardPane(self.migration_engine)
            with TabPane("Connections", id="connections"):
                yield ConnectionsPane(self.connection_manager)
            with TabPane("Browser", id="browser"):
                yield BrowserPane(self.connection_manager)
        yield Footer()

    def action_switch_tab(self, tab_id: str) -> None:
        """Switch to a specific tab."""
        tabbed_content = self.query_one(TabbedContent)
        tabbed_content.active = tab_id

    def action_help(self) -> None:
        """Show help screen."""
        self.push_screen("help")


def main() -> None:
    """Run the application."""
    app = SnowMigrateApp()
    app.run()


if __name__ == "__main__":
    main()
