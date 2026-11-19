// Loads data from the API first, then the application scripts in dependency order.
const FILES=['state','components','core','common','overview','acts','analysis','models','simulator','database','app'];
function loadSeq(i=0){return i>=FILES.length?Promise.resolve():new Promise((ok,fail)=>{const s=document.createElement('script');s.src='js/'+FILES[i]+'.js';s.onload=ok;s.onerror=()=>fail(new Error('Could not load js/'+FILES[i]+'.js'));document.body.append(s)}).then(()=>loadSeq(i+1))}
api.bootstrap().then(d=>{window.D=d;return loadSeq()}).catch(e=>{document.getElementById('pg').innerHTML='<div class="em"><b>Could not load the dashboard</b>'+String(e.message).replace(/</g,'&lt;')+'<br>Start the backend with: python3 backend/server.py</div>'});
