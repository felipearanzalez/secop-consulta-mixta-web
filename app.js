/* SECOP consulta web 2.2. Consulta selectiva de fuentes oficiales; nunca demuestra exhaustividad. */
(function(root){
'use strict';
const DS={providers:'qmzu-gj57',groups:'ceth-n4bn',contractsII:'jbjy-vk9h',contractsI:'f789-7hwg',historic:'qddk-cgux'};
const SOURCE='https://www.datos.gov.co';
const DIRECTORY='https://community.secop.gov.co/Directory/CompanyProfiles/Network/Index';
const txt=v=>v==null?'':String(v).trim();
const norm=v=>txt(v).normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/\s+/g,' ').toUpperCase();
const valid=v=>!!txt(v)&&!['NO DEFINIDO','NO DEFINIDA','NO PROVISTO','N/A','NULL','SIN INFORMACION','0'].includes(norm(v));
const uniq=xs=>[...new Set(xs.filter(x=>x!==undefined&&x!==null&&x!==''))];
function identity(raw,kind='NIT'){
 const s=txt(raw);if(!/^[0-9.,\-\s]+$/.test(s))throw Error('La identificación solo puede contener dígitos y separadores.');
 if(kind!=='NIT'&&kind!=='CC')throw Error('Tipo de documento no admitido');
 const bits=s.split('-');if(bits.length>2||bits.length===2&&kind==='CC')throw Error('El guion de verificación solo se admite en NIT.');
 const base=bits[0].replace(/\D/g,'');const dv=bits.length===2?bits[1].trim():'';
 if(bits.length===2&&!/^\d$/.test(dv))throw Error('Dígito de verificación inválido.');
 if(base.length<5||base.length>15)throw Error('Revise la identificación introducida.');
 const dotted=base.replace(/\B(?=(\d{3})+(?!\d))/g,'.');
 const stem=uniq([base,dotted,dotted.replace(/\./g,' ')]);
 const vars=uniq([s,...stem,...(dv?stem.flatMap(n=>[n+'-'+dv,n+' - '+dv,n+dv]):[])]);
 return {kind,base,dv,raw:s,variants:vars};
}
function idMatch(i,value){const s=txt(value);if(!/^[\d\s,.-]+$/.test(s))return false;const packed=s.replace(/[\s.,]/g,'');return i.variants.includes(s)||packed===i.base||(i.dv&&[i.base+'-'+i.dv,i.base+i.dv].includes(packed));}
function idStringMatch(a,b){try{return idMatch(identity(a,'NIT'),b)||idMatch(identity(b,'NIT'),a)}catch{return false}}
function attr(v){return txt(v).replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));}
function part(v){return norm(v).replace(/[^A-Z0-9 ]/g,' ').replace(/\s+/g,' ').trim()}
const STOP=new Set(['CONSORCIO','UNION','TEMPORAL','UT','U','T','DE','DEL','LA','EL','LOS','LAS','Y','SAS','SA','LTDA','S','A','GRUPO','ASOCIACION','PARA']);
function tokens(v){return part(v).split(' ').filter(w=>w.length>=2&&!STOP.has(w));}
function dice(a,b){a=part(a).replace(/ /g,'');b=part(b).replace(/ /g,'');if(a===b)return 1;if(a.length<3||b.length<3)return 0;let aa=new Map;for(let i=0;i<a.length-1;i++){const q=a.slice(i,i+2);aa.set(q,(aa.get(q)||0)+1)}let hits=0;for(let i=0;i<b.length-1;i++){const q=b.slice(i,i+2),count=aa.get(q)||0;if(count){hits++;aa.set(q,count-1)}}return 2*hits/(a.length+b.length-2)}
function similarity(a,b,kind='group'){
 const x=tokens(a),y=tokens(b);const distinct=uniq(x),other=uniq(y);
 if(distinct.length<2||other.length<2)return 0;
 const both=distinct.filter(t=>other.includes(t)).length;
 const j=both/(distinct.length+other.length-both);
 if(kind==='group'&&both<2||kind==='representative'&&both<2)return 0;
 const ordered=dice(distinct.join(' '),other.join(' '));
 const sorted=dice([...distinct].sort().join(' '),[...other].sort().join(' '));
 const score=Math.max(ordered,sorted)*0.45+j*0.55;
 return Math.round(score*100)/100;
}
function comparable(a,b,kind='group'){return similarity(a,b,kind)>=(kind==='group'?.83:.90)}
function bestAnchor(v){return tokens(v).filter(t=>t.length>=5).sort((a,b)=>b.length-a.length)[0]||''}
function groupUrl(code){if(!valid(code))return '';const u=new URL('/resource/'+DS.groups+'.json',SOURCE);u.searchParams.set('codigo_grupo',txt(code));return u.href}
function contractIIUrl(row){const id=txt(row.id_contrato);if(/^CO1\.PCCNTR\.\d+$/i.test(id))return 'https://community.secop.gov.co/Public/Tendering/ContractDetailView/Index?UniqueIdentifier='+encodeURIComponent(id);return safeOfficialUrl(row.urlproceso)||''}
function contractIUrl(row){const c=txt(row.numero_de_constancia);if(/^\d{2}-\d+-\d{5,}$/.test(c))return 'https://www.contratos.gov.co/consultas/detalleProceso.do?numConstancia='+encodeURIComponent(c);return safeOfficialUrl(row.ruta_proceso_en_secop_i)||''}
function safeOfficialUrl(u){try{let v=new URL(txt(u));if(!['http:','https:'].includes(v.protocol))return '';if(!/(^|\.)(datos\.gov\.co|contratos\.gov\.co|secop\.gov\.co|colombiacompra\.gov\.co)$/.test(v.hostname.toLowerCase()))return '';return v.href}catch{return ''}}
function stateText(platform,state){const s=norm(state);if(s.includes('EJECUC')||s==='INEXECUTION')return 'Ejecución reportada; verificar documentos';if(s.includes('SUSPEND'))return 'Suspensión reportada; revisar';if(s.includes('TERMIN')||s.includes('LIQUID')||s.includes('CERRAD'))return 'Cierre o terminación reportada; revisar';return platform==='I'?'Estado de proceso, no de vigencia':'Vigencia no acreditada por el estado';}
function matchUrlStatus(v){if(!valid(v))return 'Sin dato publicado';const q=norm(v);if(['SI','SÍ','TRUE','1','YES'].includes(q))return 'Activo en directorio';if(['NO','FALSE','0'].includes(q))return 'Inactivo en directorio';return 'Valor publicado: '+v}
function rowKey(platform,row){if(platform==='II')return 'II|'+txt(row.id_contrato||row.referencia_del_contrato||row.urlproceso);return 'I|'+txt(row.uid||'')+'|'+txt(row.numero_de_constancia)+'|'+txt(row.id_ajudicacion||row.id_adjudicacion)+'|'+txt(row.numero_del_contrato||row.numero_de_contrato)+'|'+txt(row.nit_de_la_entidad)}
function selectFields(row,keys){const result={};for(const key of keys)if(row[key]!==undefined)result[key]=row[key];return result}
function batch(arr,n=18){const out=[];for(let i=0;i<arr.length;i+=n)out.push(arr.slice(i,i+n));return out}
function soqlString(v){return "'"+txt(v).replace(/'/g,"''")+"'"}
class PublicData{
 constructor({fetcher,update,proxyKey}={}){
  this.update=update||(()=>{});this.proxyKey=proxyKey||'';
  this.fetcher=fetcher||((url,options={})=>{
    const parsed=new URL(url),meta=parsed.pathname.match(/^\/api\/views\/([a-z0-9-]+)\.json$/),records=parsed.pathname.match(/^\/resource\/([a-z0-9-]+)\.json$/);
    if(!this.proxyKey||(!meta&&!records))return root.fetch(url,options);
    const headers={'X-API-Key':this.proxyKey,'Content-Type':'application/json'};
    if(meta)return root.fetch('/api/public/metadata/'+meta[1],{headers});
    return root.fetch('/api/public/query/'+records[1],{method:'POST',headers,body:JSON.stringify({where:parsed.searchParams.get('$where')||'',limit:Number(parsed.searchParams.get('$limit')||200),offset:Number(parsed.searchParams.get('$offset')||0),order:':id ASC'})});
  });
  this.types=new Map;this.tasks=[];this.maxPages=5;this.page=200;
 }
 async schema(ds){if(this.types.has(ds))return this.types.get(ds);const u=SOURCE+'/api/views/'+ds+'.json';const r=await this.fetcher(u,{headers:{Accept:'application/json'}});if(!r.ok)throw Error('Metadatos '+ds+': HTTP '+r.status);const data=await r.json();const fields={};for(const x of data.columns||[])if(x.fieldName)fields[x.fieldName]=x.dataTypeName;this.types.set(ds,fields);return fields}
 async filter(ds,checks,label,{limit=800,extra=''}={}){
  const t={source:ds,label,status:'iniciado',count:0,error:'',truncated:false};this.tasks.push(t);this.update(label);
  try{
   const types=await this.schema(ds);
   const expressions=[];
   for(const [field,values] of checks){if(!/^[a-z_][a-z0-9_]*$/.test(field))throw Error('Campo no válido');if(!Object.hasOwn(types,field))throw Error('La fuente no contiene el campo '+field);const vals=uniq(values);if(!vals.length)continue;
    const numeric=['number','integer','double'].includes(types[field]);const safe=vals.map(x=>numeric?( /^\d+$/.test(txt(x))?txt(x):null ):soqlString(x)).filter(Boolean);
    if(safe.length)expressions.push(field+' in ('+safe.join(',')+')');
   }
   if(extra)expressions.push(extra);
   if(!expressions.length)throw Error('No se construyó un filtro selectivo');
   const where=expressions.length===1?expressions[0]:'('+expressions.map(x=>'('+x+')').join(' OR ')+')';
   let results=[];const pg=Math.min(this.page,Math.max(1,limit));let ended=false;
   for(let offset=0;offset<limit;offset+=pg){
    const u=new URL('/resource/'+ds+'.json',SOURCE);
    u.searchParams.set('$where',where);u.searchParams.set('$limit',String(Math.min(pg,limit-offset)));
    u.searchParams.set('$offset',String(offset));u.searchParams.set('$order',':id ASC');
    let rows,problem=null;
    // Temporary upstream failures must not silently erase already retrieved pages.
    for(let attempt=0;attempt<3;attempt++){
     try{
      const resp=await this.fetcher(u.href,{headers:{Accept:'application/json'}});
      if(!resp.ok){let reason='';try{reason=(await resp.text()).slice(0,140)}catch{}
       const err=Error('HTTP '+resp.status+' '+reason);err.transient=[408,429,500,502,503,504].includes(resp.status);throw err;}
      rows=await resp.json();if(!Array.isArray(rows))throw Error('La respuesta no fue una lista');problem=null;break;
     }catch(e){problem=e;if(attempt>=2||e.transient===false)break;
      await new Promise(resolve=>setTimeout(resolve,350*(attempt+1)));}
    }
    if(problem){t.count=results.length;t.status=results.length?'partial':'failed';t.error='Página '+(1+offset/pg)+': '+txt(problem.message||problem).slice(0,290);return results;}
    results.push(...rows);if(rows.length<Math.min(pg,limit-offset)){ended=true;break;}
   }
   t.count=results.length;t.truncated=!ended&&results.length>=limit;t.status=t.truncated?'partial':'ok';return results;
  }catch(e){t.status='failed';t.error=txt(e.message||e).slice(0,400);return []}
 }
 async contains(ds,field,seed,label,limit=600){if(!seed)return[];const types=await this.schemaSafe(ds);if(!types||!Object.hasOwn(types,field)){this.tasks.push({source:ds,label,status:'failed',count:0,error:'Campo de nombre ausente o metadatos inaccesibles'});return[]}
   const expr="upper("+field+") like '%"+seed.replace(/'/g,"''")+"%'";
   return this.filter(ds,[],label,{limit,extra:expr});
 }
 async schemaSafe(ds){try{return await this.schema(ds)}catch{return null}}
}
function firstReal(...values){return values.find(x=>valid(x))??''}
function record(platform,row,route,group=null){
 const ii=platform==='II',state=txt(ii?row.estado_contrato:row.estado_del_proceso);
 const executionStart=ii?firstReal(row.fecha_de_inicio_de_ejecucion,row.fecha_de_inicio_del_contrato):row.fecha_ini_ejec_contrato;
 const executionEnd=ii?firstReal(row.fecha_de_fin_de_ejecucion,row.fecha_de_fin_del_contrato):row.fecha_fin_ejec_contrato;
 const hasExecutionDates=ii&&(valid(row.fecha_de_inicio_de_ejecucion)||valid(row.fecha_de_fin_de_ejecucion));
 const contractNo=firstReal(row.numero_del_contrato,row.numero_de_contrato);
 return {key:rowKey(platform,row),platform,route,group:group?.name||'',groupCode:group?.code||'',
 contractor:txt(ii?row.proveedor_adjudicado:firstReal(row.nom_raz_social_contratista,row.nom_razon_social_contratista)),
 contractorId:txt(ii?row.documento_proveedor:row.identificacion_del_contratista),
 reference:txt(ii?firstReal(row.referencia_del_contrato,row.id_contrato):firstReal(contractNo,row.numero_de_constancia)),
 entity:txt(ii?row.nombre_entidad:firstReal(row.nombre_de_la_entidad,row.nombre_entidad)),state,
 start:txt(executionStart),end:txt(executionEnd),
 dateBasis:ii?(hasExecutionDates?'Fechas de ejecución publicadas (con respaldo del plazo del contrato cuando falta un dato)':'Fechas del contrato; ejecución no comprobada'):'Fechas de ejecución del registro SECOP I',
 object:txt(ii?firstReal(row.objeto_del_contrato,row.descripcion_del_proceso):firstReal(row.objeto_del_contrato_a_la_firma,row.objeto_del_contrato_a_la,row.detalle_del_objeto_a_contratar)),
 url:ii?contractIIUrl(row):contractIUrl(row),constancia:txt(row.numero_de_constancia),contractId:txt(row.id_contrato),
 value:txt(ii?row.valor_del_contrato:row.cuantia_contrato),stateMeaning:stateText(platform,state),
 source:platform==='II'?DS.contractsII:DS.contractsI,sourceRow:row};
}
function newGroup(row){return {code:txt(row.codigo_grupo),name:txt(row.nombre_grupo),nit:txt(row.nit_grupo),active:txt(row.esta_activo),type:txt(row.tipo_empresa_grupo),rep:txt(row.nombre_representante_legal_grupo),repId:txt(row.numero_doc_representante_legal_grupo),repType:txt(row.tipo_doc_representante_legal_grupo),created:txt(row.fecha_creacion_grupo),percent:txt(row.participacion),member:txt(row.nombre_participante),memberId:txt(row.nit_participante),source:'ceth-n4bn',composition:[]}}
function candidateInfo(g,rule,anchor,score){return {code:g.code,name:g.name,nit:g.nit,rep:g.rep,repId:g.repId,active:g.active,type:g.type,rule,anchor,score:score??null,url:groupUrl(g.code),source:DS.groups,disclaimer:'No se ha demostrado pertenencia del proveedor consultado a esta estructura.'}}
async function discover(id,opts={},transport){
 const data=transport||new PublicData();const out={identity:id,at:new Date().toISOString(),individual:[],groups:[],plural:[],candidates:[],tasks:data.tasks,scope:'La búsqueda puntual no sustituye un índice documental nacional de SECOP I. No acredita exhaustividad ni vigencia.'};
 const onlyI=opts.platform==='i',onlyII=opts.platform==='ii';const groups=new Map(),candidateCodes=new Set();
 const addGroup=row=>{const code=txt(row.codigo_grupo);if(!valid(code))return;let g=groups.get(code);if(!g){g=newGroup(row);groups.set(code,g)}else if(!g.member&&row.nombre_participante)g.member=txt(row.nombre_participante)};
 const codes=[];
 {
  const rows=await data.filter(DS.providers,[['nit',id.variants]],'Localizar cuentas del proveedor');
  for(const p of rows)if(idMatch(id,p.nit)&&valid(p.codigo))codes.push(txt(p.codigo));
  const conditions=[['nit_participante',id.variants]];if(codes.length)conditions.push(['codigo_participante',uniq(codes)]);
  const memberships=await data.filter(DS.groups,conditions,'Localizar pertenencias registradas SECOP II',{limit:1200});
  for(const row of memberships)if(idMatch(id,row.nit_participante)||codes.includes(txt(row.codigo_participante)))addGroup(row);
 }
 out.groups=[...groups.values()];if(opts.onProgress)opts.onProgress(out,'Grupos con pertenencia recuperada');
 // Direct contracts; keep group contractors out of the individual section.
 if(!onlyI){
  const filters=[['documento_proveedor',id.variants]];if(codes.length)filters.push(['codigo_proveedor',uniq(codes)]);
  const own=await data.filter(DS.contractsII,filters,'SECOP II: contratación individual',{limit:1200});
  const gCodes=new Set(groups.keys());
  for(const r of own){const cod=txt(r.codigo_proveedor),kind=norm(r.es_grupo);if(gCodes.has(cod)||['SI','SÍ','TRUE','YES'].includes(kind))continue;
   if(idMatch(id,r.documento_proveedor)||codes.includes(cod))out.individual.push(record('II',r,'Identificación/código propio de proveedor'));
  }
  // Prioritize contracts over 300+ composition lookups; retry smaller batches if a source rejects one.
  async function fetchGroupContracts(ids,depth=0){
   const results=await data.filter(DS.contractsII,[['codigo_proveedor',ids]],'SECOP II: contratos de grupos acreditados',{limit:1200});
   const task=data.tasks[data.tasks.length-1];
   if(task?.status==='ok'||ids.length<=1||depth>=6)return results;
   const half=Math.ceil(ids.length/2);
   const left=await fetchGroupContracts(ids.slice(0,half),depth+1);
   const right=await fetchGroupContracts(ids.slice(half),depth+1);
   return [...results,...left,...right];
  }
  for(const ids of batch([...groups.keys()],50)){
   const contracts=await fetchGroupContracts(ids);
   for(const r of contracts){const g=groups.get(txt(r.codigo_proveedor));if(g)out.plural.push(record('II',r,'Código exacto de grupo SECOP II',g));}
   // Early visible progress prevents later non-contractual work from masking recovered contracts.
   if(opts.onProgress)opts.onProgress(out,'Contratos plurales acreditados: '+out.plural.length+' (verificando grupos restantes)');
  }
 }
 if(opts.onProgress)opts.onProgress(out,'Contratos electrónicos SECOP II recuperados');
 // SECOP I direct contractor and cross-platform by group NIT; inter-platform compositions require verification.
 if(!onlyII){
  for(const ds of [DS.contractsI,...(opts.historical?[DS.historic]:[])]){
   const own=await data.filter(ds,[['identificacion_del_contratista',id.variants]],'SECOP I: contratista por identificación',{limit:1200});
   for(const r of own)if(idMatch(id,r.identificacion_del_contratista)){
     const nm=norm(firstReal(r.nom_raz_social_contratista,r.nom_razon_social_contratista));
     if(/\b(CONSORCIO|UNION TEMPORAL|U\.T\.|UT\b)/.test(nm)){
       data.tasks.push({source:ds,label:'Registro con NIT consultado y denominación plural: no atribuible sin composición',status:'partial',count:1,error:'El nombre sugiere estructura plural y su identificación coincide con la del consultado; revise el registro original.',truncated:false});
     }else out.individual.push({...record('I',r,'Identificación propia publicada'),source:ds});
   }
   const grp=[...groups.values()].filter(g=>valid(g.nit)&&!idMatch(id,g.nit));
   for(const b of batch(grp,15)){
    const vals=uniq(b.map(x=>x.nit));const found=await data.filter(ds,[['identificacion_del_contratista',vals]],'SECOP I: contratos de NIT de grupos conocidos',{limit:1200});
    for(const r of found){const g=b.find(x=>idStringMatch(x.nit,r.identificacion_del_contratista));if(!g)continue;
     const s=similarity(g.name,firstReal(r.nom_raz_social_contratista,r.nom_razon_social_contratista),'group');
     if(s>=.83||part(g.name)===part(firstReal(r.nom_raz_social_contratista,r.nom_razon_social_contratista)))out.plural.push({...record('I',r,'Identificación del grupo coincidente; corroborar composición histórica',g),source:ds});
     else data.tasks.push({source:ds,label:'NIT de grupo coincidente con nombre contractual incompatible',status:'partial',count:1,error:'Se excluyó la atribución automática por inconsistencia de identidad del grupo: '+txt(g.name),truncated:false});
    }
   }
  }
 }
 // Group composition is a supplementary step, never a prerequisite for finding a contract.
 // Keep previous comprehensive group cards while exposing contracts much earlier.
 for(const b of batch([...groups.keys()],40)){
  const components=await data.filter(DS.groups,[['codigo_grupo',b]],'Recuperar composición detallada de consorcios',{limit:1200});
  for(const r of components){const g=groups.get(txt(r.codigo_grupo));if(g)g.composition.push(selectFields(r,['codigo_participante','nit_participante','nombre_participante','participacion']))}
 }
 if(opts.onProgress)opts.onProgress(out,'Contratos y procesos SECOP I recuperados; comprobando candidatos');
 // Candidate rules: group name, representative name or representative ID only. Never promote to membership.
 if(opts.similar!==false && groups.size){
  const ids=new Set(groups.keys());
  for(const base of [...groups.values()].slice(0,12)){
   const seed=bestAnchor(base.name);if(!seed)continue;
   const matches=await data.contains(DS.groups,'nombre_grupo',seed,'Comparar nombres de estructuras plurales',400);
   for(const row of matches){const g=newGroup(row);if(!valid(g.code)||ids.has(g.code)||candidateCodes.has(g.code))continue;const score=similarity(base.name,g.name,'group');if(score<.83)continue;
    out.candidates.push(candidateInfo(g,'Nombre del grupo similar al de una estructura en la que figura el integrante',base.name,score));candidateCodes.add(g.code);
   }
  }
  for(const base of [...groups.values()].slice(0,12)){
   const seed=bestAnchor(base.rep);if(!seed)continue;
   const matches=await data.contains(DS.groups,'nombre_representante_legal_grupo',seed,'Comparar nombres de representantes',400);
   for(const row of matches){const g=newGroup(row);if(!valid(g.code)||ids.has(g.code)||candidateCodes.has(g.code))continue;const score=similarity(base.rep,g.rep,'representative');if(score<.90)continue;
    out.candidates.push(candidateInfo(g,'Nombre del representante similar al representante registrado de un grupo relacionado',base.rep,score));candidateCodes.add(g.code);
   }
  }
 }
 const reps=uniq([...groups.values()].flatMap(g=>{
  const rep=txt(g.repId);if(!valid(rep)||idStringMatch(rep,g.nit))return[];
  return [rep];}).concat(opts.representativeId?[opts.representativeId]:[]));
 if(reps.length){
  const candidates=await data.filter(DS.groups,[['numero_doc_representante_legal_grupo',reps]],'Consulta por documento de representante',{limit:1000});
  for(const row of candidates){const g=newGroup(row);if(!valid(g.code)||groups.has(g.code)||candidateCodes.has(g.code))continue;
    out.candidates.push(candidateInfo(g,'Documento del representante coincide con documento contrastado (no acredita pertenencia)',reps.find(x=>idStringMatch(x,g.repId)),null));candidateCodes.add(g.code);
  }
 }
 // SECOP I exact/similar group name: only relevant if linked group found; names never conclusively prove membership.
 if(!onlyII && groups.size && opts.similar!==false){
  for(const ds of [DS.contractsI,...(opts.historical?[DS.historic]:[])]){
   for(const group of [...groups.values()].slice(0,12)){
    const seed=bestAnchor(group.name);if(!seed)continue;
    const raw=await data.contains(ds,'nom_raz_social_contratista',seed,'SECOP I: nombres de contratistas plurales similares',400);
    for(const row of raw){const score=similarity(group.name,firstReal(row.nom_raz_social_contratista,row.nom_razon_social_contratista),'group');const signed=Boolean(/^\d{4}-\d{2}-\d{2}/.test(txt(row.fecha_de_firma_del_contrato)) || (valid(firstReal(row.numero_del_contrato,row.numero_de_contrato))&&(/^\d{4}$/.test(txt(firstReal(row.anno_firma_del_contrato,row.anno_firma_contrato)))||/CELEBRAD|TERMINAD|LIQUIDAD/.test(norm(row.estado_del_proceso))||/^\d{4}-\d{2}-\d{2}/.test(txt(row.fecha_ini_ejec_contrato)))));if(score<.83||!signed)continue;
     const k=ds+'|'+rowKey('I',row);if(candidateCodes.has(k))continue;candidateCodes.add(k);
     const idSame=valid(group.nit)&&idStringMatch(group.nit,row.identificacion_del_contratista);
     if(idSame){continue}
     out.candidates.push({type:'i_group_similar',name:txt(firstReal(row.nom_raz_social_contratista,row.nom_razon_social_contratista)),group:group.name,rule:'Denominación similar a un grupo SECOP II del integrante; el NIT contractual no permite confirmar que sea el mismo grupo.',source:ds,url:contractIUrl(row),ref:txt(firstReal(row.numero_del_contrato,row.numero_de_contrato,row.numero_de_constancia)),score,contract:{...record('I',row,'Denominación parecida a un grupo conocido; sin atribución de participación'),source:ds}});
    }
   }
  }
 }
 if(opts.indexClient){
   data.update('Consultando índice documental SECOP I del servidor');
   try{
     const response=await opts.indexClient(id);
     for(const r of response.results||[]){
       const documental={key:'INDEX|'+txt(r.source_uid||r.constancia)+'|'+txt(r.reference)+'|'+txt(r.member),platform:'I',
         contractor:txt(r.contractor||r.group),contractorId:txt(r.contractor_id),reference:txt(r.reference||r.constancia),
         entity:txt(r.entity),state:txt(r.state),start:txt(r.start),end:txt(r.end),group:txt(r.group),
         route:txt(r.match)+' · Evidencia en '+txt(r.evidence?.file)+' pág. '+txt(r.evidence?.page),
         stateMeaning:stateText('I',r.state),url:contractIUrl({numero_de_constancia:r.constancia}),
         source:'Índice documental SECOP I',object:txt(r.evidence?.excerpt),evidence:r.evidence};
       if(r.kind==='contrato_vinculado')out.plural.push(documental);
       else if(r.kind==='contratacion_directa_identificacion')out.individual.push(documental);
       // Documentary non-award candidates are intentionally not listed as contractual candidates.
     }
     data.tasks.push({source:'indice',label:'Índice documental del servidor',status:'ok',count:(response.results||[]).length,error:'',truncated:!!response.truncated});
   }catch(e){data.tasks.push({source:'indice',label:'Índice documental del servidor',status:'failed',count:0,error:txt(e.message),truncated:false})}
 }
 const dedupe=arr=>[...new Map(arr.map(r=>[r.key||r.type+'|'+r.source+'|'+r.name+'|'+r.ref+'|'+r.code,r])).values()];
 out.individual=dedupe(out.individual);out.plural=dedupe(out.plural);out.candidates=dedupe(out.candidates);
 return out;
}
const API={identity,idMatch,similarity,comparable,groupUrl,contractIUrl,contractIIUrl,safeOfficialUrl,stateText,discover,PublicData,record,norm,txt,valid,part,attr,matchUrlStatus};
if(typeof module!=='undefined'&&module.exports)module.exports=API;
root.SecopWeb=API;
})(typeof window==='undefined'?globalThis:window);

(function(){'use strict';if(typeof document==='undefined')return;
const C=window.SecopWeb,$=id=>document.getElementById(id);let last=null;
function link(url,label){const safe=C.safeOfficialUrl(url);return safe?`<a href="${C.attr(safe)}" target="_blank" rel="noopener noreferrer">${C.attr(label)} ↗</a>`:''}
const shown=v=>C.valid(v)?C.attr(v):'No publicado';
function dt(v){const s=C.txt(v);if(!s)return 'No publicada';return C.attr(s.slice(0,10))}
function contractCard(r){return `<article class="record"><div class="top"><div><span class="tag blue">SECOP ${C.attr(r.platform)}</span><span class="tag">${C.attr(r.stateMeaning)}</span><h3>${shown(r.contractor||r.group)}</h3><div class="muted">${shown(r.reference)} · ${shown(r.entity)}</div></div><div class="role">${C.attr(r.route)}</div></div><div class="detail-grid"><div><span>Estado publicado</span><strong>${shown(r.state)}</strong></div><div><span>Inicio / finalización</span><strong>${dt(r.start)} / ${dt(r.end)}</strong></div><div><span>Identificación del contratista</span><strong>${shown(r.contractorId)}</strong></div></div><details><summary>Objeto contractual y fundamento</summary><p class="secondary">${shown(r.object)}</p><p class="muted">Fuente: ${C.attr(r.source)}. ${C.attr(r.route)}. La ejecución se determina con soportes contractuales.</p></details><div class="links">${link(r.url,'Abrir contrato o proceso en SECOP')}${r.groupCode?link(C.groupUrl(r.groupCode),'Ver registro exacto del grupo'):''}</div></article>`}
function groupCard(g){const people=g.composition.length?g.composition.map(m=>`<div class="member"><strong>${shown(m.nombre_participante)}</strong><small>${shown(m.nit_participante)} · Participación: ${shown(m.participacion)} %</small></div>`).join(''):'<div class="muted">No se recuperó composición completa; revisar la fuente.</div>';const status=C.matchUrlStatus(g.active);return `<article class="record"><div class="top"><div><span class="tag strong">Integrante registrado en SECOP II</span><span class="tag">${C.attr(status)}</span><h3>${shown(g.name)}</h3><div class="muted">Código interno: ${shown(g.code)} · Identificación grupo: ${shown(g.nit)}</div></div><div class="role">Participación del consultado: <strong>${shown(g.percent)} %</strong></div></div><div class="detail-grid"><div><span>Representante registrado</span><strong>${shown(g.rep)}</strong></div><div><span>Documento representante</span><strong>${shown(g.repId)}</strong></div><div><span>Fecha creación de cuenta</span><strong>${dt(g.created)}</strong></div></div><div class="profile"><div class="profile-head">Composición publicada</div><div class="members">${people}</div></div><div class="context">La fuente prueba el registro del integrante en la cuenta plural. No certifica aceptación electrónica, creador de la cuenta ni situación contractual.</div><div class="links">${link(C.groupUrl(g.code),'Registro oficial exacto en Datos Abiertos')}${link('https://community.secop.gov.co/Directory/CompanyProfiles/Network/Index','Abrir directorio SECOP II (buscar grupo)')}</div></article>`}
function candidateCard(c){const title=c.group?`${c.group} → ${c.name}`:c.name;const details=[c.nit?'NIT grupo: '+c.nit:'',c.rep?'Representante: '+c.rep:'',c.repId?'Documento representante: '+c.repId:'',c.ref?'Referencia SECOP I: '+c.ref:''].filter(Boolean).join(' · ');return `<article class="record"><div class="top"><div><span class="tag warn">Indicio, no pertenencia acreditada</span>${c.score!=null?`<span class="tag">Similitud ${Math.round(c.score*100)} %</span>`:''}<h3>${shown(title)}</h3><div class="muted">${C.attr(details)}</div></div></div><div class="context warning"><strong>Motivo de inclusión:</strong> ${C.attr(c.rule)}${c.anchor?`<div>Dato usado para comparar: <strong>${C.attr(c.anchor)}</strong></div>`:''}</div><div class="links">${link(c.url,'Abrir registro oficial')}${c.code?link('https://community.secop.gov.co/Directory/CompanyProfiles/Network/Index','Directorio SECOP II'):''}</div></article>`}
function show(id,arr,fn,empty){$(id).innerHTML=arr.length?arr.map(fn).join(''):`<div class="empty">${empty}</div>`}
function tasks(list){$('auditResults').innerHTML=list.length?list.map(t=>`<div class="audit-item"><span class="audit-status ${C.attr(t.status)}">${C.attr(t.status==='ok'?'Completada':t.status==='partial'?'Parcial':'Falló')}</span><b>${C.attr(t.label)}</b><span class="muted"> · ${C.attr(t.source)} · ${t.count} registros</span>${t.truncated?'<div class="context warning">Límite de registros alcanzado: resultados incompletos.</div>':''}${t.error?`<div class="context warning">${C.attr(t.error)}</div>`:''}</div>`).join(''):'<div class="empty">Sin operaciones.</div>'}
function update(txt,status='processing'){$('status').textContent=txt;$('status').className='status '+status}
async function indexedLookup(id){const key=$('apiKey').value;
 if(key.length<20)throw Error('Configure la clave del índice privado (20 caracteres o más).');
 const response=await fetch('/api/search',{method:'POST',headers:{'Content-Type':'application/json','X-API-Key':key},body:JSON.stringify({identification:id.raw,kind:id.kind,include_secop_ii:false})});
 const body=await response.json().catch(()=>({detail:'Respuesta no interpretable'}));
 if(!response.ok)throw Error(body.detail||'Índice HTTP '+response.status);
 return body;
}
(async()=>{try{const r=await fetch('/health',{cache:'no-store'});if(r.ok){const d=await r.json();if(d.service==='ok')$('indexOption').hidden=false}}catch{}})();
$('searchForm').addEventListener('submit',async e=>{e.preventDefault();let identity;try{identity=C.identity($('identifier').value,$('kind').value)}catch(err){update(err.message,'problem');return}const btn=$('searchButton');btn.disabled=true;last=null;$('download').disabled=true;update('Consultando Datos Abiertos…');try{const p=new C.PublicData({update:msg=>update(msg+'…'),proxyKey:!$('indexOption').hidden?$('apiKey').value.trim():''});const report=await C.discover(identity,{platform:$('platform').value,historical:$('historical').checked,similar:$('similar').checked,representativeId:$('representativeId').value.trim(),indexClient:$('indexOption').hidden||!$('useIndex').checked?null:indexedLookup},p);last=report;
$('countIndividual').textContent=report.individual.length;$('countGroups').textContent=report.groups.length;$('countPlural').textContent=report.plural.length;$('countCandidates').textContent=report.candidates.length;
show('individualResults',report.individual,contractCard,'Sin contratos individuales localizados en las fuentes consultadas.');show('groupsResults',report.groups,groupCard,'No se localizaron pertenencias registradas en SECOP II.');show('pluralResults',report.plural,contractCard,'No se localizaron contratos de los grupos encontrados; esto no demuestra inexistencia.');show('candidateResults',report.candidates,candidateCard,'No se identificaron indicios fundamentados con las tres reglas seleccionadas.');tasks(report.tasks);const failed=report.tasks.filter(t=>t.status!=='ok');update(`Consulta terminada. ${report.tasks.length} operaciones; ${failed.length} con incidencia. Los hallazgos muestran estado publicado, no vigencia certificada.`,failed.length?'problem':'done');$('download').disabled=false;
}catch(err){update('Consulta interrumpida: '+err.message,'problem')}finally{btn.disabled=false}});
$('download').addEventListener('click',()=>{if(!last)return;const blob=new Blob([JSON.stringify(last,null,2)],{type:'application/json'});const u=URL.createObjectURL(blob),a=document.createElement('a');a.href=u;a.download='secop_consulta_'+Date.now()+'.json';document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(u),1000)});
})();

