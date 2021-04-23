from abc import ABC, abstractmethod
from enum import Enum
from struct import calcsize, pack, unpack, Struct
from typing import Union

from bitfield import Bitfield
from storage import Block, Request


class MalformedPacketException(ValueError):
    pass

class BittorrentPacketType(Enum):
    HANDSHAKE = -2
    KEEPALIVE = -1 # No type sent, length 0
    CHOKE = 0
    UNCHOKE = 1
    INTERESTED = 2
    UNINTERESTED = 3
    HAVE = 4
    BITFIELD = 5
    REQUEST = 6
    BLOCK = 7  #bep_0003 calls this a 'piece' but 
    CANCEL = 8
    EXTENDED = 14

# Special packet only sent once at beginning
class HandshakePacket:
    brepr = b'\x19BitTorrent protocol' + 8 * b'\x00'
    bspec = Struct('B19sQ20s20s')

    def __init__(self, info_hash, peer_id, reserved=0):
        assert len(info_hash) == len(peer_id) == 20
        self._info_hash = info_hash
        self._peer_id = peer_id

    def __len__(self):
        return self.bspec.size

    def info_hash(self):
        return self._info_hash

    def peer_id(self):
        return self._peer_id

    @classmethod
    def deserialize(cls, buf: bytes) -> HandshakePacket:
        plen, pstr, reserved, info_hash, peer_id = self.brepr.unpack(buf)

        if plen != 19 or pstr != b'Bittorrent Protocol':
            raise MalformedPacketException('HandshakePacket did not start with "\\x19Bittorrent Protocol"')
        
        return HandshakePacket(
            info_hash,
            peer_id
        )

    def serialize(self) -> bytes:
        return self.brepr + self._info_hash + self._peer_id

class BittorrentPacketHeader:
    bspec = Struct('!LB')
    len_bspec = Struct('!L')
    type_bspec = Struct('B')

    def __init__(self, length, ptype: BittorrentPacketType):
        self.length = length
        self.type = ptype

    @classmethod
    def __len__(cls):
        return cls.len_bspec.size + cls.type_bspec.size

    def serialize(self) -> bytes:
        self.bspec.pack(self.length, self.type.value)

    @classmethod
    def deserialize(cls, buf: bytes):
        length, = cls.len_bspec.unpack(buf)
        
        if length == 0:
            ptype = BittorrentPacketType.KEEPALIVE
        else:
            ptype, = cls.type_bspec.unpack(buf[cls.len_bspec:])

        return cls(
            length,
            BittorrentPacketType(ptype)
        )
    
    def body_length(self):
        return self.length

    def type(self):
        return self.type
    

class BittorrentPacket:
    @abstractmethod
    def serialize(self) -> bytes:
        pass

    @staticmethod
    @abstractmethod
    def deserialize(buf: bytes) -> "BittorrentPacket":
        pass

    @abstractmethod
    def __len__(self):
        pass


def SingletonPacket(name: str, packet_type: BittorrentPacketType, byte_repr: bytes):
    byte_repr_len = len(byte_repr)

        
    singleton_pkt_class = type(
        name,
        (BittorrentPacket,),  # TODO: consider adding SingletonPacket as parent class
        {
            '__len__': lambda *args: byte_repr_len,  # *args allow len(cls) and len(instance)
            'type': packet_type,
            'serialize': lambda self: byte_repr,
            # 'deserialize': singleton_pkt_deserialize  # ADDED BELOW (needs singleton_pkt_instance)
        }
    )

    singleton_pkt_instance = singleton_pkt_class()
    setattr(singleton_pkt_class, '__new__', lambda cls: singleton_pkt_instance)

    def singleton_pkt_deserialize(buf: bytes):
        return singleton_pkt_instance

    setattr(singleton_pkt_class, 'deserialize', singleton_pkt_deserialize)

    return singleton_pkt_class


def NoPayloadPacket(name: str, packet_type: BittorrentPacketType):
    if packet_type.value > 255:
        raise ValueError(f'Packet type {packet_type} cannot fit into one byte!')
    
    return SingletonPacket(name, packet_type=packet_type, byte_repr=pack('!LB', 1, packet_type.value))


# Peer Messages

# Choke:: length: 1, type: 0
KeepalivePacket = SingletonPacket('KeepalivePacket', -1, b'')

# Choke:: length: 1, type: 0
ChokePacket = NoPayloadPacket(name='ChokePacket', packet_type=BittorrentPacketType.CHOKE) 

# Unchoke:: length: 1, type: 1
UnchokePacket = NoPayloadPacket(name='UnchokePacket', packet_type=BittorrentPacketType.UNCHOKE) 

# Interested:: length: 1, type: 0
InterestedPacket = NoPayloadPacket(name='InterestedPacket', packet_type=BittorrentPacketType.INTERESTED)

# Uninterested:: length: 1, type: 0
UninterestedPacket = NoPayloadPacket(name='UninterestedPacket', packet_type=BittorrentPacketType.UNINTERESTED)


class HavePacket(BittorrentPacket):
    type = BittorrentPacketType.HAVE
    bspec = Struct('!LBL')
    body_bspec = Struct('!L')

    def __init__(self, piece_index):
        self.completed_piece_index = piece_index
    
    def piece_index(self):
        return self.completed_piece_index

    def serialize(self):
        return self.bspec.pack(self.bspec.size, self.type.value, self.completed_piece_index)

    @classmethod
    def deserialize(cls, buf: bytes) -> "HavePacket":
        piece_index, = cls.body_bspec.unpack_from(buf)

        return cls(piece_index)
        


