import asyncio
import random
import time
from unittest import IsolatedAsyncioTestCase, main
from unittest.mock import MagicMock, patch
from gossip_logic import GossipHandler
from util import Module, MessageType, Peer
from parameterized import parameterized


class TestGossipHandler(IsolatedAsyncioTestCase):

    @staticmethod
    def new_basic_handler():
        return GossipHandler(asyncio.Queue(), asyncio.Queue(), asyncio.Queue(), asyncio.Queue(), None, 600, 60)

    @staticmethod
    def get_data():
        return random.randbytes(10)

    @staticmethod
    def get_data_type_or_msg_id():
        return random.randbytes(2)

    @staticmethod
    def get_valid_ttl():
        return random.randint(1, 3)

    async def test__handle_external(self):
        handler = self.new_basic_handler()
        ttl, msg_id, data_type, data, n, peer_notification = self.__get_send_notification_basics(True, False, True)
        with patch.object(GossipHandler, '_GossipHandler__send_notification') as mock:
            await handler._GossipHandler__handle_external(MessageType.GOSSIP_PEER_NOTIFICATION, None, peer_notification)
        mock.assert_called_with(ttl - 1, msg_id, data_type, data)

        handler.spread.update({msg_id: time.time()})
        with patch.object(GossipHandler, '_GossipHandler__send_notification') as mock:
            await handler._GossipHandler__handle_external(MessageType.GOSSIP_PEER_NOTIFICATION, None, peer_notification)
        mock.assert_not_called()

    async def test__handle_internal(self):
        handler = self.new_basic_handler()
        sender = None
        message = b''
        with patch.object(GossipHandler, '_GossipHandler__notify') as mock:
            await handler._GossipHandler__handle_internal(MessageType.GOSSIP_NOTIFY, sender, message)
        mock.assert_called()

        with patch.object(GossipHandler, '_GossipHandler__forward_announce') as mock:
            await handler._GossipHandler__handle_internal(MessageType.GOSSIP_ANNOUNCE, sender, message)
        mock.assert_called()

        with patch.object(GossipHandler, '_GossipHandler__validate') as mock:
            await handler._GossipHandler__handle_internal(MessageType.GOSSIP_VALIDATION, sender, message)
        mock.assert_called()

    @parameterized.expand([(0,), (1,), (2,), (20,), (50,)])
    async def test__forward_announce(self, ttl: int):
        handler = self.new_basic_handler()
        data_type = self.get_data_type_or_msg_id()
        data = self.get_data()
        message = (18).to_bytes(2, 'big') + (500).to_bytes(2, 'big') + ttl.to_bytes(1, 'big') + b'0' + data_type + data
        handler.notify.append(Module(None, data_type))
        await handler._GossipHandler__forward_announce(message)
        self.assertEqual(1, handler.api_send_queue.qsize())
        if ttl > 0:
            self.assertEqual(1, len(handler.waiting_for_validation))
        else:
            self.assertEqual(0, len(handler.waiting_for_validation))

    def test__notify(self):
        handler = self.new_basic_handler()
        data_type = self.get_data_type_or_msg_id()
        message = (8).to_bytes(2, 'big') + (501).to_bytes(2, 'big') + b'00' + data_type
        sender = Peer("1.1.1.1", 1111)
        handler._GossipHandler__notify(sender, message)
        temp = handler.notify.pop()
        self.assertEqual(sender.port, temp.peer.port)
        self.assertEqual(sender.ip, temp.peer.ip)
        self.assertEqual(data_type, temp.type_of_data)

    @staticmethod
    def __get_send_notification_basics(valid_ttl: bool, get_message: bool, get_peer: bool):
        if valid_ttl:
            ttl = TestGossipHandler.get_valid_ttl()
        else:
            ttl = 0
        msg_id = TestGossipHandler.get_data_type_or_msg_id()
        data_type = TestGossipHandler.get_data_type_or_msg_id()
        data = TestGossipHandler.get_data()
        notification_message = b''
        peer_notification_message = b''
        if get_message:
            notification_message = (18).to_bytes(2, 'big') + (502).to_bytes(2, 'big') + msg_id + data_type + data
        if get_peer and valid_ttl:
            peer_notification_message = (20).to_bytes(2, 'big') + (511).to_bytes(2, 'big') + (ttl - 1).to_bytes(
                1, 'big') + (0).to_bytes(1, 'big') + msg_id + data_type + data
        elif get_peer:
            print("get_peer can only be used with valid_ttl.")
            raise RuntimeError("get_peer can only be used with valid_ttl.")
        return ttl, msg_id, data_type, data, notification_message, peer_notification_message

    async def test__send_notification_no_notifiers(self):
        handler = self.new_basic_handler()
        ttl, msg_id, data_type, data, notification, peer_notification = self.__get_send_notification_basics(True, False,
                                                                                                            False)

        await handler._GossipHandler__send_notification(ttl, msg_id, data_type, data)

        self.assertTrue(handler.api_send_queue.empty())
        self.assertTrue(handler.p2p_send_queue.empty())
        self.assertEqual(0, len(handler.waiting_for_validation))

    @parameterized.expand([(True,), (False,)])
    async def test__send_notification_single_notifier(self, valid_ttl: bool):
        handler = self.new_basic_handler()
        ttl, msg_id, data_type, data, notification, peer_notification = self.__get_send_notification_basics(valid_ttl,
                                                                                                            True,
                                                                                                            valid_ttl)
        handler.notify.append(Module(None, data_type))
        await handler._GossipHandler__send_notification(ttl, msg_id, data_type, data)
        if ttl > 0:
            self.assertEqual(1, len(handler.waiting_for_validation))  # TTL > 0 -> spread message
            self.assertEqual(peer_notification, handler.waiting_for_validation.get(msg_id)[0])
        else:
            self.assertEqual(0, len(handler.waiting_for_validation))
        self.assertEqual(1, handler.api_send_queue.qsize())
        self.assertTrue(handler.p2p_send_queue.empty())
        temp = await handler.api_send_queue.get()
        self.assertEqual(notification, temp[0])

    async def test__send_notification_single_false_notifier(self):
        handler = self.new_basic_handler()
        ttl, msg_id, data_type, data, notification, peer_notification = self.__get_send_notification_basics(True, False,
                                                                                                            False)
        false_data_type = self.get_data_type_or_msg_id()
        while false_data_type == data_type:
            false_data_type = self.get_data_type_or_msg_id()
        handler.notify.append(Module(None, false_data_type))
        await handler._GossipHandler__send_notification(ttl, msg_id, data_type, data)
        self.assertEqual(0, len(handler.waiting_for_validation))
        self.assertEqual(0, handler.api_send_queue.qsize())
        self.assertTrue(handler.p2p_send_queue.empty())

    @parameterized.expand([(True,), (False,)])
    async def test__send_notification_multiple_notifiers(self, valid_ttl: bool):
        handler = self.new_basic_handler()
        ttl, msg_id, data_type, data, notification, peer_notification = self.__get_send_notification_basics(valid_ttl,
                                                                                                            True,
                                                                                                            valid_ttl)
        false_data_type = self.get_data_type_or_msg_id()
        while false_data_type == data_type:
            false_data_type = self.get_data_type_or_msg_id()
        handler.notify.append(Module(None, false_data_type))
        handler.notify.append(Module(None, data_type))
        handler.notify.append(Module(None, data_type))
        handler.notify.append(Module(None, false_data_type))

        await handler._GossipHandler__send_notification(ttl, msg_id, data_type, data)

        if ttl:
            self.assertEqual(1, len(handler.waiting_for_validation))
            self.assertEqual(peer_notification, handler.waiting_for_validation.get(msg_id)[0])
        else:
            self.assertEqual(0, len(handler.waiting_for_validation))
        self.assertEqual(2, handler.api_send_queue.qsize())
        temp = await handler.api_send_queue.get()
        self.assertEqual(notification, temp[0])
        self.assertTrue(handler.p2p_send_queue.empty())

    def test__remove_old_waiting_stay(self):
        handler = self.new_basic_handler()
        handler.waiting_for_validation.update({(1).to_bytes(1, 'big'): ("1".encode(), time.time())})
        handler.waiting_for_validation.update({(2).to_bytes(1, 'big'): ("2".encode(), time.time())})
        handler._GossipHandler__remove_old_waiting()
        self.assertEqual(2, len(handler.waiting_for_validation))

    def test__remove_old_waiting_leave(self):
        handler = self.new_basic_handler()
        handler.waiting_for_validation.update({(1).to_bytes(1, 'big'): ("1".encode(), time.time() - 60)})
        testtime = time.time()
        handler.waiting_for_validation.update({(2).to_bytes(1, 'big'): ("2".encode(), testtime)})
        handler._GossipHandler__remove_old_waiting()
        self.assertEqual(1, len(handler.waiting_for_validation))
        self.assertTrue((2).to_bytes(1, 'big') in handler.waiting_for_validation)
        self.assertEqual(("2".encode(), testtime), handler.waiting_for_validation[(2).to_bytes(1, 'big')])

    @parameterized.expand([(True,), (False,)])
    async def test__validate(self, valid: bool):
        handler = self.new_basic_handler()
        msg_id = self.get_data_type_or_msg_id()
        mock_message = self.get_data()
        handler.waiting_for_validation.update({msg_id: (mock_message, time.time())})
        message = (8).to_bytes(2, 'big') + (503).to_bytes(2, 'big') + msg_id
        if valid:
            message += (1).to_bytes(2, 'big')
            with patch.object(GossipHandler, '_GossipHandler__remove_old_spread') as mock:
                await handler._GossipHandler__validate(message)
            mock.assert_called()
            self.assertTrue(msg_id in handler.spread)
            temp = await handler.p2p_send_queue.get()
            self.assertEqual(mock_message, temp[0])
        else:
            message += (0).to_bytes(2, 'big')
            logger = MagicMock()
            handler.logger = logger
            await handler._GossipHandler__validate(message)
            logger.warning.assert_called_with(
                "Message validation failed, message will be removed and not send: msgID %s", msg_id)

    def test__remove_old_spread_stay(self):
        handler = self.new_basic_handler()
        msg_id_a = self.get_data_type_or_msg_id()
        msg_id_b = self.get_data_type_or_msg_id()
        handler.spread.update({msg_id_a: time.time()})
        handler.spread.update({msg_id_b: time.time()})
        handler._GossipHandler__remove_old_spread()
        self.assertEqual(2, len(handler.spread))

    def test__remove_old_spread_leave(self):
        handler = self.new_basic_handler()
        msg_id_a = self.get_data_type_or_msg_id()
        msg_id_b = self.get_data_type_or_msg_id()
        handler.spread.update({msg_id_a: time.time() - 600})
        handler.spread.update({msg_id_b: time.time()})
        handler._GossipHandler__remove_old_spread()
        self.assertEqual(1, len(handler.spread))
        self.assertTrue(msg_id_b in handler.spread)


if __name__ == "__main__":
    main()
