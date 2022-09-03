import asyncio
import socket
import logging
from connection import Connections
from struct import unpack, pack
from util import MessageType, Peer, do_pow
from packing import *
class Server():
    '''
    This class is never meant to be instanciated. It is merely an abstract superclass that unifies common properties 
    and functions of the actual P2PServer and APIServer
    '''

    def __init__(self, server, host, port, send_queue: asyncio.PriorityQueue, recv_queue: asyncio.PriorityQueue, event_loop, degree=-1):
        self.server = server
        self.host = Peer(host, port)
        self.degree = degree

        self._logger = logging.getLogger(self.host.string())

        # Only check for alive peers when we have > degree peers or we have to answer a PEER_REQUEST
        self._connections = Connections(self.degree, self._logger)
        # Gossip -> out
        self.send_queue = send_queue
        # out -> Gossip
        self.recv_queue = recv_queue
        self.eloop = event_loop

    def start(self):
        server = asyncio.start_server(self._handle_receiving,
                                      host=self.host.ip,
                                      port=self.host.port,
                                      family=socket.AF_INET,
                                      reuse_address=True,
                                      reuse_port=True)

        self.eloop.create_task(server)
        self.eloop.create_task(self._handle_sending())

    async def _handle_sending(self):
        while True:
            recv, msg_size, msg_type, msg = (await self.send_queue.get())
            if recv is None:
                await self._send_msg_to_all(msg_size, msg_type, msg)
            else:
                await self._send_msg(recv, msg_size, msg_type, msg)
            self.send_queue.task_done()  # Noetig?

    '''
    Assembles and sends message to all the known peers with an established connection.
    '''

    async def _send_msg_to_all(self, message_size, message_type: MessageType, message):

        if message_type == MessageType.GOSSIP_PEER_RESPONSE:
            self._send_peer_response(message)
        else:
            for peer in self._connections.get_all_connections():
                await self._send_msg(peer, message_size, message_type, message)

    ''' 
    Send message to receiver. Returns whether it was able to send the message.
    '''
    async def _send_msg(self, receiver: Peer, message_size, message_type: MessageType, message):
        #msg = b''
        #msg += pack(">H", message_size)
        #msg += pack(">H", message_type)
        msg = message

        self._logger.debug("Ready to send")

        reader, writer = self._connections.get_streams(receiver)
        if writer is None:
            # Probleme mit shadowing
            reader, writer = await self._create_new_connection(receiver)
        if writer is None :
            return False
        if writer.is_closing():
            # self._remove_peer(receiver)
            return False

        try:
            writer.write(msg)
            await writer.drain()
        except:
            self._logger.warn("Error sending to %s" % receiver)
            self._connections.remove_connection(receiver)
            return False

        self._logger.debug("Sent to %s: %s" % (receiver, msg))
        return True

    async def _create_new_connection(self, peer):
        if peer == self.host:
            return None, None
        reader, writer = await self._connections.establish_connection(peer)
        if reader is not None:
            # Start listening on read stream
            asyncio.gather(self._handle_receiving(reader, writer))
        return reader, writer


    async def _handle_receiving(self, reader: asyncio.StreamReader,  writer: asyncio.StreamWriter):
        addr, port = writer.get_extra_info('socket').getpeername()
        # TODO: Send challenge + check response before adding to peers-list
        new_peer = Peer(addr, port)
        try:
            while True:
                msg = await self._read_msg(reader, writer)
                if (msg[0] != 0):
                    print("Connextion lost")
                    # Connection is lost
                    if await self._connections.is_alive(new_peer):
                        # lazy clean-up
                        return
                else:
                    print("Received")
                    await self._handle_received_message(msg[1], reader, writer, new_peer)
        except Exception as e:
            self._logger.exception("In handle receiving routine: %s " % str(e))
            writer.close()
        self._logger.warn("Exit recv loop")

        
    async def _handle_received_message(self, reader, writer, new_peer):
        raise NotImplementedError


    '''
    Reads a message from an existing reader and returns a tuple (ret, msg).
    ret is -1 if connection is closing/closed, 1 on an error and 0, if we have a message
    msg is a triple of message size, message type and the message itself.
    '''
    async def _read_msg(cls, reader, writer):
        message = b''
        print("Read msg")
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
        if size-4 > 0:
            message += await reader.read(size-4)
            if (message == b''):
                return (1, b"")

        msg = size, m_type, message

        return (0, msg)

