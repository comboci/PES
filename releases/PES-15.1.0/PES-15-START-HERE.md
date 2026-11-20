# START HERE — PES-15.1.0 (Independent Reference Implementation)

1. **Version isolation:** PES-14 consumers and `Project-Evolution-V1-PES-14.json` are NOT upgraded automatically. Never edit the PES-14 canonical source in-place.
2. **Validation before writing:** use `python -m pes15 validate`; native writers must use `CanonicalStore.commit()`.
3. **Provenance:** don't infer priority, acceptance, observation timestamp, status, implementation verification, live freshness, or deployment success.
4. **Concurrency:** always include both `expected_revision` and `expected_sha256`; on conflict re-fetch, compare, reconcile, validate and retry. No forced overwrite.
5. **Migration:** if explicitly authorized, use `python -m pes15 migrate old-v14.json --output NEW-v15.json`. Preserve source hash and keep original.
6. **Project context:** use `RETRIEVAL-PES15-FULL` for comprehensive context on migrated snapshots, not the old incomplete default. Check warnings before trusting a status.
7. **Product integration:** the reference engine doesn't verify GitHub source or the application's runtime. Record owner acceptance separately.
8. **Run tests:** `python -m unittest discover -s tests -v`, then `python tools/evaluate_portfolio_builder.py --output-dir <new folder>`.

Complete documentation: `README-FA.md`, `PES-15-STANDARD.md`, `PORTFOLIO-BUILDER-INTEGRATION-FA.md`.

9. **Independent task phases:** rank/color/priority never means implemented; code corrected never means tested or accepted. Use `workflow.phases` and `workflow.deliverable_phase`, not legacy Task.status for phase reporting.
10. **Historical task workflows:** show unknown; initialize all its phases as unknown with explicit `task-workflow-init` on a new snapshot only; never backfill stages from historic prose.
11. **HTML consumers:** keep analysis, prioritization, implementation, verification and acceptance in separate sections. Do not modify the existing Portfolio Builder UI automatically.
