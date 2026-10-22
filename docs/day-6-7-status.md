# Day 6–7: Story E — file, reject, correct, amend and answer the notice

Implemented October 22, 2026. This is a local simulated filing workflow. Nothing is transmitted to an agency.

## The story in plain language

A filing is a permanent copy of exactly what was approved and submitted. If an agency rejects it, that copy stays unchanged. The team corrects the working draft, obtains new approvals, and submits a new copy linked to the rejected attempt.

After acceptance, the client copy, payment model, next-year planning and examination bundle use the accepted frozen record. An amendment starts a separate branch from it.

## Start locally

```sh
make db
make migrate
make dev
```

Migration **0005** has been applied locally. Restart an already-running backend to load the filing routes. It creates the snapshot table and a PostgreSQL trigger that rejects snapshot updates and deletes.

The original filing workspace is initialized at replay date **July 10, 2026**. It starts with genuine readiness blockers. No approvals, submissions or synthetic test proofs were added to the live database. The replay date is separate from the computer clock and audit-event timestamps.

## 1. Prepare and review

Open **Readiness & filing** as Priya.

- Every current v3 claim needs current verification or an explicit independently reviewed disposition. Registered arithmetic inherits readiness only when its inputs are ready. Unsupported calculations do not inherit readiness merely because the engine produced a number.
- Every document available by the replay date needs a disposition. Future D71 and D72 are excluded until their receipt events; the initial scope contains 72 available documents.
- Pending/reopened corrections, unresolved client questions, blocking review notes, confirmed findings, warning diagnostics and required preparer steps remain visible as separate blockers.
- The default case has substantial review work left. There is no “approve everything” or “mark ready” action. Use the earlier claim workflows, the checked sales bulk-verification workflow, document dispositions and explicitly supported issue decisions.

The blocker list filters by type and reference. Open a claim/document to inspect support, or record a disposition with a conclusion, authority, rationale and evidence. Dispositions keep the stated claim value; ordinary numeric corrections use the existing correction workflow. A reviewer independently approves or rejects each disposition, and self-review is blocked.

For **California AMT**, the engine’s zero is initially labeled unresolved. Record an independently reviewed amount or an explicit reasoned “none,” with authority and rationale. A stated additional amount is included in the filing draft’s California summary and its estimation explanation; a material amount requires partner review. The app does not independently calculate Schedule P.

The nine preparer checklist items are recorded with notes and evidence. Reviewer sign-off, partner sign-off and client authorization are computed separately. Open blocking review notes prevent submission; closing an administrative note preserves the underlying claim history.

## 2. Sign the exact draft

Once technical blockers are resolved:

1. Switch to Daniel for the independent reviewer sign-off.
2. Switch to Helen for partner sign-off and the **Accept estimated computation for simulated filing** decision. The view shows the estimated summary, largest contributors and calculation limits. The decision retains that scope and rationale.
3. Substantive preparers cannot sign off their own draft. Review activity itself does not make a reviewer its preparer.
4. Switch to **Ngozi**, then **Erik**. Open **Approve & copies**, review the draft amounts and limits, and explicitly approve and authorize the exact displayed fingerprint. Both authorizations are required.
5. Changed values, covered evidence or substantive dispositions make the earlier approvals stale. They stay in history. Acknowledging or viewing a page is never authorization.

Registered arithmetic, affected engine values and the estimated tax summary remain distinct. The partner decision permits this simulated filing; it never implies an engine recompute occurred.

## 3. Submit and replay the rejection

As Priya, click **Freeze and submit simulated return**.

- The app creates a new immutable snapshot with a SHA-256 hash, household identity, every claim’s value and computation basis, summary, evidence graph, simulated pages, client evidence/attachments, verifications, adjustments and their reviews, decisions, sign-offs, client authorizations and audit history.
- Snapshot bytes remain verifiable after PostgreSQL reloads. Signed numeric zero is normalized when computing the content hash because JSONB normalizes it too.
- The submission references this snapshot. The original packet and imported engine values are not overwritten.

Click **Replay next agency response**. The first attempt records the supplied federal rejection **R0000-504-02** for Theo’s identity and California **not transmitted**. The rejected snapshot stays inspectable with its hash and original identity.

The replay advances to receipt of **D71 / msg-10** on July 13. Source access now permits that card and message; the later acceptance records and 2028 notice are still unavailable. Lists of agency events are filtered to the replay date too.

## 4. Correct and resubmit

1. Mark D71’s document disposition after inspecting it.
2. In the branch-correction form, use `household:theo`, cite **D71** and **msg-10**, and record the authority and reason. The proposed number is read from the supplied card. It does not replace the original household record or the rejected copy.
3. Daniel independently reviews the correction. Its tax effect is zero, but it still needs review and new exact-draft authorizations.
4. Resolve any newly exposed blockers, then repeat the reviewer/partner/computation decisions and both client authorizations against the corrected draft.
5. Freeze a corrected submission. It references the rejected attempt and uses a **new snapshot**, linked to the rejected snapshot as its parent.
6. Replay federal acceptance, then California acceptance separately. Each agency event remains attached to the snapshot actually submitted. Earlier attempt history is retained.

