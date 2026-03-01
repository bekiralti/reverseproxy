# Own modules
from reverseproxy.reverseproxy import run_reverseproxy

# Standard modules
import logging, uuid

# 3rd party modules
from textual.app import App, ComposeResult
from textual.containers import HorizontalGroup, VerticalScroll, ScrollableContainer
from textual.widgets import Static

# Helper Code for the TUI:
class LogHandler(logging.Handler):
    def __init__(self, container) -> None:
        super().__init__()
        self.container = container

    def emit(self, record: logging.LogRecord) -> None:
        self.container.add_log(self.format(record))

# TUI Code:
class LogContainer(ScrollableContainer):
    def add_log(self, message: str) -> None:
        self.mount(Static(message))

class Reverseproxy(LogContainer):
    # textualize methods
    def on_mount(self) -> None:
        # To catch and display logging messages from the reverseproxy module
        logging.getLogger('reverseproxy').addHandler(LogHandler(self))
        logging.getLogger('reverseproxy').setLevel(logging.DEBUG)

class ClientServerRow(HorizontalGroup):
    def compose(self) -> ComposeResult:
        yield LogContainer(id='client')
        yield LogContainer(id='server')

class TUI(App):
    # textualize attributes
    CSS_PATH = 'terminal.tcss'

    # textualize methods
    def compose(self) -> ComposeResult:
        yield VerticalScroll(Reverseproxy())

    def on_mount(self) -> None:
        self.run_worker(run_reverseproxy(self.ui_callback))

    # own methods
    async def ui_callback(self, event: str, connection_id: uuid.UUID, *args) -> None:
        # Avoids if-elif-else chain
        dispatch = {
            'new_connection': self.new_connection,
            'client_to_server': self.client_to_server,
            'server_to_client': self.server_to_client,
            'delete_connection': self.delete_connection
        }
        method = dispatch.get(event)
        method(connection_id, *args)

    def new_connection(self, connection_id: uuid.UUID) -> None:
        row = ClientServerRow(id=f"connection-{str(connection_id)}")
        self.query_one(VerticalScroll).mount(row)

    def client_to_server(self, connection_id: uuid.UUID, message: str) -> None:
        row = self.query_one(f"#connection-{str(connection_id)}")
        client = row.query_one('#client', LogContainer)
        server = row.query_one('#server', LogContainer)
        client.add_log(f"Sends: {message}")
        server.add_log(f"Receives: {message}")

    def server_to_client(self, connection_id: uuid.UUID, message: str) -> None:
        row = self.query_one(f"#connection-{str(connection_id)}")
        server = row.query_one('#server', LogContainer)
        client = row.query_one('#client', LogContainer)
        server.add_log(f"Sends: {message}")
        client.add_log(f'Receives: {message}')

    def delete_connection(self, connection_id: uuid.UUID) -> None:
        row = self.query_one(f"#connection-{str(connection_id)}")
        row.remove()

TUI().run()