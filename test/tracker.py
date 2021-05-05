import os
import socket

from bencode import bencode, bdecode
from torrent import Torrent
from tracker import Peer, Tracker, TrackerRequest

tfiles = [f'test/torrents/{tf}' for tf in os.listdir('test/torrents') if tf.endswith('.torrent')]
torrents = [Torrent(tf) for tf in tfiles]
tracker_responses = [f'test/tracker_responses/{tf}' for tf in os.listdir('test/tracker_responses')]

peer_id = b'OceanC-3451234512345'

def is_open_port(host, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    
    try:
        result = sock.connect((host, port))
        # assert result == 0
        print('Peer is listening at {}:{}'.format(host, port))
        return True

    except (AssertionError, ConnectionRefusedError, socket.timeout):
    # except:
        print('Peer is NOT listening at {}:{}'.format(host, port))
        return False

    finally:
        sock.close()

def can_connect_to_peer(p: Peer):
    print('Testing connection to peer, {}'.format(p.id))
    return is_open_port(p.host, p.port)

def valid_peer_id(pid):
    return len(pid) == 20 or pid == ''

def test_decode_tracker_bdict_response():
    # for trn in tracker_responses:
    #     with open(trn, 'rb') as f:
    #         rdata = f.read()
    #         data = bdecode(rdata)
    #         print(data['peers'])
    #         print(data)
    #         peers = TrackerRequest.decode_response(rdata)
    #         print(peers)

    expected_peers = [Peer(id='', host='147.147.96.18', port=48382), Peer(id='', host='62.143.215.73', port=55250), Peer(id='', host='193.104.203.4', port=53658), Peer(id='', host='78.31.92.147', port=56666), Peer(id='', host='212.129.0.223', port=26467), Peer(id='', host='163.172.61.146', port=51413), Peer(id='', host='185.148.3.123', port=59108), Peer(id='', host='95.161.27.44', port=51413), Peer(id='', host='69.70.135.194', port=51413), Peer(id='', host='82.95.242.16', port=51473), Peer(id='', host='181.161.52.36', port=51413), Peer(id='', host='99.62.162.46', port=6881), Peer(id='', host='88.243.194.252', port=13485), Peer(id='', host='176.36.226.252', port=51413), Peer(id='', host='77.20.163.149', port=51425), Peer(id='', host='79.11.28.157', port=16881), Peer(id='', host='5.103.137.146', port=15642), Peer(id='', host='176.63.26.207', port=8999), Peer(id='', host='163.172.97.236', port=11468), Peer(id='', host='202.187.69.203', port=51413), Peer(id='', host='76.28.90.242', port=6881), Peer(id='', host='93.221.42.157', port=65301), Peer(id='', host='185.38.14.204', port=64059), Peer(id='', host='217.174.206.67', port=51413), Peer(id='', host='46.232.250.245', port=49278), Peer(id='', host='108.201.153.44', port=28415), Peer(id='', host='79.133.18.232', port=26461), Peer(id='', host='79.144.80.59', port=49161), Peer(id='', host='95.163.82.83', port=25565), Peer(id='', host='75.118.9.52', port=51413), Peer(id='', host='95.59.225.55', port=12826), Peer(id='', host='109.230.155.187', port=49155), Peer(id='', host='82.64.237.93', port=51413), Peer(id='', host='128.68.75.125', port=52248), Peer(id='', host='134.249.136.112', port=29905), Peer(id='', host='94.140.9.165', port=56194), Peer(id='', host='37.120.197.42', port=51413), Peer(id='', host='185.244.214.20', port=42000), Peer(id='', host='71.92.63.124', port=34936), Peer(id='', host='71.135.217.90', port=51413), Peer(id='', host='97.113.124.175', port=6888), Peer(id='', host='134.249.153.220', port=49164), Peer(id='', host='185.148.3.108', port=21665), Peer(id='', host='88.1.155.113', port=4666), Peer(id='', host='58.142.3.193', port=65277), Peer(id='', host='62.227.100.177', port=55555), Peer(id='', host='185.159.157.10', port=51413), Peer(id='', host='164.58.9.142', port=51413), Peer(id='', host='192.145.130.213', port=51413), Peer(id='', host='94.21.153.50', port=51413)]
    with open('test/tracker_responses/ubuntu.resp', 'rb') as f:
        rdata = f.read()
        data = bdecode(rdata)
        peers = TrackerRequest.decode_response(rdata)
        assert(len(peers) == 50)
        print(peers)
        assert peers == expected_peers
        for p in peers:
            assert valid_peer_id(p.id)


def test_tracker():
    "Gets peers for torrents in test/torrents and tries connecting to them."

    for torrent in torrents:
        torrent: Torrent = torrent

        t = Tracker(peer_id, torrent, 'mooblek.com', '1955')
        
        peers = t.get_peers()
        live_peers = 0
        for peer in peers:
            assert valid_peer_id(peer.id)
            if can_connect_to_peer(peer):
                live_peers += 1

        print(f'{live_peers}/{len(peers)} peers were up.')
        assert live_peers >= 0.6 * len(peers)


if __name__ == '__main__':
    test_tracker()