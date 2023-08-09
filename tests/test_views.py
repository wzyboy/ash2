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

    def test_search_with_basic_auth(self, client):
        db = {
            'username': 'foo',
            'password': 'bar'
        }
        client.application.config['T_SEARCH_BASIC_AUTH'] = db
        resp = client.get('/tweet/search.html')
        assert resp.status_code == 401
        resp = client.get('/tweet/search.html', auth=(db['username'], db['password']))
        assert '<option value="wzyboy">' in resp.text


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


class TestUserDictInjection:
    tweet_id = '1676023376631197696'
    screen_name = 'alan_blake'
    name = 'Test Injection Name'
    profile_image_url_https = 'https://example.com/profile.png'

    def test_injection(self, client):
        user_dicts = {}
        user_dicts[self.screen_name] = {
            'name': self.name,
            'profile_image_url_https': self.profile_image_url_https,
        }
        client.application.config['T_USER_DICTS'] = user_dicts
        resp = client.get(f'/tweet/{self.tweet_id}.html')
        assert f'<div class="screen-name">@{self.screen_name}</div>' in resp.text
        assert f'<div class="name">{self.name}</div>' in resp.text
        assert f'<img src="{self.profile_image_url_https}"' in resp.text
