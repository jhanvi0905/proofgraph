"""Page geometry from PDF coordinates (D12, item 3). Shared by the parser and the checker.

Only pdfplumber's own words and their boxes are used, never this project's extracted text, so the
checker stays independent of the parser: both ask the same question of the page's coordinates.

A page is either `single` (whole-page reading order) or `columns` with one or more gutters (x
positions). A gutter is a vertical band of whitespace between text masses: few rows put a word in
it, and each side holds real column text (enough rows, lines that mostly fill the column). A page
whose candidate split fails that test is `single`: a table's label and amount are read on one line,
never torn into two columns. A page with two printed pages side by side has three gutters (four
columns). Two-column pages keep the gutter the parser has always used (`percentile_gutter`), so
existing reading order does not move.
"""

from __future__ import annotations

from statistics import median

from proofgraph.schema import PageLayout

# Measured on HO 00 03 04 91: gaps between words are 0-7pt, column gutters 20pt+.
FULL_WIDTH_MAX_GAP = 12.0
_MIN_GUTTER = 8.0  # narrower whitespace is a gap between words or a hanging number's indent
_MIN_FILL = 0.6  # median line width over column width: wrapped text fills its column, a table cell does not


def without_stamps(page):
    """The page without watermark and stamp characters: any glyph more than three times the page's typical
    text size ("SAMPLE", "SPECIMEN", "COPY" printed across the page). Body text, headings and footers are far
    below that. Without this, stamp letters land inside sentences and no verbatim quote of them can verify."""
    sizes = sorted(c["size"] for c in page.chars if c.get("text", "").strip())
    if not sizes:
        return page
    limit = 3 * sizes[len(sizes) // 2]
    return page.filter(lambda o: o.get("object_type") != "char" or o.get("size", 0) <= limit)


def page_words(page, extra_attrs: list[str] | None = None) -> list[dict]:
    """The words of a page, stamps dropped, as the parser and the checker both read them."""
    return without_stamps(page).extract_words(x_tolerance=1.5, y_tolerance=2, keep_blank_chars=False,
                                              extra_attrs=extra_attrs or [])


def rows(words: list[dict], tol: float = 2.0) -> list[list[dict]]:
    out: list[list[dict]] = []
    for w in sorted(words, key=lambda w: (round(w["top"]), w["x0"])):
        if out and abs(out[-1][0]["top"] - w["top"]) <= tol:
            out[-1].append(w)
        else:
            out.append([w])
    return [sorted(r, key=lambda w: w["x0"]) for r in out]


def percentile_gutter(words: list[dict], width: float) -> float | None:
    """Midway between the left column's right margin and the right column's left margin, or None if they overlap.

    Margins are measured from the page's own words (95th percentile of left-column right edges, 5th
    percentile of right-column left edges), so hanging list numbers ("1." set into the gutter) do not move it.
    """
    mid = width / 2
    lefts = sorted(w["x1"] for w in words if w["x1"] < mid + 20 and w["x0"] < mid - 40)
    rights = sorted(w["x0"] for w in words if w["x0"] > mid - 20 and w["x1"] > mid + 40)
    if not lefts or not rights:
        return None
    left_edge = lefts[int(len(lefts) * 0.95)]
    right_edge = rights[int(len(rights) * 0.05)]
    return (left_edge + right_edge) / 2 if left_edge < right_edge else None


def _whitespace_runs(rws: list[list[dict]], width: float) -> list[tuple[float, float]]:
    """x bands, at least _MIN_GUTTER wide, that at most a few rows put a word in."""
    n = int(width) + 2
    occ = [0] * n
    for r in rws:
        cov: set[int] = set()
        for w in r:
            cov.update(range(max(0, int(w["x0"])), min(n - 1, int(w["x1"])) + 1))
        for x in cov:
            occ[x] += 1
    allow = max(2, 0.04 * len(rws))
    xs0 = sorted(w["x0"] for r in rws for w in r)
    xs1 = sorted(w["x1"] for r in rws for w in r)
    lo, hi = int(xs0[int(len(xs0) * 0.05)]), int(xs1[int(len(xs1) * 0.95)])
    runs: list[list[int]] = []
    for x in range(lo + 1, hi):
        if occ[x] <= allow:
            if runs and runs[-1][1] == x - 1:
                runs[-1][1] = x
            else:
                runs.append([x, x])
    return [(float(a), float(b)) for a, b in runs if b - a >= _MIN_GUTTER]


def _columns_hold_text(rws: list[list[dict]], gutters: tuple[float, ...]) -> bool:
    """Each column between gutters holds column text: enough rows, and lines that mostly fill it."""
    need = max(5, 0.15 * len(rws))
    edges = (float("-inf"), *gutters, float("inf"))
    for a, b in zip(edges, edges[1:]):
        segs = []
        for r in rws:
            if any(w["x0"] < g < w["x1"] for w in r for g in gutters):
                continue  # full width
            seg = [w for w in r if w["x0"] >= a and w["x1"] <= b]
            if seg:
                segs.append((min(w["x0"] for w in seg), max(w["x1"] for w in seg)))
        if len(segs) < need:
            return False
        x0s = sorted(s[0] for s in segs)
        x1s = sorted(s[1] for s in segs)
        left = x0s[int(len(x0s) * 0.05)]
        right = x1s[int(len(x1s) * 0.95)]
        if right - left <= 0 or median((s[1] - s[0]) / (right - left) for s in segs) < _MIN_FILL:
            return False
    return True


def page_layout(words: list[dict], width: float) -> PageLayout:
    """Columns from the page's coordinates. Single when no split holds column text on every side."""
    rws = rows(words)
    if not rws:
        return PageLayout(kind="single", gutters=())
    g0 = percentile_gutter(words, width)
    gutters: list[float] = []
    for a, b in _whitespace_runs(rws, width):
        left = sum(1 for r in rws if any(w["x1"] <= a for w in r))
        right = sum(1 for r in rws if any(w["x0"] >= b for w in r))
        if min(left, right) < max(5, 0.15 * len(rws)):
            continue  # a margin, a footer box or a sidebar, not a column break
        gutters.append(g0 if g0 is not None and a <= g0 <= b else (a + b) / 2)
    if not gutters and g0 is not None:
        gutters = [g0]  # headings cross the gutter on every row band: the margins still separate
    if gutters and _columns_hold_text(rws, tuple(gutters)):
        return PageLayout(kind="columns", gutters=tuple(sorted(gutters)))
    return PageLayout(kind="single", gutters=())


def column_of(layout: PageLayout, x0: float, x1: float) -> int:
    """The column a box sits in: its index, or -1 when it crosses a gutter (a full-width line)."""
    if any(x0 < g < x1 for g in layout.gutters):
        return -1
    return sum(1 for g in layout.gutters if x0 >= g)
