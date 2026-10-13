/* SECOP 2.7: secondary sourced document index. Never claims completeness or verified execution. */
(function(){'use strict';
 if(typeof document==='undefined')return;
 const API='https://secop-indice-ligero-api.onrender.com';
 const VERIFIED_SNAPSHOT=[{"contract_key":"ASOSUPRO:LP-035-2025:002-2026","entity_name":"ASOCIACION SUPRADEPARTAMENTAL DE MUNICIPIOS PARA EL PROGRESO - ASOSUPRO","process_ref":"LP-035-2025","contract_ref":"Contrato de Obra Publica 002 de 2026","contractor":"CONSORCIO MATEPANTANO MYM","contract_value_cop":10046170904,"sign_date":"2026-01-06","execution_class":"firma_acreditada_ejecucion_no_verificada","process_url":"https://contratacion.asosupro.gov.co/proceso/view?id=9aa802dc335a11f1bfe2fa163e75d6de","members":[{"nit":"800143586","name":"MEYAN S.A.","share_percent":10},{"nit":"901505828","name":"MYM INCONSER SAS ZOMAC","share_percent":80},{"nit":"901601837","name":"AGREOBRAS SAS","share_percent":10}],"evidence":[{"kind":"contrato_firmado","label":"Contrato de Obra Publica 002 de 2026; partes, valor y firma","url":"https://contratacion.asosupro.gov.co/admin/uploads/proceso/9aa802dc335a11f1bfe2fa163e75d6de/23.%20CONTRATO%20DE%20OBRA%20PUBLICA%20002%20DE%202026.pdf","page":4,"note":"Pag. 2: partes; pag. 4: precio y plazo; pag. 23: firmas"},{"kind":"composicion_plural","label":"Poliza de cumplimiento: identificaciones y participacion 10/80/10","url":"https://contratacion.asosupro.gov.co/admin/uploads/proceso/9aa802dc335a11f1bfe2fa163e75d6de/25.%20GARANTIAS%20-%20POLIZAS.pdf","page":4,"note":"Tabla Participantes Consorcio - Union Temporal, pag. 4 del PDF"},{"kind":"secop_expediente","label":"Expediente publicado en SECOP II (sin contrato estructurado asociado)","url":"https://community.secop.gov.co/Public/Tendering/OpportunityDetail/Index?noticeUID=CO1.NTC.10035129","page":null,"note":"El registro estructurado del proceso no acredita adjudicacion ni contrato; la evidencia es documental"}]}];
 function snapshot(nit){const matches=[];for(const c of VERIFIED_SNAPSHOT)for(const m of c.members){if(m.nit===nit)matches.push({...c,member_nit:m.nit,member_name:m.name,share_percent:m.share_percent,sources:c.evidence})}return {contracts:matches,indicators:[]}}
 const form=document.getElementById('searchForm'), input=document.getElementById('identifier'), kind=document.getElementById('kind');
 if(!form||!input)return;
 const panel=document.createElement('section');panel.id='documentIndex27';panel.className='panel documentary-index';panel.hidden=true;
 panel.innerHTML='<div class="index-line"><div><div class="section-label">Indice documental de fuentes verificables</div><h2>Contratos encontrados en documentos</h2></div><span class="index-note">Sin archivos almacenados</span></div><p class="hint">Complemento a SECOP I y II. Registra integrantes acreditados en documentos y sus enlaces. No certifica ejecucion vigente ni garantiza cobertura total.</p><div id="index27Status" class="context" role="status" aria-live="polite">Sin consulta.</div><div id="index27Records" class="index27-records"></div>';
 const metrics=document.querySelector('section.metrics');if(metrics)metrics.insertAdjacentElement('beforebegin',panel);else form.insertAdjacentElement('afterend',panel);
 const status=document.getElementById('index27Status'), list=document.getElementById('index27Records');
 let requestId=0;
 const text=(node,v)=>{node.textContent=v==null?'':String(v);return node};
 const node=(name,cls,value)=>{const n=document.createElement(name);if(cls)n.className=cls;if(value!==undefined)text(n,value);return n};
 function safeLink(url,label){try{const u=new URL(url);if(u.protocol!=='https:' || !/(^|\.)(asosupro\.gov\.co|secop\.gov\.co|contratos\.gov\.co|datos\.gov\.co|findeter\.gov\.co)$/.test(u.hostname))return null;
  const a=node('a','index27-source',label+' ↗');a.href=u.href;a.target='_blank';a.rel='noopener noreferrer';return a;
 }catch{return null}}
 function card(r){const article=node('article','index27-card');
  const top=node('div','index27-top');top.append(node('span','tag blue','Contrato documental'),node('span','tag','Participacion plural '+r.share_percent+' %'));article.append(top);
  article.append(node('h3','',r.contractor||'Estructura plural'),node('div','index27-id',(r.contract_ref||'Contrato')+' · '+(r.entity_name||'Entidad no publicada')));
  article.append(node('p','index27-detail',(r.member_name||'Integrante')+' · NIT '+r.member_nit));
  article.append(node('p','index27-detail','Contrato firmado: '+(r.sign_date||'fecha no registrada')+' · Ejecucion actual: sin verificar'));
  const foot=node('div','index27-links');const root=safeLink(r.process_url,'Expediente');if(root)foot.append(root);
  for(const e of r.sources||[]){if(['contrato_firmado','composicion_plural'].includes(e.kind)){let a=safeLink(e.url,e.kind==='contrato_firmado'?'Contrato firmado':'Prueba de integrantes');if(a)foot.append(a)}}
  article.append(foot);return article;
 }
 function render(data){list.replaceChildren();const records=data.contracts||[];
  if(records.length){status.textContent=records.length+' hallazgo(s) documentales asociados al NIT. Cada vinculo contiene evidencia; no prueba ejecucion actual.';records.forEach(x=>list.append(card(x)))}
  else status.textContent='Sin contratos documentales indexados para este NIT. Indice piloto, cobertura todavia incompleta.';
  const hints=data.indicators||[];if(hints.length){let detail=node('details','index27-indicators');let summary=node('summary','',hints.length+' menciones de NIT sin verificar (no son contratos)');detail.append(summary);
   for(const h of hints.slice(0,12)){let line=node('div','index27-hint',h.source+' · '+h.process_ref+' · pagina '+h.document_page+' · ');let a=safeLink(h.document_url,'Ver fuente');if(a)line.append(a);detail.append(line)}list.append(detail)}
 }
 document.addEventListener('submit',async(event)=>{
  if(event.target!==form)return;
  const serial=++requestId,raw=input.value.trim();panel.hidden=false;list.replaceChildren();
  if(kind&&kind.value!=='NIT'){status.textContent='El indice documental piloto consulta NIT. La busqueda SECOP para cedulas continua normalmente.';return}
  let nit=raw.split('-')[0].replace(/\D/g,'');if(nit.length===10)nit=nit.slice(0,9);
  if(nit.length!==9){status.textContent='Escriba un NIT valido para consultar el indice documental.';return}
  const initial=snapshot(nit);
  if(initial.contracts.length){render(initial);status.textContent=initial.contracts.length+' antecedente documental verificado en el piloto. Contrastando actualizaciones del indice remoto…'}
  else status.textContent='Contrastando el indice documental…';
  try{const response=await fetch(API+'/api/index/search?nit='+encodeURIComponent(nit),{cache:'no-store',signal:AbortSignal.timeout(65000)});
   const data=await response.json();if(serial!==requestId)return;
   if(!response.ok)throw new Error(data.error||'Indice no disponible');render(data);
  }catch(e){if(serial===requestId)status.textContent=initial.contracts.length?'Antecedente inicial mostrado desde el indice local verificado; actualizacion del indice remoto pendiente.':'Indice documental remoto aun no disponible. La consulta oficial SECOP no se interrumpe.'}
 },{capture:true});
})();
