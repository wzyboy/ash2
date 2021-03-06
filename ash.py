'''
A Flask-based web server that serves Twitter Archive.
'''

import os
import re
import pprint
import itertools
from datetime import datetime
from functools import lru_cache
from urllib.parse import urlparse
from collections.abc import Mapping

import flask
import requests
from elasticsearch import Elasticsearch


app = flask.Flask(
    __name__,
    static_url_path='/tweet/static'
)
app.config.from_object('config.Config')


# Set up external Tweets support
if app.config.get('T_EXTERNAL_TWEETS'):

    # https://developer.twitter.com/en/docs/basics/authentication/api-reference/token
    resp = requests.post(
        'https://api.twitter.com/oauth2/token',
        headers={
            'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8'
        },
        auth=(app.config['T_TWITTER_KEY'], app.config['T_TWITTER_SECRET']),
        data='grant_type=client_credentials'
    )
    if not resp.ok:
        raise RuntimeError('Failed to set up external Tweets support. Error from Twitter: {}'.format(resp.json()))
    bearer_token = resp.json()['access_token']
    app.config['T_TWITTER_TOKEN'] = bearer_token


class TweetsDatabase(Mapping):

    def __init__(self, es_host, es_index):
        self.es = Elasticsearch(es_host)
        self.es_index = es_index

    def _search(self, **kwargs):
        if not kwargs.get('index'):
            kwargs['index'] = self.es_index
        hits = self.es.search(**kwargs)['hits']['hits']
        tweets = []
        for hit in hits:
            tweet = hit['_source']
            tweet['@index'] = hit['_index']
            tweets.append(tweet)
        return tweets

    def __getitem__(self, tweet_id):
        resp = self._search(
            query={
                'term': {
                    'id': tweet_id
                }
            })
        if len(resp) == 0:
            raise KeyError('Tweet ID {} not found'.format(tweet_id))
        else:
            tweet = resp[0]
        return tweet

    def __iter__(self):
        resp = self._search(
            sort=['@timestamp'],
            #size=1000,
        )
        for tweet in resp:
            yield tweet['id']

    def __reversed__(self):
        resp = self._search(
            sort=[{
                '@timestamp': {'order': 'desc'}
            }],
            #size=1000,
        )
        for tweet in resp:
            yield tweet['id']

    def __len__(self):
        return self.es.count(index=self.es_index)['count']

    def search(self, *, keyword=None, user_screen_name=None, index=None, limit=100):
        keyword_query = {
            'simple_query_string': {
                'query': keyword,
                'fields': ['text', 'full_text'],
                'default_operator': 'AND',
            }
        }
        user_query = {
            'term': {
                'user.screen_name.keyword': user_screen_name
            }
        }
        compound_query = {
            'bool': {
                'must': keyword_query,
            }
        }
        if user_screen_name:
            compound_query['bool']['filter'] = user_query
        resp = self._search(
            index=index,
            query=compound_query,
            sort=[{
                '@timestamp': {'order': 'desc'}
            }],
            size=limit,
        )
        return resp

    def get_users(self):
        agg_name = 'user_screen_names'
        resp = self.es.search(
            index=self.es_index,
            size=0,
            aggs={
                agg_name: {
                    'terms': {
                        'field': 'user.screen_name.keyword'
                    }
                }
            },
        )
        users = [
            {
                'screen_name': bucket['key'],
                'tweets_count': bucket['doc_count']
            }
            for bucket in resp['aggregations'][agg_name]['buckets']
        ]
        return users

    def get_indexes(self):
        agg_name = 'index_names'
        resp = self.es.search(
            index=self.es_index,
            size=0,
            aggs={
                agg_name: {
                    'terms': {
                        'field': '_index'
                    }
                }
            },
        )
        indexes = [
            {
                'name': bucket['key'],
                'tweets_count': bucket['doc_count']
            }
            for bucket in resp['aggregations'][agg_name]['buckets']
        ]
        print(indexes)
        return indexes


