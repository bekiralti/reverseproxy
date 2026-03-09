# Local modules
from reverseproxy.reverseproxy import run_reverseproxy

# Standard modules
import logging
from typing import Callable, Tuple

# 3rd party modules
from textual.app import App, ComposeResult
from textual.containers import HorizontalGroup, VerticalScroll, ScrollableContainer
from textual.widgets import Static

# Logging Handler to make logging *visible* for the TUI
class LogHandler(logging.Handler):
    def __init__(self, container) -> None:
        super().__init__()
        self.container = container

    # logging.Handler method
    def emit(self, record: logging.LogRecord) -> None:
        # format() is defined by the logging module
        self.container.add_log(self.format(record))

# TUI Code:
class Panel(ScrollableContainer):
    """ For Displaying the logging message and forwarding messages."""

    # own methods
    def add_log(self, message: str) -> None:
        self.mount(Static(message))

class ClientServerRow(HorizontalGroup):
    def compose(self) -> ComposeResult:
        yield Panel(id='client')
        yield Panel(id='server')

class TUI(App):
    # textualize attributes
    CSS_PATH = 'tui.tcss'

    # textualize methods
    def compose(self) -> ComposeResult:
        yield VerticalScroll(Panel(id='reverseproxy-log'), id='tui')

    def on_mount(self) -> None:
        reverseproxy_log = self.query_one('#reverseproxy-log', Panel)
        logging.getLogger('reverseproxy').addHandler(LogHandler(reverseproxy_log))
        logging.getLogger('reverseproxy').setLevel(logging.DEBUG)

        self.run_worker(run_reverseproxy(self.ui_callback))

    # own methods
    def ui_callback(self, event: str, connection_id: int, *args) -> None:
        # Avoids if-elif-else chain. Type Hinting to calm down Linter for e.g. the signature of `new_connection`
        dispatch: dict[str, Callable[..., None]] = {
            'new_connection': self.new_connection,
            'client_to_server': self.client_to_server,
            'server_to_client': self.server_to_client,
            'delete_connection': self.delete_connection
        }
        method = dispatch[event]
        method(connection_id, *args)

    def new_connection(self, connection_id: int, client_addr: Tuple[str, int], server_addr: Tuple[str, int]) -> None:
        client_ip, client_port = client_addr
        server_ip, server_port = server_addr

        row = ClientServerRow(id=f"connection-{str(connection_id)}")
        self.query_one('#tui', VerticalScroll).mount(row)

        client = row.query_one('#client', Panel)
        server = row.query_one('#server', Panel)
        client.add_log(f"Connection {connection_id} Client {client_ip}:{client_port}")
        server.add_log(f"Connection {connection_id} Server {server_ip}:{server_port}")

    def client_to_server(self, connection_id: int, message: str) -> None:
        row = self.query_one(f"#connection-{str(connection_id)}", ClientServerRow)
        client = row.query_one('#client', Panel)
        server = row.query_one('#server', Panel)

        client.add_log(f"Sends: {message}")
        server.add_log(f"Receives: {message}")

    def server_to_client(self, connection_id: int, message: str) -> None:
        row = self.query_one(f"#connection-{str(connection_id)}", ClientServerRow)
        server = row.query_one('#server', Panel)
        client = row.query_one('#client', Panel)

        server.add_log(f"Sends: {message}")
        client.add_log(f'Receives: {message}')

    def delete_connection(self, connection_id: int) -> None:
        row = self.query_one(f"#connection-{str(connection_id)}", ClientServerRow)

        row.remove()

TUI().run()