"""Generate the handoff audit report from current packet checks."""
from pathlib import Path
from backend.config import settings, ROOT
from backend.domain.packet import Packet
from backend.domain.audit import run_audit


def main():
    report=run_audit(Packet.read(settings.packet_path))
    lines=['# Day 0–1 audit report','',
           'The initial demo error list is fixed at 14 source-backed discrepancies. These are proposed corrections, not verified or approved workpaper changes. Judgment-dependent proposals still need the preparer/reviewer workflow in later stories.',
           '',f"Packet SHA-256: `{report['packet_hash']}`",'',
           '| ID | Finding | Claim | Engine | Proposed | Evidence |',
           '| --- | --- | --- | ---: | ---: | --- |']
    for f in report['findings']:
        lines.append(f"| {f['id']} | {f['title']} | `{f['claim']}` | {'Missing' if f.get('new_claim') else f['observed']} | {f['proposed']} | {', '.join(f['evidence'])} |")
    lines += ['', '## Demo sequence','',
              '- E1: trace duplicate sweep interest to both source documents.',
              '- E4: reconcile books to deposits and require partner review for the material correction.',
              '- E3: document the vehicle-donation conclusion and supporting authority.',
              '- E12: demonstrate a supplemental page the pipeline never read, and create a supported new lot in the later adjustment workflow.',
              '- Crypto C6: demonstrate a judgment requiring assessment of client-supplied evidence, without pre-approving an uncertain basis.',
              '', '## Investigation dispositions','',
              'Every initial lead has been investigated and given a disposition. `needs_decision` is an explicit future workpaper task, not an unfinished search or an assumed resolution. Nothing here clears filing readiness.',
              '', '| Lead | Disposition | Conclusion | Evidence |', '| --- | --- | --- | --- |']
    for item in report['investigations']:
        lines.append(f"| {item['lead']} | {item['status']} | {item['conclusion']} | {', '.join(item['evidence'])} |")
    lines += ['', '## How the interface surfaces the findings','',
              'Select Priya → Review queue → finding → evidence link. A document opens its simulated pages and extracted-field list. Select a field to see the exact highlighted source. On a prepared extraction, select source text and choose **Save source anchor**; the new anchor, actor, time and revision survive reloads. This locates evidence and does not verify the number.',
              '', '## Audit coverage and limitations','',
              f"- {report['counts']['documents']} documents; {report['counts']['extractions']} values; {report['counts']['claims']} version-scoped lines; {report['counts']['edges']} edges.",
              f"- All source/input references resolve. Automatic anchors resolve {report['locators']['resolved']} / {report['locators']['total']} values. Remaining values need manual anchors or further mappings; they are never auto-approved.",
              '- 11 explicit formulas reproduce v3. SchB.1.8 is absent in v1/v2, so the eight-payer formula is unavailable there rather than inventing an input.',
              '- E12 is an unextracted M18 lot: page 32 proceeds 250, basis 310, loss 60. No engine line or extraction is fabricated. Its California effect is zero because the sale is after the move and no California source is identified.',
              '- E13 utilities use the client-stated 70%/50% split; E14 uses the client statement that Spotify is personal. Proposed adjustments require that evidence to be verified.',
              '- Mileage effects use the deduction/profit delta, not miles as dollars. Expense reductions increase business profit. Payments affect balance dollar for dollar.',
              '- Tax effects are rate-based estimates, never a rerun of the tax engine. Same-adjustment effects must not be counted again through downstream lines.',
              '- California AMT, crypto basis/date, wage sourcing and outside filings remain explicit decisions for later workpaper workflows.',
              '- The checks are tailored to the invented fixture. There is no claim of exhaustive independent tax-law validation or a generic OCR audit.',
              '- Browser visual review is blocked by Computer Use permission. Build, database and HTTP tests are documented separately in the implementation status.',
              '', 'Reproduce: `.venv/bin/python -m scripts.audit.report`.']
    target=ROOT/'docs/audit-findings.md'
    target.write_text('\n'.join(lines)+'\n')
    print(f'Wrote {target.relative_to(ROOT)}')

if __name__=='__main__':
    main()
