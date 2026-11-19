// Database explorer: browse every table and view in the SQLite database
S.tabs.db='';
VIEW.database=()=>{const tl=D.tables;if(!tl.find(t=>t.name==S.tabs.db))S.tabs.db=tl.find(t=>t.name=='acts')?'acts':tl[0].name;const cur=tl.find(t=>t.name==S.tabs.db);
const h=head('Database','SQLite database built from the CSV files in the data folder. Browse every table and view, then search, sort and export.',`<a class="btn" href="/api/tables/${cur.name}/export.csv" download>${ic('dl')} Download ${esc(cur.name)}.csv</a>`)+
`<div class="g g4">${kpi('Tables and views',tl.length,'<span class="fl0">in act_reactions.db</span>','','')}${kpi('Rows in this table',fmt(cur.rows),`<span class="fl0">${esc(cur.name)}</span>`,'','')}${kpi('Columns',cur.columns.length,`<span class="fl0">${cur.kind}</span>`,'','')}${kpi('Source',esc(cur.source.split('/').pop()),'<span class="fl0">'+(cur.source.startsWith('data/')?'imported CSV':'derived')+'</span>','','')}</div>
<div class="fb"><label class="fl"><span>Table or view</span><select onchange="S.tabs.db=this.value;render()">${tl.map(t=>`<option value="${t.name}" ${t.name==cur.name?'selected':''}>${t.name} (${fmt(t.rows)} rows)</option>`).join('')}</select></label></div>
<div class="g g21"><div class="c" id="dbt"></div><div class="c"><h3>Schema</h3><div class="tw" style="max-height:480px;overflow:auto"><table><thead><tr><th>Column</th><th>Type</th></tr></thead><tbody>${cur.columns.map(c=>`<tr><td>${esc(c.name)}</td><td class="mu">${esc(c.type)}</td></tr>`).join('')}</tbody></table></div></div></div>`;
return{h,a(){const el=$('#dbt');el.innerHTML=Array(6).fill('<div class="sk"></div>').join('');
api.table(cur.name).then(d=>{if(S.tabs.db!=cur.name)return;const id='db_'+cur.name;
mkT(id,{rows:()=>d.rows,hay:r=>Object.values(r).join(' '),id:()=>0,ph:'Search '+cur.name,exp_csv:cur.name+'.csv',csvCols:cur.columns.map(c=>({l:c.name,k:c.name})),
cols:cur.columns.map(c=>({l:esc(c.name),k:c.name,num:/INT|REAL/.test(c.type),r:r=>{const v=r[c.name];return v==null?'<span class="mu">null</span>':typeof v=='number'?(Number.isInteger(v)?v:+v.toFixed(4)):trunc(v,60)}}))});
el.innerHTML=T[id].html();T[id].draw()}).catch(e=>{el.innerHTML=`<div class="em"><b>Could not load table</b>${esc(e.message)}</div>`})}}};
