
class Config:

    # Elasticsearch
    T_ES_HOST = 'localhost:9200'
    T_ES_INDEX = 'tweets-*,toots-*'

    # Where to load media files
    # hotlink: Media files will be hotlinked from T_MEDIA_BASEURL
    # filesystem: Media files would be served from T_MEDIA_FS_PATH
    T_MEDIA_FROM = 'hotlink'

    # You can also use an alternative domain in case your Twitter account no longer exists
    # T_MEDIA_BASEURL = 'https://d1111111111.cloudfront.net/pbs.twimg.com'
    T_MEDIA_BASEURL = 'https://pbs.twimg.com'

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
