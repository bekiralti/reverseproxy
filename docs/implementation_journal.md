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
> Make sure to have the `docker` module installed in Python virtual environment.

> [!NOTE]
> The `àsyncio` module helps in IO-Bound operations. Thus, I will try to make every IO-Bound operation async.

For the (Node-RED) Docker-Container we will need a data directory.

```python
# ./examples/step4_1.py
import asyncio
import docker
import uuid
from asyncio import StreamReader, StreamWriter
from pathlib import Path

d = docker.from_env()

async def client_connected_cb(reader: StreamReader, writer: StreamWriter) -> None:
    path = Path(__file__).parent.parent / 'data' / uuid.uuid4().hex
    await asyncio.to_thread(path.mkdir)

async def main():
    s = await asyncio.start_server(client_connected_cb, '0.0.0.0', 1453)
    async with s:
        await s.serve_forever()

asyncio.run(main())
```

Now, we will create the Docker-Container. 
We will let the Kernel choose a free port on which we will speak to the Docker-Container.

```python
# ./examples/step4_2.py
import asyncio
import docker
import uuid
from asyncio import StreamReader, StreamWriter
from pathlib import Path

d = docker.from_env()

async def client_connected_cb(reader: StreamReader, writer: StreamWriter) -> None:
    path = Path(__file__).parent.parent / 'data' / uuid.uuid4().hex
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

Let's try to get the port number. 
The `reload()` method is used to fetch the latest information of the container.

> [!NOTE]
> I will also add a `await asyncio.sleep(1)` to not unnecessarily let the CPU work in 100 %.

```python
# ./examples/step4_3.py
import asyncio
import docker
import uuid
from asyncio import StreamReader, StreamWriter
from pathlib import Path

d = docker.from_env()

async def client_connected_cb(reader: StreamReader, writer: StreamWriter) -> None:
    path = Path(__file__).parent.parent / 'data' / uuid.uuid4().hex
    await asyncio.to_thread(path.mkdir)
    container = await asyncio.to_thread(
        d.containers.run,
        'nodered/node-red',
        detach=True,                                     # -d
        ports={'1880/tcp': 0},                           # -p 0:1880 (0 lets the kernel choose a free port)
        volumes={path: {'bind': '/data', 'mode': 'rw'}}  # -v ./docker/data:/data
    )
    while True:
        await asyncio.to_thread(container.reload)
        print(container.status)
        print(container.ports)
        port = container.ports['1880/tcp'][0]['HostPort']
        print(port)
        await asyncio.sleep(1)

async def main():
    s = await asyncio.start_server(client_connected_cb, '0.0.0.0', 1453)
    async with s:
        await s.serve_forever()

asyncio.run(main())
```

If it works, you should see something like:

```
running
{'1880/tcp': [{'HostIp': '0.0.0.0', 'HostPort': '32798'}, {'HostIp': '::', 'HostPort': '32798'}]}
32798
```

If it doesn't work, then make sure to give the Docker-Container more time to start, e.g.:

```python
# ./examples/step4_4.py
import asyncio
import docker
import uuid
from asyncio import StreamReader, StreamWriter
from pathlib import Path

d = docker.from_env()

async def client_connected_cb(reader: StreamReader, writer: StreamWriter) -> None:
    path = Path(__file__).parent.parent.parent / 'data' / uuid.uuid4().hex
    await asyncio.to_thread(path.mkdir)
    container = await asyncio.to_thread(
        d.containers.run,
        'nodered/node-red',
        detach=True,                                     # -d
        ports={'1880/tcp': 0},                           # -p 0:1880 (0 lets the kernel choose a free port)
        volumes={path: {'bind': '/data', 'mode': 'rw'}}  # -v ./docker/data:/data
    )
    while True:
        await asyncio.sleep(30)
        await asyncio.to_thread(container.reload)
        print(container.status)
        print(container.ports)
        port = container.ports['1880/tcp'][0]['HostPort']
        print(port)
        await asyncio.sleep(1)

async def main():
    s = await asyncio.start_server(client_connected_cb, '0.0.0.0', 1453)
    async with s:
        await s.serve_forever()

asyncio.run(main())
```

> [!NOTE]
> You can stop and remove all the Docker-Containers by typing `docker stop $(docker ps -qa)` and `docker rm $(docker ps -qa)` in your terminal.

> [!NOTE]
> After you are done with your experiments, 
> make sure to delete all the directories that have been created in `reverseproxy/data/`.

# Step 4: Forwarding

We are almost there to have finally created the Reverseproxy. We just need to forward the messages from:

- Client to Container,
- Container to Client.

For that, 
we can define a function `forward(reader, writer)` and call it once with the Client-Reader and Container-Writer and once with the Container-Reader and Client-Writer objects.
First, we need to get the Container-Writer and Container-Reader objects by simply connecting to the Container.

Let's try it all in one go.

> ![NOTE]
> Before we run the next program, let's clean up the directories in the `reverseproxy/data` path and the Docker-Containers (`docker stop $(docker ps -qa) && docker rm $(docker ps -qa)`).

```python
# ./examples/step5_1.py
import asyncio
import docker
import uuid
from asyncio import StreamReader, StreamWriter
from pathlib import Path

d = docker.from_env()

async def forward(reader, writer):
    while True:
        message = await reader.read(4096)
        print(message)
        if not message:
            break
        writer.write(message)
        await writer.drain()
    writer.close()
    await writer.wait_closed()

async def client_connected_cb(client_reader: StreamReader, client_writer: StreamWriter) -> None:
    path = Path(__file__).parent.parent.parent / 'data' / uuid.uuid4().hex
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
    container_reader, container_writer = await asyncio.open_connection('localhost', port)
    await asyncio.gather(
        forward(client_reader, container_writer),
        forward(container_reader, client_writer)
    )

async def main():
    s = await asyncio.start_server(client_connected_cb, '0.0.0.0', 1453)
    async with s:
        await s.serve_forever()

asyncio.run(main())
```

> [!NOTE]
> In case the Docker-Container needs time to properly start-up add something like `await asyncio.sleep(10)` before you call the `reload()` method on the Container.

I do get a `ConnectionResetError`. Let's see if it works when I wait a little bit for the Docker-Container.

# Step 5: Parsing the HTTP-Request and identifying the Browser

<!--
# Step 5: Making sure that one client doesn't spawn *infinite* Docker-Containers

# Step 5.1: A rather exotic issue: Malicious client

# Step 6: Reverseproxy (for multiple clients)

# Step 7: Saving server disk space

# Step 8: Reverseproxy (we finally did it!)

# Step 9: Accessories
-->

# YouTube video explaining Python's AsyncIO

The picture is a link to the actual YouTube video:

[![AsyncIO Python](https://img.youtube.com/vi/oAkLSJNr5zY/0.jpg)](https://youtu.be/oAkLSJNr5zY?si=ES2S-NLZ0Um8hd7F)