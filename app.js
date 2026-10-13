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
   for(let offset=0;offset<limit;offset+=pg){const u=new URL('/resource/'+ds+'.json',SOURCE);u.searchParams.set('$where',where);u.searchParams.set('$limit',String(Math.min(pg,limit-offset)));u.searchParams.set('$offset',String(offset));u.searchParams.set('$order',':id ASC');const resp=await this.fetcher(u.href,{headers:{Accept:'application/json'}});if(!resp.ok){let reason='';try{reason=(await resp.text()).slice(0,140)}catch{}throw Error('HTTP '+resp.status+' '+reason)}const rows=await resp.json();if(!Array.isArray(rows))throw Error('La respuesta no fue una lista');results.push(...rows);if(rows.length<Math.min(pg,limit-offset)){ended=true;break;}}
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
  for(const b of batch([...groups.keys()])){
   const components=await data.filter(DS.groups,[['codigo_grupo',b]],'Recuperar composición de grupos',{limit:1200});
   for(const r of components){const g=groups.get(txt(r.codigo_grupo));if(g)g.composition.push(selectFields(r,['codigo_participante','nit_participante','nombre_participante','participacion']))}
  }
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
  for(const ids of batch([...groups.keys()],20)){
   const contracts=await data.filter(DS.contractsII,[['codigo_proveedor',ids]],'SECOP II: contratos vinculados al código de grupo',{limit:1200});
   for(const r of contracts){const g=groups.get(txt(r.codigo_proveedor));if(g)out.plural.push(record('II',r,'Código exacto de grupo SECOP II',g));}
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
  return `<article class="record"><div class="top"><div>${badge}<h3>${display(r.contractor||r.group)}</h3><div class="muted">${display(r.reference)} · ${display(r.entity)}</div></div><div class="role">${safe(r.route)}</div></div><div class="detail-grid"><div><span>Estado publicado</span><strong>${display(r.state)}</strong></div><div><span>Inicio / fin publicados</span><strong>${safe(day(r.start))} / ${safe(day(r.end))}</strong><small>${safe(r.dateBasis||'Referencia del registro contractual')}</small></div><div><span>Identificación del contratista</span><strong>${display(r.contractorId)}</strong></div></div><div class="context ${e.level==='possible'||r.participationReason?'warning':''}">${safe(r.participationReason||e.text)}</div><details><summary>Objeto y fundamento de la vinculación</summary><p class="secondary">${objectText(r.object)}</p><p class="muted">Fuente: ${safe(r.source)}. ${safe(r.route)}. Una fecha proyectada no incorpora necesariamente suspensiones o modificaciones.</p></details><div class="links">${link(r.url,'Ver expediente contractual en SECOP')}${r.groupCode?`<a href="#gruposRegistrados">Ver composición del grupo en esta página ↓</a>`:''}</div></article>`;
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
  document.querySelector('.mast-tag').textContent='Consulta pública · Versión 2.4';
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
 $('download').addEventListener('click',e=>{e.preventDefault();e.stopImmediatePropagation();if(!latest)return;const b=new Blob([JSON.stringify(latest,null,2)],{type:'application/json'}),u=URL.createObjectURL(b),a=document.createElement('a');a.href=u;a.download='secop_verificacion_v24_'+Date.now()+'.json';document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(u),1000)},true);
 // Utilidades para pruebas automatizadas.
 window.SecopPresentation={isContractI,isContractII,executionStatus,summarize,collectContractCandidates};
})();
