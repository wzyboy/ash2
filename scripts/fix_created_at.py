#!/usr/bin/env python

'''
In my Twitter archives downloaded before mid-2013, all tweets have correct
"created_at" attributes. However, Twitter archives downloaded after mid-2013
not only use a different time format, but also have incorrect "created_at"
attributes for tweets ranging from 2009 to 2010. The "created_at" attributes of
affected tweets (~10000) have correct date portions but their time portions are
reset to "00:00:00" of that day for an unknown reason.

This script is a quick and dirty way to fix this: it iterates over the
JavaScript files, finding out problematic tweets and retrieve correct
"created_at" from Twitter archives downloaded before mid-2013, and finally
replace the incorrect "created_at" attributes with correct ones.
'''

import os
import re
import glob
import argparse
from datetime import datetime

from loader import load_files


def main():

    # Mon Jun 29 15:46:31 +0000 2009
    # 2017-08-17 12:57:51 +0000
    old_ts_format = '%a %b %d %H:%M:%S %z %Y'
    new_ts_format = '%Y-%m-%d %H:%M:%S %z'

    ap = argparse.ArgumentParser()
    ap.add_argument('--old-data', default='./data2')
    ap.add_argument('--new-data', default='./data')
    args = ap.parse_args()

    old_files = glob.glob(os.path.join(args.old_data, 'js/tweets/*.js'))
    old_data = load_files(old_files)
    old_db = {i['id']: i for i in old_data}

    new_files = glob.glob(os.path.join(args.new_data, 'js/tweets/*.js'))
    for js in new_files:

        print('Processing {}'.format(js))

        changed = False
        new_lines = []

        with open(js, 'r') as f:
            lines = f.readlines()

        for lineno, line in enumerate(lines):
            matched = re.match(r'  "created_at" : "(\d{4}-\d{2}-\d{2} 00:00:00 \+0000)",', line)
            if not matched:
                new_lines.append(line)
            else:
                # possible date mismatches, look behind a few lines for id
                changed = True
                before_lines = lines[lineno - 2:lineno]
                for line in before_lines:
                    matched_id = re.match(r'  "id" : (\d+),', line)
                    if matched_id:
                        break
                else:
                    raise ValueError('Cannot find tweet ID in before lines in {} @ L{}:\n{}'.format(js, lineno, before_lines))

                tweet_id = int(matched_id.group(1))
                try:
                    old_tweet = old_db[tweet_id]
                except KeyError:
                    raise ValueError('Cannot retrieve old tweet {}.'.format(tweet_id)) from None
                old_ts = datetime.strptime(old_tweet['created_at'], old_ts_format)
                corrected_ts = old_ts.strftime(new_ts_format)
                new_line = '  "created_at" : "{}",\n'.format(corrected_ts)
                new_lines.append(new_line)

        if changed:
            print('Writing {}'.format(js))
            with open(js, 'w') as f:
                f.writelines(new_lines)


if __name__ == '__main__':
    main()
