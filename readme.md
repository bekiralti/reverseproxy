# Programmablauf

1. Client Verbindungen annehmen. Verwende `asyncio` um mehrere Clients *gleichzeitig* zu verarbeiten.
   ```python
   import asyncio
   
   async def client_callback(reader, writer):
       pass
   
   async def run_reverseproxy():
       socket_for_client_connections = await asyncio.start_server(client_callback, '127.0.0.1', 3000)
       async with socket_for_client_connections:
           await socket_for_client_connections.serve_forever()
   
   asyncio.run(run_reverseproxy())
   ```
   
2. Eine eindeutige Connection ID zuweisen, um Client und Server in einem Look-Up-Table zu speichern.
   ```python
   import collections
   
   def get_id():
       if released_ids:
   
   async def client_callback(reader, writer):
       connection_id = get_id()
   ```