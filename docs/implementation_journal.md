# What is this file about?

In this file, I will try to go step-by-step through the thought processes, 
reasoning and learning that went into this project. I will try to not get lost in details, 
but I also will try to not make it too basic. It is going to be difficult to find a good balance, 
but I hope you can bear with me or suggest improvements. Thank you, very much!

# Step 1: IPC (Inter-Process-Communication)

![2 Clients <-> Reverseproxy <-> 2 Containers](./pics/2clients-rp-2containers.png)

In order to accomplish what is depicted in the above image, we, first of all, 
need to figure out a way for a Client to communicate with our Reverseproxy program. 
The Client is supposed to connect to this Reverseproxy by opening up his favorite Browser (e.g. Firefox), 
typing in the URL and hitting Enter.

At the end of the day, this Reverseproxy is nothing but a process and the Browser is nothing but a process. 
Both processes are supposed to communicate with each other through the internet. 
The immediate method to accomplish this seems to be by using *Sockets*. 
Our Reverseproxy will listen on a socket and each Client (Browser process) can connect to that socket.

To accomplish this, we will define the socket with the Socket-Type `SOCK_STREAM` (basically TCP) and the Address-Family `AF_INET` (basically IPv4).
Let's write it:

```python
# ./examples/step1_1.py
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

The above Code implements a socket that binds itself on all IPv4 addresses that are available to your device (`0.0.0.0`).

> [!NOTE]
> You can see the IPv4 addresses that are available to your device by opening up a terminal and typing in the command `ip addr`.

> [!NOTE]
> The address `127.0.0.1` or `localhost` is the loopback address. 
> Besides that address, if you are connected to a WLAN, you might also see an address like `192.168.170.23`.
> Everyone in the same WLAN can basically address your device with that IP.

Now, let's run the above Code and then type in a Browser the URL `localhost:1453`. 
The output will look something like this.

```
Binding socket
Waiting for a connection
Connected by ('127.0.0.1', 60934)

Process finished with exit code 0
```

Let's try and see if the Browser sends any message upon connecting. 


```python
# ./examples/step1_2.py
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

The output will look something like this:

```
Binding socket
Waiting for a connection
Connected by ('127.0.0.1', 46232)
b'GET / HTTP/1.1\r\nHost: localhost:1453\r\nUser-Agent: Mozilla/5.0 (X11; Linux x86_64; rv:150.0) Gecko/20100101 Firefox/150.0\r\nAccept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8\r\nAccept-Language: de,en-US;q=0.9,en;q=0.8\r\nAccept-Encoding: gzip, deflate, br, zstd\r\nSec-GPC: 1\r\nConnection: keep-alive\r\nUpgrade-Insecure-Requests: 1\r\nSec-Fetch-Dest: document\r\nSec-Fetch-Mode: navigate\r\nSec-Fetch-Site: none\r\nSec-Fetch-User: ?1\r\nPriority: u=0, i\r\n\r\n'
```

> [!NOTE]
> As far as I am aware, there doesn't seem to be any function like `read_entire_message()`.
> That's why we have to use the `recv()` function. We loop over it and read an arbritrary amount of bytes.

Before we proceed, **let's realize what we are seeing here**. Whenever you call a website in your Browser, 
your Browser automatically sends a so called HTTP-Request (just like in the above output) to that *website*.
Each *website* is programmed in such a way that it can understand the above HTTP-Request and reply accordingly.
The reply is called HTTP-Response. As of now, our Reverseproxy doesn't send any reply back.

> [!NOTE]
> A *website* is basically a program (written in whatever programming language) that listens on a socket, 
> processes the incoming HTTP-Requests and replies accordingly.

Once we click on `Stop loading Page` (in the Browser) we will get a bunch of `b''` in our output. 
This `b''` signals the end of connection. We can make use of it in our Code.

```python
# ./examples/step1_3.py
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

As you might have noticed, each line in the HTTP-Request is terminated by `\r\n`. 
This behavior is exactly defined in the RFC documents.
If you go on and research you will figure out that each HTTP-Request (and HTTP-Response) have the very same structure.

```
<HTTP-Header>
\r\n
<HTTP-Body>
```

The HTTP-Header (which we see in the above output) is separated from the HTTP-Body by an empty newline, 
thus the `\r\n\r\n` at the end of the HTTP-Header in the output above.

The `HTTP-Header` can consist of multiple headers such as `Host:`, `User-Agent:`, `Accept:` etc.
There is also the infamous `Cookie:` header (not shown in the above output). 
Cookies are set by the website you are visiting. 
Upon receiving your HTTP-Request some websites send a header field such as `Set-Cookie: name=value\r\n` in their HTTP-Response.
Upon receiving this HTTP-Response, 
your Browser automatically saves this Cookie and sends it whenever you call the same website.

# Step 2: Handling more than one Client at the same time

As of now, the above Code can only handle exactly one Connection.
We could simply wrap `s.accept()` inside a `ẁhile True:` loop to handle more than one Connection (simply speaking each Connection could be a Client). 

```python
# ./examples/step2_1.py
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
As one Client is being processed all the other Clients will have to wait.

We don't want Clients to have to wait on other Clients. Each Client should be processed *in parallel*.
Thankfully, in Python, there are multiple ways to handle more than one Client *at the same time*, 
e.g. `multithreading` or `multiprocessing`. However, I decided to go with `asyncio`. 

> [!NOTE]
> Python's `multiprocessing` is basically `multithreading` except each Thread gets its own entire Python Interpreter,
> thus creating way more overhead.

> [!NOTE]
> I have linked a YouTube video at the end of this document for anyone who wants to develop a better understanding of Python's `asyncio` module.

Let's rewrite the above example with the `asyncio` module.

```python
# ./examples/step2_2.py
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
with the `StreamReader` object you can read whatever the Client sends on that connection.
With the `StreamWriter` object you can reply to the Client.

> [!NOTE]
> The `StreamReader` object provides us with more comfortable high-level functions such as `readuntil()` or `readexactly()`, 
> which we will make use of.

# Step 3: Spawning a Node-RED Docker-Container when a Client connects

<!--
# Step 4: Reverseproxy (for only one client)

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