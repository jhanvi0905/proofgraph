"""The one-screen result: the claim as a question, the verdict and the rule that decided it, each
assertion beside the page it came from, every pair with a plain reason, and who wrote what.

The source pane is the proof a non-engineer can check: for a PDF, the page itself, cropped to the
cited block, with the cited lines boxed where the PDF parser finds them (the same check the verifier
uses); for a text filing, the raw lines with the cited characters marked.
"""

from __future__ import annotations

import base64
import html
import io
from pathlib import Path

import pdfplumber

from proofgraph.pipeline import PacketRun
from proofgraph.schema import Assertion, PageQuote, RawOffsets, SourceManifest

E = html.escape

REASON = {
    "equal": "compared: same amount, same currency, same basis",
    "different": "compared: different amounts on the same currency and basis",
    "currency_not_stated": "not compared: {who} states no currency",
    "currency_mismatch": "not compared: different currencies ({detail})",
    "basis_not_stated": "not compared: {who} states no basis (each claim, each loss, aggregate…)",
    "basis_mismatch": "not compared: different bases ({detail})",
    "no_numeral": "not compared: one side states no amount ({detail})",
}
RULE_WORDS = {
    "endorsement_over_base": "Endorsement over base form",
    "later_effective_date": "Later effective date over earlier",
}
STRENGTH = {"read": "read in the document", "derived": "derived mechanically", "judgment": "a judgment"}


def render(run: PacketRun, data: Path, title: str) -> str:
    manifest = SourceManifest.model_validate_json((data / "instruments.json").read_text(encoding="utf-8"))
    info = {i.doc_id: (s, i) for s in manifest.sources for i in s.instruments}
    v = run.verdict
    names = {a.assertion_id: _doc_name(a.instrument.doc_id, info) for a in run.assertions}

    if run.failure or v is None:
        body = f'<p class="fail">The check stopped: {E(run.failure or "no verdict")}. Nothing after this point was read.</p>'
        return _page(title, body)

    verdict_html = _verdict(v, names, info)
    rows = "".join(_assertion(a, v, names[a.assertion_id], info, data) for a in run.assertions) or \
        '<p class="empty">No document in this packet states a value for this. Nothing was cited.</p>'
    pairs = _pairs(v, names)
    rules = _rules(v, info, names)
    body = f"""
<header class="q">
  <h1>Does the packet support this claim?</h1>
  <p class="claim">“{E(run.claim.text)}”</p>
  <p class="meta">Checked against {len(run.documents)} admitted document{'s' if len(run.documents) != 1 else ''}: {E(", ".join(_doc_name(d, info) for d, _ in run.documents))}.</p>
</header>
{verdict_html}
{rules}
<section aria-labelledby="ev"><h2 id="ev">What each document states, and where</h2>{rows}</section>
{pairs}
<footer>
  <p><strong>Who wrote what.</strong> The claim, its slot (<code>{E(run.claim.slot)}</code>), and which policy each document describes are written by a person.
  The model read the admitted passages and pointed at the values; code parsed every amount, compared every pair, applied the precedence rules,
  and checked every citation against the file. Nothing on this page is generated prose standing in for a document.</p>
</footer>"""
    return _page(title, body)


# ---------------------------------------------------------------- sections


def _verdict(v, names, info) -> str:
    reason = v.supported_reason or v.unresolved_reason or v.not_found_reason
    r = reason.value if reason else ""
    if v.verdict.value == "supported" and r == "resolved_by_rule":
        cls, mark, word = "green", "tick", "Supported, decided by a rule"
        gov = _doc_name(v.governing_doc_id, info)
        line = (f"The documents could not be compared directly, so a precedence rule decided which one governs: "
                f"<strong>{E(gov)}</strong>.")
    elif v.verdict.value == "supported":
        cls, mark, word = "green", "tick", "Supported"
        line = "The documents that state this agree, and nothing disputes it. No rule had anything to decide."
    elif v.verdict.value == "unresolved" and r == "documents_disagree":
        cls, mark, word = "clash", "clash", "Unresolved: the documents disagree"
        line = "Documents state different amounts, and no precedence rule applies to pick one. The system refuses to choose."
    elif v.verdict.value == "unresolved":
        cls, mark, word = "amber", "caret", "Unresolved: agreement that could not be tested"
        line = "The amounts match, but they could not be compared on the same terms, and no rule applies."
    else:
        cls, mark, word = "slate", "bracket", "Not in these documents"
        line = "No admitted passage states a value for this."
    return f"""<section class="verdict {cls}" aria-labelledby="vd">
  <h2 id="vd"><span class="st">{_mark(mark)}{E(word)}</span></h2>
  <p>{line}</p>
</section>"""


