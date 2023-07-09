
class Config:

    # Elasticsearch
    T_ES_HOST = 'http://localhost:9200'
    T_ES_INDEX = 'tweets-*,toots-*'

    # Where to load media files
    # direct: Media files are hotlinked from Twitter
    # mirror: Media files are served from T_MEDIA_MIRRORS
    # filesystem: Media files are served from T_MEDIA_FS_PATH
    T_MEDIA_FROM = 'direct'

    # You can also mirror domains in case your Twitter account no longer exists
    # This is just simple string substitution
    T_MEDIA_MIRRORS = {
        'pbs.twimg.com': 'd1111111111.cloudfront.net/pbs.twimg.com',
        'video.twimg.com': 'd1111111111.cloudfront.net/video.twimg.com',
    }

    # Directory path if loading images from filesystem
    T_MEDIA_FS_PATH = './media'

    # Uncomment to enable basic auth on search page
    #T_SEARCH_BASIC_AUTH = {'username': 'foo', 'password': 'bar'}

    # Uncomment to enable external Tweets support. If a Tweet is not found in
    # the database, it will be fetched from Twitter API.
    T_EXTERNAL_TWEETS = False
    #T_TWITTER_KEY = 'consumer key'
    #T_TWITTER_SECRET = 'consumer secret'

    # Default user to show on index
    #T_DEFAULT_USER = 'jack'
