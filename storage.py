from abc import ABC, abstractmethod
from collections import deque
from hashlib import sha1
from random import shuffle

from bitfield import MutableBitfield
# from packet import PiecePacket, RequestPacket
from torrent import Torrent, TorrentFile

BLOCK_EXP = 14
BLOCK_LEN = int(1 << 14)


class PieceVerificationException(Exception):
    pass


class Request:
    def __init__(self, piece_index: int, begin_offset: int, length: int):
        self.__piece_idx = piece_index
        self.__begin_offset = begin_offset
        self.__length = length

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.index() == other.index() and self.begin_offset() == other.begin_offset() and self.length() == other.length()
        return False

    def __hash__(self):
        return self.index() * 19 + self.begin_offset()

    def __repr__(self):
        return f'Request(\n\tpiece_index={self.index()},\n\tbegin_offset={self.begin_offset()},\n\tlength={self.length()}\n)'

    def index(self) -> int:
        return self.__piece_idx

    def begin_offset(self) -> int:
        return self.__begin_offset

    def length(self) -> int:
        return self.__length


class Block:

    def __init__(self, piece_index: int, begin_offset: int, data: bytes):
        self.piece_index = piece_index
        self.begin_off = begin_offset
        self.dat = data

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.index() == other.index() and self.begin_offset() == other.begin_offset() and self.data() == other.data()
        return False

    def __hash__(self):
        return self.index() * 19 + self.begin_offset()

    def __repr__(self):
        return f'Block(\n\tpiece_index={self.index()},\n\tbegin_offset={self.begin_offset()},\n\tdata={self.data()}\n)'

    def index(self) -> int:
        return self.piece_index

    def begin_offset(self) -> int:
        return self.begin_off

    def data(self) -> bytes:
        return self.dat


# def fill_file(blocks: iter[Block], start_offset: int = 0):
def fill_file(blocks: iter, start_offset: int = 0):
    ''' Writes blocks into multiple TorrentFiles sent into the generator '''
    # bytes_left_in_file = f.length - start_offset
    bytes_written = 0

    # Get first file to fill starting at start_offset
    # dst_file: TorrentFile = yield bytes_written
    dst_file = yield bytes_written
    dst_file.file.seek(start_offset)

    for b in blocks:
        # Bytes left to write in this block
        bbytes_remaining = len(b.data())

        while bbytes_remaining > 0:
            # Num of bytes we can write to this file
            bbytes_to_write = min(bbytes_remaining, dst_file.length)

            assert bbytes_to_write >= 0

            if bbytes_to_write == 0:
                # If 0, we need a new file
                dst_file = yield bytes_written
                dst_file.file.seek(0)

            else:
                # If > 0, write as many as we can
                dst_file.file.write(b.data()[bytes_written: bytes_written + bbytes_to_write])
                bytes_written += bbytes_to_write

    return bytes_written


