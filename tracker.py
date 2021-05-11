from abc import ABC, abstractmethod
from collections import namedtuple
from enum import Enum
from hashlib import sha1
from socket import inet_ntoa
from struct import Struct
from urllib.parse import urlencode, quote_from_bytes
from urllib.request import urlopen
from urllib.error import URLError

from bencode import bencode, bdecode

# from swarm import SwarmPeer, PeerFinder
from torrent import Torrent

Peer = namedtuple('Peer', ['id', 'host', 'port'])


class PeerFinder(ABC):

    @abstractmethod
    # def get_peers(self) -> list[Peer]:
    def get_peers(self) -> list:
        pass


class TrackerConnectionException(Exception):
    pass


class UnsupportedTrackerException(Exception):
    pass


class DummyTracker(PeerFinder):
    """
    A peer finder that just returns a single peer for testing
    or demonstrating P2P seeding.
    """

    def __init__(self, p: Peer):
        self.__p = p

    def get_peers(self) -> list:
        return [self.__p]


class TrackerEvent(Enum):
    STARTED = 'started'
    COMPLETED = 'completed'
    STOPPED = 'stopped'
    EMPTY = 'empty'


class Tracker(PeerFinder):

    def __init__(self, peer_id: bytes, torrent: Torrent, listening_host, listening_port):
        self.pid = peer_id
        self.torrent = torrent
        # TODO: Dynamically get with UPNP
        self.host = listening_host
        self.port = listening_port

        announce_url = self.torrent.announce
        if not (announce_url.startswith('http://') or announce_url.startswith('https://')):
            raise UnsupportedTrackerException(f'Tracker protocol not supported {announce_url}!')

        # Construct tracker HTTP request
        info_hash = sha1(bencode(self.torrent.info)).digest()
        self.r = TrackerRequest(
            announce_url=self.torrent.announce,
            info_hash=info_hash,
            peer_id=self.pid,
            ip=self.host,
            port=self.port,
            uploaded=0,
            downloaded=0,
            left=self.torrent.download_length
        )

    def get_peers(self):
        return self.r.send()


class CompactResponseFormatError(ValueError):
    pass


class TrackerRequest:
    port_bspec = Struct('!H')

    def __init__(self, announce_url, info_hash, peer_id, ip, port, uploaded, downloaded, left,
                 event: TrackerEvent = None):
        self.announce_url = announce_url
        self.params = {
            # 'info_hash': quote_from_bytes(info_hash),
            'info_hash': info_hash,
            'peer_id': peer_id,
            'ip': ip,
            'port': port,
            'uploaded': uploaded,
            'downloaded': downloaded,
            'left': left,
            'compact': 1
        }

        if event:
            self.params['event'] = event

    @classmethod
    # def decode_compact_response(cls, resp_data: bytes) -> list[Peer]:
    def decode_compact_response(cls, peers_str: bytes) -> list:
        if len(peers_str) % 6 != 0:
            raise CompactResponseFormatError('peer string could not be split into 6byte IP+PORT chunks!')

        chunks = (peers_str[s:s + 6] for s in range(0, len(peers_str), 6))

        peers = [Peer(id='', host=inet_ntoa(c[0:4]), port=cls.port_bspec.unpack(c[4:6])[0]) for c in chunks]

        return peers

    @classmethod
    def decode_response(cls, resp_data: bytes):
        data = bdecode(resp_data)
        peers = data['peers']
        try:
            return [Peer(p['peer id'], p['ip'], p['port']) for p in peers]
        except TypeError as e:
            # raise e
            return cls.decode_compact_response(peers)

    def send(self):
        eparams = urlencode(self.params)

        print(u'Connecting to tracker {}'.format(self.announce_url))
        print(f'Params: {eparams}')
        # print(eparams)
        try:
            with urlopen(self.announce_url + '?' + eparams, timeout=2) as resp:
                rdata = resp.read()
                return self.decode_response(rdata)
                # with open('test/tracker_responses/ubuntu.resp', 'wb') as f:
                #     f.write(rdata)
                #     f.close()

        except URLError as e:
            print(e)
            raise TrackerConnectionException(f'Connection to {self.announce_url} failed!')
