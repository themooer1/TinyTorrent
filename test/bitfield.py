from hashlib import sha1

from hypothesis import given
# from hypothesis.strategies import binary, builds, composite, integers, lists, one_of, sampled_from, sets, text
from hypothesis.strategies import booleans, lists
from hypothesis.core import SearchStrategy

from bitfield import Bitfield, MutableBitfield
# from storage import Request, Block, Piece, BLOCK_LEN

bool_lists = lists(booleans())


@given(bool_lists)
def test_fill_bitfield(bool_list):
    bf = MutableBitfield(len(bool_list))
    for i, b in enumerate(bool_list):
        if b:
            bf.set(i)

    assert bf.num_set() == sum(bool_list)

    for i, b in enumerate(bool_list):
        assert bf.get(i) == b


