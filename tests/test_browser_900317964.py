import json
from pathlib import Path
from urllib.parse import urlsplit,parse_qs,unquote
from playwright.sync_api import sync_playwright
P=Path(__file__).resolve().parents[1]
ERRORS=[]
H={'721933083':{'codigo_grupo':'721933083','nombre_grupo':'CONSORCIO REHABILITACION IP','nit_grupo':'901752142','nit_participante':'9003179641','codigo_participante':'701552218','nombre_participante':'IES INGENIEROS SAS','participacion':'90'},
   '722004421':{'codigo_grupo':'722004421','nombre_grupo':'CONSORCIO LA VICTORIA II','nit_grupo':'901728026','nit_participante':'9003179641','codigo_participante':'701552218','nombre_participante':'IES INGENIEROS SAS','participacion':'40'}}
CONTRACTS=[{'id_contrato':'CO1.PCCNTR.5365625','nombre_entidad':'GOBERNACION DEL HUILA*','referencia_del_contrato':'1554 DE 2023','estado_contrato':'Suspendido','fecha_de_firma':'2024-04-01T00:00:00.000','fecha_de_inicio_del_contrato':'2024-04-01T00:00:00.000','fecha_de_fin_del_contrato':'2024-11-28T00:00:00.000','codigo_proveedor':'721933083','documento_proveedor':'901752142','proveedor_adjudicado':'CONSORCIO REHABILITACION IP','valor_del_contrato':'5947664432'},
{'id_contrato':'CO1.PCCNTR.5151026','nombre_entidad':'MUNICIPIO DE BUCARAMANGA','referencia_del_contrato':'184 de 2023','estado_contrato':'Suspendido','fecha_de_firma':'2023-07-12T00:00:00.000','fecha_de_inicio_del_contrato':'2023-08-08T00:00:00.000','fecha_de_fin_del_contrato':'2026-09-20T00:00:00.000','codigo_proveedor':'722004421','documento_proveedor':'901728026','proveedor_adjudicado':'CONSORCIO LA VICTORIA II','valor_del_contrato':'12918441253.19'}]
DATA={"qmzu-gj57":[{'codigo':'701552218','nit':'9003179641','nombre':'IES INGENIEROS SAS'}],"ceth-n4bn":list(H.values()),"jbjy-vk9h":CONTRACTS,"f789-7hwg":[],"qddk-cgux":[],"p6dx-8zbt":[],"hgi6-6wh3":[]}
META={ds:{'columns':[{'fieldName':col,'dataTypeName':'text'} for col in {key for row in rows for key in row}]} for ds,rows in DATA.items()}

def relevant(row,where):
 if not where:return True
 # Decode SOQL; all filters in this fixture select by field and quoted integer values.
 import re
 parts=re.findall(r'([a-z_][a-z0-9_]*)\s+in\s*\(([^)]+)\)',where)
 if not parts:return False
 for field,lst in parts:
  vals=[s.strip().strip("'") for s in lst.split(',')]
  if str(row.get(field,'')) in vals:return True
 return False

with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
 page=browser.new_page(viewport={'width':1400,'height':1050})
 page.on('pageerror',lambda e: ERRORS.append(str(e)))
 def handle(route):
  u=urlsplit(route.request.url)
  if '/api/views/' in u.path:
   ds=u.path.rsplit('/',1)[-1].replace('.json','')
   route.fulfill(status=200,content_type='application/json',body=json.dumps(META.get(ds,{'columns':[]})));return
  if '/resource/' in u.path:
   ds=u.path.rsplit('/',1)[-1].replace('.json','')
   qs=parse_qs(u.query)
   rows=[x for x in DATA.get(ds,[]) if relevant(x,qs.get('$where',[''])[0])]
   limit=int(qs.get('$limit',['200'])[0]);offset=int(qs.get('$offset',['0'])[0])
   route.fulfill(status=200,content_type='application/json',body=json.dumps(rows[offset:offset+limit]));return
  if 'secop-indice-ligero-api' in u.hostname:
   route.fulfill(status=200,content_type='application/json',body='{"status":"ok","contracts":[],"indicators":[]}');return
  route.abort()
 page.route('**/*',handle)
 page.set_default_timeout(8000)
 print('Browser configured',flush=True)
 print('Setting html',flush=True)
 page.set_content((P/'index.html').read_text(encoding='utf-8'),wait_until='domcontentloaded')
 page.add_style_tag(content=(P/'styles.css').read_text(encoding='utf-8'))
 page.add_script_tag(content=(P/'app.js').read_text(encoding='utf-8'))
 print('HTML loaded',flush=True)
 page.locator('#identifier').fill('900317964-1')
 page.evaluate("document.querySelector('#similar').checked=false;document.querySelector('#historical').checked=false")
 print('Starting query',flush=True)
 page.locator('#searchButton').click()
 page.wait_for_function("document.querySelector('#status')?.textContent.includes('Consulta completada') || document.querySelector('#status')?.textContent.includes('Consulta con cobertura parcial')",timeout=12000)
 cards=page.locator('#contractIIplural .record')
 assert cards.count()==2, f'Expected two plural contract cards, found {cards.count()}: '+page.locator('#status').inner_text()
 text=page.locator('#contractIIplural').inner_text()
 for value in ['REHABILITACION IP','LA VICTORIA II','1554 DE 2023','184 de 2023','2024-04-01','2026-09-20','Suspendido','$']:
  assert value in text,(value,text[:2500])
 assert page.locator('#executionIIplural .record').count()==0, 'Suspended must not show as executing'
 assert page.locator('#contractIIpluralCount').inner_text()=='2'
 assert page.locator('#contractSection').bounding_box()['y']<page.locator('#documentIndex27').bounding_box()['y']
 assert page.locator('#cromaEnabled').is_checked() is False
 assert not ERRORS,ERRORS
 print('PASS browser SECOP v2.10: Huila & Bucaramanga are in Other Contracts/II plural, with status Suspendido, full dates, values, and official links; layout/Croma preserved')
 browser.close()
