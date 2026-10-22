# Day 5–6: Story D — what changed, what-if and prior year

Implemented October 22, 2026. Local development only; no deployment or filing.

## The story in plain language

The engine produced three versions of the return as more documents arrived. **History** shows what actually changed between them, including changes to supporting evidence. It also separates those engine versions from the team’s approved corrections.

**What-if** lets you explore an amount without changing the return. The five supplied alternatives are separate examples against v3. Your own preview can start from v3 or the current approved workpaper. A supported preview can become a proposal, but it still needs evidence, verification and independent review.

**Prior year** asks why an amount changed from 2024 to 2025. A large change is a review prompt, not proof of an error. An explanation stays attached to the amounts and calculation basis it covered.

## Start locally

```sh
make db
make migrate
make dev
```

Migration **0004** adds saved per-user activity markers and has been applied locally. Restart an already-running backend to load the new routes. The navigation now includes **History**, **What-if** and **Prior year**.

## Try version comparison

1. Choose Priya and open **History**. The default comparison is **v2 → v3**.
2. The supplied data currently has **2 added lines and 91 changed lines**, counting amount, label, rule, input and evidence changes. These are calculated from the full snapshots, not copied from the packet’s change list.
3. Look at **F1040.24**, total federal tax: **77,470 → 81,962**, a change of **4,492**. The summary also shows payments and balance due; a larger tax does not necessarily mean a larger remaining balance.
4. Compare **v1 → v2**. The corrected brokerage statement changes the evidence for unchanged lots too. **F8949.D.M1** appears because its sources changed even though its gain did not. The old M14 classification is shown as removed and the replacement as added.
5. Select **v3 → Approved workpaper**. Pending and reopened proposals appear separately and do not change the compared approved amounts.
6. If you approve E1 using the earlier walkthrough, the corrected sweep-interest line becomes 0. Registered interest totals recompute; unsupported downstream lines retain their engine values with an **affected** label. The estimated summary includes the correction once.
7. Open a before/after value to inspect its version-scoped source. Historical v1/v2 claim panels are read only. The original fixture and imported engine values remain unchanged.

## Try “changed since you last looked”

1. Scroll to the activity section in **History**. It shows substantive saved work: proposals, verifications, reviews, evidence changes, questions/answers, decisions, bulk operations and variance explanations. Role switches and read-access logs are excluded.
2. Click **Mark displayed changes seen**. Viewing the page alone never acknowledges changes.
3. Record a new correction or verification, then return to History. The activity shows the author, time, subject and affected current claims, with links to inspect them. Activity refreshes every five seconds while this view is open.
4. Switch to Daniel. His marker is independent of Priya’s. Acknowledging Daniel’s changes does not move Priya’s marker.
5. A marker acknowledges only the displayed batch’s cursor. Work saved after that batch remains unseen. Reloads and new sessions retain each person’s marker in PostgreSQL.

The activity feed is a history of saved operations, not a reconstruction of intermediate return snapshots. Compare the supplied versions and the current approved workpaper above; earlier human proposals and reviews remain available in their claim histories.

## Try the five supplied alternatives

1. Open **What-if** and scroll to **Five supplied alternatives — each against v3**.
2. Each card shows the supplied federal and California base tax, alternative tax and tax change. Expand its changed lines for detail.
3. The alternatives are equipment section 179, equipment without bonus depreciation, HVAC as an improvement, standard deduction and annualized underpayment penalty.
4. The penalty alternative deliberately shows **zero tax change, zero penalty change and no changed lines**. Zero is retained as data, not treated as missing.
5. These are independent supplied snapshots. There is no combined scenario total or action that adds their changes to approved workpaper adjustments. Their stated base remains v3 even when the team has approved corrections.

## Try your own what-if