Changing evidence after a branch correction is approved marks it stale and excludes it from the draft until a fresh correction is reviewed.

## 5. Download the accepted client copy

After both agencies accept, download the **accepted client copy**. It is a standalone HTML file generated from the accepted snapshot, including the submitted household identity, summary and all claim values with computation-basis labels. It never reads current live values to reconstruct the filed copy.

Clients can download accepted copies for this household. Internal frozen-record and examination exports remain staff-only; staff without clearance cannot download complete original records. Rejected copies stay available for staff inspection, but are not presented as accepted client copies.

## 6. Record post-filing events

Each action names its accepted snapshot:

- **Payment and refund:** use its filed balances, not the original v3 balances. Federal Form 2210 penalty is shown separately. Interest and failure-to-pay use the supplied fixture rates with explicit simple-daily-interest and whole/partial-month assumptions. California refund follows the frozen overpayment; if the frozen draft instead has a balance due, the record identifies the modeled liability rather than inventing a refund. This is a fixture-rate model, not a complete agency account calculation.
- **2026 roll-forward:** copy the frozen carryover record with its engine/unrecomputed basis stated. Show the 110%-of-2025-tax planning benchmarks and packet installment dates/percentages, plus the known 2026 changes. Current-year tax and withholding are not assumed; the 90% alternative is not silently estimated. Carryovers affected by adjustments still require review.
- **2028 Letter 566:** advance to the supplied notice receipt. D72 and the notice become visible. The dashboard identifies the response deadline and items examined.

The supplied April extension/payment information remains visible as a historical event based on v2. These controls do not file extensions or make real payments.

## 7. Export the examination bundle

After recording the notice, download the **examination bundle ZIP** for the accepted snapshot. It contains:

- An HTML index and the frozen client copy.
- Claims and computation bases, evidence records and edges, checks, adjustments with review history, decisions, sign-offs, client authorizations and audit events.
- Simulated source pages, including the already-existing **D66 vehicle** and **D14/D15/D21 business-receipts** support.
- Frozen attachment bytes, notice metadata, the frozen snapshot and a manifest with sizes and SHA-256 checksums for every other archive entry.

The notice is a later event. It is included as notice metadata, not inserted retroactively into the submitted evidence. D72 is not fabricated as a document that existed at the original submission. Access requires staff clearance.

## 8. Create an amendment

Choose **Start amendment branch** on an accepted copy.

1. The branch names that accepted parent and inherits its frozen base. It requires a supported amendment correction; an empty amendment is not ready.
2. Record a numeric source-line correction, authority, reason and evidence. Its effect is measured from the accepted parent amount. Derived totals cannot be independently overwritten. Current configured tax-effect mappings are required.
3. An independent reviewer approves it, or a partner if its tax effect exceeds $1,000. Revised evidence makes its review stale. Rejected/superseded corrections remain in branch history.
4. Obtain fresh reviewer/partner/computation decisions and both client authorizations. Freeze and submit the amendment as a separate child snapshot.
5. Amendment acceptance uses clearly labeled simulated events and IDs; it does not reuse the packet’s original-return agency IDs. Parent snapshots, accepted original values and earlier agency events stay unchanged.

This creates an amendment record and frozen simulated return. It does not generate an official Form 1040-X or transmit one.

## Validation and practical limits

- **28 domain/API/PostgreSQL tests passed**, including four Story E acceptance tests: genuine blockers and explicit AMT disposition; complete rejection → correction → acceptance → exports → amendment; readiness inheritance only through registered arithmetic; and blocking notes with preserved approval history.
- Tests verify original/corrected identities, exact-draft client approvals, self-review restrictions, separate federal/state events, retained parent hashes/content, private downloads, linked review/evidence exports, ZIP checksums, stale amendment evidence, planning/payment bases and database rejection of snapshot updates/deletes.
- To reach later filing states without hundreds of manual entries, acceptance tests create explicitly synthetic reviewed proofs for the remaining scope **inside disposable test schemas only**. E3/E4 still use their real correction/verification/review APIs. No such proofs or shortcut exist in the product or live database.
- TypeScript checking and Vite production build passed. Migration 0005 was applied locally; offline migration SQL generation passed. Local HTTP checks verified genuine blocked readiness, client projections, source visibility and the database snapshot guard. The live database contains no test submission or snapshot.
- Visual browser interaction remains unverified under the existing Computer Use permission blocker; no visual QA result is claimed.

Remaining breadth work in `plan.md` includes the other tax-area views, assignments/policies, quality-review workflow, production authentication/storage, deployment and backup/restore. The tax engine, official amendment forms and real agency/payment connections remain outside this simulator.