def get_tdb():
    if not hasattr(flask.g, 'tdb'):
        flask.g.tdb = TweetsDatabase(
            app.config['T_ES_HOST'],
            app.config['T_ES_INDEX']
        )
    return flask.g.tdb


@app.template_global('get_tweet_link')
def get_tweet_link(screen_name, tweet_id, original_link=False):
    if original_link:
        return 'https://twitter.com/{}/status/{}'.format(screen_name, tweet_id)
    else:
        return flask.url_for('get_tweet', tweet_id=tweet_id, ext='html')


@app.template_filter('format_tweet_text')
def format_tweet_text(tweet):

    try:
        tweet_text = tweet['full_text']
    except KeyError:
        tweet_text = tweet['text']

    # Replace t.co-wrapped URLs with their original URLs
    # NOTE: for URL-expansion purpose, there are no difference between
    # extended_entities.media and entities.media
    urls = itertools.chain(
        tweet['entities'].get('urls', []),
        tweet['entities'].get('media', []),
    )
    for u in urls:
        # t.co wraps everything *looks like* a URL, even bare domains. We bring
        # sanity back.
        # A bare domain would be prepended a scheme but not a path,
        # while a real URL would always have a path.
        # https://docs.python.org/3/library/urllib.parse.html#url-parsing
        if urlparse(u['expanded_url']).path:
            a = '<a href="{expanded_url}">{display_url}</a>'.format_map(u)
        else:
            a = u['display_url']
        tweet_text = tweet_text.replace(u['url'], a)

    # Linkify hashtags
    hashtags = tweet['entities'].get('hashtags', [])
    for h in hashtags:
        hashtag = '#{}'.format(h['text'])
        link = 'https://twitter.com/hashtag/{}'.format(h['text'])
        a = '<a href="{}">{}</a>'.format(link, hashtag)
        tweet_text = tweet_text.replace(hashtag, a)

    # Linkify user mentions
    users = tweet['entities'].get('user_mentions', [])
    for user in users:
        # case-insensitive and case-preserving
        at_user = r'(?i)@({})\b'.format(user['screen_name'])
        link = 'https://twitter.com/{}'.format(user['screen_name'])
        a = r'<a href="{}" title="{}">@\1</a>'.format(link, user['name'])
        tweet_text = re.sub(at_user, a, tweet_text)

    # Link to retweeted status
    # NOTE: As of 2022-05, only tweets ingested via API has "retweeted" set to
    # true and has a valid "retweeted_status". Tweets that are ingested via
    # Twitter Archive always has "retweeted" set to false (identical to a
    # "traditional" RT.
    retweeted_status = tweet.get('retweeted_status')
    if retweeted_status:
        link = get_tweet_link('status', retweeted_status['id'])
        a = '<a href="{}">RT</a>'.format(link)
        tweet_text = tweet_text.replace('RT', a, 1)

    return tweet_text


@app.template_filter('format_created_at')
def format_created_at(timestamp, fmt):
    try:
        dt = datetime.strptime(timestamp, '%a %b %d %H:%M:%S %z %Y')
    except ValueError:
        dt = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S %z')
    return dt.strftime(fmt)


@app.template_filter('in_reply_to_link')
def in_reply_to_link(tweet):
    return get_tweet_link('status', tweet['in_reply_to_status_id'])


@app.template_filter('s3_link')
def get_s3_link(s3_key):
    return 'https://{}.s3.{}.amazonaws.com/{}'.format(
        app.config['T_MEDIA_S3_BUCKET'],
        app.config['T_MEDIA_S3_BUCKET_REGION'],
        s3_key
    )


@app.route('/')
def root():
    return flask.redirect(flask.url_for('index'))


@app.route('/tweet/')
def index():

    tdb = get_tdb()
    total_tweets = len(tdb)
    latest_tweets = [tdb[tid] for tid in itertools.islice(reversed(tdb), 10)]

    rendered = flask.render_template(
        'index.html',
        total_tweets=total_tweets,
        tweets=latest_tweets,
    )
    resp = flask.make_response(rendered)

    return resp


