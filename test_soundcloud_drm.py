from pathlib import Path
from unittest.mock import patch
import pytest
import killa_tools as kt

URL='https://soundcloud.com/example/track'
ERROR='ERROR: [soundcloud] 256277192: This video is DRM protected'

@pytest.mark.parametrize('available',[True,False])
def test_drm_only_metadata_recovery_then_verified_alternative(tmp_path,available):
    calls=[];alternate='https://www.youtube.com/watch?v=verified'
    def run(args,**kwargs):
        calls.append(args)
        if '--skip-download' in args:
            return (0,'Song\t120\tArtist','') if '--ignore-no-formats-error' in args else (1,'',ERROR)
        assert alternate in args, 'Protected direct media must never be downloaded'
        (tmp_path/'download.mp3').write_bytes(b'non-drm alternate audio')
        return 0,'',''
    candidates=[dict(url=alternate,is_youtube=True,duration=120)] if available else []
    with patch.object(kt,'_run_yt',side_effect=run),patch.object(kt,'_ytdlp_bin',return_value='yt-dlp'),patch.object(kt,'_normalize_download_url',return_value=URL),patch.object(kt,'_cookies_args',return_value=[]),patch.object(kt,'_probe_verified_search_candidates',return_value=candidates) as search,patch.object(kt,'_duration_seconds',return_value=120),patch.object(kt,'strip_audio_metadata'):
        if available:
            result=kt.download_media(URL,str(tmp_path))
            assert result['webpage_url']==alternate
            assert 'DRM was not decrypted' in result['note']
            assert Path(result['path']).exists()
        else:
            with pytest.raises(RuntimeError,match='No unprotected full download'):
                kt.download_media(URL,str(tmp_path))
    assert search.call_count==1
    assert len([c for c in calls if '--ignore-no-formats-error' in c])==1
    assert all('--allow-unplayable-formats' not in c for c in calls)
    assert all('--ignore-no-formats-error' not in c or '--skip-download' in c for c in calls)


def test_direct_drm_failure_is_not_retried_as_download(tmp_path):
    calls=[]
    def run(args,**kwargs):
        calls.append(args)
        if '--skip-download' in args:return 0,'Song\t120\tArtist',''
        return 1,'',ERROR
    with patch.object(kt,'_run_yt',side_effect=run),patch.object(kt,'_ytdlp_bin',return_value='yt-dlp'),patch.object(kt,'_normalize_download_url',return_value=URL),patch.object(kt,'_cookies_args',return_value=[]),patch.object(kt,'_probe_verified_search_candidates',return_value=[]):
        with pytest.raises(RuntimeError,match='SoundCloud reports DRM'):
            kt.download_media(URL,str(tmp_path))
    assert len([c for c in calls if '-x' in c])==1


def test_no_metadata_means_no_guessed_search(tmp_path):
    with patch.object(kt,'_run_yt',return_value=(1,'',ERROR)),patch.object(kt,'_ytdlp_bin',return_value='yt-dlp'),patch.object(kt,'_normalize_download_url',return_value=URL),patch.object(kt,'_cookies_args',return_value=[]),patch.object(kt,'_probe_verified_search_candidates') as search:
        with pytest.raises(RuntimeError,match='DRM was not decrypted'):
            kt.download_media(URL,str(tmp_path))
    search.assert_not_called()


def test_drm_hint_does_not_invent_scheme():
    hint=kt._err_hint(ERROR)
    assert 'Widevine/PlayReady' not in hint
    assert 'cannot decrypt' in hint
