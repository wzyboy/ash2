# Twitter Archive Server (V2)

Twitter Archive Server, as its name implies, provides a UI to view and search tweets in the archive (database). The project is useful if you have a protected Twitter account. It aims to solve the following issues:

1. A user with a protected Twitter account cannot search their own tweets;
2. A user with a protected Twitter account cannot share their tweets with whom without Twitter accounts;
3. A user cannot search their own "Liked" / "Favorited" tweets.

Additionally, if your Twitter account no longer exists, you can use this server to serve your tweets from your archive.

## Features:

- Use Elasticsearch as the backend ([simple query syntax](https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-simple-query-string-query.html));
- Multiple archives from different accounts could be merged together;
- HTML, TXT and JSON formats;
- Full-text search with optional basic auth;
- Linkify mentions, hashtags, retweets, etc;
- Restore sanity to t.co-wrapped links and non-links;
- Hotlink images from Twitter, or a mirror URL of your choice, or a directory;
- Fetch Tweets from Twitter API if not found in the database (requires Twitter API key).


## Setup

1. Use [tbeat](https://github.com/wzyboy/tbeat) to load your tweets into Elasticsearch;
2. (Optional) Copy `config.sample.py` to `config.py` and edit it to meet your needs.


## Media

If your Twitter account is still alive, all your media files can still be accessed from `(pbs|video).twimg.com` domains. In case your Twitter account no longer exists, you need an alternate way to serve the media files.

Check out `./contrib/extract_media/main.py` for a helper script to extract media files from Twitter archive and/or `(pbs|video).twimg.com`. You can then [upload](https://rclone.org/) the local directory to an object storage service and serve it with a CDN by setting `T_MEDIA_MIRRORS` parameter in `config.py`. This archive server can also be configured to serve the files from a local directory `T_MEDIA_FS_PATH`.

## Running

Setting up a venv is recommended:

```bash
$ python3 -m venv venv
$ source venv/bin/activate
```

For development / quick start:

```bash
$ (venv) pip install -r requirements.txt
$ (venv) make dev-server
```

You could now view and search your Twitter Archive at: [http://localhost:3026/](http://localhost:3026/)

-----

For production deployment, you may want to use [Gunicorn](https://docs.gunicorn.org/en/stable/deploy.html).
