from bencode import bencode, bdecode

from storage import length_to_pieces, piece_to_index, TorrentFile

class MalformedTorrentException(Exception):
    pass

class Torrent(PieceStore):
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

            # Info parameters
            self.files = dict()  # starting piece index -> file
            piece_length = self.info.get('piece length')
            raw_piece_hashes = self.info.get('pieces')
            self.piece_hashes = [raw_piece_hashes[i:i + 20] for i in range(0, len(raw_piece_hashes), 20)]
            try:
                self.length = self.info['length']
                file_name = self.info['name']
                f = TorrentFile(
                    piece_size = self.piece_length,
                    length = self.length,
                    path = self.filename,
                    piece_hashes = self.piece_hashes
                )

                self.files[0] = f

            except KeyError:
                self.length = 0
                next_piece_idx = 0
                for file_dict in self.info['files']:
                    file_length = file_dict['length']
                    file_name = file_dict['name']
                    f = TorrentFile(
                        piece_size = self.piece_length,
                        length = file_length,
                        path = file_name,
                        piece_hashes = self.pieces[next_piece_idx: next_piece_idx + length]
                    )

                    self.file[next_piece_idx] = f

                    self.length += file_length
                    next_piece_idx += length_to_pieces(file_length, self.piece_length)

    def get_file_containing_piece(self, index: int) -> TorrentFile:
        # Get closest without going over index
        base_index = min(
            filter(
                lambda findex: findex <= index,
                self.files.keys()
            ), 
            lambda findex: findex - index
        )
        return self.files.get(base_index)
    
    def get_piece_by_index(self, index: int):
        f: TorrentFile = get_file_containing_piece(index)
        return f.get_piece(index)

    def get_piece(self, piece: Union[int, Piece, Request]):
        index = piece_to_index(piece)
        return self.get_piece_by_index(index)

    def store_piece(self, piece: Piece):
        f: TorrentFile = self.get_file_containing_piece(piece.index())
        f.store_piece(p)

    def get_pieces(self) -> list[Piece]:
        return self.piece_hashes

    def num_pieces(self) -> int:
        len(self.get_pieces())
                
    def announce_url(self):
        return self.announce_url

    def info(self):
        return self.info

    def download_size(self):
        return self.length

