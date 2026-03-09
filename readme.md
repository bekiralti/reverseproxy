> [!WARNING]
> **Work In Progress**


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
