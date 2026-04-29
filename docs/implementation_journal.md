# What is this file about?

In this file, we will step-by-step go through the thought processes, reasoning and learning that went into this project.

In order to handle more than 1 Client *simultaneously* we will use Python's asynchronous programming (Keywords: `async/await`, Standard Library: `asyncio`).
We could have also used *m̀ultithreading* or any other form of concurrency however `asyncio` seemed to be the most straightforward way to me.

# Step 1: Create a socket on which this Reverseproxy listens

The Reverseproxy socket can simply be created by the following line of code:

```python
# '0.0.0.0' means the socket listens on all IP addresses.
# 3000 is the Port. You can use any other Port you desire as long as it is free, in other words not reserved.
socket = await asyncio.start_server(client_callback_cb, '0.0.0.0', 3000)
```

When a Client connects, the function `client_callback_cb(reader, writer)` will be called. 
Through the `reader` object the Reverseproxy is able to receive messages from the Client that connected and through the `writer` object the Reverseproxy is able to send messages to the Client that connected.

Here is a minimal working example. It does nothing though yet.

```python
import asyncio

async def reverseproxy_handler(reader, writer):
    pass

async def main():
    reverseproxy = await asyncio.start_server(reverseproxy_handler, '0.0.0.0', 3000)
    async with reverseproxy:
        await reverseproxy.serve_forever()

asyncio.run(main())
```

# Step 2: Identifying the Client

