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
import json
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
    "currency_country_not_printed": "not compared: one side prints only \"$\", dollars with no country, the other a named currency ({detail})",
}
CURRENCY_SOURCE = {"claimant": "written in the claim", "set_at_confirmation": "set at confirmation, not written by the claimant",
                   "dollars_country_not_printed": "\"$\" as written: dollars, country not printed", "not_stated": "not stated"}


def _currency(c) -> str:
    """How a currency reads on the page. "$" names no country (D12)."""
    if c is None:
        return "not stated"
    return "dollars, country not printed" if c.value == "dollars_country_not_printed" else c.value
RULE_WORDS = {
    "endorsement_over_base": "Endorsement over base form",
    "later_effective_date": "Later effective date over earlier",
}
STRENGTH = {"read": "read in the document", "derived": "derived mechanically", "judgment": "a judgment"}


def render(run: PacketRun, data: Path, title: str, question: str | None = None, rerun: str | None = None,
           record: dict | None = None, review_id: str | None = None, approval: dict | None = None) -> str:
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
    shown = (record or {}).get("amount_as_written") or v.claim_value  # a typed claim bolds what was typed
    if shown and E(shown) in claim:
        claim = claim.replace(E(shown), f"<b>{E(shown)}</b>", 1)
    head = f"""<header class="q">
  <p class="q-label">Question</p>
  <h1>{E(question or run.claim.slot)}</h1>
  <p class="claim"><span class="q-label">Claim</span> {claim}</p>
</header>"""
    rows = "".join(_assertion(a, v, names[a.assertion_id], info, data, record is not None) for a in run.assertions) or \
        ('<p class="empty">This claim is about wording, so no amount was read. The clauses are quoted below.</p>'
         if v.verdict.value == "quoted" else '<p class="empty">None of these documents states an amount for this. Nothing was cited.</p>')
    chain = f"""<details class="chain">
  <summary>How this was decided: what the model saw, the checks for and against, and the rule</summary>
  {_admitted(run, v, info)}
  {_rules(v, info, names)}
  <section aria-labelledby="ev"><h2 id="ev">What each document states, and where</h2>
  <p class="why">Two separate checks, for and against the claim. The model quoted; code read every amount and checked every quote against the file. Each step is <strong>read</strong> (off the page), <strong>derived</strong> (by code) or <strong>judgment</strong> (the model&rsquo;s or a person&rsquo;s call, still resting on a checked quote).</p>{rows}</section>
  {_pairs(v, names, {a.assertion_id: a for a in run.assertions}) if v.verdict.value != "quoted" else _clauses(v, info)}
</details>"""
    body = f"""{head}
{_answer(run, v, names, info, data, record is not None)}
{_how_set(record) if record else ""}
{chain}
{_footer(run, info, rerun, record, review_id, approval)}"""
    return _page(title, body, review_id)


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


def _answer(run, v, names, info, data: Path, confirmed: bool = False) -> str:
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
        why = (f'<p class="why-line">Wording isn&rsquo;t judged. Here is the controlling clause, with its page, for a person to read.'
               f'{" " + E(v.unresolved_detail) if v.unresolved_detail and not q else ""}</p>')
        if v.clashes:
            why += ('<p class="why-line clash-note">The check against the claim found a clause that may read differently: the model&rsquo;s '
                    'judgment, shown below, never a verdict.</p>')
    else:
        reason = v.unresolved_reason.value if v.unresolved_reason else "no_addressing_span"
        head = {"documents_disagree": "The documents state different amounts, and no rule says which one controls.",
                "amounts_not_comparable": "The amounts cannot be compared.",
                "governing_instrument_absent": "A document needed to decide this is missing.",
                "no_addressing_span": "None of these documents addresses this question."}[reason]
        detail = (_absent_detail(v, info) if reason == "governing_instrument_absent"
                  else "" if reason == "documents_disagree"
                  else _not_comparable(v, run.assertions, names) if reason == "amounts_not_comparable"
                  else _human(v.unresolved_detail or "", names))
        states = "".join(f"<li><strong>{E(names[a.assertion_id])}</strong> states <span class='num'>{E(a.value.text)}</span></li>"
                         for a in run.assertions)
        why = f'<p class="why-line"><strong>{E(head)}</strong> {E(detail)}</p>' + (f'<ul class="states">{states}</ul>' if states else "")
    shown = gov
    if shown is None and verdict in ("unresolved", "not_found") and run.assertions:
        shown = run.assertions[0]  # a lead quote here too: the first cited page
    if verdict == "quoted" and v.quoted:
        shown = next((a for a in run.assertions if a.instrument.doc_id == v.quoted.doc_id), None)
    pane = ""
    pair = _precedence_pair(run, v, names, info, data) if verdict in ("supported", "contradicted") else ""
    if pair:
        pane = pair
    elif shown is not None:
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
  {_attack_line(run, names) if verdict != "quoted" else ""}
  {pane}
  <p class="not-opinion">{"A quotation of the controlling clause" if verdict == "quoted" else "A comparison of the amounts the documents state"}, not a coverage opinion or legal advice.</p>
</section>"""


def _attack_line(run, names) -> str:
    found = [a for a in run.assertions if a.assertion_id.startswith("attack:")]
    if not found:
        return '<p class="check-line">The check against the claim found nothing that disagrees.</p>'
    items = "; ".join(f"{E(names[a.assertion_id])} states {E(a.value.text)}" for a in found)
    return f'<p class="check-line">The check against the claim found {len(found)} line{"" if len(found) == 1 else "s"}: {items}.</p>'


def _precedence_pair(run, v, names, info, data: Path) -> str:
    """When a precedence rule fired: the governing page and the overridden page, side by side, each captioned."""
    if not v.governing_rule or v.governing_rule.value not in RULE_WORDS:
        return ""
    gov = next((a for a in run.assertions if a.assertion_id == v.governing_assertion), None)
    if gov is None:
        return ""
    over = next((a for a in run.assertions if a.assertion_id != gov.assertion_id and a.instrument.doc_id != gov.instrument.doc_id
                 and a.assertion_id in v.in_scope), None)
    if over is None:
        return ""

    def cap(a, word):
        loc = a.citation.locator
        page = f", page {loc.page}" if isinstance(loc, PageQuote) else ""
        return f"{word}: {E(names[a.assertion_id])}{page}"
    return (f'<div class="precedence" aria-label="The proof of precedence">'
            f'<figure class="src lead-src"><p class="pc-cap controls">{cap(gov, "Controls")}</p>{_source(gov, info, data)}</figure>'
            f'<figure class="src lead-src"><p class="pc-cap overridden">{cap(over, "Overridden")}</p>{_source(over, info, data)}</figure></div>')


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
<p class="why">Quoted as found. Clauses from the check against the claim are the model&rsquo;s judgment, never a verdict.</p>
<ul class="clauses">{items}</ul></section>"""


def _not_comparable(v, assertions, names) -> str:
    """One plain sentence: which document leaves out the currency or the basis, or whose bases differ."""
    by = {a.assertion_id: a for a in assertions}
    involved = {x for p in v.pairs if not p.compared and p.value.value == "equal" for x in (p.a, p.b) if x in by}
    if not involved:  # the claim against the governing value
        return _human(v.unresolved_detail or "", names)
    who = lambda pred: sorted({names[i] for i in involved if pred(by[i])})
    parts = []
    if no_cur := who(lambda a: a.amount.currency is None):
        parts.append(f"{' and '.join(no_cur)} {'states' if len(no_cur) == 1 else 'state'} no currency")
    if no_basis := who(lambda a: a.basis is None):
        parts.append(f"{' and '.join(no_basis)} {'states' if len(no_basis) == 1 else 'state'} no basis")
    dollars = who(lambda a: a.amount.currency is not None and a.amount.currency.value == "dollars_country_not_printed")
    named = sorted({by[i].amount.currency.value for i in involved if by[i].amount.currency is not None
                    and by[i].amount.currency.value != "dollars_country_not_printed"})
    if dollars and named:
        parts.append(f"{' and '.join(dollars)} {'prints' if len(dollars) == 1 else 'print'} only \"$\" (dollars, no country) "
                     f"against {', '.join(named)}")
    bases = sorted({a.basis.value.replace('_', ' ') for i in involved if (a := by[i]).basis})
    if len(bases) > 1:
        parts.append(f"the bases differ ({' vs '.join(bases)})")
    return "They agree on the digits, but " + "; ".join(parts) + "." if parts else _human(v.unresolved_detail or "", names)


def _absent_detail(v, info) -> str:
    gone = [c for c in v.amends_checks if c.outcome == "absent"]
    if not gone:
        return v.unresolved_detail or ""
    c = gone[0]
    return (f"{_doc_name(c.doc_id, info)} changes {c.amends}, and {c.amends} is not among these documents. "
            f"Without it the final amount can&rsquo;t be known. Add {c.amends} and run again.")


def _admitted(run, v, info) -> str:
    rows = "".join(f"<tr><td>{E(_doc_name(d, info))}</td><td class='num'>{n}</td></tr>" for d, n in run.documents)
    ex = [c for c in v.amends_checks if c.outcome == "excluded"]
    note = "".join(f"<li>{E(_doc_name(c.doc_id, info))} changes {E(c.amends)}{'' if c.amends == c.amends_policy else ', part of policy ' + E(c.amends_policy)}, "
                   f"which isn&rsquo;t here. It belongs to another policy, not "
                   f"{E(', '.join(v.policies))}, so it doesn&rsquo;t affect this answer. Listed, not dropped.</li>" for c in ex)
    return f"""<section aria-labelledby="ad"><h2 id="ad">What the model was allowed to see</h2>
<p class="why">Set by code before the model ran: only documents a person assigned to {E(', '.join(v.policies) or 'this policy')}, only the parts that apply.</p>
<div class="tw"><table><thead><tr><th>Document</th><th>Passages it could see</th></tr></thead><tbody>{rows}</tbody></table></div>
{f'<ul class="skipped">{note}</ul>' if note else ''}</section>"""


def _footer(run, info, rerun, record=None, review_id=None, approval=None) -> str:
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
  <p><strong>Who wrote what.</strong> A person: the claim, and which policy each document belongs to. The model: quotes from the passages it was shown. Code: amounts, comparisons, rules, and checking every quote against the file.</p>
  <ul class="files">{''.join(files)}</ul>
  {_record_line(record) if record else ""}
  {_approval(review_id, approval)}
  <p>Commit <code>{E(_commit())}</code>.{again}</p>
  <p class="keep">This result is saved on the server that ran it; the link works for as long as that server keeps it.</p>
</footer>"""


def _approval(review_id, approval) -> str:
    if approval:
        return f'<p class="approved"><strong>Approved by {E(approval["approved_by"])}, {E(approval["approved_at"])}.</strong></p>'
    if not review_id:
        return ""
    return """<form class="approve" id="approve-form" novalidate>
  <label for="approver"><strong>Approved by</strong></label>
  <input id="approver" name="approved_by" type="text" autocomplete="name" placeholder="Your name">
  <button class="btn" type="submit">Approve</button>
  <p class="approve-msg" id="approve-msg" role="status"></p>
</form>"""


GROUPING = {"person": "confirmed by a person", "prefilled_from_mapping": "pre-filled from a mapping row"}
VALUE_SOURCE = {"verified_quote": "read from the verified line", "set_at_confirmation": "picked at confirmation by a person, not read by code"}
BASIS_SOURCE = {"claimant": "written in the claim", "set_at_confirmation": "set at confirmation, not written by the claimant",
                "not_stated": "not stated"}


def _record_line(r: dict) -> str:
    """D11: how this question was set, recorded on every typed-claim run. A short definition list; every fact kept."""
    mode = GROUPING.get(r["grouping_mode"], r["grouping_mode"]) + (f" (row {r['mapping_row']})" if r.get("mapping_row") else "")
    pol = (f"found in the claim (&ldquo;{E(r['policy'])}&rdquo;), shown and accepted" if r["policy_source"] == "matched_in_claim"
           else "the only one in these documents" if r["policy_source"] == "only_in_packet" else "chosen by the person")
    docs = ("Documents", "uploaded and checked as one set") if r["policy"] == "Uploaded set" else (f"Policy {E(r['policy'])}", pol)
    figure = (E(VALUE_SOURCE.get(r.get("value_source", "verified_quote"), r.get("value_source", "")))
              + "".join(" (" + E(x["figure"]) + " in &ldquo;" + E(x["line"]) + "&rdquo;)" for x in r.get("value_set", [])))
    cur = (E(CURRENCY_SOURCE.get(r.get("currency_source", "claimant"), r.get("currency_source", "")))
           + (" (" + E(r["currency_set"]) + ")" if r.get("currency_set") else ""))
    rows = [("Grouping", E(mode)),
            ("Confirmed by", E(r["confirmed_by"]) + (", " + E(r["confirmed_on"]) if r.get("confirmed_on") else "")),
            (docs[0], docs[1]),
            ("Basis", E(BASIS_SOURCE.get(r["basis_source"], r["basis_source"]))),
            ("Currency", cur), ("Figure", figure),
            ("Question key", f"<code>{E(r['question'])}</code>, from the printed line &ldquo;{E(r['label_from'])}&rdquo;")]
    return ('<div class="record"><p><strong>How this question was set.</strong></p><dl class="record-dl">'
            + "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in rows) + "</dl></div>")


def _how_set(r: dict) -> str:
    """Under the answer: what code read from the claim, the lines a person set aside, documents with nothing found."""
    read = (f'You wrote <b>{E(r["amount_as_written"])}</b>; code read <b>{E(r["claim_value_compared"])}</b>.'
            if r.get("amount_as_written") else "A claim about wording: nothing to read as an amount.")
    basis = " The basis was set at confirmation, not written by the claimant." if r["basis_source"] == "set_at_confirmation" else ""
    if r.get("currency_source") == "set_at_confirmation":
        basis += f" The currency ({r['currency_set']}) was set at confirmation: the claim wrote \"$\", which names no country."
    for x in r.get("value_set", []):
        basis += f" The figure {E(x['figure'])} was picked at confirmation: the line states several amounts ({E(', '.join(x['figures']))})."
    dropped = "".join(f'<li><strong>{E(x["doc"])}</strong>: set aside by a person, because &ldquo;{E(x["reason"])}&rdquo;'
                      f'<blockquote class="says">{E(" ".join(x["text"].split()))}</blockquote></li>' for x in r["dropped"])
    nothing = "".join(f"<li>{E(x)}: nothing found</li>" for x in r["nothing_found"])
    return f"""<section class="how-set" aria-labelledby="hs"><h2 id="hs">How this question was set</h2>
<p>{read}{basis} {E(GROUPING.get(r["grouping_mode"], r["grouping_mode"])).capitalize()}: {E(r["confirmed_by"])}.</p>
{f'<ul class="set-aside">{dropped}</ul>' if dropped else '<p class="why">No line was set aside.</p>'}
{f'<ul class="nothing">{nothing}</ul>' if nothing else ''}
</section>"""


_COMMIT_CACHE: tuple[float, str] = (0.0, "")


def _commit() -> str:
    """The commit at render time, plus " (with uncommitted changes)" when the tree is dirty. Cached a few seconds."""
    import subprocess
    import time
    global _COMMIT_CACHE
    now = time.monotonic()
    if _COMMIT_CACHE[1] and now - _COMMIT_CACHE[0] < 5:
        return _COMMIT_CACHE[1]
    cwd = Path(__file__).parent
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=2, cwd=cwd).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, timeout=2, cwd=cwd).stdout.strip()) if sha else False
        out = (sha + (" (with uncommitted changes)" if dirty else "")) if sha else "unknown"
    except Exception:
        out = "unknown"
    _COMMIT_CACHE = (now, out)
    return out


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
        why = (f"Rules only rank documents issued under {policy}. "
               f"{'Only ' + scope[0] + ' is' if scope else 'None of these documents is'} issued under it; "
               "the others come from other policies, so nothing to rank.")
    else:
        why = (f"{' and '.join(scope)} are issued under {policy}, but none endorses another "
               "and no effective date is later.")
    return f"""<section class="rule none" aria-labelledby="rl">
  <h2 id="rl">Neither rule applied</h2>
  <p class="why">{E(why)}</p>
</section>"""


def _weakest_label(a: Assertion, confirmed: bool = False) -> str:
    r = next(r for r in a.routes if r.strength is a.weakest)
    policy = r.mapping_id.startswith("identify")
    if policy and confirmed:  # a person confirmed the policy: not an unreviewed judgment
        return "Which policy: confirmed by a person"
    which = "which policy" if policy else "which figure"
    return f"{which}, {STRENGTH[r.strength.value]}"


def _assertion(a: Assertion, v, name: str, info, data: Path, confirmed: bool = False) -> str:
    governs = a.assertion_id == v.governing_assertion
    side = "Cited against the claim" if a.assertion_id.startswith("attack:") else "Cited for the claim"
    cur = _currency(a.amount.currency)
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
    <p class="weakest">{"Weakest step: " if not _weakest_label(a, confirmed).startswith("Which policy:") else ""}{E(_weakest_label(a, confirmed))}. Check this one first.</p>
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
    if tuple(i.policy_numbers) == ("Uploaded set",):  # uploads checked as one set: the name is what is printed on it
        return i.issuer
    number = f" {', '.join(i.policy_numbers)}" if i.policy_numbers else ""
    return known.get(doc_id, f"{i.issuer}, {kind}{number}")


def _mark(kind: str) -> str:
    paths = {
        "tick": '<path d="M3.5 13.2C5.6 15 7.2 16.8 8.6 19.6 11.4 12.6 15.4 7.2 20.8 3.8"/>',
        "clash": '<path d="M5 9h14M5 15h14M15 5L9 19"/>',
        "caret": '<path d="M5 15l7-8 7 8"/>',
        "bracket": '<path d="M9 4H5v16h4M15 4h4v16h-4"/>',
        "circle": '<path d="M12.4 3.1C6.8 2.4 2.7 7 3.3 12.5c.6 5.5 6.2 8.7 11.2 7.5 5-1.2 7.1-6 6-10.4-1-4-4.8-6.3-9.4-5.8"/>',
    }
    return (f'<svg class="mark m-{kind}" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{paths[kind]}</svg>')


def _page(title: str, body: str, review_id: str | None = None) -> str:
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{E(title)}</title>
<link rel="stylesheet" href="/web/tokens.css"><link rel="stylesheet" href="/web/result.css">
</head><body><main>{body}</main>
<script>
(function () {{
  function post() {{ parent.postMessage({{ type: "proofgraph-layout", height: document.documentElement.scrollHeight, sections: [] }}, location.origin); }}
  addEventListener("load", post); addEventListener("resize", post);
  addEventListener("beforeprint", function () {{ document.querySelectorAll("details").forEach(function (d) {{ d.open = true; }}); }});
  var f = document.getElementById("approve-form");
  if (f) f.addEventListener("submit", function (e) {{
    e.preventDefault();
    var msg = document.getElementById("approve-msg"), name = document.getElementById("approver").value;
    fetch("/api/review/" + {json.dumps(review_id)} + "/approve", {{ method: "POST", headers: {{ "Content-Type": "application/json" }},
      body: JSON.stringify({{ approved_by: name }}) }})
      .then(function (r) {{ return r.json().then(function (j) {{ return [r.ok, j]; }}); }})
      .then(function (x) {{ if (x[0]) location.reload(); else msg.textContent = x[1].refusal || "Could not record the approval."; }})
      .catch(function () {{ msg.textContent = "Could not reach the server."; }});
  }});
}})();
</script></body></html>"""
