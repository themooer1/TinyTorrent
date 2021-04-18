from swarm import Peer, PeerFinder

class TrackerFailureException(Exception):
    pass
 
class TrackerEvent(Enum):
    STARTED = 'started'
    COMPLETED = 'completed'
    STOPPED = 'stopped'
    EMPTY = 'empty'


class Tracker(PeerFinder):

    def __init__(self, announce_url, info_hash, peer_id, ip, port, uploaded, downloaded, left, event: TrackerEvent = None):

    def get_peers(self):
        pass

class CompactResponseFormatError(ValueError):
    pass

class TrackerRequest:
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

    @staticmethod
    def decode_compact_response(resp_data: bytes) -> list[Peer]:
        if len(resp_data) % 6 != 0:
            raise CompactResponseFormatError('resp could not be split into 6byte IP+PORT chunks!')

        chunks = (resp_data[s:s + 6] for s in range(0, len(resp_data), 6))

        peers = []
        

    def send(self):
        eparams = urlencode(self.params).encode('utf-8')
        
        with urlopen(self.announce_url, data=eparams) as resp:
            rdata = resp.read().decode()
            if self.params['compact'] == 0:
                try:
                    return bdecode(resp)
                except:
                    return self.decode_compact_response(resp)


