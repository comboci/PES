# Project Evolution — START HERE (PES-14)

## Startup
Before analysis, review, planning, coding or migration:

1. Locate the declared canonical PE store.
2. Read this file.
3. Resolve the latest valid canonical PES-14 artifact.
4. Read applicable overlays.
5. Read Product Purpose and continuation state.
6. Resolve relevant Scope identities.
7. Apply the relevant Retrieval Contract.
8. Read Business Rules, Technical Contracts, Requirements, Decisions, Solutions, Findings, Questions, Verification and Acceptance.
9. Read Current Architecture / Current Operational Context views when present, but check freshness first.
10. For source work, verify Source Revision alignment before modification.
11. For runtime/deployment claims, use timestamped Observations and report freshness.
12. If PE/source/context disagree materially, stop mutation and report the mismatch.

## Meaning
Statement = faithful material input
Question = unresolved/answered project question
Analysis = reasoning
Finding = supported problem/observation
BusinessRule = durable domain rule
TechnicalContract = authoritative interface/contract reference
Solution = proposed remedy
Decision = attributable selection/rejection/deferment
Requirement = condition to satisfy
Task = executable work
Evidence = source-bound support
Verification = observed check/result
Acceptance = authorized acceptance
Observation = timestamped runtime/deployment/environment fact

Do not collapse these meanings.

## Current Architecture
A derived view, not a competing truth store. It must remain traceable to canonical records/source revisions and carries freshness.

## Current Operational Context
A derived view of build/test/run/deploy/backup/restore/rollback knowledge and authoritative references.

## Business Rules
Business Rules are first-class. Keep them scoped, precise/testable where practical, status-aware and linked to Requirements/Decisions/Verification.

## Technical Contracts
Reference the authoritative contract definition, version/revision and digest when possible. Do not copy large external schemas unless portability explicitly requires it.

## Finding profiles
Use one Finding entity with categories such as code_review, implementation, runtime, security, data_integrity, architecture, performance and operations.

## Retrieval Contract
Retrieval builds context from canonical records/views/source evidence. Context packages are derived and rebuildable, not a second knowledge store.

## Freshness
For views/contracts/observations, inspect freshness_state, observed_at, confirmed_at, valid_from, valid_until and source revision references. Stale/unknown state must be stated explicitly.

## Runtime / Deployment
Never equate source exists, merged, tests pass, accepted, deployed and healthy in production. Deployment/runtime state comes from timestamped Observations or a live provider.

## Task Priority
P0 Critical
P1 High
P2 Medium
P3 Low
unassigned

Priority is not authorization and is distinct from execution_order.

## Verification vs Acceptance
Verification is not Acceptance.

## Stale writer
Before material write: re-fetch canonical state. If advanced, merge/reconcile by stable IDs, provenance, relationships, conflicts and supersession; then validate and commit.

## Security
Never store secrets/passwords/tokens/private keys in PE.

## Cold-handoff prompt
Read START-HERE, latest canonical PES-14 and active overlays. Apply the relevant Retrieval Contract. Report Product Purpose, current Architecture with freshness, Business Rules, Technical Contracts, open Questions/Findings/conflicts, selected/candidate Solutions, Requirements, prioritized Tasks, Source alignment, Verification/Acceptance, runtime/deployment Observations with freshness, and the next valid work step before changing anything.
