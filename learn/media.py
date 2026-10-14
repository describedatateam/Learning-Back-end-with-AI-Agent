"""NotebookLM video and audio overviews, linked per chapter in admin (ChapterMedia).

NotebookLM has no public API, so the instructor makes each overview by hand,
shares it (YouTube unlisted or Google Drive) and pastes the link in admin. Here
those links become something a phone can play inline: YouTube and Drive links
turn into embed addresses, direct audio files play in an <audio> tag, and
anything else stays a plain link that opens in a new tab.
"""
import re
from urllib.parse import parse_qs, urlparse

from .models import ChapterMedia

YOUTUBE_ID = re.compile(r'^[\w-]{11}$')
DRIVE_FILE = re.compile(r'/file/d/([\w-]+)')
AUDIO_EXTENSIONS = ('.mp3', '.m4a', '.wav', '.ogg', '.aac')


def youtube_id(url):
    parts = urlparse(url)
    host = parts.netloc.lower().removeprefix('www.').removeprefix('m.')
    if host == 'youtu.be':
        candidate = parts.path.strip('/').split('/')[0]
    elif host in ('youtube.com', 'youtube-nocookie.com'):
        if parts.path == '/watch':
            candidate = parse_qs(parts.query).get('v', [''])[0]
        else:
            bits = parts.path.strip('/').split('/')
            candidate = bits[1] if len(bits) > 1 and bits[0] in ('embed', 'shorts', 'live') else ''
    else:
        return ''
    return candidate if YOUTUBE_ID.match(candidate or '') else ''


def drive_id(url):
    parts = urlparse(url)
    if parts.netloc.lower() != 'drive.google.com':
        return ''
    match = DRIVE_FILE.search(parts.path)
    if match:
        return match.group(1)
    return parse_qs(parts.query).get('id', [''])[0] if parts.path == '/open' else ''


def player(url, audio=False):
    """How to show one link: {'kind': 'frame' | 'audio' | 'link', 'src': ..., 'url': ...}."""
    if not url:
        return None
    video = youtube_id(url)
    if video:
        return {'kind': 'frame', 'src': f'https://www.youtube-nocookie.com/embed/{video}', 'url': url}
    drive = drive_id(url)
    if drive:
        return {'kind': 'frame', 'src': f'https://drive.google.com/file/d/{drive}/preview', 'url': url,
                'short': audio}
    if audio and urlparse(url).path.lower().endswith(AUDIO_EXTENSIONS):
        return {'kind': 'audio', 'src': url, 'url': url}
    return {'kind': 'link', 'src': url, 'url': url}


def for_chapter(slug):
    """The chapter's video and audio players, or None when it has neither."""
    media = ChapterMedia.objects.filter(chapter_slug=slug).first()
    if not media or not (media.video_url or media.audio_url):
        return None
    return {'video': player(media.video_url), 'audio': player(media.audio_url, audio=True), 'note': media.note}


def chapters_with_media():
    """{chapter slug: {'video': url, 'audio': url}}, for the link chips on chapter lists."""
    return {m.chapter_slug: {'video': m.video_url, 'audio': m.audio_url}
            for m in ChapterMedia.objects.all() if m.video_url or m.audio_url}
