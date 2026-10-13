/* SECOP 2.6: coverage complement -- official awards and bidders are NOT signed contracts.
   The base contract search remains authoritative for electronically published contracts. */
(function(root){
'use strict';
const C=root.SecopWeb || (typeof require === 'function' ? require('./app.js') : null);
if(!C) return;
const PROCESS='p6dx-8zbt',BIDDERS='hgi6-6wh3';
const norm=C.norm, valid=C.valid, txt=C.txt;
const uniq=x=>[...new Set(x.filter(Boolean))];
function chunks(xs,n=18){const all=[];for(let i=0;i<xs.length;i+=n)all.push(xs.slice(i,i+n));return all;}
function groupLabel(text){return /\b(CONSORCIO|UNION TEMPORAL|U\s*T|PROMESA DE SOCIEDAD FUTURA)\b/.test(norm(text||''));}
function awardReported(row){
 const v=norm(row.adjudicado||'');
 return ['SI','SÍ','TRUE','YES','1'].includes(v);
}
function officialLink(value){const url=(value&&typeof value==='object')?value.url:value;return C.safeOfficialUrl(url)||'';}
function evidenceLink(row,source){
 const u=officialLink(row.urlproceso||row.url_proceso);if(u)return u;
 const field=source===PROCESS?'id_del_proceso':'id_procedimiento';
 const code=txt(row[field]);
 if(!/^CO1\.[A-Z]+\.\d+$/.test(code))return '';
 return `https://www.datos.gov.co/resource/${source}.json?${field}=${encodeURIComponent(code)}`;
}
function codesFromAccounts(id,accounts){return uniq(accounts.filter(x=>C.idMatch(id,x.nit)).map(x=>txt(x.codigo)).filter(valid));}
function sourceStatus(rows,job){return {source:job,status:rows.length?'records':'none',count:rows.length};}
function contractIndex(core){
 const all=[...(core.individual||[]),...(core.plural||[])].filter(x=>x.platform==='II');
 const map=new Map;
 for(const contract of all){const r=contract.sourceRow||{};const key=txt(r.proceso_de_compra),code=txt(r.codigo_proveedor);
  if(!key||!code||!/^CO1\.BDOS\.\d+$/.test(key))continue;
  const k=key+'|'+code;if(!map.has(k))map.set(k,[]);map.get(k).push(contract);
 }
 return map;
}
function affiliation(id,record,groups,individualCodes,{source}){
 const code=txt(source===PROCESS?record.codigoproveedor:record.codigo_proveedor);
 const memberNit=txt(source===PROCESS?record.nit_del_proveedor_adjudicado:record.nit_proveedor);
 const supplier=txt(source===PROCESS?record.nombre_del_proveedor:record.proveedor);
 if(code && groups.has(code))return {kind:'plural',route:'Código exacto de grupo con integrante registrado en SECOP II',group:groups.get(code),code,nit:memberNit};
 if(C.idMatch(id,memberNit)){
  if(groupLabel(supplier))return {kind:'uncertain',route:'NIT individual publicado para un posible grupo plural; falta composición',code,nit:memberNit};
  return {kind:'individual',route:'Documento del proveedor adjudicado o proponente coincide con la identificación',code,nit:memberNit};
 }
 if(code && individualCodes.includes(code)){
  if(groupLabel(supplier))return {kind:'uncertain',route:'Cuenta de proveedor asociada a denominación plural, no acreditada',code,nit:memberNit};
  return {kind:'individual',route:'Código exacto de la cuenta individual SECOP II',code,nit:memberNit};
 }
 return null;
}
async function readSource(p,ds,identity,individualCodes,groupCodes,which){
 const out=[];
 const docField=ds===PROCESS?'nit_del_proveedor_adjudicado':'nit_proveedor';
 const codeField=ds===PROCESS?'codigoproveedor':'codigo_proveedor';
 // Separate NIT and provider-code queries to avoid one large OR query on a national dataset.
 out.push(...await p.filter(ds,[[docField,identity.variants]],`SECOP II: ${which} por NIT`,{limit:1200}));
 const partitions=chunks(uniq([...individualCodes,...groupCodes]));
 // Limit concurrency to protect Datos Abiertos and improve browser responsiveness.
 for(let i=0;i<partitions.length;i+=3){
  const batchResults=await Promise.all(partitions.slice(i,i+3).map(piece=>
   p.filter(ds,[[codeField,piece]],`SECOP II: ${which} por códigos vinculados`,{limit:1000})));
  for(const part of batchResults)out.push(...part);
 }
 return out;
}
function makeAward(row,identity,affiliation,linkedIndex){
 const pid=txt(row.id_del_proceso),portfolio=txt(row.id_del_portafolio),awardId=txt(row.id_adjudicacion);
 const supplier=txt(row.nombre_del_proveedor),code=affiliation.code;
 const linked=(portfolio&&code)?(linkedIndex.get(portfolio+'|'+code)||[]):[];
 return {
  key:[pid||portfolio||txt(row.referencia_del_proceso),awardId||'no-id',code||affiliation.nit].join('|'),
  platform:'II',source:PROCESS,kind:affiliation.kind,reason:affiliation.route,
  group:affiliation.group?.name||'',groupCode:affiliation.group?.code||'',
  supplier:supplier||affiliation.group?.name||'No informado',providerNit:txt(row.nit_del_proveedor_adjudicado),providerCode:code,
  entity:txt(row.entidad),entityNit:txt(row.nit_entidad),
  processId:pid,portfolio,reference:txt(row.referencia_del_proceso),awardId,
  awardDate:txt(row.fecha_adjudicacion),value:txt(row.valor_total_adjudicacion),
  modality:txt(row.modalidad_de_contratacion),state:txt(row.estado_del_procedimiento),
  awarded:awardReported(row),statusNote:awardReported(row)?'Adjudicación reportada; no acredita por sí sola un contrato firmado.':'Vinculación al proceso; adjudicación no acreditada en este registro.',
  electronicContracts:uniq(linked.map(c=>c.contractId)),
  url:evidenceLink(row,PROCESS),evidenceUrl:officialLink(row.urlproceso),
  sourceRow:row
 };
}
function makeBid(row,affiliation){return {
 key:[txt(row.id_procedimiento),affiliation.code||affiliation.nit].join('|'),
 platform:'II',source:BIDDERS,kind:affiliation.kind,reason:affiliation.route,
 group:affiliation.group?.name||'',groupCode:affiliation.group?.code||'',
 supplier:txt(row.proveedor),providerNit:txt(row.nit_proveedor),providerCode:affiliation.code,
 processId:txt(row.id_procedimiento),reference:txt(row.id_procedimiento),
 entity:txt(row.entidad_compradora),entityNit:txt(row.nit_entidad),
 procedureName:txt(row.nombre_procedimiento),published:txt(row.fecha_publicaci_n),
 url:evidenceLink(row,BIDDERS),
 statusNote:'Proponente registrado en procedimiento SECOP II. No acredita adjudicación ni contrato.',
 sourceRow:row
 };}
async function lookup(identity,core,accounts,transport,opts={}){
 const excluded=opts.platform==='i';
 const result={at:new Date().toISOString(),sourceIds:[PROCESS,BIDDERS],awards:[],otherProcesses:[],bids:[],uncertain:[],linkedElectronic:[],scope:'Solo SECOP II: adjudicaciones y proponentes registrados. Un proceso o adjudicación NO se contabiliza como contrato celebrado. Registros sujetos a límites y errores de fuente.',skipped:excluded};
 if(excluded)return result;
 const groups=new Map((core.groups||[]).filter(g=>valid(g.code)).map(g=>[txt(g.code),g]));
 const groupCodes=[...groups.keys()];
 const individualCodes=codesFromAccounts(identity,accounts||[]);
 const contracts=contractIndex(core);
 const pRows=await readSource(transport,PROCESS,identity,individualCodes,groupCodes,'procesos y adjudicaciones');
 const pSeen=new Set;
 const linked=new Set;
 for(const row of pRows){
  const a=affiliation(identity,row,groups,individualCodes,{source:PROCESS});if(!a)continue;
  const o=makeAward(row,identity,a,contracts);
  if(pSeen.has(o.key))continue;pSeen.add(o.key);
  if(a.kind==='uncertain'){result.uncertain.push({...o,reason:o.reason+'; no atribuido al NIT'});continue;}
  if(o.electronicContracts.length){for(const c of o.electronicContracts)linked.add(c);result.linkedElectronic.push(o);continue;}
  if(o.awarded)result.awards.push(o);else result.otherProcesses.push(o);
 }
 const bRows=await readSource(transport,BIDDERS,identity,individualCodes,groupCodes,'proponentes por proceso');
 const bids=new Set;
 const observed=new Set([...result.awards,...result.otherProcesses,...result.linkedElectronic].map(x=>x.processId+'|'+x.providerCode));
 for(const row of bRows){
  const a=affiliation(identity,row,groups,individualCodes,{source:BIDDERS});if(!a)continue;
  const o=makeBid(row,a);
  if(bids.has(o.key))continue;bids.add(o.key);
  if(a.kind==='uncertain'){result.uncertain.push({...o,reason:o.reason+'; no atribuido al NIT'});continue;}
  if(observed.has(o.processId+'|'+o.providerCode))continue;
  result.bids.push(o);
 }
 result.awards.sort((a,b)=>b.awardDate.localeCompare(a.awardDate));
 result.bids.sort((a,b)=>b.published.localeCompare(a.published));
 return result;
}
const API={lookup,awardReported,affiliation,makeAward,makeBid,officialLink,evidenceLink,contractIndex,groupLabel,PROCESS,BIDDERS};
root.SecopExtended26=API;
})(typeof window==='undefined'?globalThis:window);

