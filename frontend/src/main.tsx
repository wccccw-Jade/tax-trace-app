import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';
import {api} from './api';
import {Source} from './Source';
import {ClaimWorkpaper} from './ClaimWorkpaper';
import {DocumentDisposition} from './DocumentDisposition';
import type {Actor,Trace} from './types';

type Finding = { new_claim?:boolean; id: string; title: string; claim: string; observed: string; proposed: string; evidence: string[]; tax_effect: Record<string,string> };
type WorkSummary = {approved_adjustments:number;summary:Record<string,{total_tax:string;payments:string;balance_due:string}>;tax_change:Record<string,string>;basis:string;changed_lines:{key:string;value:string|number;basis:string}[]};
type Statuses=Record<string,{status:string;proposed_value:string}>;
type Report = { counts: Record<string,number>; locators: { resolved:number; total:number }; findings: Finding[]; unresolved_references: unknown[] };
function App() {
  const [actors,setActors] = useState<Actor[]>([]);
  const [actor,setActor] = useState<Actor|null>(null);
  const [report,setReport] = useState<Report|null>(null);
  const [docs,setDocs] = useState<{ref:string;payload:{title:string;extraction:{status:string}}}[]>([]);
  const [trace,setTrace] = useState<Trace|null>(null);
  const [tab,setTab] = useState('queue');
  const [error,setError] = useState('');
  const [loading,setLoading] = useState(false);
  const [query,setQuery] = useState('');
  const [summary,setSummary] = useState<unknown>(null);
  const [workSummary,setWorkSummary]=useState<WorkSummary|null>(null);
  const [statuses,setStatuses]=useState<Statuses>({});
  useEffect(()=>{api<Actor[]>('/actors').then(setActors).catch(e=>setError(e.message));
    api<Actor>('/session').then(setActor).catch(()=>{});},[]);
  useEffect(()=>{
    setReport(null);setDocs([]);setTrace(null);setSummary(null);setWorkSummary(null);setStatuses({});
    if(!actor)return;
    setLoading(true);setError('');
    let active=true;
    const load = actor.role==='client'
      ? api('/summary').then(value=>{if(active)setSummary(value);})
      : Promise.all([api<Report>('/audit').then(value=>{if(active)setReport(value);}),api<typeof docs>('/records?kind=document').then(value=>{if(active)setDocs(value);}),api<WorkSummary>('/workpaper/summary').then(value=>{if(active)setWorkSummary(value);}),api<Statuses>('/workpaper/status').then(value=>{if(active)setStatuses(value);})]);
    load.catch(e=>{if(active)setError(e.message);}).finally(()=>{if(active)setLoading(false);});
    return ()=>{active=false;};
  },[actor?.id]);
  async function switchRole(id:string){
    setError('');setReport(null);setTrace(null);setDocs([]);
    try {setActor(await api<Actor>('/session',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({actor_id:id})}));}
    catch(e){setActor(null);setError((e as Error).message);}
  }
  async function open(ref:string){
    setError('');
    try{setTrace(await api<Trace>('/trace?ref='+encodeURIComponent(ref)));}
    catch(e){setError((e as Error).message);}
  }
  function refreshWork(){
    if(trace)void open(trace.ref);
    Promise.all([api<Report>('/audit').then(setReport),api<WorkSummary>('/workpaper/summary').then(setWorkSummary),api<Statuses>('/workpaper/status').then(setStatuses),api<typeof docs>('/records?kind=document').then(setDocs)]).catch(e=>setError(e.message));
  }
  return <div className="app">
    <aside><a className="brand" href="/">m<span>miraflores</span></a><div className="caption">WORKPAPER / 2025</div>
      <h2>Okafor–Lindqvist</h2><p className="muted">Joint return · California / Texas</p>
      <nav>{[['queue','Review queue'],['documents','Evidence library']].map(([key,label])=><button className={tab===key?'selected':''} key={key} onClick={()=>setTab(key)}>{label}<span>↗</span></button>)}</nav>
      <div className="aside-bottom"><span className="dot"/> Local demo<span className="muted">Story A · Trace & correct</span></div>
    </aside>
    <main><header><div className="caption">ENGAGEMENT CL-20417 / ENGINE v3</div><label>Acting as <select aria-label="Demo identity" value={actor?.id||''} onChange={e=>void switchRole(e.target.value)}><option value="" disabled>Choose identity</option>{actors.map(a=><option key={a.id} value={a.id}>{a.name} · {a.role.replaceAll('_',' ')}</option>)}</select></label></header>
      <section className="intro"><div><div className="caption">EVIDENCE BEFORE APPROVAL</div><h1>{actor?.role==='client'?'Your return summary':tab==='queue'?'Make the return provable.':'Every document, accounted for.'}</h1><p className="muted">{tab==='queue'?'Start with the discrepancies. Follow each claim back to its evidence.':'Original page text, extraction details, and links to where each value was used.'}</p></div><span className="pill">Unreviewed</span></section>
      {error&&<div role="alert" className="error">{error}</div>}
      {!actor&&!error&&<div className="empty">Choose a demo identity to open the workspace.</div>}
      {loading&&<p role="status">Loading imported records…</p>}
      {summary!==null&&<section className="panel"><h2>Current workpaper summary</h2><pre>{JSON.stringify(summary,null,2)}</pre><p>Client approvals and questions arrive in later implementation stories.</p></section>}
      {report&&<>{workSummary&&<section className="work-summary" aria-label="Approved workpaper summary"><div><h2>Approved workpaper</h2><p>{workSummary.approved_adjustments} approved corrections · proposals excluded</p></div>{['federal','california'].map(j=><div key={j}><span>{j==='federal'?'Federal':'California'} estimated tax</span><strong>{Number(workSummary.summary[j].total_tax).toLocaleString('en-US',{style:'currency',currency:'USD',maximumFractionDigits:0})}</strong><small>Change from v3: {workSummary.tax_change[j]}</small></div>)}<details><summary>Calculation basis</summary><p>{workSummary.basis}</p><p>Unsupported downstream lines remain affected and are not silently recomputed.</p>{workSummary.changed_lines.map(l=><p key={l.key}>{l.key}: {l.value} · {l.basis}</p>)}</details></section>}<div className="stats">{[['Documents',report.counts.documents],['Extracted values',report.counts.extractions],['Source anchors',`${report.locators.resolved} / ${report.locators.total}`],['Independent findings',report.findings.length]].map(([label,value])=><div key={label}><span>{label}</span><strong>{value}</strong></div>)}</div>
      <div className="section-heading"><h2>{tab==='queue'?'Independent findings':'Document index'}</h2><span className="muted">{tab==='queue'?'Engine findings with persisted review status':'74 supplied records'}</span></div>
      {tab==='queue'?<div className="findings">{report.findings.map(f=><article className="finding" key={f.id}><span className="finding-id">{f.id}</span><div><span className={"status "+(statuses['v3:'+f.claim]?.status??'contradicted')}>{({approved:'Approved correction',proposed:'Awaiting review',rejected:'Proposal rejected',stale:'Review stale'} as Record<string,string>)[statuses['v3:'+f.claim]?.status]??'Contradicted'}</span><h3><button className="text-button" onClick={()=>void open(f.new_claim?f.evidence[0]:'v3:'+f.claim)}>{f.title}</button></h3><div className="muted">{f.claim} · Engine {f.observed} → proposed {f.proposed}</div><div className="evidence">{f.evidence.map(ref=><button key={ref} onClick={()=>void open(ref)}>{ref} ↗</button>)}</div></div><span className="muted">{statuses['v3:'+f.claim]?.status==='approved'?'Reviewed':'Needs review'}</span></article>)}</div>:<><input className="search" aria-label="Search documents" placeholder="Find a document by title or ID…" value={query} onChange={e=>setQuery(e.target.value)}/><div className="documents">{docs.filter(d=>(d.ref+' '+d.payload.title).toLowerCase().includes(query.toLowerCase())).map(d=><button key={d.ref} onClick={()=>void open(d.ref)}><strong>{d.ref}</strong><span>{d.payload.title}</span><small>{d.payload.extraction.status.replaceAll('_',' ')}</small></button>)}</div></>}
      <p className="footnote">Independent checks are separate from engine diagnostics. Approved corrections are recorded in the workpaper. No return is filed by this demo.</p></>}
    </main>
    {trace&&<section className="drawer" aria-label="Evidence detail"><button className="close" aria-label="Close evidence" onClick={()=>setTrace(null)}>×</button><div className="caption">SOURCE & USAGE</div><h2>{trace.ref}</h2>{trace.value.printed_content!==undefined&&<span className="pill">Simulated source document</span>}{actor&&trace.kind==='claim'&&typeof trace.value.value==='number'&&<ClaimWorkpaper key={actor.id+':claim:'+trace.ref} trace={trace} actor={actor} suggestion={report?.findings.find(f=>'v3:'+f.claim===trace.ref)} onSaved={refreshWork} onOpen={ref=>void open(ref)}/>}
    {actor&&trace.kind==='document'&&<DocumentDisposition key={actor.id+':doc:'+trace.ref} trace={trace} actor={actor} onSaved={refreshWork}/>}
    <Source key={actor?.id+':'+trace.ref} trace={trace} actor={actor} onOpen={ref=>void open(ref)} onSaved={refreshWork}/><h3>Linked evidence</h3>{trace.edges.map((e,i)=><button className="edge" key={i} onClick={()=>void open(e.source===trace.ref?e.target:e.source)}>{e.kind} · {e.source===trace.ref?e.target:e.source} ↗</button>)}</section>}
  </div>;
}
createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
