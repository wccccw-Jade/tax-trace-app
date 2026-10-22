# Miraflores tax workpaper: product and implementation plan

Status: revised plan, ready to build.
Revised: October 21, 2026.
Scope: one complex household (Okafor-Lindqvist), tax year 2025.

## 1. What we are building and how it will be judged

A web app, run from a link, that proves the 2025 return is right: where every number came from, what was done to it, who checked it, and what is still open. It must load the packet as delivered, save everything to shared storage, and have a role switcher.

The brief sets three tests:

1. **Everything in the brief works**, even if some of it only works simply. Missing a capability costs more than polish does.
2. **It is invented from the purpose.** No spreadsheet and no traditional workpaper sections with new labels.
3. **A 20-year CPA finds it faster and more trustworthy; a new hire can use it on day one.**

There are four deliverables: the app, a one-page note on the core idea and data model, an error report, and a video walkthrough. "Sending sooner is better," so the plan is built around a fixed time budget (section 9).

## 2. Core idea: the return as a set of claims with proof

Every number on the return is a **claim**. The workpaper's job is to make every claim that is in scope *proven* or *knowingly accepted*. Each claim's history stays attached to it.

A claim's status has three separate parts. They are stored independently, because one claim can be in several states at once (for example contradicted *and* stale).

| Part | Values | Notes |
| --- | --- | --- |
| Evidence | missing · cited (extracted field) · cited (manual page anchor) · client statement · third-party / agency record | Describes what the support *is*, not whether it is good enough. An unextracted page, a low-confidence read or a client answer can still support a verified conclusion once a person has reviewed it. |
| Checks | not applicable · passed · failed (discrepancy) · open question | Results of independent checks (section 6), each with the inputs it derived |
| Review | not reviewed · verified (method, evidence, revision) · accepted by judgment (decision, authority, approver) · stale (reason) | Stale means a verification or approval was given, and then something it covered changed |

The **queue label** is derived from the three parts, and the first match wins: *Contradicted* (a check failed) → *Needs evidence* (evidence missing, or a locator is unresolved) → *Stale* → *Needs review* → *Done*. Extra badges show any other conditions that also apply.

What follows from this:

- **The main screen is a queue, not a form tree.** Open claims are ranked by queue label, then by estimated tax effect. "What should I do next?" has one answer for a new hire. "Where is the risk?" has one answer for a partner.
- **Tax areas are filters on the queue**, not separate documents. "Investments" means claims tagged investments. The records a CPA expects (depreciation schedule, books to tax, state split and so on) are generated views over the same claims and evidence. They are never edited separately.
- **Evidence is a graph.** Each claim links to one or more sources: document fields, client answers, agency records, prior-year values, other claims. Following a number traces it down to the source. Following a document traces it up to everywhere it landed, or records why it didn't.
- **Readiness to file is computed, not declared.** It applies only to **in-scope claims**: the lines of the current return revision plus every input that feeds them through evidence edges. Superseded, duplicate or unused extractions need only a document disposition, not a review. Every in-scope claim must be *Done*, meaning one of:
  - **Leaf claim** (fed directly by a source): verified or accepted by judgment, with a resolved evidence reference. The reference type depends on the source: document field (with a locator), client answer, agency record, prior-year value, or engine parameter.
  - **Derived claim** (built from other lines): it inherits *Done* when its arithmetic check passes and all its inputs are Done. This is how 295 Form 8949 rows can support 7 box totals without anyone signing every total.
  - **Derived claim whose rule cannot be checked independently** (tax brackets, phase-outs, SE tax, QBI, AMT, credit limits): a person verifies it explicitly, or it goes through the estimation contract in section 8.

  In addition, every required step must be complete and no blocking review note may be open. Sign-offs are attached to a fingerprint of the claims they cover, so they go stale automatically when a covered claim changes.
- **Engine output is one witness, not the truth.** Within a single document, the printed page beats the extracted value. That only establishes what the document says, though. When documents disagree with each other (a corrected statement vs the original, an agency transcript vs a client record, late evidence vs early evidence), the conflict is resolved by an explicit, recorded reconciliation or decision, never by a fixed ranking. Confidence scores never count as verification.

This idea is what the one-page deliverable explains. Every screen should be explainable in terms of it.

## 3. Inputs and constraints

### Packet facts (verified)

