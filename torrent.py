import os

from bencode import bencode, bdecode
from hashlib import sha1

# from storage import length_to_pieces, piece_to_index, TorrentFile

class MalformedTorrentException(Exception):
    pass


class TorrentFile:

    DOWNLOAD_SUBDIR = 'download/'

    def __init__(self, length: int, offset: int, path: str):
        self.__length = length
        self.__offset = offset
        self.__path = os.path.join(self.DOWNLOAD_SUBDIR, path)
        os.makedirs(os.path.dirname(self.path), exist_ok=True)

        self.__file = open(self.path, 'wb')

    def __close__(self):
        self.file.close()

    def __eq__(self, other):
        if issubclass(other, TorrentFile):
            return self.length() == other.length() and self.offset() == other.offset() and self.path() == other.path()
        return False

    def __hash__(self):
        return self.length() * 19 + self.begin_offset() + hash(self.path())

    @property
    def file(self):
        '''File handle for downloaded file on disk'''
        return self.__file

    @property
    def length(self):
        '''Number of bytes when downloaded'''
        return self.__length

    @property
    def offset(self):
        '''Number of bytes into the total download (in order according to files dict in .torrent)'''
        return self.__offset
    
    @property
    def path(self):
        '''Path to this downloaded file on disk'''
        return self.__path
    

class Torrent:
    def __init__(self, filename):
        with open(filename, 'rb') as f:
            torrent_d = bdecode(f)
            print(f'Opening {filename}')
            print(torrent_d.keys())
            # print(torrent_d['info']['length'])
            # print(torrent_d['info']['name'])
            # print(torrent_d['info']['piece length'])
            # print(len(torrent_d['info']['pieces']))
            # print(torrent_d['info'].keys())
            print(torrent_d['announce'])
            
            # Top Level Params
            self.__announce_url = torrent_d['announce']
            self.__info = torrent_d['info']
            self.__info_hash_b = sha1(bencode(self.info)).digest()

            # Info parameters
            self.__files = dict()  # starting piece index -> file
            self.__piece_len = self.info.get('piece length')
            raw_piece_hashes = self.info.get('pieces')
            self.__piece_hashes = [raw_piece_hashes[i:i + 20] for i in range(0, len(raw_piece_hashes), 20)]
            try:
                self.__length = self.info['length']
                file_name = self.info['name']
                f = TorrentFile(
                    length = self.__length,
                    offset = 0,
                    path = file_name,
                )

                self.__files[0] = f

            except KeyError:
                self.__length = 0
                for file_dict in self.__info['files']:
                    print(file_dict.keys())
                    file_length = file_dict['length']
                    file_name = '/'.join(file_dict['path'])
                    print(file_name)

                    f = TorrentFile(
                        length = file_length,
                        offset = self.__length,
                        path = file_name
                    )

                    self.__files[f.offset // self.piece_length] = f

                    self.__length += file_length

    @property
    def announce(self) -> str:
        return self.__announce_url

    @property
    def download_length(self) -> int:
        return self.__length

    # def files(self) -> list[TorrentFile]:
    @property
    def files(self) -> list:
        return self.__files

    @property
    def piece_length(self) -> int:
        return self.__piece_len

    @property
    def pieces(self):
        return self.__piece_hashes

    @property
    def info(self):
        return self.__info
    
    @property
    def info_hash(self):
        return self.__info_hash_b

    def piece_offset(self, index):
        return index * self.piece_length

    def start_offset(self, file: TorrentFile):
        offset = 0
        
        for f in self.files():
            if f == file:
                return offset
            
            offset += f.length()

        raise ValueError(f"Asked for offset of {file.path()} in a torrent which doesn't contain it.")

    # def start_offsets(self) -> dict[int, TorrentFile]:
    @property
    def start_offsets(self) -> dict:
        '''Returns Map<start_offset, TorrentFile>'''

        offset = 0
        offsets = {}

        for f in self.files():
            offsets[offset] = f

        offset += f.length()

    # def end_offsets(self) -> dict[int, TorrentFile]:
    @property
    def end_offsets(self) -> dict:
        '''Returns Map<end_offset, TorrentFile>'''
        return {off + f.length(): f for off, f in self.start_offsets().items()}



