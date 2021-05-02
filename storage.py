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
        self.piece_idx = piece_index
        self.begin_off = begin_offset
        self.leng = length
    
    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.index() == other.index() and self.begin_offset() == other.begin_offset() and self.length() == other.length()
        return False
    
    def __hash__(self):
        return self.index() * 19 + self.begin_offset()

    def __repr__(self):
        return f'Request(\n\tpiece_index={self.index()},\n\tbegin_offset={self.begin_offset()},\n\tlength={self.length()}\n)'
        
    def index(self) -> int:
        return self.piece_idx

    def begin_offset(self) -> int:
        return self.begin_off

    def length(self) -> int:
        return self.leng
    

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
    # bytes_left_in_file = f.length() - start_offset
    bytes_written = 0

    # Get first file to fill starting at start_offset
    # dst_file: TorrentFile = yield bytes_written
    dst_file= yield bytes_written
    dst_file.file.seek(start_offset)
    

    for b in blocks:
        # Bytes left to write in this block
        bbytes_remaining = len(b.data())

        while (bbytes_remaining > 0):
            # Num of bytes we can write to this file
            bbytes_to_write = min(bbytes_remaining, dst_file.length())
            
            assert bbytes_to_write >= 0

            if (bbytes_to_write == 0):
                # If 0, we need a new file
                dst_file = yield bytes_written
                dst_file.seek(0)
            
            else:
                # If > 0, write as many as we can
                dst_file.write(b.data()[bytes_written: bytes_written + bbytes_to_write])
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
            num_blocks += 1

        # Reset downloaded blocks and requests
        self.reset()

    def _init_request_list(self):
        requests = self._create_request_list()
        # shuffle(requests)

        self.requests = deque(requests)
        self.completed_blocks = list()

    def _create_request_list(self):
        '''Create list of requests for blocks needed to complete this piece'''
        requests: list[Request] = []

        # Create block requests
        for begin_offset in range(0, length, BLOCK_LEN):
            r = Request(
                self.index,
                begin_offset,
                BLOCK_LEN
            )
            requests.append(r)

        # Create last request when BLOCK_LEN doesn't divide PIECE_LEN
        last_block_len = length % BLOCK_LEN
        if last_block_len > 0:
            r = Request(
                piece_index = self.index,
                begin_offset = self.length - last_block_len,
                length = last_block_len
            )
            requests.append(r)

        # Double Check That Loop!
        assert len(self.requests) == self.num_blocks

        return requests

    def block_completed(self, begin_offset: int) -> bool:
        assert begin_offset % BLOCK_LEN == 0
        block_index = begin_offset << BLOCK_EXP

        return block_index in self.completed_blocks

    def complete(self):
        '''True if all blocks have been downloaded.  ¡DOES NOT VERIFY PIECE HASH!'''
        return len(self.completed_blocks) == self.num_blocks

        

    # def get_downloaded_blocks(self) -> list[Block]:
    def get_downloaded_blocks(self) -> list:
        '''
        Returns a list of downloaded blocks.
        Includes all blocks ONLY if this.completed()
        Blocks are correct ONLY if this.verify()
        '''
        return self.downloaded_blocks

    
    def next_request(self) -> Request:
        '''Generate request for next block needed to finish this piece'''
        
        for r in self.requests:
            if not self.block_completed(r.begin_offset()):
                self.requests.append(r)  # Put r back in the queue until we get data back for it
                return r
            
    def save_block(self, b: Block):
        if self.valid_block(b) and not self.block_completed(b.begin_offset()):
            self.blocks.append(b)
            self.completed_blocks.add(b.begin_offset())

        else:
            print('Invalid block!  (begin_offset not aligned and no request was sent for it)')

    def sort_blocks(self):
        self.downloaded_blocks.sort(key=lambda b: b.begin_offset())

    def valid_block(self, b: Block):
        return b.begin_offset() % BLOCK_LEN == 0
    
    def verify(self):
        self.sort_blocks()
        
        checksum = sha1()
        bytes_hashed = 0
        for b in self.downloaded_blocks:
            data = b.data()
            checksum.update(data)
            bytes_hashed += len(data)
        
        # Pad with 0's
        if bytes_hashed < self.length:
            checksum.update(b'0' * (self.length - bytes_hashed))

        
        return checksum.digest() == self.checksum
        
    def reset(self):
        '''Clear all downloaded blocks, and regenerate block requests'''
        self._init_request_list()
        self.downloaded_blocks = []


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
    '''Writes pieces to a file (or multiple files depending on the torrent)'''

    def __init__(self, t: Torrent):
        self.torrent: Torrent = t
        self.path = path
    
    def files_for_piece(self):
        '''Returns mapping from offsets in a piece '''
        pass

    def get_block_by_offset(self, begin_offset: int):
        for block in self.completed_blocks:
            if block.begin_offset() == begin_offset:
                return block
            

    def get_block(self, r: Request) -> Block:
        assert r.begin_offset <= BLOCK_LEN
        start_offset = r.index() * self.torrent.piece_length() + r.begin_offset()

        bytes_to_read = r.length()
        bytes_read = bytearray()

        for f in self.file_from_offset(start_offset):
            if bytes_to_read <= 0:
                break

            f: TorrentFile = f
            fstart_offset = start_offset - f.offset()
            fbytes_to_read = min(bytes_to_read, f.length())

            f.seek(fstart_offset)
            bytes_read.extend(f.file().read(fbytes_to_read))

            bytes_to_read -= fbytes_to_read

        assert bytes_to_read == 0

        return Block(
            piece_index = r.index(), 
            begin_offset = r.begin_offset(), 
            data = bytes_read
        )
            
            

    def files_from_offset(self, start_offset):
        for off, f in self.torrent.end_offsets():
            # f: TorrentFile = f
            if off <= start_offset:
                continue

            yield f

    def write(self, p: Piece):
        assert p.complete()
        assert p.verify()


        start_offset = p.index * self.torrent.piece_length()
        bytes_to_write = p.length
        bytes_written = 0

        filler = fill_file(p.get_downloaded_blocks(), start_offset)

        for off, f in self.torrent.end_offsets():
            # f: TorrentFile = f
            if off <= start_offset:
                continue

            else:
                bytes_written = filler.send(f)
        
        return bytes_written


