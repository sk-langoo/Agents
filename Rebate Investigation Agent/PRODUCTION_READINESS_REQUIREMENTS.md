# Rebate Investigation Agent: Production-Readiness Requirements

**Status:** Draft for stakeholder assignment and approval

**System classification:** High-impact financial decision support

**Commercial scale assumption:** More than $10B in annual transaction value
**Default operating mode:** Read-only investigation; no autonomous payments or ledger writes

## 1. Purpose and operating boundary

The system helps authorized employees investigate rebate eligibility, expected
rebates, payments, and exceptions. It may collect evidence, perform deterministic
calculations, explain conclusions, and route uncertain cases to people.

It must not create or approve payments, modify agreements, alter source
transactions, post journal entries, or make legally binding contract
interpretations. Those capabilities require a separate risk review and approval.

The language model is an orchestration and explanation layer. Authoritative data,
financial calculations, permissions, workflow state, and audit records are owned
by deterministic services.

## 2. Owner roles

Named individuals must be assigned before Phase 2 begins. Until then these role
owners are accountable placeholders.

| Owner role | Accountability |
| --- | --- |
| Executive sponsor | Risk acceptance, funding, final production authorization |
| Product owner | Scope, user outcomes, rollout, metric targets |
| Finance policy owner | Rebate policy, calculation rules, materiality thresholds |
| Contract operations owner | Agreement authority, amendment precedence, ambiguity process |
| Engineering owner | Architecture, implementation, testing, releases |
| Data owner | Source quality, lineage, reconciliation, retention |
| Security owner | Threat model, secrets, access control, incident response |
| Privacy/legal owner | Data classification, privacy, contract interpretation boundaries |
| Model risk owner | Model validation, evaluation thresholds, change approval |
| SRE/operations owner | Availability, latency, monitoring, recovery |
| Internal audit owner | Audit evidence, control design, periodic control testing |

## 3. Priority definitions

- **P0:** Required before any production transaction data is processed.
- **P1:** Required before a controlled pilot with real users.
- **P2:** Required before scaled rollout or shortly afterward under an approved exception.

## 4. Requirements by control area