class Piece:
    def __init__(self, index: int, checksum: bytes, length: int):
        self.index = index
        self.checksum = checksum
        self.length = length

        self.num_blocks = length // BLOCK_LEN
        last_block_len = length % BLOCK_LEN
        if last_block_len > 0:
            self.num_blocks += 1

        # Reset downloaded blocks and requests
        self.reset()

    def __repr__(self):
        return f'Piece(\n\tpiece_index={self.index},\n\tchecksum={self.checksum},\n\tlength={self.length}\n\tnum_blocks={self.num_blocks}\n\tcompleted_blocks={self.completed_blocks}\n)'

    def reset(self):
        """Clear all downloaded blocks, and regenerate block requests"""
        self._init_request_list()
        self.downloaded_blocks = []

    def _init_request_list(self):
        requests = self._create_request_list()
        # shuffle(requests)

        self.requests = deque(requests)
        self.completed_blocks = []

    def _create_request_list(self):
        """Create list of requests for blocks needed to complete this piece"""
        requests: list[Request] = []
        last_block_len = self.length % BLOCK_LEN

        # Create block requests
        for begin_offset in range(0, self.length - last_block_len, BLOCK_LEN):
            r = Request(
                self.index,
                begin_offset,
                BLOCK_LEN
            )
            requests.append(r)

        # Create last request when BLOCK_LEN doesn't divide PIECE_LEN
        if last_block_len > 0:
            r = Request(
                piece_index=self.index,
                begin_offset=self.length - last_block_len,
                length=last_block_len
            )
            requests.append(r)

        # Double Check That Loop!
        if len(requests) != self.num_blocks:
            print(self.length)
            print(last_block_len)
            print(len(requests))
            print(self.num_blocks)
            print(requests)
            assert False

        return requests

    def block_completed(self, begin_offset: int) -> bool:
        assert begin_offset % BLOCK_LEN == 0
        # block_index = begin_offset >> BLOCK_EXP

        # return block_index in self.completed_blocks
        return begin_offset in self.completed_blocks

    def complete(self):
        """True if all blocks have been downloaded.  ¡DOES NOT VERIFY PIECE HASH!"""
        return len(self.completed_blocks) == self.num_blocks

    # def get_downloaded_blocks(self) -> list[Block]:
    def get_downloaded_blocks(self) -> list:
        """
        Returns a list of downloaded blocks.
        Includes all blocks ONLY if this.completed()
        Blocks are correct ONLY if this.verify()
        """
        return self.downloaded_blocks

    def next_request(self) -> Request:
        """Generate request for next block needed to finish this piece"""

        try:
            r = self.requests.popleft()
            while self.block_completed(r.begin_offset()):
                # We can remove completed blocks from the queue
                r = self.requests.popleft()

        except IndexError:
            # Queue is empty
            return None

        # Found a block still needed to complete this piece
        self.requests.append(r)  # Put r back in the queue until we get data back for it
        return r

    def save_block(self, b: Block):
        if self.valid_block(b) and not self.block_completed(b.begin_offset()):
            self.downloaded_blocks.append(b)
            self.completed_blocks.append(b.begin_offset())

        else:
            if self.block_completed(b.begin_offset()):
                print('Invalid block!  (already have this block)')
            elif not self.valid_block(b):
                print(f'Invalid block!  (begin_offset not aligned or not last block or length wasn\'t {BLOCK_LEN} bytes'
                      + 'and no request was sent for it)')
            else:
                assert False

    def sort_blocks(self):
        self.downloaded_blocks.sort(key=lambda b: b.begin_offset())

    def valid_block(self, b: Block):
        def is_last_block(b: Block):
            return b.begin_offset() + len(b.data()) == self.length

        return \
            b.begin_offset() % BLOCK_LEN == 0 and \
            (len(b.data()) == BLOCK_LEN or is_last_block(b))

    def verify(self):
        self.sort_blocks()

        checksum = sha1()
        bytes_hashed = 0
        for b in self.downloaded_blocks:
            data = b.data()
            checksum.update(data)
            bytes_hashed += len(data)

        # Pad with 0's  # Don't do this?
        # if bytes_hashed < self.length:
        #     checksum.update(b'\x00' * (self.length - bytes_hashed))

        return checksum.digest() == self.checksum


# class PieceStore(ABC):
#     @abstractmethod
#     def get_piece(self, piece: Union[int, Piece, Request]):
#         pass

#     @abstractmethod
#     def store_piece(self, p: Piece):
#         pass


# def piece_to_index(piece):
#     if issubclass(piece, int):
#         index = piece
#     elif issubclass(piece, Block) or issubclass(piece, Request):
#         index = piece.index()
#     else:
#         raise ValueError("Argument, 'piece', must be an int or support the 'index()' method")


# def length_to_pieces(length_in_bytes: int, piece_size_in_bytes: int):
#     '''
#     Returns how many pieces it would take to hash length_in_bytes bytes
#     '''
#     return (length_in_bytes // piece_size_in_bytes) + (-length_in_bytes % piece_size_in_bytes)

