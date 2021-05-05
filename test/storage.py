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







