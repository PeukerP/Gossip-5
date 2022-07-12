import asyncio
import socket
from struct import unpack, pack
from util import MessageType

# TODO: Make ipv4 AND ipv6 sockets possible
# Disclaimer: Bootstrapping is not implemented yet. And until now, technically we only support ipv4
# Maybe give up the Idea of simply use asyncio.start_server?


class Server():

    def __init__(self, host, port, send_queue: asyncio.PriorityQueue, recv_queue: asyncio.PriorityQueue, event_loop, degree=-1, bootstrapper=None):

        self.host = host
        self.port = port
        self.bootstrapper = bootstrapper
        self.degree = degree
        self.__peer_list = []
        self.__connections = {}
        # Gossip -> out
        self.send_queue = send_queue
        # out -> Gossip
        self.recv_queue = recv_queue
        self.eloop = event_loop

    async def __establish_connection(self, address, port):
        reader, writer = await asyncio.open_connection(address, port)
        self.__connections.update({(address, port): (reader, writer)})
        return reader, writer

    async def __send_peer_response(self, message):
        # Since only the server knows its neighbors, we have to assemble this package here
        # In this case, message contains (limit, nonce)

        # We now assume, that there are only ipv4 addresses. TODO: change this
        # TODO: Limit number of peers!!!!!!!!1
        return

        msg += pack(">HQQ", message_type, nonce, do_pow(nonce))
        msg += pack(">L", 0)
        msg += socket.inet_aton(p[0])
        msg += pack(">H", p[1])
        msg = pack(">H", 2 + len(msg)) + msg

    '''
    Send message to all the known peers. If a peer has dropped out, we 
    remove it from the known-peers-list
    '''

    async def __send_msg(self, message_size, message_type: MessageType, message):

        peers_to_remove = []
        msg = b''
        i = 0

        if message_type == MessageType.GOSSIP_PEER_RESPONSE:
            self.__send_peer_response(message)
            return

        for peer in self.__peer_list:
            writer = None
            if peer in self.__connections:
                writer = self.__connections[peer][1]
            else:
                reader, writer = self.__establish_connection(peer[0], peer[1])

            if writer.is_closing():
                # Remember to remove
                peers_to_remove.append((peer, (reader, writer)))
                continue

            msg += pack(">H", message_size)
            msg += pack(">H", message_type)
            msg += message

            writer.write(msg)
            await writer.drain()
        # Remove from peer-list
        for peer in peers_to_remove:
            self.__peer_list.remove(peer)
            self.__connections.popitem(peer)

    async def __handle_sending(self):
        msg_size, msg_type, msg = (await self.send_queue.get())
        self.__send_msg(msg_size, msg_type, msg)
        self.send_queue.task_done()  # Noetig?

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
        if (msg_size == b'' or len(msg_size) < 2):
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

    async def __pass_to_recv_queue(self, msg: tuple):
        if msg[1] == MessageType.GOSSIP_VALIDATION:
            # validation has a higher prio
            await self.recv_queue.put((0, msg))
        else:
            await self.recv_queue.put((1, msg))

    async def __handle_connection(self, reader: asyncio.StreamReader,  writer: asyncio.StreamWriter):
        addr, port = writer.get_extra_info('socket').getpeername()
        # Register connection
        if len(self.__peer_list) == self.degree:
            # remove first connection
            self.__peer_list.pop(0)

        # TODO: Send challenge + check response before adding to peers-list
        self.__peer_list.append(((addr, port)))
        self.__connections.update({(addr, port): (reader, writer)})

        # Read and hand over to gossip
        while True:
            msg = await self.__read_msg(reader, writer)
            if (msg[0] == -1):
                # Connection is lost
                self.__peer_list.remove((addr, port))
                self.__connections.popitem((addr, port))
                return
            if msg[0] == 1:
                # No message received
                return
            else:
                print(msg)
                await self.__pass_to_recv_queue(msg[1])

    def init_bootstrap(self):
        # Build GOSSIP PEER REQUEST
        msg = b''
        msg += pack(">HL", MessageType.GOSSIP_PEER_REQUEST, self.degree)
        # TODO: sinnvoller Wert für die nonce
        msg += pack(">Q", 0)

        msg = pack(">H", 2 + len(msg)) + msg

        # Put message into send_queue
        self.send_queue.put((len(msg), MessageType.GOSSIP_PEER_REQUEST, msg))

    def start(self):
        # Todo: Put a peer request into send queue
        if self.bootstrapper is not None:
            self.init_bootstrap()
        server = asyncio.start_server(self.__handle_connection,
                                      host=self.host,
                                      port=self.port,
                                      family=socket.AF_UNSPEC,
                                      reuse_address=True,
                                      reuse_port=True)
        self.eloop.create_task(server)
        self.eloop.create_task(self.__handle_sending())
