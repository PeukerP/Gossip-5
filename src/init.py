import asyncio

from connection import API_Server

# TODO: init and bootstrapping
# This is only a temporary file. Will be improved.

HOST = "127.0.0.1"
PORT = 7001

p2p_send_queue = asyncio.PriorityQueue()
p2p_recv_queue = asyncio.PriorityQueue()
api_send_queue = asyncio.PriorityQueue()
api_recv_queue = asyncio.PriorityQueue()

p2p_send_lock = asyncio.Lock()
p2p_recv_lock = asyncio.Lock()
api_send_lock = asyncio.Lock()
api_recv_lock = asyncio.Lock()


api_server = API_Server(HOST, PORT, api_send_queue, api_recv_queue, api_send_lock, api_recv_lock)
api_server.start()




