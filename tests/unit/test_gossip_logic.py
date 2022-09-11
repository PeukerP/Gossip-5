import asyncio
from unittest import TestCase

api_recv_queue = asyncio.Queue()
p2p_recv_queue = asyncio.Queue()
api_send_queue = asyncio.Queue()
p2p_send_queue = asyncio.Queue()


class TestGossipHandler(TestCase):
    def test__handle_external(self):
        self.fail()

    def test__handle_internal(self):
        self.fail()

    def test__forward_announce(self):
        self.fail()

    def test__notify(self):
        self.fail()

    def test__send_notification(self):
        self.fail()

    def test__remove_old_waiting(self):
        self.fail()

    def test__validate(self):
        self.fail()

    def test__remove_old_spread(self):
        self.fail()

    def test_start(self):
        self.fail()
