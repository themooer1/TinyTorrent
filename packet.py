from abc import ABC, abstractmethod
from asyncio import coroutine, StreamReader, StreamWriter, IncompleteReadError
from enum import Enum
from struct import calcsize, pack, unpack, Struct
from typing import Union

from bitfield import Bitfield
from storage import Block, Request


class MalformedPacketException(ValueError):
    pass

class PeerDisconnected(Exception):
    pass

class PeerError(Exception):
    """For when a Bittorrent peer does someting fishy"""
    pass


class BittorrentPacketType(Enum):
    HANDSHAKE = -2
    KEEPALIVE = -1  # No type sent, length 0
    CHOKE = 0
    UNCHOKE = 1
    INTERESTED = 2
    UNINTERESTED = 3
    HAVE = 4
    BITFIELD = 5
    REQUEST = 6
    BLOCK = 7  # bep_0003 calls this a 'piece' but
    CANCEL = 8
    EXTENDED = 14


# Special packet only sent once at beginning
class HandshakePacket:
    # Hex Const vv  is 19 in decimal         
    brepr = b'\x13BitTorrent protocol' + 8 * b'\x00'
    bspec = Struct('!B19sQ20s20s')

    def __init__(self, info_hash: bytes, peer_id, reserved=0):
        try:
            assert len(info_hash) == 20
            assert len(peer_id) == 20
        except AssertionError as e:
            print(f'info hash: {info_hash}')
            print(f'info hash len: {len(info_hash)}')
            print(f'peer id: {peer_id}')
            print(f'peer id len: {len(peer_id)}')
            raise e

        self._info_hash = info_hash
        self._peer_id = bytes(peer_id, encoding='utf8') if isinstance(peer_id, str) else peer_id

    def __eq__(self, other):
        if isinstance(other, type(self)):
            return self._info_hash == other._info_hash and self._peer_id == other._peer_id
        return False

    def __len__(self):
        return self.bspec.size

    @classmethod
    def size(cls):
        return cls.bspec.size

    def __repr__(self):
        return f'HandshakePacket(\n\tinfo_hash={self.info_hash()},\n\tpeer_id={self.peer_id()}\n)'

    def info_hash(self):
        return self._info_hash

    def peer_id(self):
        return self._peer_id

    @classmethod
    def deserialize(cls, buf: bytes) -> "HandshakePacket":
        plen, pstr, reserved, info_hash, peer_id = cls.bspec.unpack(buf)

        if plen != 19 or pstr != b'BitTorrent protocol':
            print(buf)
            print(plen)
            print(plen)
            raise MalformedPacketException('HandshakePacket did not start with "\\x19Bittorrent protocol"')

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
        self.ptype = ptype

    def __eq__(self, other):
        if isinstance(other, type(self)):
            return self.length == other.length and self.type() == other.type()
        return False

    @classmethod
    def __len__(cls):
        return cls.len_bspec.size + cls.type_bspec.size

    def __repr__(self):
        return f'{self.__class__.__name__}(\n\tlength={self.body_length() + 1}\n\tbody_length={self.body_length()},\n\ttype={self.type()}\n)'

    @classmethod
    def size(cls):
        return cls.bspec.size

    def serialize(self) -> bytes:
        self.bspec.pack(self.length, self.type().value)

    @classmethod
    def deserialize(cls, buf: bytes):
        length, = cls.len_bspec.unpack_from(buf)

        if length == 0:
            ptype = BittorrentPacketType.KEEPALIVE
        else:
            ptype, = cls.type_bspec.unpack_from(buf[cls.len_bspec.size:])

        return cls(
            length,
            BittorrentPacketType(ptype)
        )

    def body_length(self):
        return self.length - 1  # Exclude pkt type byte

    def type(self):
        return self.ptype


class BittorrentPacket:
    @abstractmethod
    def serialize(self) -> bytes:
        pass

    @staticmethod
    @abstractmethod
    def deserialize(buf: bytes) -> "BittorrentPacket":
        pass

    # @abstractmethod
    def __len__(self):
        return self.bspec.size


def SingletonPacket(name: str, packet_type: BittorrentPacketType, byte_repr: bytes):
    byte_repr_len = len(byte_repr)

    singleton_pkt_class = type(
        name,
        (BittorrentPacket,),  # TODO: consider adding SingletonPacket as parent class
        {
            '__len__': lambda *args: byte_repr_len,  # *args allow len(cls) and len(instance)
            'size': lambda *args: byte_repr_len,
            '__str__': lambda self: self.__class__.__name__,
            'type': packet_type,
            'serialize': lambda self: byte_repr,
            # 'deserialize': singleton_pkt_deserialize  # ADDED BELOW (needs singleton_pkt_instance)
        }
    )

    singleton_pkt_instance = singleton_pkt_class()
    setattr(singleton_pkt_class, '__new__', lambda cls: singleton_pkt_instance)
    setattr(singleton_pkt_class, '__eq__', lambda self, other: isinstance(other, type(singleton_pkt_instance)))

    # def singleton_pkt_deserialize(cls, buf: bytes):
    def singleton_pkt_deserialize(*args):
        # print('fjfi')
        # print(args)
        return singleton_pkt_instance

    setattr(singleton_pkt_class, 'deserialize', singleton_pkt_deserialize)

    return singleton_pkt_class


def NoPayloadPacket(name: str, packet_type: BittorrentPacketType):
    if packet_type.value > 255:
        raise ValueError(f'Packet type {packet_type} cannot fit into one byte!')

    return SingletonPacket(name, packet_type=packet_type, byte_repr=pack('!LB', 1, packet_type.value))


# Peer Messages

