# What is this file about?

In this file, I will try to go step-by-step through the thought processes, 
reasoning and learning that went into this project. I don't want to make this too detailed, 
but I also don't want to make it too basic. It is going to be difficult to find a good balance, 
but I hope you can bear with me or suggest improvements. Thank you, very much!

# Step 1: IPC (Inter-Process-Communication)

At the end of the day, 

![2 Clients <-> Reverseproxy <-> 2 Containers](./pics/2clients-rp-2containers.png)

I want that a person is able to connect to this Reverseproxy by typing in the URL and hitting Enter in his Browser.
Since this Reverseproxy is nothing but a process and the Browser is nothing but a process the immediately answer that comes to my mind is: *Sockets*!

Sockets allow two processes to talk with each other. 
In this case the benefit of Sockets is that they also support IPC over internet.
Most of the time you just have to define the Socket-Type (e.g. `SOCK_STREAM` for TCP) and Adress-Family (e.g. `AF_INET` for IPv4).

Let's write a simple socket.

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

The above Code implements a socket that binds itself on all IPv4 addresses that are available to your device.
One way to figure out which addresses are available you can open up a terminal and type in the command `ip addr`.
Let's run the above Code and then type in a Browser the URL `localhost:1453`. The output will look something like this:

```
Binding socket
Waiting for a connection
Connected by ('127.0.0.1', 60934)

Process finished with exit code 0
```

Let's try and see if the Browser sends any message upon connecting. 
Since there doesn't seem to be any function like `read_entire_message()`, 
we will have to use the `recv()` function and constantly read a specific amount of bytes.

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
            message = conn.recv(512)
            print(message)
```

The output will look something like this:

```
Binding socket
Waiting for a connection
Connected by ('127.0.0.1', 46232)
b'GET / HTTP/1.1\r\nHost: localhost:1453\r\nUser-Agent: Mozilla/5.0 (X11; Linux x86_64; rv:150.0) Gecko/20100101 Firefox/150.0\r\nAccept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8\r\nAccept-Language: de,en-US;q=0.9,en;q=0.8\r\nAccept-Encoding: gzip, deflate, br, zstd\r\nSec-GPC: 1\r\nConnection: keep-alive\r\nUpgrade-Insecure-Requests: 1\r\nSec-Fetch-Dest: document\r\nSec-Fetch-Mode: navigate\r\nSec-Fetch-Site: none\r\nSec-Fetch-User: ?1\r\nPriority: u=0, i\r\n\r\n'
```

Before we proceed, let's realize what we are seeing here. Whenever you call a website in your Browser, 
your Browser automatically sends a so called HTTP-Request (just like in the above output) to that website.
Each website is programmed in such a way that it can understand the above HTTP-Request and reply accordingly.
The reply is called HTTP-Response.

> [!NOTE]
> A website is basically a program (written in whatever programming language) that listens on a socket, 
> processes the incoming HTTP-Requests and replies.

Once you click on `Stop loading Page` inside your Browser you will get a bunch of `b''` in your output. 
This `b''` signals the end of connection.

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
            message = conn.recv(512)
            print(message)
            if not message:
                break
```

As you might have noticed, each line in the HTTP-Request ist terminated by `\r\n`. 
This behavior is exactly defined in the RFC documents.
If you go on and research you will figure out that each HTTP-Request (and HTTP-Response) have the very same structure.

```
<HTTP-Header>
\r\n
<HTTP-Body>
```

The HTTP-Header (which we see in the above output) is separated from the HTTP-Body by an empty newline, 
thus the double `\r\n\r\n` at the end of the HTTP-Header. On the very first HTTP-Request there is no HTTP-Body.

As you saw in the above output the `HTTP-Header` can consist of multiple headers such as `Host:`, `User-Agent:`, `Accept:` etc.
There is also the infamous `Cookies:` header (not shown in the above output). 
We will get to this soon however the Cookies are set by the website you are visiting. 
Upon receiving your HTTP-Request some websites send a header field such as `Set-Cookie: name=value\r\n` in their HTTP-Response.
Upon receiving this, your Browser automatically saves this Cookie and sends it whenever you call the same website.

# Step 2: Handling more than one Client at the same time

As of now, the above Code can only handle exactly one Client. 
We could simply wrap `s.accept()` inside a `ẁhile True:` loop to handle more than one Clients however we will only be able to handle each Client sequentially.
If two or more Clients connect at the same time they will have to wait on each other to get an HTTP-Response from the server.

We do want to handle each Client rather *simultaneously*. 
There are multiple ways to accomplish this (e.g. `multithreading`, `multiprocessing` etc.). 
We are going to use `asyncio` for this.

<!--
# Step 3: Spawning a Node-RED Docker-Container when one client connects

# Step 4: Reverseproxy (for only one client)

# Step 5: Making sure that one client doesn't spawn *infinite* Docker-Containers

# Step 5.1: A rather exotic issue: Malicious client

# Step 6: Reverseproxy (for multiple clients)

# Step 7: Saving server disk space

# Step 8: Reverseproxy (we finally did it!)

# Step 9: Accessories
-->