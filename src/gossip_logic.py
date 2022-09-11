import asyncio
import logging
import random
import time

from util import MessageType, Module, Peer


class GossipHandler:

    def __init__(self, p2p_send_queue: asyncio.Queue, p2p_recv_queue: asyncio.Queue, api_send_queue: asyncio.Queue,
                 api_recv_queue: asyncio.Queue, eloop, suppress_circular_messages_time: int, validation_wait_time: int):
        """
        This class manages the deliverance of "GOSSIP" type packages as defined in the project specification.

        :param p2p_send_queue: Queue to put messages that have to be sent. Type: (message: bytes, receiver: Peer) where
        a broadcast to all peers is done with a "None" as peer.
        :param p2p_recv_queue: Queue to get peer messages from that have to be handled. Type: ((msg), sender: Peer)
        :param api_send_queue: Like p2p_send_queue but for Modules instead of peers.
        :param api_recv_queue: Like p2p_recv_queue but for Modules instead of peers.
        :param eloop: EventLoop for coroutine execution.
        :param suppress_circular_messages_time: time in seconds for how long a messageID should be suppressed from
        resending to avoid circular messages.
        :param validation_wait_time: time in seconds for how long a message shall be kept back until it was validated by
        a module
        """
        self.notify: [Module] = []  # List with Modules which shall be notified. Type = [Module]
        self.waiting_for_validation: {bytes: (bytes, float)} = {}
        # Dictionary of messages with timestamp that are waiting for validation to be spread.
        # Type = {msgID: (message, timestamp)}
        self.spread: {bytes: float} = {}
        # Dictionary of messages with timestamp that already have been spread. Type = {msgID: timestamp}
        self.logger = logging.getLogger(type(self).__name__)
        self.p2p_send_queue: asyncio.Queue = p2p_send_queue
        self.p2p_recv_queue: asyncio.Queue = p2p_recv_queue
        self.api_send_queue: asyncio.Queue = api_send_queue
        self.api_recv_queue: asyncio.Queue = api_recv_queue
        self.eloop = eloop
        self.suppress_circular_messages_time = suppress_circular_messages_time
        self.validation_wait_time = validation_wait_time

    async def _handle_external(self, message_type: MessageType, sender: Peer, message: bytes):
        """
        Handler to process messages from p2p_recv_queue.

        :param message_type: A MessageType object like defined in util.py for Type validation.
        :param message: The received p2p message as bytes.
        """
        if message_type == MessageType.GOSSIP_PEER_NOTIFICATION:  # Handle GOSSIP_PEER_NOTIFICATION
            ttl = int.from_bytes(message[4:5], 'big')
            msg_id: bytes = message[6:8]
            data_type: bytes = message[8:10]
            data: bytes = message[10:]
            if msg_id not in self.spread:
                await self._send_notification(ttl, msg_id, data_type, data)
        else:  # MessageType unknown or illegal
            self.logger.warning("Unknown or illegal MessageType received from other peer(%s): %s", sender, message_type)

    async def _handle_internal(self, message_type: MessageType, sender: Peer, message: bytes):
        """
        Handler to process messages from api_recv_queue.

        :param message_type: A MessageType object like defined in util.py for Type validation.
        :param sender: The sender of the message as Peer object.
        :param message: The received qpi message as bytes.
        """
        if message_type == MessageType.GOSSIP_NOTIFY:
            self._notify(sender, message)
        elif message_type == MessageType.GOSSIP_ANNOUNCE:
            await self._forward_announce(message)
        elif message_type == MessageType.GOSSIP_VALIDATION:
            await self._validate(message)
        else:
            self.logger.warning("Unknown or illegal MessageType received from module(%s): %s", sender, message_type)

    async def __listen_recv_p2p(self):
        """
        Listen loop for p2p_recv_queue.
        """
        while True:
            (size, msg_type, body, message), sender = await self.p2p_recv_queue.get()
            await self._handle_external(msg_type, sender, message)

    async def __listen_recv_api(self):
        """
        Listen loop for api_recv_queue.
        """
        while True:
            (size, msg_type, body, message), sender = await self.api_recv_queue.get()
            await self._handle_internal(msg_type, sender, message)

    async def _forward_announce(self, message: bytes):
        """
        Handles a received GOSSIP_ANNOUNCE message. Generates a new messageID and calls send_notification()

        :param message: The received GOSSIP_ANNOUNCE message as bytes.
        """
        ttl = int.from_bytes(message[4:5], 'big')
        data_type = message[6:8]
        data = message[8:]
        msg_id: bytes = random.randbytes(2)
        await self._send_notification(ttl + 1, msg_id, data_type, data)

    def _notify(self, sender: Peer, message: bytes):
        """
        Consumes a received GOSSIP_NOTIFY message and saves the Module to be notified

        :param sender: The sending module as Peer from util.py.
        :param message: The received GOSSIP_NOTIFY message as bytes
        """
        data_type = message[6:8]
        self.notify.append(Module(sender, data_type))

        self.logger.debug("Module %s asked to get notified for data type %s", sender, data_type)

    async def _send_notification(self, ttl: int, msg_id: bytes, data_type: bytes, data: bytes):
        """
        Sends GOSSIP_NOTIFICATION to Modules which are to be notified for given data_type. Stores message in temporary
        dictionary to spread the message to other peers when it can be validated.
        A message with a data_type not registered by any Module will not be spread in any way.

        :param ttl: The ttl defined by the received message which will be used while spreading to other peers as int.
        :param msg_id: The random messageID user for identification of circulating messages as bytes.
        :param data_type: The data_type of the message to be spread as bytes.
        :param data: The data of the message to be spread as bytes.
        """
        self._remove_old_waiting()
        validate: bool = False
        message: bytes = MessageType.GOSSIP_NOTIFICATION.to_bytes(2, 'big') + msg_id + data_type + data
        message = (len(message) + 2).to_bytes(2, 'big') + message
        for module in self.notify:
            if module.type_of_data == data_type:
                await self.api_send_queue.put((message, module.peer))
                if not validate:
                    validate = True
        if validate and ttl > 0:  # When it has been sent, wait for validation to send to others
            peer_message: bytes = MessageType.GOSSIP_PEER_NOTIFICATION.to_bytes(2, 'big') + \
                                  (ttl - 1).to_bytes(1, 'big') + b'0' + msg_id + data_type + data
            peer_message = (len(peer_message) + 2).to_bytes(2, 'big') + peer_message
            self.waiting_for_validation.update({msg_id: (peer_message, time.time())})
            self.logger.debug("Message is waiting for validation: msgID %s ", msg_id)

    def _remove_old_waiting(self):
        """
        Removes expired messages that are waiting for validation from the dictionary after defined time in
        validation_wait_time.
        """
        for msg_id in self.waiting_for_validation:  # Remove messages when waiting to long
            if time.time() - self.waiting_for_validation[msg_id] > self.validation_wait_time:
                del self.waiting_for_validation[msg_id]
                self.logger.debug("Removed old message from spread list: msgID %s", msg_id)

    async def _validate(self, message: bytes):
        """
        Consumes a GOSSIP_VALIDATION message and checks for the validation bit. Releases a GOSSIP_PEER_NOTIFICATION
        message if the validation bit is set and a message with given messageID is waiting for validation.

        :param message: The received GOSSIP_VALIDATION message as bytes.
        """
        msg_id: bytes = message[4:6]
        validation: bool = int.from_bytes(message[7:], 'big') == 1
        if msg_id in self.waiting_for_validation:
            if validation:
                peer_notification_message: bytes = self.waiting_for_validation[msg_id][0]
                await self.p2p_send_queue.put((peer_notification_message, None))
                self.spread.update({msg_id: time.time()})
                self.logger.debug("Message was spread: msgID %s ", msg_id)
                self.logger.debug("Sent validated message from waiting list: msgID %s", msg_id)
                self._remove_old_spread()
            else:
                self.logger.warning("Message validation failed, message will be removed and not send: msgID %s", msg_id)
            del self.waiting_for_validation[msg_id]

    def _remove_old_spread(self):
        """
        Removes expired messageIDs from the dictionary with already spread messages after defined time in
        suppress_circular_messages_time.
        """
        for msg_id in self.spread:
            if time.time() - self.spread[msg_id] > self.suppress_circular_messages_time:
                del self.spread[msg_id]
                self.logger.debug("Removed old msgID from spread list: %s", msg_id)

    def start(self):
        """
        Start method to create coroutine tasks for both recv_queues.
        """
        self.eloop.create_task(self.__listen_recv_p2p())
        self.eloop.create_task(self.__listen_recv_api())
