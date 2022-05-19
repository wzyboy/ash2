# Twitter Archive Server

## Features:

- No external database needed;
- Multiple archives from different accounts could be merged together;
- HTML, TXT and JSON output;
- Full-text search (optional basic auth);
- Linkify mentions, hashtags, retweets, etc;
- Restore sanity to t.co-wrapped links and non-links;
- Load images from Twitter, or on-disk mirror, or S3 mirror;
- Fetch Tweets from Twitter API if not found in the archive.


## Requirements

- Python 3
- Flask


## Setup

1. Download your [Twitter Archive](https://help.twitter.com/en/managing-your-account/how-to-download-your-twitter-archive);
2. Extract `data/` directory from the zip file;
3. Load archive files into SQLite: `./scripts/initdb.py`;
4. (Optional) Use `./scripts/extract_media_urls.py` to extract and download media files;
5. Copy `config.sample.py` to `config.py` and edit it to meet your needs.

You could load multiple archives from different accounts into SQLite by repeating step 2 with `-a / --append` flag.


## Running

Set up a venv is recommended:

```bash
$ python3 -m venv venv
$ source venv/bin/activate
```

For development / quick start:

```bash
$ pip install Flask
$ FLASK_APP=ash.py flask run --port 3026
```

You could now view and search your Twitter Archive at: http://localhost:3026/

-----

For production deployment, you may want to use [Gunicorn](https://docs.gunicorn.org/en/stable/deploy.html).
