# ADR-0007: Exactly-once effects via at-least-once delivery and idempotent consumers

- **Status:** Accepted
- **Date:** 2026-10-11

## Context

Exactly-once *delivery* over a network is impossible: if the sender crashes after the receiver processed a message but before the acknowledgment is recorded, the sender can't know and must resend. What systems can achieve is exactly-once *effects*: a message may arrive several times, but it changes the receiver's state only once.

## Decision

Ledger guarantees at-least-once delivery and gives consumers what they need to apply each event exactly once:

1. **Stable identity.** Every event has a unique `id` (`evt_…`) that is identical on every delivery attempt and in `GET /v1/events`.
2. **Authenticity.** Each delivery carries
   `Ledger-Signature: t=<unix seconds>,v1=<hex HMAC-SHA256(endpoint_secret, "<t>.<raw body>")>`.
   During secret rotation, both old and new signatures are sent as two `v1=` values.
3. **Replay protection.** Consumers reject signatures whose `t` is more than 5 minutes old.
4. **Deduplication contract.** Consumers record processed event IDs in the same transaction as their own effect and skip IDs they've already seen. The SDK's `webhooks.verify()` handles steps 2 and 3; the docs show step 4.
5. **Delivery policy.**
   - 10 s timeout; any 2xx is success; redirects are not followed.
   - Retries at roughly 1 m, 5 m, 30 m, 2 h, 6 h, 12 h, 24 h with ±20% jitter, then `dead`.
   - Manual replay via `POST /v1/webhook_deliveries/{id}/retry` or the dashboard.
   - An endpoint that fails continuously for 3 days is disabled and the merchant is told in the dashboard.

## Consequences

- Correct even when the dispatcher crashes after a successful send (design doc F8).
- Consumers carry some responsibility. The test consumer in this repo is the reference implementation and is what the chaos suite checks.
- Ordering is not guaranteed. Payloads include `created_at` and the full object state so consumers can discard stale updates.

## Alternatives considered

- **Claiming exactly-once delivery:** not achievable; would be a false promise.
- **Ordered, per-merchant delivery:** one stuck event would block all later ones. Rejected for v1.
