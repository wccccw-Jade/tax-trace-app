import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';

type Actor = { id: string; name: string; role: string; sensitive_data_clearance?: boolean };
type Finding = { id: string; title: string; claim: string; observed: string; proposed: string; evidence: string[]; tax_effect: Record<string,string> };
type Report = { counts: Record<string,number>; locators: { resolved:number; total:number }; findings: Finding[]; unresolved_references: unknown[] };
type Trace = {page?:{printed_content:string}|null; ref:string; value: Record<string,unknown>; edges:{source:string;target:string;kind:string}[]};
async function api<T>(url:string, options?:RequestInit):Promise<T> {
  const response = await fetch('/api'+url, options);
  const body = await response.json();
  if (!response.ok) throw new Error(body.detail || 'Request failed');
  return body;
}
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
  useEffect(()=>{api<Actor[]>('/actors').then(setActors).catch(e=>setError(e.message));
    api<Actor>('/session').then(setActor).catch(()=>{});},[]);
  useEffect(()=>{
    setReport(null);setDocs([]);setTrace(null);setSummary(null);
    if(!actor)return;
    setLoading(true);setError('');
    const load = actor.role==='client'
      ? api('/summary').then(setSummary)
      : Promise.all([api<Report>('/audit').then(setReport),api<typeof docs>('/records?kind=document').then(setDocs)]);
    load.catch(e=>setError(e.message)).finally(()=>setLoading(false));
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
  return <div className="app">
    <aside><a className="brand" href="/">m<span>miraflores</span></a><div className="caption">WORKPAPER / 2025</div>
      <h2>Okafor–Lindqvist</h2><p className="muted">Joint return · California / Texas</p>
      <nav>{[['queue','Review queue'],['documents','Evidence library']].map(([key,label])=><button className={tab===key?'selected':''} key={key} onClick={()=>setTab(key)}>{label}<span>↗</span></button>)}</nav>
      <div className="aside-bottom"><span className="dot"/> Local demo<span className="muted">Day 0–1 foundation</span></div>
    </aside>
    <main><header><div className="caption">ENGAGEMENT CL-20417 / ENGINE v3</div><label>Acting as <select aria-label="Demo identity" value={actor?.id||''} onChange={e=>void switchRole(e.target.value)}><option value="" disabled>Choose identity</option>{actors.map(a=><option key={a.id} value={a.id}>{a.name} · {a.role.replaceAll('_',' ')}</option>)}</select></label></header>
      <section className="intro"><div><div className="caption">EVIDENCE BEFORE APPROVAL</div><h1>{actor?.role==='client'?'Your return summary':tab==='queue'?'Make the return provable.':'Every document, accounted for.'}</h1><p className="muted">{tab==='queue'?'Start with the discrepancies. Follow each claim back to its evidence.':'Original page text, extraction details, and links to where each value was used.'}</p></div><span className="pill">Unreviewed</span></section>
      {error&&<div role="alert" className="error">{error}</div>}
      {!actor&&!error&&<div className="empty">Choose a demo identity to open the workspace.</div>}
      {loading&&<p role="status">Loading imported records…</p>}
      {summary!==null&&<section className="panel"><h2>Current engine summary</h2><pre>{JSON.stringify(summary,null,2)}</pre><p>Client approvals and questions arrive in later implementation stories.</p></section>}
      {report&&<><div className="stats">{[['Documents',report.counts.documents],['Extracted values',report.counts.extractions],['Source anchors',`${report.locators.resolved} / ${report.locators.total}`],['Independent findings',report.findings.length]].map(([label,value])=><div key={label}><span>{label}</span><strong>{value}</strong></div>)}</div>
      <div className="section-heading"><h2>{tab==='queue'?'Independent findings':'Document index'}</h2><span className="muted">{tab==='queue'?'Proposals only · no adjustments applied':'74 supplied records'}</span></div>
      {tab==='queue'?<div className="findings">{report.findings.map(f=><article className="finding" key={f.id}><span className="finding-id">{f.id}</span><div><span className="status">Contradicted</span><h3><button className="text-button" onClick={()=>void open('v3:'+f.claim)}>{f.title}</button></h3><div className="muted">{f.claim} · Engine {f.observed} → proposed {f.proposed}</div><div className="evidence">{f.evidence.map(ref=><button key={ref} onClick={()=>void open(ref)}>{ref} ↗</button>)}</div></div><span className="muted">Needs review</span></article>)}</div>:<><input className="search" aria-label="Search documents" placeholder="Find a document by title or ID…" value={query} onChange={e=>setQuery(e.target.value)}/><div className="documents">{docs.filter(d=>(d.ref+' '+d.payload.title).toLowerCase().includes(query.toLowerCase())).map(d=><button key={d.ref} onClick={()=>void open(d.ref)}><strong>{d.ref}</strong><span>{d.payload.title}</span><small>{d.payload.extraction.status.replaceAll('_',' ')}</small></button>)}</div></>}
      <p className="footnote">Independent checks are separate from engine diagnostics. This foundation does not approve or file a return.</p></>}
    </main>
    {trace&&<section className="drawer" aria-label="Evidence detail"><button className="close" aria-label="Close evidence" onClick={()=>setTrace(null)}>×</button><div className="caption">SOURCE & USAGE</div><h2>{trace.ref}</h2>{trace.value.printed_content!==undefined&&<span className="pill">Simulated source document</span>}<Source trace={trace}/><h3>Linked evidence</h3>{trace.edges.map((e,i)=><button className="edge" key={i} onClick={()=>void open(e.source===trace.ref?e.target:e.source)}>{e.kind} · {e.source===trace.ref?e.target:e.source} ↗</button>)}</section>}
  </div>;
}
function Source({trace}:{trace:Trace}) {
  const pageText = trace.page?.printed_content || (typeof trace.value.printed_content==='string'?trace.value.printed_content:null);
  const loc = trace.value.locator as {resolved:boolean;start:number;end:number;quote:string}|undefined;
  const valid = pageText && loc?.resolved && pageText.slice(loc.start,loc.end)===loc.quote;
  if(pageText)return <><p className="caption">SIMULATED SOURCE PAGE</p><div className="source-page">{valid?<>{pageText.slice(0,loc.start)}<mark>{loc.quote}</mark>{pageText.slice(loc.end)}</>:pageText}</div>{loc&&!valid&&<p className="muted">Field location unresolved or masked; manual source anchor needed.</p>}<details><summary>Record details</summary><pre>{JSON.stringify(trace.value,null,2)}</pre></details></>;
  const pages = trace.value.pages as {page:number;printed_content:string}[]|undefined;
  if(pages)return <><p className="caption">SIMULATED SOURCE DOCUMENT</p>{pages.map(page=><section key={page.page}><h3>Page {page.page}</h3><div className="source-page">{page.printed_content}</div></section>)}</>;
  return <pre>{JSON.stringify(trace.value,null,2)}</pre>;
}
createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
