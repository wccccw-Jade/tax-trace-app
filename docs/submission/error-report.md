# Error report: source checks that challenge the engine

Packet SHA-256: `ee01f8508bd2fd9854754b82fd9c4a055bdc55e2778a132002a25381c412ad19`. All data is invented. These are source-backed proposed discrepancies, not pre-approved corrections or a claim that the live return is ready to file.

The design makes each discrepancy actionable: a finding opens its return claim and original/approved values, links to the simulated source page or agency record, and preserves the correction's explanation, evidence, verification and independent approval. E12 opens the unextracted source page because no return line exists to open.

| ID | Engine → proposed | Independent check and sources | Tax effect estimate: federal / CA | UI path |
| --- | --- | --- | --- | --- |
| E1 | `SchB.1.2`: 1840 → 0 | Duplicate Northlake sweep interest. `doc:D28#page1`, `doc:D29#page1` | -640 / -127 (estimated) | Review workspace → E1 → Review / Evidence |
| E2 | `SchB.1.6`: 1747 → 1871 | Prior-year exchange rate used for 2025 interest. `ev-0960`, `ref:fx.SEK.2025_average` | 43 / 9 (estimated) | Review workspace → E2 → Review / Evidence |
| E3 | `F8283.A1.vehicle`: 6000 → 2900.00 | Vehicle gift exceeds charity sale proceeds. `doc:D66#page1`, `call-01` | 806 / 149 (estimated) | Review workspace → E3 → Review / Evidence; Questions & decisions |
| E4 | `SchC.1`: 163700 → 151300.00 | 1099-K receipts already included in books. `doc:D14#page1`, `doc:D15#page3`, `D21` | -4402 / -384 (estimated) | Review workspace → E4 → Review / Evidence; Business income |
| E5 | `F8949.B.N1`: 19240.0 → 140.00 | RSU adjusted basis omitted. `doc:D11#page2`, `D28` | -6647 / -1222 (estimated) | Review workspace → E5 → Review / Evidence |
| E6 | `F8949.B.N3`: 18480.0 → -620.00 | RSU adjusted basis omitted. `doc:D11#page2`, `D28` | -6647 / -1222 (estimated) | Review workspace → E6 → Review / Evidence |
| E7 | `F8949.E.N4`: 15300.0 → 5880.00 | RSU adjusted basis omitted. `doc:D11#page2`, `D28` | -2242 / -320 (estimated) | Review workspace → E7 → Review / Evidence |
| E8 | `SchC.44a`: 11800 miles → 8100 miles | Duplicate mileage log page counted twice. `doc:D23#page2`, `doc:D23#page3` | 919 / 80 (estimated) | Review workspace → E8 → Review / Evidence |
| E9 | `SchA.8a`: 21847 → 19697.00 | Payoff interest already included in Form 1098. `D55`, `D56` | 559 / 103 (estimated) | Review workspace → E9 → Review / Evidence |
| E10 | `F1040.26`: 13000 → 12000 | Federal estimates do not agree to IRS transcript. `agency:/irs_account_transcript_2025/0` | Balance 1000 / 0 (exact) | Review workspace → E10 → Review / Evidence |
| E11 | `F540NR.72`: 14000 → 10500 | 2024-designated payment counted toward 2025 California. `D68`, `agency:/ftb_account` | Balance 0 / 3500 (exact) | Review workspace → E11 → Review / Evidence |
| E12 | `F8949.C.M18`: Missing → -60.00 | Supplemental brokerage lot M18 was never extracted. `doc:D31#page32`, `doc:D31#page1` | -21 / 0 (estimated) | Review workspace → E12 → D31 page 32; explicit missing-lot disposition |
| E13 | `SchC.25`: 3480 → 2172.00 | Family phone and internet deducted at full cost. `call-01`, `doc:D15#page2` | 464 / 41 (estimated) | Review workspace → E13 → Review / Evidence |
| E14 | `SchC.27a.1`: 6850 → 6634.00 | Personal Spotify subscription in business software. `call-01`, `doc:D15#page1` | 77 / 7 (estimated) | Review workspace → E14 → Review / Evidence |

## Interpretation and review status

E1 compares the same sweep account across D28/D29, not merely equal numbers. E2 uses the packet's 2025 exchange rate. E3 compares a vehicle deduction to the charity's sale proceeds and still requires a supported tax judgment. E4 reconciles payment-platform receipts already in the business books. E5–E7 use the stock-compensation supplement's adjusted purchase costs rather than treating all proceeds as gain. E8 removes a duplicate mileage page and estimates the resulting deduction/profit change, not miles as dollars. E9 compares payoff interest to the annual lender statement. E10/E11 reconcile the payment amount and designated year against agency records. E12 identifies a real unextracted loss of 60, rather than fabricating an extraction or a zero-valued line. E13/E14 depend on evaluating the client's business-use/personal-use statement.

The supplied effect rates do not model thresholds or interactions; these estimates should not be presented as a full tax recomputation or blindly added to supplied what-if alternatives. Payments change balance dollar for dollar, rather than estimated tax. Original engine values are retained. No live reviewer approvals are asserted in this report; the app records the actual acting identities and review history when review is performed.

## Uncertainty is kept separate from proved discrepancies

- Crypto C6: client-stated basis/date require support and judgment; a zero basis alone does not establish the final correction.
- California wages: D73 reports 22,469 near the move versus annual Halvorsen CA wages of 111,300. A 129,569 combined candidate requires work-date and HSA reconciliation, authority and independent review; it is not an automatic correction.
- California AMT: an uncomputed calculation remains unresolved until an explicit supported conclusion, not an invented zero.
- The duplicate Halvorsen W-2 is a valid duplicate, not a second wage error. S-corporation basis reconciles to 2,300 when D40 is included. The unchanged Form 2210 penalty and ambiguous handwritten receipt are not treated as proved errors solely because they look suspicious.
- Outside filings and missing related returns require responsibility, communication and scope conclusions, not invented filings.

Reproduce the findings with `make audit`. The detailed initial investigation dispositions remain in [audit-findings.md](../audit-findings.md). The claim, evidence, judgment and filing paths are demonstrated in the story walkthroughs and [Day 7–8 status](../day-7-8-status.md).
