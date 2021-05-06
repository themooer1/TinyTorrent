from hashlib import sha1

from hypothesis import given
from hypothesis.strategies import binary, builds, composite, integers, one_of, sampled_from, text
from hypothesis.core import SearchStrategy

from storage import Request, Block, Piece, BLOCK_LEN

block_lengths = integers(min_value=0)
valid_block_lengths = sampled_from([0, BLOCK_LEN])
piece_indices = integers(min_value=0, max_value=0xFFFFFFFF)
piece_data = binary()


@composite
def piece_and_data_pairs(draw):
    piece_id = draw(piece_indices)
    data = draw(piece_data)
    data_hash = sha1(data).digest()

    p = Piece(piece_id, data_hash, len(data))

    return p, data


@composite
def piece_and_blocks_pairs(draw):
    p, data = draw(piece_and_data_pairs())

    blocks = []
    nxt_blk_off = 0

    while nxt_blk_off < len(data):
        nxt_blk_len = min(draw(valid_block_lengths), len(data) - nxt_blk_off)
        b = Block(
            piece_index=p.index,
            begin_offset=nxt_blk_off,
            data=data[nxt_blk_off:nxt_blk_off + nxt_blk_len]
        )

        blocks.append(b)
        nxt_blk_off += nxt_blk_len

    return p, blocks


@given(piece_and_blocks_pairs())
def test_fill_piece(piece_and_blocks):
    p, blks = piece_and_blocks

    p: Piece = p

    for b in blks:
        assert not p.complete()
        assert not p.verify()

        p.save_block(b)

    assert p.complete()
    assert p.verify()

    p.reset()

    assert p.num_blocks >= 0

    if p.num_blocks > 0:
        assert not p.complete()
        assert not p.verify()


def simple_piece_request():
    data = b'\x00'
    piece = Piece(
        index=0,
        checksum=b'[\xa9<\x9d\xb0\xcf\xf9?R\xb5!\xd7B\x0eC\xf6\xed\xa2xO',
        length=1
    )

    r = piece.next_request()
    assert r
    assert r.index() == 0
    assert r.begin_offset() == 0
    assert r.length() == 1

    b = Block(
        piece_index=0,
        begin_offset=0,
        data=data  # ¡Special Case! All the data can fit in this one block
    )

    assert not piece.complete()
    assert not piece.verify()

    piece.save_block(b)

    assert piece.complete()
    assert piece.verify()

    # Nothing should change if same block is added again
    piece.save_block(b)

    assert piece.complete()
    assert piece.verify()


def make_block_for_request(r: Request, data: bytes):
    requested_data = data[r.begin_offset(): r.begin_offset() + r.length()]

    b = Block(
        piece_index=r.index(),
        begin_offset=r.begin_offset(),
        data=requested_data
    )

    return b


@given(piece_and_data_pairs())
def test_requests_complete_piece(piece_and_data):
    p, data = piece_and_data

    previous_requests = set()

    r = p.next_request()
    while r:
        # All requests are immediately fulfilled, so none should occur twice
        if r in previous_requests:
            print(r)
        assert r not in previous_requests
        previous_requests.add(r)

        b = make_block_for_request(r, data)
        p.save_block(b)

        # Get next request
        r = p.next_request()

    assert p.complete()
    assert p.verify()

    p.reset()

    assert p.num_blocks >= 0

    if p.num_blocks > 0:
        assert not p.complete()
        assert not p.verify()

    assert len(data) == 0 or p.next_request() is not None


