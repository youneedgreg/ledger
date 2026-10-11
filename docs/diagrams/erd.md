# Entity-Relationship Diagram

The v1 schema. Column types are Postgres types; `char3` means `char(3)`.

```mermaid
erDiagram
  merchants ||--o{ api_keys : "authenticates with"
  merchants ||--o{ accounts : owns
  merchants ||--o{ ledger_transactions : owns
  merchants ||--o{ idempotency_keys : scopes
  merchants ||--o{ outbox_events : emits
  merchants ||--o{ webhook_endpoints : registers
  api_keys ||--o{ ledger_transactions : created
  ledger_transactions ||--|{ entries : "has 2 or more"
  accounts ||--o{ entries : "posted to"
  ledger_transactions |o--o{ ledger_transactions : reverses
  accounts ||--o{ holds : "funds come from"
  holds |o--|{ ledger_transactions : "moves funds via"
  outbox_events ||--o{ webhook_deliveries : "delivered as"
  webhook_endpoints ||--o{ webhook_deliveries : receives

  merchants {
    uuid id PK
    text name
    timestamptz created_at
  }
  api_keys {
    uuid id PK
    uuid merchant_id FK
    text prefix UK "e.g. sk_test_4f9a"
    bytea key_hash "SHA-256 of the full key"
    text api_version "pinned Ledger-Version"
    timestamptz created_at
    timestamptz revoked_at
  }
  accounts {
    uuid id PK
    uuid merchant_id FK
    text kind "user | external | holds"
    char3 currency "unique (id, currency) for composite FKs"
    bigint balance "cached; CHECK allow_negative OR balance >= 0"
    boolean allow_negative "true only for external"
    jsonb metadata
    timestamptz created_at
  }
  ledger_transactions {
    uuid id PK
    uuid merchant_id FK
    text type "transfer | refund | hold_*"
    char3 currency "unique (id, currency) for composite FKs"
    uuid reverses_transaction_id FK "refunds only"
    uuid hold_id FK "hold_* only"
    uuid created_by_api_key_id FK
    text description
    jsonb metadata
    timestamptz created_at
  }
  entries {
    uuid id PK
    uuid transaction_id FK "FK (transaction_id, currency)"
    uuid account_id FK "FK (account_id, currency)"
    char3 currency
    text direction "debit | credit"
    bigint amount "CHECK amount > 0"
    timestamptz created_at
  }
  holds {
    uuid id PK
    uuid merchant_id FK
    uuid source_account_id FK
    char3 currency
    bigint amount
    bigint captured_amount "NULL until captured"
    text status "authorized | captured | voided | expired"
    timestamptz expires_at
    timestamptz created_at
    timestamptz closed_at
  }
  idempotency_keys {
    uuid merchant_id PK
    text key PK
    text method
    text path
    bytea request_hash "SHA-256 of canonical body"
    int response_status
    jsonb response_body
    timestamptz created_at
    timestamptz expires_at "created_at + 24h"
  }
  outbox_events {
    uuid id PK
    uuid merchant_id FK
    text type "e.g. transfer.created"
    jsonb payload "full object state"
    timestamptz created_at
    timestamptz published_at "NULL until relayed"
  }
  webhook_endpoints {
    uuid id PK
    uuid merchant_id FK
    text url "https only in production"
    text_array event_types
    bytea secret_ciphertext "encrypted; needed to sign"
    text status "enabled | disabled"
    timestamptz created_at
  }
  webhook_deliveries {
    uuid id PK
    uuid event_id FK "UK (event_id, endpoint_id)"
    uuid endpoint_id FK
    text status "pending | succeeded | dead"
    int attempt_count
    timestamptz next_attempt_at
    int last_response_status
    text last_error
    timestamptz created_at
    timestamptz succeeded_at
  }
  reconciliation_runs {
    uuid id PK
    timestamptz started_at
    timestamptz finished_at
    text status "passed | failed"
    jsonb results "per-invariant counts"
  }
```

## Constraints the diagram can't show

| Rule | How it's enforced |
|---|---|
| Debits = credits per transaction, ≥ 2 entries (INV-1) | Deferred constraint trigger on `entries` ([ADR-0003](../adr/0003-zero-sum-enforced-in-database.md)) |
| Entry currency = account currency = transaction currency | Composite FKs `(account_id, currency)` and `(transaction_id, currency)` |
| No overdraft on user and holds accounts (INV-4) | `CHECK (allow_negative OR balance >= 0)` on `accounts` |
| Entries and transactions never change (INV-5) | No UPDATE/DELETE grants, plus a rejecting trigger ([ADR-0002](../adr/0002-immutable-entries.md)) |
| One system account of each kind per merchant and currency | Partial unique index on `accounts (merchant_id, kind, currency) WHERE kind <> 'user'` |
| One delivery per event per endpoint | Unique `(event_id, endpoint_id)` on `webhook_deliveries` |

## Indexes worth noting

- `entries (account_id, created_at DESC)` for account statements.
- `outbox_events (created_at) WHERE published_at IS NULL` so the relay's claim query stays fast as the table grows.
- `webhook_deliveries (next_attempt_at) WHERE status = 'pending'` for the dispatcher.
- `holds (expires_at) WHERE status = 'authorized'` for the expiry job.
- `idempotency_keys (expires_at)` for cleanup.