/* SECOP 2.4 — clasificación de ejecución y lectura canónica de campos y verificación amigable.
   Extensión no intrusiva sobre SecopWeb 2.2; no realiza cargas documentales. */
(function(){'use strict';
 if(typeof document==='undefined'||!window.SecopWeb)return;
 const C=window.SecopWeb,$=id=>document.getElementById(id);
 const safe=s=>C.attr(s==null?'':String(s));
 const display=v=>C.valid(v)?safe(v):'No publicado';
 const norm=C.norm;
 const firstReal=(...xs)=>xs.find(C.valid)??'';
 const date=v=>{const s=String(v||'');const m=s.match(/^(\d{4})-(\d{2})-(\d{2})/);if(!m)return null;const d=new Date(m[1]+'-'+m[2]+'-'+m[3]+'T12:00:00Z');return Number.isFinite(d.getTime())&&d.toISOString().slice(0,10)===m[0]?d:null};
 const day=v=>date(v)?date(v).toISOString().slice(0,10):'No registrada';
 const currentDay=()=>{const p=Object.fromEntries(new Intl.DateTimeFormat('es-CO',{timeZone:'America/Bogota',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date()).filter(x=>x.type!=='literal').map(x=>[x.type,x.value]));return `${p.year}-${p.month}-${p.day}`};
 const link=(url,label)=>{const u=C.safeOfficialUrl(url);return u?`<a href="${safe(u)}" target="_blank" rel="noopener noreferrer">${safe(label)} ↗</a>`:''};
 function isContractI(r){
  const d=r.sourceRow||r;
  const n=String(firstReal(d.numero_del_contrato,d.numero_de_contrato)).trim(),hasNumber=C.valid(n)&&!/^(SIN|NO)\b/i.test(n);
  const signed=date(d.fecha_de_firma_del_contrato);
  const year=String(firstReal(d.anno_firma_del_contrato,d.anno_firma_contrato)).trim(),state=norm(d.estado_del_proceso||r.state);
  return Boolean(signed || (hasNumber && (/^(19|20)\d{2}$/.test(year)||/CELEBRAD|LIQUIDAD|TERMINAD/.test(state)||date(d.fecha_ini_ejec_contrato))));
 }
 function isContractII(r){const d=r.sourceRow||r,st=norm(d.estado_contrato||r.state);return Boolean(C.valid(d.id_contrato||r.contractId)&& !/BORRADOR|EN APROBACION|EN FIRMA|PENDIENTE DE FIRMA/.test(st));}
 function executionStatus(r,today=currentDay()){
  const s=norm(r.state),d=r.sourceRow||r;
  const now=date(today),start=date(r.start),end=date(r.end);
  const ended=now&&end&&end<now,notExpired=now&&end&&end>=now;
  const started=now&&start&&start<=now;
  const explicitStop=/SUSPEND|TERMIN|LIQUID|CERRAD|ANULAD|CANCELAD|REVOCAD|CADUCAD|RESCIND|RESUELT/.test(s);
  if(explicitStop)return {level:'other',text:`Estado publicado «${r.state}»: no presumir ejecución, aunque la fecha final figure vigente.`};
  if(r.platform==='II'&&(/\bEN EJECUCION\b|\bIN EXECUTION\b/.test(s))){
   return {level:'reported',text:ended?'SECOP II publica «En ejecución», pero la fecha final informada ya pasó: comprobar prórrogas, suspensiones y fecha de corte.':'SECOP II publica estado «En ejecución». Confirmar novedades y soportes contractuales.'};
  }
  if(start&&notExpired&&started){
   return {level:'possible',text:`Plazo publicado vigente (${r.dateBasis||'fechas registradas'}); el estado «${r.state||'no informado'}» no acredita por sí solo ejecución. Corroborar acta de inicio, suspensiones y modificaciones.`};
  }
  // Fecha final futura con inicio ausente: es alerta útil, no ejecución acreditada.
  const signed=date(d.fecha_de_firma_del_contrato||d.fecha_de_firma);
  if(!start&&notExpired&&signed&&signed<=now){
   return {level:'possible',text:'Terminación futura y firma anterior a la fecha de consulta, pero falta fecha de inicio de ejecución. Es un indicio, no un contrato en ejecución comprobada.'};
  }
  return {level:'other',text:ended?'El plazo registrado terminó; puede existir suspensión o prórroga sin reflejar en la fuente. Revisar expediente.':start&&now&&start>now?'El inicio publicado es futuro; no se presume ejecución actual.':'Falta fecha válida de inicio, terminación o evidencia de ejecución actual.'};
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
  return `<article class="record"><div class="top"><div>${badge}<h3>${display(r.contractor||r.group)}</h3><div class="muted">${display(r.reference)} · ${display(r.entity)}</div></div><div class="role">${safe(r.route)}</div></div><div class="detail-grid"><div><span>Estado publicado</span><strong>${display(r.state)}</strong></div><div><span>Firma / inicio / fin</span><strong>${safe(day(r.sourceRow?.fecha_de_firma||r.sourceRow?.fecha_de_firma_del_contrato))} / ${safe(day(r.start))} / ${safe(day(r.end))}</strong><small>${safe(r.dateBasis||'Referencia del registro contractual')}</small></div><div><span>Identificación del contratista</span><strong>${display(r.contractorId)}</strong></div><div><span>Valor inicial publicado</span><strong>${r.value&&!isNaN(Number(r.value))?new Intl.NumberFormat('es-CO',{style:'currency',currency:'COP',maximumFractionDigits:0}).format(Number(r.value)):display(r.value)}</strong></div></div><div class="context ${e.level==='possible'||r.participationReason?'warning':''}">${safe(r.participationReason||e.text)}</div><details><summary>Objeto y fundamento de la vinculación</summary><p class="secondary">${objectText(r.object)}</p><p class="muted">Fuente: ${safe(r.source)}. ${safe(r.route)}. Una fecha proyectada no incorpora necesariamente suspensiones o modificaciones.</p></details><div class="links">${link(r.url,'Ver expediente contractual en SECOP')}${r.groupCode?`<a href="#gruposRegistrados">Ver composición del grupo en esta página ↓</a>`:''}</div></article>`;
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
  makeBuckets('execution','Contratos con ejecución reportada o posible','Se incluyen: (i) estado «En ejecución» en SECOP II, y (ii) indicios de plazo vigente con fechas verificables, aunque la fuente use otra denominación. No se incluyen contratos con estado publicado de suspensión o terminación. Los plazos no acreditan por sí solos ejecución real.', '02')+
  makeBuckets('contract','Otros contratos registrados','Contratos formalizados en las fuentes consultadas sin acreditación suficiente de ejecución actual. No se repiten los del primer apartado.','03')+
  `<section class="panel" id="participationSection"><div class="section-label">04 / Participaciones y cuentas</div><h2>Registros de participación individual y plural</h2><p class="hint">Se distinguen las cuentas de proveedores y grupos, y los procesos sin firma contractual comprobada. Un registro de cuenta no implica adjudicación; SECOP I no identifica necesariamente a todos los oferentes.</p><div class="bucket-grid"><section class="bucket"><header><strong>SECOP I · Individual</strong></header><div class="results" id="participationIndividualI"></div></section><section class="bucket"><header><strong>SECOP I · Plural</strong></header><div class="results" id="participationPluralI"></div></section><section class="bucket" ><header><strong>SECOP II · Individual</strong></header><div class="results" id="participationIndividualII"></div></section><section class="bucket" id="gruposRegistrados"><header><strong>SECOP II · Plural</strong></header><div class="results" id="participationPluralII"></div></section></div></section>`+
  `<section class="panel" id="candidateSection"><div class="section-label">05 / Candidatos con contratos</div><h2>Contratos de estructuras parecidas, pendientes de comprobar</h2><p class="hint">Coincidencias de denominación plural o representante, vinculadas además a un contrato identificado. No se atribuyen al consultado sin acreditar composición.</p><div class="bucket-grid">${['I','II'].map(p=>`<section class="bucket"><header><strong>SECOP ${p} · Estructuras plurales</strong><span class="bucket-count" id="candidate${p}pluralCount">0</span></header><div id="candidate${p}plural" class="results"></div></section>`).join('')}</div></section>`;
  const trace=$('trace');trace.insertAdjacentHTML('beforebegin',newSections);
  $('trace').querySelector('.section-label').textContent='06 / Fuentes y cobertura';
  document.querySelector('.mast-tag').textContent='Consulta pública · Versión 2.10 (recuperación reforzada)';
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
  // El contraste con Croma es voluntario, independiente y nunca bloquea SECOP.
  window.SecopCroma?.start(id.raw,$('representativeId').value.trim(),$('platform').value);
  // Las fuentes SECOP se consultan de manera independiente de cualquier contraste.
  window.SecopCoverage26?.reset();
  try{
   const p=new C.PublicData({update:stage=>update(stage+'…'),proxyKey:!$('indexOption').hidden?$('apiKey').value.trim():''});
   const core=await C.discover(id,{platform:$('platform').value,historical:$('historical').checked,similar:$('similar').checked,representativeId:$('representativeId').value.trim(),indexClient:$('indexOption').hidden||!$('useIndex').checked?null:indexClient,onProgress:(part,stage)=>{reportUI(summarize(part),part,stage);}},p);
   update('Verificando si los candidatos tienen realmente contratos asociados…');
   const accounts=$('platform').value==='i'?[]:await p.filter('qmzu-gj57',[['nit',id.variants]],'SECOP II: consulta de cuentas individuales',{limit:400});
   const coverageTask=window.SecopExtended26?.lookup(id,core,accounts,p,{platform:$('platform').value})||Promise.resolve(null);
   const contractedCandidates=await collectContractCandidates(core,p);
   const report=summarize(core,accounts,contractedCandidates);
   reportUI(report,core,'Contratos localizados. Verificando procesos y proponentes adicionales...');
   latest={identity:id,at:new Date().toISOString(),report,extended:null,institutional_coverage:{findeter:'indexador piloto no conectado a sitio web',asosupro:'indexador piloto no conectado a sitio web',universidades:'pendiente',empresas_servicios_publicos:'pendiente',internacional:'pendiente'},scope:'Consulta pública parcial. La ejecución de SECOP I por fechas es indicativa y no comprueba acta de inicio, suspensiones o liquidación. Adjudicaciones y proponentes no equivalen a contratos celebrados.'};
   update('Contratos publicados. Consultando adjudicaciones y proponentes en otras fuentes oficiales...');
   try{
    const coverage=await coverageTask;
    if(coverage){latest.extended=coverage;window.SecopCoverage26?.render(coverage)}
   }catch(err){p.tasks.push({source:'p6dx-8zbt / hgi6-6wh3',label:'Cobertura adicional SECOP II',status:'failed',count:0,error:String(err.message||err),truncated:false});}
   reportUI(report,core,'Consulta finalizada. Consulte cobertura e incidencias; procesos sin contrato acreditado se informan por separado.');
   const issues=p.tasks.filter(t=>t.status!=='ok');
   update(`Consulta ${issues.length?'con cobertura parcial':'completada'}: ${report.execution.length} contratos con ejecución reportada/posible en datos estructurados; ${report.contracts.length} otros contratos en datos estructurados; ${report.candidates.length} candidatos sin pertenencia acreditada; ${latest.extended?.awards.length||0} adjudicaciones adicionales sin contrato electrónico. ${issues.length} operaciones con incidencia. Revise también los contratos documentales en el apartado 03A.`,issues.length?'problem':'done');
   $('download').disabled=false;
  }catch(e){update('Consulta interrumpida: '+(e.message||e),'problem')}finally{btn.disabled=false}
 },true);
 // Captura exportación para que se descargue el nuevo informe, no el anterior.
 $('download').addEventListener('click',e=>{e.preventDefault();e.stopImmediatePropagation();if(!latest)return; if(window.SecopCroma?.isEnabled()){latest.croma=window.SecopCroma.getState()||null;}else{delete latest.croma;}const b=new Blob([JSON.stringify(latest,null,2)],{type:'application/json'}),u=URL.createObjectURL(b),a=document.createElement('a');a.href=u;a.download='secop_verificacion_v26_'+Date.now()+'.json';document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(u),1000)},true);
 // Utilidades para pruebas automatizadas.
 window.SecopPresentation={isContractI,isContractII,executionStatus,summarize,collectContractCandidates};
})();



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
  const audit=$('trace');if(audit){const note=document.createElement('details');note.className='institutional-coverage';
 note.innerHTML=`<summary>Portales externos: alcance que falta indexar</summary><p class="hint">FINDETER, ASOSUPRO, universidades, empresas de servicios públicos y fuentes internacionales no están conectadas a esta edición estática. Que no aparezcan contratos de esas fuentes no acredita su inexistencia. El paquete de desarrollo contiene un rastreador piloto independiente para FINDETER y ASOSUPRO, aún no desplegado como servicio persistente.</p><div class="links"><a href="https://www.findeter.gov.co/convocatorias" target="_blank" rel="noopener noreferrer">FINDETER ↗</a><a href="https://contratacion.asosupro.gov.co/site/index" target="_blank" rel="noopener noreferrer">ASOSUPRO ↗</a></div>`;
 audit.append(note)}
 window.SecopCoverage26={render,reset(){show('extended26Awards',[],awardCard,'Esperando consulta.');show('extended26Bids',[],bidCard,'Esperando consulta.');$('extended26Status').textContent='Consultando fuentes nuevas...';}};
})();

