import asyncio
import socket
from struct import unpack


class Server():

    def __init__(self, host, port, send_queue: asyncio.PriorityQueue, recv_queue: asyncio.PriorityQueue, send_lock: asyncio.Lock, recv_lock: asyncio.Lock):

        self.host = host
        self.port = port
        # Irgendwie müssen connctions verwaltet werden.
        # Solange bis klar, wie genau, ist das ein set aus (reader, writer)
        self.__connections = {}
        # Gossip -> out
        self.send_queue = send_queue
        self.send_lock = send_lock
        # out -> Gossip
        self.recv_queue = recv_queue
        self.recv_lock = recv_lock

    async def __establish_connection(self, host, port):
        reader, writer = await asyncio.open_connection(host=host, port=port)
        self.__connections.update({(host, port): (reader, writer)})
        return reader, writer

    async def __send_msg(self, addr, port, message):
        writer = None
        if (addr, port) in self.__connections:
            writer = self.__connections[(addr, port)]
        else:
            writer = self.__establish_connection(addr, port)[1]

        if writer.is_closing():
            return ""
        #TODO: Can we use API messages for p2p layer??? Otherwise new subclass
        writer.write(message)
        await writer.drain()

    async def __handle_sending(self):
        while True:
            async with self.send_lock:
                addr, port, msg = await self.send_queue.get()
            self.__send_msg(addr, port, message)


    async def __read_msg(cls, reader, writer):
       # TODO: error handling
        # Whether connection is open can only be tested with writer
        if writer.is_closing():
            return (-1, b"")

        msg_size = await reader.read(2)
        if (msg_size == b''):
            return (0, msg_size)        
        size = unpack(">H", msg_size)[0]
        #print("Found message of length", size)
        msg = msg_size + await reader.read(size-2)
        if (msg == msg_size and size > 0):
            return (0, msg_size)  
        #print(msg)

        # TODO: Prio according message type -> new class -> how to handle inhertitance???
        return (1, msg)

    async def __pass_to_recv_queue(self, msg):
        async with self.recv_lock:
            await self.recv_queue.put(msg)

    async def __handle_connection(self, reader: asyncio.StreamReader,  writer: asyncio.StreamWriter):
        addr, port = writer.get_extra_info('socket').getpeername()
        # Register connection
        self.__connections.update({(addr, port): (reader, writer)})

        # Read and hand over to gossip
        while True:
            msg = await self.__read_msg(reader, writer)
            if (msg[0] == -1):
                # Connection is lost
                self.__connections.popitem((addr, port))
                return
            if msg[1] == b'':
                continue
            await self.__pass_to_recv_queue(msg)

    def start(self):
        eloop = asyncio.get_event_loop()
        server = asyncio.start_server(self.__handle_connection,
                                      host=self.host,
                                      port=self.port,
                                      family=socket.AddressFamily.AF_INET,
                                      reuse_address=True,
                                      reuse_port=True)
        eloop.create_task(server)
        eloop.create_task(self.__handle_sending())
        try:
            eloop.run_forever()
        except KeyboardInterrupt as e:
            eloop.stop()