class BitfieldPacket(BittorrentPacket):
    type = BittorrentPacketType.BITFIELD
    bspec = Struct('!LB')

    def __init__(self, bitfield: bytes):
        self.bitfield = Bitfield(bitfield)
    
    def bitfield(self):
        return self.bitfield

    def serialize(self):
        return self.bspec.pack(len(self.bitfield) + 1, self.type.value) + bytes(self.bitfield)
    
    @classmethod
    def deserialize(cls, buf: bytes) -> "BitfieldPacket":
        return cls(bitfield=buf)


class RequestPacket(BittorrentPacket):
    type = BittorrentPacketType.REQUEST
    bspec = Struct('!LBLLL')
    body_bspec = Struct('!LLL')

    def __init__(self, r: Request):
        self.req: Request = r

    def serialize(self):
        return self.bspec.pack(
            self.bspec.size,
            self.type.value,
            self.req.index(),
            self.req.begin_offset(),
            self.req.length()
        )
    
    @classmethod
    def deserialize(cls, buf: bytes) -> "RequestPacket":
        piece_index, begin_offset, piece_length = cls.bspec.unpack(buf)

        return cls(
            Request(piece_index, begin_offset, piece_length)
        )

    def request(self) -> Request:
        return self.req
    

class BlockPacket(BittorrentPacket):
    type = BittorrentPacketType.BLOCK
    bspec = Struct('!LBLL')
    body_bspec = Struct('!LL')

    def __init__(self, b: Block):
        self.block: Block = b

    def serialize(self):
        return self.bspec.pack(
            self.bspec.size + len(self.data),
            self.type.value,
            self.block.index(),
            self.block.begin_offset(),
            self.block.data()
        )
    
    @classmethod
    def deserialize(cls, buf: bytes) -> "PiecePacket":
        piece_index, begin_offset = cls.bspec.unpack(buf)
        data = buf[cls.body_bspec.size:]

        return cls(
            Block(piece_index, begin_offset, data)
        )

    def block(self) -> Block:
        return self.block


class CancelPacket(BittorrentPacket, PiecePacket):
    type = BittorrentPacketType.CANCEL


class ExtendedPacket(BittorrentPacket):
    type = BittorrentPacketType.EXTENDED
    


PACKETS_BY_TYPE: dict[BittorrentPacketType, BittorrentPacket] = {
    BittorrentPacketType.CHOKE: ChokePacket,
    BittorrentPacketType.UNCHOKE: UnchokePacket,
    BittorrentPacketType.INTERESTED: InterestedPacket,
    BittorrentPacketType.UNINTERESTED: UninterestedPacket,
    BittorrentPacketType.HAVE: HavePacket,
    BittorrentPacketType.BITFIELD: BitfieldPacket,
    BittorrentPacketType.REQUEST: RequestPacket,
    BittorrentPacketType.PIECE: PiecePacket,
    BittorrentPacketType.CANCEL: CancelPacket
}

@coroutine
def read_next_packet(reader: StreamReader):

    try:
        # Read header to get length
        header_bytes = yield from reader.readexactly(len(BittorrentPacketHeader))
        header: BittorrentPacketHeader = BittorrentPacketHeader.deserialize(header_bytes)



        # Read inner packet
        pkt_len = header.packet_length
        next_packet_body = yield from reader.readexactly(pkt_len)
        next_packet = PACKETS_BY_TYPE[header.type()].deserialize(next_packet_body)

        return next_packet

    except Exception as e:
        print(e)
        raise MalformedPacketException(e)

@coroutine
def read_handshake_response(reader: StreamReader):
    handshake_resp_bytes = yield from reader.readexactly(len(HandshakePacket))
    handshake_resp = HandshakePacket.deserialize(handshake_resp_bytes)

    return handshake_resp
    

@coroutine
def send_packet(writer: StreamWriter, packet: BittorrentPacket):
    writer.write(packet.serialize())
    yield from writer.drain()


def self_test():
    c = ChokePacket()
    c2 = ChokePacket()

    assert c is c2
    assert c.serialize() == b'\x00\x00\x00\x01\x00'

    u = UnchokePacket()
    u2 = UnchokePacket()


    assert u is u2
    assert u.serialize() == b'\x00\x00\x00\x01\x01'

    assert ChokePacket.type == BittorrentPacketType.CHOKE
    assert HavePacket.type == BittorrentPacketType.HAVE
    assert ExtendedPacket.type == BittorrentPacketType.EXTENDED

    expected_bits = [1, 1, 1, 1, 0, 0, 0, 1,] + ([0] * 8) + ([1] + [0] * 6 + [1])
    b = Bitfield(b'\xF1\x00\x81')

    assert b.get(0) == 1
    assert b.get(1) == 1
    assert b.get(2) == 1
    assert b.get(3) == 1
    assert b.get(4) == 0
    assert b.get(5) == 0
    assert b.get(6) == 0
    assert b.get(7) == 1
    assert b.get(8) == 0
    assert b.get(15) == 0
    assert b.get(16) == 1
    assert b.get(17) == 0
    assert b.get(22) == 0
    assert b.get(23) == 1

    actual_bits = list(b)
    if actual_bits != expected_bits:
        print(f'Expected: {expected_bits}\nGot: {actual_bits}')
        assert actual_bits == expected_bits

    print('Self test succeeded!')

if __name__ == '__main__':
    self_test()