class PieceIO:
    """Writes pieces to a file (or multiple files depending on the torrent)"""

    def __init__(self, t: Torrent):
        self.torrent: Torrent = t
        # self.path = path

    # def files_for_piece(self):
    #     '''Returns mapping from offsets in a piece '''
    #     pass
    #
    # def get_block_by_offset(self, begin_offset: int):
    #     for block in self.completed_blocks:
    #         if block.begin_offset() == begin_offset:
    #             return block

    def get_block(self, r: Request) -> Block:
        assert r.begin_offset() <= BLOCK_LEN
        start_offset = r.index() * self.torrent.piece_length + r.begin_offset()

        bytes_to_read = r.length()
        bytes_read = bytearray()

        for f in self.files_from_offset(start_offset):
            if bytes_to_read <= 0:
                break

            f: TorrentFile = f
            fstart_offset = start_offset - f.offset
            fbytes_to_read = min(bytes_to_read, f.length)

            f.file.seek(fstart_offset)
            bytes_read.extend(f.file.read(fbytes_to_read))

            bytes_to_read -= fbytes_to_read

        assert bytes_to_read == 0

        return Block(
            piece_index=r.index(),
            begin_offset=r.begin_offset(),
            data=bytes_read
        )

    def files_from_offset(self, start_offset):
        for off, f in self.torrent.end_offsets:
            # f: TorrentFile = f
            if off <= start_offset:
                continue

            yield f

    def write(self, p: Piece):
        assert p.complete()
        assert p.verify()

        start_offset = p.index * self.torrent.piece_length
        bytes_written = 0

        out_files = self.files_from_offset(start_offset)
        current_file: TorrentFile = next(out_files)
        offset_in_file = start_offset - current_file.offset
        current_file.file.seek(offset_in_file)

        blocks = iter(p.get_downloaded_blocks())
        current_block: Block = next(blocks)  # TODO: Should this even have to write an empty piece?

        bbytes_written = 0
        bytes_left_in_block = len(current_block.data())
        bytes_left_in_file = current_file.length - offset_in_file

        while bytes_written < p.length:
            # Get a new block if we need data to write
            assert bytes_left_in_block >= 0
            if bytes_left_in_block == 0:
                assert bbytes_written == len(current_block.data())
                current_block = next(blocks)

                bbytes_written = 0
                bytes_left_in_block = len(current_block.data())

            # Get a new file if we've filled the last one
            assert bytes_left_in_file >= 0
            if bytes_left_in_file == 0:
                current_file.file.flush()
                current_file = next(out_files)
                bytes_left_in_file = current_file.length

            # How many bytes can we write FROM this blk TO this file
            bytes_to_write = min(bytes_left_in_block, bytes_left_in_file)

            # Write it
            bdata = current_block.data()
            data_to_write = bdata[bbytes_written: bbytes_written + bytes_to_write]
            current_file.file.write(data_to_write)

            bytes_written += bytes_to_write  # Num bytes written of entire piece
            bbytes_written += bytes_to_write  # Num bytes written of current block
            bytes_left_in_block -= bytes_to_write  # Bytes still to write in current block
            bytes_left_in_file -= bytes_to_write  # Bytes we can still write to current file

        current_file.file.flush()

    # def write(self, p: Piece):
    #     assert p.complete()
    #     assert p.verify()

    #     start_offset = p.index * self.torrent.piece_length
    #     bytes_to_write = p.length
    #     bytes_written = 0

    #     filler = fill_file(p.get_downloaded_blocks(), start_offset)

    #     for off, f in self.torrent.end_offsets():
    #         # f: TorrentFile = f
    #         if off <= start_offset:
    #             continue

    #         else:
    #             bytes_written = filler.send(f)

    #     return bytes_written


class PieceManager:
    """
    Manages requesting blocks in pieces, caching them until the piece is complete, and saving the piece
    """

    def __init__(self, t: Torrent, io: PieceIO):
        self.torrent: Torrent = t
        self.io: PieceIO = io

        self.unfinished_pieces = self.make_piece_dict(t)
        self.finished_pieces = {}
        self.finished_pieces_bitfield: MutableBitfield = MutableBitfield(len(self.unfinished_pieces))

    @staticmethod
    # def make_piece_dict(self, t: Torrent) -> dict[int, Piece]:
    def make_piece_dict(t: Torrent) -> dict:
        """Makes a map from piece_indices to pieces"""
        bytes_left = t.download_length

        pieces = {}
        for index, piece in enumerate(t.pieces):
            piece_len = min(bytes_left, t.piece_length)  # Should be t.piece_length for all but the last piece
            p = Piece(
                index,
                checksum=piece,
                length=piece_len
            )

            pieces[index] = p
            bytes_left -= piece_len

        return pieces

    def complete(self):
        if len(self.finished_pieces) == self.num_pieces():
            assert len(self.unfinished_pieces) == 0

        return len(self.finished_pieces) == self.num_pieces()

    def get_block(self, r: Request) -> Block:
        return self.io.get_block(r)

    def has_piece(self, index: int):
        return index in self.finished_pieces

    def mark_finished(self, p: Piece):
        assert p.index in self.unfinished_pieces

        del self.unfinished_pieces[p.index]
        self.finished_pieces[p.index] = p

    def num_pieces(self):
        return self.torrent.num_pieces

    def requests(self):
        """ Generates requests needed to finish all pieces"""

        while len(self.unfinished_pieces) > 0:
            # For now, just finish one piece at a time
            for piece in list(self.unfinished_pieces.values()):  # (mark_finished removes piece from unfinished_pieces)
                # piece: Piece = piece
                r = piece.next_request()
                while r is not None:
                    yield r
                    r = piece.next_request()

    def save_block(self, b: Block):
        idx = b.index()

        if self.valid_piece_index(idx) and not self.has_piece(idx):
            piece: Piece = self.unfinished_pieces[idx]
            piece.save_block(b)

            if piece.complete():
                if piece.verify():
                    self.mark_finished(piece)
                    self.io.write(piece)
                else:
                    print(f'Piece {piece.index} failed verification!  Resetting...')
                    piece.reset()

        else:
            print('Block does not correspond to a valid piece.')

    def valid_piece_index(self, index: int) -> bool:
        return 0 <= index < self.torrent.num_pieces
