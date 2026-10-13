"""Browser smoke test with deterministic mock data, no claims about live Socrata APIs."""
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import os
import threading
from playwright.sync_api import sync_playwright
from index27.store import Store
ROOT=Path(__file__).resolve().parents[1]
old=os.getcwd();os.chdir(ROOT)
server=ThreadingHTTPServer(('127.0.0.1',0),lambda *x,**y:SimpleHTTPRequestHandler(*x,**y))
threading.Thread(target=server.serve_forever,daemon=True).start()
# SQLite source fixture returned through mocked Render API only.
store=Store('sqlite:///:memory:');store.create_schema();store.import_cases(ROOT/'index27/verified_cases.json')
case=store.find('800143586-1')
try:
 with sync_playwright() as p:
  browser=p.chromium.launch(headless=True,executable_path="/usr/bin/chromium",args=["--no-sandbox"])
  page=browser.new_page(viewport={'width':1360,'height':940})
  errors=[]
  page.on('pageerror',lambda e:errors.append(str(e)))
  def route_handler(route):
   url=route.request.url
   if url.startswith('https://secop-indice-ligero-api.onrender.com/api/index/search?nit='):
    route.fulfill(status=200,content_type='application/json',body=json.dumps({'status':'ok',**case}))
   elif 'datos.gov.co' in url or 'secop-croma-bridge' in url:
    route.fulfill(status=200,content_type='application/json',body='[]')
   else:route.continue_()
  page.route('**/*',route_handler)
  page.set_content((ROOT/'index.html').read_text(),wait_until='domcontentloaded')
  page.add_style_tag(content=(ROOT/'styles.css').read_text())
  page.add_script_tag(content=(ROOT/'app.js').read_text())
  page.locator('#identifier').fill('800143586-1')
  page.locator('#searchButton').click()
  page.wait_for_timeout(1000)
  panel=page.locator('#documentIndex27')
  print('browser errors',errors[:4],'exists',panel.count(),'hidden',panel.get_attribute('hidden') if panel.count() else '-')
  print('search status',page.locator('#status').inner_text()[:300])
  assert panel.is_visible(), 'Panel not visible'
  assert panel.get_by_text('CONSORCIO MATEPANTANO MYM').count()==1
  assert panel.get_by_text('MEYAN S.A.').count()==1
  assert '10 %' in panel.inner_text()
  assert 'sin verificar' in panel.inner_text().lower()
  assert panel.locator('a').count()==3
  print('UI OK. Contract displayed; three evidence links; independent SECOP UI.')
  if errors: raise RuntimeError(str(errors))
  (ROOT/'tests'/'pilot27_mock.png').write_bytes(page.screenshot(full_page=False))
  # Cloud index not configured yet: the verified documentary pilot remains visible.
  page.route('https://secop-indice-ligero-api.onrender.com/**',lambda route:route.fulfill(status=503,content_type='application/json',body='{"error":"Configuracion pendiente"}'))
  page.locator('#searchButton').click()
  page.wait_for_timeout(450)
  assert 'CONSORCIO MATEPANTANO MYM' in panel.inner_text()
  assert 'remoto pendiente' in panel.inner_text().lower()
  page.set_viewport_size({'width':390,'height':844})
  (ROOT/'tests'/'pilot27_mobile.png').write_bytes(page.screenshot(full_page=False))
  print('Fallback offline y vista movil OK')
  browser.close()
finally:
 store.close();server.shutdown();server.server_close();os.chdir(old)
