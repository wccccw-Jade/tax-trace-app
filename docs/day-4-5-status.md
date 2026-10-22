# Day 4–5: Story C — client evidence, judgment and bulk verification

Implemented October 22, 2026. Local development only; no deployment, external messages or filing.

## The story in plain language

Sometimes the app can prove a number is wrong. Sometimes it needs a person to decide what the evidence supports.

For the donated car, the client estimated $6,000, but the charity’s statement says the car sold for $2,900. The team can ask for any later correspondence, receive a client answer and file, then document the treatment with its authority. Receiving an answer does not automatically verify or approve it.

For the crypto sale, the engine does not know what the client originally paid. The client says about $3,050 in March 2021, but that statement still needs assessment. The team can request the supporting bank record, decide whether it sufficiently connects to the sold crypto, and have an independent person review that decision. A decision to request more evidence keeps the issue open.

Routine broker sales follow a simpler path: check them against the printed statement, verify the passing rows together, and leave the exceptions for individual attention.

## Start locally

```sh
make db
make migrate
make dev
```

Migration **0003** adds operation and reversal metadata to verification history. It has been applied to the local database. Restart an already-running backend so it loads the new routes.

## Try the donated-car flow

1. Choose **Priya Raman**. Open **E3** from the review queue. The claim still shows the original $6,000.
2. In **Client evidence and judgment**, expand **Ask the client**. Choose **Ngozi Okafor**. Ask for later charity correspondence or changes; D66 and the existing call already record the auction sale, so there is no need to ask those same facts again.
3. Switch to **Ngozi**. Her portal shows only questions assigned to her and the client summary. Answer and attach a small invented case-study file. For a file-handling demo, a text file clearly labeled “demo support” is sufficient; it is not additional substantiation by itself.
4. Switch to **Priya**, reopen E3, and read the answer. The answer and attachment have evidence references. Download links use authenticated routes; uploaded files are never public static assets. You may mark the question resolved after reviewing the response.
5. In **Record a judgment with authority**, select **Use documented charity sale proceeds**, record the rationale, and cite `doc:D66#page1`, `call-01`, and the new answer reference. Keep the proposed corrected value at **2900**. The form suggests the IRS Form 8283 instructions; record the authority actually relied on.
6. Save the decision. Above it, verify the proposed $2,900 correction and explain what you checked. Evidence entered for the decision is included in the verification scope automatically.
7. Switch to **Daniel Ortiz**, reopen E3, and approve the **decision** in the lower panel with an independent conclusion. The authority and correction are approved together; the generic correction-review endpoint cannot bypass the decision.
8. The approved claim becomes $2,900, the original remains $6,000, and the estimated tax changes are **+$806 federal / +$149 California**. Reloading retains the question, answer, attachment, decision and review history.

## Try the crypto C6 flow

1. As Priya, open **Crypto purchase cost and date need support** in the queue, or C6 from **Sales detail**.
2. Ask **Erik Lindqvist** for the bank-statement line mentioned in `msg-07` and an explanation connecting it to the sold BTC. Switch to Erik to answer and attach an invented case-study supporting file; switch back to Priya to assess it.
3. There are two useful demo paths:
   - **Insufficient support:** choose a treatment that requests more evidence, explain the gap and record the authority. A reviewer can approve that conclusion, but the claim stays **Needs evidence**, its current amount stays unchanged, and no tax correction is applied.
   - **Accept supported basis and date:** choose **Accept client basis and acquisition date**, record the proposed supported basis/date and explain why the collected evidence is sufficient. Cite `msg-07`, `D34`, `D35` and the new answer reference. The app does not decide that the client’s statement is sufficient.
4. If the documented decision accepts **$3,050** and **2021-03-15**, the proposed gain is **$2,275** ($5,325 proceeds minus basis), with a long-term treatment recorded separately from the engine’s short-term classification.
5. Priya verifies the correction. **Helen Strand** must approve the decision because this combined rate estimate exceeds $1,000. Daniel can review/reject but cannot approve this material adjustment.
6. The estimate removes the engine short-term gain and adds the chosen gain at the packet’s long-term rate: **−$1,312 federal / −$104 California**. This is one estimate, not a second basis-only adjustment. Thresholds and interactions are not recomputed.
7. The sales view shows the chosen basis/date, original and target box totals. Both totals and dependent Schedule D lines remain explicitly **affected**, with their engine values retained. The app does not imply it reran those calculations.
8. A later change to cited D35 evidence reopens the correction and marks the judgment stale. Fresh verification and independent partner review restore approval while preserving the earlier reviews.

