import sys
sys.path.insert(0, '.')

from bs4 import BeautifulSoup

from pipeline.scout import (
    article_id,
    extract_date_from_html,
    is_youtube_short,
    looks_like_live_video,
    normalize_url,
    parse_date_str,
    source_feed_url,
    video_filter_reason,
    youtube_thumbnail_from_entry,
    youtube_video_id_from_entry,
)


def test_parse_date_str_iso_date():
    assert parse_date_str("2026-07-21").strftime("%Y-%m-%d") == "2026-07-21"


def test_extract_date_from_jsonld_upload_date():
    soup = BeautifulSoup(
        """
        <script type="application/ld+json">
        {"@type":"VideoObject","name":"Kotlin Talk","uploadDate":"2026-07-21"}
        </script>
        """,
        "html.parser",
    )

    dt, uncertain = extract_date_from_html(soup, "https://www.youtube.com/watch?v=test")

    assert dt.strftime("%Y-%m-%d") == "2026-07-21"
    assert uncertain is False


def test_extract_date_from_jsonld_graph_upload_date():
    soup = BeautifulSoup(
        """
        <script type="application/ld+json">
        {"@graph":[
          {"@type":"WebPage","name":"Video page"},
          {"@type":"VideoObject","uploadDate":"2026-07-22T10:00:00Z"}
        ]}
        </script>
        """,
        "html.parser",
    )

    dt, uncertain = extract_date_from_html(soup, "https://www.youtube.com/watch?v=test")

    assert dt.strftime("%Y-%m-%d") == "2026-07-22"
    assert uncertain is False


def test_normalize_youtube_watch_preserves_video_id_only():
    assert normalize_url("https://www.youtube.com/watch?v=W2dOOBN1OQI&t=10s") == (
        "https://www.youtube.com/watch?v=W2dOOBN1OQI"
    )


def test_youtube_watch_ids_do_not_collide():
    first = article_id("https://www.youtube.com/watch?v=W2dOOBN1OQI")
    second = article_id("https://www.youtube.com/watch?v=iQsN_IDUTSc")

    assert first != second


def test_youtube_shorts_are_valid_article_urls():
    assert article_id("https://www.youtube.com/shorts/BQZZh8L1w_A")


def test_video_filter_can_exclude_shorts_per_source():
    source = {"type": "video", "video": {"include_shorts": False}}

    assert video_filter_reason(
        source,
        "https://www.youtube.com/shorts/BQZZh8L1w_A",
        "Short Android tip",
        "",
    ) == "short"


def test_video_filter_allows_shorts_by_default():
    assert video_filter_reason(
        {"type": "video"},
        "https://www.youtube.com/shorts/BQZZh8L1w_A",
        "Short Android tip",
        "",
    ) is None


def test_video_filter_can_exclude_live_per_source():
    source = {"type": "video", "video": {"include_live": False}}

    assert video_filter_reason(
        source,
        "https://www.youtube.com/watch?v=Np7RsqtkF1Q",
        "Jetpack Compose 5th-Anniversary: Livestream Birthday Party",
        "",
    ) == "live"


def test_video_filter_can_exclude_terms_per_source():
    source = {"type": "video", "video": {"exclude_terms": ["#ad", "#anzeige"]}}

    assert video_filter_reason(
        source,
        "https://www.youtube.com/watch?v=test",
        "Android architecture",
        "Thanks to the sponsor #Anzeige",
    ) == "excluded-term:#anzeige"


def test_youtube_short_and_live_helpers():
    assert is_youtube_short("https://www.youtube.com/shorts/BQZZh8L1w_A")
    assert not is_youtube_short("https://www.youtube.com/watch?v=BQZZh8L1w_A")
    assert looks_like_live_video("Live: Android Q&A", "")
    assert not looks_like_live_video("Livecoding Soundscapes with Compose Multiplatform", "")


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
