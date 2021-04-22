
import asyncio
import random
import time

from abc import ABC, abstractmethod
from asyncio import coroutine, open_connection, Semaphore, sleep, StreamReader, StreamWriter

from bitfield import MutableBitfield
from packet import HandshakePacket, KeepalivePacket, ChokePacket, UnchokePacket, InterestedPacket, UninterestedPacket, HavePacket, BitfieldPacket, BlockPacket, RequestPacket, CancelPacket, read_next_packet, send_packet
from storage import Block, PieceManager, Request
from tracker import Peer, PeerFinder
from torrent import Torrent

PEER_PORT = 7478


def generate_peer_id() -> bytes:
    '''Generates a random 20 byte peer ID'''
    (''.join(random.choices('1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=20))).encode()


class SwarmPeer:
    def __init__(self, swarm: Swarm, reader: StreamReader, writer: StreamWriter, choking=True, interested=False):
        self.swarm = swarm
        self.pid = pid # TODO: set this when connection is made
        self.am_choking = choking
        self.am_interested = interested
        self.peer_choking = True
        self.peer_interested = False
        self.reader = reader
        self.writer = writer

        self.last_seen = time.time()

        num_pieces = swarm.get_torrent().num_pieces()
        self.bitfield = MutableBitfield(bytearray(num_pieces))

        # Stops eternal coroutines
        self.running = True

    def peer_id(self):
        return self.pid

    @coroutine
    def connect(self):
        pkt = HandshakePacket(self.peer_id(), self.swarm.torrent.info_hash())

    @coroutine
    def choke_and_notify(self):
        self.choke()

        pkt = ChokePacket()
        yield from self.send_packet(pkt)


    def choke(self):
        self.choke = True

    @coroutine
    def unchoke_and_notify(self):
        self.unchoke()

        pkt = UnchokePacket()
        yield from self.send_packet(pkt)
    

    def unchoke(self):
        self.unchoke = True

    @coroutine
    def take_interest_and_notify(self):
        self.take_interest()

        pkt = InterestedPacket()
        yield from self.send_packet(pkt)
    

    def take_interest(self):
        self.am_interested = True

    
    @coroutine
    def remove_interest_and_notify(self):
        self.remove_interest()

        pkt = UninterestedPacket()
        yield from self.send_packet(pkt)
    

    def remove_interest(self):
        self.am_interested = False

    def am_choking(self):
        '''Are WE choking the peer'''
        return self.am_choking

    def peer_choking(self):
        '''Is the PEER choking us'''
        return self.peer_choking

    def am_interested(self):
        '''Is the peer interested in our data'''
        return self.am_interested
    
    def peer_interested(self):
        '''Is the PEER interested in our data'''
        return self.peer_interested

    def has_piece(self, index: int) -> bool:
        return self.bitfield.get(index)

    @coroutine
    def request_piece(self, r: Request):
        pkt = RequestPacket(r)

        yield from self.send_packet(pkt)
    

    @coroutine
    def send_piece(self, b: Block):
        pkt = BlockPacket(b)

        yield from self.send_packet(pkt)

    @coroutine
    def send_have(self, piece_index: int):
        pkt = HavePacket(piece_index)

        yield from self.send_packet(pkt)

    @coroutine
    def send_packet(self, pkt: BittorrentPacket):
        yield from send_packet(self.writer, pkt)
    
    @coroutine
    def read_next_packet(self):
        '''Returns (self, next_pkt_for_this_peer)'''
        pkt = yield from read_next_packet(self.reader)

        self.last_seen = time.time()

        # Process if we can
        if issubclass(pkt, KeepalivePacket):
            pass

        elif issubclass(pkt, ChokePacket):
            self.peer_choking = True
        
        elif issubclass(pkt, UnchokePacket):
            self.peer_choking = False
        
        elif issubclass(pkt, InterestedPacket):
            self.peer_interested = True

        elif issubclass(pkt, UninterestedPacket):
            self.peer_interested = False
        
        elif issubclass(pkt, HavePacket):
            self.bitfield.set(pkt.piece_index())

        elif issubclass(pkt, BitfieldPacket):
            assert len(pkt.bitfield()) == self.swarm.torrent.num_pieces()
            self.bitfield = MutableBitfield(pkt.bitfield())
        
        # Otherwise hand off to swarm's read_next_packet
        return self, pkt


class Swarm:
    MAX_ACTIVE_PEERS = 30
    MAX_OUTSTANDING_REQUESTS = 30

    def __init__(self, torrent: Torrent, manager: PieceManager, finder: PeerFinder, piece_request_timeout = 5):
        self.my_pid = generate_peer_id()
        self.outstanding_requests = Semaphore(self.MAX_OUTSTANDING_REQUESTS)
        self.peers: list[SwarmPeer] = finder.get_peers()
        self.peers_not_choking_me: list[SwarmPeer] = []

        self.piece_manager: PieceManager = manager

        self.request_timeout = piece_request_timeout

        self.torrent = torrent

    
    @coroutine
    def connect_to_peer(self, host, port):
        reader, writer = yield from open_connection(host, port)

        p = SwarmPeer(self, reader, writer)
        self.peers.append(p)

    def peers_with_piece(self, piece_index: int):
        return [p for p in self.peers_not_choking_me if p.has_piece(piece_index)]
    
    def random_peer_with_piece(self, piece_index: int):
        return random.choice(self.peers_with_piece(piece_index))

    def reset_outstanding_requests(self):
        self.outstanding_requests = Semaphore(self.MAX_OUTSTANDING_REQUESTS)
    
    @coroutine
    def request_pieces(self):
        for request in self.piece_manager.requests():
            request: Request = Request

            peer_to_ask: SwarmPeer = self.random_peer_with_piece(request.index())

            yield from peer_to_ask.request_piece(request)

            try:
                asyncio.wait_for(self.outstanding_requests.acquire(), timeout=self.request_timeout)

            except asyncio.TimeoutError:
                # Consider all outstanding requests timed out
                self.reset_outstanding_requests()
        

    @coroutine
    def handle_incoming(self):
        while self.running:
            for peer, pkt in asyncio.gather((p.read_next_packet() for p in self.peers)):
                peer: SwarmPeer = peer
                if issubclass(pkt, KeepalivePacket):
                    pass

                # Handled by peer's read_next_packet
                # elif issubclass(pkt, ChokePacket):
                #     peer.choke()
                
                # elif issubclass(pkt, UnchokePacket):
                #     peer.unchoke()
                                
                # elif issubclass(pkt, InterestedPacket):
                #     self.interested = True

                # elif issubclass(pkt, UninterestedPacket):
                #     self.interested = False

                # elif issubclass(pkt, HavePacket):
                    # pass
                # elif issubclass(pkt, BitfieldPacket):
                    # pass
                
                elif issubclass(pkt, RequestPacket):
                    if not peer.am_choking():
                        if self.torrent.has_piece(pkt.piece()):
                            piece = self.torrent.get_piece(pkt.piece())
                            peer.send_piece(piece)
                        else:
                            # Refresh peer's knownledge of what we have
                            # bfp = BitfieldPacket()
                            pass
                    else:
                        # Re-notify peer we are choking
                        peer.choke()
                
                elif issubclass(pkt, BlockPacket):
                    try:
                        self.torrent.store_piece(pkt.piece())
                        yield from self.bounties[pkt.index()].notify()
                        yield from self.send_haves(pkt)
                    except PieceVerificationException:
                        print(f'Failed to validate idx {pkt.index()} from {peer.peer_id()}')

    @coroutine
    def send_haves(self, p: Block):
        yield from asyncio.gather(
            (peer.send_have(p) for peer in self.peers)
        )
    
    @coroutine
    def send_keepalives_forever(self):
        '''Send keepalives to all peers once every 100 seconds'''
        pkt = KeepalivePacket()
        while self.running:
            for peer in self.peers():
                yield from peer.send_packet(pkt)
            
            asyncio.sleep(100)


    @coroutine
    def accept_peer_connection(self, reader: StreamReader, writer: StreamWriter):
        peer = SwarmPeer(
            swarm = self,
            reader = reader,
            writer = writer
        )

        self.peers.append(peer)

        pkt = HandshakePacket()
        yield from peer.send_packet(pkt)

    @coroutine
    def handle_incomming_connections(self):
        yield from asyncio.start_server(self.accept_peer_connection, host=None, port=PEER_PORT)


    @coroutine
    def request_all_pieces(self):
        pieces_to_get = list(range(0, self.torrent.num_pieces()))
        random.shuffle(pieces_to_get)

        for index in pieces_to_get:
            # Will pause as necessary in request_piece
            yield from self.pieces_to_download.put(
                SimpleRequest(
                    index = index,
                    length = self.torrent.piece_length()
                )
            )

        while self.pieces_to_download.qsize() > 0:
            yield from asyncio.gather(
                self.MAX_OUTSTANDING_PIECES * [self.request_next_piece()]
            )
        
    @coroutine
    def control_flow(self):
        while self.running:
            self.peers_im_downloading_from = random.choices(
                peers, 
                k = MAX_ACTIVE_PEERS
            )
            asyncio.sleep(30)
            
        
    @coroutine
    def start(self):
        '''Completes local files then seeds forever.'''
        yield from asyncio.gather(
            self.handle_incomming_connections(),
            self.request_all_pieces(),
            self.handle_incomming(),
            self.send_keepalives_forever(),
        )



        # TODO: 
        # Handle adding peers that connect
        # Connect to peers from tracker
        # Unchoke some peers
        # Solicit pieces
        # Respond to incoming packets
        pass


