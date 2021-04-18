from bencode import bencode, bdecode

from storage import TorrentFile

class MalformedTorrentException(Exception):
    pass

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

            # Info parameters
            self.files = []
            piece_length = self.info.get('piece length')
            try:
                f = TorrentFile('')
                self.length = self.info['length']
                filename = self.info['name']
            

                

    def announce_url(self):
        return self.announce_url

    def info(self):
        return self.info

    def download_size(self):
        return self.length

