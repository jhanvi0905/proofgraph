"""Absence receipt: what was read, what was swept, what a human must still look at."""

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

from proofgraph.review.absence import AbsencePage, build_receipt, sweep_terms
from proofgraph.review.models import Card
from proofgraph.review.status import part_status

ROOT = Path(__file__).resolve().parents[1]

FILL = "Notes for the file today. "  # a page needs real words to count as read
LEASE = AbsencePage("d1", 1, "This lease runs for twelve months. Rent is due on the first day of each month.")
NOTES = AbsencePage("d2", 1, "Meeting notes. The landlord agreed to repaint the hallway before March.")
CLAIM = "The tenant paid a $250 deposit to Harborview Properties."


def card(doc="d1", page=1, quote="Rent is due on the first day", relation="supports",
         box_status="pinned", id="c"):
    return Card(id=id, part="P1", relation=relation, quote=quote, doc=doc, page=page,
                box_status=box_status, why="w", check="not_run")


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
    r = build_receipt("Charge of $250.", [AbsencePage("d", 1, FILL + text)], [])
    assert r.complete is False
    assert r.uncited_hits[0].term == "250"


def test_thousands_separator_matches():
    r = build_receipt("Charge of 1250.", [AbsencePage("d", 1, FILL + "Sum of $1,250.00 due")], [])
    assert r.uncited_hits and r.uncited_hits[0].term == "1250"


def test_different_number_is_not_a_hit():
    page = "Sum of $2500 and 25.5 due. Later Paid $250 in cash."
    r = build_receipt("Charge of $250.", [AbsencePage("d", 1, page)], [])
    assert [(h.term, h.offset) for h in r.uncited_hits] == [("250", page.index("250 in cash"))]


def test_terms_are_case_insensitive():
    r = build_receipt("Harborview owns it.", [AbsencePage("d", 1, "HARBORVIEW LLC signed.")], [])
    assert r.uncited_hits[0].term == "harborview"


def test_no_partial_word_hits():
    page = "The contract and the actor. The act of God."
    r = build_receipt("The act applies.", [AbsencePage("d", 1, page)], [])
    assert [(h.term, h.offset) for h in r.uncited_hits] == [("act", page.index("act of"))]


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


def test_true_claim_noise_is_only_the_other_sentence_and_status_stays_supported():
    # The card covers its own sentence. The only uncited hit is "months" in the other sentence:
    # an honest cost (a human reads one line), and the supported status is unaffected.
    claim = "Rent is due on the first day of each month."
    c = card(quote="Rent is due on the first day of each month")
    r = build_receipt(claim, [LEASE], [c])
    assert [(h.term, h.offset) for h in r.uncited_hits] == [("month", LEASE.text.index("months"))]
    own = [h for t in r.hits.values() for h in t if h.offset > LEASE.text.index("Rent")]
    assert own and all(h.cited for h in own)
    assert r.complete is False and "uncited" in r.reason
    assert part_status([c], receipt_complete=r.complete) == ("supported", False)


