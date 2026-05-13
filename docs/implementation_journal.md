# What is this file about?

In this file, I will try to go step-by-step through my thought processes and reasoning.

# Step 1: Plan

Let's take a look again at the diagram from the video on the main page.

![2 Clients <-> Reverseproxy <-> 2 Containers](./pics/2clients-rp-2containers.png)

Client 1 and Client 2 are supposed to connect to the Reverseproxy via typing in its URL in a Browser such as Firefox.
As soon as Client 1 connects the Reverseproxy starts a Node-RED Docker-Container for Client 1.
As soon as Client 2 connects the Reverseproxy starts a Node-RED Docker-Container for Client 2.
The Reverseproxy connects Client 1 with Container 1 and Client 2 with Container 2.
Both connections are basically isolated from each other by the Reverseproxy.
When a Client disconnects its Container also gets deleted.

# Step 2: IPC (Inter-Process-Communication)

First of all, I had to figure out how Client 1 can connect to the Reverseproxy. 
Since the Browser is a process and my Reverseproxy is a process the immediate and only answer that came to my mind was **Sockets**.

We can easily define a TCP (`SOCK_STREAM`) socket and bind it to an IPv4 adress (`AF_INET`) that is available to our device.

> [!NOTE]
> You can check which IP addresses are available to your device by typing in the command `ìp addr` in your terminal.

Let's take a look at an example code:

```python
# ./examples/step2_1.py
import socket
from socket import AF_INET, SOCK_STREAM

with socket.socket(AF_INET, SOCK_STREAM) as s:
    print("Binding socket")
    s.bind(('0.0.0.0', 1453))
    s.listen()
    print("Waiting for a connection")
    conn, addr = s.accept()
    with conn:
        print(f"Connected by {addr}")
```

The above Code implements a TCP socket that binds on all IPv4 addresses that are available to your device (`0.0.0.0`).

> [!NOTE]
> This means, you can communicate with this socket by typing in any of the IPv4 addresses you see in the `ìp addr` output.

If I run the above Code and type in my Browser `localhost:1453`, then the above Code gives me the following output:

```
Binding socket
Waiting for a connection
Connected by ('127.0.0.1', 60934)

Process finished with exit code 0
```

Now, let's read if and what kind of message we receive when the Browser connects to our socket.

```python
# ./examples/step2_2.py
import socket
from socket import AF_INET, SOCK_STREAM

with socket.socket(AF_INET, SOCK_STREAM) as s:
    print("Binding socket")
    s.bind(('0.0.0.0', 1453))
    s.listen()
    print("Waiting for a connection")
    conn, addr = s.accept()
    with conn:
        print(f"Connected by {addr}")
        while True:
            message = conn.recv(1024)
            print(message)
```

We read the incoming message in a loop. 
In each iteration we try to read `1024` Bytes (you can for example experiment with this number) from the *network buffer*.

If I run the above Code and type in the URL `localhost:1453` in my Browser I get the following output:

```
Binding socket
Waiting for a connection
Connected by ('127.0.0.1', 46232)
b'GET / HTTP/1.1\r\nHost: localhost:1453\r\nUser-Agent: Mozilla/5.0 (X11; Linux x86_64; rv:150.0) Gecko/20100101 Firefox/150.0\r\nAccept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8\r\nAccept-Language: de,en-US;q=0.9,en;q=0.8\r\nAccept-Encoding: gzip, deflate, br, zstd\r\nSec-GPC: 1\r\nConnection: keep-alive\r\nUpgrade-Insecure-Requests: 1\r\nSec-Fetch-Dest: document\r\nSec-Fetch-Mode: navigate\r\nSec-Fetch-Site: none\r\nSec-Fetch-User: ?1\r\nPriority: u=0, i\r\n\r\n'
```

> [!NOTE]
> I desperately tried to find a function such as `read_entire_message()`, 
> but it looks like in network programming we don't have such luxurious functions. 
> For me, this was a key point in which I realized why protocols even exist in the first place.

## Step 2.1: Analyzing the Browser's first message

