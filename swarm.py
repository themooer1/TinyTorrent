from abc import ABC, abstractmethod

class PeerFinder(ABC):

    @abstractmethod
    def get_peers(self) -> list[Peer]:
        pass


class Peer:
    def __init__(self, pid, choked=True, interested=False):
        self.pid = pid
        self.choked = choked
        self.interested = interested


class Swarm:
    def __init__(self,)