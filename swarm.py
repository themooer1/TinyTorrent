import asyncio
import random
import time

from abc import ABC, abstractmethod
from asyncio import coroutine, open_connection, Semaphore, sleep, StreamReader, StreamWriter, IncompleteReadError
from typing import Union

from bitfield import MutableBitfield
from packet import BittorrentPacket, HandshakePacket, KeepalivePacket, ChokePacket, UnchokePacket, InterestedPacket, \
    UninterestedPacket, HavePacket, BitfieldPacket, BlockPacket, RequestPacket, CancelPacket, read_handshake_response, \
    read_next_packet, send_packet, PeerError, PeerDisconnected
from storage import Block, PieceManager, Request
from tracker import Peer, PeerFinder
from torrent import Torrent

PEER_PORT = 1955


def generate_peer_id() -> bytes:
    """Generates a random 20 byte peer ID"""
    return ('OceanC' + ''.join(random.choices('1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=14))).encode()


class InfoHashDoesntMatchException(Exception):
    pass


class NoPeersException(Exception):
    """When there aren't yet peers to download from"""
    pass


class SwarmPeer:
    def __init__(self, swarm: "Swarm", reader: StreamReader, writer: StreamWriter, choking=True, interested=False):
        self.swarm = swarm
        self.__pid = b'UNNAMED_PEER01234569'  # set when connection is made (self.connect())
        self.__am_choking = choking
        self.__am_interested = interested
        self.__peer_choking = True
        self.__peer_interested = False
        self.__reader = reader
        self.__writer = writer

        self.__last_seen = time.time()

        num_pieces = swarm.torrent.num_pieces
        self.__bitfield = MutableBitfield(bytearray(num_pieces))

        # Stops eternal coroutines
        self.running = True

    def peer_id(self):
        return self.__pid

    def __del__(self):
        self.__writer.close()

    @coroutine
    def connect(self):
        pkt = HandshakePacket(self.swarm.torrent.info_hash, self.swarm.my_pid)
        yield from self.send_packet(pkt)
        # resp: HandshakePacket = yield from read_handshake_response(self.reader)
        resp = yield from read_handshake_response(self.__reader)

        self.__pid = resp.peer_id()

        sent_info_hash = self.swarm.torrent.info_hash
        recv_info_hash = resp.info_hash()
        if sent_info_hash != recv_info_hash:
            raise InfoHashDoesntMatchException(f'Sent {sent_info_hash}, but got {recv_info_hash}')

    @coroutine
    def accept_connection(self):
        # incoming_handshake: HandshakePacket = yield from read_handshake_response(self.reader)
        incoming_handshake = yield from read_handshake_response(self.__reader)

        self.__pid = incoming_handshake.peer_id()

        my_info_hash = self.swarm.torrent.info_hash
        incoming_handshake_info_hash = incoming_handshake.info_hash()
        if my_info_hash != incoming_handshake_info_hash:
            raise InfoHashDoesntMatchException(f'Connecting client send info hash {incoming_handshake_info_hash} which '
                                               f'does not match current torrent\'s info hash {my_info_hash}')

        pkt = HandshakePacket(self.swarm.torrent.info_hash, self.swarm.my_pid)
        yield from self.send_packet(pkt)

    @coroutine
    def choke_and_notify(self):
        self.choke()

        pkt = ChokePacket()
        yield from self.send_packet(pkt)

    def choke(self):
        self.__am_choking = True

    @coroutine
    def unchoke_and_notify(self):
        self.unchoke()

        pkt = UnchokePacket()
        yield from self.send_packet(pkt)

    def unchoke(self):
        self.__am_choking = True

    @coroutine
    def take_interest_and_notify(self):
        self.take_interest()

        pkt = InterestedPacket()
        yield from self.send_packet(pkt)

    def take_interest(self):
        self.__am_interested = True

    @coroutine
    def remove_interest_and_notify(self):
        self.remove_interest()

        pkt = UninterestedPacket()
        yield from self.send_packet(pkt)

    def remove_interest(self):
        self.__am_interested = False

    def am_choking(self):
        """Are WE choking the peer"""
        return self.__am_choking

    def peer_choking(self):
        """Is the PEER choking us"""
        return self.__peer_choking

    def am_interested(self):
        """Is the peer interested in our data"""
        return self.__am_interested

    def peer_interested(self):
        """Is the PEER interested in our data"""
        return self.__peer_interested

    def has_piece(self, index: int) -> bool:
        return self.__bitfield.get(index)

    @coroutine
    def request_piece(self, r: Request):
        pkt = RequestPacket(r)

        yield from self.send_packet(pkt)

    @coroutine
    def send_block(self, b: Block):
        pkt = BlockPacket(b)

        yield from self.send_packet(pkt)

    @coroutine
    def send_have(self, piece_index: int):
        pkt = HavePacket(piece_index)

        yield from self.send_packet(pkt)

    @coroutine
    def send_packet(self, pkt: Union[BittorrentPacket, HandshakePacket]):
        yield from send_packet(self.__writer, pkt)

    @coroutine
    def read_next_packet(self):
        """Returns (self, next_pkt_for_this_peer)"""
        pkt = yield from read_next_packet(self.__reader)

        self.__last_seen = time.time()

        # Process if we can
        if isinstance(pkt, KeepalivePacket):
            pass

        elif isinstance(pkt, ChokePacket):
            self.__peer_choking = True

        elif isinstance(pkt, UnchokePacket):
            self.__peer_choking = False

        elif isinstance(pkt, InterestedPacket):
            self.__peer_interested = True

        elif isinstance(pkt, UninterestedPacket):
            self.__peer_interested = False

        elif isinstance(pkt, HavePacket):
            self.__bitfield.set(pkt.piece_index())

        elif isinstance(pkt, BitfieldPacket):
            # Bitfields allocate to the nearest byte
            assert 0 <= len(pkt.bitfield()) - self.swarm.torrent.num_pieces < 8
            self.__bitfield = MutableBitfield(pkt.bitfield())

        # hand off to swarm's read_next_packet
        return self, pkt


class Swarm:
    MAX_ACTIVE_PEERS = 30
    MAX_OUTSTANDING_REQUESTS = 300

    def __init__(self, torrent: Torrent, manager: PieceManager, finder: PeerFinder, piece_request_timeout=2):
        self.running = False
        self.my_pid = generate_peer_id()

        self.finder = finder
        self.outstanding_requests = Semaphore(self.MAX_OUTSTANDING_REQUESTS)
        # self.peers: list[SwarmPeer] = finder.get_peers()
        self.peers: list = []
        # self.peers_not_choking_me: set[SwarmPeer] = set()
        self.peers_not_choking_me: set = set()

        self.piece_manager: PieceManager = manager

        self.request_timeout = piece_request_timeout

        self.__torrent = torrent

    @property
    def torrent(self):
        return self.__torrent

    def disconnect(self, p: Peer):
        self.peers_not_choking_me.remove(p)
        self.peers.remove(p)

    @coroutine
    def find_peers(self):
        @coroutine
        def safe_connect(p: Peer):
            try:
                yield from self.connect_to_peer(p.host, p.port)
                print(f'Connected to peer {p.host}:{p.port}')
                print(f'I now have {len(self.peers)} peers.')
                print(f'{len(self.peers_not_choking_me)} peers have unchoked me.')

            except (PeerError, PeerDisconnected, IncompleteReadError, ConnectionRefusedError, asyncio.TimeoutError) as e:
                print(type(e))
                print(f'Could not connect to peer {p.host}:{p.port}')

        connect_tasks = [safe_connect(p) for p in self.finder.get_peers()]
        yield from asyncio.gather(*connect_tasks)

        # for p in self.finder.get_peers():
        #     try:
        #         yield from self.connect_to_peer(p.host, p.port)
        #         print(f'Connected to peer {p.host}:{p.port}')
        #         print(f'I now have {len(self.peers)} peers.')
        #         print(f'{len(self.peers_not_choking_me)} peers have unchoked me.')
        #
        #     except (PeerError, PeerDisconnected, IncompleteReadError, ConnectionRefusedError, asyncio.TimeoutError) as e:
        #         print(type(e))
        #         print(f'Could not connect to peer {p.host}:{p.port}')

    @coroutine
    def connect_to_peer(self, host, port):
        reader, writer = yield from asyncio.wait_for(open_connection(host, port), self.request_timeout)

        p = SwarmPeer(self, reader, writer)
        yield from p.connect()
        yield from p.take_interest_and_notify()
        self.peers.append(p)

    def peers_with_piece(self, piece_index: int):
        return [p for p in self.peers_not_choking_me if p.has_piece(piece_index)]

    def random_peer_with_piece(self, piece_index: int):
        peers_with_piece = self.peers_with_piece(piece_index)

        if peers_with_piece:
            return random.choice(peers_with_piece)
        return None

    def reset_outstanding_requests(self):
        self.outstanding_requests = Semaphore(self.MAX_OUTSTANDING_REQUESTS)

    @coroutine
    def request_pieces(self):
        for request in self.piece_manager.requests():
            # request: Request = request

            peer_to_ask: SwarmPeer = self.random_peer_with_piece(request.index())
            while peer_to_ask is None:
                print('Waiting for peers')
                yield from asyncio.sleep(1)
                peer_to_ask: SwarmPeer = self.random_peer_with_piece(request.index())

            try:
                yield from peer_to_ask.request_piece(request)

                try:
                    yield from asyncio.wait_for(self.outstanding_requests.acquire(), timeout=self.request_timeout)

                except asyncio.TimeoutError:
                    # Consider all outstanding requests timed out
                    self.reset_outstanding_requests()

            except (PeerDisconnected, PeerError):
                self.disconnect(peer_to_ask)

        assert self.piece_manager.complete()
        exit(0)

    @coroutine
    def handle_incoming(self):
        @coroutine
        def handle_peer_msgs(p: SwarmPeer):
            while self.running:
                try:
                    peer, pkt = yield from p.read_next_packet()
                    yield from self._handle_packet(peer, pkt)
                except PeerDisconnected as e:
                    print(e)
                    break

        peer_handler_tasks = [handle_peer_msgs(p) for p in self.peers]
        yield from asyncio.gather(*peer_handler_tasks)

    @coroutine
    def _handle_packet(self, src_peer: SwarmPeer, pkt: BittorrentPacket):
        # peer: SwarmPeer = peer
        if isinstance(pkt, KeepalivePacket):
            pass

        # Handled by peer's read_next_packet
        elif isinstance(pkt, ChokePacket):
            self.peers_not_choking_me.discard(src_peer)

        elif isinstance(pkt, UnchokePacket):
            self.peers_not_choking_me.add(src_peer)

        # elif isinstance(pkt, InterestedPacket):
        #     self.interested = True

        # elif isinstance(pkt, UninterestedPacket):
        #     self.interested = False

        # elif isinstance(pkt, HavePacket):
        # pass
        # elif isinstance(pkt, BitfieldPacket):
        # pass

        elif isinstance(pkt, RequestPacket):
            if not src_peer.am_choking:
                if self.piece_manager.has_piece(pkt.request().index()):
                    block = self.piece_manager.get_block(pkt.request())
                    src_peer.send_block(block)
                else:
                    # Refresh peer's knownledge of what we have
                    # bfp = BitfieldPacket()
                    pass
            else:
                # Re-notify peer we are choking
                print(f'Peer {src_peer.peer_id()} requested data when choked.')
                src_peer.choke_and_notify()

        elif isinstance(pkt, BlockPacket):
            self.outstanding_requests.release()
            self.piece_manager.save_block(pkt.block())
            if self.piece_manager.has_piece(pkt.block().index()):
                yield from src_peer.send_have(pkt.block().index())

    # @coroutine
    # def send_haves(self, p: Block):
    #     yield from asyncio.gather(
    #         (peer.send_have(p) for peer in self.peers)
    #     )

    @coroutine
    def send_keepalives_forever(self):
        """Send keepalives to all peers once every 100 seconds"""
        pkt = KeepalivePacket()
        while self.running:
            yield from asyncio.sleep(100)
            for peer in self.peers:
                yield from peer.send_packet(pkt)

    @coroutine
    def accept_peer_connection(self, reader: StreamReader, writer: StreamWriter):
        peer = SwarmPeer(
            swarm=self,
            reader=reader,
            writer=writer
        )

        try:
            yield from asyncio.wait_for(peer.accept_connection(), timeout=10)
            self.peers.append(peer)

        except (PeerDisconnected, InfoHashDoesntMatchException, asyncio.TimeoutError) as e:
            print(e)

        # SwarmPeer's __del__ will close the writer

    @coroutine
    def handle_incoming_connections(self):
        yield from asyncio.start_server(self.accept_peer_connection, host=None, port=PEER_PORT)

    @coroutine
    def start(self):
        """Completes local files then seeds forever."""
        self.running = True

        yield from self.find_peers()

        yield from asyncio.gather(
            self.handle_incoming(),
            self.handle_incoming_connections(),
            self.request_pieces(),
            self.send_keepalives_forever(),
        )

    def stop(self):
        self.running = False

        # TODO:
        # Handle adding peers that connect
        # Connect to peers from tracker
        # Unchoke some peers
        # Solicit pieces
        # Respond to incoming packets
        pass
