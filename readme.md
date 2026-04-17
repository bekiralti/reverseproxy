**TODO: REFACTOR THIS!**

# Description (What is this about?)

This is a reverse-proxy. For each connecting client this reverse-proxy spawns a docker-container. 
In other words, each client gets his own docker-container.

**TODO: ADD A GIF EXPLAINING THIS**

**Start with a blue box in the middle with a name in it "Reverse-Proxy"**

**A Client, call it "Browser 1" or smth, pops up in an organ box to the left**

**An arrow connecting "Browser 1" to "Reverse-Proxy"**

**Docker-Container in a green Box, call it "Container 1", pops up to the right**

**Reverse-Proxy connects to "Container 1""**

**Mit gestrichelten Linien die vom "Browser 1" durch Reverse-Proxy zu "Container 1" durchgehende Verbindung zeigen**

**Noch ein zwei weitere Clients genau wie oben zeichnen**

## Requirements (What are my assumptions?)

Assumption is that the client connects to this reverse-proxy via a browser (e.g. Firefox).

**What does this mean in more technical terms?**

As of now the reverse-proxy can only accept TCP-Connections. For anyone interested, it is because I open the socket via this command:

```python
await asyncio.start_server(client_connected_cb, '0.0.0.0', 1024)
```

What does this mean? This means that the client needs to open a TCP-Connection if he wants to connect to this reverse-proxy. 

*TMI: For anyone familiar, that's the Data Link Layer (Layer 2) in the OSI-model.*

**Why HTTP?**

Since I assumed that clients will establish the connection via a Browser (e.g. Firefox) I could also assume that each client is somewhat cappable of speaking HTTP.
Upon successfully building a connection the Browser (e.g. Firefox) sends a so called HTTP-Request. It typically looks something like this:

```
GET / HTTP/1.1
Host: localhost:1024
User-Agent: Mozilla/5.0 (X11; Linux x86_64; rv:149.0) Gecko/20100101 Firefox/149.0
Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8
Accept-Language: de,en-US;q=0.9,en;q=0.8
Accept-Encoding: gzip, deflate, br, zstd
Connection: keep-alive
Upgrade-Insecure-Requests: 1
Sec-Fetch-Dest: document
Sec-Fetch-Mode: navigate
Sec-Fetch-Site: none
Sec-Fetch-User: ?1
Priority: u=0, 

```

Here comes the issue. A Browser (e.g. Firefox) usually opens mutliple TCP-Connections (e.g. to retrieve the favicon image, CSS files, Javascript files ... you name it).
You can probably already tell it. We have to avoid firing up a Docker-Container for each TCP-Connection. 
We somehow need an identifier to tell if a TCP-Connection comes from the same client or if it is a new client.
I decided to simply use a UUID (specifically Version 4) and tell the Browser to set it as a Cookie.

```
Set-Cookie: uuid=<uuid4>
```

You can replace `<uuid4>` with an actual UUID (Version 4) value, e.g. `cb6a8e94-e474-4d9b-9a4f-9b020552bae3`. 
The value in itself is not important, it is important that UUID (Version 4) has about 2^122 possibilities.
Practically, it is quite unlikely that two UUIDs (Version 4) will have the exact same value. 
Thus, at least for now, we do not need to implement a check for a UUID collision.

This is pretty much the most important part. The client NEEDS TO be able to handle `Set-Cookie: uuid=<uuid4>`. 
For example, instead of using a browser (like Firefox) you could simply write your own program (in C or Python or any language of your choice) and connect to this reverse-proxy.
You can also write a bash script (I'm thinking of using the program `curl`). 
The *only* thing you need to do is to read the `<uuid4>` value and retransmit it on reconnection in the form of:

```
Cookie: uuid=<uuid4>
```

The docker-container can be whatever you want. I used a Node-RED Docker-Container for testing purposes. 
Node-RED speaks HTTP and asks the Browser (here via reverse-proxy) to upgrade the Connection to a so called Websocket.

**What is a Websocket?**

If you are like me, you might be now wondering what on earth a Websocket is. TCP, HTTP and now Websocket?! 
Thankfully, it is rather straightforward. Normally, an HTTP Connection goes like this:

```
Client sends a so called HTTP-Request -> Server replies with a so called HTTP-Response
```

Whether it is an HTTP-Request or an HTTP-Response the structure is always the same. 
HTTP consists of a so called Request part and an optional Body part.

```
HTTP-Request

[HTTP-Body]
```

Per definition (RFC **TODO: Number**) there is always a blank line after the HTTP-Request. 
That is why when we parse the Browser-Request we read until `\r\n\r\n`. **TODO: Code Snippet**

The HTTP-Body can be blank or whatever you desire.

Since we assume that the client connects to this reverse-proxy via a browser (like Firefox) it would be inconvenient if the client has to press refresh himself (because we set the UUID Cookie first and require the client to connect again with the assigned UUID).
Thankfully, there is also a solution for this. You can tell the Browser in your HTTP-Response that it should automatically connect again after x seconds. **TODO: Code Snippet**

**TODO: ADVANCED TECHNICAL COMMENTARY ON THE RACING CONDITION**

# Language (Why are some of my Code comments german and some are english?)

Personally, I prefer to write in german however I got used to coding in english. If you take a look into the Source-Code you will notice that I have sometimes written my comments in english and sometimes in german. For this readme however I will try to stick to one language.