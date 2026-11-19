// Thin client for the backend REST API (see backend/server.py)
const api={
  async j(url,opt={}){const r=await fetch(url,{headers:{'Content-Type':'application/json'},...opt});
    if(!r.ok){let m=r.statusText;try{m=(await r.json()).error||m}catch(e){}throw new Error(m)}return r.json()},
  bootstrap(){return api.j('/api/bootstrap')},
  saveAct(a){return api.j('/api/acts',{method:'POST',body:JSON.stringify(a)})},
  updateAct(id,f){return api.j('/api/acts/'+encodeURIComponent(id),{method:'PUT',body:JSON.stringify(f)})},
  removeAct(id){return api.j('/api/acts/'+encodeURIComponent(id),{method:'DELETE'})},
  addScen(s){return api.j('/api/scenarios',{method:'POST',body:JSON.stringify(s)})},
  delScen(id){return api.j('/api/scenarios/'+id,{method:'DELETE'})},
  tables(){return api.j('/api/tables')},
  table(name){return api.j('/api/tables/'+encodeURIComponent(name)+'?limit=20000')},
  reset(){return api.j('/api/reset',{method:'POST'})}
};
