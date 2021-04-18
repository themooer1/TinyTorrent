import argparse
import random

from enum import Enum
from hashlib import sha1
from urllib.request import Request, urlencode, urlopen

PEER_ID_LEN = 20



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



