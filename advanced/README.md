# Advanced

Production-grade agent patterns. Most live as standalone repos and
are linked from the [root README](../README.md#advanced) — the
cookbook never duplicates one of those.

The in-cookbook advanced recipes live here too:
[prior-auth-agent](prior-auth-agent) — a prior authorization tracker
built on a deterministic state machine that holds state across days
of waiting. It teaches the long-lived workflow pattern at cookbook
scale, where the starter recipes teach single-turn patterns.
[deja-vu-agent](deja-vu-agent) — Deja Vu Agent: idempotency keys
and an execution ledger so a retried tool call runs exactly once,
even when the first attempt timed out after committing.
