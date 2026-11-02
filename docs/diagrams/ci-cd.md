# CI/CD Pipeline

Every pull request and every push to `main` runs the same checks. Local hooks catch problems early, but they can be skipped, so CI is what enforces the rules.

```mermaid
flowchart LR
  dev([Developer]) --> hooks

  subgraph local [Local git hooks]
    hooks["On commit: ruff, mypy, ESLint, tsc, gitleaks, message format<br/>On push: unit tests"]
  end

  hooks --> pr[Pull request]

  subgraph ci [CI workflow]
    direction TB
    python["Python<br/>ruff, mypy, unit and integration tests"]
    typescript["TypeScript<br/>ESLint, tsc, Vitest, build"]
    secrets["Secret scan<br/>gitleaks over full history"]
    stack["Compose stack<br/>build images, migrate, check readiness"]
    passed{{CI passed}}
    python --> passed
    typescript --> passed
    secrets --> passed
    stack --> passed
  end

  subgraph security [Security workflow]
    codeql["CodeQL<br/>Python and TypeScript"]
  end

  pr --> python & typescript & secrets & stack
  pr --> codeql

  passed --> gate{{Branch protection}}
  gate --> main[(main)]

  bot([Dependabot]) -. weekly update PRs .-> pr

  subgraph later [Planned]
    direction TB
    chaos["Week 8: nightly chaos and load"]
    npm["Week 6: publish SDK to npm"]
    deploy["Week 9: deploy to production"]
  end

  main -.-> npm & deploy
  main -.-> chaos
```

## Decisions

| Decision | Why |
|---|---|
| Branch protection requires one check, `CI passed` | Jobs can be added or renamed without editing the rule. A skipped or cancelled job counts as a failure. |
| Integration tests run on every PR | Correctness depends on real Postgres behaviour, so a mock wouldn't prove anything. |
| The compose stack is started in CI | It catches broken Dockerfiles, migrations and role grants that unit tests can't see. |
| Actions are pinned to full commit SHAs | A moved tag can't change what runs. Dependabot keeps the pins current. |
| `GITHUB_TOKEN` is read-only by default | Only the CodeQL job gets more: `security-events: write`, to upload results. |
| Dependabot waits 7 days before proposing Python and npm releases | It gives the ecosystem time to catch a compromised release before it reaches this repo. |
