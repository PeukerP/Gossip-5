import socket
from struct import pack, unpack
from util import MessageType, Peer, do_pow

def pack_push_update(peer, ttl):
    msg = b''
    msg += pack(">HH", MessageType.GOSSIP_PUSH, ttl)
    # Schicke neuen Peer mit mit
    msg += socket.inet_aton(peer.ip)
    msg += pack(">H", peer.port)
    msg = pack(">H", 2 + len(msg)) + msg

    return msg

def pack_hello(peer):
    msg = b''
    msg += pack(">H", MessageType.GOSSIP_HELLO)
    # Schicke Absender mit
    msg += socket.inet_aton(peer.ip)
    msg += pack(">H", peer.port)

    msg = pack(">H", 2 + len(msg)) + msg

    return msg

def pack_peer_request():
    msg = b''
    msg += pack(">HL", MessageType.GOSSIP_PEER_REQUEST, self.degree)
    # TODO: sinnvoller Wert für die nonce
    msg += pack(">Q", 0)
    msg = pack(">H", 2 + len(msg)) + msg   
    return msg

def pack_peer_response(neighbors, sender):
    msg = b''
    msg += pack(">HQQ", MessageType.GOSSIP_PEER_RESPONSE, 0, do_pow(0))
    msg += pack(">L", 0)

    for p in neighbors:
        if p == sender:
            continue
        msg += socket.inet_aton(p.ip)
        msg += pack(">H", p.port)
    msg = pack(">H", 2 + len(msg)) + msg
    return msg


