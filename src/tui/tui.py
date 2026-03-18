# Local modules
from reverseproxy.reverseproxy import run_reverseproxy

# Standard modules
import logging
from typing import Callable, Tuple

# 3rd party modules
from textual.app import App, ComposeResult
from textual.containers import HorizontalGroup, VerticalScroll, ScrollableContainer
from textual.message import Message
from textual.widgets import Input, Static


# ─── Logging ──────────────────────────────────────────────────────────────────────────────────────────────────────────

class LogHandler(logging.Handler):
    """ Make logging *visible* for the TUI """

    def __init__(self, container) -> None:
        super().__init__()
        self.container = container

    # ─── logging.Handler methods ──────────────────────────────────────────────────────────────────────────────────────

    def emit(self, record: logging.LogRecord) -> None:
        # format() is defined by the logging module
        self.container.add_log(self.format(record))


# ─── Custom Messages ──────────────────────────────────────────────────────────────────────────────────────────────────

class NewConnection(Message):
    """
    Whenever post_message(NewConnection(...)) is called, the Event Handler on_new_connection(message) is called,
    whereas message is an instance of this class NewConnection
    """

    def __init__(self, connection_id: int, client_addr: Tuple[str, int], server_addr: Tuple[str, int]) -> None:
        super().__init__()
        self.connection_id = connection_id
        self.client_addr = client_addr
        self.server_addr = server_addr

class DeleteConnection(Message):
    """
    Whenever post_message(DeleteConnection(...)) is called, the Event Handler on_delete_connection(message) is called,
    whereas message is an instance of this class DeleteConnection
    """

    def __init__(self, connection_id: int) -> None:
        super().__init__()
        self.connection_id = connection_id

class ClientToServer(Message):
    """
    Whenever post_message(ClientToServer(...)) is called, the Event Handler on_client_to_server(message) is called,
    whereas message is an instance of this class ClientToServer
    """

    def __init__(self, connection_id: int, message: str) -> None:
        super().__init__()
        self.connection_id = connection_id
        self.message = message

class ServerToClient(Message):
    """
    Whenever post_message(ServerToClient(...)) is called, the Event Handler on_server_to_client(message) is called,
    whereas message is an instance of this class ServerToClient
    """

    def __init__(self, connection_id: int, message: str) -> None:
        super().__init__()
        self.connection_id = connection_id
        self.message = message

class ServerLog(Message):
    """
    Whenever post_message(ServerLog(...)) is called, the Event Handler on_server_log(message) is called,
    whereas message is an instance of this class ServerLog
    """

    def __init__(self, connection_id: int, message: str) -> None:
        super().__init__()
        self.connection_id = connection_id
        self.message = message


# ─── Widgets ──────────────────────────────────────────────────────────────────────────────────────────────────────────

class Panel(ScrollableContainer):
    """ For Displaying the logging messages and forwarded messages """

    def add_log(self, message: str) -> None:
        self.mount(Static(message))

class ClientServerRow(HorizontalGroup):

    # ─── Textual attributes and methods ───────────────────────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Panel(id='client')
        yield Panel(id='server')


# ─── TUI ──────────────────────────────────────────────────────────────────────────────────────────────────────────────

