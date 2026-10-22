import {useEffect,useState} from 'react';
import {api} from './api';
import type {Actor,Trace} from './types';

type Effect={basis:string;kind:string;tax_change:Record<string,string>;balance_change:Record<string,string>;note?:string};
type Change={requires_partner:boolean;approval_current:boolean;reopen_events:{reason:string}[];id:number;actor_id:string;original_value:string;proposed_value:string;category:string;reason:string;evidence:string[];effect:Effect;status:string;at:string;reviews:{actor_id:string;decision:string;note:string;current:boolean;at:string}[]};
type Workflow={ref:string;revision:number;engine_value:string;approved_value:string;review_value:string;category:string|null;verification_methods:string[];preparers:string[];adjustments:Change[];verifications:{id:number;actor_id:string;method:string;note:string;evidence:string[];value:string;at:string;current:boolean}[]};
const refs=(text:string)=>text.split(/[\n,]+/).map(x=>x.trim()).filter(Boolean);
const money=(value:string)=>Number(value).toLocaleString('en-US',{style:'currency',currency:'USD',maximumFractionDigits:2});

export function ClaimWorkpaper({trace,actor,suggestion,onSaved,onOpen}:{trace:Trace;actor:Actor;suggestion?:{proposed:string;evidence:string[]};onSaved:()=>void;onOpen:(ref:string)=>void}) {
  const [work,setWork]=useState<Workflow|null>(null);
  const [error,setError]=useState('');
  const [message,setMessage]=useState('');
  const [busy,setBusy]=useState(false);
  const [value,setValue]=useState(suggestion?.proposed??String(trace.value.value));
  const [reason,setReason]=useState('');
  const defaults=suggestion?.evidence??(trace.value.sources as string[]??[]);
  const [evidence,setEvidence]=useState(defaults.join('\n'));
  const [method,setMethod]=useState('agreed_to_source_document');
  const [verificationNote,setVerificationNote]=useState('');
  const [reviewNote,setReviewNote]=useState('');
  useEffect(()=>{
    let active=true;
    api<Workflow>('/workpaper/claim?ref='+encodeURIComponent(trace.ref)).then(v=>{if(active)setWork(v);}).catch(e=>{if(active)setError(e.message);});
    return ()=>{active=false;};
  },[trace.ref,trace.revision]);
  async function send(path:string,body:object,success:string){
    setBusy(true);setError('');setMessage('');
    try{
      const next=await api<Workflow>(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
      setWork(next);setMessage(success);onSaved();
    }catch(e){setError((e as Error).message);}finally{setBusy(false);}
  }
  if(!work)return <section className="workpaper-panel">{error?<p role="alert" className="error">{error}</p>:<p>Loading review record…</p>}</section>;
  const pending=work.adjustments.find(c=>['proposed','reopened'].includes(c.status));
  const stale=work.adjustments.find(c=>c.status==='approved'&&!c.approval_current);
  const canPrepare=['preparer','reviewer','partner'].includes(actor.role);
  const own=work.preparers.includes(actor.id);
  const currentVerification=work.verifications.some(v=>v.current);
  const canReview=!!pending&&['reviewer','partner'].includes(actor.role)&&!own;
  return <section className="workpaper-panel" aria-label="Claim review workflow">
    <h3>Review this claim</h3>
    {stale&&<div className="proposal-banner"><p>Evidence changed after approval. The summary excludes this correction.</p>{canPrepare&&<button disabled={busy} onClick={()=>void send(`/workpaper/adjustments/${stale.id}/reopen`,{expected_revision:work.revision},'Approval reopened. Check the current evidence before requesting approval again.')}>Reopen for review</button>}</div>}
    {pending?.status==='reopened'&&<div className="proposal-banner"><strong>Approval reopened</strong>{pending.reopen_events.map((e,i)=><p key={i}>{e.reason}</p>)}<p>The earlier approval stays in history. Verify the current evidence and request approval again.</p></div>}
    <div className="value-grid"><div><span>Original engine value</span><strong>{money(work.engine_value)}</strong></div><div><span>Approved workpaper value</span><strong>{money(work.approved_value)}</strong></div></div>
    {pending&&<div className="proposal-banner"><strong>Proposed: {money(pending.proposed_value)}</strong><p>Awaiting independent review. The approved value has not changed.</p><p>{pending.reason}</p>{pending.requires_partner&&<p><strong>Partner approval required: estimated tax effect exceeds $1,000. Helen can approve if she has not prepared this work.</strong></p>}<p>{pending.effect.basis==='estimated'?'Estimated tax change from v3':'Exact change'} · Federal {money(pending.effect.kind==='payment'?pending.effect.balance_change.federal:pending.effect.tax_change.federal)} · California {money(pending.effect.kind==='payment'?pending.effect.balance_change.california:pending.effect.tax_change.california)}</p>{pending.effect.note&&<small>{pending.effect.note}</small>}</div>}
    {!pending&&!stale&&canPrepare&&work.category&&!((trace.value.inputs as string[]??[]).length>0)&&<form className="workflow-form" onSubmit={e=>{e.preventDefault();void send('/workpaper/adjustments?ref='+encodeURIComponent(trace.ref),{expected_revision:work.revision,proposed_value:value,reason,evidence:refs(evidence)},'Correction proposed; verify the proposed value before independent review.');}}>
      <h4>Propose a correction</h4><label>Corrected value<input required type="number" step="0.01" value={value} onChange={e=>setValue(e.target.value)}/></label><label>Why this value changes<textarea required value={reason} onChange={e=>setReason(e.target.value)} placeholder="Explain the discrepancy and your proposed treatment."/></label><label>Evidence references, one per line<textarea required value={evidence} onChange={e=>setEvidence(e.target.value)} /></label><button disabled={busy}>Save proposal</button>
    </form>}
    {canPrepare&&<form className="workflow-form" onSubmit={e=>{e.preventDefault();void send('/workpaper/verify?ref='+encodeURIComponent(trace.ref),{expected_revision:work.revision,method,note:verificationNote,evidence:refs(evidence)},'Verification recorded against this value and its evidence.');}}>
      <h4>{pending?.status==='reopened'?'Check evidence again — ':''}Verify {pending?'proposed':'approved'} value: {money(work.review_value)}</h4><label>Verification method<select value={method} onChange={e=>setMethod(e.target.value)}>{work.verification_methods.map(m=><option value={m} key={m}>{m.replaceAll('_',' ')}</option>)}</select></label><label>What you checked<textarea required value={verificationNote} onChange={e=>setVerificationNote(e.target.value)} placeholder="State how the evidence supports this value."/></label><label>Evidence references<textarea required value={evidence} onChange={e=>setEvidence(e.target.value)}/></label><button disabled={busy}>Record verification</button>
    </form>}
    {pending&&<div className="workflow-form"><h4>Independent review</h4>{own?<p>You prepared this claim or its evidence. Switch to a different reviewer to approve it.</p>:!canReview?<p>A reviewer or partner must review this proposal.</p>:<>{pending.requires_partner&&actor.role!=='partner'&&<p>Switch to Helen, the partner, to approve this correction. You can reject it with a reason.</p>}<p>{currentVerification?'A current verification is recorded.':'A preparer must verify this proposed value before approval.'}</p><label>Review conclusion<textarea value={reviewNote} onChange={e=>setReviewNote(e.target.value)} placeholder="Explain your approval or request for changes."/></label><div className="workflow-actions"><button disabled={busy||!currentVerification||!reviewNote.trim()||(pending.requires_partner&&actor.role!=='partner')} onClick={()=>void send(`/workpaper/adjustments/${pending.id}/review`,{expected_revision:work.revision,decision:'approved',note:reviewNote},'Correction approved by an independent reviewer.')}>Approve correction</button><button className="secondary" disabled={busy||!reviewNote.trim()} onClick={()=>void send(`/workpaper/adjustments/${pending.id}/review`,{expected_revision:work.revision,decision:'rejected',note:reviewNote},'Proposal rejected; approved value preserved.')}>Reject proposal</button></div></>}</div>}
    {message&&<p className="success" role="status">{message}</p>}{error&&<p className="error" role="alert">{error}</p>}
    <details className="workflow-history" open={work.adjustments.length>0||work.verifications.length>0}><summary>Verification and correction history</summary>
      {!work.adjustments.length&&!work.verifications.length&&<p>No work has been recorded for this claim.</p>}
      {work.verifications.map(v=><div className="history-item" key={'v'+v.id}><strong>{v.current?'Verified':'Stale verification'} · {money(v.value)}</strong><p>{v.method.replaceAll('_',' ')} · {v.actor_id} · {new Date(v.at).toLocaleString()}</p><p>{v.note}</p><div className="evidence">{v.evidence.map(r=><button key={r} onClick={()=>onOpen(r)}>{r} ↗</button>)}</div></div>)}
      {work.adjustments.map(c=><div className="history-item" key={'a'+c.id}><strong>{c.status} · {money(c.original_value)} → {money(c.proposed_value)}</strong><p>{c.actor_id} · {new Date(c.at).toLocaleString()}</p><p>{c.reason}</p>{c.reopen_events.map((e,i)=><p key={'reopen'+i}>Reopened: {e.reason}</p>)}{c.reviews.map((r,i)=><p key={i}>{r.decision} by {r.actor_id}{r.current?'':' · evidence changed; review stale'}: {r.note}</p>)}</div>)}
    </details>
  </section>;
}
