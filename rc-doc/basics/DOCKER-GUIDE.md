# Docker for ResearchCrew — A Crash Course

You have never used Docker. This document explains what Docker is, why
it exists, how it works, and exactly what role it plays in ResearchCrew.
Then it shows you the patterns you will reuse on any future project.

Read top to bottom. Every command is copy-pasteable.

---

## 1. The problem Docker solves

Imagine you write a Python script on your laptop. It works.

You send it to a friend. They run it. It crashes. Why?

- Their Python is 3.11, yours is 3.12.
- They have `psycopg` 3.2, you have 3.3.
- Their Postgres is version 14, yours is 16.
- Their OS is macOS, yours is Windows.

This is the "works on my machine" problem. It is not a small problem.
It is one of the most expensive problems in software.

Docker's answer: **ship the machine, not just the code.**

A Docker container is a self-contained box that includes:
- The operating system libraries your program needs
- The exact version of Python you used
- The exact versions of every package
- Your code

Run the box on any machine that has Docker installed. It behaves
identically. "Works on my machine" becomes "works on every machine that
runs the container."

---

## 2. Container vs Virtual Machine

You may have heard of virtual machines (VMs). Docker containers are
similar in spirit but much lighter.

**Virtual Machine:**
- Includes a full operating system (Windows, Ubuntu, etc.)
- Boots like a real computer (30-60 seconds)
- Uses gigabytes of disk and RAM
- Strong isolation: a VM cannot see the host OS

**Docker Container:**
- Shares the host OS kernel
- Starts in milliseconds to a couple of seconds
- Uses megabytes
- Isolation via Linux namespaces and cgroups, not a full OS

Think of it this way: a VM is a separate house. A container is a
separate room in the same house. The room has its own lock and its own
furniture, but it shares the plumbing and electricity.

For ResearchCrew, containers are the right choice: we need isolated
Postgres, not an entire second operating system.

---

## 3. The four Docker concepts you must know

Everything in Docker is built from four things. Learn these and 90% of
Docker commands make sense.

### 3.1 Image

An image is a **blueprint**. It is a frozen filesystem plus metadata.
It cannot run by itself. It is like a `.zip` file that contains
everything needed to start a process.

Example: `pgvector/pgvector:pg16` is an image. It contains Ubuntu,
Postgres 16, and the pgvector extension, already installed and
configured.

Images are built from a `Dockerfile` (see Section 5) or pulled from a
registry (see Section 3.4).

### 3.2 Container

A container is a **running instance of an image**. It is the image
unpacked into memory, with a process running inside.

One image can produce many containers. Just like one Python class can
produce many objects.

Example: `docker run pgvector/pgvector:pg16` starts a container from
the pgvector image. The container runs Postgres.

Containers are ephemeral by default. Delete the container, and any
data written inside it is gone. This is why we use volumes (Section
3.3).

### 3.3 Volume

A volume is **persistent storage that lives outside the container**.
It is a directory on the host machine that Docker mounts into the
container.

Why it matters: Postgres writes its tables to disk. If that disk is
inside the container, deleting the container deletes the tables.
Mount a volume, and the tables survive container deletion.

Example:

    docker run -v rc_pgdata:/var/lib/postgresql/data pgvector/pgvector:pg16

`rc_pgdata` is a named volume. Docker creates it on first run and keeps
it until you explicitly delete it.

### 3.4 Registry

A registry is a **server that stores images**. Docker Hub is the
default public registry. Anyone can push an image, anyone can pull it.

Example: `pgvector/pgvector:pg16` was pulled from Docker Hub the first
time you ran it. Subsequent runs use the local copy.

---

## 4. Docker's architecture, plainly

Docker is a client-server system. Three pieces:

**Docker Client** — the `docker` command you type in PowerShell. It
does not do the work. It sends instructions to the daemon.

**Docker Daemon** (`dockerd`) — the background service that actually
builds images, runs containers, manages volumes. On Windows, this runs
inside the Docker Desktop Linux VM.

**Docker Registry** — where images come from and go to.

The flow when you run `docker run postgres`:

    You type: docker run postgres
        |
        v
    Docker Client sends "run postgres" to Daemon
        |
        v
    Daemon checks local images. No postgres image? Pull from Docker Hub.
        |
        v
    Daemon creates a container from the image.
        |
        v
    Daemon starts the process inside the container.
        |
        v
    Daemon reports the container ID back to the client.
        |
        v
    You see a container ID in your terminal.

Every Docker command follows this pattern. The client is a messenger.
The daemon does the work.

---

## 5. Dockerfile: how images are built

An image is built from a `Dockerfile`. It is a plain text file with
instructions. Each instruction creates a **layer**. Layers are cached.

Example Dockerfile for a Python app:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["python", "cli.py"]