class TUI(App):

    # ─── Textual attributes and methods ───────────────────────────────────────────────────────────────────────────────

    CSS_PATH = 'tui.tcss'

    def __init__(self) -> None:
        super().__init__()
        self.send_to_server = None

    def compose(self) -> ComposeResult:
        yield VerticalScroll(Panel(id='reverseproxy-log'), id='tui')

    def on_mount(self) -> None:
        reverseproxy_log = self.query_one('#reverseproxy-log', Panel)
        logging.getLogger('reverseproxy').addHandler(LogHandler(reverseproxy_log))
        logging.getLogger('reverseproxy').setLevel(logging.DEBUG)

        self.run_worker(run_reverseproxy(self.ui_callback, self.register_callback))

    # ─── Input / Output Event Handler ─────────────────────────────────────────────────────────────────────────────────

    def on_new_connection(self, message: NewConnection) -> None:
        # Get IP and Port for readability purposes
        client_ip, client_port = message.client_addr
        server_ip, server_port = message.server_addr

        # Create the new Connection row for displaying Client <-> Server messages
        row = ClientServerRow(id=f"connection-{str(message.connection_id)}")
        self.query_one('#tui', VerticalScroll).mount(row)

        # Show on the TUI, that the Connection has been established
        client = row.query_one('#client', Panel)
        server = row.query_one('#server', Panel)
        client.add_log(f"Connection {message.connection_id} Client {client_ip}:{client_port}")
        server.add_log(f"Connection {message.connection_id} Server {server_ip}:{server_port}")

        # Create an Input *field* for the *server side*. Purpose is to manually test the Server -> Client forwarding
        server.mount(Input(placeholder='Send to server ...', type='text', id=f"input-{message.connection_id}"))

    def on_delete_connection(self, message: DeleteConnection) -> None:
        # Get the Client <-> Server Row of the Connection that has been closed and remove it from the TUI
        row = self.query_one(f"#connection-{str(message.connection_id)}", ClientServerRow)
        row.remove()

    def on_client_to_server(self, message: ClientToServer) -> None:
        # Get the Client <-> Server Row that this Client belongs to (done, by looking up `connection_id`)
        row = self.query_one(f"#connection-{str(message.connection_id)}", ClientServerRow)

        # Get the Client's panel in the Client <-> Server Row and show the message that the Client has sent
        client = row.query_one('#client', Panel)
        client.add_log(f"Sends: {message.message}") # LOL at message.message

    def on_server_to_client(self, message: ClientToServer) -> None:
        # Get the Client <-> Server Row that this Server belongs to (done, by looking up `connection_id`)
        row = self.query_one(f"#connection-{str(message.connection_id)}", ClientServerRow)

        # Get the Server's panel in the Client <-> Server Row and show the message that the Server has sent
        server = row.query_one('#server', Panel)
        server.add_log(f"Sends: {message.message}") # LOL at message.message

    def on_server_log(self, message: ServerLog):
        # Get the Client <-> Server Row that this Servevr belongs to (done, by looking up `connection_id`)
        row = self.query_one(f"#connection-{str(message.connection_id)}", ClientServerRow)

        # Get the Server's panel in the Client <-> Server Row and show the Server side log message
        server = row.query_one('#server', Panel)
        server.add_log(message.message)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        connection_id = int(event.input.id.split('-')[1])
        self.run_worker(self.send_to_server(connection_id, event.value))
        event.input.value = ''

    # ─── Reverseproxy Callbacks ───────────────────────────────────────────────────────────────────────────────────────

    def register_callback(self, send_to_server: Callable) -> None:
        self.send_to_server = send_to_server

    def ui_callback(self, event: str, connection_id: int, *args) -> None:
        """
        This function is called by the reverseproxy, whenever:
        - A new client connects to the reverseproxy: `new_connection`
        - A Client sends a message to its connected Server: `client_to_server`
        - A Server sends a message to its connected Client: `server_to_client`
        - To show the Server side logs in the TUI: `server_log`
        - A Client <-> Server connection closes: `delete_connection`

        *args usually contains parameters such as `client_addr`, `server_addr`, `message`:
        - `client_addr` and `server_addr` are meant to show in the TUI the IP and Port of the Client and the Server.
        - `message` is the string, the actual message that is being sent Client -> Server (or Server -> Client).
        """

        match event:
            case 'new_connection':
                self.post_message(NewConnection(connection_id, *args))
            case 'delete_connection':
                self.post_message(DeleteConnection(connection_id))
            case 'client_to_server':
                self.post_message(ClientToServer(connection_id, *args))
            case 'server_to_client':
                self.post_message(ServerToClient(connection_id, *args))
            case 'server_log':
                self.post_message(ServerLog(connection_id, *args))

    def server_log(self, connection_id: int, message: str) -> None:
        row = self.query_one(f"#connection-{str(connection_id)}", ClientServerRow)
        server = row.query_one('#server', Panel)

        server.add_log(message)

    def delete_connection(self, connection_id: int) -> None:
        row = self.query_one(f"#connection-{str(connection_id)}", ClientServerRow)

        row.remove()

TUI().run()