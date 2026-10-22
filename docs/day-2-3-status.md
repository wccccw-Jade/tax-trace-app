# Day 2–3: Story A — trace and correct

Implemented October 22, 2026. Local-only work; no deployment or filing occurred.

## Delivered

- Persisted document dispositions, including duplicate-of links, reason, actor/time and prior disposition history.
- Evidence-bound verification using the firm's five methods. Verification identifies the value checked, source references, subject revision, author, time and note.
- Correction proposals retain the original engine value, proposed value, reason, evidence and separately labeled tax-effect estimate.
- A proposal does not alter the approved return. Approval by an independent reviewer applies it; rejection leaves the approved value intact.
- Self-review checks cover preparers of the claim and its cited evidence. A reviewer who substantively prepares work cannot then approve it.
- Approval requires a current verification of the proposed value. Changed source revisions make old verification stale. Large tax effects require a partner.
- Pending, approved, rejected and stale review indicators appear in the queue; claim history shows verifications and reviewer conclusions.
- Approved-only summary counts the tax effect once. Registered arithmetic propagates the corrected interest; unsupported downstream lines remain explicitly `affected`.
- Original packet and imported engine values remain unchanged. Derived audit/locator refresh preserves the verification and correction records.
- Migration `0002` adds verification, adjustment and independent-review tables.

## Try E1 locally

```sh
make db
make migrate
make dev
```

1. Choose Priya. Open E1 and inspect D28/D29 source evidence.
2. In the evidence library, mark D29 as a duplicate of D28 and explain the matching sweep/account.
3. In E1, propose value 0 with a reason and D28/D29 evidence references.
4. Record verification of proposed value 0. The approved value is still 1,840 until review.
5. Priya's panel explains why she cannot review her own work.
6. Switch to Daniel, reopen E1, record a review conclusion and approve.
7. Refresh/reopen: original 1,840, approved 0, preparer verification and Daniel's approval remain visible. The estimated tax deltas are federal −640 and California −127.

## Validation

- 13 PostgreSQL/domain/API tests passed, including the full E1 sequence, persistence on fresh requests, retention through derived refresh, exact interest propagation, unchanged engine values, client denial, self-review by both a preparer and a reviewer, rejection, revision conflicts, stale-source verification blocking, invalid evidence and partner threshold.
- TypeScript check and Vite production build passed.
- Production HTTP smoke passed for the built frontend, database readiness, workflow metadata, approved-only summary and status routes. No corrections were created in the live demo by these checks.
- Tests create isolated PostgreSQL schemas, so the live demo starts without automatically approved corrections.
- Visual browser interaction was not verified; the existing Computer Use permission blocker remains. No browser result is claimed.

## Scope boundary

This delivers Story A, not full filing readiness. The next story adds the focused books-to-tax/partner workflow and reopening experience. Questions, bulk operations, whole-return review notes, filing, signatures and exports remain later phases. Rate estimates never become exact tax-engine results.
