export async function api<T>(url:string, options?:RequestInit):Promise<T> {
  const response = await fetch('/api'+url, options);
  const body = await response.json();
  if (!response.ok) throw new Error(typeof body.detail==='string'?body.detail:Array.isArray(body.detail)?body.detail.map((e:{msg:string})=>e.msg).join('; '):'Request failed');
  return body;
}
