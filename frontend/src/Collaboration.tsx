import {useEffect,useState} from 'react';
import {api} from './api';
import type {Actor,Trace} from './types';

type Answer={ref:string;text:string;actor_id:string;at:string;files:{ref:string;filename:string;size:number;sha256:string}[]};
type Question={ref:string;revision:number;prompt:string;recipient:string;claim_ref:string;claim_label:string;status:string;at:string;answers:Answer[]};
type Decision={ref:string;revision:number;claim_revision:number;question:string;alternatives:string[];choice:string;authority:string;rationale:string;evidence:string[];actor_id:string;at:string;status:string;requires_partner:boolean;adjustment_id:number|null;treatment:{cost_basis:string;acquired_on:string;holding_period:string}|null;reviews:{actor_id:string;decision:string;note:string;current:boolean}[]};
const json=(body:object)=>({method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
const evidenceRefs=(v:string)=>v.split(/[\n,]+/).map(x=>x.trim()).filter(Boolean);

function QuestionThread({question,actor,onSaved,onOpen}:{question:Question;actor:Actor;onSaved:()=>void;onOpen?:(ref:string)=>void}){
  const [text,setText]=useState('');const [files,setFiles]=useState<File[]>([]);const [error,setError]=useState('');const [busy,setBusy]=useState(false);
  async function answer(){
    setBusy(true);setError('');
    try{
      const encoded=await Promise.all(files.map(async f=>{
        if(f.size>5*1024*1024)throw new Error('Each file must be 5 MB or smaller.');
        const content=await new Promise<string>((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result).split(',')[1]);reader.onerror=()=>reject(new Error('Could not read '+f.name));reader.readAsDataURL(f);});
        return {filename:f.name,content_base64:content};
      }));
      await api('/collaboration/questions/'+question.ref+'/answers',json({expected_revision:question.revision,text,files:encoded}));
      setText('');setFiles([]);onSaved();
    }catch(e){setError((e as Error).message);}finally{setBusy(false);}
  }
  async function resolve(){setBusy(true);setError('');try{await api('/collaboration/questions/'+question.ref+'/resolve',json({expected_revision:question.revision}));onSaved();}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
  const client=actor.role==='client';
  return <article className="question-thread"><div className="caption">{question.status.replaceAll('_',' ')} · {new Date(question.at).toLocaleDateString()}</div><h3>{question.prompt}</h3>
    {onOpen?<button className="text-button" onClick={()=>onOpen(question.claim_ref)}>{question.claim_ref} ↗</button>:<p className="muted">Regarding: {question.claim_label}</p>}
    {question.answers.map(a=><div className="client-answer" key={a.ref}><strong>Client answer · {a.actor_id}</strong><p>{a.text}</p>{!client&&<p className="muted">Evidence reference: <button className="text-button" onClick={()=>onOpen?.(a.ref)}>{a.ref} ↗</button></p>}{a.files.map(f=><p key={f.ref}><a href={'/api/collaboration/attachments/'+f.ref}>{f.filename} ↓</a> <small>({Math.ceil(f.size/1024)} KB)</small>{!client&&<small className="evidence-ref">Evidence: {f.ref}</small>}</p>)}</div>)}
    {client&&question.status!=='resolved'&&<form className="workflow-form" onSubmit={e=>{e.preventDefault();void answer();}}><label>Your answer<textarea required value={text} onChange={e=>setText(e.target.value)}/></label><label>Supporting files (up to 3, 5 MB each)<input key={question.revision} type="file" multiple onChange={e=>setFiles(Array.from(e.target.files??[]))}/></label><p>Upload invented case-study files only. Your answer and files become evidence for the firm to review.</p><button disabled={busy||files.length>3}>{busy?'Saving…':'Send answer'}</button></form>}
    {!client&&question.status==='answered'&&['preparer','reviewer','partner'].includes(actor.role)&&<button className="secondary" disabled={busy} onClick={()=>void resolve()}>Mark question resolved</button>}
    {error&&<p role="alert" className="error">{error}</p>}
  </article>;
}

export function Questions({actor,refresh,onSaved,onOpen,claimRef}:{actor:Actor;refresh:number;onSaved:()=>void;onOpen?:(ref:string)=>void;claimRef?:string}){
  const [questions,setQuestions]=useState<Question[]>([]);const [error,setError]=useState('');
  useEffect(()=>{
    let active=true;
    const load=()=>api<Question[]>('/collaboration/questions'+(claimRef?'?ref='+encodeURIComponent(claimRef):'')).then(v=>{if(active){setQuestions(v);setError('');}}).catch(e=>{if(active)setError(e.message);});
    void load();const timer=window.setInterval(()=>void load(),5000);
    return()=>{active=false;window.clearInterval(timer);};
  },[actor.id,refresh,claimRef]);
  return <section className="questions-panel"><h2>{actor.role==='client'?'Questions from your tax team':'Client questions'}</h2><p className="muted">{actor.role==='client'?'Answer the questions assigned to you and add supporting files.':'Answers and attachments are evidence, not automatic verification or approval.'}</p>{questions.map(q=><QuestionThread key={q.ref} question={q} actor={actor} onSaved={onSaved} onOpen={onOpen}/>)}{!questions.length&&!error&&<p className="empty">{actor.role==='client'?'You have no questions waiting for an answer.':'No client questions yet. Open a claim to ask one.'}</p>}{error&&<p role="alert" className="error">{error}</p>}</section>;
}

export function ClaimCollaboration({trace,actor,refresh,onSaved,onOpen}:{trace:Trace;actor:Actor;refresh:number;onSaved:()=>void;onOpen:(ref:string)=>void}){
  const crypto=trace.ref==='v3:F8949.H.C6';const vehicle=trace.ref==='v3:F8283.A1.vehicle';
  const canPrepare=['preparer','reviewer','partner'].includes(actor.role);
  const alternatives=crypto?['Retain engine treatment while requesting evidence','Accept client basis and acquisition date','Defer conclusion for more evidence']:['Use documented charity sale proceeds','Keep client valuation pending support'];
  const [prompt,setPrompt]=useState(crypto?'Please upload the bank-statement line mentioned in your earlier message and explain how it relates to the BTC sold in June.':'Please upload any later charity correspondence about the donated vehicle. D66 and our call already record the auction sale; let us know if anything changed.');
  const [recipient,setRecipient]=useState(crypto?'cu-02':'cu-01');const [question,setQuestion]=useState(crypto?'What basis and acquisition date can we support for C6?':'Which evidence supports the vehicle deduction?');
  const [options,setOptions]=useState(alternatives.join('\n'));const [choice,setChoice]=useState(alternatives[0]);
  const [authority,setAuthority]=useState(crypto?'IRS digital asset recordkeeping: https://www.irs.gov/filing/digital-assets':vehicle?'2025 Instructions for Form 8283: https://www.irs.gov/instructions/i8283':'');
  const [rationale,setRationale]=useState('');const [evidence,setEvidence]=useState(crypto?'msg-07\nD34\nD35':vehicle?'doc:D66#page1\ncall-01':(trace.value.sources as string[]??[]).join('\n'));
  const [value,setValue]=useState(vehicle?'2900':'');const [basis,setBasis]=useState('3050');const [acquired,setAcquired]=useState('2021-03-15');
  const [decisions,setDecisions]=useState<Decision[]>([]);const [note,setNote]=useState('');const [error,setError]=useState('');const [message,setMessage]=useState('');const [busy,setBusy]=useState(false);
  useEffect(()=>{let active=true;api<Decision[]>('/collaboration/decisions?ref='+encodeURIComponent(trace.ref)).then(v=>{if(active)setDecisions(v);}).catch(e=>{if(active)setError(e.message);});return()=>{active=false;};},[trace.ref,trace.revision,refresh]);
  async function send(path:string,body:object,success:string){setBusy(true);setError('');setMessage('');try{await api(path,json(body));setMessage(success);onSaved();}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
  const opts=options.split('\n').map(x=>x.trim()).filter(Boolean);
  const acceptBasis=crypto&&choice==='Accept client basis and acquisition date';
  return <section className="collaboration-panel"><h3>Client evidence and judgment</h3><p>Ask for missing support, then record what you conclude and why. The client’s answer does not decide the tax treatment.</p>
    {canPrepare&&<details><summary>Ask the client</summary><form className="workflow-form" onSubmit={e=>{e.preventDefault();void send('/collaboration/questions?ref='+encodeURIComponent(trace.ref),{expected_revision:trace.revision,recipient,prompt},'Question saved in the client portal. Switch to the assigned client to answer.');}}><label>Client<select value={recipient} onChange={e=>setRecipient(e.target.value)}><option value="cu-01">Ngozi Okafor</option><option value="cu-02">Erik Lindqvist</option></select></label><label>Question visible to the client<textarea required value={prompt} onChange={e=>setPrompt(e.target.value)}/></label><button disabled={busy}>Ask client</button></form></details>}
    <Questions actor={actor} refresh={refresh} onSaved={onSaved} onOpen={onOpen} claimRef={trace.ref}/>
    {canPrepare&&<details open={vehicle||crypto}><summary>Record a judgment with authority</summary><form className="workflow-form" onSubmit={e=>{e.preventDefault();void send('/collaboration/decisions?ref='+encodeURIComponent(trace.ref),{expected_revision:trace.revision,question,alternatives:opts,choice,authority,rationale,evidence:evidenceRefs(evidence),outcome:crypto&&!acceptBasis||vehicle&&choice===alternatives[1]?'needs_evidence':'accepted',proposed_value:!crypto&&value!==''&&!(vehicle&&choice===alternatives[1])?value:null,cost_basis:acceptBasis?basis:null,acquired_on:acceptBasis?acquired:null},'Decision recorded. Verify any proposed correction above, then have an independent reviewer approve the decision below.');}}>
      <label>Question to settle<textarea required value={question} onChange={e=>setQuestion(e.target.value)}/></label><label>Alternatives, one per line<textarea required value={options} onChange={e=>setOptions(e.target.value)}/></label><label>Chosen treatment<select value={choice} onChange={e=>setChoice(e.target.value)}>{opts.map(o=><option key={o}>{o}</option>)}</select></label><label>Authority relied on<textarea required value={authority} onChange={e=>setAuthority(e.target.value)}/></label><label>Rationale — why the evidence supports this choice<textarea required value={rationale} onChange={e=>setRationale(e.target.value)}/></label><label>Evidence references (include the client-answer reference above)<textarea required value={evidence} onChange={e=>setEvidence(e.target.value)}/></label>
      {crypto?<><p>The packet records the client’s claim of about $3,050 paid in March 2021. It does not establish that claim by itself. Choose whether the additional support is sufficient.</p>{acceptBasis&&<><label>Proposed supported basis<input required type="number" step="0.01" min="0" value={basis} onChange={e=>setBasis(e.target.value)}/></label><label>Proposed acquisition date<input required type="date" value={acquired} onChange={e=>setAcquired(e.target.value)}/></label><p>The proposed gain is proceeds minus basis. Holding-period changes are recorded; unsupported totals remain affected.</p></>}</>:<label>Corrected claim value (optional; blank keeps the current value)<input type="number" step="0.01" value={value} onChange={e=>setValue(e.target.value)}/></label>}
      {(crypto&&!acceptBasis||vehicle&&choice===alternatives[1])&&<p>This choice keeps the current claim value and leaves the evidence issue open, even after the reviewer approves the decision.</p>}<button disabled={busy}>Save decision for review</button>
    </form></details>}
    <h4>Decision history</h4>{!decisions.length&&<p>No judgment has been recorded.</p>}{decisions.map(d=><article className="history-item" key={d.ref}><strong>{d.status} · {d.choice}</strong><p>{d.question}</p><p>Alternatives: {d.alternatives.join(' / ')}</p><p>Authority: {d.authority}</p><p>{d.rationale}</p>{d.treatment&&<p>Proposed basis {d.treatment.cost_basis} · acquired {d.treatment.acquired_on} · {d.treatment.holding_period}</p>}<div className="evidence">{d.evidence.map(r=><button key={r} onClick={()=>onOpen(r)}>{r} ↗</button>)}</div>{d.requires_partner&&<p>Partner approval required.</p>}{d.reviews.map((r,i)=><p key={i}>{r.decision} by {r.actor_id}{r.current?'':' · stale'}: {r.note}</p>)}
      {['proposed','stale'].includes(d.status)&&['reviewer','partner'].includes(actor.role)&&<div className="workflow-form"><label>Independent review conclusion<textarea value={note} onChange={e=>setNote(e.target.value)}/></label><p>Approve the authority, evidence and any linked correction together. Self-review is blocked. A proposed correction must have a current verification.</p><div className="workflow-actions"><button disabled={busy||!note.trim()||d.actor_id===actor.id||(d.requires_partner&&actor.role!=='partner')} onClick={()=>void send('/collaboration/decisions/'+d.ref+'/review',{expected_revision:d.revision,expected_claim_revision:d.claim_revision,decision:'approved',note},'Decision and any linked correction approved together.')}>Approve decision</button><button className="secondary" disabled={busy||!note.trim()||d.actor_id===actor.id} onClick={()=>void send('/collaboration/decisions/'+d.ref+'/review',{expected_revision:d.revision,expected_claim_revision:d.claim_revision,decision:'rejected',note},'Decision rejected; original values preserved.')}>Reject decision</button></div></div>}
    </article>)}{message&&<p role="status" className="success">{message}</p>}{error&&<p role="alert" className="error">{error}</p>}
  </section>;
}
