import React, {useEffect, useRef, useState} from 'react';
import {createRoot} from 'react-dom/client';
import './style.css';
import {api} from './api';
import {Questions, ClaimCollaboration} from './Collaboration';
import {Filing} from './Filing';
import {History} from './History';
import {WhatIf} from './WhatIf';
import {PriorYear} from './PriorYear';
import {Sales} from './Sales';
import {BusinessIncome} from './BusinessIncome';
import {Source} from './Source';
import {ClaimWorkpaper} from './ClaimWorkpaper';
import {DocumentDisposition} from './DocumentDisposition';
import type {Actor, Trace} from './types';

type Finding = {new_claim?:boolean; id:string; title:string; claim:string; observed:string; proposed:string; evidence:string[]; tax_effect:Record<string,string>};
type WorkSummary = {approved_adjustments:number; reopened_adjustments:number; summary:Record<string,{total_tax:string; payments:string; balance_due:string}>; tax_change:Record<string,string>; basis:string; changed_lines:{key:string;value:string|number;basis:string}[]};
type ClientSummary = {summary:WorkSummary['summary']; basis:string};
type Statuses = Record<string,{status:string; proposed_value:string}>;
type Report = {counts:Record<string,number>; locators:{resolved:number;total:number}; findings:Finding[]};
const money = (value:string|number) => Number(value).toLocaleString('en-US',{style:'currency',currency:'USD',maximumFractionDigits:0});
const pages:Record<string,{title:string; description:string; icon:string}> = {
  queue:{title:'Review workspace',description:'Resolve discrepancies, check the evidence, and send corrections for review.',icon:'check'},
  business:{title:'Business income',description:'Follow the difference between the books and the return, one step at a time.',icon:'briefcase'},
  sales:{title:'Investment sales',description:'Review sales together. Keep exceptions separate until their evidence is complete.',icon:'chart'},
  questions:{title:'Client questions',description:'Ask for missing information and keep the answers with the work they support.',icon:'message'},
  documents:{title:'Evidence library',description:'Find a source document, inspect its extracted values, and record how it was used.',icon:'file'},
  history:{title:'Changes & history',description:'Compare versions and see who changed what, with the supporting evidence.',icon:'clock'},
  whatif:{title:'Explore a scenario',description:'Preview the effect of a change before proposing it for the workpaper.',icon:'sliders'},
  prior:{title:'Compare last year',description:'Explain meaningful differences from the previous return.',icon:'compare'},
  filing:{title:'Filing checklist',description:'Complete the review, collect approvals, and follow the simulated submission.',icon:'send'},
};
function Icon({name}:{name:string}) {
  const paths:Record<string,React.ReactNode> = {
    check:<><rect x="4" y="3" width="16" height="18" rx="3"/><path d="m8 12 3 3 5-6"/></>,
    briefcase:<><rect x="3" y="7" width="18" height="14" rx="3"/><path d="M8 7V4h8v3M3 12a22 22 0 0 0 18 0M10 13h4"/></>,
    chart:<><path d="M4 3v17h17M8 15l4-5 4 2 5-7"/></>,
    message:<path d="M21 11a8 8 0 0 1-8 8H8l-5 3V11a9 9 0 0 1 18 0Z"/>,
    file:<><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9ZM14 3v6h6M8 13h8M8 17h5"/></>,
    clock:<><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>,
    sliders:<><path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="3"/><circle cx="16" cy="17" r="3"/></>,
    compare:<><path d="M4 7h16l-4-4M20 17H4l4 4M4 7v5M20 17v-5"/></>,
    send:<><path d="m3 3 18 9-18 9 4-9ZM7 12h14"/></>,
    arrow:<path d="M5 12h14m-5-5 5 5-5 5"/>,
    search:<><circle cx="10" cy="10" r="6"/><path d="m15 15 5 5"/></>,
  };
  return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]??paths.file}</svg>;
}
const statusLabel = (status:string) => ({approved:'Approved',proposed:'Awaiting review',rejected:'Changes requested',reopened:'Review reopened',stale:'Review out of date',judgment_approved:'Decision approved',judgment_proposed:'Awaiting decision review',judgment_rejected:'Decision rejected',needs_evidence:'Needs evidence'} as Record<string,string>)[status]??'Needs review';
const complete = (status:string) => ['approved','judgment_approved'].includes(status);
const findingCopy:Record<string,{title:string; why:string}> = {
  E1:{title:'Savings interest may be counted twice',why:'The bank and investment statements appear to report the same interest.'},
  E2:{title:'Foreign interest uses last year’s exchange rate',why:'Check the Swedish interest against the exchange rate for this return’s tax year.'},
  E3:{title:'The donated car deduction needs checking',why:'The deduction is higher than the amount the charity received from selling the car.'},
  E4:{title:'Business receipts may be counted twice',why:'Payment-platform receipts already appear in the business books.'},
  E5:{title:'A stock sale is missing its purchase cost',why:'Check the supplemental stock statement so the full sale is not treated as profit.'},
  E6:{title:'Another stock sale is missing its purchase cost',why:'Check the purchase cost for this separate sale against the supplemental statement.'},
  E7:{title:'A long-term stock sale is missing its purchase cost',why:'Check the supplemental statement before approving the reported gain.'},
  E8:{title:'The same mileage page was counted twice',why:'Remove the duplicate page from the business mileage calculation.'},
  E9:{title:'Mortgage interest may be counted twice',why:'The mortgage payoff interest already appears on the annual lender statement.'},
  E10:{title:'Federal payments do not match IRS records',why:'Compare the estimated payments on the return with the IRS payment history.'},
  E11:{title:'A California payment belongs to a different year',why:'Check which tax year the payment was assigned to before including it here.'},
  E12:{title:'An investment sale is missing from the return',why:'Inspect the brokerage supplement and record the missing sale through the source workflow.'},
  E13:{title:'Phone and internet expenses include personal use',why:'Confirm the business-use share with the client before allowing the deduction.'},
  E14:{title:'A family subscription appears in business expenses',why:'Check the client’s explanation and remove the personal expense if supported.'},
};
const findingValue = (f:Finding,value:string) => f.id==='E8'
  ? Number(value).toLocaleString('en-US')+' miles'
  : Number(value).toLocaleString('en-US',{style:'currency',currency:'USD',maximumFractionDigits:2});


