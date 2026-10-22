# Day 0–1 audit report

The initial demo error list is fixed at 14 source-backed discrepancies. These are proposed corrections, not verified or approved workpaper changes. Judgment-dependent proposals still need the preparer/reviewer workflow in later stories.

Packet SHA-256: `ee01f8508bd2fd9854754b82fd9c4a055bdc55e2778a132002a25381c412ad19`

| ID | Finding | Claim | Engine | Proposed | Evidence |
| --- | --- | --- | ---: | ---: | --- |
| E1 | Duplicate Northlake sweep interest | `SchB.1.2` | 1840 | 0 | doc:D28#page1, doc:D29#page1 |
| E2 | Prior-year exchange rate used for 2025 interest | `SchB.1.6` | 1747 | 1871 | ev-0960, ref:fx.SEK.2025_average |
| E3 | Vehicle gift exceeds charity sale proceeds | `F8283.A1.vehicle` | 6000 | 2900.00 | doc:D66#page1, call-01 |
| E4 | 1099-K receipts already included in books | `SchC.1` | 163700 | 151300.00 | doc:D14#page1, doc:D15#page3, D21 |
| E5 | RSU adjusted basis omitted | `F8949.B.N1` | 19240.0 | 140.00 | doc:D11#page2, D28 |
| E6 | RSU adjusted basis omitted | `F8949.B.N3` | 18480.0 | -620.00 | doc:D11#page2, D28 |
| E7 | RSU adjusted basis omitted | `F8949.E.N4` | 15300.0 | 5880.00 | doc:D11#page2, D28 |
| E8 | Duplicate mileage log page counted twice | `SchC.44a` | 11800 | 8100 | doc:D23#page2, doc:D23#page3 |
| E9 | Payoff interest already included in Form 1098 | `SchA.8a` | 21847 | 19697.00 | D55, D56 |
| E10 | Federal estimates do not agree to IRS transcript | `F1040.26` | 13000 | 12000 | agency:/irs_account_transcript_2025/0 |
| E11 | 2024-designated payment counted toward 2025 California | `F540NR.72` | 14000 | 10500 | D68, agency:/ftb_account |
| E12 | Supplemental brokerage lot M18 was never extracted | `F8949.C.M18` | Missing | -60.00 | doc:D31#page32, doc:D31#page1 |
| E13 | Family phone and internet deducted at full cost | `SchC.25` | 3480 | 2172.00 | call-01, doc:D15#page2 |
| E14 | Personal Spotify subscription in business software | `SchC.27a.1` | 6850 | 6634.00 | call-01, doc:D15#page1 |

## Demo sequence

- E1: trace duplicate sweep interest to both source documents.
- E4: reconcile books to deposits and require partner review for the material correction.
- E3: document the vehicle-donation conclusion and supporting authority.
- E12: demonstrate a supplemental page the pipeline never read, and create a supported new lot in the later adjustment workflow.
- Crypto C6: demonstrate a judgment requiring assessment of client-supplied evidence, without pre-approving an uncertain basis.

## Investigation dispositions

Every initial lead has been investigated and given a disposition. `needs_decision` is an explicit future workpaper task, not an unfinished search or an assumed resolution. Nothing here clears filing readiness.

