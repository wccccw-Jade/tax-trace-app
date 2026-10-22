"""Fixture-backed books-to-tax bridge; no inferred tax formulas."""
from backend.domain.formulas import D
from backend.domain.workpaper import get_record, workflow, projected_summary


def business_income(db, packet):
    work=workflow(db,packet,get_record(db,packet,'v3:SchC.1'))
    summary=projected_summary(db,packet)
    lines={l['key']:D(l['value']) for l in packet.data['return_versions'][-1]['lines'] if l['key'].startswith('SchC.') and isinstance(l['value'],(int,float))}
    lines.update({l['key']:D(l['value']) for l in summary['changed_lines'] if l['basis']=='recomputed' and l['key'].startswith('SchC.')})
    books={k:D(packet.resolve(ref)['value']) for k,ref in {'income':'ev-0103','expenses':'ev-0104','profit':'ev-0105'}.items()}
    approved_receipts=lines['SchC.1']
    preview_profit=lines['SchC.31']+D(work['review_value'])-approved_receipts
    return {'claim':'v3:SchC.1','workflow':work,'books':{k:str(v) for k,v in books.items()},
        'engine_receipts':str(packet.resolve('v3:SchC.1')['value']),
        'recommended_receipts':str(books['income']),
        'duplicate_payment':str(D(packet.resolve('v3:SchC.1')['value'])-books['income']),
        'approved_profit':str(lines['SchC.31']),'preview_profit':str(preview_profit),
        'bridge':[
            {'label':'Profit in the client’s books','value':str(books['profit']),'source':'ev-0105'},
            {'label':'Receipts above the books (the duplicated payment)','value':str(approved_receipts-books['income']),'source':'v3:SchC.1'},
            {'label':'Book expenses less current tax expenses','value':str(books['expenses']-lines['SchC.28']),'source':'v3:SchC.28'},
            {'label':'Home-office deduction','value':str(-lines['SchC.30']),'source':'v3:SchC.30'},
        ],
        'sources':[{'ref':'D14','description':'Client books: $151,300 of revenue, including the payment.'},
                   {'ref':'doc:D15#page3','description':'Deposit detail: $41,200 from Atlas = $12,400 via Paywell + $28,800 by bank transfer; already included in the books.'},
                   {'ref':'D21','description':'Paywell’s 1099-K reports that same $12,400. It is evidence of the payment, not extra revenue.'}],
        'limit':'This bridge uses current approved expenses. It does not approve the other expense findings. Schedule C arithmetic is exact; SE tax, QBI and total tax remain affected. The tax summary uses one combined schc_profit estimate that already includes SE tax and QBI; it does not add them again.'}
