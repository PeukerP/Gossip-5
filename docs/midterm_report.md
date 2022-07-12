# Midterm Report

## Changes to your assumptions in the initial report
- Implementation: Gossip

## Architecture of your module
```
         ___________________ to other modules on same peer
         | 
|--------|----------|
|    API_Server     |
|-----s_q----r_q----|
|                   |
|  Gossip_Handler   |
|                   |
|-----s_q----r_q----|
|    P2P_Server     |
|--------|----------|
         |__________________ to other gossip module on other peer

```
API_Server and P2P_Server are instances of the class Server.
A server receives/sends messages from/to P2P_Servers and modules.
When a message is received, the Server forwards the message to the Gossip_Handler via the receive queues (r_q).
The Gossip_Handler decides how to proceed with these messages and puts the response that should be send into the send queue (s_q). 

The receive queues are implemented as priority queues, since we want to prioritize GOSSIP VALIDATION messages. As the gossip module needs to store GOSSIP NOTIFICATION messages until the fitting GOSSIP VALIDATION message is received, prioritizing may be beneficial.

The Servers and the Gossip_Handler are supposed to run in separate threads.

For networking and intra-module communication, we use asyncio tasks. The Servers use a task each for receiving messages via the send queues.

### Security Features
We assume that sensitive data are encrypted by higher layers.

To counter Sybil Attacks we validate the identities by proof-of-work through our GOSSIP VERIFICATION REQUEST and RESPONSE messages. For the proof of work we will use a system of nonce and challenge as it was used for the p2p registration. The peer to be validated has to compute 64 bit so that the sha256 of the GOSSIP VERIFICATION RESPONSE has the first 24 bits set to 0. Peers will be validated before they are to be added to a known-peers-list or if they provide peers via a GOSSIP PEER REQUEST and RESPONSE.
To counter Eclipse Attacks one could periodically rejoin the network and get a new peer list from the bootstrap server.


## The peer-to-peer protocol(s) that is present in the implementation

GOSSIP ANNOUNCE
GOSSIP NOTIFY 
GOSSIP NOTIFICATION
GOSSIP VALIDATION
as specified in the specification.

Additionally we define the following messages for entering the P2P network:

### GOSSIP PEER REQUEST
A peer sends a request to share known peers with him to the bootstrap server (if existent) or other already known peers.

```
0_______________8_______________|_______________|_______________|31
| size                          |   GOSSIP PEER  REQUEST        |
|_______________________________|_______________________________|
|  peer limit   |                reserved                       | 
|_______________|_______________________________________________|
|                             nonce                             |
|_______________________________________________________________|

```
peer limit: Maximum number of peers that should be sent.
nonce: challenge for POW

### GOSSIP PEER RESPONSE
Response to the GOSSIP PEER REQUEST with a subset of known peers.

For ipv4 addresses:

```
0_______________8_______________|_______________|_______________|31
| size                          |   GOSSIP PEER RESPONSE        |
|_______________________________|_______________________________|
|                         nonce                                 
|---------------------------------------------------------------|
                                                                |
|_______________________________________________________________|
|                         challenge                             
|---------------------------------------------------------------|
                                                                |
|_______________________________________________________________|
| X|                   reserved                                 |
|__|____________________________________________________________|
|                    addr1_v4                                   |
|_______________________________________________________________|
|          port1                |          addr2_v4             
|_______________________________|_______________________________|
                                |          port2                |
|_______________________________|_______________________________|
|        ...  

```
For ipv6 addresses:

```
0_______________8_______________|_______________|_______________|31
| size                          |   GOSSIP PEER RESPONSE        |
|_______________________________|_______________________________|
|                         nonce                                 
|---------------------------------------------------------------|
                                                                |
|_______________________________________________________________|
|                         challenge                             
|---------------------------------------------------------------|
                                                                |
|_______________________________________________________________|
| X|                   reserved                                 |
|__|____________________________________________________________|
|                    addr1_v6                                   
|---------------------------------------------------------------|

|---------------------------------------------------------------|

|---------------------------------------------------------------|
                                                                |
|_______________________________________________________________|
|     port1                     |  addr2_v6
|_______________________________|_______________________________|
|     ...

```
X indicates ipv4 or ipv6 addresses. Values are 0 for ipv4 and 1 for ipv6.

### GOSSIP VERIFICATION REQUEST
A peer sends a verification request to another peer with nonce for the POW before he inserts the other peer into his known-peers-list.

```
0_______________8_______________|_______________|_______________|31
| size                          |   GOSSIP VERIFICATION REQUEST |
|_______________________________|_______________________________|
|                         nonce                                 
|---------------------------------------------------------------|
                                                                |
|_______________________________________________________________|

```

### GOSSIP VERIFICATION RESPONSE
Response to challenge for POW

```
0_______________8_______________|_______________|_______________|31
| size                          |   GOSSIP VERIFICATION RESPONSE|
|_______________________________|_______________________________|
|                         nonce                                 
|---------------------------------------------------------------|
                                                                |
|_______________________________________________________________|
|                         challenge                             
|---------------------------------------------------------------|
                                                                |
|_______________________________________________________________|

```

If a package received on the P2P layer is damaged, we do not request the sender to resend, since 
Voidphone is a realtime application, and thus resending is not required.

If a peer leaves the network, this will be detected when we want to send a message to it and the sending 
fails. The peer is then removed from the known-peers-list.

## Future Work
- Bootstrapping
- Multithreading
- Complete implementation of Gossip_Handler
- Implement Security features
- Testing

## Workload Distribution
- Concept: both equally
- Petra: (~ 1,5 weeks)
  - Server class
  - Config file parsing and initialization
  - [WIP] Bootstrapping
- Thomas: (~ 2 days)
  - [WIP] Gossip_Handler

Main effort planned in august/september
