import sys
sys.path.insert(0, '.')

from pipeline.scout import (
    source_feed_url,
    youtube_thumbnail_from_entry,
    youtube_video_id_from_entry,
)


def test_source_feed_url_derives_youtube_channel_feed():
    source = {"type": "youtube", "channel_id": "UC123"}
    assert source_feed_url(source) == "https://www.youtube.com/feeds/videos.xml?channel_id=UC123"


def test_source_feed_url_prefers_explicit_feed():
    source = {"type": "youtube", "channel_id": "UC123", "rss": "https://example.com/feed.xml"}
    assert source_feed_url(source) == "https://example.com/feed.xml"


def test_youtube_video_id_from_entry_metadata_or_url():
    assert youtube_video_id_from_entry({"yt_videoid": "abcdefghijk"}, "") == "abcdefghijk"
    assert youtube_video_id_from_entry({}, "https://www.youtube.com/watch?v=bbbbbbbbbbb") == "bbbbbbbbbbb"


def test_youtube_thumbnail_from_entry():
    entry = {"media_thumbnail": [{"url": "https://i.ytimg.com/vi/x/hqdefault.jpg"}]}
    assert youtube_thumbnail_from_entry(entry) == "https://i.ytimg.com/vi/x/hqdefault.jpg"
