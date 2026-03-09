> [!WARNING]
> **Work In Progress**

# Brief description

The reverseproxy spawns for each connecting Client a Docker container and establishes the connection.

# Installation

Assuming you are using a Linux distribution (might or might not work on other Operating Systems).

1. Download this repo:
   ```bash
   git clone https://github.com/bekiralti/reverseproxy
   cd reverseproxy
   ```
3. Create `venv`:
   ```python
   python -m venv .venv
   source .venv/bin/activate
   ```
5. Install:
   ```bash
   pip install .
   ```
   or if you want to edit the source files (e.g. `src/reverseproxy/reverseproxy.py`) and see its effects immediately:
   ```bash
   pip install -e .
   ```

# Example

1. Create server.py docker container:
   ```bash
   docker build -t server -f dockerfiles/server.dockerfile .
   ```
   Explanation: `server` is the dockername, it has to be the same as spawned in `src/reverseproxy/reverseproxy.py` (see above). `.` is the context.
2. Run the UI (as of now only TUI):
   ```bash
   python src/tui/tui.py
   ```
3. Open another Terminal, make sure you are inside the repository directory and start the client example:
   ```bash
   python examples/client.py
   ```
   Optional: Start as many clients as you like.
4. Have fun :)
       - Try sending messages from within each Client.
       - Try sending messages *from the servers* (in this case you have to use the TUI for this) to the clients.
       - Try closing some clients, sending messages, opening more clients, sending messages and so on :)

# Architecture

It is designed in such a way that the core `src/reverseproxy/reverseproxy.py` can run on its own. It is not dependent from the UI. It is not dependent from the Docker container. This means you can fully provide your own UI implementation and Docker container.

*Further explanations coming soon.*
