import os
import pickle

PKL_FILENAME = 'pickled_truth.pkl'

ground_truth = {}


def dir2dict(basedir, d):
    for f in os.listdir(basedir):
        full_path = os.path.join(basedir, f)
        if os.path.isfile(full_path):
            with open(full_path, 'rb') as fb:
                d[f] = fb.read()

        elif os.path.isdir(full_path):
            d[f] = {}
            dir2dict(full_path, d[f])

        else:
            print(f)
            assert False


def main():
    dir2dict('ground_truth', ground_truth)

    with open(PKL_FILENAME, 'wb') as f:
        pickle.dump(ground_truth, f)


if __name__ == '__main__':
    main()
