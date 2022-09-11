import asyncio
import socket
import logging
from typing import Union, Tuple
from connection import Connections
from struct import unpack
from util import MessageType, Peer, generate_nonce, verify_pow
from packing import *


# TODO: Timeout connections
class Server():
    '''
    This class is never meant to be instantiated. It is merely an abstract superclass
    that unifies common properties and functions of the actual P2PServer and APIServer
    '''

    def __init__(self, server, host, port,
                 send_queue: asyncio.Queue, recv_queue: asyncio.Queue, event_loop):
        self.server = server
        self.host = Peer(host, port)
        self._logger = logging.getLogger(self.host.string())

        # Only check for alive peers when we have > degree peers or we have to answer a PEER_REQUEST
        self._connections = Connections(self._logger)
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

        t1 = self.eloop.create_task(server)
        t2 = self.eloop.create_task(self._handle_sending())
        return t1, t2

    async def _handle_sending(self):
        '''
        Loop that listen on send queue. Needs to be implemented in a subclass.
        '''
        raise NotImplementedError

    '''
    Assembles and sends message to all the known peers with an established connection.
    '''

    async def _send_msg_to_all(self, message):
        for peer in self._connections.get_all_connections():
            await self._send_msg(peer, message)

    async def _send_msg_to_degree(self, message, degree):
        '''
        Sends message to up to degree peers from the peer list.
        '''
        random_peers = self._connections.get_random_peers(degree)
        for peer in random_peers:
            await self._send_msg(peer, message)

    async def _send_msg(self,
                        receiver: Union[Peer, Tuple[asyncio.StreamReader, asyncio.StreamWriter]],
                        message: bytes) -> bool:
        '''
        Send message to receiver. Returns whether it was able to send the message.
        receiver can be Peer or tuple(reader, writer).

        :param receiver: Receiver of the message.
        :param message_size: To remove
        :param message_type: To remove
        :param message: Whole message packet to be sent.

        :return: Whether sending was successful

        If sender is Peer:
        If there is no connection registered for this peer,
        establish a new one and update the peer list.
        If sending fails, remove peer from peer list.
        '''
        msg = message
        reader: asyncio.StreamReader
        writer: asyncio.StreamWriter

        self._logger.debug("Ready to send")
        if isinstance(receiver, Peer):

            reader, writer = self._connections.get_streams(receiver)
            if writer is None:
                reader, writer = await self._create_new_connection(receiver)
            if writer is None:
                return False
        elif isinstance(receiver, tuple):
            reader, writer = receiver
        else:
            self._logger.error(
                "Got %s, expected Peer or tuple" % type(receiver))
            return False
        if writer.is_closing():
            await self._connections.remove_connection(receiver)
            return False

        try:
            writer.write(msg)
            await writer.drain()
        except:
            self._logger.warning("Error sending to %s" % str(receiver))
            # if isinstance(receiver, Peer):
            await self._connections.remove_connection(receiver)
            return False

        self._logger.debug("Sent to %s: %s" % (receiver, msg))
        return True

    async def _create_new_connection(self, peer: Peer) -> Tuple:
        '''
        Establishes new connection to peer and start handler to listen on the StreamReader.
        :param peer: Peer who exists in peer list
        :return: Tuple(reader,writer) on success and (None, None) on failure
        '''
        if peer == self.host:
            return None, None
        reader, writer = await self._connections.establish_connection(peer)
        if reader is not None:
            # Start listening on read stream
            asyncio.gather(self._handle_receiving(reader, writer))
        self._logger.debug("Successfully created connection")
        return reader, writer

    async def _handle_receiving(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        '''
        This function is called when a new connection with this server has been established.
        Continuously read on the streamReader. If message received, pass to _handle_received_message()
        which has to be implemented by the subclass. Returns on failure.
        '''
        addr, port = writer.get_extra_info('socket').getpeername()
        new_peer = Peer(addr, port)
        try:
            while True:
                msg = await self._read_msg(reader, writer)
                if (msg[0] != 0):
                    self._logger.debug("Connection lost")
                    # Connection is lost
                    if not await self._connections.is_alive(stream_tuple=(reader, writer)):
                        return
                else:
                    await self._handle_received_message(msg[1], reader, writer, new_peer)
        except Exception as e:
            self._logger.exception("In handle receiving routine: %s " % str(e))
            if not writer.is_closing():
                writer.close()
                await writer.wait_closed()
        self._logger.warn("Exit recv loop")

    async def _handle_received_message(self, message, reader, writer, new_peer):
        '''
        Needs to be implemented in a subclass.
        '''
        raise NotImplementedError

    async def _read_msg(self, reader, writer):
        '''
        Reads a message from an existing reader and returns a tuple (ret, msg).
        ret is -1 if connection is closing/closed, 1 on an error and 0, if we have a message
        msg is a tuple of message size, message type and the message itself.
        '''
        message = b''
        # Whether connection is open can only be tested with writer
        if writer.is_closing():
            return (-1, b"")

        # Read message header
        # Read size of package
        msg_size = await reader.read(2)
        if (msg_size == b'' or len(msg_size) < 2):
            return (1, b"")
        size = unpack(">H", msg_size)[0]
        # Is size less than header size?
        if size < 4:
            return (1, b"")
        # Read message type
        msg_type = await reader.read(2)
        if (msg_type == b""):
            return (1, b"")
        m_type = unpack(">H", msg_type)[0]
        # Read message
        if size - 4 > 0:
            message += await reader.read(size - 4)
            if message == b'':
                return (1, b"")

        msg = size, m_type, message, (msg_size + msg_type + message)

        return (0, msg)


class P2PServer(Server):
    '''
    Implements the P2P Server
    '''

    def __init__(self, server, host, port, max_ttl,
                 send_queue: asyncio.PriorityQueue, recv_queue: asyncio.PriorityQueue, event_loop,
                 cache_size, degree, bootstrapper=None):
        super().__init__(server, host, port, send_queue, recv_queue, event_loop)
        self._degree = degree
        self._cache_size = cache_size
        self._max_ttl = max_ttl
        self._bootstrapper = None if (bootstrapper == None) else Peer(
            bootstrapper[0], bootstrapper[1])
        # To check wether the received challenge belongs to a known nonce.
        self._pending_validation = {}  # Stream tuple -> nonce
        self._peer_threshold = 2  # TODO

        if self._bootstrapper is not None:
            self._connections.add_peer(self._bootstrapper)

        if cache_size < 2:
            self._logger.error(
                "Cache size of %i is too less. Needs at least be 2." % cache_size)
            exit(-1)
        self._connections.set_limit(cache_size)

    def start(self):
        self._logger.debug("Start %s-server" % self.server)

        if self._bootstrapper is not None:
            asyncio.run(self._send_gossip_hello(self._bootstrapper))
        super().start()

    async def _handle_sending(self):
        try:
            while True:
                msg, recv = (await self.send_queue.get())
                print(self._connections)
                if recv is None:
                    await self._send_msg_to_degree(msg, self._degree)
                    # If there are too few peers in the list, try a peer request
                    if 0 < len(self._connections.get_all_connections()) < self._peer_threshold:
                        self._logger.debug(
                            "Try to gather a peer list from a random neighbor")
                        rp = self._connections.get_random_peers(1)
                        if len(rp) == 0:
                            # new attempt for bootstrapping
                            await self._send_gossip_hello(self._bootstrapper)
                        await self._send_gossip_hello(list(rp)[0])

                elif isinstance(recv, Peer) or isinstance(recv, tuple):
                    await self._send_msg(recv, msg)
                else:
                    await self._send_msg_to_all(msg)

        except:
            self._logger.exception("Failure in sending message")

    async def _handle_received_message(self, msg, reader, writer, new_peer):
        msg_len, msg_type, data, raw_msg = msg

        self._logger.debug("Received from %s %s" % (new_peer, msg))
        match msg_type:
            case MessageType.GOSSIP_HELLO:
                await self._send_verification_request(reader, writer)
                '''
                if self._bootstrapper is None:
                    # First, request PoW, then may add to peer list
                    # Send nonce
                    await self._send_verification_request(reader, writer)
                else:
                    await self._receive_gossip_hello(data, reader, writer)
                '''
            case MessageType.GOSSIP_VERIFICATION_REQUEST:
            # TODO: Muss bootstapper sich auch irgendwo verifizieren?
                await self._receive_verification_request(data, reader, writer)
            case MessageType.GOSSIP_VERIFICATION_RESPONSE:
                await self._receive_verification_response(data, reader, writer)
            case MessageType.GOSSIP_PEER_RESPONSE:
                await self._receive_peer_response(data, msg_len)
            case MessageType.GOSSIP_PUSH:
                await self._receive_push_update(data)
            case MessageType.PING:
                pass  # Do nothing
            case _:
                await self.recv_queue.put((msg, (reader, writer)))

    '''
    async def _send_peer_request(self, peer):
        # Build GOSSIP PEER REQUEST
        msg = pack_peer_request()
        # Put message into send_queue
        await self.send_queue.put((msg, peer))
    '''

    async def _send_peer_response(self, sender):
        msg = pack_peer_response(
            self._connections.get_all_connections(), sender)
        await self.send_queue.put((msg, sender))

    async def _receive_peer_response(self, msg, msg_len):
        '''
        Parses PEER_RESPONSE and update the peer list.
        At most half of the cache size is updated -> A single malicious 
        PEER_RESPONSE cannot change the whole peer list.

        :param msg: Payload of PEER_RESPONSE
        :param msg_len: Length of the PEER_RESPONSE package
        '''
        no_updates = 0  # Counts the number of updates
        data = unpack_peer_response(msg, msg_len)
        capacity = self._connections.get_capacity()
        for peer_dir in data['peer_list']:
            if capacity == 0 or no_updates > self._cache_size / 2:
                break
            new_peer = Peer(peer_dir['addr'], peer_dir['port'])

            if new_peer not in self._connections.get_all_connections():
                no_updates += 1
                capacity -= 1

            if self._connections.get_streams(new_peer) == (None, None):
                await self._send_gossip_hello(new_peer) 

    async def _send_gossip_hello(self, receiver):
        msg = pack_hello(self.host)
        print("Send hello")
        await self.send_queue.put((msg, receiver))

    async def _receive_gossip_hello(self, msg, reader, writer):
        data = unpack_hello(msg)
        peer = Peer(data['addr'], data['port'])
        await self._connections.update_connection(peer, reader, writer)
        # Send my view to the new one
        await self._send_peer_response(peer)
        # PUSH the new one to all other
        await self._send_push_update(peer, 1)

    async def _send_push_update(self, peer, ttl):
        # TODO: Was ist eine sinnolle ttl?
        msg = pack_push_update(peer, ttl)
        # TODO: none?
        await self.send_queue.put((msg, "ALL"))

    async def _receive_push_update(self, msg):
        data = unpack_push_update(msg)
        new_peer = Peer(data['addr'], data['port'])

        print(self._connections.get_all_connections())

        # This check should prevent peers near the initiator to
        # receive the push message too many times
        if data['ttl'] < self._max_ttl / 2:
            if new_peer != self.host:
                if self._connections.get_streams(new_peer) == (None, None):
                    await self._connections.update_connection(new_peer, None, None)
                    self._logger.debug("Say hello to %s" % new_peer)
                    await self._send_gossip_hello(new_peer)
        if data['ttl'] > 0:
            await self._send_push_update(new_peer, data['ttl'] - 1)

    async def _send_verification_request(self, reader, writer):
        nonce = generate_nonce()
        print("Nonce ", nonce)
        self._logger.debug("Generate nonce: %i" % nonce)
        msg = pack_verification_request(nonce)
        await self.send_queue.put((msg, (reader, writer)))
        self._pending_validation.update({(reader, writer): nonce})

    async def _receive_verification_request(self, msg, reader, writer):
        data = unpack_verification_request(msg)
        nonce = data['nonce']
        msg = pack_verification_response(nonce, self.host)
        await self.send_queue.put((msg, (reader, writer)))

    async def _receive_verification_response(self, msg, reader, writer):
        success = False
        data = unpack_verification_response(msg)
        if (reader, writer) in self._pending_validation:
            old_nonce = self._pending_validation[(reader, writer)]
            if old_nonce == data['nonce']:
                if verify_pow(data['nonce'], data['challenge']):
                    success = True
                    await self._connections.update_connection(data['peer'], reader, writer)
                else:
                    self._logger.warning("Verify challenge failed.")
            else:
                self._logger.warning(
                    "Nonce differs: %i but expected %i" % (data['nonce'], old_nonce))
            self._pending_validation.pop((reader, writer))
        if not success:
            try:
                writer.close()
                await writer.wait_closed()
            except:
                self._logger.warn("Closing failed")
        else:
            await self._send_peer_response(data['peer'])
            await self._send_push_update(data['peer'], self._max_ttl)


class APIServer(Server):
    '''
    Implements the API Server.
    '''

    def __init__(self, server, host, port, send_queue: asyncio.Queue, recv_queue: asyncio.Queue, event_loop):
        super().__init__(server, host, port, send_queue, recv_queue, event_loop)

    def start(self):
        self._logger.debug("Start %s-server" % self.server)
        server = asyncio.start_server(self._handle_receiving,
                                      host=self.host.ip,
                                      port=self.host.port,
                                      family=socket.AF_INET,
                                      reuse_address=True,
                                      reuse_port=True)

        self.eloop.create_task(server)
        self.eloop.create_task(self._handle_sending())

    async def _handle_received_message(self, message, reader, writer, new_peer):
        '''
        Put received message and the sender to the receive queue.
        '''
        await self.recv_queue.put((message, (reader, writer)))

    async def _handle_sending(self):
        try:
            while True:
                msg, recv = (await self.send_queue.get())
                await self._send_msg(recv, msg)
        except:
            self._logger.exception("Failure in sending message")
