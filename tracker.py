from bencode import bencode, bdecode
from collections import namedtuple
from hashlib import sha1
from socket import inet_ntoa
from struct import Struct
from urllib import urlencode, urlopen

from swarm import SwarmPeer, PeerFinder
from torrent import Torrent


Peer = namedtuple('Peer', ['id', 'host', 'port'])

class PeerFinder(ABC):

    @abstractmethod
    def get_peers(self) -> list[Peer]:
        pass

class TrackerFailureException(Exception):
    pass
 
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

    def get_peers(self, ):
        info_hash = sha1(bencode(self.torrent.info())).digest

        r = TrackerRequest(
            announce_url=self.torrent.announce_url(),
            info_hash=info_hash,
            peer_id=self.pid,
            ip=self.listening_host,
            port=self.listening_port,
            uploaded=0, 
            downloaded=0,
            left=self.torrent.download_size()
        )




class CompactResponseFormatError(ValueError):
    pass

class TrackerRequest:
    port_bspec = Struct('!H')
    def __init__(self, announce_url, info_hash, peer_id, ip, port, uploaded, downloaded, left, event: TrackerEvent = None):
        self.announce_url = announce_url
        self.params = {
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
    def decode_compact_response(cls, resp_data: bytes) -> list[Peer]:
        if len(resp_data) % 6 != 0:
            raise CompactResponseFormatError('resp could not be split into 6byte IP+PORT chunks!')

        chunks = (resp_data[s:s + 6] for s in range(0, len(resp_data), 6))

        peers = [Peer(id='', ip = inet_ntoa(c[0:4]), port=cls.port_bspec.unpack(c[4:6])) for c in chunks]

        return peers
        

    def send(self):
        eparams = urlencode(self.params).encode('utf-8')
        
        with urlopen(self.announce_url, data=eparams) as resp:
            rdata = resp.read().decode()
            if self.params['compact'] == 0:
                try:
                    return [Peer(p['peer id'], p['ip'], p['port']) for p in bdecode(resp)['peers']]
                except:
                    return self.decode_compact_response(resp)


