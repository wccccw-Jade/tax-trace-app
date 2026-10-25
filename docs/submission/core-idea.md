# Miraflores: the return as claims with proof

The workpaper answers four questions about every return value: where did it come from, what changed, who checked it, and what remains open? The starting point is a review queue. Tax schedules are generated views of the same claims and evidence, rather than separate files to keep in sync.

A preparer follows a claim into the printed source, records the exact supporting passage, and verifies or proposes a correction with a reason. Engine, proposed and approved values stay separate. An independent reviewer approves the work; material tax effects require a partner. Evidence changes invalidate the approvals that depended on it. A client answer is evidence to evaluate, never automatic proof.

## Data model

| Records | Purpose |
| --- | --- |
| Packet, document, page, extraction, locator | Preserve the supplied JSON and SHA-256. Locate exact source text; retain manual anchors and document dispositions. |
| Claim and evidence edge | Identify a line by return version and key. Connect source fields, other claims, prior-year records, client answers and agency evidence in both directions. |
| Verification, adjustment, decision, review | Record method, evidence, original/proposed value, authority, rationale, contributors and independent approval. Fingerprints bind review to the evidence it covered. |
| Filing snapshot, submission, amendment | Freeze a hashed, database-protected copy per attempt. Preserve rejected copies; link resubmissions and amendments to their predecessors. |
| Policy, assignment, time entry, audit event | Version firm rules, track responsibilities/budgets and retain who changed or viewed what. Operational retention changes do not invalidate tax review. |

PostgreSQL holds these records and transactions. Expected revisions prevent one editor from silently overwriting another. Files are private attachments behind the same authorization boundary; local files serve development and an S3-compatible adapter serves deployment.

## Readiness and honest limits

Readiness is computed from current proofs, document/area coverage, outside responsibilities, blocking notes, required steps, staff sign-offs and both clients' authorization of the exact draft. Nothing is marked complete merely because it was extracted confidently.

This prototype is not a tax engine. A small checked formula registry recomputes arithmetic. Other affected lines retain an explicit basis label, and tax effects use the packet's rates as estimates. Simulated filing requires a partner to accept that limitation. Frozen copies retain the calculation basis and supporting record; later quality findings never rewrite them.
