"""app/limit.py: the per-visitor live-run window."""

from app.limit import LiveRunLimit, visitor_id


def test_blocks_after_the_limit_and_frees_after_the_window():
    now = [0.0]
    limit = LiveRunLimit(runs=2, window=100, clock=lambda: now[0])
    assert limit.allow("a") and limit.allow("a")
    assert not limit.allow("a")
    assert limit.allow("b")  # another visitor has their own window
    now[0] = 101.0
    assert limit.allow("a")


def test_zero_turns_the_limit_off():
    limit = LiveRunLimit(runs=0)
    assert all(limit.allow("a") for _ in range(20))


def test_visitor_is_the_first_forwarded_address():
    assert visitor_id({"x-forwarded-for": "203.0.113.9, 10.0.0.1"}, "10.0.0.1") == "203.0.113.9"
    assert visitor_id({}, "10.0.0.1") == "10.0.0.1"
    assert visitor_id({}, None) == "unknown"
