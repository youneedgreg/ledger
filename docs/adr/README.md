# Architecture Decision Records

Each ADR records one significant decision: the context, the choice, and its consequences. ADRs are immutable once accepted; a change of mind is a new ADR that supersedes the old one.

New ADRs start from [the template](template.md).

| # | Decision | Status |
|---|---|---|
| [0001](0001-integer-minor-units.md) | Store money as integer minor units | Accepted |
| [0002](0002-immutable-entries.md) | Entries are append-only; corrections are reversing transactions | Accepted |
| [0003](0003-zero-sum-enforced-in-database.md) | Enforce double-entry in the database, not just the app | Accepted |
| [0004](0004-serializable-isolation-with-retries.md) | SERIALIZABLE isolation with bounded, jittered retries | Accepted |
| [0005](0005-idempotency-keys.md) | Idempotency keys stored in the same transaction as the effect | Accepted |
| [0006](0006-transactional-outbox.md) | Transactional outbox for events | Accepted |
| [0007](0007-exactly-once-effects.md) | Exactly-once effects via at-least-once delivery and idempotent consumers | Accepted |
| [0008](0008-holds-as-state-machine.md) | Holds as an explicit state machine backed by a holds account | Accepted |
