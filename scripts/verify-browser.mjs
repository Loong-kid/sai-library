import {createRequire} from 'node:module';
import {mkdirSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';
const require=createRequire(new URL('../artifacts/qa/package.json',import.meta.url));
const {chromium}=require('playwright-core');
const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
mkdirSync(new URL('../artifacts/qa/screenshots/',import.meta.url),{recursive:true});
const failures=[];
try{
  for(const viewport of [{width:1440,height:1000},{width:390,height:844},{width:844,height:390}]){
    const page=await browser.newPage({viewport,deviceScaleFactor:1});
    page.on('pageerror',error=>failures.push(error.message));
    await page.goto('http://127.0.0.1:4173/#/read/advanced-holdem/0');
    await page.locator('[data-view-figure="p18-draws"]').waitFor();
    await page.evaluate(()=>document.fonts.ready);
    assert.equal(await page.locator('#prose .figure-table').count(),2);
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'No horizontal page overflow');
    // Every diagram control must fit in its CSS column and be reachable by turns.
    const geometry=await page.locator('#prose .reading-figure').evaluateAll(figures=>figures.map(f=>({height:f.getBoundingClientRect().height,available:document.querySelector('#prose').clientHeight})));
    for(const box of geometry)assert.ok(box.height<=box.available+1,`Figure fits ${viewport.width}x${viewport.height}: ${JSON.stringify(box)}`);
    await page.evaluate(()=>document.querySelector('[data-view-figure="p18-draws"]').click());
    await page.locator('#figure-dialog[open]').waitFor();
    assert.equal(await page.locator('#figure-frame tbody tr').count(),4);
    await page.locator('#figure-zoom').click();
    await page.locator('#figure-source').click();
    await page.locator('#source-dialog[open]').waitFor();
    await page.locator('#source-image').evaluate(img=>img.decode());
    await page.locator('#source-dialog .close-dialog').click();
    await page.goto('http://127.0.0.1:4173/#/read/advanced-holdem/120');
    await page.locator('#prose .figure-image').first().waitFor();
    await page.locator('#prose .figure-image').evaluateAll(imgs=>Promise.all(imgs.map(img=>img.decode())));
    await page.evaluate(()=>{document.querySelector('[data-mode="scroll"]').click();document.querySelectorAll('dialog[open]').forEach(d=>d.close())});
    await page.screenshot({path:fileURLToPath(new URL(`../artifacts/qa/screenshots/reading-${viewport.width}.png`,import.meta.url)),fullPage:true});
    await page.locator('[data-view-figure]').first().click();
    await page.locator('#figure-dialog[open]').waitFor();
    await page.locator('#figure-frame img').evaluate(img=>img.decode());
    const fits=await page.locator('#figure-dialog').evaluate(d=>{const r=d.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth+1&&r.top>=0&&r.bottom<=innerHeight+1});
    assert.ok(fits,'Figure dialog stays inside viewport');
    await page.screenshot({path:fileURLToPath(new URL(`../artifacts/qa/screenshots/figure-${viewport.width}.png`,import.meta.url))});
    await page.close();
  }
  assert.deepEqual(failures,[]);
  console.log('PASS: Chromium desktop, mobile and landscape; column figure geometry, source comparison, image decoding, scroll reading, dialog bounds.');
}finally{await browser.close()}
