const assert=require('node:assert/strict');
const path=require('node:path');
const root=path.join(__dirname,'..');
const C=require(path.join(root,'app.js'));
const X=global.SecopExtended26;
assert(X,'Coverage module loaded');
const id=C.identity('800143586-1');
const group={code:'736416603',name:'CONSORCIO ARTEMIS 2',nit:'902000111',composition:[{nit_participante:'800143586',participacion:'90'}]};
const core={groups:[group],individual:[{platform:'II',contractId:'CO1.PCCNTR.500',sourceRow:{proceso_de_compra:'CO1.BDOS.101',codigo_proveedor:'702667247',documento_proveedor:'800143586'}}],plural:[{platform:'II',contractId:'CO1.PCCNTR.501',sourceRow:{proceso_de_compra:'CO1.BDOS.102',codigo_proveedor:'736416603',documento_proveedor:'902000111'}}]};
const accounts=[{nit:'800143586',codigo:'702667247'}];
const process=(id,portfolio,award,group=false,extra={})=>({id_del_proceso:'CO1.REQ.'+id,id_del_portafolio:'CO1.BDOS.'+portfolio,referencia_del_proceso:'LP-'+id,adjudicado:award?'Si':'No',id_adjudicacion:award?'CO1.AWD.'+id:'No Adjudicado',codigoproveedor:group?'736416603':'702667247',nit_del_proveedor_adjudicado:group?'902000111':'800143586',nombre_del_proveedor:group?'CONSORCIO ARTEMIS 2':'MEYAN S.A.',entidad:'ALCALDIA',estado_del_procedimiento:'Seleccionado',fecha_adjudicacion:'2026-06-15T00:00:00',valor_total_adjudicacion:500000,modalidad_de_contratacion:'Contratación régimen especial',urlproceso:{url:'https://community.secop.gov.co/Public/Tendering/OpportunityDetail/Index?noticeUID=CO1.NTC.'+id},...extra});
const bidder=(id,code='702667247',name='MEYAN S.A.',nit='800143586')=>({id_procedimiento:'CO1.REQ.'+id,proveedor:name,nit_proveedor:nit,codigo_proveedor:code,entidad_compradora:'ALCALDIA',nombre_procedimiento:'Procedimiento de obra',fecha_publicaci_n:'2026-08-01T00:00:00'});
const rows={
'p6dx-8zbt':[
 process('101','101',true),    // electronically signed: NOT additional award
 process('102','102',true,true), // electronically signed group: NOT additional award
 process('103','103',true),    // NEW award no signed record
 process('104','104',true,true),// NEW group award
 process('105','105',false),   // related process but no award
 process('106','106',true,false,{nombre_del_proveedor:'UNION TEMPORAL FALSO 2026'}) // ambiguous group incorrectly linked to individual NIT
],
'hgi6-6wh3':[
 bidder('103'),              // already in awards, not duplicate
 bidder('107'),              // new bid only
 bidder('108','736416603','CONSORCIO ARTEMIS 2','902000111'), // group bidder
 bidder('109','702667247','CONSORCIO DESCONOCIDO','800143586'), // ambiguous
 bidder('999','9999999','OTRA EMPRESA','999999999'), // unrelated
 bidder('107') // duplicate bidder
]
};
const jobs=[];
const transport={tasks:jobs,async filter(ds,checks,label){jobs.push({source:ds,label,status:'ok',count:0,truncated:false});const output=(rows[ds]||[]).filter(row=>checks.some(([field,vals])=>vals.map(String).includes(String(row[field]))));jobs[jobs.length-1].count=output.length;return output;}};
async function run(){
 let found=await X.lookup(id,core,accounts,transport,{});
 assert.equal(found.awards.length,2);assert.equal(found.linkedElectronic.length,2);assert.equal(found.otherProcesses.length,1);
 assert.equal(found.bids.length,2);assert.equal(found.uncertain.length,2);
 assert.deepEqual(found.awards.map(x=>x.reference).sort(),['LP-103','LP-104']);
 assert(found.awards.some(x=>x.kind==='plural'&&x.group==='CONSORCIO ARTEMIS 2'));
 assert(!found.awards.some(x=>x.reference==='LP-101'));
 assert(!found.awards.some(x=>x.reference==='LP-102'));
 assert(!found.bids.some(x=>x.processId==='CO1.REQ.103'));
 assert(found.bids.some(x=>x.processId==='CO1.REQ.108'&&x.kind==='plural'));
 assert(found.awards.every(x=>x.statusNote.includes('no acredita')));
 assert.equal(X.awardReported({adjudicado:'No'}),false);
 assert.equal(X.awardReported({adjudicado:'Si'}),true);
 assert.equal(X.officialLink({url:'https://community.secop.gov.co/a'}),'https://community.secop.gov.co/a');
 assert.equal(X.officialLink({url:'https://untrusted.example/a'}),'');
 assert(X.evidenceLink({id_del_proceso:'CO1.REQ.12345'},X.PROCESS).startsWith('https://www.datos.gov.co/resource/'));
 assert.equal(X.evidenceLink({id_del_proceso:'unsafe<script>'},X.PROCESS),'');
 assert.equal(X.affiliation(id,process('110','110',true,false,{nit_del_proveedor_adjudicado:'9999999',codigoproveedor:'9999999'}),new Map(),[],{source:X.PROCESS}),null);
 assert.equal(found.sourceIds.length,2);
 const excluded=await X.lookup(id,core,accounts,transport,{platform:'i'});
 assert(excluded.skipped);assert.equal(excluded.awards.length,0);
 assert(jobs.length>=4);
 console.log('PASS: coverage sources, contract linking, award distinctness, unknown plural, ambiguous exclusion, bidder deduplication, URL checks, source exclusion (19 assertions)');
}
run().catch(e=>{console.error(e);process.exit(1)});
