# What is this about?

This Reverseproxy spawns for any connecting client its own Docker-Container. 
The following video is supposed to show the basic way this Reverseproxy works.

https://github.com/user-attachments/assets/8e0c54d3-5700-47f5-aca5-c39d097d5054

Video description:
- Assume a Client (labeled Client 1) connects to the Reverseproxy (via a Browser such as Firefox).
- Upon calling a *website* the Browser automatically sends a so called HTTP-Request.
- The Reverseproxy receives the HTTP-Request and starts a Docker-Container (labeled Container 1).
- The Reverseproxy forwards the HTTP-Request to Container 1.
- Container 1 receives the HTTP-Request and replies with a so called HTTP-Response.
- The Reverseproxy receives the HTTP-Response.
- The Reverseproxy forwards the HTTP-Response to Client 1.
- Thus, the Reverseproxy has established a Connection between Client 1 and Container 1.
- Let's assume a second Client (labeled Client 2) connects to the Reverseproxy while Client 1 is still connected as well.
- The Reverseproxy spawns a second Docker-Container (labeled Container 2) for Client 2.
- Now, Client 2 and Container 2 speak with each other and Client 1 and Container 1 speak with each other through the Reverseproxy.
- If one of the Clients disconnects (e.g. Client 1), then the Reverseproxy also deletes the Container associated with that Client.

# How to install and run?

> [!TIP]
> As of now, I'm mainly using Arch Linux. Thus, adjust the steps in this guide to your OS if necessary.

First of all the **Requirements**:
- a terminal of your choice (e.g. `kitty`),
- `python`,
- `docker`.

> [!IMPORTANT]
> Make sure the docker daemon is running, e.g.: `sudo systemctl enable docker --now`.

> [!IMPORTANT]
> Add docker to your user group in order to execute docker commands without sudo, e.g.: `sudo useradd -aG docker $USER`.
> Reboot your machine or relogin to make this change effective.

Second of all, download this repository. One way is to type in your terminal the following command:

```shell
git clone https://github.com/bekiralti/reverseproxy.git
```

Then change into the directory:

```shell
cd reverseproxy
```

Then create a Python virtual environment (so that the additionally installed packages required by this Reverseproxy do not mess up your system Python installation):

```shell
python -m venv .venv
```

> [!NOTE]
> The `.venv` is the directory name, you can choose whatever name you want.

Then *activate* the venv:

```shell
source .venv/bin/activate
```

Then install this program:

```shell
pip install .
```

> [!NOTE]
> You can use `pip install -e .` instead if you want to change things in the Code and see its effects immediately without having to reinstall.

Then run this program:

```shell
python ./src/main.py
```

## Basic example

Once you run this program

```shell
python ./src/main.py
```

open up a Browser of your choice (e.g. Firefox) and type in `localhost:1071`. 
After a short while you should see a Node-RED Docker-Container loading up. 
To simulate a second Client you can open another Browser in incognito mode and type in `localhost:1071`.

## Basic usage / customization

Instead of the default Node-RED Docker-Container you can use any other Docker Image of your choice. 
You just have to change the Image Name in this part of the code

```python
docker_container = await asyncio.to_thread(
    docker_client.containers.run,
    'nodered/node-red',
    detach=cast(Literal[True], True),
    ports={'1880/tcp': 0},
    volumes={path: {'bind': '/data', 'mode': 'rw'}}
)
```

to the Docker Image you want to use

```python
docker_container = await asyncio.to_thread(
    docker_client.containers.run,
    'my-docker-image',
    detach=cast(Literal[True], True),
    ports={'1880/tcp': 0},
    volumes={path: {'bind': '/data', 'mode': 'rw'}}
)
```

> [!NOTE]
> One of the reasons for Node-RED being the Default is that you can see the workings of the Reverseproxy immediately thanks to Node-RED's Websocket implementation.

# How this Reverseproxy was built?

If you are interested on the thought processes, reasoning and learning that went into this project,
then feel free to read through [./docs/implementation_journal.md](./docs/implementation_journal.md).