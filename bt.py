import argparse
import random

from bencode import bencode, bdecode
from enum import Enum
from hashlib import sha1
from urllib.request import Request, urlencode, urlopen

PEER_ID_LEN = 20

class TrackerFailureException(Exception):
    pass
 
class TrackerEvent(Enum):
    STARTED = 'started'
    COMPLETED = 'completed'
    STOPPED = 'stopped'
    EMPTY = 'empty'


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
        

    def send(self):
        eparams = urlencode(self.params).encode('utf-8')
        
        with urlopen(self.announce_url, data=eparams) as resp:
            rdata = resp.read().decode()
            if self.params['compact'] == 0:
                try:
                    return bdecode(resp)
                except:
                    return self.decode_compact_response(resp)




class Torrent:
    def __init__(self, filename):
        with open(filename, 'rb') as f:
            torrent_d = bdecode(f)
            print(torrent_d.keys())
            print(torrent_d['info']['length'])
            print(torrent_d['info']['name'])
            print(torrent_d['info']['piece length'])
            print(len(torrent_d['info']['pieces']))
            print(torrent_d['info'].keys())
            print(torrent_d['announce'])

            self.announce_url = torrent_d['announce']
            self.info = torrent_d['info']

            self.files = []
            try:
                f = TorrentFile()
                self.length = self.info['length']
                

    def announce_url(self):
        return self.announce_url

    def info(self):
        return self.info

    def download_size(self):
        return self.length


class Peer:
    def __init__(self, pid, choked=True, interested=False):
        self.pid = pid
        self.choked = choked
        self.interested = interested



class Downloader:
    def __init__(self, file: TorrentFile, ip, port):
        self.file = file
        self.pid = random.SystemRandom.getrandbits(PEER_ID_LEN * 8).to_bytes(PEER_ID_LEN, byteorder='little')
        info_hash = sha1(bencode(self.file.info()))
        tracker_request = TrackerRequest(
            announce_url=file.announce_url,
            info_hash=info_hash,
            peer_id=self.pid,
            ip=ip,
            port=port,
            uploaded=0,
            downloaded=0,
            left=self.file.download_size(),
            event=None
        )
    


def download_torrent(filename):
    t = Torrent(filename)
    d = Downloader(t)

def main():
    p = argparse.ArgumentParser("BT", description="Download torrent files.")
    p.add_argument("torrent_file")
    
    args = p.parse_args()
    
    download_torrent(args.torrent_file)


if __name__ == "__main__":
    main()