# Choke:: length: 1, type: 0
KeepalivePacket = SingletonPacket('KeepalivePacket', BittorrentPacketType.KEEPALIVE, b'\x00' * 4)

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

    def __repr__(self):
        return f'HavePacket(info_hash={self.piece_index()})'

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.completed_piece_index == other.completed_piece_index
        return False

    def piece_index(self):
        return self.completed_piece_index

    def serialize(self):
        return self.bspec.pack(self.body_bspec.size + 1, self.type.value, self.completed_piece_index)

    @classmethod
    def size(cls):
        return cls.bspec.size

    @classmethod
    def deserialize(cls, buf: bytes) -> "HavePacket":
        piece_index, = cls.body_bspec.unpack_from(buf)

        return cls(piece_index)


class BitfieldPacket(BittorrentPacket):
    type = BittorrentPacketType.BITFIELD
    bspec = Struct('!LB')

    def __init__(self, bitfield: bytes):
        self.b = Bitfield(bitfield)

    def __repr__(self):
        return f'BitfieldPacket(\n\tbitfield={self.b.bitfield}\n)'

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.bitfield() == other.bitfield()
        return False

    def __len__(self):
        return self.bspec.size + self.bitfield().num_bytes()

    def bitfield(self) -> Bitfield:
        return self.b

    def serialize(self):
        return self.bspec.pack(self.bitfield().num_bytes() + 1, self.type.value) + bytes(self.bitfield())

    @classmethod
    def deserialize(cls, buf: bytes) -> "BitfieldPacket":
        return cls(bitfield=buf)


class RequestPacket(BittorrentPacket):
    type = BittorrentPacketType.REQUEST
    bspec = Struct('!LBLLL')
    body_bspec = Struct('!LLL')

    def __init__(self, r: Request):
        self.req: Request = r

    def __repr__(self):
        return f'{self.__class__.__name__}(\n\tr={repr(self.request())}\n)'

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.req == other.req
        return False

    def serialize(self):
        return self.bspec.pack(
            self.body_bspec.size + 1,
            self.type.value,
            self.req.index(),
            self.req.begin_offset(),
            self.req.length()
        )

    @classmethod
    def deserialize(cls, buf: bytes) -> "RequestPacket":
        piece_index, begin_offset, piece_length = cls.body_bspec.unpack(buf)

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
        self.b: Block = b

    def __repr__(self):
        return f'BlockPacket(\n\tb={repr(self.block())}\n)'

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.b == other.b
        return False

    def __len__(self):
        return self.bspec.size + len(self.b.data())

    def serialize(self):
        return self.bspec.pack(
            self.body_bspec.size + 1 + len(self.b.data()),
            self.type.value,
            self.b.index(),
            self.b.begin_offset(),
        ) + self.b.data()

    @classmethod
    def deserialize(cls, buf: bytes) -> "PiecePacket":
        piece_index, begin_offset = cls.body_bspec.unpack_from(buf)
        data = buf[cls.body_bspec.size:]

        return cls(
            Block(piece_index, begin_offset, data)
        )

    def block(self) -> Block:
        return self.b


class CancelPacket(RequestPacket):
    type = BittorrentPacketType.CANCEL


class ExtendedPacket(BittorrentPacket):
    type = BittorrentPacketType.EXTENDED


# PACKETS_BY_TYPE: dict[BittorrentPacketType, BittorrentPacket] = {
PACKETS_BY_TYPE = {
    BittorrentPacketType.HANDSHAKE: HandshakePacket,
    BittorrentPacketType.KEEPALIVE: KeepalivePacket,
    BittorrentPacketType.CHOKE: ChokePacket,
    BittorrentPacketType.UNCHOKE: UnchokePacket,
    BittorrentPacketType.INTERESTED: InterestedPacket,
    BittorrentPacketType.UNINTERESTED: UninterestedPacket,
    BittorrentPacketType.HAVE: HavePacket,
    BittorrentPacketType.BITFIELD: BitfieldPacket,
    BittorrentPacketType.REQUEST: RequestPacket,
    BittorrentPacketType.BLOCK: BlockPacket,
    BittorrentPacketType.CANCEL: CancelPacket
}


@coroutine
def read_next_packet(reader: StreamReader):
    try:
        # Read header to get length
        header_bytes = yield from reader.readexactly(BittorrentPacketHeader.size())
        header: BittorrentPacketHeader = BittorrentPacketHeader.deserialize(header_bytes)

        # Read inner packet
        pkt_len = header.body_length()
        next_packet_body = yield from reader.readexactly(pkt_len)
        next_packet = PACKETS_BY_TYPE[header.type()].deserialize(next_packet_body)

        return next_packet

    except IncompleteReadError:
        raise PeerDisconnected()

    except ValueError as e:
        print(e)
        try:
            print(header)
        except:
            print('header was not defined')

    except Exception as e:
        print(e)

        # raise e


@coroutine
def read_handshake_response(reader: StreamReader) -> HandshakePacket:
    try:
        handshake_resp_bytes = yield from reader.readexactly(HandshakePacket.size())
    except (ConnectionResetError, IncompleteReadError):
        raise PeerDisconnected()

    handshake_resp = HandshakePacket.deserialize(handshake_resp_bytes)

    return handshake_resp


@coroutine
def send_packet(writer: StreamWriter, packet: Union[BittorrentPacket, HandshakePacket]):
    writer.write(packet.serialize())

    try:
        yield from writer.drain()
    except ConnectionError:
        raise PeerDisconnected()


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

    expected_bits = [1, 1, 1, 1, 0, 0, 0, 1, ] + ([0] * 8) + ([1] + [0] * 6 + [1])
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
