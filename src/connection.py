import asyncio
import socket
import logging
from struct import unpack, pack


# TODO: Ist big-endian im packet wirklich nötig?
# TODO: Send valid peer list


class Connections():
    def __init__(self, limit, logger):
        
        self.__limit = limit
        self.__connections = {} # Peer -> read,write stream
        self.__logger = logger

    def __str__(self):
        return str(self.__connections.keys())
        
        
    def get_all_connections(self):
        return self.__connections

    def get_streams(self, peer):
        if peer in self.__connections:
            return self.__connections[peer]
        else:
            return (None,None)

    def get_capacity(self):
        return self.__limit - len(self.__connections)

    def update_connection(self, peer, reader, writer):
        if len(self.__connections) == self.__limit and peer not in self.__connections:
            #await self.__remove_unused_connections()
            # if the connection buffer is still full, remove any connection
            #if len(self.__connections) == limit:
            self.remove_connection(self.__connections.keys()[0])

        if peer in self.__connections and (reader is None or writer is None):
            # Ignore downgrade
            return

        self.__connections.update({peer: (reader, writer)})
    
    async def remove_unused_connections(self):
        peers_to_remove = []

        for p in self.__connections:
            if not await self.is_alive(p):
                peers_to_remove.append(p)

        for p in peers_to_remove:
            self.__connections.pop(p)

    async def remove_connection(self, peer):
        if peer not in self.__connections:
            return
        writer = self.__connections[peer][1]
        if writer is not None and not writer.is_closing():
            try:
                writer.close()
                await writer.wait_closed()
            except:
                pass

        self.__connections.pop(peer)

    async def is_alive(self, peer):
        print("Check for life")
        writer = self.__connections[peer][1]
        # Build PING message
        msg = pack(">HH", 4, MessageType.PING)

        if peer in self.__connections:
            writer = self.__connections[peer][1]
        else:
            reader, writer = await self.establish_connection(peer)

        if writer.is_closing():
            return False

        try:
            writer.write(msg)
            await writer.drain()
        except:
            self.__logger.warn("Error sending to %s" % receiver)
            return False
        return True

    async def establish_connection(self, peer):
        self.__logger.debug("Establish connection with %s" % peer)
        try:
            reader, writer = await asyncio.open_connection(peer.ip, peer.port)
        except:
            self.__logger.warn("Connection with %s cannot be established" % peer)
            self.remove_connection(peer)
            return None, None
        self.update_connection(peer, reader, writer)
        me = writer.get_extra_info('sockname')
        print("I am ", me)
        return reader, writer

    