- 74 documents and 3,012 extracted values. D07, D69, D70 and D72 are not extracted; D30 and D31 are partial.
- Three engine versions. v3 (2026-06-23) is current and has 627 lines, 9 assets and 11 diagnostics. 302 of the lines are Form 8949 rows: 295 detail rows (282 brokerage transactions, 12 crypto disposals, and 1 S-corporation distribution in excess of basis) plus 7 box totals.
- `printed_content` is the truth for each page. It is a single prose paragraph, not a laid-out form.
- `text_as_read` often doesn't appear word for word in `printed_content`: dates are reformatted, checkboxes read as "X", page totals are derived. A naive substring match fails for about 889 high-confidence values.
- Events after v3 (client approval, e-file rejection and acceptance, payment, refund, quality review, next-year roll-forward, the 2028 Letter 566) are scripted replay material.
- The staff list includes a preparer without sensitive-data clearance (st-04, Marcus Bell) and a quality reviewer active only from 2027-01-04 (st-06).
- Starter standards: five verification types; variance flagged at more than 10% *and* more than $1,000; partner sign-off for any adjustment whose tax effect exceeds $1,000; 12 required steps; seven-year retention.

### Rules

1. Load the packet unmodified. Store the original and its hash.
2. Keep engine values, proposed adjustments, approved workpaper values and estimated tax effects distinct, in both the data and the UI.
3. Do not build a tax engine. A tax effect is the change multiplied by `tax_effect_rates` (as the README allows), labeled as an estimate. Only a small formula registry is recomputed exactly; other affected lines are labeled, not recomputed (the computation contract in section 8). Supplied `what_if` results apply only to their stated base version and are never added together.
4. Simulated documents are rendered from `printed_content` and labeled as simulated. Never fabricate a scan.
5. Replay never shows evidence before the time it arrived.
6. Related returns outside the packet (Ada's own 1040, the 1120-S, the 1065) appear as linked records with missing evidence. Their contents are not invented.

## 4. Errors found so far (Day-0 audit)

The audit runs **first**, because the errors decide which checks and screens we build, and the error report is a deliverable. Four confident mistakes are already confirmed from packet evidence. Tax effects are v3 rate estimates.

| # | Error | Evidence | Correction | Est. effect (fed / CA) |
| --- | --- | --- | --- | --- |
| E1 | **Interest counted twice.** The Northlake Bank sweep interest of 1,840 appears as SchB.1.1 (from the D28 consolidated 1099) and again as SchB.1.2 (from the D29 standalone 1099-INT). | D29 says it is the "bank sweep program for Northlake Securities account ending 7731". D28 lists the same sweep for account 7731. | Remove SchB.1.2 (−1,840) | −640 / −127 |
| E2 | **Wrong exchange rate.** Swedish interest of SEK 18,450 (ev-0960, D36) was converted at `fx.SEK.2024_average` (10.56) to 1,747. 2025 income calls for the 2025 average (9.86), which gives 1,871. | SchB.1.6 sources cite `ref:fx.SEK.2024_average`; `fx_rates` has `2025_average` | +124 interest | +43 / +9 |
| E3 | **Vehicle donation overstated.** Form 8283 claims 6,000 for the 2012 Subaru, based on the client's Kelley Blue Book figure (qa-39). The 1098-C (D66) shows the charity sold the car at arm's length for gross proceeds of 2,900. | F8283.A1.vehicle sources are qa-39 plus only the *date* from D66 (ev-1055); the 2,900 in box 4c was not used | Limit to 2,900 (−3,100 itemized) | +806 / +149 |
| E4 | **1099-K counted twice in gross receipts.** SchC.1 = 163,700 = book revenue 151,300 + 1099-K 12,400, because rule R-SCHC-GROSS treated the 1099-K as unmatched. D15 says Atlas Outdoor Gear's 41,200 includes 12,400 "through Paywell Payments card processing (deposited gross)", so it is already in book revenue. | D14, D15, D21, D17 | Gross receipts 151,300 (−12,400) | −4,402 / −384. The `schc_profit` rate already combines income tax, SE tax and QBI. It is a single combined estimate measured at v3 numbers, so threshold and interaction effects are not captured. |

E4 is above $1,000, so it requires partner sign-off, which makes it a good demo of that rule. call-01 supports E3 independently ("the charity sold it at auction"). E3 and E4 are exactly what the 2028 IRS Letter 566 examines (Form 8283 noncash gifts; Schedule C receipts against 1099-NEC 142,000 and 1099-K 12,400). The demo should show that the workpaper surfaced both **before filing**, and that the notice response is a one-click export of evidence that already exists.

### Open leads (to finish in the Day-0/Day-1 audit)

| Lead | Trigger | Question to settle |
| --- | --- | --- |
| Broker mismatch | v3: Meridian summary proceeds 71,965 vs extracted lots 71,715 | Which lot is missing or misread? Is it in the corrected D31? |
| Corrected brokerage statement | D30 → D31, both partial | Do v3 lots come only from the replacement? |
| Duplicate W-2 upload | D09/D10, msg-02 | Prove wages are counted once. A *valid* duplicate is not an error. |
| Crypto lot C6 has no basis | Diagnostic; msg-07 | What evidence supports the client's claimed basis and date? |
| Handwritten receipt | D64 confidence 0.41; msg-08 | Printed value vs extracted vs client confirmation |
| S-corporation basis gap | D39/D40; diagnostic disappears in v3 | Does the late 2023 K-1 actually close the gap? |
| California-source wages | D73 paystub, mid-year move | Allocation by work and pay period, not a blanket day fraction |
| California AMT not computed | `CA_AMT_NOT_COMPUTED` | Owner, evidence and explicit resolution before filing |
| Questionnaire conflict | qa-14 "no sales" vs 282 sales and 12 crypto disposals | Record the client correction |
| Underpayment penalty (Form 2210) | 164 in every version | Check against the Form 2210 rules, not `post_filing_rates` (those apply to late payment after filing). The required annual payment of 41,313 is 110% of the 2024 tax of 37,557, so the prior-year safe harbor governs and an unchanged penalty is expected. Remaining checks: installment timing, how withholding is treated, the annualized alternative (also 164; `penalty_annualized` what-if = 0 change), and the penalty decision record. |
| Business mixed use | D15: books charge the family phone plan (4 lines) and home internet at 100%; "Spotify Family" sits in software | call-01 already supplies the percentages: phone 70%, internet 50%, Spotify personal ("booked by mistake"). The task is to evaluate that client statement as evidence, decide, and apply the books-to-tax adjustments, not to ask the client again. |
| Home office | 240 vs 300 sq ft prior year | Explain the variance |
| Outside filings | FBAR, late 1099-NECs (2026-02-02 already missed), Ada's own return | Responsibility and communication, not filing |
| Dependent identity | e-file rejection R0000-504-02 for Theo; D71, msg-10 | Keep submitted, rejected and corrected identities separate |
| Unextracted documents | D07, D69, D70, D72 | Manual citations at page level |

Method: a small script audit (`scripts/audit/`) that (a) normalizes and compares printed values to extracted values, (b) re-derives totals and subtotals from line inputs where the arithmetic is known, (c) checks every `ref:` and FX citation against the tax year, and (d) cross-checks documents that should agree (books ↔ 1099s ↔ deposits, broker summary ↔ lots, payments ↔ agency transcript). Each check that finds something becomes a product check in section 6.

For each confirmed error the report records: sources, printed / extracted / engine values, the independent check that caught it, the correction, the tax effect and how certain it is, the reviewer, and **the UI path that surfaced it**.

## 5. Product structure

### Screens

- **Queue (home):** open claims ranked by effect and severity, with filters for area, queue label, owner, "changed since I last looked", and blocking only. Each role starts from its own default filter.
- **Claim view:** the value, its queue label and the reason for it (evidence, checks, review), a trace (source field → extracted value → transformation → return line), checks, history, adjustments, notes, questions and sign-offs. Actions: verify, adjust, ask, decide, note.
- **Source drawer:** the simulated page with the exact field highlighted, printed vs extracted vs engine values, confidence, verification history, and "where used". It is available from anywhere.
- **Documents:** an index of all 74 documents with a disposition for each: used, superseded, duplicate, supporting, outside scope, unextracted–reviewed, unresolved. Anything other than "used" requires a reason.
- **Views (records a CPA expects):** generated, read-only views with drill-down to claims. Return vs last year, tax computation, depreciation by asset (federal / CA / AMT, bonus, disposals, recapture), sales detail (295 rows rolling up to 7 box totals: totals and exception groups first, then searchable detail), books to tax, rentals and passive losses, K-1 lines, basis by year, retirement and foreign items, deductions and credits with limits, payments vs agency records, state split, carryovers, and prior preparer vs our changes.
- **Readiness and filing:** required steps, blockers, client approval, extension, submissions, rejection and acceptance, frozen copies, amendments, notice response, carryforward and 2026 estimates.
- **History:** version compare (v1/v2/v3 and our revisions), activity, and a replay slider.
- **Firm:** standards (versioned, editable by the administrator), roles and clearance, access log, time vs budget, search.

### What-ifs

- **Supplied scenarios** (the five in `what_if`): shown against v3 only, side by side, never combined.
- **User what-ifs:** pick any claims, enter a change, and see the rate-based estimate with its limits stated (thresholds, QBI, SE tax). Nothing is saved unless it is turned into a proposed adjustment.

### Source document design (built to be replaced later)

- `DocumentRenderer` interface: `render(document_id, page) → view`. The simulated implementation renders `printed_content` with a template per `document_type` (W-2, 1099, K-1, P&L, log, letter) so it reads like the form it represents. A real-scan implementation would render the image.
- `Locator` type: `{document_id, page, anchor}`, where `anchor` is either `{kind: "text", start, end, quote}` (simulated) or `{kind: "box", x0, y0, x1, y1}` (real scans; the packet's synthetic `position` already has this shape).
- Locators are built in three layers. Each locator records which layer produced it.
  1. **Field mappings per document type** for the common forms (W-2 boxes, 1099 boxes, K-1 lines, P&L accounts): a field name maps to its label pattern in `printed_content`.
  2. **Normalizing matcher** for everything else: numbers without commas and $, dates in several formats, checkbox words, and a label near the value. It accepts only a unique match.
  3. **Manual anchor:** a person selects the passage in the simulated page. The anchor is saved with who set it and when, and it counts as evidence.
- If none of these gives a unique match, the locator is **unresolved**. The page is shown, an unrelated passage is never highlighted, and the claim is labeled *Needs evidence*. An unresolved locator is a temporary state, not an acceptable final trace. It blocks readiness for in-scope claims, and every claim used in the demo or the final record gets a field mapping or a manual anchor.

## 6. Independent checks (do not trust the engine)

Each check computes its own inputs from the sources, shows them, and produces a result: proven discrepancy, valid duplicate, open question, or judgment call. Checks are listed separately from the engine's diagnostics.

- Duplicate and superseded documents (E1, D09/D10, D30/D31).
- Printed vs extracted where the field can be matched.
- Line arithmetic where the transformation is known. `R-SUM` is not assumed to mean addition with plus signs.
- Citation checks: FX and parameter references match the tax year (E2).
- Document agreement: books ↔ 1099-NEC/1099-K ↔ deposits (E4); broker summary ↔ lots; W-2 count ↔ wages; payments ↔ IRS/FTB transcripts.
- Charitable substantiation: a noncash value vs third-party evidence such as the 1098-C (E3).
- Carryovers, basis rollforwards, depreciation totals, federal vs CA differences.
- Residency dates and California-source allocation.
- Variance against prior year using the firm threshold, with a zero prior-year value handled separately.
- Completeness: every document disposed of, every area considered, due diligence (Form 8867), outside filings.

## 7. Roles and enforcement

The role switcher sets the acting identity on the server in a clearly labeled demo. It is not production authentication.

| Role | Can | Cannot |
| --- | --- | --- |
| Preparer (st-01, st-04) | Verify, propose adjustments, record judgments, ask questions, hand off | Review or sign off their own work |
| Reviewer (st-02) | Review, write notes (which can block filing), approve others' work | Approve anything they contributed to |
| Partner (st-03) | Approve adjustments over $1,000 and final readiness | Bypass separation of duties |
| Client (client_users) | Answer, attach, view the client summary, approve and authorize | See internal notes, settings or staff edits |
| Firm administrator (st-05) | Standards, assignments, permissions, budgets, retention | Sign off on tax work |
| Quality reviewer (st-06) | Inspect frozen records and record findings | Change filed history |

- Clearance is separate from role. Unmasking happens on the server, covering API responses, document text, search, notifications and exports. Every unmasked view is logged. Marcus Bell (st-04) is the demo case.
- During replay, a person can act only from their `active_from` date.
- For the self-review rule, the system tracks **preparers**, not everyone who touched a claim. A preparer is anyone who changed the claim's value, evidence or disposition: they authored an adjustment, a verification, a decision, a manual anchor or a document disposition. Review activity (review notes, comments, earlier sign-offs, requests for changes) does not make someone a preparer. A reviewer who later edits a claim substantively becomes its preparer and cannot then sign off that claim.

## 8. Architecture and data model

### Stack: chosen for speed to a working link

- **Backend:** FastAPI + Pydantic (Python, which also runs the audit scripts and the import). `main.py` is the entry point.
- **Frontend:** React + TypeScript + Vite, built and served by the same FastAPI process from one origin.
- **Storage:** PostgreSQL from day one, accessed through SQLAlchemy. Run PostgreSQL locally in Docker Compose (no native PostgreSQL installation); use Heroku Postgres when deploying. Attachments use local storage during development and private object storage (such as S3) on Heroku. Heroku's dyno filesystem is used only for temporary files, never durable records.
  - Configure the database through `DATABASE_URL` and the file-storage backend through environment variables. Local and hosted databases stay separate; both use the same schema migrations and packet importer.
  - Keep write transactions short, enforce database constraints, and check expected revisions in both environments.
  - Use Alembic schema migrations from the initial setup. At deployment, apply them to Heroku Postgres and import the supplied packet; local test data does not need to be transferred. Add and test the object-storage adapter before deployment.
  - Configure database backups and attachment recovery; test restoration before submission.
- **Live updates:** each client polls for changes every few seconds using a revision cursor. Server-sent events and presence indicators are out of scope.
- **Hosting:** Heroku. Build and test locally first; begin deployment only after a working prototype is ready. FastAPI serves the built React frontend and API from one origin. At deployment time, add the Heroku build/start configuration, bind the server to the provided `PORT`, configure environment variables, and verify that saved records and attachments survive restarts and redeployments. Only the invented fixture is deployed.
- **Tests:** pytest for import, permissions, sign-off invalidation, conflicts and checks. A single Playwright smoke test of the main demo story only if time allows.

Tradeoff to state in the video: PostgreSQL in both environments avoids a later database-engine migration and keeps database behavior consistent. Local development needs a PostgreSQL service, but hosting is still deferred until the prototype is ready. Polling stays the same in both environments; push updates are not needed for this prototype.

### Entities

All packet IDs and JSON paths are kept. Line keys are scoped to their version.

| Entity | Key fields |
| --- | --- |
| PacketImport | original JSON, hash, import report |
| Document / Page / Extraction | packet fields, disposition and reason, supersedes / duplicate-of |
| Locator | document, page, anchor (text span or box), resolved flag |
| Claim | version-scoped line key or extracted-value id, value, evidence / check / review status, area tags, preparers, revision |
| EvidenceEdge | from, to, kind (source / input / supersedes / duplicate / supports / contradicts), version scope, resolved |
| Check / CheckResult | rule, derived inputs, expected vs actual, result type, disposition |
| Verification | claim revision, method (firm verification type), evidence, actor |
| Adjustment | claim, original, proposed, delta, reason, evidence, category, estimated effect, status |
| Decision | question, alternatives, choice, authority, rationale, approver, linked what-if |
| Note / Question | audience, blocking flag, assignee, due date, thread, responses become evidence |
| SignOff | scope, signer, role, fingerprint of covered claims and standards version, valid / stale with reason |
| AuditEvent | actor, UTC time, action, subject, before/after, operation id (for bulk actions and undo) |
| FilingSnapshot | immutable; one per submission attempt (including rejected ones); content hash, jurisdiction, revision, the computation basis of each line (section 8), authorization |
| Submission | snapshot, agency submission id, status (transmitted / rejected / not transmitted / accepted), errors, link to the earlier submission it corrects |
| Amendment | parent: the accepted snapshot; a branch of new revisions; never changes the parent |
| CarryForward | origin snapshot, amount, jurisdiction, next-year status |
| FirmPolicy / TimeEntry / LastSeen | versioned standards; hours by area against budget; last-seen revision per user and scope |

### Rules for writes

- Every write sends the revision it expects. A stale write returns a conflict along with the other person's change.
- Each change and its audit event commit in one transaction.
- A bulk action has one operation id and commits all at once. Undo applies a reversing change; history is never erased.
- Changing a claim marks dependent claims and sign-offs stale by walking the evidence edges.
- Money uses Decimal. A missing value is never treated as zero.

### Computation contract: from adjustment to the filed return

There is no engine rerun, so every line on the return carries a **computation basis**, and the UI, snapshots and exports show it:

| Basis | Meaning |
| --- | --- |
| `engine` | v3 value, unaffected by any workpaper adjustment |
| `recomputed` | Recalculated by our arithmetic from adjusted inputs, using the formula registry below |
| `affected` | Depends on an adjusted input, but we do not recompute it; the v3 value is shown with an "affected, not recomputed" label |
| `unresolved` | The engine did not compute it (California AMT), and no conclusion has been recorded yet |

Tax effect is a separate number, never a line value: each adjustment's estimated effect (change × category rate) is shown once, in the tax summary panel, as federal and California deltas to total tax. Rates estimate tax change only, so they are never applied to AGI, taxable income, QBI or individual credit amounts. Payment adjustments are not rate-based: they change payments and balance due dollar for dollar and are left out of the estimated tax change. Credit adjustments change total tax dollar for dollar, as the packet specifies, so they are applied exactly rather than through a rate.

**1. Formula registry (what we recompute).** A small, explicit list of formulas, only for the arithmetic the demo needs, for example:
- Document-to-line mappings: W-2 box sums, payer interest and dividend lines, books lines to Schedule C, rental lines.
- Form 8949 rows rolling up to box totals and Schedule D.
- Schedule C gross receipts, meals at 50%, mileage, simplified home office, cash and noncash gifts, depreciation sums.
- Plain carries, estimated payments and extension payment.
- California sourcing, one rule at a time (never one "SOURCE" formula): interest, dividends and business by residency days (195/365); wages from W-2 box 16; IRA conversions by transaction date; capital gains by sale date (with the packet's other allocation rules); rentals by property location and activity.

Each registry formula is checked once against the supplied versions (it must reproduce the v3 value with no adjustments). If it does not match, it stays out of the registry and the line is `affected`. We don't try to infer formulas from the snapshots. Anything not in the registry (R-SUM lines included, unless added deliberately) is left unchanged and labeled.

**2. What is not recomputed.** Everything built on thresholds, limits, rate schedules or interactions: SE tax, SEP, SE health insurance, QBI, tax worksheets, AMT, surtaxes, credits and their phase-outs, SALT cap, deduction choice, passive losses, 8606, penalties, and California tax and credits. These and the lines above them (AGI where it depends on them, taxable income, total tax, balance due) show as `affected`.

For the summary, total tax shown = v3 total tax + the sum of each rate-based adjustment's estimated effect (plus credit adjustments dollar for dollar), counted once, labeled an estimate with its limits (rates measured at v3, thresholds can be crossed, interactions not modeled). Payments are reconciled separately and exactly, including any payment adjustments: balance due = estimated total tax − payments.

**3. How estimates affect simulated filing.** The required step "Final computation" has two possible resolutions:
- **(a) Engine recompute.** Not available in this case study. It is the production path: the adjustment set is exported as engine input overrides.
- **(b) Partner decision.** A partner records "accept estimated computation for simulated filing". The decision states the total estimated change, the largest contributors and their limits.

An estimate never satisfies this step silently. Every `unresolved` line needs its own disposition before readiness. For example, California AMT needs a documented conclusion on whether the incentive stock option exercise is California-source, with authority and an amount or a reasoned "none". The replayed approval, rejection and acceptance events run against whatever snapshot results.

**4. What the frozen copy calls final.** The snapshot and client copy show the values as submitted, and label each line with its basis. The header states that this is a simulated filing, which lines are affected but not recomputed, that the total tax in the summary is a rate-based estimate over the engine's v3 computation, and that a production filing requires an engine recompute. "Final" means *frozen as submitted*, not *exact*. Replayed post-filing amounts (federal balance paid, California refund) come from the submitted snapshot, as the README specifies ("the return as your workpaper finalizes it"). Late-payment interest and penalty come from `post_filing_rates`.

## 9. Build plan: demo stories, time-boxed

Assumes about **10 working days** to submission. The order puts thin coverage of every brief capability ahead of depth. Each slice ends with something that can be shown and is saved.

### Day 0–1: audit and foundation

- [x] Finish the Day 0–1 audit: 14 proposed discrepancies, a frozen demo sequence, and documented dispositions for every original lead. Tax judgments remain explicit later-story tasks; see `docs/audit-findings.md`.
- [x] Repo setup: `.gitignore`, backend and frontend skeletons, local PostgreSQL via Docker Compose, `DATABASE_URL` configuration, Alembic migrations, and documented startup commands.
- [x] Import the packet unmodified; build claims, evidence edges and the document index. Automatic anchors resolve 2,672 / 3,012 values; manual source-selection UI and persisted anchors cover unresolved fields. Original data and manual anchors survive derived-data refresh.
- [x] Build the initial formula registry and check each formula against v3 (11 explicit formulas; see `docs/day-0-1-status.md`).
- [x] Role switcher, server-side permissions and masking from the start (verified through live local API checks).
- [x] Build and test locally; keep database and storage settings environment-configurable. Defer Heroku setup until the working prototype is ready. TypeScript/Vite build and local HTTP smoke checks passed; visual browser review remains pending.

### Day 2–3, Story A: "Trace and correct" (E1 sweep interest)

Preparer opens the queue → E1 is shown as contradicted → trace to D28 and D29 in the source drawer → mark D29 as a duplicate with a reason → propose −1,840 → see the estimated effect → reload, and it is still there. A reviewer approves it, and approving one's own work is blocked.
Covers: trace in both directions, simulated docs, verification, adjustment with original kept, durable saves, separation of duties.

**Implemented October 22, 2026:** persisted document dispositions, reason/evidence-backed correction proposals, verification methods tied to value/source revisions, independent approval/rejection, original and approved values side by side, queue status and an approved-only estimated summary. Migration `0002` applied. PostgreSQL acceptance tests and production frontend build passed. See [Story A walkthrough](docs/day-2-3-status.md). Visual browser review remains unverified because Computer Use permission was not granted.

### Day 3–4, Story B: "Partner threshold and reopening" (E4 gross receipts)

A books-to-tax view shows gross receipts 163,700 against books revenue of 151,300 that already includes the 1099-K deposits (D15) → adjustment of −12,400 → effect over $1,000, so partner sign-off is required → the partner approves → a later edit to D15's disposition makes the sign-off stale and explains why. Schedule C gross receipts and profit lines recompute from the registry. SE tax, QBI and total tax show as `affected`, and the summary shows one tax-effect estimate using the combined `schc_profit` rate (which already covers SE tax and QBI), with its limits stated.
Covers: books to tax, partner rule, sign-off invalidation, honest limits of estimates.

**Implemented October 22, 2026:** business-income view with source-backed book-profit bridge, explicit partner requirement, automatic reopening after cited disposition/anchor changes, preserved approval history, fresh verification and partner reapproval, and approved-only summary excluding reopened corrections. Schedule C propagation is exact within the registry; downstream tax remains labeled affected with one combined estimate. PostgreSQL acceptance tests and TypeScript/Vite build passed. See [plain-language Story B walkthrough](docs/day-3-4-status.md). Visual browser review remains unverified because Computer Use permission was not granted.

### Day 4–5, Story C: "Client evidence and judgment" (E3 vehicle, C6 crypto)

A question to the client from the vehicle claim → client role answers and attaches a file → the answer becomes evidence → the decision is recorded with authority. Crypto C6 runs the same flow with a judgment call and independent review. Bulk verification covers only the 8949 detail rows whose checks passed (matched to the broker statement, no basis or wash-sale exception). The selection is built from check results, never from "all 282". Rows that failed or have exceptions stay in the queue. Undo reverses the whole operation.
Covers: questions become evidence, judgments and authority, large detail, bulk actions with undo.

### Day 5–6, Story D: "What changed and what-if"

Compare v2 → v3 and our revisions. "Changed since I last looked" per user. The five supplied scenarios against v3. A user what-if on any claim. Variance against prior year using the firm threshold.
Covers: change tracking, version compare, what-ifs, prior-year swings.

### Day 6–7, Story E: "File, reject, amend, answer the notice"

Readiness is blocked by open items → resolve, including the "Final computation" partner decision → client approval tied to the revision → **submission freezes an immutable snapshot** → replay of the federal rejection (Theo's identity; California not transmitted) → the rejected snapshot is kept → the correction is a new revision, needs new approval if the change is material, and creates a new snapshot and submission linked to the rejected one → federal and California acceptance each reference their snapshot → client copy generated from the accepted snapshot. The 2028 Letter 566 → export an examination bundle (HTML index, simulated pages, claims, checks, decisions, sign-offs, manifest with checksums) that already contains the E3 and E4 support. Amendment branch on top of the frozen record. Carry forward to 2026 with planning estimates.
Covers: filing and after, freeze and amend, notice response, carry forward.

### Day 7–8: breadth pass

Make every remaining requirement work, even simply:
- [ ] Remaining required views: depreciation by asset, rentals and passive losses, K-1 lines, basis by year, retirement and foreign items, deductions and credits with limits, payments vs transcripts, state split, carryovers, prior preparer vs our changes.
- [ ] State-split check: D73 paystub allocation.
- [ ] Assignments, deadlines (from `firm.deadlines`), in-app notifications, two-session conflict demo.
- [ ] Firm standards editor (versioned; changes reopen only affected sign-offs), access log, time vs budget, search, retention as configuration showing eligibility and holds. Records are never actually deleted.
- [ ] Quality reviewer view of the frozen return.
- [ ] Every outside filing and every document disposed of; completeness indicator.

Use a requirement checklist (one row per brief bullet → screen → working yes/no) to track this.

### Day 9: harden and write

- [ ] Tests for import integrity, masking, self-review block (preparer vs reviewer activity), sign-off staleness, stale-write conflict, snapshot immutability per submission, readiness inheritance for derived claims, registry formulas reproducing v3, and the computation basis labels.
- [ ] Once the local prototype is ready, deploy to Heroku with Postgres and private object storage; verify the app link, role switching, and persistence across restart/redeployment.
- [ ] Backup and restore drill for the database and attachments.
- [ ] Keyboard, focus and labeled statuses; empty and error states; sales detail stays fast.
- [ ] One-page core idea and data model (section 2 plus the entity table).
- [ ] Error report (section 4, finished).
- [ ] Note on tools and AI use, including how the AI's findings were verified.

### Day 10: video and submit

- [ ] Script follows Stories A → E in about 10 minutes; technical decisions and tradeoffs from section 10.
- [ ] The user records the video personally and uploads it.
- [ ] Final check: app link, role switcher, durable saves, the one-pager, the error report, the video link.

If time runs short, cut depth, never breadth. Keep every capability working simply and drop polish, extra views and tests beyond the core set.

## 10. Tradeoffs to explain in the video

- **Claims and proof states, not forms:** the UI is organized around what is still unproven. Forms are generated views.
- **No recomputation engine:** exact arithmetic only for a small formula registry; everything else is labeled `affected` and the tax effect is one estimate in the summary. Each line is `engine`, `recomputed`, `affected` or `unresolved`. Filing on estimates requires an explicit partner decision.
- **Three-part status instead of one label:** separating evidence, checks and review lets a claim be contradicted and stale at once, and lets a client statement support a verified conclusion.
- **Relational store with an evidence edge table**, not a graph database. Append-only audit, not full event sourcing.
- **Local first, then Heroku:** PostgreSQL from day one, locally and on Heroku. Attachments use local storage during development and private object storage when hosted. Polling supports updates in both environments.
- **Simulated documents behind a renderer and locator interface:** real scans plug in with box anchors.
- **Simulated e-file and signatures:** recorded against an exact revision and clearly labeled as simulated.

## 11. Out of scope

Multi-client practice management; real authentication and tenant isolation; email/SMS; real e-file and e-signature; tax-engine recomputation; actually destroying records.


### Day 0–1 implementation status

Implementation started October 21, 2026. See [status and verification](docs/day-0-1-status.md), [audit findings](docs/audit-findings.md), and [local setup](README.md).

Day 0–1 implementation and automated checks are complete: 14 proposed discrepancies with all initial leads dispositioned, 2,672 automatic source anchors plus a persisted manual-anchor UI, 11 registered formulas, and 10 passing backend tests including PostgreSQL/API checks. TypeScript/Vite build passed. Manual anchor, revision, demo session, original hash and counts survived app/database restarts. Visual browser review is the remaining verification gate: Computer Use permission was not granted, so it is not claimed complete. No cloud deployment was performed.
