import asyncio
import random
import time

from util import MessageType, Module, Peer


class GossipHandler:

    def __init__(self, p2p_send_queue: asyncio.Queue, p2p_recv_queue: asyncio.Queue, api_send_queue: asyncio.Queue,
                 api_recv_queue: asyncio.Queue, eloop):
        self.notify: [Module] = []
        self.waiting_for_validation: {} = {}
        self.spread: {} = {}
        self.p2p_send_queue: asyncio.Queue = p2p_send_queue
        self.p2p_recv_queue: asyncio.Queue = p2p_recv_queue
        self.api_send_queue: asyncio.Queue = api_send_queue
        self.api_recv_queue: asyncio.Queue = api_recv_queue
        self.eloop = eloop

    async def __handle_external(self, message_type: MessageType, message: bytes):
        if message_type == MessageType.GOSSIP_PEER_NOTIFICATION:
            ttl = int.from_bytes(message[4:5], 'big')
            msg_id: bytes = message[6:8]
            data_type: bytes = message[8:10]
            data: bytes = message[10:]
            if msg_id not in self.spread:
                await self.__send_notification(ttl, msg_id, data_type, data)
        else:
            print("Error: Unknown Message Type.")

    async def __handle_internal(self, message_type: MessageType, sender: Peer, message: bytes):
        if message_type == MessageType.GOSSIP_NOTIFY:
            await self.__notify(sender, message)
        elif message_type == MessageType.GOSSIP_ANNOUNCE:
            await self.__forward_announce(message)
        elif message_type == MessageType.GOSSIP_VALIDATION:
            await self.__validate(message)
        else:
            print("Error: Unknown Message Type.")

    async def __listen_recv_p2p(self):
        while True:
            (size, msg_type, body, message), sender = await self.p2p_recv_queue.get()
            await self.__handle_external(msg_type, message)

    async def __listen_recv_api(self):
        while True:
            (size, msg_type, body, message), sender = await self.api_recv_queue.get()
            await self.__handle_internal(msg_type, sender, message)

    async def __spread_peer_notification(self, msg_id: bytes, message: bytes):
        if msg_id not in self.spread:
            self.spread.update({msg_id: time.time()})
            await self.p2p_send_queue.put((None, message))
        await self.__remove_old_spread()

    async def __forward_announce(self, message: bytes):
        ttl = int.from_bytes(message[4:5], 'big')
        data_type = message[6:8]
        data = message[8:]
        msg_id: bytes = random.randbytes(2)
        await self.__send_notification(ttl, msg_id, data_type, data)

    async def __notify(self, sender: Peer, message: bytes):
        data_type = message[7:9]  # TODO: Check for correctness: Bytes 7&8
        self.notify.append(Module(sender, data_type))

    async def __send_notification(self, ttl: int, msg_id: bytes, data_type: bytes, data: bytes):
        await self.__remove_old_waiting()
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

    async def __remove_old_waiting(self):
        for msg_id in self.waiting_for_validation:  # Remove messages when waiting to long
            if time.time() - self.waiting_for_validation[msg_id] > 300:
                del self.waiting_for_validation[msg_id]

    async def __validate(self, message: bytes):
        msg_id: bytes = message[4:6]
        validation: bool = (message[7:] << 7 >> 7) == (1).to_bytes(1, 'big')
        if msg_id in self.waiting_for_validation:
            if validation:
                peer_notification_message: bytes = self.waiting_for_validation[msg_id][0]
                await self.p2p_send_queue.put((peer_notification_message, None))
                del self.waiting_for_validation[msg_id]
            else:
                del self.waiting_for_validation[msg_id]
        await self.__remove_old_waiting()

    async def __remove_old_spread(self):
        for msg_id in self.spread:
            if time.time() - self.spread[msg_id] > 600:
                del self.spread[msg_id]

    def start(self):
        self.eloop.create_task(self.__listen_recv_p2p())
        self.eloop.create_task(self.__listen_recv_api())
