# Day 0–1 audit findings

Generated from the immutable supplied packet using `python -m backend.cli audit`. These are proposed workpaper corrections, not approved changes. Tax effects are separate estimates; payment changes are exact. No tax-engine rerun is performed.

Packet SHA-256: `ee01f8508bd2fd9854754b82fd9c4a055bdc55e2778a132002a25381c412ad19`

| Finding | Claim | Engine | Proposed | Evidence |
| --- | --- | ---: | ---: | --- |
| E1: Duplicate Northlake sweep interest | `SchB.1.2` | 1840 | 0 | doc:D28#page1, doc:D29#page1 |
| E2: Prior-year exchange rate used for 2025 interest | `SchB.1.6` | 1747 | 1871 | ev-0960, ref:fx.SEK.2025_average |
| E3: Vehicle gift exceeds charity sale proceeds | `F8283.A1.vehicle` | 6000 | 2900.00 | doc:D66#page1, call-01 |
| E4: 1099-K receipts already included in books | `SchC.1` | 163700 | 151300.00 | doc:D14#page1, doc:D15#page3, D21 |
| E5: RSU adjusted basis omitted | `F8949.B.N1` | 19240.0 | 140.00 | doc:D11#page2, D28 |
| E6: RSU adjusted basis omitted | `F8949.B.N3` | 18480.0 | -620.00 | doc:D11#page2, D28 |
| E7: RSU adjusted basis omitted | `F8949.E.N4` | 15300.0 | 5880.00 | doc:D11#page2, D28 |
| E8: Duplicate mileage log page counted twice | `SchC.44a` | 11800 | 8100 | doc:D23#page2, doc:D23#page3 |
| E9: Payoff interest already included in Form 1098 | `SchA.8a` | 21847 | 19697.00 | D55, D56 |
| E10: Federal estimates do not agree to IRS transcript | `F1040.26` | 13000 | 12000 | agency:/irs_account_transcript_2025/0 |
| E11: 2024-designated payment counted toward 2025 California | `F540NR.72` | 14000 | 10500 | D68, agency:/ftb_account |

## Coverage and limits

- 74 documents, 3012 extractions, 1877 version-scoped lines and 11280 evidence edges.
- Unresolved source/input references: 0.
- Source locators resolved automatically: 1206 / 3012. Others require a manual anchor or a better field mapping; none are assumed verified.
- Eleven explicit arithmetic formulas reproduce v3. Earlier versions lack SchB.1.8, so that one formula is reported unavailable rather than inventing an input.
- Findings are based on the particular fixture fields and source relationships. The script is not a general OCR or tax-law checker.
- E3 flags the vehicle amount against the 1098-C proceeds. Its tax treatment still needs a recorded decision/authority in Story C.
- E8 removes the repeated May–August scan; its tax estimate uses the resulting deduction/profit change, not miles as dollars.
- E5/E6 use the California-source rate because those sales occur during California residency.
- Current UI path (written, runtime pending): choose staff identity → Review queue → finding → source reference → simulated page; further linked evidence is available in the drawer.
- No finding has a preparer verification or reviewer approval yet. Those workflows belong to subsequent stories.

## Open leads

- Meridian 250 proceeds discrepancy: locate exact lot
- California-source wage allocation from D73
- California AMT not computed
- Crypto C6 basis/date: assess msg-07 evidence
- Mixed business use and Spotify: evaluate call-01
- Historical S corporation basis reconciliation
- Due diligence and outside filings
- Theo identity correction belongs to later replay