def test_module_imports_only_stdlib_and_models_and_no_dynamic_import():
    tree = ast.parse((ROOT / "proofgraph" / "review" / "absence.py").read_text(encoding="utf-8"))
    allowed = {"__future__", "re", "unicodedata", "decimal", "dataclasses", "collections.abc",
               "proofgraph.review.models"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(a.name in allowed for a in node.names), [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0 and node.module in allowed, node.module
        elif isinstance(node, ast.Name):
            assert node.id not in {"__import__", "importlib", "eval", "exec", "compile", "open"}, node.id
        elif isinstance(node, ast.Attribute):
            assert node.attr not in {"import_module", "__import__"}, node.attr
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            assert "importlib" not in node.value and "__import__" not in node.value


# ---------------------------------------------------------------- R-18b hardening

def hit_terms(claim, page, cards=()):
    r = build_receipt(claim, [AbsencePage("d", 1, FILL + page)], list(cards))
    return r, {h.term for h in r.uncited_hits}


VARIANTS = [
    ("A fee was charged.", "The fees apply here.", "fee"),
    ("Annual bonus due.", "The bonuses are listed.", "bonus"),
    ("The party signed.", "Both parties signed.", "party"),
    ("The deposit was returned.", "It was deposited in March.", "deposit"),
    ("They pay monthly.", "Rent was paid on time.", "pay"),
    ("The deposit was returned.", "The dep-\nosit was held.", "deposit"),
    ("A well-known firm.", "A well known firm.", "well"),
    ("The office lease.", "The o\ufb03ce lease.", "office"),
    ("Nestle owns the plant.", "Nestl\u00e9 SA signed it.", "nestle"),
    ("Zurich branch opened.", "The Z\u00fcrich branch opened.", "zurich"),
    ("The deposit was returned.", "The dep\u200bosit was held.", "deposit"),
    ("Meeting at 2:30 sharp.", "Meeting at 2.30 sharp.", "2.3"),
    ("Meeting at 2.30 sharp.", "Meeting at 14:30 sharp.", "2.3"),
    ("Meeting at 14:30 sharp.", "Meeting at 2:30 sharp.", "14.3"),
    ("A charge of 250 dollars.", "Charge was two hundred fifty only.", "250"),
    ("A charge of two hundred and fifty dollars.", "Charge was 250 only.", "250"),
    ("They raised $1.2m last year.", "Raised 1,200,000 last year.", "1200000"),
    ("They raised $1.2m last year.", "Raised 1.2 million last year.", "1200000"),
]


@pytest.mark.parametrize("claim,page,term", VARIANTS)
def test_word_variants_still_hit_and_block_completeness(claim, page, term):
    r, terms = hit_terms(claim, page)
    assert term in terms, (terms, r.terms)
    assert r.complete is False
    assert part_status([], receipt_complete=r.complete) == ("cannot_tell", False)


def test_ligature_hit_offset_points_at_original_text():
    page = "Notes for the o\ufb03ce lease today."
    r = build_receipt("The office lease.", [AbsencePage("d", 1, page)], [])
    offs = {h.term: h.offset for h in r.uncited_hits}
    assert offs["office"] == page.index("o\ufb03ce")


@pytest.mark.parametrize("a,b", [
    ("fees", "fee"), ("bonuses", "bonus"), ("parties", "party"), ("deposited", "deposit"),
    ("depositing", "deposit"), ("paid", "pay"), ("pays", "pay"), ("leases", "lease"),
    ("stopped", "stop"), ("billed", "bill"), ("agreed", "agree"), ("making", "make"),
    ("taxes", "tax"), ("applied", "apply"),
])
def test_stemmer_rules_one_at_a_time(a, b):
    from proofgraph.review.absence import _stem
    assert _stem(a) == _stem(b)


@pytest.mark.parametrize("a,b", [("act", "actor"), ("rent", "rental"), ("tenant", "tenancy"),
                                 ("contract", "contact"), ("status", "state")])
def test_stemmer_does_not_merge_different_words(a, b):
    from proofgraph.review.absence import _stem
    assert _stem(a) != _stem(b)


@pytest.mark.parametrize("text", ["\u200b" * 300, "-----", "t3n@nt d3p0s1t ~~~", "\u200b\u200b dep \u200b osit"])
def test_garbage_or_invisible_page_is_unread(text):
    r = build_receipt(CLAIM, [LEASE, AbsencePage("g", 2, text)], [])
    assert r.unread == (("g", 2),) and r.complete is False and "unread" in r.reason
    assert part_status([], receipt_complete=r.complete) == ("cannot_tell", False)


def test_readability_edges():
    def unread(text):
        return build_receipt(CLAIM, [AbsencePage("g", 1, text)], []).unread
    assert unread("abc abc abc") == ()                       # exactly 3 words of length 3
    assert unread("abc abc") == (("g", 1),)                  # 2 words
    assert unread("ab ab ab ab ab") == (("g", 1),)           # short words do not count
    assert unread("abc abc abc " + "1" * 13) == ()           # alpha share 9/22 = 0.41
    assert unread("abc abc abc " + "1" * 14) == (("g", 1),)  # alpha share 9/23 = 0.39


HIT_PAGE = "Payment log. A deposit of two weeks was mentioned by the agent."


@pytest.mark.parametrize("box", ["unpinned", "approximate"])
@pytest.mark.parametrize("relation", ["contradicts", "supports", "weakens"])
def test_card_in_a_non_red_box_never_cites_and_blocks_completeness(box, relation):
    page = AbsencePage("d2", 3, HIT_PAGE)
    c = card("d2", 3, "A deposit of two weeks was mentioned", relation, box)
    r = build_receipt(CLAIM, [page], [c])
    assert r.complete is False
    assert len(r.uncited_hits) == 1 and r.uncited_hits[0].cited is False
    assert "could not be pinned" in r.reason
    assert part_status([c], receipt_complete=r.complete)[0] != "not_found"


def test_unpinned_card_blocks_completeness_even_with_no_hits():
    page = AbsencePage("d2", 3, "Nothing relevant on this page at all.")
    c = card("d2", 3, "words we could not find", "contradicts", "unpinned")
    r = build_receipt(CLAIM, [page], [c])
    assert r.complete is False and "could not be pinned" in r.reason


def test_set_aside_card_never_cites_and_unpinned_set_aside_is_ignored():
    page = AbsencePage("d2", 3, HIT_PAGE)
    q = "A deposit of two weeks was mentioned"
    r = build_receipt(CLAIM, [page], [card("d2", 3, q, "set_aside", "pinned")])
    assert r.complete is False and len(r.uncited_hits) == 1
    r2 = build_receipt(CLAIM, [AbsencePage("d2", 3, "Nothing relevant on this page at all.")],
                       [card("d2", 3, q, "set_aside", "unpinned")])
    assert r2.complete is True


@pytest.mark.parametrize("box,relation", [("pinned", "supports"), ("located", "weakens"),
                                          ("located", "contradicts")])
def test_pinned_or_located_card_cites_its_own_hit(box, relation):
    page = AbsencePage("d2", 3, HIT_PAGE)
    r = build_receipt(CLAIM, [page], [card("d2", 3, "A deposit of two weeks was mentioned", relation, box)])
    assert r.complete is True and r.uncited_hits == ()


THREE = AbsencePage("d", 1, "First line has a deposit. Second line has a deposit. Third line has a deposit.")


def test_one_word_quote_cites_only_one_occurrence():
    r = build_receipt("The deposit.", [THREE], [card("d", 1, "deposit")])
    assert len(r.hits["deposit"]) == 3
    assert [h.cited for h in r.hits["deposit"]] == [True, False, False]
    assert len(r.uncited_hits) == 2 and r.complete is False


def test_each_card_takes_a_distinct_occurrence_in_any_order():
    a, b = card("d", 1, "deposit", id="a"), card("d", 1, "deposit", id="b")
    for cards in ([a, b], [b, a]):
        r = build_receipt("The deposit.", [THREE], cards)
        assert [h.cited for h in r.hits["deposit"]] == [True, True, False]
    r3 = build_receipt("The deposit.", [THREE], [a, b, card("d", 1, "deposit", id="c")])
    assert r3.complete is True


def test_duplicate_pages_count_once():
    p = AbsencePage("d1", 1, LEASE.text)
    r = build_receipt(CLAIM, [LEASE, p, AbsencePage("x", 2, None), AbsencePage("x", 2, None)], [])
    assert r.pages_read == (("d1", 1),) and r.unread == (("x", 2),)


def test_to_model_receipt_dedupes_and_keeps_counts_consistent():
    from proofgraph.review.absence import to_model_receipt
    from proofgraph.review.models import Receipt
    pages = [LEASE, LEASE, NOTES, AbsencePage("x", 4, None), AbsencePage("y", 4, None),
             AbsencePage("x", 4, None), AbsencePage("z", 2, HIT_PAGE)]
    r = build_receipt(CLAIM, pages, [])
    m = to_model_receipt(r)
    assert isinstance(m, Receipt)
    assert m.pages_read == 3 and m.unread == [4, 4]
    assert m.terms == list(r.terms)
    assert len(m.uncited_hits) == len(r.uncited_hits) == 1
    assert "deposit" in m.uncited_hits[0] and "z" in m.uncited_hits[0]


def test_receipt_is_identical_across_processes_and_hash_seeds():
    code = (
        "from proofgraph.review.absence import AbsencePage, build_receipt\n"
        "pages=[AbsencePage('b',2,'Fees paid. Two hundred fifty at 14:30, dep-\\nosit Nestl\\u00e9 o\\ufb03ce parties.'),"
        "AbsencePage('a',1,'deposit deposit 250 well known')]\n"
        "print(repr(build_receipt('The tenant paid a $250 deposit, fee, party, Nestle, office at 2:30 well-known.', pages, [])))\n"
    )
    outs = set()
    for seed in ("0", "1", "12345"):
        env = {**os.environ, "PYTHONHASHSEED": seed}
        out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True,
                             text=True, check=True).stdout
        outs.add(out)
    assert len(outs) == 1 and "uncited_hits" in outs.pop()
