import logging
import asyncio
from connection import Connections
from unittest import IsolatedAsyncioTestCase, main
from unittest.mock import Mock, patch

logger = logging.getLogger("Test")


class TestConnections(IsolatedAsyncioTestCase):

    def test_get_capacity(self):
        c = Connections(logger)
        assert c.get_capacity() == -1

    def test_set_limit(self):
        c = Connections(logger)
        c.set_limit(2)
        assert c.get_capacity() == 2
        c.set_limit(6)
        assert c.get_capacity() == 2

    async def test_update_connection_alive(self):
        with patch.object(Connections, "is_alive", return_value=True):
            c = Connections(logger)

            await c.update_connection("a", None, None)
            assert c.get_all_connections() == {"a": (None,None)}
            # Test upgrade
            await c.update_connection("a", 1, 1)
            assert c.get_all_connections() == {"a": (1,1)}
            # Test no overwrite
            await c.update_connection("a", 1, 2)
            assert c.get_all_connections() == {"a": (1,1)}

            await c.update_connection("b", 2, 2)
            assert c.get_all_connections() == {"a": (1,1), "b": (2,2)}

    async def test_update_connection_overwrite(self):
        with patch.object(Connections, "is_alive", return_value=False):
            c = Connections(logger)

            await c.update_connection("a", None, None)
            assert c.get_all_connections() == {"a": (None,None)}

            await c.update_connection("a", 1, 1)
            assert c.get_all_connections() == {"a": (1,1)}
            # Test overwrite
            await c.update_connection("a", 1, 2)
            assert c.get_all_connections() == {"a": (1,2)}

            await c.update_connection("b", 2, 2)
            assert c.get_all_connections() == {"a": (1,2), "b": (2,2)}

    async def test_update_connection_limit_not_alive(self):
        with patch.object(Connections, "is_alive", return_value=False):
            # Stream Mock
            mock_s = Mock()
            mock_s.is_closing.return_value=False

            c = Connections(logger)
            c.set_limit(1)
            await c.update_connection("a", None, None)
            assert c.get_all_connections() == {"a": (None,None)}

            await c.update_connection("a", 1, mock_s)
            assert c.get_all_connections() == {"a": (1,mock_s)}

            await c.update_connection("b", 1, 1)
            assert c.get_all_connections() == {"b": (1,1)}

    async def test_update_connection_limit_alive(self):
        with patch.object(Connections, "is_alive", return_value=True):
            # Stream Mock
            f = asyncio.Future()
            f.set_result(None)
            mock_s = Mock()
            mock_s.is_closing.return_value=False
            mock_s.close.return_value=None
            mock_s.wait_closed.return_value=f

            c = Connections(logger)
            c.set_limit(1)
            await c.update_connection("a", None, None)
            assert c.get_all_connections() == {"a": (None,None)}

            await c.update_connection("a", 1, mock_s)
            assert c.get_all_connections() == {"a": (1,mock_s)}

            await c.update_connection("b", 1, 1)
            assert c.get_all_connections() == {"b": (1,1)}

    async def test_get_random_peers(self):
        c = Connections(logger)
        await c.update_connection("a", 1, 1)

        assert c.get_random_peers(1) == set(["a"])
        assert c.get_random_peers(2) == set(["a"])
        assert c.get_random_peers(-2) == set()

        await c.update_connection("b", 2, 2)

        assert len(c.get_random_peers(1)) == 1
        assert c.get_random_peers(2) == set(["a", "b"])

    async def test_remove_connection_None(self):
        c = Connections(logger)
        mock = Mock()
        mock.is_closing.return_value=False
        await c.update_connection("a", None, None)
        await c.remove_connection("a")
        assert c.get_all_connections() == {}

    async def test_remove_connection(self):
        with patch.object(Connections, "is_alive", return_value=True):
            c = Connections(logger)
            mock = Mock()
            mock.is_closing.return_value=False
            await c.update_connection("a", 1, mock)
            await c.remove_connection("a")
            assert c.get_all_connections() == {}

    async def test_remove_connection_not_in(self):
        c = Connections(logger)
        mock = Mock()
        mock.is_closing.return_value=False
        await c.update_connection("a", 0, mock)
        await c.remove_connection("b")
        assert c.get_all_connections() == {"a": (0, mock)}

    async def test_is_alive_1(self):
        # Peer exists in list and is alive
        # Stream Mock
        f = asyncio.Future()
        f.set_result(None)

        mock_s = Mock()
        mock_s.is_closing.return_value=False
        mock_s.close.return_value=None
        mock_s.wait_closed.return_value=f
        mock_s.write.return_value=None
        mock_s.drain.return_value=f

        with patch.object(Connections, "establish_connection", return_value=(Mock(), mock_s)):
            c = Connections(logger)
            await c.update_connection("a", 0, mock_s)
            assert await c.is_alive("a") == True
            mock_s.close.assert_not_called()
            mock_s.wait_closed.assert_not_called()
            
    async def test_is_alive_2(self):
        # Peer does not exist in list, but is alive
        # Stream Mock
        f = asyncio.Future()
        f.set_result(None)

        mock_s = Mock()
        mock_s.is_closing.return_value=False
        mock_s.close.return_value=None
        mock_s.wait_closed.return_value=f
        mock_s.write.return_value=None
        mock_s.drain.return_value=f

        with patch.object(Connections, "establish_connection", return_value=(Mock(), mock_s)):
            c = Connections(logger)
            assert await c.is_alive("a") == True
            mock_s.close.assert_called_once()
            mock_s.wait_closed.assert_called_once()

    async def test_is_alive_3(self):
        # Peer exist in list and is not alive
        # Stream Mock
        f = asyncio.Future()
        f.set_result(None)

        mock_s = Mock()
        mock_s.is_closing.return_value=False
        mock_s.close.return_value=None
        mock_s.wait_closed.return_value=f
        mock_s.write.side_effect=Exception
        mock_s.drain.return_value=f

        with patch.object(Connections, "establish_connection", return_value=(None, None)):
            c = Connections(logger)
            await c.update_connection("a", 0, mock_s)
            assert await c.is_alive("a") == False


    async def test_is_alive_4(self):
        # Peer exist not list and is not alive
        # Stream Mock
        f = asyncio.Future()
        f.set_result(None)

        mock_s = Mock()
        mock_s.is_closing.return_value=False
        mock_s.close.return_value=None
        mock_s.wait_closed.return_value=f
        mock_s.write.side_effect=Exception
        mock_s.drain.return_value=f

        with patch.object(Connections, "establish_connection", return_value=(None, mock_s)):
            c = Connections(logger)
            assert await c.is_alive("a") == False
            mock_s.close.assert_not_called()
            mock_s.wait_closed.assert_not_called()

    async def test_establish_connection_1(self):
        c = Connections(logger)
        assert await c.establish_connection("a") == (None, None)


    async def test_establish_connection_2(self):
        # Connection works
        # Stream Mock
        
        mock = Mock()
        mock.get_extra_info.return_value="Test"

        peer  = Mock()
        peer.ip="Test"
        peer.port="123"

        with patch("asyncio.open_connection", return_value=(mock,mock)):
            c = Connections(logger)
            await c.update_connection(peer, None, None)
            assert await c.establish_connection(peer) == (mock, mock)
            assert c.get_all_connections() == {peer: (mock,mock)}

    async def test_establish_connection_3(self):
        # Connection fails
        # Stream Mock
        
        mock = Mock()
        mock.get_extra_info.return_value="Test"

        peer  = Mock()
        peer.ip="Test"
        peer.port="123"

        with patch("asyncio.open_connection", side_effect=Exception):
            c = Connections(logger)
            await c.update_connection(peer, None, None)
            assert await c.establish_connection(peer) == (None, None)
            assert c.get_all_connections() == {}
    
if __name__ == "__main__":
    main()
    
        

    

    

        

