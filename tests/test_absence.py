"""Absence receipt: what was read, what was swept, what a human must still look at."""

import ast
from pathlib import Path

import pytest

from proofgraph.review.absence import AbsencePage, build_receipt, sweep_terms
from proofgraph.review.models import Card
from proofgraph.review.status import part_status

ROOT = Path(__file__).resolve().parents[1]

LEASE = AbsencePage("d1", 1, "This lease runs for twelve months. Rent is due on the first day of each month.")
NOTES = AbsencePage("d2", 1, "Meeting notes. The landlord agreed to repaint the hallway before March.")
CLAIM = "The tenant paid a $250 deposit to Harborview Properties."


def card(doc="d1", page=1, quote="Rent is due on the first day", relation="supports"):
    return Card(id="c", part="P1", relation=relation, quote=quote, doc=doc, page=page,
                box_status="pinned", why="w", check="not_run")


def test_absent_claim_terms_give_complete_receipt_and_not_found():
    r = build_receipt(CLAIM, [LEASE, NOTES], [])
    assert r.complete is True and r.reason is None
    assert r.pages_read == (("d1", 1), ("d2", 1))
    assert r.unread == () and r.uncited_hits == ()
    assert part_status([], receipt_complete=r.complete) == ("not_found", False)


def test_image_only_page_is_unread_and_gives_cannot_tell():
    scan = AbsencePage("d3", 4, None)
    r = build_receipt(CLAIM, [LEASE, scan], [])
    assert r.unread == (("d3", 4),)
    assert r.pages_read == (("d1", 1),)
    assert r.complete is False and "unread" in r.reason
    assert part_status([], receipt_complete=r.complete) == ("cannot_tell", False)


def test_blank_text_page_counts_as_unread():
    r = build_receipt(CLAIM, [LEASE, AbsencePage("d3", 2, "   \n ")], [])
    assert r.unread == (("d3", 2),) and r.complete is False


def test_uncited_hit_blocks_completeness_and_carries_context():
    page = AbsencePage("d2", 3, "Payment log. A deposit of two weeks was mentioned by the agent.")
    r = build_receipt(CLAIM, [LEASE, page], [])
    assert r.complete is False
    assert len(r.uncited_hits) == 1
    h = r.uncited_hits[0]
    assert (h.term, h.doc, h.page) == ("deposit", "d2", 3)
    assert "deposit of two weeks" in h.context
    assert "deposit" in r.hits and r.hits["deposit"] == (h,)
    assert "uncited" in r.reason


def test_hit_covered_by_card_quote_is_not_uncited():
    page = AbsencePage("d2", 3, "Payment log. A deposit of two weeks was mentioned by the agent.")
    c = card("d2", 3, "A deposit of two weeks was mentioned")
    r = build_receipt(CLAIM, [LEASE, page], [c])
    assert r.hits["deposit"][0].cited is True
    assert r.uncited_hits == () and r.complete is True


def test_card_on_same_page_does_not_cover_a_different_line():
    page = AbsencePage("d2", 3, "Rent is due monthly. Elsewhere a deposit was mentioned.")
    r = build_receipt(CLAIM, [page], [card("d2", 3, "Rent is due monthly")])
    assert r.complete is False and len(r.uncited_hits) == 1


def test_card_quote_not_found_in_page_text_covers_nothing():
    page = AbsencePage("d2", 3, "A deposit was mentioned.")
    r = build_receipt(CLAIM, [page], [card("d2", 3, "totally different words here")])
    assert r.complete is False


@pytest.mark.parametrize("text", ["Paid $250 on arrival.", "Total 250.00 received.", "Sum: 250", "pay 250."])
def test_numbers_match_across_formats(text):
    r = build_receipt("Charge of $250.", [AbsencePage("d", 1, text)], [])
    assert r.complete is False
    assert r.uncited_hits[0].term == "250"


def test_thousands_separator_matches():
    r = build_receipt("Charge of 1250.", [AbsencePage("d", 1, "Sum of $1,250.00 due")], [])
    assert r.uncited_hits and r.uncited_hits[0].term == "1250"


def test_different_number_is_not_a_hit():
    r = build_receipt("Charge of $250.", [AbsencePage("d", 1, "Sum of $2500 and 25.5 due")], [])
    assert r.uncited_hits == ()


def test_terms_are_case_insensitive():
    r = build_receipt("Harborview owns it.", [AbsencePage("d", 1, "HARBORVIEW LLC signed.")], [])
    assert r.uncited_hits[0].term == "harborview"


def test_no_partial_word_hits():
    r = build_receipt("The act applies.", [AbsencePage("d", 1, "The contract and the actor.")], [])
    assert r.uncited_hits == ()
    assert r.complete is True


def test_receipt_is_deterministic():
    pages = [NOTES, LEASE, AbsencePage("d2", 3, "deposit Harborview 250 deposit")]
    a = build_receipt(CLAIM, pages, [])
    b = build_receipt(CLAIM, list(pages), [])
    assert a == b
    assert a.terms == ("tenant", "paid", "250", "deposit", "harborview", "properties")
    keys = [(h.doc, h.page, h.offset) for h in a.uncited_hits]
    assert keys == sorted(keys)


def test_stopwords_and_short_terms_dropped():
    terms = sweep_terms("The tenant is in a lease of it to be OK")
    assert terms == ("tenant", "lease")


def test_empty_term_part_is_incomplete_not_vacuous_true():
    r = build_receipt("It is what it was.", [LEASE], [])
    assert r.terms == ()
    assert r.complete is False and "no searchable terms" in r.reason
    assert part_status([], receipt_complete=r.complete) == ("cannot_tell", False)


def test_no_pages_is_incomplete():
    r = build_receipt(CLAIM, [], [])
    assert r.complete is False and r.reason


def test_true_claim_sweep_noise_is_visible_and_fails_toward_cannot_tell():
    # Supported claim, cited quote covers its own hits, but "months" and the uncovered tail
    # "each month" match the term "month". Noise only costs a not_found a human can read the reason for.
    claim = "Rent is due on the first day of each month."
    r = build_receipt(claim, [LEASE], [card()])
    assert [h.term for h in r.uncited_hits] == ["month", "month"]
    assert r.complete is False and "uncited" in r.reason
    assert part_status([card()], receipt_complete=r.complete) == ("supported", False)


def test_module_imports_no_model_gold_or_network():
    tree = ast.parse((ROOT / "proofgraph" / "review" / "absence.py").read_text(encoding="utf-8"))
    banned = ("muse", "relate", "scan", "ingest", "gold", "packs", "openai", "httpx", "requests", "socket", "urllib")
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        for n in names:
            assert not any(b in n for b in banned), n
