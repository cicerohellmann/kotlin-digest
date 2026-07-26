"""Crossword layout — curate words, auto-fit the grid.

Puzzles are authored as a list of {answer, clue} in crosswords/crosswords.yml.
This module greedily packs the answers into a blocked grid: the first word is
laid down, then each subsequent word is placed so it CROSSES an already-placed
letter (perpendicular), validated so it never collides or forms accidental
adjacent words. Cells with no letter are blocks. The result is numbered like a
real crossword and returned as a plain dict ready to inject as JS.

Deterministic: same word order in the YAML → same grid. No external calls.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).parent.parent.parent
CROSSWORDS_FILE = ROOT / "crosswords" / "crosswords.yml"


def _can_place(grid: dict, word: str, sr: int, sc: int, down: bool) -> bool:
    """True if `word` fits starting at (sr,sc), crossing >=1 existing letter and
    never colliding or brushing another word alongside a non-crossing cell."""
    dr, dc = (1, 0) if down else (0, 1)
    pr, pc = (0, 1) if down else (1, 0)  # perpendicular
    # The cells immediately before the start and after the end must be empty,
    # else this word would run straight into another.
    if (sr - dr, sc - dc) in grid:
        return False
    if (sr + dr * len(word), sc + dc * len(word)) in grid:
        return False
    crossed = False
    for i, ch in enumerate(word):
        r, c = sr + dr * i, sc + dc * i
        if (r, c) in grid:
            if grid[(r, c)] != ch:
                return False
            crossed = True  # legit crossing at a matching letter
        else:
            # A non-crossing cell must not sit directly beside another word.
            if (r + pr, c + pc) in grid or (r - pr, c - pc) in grid:
                return False
    return crossed


def _place(words: list[tuple[str, str]]) -> list[dict]:
    """Greedy placement. Returns entries: {answer, clue, row, col, down}."""
    grid: dict[tuple[int, int], str] = {}
    entries: list[dict] = []

    first_ans, first_clue = words[0]
    for i, ch in enumerate(first_ans):
        grid[(0, i)] = ch
    entries.append({"answer": first_ans, "clue": first_clue, "row": 0, "col": 0, "down": False})

    for ans, clue in words[1:]:
        # Gather every legal placement, then pick the most compact one (smallest
        # resulting bounding box) so the grid stays dense instead of sprawling.
        candidates = []
        for i, ch in enumerate(ans):
            for (r, c), gch in grid.items():
                if gch != ch:
                    continue
                for sr, sc, down in ((r - i, c, True), (r, c - i, False)):
                    if _can_place(grid, ans, sr, sc, down):
                        candidates.append((sr, sc, down))
        placed = None
        if candidates:
            rs = [r for r, _ in grid]
            cs = [c for _, c in grid]
            r0, r1, c0, c1 = min(rs), max(rs), min(cs), max(cs)

            def area(cand):
                sr, sc, down = cand
                er = sr + (len(ans) - 1 if down else 0)
                ec = sc + (0 if down else len(ans) - 1)
                h = max(r1, sr, er) - min(r0, sr, er)
                w = max(c1, sc, ec) - min(c0, sc, ec)
                return (h * w, h + w)

            placed = min(candidates, key=area)
        if not placed:
            # Couldn't cross anything — drop below the grid, disconnected.
            max_r = max((r for r, _ in grid), default=0)
            placed = (max_r + 2, 0, False)
        sr, sc, down = placed
        dr, dc = (1, 0) if down else (0, 1)
        for i, ch in enumerate(ans):
            grid[(sr + dr * i, sc + dc * i)] = ch
        entries.append({"answer": ans, "clue": clue, "row": sr, "col": sc, "down": down})

    return _normalize(grid, entries)


def _normalize(grid: dict, entries: list[dict]) -> dict:
    """Shift to origin, size the board, number the entries like a crossword."""
    min_r = min(r for r, _ in grid)
    min_c = min(c for _, c in grid)
    grid = {(r - min_r, c - min_c): ch for (r, c), ch in grid.items()}
    for e in entries:
        e["row"] -= min_r
        e["col"] -= min_c
    rows = max(r for r, _ in grid) + 1
    cols = max(c for _, c in grid) + 1

    # A cell is numbered if it starts an across run (no letter to its left, a
    # letter to its right) or a down run (no letter above, a letter below).
    number_at: dict[tuple[int, int], int] = {}
    n = 0
    for r in range(rows):
        for c in range(cols):
            if (r, c) not in grid:
                continue
            starts_across = (r, c - 1) not in grid and (r, c + 1) in grid
            starts_down = (r - 1, c) not in grid and (r + 1, c) in grid
            if starts_across or starts_down:
                n += 1
                number_at[(r, c)] = n

    across, down = [], []
    for e in entries:
        num = number_at[(e["row"], e["col"])]
        item = {"num": num, "row": e["row"], "col": e["col"],
                "answer": e["answer"], "clue": e["clue"], "len": len(e["answer"])}
        (down if e["down"] else across).append(item)
    across.sort(key=lambda x: x["num"])
    down.sort(key=lambda x: x["num"])

    # Solution letters as a rows×cols array; None = block.
    solution = [[grid.get((r, c)) for c in range(cols)] for r in range(rows)]
    numbers = [[number_at.get((r, c)) for c in range(cols)] for r in range(rows)]
    return {"rows": rows, "cols": cols, "solution": solution,
            "numbers": numbers, "across": across, "down": down}


def build_puzzle(puzzle: dict) -> dict:
    words = [(w["answer"].upper(), w["clue"]) for w in puzzle["words"]]
    laid = _place(words)
    placed_answers = {a["answer"] for a in laid["across"]} | {d["answer"] for d in laid["down"]}
    dropped = [w for w, _ in words if w not in placed_answers]
    return {"id": puzzle["id"], "title": puzzle.get("title", ""),
            "theme": puzzle.get("theme", ""), "dropped": dropped, **laid}


def load_puzzles(path: Path = CROSSWORDS_FILE) -> list[dict]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [build_puzzle(p) for p in data.get("puzzles", [])]


def _ascii(puz: dict) -> str:
    out = []
    for row in puz["solution"]:
        out.append("".join(ch if ch else "#" for ch in row))
    return "\n".join(out)


if __name__ == "__main__":
    puzzles = load_puzzles()
    for p in puzzles:
        print(f"# {p['id']}  {p['rows']}x{p['cols']}  "
              f"across={len(p['across'])} down={len(p['down'])} "
              f"dropped={p['dropped']}", file=sys.stderr)
        print(_ascii(p), file=sys.stderr)
        print(file=sys.stderr)
    # JSON of the first puzzle to stdout (for embedding / inspection).
    print(json.dumps(puzzles[0], ensure_ascii=False, indent=2))
