# Project Evolution Standard — PES-14

Status: Current project standard
Schema revision: 14.0.0

## Purpose
PES-14 is a provider-neutral semantic standard for durable project knowledge that humans and AI can continue without prior chat history.

## Core model
PES-14 distinguishes:
1. Canonical Records — durable semantic knowledge.
2. Derived Views — rebuildable current-state projections.
3. Observations — timestamped runtime/deployment/environment facts.
4. Retrieval Contracts — rules for assembling context without duplicating knowledge.

## New first-class records
### BusinessRule
A durable domain rule. It is distinct from Requirement, Decision, Analysis and Task.

### TechnicalContract
An authoritative interface/integration contract reference such as API, database/schema, event, protocol or service boundary. Prefer reference + revision/version + digest over copying whole external schemas.

## Enhanced Finding
Finding remains the canonical entity. Use category/profile values such as:
general, code_review, implementation, runtime, security, data_integrity, architecture, performance, operations, other.

## Scope identity
PES-14 adds stable scope identities such as:
domain, module, feature, entity, service, integration, environment, codebase, other.

Records may reference scopes to support retrieval and impact analysis.

## Freshness and validity
Current-state knowledge can carry:
freshness_state, observed_at, confirmed_at, valid_from, valid_until, source_revision_refs.

Stale or unknown state must not be represented as current truth.

## Derived views
### Current Architecture
A rebuildable projection of currently valid architecture, derived from canonical records and source evidence.

### Current Operational Context
A rebuildable projection of build/test/run/deploy/backup/restore/rollback knowledge and authoritative references.

Derived views are not competing sources of truth.

## Deployment/runtime observations
Deployment/runtime state is represented as timestamped Observation records, not timeless live truth.

## Retrieval Contract
A Retrieval Contract defines how to assemble context for a Task, Feature, Module, Domain or other scope by following canonical references.

It should preserve traceability to:
Business Rules, Technical Contracts, Requirements, Decisions, Solutions, Findings, Questions/conflicts, source revision, Verification/Acceptance, derived views and relevant Observations.

A context package is derived and rebuildable; it is not a second knowledge store.

## Task Priority
P0 Critical
P1 High
P2 Medium
P3 Low
unassigned = no authoritative priority

Priority is not implementation authorization and is distinct from execution_order.

## Verification vs Acceptance
Verification does not imply Acceptance.

## Concurrency
A stale writer must not overwrite newer canonical state. Re-fetch, compare/merge by stable IDs/provenance/relationships/conflicts/supersession, validate, then commit.

## Security
Never store secrets, passwords, tokens or private keys in PE. Store secure references only.

## Migration from PES-13
Migration is additive and non-destructive.
Preserve stable IDs, provenance, relationships, material history and Task priority.
Do not infer missing Business Rules, Technical Contracts, scopes, freshness or acceptance.
Finding keeps its identity and gains category/profile metadata.
Current Architecture and Current Operational Context are derived views.
Runtime/deployment facts become timestamped Observations.
