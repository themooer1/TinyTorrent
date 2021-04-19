
import asyncio
import random
import time

from abc import ABC, abstractmethod
from asyncio import coroutine, open_connection, sleep, StreamReader, StreamWriter

from bitfield import MutableBitfield
from packet import HandshakePacket, KeepalivePacket, ChokePacket, UnchokePacket, InterestedPacket, UninterestedPacket, HavePacket, BitfieldPacket, PiecePacket, RequestPacket, CancelPacket, read_next_packet, send_packet
from storage import Piece, Request
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

    def has_index(self, index: int) -> bool:
        return self.bitfield.get(index)

    def has(self, piece: Union[int, Piece, Request]) -> bool:
        if issubclass(piece, Piece) or issubclass(piece, Request):
            index = piece.index()
        else:
            index = piece
        
        return self.has_index(index)

    @coroutine
    def request_piece(self, r: Request):
        pkt = RequestPacket(
            piece_index = r.index(),
            begin_offset = r.begin_offset(),
            length = r.length()
        )

        yield from self.send_packet(pkt)
    

    @coroutine
    def send_piece(self, p: Piece):
        pkt = PiecePacket(
            piece_index = p.index(),
            begin_offset = p.begin_offset(),
            data = p.data()
        )

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
            self.choking = True
        
        elif issubclass(pkt, UnchokePacket):
            self.choking = False
        
        elif issubclass(pkt, InterestedPacket):
            self.interested = True

        elif issubclass(pkt, UninterestedPacket):
            self.interested = False
        
        elif issubclass(pkt, HavePacket):
            self.bitfield.set(pkt.piece_index())

        elif issubclass(pkt, BitfieldPacket):
            assert len(pkt.bitfield()) == self.swarm.torrent.num_pieces()
            self.bitfield = pkt.bitfield()
        
        

        
        #o.w. hand off to swarm's read_next_packet
        
        return self, pkt


class ManualRequest(Request):
    def __init__(self, index: int, begin_offset: int, length: int):
        self.index = index
        self.begin_offset = begin_offset
        self.length = length

    def index(self) -> int:
        return self.index

    def begin_offset(self) -> int:
        return self.begin_offset
    
    def length(self) -> int:
        return self.length


class SimpleRequest(ManualRequest):
    def __init__(self, index: int, length: int):
        self.index = index
        self.length = length
    
    @override
    def begin_offset(self) -> int:
        return 0
    
    @override
    def length(self) -> int:
        return self.length



class Swarm:
    MAX_ACTIVE_PEERS = 30
    MAX_OUTSTANDING_PIECES = 30

    def __init__(self, torrent: Torrent, finder: PeerFinder, piece_request_timeout = 5):
        self.bounties = dict()  # Pieces currently being awaited
        self.pieces_to_download = asyncio.Queue(torrent.num_pieces())

        self.my_pid = generate_peer_id()
        self.peers = finder.get_peers()
        # Nothing else made it clear who was sending to whom XD
        self.peers_im_downloading_from = []
        self.peers_im_sending_to = {}  # Map<peer_id -> SwarmPeer>

        self.request_timeout = piece_request_timeout

        self.torrent = torrent

    
    @coroutine
    def connect_to_peer(self, host, port):
        reader, writer = yield from open_connection(host, port)

        p = SwarmPeer(self, reader, writer)
        self.peers.append(p)
    
    def get_torrent(self) -> Torrent:
        return self.torrent

    @coroutine
    def request_next_piece(self):
        r = yield from self.pieces_to_download.get()
        request_fulfilled = asyncio.Condition()
        self.bounties[r] = request_fulfilled

        peers_with_piece = list(filter(self.peers_im_downloading_from.values(), lambda p: p.has(r)))
        for peer_to_ask in random.shuffle(peers_with_piece):
            yield from peer_to_ask.request_piece(r)

            try:
                asyncio.wait_for(request_fulfilled, timeout=self.request_timeout)
                return  # The piece was received and stored, so stop asking
            except asyncio.TimeoutError:
                print(f'Peer {peer_to_ask.peer_id()} timed out on piece index {r.index()}.')
        
        # Try again later
        self.bounties.pop(r)
        yield from self.pieces_to_download.put(r)

        # TODO: put back on queue in 


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
                
                elif issubclass(pkt, PiecePacket):
                    self.torrent.store_piece(pkt.piece())
                    self.pieces_to_download.task_done()
                    yield from self.bounties[pkt.index()].notify()
                        
    
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
            self.pieces_to_download.put_nowait(
                SimpleRequest(
                    index = index,
                    length = self.torrent.piece_length()
                )
            )
        
        yield from self.pieces_to_download.join()
        
    @coroutine
    def start(self):
        '''Completes local files then seeds forever.'''



        # TODO: 
        # Handle adding peers that connect
        # Connect to peers from tracker
        # Unchoke some peers
        # Solicit pieces
        # Respond to incoming packets
        pass