/* Browser presentation; all new material is strictly below the contracted-results sections. */
(function(){'use strict';
 if(typeof document==='undefined'||!window.SecopWeb||!window.SecopExtended26)return;
 const C=window.SecopWeb,$=id=>document.getElementById(id);
 function esc(v){return C.attr(v==null?'':String(v));}
 function human(v){return C.valid(v)?esc(v):'No publicado';}
 function link(url,label){const x=C.safeOfficialUrl(url);return x?`<a href="${esc(x)}" target="_blank" rel="noopener noreferrer">${esc(label)} &nearr;</a>`:''}
 function awardCard(r){return `<article class="record"><div class="top"><div><span class="tag blue">SECOP II</span><span class="tag">${r.kind==='plural'?'Estructura plural':'Individual'}</span><h3>${human(r.supplier)}</h3><div class="muted">${human(r.reference||r.processId)} &middot; ${human(r.entity)}</div></div></div><div class="detail-grid"><div><span>Resultado publicado</span><strong>Adjudicación, contrato por verificar</strong></div><div><span>Fecha de adjudicación</span><strong>${human(r.awardDate?.slice(0,10))}</strong></div><div><span>Valor adjudicado</span><strong>${human(r.value)}</strong></div></div><p class="micro">${esc(r.reason)}. ${esc(r.statusNote)}</p><div class="links">${link(r.url,'Consultar proceso oficial')}${r.groupCode?link(C.groupUrl(r.groupCode),'Composición del grupo'):''}</div></article>`}
 function bidCard(r){return `<article class="record"><span class="tag">Proponente SECOP II</span><h3>${human(r.supplier)}</h3><div class="muted">${human(r.processId)} &middot; ${human(r.entity)}</div><p class="micro">${human(r.procedureName)}. ${esc(r.statusNote)} ${esc(r.reason)}</p><div class="links">${link(r.url,'Ver registro de proponentes')}${r.groupCode?link(C.groupUrl(r.groupCode),'Composición de la estructura'):''}</div></article>`}
 function show(name,list,fun,empty){const h=$(name);if(h)h.innerHTML=list.length?list.map(fun).join(''):`<div class="empty">${esc(empty)}</div>`;const n=$(name+'Count');if(n)n.textContent=list.length;}
 function render(data){show('extended26Awards',data.awards,awardCard,'Sin adjudicaciones adicionales asociadas al NIT o a sus estructuras en esta consulta.');show('extended26Bids',data.bids,bidCard,'Sin otros registros de proponentes recuperados en esta consulta.');
 const totals=$('extended26Status');if(totals)totals.textContent=data.skipped?'No se consultaron procesos SECOP II porque se eligió solo SECOP I.':`${data.awards.length} adjudicaciones sin contrato electrónico enlazado en esta consulta, ${data.bids.length} participaciones en procedimientos no duplicadas, ${data.linkedElectronic.length} adjudicaciones vinculadas a contratos ya mostrados. ${data.uncertain.length} registros ambiguos excluidos de la atribución. Ver incidencias de fuentes.`;
 }
 const section=document.createElement('section');section.id='extended26Section';section.className='panel';section.innerHTML=`<div class="section-label">04A / Ampliación de cobertura SECOP II</div><h2>Adjudicaciones y propuestas sin contrato electrónico acreditado</h2><p class="hint">Fuentes oficiales: procesos adjudicados (p6dx-8zbt) y proponentes por procedimiento (hgi6-6wh3). No se incorporan a la suma de contratos celebrados ni se califican como contratos en ejecución. Las relaciones plurales requieren coincidencia exacta de código de grupo con integrante registrado.</p><div id="extended26Status" class="context">Pendiente de consulta.</div><div class="bucket-grid"><section class="bucket"><header><strong>Adjudicaciones por verificar</strong><span class="bucket-count" id="extended26AwardsCount">0</span></header><div id="extended26Awards" class="results"><div class="empty">Ingrese un NIT.</div></div></section><section class="bucket"><header><strong>Otras participaciones en procesos</strong><span class="bucket-count" id="extended26BidsCount">0</span></header><div id="extended26Bids" class="results"><div class="empty">Ingrese un NIT.</div></div></section></div>`;
 const next=$('candidateSection')||$('trace');if(next)next.insertAdjacentElement('beforebegin',section);
 window.SecopCoverage26={render,reset(){show('extended26Awards',[],awardCard,'Esperando consulta.');show('extended26Bids',[],bidCard,'Esperando consulta.');$('extended26Status').textContent='Consultando fuentes nuevas...';}};
})();
