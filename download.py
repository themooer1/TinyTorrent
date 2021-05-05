import argparse
import asyncio
import random

from tracker import Tracker
from storage import PieceIO, PieceManager
from swarm import Swarm, PEER_PORT as PORT
from torrent import Torrent

HOST = 'mooblek.com'
# PORT = 1955
PEER_ID = 'OceanC2222-XXXX-YYYY'
PEER_ID_LEN = 20

# PEER_ID = random.SystemRandom.getrandbits(PEER_ID_LEN * 8).to_bytes(PEER_ID_LEN, byteorder='little')

class Downloader:
    def __init__(self, file, ip, port):
        self.torrent = Torrent(file)

        piece_io = PieceIO(self.torrent)
        piece_mgr = PieceManager(
            t = self.torrent,
            io = piece_io
        )

        tracker = Tracker(
            peer_id = PEER_ID,
            torrent = self.torrent,
            listening_host = HOST,
            listening_port = 1955
        )
        self.swarm = Swarm(
            self.torrent,
            manager = piece_mgr,
            finder = tracker
        )
    
    def start(self):
        loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()

        loop.run_until_complete(
            self.swarm.start()
        )


def download_torrent(filename):
    d = Downloader(filename, HOST, PORT)
    d.start()

def main():
    p = argparse.ArgumentParser("BT", description="Download torrent files.")
    p.add_argument("torrent_file")
    
    args = p.parse_args()
    
    download_torrent(args.torrent_file)


if __name__ == "__main__":
    main()



