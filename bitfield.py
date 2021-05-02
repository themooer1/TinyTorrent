from typing import Union


class Bitfield:
    def __init__(self, bitfield: bytes):
        self.bitfield = bitfield
        self.num_set = None

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            if self.bitfield == other.bitfield:
                assert self.num_set == other.num_set
                return True
        return False


    def get(self, index):
        return (self.bitfield[index // 8] >> (7 - (index % 8))) & 1
    
    def num_bytes(self):
        return len(self.bitfield)

    def num_set(self):
        return num_set

    def fraction_set(self):
        return self.num_set() / len(self)

    def __bytes__(self):
        return self.bitfield
    
    def __iter__(self):
        for i in range(0, len(self.bitfield)):
            yield self.bitfield[i] >> 7 & 1
            yield self.bitfield[i] >> 6 & 1
            yield self.bitfield[i] >> 5 & 1
            yield self.bitfield[i] >> 4 & 1
            yield self.bitfield[i] >> 3 & 1
            yield self.bitfield[i] >> 2 & 1
            yield self.bitfield[i] >> 1 & 1
            yield self.bitfield[i] & 1

    def __len__(self):
        return len(self.bitfield) * 8

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
    def __init__(self, bitfield: Union[int, bytes, bytearray]):
        if type(bitfield) != bytearray:
            self.bitfield = bytearray(bitfield)
        self.bitfield = bitfield

    def __bytes__(self):
        return bytes(self.bitfield)
    
    def set(self, index):
        if self.get(index) == 0:
            self.num_set += 1
        self.bitfield[index // 8] |= 1 << (index % 8)
    
    def unset(self, index):
        if self.get(index) == 1:
            self.num_set -= 1
        self.bitfield[index // 8] &= ~(1 << (index % 8))