1. At the top of **What-if**, choose **SchB.1.2** (duplicate sweep interest), starting point **Original engine v3**, and new value **0**. The configured interest category is selected automatically.
2. Click **Calculate preview**. The estimated tax changes are **−640 federal / −127 California**. No correction or approval is saved.
3. Try a payment amount, such as **F1040.26**. Payment changes affect payments and balance due dollar for dollar, with no tax change. Credit previews change tax dollar for dollar. California-only line previews leave federal tax unchanged.
4. For a line without a configured mapping, choose a rate category explicitly. The result identifies this as an assumption. Text, dates and yes/no claims have no amount-times-rate calculation; the interface explains that limitation.
5. Configured mappings preserve expense signs, mileage units and known source-rate overrides. A business-expense reduction increases estimated profit; a change in mileage is converted into a deduction change before applying the rate.
6. Choosing **Current approved workpaper** uses only current approved values and the approved estimated summary. Affected starting values remain labeled provisional. The preview does not rerun thresholds, interactions or dependent return lines.
7. To save a supported leaf-claim preview, enter a reason and evidence references and click **Save proposal for review**. This uses the existing proposal endpoint and expected revision. It does not approve anything. Open the claim to verify it and obtain independent approval.
8. Derived totals and manually assumed mappings cannot bypass the configured correction workflow. E3 and C6 still require authority-backed judgments. A numeric C6 preview does not establish a new basis or acquisition date.

Every current claim can be opened in this view through **Explore a what-if** in its drawer. Rate estimates require numeric claims. The underlying claim’s category, computation and review rules determine whether a preview can be promoted directly.

## Try prior-year variance review

1. Open **Prior year**. The initial fixture currently has **78 comparable monetary lines**, with **49 flagged** by the firm rule. Counts change as approved work changes the current values.
2. A line is flagged only if its absolute change is **more than 10% and more than $1,000**. Exactly either threshold is not enough. For a zero prior amount, percentage is undefined; new activity above the dollar threshold is flagged explicitly.
3. Inspect taxable interest **F1040.2b**: **2,310 in 2024 → 6,450 in engine v3**. Open the prior value or its extraction source to inspect support.
4. Expand its explanation history and record why the amount changed. The note stores the author, time, compared values and calculation basis; it does not change the return or approve the claim.
5. Approve the E1 interest correction. The current interest total becomes **4,610**. The earlier explanation stays in history but is marked stale because it covered different values. Record a fresh explanation against the revised comparison if needed.
6. Use the filters for flagged, unexplained or all comparable lines, plus text search.
7. Expand the unpaired-lines list. Different payer row positions, missing lines, text fields and resident-versus-part-year California forms are not equated automatically. Mileage is a quantity, so the dollar threshold is not applied to it. Missing amounts are never treated as zero.

Affected lines still contain engine values until final computation; the variance view labels that basis and does not present a provisional amount as a recomputed result.

## Storage and boundaries

- `LastSeen` stores the packet, acting staff member, acknowledged event cursor, revision and time. Clients cannot access internal history, comparisons, scenarios or variance review.
- Variance explanations are append-only `Record` nodes with a fingerprint of the compared amounts, basis and firm threshold. New explanations preserve earlier history and save an audit event.
- Previews and supplied-scenario reads do not write claims, adjustments, approvals or seen markers. Cleared internal access is still logged under the existing policy.
- Comparisons read the imported versions and the approved-only projection. The original packet remains unchanged. Current classification changes such as C6 remain visible without silently recomputing unsupported totals.
- This story does not add a tax engine, combine supplied scenarios, or introduce an alternative approval path.

## Validation

- **24 domain/API/PostgreSQL tests passed**, including five new Story D checks: variance threshold/zero behavior; snapshot and evidence comparison with approved-only changes; per-user cursors that preserve newer unseen events; supplied/read-only user what-ifs and explicit proposal promotion; and variance explanations that become stale after their compared values change.
- Checks cover exact payment effects, expense signs, explicit category assumptions, California-only scope, approved-workpaper preview baselines, invalid inputs, client restrictions, original values retained and independent review after conversion.
- TypeScript checking and Vite production build passed. Alembic offline SQL generation passed, and migration 0004 was applied locally.
- Production HTTP smoke passed for the built frontend, database readiness, comparison, activity, all five supplied scenarios, read-only previews, prior-year review and client restrictions. No workpaper edits or seen markers were created in the live database by these checks.
- Mutating acceptance tests used isolated PostgreSQL schemas. Visual browser interaction remains unverified under the existing Computer Use permission blocker; no visual QA result is claimed.

The next story is simulated filing readiness, frozen submissions, rejection/correction and post-filing records.
