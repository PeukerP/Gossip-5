from enum import IntEnum
from hashlib import sha256

class MessageType(IntEnum):
    GOSSIP_ANNOUNCE = 500,
    GOSSIP_NOTIFY = 501,
    GOSSIP_NOTIFICATION = 502,
    GOSSIP_VALIDATION = 503,
    GOSSIP_PEER_REQUEST = 504,
    GOSSIP_PEER_RESPONSE = 505,
    GOSSIP_VERIFICATION_REQUEST = 506,
    GOSSIP_VERIFICATION_RESPONSE = 507,
    GOSSIP_HELLO = 508, # Ich establishe eine connection und schicke mich mit
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

def do_pow(nonce):
    # TODO
    return 0
