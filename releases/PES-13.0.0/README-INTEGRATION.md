# PES-13 Portable Package

This ZIP contains the latest Project Evolution Standard package currently used in this project line.

Files:

1. `Project-Evolution-Empty-Bootstrap-PES-13.json`
   - Raw empty Project Evolution bootstrap artifact.
   - Use this as the starting structure for a new project.

2. `PES-13.schema.json`
   - Structural JSON Schema.

3. `PES-13.semantic-rules.json`
   - Normative semantic rules and invariants.

4. `PES-13.compatibility-profile.json`
   - Migration/compatibility guidance from older PES versions.

5. `PROJECT-EVOLUTION-START-HERE-PES-13.md`
   - Generic Help / onboarding contract.
   - A project may create a project-specific START-HERE file based on this.

Integration recommendation:
- Keep `project_id` stable for the lifetime of a project.
- Do not infer unknown values.
- Preserve material history.
- Keep Analysis, Solution, Decision, Requirement, Task, Verification and Acceptance distinct.
- For Tasks, use P0/P1/P2/P3/unassigned.
- If using Git or another shared store, implement stale-writer compare/merge behavior.
- Treat the Project Evolution artifact as portable durable project memory, not as temporary chat context.