| ID | Area | Pri. | Requirement and acceptance criteria | Owner | Dependencies | Approval gate |
| --- | --- | --- | --- | --- | --- | --- |
| ACC-01 | Accuracy | P0 | Rebate eligibility, rates, thresholds, dates, exclusions, rounding, and variance are calculated by versioned deterministic rules; 100% of approved golden calculations pass. | Finance + Engineering | Signed calculation specification | Finance rule approval |
| ACC-02 | Accuracy | P0 | Missing, ambiguous, conflicting, duplicate, or unreconciled evidence never silently becomes zero; all such cases enter an explicit exception state. | Finance | Data-quality rules | Finance control approval |
| ACC-03 | Accuracy | P1 | Model conclusions cite source record IDs and cannot override deterministic results. | Model risk | Provenance-capable tools | Eval gate |
| DAT-01 | Data | P0 | Every source has a named owner, authoritative-system designation, schema, freshness target, and reconciliation control. | Data owner | Source inventory | Data readiness sign-off |
| DAT-02 | Data | P0 | Money uses decimal arithmetic; dates use an approved business timezone; record IDs and versions are immutable. | Engineering + Finance | Canonical schema | Architecture review |
| DAT-03 | Data | P1 | Ingestion rejects or quarantines invalid schemas, duplicate IDs, impossible dates, missing currency, and failed control totals. | Data owner | Validation service | Data readiness sign-off |
| TOO-01 | Tools | P0 | Tools are read-only, narrowly scoped, typed, tenant-aware, time-bounded, paginated, and return provenance plus source version. | Engineering | Source APIs | Security review |
| TOO-02 | Tools | P0 | The model cannot choose tenant, authorization scope, or unrestricted queries; server code derives these from authenticated context. | Engineering + Security | Identity integration | Security approval |
| TOO-03 | Tools | P1 | Tool retries are bounded and safe; idempotency and circuit-breaking behavior are tested. | SRE | Reliability library | Operational readiness |
| PER-01 | Permissions | P0 | Least-privilege RBAC and customer/account scoping are enforced server-side for every request and tool call. | Security | Identity provider, entitlement map | Access-control sign-off |
| PER-02 | Permissions | P0 | Investigator, reviewer, auditor, and administrator duties are separated. Users cannot approve their own material cases. | Security + Finance | Workflow identity | Segregation-of-duties approval |
| SEC-01 | Security | P0 | Threat model covers prompt injection, data exfiltration, cross-tenant access, malicious source text, secret leakage, and dependency risk. | Security | Architecture/data flow | Threat-model approval |
| SEC-02 | Security | P0 | Secrets use an approved secret manager; data is encrypted in transit and at rest; logs redact secrets and sensitive fields. | Security | Enterprise platform | Security approval |
| SEC-03 | Security | P1 | Dependency scanning, SAST, vulnerability response SLAs, and incident playbooks are active. | Security + Engineering | CI/CD | Release gate |
| OBS-01 | Observability | P0 | Each request has a correlation ID and records tool calls, durations, retries, model/version, prompt/version, token use, decision state, and errors without sensitive payloads. | SRE | Telemetry platform | Operational readiness |
| OBS-02 | Observability | P1 | Dashboards and alerts cover correctness proxies, error rate, p95 latency, cost, escalation backlog, and source freshness. | SRE + Product | Metrics backend | Pilot approval |
| EVA-01 | Evaluations | P0 | Versioned datasets cover common, edge, adversarial, permission, security, failure, and human-review cases with no production personal data. | Model risk | Eval runner | Eval approval |
| EVA-02 | Evaluations | P0 | Every model, prompt, rule, schema, or tool change passes defined regression thresholds before promotion. | Model risk + Engineering | CI gate | Model change approval |
| EVA-03 | Evaluations | P1 | Pilot outcomes are sampled and adjudicated by Finance; dataset gaps become new regression cases. | Finance + Model risk | Review workflow | Pilot exit approval |
| HIT-01 | Human-in-the-loop | P0 | Missing agreements, conflicts, ambiguity, unreconciled totals, suspended terms, and materiality-policy triggers route to review. | Finance + Contract Ops | Review taxonomy | Workflow approval |
| HIT-02 | Human-in-the-loop | P0 | Reviewers see evidence, calculation, reason codes, provenance, and prior actions; approval/rejection requires identity, timestamp, and rationale. | Product + Audit | Case UI/workflow | Control owner approval |
| HIT-03 | Human-in-the-loop | P1 | Queues have severity, SLA, reassignment, aging alerts, and no self-approval for restricted cases. | Operations | Identity + notifications | Pilot approval |
| LAT-01 | Latency | P1 | Product owner approves service objectives after baseline testing; initially measure median, p95, and p99 end-to-end and by dependency. | Product + SRE | Load tests | SLO approval |
| LAT-02 | Latency | P1 | Requests have timeouts, bounded retries, cancellation, and graceful partial-failure behavior. | SRE | Tool contracts | Operational readiness |
| CST-01 | Cost | P1 | Per-case input, cached-input, output, retry, and tool costs are attributable by model/prompt version and customer scope. | Product + FinOps | Usage telemetry, price config | Pilot approval |
| CST-02 | Cost | P2 | Budgets, anomaly alerts, and per-request token/tool-call limits prevent runaway spend. | FinOps + SRE | Billing export | Scale approval |
| AUD-01 | Auditability | P0 | An append-only audit trail records who requested, what evidence/version was used, rules and model versions, result, escalation, and approvals. | Internal audit | Audit store | Audit-control approval |
| AUD-02 | Auditability | P0 | Audit records are tamper-evident, access-controlled, retained per policy, searchable, and exportable without exposing secrets. | Security + Audit | Retention policy | Audit-control approval |
| REL-01 | Reliability | P0 | Failure modes are defined for each dependency; the system fails closed on authorization and financial uncertainty. | Engineering + SRE | Dependency inventory | Architecture review |
| REL-02 | Reliability | P1 | Availability, recovery objectives, backup/restore, disaster recovery, rate limits, load tests, and rollback are tested. | SRE | Production platform | Operational readiness |
| REL-03 | Reliability | P1 | Releases are versioned, reproducible, canaried, monitored, and automatically or manually reversible. | Engineering + SRE | CI/CD | Release approval |

## 5. Approval gates

