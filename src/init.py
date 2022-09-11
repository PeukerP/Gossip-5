import asyncio
import re
import socket
import logging
import os
from argparse import ArgumentParser
from configobj import ConfigObj

from server import P2PServer, APIServer
from gossip_logic import GossipHandler


def split_address_into_tuple(address):
    pattern_v4_ip = r"([\d]{1-3}.[\d]{1-3}.[\d]{1-3}.[\d]{1-3}):([\d]+)"
    pattern_name = r"([\w.-]+):([\d]+)"

    res = re.match(pattern_v4_ip, address)
    if res is None:
        # try name
        res = re.match(pattern_name, address)
    if res is None:
        print("%s has the wrong format" % address)
        exit(1)

    entry = socket.getaddrinfo(res.group(1), int(res.group(2)))
    if len(entry) == 0:
        print("Cannot get information about %s:%s" %
              res.group(1), res.group(2))
        exit(1)

    addr, port = entry[0][4]
    return addr, port


def parse_config_file(config_file):
    options = ['cache_size', 'degree', 'bootstrapper', 'p2p_address', 'api_address']
    config = ConfigObj(config_file)
    if 'gossip' not in config:
        print("section 'gossip' is missing in .ini file")
        exit(1)

    if 'hostkey' not in config:
        print("'hostkey' is missing in .ini file")
        exit(1)

    hostkey = config['hostkey']

    # Read the value to the corresponding global variables
    for o in options:
        if o in config['gossip']:
            globals()[o] = config['gossip'][o]
        else:
            if o != 'bootstrapper':
                print("'%s' is missing in .ini file" % o)
                exit(1)

    # Split the addresses into tuples

    p2p_addr = split_address_into_tuple(p2p_address)
    api_addr = split_address_into_tuple(api_address)

    if 'bootstrapper' in config['gossip']:
        bootstr = split_address_into_tuple(bootstrapper)

        return {'cache_size': int(cache_size), 'degree': int(degree), 'bootstrapper': bootstr,
                'p2p_address': p2p_addr, 'api_address': api_addr}
    else:
        return {'cache_size': int(cache_size), 'degree': int(degree), 'bootstrapper': None,
                'p2p_address': p2p_addr, 'api_address': api_addr}


def main():
    parser = ArgumentParser()
    # Read the command line arguments:
    # For config file path
    parser.add_argument('-c', dest='config_file',
                        help='Give the path to the configuration file.', type=str, required=True)
    # For GossipHandler.validation_wait_time
    parser.add_argument('-v', dest='validation_time', help="Time in seconds to wait for a message to be validated.",
                        type=int, default=60)
    # For GossipHandler.suppress_circular_messages_time
    parser.add_argument('-s', dest='spread_time',
                        help="Time in seconds to storage a messageID to suppress circulating massages.", type=int,
                        default=600)
    args = parser.parse_args()

    # Get the name of the config file to print as name in logs
    logger_name = os.path.splitext(os.path.basename(args.config_file))[0]
    logging.basicConfig(format='%(levelname)s - ' + logger_name + ' - %(name)s - %(message)s', filename='server.log',
                        encoding='utf-8', level=logging.DEBUG)
    logger = logging.getLogger("init_main")

    # Set parameters from command line
    configs = parse_config_file(args.config_file)
    logger.debug("Config path: %s", args.config_file)
    gossip_validation_wait_time: int = args.validation_time
    logger.debug("Validation wait time set to: %i", gossip_validation_wait_time)
    gossip_suppress_circular_messages_time: int = args.spread_time
    logger.debug("Spread suppress time set to: %i", gossip_suppress_circular_messages_time)

    p2p_send_queue = asyncio.Queue()
    p2p_recv_queue = asyncio.Queue()
    api_send_queue = asyncio.Queue()
    api_recv_queue = asyncio.Queue()

    # Send queue: gossip->out
    #   Items: (raw_msg, recv)
    # Recv queue: out->gossip
    #   Items: (msg, sender) msg=(size, type, body, raw_msg)

    eloop = asyncio.new_event_loop()

    # Start API Server
    api_server = APIServer('api',
                           configs['api_address'][0], configs['api_address'][1],
                           api_send_queue, api_recv_queue, eloop)
    api_server.start()

    # Start P2P server
    p2p_server = P2PServer('p2p',
                           configs['p2p_address'][0], configs['p2p_address'][1], 5,
                           p2p_send_queue, p2p_recv_queue, eloop,
                           configs['cache_size'], configs['degree'], configs['bootstrapper'])
    p2p_server.start()

    # Start GossipHandler
    gossip_handler = GossipHandler(p2p_send_queue, p2p_recv_queue, api_send_queue, api_recv_queue, eloop,
                                   gossip_suppress_circular_messages_time, gossip_validation_wait_time)
    gossip_handler.start()

    try:
        eloop.run_forever()
    except KeyboardInterrupt:
        eloop.close()


if __name__ == "__main__":
    main()
