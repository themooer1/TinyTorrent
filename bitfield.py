
class Bitfield:
    def __init__(self, bitfield: bytes):
        self.bitfield = bitfield

    def get(self, index):
        return (self.bitfield[index // 8] >> (7 - (index % 8))) & 1

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


class MutableBitfield(Bitfield):
    def __init__(self, bitfield: Union[int, bytes, bytearray]):
        if type(bitfield) != bytearray:
            self.bitfield = bytearray(bitfield)
        self.bitfield = bitfield

    def __bytes__(self):
        return bytes(self.bitfield)
    
    def set(self, index):
        self.bitfield[index // 8] |= 1 << (index % 8)
    
    def set(self, index):
        self.bitfield[index // 8] &= ~(1 << (index % 8))