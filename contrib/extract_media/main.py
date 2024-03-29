#!/usr/bin/env python

'''
The script extracts pbs.twimg.com URLs from Twitter archive and saves them to a
local directory.
'''

import re
import shutil
import argparse
from pathlib import Path
from urllib.parse import urlsplit

from typing import Optional
from collections.abc import Iterator
from collections.abc import Iterable

import scrapy
from scrapy.crawler import CrawlerProcess


class TwimgExtractor(scrapy.Spider):
    name = 'TwimgExtractor'

    def __init__(self, archive_dir: Path, output_dir: Path, **kwargs):
        self.js_files = (archive_dir / 'data').rglob('*.js')
        self.media_dir = archive_dir / 'data/tweets_media'
        self.output_dir = output_dir
        super().__init__(**kwargs)

    def start_requests(self) -> Iterator[scrapy.Request]:
        media_cache = TweetsMediaCache(self.media_dir)
        for url in self.find_urls(self.js_files):
            if cached := media_cache.get(url):
                output = self.url_to_fs_path(url, self.output_dir)
                output.parent.mkdir(parents=True, exist_ok=True)
                if output.exists():
                    self.logger.debug(f'Skipped copying as target exists:: {output}')
                else:
                    shutil.copy2(cached, output)
                    self.logger.debug(f'Copied from local: {cached}')
            else:
                yield from self.download_url(url)

    def download_url(self, url: str) -> Iterator[scrapy.Request]:
        output: Path = self.url_to_fs_path(url, self.output_dir)
        if output.exists() and output.stat().st_size > 0:
            self.logger.debug(f'Skipped downloading as target exists: {output}')
        else:
            yield scrapy.Request(url=url, callback=self.write_to_disk, cb_kwargs={'output': output})

    def write_to_disk(self, response, output: Path):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(response.body)

    @staticmethod
    def find_urls(js_files: Iterable[Path]) -> Iterator[str]:
        twimg_url_re = re.compile(r'(?<=")https://(pbs|video).twimg.com/.*?(?=")')
        seen = set()
        for js_file in js_files:
            with open(js_file, 'r') as f:
                for line in f:
                    if matched := twimg_url_re.search(line):
                        url = matched.group(0)
                        if url not in seen:
                            yield url
                            seen.add(url)

    @staticmethod
    def url_to_fs_path(url: str, parent: Path) -> Path:
        parts = urlsplit(url)
        return parent / f'{parts.netloc}{parts.path}'


class TweetsMediaCache:
    def __init__(self, media_dir: Path) -> None:
        self._dict = dict()
        for file in media_dir.glob('*'):
            key = file.name.split('-', 1)[1]
            self._dict[key] = file

    def get(self, url: str) -> Optional[Path]:
        key = Path(urlsplit(url).path).name
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
