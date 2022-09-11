import asyncio
from random import choice
from struct import pack
from util import MessageType


class Connections():

    def __init__(self, logger, limit=-1):
        """
        This class manages the peer list. The max number of peers can be limited
        or is unlimited by default.
        :param logger: Set logger for debugging purposes
        :param limit: Set limit for the max number of peers in the peer list
        """
        self.__limit = limit
        self.__connections = {}  # Peer -> read,write stream
        self.__logger = logger

    def __str__(self):
        return str(self.__connections.keys())

    def set_limit(self, limit):
        """
        Sets the max number of peers in the list to limit. Can be only applied if the limit
        has not already been set.
        """
        if self.__limit != -1 or limit < 1:
            return
        self.__limit = limit

    def get_all_connections(self):
        return self.__connections

    def get_streams(self, peer):
        """
        Get r/w streams registered for a peer. If peer is not in peer list, return (None, None)
        """
        if peer in self.__connections:
            return self.__connections[peer]
        else:
            return (None, None)

    def get_capacity(self):
        """
        Get current capacity of peer list. If no limit has been set, return -1.
        """
        if self.__limit == -1:
            return -1
        return self.__limit - len(self.__connections)

    def get_random_peers(self, amount):
        """
        Return a set of min(amount, len(peer list)) peers from the peer list.
        """
        if amount < 0:
            return set()
        res = set()
        iter = 0

        while True:
            if iter == min(amount, len(self.__connections)):
                break
            p = choice(list(self.__connections.keys()))
            if p not in res:
                iter += 1
                res.add(p)
        print(res, len(self.__connections))
        return res

    def add_peer(self, peer):
        """
        Updates peer with None streams.
        This function should be used carefully.
        """
        self.__connections.update({peer: (None, None)})

    async def update_connection(self, peer, reader, writer):
        """
        Adds peer to connections if it is not in connections.

        :param peer: Peer to update
        :param reader: Reader stream
        :param writer: Writer stream
        :return: bool

        Peers can be updated if their streams are None before. Otherwise they can only be
        updated if the previous connection is down. The idea is that there is only one connection
        from one module.
        If the peer cannot be updated due to a alive connection, return False. Otherwise True.
        """
        if len(self.__connections) == self.__limit and peer not in self.__connections:
            # if the connection buffer is still full, remove any connection
            r = self.get_random_peers(1).pop()
            await self.remove_connection(r)

        if peer in self.__connections:
            if reader is None or writer is None:
                # Ignore downgrade
                return True
            elif self.get_streams(peer) != (None, None):
                # Is connection still alive? -> Do not upgrade
                if await self.is_alive(peer):
                    return False
        self.__connections.update({peer: (reader, writer)})
        return True

    """
    never used?

    async def remove_unused_connections(self):
        peers_to_remove = []

        for p in self.__connections:
            if not await self.is_alive(p):
                peers_to_remove.append(p)

        for p in peers_to_remove:
            self.__connections.pop(p)
    """

    async def remove_connection(self, peer):
        """
        Removes peer from the peer list. If there is still an open connection, close it.
        """
        if peer not in self.__connections:
            return
        writer = self.__connections[peer][1]
        if writer is not None and await self.is_alive(peer) and not writer.is_closing():
            self.__logger.debug("Close connection with %s" % peer)
            try:
                writer.close()
                await writer.wait_closed()
            except:
                self.__logger.exception("Problem with closing %s" % peer)

        self.__connections.pop(peer)

    async def is_alive(self, peer=None, stream_tuple=None):
        """
        Checks if the connection is alive. At least one argument must not be None
        :param peer: Peer to check
        :param stream_tuple: Streams (r,w) to check. This is checked when the peer is not given.
        :return: Bool whether connection is alive

        This function checks if a connection is still alive by sending a PING message
        to the writer stream.
        """
        # established = False
        writer = None
        # Build PING message
        msg = pack(">HH", 4, MessageType.PING)

        if peer is None and stream_tuple is None:
            self.__logger.warning("is_alive request for None type")
            return False

        if peer is not None and peer in self.__connections:
            writer = self.__connections[peer][1]
        elif stream_tuple is not None:
            # await self.establish_connection(peer)
            reader, writer = stream_tuple
            # established = True
            # return False
        if writer is None:
            return False

        if writer.is_closing():
            return False

        try:
            writer.write(msg)
            await writer.drain()
        except:
            self.__logger.warning("Error sending to %s" % peer)
            return False
        # if established:
        #   # Schließe connection wieder
        #    try:
        #        writer.close()
        #        await writer.wait_closed()
        #    except:
        #        # TODO
        #        pass

        return True

    async def establish_connection(self, peer):
        """
        Establishes a connection  with peer. Peer needs to be in the peer list.
        If a connection could not be established, remove the peer from the list.
        """
        # Peer has to be in peer list
        if peer not in self.__connections:
            return None, None

        self.__logger.debug("Establish connection with %s" % peer)

        try:
            reader, writer = await asyncio.open_connection(peer.ip, peer.port)
        except:
            self.__logger.exception(
                "Connection with %s cannot be established" % peer)
            await self.remove_connection(peer)
            return None, None
        await self.update_connection(peer, reader, writer)
        me = writer.get_extra_info('sockname')
        print("I am ", me)
        return reader, writer
