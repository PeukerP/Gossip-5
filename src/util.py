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
    GOSSIP_VERIFICATION_RESPONSE = 507


def do_pow(nonce):
    # TODO
    return 0
