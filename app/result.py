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
import threading
from pathlib import Path
from urllib.parse import urlparse

import pdfplumber

from proofgraph.pipeline import PacketRun
from proofgraph.schema import Assertion, PageQuote, RawOffsets, SourceManifest

E = html.escape
# pdfium (pdfplumber's renderer) is not thread-safe: concurrent renders abort the process (seen as exit 134
# when a browser fetched four crops at once). Every page render goes through this lock.
_RENDER = threading.Lock()

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


def render(run: PacketRun, data: Path, title: str, question: str | None = None, rerun: str | None = None) -> str:
    """One screen, read like a report: question, claim, answer, why. The chain sits collapsed below it."""
    manifest = SourceManifest.model_validate_json((data / "instruments.json").read_text(encoding="utf-8"))
    info = {i.doc_id: (s, i) for s in manifest.sources for i in s.instruments}
    v = run.verdict
    names = {a.assertion_id: _doc_name(a.instrument.doc_id, info) for a in run.assertions}

    if run.failure or v is None:
        body = f'<p class="fail">The check stopped: {E(run.failure or "no verdict")}. Nothing after this point was read.</p>'
        return _page(title, body)
    names.update({c.clause_id: _doc_name(c.doc_id, info) for c in v.clauses})  # wording claims rank clauses, not amounts

    claim = E(run.claim.text)
    if v.claim_value and E(v.claim_value) in claim:
        claim = claim.replace(E(v.claim_value), f"<b>{E(v.claim_value)}</b>", 1)
    head = f"""<header class="q">
  <p class="q-label">Question</p>
  <h1>{E(question or run.claim.slot)}</h1>
  <p class="claim"><span class="q-label">Claim</span> {claim}</p>
</header>"""
    rows = "".join(_assertion(a, v, names[a.assertion_id], info, data) for a in run.assertions) or \
        ('<p class="empty">This claim is about wording, so no amount was read. The clauses are quoted below.</p>'
         if v.verdict.value == "quoted" else '<p class="empty">None of these documents states an amount for this. Nothing was cited.</p>')
    chain = f"""<details class="chain">
  <summary>How this was decided: what the model saw, the checks for and against, and the rule</summary>
  {_admitted(run, v, info)}
  {_rules(v, info, names)}
  <section aria-labelledby="ev"><h2 id="ev">What each document states, and where</h2>
  <p class="why">The claim was checked twice, once for evidence that supports it and separately for evidence against it. Each check saw only the claim and the passages it was allowed to see. The model found and quoted; code read every amount and checked every quote against the file. Each step is <strong>read</strong> off the page, <strong>derived</strong> by code, or a <strong>judgment</strong> (the model&rsquo;s reading or a person&rsquo;s identification); a judgment step still rests on a quote checked against the file.</p>{rows}</section>
  {_pairs(v, names, {a.assertion_id: a for a in run.assertions}) if v.verdict.value != "quoted" else _clauses(v, info)}
</details>"""
    body = f"""{head}
{_answer(run, v, names, info, data)}
{chain}
{_footer(run, info, rerun)}"""
    return _page(title, body)


# ---------------------------------------------------------------- the answer, then why

ANSWER = {
    "supported": ("green", "tick", "The claim is right."),
    "contradicted": ("red", "circle", "The claim is wrong."),
    "unresolved": ("clash", "clash", "This can\u2019t be settled from these documents."),
    "not_found": ("clash", "clash", "This can\u2019t be settled from these documents."),
    "quoted": ("slate", "bracket", "Quoted, not checked."),
}
RULE_WHY = {"endorsement_over_base": "an endorsement overrides the form it changes where they differ",
            "later_effective_date": "a later effective date overrides an earlier one"}


