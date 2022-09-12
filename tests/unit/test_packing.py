from packing import *
from util import Peer
from unittest import TestCase


class TestPacking(TestCase):
    def test_pack_push_update(self):
        msg = pack_push_update(Peer("127.0.0.1", 0x1b59), 1)
        msg_val = b'\x00\x0c\x01\xfd\x00\x01\x7f\x00\x00\x01\x1b\x59'
        assert msg == msg_val

    def test_unpack_push_update(self):
        msg = b'\x00\x01\x7f\x00\x00\x01\x1b\x59'
        data = unpack_push_update(msg)
        assert data['ttl'] == 1
        assert data['addr'] == "127.0.0.1"
        assert data['port'] == 0x1b59

    def test_pack_hello(self):
        msg = pack_hello(Peer("127.0.0.1", 0x1b59))
        msg_val = b'\x00\x0a\x01\xfc\x7f\x00\x00\x01\x1b\x59'
        assert msg == msg_val

    def test_unpack_hello(self):
        msg = b'\x7f\x00\x00\x01\x1b\x59'
        data = unpack_hello(msg)
        assert data['addr'] == "127.0.0.1"
        assert data['port'] == 0x1b59

    def test_pack_peer_response(self):
        peers = [Peer("127.0.0.1", 0x1b59), Peer("127.0.0.1", 0x1b60)]
        msg = pack_peer_response(peers, Peer("127.0.0.1", 0x1b60))
        msg_val = b'\x00\n\x01\xf9\x7f\x00\x00\x01\x1b\x59'
        assert msg == msg_val

    def test_unpack_peer_response(self):
        msg = b'\x7f\x00\x00\x01\x1b\x59'
        peers = [{'addr': '127.0.0.1', 'port': 7001}]
        data = unpack_peer_response(msg, len(msg)+4)
        assert data['peer_list'] == peers

    def test_pack_verification_request(self):
        msg = pack_verification_request(0)
        msg_val = b'\x00\x0c\x01\xfa\x00\x00\x00\x00\x00\x00\x00\x00'
        assert msg == msg_val

    def test_unpack_verification_request(self):
        msg = b'\x00\x00\x00\x00\x00\x00\x00\x00'
        data = unpack_verification_request(msg)
        assert data['nonce'] == 0

    def test_pack_verification_response(self):
        msg = pack_verification_response(0, Peer("127.0.0.1", 0x1b60))
        msg_val = b'\x00\x1a\x01\xfb\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x5c\x4d\xc1\x7f\x00\x00\x01\x1b\x60'
        assert msg == msg_val

    def test_unpack_verification_response(self):
        msg = b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\x05\x45\x7f\x00\x00\x01\x1b\x60'
        data = unpack_verification_response(msg)
        assert data['nonce'] == 0
        assert data['challenge'] == 66885
        assert data['peer'] == Peer("127.0.0.1", 0x1b60)


if __name__ == '__main__':
    main()
