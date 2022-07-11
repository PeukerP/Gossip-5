import asyncio
import socket
from struct import unpack, pack
from util import MessageType


class Server():

    def __init__(self, host, port, send_queue: asyncio.PriorityQueue, recv_queue: asyncio.PriorityQueue, event_loop):

        self.host = host
        self.port = port
        if host.find("."):
            self.addresses_family = socket.AddressFamily.AF_INET
        elif host.find(":"):
            self.addresses_family = socket.AddressFamily.AF_INET6
        else:
            print("Address Family is not known")
            exit(-1)

        # Irgendwie müssen connctions verwaltet werden?
        # Solange bis klar, wie genau, ist das eine map (adddr, port) -> (reder, writer)
        self.__connections = {}
        # Gossip -> out
        self.send_queue = send_queue
        # out -> Gossip
        self.recv_queue = recv_queue
        self.eloop = event_loop

    async def __establish_connection(self, host, port):
        # TODO: POW? Authentication?
        reader, writer = await asyncio.open_connection(host=host, port=port)
        self.__connections.update({(host, port): (reader, writer)})
        return reader, writer

    async def __send_msg(self, addr, port, message_type, message):
        writer = None
        if (addr, port) in self.__connections:
            writer = self.__connections[(addr, port)]
        else:
            writer = self.__establish_connection(addr, port)[1]

        if writer.is_closing():
            return ""

        msg = pack(">H", len(message))
        msg += pack(">H", message_type)
        msg += message

        writer.write(msg)
        await writer.drain()

    async def __handle_sending(self):
        addr, port, msg_type, msg = (await self.send_queue.get())[1]
        self.__send_msg(addr, port, msg_type, msg)
        self.send_queue.task_done() # Noetig?

    '''
    Reads a message from an existing reader and returns a tuple (ret, msg).
    ret is -1 if connection is closing/closed, 1 on an error and 0, if we have a message
    msg is a triple of message size, message type and the message itself.
    '''
    async def __read_msg(cls, reader, writer):
        # Whether connection is open can only be tested with writer
        if writer.is_closing():
            return (-1, b"")

        # Read message header
        # Read size of package
        msg_size = await reader.read(2)
        if (msg_size == b''):
            return (1, b"")
        size = unpack(">H", msg_size)[0]
        # Read message type
        msg_type = await reader.read(2)
        if (msg_type == b""):
            return (1, b"")
        m_type = unpack(">H", msg_type)[0]
        #print("Found message of length", size)
        # Read message
        message = await reader.read(size-4)
        if (message == b''):
            return (1, b"")

        msg = msg_size, msg_type, message

        return (0, msg)

    async def __pass_to_recv_queue(self, msg_type, msg):
        if msg_type == MessageType.GOSSIP_VALIDATION:
            # validation has a higher prio
            await self.recv_queue.put((0, msg))
        else :
            await self.recv_queue.put((1, msg))


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
            if msg[0] == 1:
                # No message received
                return
            else:
                print(msg)
                await self.__pass_to_recv_queue(msg[1][1], msg[1][2])

    def start(self):
        server = asyncio.start_server(self.__handle_connection,
                                      host=self.host,
                                      port=self.port,
                                      family=self.addresses_family,
                                      reuse_address=True,
                                      reuse_port=True)
        self.eloop.create_task(server)
        self.eloop.create_task(self.__handle_sending())
        
