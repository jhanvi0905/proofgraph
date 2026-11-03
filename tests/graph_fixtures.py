"""Shared TC17-shaped graph fixture for the graph tests (bylaws, a resolution, an exception, a hub)."""
from proofgraph.review.graph import build_entities, edges, merge
from proofgraph.review.graph_extract import Alignment, DefinedTerm, DocRead, GroundedRule, Header, Relation, Rule

RES_Q = "The Board ratified the appointment of Connors as Interim Chief Medical Officer on May 13, 2026, effective as of May 7, 2026."
CMO_Q = "A Chief Medical Officer is a principal officer under Section 5.1."
P52_Q = "No appointment of a principal officer is effective until approved by the Board (Section 5.2)."
LETTER_Q = "The CEO appointed her by letter dated May 7, 2026."


def _g(doc, rid, bearer, quote, level="exact", **kw):
    r = Rule(id=rid, bearer=bearer, deontic="is", action="a", page=1, quote=quote, **kw)
    return GroundedRule(r, doc, Alignment(level, 1))


def _reads(level="exact"):
    res = DocRead("res", Header(role="resolution", date="May 13, 2026"), [
        _g("res", "res-r1", "Connors", RES_Q, level, concepts=["Chief Medical Officer"],
           relations=[Relation(kind="holds_office", subject="Connors", object="Chief Medical Officer", interim=True)]),
        _g("res", "res-r2", "CEO", LETTER_Q)])
    byl = DocRead("byl", Header(role="bylaws", date="March 12, 2025",
                                defined_terms=[DefinedTerm(term="principal officer", quote="principal officer means X")]), [
        _g("byl", "byl-r1", "Chief Medical Officer", CMO_Q, concepts=["principal officer", "Section 5.1"],
           relations=[Relation(kind="is_a", subject="Chief Medical Officer", object="principal officer")]),
        _g("byl", "byl-r2", "Board", P52_Q, concepts=["principal officer", "Section 5.2"]),
        _g("byl", "byl-r3", "Board", "The Board may waive Section 5.2 unless a bylaw forbids it.",
           concepts=["Section 5.2"], link_kind="exception", excepts="byl-r2"),
        _g("byl", "byl-r4", "Board", "Ghost exception.", link_kind="exception", excepts="byl-zz")])
    byl.terms = {"principal officer": Alignment("exact", 1)}
    return [res, byl]


def _graph(reads=None, **kw):
    reads = reads or _reads()
    ents = build_entities(reads)
    return edges(reads, ents, merge(ents, reads), **kw)
