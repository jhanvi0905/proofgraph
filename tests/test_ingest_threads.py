"""Page rendering must never run on two threads at once: pdfium is not thread-safe and crashes the whole server."""

import threading
import time
from pathlib import Path

from PIL import Image

from proofgraph.review import ingest as ing

PDF = Path(__file__).resolve().parent / "fixtures" / "text_span_rate.pdf"


class _Rendered:
    original = Image.new("RGB", (4, 4), "white")


class _Page:
    """Stands in for a pdfplumber page: records how many renders overlap."""

    def __init__(self):
        self.active = self.peak = 0
        self._guard = threading.Lock()

    def to_image(self, resolution):
        with self._guard:
            self.active += 1
            self.peak = max(self.peak, self.active)
        time.sleep(0.02)
        with self._guard:
            self.active -= 1
        return _Rendered()


def test_rendering_from_many_threads_never_overlaps():
    page = _Page()
    threads = [threading.Thread(target=ing.render_page, args=(page, 72)) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert page.peak == 1


def test_ingest_renders_pages_through_the_lock(monkeypatch):
    calls = []
    original = ing.render_page
    monkeypatch.setattr(ing, "render_page", lambda page, dpi: calls.append(dpi) or original(page, dpi))
    list(ing.ingest([PDF]))
    assert calls
