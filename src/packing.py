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

def unpack_push_update(payload):
    ttl = unpack(">H", payload[:2])[0]
    ip = socket.inet_ntoa(payload[2:6])
    port = unpack(">H", payload[6:])[0]

    res = {'ttl': ttl, 'addr': ip, 'port': port}
    return res    

def pack_hello(peer):
    msg = b''
    msg += pack(">H", MessageType.GOSSIP_HELLO)
    # Schicke Absender mit
    msg += socket.inet_aton(peer.ip)
    msg += pack(">H", peer.port)

    msg = pack(">H", 2 + len(msg)) + msg

    return msg

def unpack_hello(payload):
    ip = socket.inet_ntoa(payload[0:4])
    port = unpack(">H", payload[4:])[0]

    res = {'addr': ip, 'port': port}
    return res    

def pack_peer_request():
    msg = b''
    msg += pack(">HL", MessageType.GOSSIP_PEER_REQUEST, self.degree)
    # TODO: sinnvoller Wert für die nonce
    msg += pack(">Q", 0)
    msg = pack(">H", 2 + len(msg)) + msg   
    return msg

def unpack_peer_request(payload):
    degree = unpack(">L", payload[:4])[0]
    nonce = unpack(">L", payload[4:12])[0]

    ret = {'degree': degree, 'nonce': nonce}
    return ret

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


def unpack_peer_response(payload, msg_len):
    id = []
    nonce, challenge, _ = unpack(">QQL", payload[:2*8+4])
    for i in range(2*8+4, msg_len-4, 6):
        addr = socket.inet_ntoa(payload[i:i+4])
        port = unpack(">H", payload[i+4:i+6])[0]
        id.append({'addr':addr, 'port':port})

    res = {'nonce': nonce, 'challenge': challenge, 'peer_list': id}
    return res


