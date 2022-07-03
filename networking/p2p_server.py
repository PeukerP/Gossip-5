import asyncio
from struct import unpack


class P2PServer():

    def __init__(self, host, port):

        self.host = host
        self.port = port
        # Irgendwie müssen connctions verwaltet werden.
        # Solange bis klar, wie genau, ist das ein set aus (reader, writer)
        self.connections = {}
        self.connections_lock = asyncio.Lock()

    def establish_connection(self, host, port):
        pass

    def send_msg(self, addr, port, message):
        writer = None
        if (addr, port) in self.connections:
            writer = self.connections[(addr, port)]
        else:
            writer = self.establish_connection(addr, port)

        if writer.is_closing():
            return ""
        writer.write(message)
        await writer.drain()

    def read_msg(self, reader, writer):
        # TODO: error handling
        # Whether connection is open can only be tested with writer
        if writer.is_closing():
            return ""

        msg_size = reader.read(2)
        size = unpack(">H", msg_size)[0]
        msg = msg_size + reader.read(size)
            
        return msg

    async def handle_connection(self, reader : asyncio.StreamReader,  writer : asyncio.StreamWriter):
         addr, port = writer.get_extra_info('socket').getpeername()
        # Register connection
        async with self.connections_lock:
            self.connctions.update({(addr, port) : (reader, writer)})

        # Read and hand over to api layer



    def start(self):
        eloop = asyncio.get_event_loop()
        server = asyncio.start_server(self.handle_connection,
                                      host=self.host,
                                      port=self.port,
                                      family=socket.AddressFamily.AF_INET,
                                      reuse_address=True,
                                      reuse_port=True)
        eloop.create_task(server)
        try:
            eloop.run_forever()
        except KeyboardInterrupt as e:
            eloop.stop()
