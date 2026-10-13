from pathlib import Path
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
html=(root/'index.html').read_text()
css=(root/'styles.css').read_text()
js=(root/'app.js').read_text()
with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1365,'height':900})
    errors=[]
    page.on('pageerror',lambda err: errors.append(str(err)))
    page.set_content(html,wait_until='domcontentloaded')
    page.add_style_tag(content=css)
    page.add_script_tag(content=js)
    assert not errors,errors
    assert page.locator('#extended26Section').count()==1
    assert page.locator('#extended26Awards').count()==1
    assert page.locator('#extended26Bids').count()==1
    assert page.locator('#cromaSection').count()==0
    assert page.locator('.croma-settings').count()==0
    assert page.locator('#executionSection').count()==1
    assert page.locator('#contractSection').count()==1
    assert page.locator('#candidateSection').count()==1
    assert page.locator('input#identifier').count()==1
    assert page.locator('#extended26Section').evaluate('(el)=>el.getBoundingClientRect().top') < page.locator('#candidateSection').evaluate('(el)=>el.getBoundingClientRect().top')
    assert page.locator('.mast-tag').inner_text().find('2.6')>=0
    page.screenshot(path=str(root/'tests/web_2_6_desktop.png'),full_page=True)
    print('PASS: no JS errors; 2.6 main layout, SECOP extensions, no Croma UI, correct order')
    browser.close()