def _rules(v, info, names) -> str:
    fired = [r for r in v.rules if r.fired and r.name.value in RULE_WORDS]
    if fired:
        r = fired[0]
        gov = _doc_name(v.governing_doc_id, info)
        others = sorted({names[a] for a in v.in_scope if a != v.governing_assertion and names.get(a) != gov})
        if r.name.value == "endorsement_over_base":
            why = (f"{gov} is an endorsement to {' and '.join(others) or 'the base form'}, and both belong to this policy, "
                   "so the endorsement governs over the form it amends.")
        else:
            why = f"{gov} has the latest effective date of the documents issued under this policy, so it governs."
        return f"""<section class="rule" aria-labelledby="rl">
  <h2 id="rl">Rule applied: {E(RULE_WORDS[r.name.value].lower())}</h2>
  <p><strong>{E(gov)} governs.</strong> <span class="why">{E(why)}</span></p>
</section>"""
    policy = v.slot.split(".", 1)[0]
    scope = sorted({names.get(a, a) for a in v.in_scope})
    if len(scope) < 2:
        why = (f"A precedence rule only compares documents issued under the policy in question ({policy}). "
               f"{'Only ' + scope[0] + ' is' if scope else 'None of these documents is'} issued under it; "
               "the others describe it from their own policies, so no rule can rank them.")
    else:
        why = (f"{' and '.join(scope)} are issued under {policy}, but none is an endorsement to another "
               "and their effective dates do not put one after the other.")
    return f"""<section class="rule none" aria-labelledby="rl">
  <h2 id="rl">Neither precedence rule fired</h2>
  <p class="why">{E(why)}</p>
</section>"""


def _assertion(a: Assertion, v, name: str, info, data: Path) -> str:
    governs = a.assertion_id == v.governing_assertion
    side = "Cited against the claim" if a.assertion_id.startswith("attack:") else "Cited for the claim"
    cur = a.amount.currency.value if a.amount.currency else "not stated"
    basis = a.basis.value.replace("_", " ") if a.basis else "not stated"
    routes = "".join(
        f'<li><span class="k">{"Which policy" if r.mapping_id.startswith("identify") else "Which figure"}</span> '
        f'<span class="s s-{r.strength.value}">{E(STRENGTH[r.strength.value])}</span></li>' for r in a.routes)
    return f"""<article class="as{' gov' if governs else ''}">
  <div class="facts">
    <h3>{E(name)}{' <span class="gov-mark">Governs</span>' if governs else ''}</h3>
    <p class="side">{E(side)}</p>
    <dl>
      <dt>States</dt><dd class="num big">{E(a.value.text)}</dd>
      <dt>Currency</dt><dd class="{'ns' if cur == 'not stated' else ''}">{E(cur)}</dd>
      <dt>Basis</dt><dd class="{'ns' if basis == 'not stated' else ''}">{E(basis)}</dd>
    </dl>
    <ul class="routes" aria-label="How it reaches the claim">{routes}</ul>
  </div>
  <figure class="src">{_source(a, info, data)}</figure>
</article>"""


def _pairs(v, names) -> str:
    if not v.pairs:
        return ('<section aria-labelledby="pr"><h2 id="pr">Pairs</h2>'
                '<p class="empty">Only one document states this, so there is nothing to compare.</p></section>')
    rows = []
    for p in v.pairs:
        who_ids = [x.strip() for x in p.detail.replace("not stated by", "").split(",")] if "not stated by" in p.detail else []
        who = " and ".join(names.get(x, x) for x in who_ids) or "one side"
        text = REASON.get(p.reason.value, p.reason.value).format(who=who, detail=p.detail)
        if len(who_ids) > 1:
            text = text.replace(" states no ", " state no ")
        same = {"equal": "same", "different": "different", "not_comparable": "no figure"}[p.value.value]
        rows.append(f"<tr><td>{E(names.get(p.a, p.a))}</td><td>{E(names.get(p.b, p.b))}</td>"
                    f"<td class='num'>{same}</td><td class='{'ok' if p.compared else 'no'}'>{E(text)}</td></tr>")
    return f"""<section aria-labelledby="pr"><h2 id="pr">Every pair of documents</h2>
<div class="tw"><table><thead><tr><th>Document</th><th>Document</th><th>Amounts</th><th>Compared?</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div></section>"""


