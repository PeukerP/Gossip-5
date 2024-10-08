import asyncio
from helper import *
from util import Peer, MessageType
from packing import *
from connection import Connections
from server import Server, APIServer, P2PServer
from unittest import IsolatedAsyncioTestCase, main
from unittest.mock import Mock, patch
from parameterized import parameterized

logger = Mock()

msg_wo_body = b'\x00\x04\x00\x00'
msg_body = b'\x00\x08\x00\x00\x12\x34\x56\x78'
msg_wrong_size1 = b'\x00'
msg_wrong_size2 = b'\x00\x01'
msg_wrong_size3 = b'\x00\x02\x00\x00\x01'
msg_empty = b''
msg_only_size = b'\x00\x04'
msg_missing_pl = b'\x00\x08\x12\34'


class TestServer(IsolatedAsyncioTestCase):

    @parameterized.expand([
        (msg_wo_body, (0, (4, 0, b'', msg_wo_body))),
        (msg_body, (0, (8, 0, b'\x12\x34\x56\x78', msg_body))),
        (msg_wrong_size1, (1, b'')),
        (msg_wrong_size2, (1, b'')),
        (msg_wrong_size3, (1, b'')),
        (msg_empty, (1, b'')),
        (msg_only_size, (1, b'')),
        (msg_missing_pl, (1, b''))
    ])
    async def test__read_msg_1(self, input, output):
        server = Server("Test", "0.0.0.0", 123, Mock(), Mock(), Mock())
        # Do not start server
        r = generate_stream_mock_read(input)
        w = generate_stream_mock_write(False)

        ret = await server._read_msg(r, w)
        assert ret == output

    async def test__read_msg_2(self):
        server = Server("Test", "0.0.0.0", 123, Mock(), Mock(), Mock())
        # Do not start server
        r = generate_stream_mock_read(msg_body)
        w = generate_stream_mock_write(True)

        ret = await server._read_msg(r, w)
        assert ret == (1, b'')

    @parameterized.expand([
        (Peer("0.0.0.0", 123), (None, None), 0),
        (Peer("1.2.3.4", 123), (1, 2), 1)
    ])
    async def test__create_new_connection(self, input, output, called):
        f = asyncio.Future()
        f.set_result("Finished")
        with patch.object(Server, "_handle_receiving", return_value=f):
            with patch.object(Connections, "establish_connection", return_value=(1, 2)):
                server = Server("Test", "0.0.0.0", 123, Mock(), Mock(), Mock())
                # Do not start() server
                ret = await server._create_new_connection(input)
                assert ret == output
                if called == 0:
                    server._handle_receiving.assert_not_called()
                if called == 1:
                    server._handle_receiving.assert_called_once()

    @parameterized.expand([
        (True, False, False),
        (False, True, False),
        (False, False, True),
    ])
    async def test__send_msg_stream(self, is_closing, output, throw_exception):
        f = asyncio.Future()
        f.set_result("Finished")
        with patch.object(Server, "_create_new_connection", return_value=(None, None)):
            server = Server("Test", "0.0.0.0", 123, Mock(), Mock(), Mock())
            r = Mock()
            w = generate_stream_mock_write(is_closing)
            if throw_exception:
                w.write.side_effect = Exception()

            # Do not start() server
            assert await server._send_msg((r, w), msg_empty) == output

            if output:
                w.write.assert_called_once()
                w.drain.assert_called_once()

    @parameterized.expand([
        (Peer("a", 1), False, True, True),
        (Peer("a", 1), False, False, True),
        (Peer("a", 1), True, True, False),
        ("Test", True, False, False)
    ])
    async def test__send_msg_peer_1(self, peer, is_closing, in_list, result):

        r = Mock()
        w = generate_stream_mock_write(is_closing)

        with patch.object(Server, "_create_new_connection", return_value=(r, w)):
            # with patch.object(Connections, "remove_connection", return_value=f):
            server = Server("Test", "0.0.0.0", 123, Mock(), Mock(), Mock())

            if in_list:
                await server._connections.update_connection(peer, r, w)

            # Do not start() server
            assert await server._send_msg(peer, msg_empty) == result

            if not is_closing:
                w.write.assert_called_once()
                w.drain.assert_called_once()
            else:
                w.write.assert_not_called()
                w.drain.assert_not_called()

            if not result:
                assert peer not in server._connections.get_all_connections()

    async def test__send_msg_peer_2(self):
        # Connection cannot be established
        peer = Peer("a", 1)
        with patch.object(Server, "_create_new_connection", return_value=(None, None)):
            server = Server("Test", "0.0.0.0", 123, Mock(), Mock(), Mock())

            await server._connections.update_connection(peer, None, None)

            # Do not start() server
            assert not await server._send_msg(peer, msg_empty)

    async def test__send_msg_peer_3(self):
        # Test send with Exception on write
        with patch.object(Server, "_create_new_connection", return_value=(None, None)):
            server = Server("Test", "0.0.0.0", 123, Mock(), Mock(), Mock())
            r = Mock()
            w = generate_stream_mock_write(False)
            w.write.side_effect = Exception()
            peer = Peer("a", 1)
            await server._connections.update_connection(peer, r, w)

            # Do not start() server
            assert not await server._send_msg(peer, msg_empty)