/* SECOP 2.7: secondary sourced document index. Never claims completeness or verified execution. */
(function(){'use strict';
 if(typeof document==='undefined')return;
 const API='https://secop-indice-ligero-api.onrender.com';
 const VERIFIED_SNAPSHOT=[{"contract_key":"ASOSUPRO:LP-035-2025:002-2026","entity_name":"ASOCIACION SUPRADEPARTAMENTAL DE MUNICIPIOS PARA EL PROGRESO - ASOSUPRO","process_ref":"LP-035-2025","contract_ref":"Contrato de Obra Publica 002 de 2026","contractor":"CONSORCIO MATEPANTANO MYM","contract_value_cop":10046170904,"sign_date":"2026-01-06","execution_class":"firma_acreditada_ejecucion_no_verificada","process_url":"https://contratacion.asosupro.gov.co/proceso/view?id=9aa802dc335a11f1bfe2fa163e75d6de","members":[{"nit":"800143586","name":"MEYAN S.A.","share_percent":10},{"nit":"901505828","name":"MYM INCONSER SAS ZOMAC","share_percent":80},{"nit":"901601837","name":"AGREOBRAS SAS","share_percent":10}],"evidence":[{"kind":"contrato_firmado","label":"Contrato de Obra Publica 002 de 2026; partes, valor y firma","url":"https://contratacion.asosupro.gov.co/admin/uploads/proceso/9aa802dc335a11f1bfe2fa163e75d6de/23.%20CONTRATO%20DE%20OBRA%20PUBLICA%20002%20DE%202026.pdf","page":4,"note":"Pag. 2: partes; pag. 4: precio y plazo; pag. 23: firmas"},{"kind":"composicion_plural","label":"Poliza de cumplimiento: identificaciones y participacion 10/80/10","url":"https://contratacion.asosupro.gov.co/admin/uploads/proceso/9aa802dc335a11f1bfe2fa163e75d6de/25.%20GARANTIAS%20-%20POLIZAS.pdf","page":4,"note":"Tabla Participantes Consorcio - Union Temporal, pag. 4 del PDF"},{"kind":"secop_expediente","label":"Expediente publicado en SECOP II (sin contrato estructurado asociado)","url":"https://community.secop.gov.co/Public/Tendering/OpportunityDetail/Index?noticeUID=CO1.NTC.10035129","page":null,"note":"El registro estructurado del proceso no acredita adjudicacion ni contrato; la evidencia es documental"}]}];
 function snapshot(nit){const matches=[];for(const c of VERIFIED_SNAPSHOT)for(const m of c.members){if(m.nit===nit)matches.push({...c,member_nit:m.nit,member_name:m.name,share_percent:m.share_percent,sources:c.evidence})}return {contracts:matches,indicators:[]}}
 const form=document.getElementById('searchForm'), input=document.getElementById('identifier'), kind=document.getElementById('kind');
 if(!form||!input)return;
 const panel=document.createElement('section');panel.id='documentIndex27';panel.className='panel documentary-index';panel.hidden=true;
 panel.innerHTML='<div class="index-line"><div><div class="section-label">03A / Contratación acreditada documentalmente</div><h2>Contratos adicionales encontrados en documentos</h2></div><span class="index-note">Sin archivos almacenados</span></div><p class="hint">Contratos acreditados mediante contrato suscrito y documento de conformacion plural, aunque no aparezcan vinculados al NIT en los conjuntos estructurados. No son indicios de ejecucion actual.</p><div id="index27Status" class="context" role="status" aria-live="polite">Sin consulta.</div><div id="index27Records" class="index27-records"></div>';
 // Preserve the agreed reading order: execution, SECOP contracts, documentary contracts, memberships, candidates.
 const formalContracts=document.getElementById('contractSection');
 if(formalContracts)formalContracts.insertAdjacentElement('afterend',panel);
 else {const metrics=document.querySelector('section.metrics');if(metrics)metrics.insertAdjacentElement('afterend',panel);else form.insertAdjacentElement('afterend',panel);}
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
  article.append(node('p','index27-detail','Valor contractual: '+(Number.isFinite(Number(r.contract_value_cop)) ? new Intl.NumberFormat('es-CO',{style:'currency',currency:'COP',maximumFractionDigits:0}).format(Number(r.contract_value_cop)) : 'No publicado')));
  article.append(node('p','index27-detail','Fecha de firma: '+(r.sign_date||'No publicada')+' · Inicio de ejecucion: '+(r.execution_start_date||'No acreditado')+' · Fin de ejecucion: '+(r.execution_end_date||'No acreditado')));
  article.append(node('p','index27-detail','Estado documental: contrato firmado; ejecucion vigente sin verificar'));
  const foot=node('div','index27-links');const root=safeLink(r.process_url,'Expediente');if(root)foot.append(root);
  for(const e of r.sources||[]){if(['contrato_firmado','composicion_plural'].includes(e.kind)){let a=safeLink(e.url,e.kind==='contrato_firmado'?'Contrato firmado':'Prueba de integrantes');if(a)foot.append(a)}}
  article.append(foot);return article;
 }
 function render(data){list.replaceChildren();const records=data.contracts||[];
  if(records.length){status.textContent=records.length+' contrato(s) adicionales acreditados con documentos para este NIT; no confundir con ejecucion vigente. Las categorias SECOP I y II anteriores solo cuentan registros estructurados.';records.forEach(x=>list.append(card(x)))}
  else status.textContent='Sin contratos documentales adicionales indexados para este NIT. Cobertura piloto incompleta: no significa ausencia de contratos.';
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

/* SECOP 2.9: independent optional Croma contrast. Disabled by default; no Croma
   requests until explicitly enabled. Never changes main SECOP classifications. */
(function(root){
'use strict';
if(typeof document==='undefined')return;
const API='https://secop-croma-bridge.onrender.com';
const $=id=>document.getElementById(id);
const clean=v=>v==null?'':String(v).trim();
const C=root.SecopWeb;
let enabled=false,configured=null,requestId=0,last=null;
function field(record,keys){for(const k of keys){const v=record?.[k];if(v!==undefined&&v!==null&&clean(v))return clean(v)}return ''}
function platform(record){const v=field(record,['platform','source_platform']).toLowerCase();if(/secop.?ii$/.test(v)||v==='ii')return 'SECOP II';if(/secop.?i$/.test(v)||v==='i')return 'SECOP I';return v||'Plataforma sin indicar'}
function recordLink(record){
 const u=field(record,['url','contract_url','process_url','secop_url','source_url','link']);
 try{const a=new URL(u);if(a.protocol==='https:'&&/(^|\.)(datos\.gov\.co|contratos\.gov\.co|secop\.gov\.co|colombiacompra\.gov\.co)$/.test(a.hostname))return a.href}catch{}
 const c=field(record,['contract_id']);
 if(/^CO1\.PCCNTR\.\d+$/i.test(c))return 'https://community.secop.gov.co/Public/Tendering/ContractDetailView/Index?UniqueIdentifier='+encodeURIComponent(c);
 const p=field(record,['constancia','process_reference']);
 if(/^\d{2}-\d+-\d{5,}$/.test(p))return 'https://www.contratos.gov.co/consultas/detalleProceso.do?numConstancia='+encodeURIComponent(p);
 return '';
}
function elt(tag,cls,txt){const a=document.createElement(tag);if(cls)a.className=cls;if(txt!==undefined)a.textContent=txt;return a}
function status(message){const a=$('cromaStatus');if(a)a.textContent=message}
function renderList(host,part,isRepresentative){
 host.replaceChildren();if(!part){host.append(elt('div','empty','Sin consulta por representante.'));return}
 const rows=Array.isArray(part.records)?part.records:[];
 const total=Number.isFinite(Number(part.total_reported))?part.total_reported:'no determinado';
 host.append(elt('div','context',`${rows.length} registro(s) recuperados de ${total} reportados · corte ${part.as_of||'no indicado'}${part.truncated?' · Cobertura parcial por paginación':''}.`));
 if(!rows.length){host.append(elt('div','empty','Sin registros en las páginas consultadas. No certifica inexistencia.'));return}
 for(const r of rows){
  const a=elt('article','record');a.append(elt('h3','',field(r,['provider_name','contractor_name','supplier_name','contractor','provider','proveedor','contractor_legal_name'])||'Contratista no indicado'));
  a.append(elt('div','muted',platform(r)+' · '+(field(r,['contract_id','contract_reference','reference','id'])||'Referencia no informada')+(isRepresentative?' · VÍNCULO POR REPRESENTANTE (NO ACREDITA PARTICIPACIÓN)':'')));
  const entity=field(r,['entity_name','entity','contracting_entity','buyer_name','buyer']);if(entity)a.append(elt('div','detail-row','Entidad: '+entity));
  const state=field(r,['status','contract_status','state']);a.append(elt('div','detail-row','Estado publicado: '+(state||'No informado')));
  const start=field(r,['start_date','contract_start_date','execution_start_date']);
  const end=field(r,['end_date','contract_end_date','execution_end_date','fecha_fin']);
  a.append(elt('div','detail-row','Inicio: '+(start||'No informado')+' · Terminación: '+(end||'No informada')));
  const value=field(r,['value_with_additions','contract_value','value']);if(value)a.append(elt('div','detail-row','Valor reportado: '+value));
  const link=recordLink(r);if(link){const source=elt('a','croma-source','Abrir registro oficial ↗');source.href=link;source.target='_blank';source.rel='noopener noreferrer';a.append(source)}
  else a.append(elt('div','muted','Sin enlace directo oficial confirmado.'));
  host.append(a);
 }
}
function render(data){
 last=data;
 renderList($('cromaDirect'),data.direct||{},false);
 renderList($('cromaRepresentative'),data.representative_candidates,true);
 const first=data.direct||{};
 status(`Contraste finalizado: ${first.count_returned??(first.records||[]).length} registro(s) por identificación; ${data.representative_candidates?.count_returned||0} coincidencias por representante sin atribución contractual. Esta sección no altera el resultado principal.`);
}
async function health(){
 try{
  const response=await fetch(API+'/health',{cache:'no-store',signal:AbortSignal.timeout(9000)});
  if(!response.ok)throw Error('Servidor no disponible');
  const j=await response.json();configured=j.configured===true;
  if(enabled)status(configured?'Conexión complementaria disponible. Ingrese la clave privada del buscador y consulte.':'El servicio Croma no está configurado en Render. SECOP funciona independientemente.');
  return configured;
 }catch{configured=false;if(enabled)status('La conexión opcional Croma no está disponible. Los resultados SECOP no se afectan.');return false}
}
function disable(){
 enabled=false;configured=null;requestId++;last=null;
 const area=$('cromaAuthArea'),panel=$('cromaSection');if(area)area.hidden=true;if(panel)panel.hidden=true;
 if($('cromaAccess'))$('cromaAccess').value='';
 if($('cromaDirect'))$('cromaDirect').replaceChildren(elt('div','empty','Sin contraste aún.'));
 if($('cromaRepresentative'))$('cromaRepresentative').replaceChildren(elt('div','empty','Sin contraste aún.'));
}
async function start(raw,representativeId,choice){
 if(!enabled||!$('cromaEnabled')?.checked)return;
 const serial=++requestId;
 $('cromaSection').hidden=false;
 const token=clean($('cromaAccess')?.value);
 if(token.length<20){status('Introduzca la clave privada de acceso al buscador, distinta de la API key de Croma.');return}
 let documentId;
 try{if($('kind')?.value!=='NIT')throw Error('La opción complementaria está habilitada para NIT.');documentId=C.identity(raw,'NIT').raw}
 catch{status('Ingrese un NIT válido para consultar Croma.');return}
 if(configured!==true){status('Comprobando disponibilidad del contraste opcional…');if(!await health()||serial!==requestId)return}
 status('Consultando Croma en paralelo, sin afectar SECOP I y II…');
 try{
  const r=await fetch(API+'/api/croma/search',{method:'POST',headers:{'Content-Type':'application/json','X-SECOP-Access':token},cache:'no-store',signal:AbortSignal.timeout(95000),body:JSON.stringify({document:documentId,representative_document:clean(representativeId)||undefined,platform:choice==='i'?'secop_i':choice==='ii'?'secop_ii':'any'})});
  const data=await r.json();if(serial!==requestId||!enabled)return;
  if(!r.ok)throw Error(data.error||'Fallo del servidor Croma');
  render(data);
 }catch(e){if(serial===requestId&&enabled){last=null;status('Contraste Croma no completado: '+clean(e.message||'Error de conexión')+'. La consulta SECOP permanece independiente.')}}
}
function create(){
 const form=$('searchForm'),trace=$('trace');if(!form||!trace||!C)return;
 const settings=elt('details','croma-settings');
 settings.innerHTML='<summary>Conexión opcional con Croma (desactivada)</summary><p class="micro">Sirve únicamente para contrastar contratos; no sustituye los resultados ni añade contratos automáticamente. No se conecta a Croma mientras esté desactivada.</p><label class="check" for="cromaEnabled"><input type="checkbox" id="cromaEnabled"> Habilitar contraste independiente con Croma</label><div id="cromaAuthArea" hidden><label for="cromaAccess">Clave privada del buscador (NO la clave API de Croma)</label><input id="cromaAccess" type="password" autocomplete="off" spellcheck="false" placeholder="Clave privada configurada en Render"><p class="micro">Se usa solo para la consulta que autorice; no se guarda en el navegador ni se incluye en el informe.</p><button type="button" class="croma-run outline" id="cromaRun">Contrastar este NIT ahora</button></div>';
 const more=form.parentElement?.querySelector('.more');
 if(more)more.insertAdjacentElement('afterend',settings);else form.insertAdjacentElement('afterend',settings);
 const section=elt('section','panel croma-panel');section.id='cromaSection';section.hidden=true;
 section.innerHTML='<div class="section-label">07 / Contraste complementario</div><h2>Croma · Comparación opcional</h2><p class="hint">Resultados de consulta complementaria. No se mezclan con contratos individualizados ni con participación plural acreditada en SECOP. Fechas y estados requieren verificación de su fuente.</p><div id="cromaStatus" class="context" role="status" aria-live="polite">Active Croma para consultar.</div><div class="bucket-grid"><section class="bucket"><header><strong>Contratos asociados al NIT</strong></header><div id="cromaDirect" class="results"><div class="empty">Sin contraste aún.</div></div></section><section class="bucket"><header><strong>Coincidencias por representante · no atribuibles</strong></header><div id="cromaRepresentative" class="results"><div class="empty">Sin contraste aún.</div></div></section></div>';
 trace.insertAdjacentElement('afterend',section);
 $('cromaEnabled').addEventListener('change',async e=>{
  if(!e.target.checked){disable();settings.querySelector('summary').textContent='Conexión opcional con Croma (desactivada)';return}
  enabled=true;$('cromaAuthArea').hidden=false;$('cromaSection').hidden=false;
  settings.querySelector('summary').textContent='Conexión opcional con Croma (habilitada)';
  status('Verificando disponibilidad del servicio opcional…');await health();
 });
 $('cromaRun').addEventListener('click',()=>start($('identifier').value,$('representativeId')?.value||'',$('platform')?.value||'both'));
}
create();
root.SecopCroma={start,health,isEnabled:()=>enabled,getState:()=>enabled?last:null};
})(typeof window!=='undefined'?window:globalThis);