def _answer(run, v, names, info, data: Path) -> str:
    cls, mark, word = ANSWER[v.verdict.value]
    gov = next((a for a in run.assertions if a.assertion_id == v.governing_assertion), None)
    gov_name = _doc_name(v.governing_doc_id, info) if v.governing_doc_id else None
    rule = RULE_WHY.get(v.governing_rule.value) if v.governing_rule else None
    verdict = v.verdict.value
    if verdict in ("supported", "contradicted"):
        lead = f"<strong>{E(gov_name)} controls</strong>" if gov_name else "<strong>The documents that state it agree</strong>"
        if rule:
            others = sorted({names[a] for a in v.in_scope if a in names and a != v.governing_assertion and names[a] != gov_name})
            lead += f" over {E(' and '.join(others))}: {E(rule)}." if others else f": {E(rule)}."
        else:
            lead += "."
        amounts = (f'<div class="amounts"><div><span class="q-label">The claim says</span><span class="amt">{E(v.claim_value or "")}</span></div>'
                   f'<div><span class="q-label">{E(gov_name or "The documents")} {"state" if not gov_name else "states"}</span>'
                   f'<span class="amt">{E(v.governing_value or "")}</span></div></div>')
        why = f'<p class="why-line">{lead}</p>{amounts}'
    elif verdict == "quoted":
        q = v.quoted
        why = (f'<p class="why-line">A claim about wording is not judged. Here is the clause that controls, quoted with its page, for a person to read.'
               f'{" " + E(v.unresolved_detail) if v.unresolved_detail and not q else ""}</p>')
        if v.clashes:
            why += ('<p class="why-line clash-note">The check for evidence against the claim found a clause that may read differently. That is the model&rsquo;s '
                    'reading, a judgment, and it is shown in full below, never as a verdict.</p>')
    else:
        reason = v.unresolved_reason.value if v.unresolved_reason else "no_addressing_span"
        head = {"documents_disagree": "The documents state different amounts, and no rule says which one controls.",
                "amounts_not_comparable": "The amounts cannot be compared.",
                "governing_instrument_absent": "A document needed to decide this is missing.",
                "no_addressing_span": "None of these documents addresses this question."}[reason]
        detail = (_absent_detail(v, info) if reason == "governing_instrument_absent"
                  else "" if reason == "documents_disagree" else _human(v.unresolved_detail or "", names))
        states = "".join(f"<li><strong>{E(names[a.assertion_id])}</strong> states <span class='num'>{E(a.value.text)}</span></li>"
                         for a in run.assertions)
        why = f'<p class="why-line"><strong>{E(head)}</strong> {E(detail)}</p>' + (f'<ul class="states">{states}</ul>' if states else "")
    shown = gov
    if verdict == "quoted" and v.quoted:
        shown = next((a for a in run.assertions if a.instrument.doc_id == v.quoted.doc_id), None)
    pane = ""
    if shown is not None:
        pane = f'<figure class="src lead-src">{_source(shown, info, data)}</figure>'
    elif verdict == "quoted" and v.quoted and info[v.quoted.doc_id][0].file.endswith(".pdf"):
        q = v.quoted
        png = _pdf_crop(data / "raw" / info[q.doc_id][0].file, q.page, q.text.split("\n"))
        pane = (f'<figure class="src lead-src"><img src="data:image/png;base64,{png}" alt="Page {q.page} with the quoted lines boxed">'
                f'<figcaption>{E(_doc_name(q.doc_id, info))}, page {q.page}. Boxed: the quoted clause. Quoted, not checked.</figcaption></figure>')
    elif verdict == "quoted" and v.quoted:
        pane = (f'<blockquote class="says lead-quote"><span class="ref">{E(_doc_name(v.quoted.doc_id, info))}, page {v.quoted.page}</span>'
                f'{E(" ".join(v.quoted.text.split()))}</blockquote>')
    return f"""<section class="verdict {cls}" aria-labelledby="vd">
  <h2 id="vd"><span class="st">{_mark(mark)}{E(word)}</span></h2>
  {why}
  {pane}
  <p class="not-opinion">{"A quotation of the controlling clause" if verdict == "quoted" else "A comparison of the amounts the documents state"}, not a coverage opinion or legal advice.</p>
</section>"""


def _human(text: str, names: dict) -> str:
    """Internal ids out, document names in: nothing on the page should need the code to read it."""
    import re
    text = re.sub(r"\s*\(?in scope: \[[^\]]*\]\)?", "", text)
    for aid in sorted(names, key=len, reverse=True):
        text = text.replace(aid, names[aid])
    return re.sub(r"\b(support|attack):[\w:]+", "a cited document", text).replace("_", " ")


def _clauses(v, info) -> str:
    items = "".join(
        f'<li><strong>{E(_doc_name(c.doc_id, info))}, page {c.page}</strong> '
        f'<span class="s s-{c.strength.value}">{E(STRENGTH[c.strength.value])}</span>'
        f'{" &middot; found by the check against the claim" if c.side.value == "attack" else ""}'
        f'<blockquote class="says">{E(" ".join(c.text.split()))}</blockquote><p class="why">{E(c.reading)}</p></li>' for c in v.clauses)
    return f"""<section aria-labelledby="cl"><h2 id="cl">Every clause the checks quoted</h2>
<p class="why">Shown as quoted. A clause found by the check against the claim is the model&rsquo;s reading, marked as a judgment, never a verdict.</p>
<ul class="clauses">{items}</ul></section>"""