class TestP2PServer(IsolatedAsyncioTestCase):
    async def test_handle_received_message_GOSSIP_VERIFICATION_REQUEST_1(self):
        with patch('util.PoW.generate_nonce', return_value=0):
            sq = asyncio.Queue()
            rq = asyncio.Queue()
            r = generate_stream_mock_read(None)
            w = generate_stream_mock_write(False)
            server = P2PServer("Test", "127.0.0.1", 6001,
                               5, sq, rq, None, 5, 4)
            msg = (12, 506, b'\x00\x00\x00\x00\x00\x00\x00\x00',
                   b'\x00\x0c\x01\xfa\x00\x00\x00\x00\x00\x00\x00\x00')
            msg_ret = b'\x00\x1a\x01\xfb\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x5c\x4d\xc1\x7f\x00\x00\x01\x17\x71'
            await server._handle_received_message(msg, r, w, Peer("a", 1))

            assert sq.empty()

    async def test_handle_received_message_GOSSIP_VERIFICATION_REQUEST_2(self):
        with patch('util.PoW.generate_nonce', return_value=0):
            sq = asyncio.Queue()
            rq = asyncio.Queue()
            r = generate_stream_mock_read(None)
            w = generate_stream_mock_write(False)
            server = P2PServer("Test", "127.0.0.1", 6001,
                               5, sq, rq, None, 5, 4)
            msg = (12, 506, b'\x00\x00\x00\x00\x00\x00\x00\x00',
                   b'\x00\x0c\x01\xfa\x00\x00\x00\x00\x00\x00\x00\x00')
            msg_ret = b'\x00\x1a\x01\xfb\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x5c\x4d\xc1\x7f\x00\x00\x01\x17\x71'
            await server._connections.update_connection(Peer("a", 1), r, w)

            await server._handle_received_message(msg, r, w, Peer("a", 1))

            assert sq.get_nowait() == (msg_ret, (r, w))

    async def test_handle_received_message_GOSSIP_HELLO(self):
        with patch('util.PoW.generate_nonce', return_value=0):
            sq = asyncio.Queue()
            rq = asyncio.Queue()
            r = generate_stream_mock_read(None)
            w = generate_stream_mock_write(False)
            server = P2PServer("Test", "127.0.0.1", 6001,
                               5, sq, rq, None, 5, 4)
            msg = (10, 508, b'\x7f\x00\x00\x01\x1b\x59',
                   b'\x00\x0a\x01\xfc\x7f\x00\x00\x01\x1b\x59')
            msg_ret = b'\x00\x0c\x01\xfa\x00\x00\x00\x00\x00\x00\x00\x00'

            await server._handle_received_message(msg, r, w, Peer("a", 1))

            assert sq.get_nowait() == (msg_ret, (r, w))
            assert server._pending_validation == {(r, w): 0}

            # Send it again
            await server._handle_received_message(msg, r, w, Peer("a", 1))
            assert sq.empty()
            assert server._pending_validation == {(r, w): 0}

    @parameterized.expand([
        # GOSSIP_VERIFICATION_RESPONSE which is valid
        ((26, 507, b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x5c\x4d\xc1\x7f\x00\x00\x01\x17\x71',
         b'\x00\x1a\x01\xfb\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x5c\x4d\xc1\x7f\x00\x00\x01\x17\x71'),
         b'\x00\n\x01\xf9\x7f\x00\x00\x01\x1b\x59',
         b'\x00\x0c\x01\xfd\x00\x05\x7f\x00\x00\x01\x17\x71',
         True, True, False),
        # GOSSIP_VERIFICATION_RESPONSE with wrong nonce
        ((26, 507, b'\xff\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x5c\x4d\xc1\x7f\x00\x00\x01\x17\x71',
         b'\x00\x1a\x01\xfb\xff\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x5c\x4d\xc1\x7f\x00\x00\x01\x17\x71'),
         b'\x00\n\x01\xf9\x7f\x00\x00\x01\x1b\x59',
         b'\x00\x0c\x01\xfd\x00\x05\x7f\x00\x00\x01\x17\x71',
         False, True, False),
        # GOSSIP_VERIFICATION_RESPONSE with wrong challenge
        ((26, 507, b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\x05\x45\x7f\x00\x00\x01\x17\x71',
         b'\x00\x1a\x01\xfb\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\x05\x45\x7f\x00\x00\x01\x17\x71'),
         b'\x00\n\x01\xf9\x7f\x00\x00\x01\x1b\x59',
         b'\x00\x0c\x01\xfd\x00\x05\x7f\x00\x00\x01\x17\x71',
         False, True, False),
        # GOSSIP_VERIFICATION_RESPONSE which is not registered
        ((26, 507, b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x5c\x4d\xc1\x7f\x00\x00\x01\x17\x71',
         b'\x00\x1a\x01\xfb\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x5c\x4d\xc1\x7f\x00\x00\x01\x17\x71'),
         b'\x00\n\x01\xf9\x7f\x00\x00\x01\x1b\x59',
         b'\x00\x0c\x01\xfd\x00\x05\x7f\x00\x00\x01\x17\x71',
         False, False, False),
        # GOSSIP_VERIFICATION_RESPONSE with wrong challenge and writing is closing
        ((26, 507, b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\x05\x45\x7f\x00\x00\x01\x17\x71',
         b'\x00\x1a\x01\xfb\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\x05\x45\x7f\x00\x00\x01\x17\x71'),
         b'\x00\n\x01\xf9\x7f\x00\x00\x01\x1b\x59',
         b'\x00\x0c\x01\xfd\x00\x05\x7f\x00\x00\x01\x17\x71',
         False, True, True),
    ])
    async def test_handle_received_message_GOSSIP_VERIFICATION_RESPONSE(self, msg, msg_ret1, msg_push, is_valid, is_in_pending, write_fails):
        sq = asyncio.Queue()
        rq = asyncio.Queue()
        r = generate_stream_mock_read(None)
        w = generate_stream_mock_write(False)
        if write_fails:
            w.write.side_effect = Exception()
        server = P2PServer("Test", "127.0.0.1", 6001,
                           5, sq, rq, None, 5, 4)
        await server._connections.update_connection(Peer("127.0.0.1", 0x1b59), None, None)

        if is_in_pending:
            server._pending_validation = {(r, w): 0}

        await server._handle_received_message(msg, r, w, Peer("a", 1))

        assert server._pending_validation == {}

        if is_valid:
            assert sq.get_nowait() == (msg_ret1, Peer("127.0.0.1", 6001))
            assert sq.get_nowait() == (msg_push, [(r, w)])
            assert Peer(
                "127.0.0.1", 6001) in server._connections.get_all_connections()
        else:
            assert sq.empty()
            assert Peer(
                "127.0.0.1", 6001) not in server._connections.get_all_connections()
            w.close.assert_called_once()

    async def test_handle_received_message_GOSSIP_PEER_RESPONSE_0(self):
        sq = asyncio.Queue()
        rq = asyncio.Queue()
        r = generate_stream_mock_read(None)
        w = generate_stream_mock_write(False)
        me = Peer("127.0.0.1", 6001)
        peer_list = [Peer("127.0.0.1", 1), Peer(
            "127.0.0.1", 2), Peer("127.0.0.1", 3)]
        server = P2PServer("Test", "127.0.0.1", 6001,
                           5, sq, rq, None, 5, 4)
        msg = pack_peer_response(peer_list, me)

        await server._handle_received_message((len(msg), MessageType.GOSSIP_PEER_RESPONSE, msg[4:], msg), r, w, Peer("y", 6))
        assert sq.qsize() == 0

    async def test_handle_received_message_GOSSIP_PEER_RESPONSE_1(self):
        sq = asyncio.Queue()
        rq = asyncio.Queue()
        r = generate_stream_mock_read(None)
        w = generate_stream_mock_write(False)
        me = Peer("127.0.0.1", 6001)
        peer_list = [Peer("127.0.0.1", 1), Peer(
            "127.0.0.1", 2), Peer("127.0.0.1", 3)]
        server = P2PServer("Test", "127.0.0.1", 6001,
                           5, sq, rq, None, 5, 4)
        msg = pack_peer_response(peer_list, me)

        await server._handle_received_message((len(msg), MessageType.GOSSIP_PEER_RESPONSE, msg[4:], msg), r, w, Peer("y", 6))
        assert sq.qsize() == 0

    async def test_handle_received_message_GOSSIP_PEER_RESPONSE_1(self):
        sq = asyncio.Queue()
        rq = asyncio.Queue()
        r = generate_stream_mock_read(None)
        w = generate_stream_mock_write(False)
        me = Peer("127.0.0.1", 6001)
        peer_list = [Peer("127.0.0.1", 1), Peer(
            "127.0.0.1", 2), Peer("127.0.0.1", 3)]
        server = P2PServer("Test", "127.0.0.1", 6001,
                           5, sq, rq, None, 5, 4)
        msg = pack_peer_response(peer_list, me)
        await server._connections.update_connection(Peer("a", 1), r, w)

        await server._handle_received_message((len(msg), MessageType.GOSSIP_PEER_RESPONSE, msg[4:], msg), r, w, Peer("y", 6))
        assert sq.qsize() == 3

    @parameterized.expand([
        ([Peer("127.0.0.1", 4), Peer("127.0.0.1", 5), Peer("127.0.0.1", 6)], 1),
        ([Peer("127.0.0.1", 1), Peer("127.0.0.1", 5), Peer("127.0.0.1", 6)], 2)
    ])
    async def test_handle_received_message_GOSSIP_PEER_RESPONSE_2(self, peer_list_resp, queue_S):
        sq = asyncio.Queue()
        rq = asyncio.Queue()
        r = generate_stream_mock_read(None)
        w = generate_stream_mock_write(False)
        me = Peer("127.0.0.1", 6001)
        peer_list = [Peer("127.0.0.1", 1), Peer(
            "127.0.0.1", 2)]
        server = P2PServer("Test", "127.0.0.1", 6001,
                           5, sq, rq, None, 4, 4)
        msg = pack_peer_response(peer_list_resp, me)

        for p in peer_list:
            await server._connections.update_connection(p, None, None)
        await server._connections.update_connection(Peer("127.0.0.1", 3), r, w)

        await server._handle_received_message((len(msg), MessageType.GOSSIP_PEER_RESPONSE, msg[4:], msg), r, w, Peer("y", 6))
        assert sq.qsize() == queue_S

    async def test_handle_received_message_GOSSIP_PEER_RESPONSE_3(self):
        sq = asyncio.Queue()
        rq = asyncio.Queue()
        r = generate_stream_mock_read(None)
        w = generate_stream_mock_write(False)
        me = Peer("127.0.0.1", 6001)
        peer_list = [Peer("127.0.0.1", 1), Peer("127.0.0.1", 2)]
        server = P2PServer("Test", "127.0.0.1", 6001,
                           5, sq, rq, None, 4, 4)
        msg = pack_peer_response([Peer("127.0.0.1", 1)], me)

        for p in peer_list:
            await server._connections.update_connection(p, r, w)

        await server._handle_received_message((len(msg), MessageType.GOSSIP_PEER_RESPONSE, msg[4:], msg), r, w, Peer("y", 6))
        assert sq.qsize() == 0

    @parameterized.expand([
        (4, 2),
        (0, 1)
    ])
    async def test_handle_received_message_GOSSIP_PUSH_1(self, ttl, qsize):
        sq = asyncio.Queue()
        rq = asyncio.Queue()
        r = generate_stream_mock_read(None)
        w = generate_stream_mock_write(False)
        me = Peer("127.0.0.1", 6001)
        other = Peer("127.0.0.1", 6011)
        server = P2PServer("Test", "127.0.0.1", 6001,
                           5, sq, rq, None, 4, 4)
        msg = pack_push_update(other, ttl)
        await server._connections.update_connection(Peer("a", 1), r, w)

        await server._handle_received_message((len(msg), MessageType.GOSSIP_PUSH, msg[4:], msg), r, w, other)

        assert sq.qsize() == qsize
        assert len(server._connections.get_all_connections()) == 2

    async def test_handle_received_message_GOSSIP_PUSH_2(self):
        # Replace in peer list
        sq = asyncio.Queue()
        rq = asyncio.Queue()
        r = generate_stream_mock_read(None)
        w = generate_stream_mock_write(False)
        me = Peer("127.0.0.1", 6001)
        other = Peer("127.0.0.1", 6011)
        peer_list = [Peer("127.0.0.1", 1), Peer(
            "127.0.0.1", 2), Peer("127.0.0.1", 3)]
        server = P2PServer("Test", "127.0.0.1", 6001,
                           5, sq, rq, None, 3, 3)
        msg = pack_push_update(other, 0)

        for p in peer_list:
            await server._connections.update_connection(p, r, w)

        await server._handle_received_message((len(msg), MessageType.GOSSIP_PUSH, msg[4:], msg), r, w, other)

        assert sq.qsize() == 1
        assert other in server._connections.get_all_connections()
        assert len(server._connections.get_all_connections()) == 3

    async def test_handle_received_message_GOSSIP_PUSH_3(self):
        # Does not replace or add anything
        sq = asyncio.Queue()
        rq = asyncio.Queue()
        r = generate_stream_mock_read(None)
        w = generate_stream_mock_write(False)
        me = Peer("127.0.0.1", 6001)
        other = Peer("127.0.0.1", 6011)
        peer_list = [Peer("127.0.0.1", 1), Peer(
            "127.0.0.1", 2), Peer("127.0.0.1", 3)]
        server = P2PServer("Test", "127.0.0.1", 6001,
                           5, sq, rq, None, 3, 3)
        msg = pack_push_update(me, 0)

        for p in peer_list:
            await server._connections.update_connection(p, None, None)

        await server._handle_received_message((len(msg), MessageType.GOSSIP_PUSH, msg[4:], msg), r, w, other)

        assert sq.qsize() == 0
        for p in peer_list:
            assert p in server._connections.get_all_connections()

    async def test_handle_received_message_GOSSIP_PUSH_4(self):
        # Replace in peer list
        sq = asyncio.Queue()
        rq = asyncio.Queue()
        r = generate_stream_mock_read(None)
        w = generate_stream_mock_write(False)
        me = Peer("127.0.0.1", 6001)
        other = Peer("127.0.0.1", 6011)
        peer_list = [Peer("127.0.0.1", 1), Peer(
            "127.0.0.1", 2), Peer("127.0.0.1", 3)]
        server = P2PServer("Test", "127.0.0.1", 6001,
                           5, sq, rq, None, 3, 3)
        msg = pack_push_update(other, 0)

        await server._connections.update_connection(other, r, w)

        await server._handle_received_message((len(msg), MessageType.GOSSIP_PUSH, msg[4:], msg), r, w, other)

        assert sq.qsize() == 0

    async def test_handle_received_message_PING(self):
        sq = asyncio.Queue()
        rq = asyncio.Queue()
        r = generate_stream_mock_read(None)
        w = generate_stream_mock_write(False)
        other = Peer("127.0.0.1", 6011)
        peer_list = [Peer("127.0.0.1", 1), Peer(
            "127.0.0.1", 2), Peer("127.0.0.1", 3)]
        server = P2PServer("Test", "127.0.0.1", 6001,
                           5, sq, rq, None, 3, 3)
        msg = b'\x00\x04\x01\xfe'

        for p in peer_list:
            await server._connections.update_connection(p, None, None)

        await server._handle_received_message((len(msg), MessageType.PING, b'', msg), r, w, other)

        assert sq.empty()
        for p in peer_list:
            assert p in server._connections.get_all_connections()

    async def test_handle_received_message(self):
        sq = asyncio.Queue()
        rq = asyncio.Queue()
        r = generate_stream_mock_read(None)
        w = generate_stream_mock_write(False)
        other = Peer("127.0.0.1", 6011)
        peer_list = [Peer("127.0.0.1", 1), Peer(
            "127.0.0.1", 2), Peer("127.0.0.1", 3)]
        server = P2PServer("Test", "127.0.0.1", 6001,
                           5, sq, rq, None, 3, 3)
        msg = b'\x00\x04\xff\xff'
        t = (len(msg), 0xffff, b'', msg)

        await server._handle_received_message(t, r, w, other)

        assert rq.get_nowait() == (t, (r, w))


if __name__ == "__main__":
    logger.exception.return_value = None
    logger.warning.return_value = None
    main()
