"""A per-visitor cap on live runs, so one visitor cannot spend the shared model budget.

Only runs that can reach the model count: an upload or a new claim on an uploaded packet. The worked
example answers from the cache and is never limited. State is in memory, per process; a restart clears it.
"""

from __future__ import annotations

import os
import time
from collections import defaultdict, deque

WINDOW_SECONDS = 3600
DEFAULT_RUNS_PER_WINDOW = 3


class LiveRunLimit:
    def __init__(self, runs: int | None = None, window: int = WINDOW_SECONDS, clock=time.monotonic) -> None:
        self.runs = runs if runs is not None else int(os.environ.get("LIVE_RUNS_PER_HOUR", DEFAULT_RUNS_PER_WINDOW))
        self.window = window
        self._clock = clock
        self._seen: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, visitor: str) -> bool:
        """Record a run for this visitor and say whether it is within the limit. A limit of 0 turns it off."""
        if self.runs <= 0:
            return True
        now = self._clock()
        recent = self._seen[visitor]
        while recent and now - recent[0] >= self.window:
            recent.popleft()
        if len(recent) >= self.runs:
            return False
        recent.append(now)
        return True


def visitor_id(headers, client_host: str | None) -> str:
    """The first address in X-Forwarded-For (the host's proxy sets it), else the socket peer."""
    forwarded = headers.get("x-forwarded-for", "")
    return forwarded.split(",")[0].strip() or client_host or "unknown"
