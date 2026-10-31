"""R-06: snap turns a returned quote into exact line rectangles on a text-layer page."""

from __future__ import annotations

import os
from functools import cache
from pathlib import Path

import pytest
from pydantic import TypeAdapter

from proofgraph.review.ingest import Word, ingest
from proofgraph.review.models import Box
from proofgraph.review.packs import load_gold
from proofgraph.review.snap import PAD, snap

ROOT = Path(__file__).resolve().parents[1]
_BOX = TypeAdapter(Box)


def _padded(x0: int, y0: int, x1: int, y1: int) -> list[int]:
    return [x0 - PAD, y0 - PAD, x1 + PAD, y1 + PAD]


def _line(texts: list[str], y: int, x: int = 100, h: int = 10, w: int = 40) -> list[Word]:
    """One printed line: words laid left to right with a 5 unit gap."""
    words = []
    for text in texts:
        words.append(Word(text, (x, y, x + w, y + h)))
        x += w + 5
    return words


def _page(*lines: list[str]) -> list[Word]:
    words: list[Word] = []
    for i, texts in enumerate(lines):
        words += _line(texts, y=100 + i * 20)
    return words


# --- the honest answers -------------------------------------------------------------------


def test_quote_not_on_page_is_unpinned_with_no_box() -> None:
    words = _page(["Payment", "is", "due", "in", "thirty", "days"])
    result = snap("The carrier shall pay a detention fee", words)
    assert result.status == "unpinned"
    assert result.boxes == []


def test_empty_quote_or_empty_page_is_unpinned() -> None:
    assert snap("", _page(["a", "b"])).status == "unpinned"
    assert snap("anything at all", []).status == "unpinned"


# --- exact match, one rule at a time ------------------------------------------------------


def test_single_line_quote_gives_one_rectangle() -> None:
    words = _page(["Detention", "begins", "after", "two", "hours", "free", "time"])
    result = snap("begins after two hours", words)
    assert result.status == "pinned"
    assert result.boxes == [_padded(145, 100, 320, 110)]


def test_case_and_punctuation_do_not_matter() -> None:
    words = _page(["Net", "30,", "days;", "no", "discount."])
    assert snap("NET 30 DAYS no discount", words).status == "pinned"


def test_pipe_table_quote_snaps_with_pipes_removed() -> None:
    # The page words are cells with no pipes; the quote carries them.
    words = _page(["Total", "Current", "Liabilities", "123,391", "99,854"])
    result = snap("| Total Current Liabilities | 123,391 | 99,854 |", words)
    assert result.status == "pinned"
    assert result.boxes == [_padded(100, 100, 100 + 5 * 40 + 4 * 5, 110)]


def test_ligature_in_page_matches_plain_quote() -> None:
    words = _page(["the", "ﬁrst", "oﬃce", "opened"])
    assert snap("the first office opened", words).status == "pinned"


def test_hyphen_line_break_is_joined() -> None:
    words = _page(["the", "ship-"], ["ment", "arrived", "late"])
    result = snap("the shipment arrived late", words)
    assert result.status == "pinned"
    assert len(result.boxes) == 2


def test_match_inside_a_fused_word_trims_by_letter_share() -> None:
    # Some PDFs fuse printed words into one extracted word. The box stays inside the real
    # word boxes and is cut by the share of letters outside the match: 3 of 7 on each end.
    words = _page(["carrier", "pays", "nothing"])
    result = snap("rier pays noth", words)
    assert result.status == "pinned"
    assert result.boxes == [_padded(100 + round(40 * 3 / 7), 100, 230 - round(40 * 3 / 7), 110)]


# --- line rectangles ----------------------------------------------------------------------


def test_quote_wrapped_over_two_lines_gives_two_rectangles() -> None:
    words = _page(["No", "TONU", "shall", "be", "paid"], ["if", "cancelled", "early"])
    result = snap("paid if cancelled", words)
    assert result.status == "pinned"
    assert len(result.boxes) == 2
    first, second = result.boxes
    assert first[3] < second[1], "line rectangles must not overlap or fuse"
    assert first == _padded(100 + 4 * 45, 100, 100 + 4 * 45 + 40, 110)
    assert second == _padded(100, 120, 100 + 45 + 40, 130)


