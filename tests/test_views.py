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
