"""Scorer v0: run versus gold, per-pool and per-group rows, Wilson intervals. No network, no models."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from proofgraph.review.models import Review
from proofgraph.review.packs import Gold

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("report_review", ROOT / "scripts" / "report_review.py")
rr = importlib.util.module_from_spec(_spec)
sys.modules["report_review"] = rr
_spec.loader.exec_module(rr)


def _gold(case="C1", pool="suite", split="dev", dataset="DS-A", conflict=False) -> Gold:
    rel = {"weakener_type": None, "file": "a.pdf", "page": 1, "box_origin": "authored", "origin": "curated"}
    relations = [
        rel | {"part": "P1", "relation": "supports", "quote": "the fee is flat", "quote_pdf": "the fee is flat",
               "boxes": [[100, 200, 500, 220]]},
        rel | {"part": "P2", "relation": "weakens", "weakener_type": "condition", "page": 2,
               "quote": "only if approved by the board", "quote_pdf": "only if approved by the board",
               "boxes": [[100, 300, 600, 340]]},
    ]
    if conflict:
        relations.append(rel | {"part": "P1", "relation": "contradicts", "quote": "fee waived entirely",
                                "quote_pdf": "fee waived entirely", "boxes": [[100, 400, 500, 420]]})
    return Gold.model_validate({
        "case": case, "pool": pool, "source_dataset": dataset, "split": split, "claim": "alpha beta",
        "reference": {"verdict": "x", "origin": "curated"},
        "parts": [
            {"id": "P1", "text": "alpha", "span": [0, 5], "status": "contradicted" if conflict else "supported",
             "conflict": conflict, "origin": "curated"},
            {"id": "P2", "text": "beta", "span": [6, 10], "status": "weakened", "origin": "curated"},
        ],
        "relations": relations,
    })


def _run_from_gold(gold: Gold, kind="text_layer") -> Review:
    pages = sorted({r.page for r in gold.relations})
    cards = [
        {"id": f"c{i}", "part": r.part, "relation": r.relation, "weakener_type": r.weakener_type,
         "quote": r.quote_pdf, "doc": "D1", "page": r.page, "boxes": r.boxes or [], "box_status": "pinned",
         "why": "w", "check": "agrees"}
        for i, r in enumerate(gold.relations)
    ]
    parts = [
        {"id": p.id, "text": p.text, "span": list(p.span or (0, 1)), "status": p.status, "conflict": p.conflict,
         "card_ids": [c["id"] for c in cards if c["part"] == p.id]}
        for p in gold.parts
    ]
    return Review.model_validate({
        "version": "review-1", "review_id": "r", "claim": {"text": gold.claim, "origin": "typed"},
        "status": "supported", "run": {"mode": "replayed", "recorded_at": "t", "models": {}, "cost_usd": 0},
        "docs": [{"id": "D1", "name": "a.pdf",
                  "pages": [{"n": n, "kind": kind, "png": "p", "w": 1, "h": 1, "readable": True} for n in pages]}],
        "parts": parts, "cards": cards,
    })


def _mutate(review: Review, fn) -> Review:
    raw = review.model_dump(mode="json")
    fn(raw)
    return Review.model_validate(raw)


def _line(case: str, review: Review) -> str:
    return json.dumps({"case": case, "review": review.model_dump(mode="json")}) + "\n"


def test_run_equal_to_gold_scores_one_everywhere():
    gold = _gold()
    t = rr.score_case(_run_from_gold(gold), gold)
    for key in ("recall:supports", "recall:weakens", "precision:supports", "precision:weakens", "part_status",
                "pin_rate", "hit50:text_layer", "centre:text_layer"):
        assert key in t, key
    for key, (k, n) in t.items():
        assert n > 0 and k == n, f"{key}: {k}/{n}"


def test_shifted_box_fails_hit50_and_nothing_else():
    gold = _gold()
    base = rr.score_case(_run_from_gold(gold), gold)

    def shift(raw):
        raw["cards"][0]["boxes"] = [[250, 200, 650, 220]]  # IoU 250/550 = 0.45, centre 450 still inside gold

    t = rr.score_case(_mutate(_run_from_gold(gold), shift), gold)
    assert t["hit50:text_layer"] == (base["hit50:text_layer"][0] - 1, base["hit50:text_layer"][1])
    for key in base:
        if key != "hit50:text_layer":
            assert t[key] == base[key], key


def test_box_with_centre_outside_gold_also_fails_centre_in_box():
    gold = _gold()
    base = rr.score_case(_run_from_gold(gold), gold)

    def shift(raw):
        raw["cards"][0]["boxes"] = [[600, 200, 1000, 220]]

    t = rr.score_case(_mutate(_run_from_gold(gold), shift), gold)
    assert t["centre:text_layer"][0] == base["centre:text_layer"][0] - 1


def test_wrong_relation_hits_only_the_two_relations_involved():
    gold = _gold()
    base = rr.score_case(_run_from_gold(gold), gold)

    def wrong(raw):
        raw["cards"][1]["relation"] = "contradicts"  # gold says weakens
        raw["cards"][1]["weakener_type"] = None

    t = rr.score_case(_mutate(_run_from_gold(gold), wrong), gold)
    assert t["recall:weakens"] == (0, 1)
    assert t["precision:contradicts"] == (0, 1)
    assert t.get("precision:weakens", (0, 0)) == (0, 0)
    assert t["recall:supports"] == base["recall:supports"]
    assert t["precision:supports"] == base["precision:supports"]


@pytest.mark.parametrize(
    ("run_status", "run_conflict", "passes"),
    [("contradicted", True, True), ("contradicted", False, False), ("supported", False, False)],
)
def test_conflict_gold_part_passes_only_with_contradicted_and_conflict(run_status, run_conflict, passes):
    gold = _gold(conflict=True)

    def edit(raw):
        raw["parts"][0]["status"] = run_status
        raw["parts"][0]["conflict"] = run_conflict

    t = rr.score_case(_mutate(_run_from_gold(gold), edit), gold)
    assert t["part_status"] == (2 if passes else 1, 2)
    assert t["conflict_pass"] == (1 if passes else 0, 1)


@pytest.mark.parametrize(
    ("k", "n", "lo", "hi"),
    [(5, 5, 0.566, 1.0), (0, 5, 0.0, 0.434), (1, 2, 0.095, 0.905), (10, 10, 0.722, 1.0)],
)
def test_wilson_interval_matches_hand_values(k, n, lo, hi):
    got_lo, got_hi = rr.wilson(k, n)
    assert got_lo == pytest.approx(lo, abs=0.001)
    assert got_hi == pytest.approx(hi, abs=0.001)


def test_wilson_with_no_denominator_is_not_available():
    assert rr.wilson(0, 0) is None
    assert rr.fmt_proportion(0, 0) == "n/a (0/0)"


def test_pool_and_group_rows_are_separate_and_pooled_row_kept():
    suite = _gold("S1", pool="suite", split="dev", dataset="DS-A")
    pack = _gold("frt-01", pool="pack", split="held_out", dataset="Packs")
    pack_bad = _mutate(_run_from_gold(pack), lambda raw: raw["parts"][0].update(status="not_found"))
    rows = rr.build_rows({"S1": _run_from_gold(suite), "frt-01": pack_bad}, [suite, pack])
    assert {"ALL", "pool=suite", "pool=pack", "split=dev", "split=held_out",
            "dataset=DS-A", "dataset=Packs"} <= set(rows)
    assert rows["pool=suite"]["part_status"] == (2, 2)
    assert rows["pool=pack"]["part_status"] == (1, 2)
    assert rows["ALL"]["part_status"] == (3, 4)


def test_missing_case_is_a_miss_not_dropped():
    gold = _gold()
    t = rr.score_case(None, gold)
    assert t["part_status"] == (0, 2)
    assert t["recall:supports"] == (0, 1)
    assert t["recall:weakens"] == (0, 1)
    assert t["pin_rate"] == (0, 2)
    rows = rr.build_rows({}, [gold])
    assert rows["ALL"]["part_status"] == (0, 2)
    assert "C1" in rr.render(rows, missing=["C1"], extra=[], title="t")


def test_empty_run_for_a_case_is_a_miss_too():
    gold = _gold()

    def drop(raw):
        raw["cards"] = []
        for p in raw["parts"]:
            p["card_ids"] = []

    t = rr.score_case(_mutate(_run_from_gold(gold), drop), gold)
    assert t["recall:supports"] == (0, 1)
    assert t["pin_rate"] == (0, 2)


def test_report_states_denominator_beside_every_percentage():
    gold = _gold()
    text = rr.render(rr.build_rows({"C1": _run_from_gold(gold)}, [gold]), missing=[], extra=[], title="t")
    pct_lines = [ln for ln in text.splitlines() if "%" in ln and ln.lstrip().startswith("-")]
    assert pct_lines
    for ln in pct_lines:
        assert "100.0% (2/2)" in ln or "(" in ln and "/" in ln, ln
    assert "95% CI" in text


def test_small_n_is_flagged_wide():
    gold = _gold()
    text = rr.render(rr.build_rows({"C1": _run_from_gold(gold)}, [gold]), missing=[], extra=[], title="t")
    assert "wide" in text


def test_word_overlap_threshold():
    assert rr.word_overlap("the fee is flat", "The fee is flat.") == 1.0
    assert rr.word_overlap("a b c d", "a b x y") == 0.5
    assert rr.word_overlap("a b c d", "a x y z") < 0.5


def test_page_mismatch_is_not_a_match():
    gold = _gold()

    def wrong_page(raw):
        raw["docs"][0]["pages"].append({"n": 9, "kind": "text_layer", "png": "p", "w": 1, "h": 1, "readable": True})
        raw["cards"][0]["page"] = 9

    t = rr.score_case(_mutate(_run_from_gold(gold), wrong_page), gold)
    assert t["recall:supports"] == (0, 1)
    assert t["precision:supports"] == (0, 1)


def test_load_runs_reads_case_and_review_per_line(tmp_path):
    f = tmp_path / "review-t-2026-11-01.jsonl"
    f.write_text(_line("C1", _run_from_gold(_gold())))
    assert set(rr.load_runs(f)) == {"C1"}


def test_main_exits_nonzero_when_no_run_files(tmp_path, capsys):
    code = rr.main(["--runs-glob", str(tmp_path / "runs" / "review-*.jsonl"), "--out", str(tmp_path / "r.md")])
    assert code != 0
    assert "no run files" in capsys.readouterr().err.lower()
    assert not (tmp_path / "r.md").exists()


def test_main_writes_report_and_stdout(tmp_path, capsys):
    gold = _gold()
    gdir = tmp_path / "gold"
    gdir.mkdir()
    (gdir / "C1.json").write_text(gold.model_dump_json())
    run = tmp_path / "review-t-2026-11-01.jsonl"
    run.write_text(_line("C1", _run_from_gold(gold)))
    out = tmp_path / "out" / "report.md"
    assert rr.main(["--runs-glob", str(run), "--gold", str(gdir), "--out", str(out)]) == 0
    assert "(2/2)" in out.read_text()
    assert "(2/2)" in capsys.readouterr().out


# ---- R-12b: parts are aligned by claim span (or text) before scoring; ids play no role ----
# The old exact-id expectations are replaced by span-based ones: _run_from_gold now copies each gold
# part's span into the run part, and tests that need a different id or span say so explicitly.

def _rename(review: Review, mapping: dict[str, str], reverse_order: bool = True) -> Review:
    def edit(raw):
        for p in raw["parts"]:
            p["id"] = mapping[p["id"]]
        for c in raw["cards"]:
            c["part"] = mapping[c["part"]]
        if reverse_order:
            raw["parts"].reverse()

    return _mutate(review, edit)


def _alignment_of(review, gold):
    a = rr.align(review, gold)
    return {m.gold: (m.run, m.overlap) for m in a.matches}, a


def test_renamed_lowercase_ids_and_different_order_still_score_one_everywhere():
    gold = _gold()
    run = _rename(_run_from_gold(gold), {"P1": "p2", "P2": "p1"})
    t = rr.score_case(run, gold)
    assert t["alignment"] == (2, 2)
    for key in ("recall:supports", "recall:weakens", "precision:supports", "precision:weakens", "part_status",
                "pin_rate", "hit50:text_layer", "centre:text_layer"):
        assert key in t, key
    for key, (k, n) in t.items():
        assert n > 0 and k == n, f"{key}: {k}/{n}"


def test_finer_split_is_merged_worst_status_wins_and_cards_are_unioned():
    gold = _gold()

    def split(raw):
        p2 = raw["parts"][1]
        a = p2 | {"id": "x1", "text": "be", "span": [6, 8], "status": "weakened", "card_ids": []}
        b = p2 | {"id": "x2", "text": "ta", "span": [8, 10], "status": "supported"}  # card sits here
        raw["parts"][1:] = [a, b]
        raw["cards"][1]["part"] = "x2"

    run = _mutate(_run_from_gold(gold), split)
    got, _ = _alignment_of(run, gold)
    assert got["P2"] == (("x1", "x2"), 1.0)
    t = rr.score_case(run, gold)
    assert t["part_status"] == (2, 2)  # weakened (worst of weakened and supported) equals gold
    assert t["recall:weakens"] == (1, 1) and t["precision:weakens"] == (1, 1)
    assert t["alignment"] == (2, 2)

    def both_supported(raw):
        split(raw)
        raw["parts"][1]["status"] = "supported"

    t2 = rr.score_case(_mutate(_run_from_gold(gold), both_supported), gold)
    assert t2["part_status"] == (1, 2)  # both pieces supported, gold says weakened


def test_coarser_run_part_scores_best_overlap_gold_part_and_lists_the_other_as_a_miss():
    gold = _gold()

    def coarse(raw):
        merged = raw["parts"][0] | {"id": "only", "text": "alpha beta", "span": [0, 10],
                                    "card_ids": [c["id"] for c in raw["cards"]]}
        raw["parts"] = [merged]
        for c in raw["cards"]:
            c["part"] = "only"

    run = _mutate(_run_from_gold(gold), coarse)
    got, a = _alignment_of(run, gold)
    assert got == {"P1": (("only",), 1.0)}
    assert a.gold_unmatched == ["P2"] and a.run_unmatched == []
    t = rr.score_case(run, gold)
    assert t["alignment"] == (1, 2)
    assert t["part_status"] == (1, 2)
    assert t["recall:supports"] == (1, 1)
    assert t["recall:weakens"] == (0, 1)  # the other gold part's relation is a miss


def test_gold_part_without_span_aligns_by_normalised_text_similarity():
    raw = _gold().model_dump(mode="json")
    raw["parts"][0] |= {"text": "first  thing", "span": None}
    gold = Gold.model_validate(raw)

    def text(r):
        r["parts"][0]["text"] = " FIRST thing "
        r["parts"][0]["span"] = [40, 52]

    run = _mutate(_run_from_gold(gold), text)
    got, _ = _alignment_of(run, gold)
    assert got["P1"][0] == ("P1",)
    assert rr.score_case(run, gold)["alignment"] == (2, 2)

    def other(r):
        r["parts"][0]["text"] = "something else entirely"
        r["parts"][0]["span"] = [40, 52]

    assert rr.score_case(_mutate(_run_from_gold(gold), other), gold)["alignment"] == (1, 2)


def test_no_overlap_leaves_every_gold_part_unmatched_and_nothing_divides_by_zero():
    gold = _gold()

    def far(raw):
        for p, start in zip(raw["parts"], (100, 200)):
            p["span"] = [start, start + 5]

    far_run = _mutate(_run_from_gold(gold), far)
    empty_run = _mutate(_run_from_gold(gold), lambda r: r.update(parts=[], cards=[]))
    for run in (far_run, empty_run):
        t = rr.score_case(run, gold)
        assert t["alignment"] == (0, 2)
        assert t["part_status"] == (0, 2)
        assert t["recall:supports"] == (0, 1) and t["recall:weakens"] == (0, 1)
        assert t["pin_rate"] == (0, 2)
        text = rr.render(rr.build_rows({"C1": run}, [gold]), missing=[], extra=[], title="t")
        assert "alignment" in text
    assert rr.align(far_run, gold).run_unmatched == ["P1", "P2"]


def test_alignment_table_is_in_the_report_and_deterministic():
    gold = _gold()
    run = _rename(_run_from_gold(gold), {"P1": "p1", "P2": "p2"}, reverse_order=False)
    one = rr.alignment_report({"C1": run}, [gold])
    assert one == rr.alignment_report({"C1": run}, [gold])
    assert "C1" in one and "P1" in one and "p1" in one and "1.00" in one
    text = rr.render(rr.build_rows({"C1": run}, [gold]), missing=[], extra=[], title="t", alignment=one)
    assert one in text
    assert "alignment" in text.lower() and "(2/2)" in text


def test_right_ids_with_wrong_spans_do_not_match():
    gold = _gold()

    def wrong(raw):
        raw["parts"][0]["span"] = [50, 55]
        raw["parts"][1]["span"] = [60, 64]

    t = rr.score_case(_mutate(_run_from_gold(gold), wrong), gold)
    assert t["alignment"] == (0, 2)
    assert t["part_status"] == (0, 2)
    assert t["recall:supports"] == (0, 1)
