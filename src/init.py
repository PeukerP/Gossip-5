import asyncio
import re
from argparse import ArgumentParser
from configobj import ConfigObj

from connection import Server


def split_address_into_tuple(address):
    res = None
    pattern_v4_ip = r"([\d]{1-3}.[\d]{1-3}.[\d]{1-3}.[\d]{1-3}):([\d]+)"
    pattern_v4_name = r"([\w.-]+):([\d]+)"
    pattern_v6 = r"\[([a-f\d]*:[a-f\d]*:[a-f\d]*:[a-f\d]*:[a-f\d]*:[a-f\d]*:[a-f\d]*:[a-f\d]*)\]:([\d]+)"

    res = re.match(pattern_v4_ip, address)
    if res is None:
        # try name
        res = re.match(pattern_v4_name, address)
    if res is None:
        # try IPv6
        res = re.match(pattern_v6, address)
    if res is None:
        print("%s has the wrong format" % address)
        exit(1)

    return (res.group(1), res.group(2))


def parse_config_file(config_file):
    options = ['cache_size', 'degree',
               'bootstrapper', 'p2p_address', 'api_address']
    config = ConfigObj(config_file)
    # config.read()
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
            print("'%s' is missing in .ini file" % o)
            exit(1)

    # Split the addresses into tuples
    bootstr = split_address_into_tuple(bootstrapper)
    p2p_addr = split_address_into_tuple(p2p_address)
    api_addr = split_address_into_tuple(api_address)

    return {'cache_size': int(cache_size), 'degree': int(degree), 'bootstrapper': bootstr,
            'p2p_address': p2p_addr, 'api_address': api_addr}


def main():
    parser = ArgumentParser()
    parser.add_argument('-c', dest='config_file',
                        help='Give the path to the configuration file.', type=str, required=True)
    args = parser.parse_args()

    configs = parse_config_file(args.config_file)

    p2p_send_queue = asyncio.PriorityQueue()
    p2p_recv_queue = asyncio.PriorityQueue()
    api_send_queue = asyncio.PriorityQueue()
    api_recv_queue = asyncio.PriorityQueue()

    # Send queue: gossip->out
    #   Items: (prio, (address, port, msg_type, msg (without header)))
    # Recv queue: out->gossip
    #   Items: (prio, (msg_size, msg_type, msg))

    # We also need to init and start the Gossip handler here

    eloop = asyncio.new_event_loop()

    # Start API Server
    api_server = Server(
        configs['api_address'][0], configs['api_address'][1], api_send_queue, api_recv_queue, eloop)
    api_server.start()

    # Start P2P server
    p2p_server = Server(
        configs['p2p_address'][0], configs['p2p_address'][1], p2p_send_queue, p2p_recv_queue, eloop)
    p2p_server.start()

    try:
        eloop.run_forever()
    except KeyboardInterrupt as e:
        eloop.stop()




if __name__ == "__main__":
    main()
