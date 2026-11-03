from proofgraph.review.graph import build_entities, canon_name, entity_type, merge, section_key
from proofgraph.review.graph_extract import Alignment, DocRead, GroundedRule, Header, Rule
from proofgraph.review.graph_extract import DefinedTerm


def _g(doc, rid, bearer, concepts=(), quote="q", **kw):
    r = Rule(id=rid, bearer=bearer, deontic="is", action="a", page=1, quote=quote, concepts=list(concepts), **kw)
    return GroundedRule(r, doc, Alignment("exact", 1))


def _read(doc, rules, parties=(), terms=()):
    h = Header(parties=list(parties), defined_terms=[DefinedTerm(term=t, quote=q) for t, q in terms])
    return DocRead(doc, h, rules)


def _tc17():
    res = _read("res", [_g("res", "res-r1", "Connors", ["Interim CMO", "Chief Medical Officer"]),
                        _g("res", "res-r2", "Board", ["Section 5.9"])], parties=["Connors"])
    byl = _read("byl", [_g("byl", "byl-r1", "Chief Medical Officer", ["principal officer"]),
                        _g("byl", "byl-r2", "Board", ["§5.2", "principal officer"])])
    return [res, byl]


def test_every_statement_points_at_one_entity_and_cmo_spans_two_documents():
    reads = _tc17()
    ents = build_entities(reads)
    assert set(ents.subject) == {"res-r1", "res-r2", "byl-r1", "byl-r2"}
    cmo = ents.by_id["e:chief medical officer"]
    assert cmo.docs == {"res", "byl"} and cmo.type == "office"
    assert ents.by_id[ents.subject["res-r1"]].type == "person"


def test_section_surface_forms_share_one_scoped_entity():
    ents = build_entities([_read("byl", [_g("byl", "r1", "Board", ["Section 5.2", "§5.2", "5.2"])])])
    assert [e.id for e in ents.by_id.values() if e.type == "section"] == ["e:byl:section 5.2"]


def test_sections_never_merge_across_documents_or_numbers():
    reads = [_read("a", [_g("a", "r1", "X", ["Section 3.2", "Section 3.3"])]),
             _read("b", [_g("b", "r2", "X", ["Section 3.2"])])]
    ents = build_entities(reads)
    m = merge(ents, reads)
    ids = {"e:a:section 3.2", "e:a:section 3.3", "e:b:section 3.2"}
    assert ids <= set(ents.by_id)
    assert len({m.canon[i] for i in ids}) == 3
    assert not any(l.kind == "same_as" for l in m.links)


def test_parties_clause_and_definition_merge_with_quote():
    nda = _read("nda", [_g("nda", "r1", "Recipient", ["Affiliate"]), _g("nda", "r2", "Bosch Inc.")],
                parties=["Bosch Inc."],
                terms=[("Recipient", 'Bosch Inc. (the "Recipient") receives information'),
                       ("Affiliate", '"Affiliate" means any entity controlling the Company')])
    ents = build_entities([nda])
    m = merge(ents, [nda])
    assert m.canon["e:nda:recipient"] == m.canon["e:bosch inc"]
    assert m.canon["e:nda:affiliate"] == "e:nda:affiliate"
    link = next(l for l in m.links if l.rule == "parties_clause")
    assert link.kind == "same_as" and "Recipient" in link.quote


def test_defined_term_crosses_documents_only_on_as_defined_in():
    a = _read("a", [_g("a", "a1", "Affiliate", quote="Affiliate as defined in the Master Agreement")],
              terms=[("Affiliate", '"Affiliate" means X')])
    b = _read("b", [_g("b", "b1", "Affiliate")], terms=[("Affiliate", '"Affiliate" means Y')])
    ents = build_entities([a, b])
    assert merge(ents, [a, b]).canon["e:a:affiliate"] == merge(ents, [a, b]).canon["e:b:affiliate"]
    a2 = _read("a", [_g("a", "a1", "Affiliate", quote="Affiliate only")], terms=[("Affiliate", '"Affiliate" means X')])
    ents2 = build_entities([a2, b])
    m2 = merge(ents2, [a2, b])
    assert m2.canon["e:a:affiliate"] != m2.canon["e:b:affiliate"]


