# Twitter Archive Server (V2)

Twitter Archive Server, as its name implies, provides a UI to view and search tweets in the archive (database). The project is useful if you have a protected Twitter account. It aims to solve the following issues:

1. A user with a protected Twitter account cannot search their own tweets;
2. A user with a protected Twitter account cannot share their tweets with whom without Twitter accounts;
3. A user cannot search their own "Liked" / "Favorited" tweets.

The project is a rewrite of [ash](https://github.com/wzyboy/ash).

## Features:

- Use Elasticsearch as the backend ([simple query syntax](https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-simple-query-string-query.html));
- Multiple archives from different accounts could be merged together;
- HTML, TXT and JSON formats;
- Full-text search with optional basic auth;
- Linkify mentions, hashtags, retweets, etc;
- Restore sanity to t.co-wrapped links and non-links;
- Hot-link images from Twitter, on-disk mirror, or S3 mirror;
- Fetch Tweets from Twitter API if not found in the database.


## Setup

1. Use [tbeat](https://github.com/wzyboy/tbeat) to load your tweets into Elasticsearch;
2. Copy `config.sample.py` to `config.py` and edit it to meet your needs.


## Running

Setting up a venv is recommended:

```bash
$ python3 -m venv venv
$ source venv/bin/activate
```

For development / quick start:

```bash
$ (venv) pip install -r requirements.txt
$ (venv) FLASK_APP=ash flask run --port 3026
```

You could now view and search your Twitter Archive at: http://localhost:3026/

-----

For production deployment, you may want to use [Gunicorn](https://docs.gunicorn.org/en/stable/deploy.html).