def test_boxes_are_valid_grid_ints() -> None:
    words = _page(["alpha", "beta", "gamma"], ["delta", "epsilon"])
    result = snap("beta gamma delta", words)
    for box in result.boxes:
        _BOX.validate_python(box)
        assert all(isinstance(v, int) for v in box)


# --- fuzzy window at 0.9 ------------------------------------------------------------------


def test_near_match_above_ninety_percent_pins() -> None:
    page = ["The", "carrier", "shall", "receive", "reimbursement", "within", "thirty", "days"]
    words = _page(page)
    # One dropped letter in a 49 character quote: ratio is about 0.99.
    result = snap("carrier shall receive reimbursment within thirty days", words)
    assert result.status == "pinned"
    assert len(result.boxes) == 1


def test_loose_paraphrase_below_ninety_percent_is_unpinned() -> None:
    words = _page(["The", "carrier", "shall", "receive", "reimbursement", "within", "thirty", "days"])
    assert snap("carrier gets reimbursed in a month", words).status == "unpinned"


# --- gold: real text-layer pages ----------------------------------------------------------

_HANDOFF = Path("data") / "handoff-2026-10-31" / "packs"
_PACK_DIRS = {"frt-07": "freight/frt-07-tonu-injection", "fin-08": "finance/fin-08-restatement-injection"}
MIN_SNAP_RATE = 0.95
MIN_IOU = 0.7


def _packs_root() -> Path | None:
    env = os.environ.get("PROOFGRAPH_HANDOFF")
    candidates = [Path(env) / "packs"] if env else []
    # A worktree lives at <repo>/.claude/worktrees/<name>; the data dir is in the main checkout.
    candidates += [ROOT / _HANDOFF, ROOT.parents[2] / _HANDOFF]
    return next((c for c in candidates if c.is_dir()), None)


def _bounds(rects: list[list[int]]) -> list[int]:
    """The single rectangle around all line rectangles. Gold keeps one box per page."""
    return [min(r[0] for r in rects), min(r[1] for r in rects),
            max(r[2] for r in rects), max(r[3] for r in rects)]


def _iou(a: list[list[int]], b: list[list[int]]) -> float:
    if not a or not b:
        return 0.0
    (ax0, ay0, ax1, ay1), (bx0, by0, bx1, by1) = _bounds(a), _bounds(b)
    inter = max(0, min(ax1, bx1) - max(ax0, bx0)) * max(0, min(ay1, by1) - max(ay0, by0))
    union = (ax1 - ax0) * (ay1 - ay0) + (bx1 - bx0) * (by1 - by0) - inter
    return inter / union


@cache
def _ingest(path: Path):
    [doc] = ingest([path])
    assert doc.error is None, doc.error
    return doc


def _gold_cases() -> list[tuple[str, Path, object]]:
    root = _packs_root()
    if root is None:
        return []
    cases = []
    for key, rel in _PACK_DIRS.items():
        pack = root / rel
        for relation in load_gold(pack).relations:
            cases.append((key, pack / "upload" / relation.file, relation))
    return cases


@pytest.mark.skipif(_packs_root() is None, reason="handoff packs not present locally")
def test_text_layer_gold_quotes_snap_with_iou_at_least_point_seven() -> None:
    """At least 95% of text-layer gold relations on frt-07 and fin-08 snap with union IoU >= 0.7.

    Known miss (documented in the roadmap, S1-06; not in these two packs): the fin-02 par
    value row. It is excluded here because fin-02 is not part of this subset.
    """
    hits, misses = 0, []
    cases = _gold_cases()
    text_cases = []
    for key, path, relation in cases:
        page = _ingest(path).pages[relation.page - 1]
        if page.kind == "text":
            text_cases.append((key, path, relation, page))
    assert len(text_cases) >= 10, "expected the gold relations of both packs"
    for key, path, relation, page in text_cases:
        result = snap(relation.quote, page.words)
        iou = _iou(result.boxes, relation.boxes) if result.status == "pinned" else 0.0
        if iou >= MIN_IOU:
            hits += 1
        else:
            misses.append((key, path.name, relation.page, round(iou, 2), relation.quote[:50]))
    rate = hits / len(text_cases)
    print(f"snap rate {hits}/{len(text_cases)} = {rate:.3f}; misses: {misses}")
    assert rate >= MIN_SNAP_RATE, f"{hits}/{len(text_cases)} snapped; misses: {misses}"
