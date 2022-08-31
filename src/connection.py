import asyncio
import socket
import logging
from struct import unpack, pack
from util import MessageType, Peer, do_pow

# TODO: Ist big-endian im packet wirklich nötig?


class Server():

    def __init__(self, server, host, port, send_queue: asyncio.PriorityQueue, recv_queue: asyncio.PriorityQueue, event_loop, degree=-1, bootstrapper=None):

        self.server = server
        self.host = Peer(host, port)
        self.bootstrapper = None if (bootstrapper == None) else Peer(bootstrapper[0], bootstrapper[1])
        self.degree = degree
        self.__peer_list = []
        self.__connections = {}
        # Gossip -> out
        self.send_queue = send_queue
        # out -> Gossip
        self.recv_queue = recv_queue
        self.eloop = event_loop

        self.__logger = logging.getLogger(self.host.string())


    def start(self):
        self.__logger.debug("Start %s-server" % self.server)

        #transport = None
        #task = self.eloop.create_connection(lambda: Gossip_PULL_Proto("hello", self.eloop), self.host.ip, self.host.port)
        #self.eloop.run_until_complete(task)

        
        # Todo: Put a peer request into send queue
        if self.bootstrapper is not None:
            #self.__peer_list.append(self.bootstrapper)
            # First finish bootstrapping, then start server, since we need 
            # the port to register at the bootstrapper
            asyncio.run(self.init_bootstrap())
        server = asyncio.start_server(self.__handle_connection,
                                      host=self.host.ip,
                                      port=self.host.port,
                                      family=socket.AF_INET,
                                      reuse_address=True,
                                      reuse_port=True)
                                      
        self.eloop.create_task(server)
        self.eloop.create_task(self.__handle_sending())


    async def init_bootstrap(self):
        # Build GOSSIP PEER REQUEST
        self.__logger.debug("Start bootstrapping...")
        msg = b''
        msg += pack(">HL", MessageType.GOSSIP_PEER_REQUEST, self.degree)
        # TODO: sinnvoller Wert für die nonce
        msg += pack(">Q", 0)

        msg = pack(">H", 2 + len(msg)) + msg

        #await self.__establish_connection(bootstapper, local_addr=(host))

        # Put message into send_queue
        await self.send_queue.put((self.bootstrapper, len(msg), MessageType.GOSSIP_PEER_REQUEST, msg))



    async def __handle_sending(self):
        while True:
            recv, msg_size, msg_type, msg = (await self.send_queue.get())
            if recv is None:
                await self.__send_msg_to_all(msg_size, msg_type, msg)
            else:
                await self.__send_msg(recv, msg_size, msg_type, msg)
            self.send_queue.task_done()  # Noetig?

    '''
    Assembles and sends message to all the known peers. If a peer has dropped out, we 
    remove it from the known-peers-list
    '''

    async def __send_msg_to_all(self, message_size, message_type: MessageType, message):

        if message_type == MessageType.GOSSIP_PEER_RESPONSE:
            self.__send_peer_response(message)
            return

        for peer in self.__peer_list:

            if not await self.__send_msg(peer, message_size, message_type, message):
                # Remember to remove
                peers_to_remove.append((peer, (reader, writer)))
                continue

    ''' 
    Send message to receiver. If a peer has dropped out, we remove it from the known-peers-list.
    '''
    async def __send_msg(self, receiver: Peer, message_size, message_type: MessageType, message):
        writer = None
        #msg = b''
        #msg += pack(">H", message_size)
        #msg += pack(">H", message_type)
        msg = message  

        self.__logger.debug("Ready to send")

        if receiver in self.__connections:
            writer = self.__connections[receiver][1]
        else:
            reader, writer = await self.__establish_connection(receiver)

        if writer.is_closing():
            self.__remove_peer(receiver)
            return False

        try:
            
            writer.write(msg)
            await writer.drain()
        except:
            self.__logger.warn("Error sending to %s" % receiver)
            self.__remove_peer(receiver)
            return False

        self.__logger.debug("Sent to %s: %s" %(receiver, msg))
        return True
        
    async def __establish_connection(self, peer):
        self.__logger.debug("Establish connection with %s" % peer)
        reader, writer = await asyncio.open_connection(peer.ip, peer.port)
        self.__connections.update({peer: (reader, writer)})
        # Start task that reads from this connection

        me = writer.get_extra_info('sockname')
        print("I am ", me)
        asyncio.gather(self.__receive_from_stream(reader, writer, peer))
        return reader, writer

    def __remove_peer(self, peer):
        self.__logger.debug("Remove %s since it is down" % peer.string())
        self.__peer_list.remove(peer)
        self.__connections.pop(peer)


    #######################################################################################################

    async def __handle_connection(self, reader: asyncio.StreamReader,  writer: asyncio.StreamWriter):
        addr, port = writer.get_extra_info('socket').getpeername()
        # Register connection
        if len(self.__peer_list) == self.degree:
            # remove first connection
            # TODO: bessere heuristik
            self.__peer_list.pop(0)

        # TODO: Send challenge + check response before adding to peers-list
        new_peer = Peer(addr, port)
        if new_peer in self.__peer_list:
            # Move new_peer at the end of the list
            self.__peer_list.remove(new_peer)
        self.__peer_list.append(new_peer)
        self.__connections.update({new_peer: (reader, writer)})

        await self.__receive_from_stream(reader, writer, new_peer)
        


    async def __receive_from_stream(self, reader, writer, new_peer):
        # Read and hand over to gossip if not GOSSIP_PEER_REQUEST
        try:
            while True:
                self.__logger.warn("Waiting for incoming")
                msg = await self.__read_msg(reader, writer)
                if (msg[0] != 0):
                    print("Connextion lost")
                    # Connection is lost
                    if self.__peer_list.remove(new_peer):
                        return
                    #self.__connections.popitem(new_peer)
                    #self.__remove_peer(new_peer)
                else:
                    self.__logger.debug("Received from %s %s" % (new_peer, msg))
                    await self.__pass_to_recv_queue(msg[1], new_peer)
        except:
            writer.close()
        self.__logger.warn("Exit recv loop")



    '''
    Reads a message from an existing reader and returns a tuple (ret, msg).
    ret is -1 if connection is closing/closed, 1 on an error and 0, if we have a message
    msg is a triple of message size, message type and the message itself.
    '''
    async def __read_msg(cls, reader, writer):
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
        # Read message type
        msg_type = await reader.read(2)
        if (msg_type == b""):
            return (1, b"")
        m_type = unpack(">H", msg_type)[0]
        #print("Found message of length", size)
        # Read message
        if size-4 > 0 :
            message += await reader.read(size-4)
            if (message == b''):
                return (1, b"")
        
        msg = size, m_type, message

        return (0, msg)

    async def __pass_to_recv_queue(self, msg: tuple, sender: Peer):
        
        if msg[1] == MessageType.GOSSIP_VALIDATION:
            # validation has a higher prio
            await self.recv_queue.put((0, msg, sender))
        elif msg[1] == MessageType.GOSSIP_PEER_REQUEST:
            # answer directly
            await self.__send_peer_response(sender, msg[2])
        elif msg[1] == MessageType.GOSSIP_PEER_RESPONSE:
            self.__logger.debug("Got PUSH response")
            self.__parse_peer_response(msg[2], msg[0])
        elif msg[1] == MessageType.PING:
            pass # Do nothing
        else:
            print(msg[1])
            await self.recv_queue.put((1, msg, sender))


    async def __send_peer_response(self, sender, message):
        # Since only the server knows its neighbors, we have to assemble this package here
        # In this case, message contains (limit, nonce)

        # We now assume, that there are only ipv4 addresses.
        # TODO: Limit number of peers!!!!!!!!1
        d = 0
        peers_to_remove = []
        msg = b''
        msg += pack(">HQQ", MessageType.GOSSIP_PEER_RESPONSE, 0, do_pow(0))
        msg += pack(">L", 0)

        self.__logger.debug("__pass_to_recv_queue")
        

        for p in self.__connections:

            if not await self.__is_alive(p):
                self.__logger.debug("%s is not alive" % p)
                peers_to_remove.append(p)
                continue
            if d == self.degree:
                break

            msg += socket.inet_aton(p.ip)
            msg += pack(">H", p.port)

        msg = pack(">H", 2 + len(msg)) + msg
        
        await self.send_queue.put((sender, len(msg), MessageType.GOSSIP_PEER_RESPONSE, msg))

        for p in peers_to_remove:
            self.__remove_peer(p)

        print(self.__connections)

    def __parse_peer_response(self, msg, msg_len):
        print(msg_len)
        nonce, challenge,_ = unpack(">QQL", msg[:2*8+4])
        print(msg_len, msg_len-4-16)
        print(msg)
        for i in range(2*8+4, msg_len-4, 6):
            print(i, msg[i:i+6])
            addr, port = unpack(">LH", msg[i:i+6])
            print("%s %i" % (addr, port))
            self.__peer_list.append(Peer(addr, port))


    async def __is_alive(self, peer):
        print("Check for life")
        writer = self.__connections[peer][1]
        # Build PING message
        msg = pack(">HH", 4, MessageType.PING)

        try:
            writer.write(msg)
            await writer.drain()
        except:
            return False 
        return True