# Day 3–4: Story B — business income and partner approval

Implemented October 22, 2026. Built and tested locally; no deployment or filing.

## The story in plain language

A client received $12,400 through a payment processor. Their bookkeeping already includes that money. The processor also sent a payment report, and the engine mistakenly counted that same money again. The business earned $151,300, but the engine reports $163,700.

Priya proposes removing the duplicate. Because the estimated tax change exceeds $1,000, Helen, the partner, must approve it. Later, someone changes how a supporting document is treated. Helen’s earlier approval no longer covers that evidence. The app keeps the old approval, explains the change, and requires another check and approval.

Revenue means money received. Profit means revenue minus expenses. Correcting this revenue changes profit from $81,854 to $69,454 while holding the current approved deductions constant. Other expense findings still need their own review.

## Try it

```sh
make db
make migrate
make dev
```

1. Choose **Priya Raman** and open **Business income**. Read “One payment, counted twice” and follow the D14, D15 page 3 and D21 links.
2. Click **Open revenue correction**. Enter corrected value **151300**. Explain: “The books already include the Paywell payment; D21 reports the same payment again.” Cite **D14**, **D15**, **D21**, one per line, and save.
3. Record verification with **agreed to source document**. Explain that you compared the books, deposit detail and payment report. The correction stays pending until approved.
4. Switch to **Daniel Ortiz** and reopen the correction. The panel explains why Daniel can reject it but cannot approve it: a partner is required.
5. Switch to **Helen Strand**, open the correction and record a review conclusion, then approve. Current approved revenue becomes **$151,300** and profit **$69,454**. E4’s estimated tax changes are federal **−$4,402**, California **−$384**.
6. Switch back to **Priya**. Open D15 from the evidence library, set its disposition to **supporting**, and enter a reason such as “Rechecked how the deposit reconciliation supports the books.” Save.
7. The save message identifies the reopened claim. The queue shows **Approval reopened**. The business view and claim panel identify D15 and its new revision. The earlier verification and approval remain in history and are marked stale. E4’s effect is excluded from the approved summary.
8. Open the revenue correction, record a fresh verification as Priya, then switch to Helen and approve again. The summary includes E4 once. Earlier approval history remains visible. Reloading preserves the result.

If E4 is the only approved correction, its approval produces estimated total tax of **$77,560 federal / $18,490 California**. If other corrections are approved, their effects remain in the summary too. Changing D15 does not reopen the independent E1 interest correction.

## Delivered

- A dedicated business-income view with source links and a book-profit-to-tax-profit bridge using fixture values and current approved Schedule C lines.
- Exact registered arithmetic for gross receipts and profit; unsupported SE tax, QBI and total-tax lines remain `affected`.
- One combined `schc_profit` tax-effect estimate; SE tax and QBI are already included in that rate and are not added again.
- Explicit partner requirement in the claim panel; enforced on the server along with independent review and current verification.
- Document disposition and manual source-anchor changes reopen affected approvals in the same database transaction. Reopening records the changed source, revision, reason, actor and time without erasing earlier reviews.
- Reopened corrections are excluded from the approved summary until verified and independently approved again. Unrelated approvals remain current.
- Queue, claim panel and summary explain reopening. Previously stale approvals can also be explicitly reopened from the claim panel.
- Existing PostgreSQL tables support this workflow; no new migration is required beyond `0002`.

## Validation

- 15 domain/API/PostgreSQL tests passed, including two new Story B acceptance tests: full partner approval → D15 change → reopening → fresh verification → partner reapproval, and reopening after a manual anchor change.
- Checks cover the book-profit bridge, exact Schedule C propagation, affected downstream lines, threshold/self-review restrictions, preserved history, unrelated E1 approval, persistence on subsequent requests, and no duplicate tax effect after reapproval.
- TypeScript check and Vite production build passed.
- Built frontend and new API route passed local production HTTP smoke checks. Tests use isolated schemas; no corrections were created in the live demo database.
- Visual browser interaction remains unverified because Computer Use permission was not granted. No visual QA result is claimed.

Questions, client attachments, bulk verification and judgment decisions are the next story. Full tax computation and filing readiness remain later work.
