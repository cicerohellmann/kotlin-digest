from datetime import date


def filter_articles(articles: list, start: date, end: date) -> list:
    """Keep articles whose date falls within [start, end] inclusive.

    Articles flagged `dead` (e.g. deleted/removed at the source) are excluded —
    the record stays in state for the audit trail but never renders.
    """
    start_s = start.isoformat()
    end_s = end.isoformat()
    return [
        a for a in articles
        if a.get("date") and start_s <= a["date"] <= end_s
        and not a.get("dead")
    ]


def score_articles(articles: list, scores: dict) -> list:
    """Add placement_score = sum of bible scores for each matched topic."""
    result = []
    for a in articles:
        a = dict(a)
        a["placement_score"] = sum(scores.get(t, 0.0) for t in a.get("topics", []))
        result.append(a)
    return result


def assign_col(rank: int) -> str:
    if rank == 1:
        return "c12"
    if rank <= 3:
        return "c8"
    if rank <= 6:
        return "c6"
    return "c4"


def cluster_articles(articles: list, clusters: list) -> list:
    """
    Group articles into chapters by primary cluster membership.
    An article's primary cluster is the first cluster whose topic list
    intersects the article's topics. Unclustered articles are dropped.
    Returns chapters sorted by descending aggregate placement_score.
    """
    topic_to_cluster = {}
    for cluster in clusters:
        for tid in cluster.get("topics", []):
            if tid not in topic_to_cluster:
                topic_to_cluster[tid] = cluster["id"]

    cluster_map = {c["id"]: c for c in clusters}
    buckets = {c["id"]: [] for c in clusters}

    for article in articles:
        assigned = None
        for tid in article.get("topics", []):
            if tid in topic_to_cluster:
                assigned = topic_to_cluster[tid]
                break
        if assigned:
            buckets[assigned].append(article)

    chapters = []
    for cid, arts in buckets.items():
        if not arts:
            continue
        arts_sorted = sorted(arts, key=lambda a: a["placement_score"], reverse=True)
        for rank, art in enumerate(arts_sorted, start=1):
            art = dict(art)
            art["col"] = assign_col(rank)
            arts_sorted[rank - 1] = art
        chapter_score = sum(a["placement_score"] for a in arts_sorted)
        chapters.append({
            "id": cid,
            "label": cluster_map[cid]["label"],
            "score": chapter_score,
            "articles": arts_sorted,
        })

    return sorted(chapters, key=lambda ch: ch["score"], reverse=True)
