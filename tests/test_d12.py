"""D12: verdict inputs come from verified text and a bounded region.

Each test names the old behaviour it rules out. The PDFs here are written by tests/pdfgen.py at test time,
laid out like the Family C pages (an off-centre gutter, hanging list numbers, parallel wording repeated
across coverages), so nothing third-party is committed.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pdfplumber
import pytest

from proofgraph.checker import open_source, verify_citation
from proofgraph.geometry import column_of, page_layout, page_words
from proofgraph.ingest import _page_lines_layout
from proofgraph.schema import BBox, Citation
from pdfgen import column_lines, write_pdf

# A Chubb-like page: left column at 42.5, right column's list numbers at 292 and its wrapped lines at 306.2,
# so the right column starts left of the page midpoint (306).
ITEM8 = "8. additional fees up to $5,000, as long as you"
ITEM8_2 = "have our written approval in advance, for:"
WAGES = "up to $5,000 per coverage period. You must"
LEFT = "a line printed once, in the left column only"


def _two_column_page():
    left = column_lines(42.5, 60, 30)
    left[6] = (42.5, 138, LEFT)
    right = column_lines(306.2, 60, 8) + [(292.0, 164, ITEM8), (306.2, 177, ITEM8_2)] + column_lines(306.2, 190, 20)
    return left + right


@pytest.fixture(scope="module")
def chubb_like(tmp_path_factory) -> Path:
    d = tmp_path_factory.mktemp("d12")
    # page 2: the same wage sentence printed under two coverages, one per column
    rep = (column_lines(42.5, 60, 10) + [(42.5, 190, WAGES)] + column_lines(42.5, 203, 18)
           + column_lines(306.2, 60, 14) + [(306.2, 242, WAGES)] + column_lines(306.2, 255, 14))
    return write_pdf(d / "chubb_like.pdf", [_two_column_page(), rep])


def _words(path: Path, page: int = 1):
    with pdfplumber.open(path) as pdf:
        p = pdf.pages[page - 1]
        return page_words(p), float(p.width)


def _cite(path: Path, page: int, text: str, region: BBox | None = None, sha: str | None = None) -> Citation:
    src = open_source(path)
    loc = {"kind": "page_quote", "page": page}
    if region is not None:
        loc["region"] = region.model_dump()
    if sha is not None:
        loc["text_sha256"] = sha
    return Citation.model_validate({"source_file": path.name, "sha256_of_file": src.sha256, "locator": loc, "text": text})


# ---------------------------------------------------------------- item 3: columns from page coordinates


def test_gutter_comes_from_coordinates_not_the_page_midpoint(chubb_like):
    words, width = _words(chubb_like)
    layout = page_layout(words, width)
    assert layout.kind == "columns" and len(layout.gutters) == 1
    g = layout.gutters[0]
    assert 270 < g < 292  # the whitespace between the columns, left of the midpoint
    # the old rule (x0 < width/2) put the right column's list number and its wrapped line in different columns
    assert (292.0 < width / 2) != (306.2 < width / 2)
    assert column_of(layout, 292.0, 500.0) == column_of(layout, 306.2, 500.0) == 1


def test_a_block_in_the_right_column_starting_left_of_the_midpoint_verifies(chubb_like):
    """Family C C3, run 2: the checker read this block as crossing columns. Coordinates say one column."""
    src = open_source(chubb_like)
    assert verify_citation(_cite(chubb_like, 1, ITEM8 + "\n" + ITEM8_2), src) is None


def test_lines_from_two_columns_are_still_refused(chubb_like):
    src = open_source(chubb_like)
    assert "more than one column" in verify_citation(_cite(chubb_like, 1, LEFT + "\n" + ITEM8), src)


def test_two_printed_pages_side_by_side_read_as_four_columns(tmp_path):
    xs = [20, 215, 410, 605]
    lines = [ln for x in xs for ln in column_lines(x, 60, 25)]
    path = write_pdf(tmp_path / "two_up.pdf", [lines], width=792, height=612, size=7)
    words, width = _words(path)
    layout = page_layout(words, width)
    assert layout.kind == "columns" and len(layout.gutters) == 3
    with pdfplumber.open(path) as pdf:
        out, _ = _page_lines_layout(pdf.pages[0])
    starts = [b.x0 for _, b, _ in out]
    # each column is read top to bottom before the next: four runs of x positions, left to right
    runs = [starts[0]] + [b for a, b in zip(starts, starts[1:]) if abs(a - b) > 1]
    assert [round(r) for r in runs] == xs


def test_a_table_is_read_row_by_row_not_split_into_columns(tmp_path):
    rows = [(42.6, 200 + 24 * k, f"{chr(65 + k)}. Coverage part {k}") for k in range(9)]
    rows += [(440.2, 200 + 24 * k, f"${k},000") for k in range(9)]
    rows += [(42.6, 150, "COVERAGE PART MAXIMUM COVERAGE PART LIMIT DEDUCTIBLE")]
    path = write_pdf(tmp_path / "table.pdf", [rows])
    words, width = _words(path)
    assert page_layout(words, width).kind == "single"
    with pdfplumber.open(path) as pdf:
        out, layout = _page_lines_layout(pdf.pages[0])
    assert "A. Coverage part 0 $0,000" in [t for t, _, _ in out]  # the label and its amount on one line


def test_the_iso_form_keeps_its_two_columns_and_gutters():
    """No existing reading order moves: every HO 00 03 page is two columns at the gutter used before D12."""
    path = Path(__file__).resolve().parent.parent / "data" / "raw" / "ho_00_03_04_91.pdf"
    if not path.exists():
        pytest.skip("ISO file absent")
    with pdfplumber.open(path) as pdf:
        for p in pdf.pages:
            words = page_words(p)
            layout = page_layout(words, p.width)
            assert layout.kind == "columns" and len(layout.gutters) == 1


def test_each_admitted_passage_records_the_geometry_in_force():
    from proofgraph.ingest import ingest
    from proofgraph.schema import SourceManifest

    root = Path(__file__).resolve().parent.parent
    labels = SourceManifest.model_validate_json((root / "data" / "instruments.json").read_text()).sources
    ho = next(s for s in labels if s.file.endswith(".pdf"))
    if not (root / "data" / "raw" / ho.file).exists():
        pytest.skip("ISO file absent")
    spans = [sp for i in ingest(ho, root / "data" / "raw").instruments for sp in i.spans]
    assert spans and all(sp.layout is not None and sp.layout.kind == "columns" for sp in spans)


# ---------------------------------------------------------------- item 2: identity is the page plus the region


def _region_of(path: Path, page: int, line: str, which: int) -> BBox:
    with pdfplumber.open(path) as pdf:
        hits = pdf.pages[page - 1].search(line, regex=False)
    h = sorted(hits, key=lambda h: h["x0"])[which]
    return BBox(x0=h["x0"] - 5, top=h["top"] - 40, x1=h["x1"] + 5, bottom=h["bottom"] + 40)


def test_a_line_repeated_elsewhere_on_the_page_is_not_ambiguity_inside_the_region(chubb_like):
    """Family C: parallel wording across coverages. Old rule: 2 times on the page, broken."""
    src = open_source(chubb_like)
    assert "2 times on page 2" in verify_citation(_cite(chubb_like, 2, WAGES), src)  # no region: the old rule
    for which in (0, 1):
        region = _region_of(chubb_like, 2, WAGES, which)
        assert verify_citation(_cite(chubb_like, 2, WAGES, region=region), src) is None


def test_a_quote_outside_the_region_is_broken(chubb_like):
    src = open_source(chubb_like)
    far = BBox(x0=40, top=600, x1=280, bottom=700)
    assert "0 times inside the passage's region" in verify_citation(_cite(chubb_like, 2, WAGES, region=far), src)


def test_lines_with_another_line_between_them_are_not_one_quote():
    """Old rule: each line once, top to bottom, same column, so lines 1 and 3 of a block passed as one quote."""
    path = Path(__file__).resolve().parent.parent / "data" / "raw" / "ho_00_03_04_91.pdf"
    if not path.exists():
        pytest.skip("ISO file absent")
    src = open_source(path)
    block = ['1. "Bodily injury" means bodily harm, sickness or', "disease, including required care, loss of services",
             "and death that results."]
    cite = lambda text: Citation.model_validate({"source_file": path.name, "sha256_of_file": src.sha256,
                                                 "locator": {"kind": "page_quote", "page": 1}, "text": text})
    assert verify_citation(cite("\n".join(block)), src) is None
    assert "not consecutive" in verify_citation(cite(block[0] + "\n" + block[2]), src)


def test_a_stale_text_hash_is_refused_never_substituted(chubb_like):
    src = open_source(chubb_like)
    good = hashlib.sha256(ITEM8.encode()).hexdigest()
    assert verify_citation(_cite(chubb_like, 1, ITEM8, sha=good), src) is None
    assert "stale" in verify_citation(_cite(chubb_like, 1, ITEM8, sha="0" * 64), src)


def test_raw_text_citations_keep_file_offsets():
    from proofgraph.schema import RawOffsets

    c = Citation.model_validate({"source_file": "x.txt", "sha256_of_file": "0" * 64,
                                 "locator": {"kind": "raw_offsets", "start": 10, "end": 13}, "text": "abc"})
    assert isinstance(c.locator, RawOffsets) and not hasattr(c.locator, "region")


# ---------------------------------------------------------------- item 1: the value comes from the verified quote


def _evidence_on(path: Path, page: int, text: str, pointer: str | None, region: BBox | None = None):
    from proofgraph.schema import DocumentRoute, Evidence, Excerpt, MappingMethod, RouteStrength, Side

    cit = _cite(path, page, text, region=region)
    value = None
    if pointer:
        i = text.index(pointer)
        value = Excerpt(start=i, end=i + len(pointer), text=pointer)
    route = DocumentRoute(policy="P1", strength=RouteStrength.READ, method=MappingMethod.LABEL, reasoning=None, citation=cit)
    return Evidence(side=Side.SUPPORT, span_id="0" * 16, doc_id="doc", identification=route, reading="r",
                    quote=Excerpt(start=0, end=len(text), text=text), citation=cit, value=value)


def _inst():
    from proofgraph.schema import Instrument

    import json

    return Instrument.model_validate_json(json.dumps({
        "doc_id": "doc", "version": "1", "instrument_type": "policy_form", "issuer": "x", "policy_numbers": ["P1"],
        "effective_date": None, "source_id": "s", "source_start": 0, "source_end": 1, "first_page": 1, "last_page": 2,
        "file_start": None, "file_end": None, "spans": [], "definitions": []}))


def test_the_one_amount_in_a_verified_quote_is_read_by_code_without_a_pointer(chubb_like):
    """Family C C2: the right line, no pointer. Before D12 the line was discarded ("the pass gave no value")."""
    from proofgraph.assertions import assert_from_evidence
    from proofgraph.trace import Trace

    a = assert_from_evidence(_evidence_on(chubb_like, 1, ITEM8, None), _inst(), "P1.x", Trace(None))
    assert a.value.text == "$5,000" and a.routes[1].strength.value == "derived"


def test_a_pointer_that_disagrees_with_the_one_amount_is_value_ambiguous(chubb_like):
    from proofgraph.assertions import assert_from_evidence
    from proofgraph.schema import InvalidAssertion
    from proofgraph.trace import Trace

    out = assert_from_evidence(_evidence_on(chubb_like, 1, ITEM8, "8."), _inst(), "P1.x", Trace(None))
    assert isinstance(out, InvalidAssertion) and out.reason.startswith("value_ambiguous")


def _gathered(candidates):
    from proofgraph.grouping import Gathered, read_claim
    from proofgraph.pipeline import PacketRun
    from proofgraph.schema import Claim

    r = read_claim("The limit is $5,000.", ("P1",))
    run = PacketRun(claim=Claim(claim_id="c", text=r.text, slot="P1.typed", kind="amount", value=r.value), atom_text=None)
    return Gathered(read=r, policy="P1", temp_slot="P1.typed", doc_ids=["doc"], run=run, checked=(), candidates=candidates)


def test_a_confirmed_line_with_several_amounts_and_no_pointer_is_unresolved_value_ambiguous():
    from proofgraph.grouping import REFUSAL_TEXT, Candidate, decide_typed

    c = Candidate("support:doc:00000000", "doc", "support", 1, None, None, "$10M NIL/NIL/1,000,000", None,
                  "value_ambiguous: the verified quote states 2 amounts")
    d = decide_typed(_gathered([c]), {c.line_id}, {}, confirmed_by="t", policy_source="chosen")
    assert d.refusal == "value_ambiguous" and "Unresolved" in REFUSAL_TEXT["value_ambiguous"]
    assert d.record["value_ambiguous"][0]["text"] == "$10M NIL/NIL/1,000,000"


def test_gather_shows_a_value_ambiguous_line_to_the_person(monkeypatch, chubb_like):
    """Never silently dropped: the line reaches the confirmation screen, marked with why no value was read."""
    import proofgraph.grouping as grouping
    from proofgraph.pipeline import PacketRun
    from proofgraph.schema import InvalidAssertion

    two = "pays $5,000 or $10,000 per coverage period"
    ev = _evidence_on(chubb_like, 1, ITEM8, None).model_copy(update={"citation": _cite(chubb_like, 1, ITEM8)})
    ev = ev.model_copy(update={"citation": ev.citation.model_copy(update={"text": two})})

    def fake_gather(packet_id, claim, doc_ids, mappings, data, trace):
        run = PacketRun(claim=claim, atom_text="x", documents=[("doc", 3)], evidence=[ev],
                        invalid=[InvalidAssertion(mapping_id="support:doc:00000000", reason="value_ambiguous: 2 amounts")])
        return run, ()

    monkeypatch.setattr(grouping, "gather", fake_gather)
    g = grouping.gather_typed(grouping.read_claim("The limit is $5,000.", ("P1",)), "P1", "t", ["doc"], None, Path("."), None)
    assert [(c.quote, c.value, c.no_value) for c in g.candidates] == [(two, None, "value_ambiguous: 2 amounts")]
    assert g.nothing_found == []


# ---------------------------------------------------------------- item 5: currency and basis are data


def test_iso_codes_and_symbols_come_from_the_table_and_an_unknown_token_is_named():
    from proofgraph.numbers import parse_amount
    from proofgraph.schema import ParseFailure

    assert parse_amount("EUR 4,200").currency.value == "EUR"  # until D12: unparseable, only US dollars were read
    assert parse_amount("£250").currency.value == "GBP"
    assert parse_amount("US$5").currency.value == "USD"
    for raw, token in (("XYZ 1,000", "XYZ"), ("NT$500", "NT$"), ("¥300", "¥")):
        out = parse_amount(raw)
        assert isinstance(out, ParseFailure) and out.reason == f"unknown_currency: {token}"
    out = parse_amount("JPY 1,000.50")  # minor units from the table: yen has none
    assert isinstance(out, ParseFailure) and "JPY" in out.reason


def test_a_typed_claim_in_an_unknown_currency_is_refused_naming_the_token():
    from proofgraph.grouping import read_claim, refusal_text

    r = read_claim("The limit is XYZ 1,000.", ())
    assert r.refusal == "unknown_currency" and "XYZ" in refusal_text(r.refusal, r.token)
    assert read_claim("Lost wages are covered for the first 60 days.", ()).kind == "wording"  # capitals only: "the 60" is no token


def test_dollar_sign_is_dollars_with_no_country_printed():
    from proofgraph.numbers import _compare, parse_amount

    d = parse_amount("$500,000").currency
    assert d.value == "dollars_country_not_printed"  # until D12: USD
    same = _compare("a", "$1,000", d, None, "b", "$1,000", d, None)
    assert same.compared and same.reason.value == "equal"
    usd = parse_amount("USD 1,000").currency
    named = _compare("a", "$1,000", d, None, "b", "USD 1,000", usd, None)
    assert not named.compared and named.reason.value == "currency_country_not_printed" and named.detail == "'$' vs USD"


def test_basis_phrases_come_from_the_table_each_its_own_basis():
    from proofgraph.numbers import find_basis

    assert find_basis("up to $5,000 per coverage period")[0].value == "per_coverage_period"  # until D12: no basis
    assert find_basis("$1,000 each occurrence")[0].value == "each_occurrence"
    assert find_basis("$1,000 per occurrence")[0].value == "per_occurrence"  # its own basis, not each_occurrence (D6)
    assert find_basis("$1,000 for any single mishap") is None  # outside the table: no basis


def test_the_atomize_prompt_keeps_its_d9_basis_list():
    from proofgraph.atomize import ATOM_BASES

    assert ATOM_BASES == ("each_occurrence", "any_one_claim", "per_person", "aggregate", "each_claim", "each_loss", "unknown")


@pytest.fixture(scope="module")
def usd_line(tmp_path_factory) -> Path:
    return write_pdf(tmp_path_factory.mktemp("usd") / "usd.pdf", [[(42.5, 100, "fees up to USD 5,000 per coverage period")]])


def _usd_gathered(usd_line):
    from proofgraph.assertions import assert_from_evidence
    from proofgraph.grouping import Candidate, Gathered, read_claim
    from proofgraph.pipeline import PacketRun
    from proofgraph.schema import Claim
    from proofgraph.trace import Trace

    r = read_claim("Under P1, fees are covered up to $5,000 per coverage period.", ("P1",))
    a = assert_from_evidence(_evidence_on(usd_line, 1, "fees up to USD 5,000 per coverage period", None), _inst(), "P1.t",
                             Trace(None))
    run = PacketRun(claim=Claim(claim_id="c", text=r.text, slot="P1.t", kind="amount", value=r.value), atom_text=None,
                    assertions=[a])
    c = Candidate(a.assertion_id, "doc", "support", 1, None, None, a.citation.text, a.value.text)
    return Gathered(read=r, policy="P1", temp_slot="P1.t", doc_ids=["doc"], run=run, checked=(), candidates=[c]), c


def test_a_dollar_claim_against_a_named_currency_waits_for_a_person(usd_line):
    from proofgraph.grouping import decide_typed

    g, c = _usd_gathered(usd_line)
    d = decide_typed(g, {c.line_id}, {}, confirmed_by="t", policy_source="chosen")
    v = d.run.verdict
    assert (v.verdict.value, v.unresolved_reason.value) == ("unresolved", "amounts_not_comparable")
    assert v.claim_comparison.reason.value == "currency_country_not_printed"
    assert d.record["currency_source"] == "dollars_country_not_printed"


def test_the_currency_set_at_confirmation_is_recorded_and_then_compared(usd_line):
    from proofgraph.grouping import decide_typed

    g, c = _usd_gathered(usd_line)
    d = decide_typed(g, {c.line_id}, {}, confirmed_by="t", policy_source="chosen", currency_set="USD")
    assert d.run.verdict.verdict.value == "supported"
    assert (d.record["currency_source"], d.record["currency_set"]) == ("set_at_confirmation", "USD")
    assert d.record["claim_value_compared"] == "USD 5,000 per coverage period"
    from app.result import _record_line

    line = _record_line({**d.record, "confirmed_on": None})
    assert "Currency: set at confirmation, not written by the claimant (USD)" in line
    g, c = _usd_gathered(usd_line)
    assert decide_typed(g, {c.line_id}, {}, confirmed_by="t", policy_source="chosen", currency_set="XYZ").refusal == \
        "currency_not_known"
