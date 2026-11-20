"""Tests for exactly-once tool execution.

The ledger and wrapper are pure Python, so every guarantee pins
down exactly: a retry after a lost response replays instead of
re-executing, concurrent duplicates execute once, and the unsafe
path demonstrably doubles. No model, no network, no key.
"""

import os
import sys
import threading
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent import run_agent  # noqa: E402
from exactly_once import (  # noqa: E402
    COMPLETED,
    IN_PROGRESS,
    UNKNOWN,
    IdempotencyStore,
    UnknownOutcomeError,
    execute_once,
)
from tools import (  # noqa: E402
    MockWorld,
    ToolTimeout,
    flaky_book_appointment,
    flaky_charge_payment,
)


def _store(tmp_path):
    return IdempotencyStore(str(tmp_path / "ledger.json"))


def test_retry_after_timeout_executes_the_side_effect_exactly_once(tmp_path):
    store = _store(tmp_path)
    world = MockWorld()
    book = flaky_book_appointment(world, "patient-123 (mock)",
                                  "2026-11-25T09:00")
    key = "book:patient-123:2026-11-25T09:00"

    # First attempt: commits, then the response is lost.
    with pytest.raises(ToolTimeout):
        execute_once(store, key, "book_appointment",
                     lambda: book(key), reconcile=world.lookup)
    assert len(world.bookings) == 1
    assert store.get(key)["status"] == UNKNOWN

    # Retry with the same key: reconciles, replays, does not re-book.
    result, replayed = execute_once(store, key, "book_appointment",
                                    lambda: book(key),
                                    reconcile=world.lookup)
    assert replayed is True
    assert result["booking_id"] == world.bookings[0]["booking_id"]
    assert len(world.bookings) == 1
    assert store.get(key)["status"] == COMPLETED


def test_retry_returns_the_stored_result_without_re_executing(tmp_path):
    store = _store(tmp_path)
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        return {"receipt": "R-1"}

    first, replayed_first = execute_once(store, "k1", "tool", fn)
    second, replayed_second = execute_once(store, "k1", "tool", fn)
    assert first == second == {"receipt": "R-1"}
    assert replayed_first is False
    assert replayed_second is True
    assert calls["n"] == 1


def test_concurrent_duplicate_calls_execute_once(tmp_path):
    store = _store(tmp_path)
    calls = {"n": 0}
    lock = threading.Lock()

    def slow_fn():
        with lock:
            calls["n"] += 1
        time.sleep(0.1)  # hold the claim so the duplicate must wait
        return {"receipt": "R-1"}

    results = []

    def call():
        results.append(execute_once(store, "k1", "tool", slow_fn))

    threads = [threading.Thread(target=call) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert calls["n"] == 1
    assert len(results) == 4
    assert all(result == {"receipt": "R-1"} for result, _ in results)
    assert sum(1 for _, replayed in results if not replayed) == 1


def test_different_keys_execute_separately(tmp_path):
    store = _store(tmp_path)
    world = MockWorld()
    book = flaky_book_appointment(world, "patient-123 (mock)",
                                  "2026-11-25T09:00", fail_mode=None)
    first, _ = execute_once(store, "book:a", "book_appointment",
                            lambda: book("book:a"),
                            reconcile=world.lookup)
    second, _ = execute_once(store, "book:b", "book_appointment",
                             lambda: book("book:b"),
                             reconcile=world.lookup)
    assert first["booking_id"] != second["booking_id"]
    assert len(world.bookings) == 2


def test_ledger_survives_a_restart_and_still_replays(tmp_path):
    path = str(tmp_path / "ledger.json")
    store = IdempotencyStore(path)
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        return {"receipt": "R-1"}

    execute_once(store, "k1", "tool", fn)

    # A new process: a fresh store over the same file.
    restarted = IdempotencyStore(path)
    result, replayed = execute_once(restarted, "k1", "tool", fn)
    assert result == {"receipt": "R-1"}
    assert replayed is True
    assert calls["n"] == 1


def test_in_progress_entry_at_load_becomes_unknown(tmp_path):
    path = str(tmp_path / "ledger.json")
    store = IdempotencyStore(path)
    entry, claimed = store.claim("k1", "tool")
    assert claimed is True
    assert entry["status"] == IN_PROGRESS

    # The process "dies" mid-flight; the next one must not assume
    # the side effect did or didn't happen.
    restarted = IdempotencyStore(path)
    assert restarted.get("k1")["status"] == UNKNOWN
    assert "restarted" in restarted.get("k1")["error"]


def test_timeout_before_commit_retries_safely(tmp_path):
    store = _store(tmp_path)
    world = MockWorld()
    charge = flaky_charge_payment(world, "patient-123 (mock)", 2500,
                                  fail_mode="before_commit")
    key = "charge:patient-123:copay"

    with pytest.raises(ToolTimeout):
        execute_once(store, key, "charge_payment",
                     lambda: charge(key), reconcile=world.lookup)
    assert world.charges == []  # nothing landed

    # Reconcile finds nothing, so the retry may execute — once.
    result, replayed = execute_once(store, key, "charge_payment",
                                    lambda: charge(key),
                                    reconcile=world.lookup)
    assert replayed is False
    assert result["amount_cents"] == 2500
    assert len(world.charges) == 1
    assert store.get(key)["attempts"] == 2


def test_unknown_outcome_without_reconcile_refuses_to_guess(tmp_path):
    store = _store(tmp_path)
    world = MockWorld()
    book = flaky_book_appointment(world, "patient-123 (mock)",
                                  "2026-11-25T09:00")
    key = "book:patient-123:2026-11-25T09:00"

    with pytest.raises(ToolTimeout):
        execute_once(store, key, "book_appointment", lambda: book(key))
    # No reconcile function: re-executing could double-book, so the
    # wrapper refuses instead of guessing.
    with pytest.raises(UnknownOutcomeError, match="Refusing to re-execute"):
        execute_once(store, key, "book_appointment", lambda: book(key))
    assert len(world.bookings) == 1


def test_key_reuse_for_a_different_tool_is_refused(tmp_path):
    store = _store(tmp_path)
    execute_once(store, "k1", "book_appointment", lambda: {"ok": True})
    with pytest.raises(ValueError, match="One key, one operation"):
        execute_once(store, "k1", "charge_payment", lambda: {"ok": True})


def test_agent_with_idempotency_books_and_charges_exactly_once(tmp_path):
    store = _store(tmp_path)
    world = MockWorld()
    result = run_agent(world, store, use_idempotency=True)
    assert len(world.bookings) == 1
    assert len(world.charges) == 1
    assert result["booking"]["booking_id"] == world.bookings[0]["booking_id"]
    assert result["charge"]["charge_id"] == world.charges[0]["charge_id"]
    # The journal shows the timeouts and the replays, not silence.
    events = [entry["event"] for entry in result["journal"]]
    assert events.count("timeout") == 2
    assert events.count("replay") == 2


def test_agent_without_idempotency_double_books_and_double_charges():
    world = MockWorld()
    run_agent(world, None, use_idempotency=False)
    # The contrast case: same flaky tools, same retries, no ledger —
    # every retry is a brand-new request.
    assert len(world.bookings) == 2
    assert len(world.charges) == 2
    assert world.bookings[0]["booking_id"] != world.bookings[1]["booking_id"]
    assert world.charges[0]["charge_id"] != world.charges[1]["charge_id"]
