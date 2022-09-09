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
    PING = 510


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


def do_pow(nonce: int) -> int:
    n = nonce.to_bytes(8, 'little')
    for i in range(0xffffffffffffffff):
        res = sha256(n + i.to_bytes(8, 'little')).digest()
        if res[0:3] == b'0' * 3:
            print(i)
            return i
    return 0


def verify_pow(nonce: int, challenge: int) -> bool:
    sha = sha256(nonce.to_bytes(8, 'little') + challenge.to_bytes(8, 'little')).digest()
    print("Verify: ", sha)
    if sha[0:3] != b'000':
        return False
    return True


def generate_nonce():
    '''
    Generate random number and return it
    '''
    return randint(0, 0xffffffffffffffff)
