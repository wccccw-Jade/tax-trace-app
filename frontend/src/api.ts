export async function api<T>(url:string, options?:RequestInit):Promise<T> {
  const response = await fetch('/api'+url, options);
  const body = await response.json();
  if (!response.ok) throw new Error(typeof body.detail==='string'?body.detail:typeof body.detail?.message==='string'?body.detail.message+(body.detail.changed_by?' Saved by '+body.detail.changed_by+' (revision '+body.detail.revision+').':'')+(body.detail.current?.note?' Latest note: '+body.detail.current.note:''):Array.isArray(body.detail)?body.detail.map((e:{msg:string})=>e.msg).join('; '):'Request failed');
  return body;
}
