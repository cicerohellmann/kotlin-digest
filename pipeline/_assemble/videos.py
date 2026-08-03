from collections import defaultdict


STRONG_KOTLIN_VIDEO_TERMS = {
    "kotlin", "kotlin multiplatform", "compose multiplatform", "kotlin/native",
    "kotlinx", "ktor", "koog", "amper", "coroutines", "kmp",
}

MEDIUM_KOTLIN_VIDEO_TERMS = {
    "jetpack compose", "compose", "gradle", "viewmodel", "stateflow",
    "androidx", "ksp", "koin", "hilt", "room", "leakcanary",
}

LOW_RELEVANCE_VIDEO_TERMS = {
    "policy", "play console", "requirements", "content ratings",
    "financial services", "random and anonymous", "behavioral interview",
    "interview", "student to", "gde ", "future of android",
}


def _source_by_id(sources_config: dict) -> dict:
    return {s["id"]: s for s in sources_config.get("sources", [])}


def _matched_terms(text: str, terms: set) -> list:
    return sorted(term for term in terms if term in text)


def video_kotlin_relevance(article: dict, source: dict) -> tuple[int, str]:
    """Return a 1-10 Kotlin relevance score and a compact reason string."""
    base = int(source.get("kotlin_relevance", 5))
    text = (
        f"{article.get('title', '')} "
        f"{article.get('excerpt', '')} "
        f"{article.get('summary', '')} "
        f"{' '.join(article.get('topics', []) or [])}"
    ).lower()

    strong = _matched_terms(text, STRONG_KOTLIN_VIDEO_TERMS)
    medium = _matched_terms(text, MEDIUM_KOTLIN_VIDEO_TERMS)
    weak = _matched_terms(text, LOW_RELEVANCE_VIDEO_TERMS)

    score = base
    if strong:
        score += 3
    if medium:
        score += 2
    if weak:
        score -= 2
    if "/shorts/" in article.get("url", ""):
        score -= 1

    score = max(1, min(10, score))

    reasons = [f"channel {base}"]
    if strong:
        reasons.append("strong: " + ", ".join(strong[:3]))
    if medium:
        reasons.append("medium: " + ", ".join(medium[:3]))
    if weak:
        reasons.append("penalty: " + ", ".join(weak[:2]))
    if "/shorts/" in article.get("url", ""):
        reasons.append("short")

    return score, "; ".join(reasons)


def video_min_score(source: dict) -> int:
    video_cfg = source.get("video") or {}
    if "min_kotlin_score" in video_cfg:
        return int(video_cfg["min_kotlin_score"])
    return 6 if int(source.get("kotlin_relevance", 5)) >= 9 else 8


def apply_video_render_filters(articles: list, sources_config: dict) -> tuple[list, list]:
    """Filter/cap video articles for rendering without mutating article state."""
    sources = _source_by_id(sources_config)
    kept_non_video = []
    video_candidates = []
    dropped = []

    for article in articles:
        source = sources.get(article.get("source_id"), {})
        if source.get("type") not in {"youtube", "video"}:
            kept_non_video.append(article)
            continue

        score, reason = video_kotlin_relevance(article, source)
        article = dict(article)
        article["video_kotlin_score"] = score
        article["video_kotlin_reason"] = reason
        min_score = video_min_score(source)
        if score < min_score:
            dropped.append((article, f"kotlin-score {score} < {min_score}: {reason}"))
        else:
            video_candidates.append(article)

    by_source = defaultdict(list)
    for article in video_candidates:
        by_source[article.get("source_id")].append(article)

    kept_videos = []
    for sid, source_articles in by_source.items():
        source = sources.get(sid, {})
        max_per_edition = (source.get("video") or {}).get("max_per_edition")
        ranked = sorted(
            source_articles,
            key=lambda a: (
                a.get("video_kotlin_score", 0),
                a.get("placement_score", 0.0),
                a.get("date", ""),
                a.get("title", ""),
            ),
            reverse=True,
        )
        if max_per_edition is None:
            kept_videos.extend(ranked)
            continue
        max_count = int(max_per_edition)
        kept_videos.extend(ranked[:max_count])
        for article in ranked[max_count:]:
            dropped.append((article, f"source cap {max_count}"))

    kept_video_ids = {a["id"] for a in kept_videos}
    ordered_kept_videos = [a for a in video_candidates if a["id"] in kept_video_ids]
    return kept_non_video + ordered_kept_videos, dropped
