// 由 scripts/build_cp_static.py 產生，請勿手改。/cp/<slug>/ 與 /<lang>/cp/<slug>/ 共用的「CP 反查 IV」。
(function(){
var el=document.getElementById('rvData'),f=document.getElementById('rvForm'),o=document.getElementById('rvOut');
if(!el||!f||!o)return;
var D=JSON.parse(el.textContent),T=D.t,C=[0.094, 0.16639787, 0.21573247, 0.25572005, 0.29024988, 0.3210876, 0.34921268, 0.3752356, 0.39956728, 0.4225, 0.44310755, 0.4627984, 0.48168495, 0.49985844, 0.51739395, 0.5343543, 0.5507927, 0.5667545, 0.5822789, 0.5974, 0.6121573, 0.6265671, 0.64065295, 0.65443563, 0.667934, 0.6811649, 0.69414365, 0.7068842, 0.7193991, 0.7317, 0.7377695, 0.74378943, 0.74976104, 0.7556855, 0.76156384, 0.76739717, 0.7731865, 0.77893275, 0.784637, 0.7903, 0.7953, 0.8003, 0.8053, 0.8103, 0.8153, 0.8203, 0.8253, 0.8303, 0.8353, 0.8403, 0.8453],F=[],i;
for(i=0;i<C.length;i++){F.push([i+1,C[i]]);if(i+1<C.length)F.push([i+1.5,Math.sqrt((C[i]*C[i]+C[i+1]*C[i+1])/2)]);}
function cp(m,a,d,s){return Math.max(10,Math.floor((D.a+a)*Math.sqrt(D.d+d)*Math.sqrt(D.s+s)*m*m/10));}
function hp(m,s){return Math.max(10,Math.floor((D.s+s)*m));}
function fm(s,v){return s.replace(/\{(\w+)\}/g,function(_,k){return v[k];});}
f.addEventListener('submit',function(ev){ev.preventDefault();
 var c=parseInt(document.getElementById('rvCp').value,10),h=parseInt(document.getElementById('rvHp').value,10),L=parseFloat(document.getElementById('rvLv').value);
 if(!(c>=10)){o.innerHTML='<p class="rv-msg">'+T.need+'</p>';return;}
 var r=[];F.forEach(function(x){if(L&&x[0]!==L)return;for(var a=0;a<16;a++)for(var d=0;d<16;d++)for(var s=0;s<16;s++){if(cp(x[1],a,d,s)!==c)continue;var hh=hp(x[1],s);if(h&&hh!==h)continue;r.push([x[0],a,d,s,hh]);}});
 if(!r.length){o.innerHTML='<p class="rv-msg">'+T.none+'</p>';return;}
 r.sort(function(x,y){return (y[1]+y[2]+y[3])-(x[1]+x[2]+x[3])||x[0]-y[0];});
 var hi=r[0][1]+r[0][2]+r[0][3],lo=r[r.length-1][1]+r[r.length-1][2]+r[r.length-1][3],rows='';
 r.forEach(function(x,k){var t=x[1]+x[2]+x[3];rows+='<tr'+(k>=30?' hidden':'')+(t===45?' class="top"':'')+'><td class="l">'+T.lv+x[0]+'</td><td class="iv">'+x[1]+' / '+x[2]+' / '+x[3]+'</td><td>'+(t/45*100).toFixed(1)+'%</td><td>'+x[4]+'</td></tr>';});
 o.innerHTML='<p class="rv-msg">'+fm(r.length===1&&T.sum1?T.sum1:T.sum,{cp:'<strong>'+c+'</strong>',hp:h?fm(T.hpPart,{hp:'<strong>'+h+'</strong>'}):'',n:'<strong>'+r.length+'</strong>',lo:Math.round(lo/45*100),hi:Math.round(hi/45*100)})+(r.length>1&&!h?T.narrow:'')+'</p>'
  +'<div class="tbl-wrap"><table class="rvt"><thead><tr><th class="l">'+T.thLv+'</th><th>'+T.thIv+'</th><th>IV%</th><th>'+T.thHp+'</th></tr></thead><tbody>'+rows+'</tbody></table></div>'
  +(r.length>30?'<button type="button" class="rv-more">'+fm(T.all,{n:r.length})+'</button>':'');
 var m=o.querySelector('.rv-more');if(m)m.onclick=function(){o.querySelectorAll('tr[hidden]').forEach(function(t){t.hidden=false;});m.remove();};
 if(window.track)window.track('cp_reverse_static',{mon:D.slug,lang:D.lang,hits:r.length});
});
})();
