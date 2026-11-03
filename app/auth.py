"""Passcode check shared by the Streamlit app and the web server (F1)."""

from __future__ import annotations

import hmac

NO_PASSCODE_MESSAGE = (
    "Live checks are off: this app has no passcode set. "
    "Reviewing a packet offline still works."
)
WRONG_PASSCODE_MESSAGE = "Enter the passcode to run a live check. Offline review needs none."


def passcode_ok(entered: object, configured: object) -> bool:
    """Constant-time match. No configured passcode means no match."""

    if not configured:
        return False
    return hmac.compare_digest(str(entered or "").encode(), str(configured).encode())


def passcode_refusal(entered: object, configured: object) -> str | None:
    """Why a live call may not run, or None when the passcode matches."""

    if not configured:
        return NO_PASSCODE_MESSAGE
    if not passcode_ok(entered, configured):
        return WRONG_PASSCODE_MESSAGE
    return None
