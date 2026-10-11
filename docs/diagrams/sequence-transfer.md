# Sequence: Create a Transfer

The happy path, an idempotent replay, and the serialization-retry loop, all in one picture.

```mermaid
sequenceDiagram
  autonumber
  participant C as Client (SDK)
  participant G as API Gateway
  participant L as Ledger Core
  participant DB as Postgres
  participant R as Outbox Relay

  C->>G: POST /v1/transfers<br/>Authorization: Bearer sk_test_…<br/>Idempotency-Key: 7c1e…
  G->>G: Hash key, look up merchant, rate-limit, validate body
  G->>L: Forward with merchant_id, request_id, traceparent

  loop up to 5 attempts while SQLSTATE 40001 / 40P01
    L->>DB: BEGIN ISOLATION LEVEL SERIALIZABLE<br/>SET LOCAL lock_timeout = '2s'
    L->>DB: INSERT INTO idempotency_keys … ON CONFLICT DO NOTHING RETURNING
    alt key already exists
      L->>DB: SELECT request_hash, response FROM idempotency_keys
      alt request_hash differs
        L-->>G: 422 idempotency_key_reused
      else same request
        L-->>G: Stored response (replay, no new effect)
      end
    else new key
      L->>DB: SELECT source and destination accounts
      alt business rule fails (e.g. insufficient funds)
        L->>DB: UPDATE idempotency_keys SET response = 402 error
        L->>DB: COMMIT
        L-->>G: 402 insufficient_funds
      else valid
        L->>DB: INSERT ledger_transactions (type = transfer)
        L->>DB: INSERT entries: debit source, credit destination
        L->>DB: UPDATE accounts SET balance = balance ± amount
        L->>DB: INSERT outbox_events (transfer.created)
        L->>DB: UPDATE idempotency_keys SET response = 201 body
        L->>DB: COMMIT
        Note over DB: Deferred trigger checks debits = credits.<br/>Any violation aborts the whole commit.
        L-->>G: 201 Created
      end
    end
  end

  G-->>C: Response + Request-Id header

  Note over R,DB: Later, asynchronously
  R->>DB: SELECT … FROM outbox_events WHERE published_at IS NULL FOR UPDATE SKIP LOCKED
  R->>DB: INSERT webhook_deliveries … ON CONFLICT DO NOTHING<br/>UPDATE outbox_events SET published_at = now()
```

## Reading notes

- **Steps inside the loop are one database transaction.** The money movement, the outbox event and the stored response commit together or not at all.
- **Concurrent same-key requests:** the second `INSERT … ON CONFLICT` waits on the first's uncommitted row. When the first commits, Postgres aborts the second with `40001`; the loop re-runs it and it takes the "key already exists" branch.
- **Retries exhausted:** the core returns 503 `ledger_contention` (not shown). The client retries with the same key.
- Webhook dispatch from `webhook_deliveries` is covered in a separate sequence diagram (Week 4).
