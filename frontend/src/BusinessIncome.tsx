import {useEffect,useState} from 'react';
import {api} from './api';
const money=(v:string)=>Number(v).toLocaleString('en-US',{style:'currency',currency:'USD',maximumFractionDigits:0});
type Business={engine_receipts:string;recommended_receipts:string;duplicate_payment:string;books:{income:string;expenses:string;profit:string};approved_profit:string;preview_profit:string;bridge:{label:string;value:string;source:string}[];sources:{ref:string;description:string}[];limit:string;workflow:{approved_value:string;review_value:string;adjustments:{status:string;reopen_events:{reason:string}[]}[]}};
export function BusinessIncome({refresh,onOpen}:{refresh:number;onOpen:(ref:string)=>void}){
  const [data,setData]=useState<Business|null>(null);const [error,setError]=useState('');
  useEffect(()=>{let active=true;api<Business>('/workpaper/business-income').then(v=>{if(active){setData(v);setError('');}}).catch(e=>{if(active)setError(e.message);});return()=>{active=false;};},[refresh]);
  if(error)return <p role="alert" className="error">{error}</p>;
  if(!data)return <p>Loading business income…</p>;
  const reopened=data.workflow.adjustments.find(a=>a.status==='reopened');
  return <section className="business-income panel">
    <div className="caption">E4 / BOOKS TO TAX</div><h2>One payment, counted twice.</h2>
    <p>The client’s books already include the Paywell payment. The engine added the payment report again. Correcting this means removing {money(data.duplicate_payment)} of duplicated revenue.</p>
    <div className="value-grid"><div><span>Revenue in the books</span><strong>{money(data.books.income)}</strong></div><div><span>Original engine revenue</span><strong>{money(data.engine_receipts)}</strong></div><div><span>Current approved revenue</span><strong>{money(data.workflow.approved_value)}</strong></div></div>
    <h3>Follow the money</h3><ol>{data.sources.map(s=><li key={s.ref}><button className="text-button" onClick={()=>onOpen(s.ref)}>{s.ref} ↗</button> — {s.description}</li>)}</ol>
    {reopened&&<div role="status" className="proposal-banner"><strong>Approval reopened — check the evidence again</strong>{reopened.reopen_events.map((e,i)=><p key={i}>{e.reason}</p>)}<p>The correction is excluded from the approved summary until it is verified and approved again.</p></div>}
    <h3>From book profit to current approved tax profit</h3><p>Revenue is money received. Profit is what remains after expenses. The tax rules use different expense amounts from the client’s books.</p>
    <table><thead><tr><th>Step</th><th>Amount</th><th>Evidence</th></tr></thead><tbody>{data.bridge.map(r=><tr key={r.source}><td>{r.label}</td><td>{money(r.value)}</td><td><button className="text-button" onClick={()=>onOpen(r.source)}>{r.source} ↗</button></td></tr>)}<tr><th>Current approved tax profit</th><th>{money(data.approved_profit)}</th><td>Schedule C, line 31</td></tr></tbody></table>
    <p>Profit using the value currently under review: <strong>{money(data.preview_profit)}</strong>. Pending or reopened corrections do not change the approved total.</p>
    <p className="muted">{data.limit}</p>
    <div className="proposal-banner"><strong>This correction needs Helen’s approval.</strong><p>The estimated federal tax change is over $1,000, so a partner must approve it. Priya proposes and checks the correction; Helen reviews it independently.</p></div>
    <button onClick={()=>onOpen('v3:SchC.1')}>Open revenue correction</button><p>Propose revenue of {money(data.recommended_receipts)}, cite D14, D15 and D21, explain the duplicate, then record what you checked. After Helen approves, edit D15’s disposition to see the approval reopen.</p>
  </section>;
}
