> [!WARNING]
> **Work In Progress**

# Brief description

For each Client the reverseproxy spawns a docker container. The docker container can be anything, there is a simple example in `examples/server.py` and a Dockerfile `dockerfiles/server.docker` for it to create the docker container. 

If you want to use your custom Docker container you have to adjust `server` in the line in `src/reverseproxy/reverseproxy.py`

```python
await asyncio.create_subprocess_exec(
    docker', 'run', '--init', '--rm', '--add-host=host.docker.internal:host-gateway',
    '-e', f"CONNECTION_ID={str(connection_id)}", 'server'
)
```

to the name of your custom Docker container.

The connection between Client <-> Reverseproxy <-> Server is continous and will be deleted if the Client disconnects (or the Reverseproxy or the Server crashes). 

# For testing

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
6. Create server.py docker container:
   ```bash
   docker build -t server -f dockerfiles/server.dockerfile .
   ```
   Explanation: `server` is the dockername, it has to be the same as spawned in `src/reverseproxy/reverseproxy.py` (see above). `.` is the context.
7. Run the UI (as of now only TUI):
   ```bash
   python src/tui/tui.py
   ```
8. Open another Terminal, make sure you are inside the repository directory and start the client example:
   ```bash
   python examples/client.py
   ```
   Optional: Start as many clients as you like.
9. Have fun :)
       - Try sending messages from within each Client.
       - Try sending messages *from the servers* (in this case you have to use the TUI for this) to the clients.
       - Try closing some clients, sending messages, opening more clients, sending messages and so on :)
