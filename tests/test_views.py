class TestIndexView:
    def test_index(self, client):
        resp = client.get('/tweet/')
        assert '<p>Number of Tweets: <code>2</code>' in resp.text
        assert 'wzyboy' in resp.text
        assert 'Uucky_Lee' in resp.text

    def test_index_with_default_user(self, client):
        client.application.config['T_DEFAULT_USER'] = 'wzyboy'
        resp = client.get('/tweet/')
        assert 'wzyboy' in resp.text
        assert 'Uucky_Lee' not in resp.text


class TestSearchView:
    keywords = ('please connect a keyboard', 'This guy found a starving dog')

    def test_search(self, client):
        resp = client.get(
            '/tweet/search.html',
            query_string={'q': '*'}
        )
        for kw in self.keywords:
            assert kw in resp.text


class TestMediaReplacement:
    tweet_id = '1615425412921987074'
    media_filename = 'Fmsk2gHacAAJGL0.jpg'
    cf_domain = 'd1111111111.cloudfront.net'

    def test_direct_media(self, client):
        client.application.config['T_MEDIA_FROM'] = 'direct'
        resp = client.get(f'/tweet/{self.tweet_id}.html')
        assert f'https://pbs.twimg.com/media/{self.media_filename}' in resp.text

    def test_mirror_media(self, client):
        client.application.config['T_MEDIA_FROM'] = 'mirror'
        client.application.config['T_MEDIA_MIRRORS'] = {
            'pbs.twimg.com': f'{self.cf_domain}/pbs.twimg.com',
            'video.twimg.com': f'{self.cf_domain}/video.twimg.com',
        }
        resp = client.get(f'/tweet/{self.tweet_id}.html')
        assert f'https://{self.cf_domain}/pbs.twimg.com/media/{self.media_filename}' in resp.text

    def test_fs_media(self, client):
        client.application.config['T_MEDIA_FROM'] = 'filesystem'
        client.application.config['T_MEDIA_FS_PATH'] = './media'
        resp = client.get(f'/tweet/{self.tweet_id}.html')
        assert f'/tweet/media/pbs.twimg.com/media/{self.media_filename}' in resp.text
