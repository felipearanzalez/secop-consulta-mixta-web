'use strict';
const assert = require('node:assert/strict');
const {identity, idMatch, discover} = require('../app.js');
const nit = identity('900317964-1','NIT');
assert.equal(idMatch(nit,'9003179641'),true);
const groups=Array.from({length:354},(_,i)=>({codigo_grupo:String(720000000+i),nombre_grupo:'CONSORCIO GRUPO '+i,nit_participante:'9003179641',codigo_participante:'701552218',nombre_participante:'IES INGENIEROS SAS',participacion:'50',nit_grupo:'No Definido'}));
const huila={codigo_grupo:'721933083',nombre_grupo:'CONSORCIO REHABILITACION IP',nit_participante:'9003179641',codigo_participante:'701552218',nombre_participante:'IES INGENIEROS SAS',participacion:'90',nit_grupo:'901752142'};
const buca={codigo_grupo:'722004421',nombre_grupo:'CONSORCIO LA VICTORIA II',nit_participante:'9003179641',codigo_participante:'701552218',nombre_participante:'IES INGENIEROS SAS',participacion:'40',nit_grupo:'901728026'};
groups[271]=huila;groups[272]=buca;
const contracts=[
 {id_contrato:'CO1.PCCNTR.5365625',nombre_entidad:'GOBERNACION DEL HUILA*',referencia_del_contrato:'1554 DE 2023',estado_contrato:'Suspendido',fecha_de_inicio_del_contrato:'2024-04-01T00:00:00.000',fecha_de_fin_del_contrato:'2024-11-28T00:00:00.000',codigo_proveedor:'721933083',documento_proveedor:'901752142',proveedor_adjudicado:'CONSORCIO REHABILITACION IP',valor_del_contrato:'5947664432'},
 {id_contrato:'CO1.PCCNTR.5151026',nombre_entidad:'MUNICIPIO DE BUCARAMANGA',referencia_del_contrato:'184 de 2023',estado_contrato:'Suspendido',fecha_de_inicio_del_contrato:'2023-08-08T00:00:00.000',fecha_de_fin_del_contrato:'2026-09-20T00:00:00.000',codigo_proveedor:'722004421',documento_proveedor:'901728026',proveedor_adjudicado:'CONSORCIO LA VICTORIA II',valor_del_contrato:'12918441253.19'}];
const direct=[{id_contrato:'CO1.PCCNTR.1559830',codigo_proveedor:'701552218',documento_proveedor:'9003179641',proveedor_adjudicado:'IES INGENIEROS SAS',estado_contrato:'Modificado',fecha_de_inicio_del_contrato:'2020-07-01T00:00:00.000',fecha_de_fin_del_contrato:'2021-01-02T00:00:00.000',nombre_entidad:'GOBERNACION DE CALDAS'}, {id_contrato:'CO1.PCCNTR.3587164',codigo_proveedor:'701552218',documento_proveedor:'9003179641',proveedor_adjudicado:'IES INGENIEROS SAS',estado_contrato:'Modificado',fecha_de_inicio_del_contrato:'2022-06-29T00:00:00.000',fecha_de_fin_del_contrato:'2024-09-27T00:00:00.000',nombre_entidad:'GOBERNACION DE NARIÑO'}];
let groupQueries=0, compositionStarted=0, progressContractAt=-1, firstCompositionAt=-1;
const tasks=[];
const data={tasks,update(){},async filter(ds,checks,label,{limit}={}){
 let result=[];let fail=false;
 if(ds==='qmzu-gj57')result=[{nit:'9003179641',codigo:'701552218'}];
 if(ds==='ceth-n4bn' && checks.some(([k])=>k==='nit_participante'))result=groups;
 if(ds==='ceth-n4bn' && checks.some(([k])=>k==='codigo_grupo')){
  compositionStarted++;if(firstCompositionAt<0)firstCompositionAt=groupQueries;
  const codes=checks.find(x=>x[0]==='codigo_grupo')[1];result=groups.filter(x=>codes.includes(x.codigo_grupo));
 }
 if(ds==='jbjy-vk9h'){
  const c=checks.find(x=>x[0]==='codigo_proveedor')?.[1]||[];
  if(checks.some(x=>x[0]==='documento_proveedor'))result=direct;
  else{
   groupQueries++;
   if(c.includes('721933083')&&c.length>25)fail=true; // upstream error: force recursive small-batch recovery
   else result=contracts.filter(x=>c.includes(x.codigo_proveedor));
  }
 }
 const t={source:ds,label,status:fail?'failed':'ok',error:fail?'HTTP 429':null,count:result.length,truncated:false};tasks.push(t);
 return fail?[]:result;
 }};
(async()=>{
 const output=await discover(nit,{platform:'both',historical:false,similar:false,onProgress:(report,stage)=>{if(stage.includes('Contratos plurales acreditados') && progressContractAt<0 && report.plural.length>=2)progressContractAt=groupQueries}},data);
 assert.equal(output.groups.length,354);
 assert.equal(output.individual.length,2);
 assert.equal(output.plural.length,2,'Both contract IDs must survive a failed large-batch query');
 assert.deepEqual(output.plural.map(x=>x.contractId).sort(),['CO1.PCCNTR.5151026','CO1.PCCNTR.5365625']);
 assert.deepEqual(output.plural.map(x=>x.state),['Suspendido','Suspendido']);
 assert.deepEqual(output.plural.map(x=>x.end).sort(),['2024-11-28T00:00:00.000','2026-09-20T00:00:00.000']);
 assert(progressContractAt>0 && firstCompositionAt>progressContractAt,'Contracts must be available before expensive composition requests');
 assert(tasks.some(x=>x.status==='failed'), 'Failed large-batch query must be explicitly registered');
 console.log('PASS: NIT 900317964-1 | 354 memberships | 2 II individual | 2 II plural official references recovered after simulated batch HTTP429');
 console.log('PASS: status Suspendido preserved, dates preserved, partial incidents traced, contracts prioritized before composition');
})().catch(e=>{console.error(e);process.exitCode=1});
