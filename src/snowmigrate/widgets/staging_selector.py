"""Staging area selector widget."""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Label, RadioButton, RadioSet, Static
from textual.widget import Widget
from textual.message import Message
from textual.reactive import reactive

from snowmigrate.models.staging import StagingArea


class StagingSelector(Widget):
    """Widget for selecting a staging area."""

    class Selected(Message):
        """A staging area was selected."""

        def __init__(self, staging_area: StagingArea) -> None:
            super().__init__()
            self.staging_area = staging_area

    DEFAULT_CSS = """
    StagingSelector {
        height: auto;
        padding: 1;
    }

    StagingSelector .staging-title {
        text-style: bold;
        margin-bottom: 1;
    }

    StagingSelector RadioSet {
        height: auto;
    }

    StagingSelector .staging-option {
        height: auto;
        padding: 0 1;
    }

    StagingSelector .staging-name {
        text-style: bold;
    }

    StagingSelector .staging-details {
        color: $text-muted;
        margin-left: 2;
    }
    """

    selected_id: reactive[str | None] = reactive(None)

    def __init__(self, staging_areas: list[StagingArea]) -> None:
        super().__init__()
        self.staging_areas = staging_areas
        self._staging_map = {s.id: s for s in staging_areas}

    def compose(self) -> ComposeResult:
        """Create the selector layout."""
        yield Label("Staging Area", classes="staging-title")

        if not self.staging_areas:
            yield Static("No staging areas available", classes="empty-state")
            return

        with RadioSet(id="staging-radioset"):
            for staging in self.staging_areas:
                available = "[OK]" if staging.available else "[N/A]"
                label = f"{staging.name} ({staging.type_display}) {available}"
                yield RadioButton(label, id=f"staging-{staging.id}", value=staging.id)

        with Vertical(id="staging-info"):
            yield Label("", id="staging-path")

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        """Handle radio selection change."""
        if event.pressed and event.pressed.value:
            staging_id = event.pressed.value
            self.selected_id = staging_id

            staging = self._staging_map.get(staging_id)
            if staging:
                self.query_one("#staging-path", Label).update(f"Path: {staging.path}")
                self.post_message(self.Selected(staging))

    def get_selected(self) -> StagingArea | None:
        """Get the currently selected staging area."""
        if self.selected_id:
            return self._staging_map.get(self.selected_id)
        return None