class PieceManager:
    '''
    Manages requesting blocks on pieces, caching them until the piece is complete, and saving the piece
    '''

    def __init__(self, t: Torrent, io: PieceIO):
        self.torrent: Torrent = t
        self.io: PieceIO = io

        self.unfinished_pieces = self.make_piece_dict(t)
        self.finished_pieces = {}
        self.finished_pieces_bitfield: MutableBitfield = MutableBitfield(len(self.unfinished_pieces))

    @staticmethod    
    # def make_piece_dict(self, t: Torrent) -> dict[int, Piece]:
    def make_piece_dict(self, t: Torrent) -> dict:
        '''Makes a map from piece_indices to pieces'''
        length = self.torrent.download_length()

        pieces = {}
        for index, piece in enumerate(t.pieces()):
            p = Piece(
                index, 
                checksum = piece,
                length = self.t.piece_length()  
            )

            pieces[index] = p

    def complete(self):
        if len(self.finished_pieces) == self.num_pieces:
            assert len(self.unfinished_pieces) == 0 

        return len(self.finished_pieces) == self.num_pieces

    def get_block(self, r: Request) -> Block:
        return self.io.get_block(r)
    
    def has_piece(self, index: int):
        return index in self.finished_pieces

    def mark_finished(self, p: Piece):
        assert p.index in self.unfinished_pieces

        del self.unfinished_pieces[p.index]
        self.finished_pieces

    def num_pieces(self):
        return len(self.torrent.pieces())

    def requests(self):
        ''' Generates requests needed to finish all pieces'''

        while len(self.unfinished_pieces) > 0:
            # For now, just finish one piece at a time
            for piece in list(self.unfinished_pieces.values()):  # (mark_finished removes piece from unfinished_pieces)
                piece : Piece = piece
                r = piece.next_request()
                while r is not None:
                    yield r
                    r = piece.next_request()


    def save_block(self, b: Block):
        idx = b.index()

        if self.valid_piece_index(idx) and not self.have(idx):
            piece: Piece = self.unfinished_pieces[idx]
            piece.save_block(b)

            if piece.complete():
                if piece.verify():
                    self.mark_finished(piece)
                    self.io.write(piece)
                else:
                    print(f'Piece {self.piece.index} failed verification!  Resetting...')
                    piece.reset()

        else:
            print('Block does not correspond to a valid piece.')
    
    def valid_piece_index(self, index: int) -> bool:
        return 0 <= index < self.torrent.num_pieces()

