import socket
from struct import pack, unpack
from util import MessageType, Peer, do_pow


def pack_push_update(peer, ttl):
    '''
    Build PUSH_UPDATE
    '''
    msg = b''
    msg += pack(">HH", MessageType.GOSSIP_PUSH, ttl)
    # Schicke neuen Peer mit mit
    msg += socket.inet_aton(peer.ip)
    msg += pack(">H", peer.port)
    msg = pack(">H", 2 + len(msg)) + msg

    return msg


def unpack_push_update(payload):
    '''
    Unpack PUSH_UPDATE to dir:{ttl, addr, port}
    '''
    ttl = unpack(">H", payload[:2])[0]
    ip = socket.inet_ntoa(payload[2:6])
    port = unpack(">H", payload[6:])[0]

    res = {'ttl': ttl, 'addr': ip, 'port': port}
    return res


def pack_hello(peer):
    '''
    Build HELLO with peer
    '''
    msg = b''
    msg += pack(">H", MessageType.GOSSIP_HELLO)
    # Schicke Absender mit
    msg += socket.inet_aton(peer.ip)
    msg += pack(">H", peer.port)

    msg = pack(">H", 2 + len(msg)) + msg

    return msg


def unpack_hello(payload):
    '''
    Unpack HELLO to dir:{addr, port} 
    '''
    ip = socket.inet_ntoa(payload[0:4])
    port = unpack(">H", payload[4:])[0]

    res = {'addr': ip, 'port': port}
    return res


def pack_peer_request():
    msg = b''
    msg += pack(">HL", MessageType.GOSSIP_PEER_REQUEST, 5)  # TODO
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
    '''
    Build PEER_RESPONSE
    :param neighbors: List of peers that should be send 
    :param sender: This peer will be excluded from the sent peer list
    '''
    msg = b''
    msg += pack(">H", MessageType.GOSSIP_PEER_RESPONSE)

    for p in neighbors:
        if p == sender:
            continue
        msg += socket.inet_aton(p.ip)
        msg += pack(">H", p.port)
    msg = pack(">H", 2 + len(msg)) + msg
    return msg


def unpack_peer_response(payload, msg_len):
    '''
    Unpack PEER_RESPONSE into dir:{peer_list} 
    '''
    id = []
    for i in range(0, msg_len - 4, 6):
        addr = socket.inet_ntoa(payload[i:i + 4])
        port = unpack(">H", payload[i + 4:i + 6])[0]
        id.append({'addr': addr, 'port': port})

    res = {'peer_list': id}
    return res


def pack_verification_request(nonce):
    '''
    Build VERIFICATION_REQUEST 
    '''
    msg = pack(">HHQ", 12, MessageType.GOSSIP_VERIFICATION_REQUEST, nonce)
    return msg


def unpack_verification_request(msg):
    '''
    Unpack VERIFICATION_REQUEST in dir:{nonce}
    '''
    nonce = unpack(">Q", msg)[0]
    res = {'nonce': nonce}
    return res


def pack_verification_response(nonce, peer):
    msg = pack(">HQQ", MessageType.GOSSIP_VERIFICATION_RESPONSE, nonce, do_pow(nonce))
    # Schicke Absender mit
    msg += socket.inet_aton(peer.ip)
    msg += pack(">H", peer.port)
    msg = pack(">H", 2 + len(msg)) + msg

    return msg


def unpack_verification_response(msg):
    nonce, challenge = unpack(">QQ", msg[:16])
    addr = socket.inet_ntoa(msg[16:20])
    port = unpack(">H", msg[20:22])[0]

    res = {'nonce': nonce, 'challenge': challenge, 'peer': Peer(addr, port)}
    return res
