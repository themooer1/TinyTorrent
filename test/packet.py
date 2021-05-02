from hypothesis import given
from hypothesis.strategies import binary, builds, composite, integers, one_of, sampled_from, text
from hypothesis.core import SearchStrategy

from bitfield import Bitfield
from packet import *
from storage import Request, Block

peer_ids = binary(min_size=20, max_size=20)
info_hashes = binary(min_size=20, max_size=20)
bitfields = binary(min_size=1, max_size=37)  # Small bitfields for now

@composite
def block_requests(draw) -> SearchStrategy[Request]:
    idx = draw(bt_ints)
    off, length = sorted((draw(bt_ints), draw(bt_ints)))

    return Request(
        piece_index=idx,
        begin_offset=off,
        length=length
    )

@composite
def blocks(draw) -> SearchStrategy[Block]:
    idx = draw(bt_ints)
    off = draw(bt_ints)


    return Block(
        piece_index=idx,
        begin_offset=off,
        data=draw(binary())
    )


# Ints in BT wire proto (Except first byte of handshake) are 4Byte unsigned network byte order
bt_ints = integers(0, 0xFFFFFFFF)

singleton_pkt_classes = sampled_from(
    (
        KeepalivePacket,
        ChokePacket,
        UnchokePacket,
        InterestedPacket,
        UninterestedPacket
    )
)

@composite
def singleton_pkts(draw):
    p = draw(singleton_pkt_classes)()
    # print(p)
    # print(type(p))
    return p

handshake_pkts = builds(HandshakePacket, info_hash=info_hashes, peer_id=peer_ids)

have_pkts = builds(HavePacket, piece_index=bt_ints)
bitfield_pkts = builds(BitfieldPacket, bitfield=bitfields)
request_pkts = builds(RequestPacket, r=block_requests())
block_pkts = builds(BlockPacket, b=blocks())
cancel_pkts = builds(CancelPacket, r=block_requests())

bt_pkts = one_of(
    # handshake_pkts,
    singleton_pkts(),
    have_pkts,
    bitfield_pkts,
    request_pkts,
    block_pkts,
    cancel_pkts
)



# print('hi')
# # print(request_pkts.example())
# # print(block_requests.example())
# # print(ct().example())
# print('hi')

# print(peer_ids.example())
# print(info_hashes.example())
# print(handshake_pkts.example())

@given(singleton_pkt_classes)
def test_singleton_pkt_eq(pkt_cls):
    p1 = pkt_cls()
    p2 = pkt_cls()

    assert p1 == p2
    assert p1 is p2

@given(bt_pkts)
def test_enc_len(pkt: BittorrentPacket):
    pkt_bytes = pkt.serialize()
    # print(len(pkt_bytes))
    # print(len(pkt))
    try:
        assert len(pkt_bytes) == len(pkt)
    except TypeError as e:
        print('LEN MISMATCH!')
        print(pkt)
        print(pkt_bytes)
        print(len(pkt_bytes))
        print(len(pkt))
        raise e

@given(bt_pkts)
def test_enc_dec(pkt: BittorrentPacket):
    pkt_bytes = pkt.serialize()
        
    h = BittorrentPacketHeader.deserialize(pkt_bytes)
    pkt_cls = PACKETS_BY_TYPE[h.type()]
    assert pkt_cls == type(pkt)

    assert len(pkt) == 4 + 1 + h.body_length()


    pkt_unserialized = pkt_cls.deserialize(pkt_bytes[-h.body_length():])
    assert pkt == pkt_unserialized


@given(handshake_pkts)
def test_handshake_enc_dec(pkt: HandshakePacket):
    pkt_bytes = pkt.serialize()
        
    assert len(pkt) == len(pkt_bytes)
    pkt_unserialized = HandshakePacket.deserialize(pkt_bytes)
    assert pkt == pkt_unserialized



