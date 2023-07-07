#!/usr/bin/env python

'''
The script extracts pbs.twimg.com URLs from Twitter archive and saves them to a
local directory.
'''

import re
import shutil
import argparse
from pathlib import Path
from urllib.parse import urlparse

from typing import Optional
from collections.abc import Iterator

import scrapy
from scrapy.crawler import CrawlerProcess


class TwimgExtractor(scrapy.Spider):
    name = 'TwimgExtractor'

    def __init__(self, archive_dir: Path, output_dir: Path, **kwargs):
        self.tweets_js = archive_dir / 'data/tweets.js'
        self.tweets_media = archive_dir / 'data/tweets_media'
        self.output_dir = output_dir
        super().__init__(**kwargs)

    def start_requests(self):
        media_cache = TweetsMediaCache(self.tweets_media)
        for url in self.find_urls(self.tweets_js):
            if cached := media_cache.get(url):
                output = self.url_to_fs_path(url, self.output_dir)
                output.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(cached, output)
                self.logger.debug(f'Copied from local: {cached}')
            else:
                yield scrapy.Request(url=url, callback=self.parse)

    def parse(self, response):
        output: Path = self.url_to_fs_path(response.url, self.output_dir)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(response.body)

    def find_urls(self, tweet_js: Path) -> Iterator[str]:
        twimg_url_re = re.compile(r'(?<=")https://pbs.twimg.com/.*?(?=")')
        seen = set()
        with open(tweet_js, 'r') as f:
            for line in f:
                if matched := twimg_url_re.search(line):
                    url = matched.group(0)
                    if url not in seen:
                        yield url
                        seen.add(url)

    @staticmethod
    def url_to_s3_key(url: str) -> str:
        return url.removeprefix('https://')

    @staticmethod
    def url_to_fs_path(url: str, parent: Path) -> Path:
        return parent / url.removeprefix('https://')


class TweetsMediaCache:
    def __init__(self, tweets_media: Path) -> None:
        self._dict = dict()
        for file in tweets_media.glob('*'):
            key = file.stem.split('-')[1]
            self._dict[key] = file

    def get(self, url: str) -> Optional[Path]:
        key = Path(urlparse(url).path).stem
        return self._dict.get(key)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('archive_dir', type=Path, help='directory of extracted Twitter archive')
    ap.add_argument('-o', '--output_dir', type=Path, help='directory to save media files into', default=Path('output_dir'))
    args = ap.parse_args()

    process = CrawlerProcess()
    process.crawl(TwimgExtractor, archive_dir=args.archive_dir, output_dir=args.output_dir)
    process.start()


if __name__ == '__main__':
    main()
