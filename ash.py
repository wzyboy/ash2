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
        raise RuntimeError(f'Failed to set up external Tweets support. Error from Twitter: {resp.json()}')
    bearer_token = resp.json()['access_token']
    app.config['T_TWITTER_TOKEN'] = bearer_token


def toot_to_tweet(status):
    '''Transform toot to be compatible with tweet-interface'''
    # Status is a tweet
    if status.get('user'):
        return status
    # Status is a toot
    user = {
        'profile_image_url_https': status['account']['avatar'],
        'screen_name': status['account']['fqn'],
        'name': status['account']['display_name'],
    }
    media = [
        {
            'media_url_https': att['url'],
            'description': att['description']
        }
        for att in status['media_attachments']
    ]
    status['user'] = user
    status['full_text'] = status['content']
    status['entities'] = {}
    status['extended_entities'] = {
        'media': media
    }
    status['in_reply_to_status_id'] = status['in_reply_to_id']
    status['in_reply_to_screen_name'] = status.get('pleroma', {}).get('in_reply_to_account_acct', '...')
    return status


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
            tweet = toot_to_tweet(tweet)
            tweets.append(tweet)
        return tweets

    def __getitem__(self, tweet_id):
        resp = self._search(
            query={
                'term': {
                    '_id': tweet_id
                }
            })
        if len(resp) == 0:
            raise KeyError(f'Tweet ID {tweet_id} not found')
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
                'fields': ['text', 'full_text', 'content_text', 'media_attachments.description'],
                'default_operator': 'AND',
            }
        }
        if user_screen_name and '@' in user_screen_name:  # Mastodon
            screen_name_field = 'account.fqn.keyword'
        else:
            screen_name_field = 'user.screen_name.keyword'
        user_query = {
            'term': {
                screen_name_field: user_screen_name
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
        agg_name_twitter = 'user_screen_names'
        agg_name_mastodon = 'account_fqn'
        resp = self.es.search(
            index=self.es_index,
            size=0,
            aggs={
                agg_name_twitter: {
                    'terms': {
                        'field': 'user.screen_name.keyword'
                    }
                },
                agg_name_mastodon: {
                    'terms': {
                        'field': 'account.fqn.keyword'
                    }
                }
            },
        )
        buckets = resp['aggregations'][agg_name_twitter]['buckets'] + resp['aggregations'][agg_name_mastodon]['buckets']
        users = [
            {
                'screen_name': bucket['key'],
                'tweets_count': bucket['doc_count']
            }
            for bucket in buckets
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
        return f'https://twitter.com/{screen_name}/status/{tweet_id}'
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
            a = f'<a href="{u["expanded_url"]}">{u["display_url"]}</a>'
        else:
            a = u['display_url']
        tweet_text = tweet_text.replace(u['url'], a)

    # Linkify hashtags
    hashtags = tweet['entities'].get('hashtags', [])
    for h in hashtags:
        hashtag = f'#{h["text"]}'
        link = f'https://twitter.com/hashtag/{h["text"]}'
        a = f'<a href="{link}">{hashtag}</a>'
        tweet_text = tweet_text.replace(hashtag, a)

    # Linkify user mentions
    users = tweet['entities'].get('user_mentions', [])
    for user in users:
        name = user['name']
        screen_name = user['screen_name']
        # case-insensitive and case-preserving
        at_user = rf'(?i)@({screen_name})\b'
        link = f'https://twitter.com/{screen_name}'
        a = rf'<a href="{link}" title="{name}">@\1</a>'
        tweet_text = re.sub(at_user, a, tweet_text)

    # Link to retweeted status
    # NOTE: As of 2022-05, only tweets ingested via API has "retweeted" set to
    # true and has a valid "retweeted_status". Tweets that are ingested via
    # Twitter Archive always has "retweeted" set to false (identical to a
    # "traditional" RT.
    retweeted_status = tweet.get('retweeted_status')
    if retweeted_status:
        link = get_tweet_link('status', retweeted_status['id'])
        a = f'<a href="{link}">RT</a>'
        tweet_text = tweet_text.replace('RT', a, 1)

    # Format reblogged toot
    reblogged_status = tweet.get('reblog')
    if reblogged_status:
        status_link = reblogged_status['url']
        author = reblogged_status['account']['fqn']
        author_link = reblogged_status['account']['url']
        prefix = f'<a href="{status_link}">RT</a> <a href="{author_link}">@{author}</a>: '
        tweet_text = prefix + tweet_text

    return tweet_text


@app.template_filter('format_created_at')
def format_created_at(timestamp, fmt):
    try:
        dt = datetime.strptime(timestamp, '%a %b %d %H:%M:%S %z %Y')
    except ValueError:
        try:
            dt = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S %z')
        except ValueError:
            dt = datetime.strptime(timestamp, '%Y-%m-%dT%H:%M:%S%z')
    return dt.strftime(fmt)


@app.template_filter('in_reply_to_link')
def in_reply_to_link(tweet):
    if tweet.get('account'):  # Mastodon
        # If this is a self-thread, return local link
        if tweet['in_reply_to_account_id'] == tweet['account']['id']:
            return flask.url_for('get_tweet', tweet_id=tweet['in_reply_to_id'], ext='html')
        # Else, redir to web interface to see the thread
        else:
            return tweet['url']
    else:  # Twitter
        return get_tweet_link('status', tweet['in_reply_to_status_id'])


@app.template_filter('s3_link')
def get_s3_link(s3_key):
    bucket = app.config['T_MEDIA_S3_BUCKET']
    region = app.config['T_MEDIA_S3_BUCKET_REGION']
    return f'https://{bucket}.s3.{region}.amazonaws.com/{s3_key}'


@app.route('/')
def root():
    return flask.redirect(flask.url_for('index'))


@app.route('/tweet/')
def index():

    tdb = get_tdb()
    total_tweets = len(tdb)
    default_user = app.config.get('T_DEFAULT_USER')
    if default_user:
        latest_tweets = tdb.search(keyword='*', user_screen_name=default_user, limit=10)
    else:
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

    token = app.config['T_TWITTER_TOKEN']

    resp = requests.get(
        'https://api.twitter.com/1.1/statuses/show.json',
        headers={
            'Authorization': f'Bearer {token}'
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


@app.route('/tweet/<tweet_id>.<ext>')
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

    # Extract list images
    images = []
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
        images.append({
            'url': img_src,
            'description': m.get('description', '')
        })

    # Render HTML
    rendered = flask.render_template(
        'tweet.html',
        tweet=tweet,
        images=images
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