## Try bulk verification and undo

1. Choose Priya and open **Sales detail**. There are **295 detail rows**: **282 broker sales**, **12 crypto sales**, and **1 basis-related distribution**. Seven box totals appear separately.
2. The initial imported data currently yields **159 eligible rows** and **136 exceptions**. These counts are derived, not hardcoded; source anchors, dispositions and recorded work can change eligibility.
3. Start with the **Exceptions** filter. Each row explains its issue: unresolved anchor, missing/mismatched basis, wash sale, other gain adjustment, or individual-review requirement. N1/N3/N4, the ESPP adjustment, wash-sale rows, crypto and the basis distribution are excluded from bulk selection.
4. Click **Select eligible rows**, enter what you checked, and **Verify selected rows**. The server rebuilds the selection from current source checks, rejects stale or ineligible selections, and saves one atomic operation. Search and individual checkboxes let you select a smaller passing group.
5. Reload: the selected rows stay verified and the operation appears in history. Verification does not change return amounts or imply independent approval.
6. Click **Undo whole batch**. All checks from that operation are marked reversed in one transaction. Their author, method, evidence and notes remain in each claim’s history. The operation remains in history too. Later edits to a selected claim block undo so newer work is not overwritten.

## What is stored and enforced

- Questions, immutable client answers, attachment metadata, decisions and bulk operations use the existing versioned `Record` nodes and evidence edges in PostgreSQL. Each write checks the expected revision and saves an audit event in its transaction.
- Client projections expose their own questions and answers, not internal decisions or staff records. Only the assigned client can answer or download their files. Staff without sensitive-data clearance cannot download original attachments.
- Files use random storage keys in the configured `ATTACHMENT_DIR`, with filename, size and SHA-256 recorded in PostgreSQL. Local files survive app restarts. A failed answer transaction cleans up newly written files. The local storage adapter must be replaced with private object storage before Heroku deployment; back up files with the database.
- A judgment requires alternatives, a chosen treatment, authority, rationale, evidence and independent review. Numeric corrections require current verification; material effects require a partner. Self-review remains blocked.
- New client evidence participates in approval fingerprints. Resolving a question administratively does not alter the underlying answer or invalidate its approval.
- Bulk verification uses printed source rows, extracted fields, resolved anchors, current document dispositions and gain arithmetic. It does not treat confidence scores as verification. Undo reverses checks; it does not erase history or original engine values.

## Validation

- **19 domain/API/PostgreSQL tests passed**, including four new Story C acceptance tests: the complete E3 client-file-to-decision flow; C6 basis/date, partner review and stale-evidence reapproval; checked bulk selection and whole-operation undo; and a reviewed request for evidence that correctly leaves C6 unresolved.
- Tests cover recipient isolation, protected file downloads, file hashes and durable reads, required authority, independent review, current verification, decision-review bypass prevention, original values retained, downstream classification labels and no duplicate tax effects.
- TypeScript checking and Vite production build passed. Local production HTTP checks passed for the built frontend, database readiness, questions, decisions, sales and client access restrictions.
- Automated mutations ran in isolated PostgreSQL schemas and temporary attachment directories. No questions, decisions, corrections or bulk operations were created in the live demo by these checks.
- Visual browser interaction remains unverified because the existing Computer Use permission blocker remains; no visual QA result is claimed.

## Authority links used by the forms

- [IRS 2025 Instructions for Form 8283](https://www.irs.gov/instructions/i8283): vehicle contribution treatment, including the gross-proceeds limitation and exceptions. The recorded rationale must explain applicability to the evidence.
- [IRS digital asset recordkeeping](https://www.irs.gov/filing/digital-assets): records supporting basis and acquisition information. This does not establish that the client’s stated purchase belongs to C6.

Version comparison, what-ifs, prior-year variance and per-user change tracking are the next story. Full filing readiness, production authentication and cloud attachment storage remain later work.
