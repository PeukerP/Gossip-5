from enum import IntEnum

class MessageType(IntEnum):
    GOSSIP_ANNOUNCE = 500,
    GOSSIP_NOTIFY = 501,
    GOSSIP_NOTIFICATION = 502,
    GOSSIP_VALIDATION = 503