# ---------------------------------------------------------------- source pane


def _source(a: Assertion, info, data: Path) -> str:
    label, _ = info[a.instrument.doc_id]
    loc = a.citation.locator
    if isinstance(loc, PageQuote):
        png = _pdf_crop(data / "raw" / label.file, loc.page, a.citation.text.split("\n"))
        cap = f"{E(_doc_name(a.instrument.doc_id, info))}, page {loc.page}. Boxed: the cited lines, found on the page by the PDF parser."
        return f'<img src="data:image/png;base64,{png}" alt="Page {loc.page} with the cited lines boxed: {E(" ".join(a.citation.text.split()))}"><figcaption>{cap}</figcaption>'
    assert isinstance(loc, RawOffsets)
    raw = (data / "raw" / label.file).read_bytes().decode("ascii")
    lo = raw.rfind("\n", 0, loc.start)
    for _ in range(3):
        lo = raw.rfind("\n", 0, max(lo, 0))
    hi = loc.end
    for _ in range(3):
        nxt = raw.find("\n", hi + 1)
        hi = len(raw) if nxt == -1 else nxt
    lo = max(lo + 1, 0)
    before, cited, after = raw[lo:loc.start], raw[loc.start:loc.end], raw[loc.end:hi]
    cap = f"{E(_doc_name(a.instrument.doc_id, info))}, raw filing, characters {loc.start:,}–{loc.end:,}. Marked: the cited text."
    return f'<pre class="raw">{E(before)}<mark>{E(cited)}</mark>{E(after)}</pre><figcaption>{cap}</figcaption>'


def _pdf_crop(path: Path, page_no: int, lines: list[str]) -> str:
    with pdfplumber.open(path) as pdf:
        page = pdf.pages[page_no - 1]
        hits = [h for line in lines for h in page.search(line.strip(), regex=False)[:1]]
        if not hits:
            region = (0, 0, page.width, page.height)
        else:
            x0, x1 = min(h["x0"] for h in hits), max(h["x1"] for h in hits)
            top, bottom = min(h["top"] for h in hits), max(h["bottom"] for h in hits)
            # crop to the whole column holding the block, so no visible word is cut at the edge
            mid = page.width / 2
            left, right = (mid - 6, page.width - 24) if x0 >= mid - 20 else (24, mid + 6)
            region = (max(0, min(left, x0 - 4)), max(0, top - 56), min(page.width, max(right, x1 + 4)), min(page.height, bottom + 56))
        im = page.crop(region).to_image(resolution=144)
        for h in hits:
            im.draw_rect((h["x0"] - 2, h["top"] - 1.5, h["x1"] + 2, h["bottom"] + 1.5),
                         fill=(207, 227, 238, 60), stroke=(22, 54, 201), stroke_width=3)
        buf = io.BytesIO()
        im.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


# ---------------------------------------------------------------- helpers


def _doc_name(doc_id: str | None, info) -> str:
    if doc_id is None or doc_id not in info:
        return doc_id or "—"
    _, i = info[doc_id]
    kind = i.instrument_type.value.replace("_", " ")
    known = {"ho_00_03": "HO 00 03 (base form)", "ho_00_15": "HO 00 15 (endorsement)"}
    number = f" {', '.join(i.policy_numbers)}" if i.policy_numbers else ""
    return known.get(doc_id, f"{i.issuer}, {kind}{number}")


def _mark(kind: str) -> str:
    paths = {
        "tick": '<path d="M3.5 13.2C5.6 15 7.2 16.8 8.6 19.6 11.4 12.6 15.4 7.2 20.8 3.8"/>',
        "clash": '<path class="c1" d="M3 6l7 7"/><path class="c2" d="M14 6l7 7M14 13l7-7"/>',
        "caret": '<path d="M5 15l7-8 7 8"/>',
        "bracket": '<path d="M9 4H5v16h4M15 4h4v16h-4"/>',
    }
    return (f'<svg class="mark m-{kind}" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{paths[kind]}</svg>')


def _page(title: str, body: str) -> str:
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{E(title)}</title>
<link rel="stylesheet" href="/web/tokens.css"><link rel="stylesheet" href="/web/result.css">
</head><body><main>{body}</main>
<script>
(function () {{
  function post() {{ parent.postMessage({{ type: "proofgraph-layout", height: document.documentElement.scrollHeight, sections: [] }}, location.origin); }}
  addEventListener("load", post); addEventListener("resize", post);
}})();
</script></body></html>"""