def _absent_detail(v, info) -> str:
    gone = [c for c in v.amends_checks if c.outcome == "absent"]
    if not gone:
        return v.unresolved_detail or ""
    c = gone[0]
    return (f"{_doc_name(c.doc_id, info)} changes {c.amends}, and {c.amends} is not among these documents. "
            f"Without it there is nothing to apply the changes to, so the final amount cannot be known. Add {c.amends} and run it again.")


def _admitted(run, v, info) -> str:
    rows = "".join(f"<tr><td>{E(_doc_name(d, info))}</td><td class='num'>{n}</td></tr>" for d, n in run.documents)
    ex = [c for c in v.amends_checks if c.outcome == "excluded"]
    note = "".join(f"<li>{E(_doc_name(c.doc_id, info))} changes {E(c.amends)}{'' if c.amends == c.amends_policy else ', part of policy ' + E(c.amends_policy)}, "
                   f"which is not among these documents. That is another policy, not this question&rsquo;s "
                   f"({E(', '.join(v.policies))}), so its absence does not affect this answer. It is listed here rather than dropped.</li>" for c in ex)
    return f"""<section aria-labelledby="ad"><h2 id="ad">What the model was allowed to see</h2>
<p class="why">Decided by code before the model was called: only documents a person recorded as belonging to {E(', '.join(v.policies) or 'this policy')}, and only the part of each that applies.</p>
<div class="tw"><table><thead><tr><th>Document</th><th>Passages it could see</th></tr></thead><tbody>{rows}</tbody></table></div>
{f'<ul class="skipped">{note}</ul>' if note else ''}</section>"""


def _footer(run, info, rerun) -> str:
    docs = [d for d, _ in run.documents] or [a.instrument.doc_id for a in run.assertions]
    files = []
    for d in dict.fromkeys(docs):
        if d in info:
            label, _ = info[d]
            src = (f' <a href="{E(label.url)}" target="_blank" rel="noopener">Open the original</a> '
                   f'<span class="src-host">({E(urlparse(label.url).netloc.removeprefix("www."))})</span>.') if label.url else ""
            files.append(f"<li>{E(_doc_name(d, info))}: <code>{E(label.file)}</code> sha256 <code>{E(label.sha256_of_file[:16])}…</code>, extractor <code>{E(label.extractor.value)}</code>.{src}</li>")
    again = f' <a href="{E(rerun)}" target="_top">Re-run this check</a>.' if rerun else ""
    return f"""<footer>
  <p><strong>Who wrote what.</strong> A person wrote the claim, its question and which policy each document describes. The model read only the passages it was allowed to see, and quoted; code read every amount, compared, applied the rules and checked every quote against the file.</p>
  <ul class="files">{''.join(files)}</ul>
  <p>Commit <code>{E(_COMMIT)}</code>.{again}</p>
</footer>"""


def _commit() -> str:
    import subprocess
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=2,
                              cwd=Path(__file__).parent).stdout.strip() or "unknown"
    except Exception:
        return "unknown"


_COMMIT = _commit()


def _rules(v, info, names) -> str:
    fired = [r for r in v.rules if r.fired and r.name.value in RULE_WORDS]
    if fired:
        r = fired[0]
        gov = _doc_name(v.governing_doc_id, info)
        others = sorted({names[a] for a in v.in_scope if a in names and a != v.governing_assertion and names[a] != gov})
        if r.name.value == "endorsement_over_base":
            why = (f"{gov} changes {' and '.join(others) or 'the base form'}, and both belong to this policy, "
                   "so the endorsement overrides the form it changes.")
        else:
            why = f"{gov} has the latest effective date of the documents issued under this policy, so it controls."
        return f"""<section class="rule" aria-labelledby="rl">
  <h2 id="rl">Rule applied: {E(RULE_WORDS[r.name.value].lower())}</h2>
  <p><strong>{E(gov)} controls.</strong> <span class="why">{E(why)}</span></p>
</section>"""
    policy = v.slot.split(".", 1)[0]
    scope = sorted({names.get(a, a) for a in v.in_scope})
    if len(scope) < 2:
        why = (f"The rules only rank documents issued under the policy in question ({policy}). "
               f"{'Only ' + scope[0] + ' is' if scope else 'None of these documents is'} issued under it; "
               "the others describe it from their own policies, so no rule can rank them.")
    else:
        why = (f"{' and '.join(scope)} are issued under {policy}, but none is an endorsement to another "
               "and their effective dates do not put one after the other.")
    return f"""<section class="rule none" aria-labelledby="rl">
  <h2 id="rl">Neither rule applied</h2>
  <p class="why">{E(why)}</p>
</section>"""


