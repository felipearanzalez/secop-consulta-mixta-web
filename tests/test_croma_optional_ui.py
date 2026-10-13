import json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
urls=[];headers=[];errors=[]
mock={'direct':{'records':[{'provider_name':'MEYAN S.A.','platform':'secop_i','contract_id':'17-1-169268','reference':'377-05','start_date':'2021-02-01','end_date':'2024-02-01','status':'Liquidado','value':'1500000000','process_reference':'17-1-169268','entity_name':'Gobernacion'}], 'total_reported':1,'count_returned':1,'as_of':'2026-10-13','truncated':False},'representative_candidates':None}
try:
 with sync_playwright() as p:
  browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
  page=browser.new_page(viewport={'width':1365,'height':920})
  page.on('pageerror',lambda e:errors.append(str(e)))
  def fake(route):
   request=route.request;u=request.url
   if 'secop-croma-bridge.onrender.com' in u:
    urls.append(u);headers.append({k:v for k,v in request.headers.items() if 'secop' in k})
    if u.endswith('/health'):route.fulfill(status=200,content_type='application/json',body=json.dumps({'status':'ok','configured':True}));return
    if '/api/croma/search' in u:route.fulfill(status=200,content_type='application/json',body=json.dumps(mock));return
   if 'secop-indice-ligero-api.onrender.com' in u:
    if '/health' in u:route.fulfill(status=200,content_type='application/json',body='{"status":"ok","contract_records":1,"documents_stored":0}');return
    route.fulfill(status=200,content_type='application/json',body='{"status":"ok","contracts":[],"indicators":[]}');return
   if 'datos.gov.co' in u:
    if '/api/views/' in u:route.fulfill(status=200,content_type='application/json',body='{"columns":[]}');return
    route.fulfill(status=200,content_type='application/json',body='[]');return
   route.continue_()
  page.route('**/*',fake)
  page.set_content((ROOT/'index.html').read_text(encoding='utf-8'),wait_until='domcontentloaded')
  page.add_style_tag(content=(ROOT/'styles.css').read_text(encoding='utf-8'))
  page.add_script_tag(content=(ROOT/'app.js').read_text(encoding='utf-8'))
  assert page.locator('#cromaEnabled').count()==1
  assert not page.locator('#cromaEnabled').is_checked()
  assert page.locator('#cromaSection').is_hidden()
  assert not urls, 'Network should not contact Croma on first load'
  # User explicitly chooses the optional comparison; health check but no contract lookup yet.
  page.locator('.croma-settings summary').click()
  assert not urls, 'Opening details must not contact Croma'
  page.locator('#cromaEnabled').check()
  page.wait_for_timeout(200)
  assert len(urls)==1 and urls[0].endswith('/health'),urls
  assert page.locator('#cromaAuthArea').is_visible()
  assert page.locator('#cromaSection').is_visible()
  page.locator('#identifier').fill('800143586-1')
  page.locator('#cromaAccess').fill('A'*30)
  page.locator('#cromaRun').click()
  page.wait_for_function('document.querySelector("#cromaDirect .record")!==null',timeout=8000)
  assert any('/api/croma/search' in u for u in urls),urls
  assert 'MEYAN S.A.' in page.locator('#cromaDirect').inner_text()
  assert '2021-02-01' in page.locator('#cromaDirect').inner_text()
  assert page.locator('#cromaDirect a').first.get_attribute('href').startswith('https://www.contratos.gov.co/')
  assert page.locator('#cromaSection').bounding_box()['y'] > page.locator('#trace').bounding_box()['y'], 'Croma must be after main sources'
  assert not page.locator('#cromaAccess').get_attribute('value'), 'Password must not be hardcoded into DOM'
  assert page.evaluate('window.SecopCroma.isEnabled()')
  assert page.evaluate('window.SecopCroma.getState().direct.count_returned')==1
  # Turning off must both hide and clear the returned data and password.
  page.locator('#cromaEnabled').uncheck()
  assert page.locator('#cromaSection').is_hidden()
  assert page.locator('#cromaAccess').input_value()==''
  assert page.evaluate('window.SecopCroma.getState()') is None
  count=len(urls)
  page.locator('#searchButton').click()
  page.wait_for_timeout(1350)
  assert len(urls)==count, 'Main SECOP submission must never call Croma when disabled'
  assert page.locator('#executionSection').count()==1
  assert page.locator('#contractSection').count()==1
  assert page.locator('#participationSection').count()==1
  assert page.locator('#documentIndex27').count()==1
  assert page.locator('#executionSection').bounding_box()['y']<page.locator('#contractSection').bounding_box()['y']<page.locator('#documentIndex27').bounding_box()['y']<page.locator('#participationSection').bounding_box()['y']
  assert not errors,errors
  browser.close()
 print('PASS: optional off by default; no off-network; manual GET+POST; independent source, dates and order; off disables and clears; main search unaffected')
 print('Croma requests made:',len(urls))
except Exception as e:
 print('browser errors:',errors[:6]);raise
finally:
 pass
