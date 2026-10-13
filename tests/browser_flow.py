from pathlib import Path
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
html=(root/'index.html').read_text()
css=(root/'styles.css').read_text()
js=(root/'app.js').read_text()
mock=r'''window.fetch=async (url,opts={})=>{
 const u=new URL(url,'https://www.datos.gov.co');
 const schema={
 'qmzu-gj57':['nit','codigo','nombre'],
 'ceth-n4bn':['nit_participante','codigo_participante','codigo_grupo','nombre_grupo','participacion'],
 'jbjy-vk9h':['documento_proveedor','codigo_proveedor','proceso_de_compra'],
 'f789-7hwg':['identificacion_del_contratista','nom_raz_social_contratista'],
 'qddk-cgux':['identificacion_del_contratista','nom_raz_social_contratista'],
 'p6dx-8zbt':['nit_del_proveedor_adjudicado','codigoproveedor','id_del_proceso','adjudicado'],
 'hgi6-6wh3':['nit_proveedor','codigo_proveedor','id_procedimiento']};
 const rows={
 'qmzu-gj57':[{nit:'800143586',codigo:'702667247',nombre:'MEYAN S.A.'}],
 'p6dx-8zbt':[{id_del_proceso:'CO1.REQ.123450',id_del_portafolio:'CO1.BDOS.123450',adjudicado:'Si',id_adjudicacion:'CO1.AWD.12345',nombre_del_proveedor:'MEYAN S.A.',nit_del_proveedor_adjudicado:'800143586',codigoproveedor:'702667247',entidad:'ENTIDAD PRUEBA',valor_total_adjudicacion:1250000,referencia_del_proceso:'REG-TEST-2026',fecha_adjudicacion:'2026-09-01',urlproceso:{url:'https://community.secop.gov.co/Public/Tendering/OpportunityDetail/Index?noticeUID=CO1.NTC.123450'}}],
 'hgi6-6wh3':[{id_procedimiento:'CO1.REQ.999999',proveedor:'MEYAN S.A.',nit_proveedor:'800143586',codigo_proveedor:'702667247',entidad_compradora:'ENTIDAD DIFERENTE',nombre_procedimiento:'PRUEBA DE OFERTA',fecha_publicaci_n:'2026-09-11'}]};
 const code=u.pathname.match(/([a-z0-9]{4}-[a-z0-9]{4})\.json$/);
 if(!code)return {ok:false,status:404,text:async()=>'',json:async()=>({})};
 const ds=code[1];
 if(u.pathname.includes('/api/views/'))return {ok:true,status:200,json:async()=>({columns:(schema[ds]||[]).map(fieldName=>({fieldName,dataTypeName:'text'}))})};
 const where=u.searchParams.get('$where')||'';
 let filtered=(rows[ds]||[]).filter(row=>Object.entries(row).some(([field,val])=>where.includes(field)&&where.includes(String(val))));
 const offset=Number(u.searchParams.get('$offset')||0),limit=Number(u.searchParams.get('$limit')||200);
 filtered=filtered.slice(offset,offset+limit);
 return {ok:true,status:200,json:async()=>filtered,text:async()=>JSON.stringify(filtered)};
};'''
with sync_playwright() as pw:
 browser=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
 page=browser.new_page(viewport={'width':1150,'height':860})
 errors=[]
 page.on('pageerror',lambda err:errors.append(str(err)))
 page.set_content(html)
 page.add_style_tag(content=css)
 page.evaluate(mock)
 page.add_script_tag(content=js)
 page.locator('#identifier').fill('800143586-1')
 page.locator('#searchButton').click()
 page.wait_for_function("document.getElementById('status').textContent.includes('Consulta finalizada')",timeout=25000)
 print('STATUS',page.locator('#status').inner_text()[:400])
 print('AWARDS',page.locator('#extended26AwardsCount').inner_text())
 print('BIDS',page.locator('#extended26BidsCount').inner_text())
 print('CONTRACTS',page.locator('#countContracts').inner_text())
 print('ERRORS',errors)
 assert not errors, errors
 assert page.locator('#extended26AwardsCount').inner_text()=='1'
 assert page.locator('#extended26BidsCount').inner_text()=='1'
 assert page.locator('#countContracts').inner_text()=='0'
 assert page.locator('#extended26Awards').inner_text().count('REG-TEST-2026')==1
 assert page.locator('#extended26Bids').inner_text().count('PRUEBA DE OFERTA')==1
 assert not page.locator('#extended26Awards').inner_text().lower().count('en ejecución')
 assert page.locator('#auditResults').inner_text().count('p6dx-8zbt')>=1
 assert page.locator('#auditResults').inner_text().count('hgi6-6wh3')>=1
 page.screenshot(path=str(root/'tests/web_2_6_results.png'),full_page=True)
 browser.close()
