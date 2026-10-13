'use strict';
const assert=require('node:assert/strict');
const {PublicData}=require('../app.js');
let attempts=new Map();
const fetching=async url=>{
 const u=new URL(url);
 if(u.pathname.startsWith('/api/views/'))return {ok:true,json:async()=>({columns:[{fieldName:'codigo_proveedor',dataTypeName:'text'}]})};
 const offset=Number(u.searchParams.get('$offset')||0),call=(attempts.get(offset)||0)+1;attempts.set(offset,call);
 if(offset===0 && call===1)return {ok:false,status:429,text:async()=> 'retry'};
 if(offset===0)return {ok:true,json:async()=>Array.from({length:200},(_,i)=>({codigo_proveedor:''+i}))};
 if(offset===200)return {ok:false,status:503,text:async()=> 'temporarily unavailable'};
 return {ok:true,json:async()=>[]};
};
(async()=>{
 const p=new PublicData({fetcher:fetching});
 const rows=await p.filter('jbjy-vk9h',[['codigo_proveedor',['721933083']]],'official group',{limit:550});
 assert.equal(rows.length,200,'Preserve first page despite failure on second page');
 assert.equal(p.tasks[0].status,'partial');
 assert.equal(p.tasks[0].count,200);
 assert.match(p.tasks[0].error,/Página 2/);
 assert.equal(attempts.get(0),2,'Retry a transient HTTP429');
 assert.equal(attempts.get(200),3,'Retry HTTP503 at most three times');
 console.log('PASS: HTTP429 retried; first page preserved when second page fails; task marked partial rather than silent zero');
})().catch(x=>{console.error(x);process.exitCode=1});