@lru_cache(maxsize=1024)
def fetch_tweet(tweet_id):

    resp = requests.get(
        'https://api.twitter.com/1.1/statuses/show.json',
        headers={
            'Authorization': 'Bearer {}'.format(app.config['T_TWITTER_TOKEN'])
        },
        params={
            'id': tweet_id,
            'tweet_mode': 'extended'
        },
    )
    if resp.ok:
        tweet = resp.json()
        return tweet
    else:
        flask.abort(resp.status_code)


@app.route('/tweet/<int:tweet_id>.<ext>')
def get_tweet(tweet_id, ext):

    if ext not in ('txt', 'json', 'html'):
        flask.abort(404)

    tdb = get_tdb()
    _is_external_tweet = False
    try:
        tweet = tdb[tweet_id]
    except KeyError:
        if app.config.get('T_EXTERNAL_TWEETS'):
            tweet = fetch_tweet(tweet_id)
            _is_external_tweet = True
        else:
            flask.abort(404)

    # Text and JSON output
    if ext == 'txt':
        rendered = pprint.pformat(tweet)
        resp = flask.make_response(rendered)
        resp.content_type = 'text/plain'
        return resp
    elif ext == 'json':
        rendered = flask.json.dumps(tweet, ensure_ascii=False)
        resp = flask.make_response(rendered)
        resp.content_type = 'application/json'
        return resp

    # HTML output

    # Generate img src
    images_src = []
    try:
        # https://developer.twitter.com/en/docs/tweets/data-dictionary/overview/extended-entities-object
        entities = tweet['extended_entities']
    except KeyError:
        entities = tweet['entities']
    media = entities.get('media', [])
    for m in media:
        media_url = m['media_url_https']
        media_key = os.path.basename(media_url)
        if _is_external_tweet or app.config['T_MEDIA_FROM'] == 'twitter':
            img_src = media_url
        elif app.config['T_MEDIA_FROM'] == 'fs':
            img_src = flask.url_for('get_media', filename=media_key)
        elif app.config['T_MEDIA_FROM'] == 's3':
            img_src = get_s3_link(media_key)
        else:
            img_src = ''
        images_src.append(img_src)

    # Render HTML
    rendered = flask.render_template(
        'tweet.html',
        tweet=tweet,
        images_src=images_src
    )
    resp = flask.make_response(rendered)

    return resp


@app.route('/tweet/media/<path:filename>')
def get_media(filename):
    return flask.send_from_directory(app.config['T_MEDIA_FS_PATH'], filename)


@app.route('/tweet/search.<ext>')
def search_tweet(ext):
    if ext not in ('html', 'txt', 'json'):
        flask.abort(404)

    basic_auth = app.config.get('T_SEARCH_BASIC_AUTH')
    if basic_auth and (basic_auth != flask.request.authorization):
        resp = flask.Response(
            status=401, headers={'WWW-Authenticate': 'Basic realm="Auth Required"'}
        )
        return resp

    tdb = get_tdb()
    users = tdb.get_users()
    indexes = tdb.get_indexes()

    user = flask.request.args.get('u', '')
    keyword = flask.request.args.get('q', '')
    index = flask.request.args.get('i', '')
    if keyword:
        tweets = tdb.search(
            keyword=keyword,
            user_screen_name=user,
            index=index,
        )
    else:
        tweets = []

    # Text and JSON output
    if ext == 'txt':
        rendered = pprint.pformat(tweets)
        resp = flask.make_response(rendered)
        resp.content_type = 'text/plain'
        return resp
    elif ext == 'json':
        rendered = flask.json.dumps(tweets, ensure_ascii=False)
        resp = flask.make_response(rendered)
        resp.content_type = 'application/json'
        return resp

    # HTML output
    rendered = flask.render_template(
        'search.html',
        keyword=keyword,
        user=user,
        users=users,
        index=index,
        indexes=indexes,
        tweets=tweets,
    )
    resp = flask.make_response(rendered)

    return resp
