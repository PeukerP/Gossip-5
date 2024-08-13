# Introduction

This project contains the implementation of the Gossip module as part of the Peer-to-Peer-Systems and Security course at TUM.

# Usage

In the following section we will introduce into the python application
and how to run and test it. For direct execution please refer to the
[Quick Start Guide](#quick-start-guide).
A description of the architecture and message specifications are provided in [docs/documentation.pdf](docs/documentation.pdf).

### Requirements

We used Python 3.10. To install the required Python packages run:

``` {.Bash language="Bash"}
pip install -r requirements.txt
```

## Configuration

To configure the Gossip module, a .ini file should be provided with the
following parameters:

-   `cache_size`: Maximum number of data items to be held as part of the
    peer's knowledge base.

-   `degree`: Number of peers the current peer has to exchange
    information with.

-   `p2p_ttl` (optional): Specifies the maximum TTL for
    `GOSSIP PUSH` updates. Default set to 5.

-   `bootstrapper` (optional): If this option is not provided, operate
    as a bootstrapper. Otherwise, connect peer to the bootstrapper node
    identified by IPv4 address and port.

-   `p2p_address`: IPv4 address with port this module is listening on
    for P2P packages.

-   `api_address`: IPv4 address with port this module is listened on for API packages.

An example is given below:

``` {.Ini language="Ini"}
[gossip]
cache_size = 50
degree = 30
p2p_ttl = 10
bootstrapper = 127.0.0.1:6001
p2p_address = 127.0.0.1:6011
api_address = 127.0.0.1:7011
```

For additional command line parameters please refer to
the `waiting_for_validation` and `spread` section in [docs/documentation.pdf](docs/documentation.pdf)

## Execution

To execute Gossip-5 a path to a configuration file is always required.
It can be specified by the `-c PATH/TO/CONFIG.ini` parameter. The
optional parameters for the validation timeout `-v INT` and the circular
spread suppression time `-s INT` can be given in seconds. Execution example:

``` {.Bash language="Bash"}
cd src
python init.py -c ./config/bootstrap.ini -v 5 -s 60
```

## Tests

To run the tests please add the full path to Gossip-5/src to your
PYTHONPATH:

``` {.Bash language="Bash"}
export PYTHONPATH="<path-to-gossip>/Gossip-5/src/"
```

Then the tests can be executed by running:

``` {.Bash language="Bash"}
cd tests/unit
python -m unittest
```

## Quick start guide

To install the required packages please run:

``` {.Bash language="Bash"}
pip install -r requirements.txt
```

And to run the first client of a network:

``` {.Bash language="Bash"}
cd src
python init.py -c ./config/bootstrapper.ini
```

And to run another client please execute:

``` {.Bash language="Bash"}
python init.py -c ./config/peer1.ini
```
