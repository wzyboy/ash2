class TestViews:
    def test_index(self, client):
        resp = client.get('/tweet/')
        print(resp.text)
        assert 'Twitter Archive' in resp.text
        assert 'keyboard' in resp.text

    def test_direct_media(self, client):
        client.application.config['T_MEDIA_FROM'] = 'direct'
        resp = client.get('/tweet/1615425412921987074.html')
        assert 'https://pbs.twimg.com/media/Fmsk2gHacAAJGL0.jpg' in resp.text

    def test_mirror_media(self, client):
        CF_DOMAIN = 'd1111111111.cloudfront.net'
        client.application.config['T_MEDIA_FROM'] = 'mirror'
        client.application.config['T_MEDIA_MIRRORS'] = {
            'pbs.twimg.com': f'{CF_DOMAIN}/pbs.twimg.com',
            'video.twimg.com': f'{CF_DOMAIN}/video.twimg.com',
        }
        resp = client.get('/tweet/1615425412921987074.html')
        assert f'https://{CF_DOMAIN}/pbs.twimg.com/media/Fmsk2gHacAAJGL0.jpg' in resp.text

    def test_fs_media(self, client):
        client.application.config['T_MEDIA_FROM'] = 'filesystem'
        client.application.config['T_MEDIA_FS_PATH'] = './media'
        resp = client.get('/tweet/1615425412921987074.html')
        assert '/tweet/media/pbs.twimg.com/media/Fmsk2gHacAAJGL0.jpg' in resp.text
