from abc import ABC, abstractmethod
from hashlib import sha1

from bitfield import MutableBitfield
from packet import PiecePacket, RequestPacket


class Piece(ABC):
    @abstractmethod
    def index(self) -> int:
        pass

    @abstractmethod
    def begin_offset(self) -> int:
        pass

    @abstractmethod
    def data(self) -> bytes:
        pass


class Request(ABC):
    @abstractmethod
    def index(self) -> int:
        pass

    @abstractmethod
    def begin_offset(self) -> int:
        pass

    @abstractmethod
    def length(self) -> int:
        pass


class PieceStore(ABC):
    @abstractmethod
    def get_piece(self, piece: Union[int, Piece, Request]):
        pass

    @abstractmethod
    def store_piece(self, p: Piece):
        pass


def piece_to_index(piece):
    if issubclass(piece, int):
        index = piece
    elif issubclass(piece, Piece) or issubclass(o, Request):
        index = piece.index()
    else:
        raise ValueError("Argument, 'piece', must be an int or support the 'index()' method")

    

def length_to_pieces(length_in_bytes: int, piece_size_in_bytes: int):
    '''
    Returns how many pieces it would take to hash length_in_bytes bytes
    '''
    return (length_in_bytes // piece_size_in_bytes) + (-length_in_bytes % piece_size_in_bytes)


class TorrentFile(PieceStore):
    def __init__(self, piece_size: int, length: int, path: str, piece_hashes: iterable[bytes]):
        self.length = length
        self.piece_size = piece_size
        self.piece_hashes = piece_hashes
        self.verified_pieces = MutableBitfield(bytearray())
        self.locked_pieces = MutableBitfield(bytearray())
        self.path = path
        self.file_on_disk = self.__setup_download_file(self.path)

    def __setup_download_file(self, path):
        f = open(path, 'wb')

        # Round up to nearest piece_size
        size = self.length + (-self.length % piece_size)

        # Preallocate space (probably a sparse file, but we still must seek to middle of file and write)
        f.truncate(size)

    def __close__(self):
        self.finalize()
        self.file_on_disk.close()
    
    def have(self, index: Union[int, Piece, Request]):
        return index in self

    def __contains__(self, o):
        index = piece_to_index(o)

        return self.verified_pieces.get(index)
    
    def __lookup_hash(self, p: Union[int, Request, Piece]):
        index = piece_to_index(p)

        return self.piece_hashes[index]
            
    def __is_locked(self, piece: Union[int, Piece, Request]):
        index = piece_to_index(piece)

        return self.locked_pieces.get(index)

    def __lock(self, piece: Union[int, Piece, Request]):
        index = piece_to_index(piece)

        self.locked_pieces.set(index)

    def __unlock(self, piece: Union[int, Piece, Request]):
        index = piece_to_index(piece)

        self.locked_pieces.unset(index)
    
    def __verify(self, piece: Union[int, Piece, Request]):
        data = piece.data()

        # If we haven't the whole piece, load it from disk
        if not len(data) == self.piece_size:
            # Goto beginning of piece
            self.file_on_disk.seek(self.piece_index_to_offset(piece.index()))
            # Load it from disk
            data = self.file_on_disk.read(self.piece_size)
        
        # Calculate checksum
        h = sha1()
        h.update(data)
        d = h.digest()

        # Check checksum
        if d == self.__lookup_hash(piece):

            # Mark verified!
            index = piece_to_index(piece)
            self.verified_pieces.set(index)


    def offset_to_piece_index(self, offset: int):
        return offset // self.piece_size
    
    def piece_index_to_offset(self, index: int):
        return index * self.piece_size
    
    def get_piece(self, piece: Union[int, Piece, Request]):
        index = piece_to_index(piece)

        if index in self:
            s_offset = self.piece_index_to_offset(p.index())
            self.file_on_disk.seek(s_offset)

            return self.file_on_disk.read(self.piece_size)
        
        else:
            return None

    
    def store_piece(self, p: Piece):
        if not self.have(p.index()):
            if not self.__is_locked(p):
                # Stop other threads from writing this piece
                self.__lock(p)

                # Calculate write offset of piece in file
                s_offset = self.piece_index_to_offset(p.index())
                s_offset += p.begin_offset

                # Write the piece
                self.file_on_disk.seek(s_offset)
                self.file_on_disk.write(p.data())

                # Verify piece
                self.__verify(p)

                self.__unlock(p)
    
    def finalize(self):
        self.file.truncate(self.length)
               

    # def flush(self):
    #     for p in self.pieces: