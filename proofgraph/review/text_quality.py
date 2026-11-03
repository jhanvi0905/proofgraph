"""Score a page's text layer. Fixed defaults, not tuned (build brief, Iteration 2 E).

Two defects show up in poor PDF text layers: font glyph codes left as text
(``(cid:82)``) and words run together with no spaces. Both are measured from
the tokens alone, with no knowledge of the document.
"""

from __future__ import annotations

CID_MAX_SHARE = 0.02  # more than 2% of tokens are (cid: codes
LONG_MAX_SHARE = 0.05  # more than 5% of words are over LONG_WORD characters
LONG_WORD = 25
TIGHT_X_TOLERANCE = 1  # pdfplumber's default is 3


def cid_share(tokens: list[str]) -> float:
    return sum("(cid:" in t for t in tokens) / len(tokens) if tokens else 0.0


def long_share(tokens: list[str]) -> float:
    return sum(len(t) > LONG_WORD for t in tokens) / len(tokens) if tokens else 0.0


def is_poor(tokens: list[str]) -> bool:
    return cid_share(tokens) > CID_MAX_SHARE or long_share(tokens) > LONG_MAX_SHARE


def pick_better(default: list[str], retry: list[str]) -> list[str]:
    """Keep the retry only when it scores strictly better; a tie keeps the default."""

    def score(tokens: list[str]) -> float:
        return cid_share(tokens) + long_share(tokens)

    return retry if score(retry) < score(default) else default
