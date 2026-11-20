"""Flaky mock tools: the hazard, on purpose.

The world here is two lists — bookings and charges — plus an index
by idempotency key. The tools act on the world and can be told to
fail in the two ways that matter:

- ``after_commit``: the side effect lands in the world, *then* the
  call raises ToolTimeout. From the caller's side this looks like
  "nothing happened." It is a lie — the booking exists. This is
  the classic exactly-once hazard, and the reason a naive retry
  double-books.
- ``before_commit``: the call raises before anything lands. A
  retry is genuinely safe here — but the caller cannot tell the
  two apart without reconciling, which is the whole lesson.

The world indexes every committed record by the idempotency key
it was created with, so ``world.lookup(key)`` can answer the
reconcile question: "did this key already commit?" In a real
system that lookup is a query against the booking/payment service
by idempotency key; here it is a dict.

Everything is fictional: no real patients, no real payments, no
network. The names and amounts are mock data.
"""


class ToolTimeout(Exception):
    """The tool call timed out. The side effect may or may not have
    committed — from the caller's side, both look identical."""


class MockWorld:
    """The outside world the tools act on.

    ``bookings`` and ``charges`` record every committed side effect,
    in order — so a double-booking is visible as two entries, not
    hidden by an overwrite. ``_by_key`` indexes the first record
    committed under each idempotency key, for reconciliation.
    """

    def __init__(self):
        self.bookings = []
        self.charges = []
        self._by_key = {}
        self._seq = 0

    def _next_id(self, prefix):
        self._seq += 1
        return f"{prefix}-{self._seq:04d}"

    def book(self, key, patient, slot):
        record = {
            "booking_id": self._next_id("BK"),
            "patient": patient,
            "slot": slot,
            "key": key,
        }
        self.bookings.append(record)
        if key is not None:
            self._by_key.setdefault(key, record)
        return record

    def charge(self, key, patient, amount_cents):
        record = {
            "charge_id": self._next_id("CH"),
            "patient": patient,
            "amount_cents": amount_cents,
            "key": key,
        }
        self.charges.append(record)
        if key is not None:
            self._by_key.setdefault(key, record)
        return record

    def lookup(self, key):
        """The record already committed under this key, or None.

        This is the reconcile function execute_once calls after an
        unknown outcome: found means "it committed, replay it";
        None means "nothing landed, safe to execute."
        """
        return self._by_key.get(key)


def flaky_book_appointment(world, patient, slot, fail_mode="after_commit",
                           fail_times=1):
    """A book_appointment tool that fails the first ``fail_times``
    calls in the chosen way, then behaves. Returns a callable
    taking the idempotency key."""
    attempts = {"n": 0}

    def book_appointment(key):
        attempts["n"] += 1
        if fail_mode == "before_commit" and attempts["n"] <= fail_times:
            raise ToolTimeout(
                "timed out before the booking was recorded"
            )
        record = world.book(key, patient, slot)
        if fail_mode == "after_commit" and attempts["n"] <= fail_times:
            raise ToolTimeout(
                "timed out after the booking committed — response lost"
            )
        return record

    return book_appointment


def flaky_charge_payment(world, patient, amount_cents,
                         fail_mode="after_commit", fail_times=1):
    """A charge_payment tool with the same failure shapes as
    flaky_book_appointment. Returns a callable taking the key."""
    attempts = {"n": 0}

    def charge_payment(key):
        attempts["n"] += 1
        if fail_mode == "before_commit" and attempts["n"] <= fail_times:
            raise ToolTimeout(
                "timed out before the charge was recorded"
            )
        record = world.charge(key, patient, amount_cents)
        if fail_mode == "after_commit" and attempts["n"] <= fail_times:
            raise ToolTimeout(
                "timed out after the charge committed — response lost"
            )
        return record

    return charge_payment


def render_world(world):
    """What actually happened in the world — the ground truth the
    demo verdicts are read from."""
    lines = [f"Bookings in the world: {len(world.bookings)}"]
    for record in world.bookings:
        lines.append(
            f"- {record['booking_id']}: {record['patient']} @ {record['slot']}"
        )
    lines.append(f"Charges in the world: {len(world.charges)}")
    for record in world.charges:
        dollars = record["amount_cents"] / 100
        lines.append(
            f"- {record['charge_id']}: {record['patient']} ${dollars:.2f}"
        )
    return "\n".join(lines)
