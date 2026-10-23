# Brief requirement checklist

Checked against the three-page case-study PDF on October 23, 2026. “Yes” means a working local prototype path; it does not mean the real return has been reviewed, filed or deployed. Tax estimates and agency events retain their explicit simulation limits. Browser visual verification is still pending.

| Brief bullet | Screen / working path | Working? | Boundary |
| --- | --- | --- | --- |
| Evidence: exact source, document usage/disposition, verification, cross-year/related links, attached evidence | Claim details → Evidence; Evidence library → Document review; Questions & decisions; Tax views → Basis/prior/related responsibilities | Yes | Unresolved anchors require manual selection; missing related returns remain missing. |
| Calculation: construction, reconciliation, large detail, books to taxable income, state split, independent checks | Review findings, Business income, Investment sales, Tax views → Tax computation/California split | Yes | Exact arithmetic only in the registered formulas; other values retain their supplied basis and tax changes are estimated. D73 allocation needs a supported human judgment. |
| Simulated source display, specific field/location, replaceable source-view boundary | Source component, resolved field highlights and manual text anchors | Yes | Simulated prose from printed_content. Real scan rendering remains a future implementation. |
| Change: original-preserving adjustments, live changes/changed-since-seen, version compare, what-ifs, bulk/undo | Review value, History, Updates, Explore a scenario, Investment sales | Yes | Questions/updates poll; other editors refresh explicitly to preserve drafts. Supplied scenarios remain independent v3 comparisons. |
| Judgment: prior-year swings, decisions/elections/due diligence/penalties, completeness | Compare last year; Questions & decisions; Filing checklist → preparer steps/dispositions; Completeness | Yes | Generic authority-backed judgments and explicit checklist evidence, not a tax-law engine. No area acknowledgment silently verifies claims. |
| People: client/colleague evidence, blocking notes, reopening sign-offs, enforced roles, simultaneous users, assignments/deadlines/notifications, client authorization | Questions; Claim details; Filing checklist; Team & deadlines; Updates | Yes | Demo identities, not production authentication. Conflicting edits return the latest revision/author/note. |
| Filing and after: extension, submission/rejection/copy, freeze/amend, notice record, carryforward/planning | Filing checklist; accepted-copy and examination exports; amendment branches; post-filing replay | Yes | Simulated signatures/agencies and supplied extension data. No real filing/payment or official Form 1040-X. |
| Firm: standards, sensitive-data protection/view logs, time/budget, status/search | Firm standards; Team & deadlines; Completeness; Search | Yes | Administrator settings are versioned. Clearance is enforced server-side. Retention only shows eligibility/holds; no record destruction. |
| Records a CPA expects | Existing review/summary/history/prior-year/documents/business/sales plus Tax views listed below | Yes | Generated from supplied engine output and current approved workpaper corrections. |

## CPA view coverage

| Required record | Screen |
| --- | --- |
| Return summary vs last year | Compare last year; approved review summary |
| Tax computation and area summaries | Tax views → Tax computation and the area selector |
| Document index | Evidence library; Completeness |
| Depreciation by asset, method/life/bonus, federal/CA/AMT, disposal/recapture | Tax views → Depreciation by asset; nine asset sections and related Form 4797 lines |
| Sales detail | Investment sales; checked selection and exceptions |
| Books to tax | Business income |
| Rentals and passive losses | Tax views → Rentals & passive losses |
| K-1 lines | Tax views → K-1 income; linked source statements |
| Retirement and foreign items | Tax views → Retirement & foreign items |
| Deductions and credits with limits | Tax views → Deductions & credits |
| Payments | Tax views → Payments & agency records |
| State split | Tax views → California split, D73 check and reviewed allocation decision |
| Carryovers | Tax views → Carryovers; saved 2026 post-filing records when available |
| Basis by year | Tax views → Basis by year; prior records and explicit S-corporation reconciliation |
| Prior preparer vs our changes | Tax views → Prior preparer vs our work; Compare last year; History |
| Quality reviewer of frozen return | Quality review; separate findings, no frozen-content mutation |

## Submission deliverables

| Deliverable | Status |
| --- | --- |
| Working app, original packet, shared persistence and role switcher | Local app works. Public Heroku link/private object storage remain Day 9. |
| One-page core idea/data model | Plan contains the model; final one-page artifact remains Day 9. |
| Errors and how the design surfaced them | Audit findings and story walkthroughs exist; final submission report remains Day 9. |
| Personal video and video link | Day 10; user records it. |
| Tools/AI-use disclosure | Final note remains Day 9. |
