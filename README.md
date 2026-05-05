# What is this Reverseproxy about?

This Reverseproxy spawns for any connecting client its own Docker-Container. 
The following video is supposed to show the basic way this Reverseproxy works.

https://github.com/user-attachments/assets/8e0c54d3-5700-47f5-aca5-c39d097d5054

Video description:
- Assume a Client (labeled Client 1) connects to the Reverseproxy via a Browser (e.g. Firefox).
> [!NOTE]
> If you type a URL in your Browser and hit Enter, your Browser automatically sends a so called HTTP-Request to that URL.
- The Reverseproxy starts a Docker-Container (labeled Container 1).
- The Reverseproxy forwards the HTTP-Request from Client 1 to Container 1.
- Container 1 sends its Response (so called HTTP-Response) to the Reverseproxy.
- The Reverseproxy forwards the HTTP-Response from Container 1 to Client 1.
- Thus, both the Client 1 and Container 1 are talking with each other through the Reverseproxy.
- Let's assume a second Client (labeled Client 2) connects to the Reverseproxy while Client 1 is also still connected.
- The Reverseproxy spawns a second Docker-Container (labeled Container 2) for Client 2.
- Now, Client 2 and Container 2 speak with each other and Client 1 and Container 1 speak with each other through the Reverseproxy.
- If one of the Clients disconnects, the Reverseproxy also deletes the Container associated with that Client (e.g. Client 1 disconnects, then the Reverseproxy deletes Container 1)

# How to install?

> [!IMPORTANT]
> As of now, I'm mainly using Arch Linux. Thus, adjust the steps in this guide to your OS if necessary.

First of all the **Requirements**:
- a terminal of your choice (e.g. `kitty`),
- `python`.

Second of all, you will need to download this repository. One way is to type in your terminal the following command:

```shell
git clone https://github.com/bekiralti/reverseproxy.git
```

Then change into the directory:

```shell
cd reverseproxy
```

Then create for Python a virtual environment (so that the additionally installed packages do not mess up your main Python installation):

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

Then run this program:

```shell
python ./src/main.py
```

## Basic testing

**Requirements**:
- A browser of your choice (e.g. `firefox`).

To simulate a Client open your browser and type in the URL: `localhost:3000`. 
To simulate a second Client you can open your browser in incognito and type in the URL: `localhost:3000`.

## What further programs are needed?

**TODO: E.g. docker**

# Example Usage

> [!NOTE]
> We will use a Node-RED Docker-Container, because it makes demonstrating the proof-of-conecpt rather easy.

**TODO: Example**

# How this Reverseproxy was built?

If you are interested on the thought processes, reasoning and learning that went into this project,
then feel free to read through ./docs/implementation_journal/README.md.
