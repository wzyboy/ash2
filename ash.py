'''
A Flask-based web server that serves Twitter Archive.
'''

import os
import re
import json
import pprint
import sqlite3
import itertools
from operator import itemgetter
from functools import lru_cache
from urllib.parse import urlparse
from collections.abc import Mapping

import flask
try:
    import requests
except ImportError:
    HAS_REQUESTS = False
else:
    HAS_REQUESTS = True


app = flask.Flask(
    __name__,
    static_url_path='/tweet/static'
)
app.config.from_object('config.Config')


# Set up external Tweets support
if app.config.get('T_EXTERNAL_TWEETS'):

    if not HAS_REQUESTS:
        raise RuntimeError('Python library "requests" is required to enable external Tweets support')

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

    def __init__(self, db_name):
        self.db = sqlite3.connect(db_name)
        self.db.row_factory = sqlite3.Row

    def __getitem__(self, tweet_id):
        if not isinstance(tweet_id, int):
            raise TypeError('Tweet ID should be int')
        cur = self.db.cursor()
        row = cur.execute('select * from tweets where id = ?', (tweet_id,)).fetchone()
        if row is None:
            raise KeyError('Tweet ID {} not found'.format(tweet_id))
        else:
            tweet = self._row_to_tweet(row)
        return tweet

    def __iter__(self):
        cur = self.db.cursor()
        for row in cur.execute('select id from tweets order by id asc'):
            yield row['id']

    def __reversed__(self):
        cur = self.db.cursor()
        for row in cur.execute('select id from tweets order by id desc'):
            yield row['id']

    def __len__(self):
        cur = self.db.cursor()
        row = cur.execute('select count(*) as c from tweets').fetchone()
        return row['c']

    @staticmethod
    def _row_to_tweet(row):
        _tweet = row['_source']
        tweet = json.loads(_tweet)
        return tweet

    def search(self, keyword=None, user_screen_name=None, limit=100):
        cur = self.db.cursor()

        # Be careful of little bobby tables
        # https://xkcd.com/327/
        _where = []
        params = {'limit': limit}
        if keyword:
            _where.append('text like :keyword')
            params['keyword'] = '%{}%'.format(keyword)
        if user_screen_name:
            _where.append('json_extract(_source, "$.user.screen_name") = :user_screen_name')
            params['user_screen_name'] = user_screen_name

        # Assemble the SQL
        where = 'where ' + ' and '.join(_where) if _where else ''
        sql = 'select * from tweets {} order by id desc limit :limit'.format(where)

        rows = cur.execute(sql, params).fetchall()
        tweets = [self._row_to_tweet(row) for row in rows]
        return tweets

    def _sql(self, *args):
        cur = self.db.cursor()
        rows = cur.execute(*args).fetchall()
        return rows


def get_tdb():
    if not hasattr(flask.g, 'tdb'):
        db_name = app.config['T_SQLITE']
        flask.g.tdb = TweetsDatabase(db_name)
    return flask.g.tdb


@app.template_global('get_tweet_link')
def get_tweet_link(screen_name, tweet_id):

    twitter_link = 'https://twitter.com/{}/status/{}'.format(screen_name, tweet_id)
    self_link = flask.url_for('get_tweet', tweet_id=tweet_id, ext='html')

    if app.config.get('T_EXTERNAL_TWEETS'):
        return self_link

    tdb = get_tdb()
    if tweet_id in tdb:
        return self_link
    else:
        return twitter_link


@app.template_filter('format_tweet_text')
def format_tweet_text(tweet):

    try:
        tweet_text = tweet['full_text']
    except KeyError:
        tweet_text = tweet['text']

    # Replace t.co-wrapped URLs with their original URLs
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
    retweeted = tweet.get('retweeted_status')
    if retweeted:
        link = get_tweet_link(retweeted['user']['screen_name'], retweeted['id'])
        a = '<a href="{}">RT</a>'.format(link)
        tweet_text = tweet_text.replace('RT', a, 1)

    return tweet_text


@app.template_filter('in_reply_to_link')
def in_reply_to_link(tweet):
    return get_tweet_link(tweet['in_reply_to_screen_name'], tweet['in_reply_to_status_id'])


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
    user_list = [
        row['u'] for row in
        tdb._sql('select json_extract(_source, "$.user.screen_name") as u from tweets group by u')
    ]

    user = flask.request.args.get('u', '')
    keyword = flask.request.args.get('q', '')
    if keyword:
        tweets = sorted(
            tdb.search(
                keyword=keyword,
                user_screen_name=user,
            ),
            key=itemgetter('id'),
            reverse=True
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
        user_list=user_list,
        tweets=tweets
    )
    resp = flask.make_response(rendered)

    return resp
