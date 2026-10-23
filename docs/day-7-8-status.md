# Day 7–8: breadth pass

Implemented October 23, 2026. Local development only. No deployment or live tax approvals were performed.

## What you can try

Run `make dev`, open http://127.0.0.1:5173, and select a demo identity. The existing migrations are sufficient: new coordination records use the existing versioned PostgreSQL records table.

### Tax views

Open **Tax views** and choose a view:

- Tax computation: federal and California return lines and tax worksheets as supplied, with current approved corrections and computation labels.
- Depreciation: all nine assets, methods, lives, federal/California/AMT amounts, disposals and related Form 4797 recapture lines.
- Rentals and passive losses; K-1 income; basis by year; retirement and foreign items; deductions and credits with their supplied limits; payments and agency records; California split; carryovers; prior preparer vs our work.

Views are read-only. Each line opens the existing claim/evidence panel. Supporting sections expand instead of placing hundreds of details on the first screen. Missing basis remains unknown. The S-corporation reconciliation separately derives the 2023/2024 roll-forward from D40 and the prior return; it does not silently alter a claim. Carryovers out remain labeled engine v3 when they have not been recomputed.

### California wage reconciliation

Choose **California split**. D73 reports Halvorsen CA taxable wages of 22,469; its annual W-2 reports 111,300. The 88,831 difference is a reconciliation item. Combining the paystub figure with Corvane's W-2 gives a candidate of 129,569, not an automatically accepted allocation.

Open `SchCA540NR.1.E` → **Questions & decisions**. Reconcile work dates, transition-day pay and HSA treatment, cite D73, and record authority and rationale. An explicitly supported corrected value can become a judgment-linked proposal. Verification and independent approval still apply; the supplied California-source rate produces an estimate only, with no federal tax change. A sufficiently large correction requires the partner under the current policy. The D73 filing check remains open until a current accepted decision or an independently reviewed explicit disposition resolves it.

### Questions to colleagues

A claim's **Questions & decisions** view can send a question to a client or a preparer/reviewer/partner. Switch to its assigned recipient to answer or attach a file. Staff threads never appear in the client portal. A colleague who contributes material evidence is treated as a preparer for self-review restrictions. Answers do not constitute approval.

### Team, deadlines and updates

**Team & deadlines** shows the packet's initial engagement roles, saved task assignments, all six packet deadlines, nine area budgets and durable time entries. Assign a claim, document or engagement role to a staff member, with a deadline and hand-off note. Overdue labels use the replay date.

**Updates** polls every 15 seconds for assignments, unresolved questions, past-due deadlines and other people's saved activity. Marking an update seen persists per identity. Other screens do not overwrite an unsaved form just because another user saves work.

To demonstrate conflicts:

1. Use two separate browser sessions, such as a regular window and a private window. Tabs in one profile share the role cookie.
2. Create an assignment in one session, then load that assignment in both sessions.
3. Save a revised hand-off note from the second session.
4. Save the older version from the first session. The server rejects it with HTTP 409 and identifies the latest revision, author and note.
5. Choose **Reload latest records**, review the other person's change, and then save deliberately.

### Completeness

**Completeness** lists every currently available document, 13 review areas and six outside/related-return responsibilities: FBAR, contractor 1099-NECs, Ada's return, the S-corporation and partnership returns, and the prior foreign-inheritance/Form 3520 follow-up.

Record an area's scope conclusion, and record the owner, status and communication for outside responsibilities. Document dispositions use the existing document review panel. Missing outside returns are not invented. Area acknowledgment does not verify its individual claims. Unaddressed areas and outside responsibilities block original-return filing, alongside the existing claim and document gates. Changes to these reviewed scope records invalidate the final filing fingerprint.

These are working controls, not pre-completed review work. The live database retains its actual unresolved documents, areas and responsibilities.

### Firm standards and retention

Select **Jo Kimura** → **Firm standards**. The versioned editor controls verification methods, combined variance thresholds, partner threshold, required steps and retention years, with an explanation and history. Independent reviewer, partner and client-authorization gates cannot be removed. Other staff can read standards but cannot edit them.

- Retention-only changes preserve tax-review fingerprints.
- A stricter partner threshold reopens an existing reviewer-approved correction when it now requires a partner; an independently partner-approved correction remains approved.
- Removing the method that supports a verification makes that verification noncurrent and reopens affected correction approvals. Bulk verification cannot use a prohibited method.
- Filing fingerprints cover the relevant tax policy, so covered sign-offs and client authorizations become stale when that policy changes.
- Newly frozen copies include the actual standards and standards revision used, not just packet defaults.

The same page exposes the latest 100 access/audit events and retention eligibility for frozen submissions. Administrators can place or release a hold with a reason. Eligibility uses the replay date and configured years after submission. Deletion is disabled.

### Quality review and search

Helen can inspect submitted copies in **Quality review**. After replay reaches January 4, 2027, Sam can inspect frozen lines, support, decisions and sign-offs, then save a separate quality finding. He cannot change the filed history. With no genuine submission, this view shows an empty state; it never manufactures a filed return.

**Search** finds current return lines, available documents, client evidence, questions, decisions and saved review work. Searches are capped at 100 results. Unauthorized sensitive values are masked before matching, and future documents/transcripts/notices stay unavailable until their replay dates.

## Verification

- Production frontend build and TypeScript check passed.
- **All 35 domain/API/PostgreSQL tests passed**, including seven new breadth acceptance scenarios. These cover the original stories and the breadth features, including isolated two-session conflicts, policy changes, colleague evidence, state-wage judgment, completeness gates, quality findings and retention holds.
- Live local HTTP smoke checks verified generated views, team data, updates, search, standards, retention, quality empty state, computed blocked readiness and frontend delivery. No live assignment, policy, correction, approval or submission was created.
- Browser visual/interaction verification remains unavailable through the current computer-use connection. Responsive layout, keyboard behavior and new forms have not been manually browser-verified.

See [requirement coverage](requirement-checklist.md). Heroku/private object storage, backup/restore, final artifacts and video remain later tasks in `plan.md`.
