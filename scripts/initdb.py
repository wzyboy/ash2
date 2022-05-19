#!/usr/bin/env python

'''
Read tweets from Twitter archive data files and load them into an SQLite
database.
'''

import os
import json
import sqlite3
import argparse
try:
    import resource  # Unix-only module
except ImportError:
    HAS_RESOURCE = False
else:
    HAS_RESOURCE = True

from loader import load_data_dir


def init_sqlite():

    ap = argparse.ArgumentParser()
    ap.add_argument('-d', '--data-dir', default='data')
    ap.add_argument('-o', '--output', default='tweets.db')
    ap.add_argument('-a', '--append', action='store_true', help='insert new Tweets into existing SQLite')
    args = ap.parse_args()

    if os.path.isfile(args.output) and not args.append:
        raise FileExistsError(
            '{} already exists. Pass --output to use a different filename. '
            'If you want to insert new Tweets into existing SQLite, '
            'pass --append flag.'
            .format(args.output)
        )

    data = load_data_dir(args.data_dir)
    tweets = (
        (i['id'], i['text'], json.dumps(i))
        for i in data
    )

    # Insert into SQLite
    db = sqlite3.connect(args.output)
    cursor = db.cursor()

    cursor.execute('create table if not exists tweets (id integer primary key, text text, _source text)')
    cursor.executemany('insert or ignore into tweets values (?, ?, ?)', tweets)
    print('Inserted {} tweets into SQLite'.format(cursor.rowcount))
    db.commit()

    cursor.execute('vacuum')
    db.commit()

    db.close()

    if HAS_RESOURCE:
        max_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        print(
            'Max resident memory usage: {}. '
            'The unit can be kilobytes or bytes, depending on your platform.'
            .format(max_rss)
        )


if __name__ == '__main__':
    init_sqlite()
