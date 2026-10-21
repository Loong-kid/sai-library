import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import assert from 'node:assert/strict';
const require=createRequire(new URL('../artifacts/qa/package.json',import.meta.url));
const {JSDOM,VirtualConsole}=require('jsdom');
const html=readFileSync(new URL('../dist/index.html',import.meta.url),'utf8');
const errors=[];
const vc=new VirtualConsole();vc.on('jsdomError',e=>errors.push(e.message));
const dom=new JSDOM(html,{url:'http://127.0.0.1:4173/sai-library/',runScripts:'outside-only',pretendToBeVisual:true,virtualConsole:vc});
const w=dom.window;
w.matchMedia=()=>({matches:false});
w.fetch=url=>{
  const resolved=new URL(url,w.location.href);
  assert.ok(resolved.pathname.startsWith('/sai-library/'),`Asset must stay under the project path: ${resolved.pathname}`);
  resolved.pathname=resolved.pathname.slice('/sai-library'.length);
  return fetch(resolved);
};
for(const asset of w.document.querySelectorAll('script[src],link[href]')){
  const resolved=new URL(asset.getAttribute('src')||asset.getAttribute('href'),w.location.href);
  if(resolved.origin===w.location.origin)assert.ok(resolved.pathname.startsWith('/sai-library/'));
}
Object.defineProperty(w.document,'fonts',{value:{ready:Promise.resolve()}});
w.scrollTo=()=>{};w.scrollBy=()=>{};
w.HTMLElement.prototype.scrollIntoView=function(){};
w.HTMLDialogElement.prototype.showModal=function(){this.setAttribute('open','')};
w.HTMLDialogElement.prototype.close=function(){this.removeAttribute('open')};
Object.defineProperty(w.HTMLElement.prototype,'clientWidth',{get(){return this.id==='page-viewport'?680:0}});
Object.defineProperty(w.HTMLElement.prototype,'scrollWidth',{get(){return this.id==='prose'?2936:0}});
w.eval(readFileSync(new URL('../dist/app.js',import.meta.url),'utf8')+'\nwindow.testState=()=>({book,chapter,chapterIndex,page,pageCount,settings,progress,bookmarks,catalog});');
const $=s=>w.document.querySelector(s);
let figureCount=0,tableCount=0;
async function until(fn,label){for(let i=0;i<150;i++){if(fn())return;await new Promise(r=>setTimeout(r,20))}throw Error('Timed out: '+label)}
await until(()=>$('.book-card'),'catalog');
assert.equal(w.document.querySelectorAll('.book-card').length,3);
assert.equal(w.testState().catalog.reduce((n,b)=>n+b.chapters.length,0),443);
for(const b of w.testState().catalog){
  let words=0;
  for(const c of b.chapters){
    const data=JSON.parse(readFileSync(new URL(`../dist/books/${b.id}/${c.id}.json`,import.meta.url),'utf8'));
    assert.ok(data.paragraphs.length>0&&data.words>0,`Nonempty section: ${b.id}/${c.id}`);
    assert.equal(data.title,c.title);words+=data.words;
    if(data.sourceImage){
      assert.equal(data.sourcePage,c.id+18);
      assert.ok(readFileSync(new URL(`../dist/${data.sourceImage.slice(2)}`,import.meta.url)).length>0);
      assert.ok(data.capturedAt);
      const ids=new Set();
      for(const f of data.figures||[]){
        assert.ok(!ids.has(f.id));ids.add(f.id);figureCount++;
        assert.equal(f.sourcePage,data.sourcePage);
        assert.ok(Number.isInteger(f.beforeParagraph)&&f.beforeParagraph>=0&&f.beforeParagraph<=data.paragraphs.length,`Figure anchor: ${f.id}`);
        for(const index of f.replaces||[])assert.ok(index>=0&&index<data.paragraphs.length);
        if(f.headers){tableCount++;assert.ok(f.rows.length);for(const row of f.rows)assert.equal(row.length,f.headers.length)}
        else{
          assert.match(f.src,/^\.\/books\/advanced-holdem\/figures\/[a-z\d-]+\.svg$/);
          const svg=readFileSync(new URL(`../dist/${f.src.slice(2)}`,import.meta.url),'utf8');
          assert.match(svg,/<svg /);assert.doesNotMatch(svg,/<image|<script|data:image|https?:\/\/[^w]/i);
          assert.ok(f.width>0&&f.height>0);
        }
      }
    }
  }
  assert.equal(words,b.words);
}
assert.equal(figureCount,319);assert.equal(tableCount,6);
$('#library-search').value='Chugong';$('#library-search').dispatchEvent(new w.Event('input'));assert.equal(w.document.querySelectorAll('.book-card').length,1);
$('#library-search').value='';$('#library-search').dispatchEvent(new w.Event('input'));
$('[data-open-book="sherlock-holmes"]').click();
await until(()=>w.testState().chapter?.paragraphs?.length,'open Holmes');
await until(()=>w.testState().pageCount>1,'pagination layout');
assert.match($('#prose').textContent,/In the year 1878/);
assert.equal($('#library').hidden,true);
assert.equal(w.document.documentElement.onclick,null,'Theme handler must never bind to root');
$('#next-page').click();assert.equal(w.testState().page,1);
$('#bookmark-toggle').click();assert.equal(w.testState().bookmarks.length,1);
$('#bookmark-toggle').click();assert.equal(w.testState().bookmarks.length,0);
$('#bookmark-toggle').click();
$('#settings-open').click();assert.equal($('#settings-dialog').open,true);
$('button[data-theme="dark"]').click();assert.equal(w.document.documentElement.dataset.theme,'dark');
$('#font-larger').click();assert.equal(w.testState().settings.fontSize,22);
$('button[data-mode="scroll"]').click();await until(()=>w.document.body.classList.contains('scroll-mode'),'scroll mode');
$('button[data-mode="pages"]').click();
$('#settings-dialog .close-dialog').click();
$('#toc-open').click();assert.ok(w.document.querySelectorAll('[data-go-chapter]').length>100);
$('[data-tab="bookmarks"]').click();assert.equal(w.document.querySelectorAll('[data-bookmark-id]').length,1);
$('[data-tab="search"]').click();$('#toc-search').value='Netley';$('#toc-search').dispatchEvent(new w.Event('input'));
await until(()=>$('[data-search-chapter]'),'full-text search');
assert.match($('#toc-results').textContent,/Netley/);
$('[data-search-chapter]').click();await until(()=>!$('#toc-dialog').open&&w.testState().chapter&&!$('#next-chapter').disabled,'search navigation');
$('#next-chapter').click();await until(()=>w.testState().chapterIndex===1&&w.testState().chapter,'next chapter');
$('#back-library').click();await until(()=>!$('#library').hidden,'back to shelf');
assert.equal($('#resume-section').hidden,false);
assert.ok(JSON.parse(w.localStorage.getItem('sai.progress'))['sherlock-holmes']);
$('[data-open-book="solo-leveling"]').click();await until(()=>w.testState().book?.id==='solo-leveling'&&w.testState().chapter,'open Solo');
assert.match($('#prose').textContent,/Jin-Woo had a bit of history/);
$('#toc-open').click();assert.equal(w.document.querySelectorAll('[data-go-chapter]').length,70);
$('[data-go-chapter="69"]').click();await until(()=>w.testState().chapterIndex===69&&w.testState().chapter,'last chapter');
assert.equal($('#next-chapter').disabled,true);
assert.doesNotMatch($('#prose').textContent,/Download all your fav|RnD Novels/);
assert.equal($('#source-open').hidden,true);
$('#back-library').click();await until(()=>!$('#library').hidden,'return to shelf');
$('#library-search').value='상어책';$('#library-search').dispatchEvent(new w.Event('input'));
assert.equal(w.document.querySelectorAll('.book-card').length,1);
$('[data-open-book="advanced-holdem"]').click();await until(()=>w.testState().book?.id==='advanced-holdem'&&w.testState().chapter,'open photographed book');
await until(()=>!$('#next-chapter').disabled,'photo reader layout');
assert.match($('#prose').textContent,/Gutshots are far more important/);
assert.match($('#prose').textContent,/9♥-8♦/);
assert.equal(w.document.querySelectorAll('#prose .figure-table').length,2);
assert.equal($('#paragraph-0'),null,'Rebuilt table replaces duplicate OCR paragraphs');
$('[data-view-figure="p18-draws"]').click();assert.equal($('#figure-dialog').open,true);
assert.equal(w.document.querySelectorAll('#figure-frame tbody tr').length,4);
assert.match($('#figure-frame').textContent,/Set to full house/);
$('#figure-zoom').click();assert.ok($('#figure-frame').classList.contains('zoomed'));
$('#figure-source').click();assert.equal($('#figure-dialog').open,false);assert.equal($('#source-dialog').open,true);
$('#source-dialog .close-dialog').click();
assert.ok($('.ocr-note'));assert.equal($('#source-open').hidden,false);
assert.match($('#chapter-label').textContent,/18쪽/);
$('#source-open').click();assert.equal($('#source-dialog').open,true);
assert.match($('#source-image').src,/sai-library\/books\/advanced-holdem\/pages\/001.webp$/);
assert.equal($('#source-prev').disabled,true);
$('#source-zoom').click();assert.ok($('#source-frame').classList.contains('zoomed'));
$('#source-next').click();assert.match($('#source-caption').textContent,/19쪽/);
assert.match($('#source-image').src,/002.webp$/);
assert.ok(!$('#source-frame').classList.contains('zoomed'));
$('#source-read').click();await until(()=>w.testState().chapterIndex===1&&w.testState().chapter&&!$('#next-chapter').disabled,'read source page 19');
assert.equal($('#source-dialog').open,false);
assert.equal(w.document.querySelectorAll('#prose tbody tr').length,13);
assert.match($('#prose tbody tr:last-child').textContent,/2042.55%43.48%67.53%/);
$('#toc-open').click();$('[data-tab="search"]').click();$('#toc-search').value='67.53%';$('#toc-search').dispatchEvent(new w.Event('input'));
await until(()=>$('[data-search-chapter]'),'table numeric search');
$('[data-search-chapter]').click();await until(()=>!$('#toc-dialog').open&&$('[data-paragraph-ids~="13"]'),'search target inside table');
assert.equal(w.testState().chapterIndex,1);
$('#toc-open').click();assert.equal(w.document.querySelectorAll('[data-go-chapter]').length,255);
$('[data-tab="search"]').click();$('#toc-search').value='Snowie';$('#toc-search').dispatchEvent(new w.Event('input'));
await until(()=>$('[data-search-chapter]'),'photo OCR full-text search');
assert.match($('#toc-results').textContent,/Snowie/);
$('#toc-dialog .close-dialog').click();
w.location.hash='#/read/advanced-holdem/120';await until(()=>w.testState().chapterIndex===120&&w.testState().chapter,'diagram page');
assert.equal(w.document.querySelectorAll('#prose .reading-figure').length,2);
assert.match($('#prose .figure-image').src,/p138-1.svg$/);
$('#prose [data-view-figure]').click();assert.equal($('#figure-dialog').open,true);
assert.match($('#figure-frame img').src,/p138-1.svg$/);
$('#figure-zoom').click();assert.ok($('#figure-frame').classList.contains('zoomed'));
$('#figure-frame img').dispatchEvent(new w.Event('error'));assert.match($('#figure-frame').textContent,/불러오지 못했습니다/);
$('#figure-source').click();assert.match($('#source-caption').textContent,/138쪽/);
$('#source-dialog .close-dialog').click();
w.location.hash='#/read/advanced-holdem/25';await until(()=>w.testState().chapterIndex===25&&w.testState().chapter,'prose-only page');
assert.equal(w.document.querySelectorAll('#prose .reading-figure').length,0,'Chapter heading is not a figure');
w.location.hash='#/read/advanced-holdem/254';await until(()=>w.testState().chapterIndex===254&&w.testState().chapter,'last photographed page');
$('#source-open').click();assert.equal($('#source-next').disabled,true);
assert.match($('#source-caption').textContent,/272쪽/);
$('#source-image').dispatchEvent(new w.Event('error'));assert.equal($('#source-error').hidden,false);
$('#source-prev').click();assert.equal($('#source-error').hidden,true);
assert.match($('#source-caption').textContent,/271쪽/);
$('#source-dialog .close-dialog').click();
assert.deepEqual(errors,[]);
console.log('PASS: 3 books, 443 sections, 319 figures (6 semantic tables), all figure/image assets and anchors, table search, figure zoom and original comparison, reading features, source navigation and error handling.');
console.log('DOM-only suite; run scripts/verify-browser.mjs for Chromium rendering and mobile geometry.');
dom.window.close();
