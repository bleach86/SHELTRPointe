from kademlia.network import Server as KademliaServer
from kademlia.storage import ForgetfulStorage

import socketio

import time
from itertools import takewhile
import operator
import asyncio
import random


class KademliaP2P:
    def __init__(self):
        self.server = KademliaServer(storage=ForgetfulStorageExt())
        self.isBootStrap = False

    async def bootstrap_conn(self, addr, port):
        await self.server.listen(8470)

        if not self.isBootStrap:
            bootstrap_node = (addr, int(port))
            await self.server.bootstrap([bootstrap_node])

    async def set(self, key, value):
        return await self.server.set(key, value)

    async def get(self, key):
        return await self.server.get(key)

    def stop(self):
        self.server.stop()


class ForgetfulStorageExt(ForgetfulStorage):
    def iter_newer_than(self, seconds_old):
        min_birthday = time.monotonic() - seconds_old
        zipped = self._triple_iter()
        matches = takewhile(lambda r: min_birthday <= r[1], zipped)
        return list(map(operator.itemgetter(0, 2), matches))


class SocketioP2PClient:
    def __init__(self):
        self.connections = {}

    async def start_socketio_client(self, server_address, port):
        sio = socketio.AsyncClient(logger=False, engineio_logger=False)
        sio.register_namespace(MyCustomNamespace("/"))  # bind

        @sio.on("connect")
        async def connect_handler():
            print(f"Connected to server {server_address}:{port}")
            await sio.emit(
                "join",
                {"username": f"{random.randint(100000, 100000000000)}", "room": "tx"},
            )

        @sio.on("message")
        @sio.on("server_response")
        @sio.on("room_message")
        async def message_handler(data):
            print(f"Received message from server {server_address}:{port}:", data)

        @sio.on("join")
        async def join_handler():
            print("we joined a room")

        await sio.connect(f"http://{server_address}:{port}")
        self.connections[(server_address, port)] = sio  # Store the client instance
        await sio.wait()

    async def add_connection(self, server_address, port):
        if (server_address, port) not in self.connections:
            await self.start_socketio_client(server_address, port)

    async def remove_connection(self, server_address, port):
        if (server_address, port) in self.connections:
            del self.connections[(server_address, port)]

    async def emit_to_connection(self, server_address, port, event, data):
        if (server_address, port) in self.connections:
            sio = self.connections[(server_address, port)]
            await sio.emit(event, data)

    async def disconnect_all(self):
        for server_address, port in self.connections.copy():
            sio = self.connections[(server_address, port)]
            try:
                await sio.disconnect()
            except asyncio.CancelledError:
                print(f"Connection to {server_address}:{port} was canceled.")
            finally:
                del self.connections[(server_address, port)]


class MyCustomNamespace(socketio.AsyncClientNamespace):
    async def on_connect(self):
        print("I'm connected!")

    async def on_disconnect(self):
        print("I'm disconnected!")

    async def on_my_event(self, data):
        await self.emit("my_response", data)

    async def on_message(self, data):
        print("[echo]:", data)


class SocketIoAsyncClient:
    def __init__(self) -> None:
        self.sio = socketio.AsyncClient(logger=False, engineio_logger=False)
        self.sio.register_namespace(MyCustomNamespace("/"))  # bind
