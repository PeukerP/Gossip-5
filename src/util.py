from enum import IntEnum
from hashlib import sha256
from random import randint


class MessageType(IntEnum):
    GOSSIP_ANNOUNCE = 500,
    GOSSIP_NOTIFY = 501,
    GOSSIP_NOTIFICATION = 502,
    GOSSIP_VALIDATION = 503,
    GOSSIP_PEER_REQUEST = 504,
    GOSSIP_PEER_RESPONSE = 505,
    GOSSIP_VERIFICATION_REQUEST = 506,
    GOSSIP_VERIFICATION_RESPONSE = 507,
    GOSSIP_HELLO = 508,  # Ich establishe eine connection und schicke mich mit
    GOSSIP_PUSH = 509,
    PING = 510,
    GOSSIP_PEER_NOTIFICATION = 511


class Peer(object):
    def __init__(self, ip: str, port: int):
        self.ip = ip
        self.port = port

    def __repr__(self):
        return "Peer %s:%i" % (self.ip, self.port)

    def __hash__(self):
        return hash(self.__repr__())

    def __eq__(self, peer):
        if type(peer) == Peer:
            if peer.ip == self.ip and peer.port == self.port:
                return True
        return False

    def string(self):
        return self.__repr__()


class Module(object):
    def __init__(self, peer, type_of_data: b""):
        self.peer = peer
        self.type_of_data = type_of_data


class PoW():
    @staticmethod
    def do_pow(nonce: int) -> int:
        n = nonce.to_bytes(8, 'big')
        for i in range(0xffffffffffffffff):
            res = sha256(n + i.to_bytes(8, 'big')).digest()
            if res[0:3] == b'000':
                return i
        return 0

    @staticmethod
    def verify_pow(nonce: int, challenge: int) -> bool:
        sha = sha256(nonce.to_bytes(8, 'big') +
                     challenge.to_bytes(8, 'big')).digest()
        if sha[0:3] != b'000':
            return False
        return True

    @staticmethod
    def generate_nonce() -> int:
        """
        Generate random number and return it
        """
        return randint(0, 0xffffffffffffffff)
