# Production Foundation

This package is the first local implementation of the production-readiness
plan. It is intentionally independent of the language model: financial and
control decisions must remain predictable even if a model response changes.

## Control map

| Area | Initial component | What remains before production |
| --- | --- | --- |
| Accuracy | `engine.py`, decimal models, reason codes | Finance-approved rules, currencies, tiers, returns, accruals, amendments |
| Data | `models.py`, provenance fields, control total | Authoritative source mapping, schemas, lineage, reconciliation operations |
| Tools | `tools.py` evidence-provider contract | Read-only enterprise adapters, pagination, timeout, tenant-filter tests |
| Permissions | `permissions.py`, service authorization first | SSO/IAM integration, entitlement lifecycle, periodic access reviews |
| Security | `security.py`, redaction, hashed customer in audit | Threat model, secret manager, encryption, scanning, pen test |
| Observability | `observability.py`, service counters/timers | Enterprise telemetry, dashboards, alerts, SLOs |
| Evaluations | Existing dataset/runner plus `eval_gate.py` | Approved thresholds, CI integration, adversarial/security evals |
| Human review | `workflow.py`, reason codes, no self-approval | Durable workflow store, reviewer UI, queues, notifications, dual approval |
| Latency | End-to-end timer and eval percentiles | Load baseline, SLO, dependency timing, capacity plan |
| Cost | Eval token and optional dollar accounting | Current price service, budgets, attribution, anomaly alerts |
| Auditability | `audit.py` hash-chained local events | Immutable enterprise store, retention/legal hold, access/export controls |
| Reliability | `reliability.py`, fail-closed service path | Idempotency store, HA, DR, backups, chaos/load tests, rollback |

## Request flow

```text
authenticated request
        |
        v
server-side permission check --denied--> redacted audit event
        |
        v
tenant-scoped evidence provider
        |
        v
deterministic validation and calculation
        |
        +--> completed result
        |
        +--> explicit human-review result
        |
        v
metrics + tamper-evident audit event
```

The model can later receive the controlled result and evidence summary to write
a clear explanation. It must not replace permission checks or financial rules.

## Important limitation

The local audit hash chain can reveal file tampering, but a person with filesystem
access can still replace the entire file. Production requires an independently
controlled immutable audit service. Likewise, the in-memory evidence provider is
only a test double, never a production data source.
