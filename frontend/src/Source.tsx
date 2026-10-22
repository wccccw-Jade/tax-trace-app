import {useEffect, useRef, useState} from 'react';
import {api} from './api';
import type {Actor,Extraction,Locator,Trace} from './types';

export function Source({trace,actor,onOpen,onSaved}:{trace:Trace;actor:Actor|null;onOpen:(ref:string)=>void;onSaved:()=>void}) {
  const textRef=useRef<HTMLDivElement>(null);
  const [selection,setSelection]=useState<{start:number;end:number;quote:string}|null>(null);
  const [saving,setSaving]=useState(false);
  const [message,setMessage]=useState('');
  const [error,setError]=useState('');
  const [fields,setFields]=useState<Extraction[]>([]);
  const [filter,setFilter]=useState('');
  const [unresolved,setUnresolved]=useState(false);
  const [limit,setLimit]=useState(40);
  const pageText=trace.page?.printed_content ?? (typeof trace.value.printed_content==='string'?trace.value.printed_content:null);
  const loc=trace.value.locator as Locator|undefined;
  const valid=pageText!==null&&loc?.resolved&&pageText.slice(loc.start,loc.end)===loc.quote;
  const canAnchor=trace.kind==='extraction'&&actor&&['preparer','reviewer','partner'].includes(actor.role)&&pageText&&!pageText.includes('[masked]');
  const docId=trace.kind==='document'?trace.ref:trace.kind==='page'?String(trace.value.document_id):null;
  useEffect(()=>{
    if(!docId)return;
    let live=true;
    api<Extraction[]>('/records?kind=extraction&document_id='+encodeURIComponent(docId))
      .then(rows=>{if(live)setFields(trace.kind==='page'?rows.filter(r=>r.payload.page===trace.value.page):rows);})
      .catch(e=>{if(live)setError(e.message);});
    return ()=>{live=false;};
  },[docId,trace.ref]);
  function capture(){
    const selected=window.getSelection();
    const node=textRef.current;
    if(!selected||selected.rangeCount===0||selected.isCollapsed||!node){setSelection(null);return;}
    const range=selected.getRangeAt(0);
    if(!node.contains(range.startContainer)||!node.contains(range.endContainer)){setSelection(null);return;}
    const prefix=range.cloneRange();prefix.selectNodeContents(node);prefix.setEnd(range.startContainer,range.startOffset);
    const start=Array.from(prefix.toString()).length;
    const quote=range.toString();
    setSelection({start,end:start+Array.from(quote).length,quote});setMessage('');
  }
  async function save(){
    if(!selection||trace.revision===null)return;
    setSaving(true);setError('');
    try{
      await api('/locators/'+encodeURIComponent(trace.ref),{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({expected_revision:trace.revision,start:selection.start,end:selection.end})});
      setSelection(null);setMessage('Source anchor saved. This locates the evidence; it does not verify the value.');onSaved();
    }catch(e){setError((e as Error).message);}finally{setSaving(false);}
  }
  const visible=fields.filter(f=>(!unresolved||!f.payload.locator.resolved)&&(f.ref+' '+f.payload.label+' '+f.payload.field).toLowerCase().includes(filter.toLowerCase()));
  const pages=trace.value.pages as {page:number;printed_content:string}[]|undefined;
  return <>
    {trace.kind==='extraction'&&<div className="field-heading"><strong>{String(trace.value.label)}</strong><p>Extracted: {String(trace.value.value)} · page {String(trace.value.page)}</p></div>}
    {pageText!==null&&<><p className="caption">SIMULATED SOURCE PAGE</p><div className="source-page" ref={textRef} onMouseUp={capture} onKeyUp={capture} tabIndex={0} aria-label="Source page text">{valid?<>{pageText.slice(0,loc.start)}<mark>{loc.quote}</mark>{pageText.slice(loc.end)}</>:pageText}</div>
      {loc&&<p className="muted">{valid?`Anchor: ${loc.layer}${loc.actor?' · '+loc.actor:''}${loc.at?' · '+new Date(loc.at).toLocaleString():''}`:'Source anchor unresolved or masked.'}</p>}
      {canAnchor&&<div className="anchor-editor"><strong>Set source anchor</strong><p>Select the exact field in the page above, then save. Existing anchors can be replaced.</p>{selection&&<blockquote>{selection.quote}</blockquote>}<button disabled={!selection||saving} onMouseDown={e=>e.preventDefault()} onClick={()=>void save()}>{saving?'Saving…':'Save source anchor'}</button></div>}
      {message&&<p className="success" role="status">{message}</p>}
    </>}
    {pages&&<><p className="caption">SIMULATED SOURCE DOCUMENT</p>{pages.map(p=><section key={p.page}><h3><button className="text-button" onClick={()=>onOpen(`doc:${trace.ref}#page${p.page}`)}>Page {p.page} ↗</button></h3><div className="source-page">{p.printed_content}</div></section>)}</>}
    {docId&&<section className="field-list"><h3>Extracted fields ({fields.length})</h3><input aria-label="Search source fields" className="search" placeholder="Find a field…" value={filter} onChange={e=>{setFilter(e.target.value);setLimit(40);}}/><label><input type="checkbox" checked={unresolved} onChange={e=>{setUnresolved(e.target.checked);setLimit(40);}}/> Unresolved anchors only</label>{visible.slice(0,limit).map(f=><button className="edge" key={f.ref} onClick={()=>onOpen(f.ref)}><strong>{f.payload.label||f.payload.field}</strong><span>{f.ref} · page {f.payload.page} · {String(f.payload.value)}</span><small>{f.payload.locator.resolved?'Located':'Needs source anchor'}</small></button>)}{!visible.length&&<p className="muted">No fields match this filter.</p>}{visible.length>limit&&<button className="load-more" onClick={()=>setLimit(limit+40)}>Show more fields ({visible.length-limit} remaining)</button>}</section>}
    {!pageText&&!pages&&<pre>{JSON.stringify(trace.value,null,2)}</pre>}
    {error&&<div role="alert" className="error">{error}</div>}
    {pageText&&<details><summary>Record details</summary><pre>{JSON.stringify(trace.value,null,2)}</pre></details>}
  </>;
}