def _weakest_label(a: Assertion) -> str:
    r = next(r for r in a.routes if r.strength is a.weakest)
    which = "which policy" if r.mapping_id.startswith("identify") else "which figure"
    return f"{which}, {STRENGTH[r.strength.value]}"


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
      <dt>Basis <small>(each loss, each claim, aggregate)</small></dt><dd class="{'ns' if basis == 'not stated' else ''}">{E(basis)}</dd>
    </dl>
    <ul class="routes" aria-label="How it reaches the claim">{routes}</ul>
    <p class="weakest">Weakest step: {E(_weakest_label(a))}. Check this one first.</p>
  </div>
  <figure class="src">{_source(a, info, data)}</figure>
</article>"""


def _pairs(v, names, by=None) -> str:
    if not v.pairs:
        return ('<section aria-labelledby="pr"><h2 id="pr">Comparisons</h2>'
                '<p class="empty">Only one document states this, so there is nothing to compare.</p></section>')
    rows = []
    for p in v.pairs:
        who_ids = [x.strip() for x in p.detail.replace("not stated by", "").split(",")] if "not stated by" in p.detail else []
        who = " and ".join(names.get(x, x) for x in who_ids) or "one side"
        text = REASON.get(p.reason.value, p.reason.value).format(who=who, detail=p.detail)
        x, y = (by or {}).get(p.a), (by or {}).get(p.b)
        if p.reason.value in ("equal", "different") and x is not None and y is not None:
            amt = "same amount" if p.reason.value == "equal" else "different amounts"
            cur = "same currency" if x.amount.currency else "neither states a currency"
            bas = "same basis" if x.basis else "neither states a basis"
            text = f"compared: {amt}; {cur}; {bas}"
        if len(who_ids) > 1:
            text = text.replace(" states no ", " state no ")
        same = {"equal": "same", "different": "different", "not_comparable": "no figure"}[p.value.value]
        rows.append(f"<tr><td>{E(names.get(p.a, p.a))}</td><td>{E(names.get(p.b, p.b))}</td>"
                    f"<td class='num'>{same}</td><td class='{'ok' if p.compared else 'no'}'>{E(text)}</td></tr>")
    return f"""<section aria-labelledby="pr"><h2 id="pr">Every comparison between two documents</h2>
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


def crop_png(path: Path, page_no: int, lines: list[str], boxed: bool = True, pad: tuple[int, int] = (56, 56),
             full_width: bool = False) -> bytes:
    """A real crop of a PDF page around `lines`, to the whole column, cited lines boxed if `boxed`.

    Rendered at request time from the PDF in data/raw. Nothing is stored in the repository.
    """
    with _RENDER, pdfplumber.open(path) as pdf:
        page = pdf.pages[page_no - 1]
        hits = [h for line in lines for h in page.search(line.strip(), regex=False)[:1]]
        if not hits:
            region = (0, 0, page.width, page.height)
        else:
            x0, x1 = min(h["x0"] for h in hits), max(h["x1"] for h in hits)
            top, bottom = min(h["top"] for h in hits), max(h["bottom"] for h in hits)
            mid = page.width / 2
            left, right = (24, page.width - 24) if full_width else ((mid - 6, page.width - 24) if x0 >= mid - 20 else (24, mid + 6))
            region = (max(0, min(left, x0 - 4)), max(0, top - pad[0]), min(page.width, max(right, x1 + 4)), min(page.height, bottom + pad[1]))
        im = page.crop(region).to_image(resolution=144)
        if boxed:
            for h in hits:
                im.draw_rect((h["x0"] - 2, h["top"] - 1.5, h["x1"] + 2, h["bottom"] + 1.5),
                             fill=(207, 227, 238, 60), stroke=(22, 54, 201), stroke_width=3)
        buf = io.BytesIO()
        im.save(buf, format="PNG")
    return buf.getvalue()


def _pdf_crop(path: Path, page_no: int, lines: list[str]) -> str:
    return base64.b64encode(crop_png(path, page_no, lines)).decode("ascii")


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
        "clash": '<path class="c1" d="M4.6 4.8c4.6 4.4 9.6 9.6 14.6 14.6"/><path class="c2" d="M19.2 4.6C14.6 9.2 9.6 14.4 4.8 19.4"/>',
        "caret": '<path d="M5 15l7-8 7 8"/>',
        "bracket": '<path d="M9 4H5v16h4M15 4h4v16h-4"/>',
        "circle": '<path d="M12.4 3.1C6.8 2.4 2.7 7 3.3 12.5c.6 5.5 6.2 8.7 11.2 7.5 5-1.2 7.1-6 6-10.4-1-4-4.8-6.3-9.4-5.8"/>',
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
