const tabsH=(key,items)=>`<div class="tabs" role="tablist">${items.map(([k,l])=>`<button role="tab" class="${S.tabs[key]==k?'on':''}" onclick="S.tabs['${key}']='${k}';render()">${l}</button>`).join('')}</div>`;
const head=(t,s,x='')=>`<div class="ph"><div><h1>${t}</h1><div class="sub">${s}</div></div><div>${x}</div></div>`;
const trunc=(s,n=90)=>`<div class="tt" title="${esc(s)}">${esc(String(s).length>n?String(s).slice(0,n)+'…':s)}</div>`;
const dlt=(a,b,pp)=>{if(S.f.y1==YEARS[0]||b==null||a==null||(!pp&&!b))return`<span class="fl0">No prior cohort</span>`;const v=pp?(a-b):(a-b)/b,up=v>=0;return`<span class="${up?'up':'dn'}">${ic(up?'up':'dn')}${pp?(up?'+':'−')+Math.abs(v*100).toFixed(1)+' pts':(up?'+':'−')+Math.abs(v*100).toFixed(1)+'%'}</span><span class="fl0">vs ${S.f.y1-1} acts</span>`};
const kpi=(l,v,d,go_,tip)=>`<button class="k" title="${tip}" onclick="${go_}"><div class="l">${l}</div><div class="v">${v}</div><div class="d">${d}</div></button>`;
const onPt=fn=>({onClick:(e,els)=>{if(els.length)fn(els[0].index)},onHover:(e,els)=>{e.native.target.style.cursor=els.length?'pointer':'default'}});
