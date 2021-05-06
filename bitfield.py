from math import ceil
from typing import Union


class Bitfield:
    def __init__(self, bitfield: bytes):
        self._bitfield = bitfield
        self._num_set = sum(self)

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            if self._bitfield == other._bitfield:
                assert self._num_set == other._num_set
                return True
        return False

    def get(self, index):
        return (self._bitfield[index // 8] >> (7 - (index % 8))) & 1

    def num_bytes(self):
        return len(self._bitfield)

    def num_set(self):
        return self._num_set

    def fraction_set(self):
        return self.num_set() / len(self)

    def __bytes__(self):
        return self._bitfield

    def __iter__(self):
        for i in range(0, len(self._bitfield)):
            yield self._bitfield[i] >> 7 & 1
            yield self._bitfield[i] >> 6 & 1
            yield self._bitfield[i] >> 5 & 1
            yield self._bitfield[i] >> 4 & 1
            yield self._bitfield[i] >> 3 & 1
            yield self._bitfield[i] >> 2 & 1
            yield self._bitfield[i] >> 1 & 1
            yield self._bitfield[i] & 1

    def __len__(self):
        return len(self._bitfield) * 8


# class ChainedBitfield(Bitfield):
#     def __init__(self, bf1: Bitfield, bf2: Bitfield):
#         self.bf1 = bf1
#         self.bf2 = bf2

#    def get(self, index):
#        b1_len = len(self.bf1) 

#        if index > b1_len:
#            return self.bf2(index - b1_len)
#         return self.bf1(index)

#     def __bytes__(self):
#         bytes(self.bf1) + bytes(self.bf2)

#     def __iter__(self):
#         yield from self.bf1
#         yield from self.bf2

#     def __len__(self):
#         len(self.bf1) + len(self.bf2)


class MutableBitfield(Bitfield):
    def __init__(self, bitfield: Union[int, bytes, bytearray, Bitfield]):
        if type(bitfield) is int:
            self._bitfield = bytearray(ceil(bitfield / 8))
        elif type(bitfield) is bytes:
            self._bitfield = bytearray(bitfield)
        elif type(bitfield) is Bitfield:
            self._bitfield = bytearray(bitfield._bitfield)
        else:
            self._bitfield = bitfield

        self._num_set = sum(self)

    def __bytes__(self):
        return bytes(self._bitfield)

    def set(self, index):
        if self.get(index) == 0:
            self._num_set += 1
        self._bitfield[index // 8] |= 1 << (index % 8)

    def unset(self, index):
        if self.get(index) == 1:
            self._num_set -= 1
        self._bitfield[index // 8] &= ~(1 << (index % 8))
