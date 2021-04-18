from abc import ABC, abstractmethod

from bitfield import MutableBitfield
from storage import Piece, Request

class PeerFinder(ABC):

    @abstractmethod
    def get_peers(self) -> list[Peer]:
        pass


class Peer:
    def __init__(self, swarm: Swarm, pid, num_pieces: int, choked=True, interested=False):
        self.pid = pid
        self.choked = choked
        self.interested = interested
        self.bitfield = MutableBitfield(bytearray(num_pieces))
    
    def has_index(self, index: int) -> bool:
        return self.bitfield.get(index)

    def has(self, piece: Union[int, Piece, Request]) -> bool:
        if issubclass(piece, Piece) or issubclass(piece, Request):
            index = piece.index()
        else:
            index = piece
        
        return self.has_index(index)

    def request_piece(self, r: Request):
        pass


class Swarm:
    def __init__(self, torrent: Torrent, finder: PeerFinder):
        self.peers = []
        # Nothing else made it clear who was sending to whom XD
        self.peers_im_downloading_from = []
        self.peers_im_sending_to = {}