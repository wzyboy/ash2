#!/usr/bin/env python

'''
A Twitter archive includes only text data. This simple script parses all media
entities in the Twitter archive and extract all media URLs. One could feed the
output list to "aria2c -i" and download all the media files to disk.

Optionally, since the filenames of the media files are unique, they could be
uploaded to object storage buckets for backup purposes.

This script also extracts profile images. The filenames of the profile images
are not unique, so a rename is performed.
'''

import re
import argparse

from loader import load_data_dir


def url_to_filename(url):
    '''
    >>> 'https://pbs.twimg.com/profile_images/1130275863/IMG_1429_400x400.JPG'
    'https___pbs.twimg.com_profile_images_1130275863_IMG_1429_400x400.JPG'
    '''
    return re.sub('[:/]', '_', url)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data-dir', default='data')
    args = ap.parse_args()

    data = load_data_dir(args.data_dir)

    media_urls = set()
    profile_image_urls = set()

    for item in data:

        # Media (including media in retweeted status)
        try:
            # https://developer.twitter.com/en/docs/tweets/data-dictionary/overview/extended-entities-object
            entities = item['extended_entities']
        except KeyError:
            entities = item['entities']
        media = entities.get('media', [])
        for m in media:
            media_url = m['media_url_https']
            media_urls.add(media_url)

        # Profile images
        profile_image_url = item['user']['profile_image_url_https']
        profile_image_urls.add(profile_image_url)

        # Retweeted profile images
        retweeted = item.get('retweeted_status')
        if retweeted:
            retweeted_profile_image_url = retweeted['user']['profile_image_url_https']
            profile_image_urls.add(retweeted_profile_image_url)

    media_urls = sorted(media_urls)
    for url in media_urls:
        print(url)

    profile_image_urls = sorted(profile_image_urls)
    for url in profile_image_urls:

        # Use a larger size
        url = re.sub(r'_normal(?=\.[a-zA-Z]{3,4}$)', '_400x400', url)
        url = re.sub(r'_normal$', '_400x400', url)

        # Rename
        filename = url_to_filename(url)
        aria2_out = '  out={}'.format(filename)

        print('{}\n{}'.format(url, aria2_out))


if __name__ == '__main__':
    main()
