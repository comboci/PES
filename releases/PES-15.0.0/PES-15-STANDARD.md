# Project Evolution Standard — PES-15 (Reference Specification)

Version: 15.0.0  
Status: Standalone reference implementation; product integration and operational acceptance pending  
Compatibility principle: Never auto-upgrade existing PES-14 consumers.

## 1. Model

PES-15 retains all 15 PES-14 canonical record collections: Statement, Idea, Question, Analysis, Solution, Finding, BusinessRule, TechnicalContract, Requirement, Decision, Task, Evidence, Verification, Acceptance, Observation.

- **Canonical records** provide stable identities and material historical provenance.
- **Scope identities** allow hierarchical selection and impact analysis.
- **Typed relationships** link two records, or explicitly declare an external target; never silently trust external references.
- **Derived views** are rebuildable, non-authoritative current-state projections.
- **Observations** refer to their observation time and do not assert timeless operational truth.
- **Retrieval contracts** select records and relationship depth without creating an alternative source of truth.
- **Append-only store revisions** preserve older snapshots and allow optimistic concurrency.

PES-15 does not replace the product's relational/business database. It persists project evolution facts.

## 2. Main payload

Required top-level fields: `_pes`, `project`, `artifact`, `release_context`, `coordination`, `purpose`, `scopes`, `records`, `relationships`, `views`, `retrieval`, `open_state`, `continuation`.

`_pes.standard = PES-15`, `_pes.schema_revision = 15.0.0`. Three SHA-256 digests bind the embedded schema, semantic rules and compatibility profile to the file. These hashes are checked, not simply warned about. A migrated file contains `_pes.migration` with the original `PES-14` canonicalized JSON SHA-256, source schema revision and method; original source remains unchanged.

`legacy_exceptions.task_priority_missing`, `legacy_exceptions.observation_time_missing`, and `legacy_exceptions.relationship_legacy_indices` are exclusively for real PES-14 migration. They cannot be extended in a future commit. Exemptions may be removed when missing fields are supplied with attributable provenance. No factual fields are synthesized.

## 3. Semantic and referential enforcement

| Invariant | Enforcement |
|---|---|
| Required record fields, dates and enums | JSON Schema + JSON Schema format checker |
| Duplicate Record/Scope/Relationship/Contract IDs | semantic validator, global namespace |
| Record references, Scope parent, open_state and retrieval references | semantic validator |
| Cycles in parent Scope hierarchy | semantic validator |
| Local relationship source/target existence, typed relationship | semantic validator |
| External relationship target | explicit `{namespace, object_id, source_uri?}`, reported as unverified |
| New Task priority P0/P1/P2/P3/unassigned | semantic validator with immutable legacy exception list |
| New Observation observed_at with UTC offset/Z | semantic validator |
| Deletion/movement of historic records, scopes, relations, contracts | baseline-aware validator |
| Changing migration source digest or project/artifact identity | baseline-aware validator |
| Concurrency/lost updates | SQLite transaction + required revision and SHA CAS |
| On-disk history/event consistency | full hash-chain verification |
| Strong credential detection | limited basic scanner, NOT a comprehensive security audit |
| Source truth, acceptance quality, runtime/build proof | NOT inferred; requires actual authoritative evidence |

A structural JSON Schema alone is insufficient for cross-record invariants. `validate()` MUST be called before canonical write. Native `PES-15` writers MUST NOT bypass the validator.

## 4. Typed relationships

Native example:

```json
{
  "relationship_id": "REL-001",
  "source_ref": "REQ-001",
  "target_ref": "DEC-001",
  "relation_type": "depends_on",
  "status": "active"
}
```

For an external target, omit `target_ref` and use `target_external_ref: {"namespace":"github", "object_id":"owner/repo#commit", "source_uri":"https://github.com/owner/repo"}`. External links remain unverified until an integration verifies them. Relations imported from old, untyped formats are preserved and separately warning-marked; they are not silently reinterpreted as native relationships.

## 5. Concurrency and historical integrity

The reference store uses one local SQLite DB per PES-15 canonical project. On every write:

1. Read `revision` and `sha256` from the current head.
2. Prepare an updated **PES-15** snapshot without deleting historic stable IDs.
3. Acquire a write transaction with `BEGIN IMMEDIATE`.
4. Compare **both** expected revision and SHA to the new head.
5. Re-run schema, semantic, and baseline tests against the actual current head.
6. If valid, append full snapshot and an event hash including actor, reason, timestamp and parent event hash; update head in the same transaction.
7. If stale, fail with `Conflict`: caller must re-fetch and reconcile. No force flag exists.

Historical revisions are never overwritten. Restoring older content as the latest head, if needed, must create a NEW revision without deleting later-added stable record identities. No automatic state merge is implemented; human/agent-assisted reconciliation is an explicit caller responsibility.

### Known deployment boundary

SQLite provides atomicity on supported local filesystems and supported configurations. Crash/restore and cross-process load testing beyond the included unit/integration tests must occur before deployment. Treat hash chains without an externally protected anchor as integrity checks rather than authenticated tamper-proof logs.

## 6. Retrieval and epistemic safety

- Retrieval is read-only and deterministic for a given snapshot, contract, scope, and supplied time.
- It includes matching scope descendants and a bounded depth of related IDs.
- Every selected record has `traceability` metadata and provenance.
- Excluded types, unknown freshness, unverified source alignment, missing legacy priority/timestamp and missing Acceptance produce explicit warnings.
- A historic record with `status=completed` is NOT a verified or accepted record.
- `current_only` excludes only explicitly terminal states, and does not invent currentness for other records.
- No retrieval output can claim that it checked a live source; `claim_of_live_source_alignment=false` until a separate verified connector provides that capability.

## 7. Version policy

PES-14 artifacts and projects are not mutated. Native PES-15 writers cannot directly write a PES-14 canonical file. The only supported migration is **explicit opt-in PES-14 copy -> PES-15**, with source digest and preservation checks. The migration tooling does not automatically accept PES-13 and earlier; missing information must be explicitly reconciled before PES-15.

A PES-15 adoption must be coordinated with an application's storage migration/deployment plan. **Do not replace** the PES-14 startup file, scheduled automation prompt, or canonical JSON path in-place.
