# ADR-0006: Transactional outbox for events

- **Status:** Accepted
- **Date:** 2026-10-11

## Context

After money moves, subscribers must be told. Sending the webhook directly from the request handler creates the dual-write problem:

- Send before commit → the commit can fail, and subscribers hear about money that never moved.
- Send after commit → the process can crash in between, and subscribers never hear about money that did move.

## Decision

- Every money-moving transaction inserts a row into `outbox_events` (`id`, `merchant_id`, `type`, `payload`, `created_at`, `published_at NULL`) **in the same transaction**. Event and effect commit or roll back together (PRD INV-6).
- A separate relay process:
  1. Claims a batch of unpublished events with `SELECT … WHERE published_at IS NULL ORDER BY created_at LIMIT 100 FOR UPDATE SKIP LOCKED`. Multiple relay replicas can run safely.
  2. For each endpoint subscribed to the event type, inserts a `webhook_deliveries` row with `ON CONFLICT (event_id, endpoint_id) DO NOTHING`.
  3. Sets `published_at` and commits.
- A dispatcher loop sends due deliveries (see [ADR-0007](0007-exactly-once-effects.md)).
- The relay polls every 250 ms when idle. `LISTEN/NOTIFY` can be added later to cut latency; polling stays as the fallback because notifications are lost while the relay is down.
- Events are retained for 30 days and exposed via `GET /v1/events`, so consumers can backfill anything they missed.

## Consequences

- No event is ever lost or invented, regardless of crashes (design doc F7, F8).
- Events are delivered at least once, possibly more, and not in strict order. Consumers must be idempotent; this is documented and the SDK helps.
- Outbox lag (`now() - min(created_at) WHERE published_at IS NULL`) becomes a key metric and alert.

## Alternatives considered

- **Kafka or another broker:** still needs an outbox to get events into the broker reliably, so it adds a system without removing the problem. Rejected for v1.
- **Change data capture (Debezium) on the WAL:** strong, but heavy infrastructure for a single database. Rejected for v1.
