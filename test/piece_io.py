import os
import pickle

from storage import Block, Request, PieceIO, PieceManager
from torrent import Torrent

# from test.storage import make_block_for_request

print(os.getcwd())

with open('piece_io_files/pickled_truth.pkl', 'rb') as f:
    ground_truth = pickle.load(f)


def make_block_for_request(r: Request, t: Torrent, data: bytes):
    s_off = r.index() * t.piece_length + r.begin_offset()
    requested_data = data[s_off: s_off + r.length()]

    b = Block(
        piece_index=r.index(),
        begin_offset=r.begin_offset(),
        data=requested_data
    )

    return b


def simulate_piece_io(test_dir):
    try:
        torrent = Torrent('piece_io_files/torrents/' + test_dir + '.torrent')
        torrent_data = bytearray()

        items = sorted(ground_truth[test_dir].items(), key=lambda t: t[0])
        print(items)
        for name, file_data in items:
            torrent_data.extend(file_data)

        io = PieceIO(torrent)
        mgr = PieceManager(torrent, io)

        for r in mgr.requests():
            b = make_block_for_request(r, torrent, torrent_data)
            mgr.save_block(b)

        assert mgr.complete()

        #                           vvv I'm looking at you .DS_Store :/
        assert os.system(f'diff -x \'.*\' -r download/ piece_io_files/ground_truth/{test_dir}') == 0

        r = Request(
            piece_index=0,
            begin_offset=2,
            length=5
        )
        block_from_pieceio = mgr.get_block(r)
        correct_block = make_block_for_request(r, torrent, torrent_data)

        print(block_from_pieceio)
        print(correct_block)
        assert block_from_pieceio == correct_block

        if test_dir == 'torrent3':
            r = Request(
                piece_index=2,
                begin_offset=2,
                length=30000
            )
            block_from_pieceio = mgr.get_block(r)
            correct_block = make_block_for_request(r, torrent, torrent_data)

            # print(block_from_pieceio)
            # print(correct_block)
            assert block_from_pieceio == correct_block

    finally:
        os.system('rm -rf download/*')
    # print(torrent_data)


def test_piece_io_1():
    simulate_piece_io('torrent1')


def test_piece_io_2():
    simulate_piece_io('torrent2')


def test_piece_io_3():
    simulate_piece_io('torrent3')


def run_tests():
    os.system('rm -rf download/*')
    test_piece_io_1()
    test_piece_io_2()
    test_piece_io_3()


if __name__ == '__main__':
    run_tests()