class P2PServer(Server):
    def __init__(self, server, host, port, max_ttl, send_queue: asyncio.PriorityQueue, recv_queue: asyncio.PriorityQueue, event_loop, degree=-1, bootstrapper=None):
        super().__init__(server, host, port, send_queue, recv_queue, event_loop, degree, bootstrapper)
        self._max_ttl= max_ttl
        self._bootstrapper = None if (bootstrapper == None) else Peer(
            bootstrapper[0], bootstrapper[1])

        if self._bootstrapper is not None:
            self._connections.update_connection(self._bootstrapper, None, None)

    def start(self):
        self._logger.debug("Start %s-server" % self.server)

        if self._bootstrapper is not None:
            # self._peer_list.append(self.bootstrapper)
            # First finish bootstrapping, then start server, since we need
            # the port to register at the bootstrapper
            asyncio.run(self._send_gossip_hello(self._bootstrapper))
        server = asyncio.start_server(self._handle_receiving,
                                      host=self.host.ip,
                                      port=self.host.port,
                                      family=socket.AF_INET,
                                      reuse_address=True,
                                      reuse_port=True)

        self.eloop.create_task(server)
        self.eloop.create_task(self._handle_sending())

    async def _handle_received_message(self, msg, reader, writer, new_peer):
        msg_len, msg_type, data = msg

        self._logger.debug("Received from %s %s" % (new_peer, msg))
        if msg_type == MessageType.GOSSIP_HELLO:
            print("Hello")
            await self._receive_gossip_hello(data, reader, writer)
        elif msg_type == MessageType.GOSSIP_VALIDATION:
            # validation has a higher prio
            await self.recv_queue.put((0, msg, sender))
        elif msg_type == MessageType.GOSSIP_PEER_REQUEST:
            # answer directly
            await self._send_peer_response(sender, data)
        elif msg_type == MessageType.GOSSIP_PEER_RESPONSE:
            await self._receive_peer_response(data, msg_len)
        elif msg_type == MessageType.GOSSIP_PUSH:
            await self._receive_push_update(data)
        elif msg_type == MessageType.PING:
            pass  # Do nothing
        else:
            print(msg_type)
            await self.recv_queue.put((1, msg, sender))

    async def _send_peer_request(self):
        # Build GOSSIP PEER REQUEST
        msg = pack_peer_request()
        # Put message into send_queue
        await self.send_queue.put((self._bootstrapper, len(msg), MessageType.GOSSIP_PEER_REQUEST, msg))

    async def _send_peer_response(self, sender, message):
        # Since only the server knows its neighbors, we have to assemble this package here
        # In this case, message contains (limit, nonce)

        # We now assume, that there are only ipv4 addresses.
        # TODO: Limit number of peers!!!!!!!!1
        msg = pack_peer_response(self._connections.get_all_connections(), sender)
        print(msg)

        await self.send_queue.put((sender, len(msg), MessageType.GOSSIP_PEER_RESPONSE, msg))

        print(self._connections)

    async def _receive_peer_response(self, msg, msg_len):
        data = unpack_peer_response(msg, msg_len)
        for peer_dir in data['peer_list']:
            if self._connections.get_capacity() <= 0:
                break
            new_peer = Peer(peer_dir['addr'], peer_dir['port'])

            if self._connections.get_streams(new_peer) == (None, None):
                #self._connections.update_connection(new_peer, None, None)
                await self._send_gossip_hello(new_peer)

    async def _send_gossip_hello(self, receiver):
        msg = pack_hello(self.host)
        await self.send_queue.put((receiver, len(msg), MessageType.GOSSIP_HELLO, msg))

    async def _receive_gossip_hello(self, msg, reader, writer):
        data = unpack_hello(msg)
        peer = Peer(data['addr'], data['port'])
        self._connections.update_connection(peer, reader, writer)
        # Send my view to the new one
        await self._send_peer_response(peer, None)
        # PUSH the new one to all other
        await self._send_push_update(peer, 1)

    async def _send_push_update(self, peer, ttl):
        #TODO: Was ist eine sinnolle ttl?
        msg = pack_push_update(peer, ttl)
        await self.send_queue.put((None, len(msg), MessageType.GOSSIP_PUSH, msg))

    async def _receive_push_update(self, msg):
        data = unpack_push_update(msg)
        new_peer = Peer(data['addr'], data['port'])

        print(self._connections.get_all_connections())

        if self._connections.get_streams(new_peer) == (None, None):
            #self._connections.update_connection(new_peer, None, None)
            await self._send_gossip_hello(new_peer)
        #TODO: Lookup ttl handling
        if data['ttl'] > 1:
            await self._send_push_update(new_peer, data['ttl']-1)