def test_near_miss_is_unclear_not_merged_and_number_vetoes():
    reads = [_read("d", [_g("d", "r1", "Disclosing Party"), _g("d", "r2", "Disclosing Parties"),
                         _g("d", "r3", "Tier 1 Supplier"), _g("d", "r4", "Tier 2 Supplier")])]
    ents = build_entities(reads)
    m = merge(ents, reads)
    unclear = {(l.a, l.b) for l in m.links if l.kind == "unclear"}
    assert ("e:disclosing parties", "e:disclosing party") in unclear
    assert not any("tier" in a for a, _ in unclear)
    assert m.canon["e:disclosing party"] != m.canon["e:disclosing parties"]


def test_helpers():
    assert canon_name("The  Recipient.") == "recipient"
    assert section_key("§ 5.2") == "section 5.2" and section_key("Section 5") == "section 5"
    assert section_key("Chief Medical Officer") is None
    assert entity_type("Chief Medical Officer", set()) == "office"
    assert entity_type("Board approval", set()) == "event"
    assert entity_type("Bosch Inc.", set()) == "organisation"


def test_singular_and_plural_are_one_entity_but_other_near_misses_are_not():
    reads = [_read("d", [_g("d", "r1", "principal officer"), _g("d", "r2", "principal officers"),
                         _g("d", "r3", "Disclosing Party"), _g("d", "r4", "Disclosing Parties")])]
    ents = build_entities(reads)
    m = merge(ents, reads)
    assert m.canon["e:principal officers"] == m.canon["e:principal officer"]
    assert next(l for l in m.links if l.rule == "plural").kind == "same_as"
    assert m.canon["e:disclosing party"] != m.canon["e:disclosing parties"]  # "ies" is not a plural of "y" here


def test_a1_statement_type_reaches_the_graph_node_and_defaults_to_rule():
    from graph_fixtures import _g, _graph, _reads

    reads = _reads()
    reads[0].rules[0].rule.stype = "fact"
    g = _graph(reads)
    assert g.nodes["res-r1"]["stype"] == "fact" and g.nodes["byl-r2"]["stype"] == "rule"
    assert _g("d", "x", "B", "q").rule.stype == "rule"


def test_a5_overrides_edge_is_verified_against_its_quote_and_unverified_is_unclear():
    from graph_fixtures import _g, _reads
    from proofgraph.review.graph import build_entities, edges, merge
    from proofgraph.review.graph_extract import Relation

    def build(subject, obj):
        reads = _reads()
        reads[0].rules.append(_g("res", "res-r9", "Board", "This Resolution replaces the earlier appointment letter.",
                                 relations=[Relation(kind="overrides", subject=subject, object=obj)]))
        ents = build_entities(reads)
        reads[0].rules.append  # noqa: B018
        return edges(reads, ents, merge(ents, reads))

    g = build("This Resolution", "appointment letter")
    found = [(u, d["tier"]) for u, _, d in g.edges(data=True) if d["kind"] == "overrides"]
    assert found == [("res-r9", "page")]
    g = build("This Resolution", "the employment contract")  # the object is not in the quote
    assert [d["tier"] for _, _, d in g.edges(data=True) if d["kind"] == "overrides"] == ["unclear"]
    assert g.graph["rejected"]["relation_not_in_quote"] == 1


def test_a2_a3_events_and_event_anchors_are_carried_on_the_node():
    import pytest
    from graph_fixtures import _graph, _reads
    from pydantic import ValidationError

    from proofgraph.review.graph_extract import Rule

    reads = _reads()
    ev = reads[0].rules[0].rule  # res-r1
    ev.stype, ev.event_type, ev.event_date, ev.actor = "event", "approve_or_adopt", "May 13, 2026", "Board"
    cond = reads[1].rules[2].rule  # byl-r3, the exception to byl-r2
    cond.awaits, cond.awaits_actor = "approve_or_adopt", "Board"
    g = _graph(reads)
    assert (g.nodes["res-r1"]["event_type"], g.nodes["res-r1"]["event_date"], g.nodes["res-r1"]["actor"]) == ("approve_or_adopt", "May 13, 2026", "Board")
    assert (g.nodes["byl-r3"]["awaits"], g.nodes["byl-r3"]["awaits_actor"]) == ("approve_or_adopt", "Board")
    assert g.nodes["byl-r2"]["event_type"] is None
    with pytest.raises(ValidationError):  # the event types are a fixed list the model chooses from, never a code synonym list
        Rule(id="x", bearer="b", deontic="is", action="a", page=1, quote="q", event_type="ratify")
