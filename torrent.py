from bencode import bencode, bdecode
from hashlib import sha1

from storage import length_to_pieces, piece_to_index, TorrentFile

class MalformedTorrentException(Exception):
    pass


class TorrentFile:
    def __init__(self, length: int, offset: int, path: str):
        self.length = length
        self.offset = offset
        self.path = path

        self.file = open(self.path, 'wb')

    def __close__(self):
        self.file.close()

    def __eq__(self, other):
        if issubclass(other, TorrentFile):
            return self.length() == other.length() and self.offset() == other.offset() and self.path() == other.path()
        return False

    def __hash__(self):
        return self.length() * 19 + self.begin_offset() + hash(self.path)

    def file(self):
        '''File handle for downloaded file on disk'''
        return self.file

    def length(self):
        '''Number of bytes when downloaded'''
        return self.length

    def offset(self):
        '''Number of bytes into the total download (in order according to files dict in .torrent)'''
        return self.offset
    
    def path(self):
        '''Path to this downloaded file on disk'''
        return self.path
    

class Torrent:
    def __init__(self, filename):
        with open(filename, 'rb') as f:
            torrent_d = bdecode(f)
            print(torrent_d.keys())
            print(torrent_d['info']['length'])
            print(torrent_d['info']['name'])
            print(torrent_d['info']['piece length'])
            print(len(torrent_d['info']['pieces']))
            print(torrent_d['info'].keys())
            print(torrent_d['announce'])
            
            # Top Level Params
            self.announce_url = torrent_d['announce']
            self.info = torrent_d['info']
            self.info_hash_b = sha1(bencode(self.info)).digest()

            # Info parameters
            self.files = dict()  # starting piece index -> file
            self.piece_length = self.info.get('piece length')
            raw_piece_hashes = self.info.get('pieces')
            self.piece_hashes = [raw_piece_hashes[i:i + 20] for i in range(0, len(raw_piece_hashes), 20)]
            try:
                self.length = self.info['length']
                file_name = self.info['name']
                f = TorrentFile(
                    length = self.length,
                    offset = 0,
                    path = self.filename,
                )

                self.files[0] = f

            except KeyError:
                self.length = 0
                for file_dict in self.info['files']:
                    file_length = file_dict['length']
                    file_name = file_dict['name']
                    f = TorrentFile(
                        length = file_length,
                        offset = length,
                        path = file_name
                    )

                    self.file[next_piece_idx] = f

                    self.length += file_length

    def announce(self) -> str:
        return self.announce_url

    def download_length(self) -> int:
        return self.length

    def files(self) -> list[TorrentFile]:
        return self.files

    def piece_length(self) -> int:
        return self.piece_length

    def pieces(self):
        return self.piece_hashes

    def get_info(self):
        return self.info
    
    def info_hash(self):
        return self.info_hash_b

    def piece_offset(self, index):
        return index * self.piece_length

    def start_offset(self, file: TorrentFile):
        offset = 0
        
        for f in self.files():
            if f == file:
                return offset
            
            offset += f.length()

        raise ValueError(f"Asked for offset of {file.path()} in a torrent which doesn't contain it.")

    def start_offsets(self) -> dict[int, TorrentFile]:
        '''Returns Map<start_offset, TorrentFile>'''

        offset = 0
        offsets = {}

        for f in self.files():
            offsets[offset] = f

        offset += f.length()

    def end_offsets(self) -> dict[int, TorrentFile]:
        '''Returns Map<end_offset, TorrentFile>'''
        return {off + f.length(): f for off, f in self.start_offsets().items()}



