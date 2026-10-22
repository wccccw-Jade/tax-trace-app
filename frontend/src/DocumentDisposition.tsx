import {useState} from 'react';
import {api} from './api';
import type {Actor,Trace} from './types';
export function DocumentDisposition({trace,actor,onSaved}:{trace:Trace;actor:Actor;onSaved:()=>void}) {
  const [state,setState]=useState(String(trace.value.disposition??'unresolved'));
  const [reason,setReason]=useState(String(trace.value.disposition_reason??''));
  const [original,setOriginal]=useState(String(trace.value.duplicate_of??''));
  const [error,setError]=useState('');const [message,setMessage]=useState('');const [busy,setBusy]=useState(false);
  if(!['preparer','reviewer','partner'].includes(actor.role))return <p className="muted">Disposition: {String(trace.value.disposition??'unresolved')}</p>;
  async function save(){
    setBusy(true);setError('');
    try{
      await api('/workpaper/documents/'+trace.ref,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({expected_revision:trace.revision,disposition:state,reason,duplicate_of:state==='duplicate'?original:null})});
      setMessage('Document disposition saved. Return values change only through a separately approved correction.');onSaved();
    }catch(e){setError((e as Error).message);}finally{setBusy(false);}
  }
  return <form className="workflow-form" onSubmit={e=>{e.preventDefault();void save();}}><h3>Document disposition</h3><label>How this document is used<select value={state} onChange={e=>setState(e.target.value)}>{['unresolved','used','duplicate','superseded','supporting','outside_scope','unextracted_reviewed'].map(s=><option value={s} key={s}>{s.replaceAll('_',' ')}</option>)}</select></label>{state==='duplicate'&&<label>Original document ID<input required value={original} placeholder="For example D28" onChange={e=>setOriginal(e.target.value)}/></label>}<label>Reason<textarea required value={reason} onChange={e=>setReason(e.target.value)} placeholder="Explain the document relationship."/></label><button disabled={busy}>{busy?'Saving…':'Save disposition'}</button>{message&&<p role="status" className="success">{message}</p>}{error&&<p role="alert" className="error">{error}</p>}</form>;
}
