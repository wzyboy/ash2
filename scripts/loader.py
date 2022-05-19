
import os
import glob
import json
from itertools import chain


def load_data_dir(data_dir):

    filenames_glob = os.path.join(os.path.abspath(data_dir), 'js/tweets/*.js')
    print('Loading tweets from archive files: {}'.format(filenames_glob))
    filenames = glob.glob(filenames_glob)
    if not filenames:
        raise FileNotFoundError('No files found.')

    data = load_files(filenames)
    return data


def load_file(filename):

    with open(filename, 'r') as f:
        # drop the first line
        lines = f.readlines()
        content = ''.join(lines[1:])
        data = json.loads(content)
    return data


def load_files(filenames):

    data = chain.from_iterable(
        load_file(filename) for filename in filenames
    )

    return data