function App() {
  const [actors,setActors]=useState<Actor[]>([]);
  const [actor,setActor]=useState<Actor|null>(null);
  const [report,setReport]=useState<Report|null>(null);
  const [docs,setDocs]=useState<{ref:string;payload:{title:string;extraction:{status:string}}}[]>([]);
  const [trace,setTrace]=useState<Trace|null>(null);
  const [trail,setTrail]=useState<Trace[]>([]);
  const [detail,setDetail]=useState('review');
  const dialog=useRef<HTMLDialogElement>(null);
  const [refresh,setRefresh]=useState(0);
  const [whatIfRef,setWhatIfRef]=useState<string|undefined>();
  const [tab,setTab]=useState('queue');
  const [error,setError]=useState('');
  const [loading,setLoading]=useState(false);
  const [query,setQuery]=useState('');
  const [queueQuery,setQueueQuery]=useState('');
  const [filter,setFilter]=useState('open');
  const [summary,setSummary]=useState<ClientSummary|null>(null);
  const [workSummary,setWorkSummary]=useState<WorkSummary|null>(null);
  const [statuses,setStatuses]=useState<Statuses>({});
  const client=actor?.role==='client';
  useEffect(()=>{api<Actor[]>('/actors').then(setActors).catch(e=>setError(e.message)); api<Actor>('/session').then(setActor).catch(()=>{});},[]);
  useEffect(()=>{
    setReport(null);setDocs([]);setTrace(null);setTrail([]);setSummary(null);setWorkSummary(null);setStatuses({});
    if(!actor)return;
    if(actor.role==='client')setTab('questions');
    setLoading(true);setError('');
    let active=true;
    const load=actor.role==='client'
      ? api<ClientSummary>('/summary').then(v=>{if(active)setSummary(v);})
      : Promise.all([api<Report>('/audit').then(v=>{if(active)setReport(v);}),api<typeof docs>('/records?kind=document').then(v=>{if(active)setDocs(v);}),api<WorkSummary>('/workpaper/summary').then(v=>{if(active)setWorkSummary(v);}),api<Statuses>('/workpaper/status').then(v=>{if(active)setStatuses(v);})]);
    load.catch(e=>{if(active)setError(e.message);}).finally(()=>{if(active)setLoading(false);});
    return ()=>{active=false;};
  },[actor?.id]);
  useEffect(()=>{
    if(trace && !dialog.current?.open)dialog.current?.showModal();
    if(!trace && dialog.current?.open)dialog.current?.close();
  },[!!trace]);
  async function switchRole(id:string){
    setError('');setReport(null);setTrace(null);setDocs([]);
    try{setActor(await api<Actor>('/session',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({actor_id:id})}));}
    catch(e){setActor(null);setError((e as Error).message);}
  }
  async function open(ref:string,follow=false){
    setError('');
    try{
      const next=await api<Trace>('/trace?ref='+encodeURIComponent(ref));
      if(follow&&trace)setTrail(prev=>[...prev,trace]);else setTrail([]);
      setDetail(next.kind==='claim'?'review':'evidence');setTrace(next);
    }catch(e){setError((e as Error).message);}
  }
  function refreshWork(){
    setRefresh(v=>v+1);
    if(trace)api<Trace>('/trace?ref='+encodeURIComponent(trace.ref)).then(setTrace).catch(e=>setError(e.message));
    Promise.all([api<Report>('/audit').then(setReport),api<WorkSummary>('/workpaper/summary').then(setWorkSummary),api<Statuses>('/workpaper/status').then(setStatuses),api<typeof docs>('/records?kind=document').then(setDocs)]).catch(e=>setError(e.message));
  }
  function navigate(key:string){setTab(key);setError('');}
  const queue=report?[...report.findings.map(f=>({...f,ref:'v3:'+f.claim})),{id:'C6',title:'Crypto purchase cost and date need support',claim:'F8949.H.C6',ref:'v3:F8949.H.C6',observed:'',proposed:'',evidence:[],tax_effect:{},new_claim:false}]:[];
  const done=queue.filter(f=>complete(statuses[f.ref]?.status)).length;
  const waiting=queue.filter(f=>['proposed','judgment_proposed'].includes(statuses[f.ref]?.status)).length;
  const visible=queue.filter(f=>(filter==='all'||(filter==='done'?complete(statuses[f.ref]?.status):filter==='waiting'?['proposed','judgment_proposed'].includes(statuses[f.ref]?.status):!complete(statuses[f.ref]?.status))))
    .filter(f=>(f.title+' '+(findingCopy[f.id]?.title??'')+' '+f.id+' '+f.claim).toLowerCase().includes(queueQuery.toLowerCase()));
  const navGroups=client?[{label:'Your return',keys:['questions','filing']}]:[{label:'Work on the return',keys:['queue','business','sales','questions','documents']},{label:'Compare & explore',keys:['history','whatif','prior']},{label:'Finish',keys:['filing']}];
  const numericClaim=actor&&trace?.kind==='claim'&&trace.ref.startsWith('v3:')&&typeof trace.value.value==='number';
  const follow=(ref:string)=>void open(ref,true);
  return <div className="app">
    <a className="skip-link" href="#main-content">Skip to content</a>
    <aside className="sidebar">
      <a className="brand" href="/" aria-label="Miraflores home"><span className="brand-mark">m</span>miraflores<span className="brand-period">.</span></a>
      <div className="engagement-card"><span className="caption">2025 TAX RETURN</span><strong>Okafor–Lindqvist</strong><span>Joint return · CA / TX</span></div>
      <nav aria-label="Workspace">{navGroups.map(group=><div className="nav-group" key={group.label}><p className="caption">{group.label}</p>{group.keys.map(key=><button className={tab===key?'selected':''} aria-current={tab===key?'page':undefined} key={key} onClick={()=>navigate(key)}><Icon name={pages[key].icon}/><span>{client?(key==='questions'?'Your questions':'Approve & copies'):pages[key].title}</span>{key==='queue'&&queue.length>0&&<span className="nav-count">{queue.length-done}</span>}</button>)}</div>)}</nav>
      <div className="aside-bottom"><span className="demo-label"><span className="dot"/>Prototype workspace</span><p>Synthetic case study.<br/>Filing actions are simulated.</p></div>
    </aside>
    <main id="main-content">
      <header className="topbar"><div className="breadcrumb">Workspace <span>/</span> <strong>2025 return</strong></div><label className="identity"><span>Demo identity</span><select value={actor?.id||''} onChange={e=>void switchRole(e.target.value)}><option value="" disabled>Choose identity</option>{actors.map(a=><option key={a.id} value={a.id}>{a.name} · {a.role.replaceAll('_',' ')}</option>)}</select></label></header>
      <section className="intro"><div><p className="eyebrow">{client?'YOUR RETURN, TOGETHER':'OKAFOR–LINDQVIST / 2025'}</p><h1>{client?(tab==='filing'?'Approve & download':'Your questions'):pages[tab].title}</h1><p>{client?'Your team will guide you through the information and approvals they need.':pages[tab].description}</p></div><span className="pill">{client?'Client view':'Engine v3 · Working draft'}</span></section>
      {error&&<div role="alert" className="error">{error}</div>}
      {!actor&&!error&&<div className="empty">Choose a demo identity above to open the workspace.</div>}
      {loading&&<div className="loading-state" role="status"><span className="loading-dot"/>Loading your workspace…</div>}
      {client&&summary&&tab!=='filing'&&<section className="client-summary"><div><span className="caption">CURRENT ESTIMATES</span><h2>A quick look at your return</h2><p>Amounts may change while your team completes the review.</p></div>{['federal','california'].map(j=><div key={j}><span>{j==='federal'?'Federal':'California'} estimated tax</span><strong>{money(summary.summary[j].total_tax)}</strong><small>Balance due {money(summary.summary[j].balance_due)}</small></div>)}<details><summary>How these estimates are calculated</summary><p>{summary.basis}</p></details></section>}
      {client&&actor&&(tab==='filing'?<Filing key={actor.id} actor={actor} refresh={refresh} onSaved={()=>setRefresh(v=>v+1)} onOpen={ref=>void open(ref)}/>:<Questions key={actor.id} actor={actor} refresh={refresh} onSaved={()=>setRefresh(v=>v+1)}/>)}
      {report&&actor&&<>
        {tab==='queue'&&<>
          <section className="overview-grid" aria-label="Review overview"><div className="overview-progress"><span className="caption">REVIEW PROGRESS</span><strong>{done}<span> / {queue.length} findings approved</span></strong><progress value={done} max={queue.length} aria-label="Findings approved"/><p>{queue.length-done} findings still need attention. Full filing readiness is tracked separately.</p></div>{workSummary&&['federal','california'].map(j=><div className="tax-card" key={j}><span>{j==='federal'?'Federal':'California'} estimated tax</span><strong>{money(workSummary.summary[j].total_tax)}</strong><small>Approved corrections only</small><span className="tax-change">Change from engine: {money(workSummary.tax_change[j])}</span></div>)}</section>
          <section className="next-step"><div className="step-icon"><Icon name="check"/></div><div><h2>Start with one discrepancy</h2><p>Open a finding → check its sources → propose and verify a correction. A different reviewer approves it.</p></div><button className="secondary" onClick={()=>navigate('filing')}>Filing checklist <Icon name="arrow"/></button></section>
          {workSummary&&<details className="calculation-note"><summary>About these estimates · {workSummary.approved_adjustments} approved corrections</summary><p>{workSummary.basis}</p><p>Pending corrections are excluded. Unsupported downstream lines are not automatically recomputed.</p>{workSummary.changed_lines.map(l=><p key={l.key}>{l.key}: {l.value} · {l.basis}</p>)}</details>}
          {!!workSummary?.reopened_adjustments&&<p className="proposal-banner" role="status">{workSummary.reopened_adjustments} corrections need a fresh review because their evidence changed.</p>}
          <div className="section-heading"><h2>Findings to review <span className="count-label">{queue.length}</span></h2><span className="muted">Evidence checks, separate from engine diagnostics</span></div>
          <div className="queue-toolbar"><div className="filter-group" aria-label="Filter findings">{[['open','Needs attention',queue.length-done],['waiting','Awaiting review',waiting],['done','Approved',done],['all','All',queue.length]].map(([key,label,count])=><button key={key} aria-pressed={filter===key} className={filter===key?'active':''} onClick={()=>setFilter(String(key))}>{label}<span>{count}</span></button>)}</div><label className="search-box"><Icon name="search"/><input aria-label="Search findings" placeholder="Search findings…" value={queueQuery} onChange={e=>setQueueQuery(e.target.value)}/></label></div>
          <div className="findings">{visible.map(f=><article className="finding" key={f.id}><span className="finding-id">{f.id}</span><div className="finding-body"><div className="finding-topline"><span className={'status '+(statuses[f.ref]?.status??'needs_evidence')}>{f.id==='C6'&&!statuses[f.ref]?'Needs client evidence':statusLabel(statuses[f.ref]?.status)}</span><span className="record-ref">{f.claim}</span></div><h3><button className="text-button" onClick={()=>void open(f.new_claim?f.evidence[0]:f.ref)}>{findingCopy[f.id]?.title??f.title}</button></h3>{findingCopy[f.id]&&<p className="finding-explanation">{findingCopy[f.id].why}</p>}{f.id==='C6'?<p className="finding-description">Confirm the original purchase cost and date with the client before deciding the treatment.</p>:<p className="finding-description">Return shows <strong>{findingValue(f,f.observed)}</strong><span className="value-arrow">→</span>Evidence suggests <strong>{findingValue(f,f.proposed)}</strong></p>}<div className="evidence">{f.evidence.map(ref=><button key={ref} onClick={()=>void open(ref)}><Icon name="file"/>{ref}</button>)}</div></div><button className="review-button" aria-label={'Review '+(findingCopy[f.id]?.title??f.title)} onClick={()=>void open(f.new_claim?f.evidence[0]:f.ref)}>Review <Icon name="arrow"/></button></article>)}{!visible.length&&<div className="empty"><h3>No findings in this view</h3><p>Try another filter or search term.</p><button className="secondary" onClick={()=>{setFilter('all');setQueueQuery('');}}>Show all findings</button></div>}</div>
        </>}
        {tab==='documents'&&<><div className="library-summary"><Icon name="file"/><span><strong>{docs.length} documents available</strong> in the current workspace</span></div><label className="search-box library-search"><Icon name="search"/><input aria-label="Search documents" placeholder="Search by document title or ID…" value={query} onChange={e=>setQuery(e.target.value)}/></label><div className="documents">{docs.filter(d=>(d.ref+' '+d.payload.title).toLowerCase().includes(query.toLowerCase())).map(d=><button key={d.ref} onClick={()=>void open(d.ref)}><span className="document-icon"><Icon name="file"/></span><span className="document-title"><strong>{d.payload.title}</strong><small>{d.ref} · {d.payload.extraction.status.replaceAll('_',' ')}</small></span><Icon name="arrow"/></button>)}</div>{!docs.some(d=>(d.ref+' '+d.payload.title).toLowerCase().includes(query.toLowerCase()))&&<div className="empty">No documents match “{query}”. Try a different title or ID.</div>}</>}
        {tab==='filing'&&<Filing actor={actor} refresh={refresh} onSaved={refreshWork} onOpen={ref=>void open(ref)}/>}
        {tab==='history'&&<History actor={actor} refresh={refresh} onOpen={ref=>void open(ref)}/>}
        {tab==='whatif'&&<WhatIf key={actor.id+':'+whatIfRef} actor={actor} refresh={refresh} initialRef={whatIfRef} onSaved={refreshWork} onOpen={ref=>void open(ref)}/>}
        {tab==='prior'&&<PriorYear actor={actor} refresh={refresh} onSaved={refreshWork} onOpen={ref=>void open(ref)}/>}
        {tab==='questions'&&<Questions actor={actor} refresh={refresh} onSaved={refreshWork} onOpen={ref=>void open(ref)}/>}
        {tab==='sales'&&<Sales actor={actor} refresh={refresh} onSaved={refreshWork} onOpen={ref=>void open(ref)}/>}
        {tab==='business'&&<BusinessIncome key={actor.id} refresh={refresh} onOpen={ref=>void open(ref)}/>}
        <footer className="footnote"><span className="dot"/>Original records are preserved. Corrections take effect after independent approval. This prototype does not file a real return.</footer>
      </>}
    </main>
    <dialog ref={dialog} className="drawer" aria-labelledby="detail-title" onCancel={()=>setTrace(null)} onClose={()=>setTrace(null)}>
      {trace&&<><div className="drawer-header"><div><p className="caption">{trace.kind.replaceAll('_',' ')} DETAILS</p><h2 id="detail-title">{String(trace.value.label??trace.value.title??trace.ref)}</h2><span className="record-ref">{trace.ref}</span></div><button autoFocus className="close secondary" aria-label="Close detail panel" onClick={()=>setTrace(null)}>×</button></div>
        {error&&<p className="error" role="alert">{error}</p>}
        {!!trail.length&&<button className="back-link text-button" onClick={()=>{const previous=trail.at(-1)!;setTrace(previous);setDetail(previous.kind==='claim'?'review':'evidence');setTrail(prev=>prev.slice(0,-1));}}>← Back to {trail.at(-1)!.ref}</button>}
        {trace.kind==='claim'&&!trace.ref.startsWith('v3:')&&<p className="proposal-banner">Historical engine version · read only</p>}
        <div className="detail-switcher" aria-label="Detail views">{(numericClaim?[['review','Review value'],['discussion','Questions & decisions'],['evidence','Evidence & details']]:trace.kind==='document'?[['evidence','Source document'],['review','Document review']]:[['evidence','Evidence & details']]).map(([key,label])=><button key={key} aria-pressed={detail===key} className={detail===key?'active':''} onClick={()=>setDetail(key)}>{label}</button>)}</div>
        <div key={actor?.id+':'+trace.ref}>
          {numericClaim&&actor&&<><div hidden={detail!=='review'}><ClaimWorkpaper trace={trace} actor={actor} suggestion={report?.findings.find(f=>'v3:'+f.claim===trace.ref)} onSaved={refreshWork} onOpen={follow}/><button className="secondary" onClick={()=>{setWhatIfRef(trace.ref);navigate('whatif');setTrace(null);}}>Preview a what-if scenario <Icon name="arrow"/></button></div><div hidden={detail!=='discussion'}><ClaimCollaboration trace={trace} actor={actor} refresh={refresh} onSaved={refreshWork} onOpen={follow}/></div></>}
          {trace.kind==='claim'&&!numericClaim&&detail==='review'&&<p className="empty">This value is read only. Open Evidence & details to inspect its sources.</p>}
          {actor&&trace.kind==='document'&&<div hidden={detail!=='review'}><DocumentDisposition trace={trace} actor={actor} onSaved={refreshWork}/></div>}
          <div hidden={detail!=='evidence'}><Source trace={trace} actor={actor} onOpen={follow} onSaved={refreshWork}/><h3>Connected records <span className="count-label">{trace.edges.length}</span></h3>{trace.edges.map((e,i)=><button className="edge" key={i} onClick={()=>follow(e.source===trace.ref?e.target:e.source)}><span>{e.kind.replaceAll('_',' ')}</span><strong>{e.source===trace.ref?e.target:e.source}</strong><Icon name="arrow"/></button>)}{!trace.edges.length&&<p className="muted">No connected records.</p>}</div>
        </div>
      </>}
    </dialog>
  </div>;
}
createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