Let's take a look at the output starting with `GET / HTTP/1.1\r\n...`. 
If you check out [RFC 9110](https://www.rfc-editor.org/rfc/rfc9110.html) you will realize that the Browser's first message is a so called HTTP-Request.
The schema is always the same:

```
<HTTP-Header>
\r\n
<HTTP-Body>
```

Realizing this demystified websites for me. 
A *website* is nothing but a process (written in whatever programming language) that listens on a socket,
processes the incoming HTTP-Requests and replies accordingly. 
The website needs to reply in such a way that the Browser can understand it. 

The reply is structurally very similar to the HTTP-Request. The major differences are the header fields.
Other than that each header field ends with `\r\n` and the Body and Header are separated by a blank line `\r\n\r\n`.

```
<HTTP-Header>
\r\n
<HTTP-Body>
```

Therefore, the reply is simply called HTTP-Response.

The Browser always sends this or a similar message upon connecting to a website.

> [!NOTE]
> You can check this out for yourself by opening up *networktools* and connecting to any website.

## Step 2.2: Realizing why today's Browsers are such massive pieces of software

If you looked a bit into programming a website you will know the three fundamental file types: HTML, CSS and JS.
The HTTP-Body in the HTTP-Response can be written in HTML, CSS or JS. 
We can expect that a (major) Browser such as Firefox will be able to interpret the HTTP-Body correctly.

This realization on the other hand, made me aware that I can simply write my own Browser. 
Here is a little sketch for it:

- Upon typing in the URL the Browser has to automatically send a proper HTTP-Request.
- The Browser has to parse and correctly interpret the HTTP-Response.

Sounds simple, but I will also have to write the logic that interprets and displays all the HTML, CSS and JS code, 
which I imagine is exhausting. I now understand why Browser are such massive pieces of software. Impressive.

## Step 2.3: End of connection

If the above Code is still running you will notice that the page is still *loading* in your Browser. 
Once you click on `Stop loading Page` you will get a bunch of `b''` in our Code output. 
The `b''` signals the end of connection. 

Let's make use of it in our Code:

```python
# ./examples/step2_3.py
import socket
from socket import AF_INET, SOCK_STREAM

with socket.socket(AF_INET, SOCK_STREAM) as s:
    print("Binding socket")
    s.bind(('0.0.0.0', 1453))
    s.listen()
    print("Waiting for a connection")
    conn, addr = s.accept()
    with conn:
        print(f"Connected by {addr}")
        while True:
            message = conn.recv(1024)
            print(message)
            if not message:
                break
```

# Step 3: Handling more than one Client at the same time

As of now, the above Code can only handle exactly one Connection.
We could simply wrap `s.accept()` inside a `ẁhile True:` loop to handle more than one Connection (simply speaking each Connection could be a Client). 

```python
# ./examples/step3_1.py
import socket
from socket import AF_INET, SOCK_STREAM

with socket.socket(AF_INET, SOCK_STREAM) as s:
    print("Binding socket")
    s.bind(('0.0.0.0', 1453))
    s.listen()
    print("Waiting for a connection")
    while True:
        conn, addr = s.accept()
        with conn:
            print(f"Connected by {addr}")
            while True:
                message = conn.recv(1024)
                print(message)
                if not message:
                    break
```

However, we will only be able to handle only one Connection at a time. 
In other words, we can only process each Client sequentially. 
As one Client is being processed all the other Clients will have to wait on that one Client.

I don't want Clients to have to wait on other Clients. Each Client should be processed *in parallel* aka *concurrently*.
There are multiple ways to accomplish this. One way is through `multithreading` or `multiprocessing`. 

> [!NOTE]
> Python's `multiprocessing` is basically `multithreading` except each Thread gets its own entire Python Interpreter,
> thus creating way more overhead.

Another way is by using Python's `asyncio` standard library.

> [!NOTE]
> I have linked a YouTube video at the end of this document for anyone who wants to develop a better understanding of Python's `asyncio` module.
> That video helped me a lot, I watched it halfway through.

Let's rewrite the above example with the `asyncio` module.

```python
# ./examples/step3_2.py
import asyncio
from asyncio import StreamReader, StreamWriter

async def client_connected_cb(reader: StreamReader, writer: StreamWriter) -> None: 
    print("A Client has connected")
    while True:
        message = await reader.read(1024)
        print(message)
        if not message:
            break

async def main():
    s = await asyncio.start_server(client_connected_cb, '0.0.0.0', 1453)
    async with s:
        await s.serve_forever()

asyncio.run(main())
```

The output will look something like this:

```
A Client has connected
b'GET / HTTP/1.1\r\nHost: localhost:1453\r\nUser-Agent: Mozilla/5.0 (X11; Linux x86_64; rv:150.0) Gecko/20100101 Firefox/150.0\r\nAccept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8\r\nAccept-Language: de,en-US;q=0.9,en;q=0.8\r\nAccept-Encoding: gzip, deflate, br, zstd\r\nSec-GPC: 1\r\nConnection: keep-alive\r\nUpgrade-Insecure-Requests: 1\r\nSec-Fetch-Dest: document\r\nSec-Fetch-Mode: navigate\r\nSec-Fetch-Site: none\r\nSec-Fetch-User: ?1\r\nPriority: u=0, i\r\n\r\n'
b''
```

Quick recap on what is happening in the Code. For each connection the `client_connected_cb` function is called.
Each connection gets its own `StreamReader` and `StreamWriter` object. Basically speaking, 
with the `StreamReader` object you can read whatever the Client sends on that connection and with the `StreamWriter` object you can reply to that Client.

> [!NOTE]
> The `StreamReader` object provides us with more comfortable high-level functions such as `readuntil()` or `readexactly()`, 
> which we can and will make use of thanks to the way HTTP is defined.

# Step 4: Spawning a Node-RED Docker-Container

> [!TIP]
> Make sure to have the `docker` module installed in your Python virtual environment.
> Make sure that you also have docker installed in your OS with the configurations, which you can find in the main page.

> [!NOTE]
> The `àsyncio` module helps with IO-Bound operations. Thus, I will try to make every IO-Bound operation async.

Before starting the Node-RED Docker-Container we have to make sure that we create a data folder for it.

```python
# ./examples/step4_1.py
import asyncio
import docker
import uuid
from asyncio import StreamReader, StreamWriter
from pathlib import Path

d = docker.from_env()

async def client_connected_cb(reader: StreamReader, writer: StreamWriter) -> None:
    path = Path(__file__).parent.parent / 'data' / str(uuid.uuid4())
    await asyncio.to_thread(path.mkdir)

async def main():
    s = await asyncio.start_server(client_connected_cb, '0.0.0.0', 1453)
    async with s:
        await s.serve_forever()

asyncio.run(main())
```

Now, we will create the Docker-Container. We will let the Kernel choose a free port for the Docker-Container.

```python
# ./examples/step4_2.py
import asyncio
import docker
import uuid
from asyncio import StreamReader, StreamWriter
from pathlib import Path

d = docker.from_env()

async def client_connected_cb(reader: StreamReader, writer: StreamWriter) -> None:
    path = Path(__file__).parent.parent / 'data' / str(uuid.uuid4())
    await asyncio.to_thread(path.mkdir)
    container = await asyncio.to_thread(
        d.containers.run,
        'nodered/node-red',
        detach=True,                                     # -d
        ports={'1880/tcp': 0},                           # -p 0:1880 (0 lets the kernel choose a free port)
        volumes={path: {'bind': '/data', 'mode': 'rw'}}  # -v ./docker/data:/data
    )

async def main():
    s = await asyncio.start_server(client_connected_cb, '0.0.0.0', 1453)
    async with s:
        await s.serve_forever()

asyncio.run(main())
```

Since we let the Kernel choose a free port, 
we have to first get the port number in order to build a connection to that Docker-Container.

```python
# ./examples/step4_3.py
import asyncio
import docker
import uuid
from asyncio import StreamReader, StreamWriter
from pathlib import Path

d = docker.from_env()

async def client_connected_cb(reader: StreamReader, writer: StreamWriter) -> None:
    path = Path(__file__).parent.parent / 'data' / str(uuid.uuid4())
    await asyncio.to_thread(path.mkdir)
    container = await asyncio.to_thread(
        d.containers.run,
        'nodered/node-red',
        detach=True,                                     # -d
        ports={'1880/tcp': 0},                           # -p 0:1880 (0 lets the kernel choose a free port)
        volumes={path: {'bind': '/data', 'mode': 'rw'}}  # -v ./docker/data:/data
    )
    print(container.ports)
    port = container.ports['1880/tcp'][0]['HostPort']
    print(port)

async def main():
    s = await asyncio.start_server(client_connected_cb, '0.0.0.0', 1453)
    async with s:
        await s.serve_forever()

asyncio.run(main())
```

> [!NOTE]
> The `ports` attribute returns something like `{'1880/tcp': [{'HostIp': '0.0.0.0', 'HostPort': '32778'}, {'HostIp': '::', 'HostPort': '32778'}]}`.

The above Code will most likely give a `KeyError: '1880/tcp`, 
that happens because we need to refresh the container values.

Let's try again. This time by calling the `reload()` method.

```python
# ./examples/step4_4.py
import asyncio
import docker
import uuid
from asyncio import StreamReader, StreamWriter
from pathlib import Path

d = docker.from_env()

async def client_connected_cb(reader: StreamReader, writer: StreamWriter) -> None:
    path = Path(__file__).parent.parent.parent / 'data' / str(uuid.uuid4())
    await asyncio.to_thread(path.mkdir)
    container = await asyncio.to_thread(
        d.containers.run,
        'nodered/node-red',
        detach=True,                                     # -d
        ports={'1880/tcp': 0},                           # -p 0:1880 (0 lets the kernel choose a free port)
        volumes={path: {'bind': '/data', 'mode': 'rw'}}  # -v ./docker/data:/data
    )
    await asyncio.to_thread(container.reload)
    print(container.ports)
    port = container.ports['1880/tcp'][0]['HostPort']
    print(port)

async def main():
    s = await asyncio.start_server(client_connected_cb, '0.0.0.0', 1453)
    async with s:
        await s.serve_forever()

asyncio.run(main())
```

This time I get the following output (hopefully you too if you follow along):

```
{'1880/tcp': [{'HostIp': '0.0.0.0', 'HostPort': '32779'}, {'HostIp': '::', 'HostPort': '32779'}]}
32779
{'1880/tcp': [{'HostIp': '0.0.0.0', 'HostPort': '32780'}, {'HostIp': '::', 'HostPort': '32780'}]}
32780
{'1880/tcp': [{'HostIp': '0.0.0.0', 'HostPort': '32781'}, {'HostIp': '::', 'HostPort': '32781'}]}
32781
{'1880/tcp': [{'HostIp': '0.0.0.0', 'HostPort': '32782'}, {'HostIp': '::', 'HostPort': '32782'}]}
32782
{'1880/tcp': [{'HostIp': '0.0.0.0', 'HostPort': '32783'}, {'HostIp': '::', 'HostPort': '32783'}]}
32783
{'1880/tcp': [{'HostIp': '0.0.0.0', 'HostPort': '32784'}, {'HostIp': '::', 'HostPort': '32784'}]}
32784
{'1880/tcp': [{'HostIp': '0.0.0.0', 'HostPort': '32785'}, {'HostIp': '::', 'HostPort': '32785'}]}
32785
{'1880/tcp': [{'HostIp': '0.0.0.0', 'HostPort': '32786'}, {'HostIp': '::', 'HostPort': '32786'}]}
32786
{'1880/tcp': [{'HostIp': '0.0.0.0', 'HostPort': '32787'}, {'HostIp': '::', 'HostPort': '32787'}]}
32787
{'1880/tcp': [{'HostIp': '0.0.0.0', 'HostPort': '32788'}, {'HostIp': '::', 'HostPort': '32788'}]}
32788
```

As you can guess, 10 Node-RED Docker-Containers were created. 
This happens because the Browser receives an EOF before receiving a proper HTTP-Response.

> [!NOTE]
> Quite possible that the Browser thinks that the Connection has been lost by accident and not by intention.
> Thus it simply tries to reconnect in the hopes to receive an HTTP-Response.

> [!TIP]
> You can stop and remove all the Docker-Containers by typing `docker stop $(docker ps -qa)` and then `docker rm $(docker ps -qa)` in your terminal.
> Also make sure to delete all the directories inside `reverseproxy/data/`.

# Step 5: Forwarding

Since Node-RED can speak HTTP it will be enough to simply forward the incoming HTTP-Request to the Node-RED Docker-Container.

Let's simply forward the very first HTTP-Request and see what happens.
We also have to forward the HTTP-Response from Node-RED otherwise we will have a similar situation as above (Browser tries to reconnect up to 10 times because it received an EOF before receiving an HTTP-Reponse).

```python
# ./examples/step5_1.py
import asyncio
import docker
import uuid
from asyncio import StreamReader, StreamWriter
from pathlib import Path

d = docker.from_env()

async def client_connected_cb(client_reader: StreamReader, client_writer: StreamWriter) -> None:
    # HTTP-Request
    http_header = await client_reader.readuntil(b'\r\n\r\n')
    print(http_header)

    # Docker-Container
    path = Path(__file__).parent.parent.parent / 'data' / str(uuid.uuid4())
    print(path)
    await asyncio.to_thread(path.mkdir)
    container = await asyncio.to_thread(
        d.containers.run,
        'nodered/node-red',
        detach=True,                                     # -d
        ports={'1880/tcp': 0},                           # -p 0:1880 (0 lets the kernel choose a free port)
        volumes={path: {'bind': '/data', 'mode': 'rw'}}  # -v ./docker/data:/data
    )
    await asyncio.to_thread(container.reload)
    port = container.ports['1880/tcp'][0]['HostPort']
    print(port)

    # Forward
    container_reader, container_writer = await asyncio.open_connection('localhost', port)
    container_writer.write(http_header)
    await container_writer.drain()

async def main():
    s = await asyncio.start_server(client_connected_cb, '0.0.0.0', 1453)
    async with s:
        await s.serve_forever()

asyncio.run(main())
```

I get a `ConnectionResetError`:

```
ConnectionResetError: [Errno 104] Connection reset by peer
```

Apparently, something is not ready yet (most likely Node-RED, even though `open_connection()` doesn't throw an error).
In order to find the issue I placed `await asyncio.sleep(10)` at various places. 
The error disappeared when I placed it right before `open_connection()`. 
Another way of solving this is to put the Codeblock in question into a retry loop.

```python
# ./examples/step5_2.py
import asyncio
import docker
import uuid
from asyncio import StreamReader, StreamWriter, IncompleteReadError
from pathlib import Path

d = docker.from_env()

async def client_connected_cb(client_reader: StreamReader, client_writer: StreamWriter) -> None:
    # HTTP-Request
    http_header = await client_reader.readuntil(b'\r\n\r\n')
    print(http_header)

    # Docker-Container
    path = Path(__file__).parent.parent.parent / 'data' / str(uuid.uuid4())
    await asyncio.to_thread(path.mkdir)
    container = await asyncio.to_thread(
        d.containers.run,
        'nodered/node-red',
        detach=True,                                     # -d
        ports={'1880/tcp': 0},                           # -p 0:1880 (0 lets the kernel choose a free port)
        volumes={path: {'bind': '/data', 'mode': 'rw'}}  # -v ./docker/data:/data
    )
    await asyncio.to_thread(container.reload)
    port = container.ports['1880/tcp'][0]['HostPort']
    print(port)

    # Forward
    while True:
        try:
            container_reader, container_writer = await asyncio.open_connection('localhost', port)
            container_writer.write(http_header)
            await container_writer.drain()

            http_header = await container_reader.readuntil(b'\r\n\r\n')
        except ConnectionResetError:
            print("ConnectionResetError")
            await asyncio.sleep(1)
            continue
        except IncompleteReadError:
            print("IncompleteReadError")
            await asyncio.sleep(1)
            continue
        break
    print(http_header)
    client_writer.write(http_header)
    await client_writer.drain()

async def main():
    s = await asyncio.start_server(client_connected_cb, '0.0.0.0', 1453)
    async with s:
        await s.serve_forever()

asyncio.run(main())
```

I also encountered an `ÌncompletedReadError` and added a 1-second waiting time before trying again. 
The output looks something like the following:

```
b'GET / HTTP/1.1\r\nHost: localhost:1453\r\nUser-Agent: Mozilla/5.0 (X11; Linux x86_64; rv:150.0) Gecko/20100101 Firefox/150.0\r\nAccept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8\r\nAccept-Language: de,en-US;q=0.9,en;q=0.8\r\nAccept-Encoding: gzip, deflate, br, zstd\r\nSec-GPC: 1\r\nConnection: keep-alive\r\nUpgrade-Insecure-Requests: 1\r\nSec-Fetch-Dest: document\r\nSec-Fetch-Mode: navigate\r\nSec-Fetch-Site: none\r\nSec-Fetch-User: ?1\r\nPriority: u=0, i\r\nPragma: no-cache\r\nCache-Control: no-cache\r\n\r\n'
32890
ConnectionResetError
IncompleteReadError
IncompleteReadError
b'HTTP/1.1 200 OK\r\nAccess-Control-Allow-Origin: *\r\nContent-Type: text/html; charset=utf-8\r\nContent-Length: 1733\r\nETag: W/"6c5-TkRPm8c1wNQQYwwWMSaVuQjC0Aw"\r\nDate: Tue, 12 May 2026 21:52:05 GMT\r\nConnection: keep-alive\r\nKeep-Alive: timeout=5\r\n\r\n'
```

If you look through the header fields in the HTTP-Response you will notice `Content-Length: 1733`. 
This means, that Node-RED also sends an HTTP-Body, which we didn't forward.

Let's forward that too.

```python
# ./examples/step5_3.py
import asyncio
import docker
import uuid
import re
from asyncio import StreamReader, StreamWriter, IncompleteReadError
from pathlib import Path

d = docker.from_env()

async def client_connected_cb(client_reader: StreamReader, client_writer: StreamWriter) -> None:
    # HTTP-Request
    http_header = await client_reader.readuntil(b'\r\n\r\n')
    print(http_header)

    # Docker-Container
    path = Path(__file__).parent.parent.parent / 'data' / str(uuid.uuid4())
    await asyncio.to_thread(path.mkdir)
    container = await asyncio.to_thread(
        d.containers.run,
        'nodered/node-red',
        detach=True,                                     # -d
        ports={'1880/tcp': 0},                           # -p 0:1880 (0 lets the kernel choose a free port)
        volumes={path: {'bind': '/data', 'mode': 'rw'}}  # -v ./docker/data:/data
    )
    await asyncio.to_thread(container.reload)
    port = container.ports['1880/tcp'][0]['HostPort']
    print(port)

    # Forward
    while True:
        try:
            container_reader, container_writer = await asyncio.open_connection('localhost', port)
            container_writer.write(http_header)
            await container_writer.drain()

            http_header = await container_reader.readuntil(b'\r\n\r\n')
        except ConnectionResetError:
            print("ConnectionResetError")
            await asyncio.sleep(1)
            continue
        except IncompleteReadError:
            print("IncompleteReadError")
            await asyncio.sleep(1)
            continue
        break
    print(http_header)

    content_length = re.search(rb'Content-Length:\s*(\d+)', http_header, re.IGNORECASE)
    content_length = int(content_length.group(1)) if content_length else 0
    http_body = await container_reader.readexactly(content_length)
    print(http_body)
    client_writer.write(http_header + http_body)
    await client_writer.drain()

async def main():
    s = await asyncio.start_server(client_connected_cb, '0.0.0.0', 1453)
    async with s:
        await s.serve_forever()

asyncio.run(main())
```

The output looks something like this:

```
b'GET / HTTP/1.1\r\nHost: localhost:1453\r\nUser-Agent: Mozilla/5.0 (X11; Linux x86_64; rv:150.0) Gecko/20100101 Firefox/150.0\r\nAccept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8\r\nAccept-Language: de,en-US;q=0.9,en;q=0.8\r\nAccept-Encoding: gzip, deflate, br, zstd\r\nSec-GPC: 1\r\nConnection: keep-alive\r\nUpgrade-Insecure-Requests: 1\r\nSec-Fetch-Dest: document\r\nSec-Fetch-Mode: navigate\r\nSec-Fetch-Site: none\r\nSec-Fetch-User: ?1\r\nPriority: u=0, i\r\nPragma: no-cache\r\nCache-Control: no-cache\r\n\r\n'
32906
ConnectionResetError
IncompleteReadError
b'HTTP/1.1 200 OK\r\nAccess-Control-Allow-Origin: *\r\nContent-Type: text/html; charset=utf-8\r\nContent-Length: 1733\r\nETag: W/"6c5-cVJ/Qf8zIIsFPYGT3VJD62eDmhQ"\r\nDate: Tue, 12 May 2026 22:09:20 GMT\r\nConnection: keep-alive\r\nKeep-Alive: timeout=5\r\n\r\n'
b'<!DOCTYPE html>\n<html>\n<head>\n<meta charset="utf-8">\n<meta http-equiv="X-UA-Compatible" content="IE=edge">\n<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=0">\n<meta name="apple-mobile-web-app-capable" content="yes">\n<meta name="mobile-web-app-capable" content="yes">\n<!--\n  Copyright OpenJS Foundation and other contributors, https://openjsf.org/\n\n  Licensed under the Apache License, Version 2.0 (the "License");\n  you may not use this file except in compliance with the License.\n  You may obtain a copy of the License at\n\n  http://www.apache.org/licenses/LICENSE-2.0\n\n  Unless required by applicable law or agreed to in writing, software\n  distributed under the License is distributed on an "AS IS" BASIS,\n  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.\n  See the License for the specific language governing permissions and\n  limitations under the License.\n-->\n<title>Node-RED</title>\n<link rel="icon" type="image/png" href="favicon.ico">\n<link rel="mask-icon" href="red/images/node-red-icon-black.svg" color="#8f0000">\n<link rel="stylesheet" href="vendor/jquery/css/base/jquery-ui.min.css?v=b6718ae767cf">\n<link rel="stylesheet" href="vendor/font-awesome/css/font-awesome.min.css?v=b6718ae767cf">\n<link rel="stylesheet" href="red/style.min.css?v=b6718ae767cf">\n<link rel="stylesheet" href="vendor/monaco/style.css?v=b6718ae767cf">\n</head>\n<body spellcheck="false">\n<div id="red-ui-editor"></div>\n<script src="vendor/vendor.js?v=b6718ae767cf"></script>\n<script src="vendor/monaco/monaco-bootstrap.js?v=b6718ae767cf"></script>\n<script src="red/red.min.js?v=b6718ae767cf"></script>\n<script src="red/main.min.js?v=b6718ae767cf"></script>\n\n\n</body>\n</html>\n'
```

If you take a closer look at the HTTP-Response you will see that there are multiple references to CSS and other files.
Those references will lead the Browser to open up multiple connections asking for those references.
However, as of now, each new Connection will lead to the creation of an entirely new Node-RED Docker-Container,
but we want that the seconds HTTP-Request from the same Browser reaches the already started Node-RED Docker-Container.

This brings us to the next step.

# Step 6: Identifying the Session

There are multiple ways to identify the session. I will simply reuse the UUID4, 
which I already create to make the data directory. 

Here is the plan:
1. Check the HTTP-Request for the UUID4 Cookie.
2. Check if a Container is running for this UUID4 Cookie, because it could be an *expired* Cookie.
3. If a Container is running then simply connect to that and forward the HTTP-Request.
4. If no Container is running then simply create one and forward the HTTP-Request.
5. If no Container is running then inject the UUID4 Cookie `Set-Cookie: uuid4=<uuid4>` into Node-RED's HTTP-Response.

For Step 2 we need something, e.g. a dictionary, from where we can look up if a Session exists.
We will also define a Session dataclass (I like to think of them as structs from the C programming language),
in which we will save the container that belongs to a session.

Let's try and implement it:

> [!NOTE]
> I had to do some trial-and-error, fix bugs (some of them obvious), until I reached this final working version.

```python
# ./examples/step6_1.py
import asyncio
import docker
import uuid
import re
from asyncio import StreamReader, StreamWriter, IncompleteReadError
from dataclasses import dataclass
from docker.models.containers import Container
from pathlib import Path

@dataclass(slots=True)
class Session:
    container: Container

d = docker.from_env()
sessions = {}

async def forward(reader: StreamReader, writer: StreamWriter) -> None:
    while True:
        message = await reader.read(4096)
        if not message:
            break
        writer.write(message)
        await writer.drain()
    writer.close()
    await writer.wait_closed()

async def client_connected_cb(client_reader: StreamReader, client_writer: StreamWriter) -> None:
    # Try reading the UUID4 Cookie from the HTTP-Request
    http_header = await client_reader.readuntil(b'\r\n\r\n')
    print(http_header)

    uuid4 = re.search(rb'uuid4=([a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12})', http_header)
    uuid4 = uuid4.group(1).decode() if uuid4 else None
    print(uuid4)

    if uuid4 in sessions:
        port = sessions[uuid4].container.ports['1880/tcp'][0]['HostPort']
        container_reader, container_writer = await asyncio.open_connection('localhost', port)

        # Forward HTTP-Request: Client -> Container
        container_writer.write(http_header)
        await container_writer.drain()

        # Forward HTTP-Response: Container -> Client
        http_header = await container_reader.readuntil(b'\r\n\r\n')
        print(http_header)

        content_length = re.search(rb'Content-Length:\s*(\d+)', http_header, re.IGNORECASE)
        content_length = int(content_length.group(1)) if content_length else 0
        http_body = await container_reader.readexactly(content_length)
        print(http_body)

        client_writer.write(http_header + http_body)
        await client_writer.drain()

        # Client <-> Container
        await asyncio.gather(
            forward(client_reader, container_writer),
            forward(container_reader, client_writer)
        )
    else:
        # Docker-Container
        uuid4 = str(uuid.uuid4())
        path = Path(__file__).parent.parent.parent / 'data' / uuid4
        await asyncio.to_thread(path.mkdir)
        container = await asyncio.to_thread(
            d.containers.run,
            'nodered/node-red',
            detach=True,                                     # -d
            ports={'1880/tcp': 0},                           # -p 0:1880 (0 lets the kernel choose a free port)
            volumes={path: {'bind': '/data', 'mode': 'rw'}}  # -v ./docker/data:/data
        )
        sessions[uuid4] = Session(container)
        await asyncio.to_thread(container.reload)
        port = container.ports['1880/tcp'][0]['HostPort']
        print(port)

        # Forward
        while True:
            try:
                container_reader, container_writer = await asyncio.open_connection('localhost', port)
                container_writer.write(http_header)
                await container_writer.drain()

                http_header = await container_reader.readuntil(b'\r\n\r\n')
            except ConnectionResetError:
                print("ConnectionResetError")
                await asyncio.sleep(1)
                continue
            except IncompleteReadError:
                print("IncompleteReadError")
                await asyncio.sleep(1)
                continue
            break

        # Inject UUID4 Cookie inside Node-RED's HTTP-Response
        http_header = http_header.replace(b'\r\n\r\n', f"\r\nSet-Cookie: uuid4={uuid4}\r\n\r\n".encode(), 1)
        print(http_header)

        # Read HTTP-Body
        content_length = re.search(rb'Content-Length:\s*(\d+)', http_header, re.IGNORECASE)
        content_length = int(content_length.group(1)) if content_length else 0
        http_body = await container_reader.readexactly(content_length)
        print(http_body)

        # Forward HTTP-Response: Container -> Client
        client_writer.write(http_header + http_body)
        await client_writer.drain()

async def main():
    s = await asyncio.start_server(client_connected_cb, '0.0.0.0', 1453)
    async with s:
        await s.serve_forever()

asyncio.run(main())
```

## Step 6.1: Fixing Bugs

I sometimes have the issue that my Reverseproxy gets stuck and I have to manually refresh the page.
Other than that it seems to work. To find out the Bug I implemented logging. 
However, I cannot reproduce the Bug anymore.

```python
# ./examples/step6_2.py
import asyncio
import docker
import logging
import uuid
import re
from asyncio import StreamReader, StreamWriter, IncompleteReadError
from dataclasses import dataclass
from docker.models.containers import Container
from pathlib import Path

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    fmt="%(asctime)s.%(msecs)03d %(levelname)-7s %(name)-12s %(message)s",
    datefmt="%H:%M:%S"
)

file_handler = logging.FileHandler("step6_2.log")
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)

@dataclass(slots=True)
class Session:
    container: Container

d = docker.from_env()
sessions = {}

async def forward(reader: StreamReader, writer: StreamWriter) -> None:
    while True:
        message = await reader.read(4096)
        if not message:
            break
        writer.write(message)
        await writer.drain()
    writer.close()
    await writer.wait_closed()

async def client_connected_cb(client_reader: StreamReader, client_writer: StreamWriter) -> None:
    # Try reading the UUID4 Cookie from the HTTP-Request
    http_header = await client_reader.readuntil(b'\r\n\r\n')
    logger.debug(f"HTTP-Request Header: {http_header}")

    uuid4 = re.search(rb'uuid4=([a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12})', http_header)
    uuid4 = uuid4.group(1).decode() if uuid4 else None
    logger.debug(f"UUID4: {uuid4}")

    if uuid4 in sessions:
        port = sessions[uuid4].container.ports['1880/tcp'][0]['HostPort']
        container_reader, container_writer = await asyncio.open_connection('localhost', port)

        # Forward HTTP-Request: Client -> Container
        container_writer.write(http_header)
        await container_writer.drain()

        # Forward HTTP-Response: Container -> Client
        http_header = await container_reader.readuntil(b'\r\n\r\n')
        logger.debug(f"HTTP-Response Header: {http_header}")

        content_length = re.search(rb'Content-Length:\s*(\d+)', http_header, re.IGNORECASE)
        content_length = int(content_length.group(1)) if content_length else 0
        http_body = await container_reader.readexactly(content_length)
        logger.debug(f"HTTP-Response Body: {http_body}")

        client_writer.write(http_header + http_body)
        await client_writer.drain()

        # Client <-> Container
        await asyncio.gather(
            forward(client_reader, container_writer),
            forward(container_reader, client_writer)
        )
    else:
        # Docker-Container
        uuid4 = str(uuid.uuid4())
        logger.debug(f"UUID4: {uuid4}")
        path = Path(__file__).parent.parent.parent / 'data' / uuid4
        await asyncio.to_thread(path.mkdir)
        container = await asyncio.to_thread(
            d.containers.run,
            'nodered/node-red',
            detach=True,                                     # -d
            ports={'1880/tcp': 0},                           # -p 0:1880 (0 lets the kernel choose a free port)
            volumes={path: {'bind': '/data', 'mode': 'rw'}}  # -v ./docker/data:/data
        )
        sessions[uuid4] = Session(container)
        await asyncio.to_thread(container.reload)
        port = container.ports['1880/tcp'][0]['HostPort']
        logger.debug(f"Port: {port}")

        # Forward
        while True:
            try:
                container_reader, container_writer = await asyncio.open_connection('localhost', port)
                container_writer.write(http_header)
                await container_writer.drain()

                http_header = await container_reader.readuntil(b'\r\n\r\n')
            except ConnectionResetError as e:
                logger.error(f"ConnectionResetError: {e}")
                await asyncio.sleep(3)
                continue
            except IncompleteReadError as e:
                logger.error(f"IncompleteReadError: {e}")
                await asyncio.sleep(3)
                continue
            break

        # Inject UUID4 Cookie inside Node-RED's HTTP-Response
        http_header = http_header.replace(b'\r\n\r\n', f"\r\nSet-Cookie: uuid4={uuid4}\r\n\r\n".encode(), 1)
        logger.debug(f"HTTP-Response Header: {http_header}")

        # Read HTTP-Body
        content_length = re.search(rb'Content-Length:\s*(\d+)', http_header, re.IGNORECASE)
        content_length = int(content_length.group(1)) if content_length else 0
        http_body = await container_reader.readexactly(content_length)
        logger.debug(f"HTTP-Response Body: {http_body}")

        # Forward HTTP-Response: Container -> Client
        client_writer.write(http_header + http_body)
        await client_writer.drain()

async def main():
    s = await asyncio.start_server(client_connected_cb, '0.0.0.0', 1453)
    async with s:
        await s.serve_forever()

asyncio.run(main(), debug=True)
```

# Step 7: Automatic Cleanup

So far I always manually removed the created data directories and Docker-Container whenever I stopped the Reverseproxy.

Let's try and automate this. 
For this we will have to extend the Session class by another attribute `path` in order to be able to delete the directories as well.

```python
# ./examples/step7_1.py
import asyncio
import docker
import logging
import uuid
import re
import shutil
import signal
import sys
from asyncio import StreamReader, StreamWriter, IncompleteReadError
from dataclasses import dataclass
from docker.models.containers import Container
from pathlib import Path
from signal import SIGINT

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    fmt="%(asctime)s.%(msecs)03d %(levelname)-7s %(name)-12s %(message)s",
    datefmt="%H:%M:%S"
)

file_handler = logging.FileHandler("step7_1.log")
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)

@dataclass(slots=True)
class Session:
    container: Container
    path: Path  # Needed for cleanup

d = docker.from_env()
sessions = {}

def graceful_shutdown(signum, frame):
    logger.info(f"Signal: {signum}, Frame: {frame}")
    for session in sessions.values():
        logger.debug(f"Stop and Remove Docker-Container: {session.container}")
        session.container.stop()
        session.container.remove()
        shutil.rmtree(session.path)
    sys.exit(0)

async def forward(reader: StreamReader, writer: StreamWriter) -> None:
    while True:
        message = await reader.read(4096)
        logger.debug(f"Forward: {message}")
        if not message:
            break
        writer.write(message)
        await writer.drain()
    writer.close()
    await writer.wait_closed()

async def client_connected_cb(client_reader: StreamReader, client_writer: StreamWriter) -> None:
    # Try reading the UUID4 Cookie from the HTTP-Request
    http_header = await client_reader.readuntil(b'\r\n\r\n')
    logger.info(f"HTTP-Request Header: {http_header}")

    uuid4 = re.search(rb'uuid4=([a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12})', http_header)
    uuid4 = uuid4.group(1).decode() if uuid4 else None
    logger.info(f"UUID4: {uuid4}")

    if uuid4 in sessions:
        port = sessions[uuid4].container.ports['1880/tcp'][0]['HostPort']
        container_reader, container_writer = await asyncio.open_connection('localhost', port)

        # Forward HTTP-Request: Client -> Container
        container_writer.write(http_header)
        await container_writer.drain()

        # Forward HTTP-Response: Container -> Client
        http_header = await container_reader.readuntil(b'\r\n\r\n')
        logger.info(f"HTTP-Response Header: {http_header}")

        content_length = re.search(rb'Content-Length:\s*(\d+)', http_header, re.IGNORECASE)
        content_length = int(content_length.group(1)) if content_length else 0
        http_body = await container_reader.readexactly(content_length)
        logger.info(f"HTTP-Response Body: {http_body}")

        client_writer.write(http_header + http_body)
        await client_writer.drain()

        # Client <-> Container
        await asyncio.gather(
            forward(client_reader, container_writer),
            forward(container_reader, client_writer)
        )
    else:
        # Docker-Container
        uuid4 = str(uuid.uuid4())
        logger.info(f"UUID4: {uuid4}")
        path = Path(__file__).parent.parent.parent / 'data' / uuid4
        await asyncio.to_thread(path.mkdir)
        container = await asyncio.to_thread(
            d.containers.run,
            'nodered/node-red',
            detach=True,                                     # -d
            ports={'1880/tcp': 0},                           # -p 0:1880 (0 lets the kernel choose a free port)
            volumes={path: {'bind': '/data', 'mode': 'rw'}}  # -v ./docker/data:/data
        )
        sessions[uuid4] = Session(container, path)
        await asyncio.to_thread(container.reload)
        port = container.ports['1880/tcp'][0]['HostPort']
        logger.info(f"Port: {port}")

        # Forward
        while True:
            try:
                container_reader, container_writer = await asyncio.open_connection('localhost', port)
                container_writer.write(http_header)
                await container_writer.drain()

                http_header = await container_reader.readuntil(b'\r\n\r\n')
            except ConnectionResetError as e:
                logger.error(f"ConnectionResetError: {e}")
                await asyncio.sleep(3)
                continue
            except IncompleteReadError as e:
                logger.error(f"IncompleteReadError: {e}")
                await asyncio.sleep(3)
                continue
            break

        # Inject UUID4 Cookie inside Node-RED's HTTP-Response
        http_header = http_header.replace(b'\r\n\r\n', f"\r\nSet-Cookie: uuid4={uuid4}\r\n\r\n".encode(), 1)
        logger.info(f"HTTP-Response Header: {http_header}")

        # Read HTTP-Body
        content_length = re.search(rb'Content-Length:\s*(\d+)', http_header, re.IGNORECASE)
        content_length = int(content_length.group(1)) if content_length else 0
        http_body = await container_reader.readexactly(content_length)
        logger.info(f"HTTP-Response Body: {http_body}")

        # Forward HTTP-Response: Container -> Client
        client_writer.write(http_header + http_body)
        await client_writer.drain()

async def main():
    signal.signal(SIGINT, graceful_shutdown)
    s = await asyncio.start_server(client_connected_cb, '0.0.0.0', 1453)
    async with s:
        await s.serve_forever()

asyncio.run(main(), debug=True)
```

## Step 7.1: Removing abandoned Containers

How do we identify the Containers that have been *abandoned* by their Clients? After all, 
these Containers just take RAM and processing power which could be used for other cases.

If you start the latest Code snippet above and connect to the socket via a Browser and let it run for a while without doing anything,
you will notice the following repeating output:

```
09:00:01.723 DEBUG   __main__     Forward: b'\x81%[{"topic":"hb","data":1778655586671}]'
```

This is the so called [WebSocket Heartbeat](https://websocket.org/guides/heartbeat/). On my end, 
it gets send about every 15 seconds. If I close the Tab, then I observe the following output:

```
09:08:51.523 DEBUG   __main__     Forward: b'\x88\x82e\xb9u\xc3fP'
09:08:51.525 DEBUG   __main__     Forward: b'\x88\x02\x03\xe9'
```

Those are the so called [WebSocket Closing-Frames](https://websocket.org/reference/close-codes/) and the heartbeat also stops as soon as the Tab is closed.

That means, I can make use of the heartbeat to determine *abandoned* Containers and remove them. 
For that I will extend the Session class by another attribute called `last_seen`.

Here is my solution:

```python
# ./examples/step7_2.py
import asyncio
import docker
import logging
import uuid
import re
import shutil
import signal
import sys
import time
from asyncio import StreamReader, StreamWriter, IncompleteReadError
from dataclasses import dataclass
from docker.models.containers import Container
from pathlib import Path
from signal import SIGINT

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    fmt="%(asctime)s.%(msecs)03d %(levelname)-7s %(name)-12s %(message)s",
    datefmt="%H:%M:%S"
)

file_handler = logging.FileHandler("step7_2.log")
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)

@dataclass(slots=True)
class Session:
    container: Container
    path: Path
    last_seen: float

d = docker.from_env()
sessions = {}

def graceful_shutdown(signum, frame):
    logger.info(f"Signal: {signum}, Frame: {frame}")
    for session in sessions.values():
        logger.info(f"Stop and Remove Docker-Container: {session.container}")
        session.container.stop()
        session.container.remove()
        shutil.rmtree(session.path)
    sys.exit(0)

async def poll_sessions():
    while True:
        logger.info('Checking for expired sessions')

        # A *too tight* window leads to the deletion of the container before it can be even used
        for uuid4, session in list(sessions.items()):
            elapsed_time = time.time() - session.last_seen
            logger.info(f"Elapsed Time: {elapsed_time} seconds for {session}")
            if elapsed_time > 60:
                logger.info(f"This session is expired and will be deleted now.")
                await asyncio.to_thread(shutil.rmtree, session.path, ignore_errors=False, onerror=None)
                await asyncio.to_thread(session.container.stop)
                await asyncio.to_thread(session.container.remove)
                del sessions[uuid4]
        await asyncio.sleep(60)

async def client_connected_cb(client_reader: StreamReader, client_writer: StreamWriter) -> None:
    # Try reading the UUID4 Cookie from the HTTP-Request
    http_header = await client_reader.readuntil(b'\r\n\r\n')
    logger.info(f"HTTP-Request Header: {http_header}")

    uuid4 = re.search(rb'uuid4=([a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12})', http_header)
    uuid4 = uuid4.group(1).decode() if uuid4 else None
    logger.info(f"UUID4: {uuid4}")

    session = sessions.get(uuid4)
    if session:
        port = sessions[uuid4].container.ports['1880/tcp'][0]['HostPort']
        container_reader, container_writer = await asyncio.open_connection('localhost', port)

        # Forward HTTP-Request: Client -> Container
        container_writer.write(http_header)
        await container_writer.drain()

        # Forward HTTP-Response: Container -> Client
        http_header = await container_reader.readuntil(b'\r\n\r\n')
        logger.info(f"HTTP-Response Header: {http_header}")

        content_length = re.search(rb'Content-Length:\s*(\d+)', http_header, re.IGNORECASE)
        content_length = int(content_length.group(1)) if content_length else 0
        http_body = await container_reader.readexactly(content_length)
        logger.info(f"HTTP-Response Body: {http_body}")

        client_writer.write(http_header + http_body)
        await client_writer.drain()

        # Client <-> Container
        async def forward(reader: StreamReader, writer: StreamWriter) -> None:
            while True:
                session.last_seen = time.time()
                message = await reader.read(4096)
                logger.debug(f"Forward: {message}")
                if not message:
                    break
                writer.write(message)
                await writer.drain()
            writer.close()
            await writer.wait_closed()
        await asyncio.gather(
            forward(client_reader, container_writer),
            forward(container_reader, client_writer)
        )
    else:
        # Docker-Container
        uuid4 = str(uuid.uuid4())
        logger.info(f"UUID4: {uuid4}")
        path = Path(__file__).parent.parent.parent / 'data' / uuid4
        await asyncio.to_thread(path.mkdir)
        container = await asyncio.to_thread(
            d.containers.run,
            'nodered/node-red',
            detach=True,                                     # -d
            ports={'1880/tcp': 0},                           # -p 0:1880 (0 lets the kernel choose a free port)
            volumes={path: {'bind': '/data', 'mode': 'rw'}}  # -v ./docker/data:/data
        )
        sessions[uuid4] = Session(container, path, time.time())
        await asyncio.to_thread(container.reload)
        port = container.ports['1880/tcp'][0]['HostPort']
        logger.info(f"Port: {port}")

        # Forward
        while True:
            try:
                container_reader, container_writer = await asyncio.open_connection('localhost', port)
                container_writer.write(http_header)
                await container_writer.drain()

                http_header = await container_reader.readuntil(b'\r\n\r\n')
            except ConnectionResetError as e:
                logger.error(f"ConnectionResetError: {e}")
                await asyncio.sleep(3)
                continue
            except IncompleteReadError as e:
                logger.error(f"IncompleteReadError: {e}")
                await asyncio.sleep(3)
                continue
            break

        # Inject UUID4 Cookie inside Node-RED's HTTP-Response
        http_header = http_header.replace(b'\r\n\r\n', f"\r\nSet-Cookie: uuid4={uuid4}\r\n\r\n".encode(), 1)
        logger.info(f"HTTP-Response Header: {http_header}")

        # Read HTTP-Body
        content_length = re.search(rb'Content-Length:\s*(\d+)', http_header, re.IGNORECASE)
        content_length = int(content_length.group(1)) if content_length else 0
        http_body = await container_reader.readexactly(content_length)
        logger.info(f"HTTP-Response Body: {http_body}")

        # Forward HTTP-Response: Container -> Client
        client_writer.write(http_header + http_body)
        await client_writer.drain()

async def main():
    signal.signal(SIGINT, graceful_shutdown)
    s = await asyncio.start_server(client_connected_cb, '0.0.0.0', 1453)
    async with s:
        await asyncio.gather(s.serve_forever(), poll_sessions())

asyncio.run(main(), debug=True)
```

<!--
# Step 7: Saving server disk space

# Step 8: Reverseproxy (we finally did it!)

# Step 9: Accessories
-->

# YouTube video explaining Python's AsyncIO

The picture is a link to the actual YouTube video:

[![AsyncIO Python](https://img.youtube.com/vi/oAkLSJNr5zY/0.jpg)](https://youtu.be/oAkLSJNr5zY?si=ES2S-NLZ0Um8hd7F)