| Lead | Disposition | Conclusion | Evidence |
| --- | --- | --- | --- |
| Meridian summary/detail mismatch | confirmed_discrepancy | Page 32 contains M18, proceeds 250 and basis 310: a missing short-term loss of 60. Add an evidence-backed manual lot in Story A; no extracted value exists for it. | doc:D31#page1, doc:D31#page32 |
| Corrected brokerage statement | reconciled | v3 Meridian lot sources use D31. The replacement is used; the supplemental unextracted lot remains a separate discrepancy. | D30, D31 |
| Duplicate W-2 upload | reconciled | D09 and D10 represent one W-2. The distinct employer wage sum is 212400, agreeing with the current return; the phone image was not counted twice. | D09, D10, msg-02, v3:F1040.1a |
| Crypto C6 basis and acquisition date | needs_decision | Client states purchase in March 2021 for about 3,050 and cites a bank statement. This is evidence to assess, not confirmed cost basis. Record a decision on the support and holding period in Story C. | msg-07, D34, D35 |
| Handwritten donation receipt | needs_decision | Printed first digit is ambiguous; extraction is 1,500 and later client confirmation is also 1,500. No amount discrepancy proved. Record substantiation and confirmation; confidence alone is not an error. | D64, msg-08, ev-1049 |
| S-corporation historical basis | reconciled | 21,300 + 14,100 - 20,000 + 16,900 - 30,000 = 2,300 opening 2025 basis, agreeing with v3. Preserve the source worksheet assumption; prior-year history is not silently rewritten. | D40, py:/basis_records/scorp_lindqvist_family_woodworks/0, py:/return_2024/K1_1120S, v3:F7203.1 |
| California-source wages | needs_decision | D73 supports 22,469 Halvorsen CA taxable wages near the move, versus annual W-2 CA wages of 111,300. Do not allocate all annual wages or use a blanket day fraction. Preparer must reconcile work dates and HSA treatment before finalizing the split. | D08, D09, D73, v3:SchCA540NR.1.E |
| California AMT | needs_decision | The engine explicitly did not compute California AMT. Keep a blocking unresolved calculation requiring a conclusion; do not manufacture a zero. | D12, v3:F6251.2i |
| Questionnaire says no investment sales | needs_decision | Broker documents prove sales despite the organizer answer. Preserve the original answer and obtain/document a reconciled response; this is a completeness conflict, not a second tax adjustment. | qa-14, D28, D31, D34, D74 |
| Underpayment penalty | reconciled | Prior-year safe harbor rounds to 41,313, agreeing with F2210.8. The supplied annualized scenario changes the penalty by zero. Unchanged 164 is not itself a defect; reassess payment timing after the confirmed IRS payment correction. | py:/return_2024/lines/F1040.24, v3:F2210.8, v3:F2210.AI |
| Mixed business use and Spotify | confirmed_discrepancy | Client statement supports phone 70%, internet 50%, Spotify personal. Proposed utilities 2,172 instead of 3,480 and software 6,634 instead of 6,850. These proposals still require verification of the statement. | call-01, D15, v3:SchC.25, v3:SchC.27a.1 |
| Home-office variance | reconciled | Current measurements are 220 Sacramento and 260 Austin; the engine uses simplified average 240. This explains a change from prior-year 300. A prior-year correction is not inferred. | D24, v3:SchC.30, D07 |
| Outside filings and prior open matters | needs_decision | FBAR and contractor 1099s are outside engagement and require responsibility/communication. Prior preparer left a 2023 Form 3520 question unresolved. Oregon and Arizona composite statements need disposition; Ada files separately. Do not imply any outside filing was completed. | D01, D07, D27, D38, D39 |
| Dependent identity rejection | replay_only | Later correction evidence supports the scripted July rejection/resubmission. Preserve submitted and corrected identities separately when replay is built; no current mutation is applied. | D71, msg-10, agency:/efile/0 |
| Unextracted documents | needs_decision | D07 and agency records can be cited manually despite no extraction. D70 records a resolved prior CP2000; D72 is future notice material. Extraction status does not establish verification or document completeness. | D07, D69, D70, D72 |

## How the interface surfaces the findings

Select Priya → Review queue → finding → evidence link. A document opens its simulated pages and extracted-field list. Select a field to see the exact highlighted source. On a prepared extraction, select source text and choose **Save source anchor**; the new anchor, actor, time and revision survive reloads. This locates evidence and does not verify the number.

## Audit coverage and limitations

- 74 documents; 3012 values; 1877 version-scoped lines; 11280 edges.
- All source/input references resolve. Automatic anchors resolve 2672 / 3012 values. Remaining values need manual anchors or further mappings; they are never auto-approved.
- 11 explicit formulas reproduce v3. SchB.1.8 is absent in v1/v2, so the eight-payer formula is unavailable there rather than inventing an input.
- E12 is an unextracted M18 lot: page 32 proceeds 250, basis 310, loss 60. No engine line or extraction is fabricated. Its California effect is zero because the sale is after the move and no California source is identified.
- E13 utilities use the client-stated 70%/50% split; E14 uses the client statement that Spotify is personal. Proposed adjustments require that evidence to be verified.
- Mileage effects use the deduction/profit delta, not miles as dollars. Expense reductions increase business profit. Payments affect balance dollar for dollar.
- Tax effects are rate-based estimates, never a rerun of the tax engine. Same-adjustment effects must not be counted again through downstream lines.
- California AMT, crypto basis/date, wage sourcing and outside filings remain explicit decisions for later workpaper workflows.
- The checks are tailored to the invented fixture. There is no claim of exhaustive independent tax-law validation or a generic OCR audit.
- Browser visual review is blocked by Computer Use permission. Build, database and HTTP tests are documented separately in the implementation status.

Reproduce: `.venv/bin/python -m scripts.audit.report`.
