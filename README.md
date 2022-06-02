# Twitter Archive Server (V2)

The project is useful if you have a protected Twitter account but you still want to show some of your tweets to the public. 

The project is a partial rewrite of [ash](https://github.com/wzyboy/ash).

## Features:

- Use Elasticsearch as the backend ([simple query syntax](https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-simple-query-string-query.html));
- Multiple archives from different accounts could be merged together;
- HTML, TXT and JSON output;
- Full-text search (optional basic auth);
- Linkify mentions, hashtags, retweets, etc;
- Restore sanity to t.co-wrapped links and non-links;
- Load images from Twitter, on-disk mirror, or S3 mirror;
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
$ (venv) FLASK_APP=ash.py flask run --port 3026
```

You could now view and search your Twitter Archive at: http://localhost:3026/

-----

For production deployment, you may want to use [Gunicorn](https://docs.gunicorn.org/en/stable/deploy.html).
