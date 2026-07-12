import sys
sys.path.insert(0, '.')

from pipeline.vet import classify, non_latin_ratio, relevance_hits


def test_spam_flagged_even_when_tagged():
    # strong signal — applies regardless of AI topic tags
    a = {"title": "H555 Game Download APK for Android", "excerpt": "",
         "source_id": "medium-android-tag", "topics": ["android-api"]}
    assert "spam/non-dev" in classify(a)


def test_non_english_flagged():
    a = {"title": "تحميل تعريفات شاومي الرسمية وحل مشاكل", "excerpt": "",
         "source_id": "medium-android-tag", "topics": None}
    assert "non-english" in classify(a)


def test_offtopic_only_when_untagged():
    base = {"title": "My Flutter App Was Buttery at 20 Widgets", "excerpt": "flutter widgets",
            "source_id": "medium-android-tag"}
    assert any(r.startswith("off-topic") for r in classify({**base, "topics": None}))
    # once the AI tags it, the soft signal must NOT override
    assert classify({**base, "topics": ["android-api"]}) == []


def test_no_signal_aggregator_only_when_untagged():
    base = {"title": "Maafkan Aku Jatuh Hati", "excerpt": "",
            "source_id": "medium-kotlin-tag"}
    assert "no-kotlin-signal" in classify({**base, "topics": None})
    assert classify({**base, "topics": ["kotlin"]}) == []


def test_clean_kotlin_article_passes():
    a = {"title": "Coroutines structured concurrency in Kotlin", "excerpt": "",
         "source_id": "medium-kotlin-tag", "topics": None}
    assert classify(a) == []


def test_non_latin_ratio_english_is_zero():
    assert non_latin_ratio("Jetpack Compose tips") == 0.0
    assert non_latin_ratio("تحميل تعريفات") > 0.5


def test_relevance_hits_broadened():
    # broadened vocab rescues legit posts scout's narrow list would miss
    assert relevance_hits("animating item placement in lazy lists") >= 1
    assert relevance_hits("diffutil and listadapter") >= 1
