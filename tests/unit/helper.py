import asyncio
from unittest.mock import Mock

msg = b''


def generate_stream_mock_write(is_closing):
    f = asyncio.Future()
    f.set_result(None)

    mock_s = Mock()
    mock_s.is_closing.return_value = is_closing
    mock_s.close.return_value = None
    mock_s.wait_closed.return_value = f
    mock_s.drain.return_value = f

    return mock_s


def generate_stream_mock_read(message):
    global msg
    msg = message
    mock_s = Mock()
    mock_s.read.side_effect = read_side_effect
    return mock_s


def read_side_effect(size):
    global msg
    f = asyncio.Future()
    ret = msg[:size]
    msg = msg[size:]
    f.set_result(ret)
    return f
