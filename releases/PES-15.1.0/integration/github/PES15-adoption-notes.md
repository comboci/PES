# Proposed side-by-side GitHub adoption (NOT pushed)

- Do not overwrite `project evolution/PES-14-STANDARD.md`.
- Do not overwrite `project evolution/PROJECT-EVOLUTION-START-HERE-PES-14.md`.
- Do not overwrite `project evolution/Project-Evolution-V1-PES-14.json`.
- Do not redirect existing hourly automation to PES-15 without user approval.
- Put the new PES-15 reference implementation in a new version-specific directory, preferably on a review branch.
- Run unit tests and read-only `tools/evaluate_portfolio_builder.py` against a separately fetched latest PES-14 snapshot.
- Review the generated migration and verification report before enabling PES-15 writers.
- Connect the Portfolio Builder app with an adapter that calls the validator and the SQLite CAS store.
- All implementation/test/acceptance states must remain epistemically separate.
