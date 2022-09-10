import asyncio
from helper import *
from util import Peer
from connection import Connections
from server import Server, APIServer
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


class TestServer(IsolatedAsyncioTestCase):

    @parameterized.expand([
        (msg_wo_body, (0, (4, 0, b'', msg_wo_body))),
        (msg_body, (0, (8, 0, b'\x12\x34\x56\x78', msg_body))),
        (msg_wrong_size1, (1, b'')),
        (msg_wrong_size2, (1, b'')),
        (msg_wrong_size3, (1, b'')),
        (msg_empty, (1, b'')),
    ])
    async def test__read_msg(self, input, output):
        server = Server("Test", "0.0.0.0", 123, Mock(), Mock(), Mock())
        # Do not start server
        r = generate_stream_mock_read(input)
        w = generate_stream_mock_write(False)

        ret = await server._read_msg(r, w)
        assert ret == output

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

    async def test__handle_receiving(self):
        # Only test failure since message handling is not implemented by Server
        with patch.object(Server, "_read_msg", return_value=((1, b''))):
            with patch.object(Connections, "is_alive", False):
                server = Server("Test", "0.0.0.0", 123, Mock(), Mock(), Mock())
                r = Mock()
                r.getpeername.return_value=("Test", 123)
                w = Mock()
                w.get_extra_info.return_value=r


#    def TestP2PServer(IsolatedAsyncioTestCase):

if __name__ == "__main__":
    logger.exception.return_value = None
    logger.warning.return_value = None
    main()
