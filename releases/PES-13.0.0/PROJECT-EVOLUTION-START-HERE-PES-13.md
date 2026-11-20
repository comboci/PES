# Project Evolution — START HERE (PES-13)

This is the generic onboarding/help file for Project Evolution Standard PES-13.

## 1. Purpose

Project Evolution is a durable project-memory and reasoning artifact. It preserves project intent, questions, analysis, findings, solutions, decisions, requirements, uncertainty, implementation references, verification, acceptance and continuation context so a new human or AI can continue the project without relying on previous chat history.

PES-13 is provider-neutral. A project may store Project Evolution in Git, a filesystem, a PE Manager/database, or another declared canonical store.

## 2. Mandatory startup sequence

Before analysis, review, planning, coding or claiming current project state:

1. Locate the project's declared canonical Project Evolution store/channel.
2. Read this START-HERE document completely.
3. Resolve the latest valid canonical Project Evolution snapshot.
4. Read every active/applicable Analysis Overlay created after that canonical snapshot.
5. Read Product Purpose/Intent, source context, open questions/conflicts, candidate/selected Solutions, Decisions, Requirements, Tasks, Verification, Acceptance, continuation and evolution history.
6. Determine your role: Analysis, Development, Review/Audit, or another explicitly declared role.
7. If source work is involved, fetch the role-appropriate source revision and verify PE/source alignment before modification.
8. If PE and source disagree materially, stop source modification, report the mismatch, and preserve new analysis without fabricating alignment.

## 3. Material-turn capture

No acknowledged material user intent should remain only in chat history.

For a material turn:
- preserve a faithful/near-literal Statement when meaningful;
- derive typed semantic records;
- preserve provenance;
- update relationships/open state;
- persist before claiming canonical incorporation.

If durable persistence fails, explicitly report `PE_SYNC_PENDING` or `PE_SYNC_FAILED`.

## 4. Core semantic distinctions

- **Statement** = faithful capture of material user/project input.
- **Question** = unresolved or answered issue that matters to continuation.
- **Analysis** = reasoning and interpretation.
- **Finding** = supported observation/problem/defect.
- **Solution** = proposed remedy.
- **Decision** = attributable selection/rejection/deferment.
- **Requirement** = what must be satisfied.
- **Task** = executable work.
- **Evidence** = support tied to source/observation.
- **Verification** = observed check/result.
- **Acceptance** = authorized acceptance.

A proposed Solution is not automatically selected or authorized.

## 5. Task Priority Contract

Every new Task uses exactly one canonical priority:

- `P0` — Critical
- `P1` — High
- `P2` — Medium
- `P3` — Low
- `unassigned` — not authoritatively prioritized; never guess

Migration aliases only:
- `critical → P0`
- `high → P1`
- `medium → P2`
- `low → P3`

Priority is **not implementation authorization**.

Priority and `execution_order` are separate:
- priority = importance / urgency;
- execution_order = queue order within a context.

Dependencies, blockers, security/data-integrity constraints and explicit owner direction may change effective queue order. Record the reason.

Changing priority is a material Project Evolution change and must preserve provenance/history.

## 6. Analysis Overlay

Use an Analysis Overlay when analysis advances without a new software release.

Naming convention:

`Project-Evolution-V<base>-AN<nnn>.json`

Rules:
- AN does not increment software release.
- It must identify its base artifact.
- If development advances beyond the overlay base, merge the overlay onto the latest valid canonical PE.
- Never overwrite a newer PE using an older overlay base.
- Preserve conflicts/parallel meaning instead of silently choosing a winner.

## 7. Verification vs Acceptance

Verification and Acceptance are separate.

Examples of Verification:
- source inspection;
- build success;
- automated test;
- integration test;
- runtime test;
- data validation.

Verification does not automatically mean the owner/user accepted the result.

If runtime/user acceptance is required, `Done` requires explicit authorized acceptance.

## 8. History

Project Evolution history is append-oriented.

Do not silently delete:
- material Findings;
- Requirements;
- Decisions;
- Solutions;
- Questions;
- rationale;
- evidence of important superseded states.

Compaction is allowed only when the derivation chain remains recoverable.

Unknown historical facts must remain unknown/unavailable/unassigned rather than being guessed.

## 9. Canonical store and stale writers

If the project declares a canonical PE store:

1. remember the revision you read;
2. before a material write, fetch/read the latest revision again;
3. if it advanced, do not overwrite;
4. compare/merge by stable IDs, provenance, relationships, conflicts and supersession;
5. preserve genuinely parallel/conflicting material knowledge;
6. commit/write only after reconciliation.

## 10. Commit-based stores

When Project Evolution is stored in Git or another commit-based VCS, a material PE commit should use:

`PE <Project> <Artifact-or-Revision> | <CHANGE-TYPE> | <short material summary>`

Commit body should state, where applicable:

- PE artifact/base;
- canonical PE branch/store;
- PES standard;
- records added/changed/resolved/superseded;
- source release/branch/commit;
- reason;
- verification;
- runtime/owner acceptance.

Generic messages such as `update PE` or `fix json` are insufficient for material changes.

## 11. Portability

PES-13 does not require GitHub, Git, a source repository, or any particular application stack.

A valid project may be:
- software;
- research;
- architecture;
- company strategy;
- product design;
- future studies;
- another long-lived knowledge/work project.

The portable Project Evolution artifact remains useful even when operational work is tracked elsewhere.

## 12. Recommended fresh-session instruction

“Read the project’s declared Project Evolution START-HERE file, then the latest canonical PE and every active/applicable overlay. Reconcile them by stable ID and report project purpose, current PE/software/source state, open P0/P1/P2/P3/unassigned Tasks, blockers/conflicts, candidate/selected Solutions, verification-only items, and your role before changing anything.”