| Gate | Required approvers | Evidence required | Exit decision |
| --- | --- | --- | --- |
| G0 Operating boundary | Executive sponsor, Product, Finance, Legal | Scope, prohibited actions, materiality definition, jurisdictions | Approve design work |
| G1 Deterministic rules | Finance, Contract Ops, Engineering | Signed rule specification, rounding/date rules, golden tests | Approve foundation |
| G2 Data and security | Data, Security, Privacy/Legal | Source inventory, DPIA as applicable, threat model, access tests | Permit real-data integration |
| G3 Workflow and audit | Finance control owner, Audit, Security | Segregation-of-duties tests, audit samples, retention design | Permit reviewer pilot |
| G4 Evaluation | Model risk, Finance, Product | Frozen eval report meeting thresholds, red-team results | Permit controlled pilot |
| G5 Operational readiness | SRE, Security, Engineering | SLOs, load/failure tests, alerts, runbooks, rollback/DR | Permit production deployment |
| G6 Rollout expansion | Executive sponsor, Product, Finance, Model risk | Pilot KPIs, error review, incident record, residual risks | Expand volume/users |

No gate may be self-approved by the implementation author alone. Exceptions need
an owner, rationale, compensating control, expiration date, and explicit risk
acceptance.

## 6. Delivery phases

### Phase 0: Set the operating boundary

Deliver scope, prohibited actions, user roles, materiality policy, data
classification, jurisdiction/retention needs, and named owners. Exit through G0.

### Phase 1: Build the deterministic foundation

Deliver canonical schemas, decimal calculations, date/rounding rules, validation,
reason codes, source provenance, and golden tests. Exit through G1.

### Phase 2: Create secure production tools

Integrate approved read-only sources behind server-side identity, tenant filters,
timeouts, pagination, schemas, lineage, and reconciliation. Complete threat model
and access tests. Exit through G2.

### Phase 3: Add workflow, audit, and human approval

Deliver explicit case states, approval matrix, separation of duties, reviewer
experience, tamper-evident audit records, retention, and exports. Exit through G3.

### Phase 4: Establish evaluation gates

Expand datasets, add adversarial and failure tests, freeze baselines, define
thresholds, and block regressions in CI. Exit through G4.

### Phase 5: Operationalize

Deliver dashboards, alerts, SLOs, cost budgets, load/failure testing, backup,
recovery, incident response, on-call runbooks, canarying, and rollback. Exit G5.

### Phase 6: Controlled rollout

Start read-only with internal reviewers, low-risk customers, capped volume, and
100% human verification. Expand only after measured accuracy, risk, operational,
and financial criteria pass G6.

## 7. Initial measurable release gates

These are conservative draft thresholds and require owner approval:

- 100% pass on deterministic financial calculations and authorization tests.
- 100% escalation recall for conflicts, ambiguity, missing authority, and failed reconciliation.
- 0 known cross-tenant data exposures or unauthorized tool results.
- At least 98% task success on the frozen representative eval set.
- At least 99% evidence correctness and at most 0.5% deterministic hallucination proxy.
- At most 5% false escalation initially, then reduce without lowering recall.
- Zero unresolved P0/P1 security findings.
- Successful restore, rollback, dependency-failure, and audit-export exercises.
- Pilot uses 100% human verification; no autonomous financial posting.

## 8. Open decisions requiring stakeholder input

1. Named people for every owner role and approval gate.
2. Authoritative agreement, transaction, payment, identity, and workflow systems.
3. Currency, jurisdiction, fiscal calendar, timezone, rounding, and FX policies.
4. Materiality thresholds and which conclusions require dual approval.
5. Data classification, residency, retention, deletion, and legal-hold policies.
6. Availability, latency, recovery, throughput, and cost objectives.
7. Pilot customers/users and permitted production data fields.
8. Whether any future write action is in scope; default remains no.

## 9. Current implementation status

The local prototype now includes early Phase 1–4 building blocks: canonical
decimal schemas, deterministic calculation, validation, least-privilege policy,
tamper-evident local audit events, review-state rules, reliability helpers, and
evaluation thresholds. These are reference implementations, not approved
enterprise controls. Phase 2–6 cannot complete until the open decisions and
external platform dependencies above are resolved and their gates are signed.
