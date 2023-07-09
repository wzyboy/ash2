import os
import json
import time
from pathlib import Path
from datetime import datetime

import pytest
from elasticsearch import Elasticsearch


@pytest.fixture
def client(es_host, es_index):
    os.environ['TESTING'] = 'True'
    from ash import app
    app.config.update({
        'TESTING': True,
        'T_ES_HOST': es_host,
        'T_ES_INDEX': es_index,
    })
    return app.test_client()


@pytest.fixture(scope='session')
def es_host() -> str:
    return os.environ.get('T_ES_HOST', 'http://localhost:9200')


@pytest.fixture(scope='session')
def es_index(es_host: str) -> str:
    cluster = Elasticsearch(es_host)
    now = datetime.now().strftime('%s')
    index = f'pytest-{now}'
    here = Path(os.path.abspath(__file__)).parent
    tweet_files = [
        here / 'fixtures/tweet_with_photo.json',
        here / 'fixtures/tweet_with_video.json',
    ]
    for tweet_file in tweet_files:
        tweet = json.loads(tweet_file.read_text())
        cluster.index(index=index, id=tweet['id'], document=tweet)

    time.sleep(3)

    return index
