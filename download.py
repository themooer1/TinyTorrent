import argparse
import asyncio
import random

from tracker import Tracker, DummyTracker, Peer
from storage import PieceIO, PieceManager
from swarm import Swarm
from torrent import Torrent

HOST = 'mooblek.com'
# PORT = 1955
PEER_ID = 'OceanC2222-XXXX-YYYY'
PEER_ID_LEN = 20


# PEER_ID = random.SystemRandom.getrandbits(PEER_ID_LEN * 8).to_bytes(PEER_ID_LEN, byteorder='little')

class Downloader:
    def __init__(self, file, dl_dir, ip, port, direct_host=None, direct_port=None):
        self.torrent = Torrent(file, dl_dir)

        piece_io = PieceIO(self.torrent)
        piece_mgr = PieceManager(
            t=self.torrent,
            io=piece_io
        )

        if direct_host and direct_port:
            tracker = DummyTracker(
                Peer(id='', host=direct_host, port=direct_port)
            )

        else:
            tracker = Tracker(
                peer_id=PEER_ID,
                torrent=self.torrent,
                listening_host=ip,
                listening_port=port
            )

        self.swarm = Swarm(
            self.torrent,
            manager=piece_mgr,
            finder=tracker,
            port=port
        )

    def start(self):
        loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()

        loop.run_until_complete(
            self.swarm.start()
        )


def download_torrent(filename, dl_dir, public_port, dhost=None, dport=None):
    d = Downloader(filename, dl_dir, HOST, public_port, direct_host=dhost, direct_port=dport)
    d.start()


def main():
    p = argparse.ArgumentParser("BT", description="Download torrent files.")
    p.add_argument("torrent_file")
    p.add_argument("-p", "--port", type=int, required=True)
    p.add_argument("-d", "--download-dir", required=True)
    p.add_argument("--direct")

    args = p.parse_args()

    dhost = None
    dport = None
    if args.direct:
        print(f'Making direct connection to {args.direct}')
        dhost, dport = args.direct.split(':')

    download_torrent(args.torrent_file, args.download_dir, args.port, dhost, dport)


if __name__ == "__main__":
    main()
