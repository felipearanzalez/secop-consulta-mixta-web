/* SECOP 2.3 — presentación contractual priorizada y verificación amigable.
   Extensión no intrusiva sobre SecopWeb 2.2; no realiza cargas documentales. */
(function(){'use strict';
 if(typeof document==='undefined'||!window.SecopWeb)return;
 const C=window.SecopWeb,$=id=>document.getElementById(id);
 const safe=s=>C.attr(s==null?'':String(s));
 const display=v=>C.valid(v)?safe(v):'No publicado';
 const norm=C.norm;
 const date=v=>{const s=String(v||'');const m=s.match(/^(\d{4})-(\d{2})-(\d{2})/);if(!m)return null;const d=new Date(m[1]+'-'+m[2]+'-'+m[3]+'T12:00:00Z');return Number.isFinite(d.getTime())&&d.toISOString().slice(0,10)===m[0]?d:null};
 const day=v=>date(v)?date(v).toISOString().slice(0,10):'No registrada';
 const currentDay=()=>new Date().toISOString().slice(0,10);
 const link=(url,label)=>{const u=C.safeOfficialUrl(url);return u?`<a href="${safe(u)}" target="_blank" rel="noopener noreferrer">${safe(label)} ↗</a>`:''};
 function isContractI(r){
  const d=r.sourceRow||r;
  const n=String(d.numero_de_contrato||'').trim(),hasNumber=C.valid(n)&&!/^(SIN|NO)\b/i.test(n);
  const signed=date(d.fecha_de_firma_del_contrato);
  const year=String(d.anno_firma_contrato||'').trim(),state=norm(d.estado_del_proceso);
  return Boolean(signed || (hasNumber && (/^(19|20)\d{2}$/.test(year)||/CELEBRAD|LIQUIDAD|TERMINAD/.test(state)||date(d.fecha_ini_ejec_contrato))));
 }
 function isContractII(r){const d=r.sourceRow||r,st=norm(d.estado_contrato||r.state);return Boolean(C.valid(d.id_contrato||r.contractId)&& !/BORRADOR|EN APROBACION|EN FIRMA|PENDIENTE DE FIRMA/.test(st));}
 function executionStatus(r,today=currentDay()){
  const s=norm(r.state);
  if(r.platform==='II')return /^EN EJECUCION$|^EN EJECUCION CONTRACTUAL$|^IN EXECUTION$/.test(s)?{level:'reported',text:'En ejecución según estado SECOP II'}:{level:'other',text:'No se acredita ejecución actual con el estado publicado'};
  if(/SUSPEND|TERMIN|LIQUID|CERRAD|ANULAD|CANCELAD/.test(s))return {level:'other',text:'Revisar estado; no se presume ejecución'};
  const start=date(r.start),end=date(r.end),now=date(today);
  if(start&&end&&now&&start<=now&&now<=end)return {level:'possible',text:'Posible ejecución por fechas SECOP I; verificar actas y suspensiones'};
  return {level:'other',text:'Ejecución no acreditada por las fechas disponibles'};
 }
 const unique=xs=>[...new Map(xs.map(x=>[x.key||x.code||x.name+'|'+x.source,x])).values()];
 function summarize(core,indII=[],candidateContracts=[],candidateI=[]){
  const contracts=[],execution=[],individualPart=[],pluralPart=[];
  const accepted=[...core.individual.map(r=>({...r,modality:'individual'})),...core.plural.map(r=>({...r,modality:'plural'}))];
  for(const r of unique(accepted)){
   const exists=r.platform==='II'?isContractII(r):isContractI(r);
   if(!exists){(r.modality==='individual'?individualPart:pluralPart).push({...r,participationReason:'Registro del proceso sin evidencia suficiente de contrato firmado'});continue}
   const status=executionStatus(r);
   (status.level==='other'?contracts:execution).push({...r,execution:status});
  }
  for(const g of core.groups)pluralPart.push({...g,platform:'II',type:'group'});
  for(const p of indII)individualPart.push({...p,platform:'II',type:'account'});
  const candidates=unique([...candidateContracts,...candidateI]);
  return {execution:unique(execution),contracts:unique(contracts),individualParticipation:unique(individualPart),pluralParticipation:unique(pluralPart),candidates,tasks:core.tasks};
 }
 const buckets=[['I','individual'],['I','plural'],['II','individual'],['II','plural']];
 const names={I:'SECOP I',II:'SECOP II',individual:'Individual',plural:'Plural'};
 function sectionBuckets(prefix,items,renderer,empty){
  for(const [platform,modality] of buckets){const place=$(prefix+platform+modality);if(!place)continue;
   const some=items.filter(x=>x.platform===platform&&x.modality===modality);
   place.innerHTML=some.length?some.map(renderer).join(''):`<div class="empty">${empty}</div>`;
   const number=$(prefix+platform+modality+'Count');if(number)number.textContent=some.length;
  }
 }
 const objectText=v=>C.valid(v)?safe(v):'Objeto no publicado';
 function contractCard(r){
  const e=r.execution||executionStatus(r);
  const badge=r.participationReason?'<span class="tag warn">Proceso sin firma acreditada</span>':e.level==='reported'?'<span class="tag strong">Ejecución reportada</span>':e.level==='possible'?'<span class="tag warn">Posible ejecución</span>':'<span class="tag">Contrato registrado</span>';
  return `<article class="record"><div class="top"><div>${badge}<h3>${display(r.contractor||r.group)}</h3><div class="muted">${display(r.reference)} · ${display(r.entity)}</div></div><div class="role">${safe(r.route)}</div></div><div class="detail-grid"><div><span>Estado publicado</span><strong>${display(r.state)}</strong></div><div><span>Inicio / fin publicados</span><strong>${safe(day(r.start))} / ${safe(day(r.end))}</strong></div><div><span>Identificación del contratista</span><strong>${display(r.contractorId)}</strong></div></div><div class="context ${e.level==='possible'||r.participationReason?'warning':''}">${safe(r.participationReason||e.text)}</div><details><summary>Objeto y fundamento de la vinculación</summary><p class="secondary">${objectText(r.object)}</p><p class="muted">Fuente: ${safe(r.source)}. ${safe(r.route)}. Una fecha proyectada no incorpora necesariamente suspensiones o modificaciones.</p></details><div class="links">${link(r.url,'Ver expediente contractual en SECOP')}${r.groupCode?`<a href="#gruposRegistrados">Ver composición del grupo en esta página ↓</a>`:''}</div></article>`;
 }
 function compositionHTML(composition){
  const members=composition||[];
  return members.length?`<div class="members">${members.map(m=>`<div class="member"><strong>${display(m.nombre_participante)}</strong><small>Documento: ${display(m.nit_participante)} · Participación ${display(m.participacion)} %</small></div>`).join('')}</div>`:'<div class="muted">No fue posible recuperar todos los integrantes.</div>';
 }
 function groupCard(g){
  return `<article class="record"><div class="top"><div><span class="tag strong">Pertenencia registrada SECOP II</span><h3>${display(g.name)}</h3><div class="muted">Código ${display(g.code)} · NIT grupo ${display(g.nit)}</div></div><div class="role">Participación: <strong>${display(g.percent)} %</strong></div></div><div class="detail-grid"><div><span>Representante</span><strong>${display(g.rep)}</strong></div><div><span>Documento representante</span><strong>${display(g.repId)}</strong></div><div><span>Estado de la cuenta</span><strong>${safe(C.matchUrlStatus(g.active))}</strong></div></div><details open class="composition"><summary>Composición oficial del grupo — leer aquí</summary>${compositionHTML(g.composition)}</details><div class="context">El registro de la cuenta del grupo acredita información declarada en SECOP II; no prueba por sí solo adjudicación, creación por el consultado ni ejecución de contrato.</div><div class="links">${link('https://community.secop.gov.co/Directory/CompanyProfiles/Network/Index','Directorio de proveedores SECOP II')}</div><details class="technical"><summary>Fuente oficial original y código de consulta</summary><p>Conjunto: Grupos de proveedores SECOP II. Código: <strong>${display(g.code)}</strong>.</p>${link(C.groupUrl(g.code),'Datos originales en formato JSON')}</details></article>`;
 }
 function accountCard(a){return `<article class="record"><span class="tag blue">Proveedor registrado en SECOP II</span><h3>${display(a.nombre||a.nombre_completo||a.nombre_proveedor||a.nit)}</h3><div class="detail-grid"><div><span>Identificación</span><strong>${display(a.nit)}</strong></div><div><span>Código del proveedor</span><strong>${display(a.codigo)}</strong></div><div><span>Alcance</span><strong>Cuenta registrada, no contrato</strong></div></div><div class="links">${link('https://www.datos.gov.co/d/qmzu-gj57','Consultar conjunto oficial')}</div></article>`}
 function candidateCard(c){
  const r=c.contract;const g=c.groupRecord;
  if(!r)return'';
  const score=c.score!=null?`<span class="tag">Similitud nominal ${Math.round(c.score*100)} %</span>`:'';
  return `<article class="record"><div class="top"><div><span class="tag warn">Coincidencia no atribuida</span>${score}<h3>${display(c.name||r.contractor)}</h3><div class="muted">Contrato ${display(r.reference)} · ${display(r.entity)} · SECOP ${safe(r.platform)}</div></div><div class="role">${safe(c.rule)}</div></div><div class="detail-grid"><div><span>Estado publicado del contrato</span><strong>${display(r.state)}</strong></div><div><span>Identificación del contratista</span><strong>${display(r.contractorId)}</strong></div><div><span>Representante registrado</span><strong>${display(c.rep)}</strong></div></div><div class="context warning"><strong>Motivo:</strong> ${safe(c.rule)}. ${c.anchor?'Referencia de comparación: '+safe(c.anchor)+'. ':''}El contrato existe en la fuente indicada, pero la pertenencia del NIT consultado no está demostrada.</div>${g?`<details class="composition"><summary>Ver aquí integrantes registrados del grupo candidato</summary>${compositionHTML(g.composition)}</details>`:''}<details><summary>Objeto del contrato</summary><p class="secondary">${objectText(r.object)}</p></details><div class="links">${link(r.url,'Ver contrato o expediente en SECOP')}</div>${c.code?`<details class="technical"><summary>Datos oficiales de la cuenta plural</summary><p>Código del grupo: ${display(c.code)}.</p>${link(C.groupUrl(c.code),'Fuente original JSON')}</details>`:''}</article>`;
 }
 const show=(id,rows,render,empty)=>{const target=$(id);if(target)target.innerHTML=rows.length?rows.map(render).join(''):`<div class="empty">${empty}</div>`};
 function reportUI(s,core,stage){
  const e=s.execution.map(r=>({...r})),other=s.contracts.map(r=>({...r}));
  sectionBuckets('execution',e,contractCard,'Sin registros de ejecución reportada o posible en esta categoría.');
  sectionBuckets('contract',other,contractCard,'Sin otros contratos identificados en esta categoría.');
  show('participationIndividualI',s.individualParticipation.filter(x=>x.platform==='I'),contractCard,'No se localizaron procesos individuales adicionales sin contrato acreditado.');
  show('participationIndividualII',s.individualParticipation.filter(x=>x.platform==='II'),accountCard,'No se recuperó cuenta individual de proveedor.');
  show('participationPluralI',s.pluralParticipation.filter(x=>x.platform==='I'),contractCard,'Sin reportes adicionales de procesos plurales sin contrato acreditado.');
  show('participationPluralII',s.pluralParticipation.filter(x=>x.platform==='II'),groupCard,'No se localizaron estructuras plurales registradas.');
  sectionBuckets('candidate',s.candidates,candidateCard,'Sin candidatos con contrato comprobable en esta categoría.');
  $('countExecution').textContent=s.execution.length;$('countContracts').textContent=s.contracts.length;
  $('countParticipations').textContent=s.individualParticipation.length+s.pluralParticipation.length;$('countCandidates').textContent=s.candidates.length;
  const tasks=core.tasks||[];
  $('auditResults').innerHTML=tasks.length?tasks.map(t=>`<div class="audit-item"><span class="audit-status ${safe(t.status)}">${t.status==='ok'?'Completada':t.status==='partial'?'Parcial':'Falló'}</span><strong>${safe(t.label)}</strong><span class="muted"> · ${safe(t.source)} · ${Number(t.count)||0} registros</span>${t.truncated?'<div class="context warning">Límite de resultados alcanzado; la cobertura es incompleta.</div>':''}${t.error?`<div class="context warning">${safe(t.error)}</div>`:''}</div>`).join(''):'<div class="empty">Aún no hay consultas documentadas.</div>';
  if(stage)$('currentStage').textContent=stage;
 }
 function createLayout(){
  for(const id of ['individual','plural','pluralContracts','candidates'])$(id)?.remove();
  const metrics=document.querySelector('.metrics');metrics.innerHTML=`<div><strong id="countExecution">—</strong><span>Ejecución reportada o posible</span></div><div><strong id="countContracts">—</strong><span>Otros contratos registrados</span></div><div><strong id="countParticipations">—</strong><span>Registros de participación</span></div><div><strong id="countCandidates">—</strong><span>Candidatos con contrato</span></div>`;
  const makeBuckets=(prefix,title,subtitle,baseIndex)=>`<section class="panel" id="${prefix}Section"><div class="section-label">${baseIndex} / Contratación</div><h2>${title}</h2><p class="hint">${subtitle}</p><div class="bucket-grid">${buckets.map(([platform,modality])=>`<section class="bucket"><header><strong>${names[platform]} · ${names[modality]}</strong><span class="bucket-count" id="${prefix+platform+modality+'Count'}">0</span></header><div id="${prefix+platform+modality}" class="results"><div class="empty">Aún sin consulta.</div></div></section>`).join('')}</div></section>`;
  const newSections=`<div class="stage" id="currentStage">Prioridad de resultados: ejecución → contratos → participaciones → candidatos.</div>`+
  makeBuckets('execution','Contratos con ejecución reportada o posible','SECOP II: estado contractual «En ejecución». SECOP I: posible ejecución según fechas publicadas, sin certeza de vigencia actual. Las suspensiones y modificaciones requieren comprobación.', '02')+
  makeBuckets('contract','Otros contratos registrados','Contratos formalizados en las fuentes consultadas sin acreditación suficiente de ejecución actual. No se repiten los del primer apartado.','03')+
  `<section class="panel" id="participationSection"><div class="section-label">04 / Participaciones y cuentas</div><h2>Registros de participación individual y plural</h2><p class="hint">Se distinguen las cuentas de proveedores y grupos, y los procesos sin firma contractual comprobada. Un registro de cuenta no implica adjudicación; SECOP I no identifica necesariamente a todos los oferentes.</p><div class="bucket-grid"><section class="bucket"><header><strong>SECOP I · Individual</strong></header><div class="results" id="participationIndividualI"></div></section><section class="bucket"><header><strong>SECOP I · Plural</strong></header><div class="results" id="participationPluralI"></div></section><section class="bucket" ><header><strong>SECOP II · Individual</strong></header><div class="results" id="participationIndividualII"></div></section><section class="bucket" id="gruposRegistrados"><header><strong>SECOP II · Plural</strong></header><div class="results" id="participationPluralII"></div></section></div></section>`+
  `<section class="panel" id="candidateSection"><div class="section-label">05 / Candidatos con contratos</div><h2>Contratos de estructuras parecidas, pendientes de comprobar</h2><p class="hint">Coincidencias de denominación plural o representante, vinculadas además a un contrato identificado. No se atribuyen al consultado sin acreditar composición.</p><div class="bucket-grid">${['I','II'].map(p=>`<section class="bucket"><header><strong>SECOP ${p} · Estructuras plurales</strong><span class="bucket-count" id="candidate${p}pluralCount">0</span></header><div id="candidate${p}plural" class="results"></div></section>`).join('')}</div></section>`;
  const trace=$('trace');trace.insertAdjacentHTML('beforebegin',newSections);
  $('trace').querySelector('.section-label').textContent='06 / Fuentes y cobertura';
  document.querySelector('.mast-tag').textContent='Consulta pública · Versión 2.3';
  document.querySelector('.mast h1').textContent='Contratos y participación por NIT';
  document.querySelector('.mast p').textContent='Primero ejecución, luego contratos, participaciones y candidatos respaldados por contratos. Información verificable en SECOP.';
 }
 async function collectContractCandidates(core,transport){
  const output=[];const individual=core.candidates.filter(c=>!c.code&&c.type==='i_group_similar');
  for(const c of individual){
   // Solo se admiten contratos de SECOP I si hubo firma o etapa contractual documentada.
   if(c.contract&&isContractI(c.contract))output.push({...c,key:'I|'+c.source+'|'+c.contract.key,platform:'I',modality:'plural'});
  }
  const codes=[...new Set(core.candidates.filter(c=>c.code).map(c=>c.code))].slice(0,80);
  if(codes.length){
   const all=[];
   for(let i=0;i<codes.length;i+=18){const slice=codes.slice(i,i+18);all.push(...await transport.filter('jbjy-vk9h',[['codigo_proveedor',slice]],'Candidatos: comprobar existencia de contrato SECOP II',{limit:1200}));}
   const joined=new Map();
   for(const r of all){if(!isContractII(r))continue;
    const c=core.candidates.find(c=>c.code===String(r.codigo_proveedor));if(!c)continue;
    const record=C.record('II',r,'Contrato publicado a nombre de estructura candidata');
    const k='II|'+record.key+'|'+c.code;if(!joined.has(k))joined.set(k,{...c,key:k,contract:record,platform:'II',modality:'plural',groupRecord:{...c,composition:[]}});
   }
   const shortlisted=[...new Set([...joined.values()].map(c=>c.code))];
   for(let i=0;i<shortlisted.length;i+=18){const piece=shortlisted.slice(i,i+18);
    const members=await transport.filter('ceth-n4bn',[['codigo_grupo',piece]],'Candidatos con contrato: recuperar composición del grupo',{limit:1000});
    for(const r of members){for(const c of joined.values())if(c.code===String(r.codigo_grupo)){
     if(!c.groupRecord.composition.some(x=>String(x.codigo_participante)===String(r.codigo_participante)&&String(x.nit_participante)===String(r.nit_participante)))c.groupRecord.composition.push(r);
    }}
   }
   output.push(...joined.values());
  }
  return unique(output);
 }
 const update=(msg,cls='processing')=>{$('status').textContent=msg;$('status').className='status '+cls};
 let latest=null;
 async function indexClient(id){const key=$('apiKey').value.trim();if(key.length<20)throw Error('La clave del índice debe tener mínimo 20 caracteres.');const response=await fetch('/api/search',{method:'POST',headers:{'Content-Type':'application/json','X-API-Key':key},body:JSON.stringify({identification:id.raw,kind:id.kind,include_secop_ii:false})});const data=await response.json();if(!response.ok)throw Error(data.detail||'Fallo al consultar índice');return data}
 createLayout();
 // Captura anterior al manejador heredado, para reemplazarlo sin cargar dos búsquedas.
 $('searchForm').addEventListener('submit',async evt=>{
  evt.preventDefault();evt.stopImmediatePropagation();
  let id;try{id=C.identity($('identifier').value,$('kind').value)}catch(e){update(e.message,'problem');return}
  const btn=$('searchButton');btn.disabled=true;$('download').disabled=true;latest=null;
  update('Buscando registros individuales y plurales…');
  try{
   const p=new C.PublicData({update:stage=>update(stage+'…'),proxyKey:!$('indexOption').hidden?$('apiKey').value.trim():''});
   const core=await C.discover(id,{platform:$('platform').value,historical:$('historical').checked,similar:$('similar').checked,representativeId:$('representativeId').value.trim(),indexClient:$('indexOption').hidden||!$('useIndex').checked?null:indexClient,onProgress:(part,stage)=>{reportUI(summarize(part),part,stage);}},p);
   update('Verificando si los candidatos tienen realmente contratos asociados…');
   const accounts=$('platform').value==='i'?[]:await p.filter('qmzu-gj57',[['nit',id.variants]],'SECOP II: consulta de cuentas individuales',{limit:400});
   const contractedCandidates=await collectContractCandidates(core,p);
   const report=summarize(core,accounts,contractedCandidates);
   reportUI(report,core,'Consulta terminada. Los registros se presentan por nivel de comprobación.');
   latest={identity:id,at:new Date().toISOString(),report,scope:'Consulta pública parcial. La ejecución de SECOP I por fechas es indicativa y no comprueba acta de inicio, suspensiones o liquidación. Los candidatos no acreditan pertenencia.'};
   const issues=p.tasks.filter(t=>t.status!=='ok');
   update(`Consulta finalizada: ${report.execution.length} con ejecución reportada o posible; ${report.contracts.length} otros contratos; ${report.candidates.length} candidatos con contrato. ${issues.length} consultas con incidencia.`,issues.length?'problem':'done');
   $('download').disabled=false;
  }catch(e){update('Consulta interrumpida: '+(e.message||e),'problem')}finally{btn.disabled=false}
 },true);
 // Captura exportación para que se descargue el nuevo informe, no el anterior.
 $('download').addEventListener('click',e=>{e.preventDefault();e.stopImmediatePropagation();if(!latest)return;const b=new Blob([JSON.stringify(latest,null,2)],{type:'application/json'}),u=URL.createObjectURL(b),a=document.createElement('a');a.href=u;a.download='secop_verificacion_v23_'+Date.now()+'.json';document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(u),1000)},true);
 // Utilidades para pruebas automatizadas.
 window.SecopPresentation={isContractI,isContractII,executionStatus,summarize,collectContractCandidates};
})();
