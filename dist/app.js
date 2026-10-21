'use strict';
const dataVersion='figures-1';
const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const icons = {
  moon:'<path d="M20.5 13.1A8.5 8.5 0 0 1 10.9 3.5a8.5 8.5 0 1 0 9.6 9.6Z"/>',
  sun:'<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5"/>',
  toc:'<path d="M8 6h13M8 12h13M8 18h13M3 6h1M3 12h1M3 18h1"/>',
  bookmark:'<path d="M6 3h12v18l-6-4-6 4z"/>',
  source:'<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8" cy="8" r="1.5"/><path d="m3 17 5-5 4 4 4-6 5 7"/>'
};
const icon = name => `<svg viewBox="0 0 24 24" aria-hidden="true">${icons[name]}</svg>`;
const escapeHTML = text => String(text).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let storageOK = true;
function readStore(key,fallback){try{return JSON.parse(localStorage.getItem(key)) ?? fallback}catch{return fallback}}
function writeStore(key,value){try{localStorage.setItem(key,JSON.stringify(value))}catch{if(storageOK){storageOK=false;toast('이 브라우저에서 저장할 수 없습니다. 브라우저의 저장 공간 설정을 확인하세요.')}}}
let settings = {...{theme:matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light',fontSize:21,font:'serif',mode:'pages'},...readStore('sai.settings',{})};
if(!['light','sepia','dark'].includes(settings.theme))settings.theme='light';
if(!['serif','sans'].includes(settings.font))settings.font='serif';
if(!['pages','scroll'].includes(settings.mode))settings.mode='pages';
settings.fontSize=Math.min(32,Math.max(16,Number(settings.fontSize)||21));
let progress=readStore('sai.progress',{}), bookmarks=readStore('sai.bookmarks',[]);
let catalog=[], book=null, chapter=null, chapterIndex=0, page=0, pageCount=1, columnStep=0;
let filter='all', tocTab='contents', openToken=0, searchToken=0, saveTimer, toastTimer, resizeTimer, searchTimer;
let sourceIndex=0, sourceToken=0;
const cache = new Map(), searchCache = new Map();
function toast(message){clearTimeout(toastTimer);$('#toast').textContent=message;$('#toast').hidden=false;toastTimer=setTimeout(()=>$('#toast').hidden=true,3200)}
function applySettings(){
  document.documentElement.dataset.theme=settings.theme;
  document.documentElement.style.setProperty('--reading-size',`${settings.fontSize}px`);
  document.documentElement.style.setProperty('--reading-font',settings.font==='sans'?'var(--font-ui)':'var(--font-book)');
  document.body.classList.toggle('scroll-mode',settings.mode==='scroll');
  $('#library-theme').innerHTML=icon(settings.theme==='dark'?'sun':'moon');
  $('#library-theme').setAttribute('aria-label',settings.theme==='dark'?'낮 모드로 전환':'밤 모드로 전환');
  $('#font-size-label').value=`${settings.fontSize}px`;
  $('#font-smaller').disabled=settings.fontSize<=16;$('#font-larger').disabled=settings.fontSize>=32;
  for(const [type,value] of Object.entries({theme:settings.theme,font:settings.font,mode:settings.mode})){
    $$(`button[data-${type}]`).forEach(el=>{el.classList.toggle('selected',el.dataset[type]===value);el.setAttribute('aria-pressed',String(el.dataset[type]===value))});
  }
}
applySettings();
$('#toc-open').innerHTML=icon('toc');$('#bookmark-toggle').innerHTML=icon('bookmark');
$('#source-open').innerHTML=icon('source');
function coverHTML(b){
  if(b.id==='advanced-holdem')return `<div class="cover shark"><small>A modern approach to poker analysis</small><strong>Advanced<br>Concepts in<br>No-Limit Hold’em</strong><svg class="cover-art" viewBox="0 0 140 100" aria-hidden="true"><path d="M8 70c28-2 42-17 61-29L63 13l26 21c18-1 29 8 41 18l-20 10 13 15-28-7C66 87 32 85 8 70Z"/><path d="m34 68 19-9 4 10m28-23 3 9m5-10 3 9M14 88h108"/><circle cx="107" cy="49" r="1.5"/></svg><span class="cover-author">Hunter Cichy</span></div>`;
  return b.id==='sherlock-holmes'?`<div class="cover"><small>The complete collection</small><strong>Sherlock<br>Holmes</strong><svg class="cover-art" viewBox="0 0 120 120" aria-hidden="true"><circle cx="51" cy="48" r="30"/><circle cx="51" cy="48" r="25"/><path d="m73 71 31 32-7 7-31-32M25 67V45l9-7 10 7v30m0-2V31l8-7 9 7v43m0-1V44l8-7 10 7v23M31 50h6m-6 9h6m12-22h7m-7 10h7m-7 11h7m10-8h7m-7 10h7M17 79h62M12 85h73"/><path d="M27 20 23 13m59 18 9-4M51 8V2"/></svg><span class="cover-author">Arthur Conan Doyle</span></div>`:`<div class="cover solo"><small>Chapter 201–270</small><strong>Solo<br>Leveling</strong><svg class="cover-art" viewBox="0 0 120 130" aria-hidden="true"><path d="m20 112 4-70 36-27 36 27 4 70M30 110l3-63 27-21 27 21 3 63M40 110V52l20-16 20 16v58M47 109V57l13-10 13 10v52"/><path d="m55 98 5-42 5 42-5 16zM59 91l-11 9m13-9 11 9M14 115h92M8 121h104M13 38l-4-6m98 6 4-6M60 9V1"/><circle cx="60" cy="65" r="2"/></svg><span class="cover-author">Chugong</span></div>`;
}
function completion(b,p=progress[b.id]){if(!p)return 0;const total=b.words;const before=b.chapters.slice(0,p.chapter).reduce((n,c)=>n+c.words,0);return Math.min(100,Math.round(100*(before+(b.chapters[p.chapter]?.words||0)*(p.ratio||0))/total))}
function renderLibrary(){
  const query=$('#library-search').value.trim().toLowerCase();
  const shown=catalog.filter(b=>(filter==='all'||filter==='reading'&&progress[b.id]||filter==='marked'&&bookmarks.some(m=>m.book===b.id))&&`${b.title} ${b.author} ${b.koreanTitle} ${b.genre}`.toLowerCase().includes(query));
  $('#book-count').textContent=`${shown.length}권`;
  $('#books-grid').innerHTML=shown.length?shown.map(b=>{const p=progress[b.id];return `<article class="book-card"><div class="cover-stage"><button class="cover-link" data-open-book="${b.id}" aria-label="${escapeHTML(b.title)} ${p?'이어서 읽기':'읽기'}">${coverHTML(b)}</button></div><div class="book-meta"><p class="book-genre">${b.genre} <span aria-hidden="true">/</span> ${b.koreanTitle}</p><h3 lang="en">${b.title}</h3><p class="author" lang="en">${b.author}</p><p class="book-description">${b.description}</p><div class="book-bottom"><span class="book-detail">${b.detail}</span><button class="read-link" data-open-book="${b.id}">${p?'이어서 읽기':'책 펼치기'} <span aria-hidden="true">↗</span></button></div>${p?`<div class="mini-progress" aria-label="전체 ${completion(b)}% 읽음"><span style="width:${completion(b)}%"></span></div>`:''}</div></article>`}).join(''):`<div class="empty-state"><p>${query?'찾는 책이 없습니다. 다른 제목이나 작가 이름으로 검색해 보세요.':filter==='reading'?'아직 읽기 시작한 책이 없습니다. 책을 펼치면 여기에 표시됩니다.':'아직 책갈피가 없습니다. 독서 화면에서 책갈피를 추가해 보세요.'}</p><button id="reset-filter">모든 책 보기</button></div>`;
  const recent=catalog.filter(b=>progress[b.id]).sort((a,b)=>progress[b.id].updated-progress[a.id].updated)[0];
  $('#resume-section').hidden=!recent;
  if(recent){const p=progress[recent.id];$('#resume-section').innerHTML=`<div class="resume-copy"><span>읽던 이야기</span><h2 lang="en">${recent.shortTitle}</h2><p lang="en">${escapeHTML(recent.chapters[p.chapter]?.title||'')} · ${completion(recent)}%</p></div><button class="quiet resume-link" data-open-book="${recent.id}">이어서 읽기 <span aria-hidden="true">→</span></button>`}
}
document.addEventListener('click',e=>{
  const open=e.target.closest('[data-open-book]');if(open){const id=open.dataset.openBook;const p=progress[id];location.hash=`/read/${id}/${p?.chapter||0}`;return}
  const f=e.target.closest('[data-filter]');if(f){filter=f.dataset.filter;$$('[data-filter]').forEach(el=>{el.classList.toggle('active',el===f);el.setAttribute('aria-pressed',String(el===f))});renderLibrary()}
  if(e.target.closest('#reset-filter')){filter='all';$('#library-search').value='';$$('[data-filter]').forEach(el=>{el.classList.toggle('active',el.dataset.filter==='all');el.setAttribute('aria-pressed',String(el.dataset.filter==='all'))});renderLibrary()}
});
$('#library-search').addEventListener('input',renderLibrary);
$('#library-theme').onclick=()=>{settings.theme=settings.theme==='dark'?'light':'dark';applySettings();writeStore('sai.settings',settings)};
async function fetchChapter(b,index){const key=`${b.id}/${index}`;if(!cache.has(key)){const response=await fetch(`./books/${key}.json?v=${dataVersion}`);if(!response.ok)throw Error('본문을 불러오지 못했습니다.');cache.set(key,await response.json())}return cache.get(key)}
function currentRatio(){if(settings.mode==='pages')return pageCount<=1?0:page/(pageCount-1);const max=document.documentElement.scrollHeight-innerHeight;return max>0?Math.min(1,scrollY/max):0}
function storePosition(){if(!book||!chapter)return;progress[book.id]={chapter:chapterIndex,page,ratio:currentRatio(),mode:settings.mode,updated:Date.now()};writeStore('sai.progress',progress)}
function updateFooter(){if(!book||!chapter)return;
  $('#chapter-label').textContent=book.unit==='page'?`원문 ${chapter.sourcePage}쪽`:`${chapterIndex+1} / ${book.chapters.length}`;
  $('#prev-chapter span').textContent=book.unit==='page'?'이전 쪽':'이전 장';$('#next-chapter span').textContent=book.unit==='page'?'다음 쪽':'다음 장';
  $('#page-label').textContent=`${page+1} / ${pageCount}`;
  $('#prev-chapter').disabled=chapterIndex===0;$('#next-chapter').disabled=chapterIndex===book.chapters.length-1;
  $('#prev-page').disabled=page===0&&chapterIndex===0;$('#next-page').disabled=page===pageCount-1&&chapterIndex===book.chapters.length-1;
  const percentage=completion(book,{chapter:chapterIndex,ratio:currentRatio()});$('#progress-label').textContent=`전체 ${percentage}%`;
  $('#progress-bar').style.width=`${percentage}%`;
  const marked=bookmarks.some(m=>m.book===book.id&&m.chapter===chapterIndex&&Math.abs(m.ratio-currentRatio())<.025);
  $('#bookmark-toggle').classList.toggle('is-marked',marked);$('#bookmark-toggle').setAttribute('aria-pressed',String(marked));$('#bookmark-toggle').setAttribute('aria-label',marked?'현재 책갈피 삭제':'현재 위치에 책갈피 추가');
}
function layout(ratio=0){if(!chapter)return;
  const viewport=$('#page-viewport'), prose=$('#prose');
  const width=viewport.clientWidth;columnStep=width+72;
  prose.style.setProperty('--figure-height',`${Math.max(36,viewport.clientHeight-92)}px`);
  prose.style.setProperty('--column-width',`${width}px`);prose.style.transform='none';
  if(settings.mode==='pages'){
    pageCount=Math.max(1,Math.round((prose.scrollWidth+72)/columnStep));page=Math.min(pageCount-1,Math.max(0,Math.round(ratio*(pageCount-1))));
    prose.style.transform=`translateX(${-page*columnStep}px)`;window.scrollTo(0,0);
  }else{page=0;pageCount=1;const max=document.documentElement.scrollHeight-innerHeight;window.scrollTo(0,Math.max(0,max*ratio))}
  updateFooter();
}
function goChapter(index,atEnd=false){if(!book||!chapter||index<0||index>=book.chapters.length)return;if(index===chapterIndex){layout(atEnd?1:0);storePosition()}else{storePosition();location.hash=`/read/${book.id}/${index}${atEnd?'?end=1':''}`}}
function turnPage(direction){if(!chapter)return;if(settings.mode==='scroll'){window.scrollBy({top:direction*(innerHeight-180),behavior:'instant'});return}if(page+direction<0){goChapter(chapterIndex-1,true);return}if(page+direction>=pageCount){goChapter(chapterIndex+1);return}page+=direction;$('#prose').style.transform=`translateX(${-page*columnStep}px)`;updateFooter();storePosition()}
function figureContent(f){
  if(f.headers)return `<div class="figure-table-scroll" tabindex="0" role="region" aria-label="${escapeHTML(f.caption)} · 가로로 스크롤"><table class="figure-table"><caption class="sr-only">${escapeHTML(f.caption)}</caption><thead><tr>${f.headers.map(h=>`<th scope="col">${escapeHTML(h)}</th>`).join('')}</tr></thead><tbody>${f.rows.map(row=>`<tr>${row.map((cell,i)=>`<${i?'td':'th scope="row"'}>${escapeHTML(cell).replace(/[♥♦]/g,s=>`<span class="red-suit">${s}</span>`)}</${i?'td':'th'}>`).join('')}</tr>`).join('')}</tbody></table></div>`;
  return `<img class="figure-image" src="${escapeHTML(f.src)}" width="${f.width}" height="${f.height}" alt="${escapeHTML(f.caption)} · 원문 ${f.sourcePage}쪽">`;
}
function chapterBody(data){
  const figures=data.figures||[],replaced=new Set(figures.flatMap(f=>f.replaces||[]));
  const parts=[];
  for(let i=0;i<=data.paragraphs.length;i++){
    for(const f of figures.filter(f=>f.beforeParagraph===i))parts.push(`<figure class="reading-figure" data-paragraph-ids="${(f.replaces||[]).join(' ')}">${figureContent(f)}<figcaption><span>${escapeHTML(f.caption)}</span><button class="quiet" data-view-figure="${escapeHTML(f.id)}" aria-label="${escapeHTML(f.caption)} 크게 보기">크게 보기 ↗</button></figcaption></figure>`);
    if(i<data.paragraphs.length&&!replaced.has(i))parts.push(`<p id="paragraph-${i}">${escapeHTML(data.paragraphs[i])}</p>`);
  }
  return parts.join('');
}
async function openReader(id,index,options={}){
  const target=catalog.find(b=>b.id===id);if(!target){location.hash='';toast('책을 찾을 수 없습니다. 책장에서 다시 선택하세요.');return}
  const token=++openToken;
  if(book&&chapter)storePosition();
  book=target;chapter=null;chapterIndex=Math.min(target.chapters.length-1,Math.max(0,index));
  $('#source-open').hidden=true;
  ['#prev-chapter','#next-chapter','#prev-page','#next-page'].forEach(s=>$(s).disabled=true);
  $('#library').hidden=true;$('#reader').hidden=false;document.body.classList.add('reading');
  $('#reader-book').textContent=book.shortTitle;$('#reader-group').textContent=book.chapters[chapterIndex].group;
  $('#prose').style.transform='none';$('#prose').innerHTML='<p class="load-note">이야기를 불러오고 있습니다…</p>';
  document.title=`${book.shortTitle} — 사이, 서재`;
  try{
    const data=await fetchChapter(book,chapterIndex);if(token!==openToken)return;
    chapter=data;
    $('#source-open').hidden=!data.sourceImage;
    const isLast=chapterIndex===book.chapters.length-1,unit=book.unit==='page'?'쪽':'장';
    const ending=book.unit==='page'&&!isLast?'':`<div class="chapter-end">${isLast?`이 책의 마지막 ${unit}입니다.`:`이 ${unit}을 모두 읽었습니다.`}<button id="end-next">${isLast?'책장으로 돌아가기':`다음 ${unit} 읽기 →`}</button></div>`;
    const sourceNote=data.sourceImage?`<aside class="ocr-note" lang="ko">${data.ocrNeedsReview?'이 쪽은 자동 인식이 고르지 않습니다. 원본 사진으로 함께 확인하세요.':data.figures?.length?'도표의 ‘크게 보기’를 누르면 확대하거나 원본과 비교할 수 있습니다.':'사진에서 추출한 텍스트입니다. 필요하면 원본과 함께 확인하세요.'}<button id="inline-source" class="quiet">원본 ${data.sourcePage}쪽 보기</button>${chapterIndex===0&&book.sourceNotice?`<span>${escapeHTML(book.sourceNotice)}</span>`:''}</aside>`:'';
    $('#prose').innerHTML=`<div class="chapter-kicker">${escapeHTML(data.group)}</div><h1>${escapeHTML(data.title)}</h1>${sourceNote}${chapterBody(data)}${ending}`;
    $$('#prose .figure-image').forEach(img=>img.onerror=()=>{const note=document.createElement('p');note.className='figure-error';note.lang='ko';note.textContent='도표를 불러오지 못했습니다. 원본 페이지에서 확인하세요.';img.replaceWith(note)});
    if($('#inline-source'))$('#inline-source').onclick=()=>openSource(chapterIndex);
    const endNext=$('#end-next');if(endNext)endNext.onclick=()=>chapterIndex===book.chapters.length-1?location.hash='':goChapter(chapterIndex+1);
    const saved=progress[id];const ratio=options.end?1:options.ratio??(saved?.chapter===chapterIndex?saved.ratio||0:0);
    requestAnimationFrame(()=>{layout(ratio);$('#prose').focus({preventScroll:true});storePosition()});
    if(chapterIndex+1<book.chapters.length)fetchChapter(book,chapterIndex+1).catch(()=>{});
  }catch(error){if(token!==openToken)return;$('#prose').innerHTML='<h1>본문을 열지 못했습니다</h1><p>인터넷 연결을 확인하고 다시 시도하세요.</p><button id="retry-reader">다시 불러오기</button>';$('#retry-reader').onclick=()=>openReader(id,index,options);toast(error.message)}
}
async function route(){
  const match=location.hash.match(/^#\/read\/([a-z-]+)\/(\d+)(\?end=1)?$/);
  if(match){await openReader(match[1],Number(match[2]),{end:!!match[3]});return}
  ++openToken;storePosition();book=null;chapter=null;
  $$('dialog[open]').forEach(d=>d.close());$('#reader').hidden=true;$('#library').hidden=false;document.body.classList.remove('reading');document.title='사이, 서재 — 책과 나 사이';window.scrollTo(0,0);renderLibrary();
}
window.addEventListener('hashchange',route);
$('#back-library').onclick=()=>location.hash='';
$('#prev-chapter').onclick=()=>goChapter(chapterIndex-1);$('#next-chapter').onclick=()=>goChapter(chapterIndex+1);
$('#prev-page').onclick=()=>turnPage(-1);$('#next-page').onclick=()=>turnPage(1);
window.addEventListener('scroll',()=>{if(!book||!chapter||settings.mode!=='scroll')return;updateFooter();clearTimeout(saveTimer);saveTimer=setTimeout(storePosition,250)},{passive:true});
window.addEventListener('pagehide',storePosition);document.addEventListener('visibilitychange',()=>{if(document.hidden)storePosition()});
window.addEventListener('resize',()=>{if(!book||!chapter)return;clearTimeout(resizeTimer);const ratio=progress[book.id]?.ratio||0;resizeTimer=setTimeout(()=>layout(ratio),150)});
document.fonts.ready.then(()=>{if(chapter)layout(progress[book.id]?.ratio||0)});
let touch=null;$('#reading-surface').addEventListener('touchstart',e=>{if(e.touches.length===1&&!e.target.closest('.figure-table-scroll'))touch={x:e.touches[0].clientX,y:e.touches[0].clientY};else touch=null},{passive:true});
$('#reading-surface').addEventListener('touchend',e=>{if(!touch||settings.mode!=='pages'||!e.changedTouches.length)return;const dx=e.changedTouches[0].clientX-touch.x,dy=e.changedTouches[0].clientY-touch.y;touch=null;if(Math.abs(dx)>55&&Math.abs(dx)>Math.abs(dy)*1.5&&getSelection().isCollapsed)turnPage(dx<0?1:-1)},{passive:true});
function showDialog(selector){$(selector).showModal()}
function openFigure(id){
  const f=chapter?.figures?.find(f=>f.id===id);if(!f)return;
  $('#figure-caption').textContent=`원문 ${f.sourcePage}쪽 · ${f.caption}`;
  $('#figure-method').textContent=f.method==='verified-data'?'원본 수치 대조':f.method==='grid-reconstruction'?'격자 재구성 · 숫자 모양 보존':'원본 그림의 선과 글자 보존';
  $('#figure-frame').classList.remove('zoomed');$('#figure-frame').innerHTML=figureContent(f);
  $('#figure-frame').style.setProperty('--figure-width',`${Math.max(f.width||1000,1000)}px`);
  $('#figure-zoom').textContent='확대';$('#figure-zoom').setAttribute('aria-pressed','false');
  const image=$('#figure-frame img');if(image)image.onerror=()=>{$('#figure-frame').innerHTML='<p class="figure-error">도표를 불러오지 못했습니다. 아래의 원본과 비교를 눌러 확인하세요.</p>'};
  if(!$('#figure-dialog').open)showDialog('#figure-dialog');$('#figure-frame').scrollTo?.(0,0);
}
document.addEventListener('click',e=>{const button=e.target.closest('[data-view-figure]');if(button)openFigure(button.dataset.viewFigure)});
$('#figure-zoom').onclick=()=>{const zoomed=$('#figure-frame').classList.toggle('zoomed');$('#figure-zoom').textContent=zoomed?'화면에 맞추기':'확대';$('#figure-zoom').setAttribute('aria-pressed',String(zoomed))};
$('#figure-source').onclick=()=>{$('#figure-dialog').close();openSource(chapterIndex)};
async function openSource(index){
  if(!book||!book.chapters[index]?.sourceImage)return;
  const token=++sourceToken;sourceIndex=index;
  $('#source-prev').disabled=index===0;$('#source-next').disabled=index===book.chapters.length-1;
  $('#source-caption').textContent=`원문 ${book.chapters[index].sourcePage}쪽 · 사진 ${index+1} / ${book.chapters.length}`;
  $('#source-image').hidden=false;$('#source-error').hidden=true;
  $('#source-frame').classList.remove('zoomed');$('#source-zoom').textContent='확대';$('#source-zoom').setAttribute('aria-pressed','false');
  const src=book.chapters[index].sourceImage;
  $('#source-image').alt=`${book.title} 원문 ${book.chapters[index].sourcePage}쪽`;
  $('#source-image').src=src;
  $('#source-image').onerror=()=>{if(token===sourceToken){$('#source-image').hidden=true;$('#source-error').hidden=false}};
  $('#source-frame').scrollTo?.(0,0);
  if(!$('#source-dialog').open)showDialog('#source-dialog');
}
$('#source-open').onclick=()=>openSource(chapterIndex);
$('#source-prev').onclick=()=>openSource(sourceIndex-1);$('#source-next').onclick=()=>openSource(sourceIndex+1);
$('#source-zoom').onclick=()=>{const zoomed=$('#source-frame').classList.toggle('zoomed');$('#source-zoom').textContent=zoomed?'화면에 맞추기':'확대';$('#source-zoom').setAttribute('aria-pressed',String(zoomed))};
$('#source-read').onclick=()=>{$('#source-dialog').close();goChapter(sourceIndex)};
$('#source-dialog').addEventListener('keydown',e=>{if(e.key==='ArrowLeft'&&sourceIndex>0){e.preventDefault();openSource(sourceIndex-1)}else if(e.key==='ArrowRight'&&sourceIndex<book.chapters.length-1){e.preventDefault();openSource(sourceIndex+1)}});
$$('.close-dialog').forEach(b=>b.onclick=()=>b.closest('dialog').close());
$$('dialog').forEach(d=>d.addEventListener('click',e=>{const r=d.getBoundingClientRect();if(e.target===d&&(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom))d.close()}));
$('#settings-open').onclick=()=>showDialog('#settings-dialog');
function changeSetting(key,value){const ratio=currentRatio();settings[key]=value;applySettings();writeStore('sai.settings',settings);if(chapter)requestAnimationFrame(()=>{layout(ratio);storePosition()})}
$$('button[data-theme]').forEach(b=>b.onclick=()=>changeSetting('theme',b.dataset.theme));
$$('[data-font]').forEach(b=>b.onclick=()=>changeSetting('font',b.dataset.font));
$$('[data-mode]').forEach(b=>b.onclick=()=>changeSetting('mode',b.dataset.mode));
$('#font-smaller').onclick=()=>changeSetting('fontSize',Math.max(16,settings.fontSize-1));$('#font-larger').onclick=()=>changeSetting('fontSize',Math.min(32,settings.fontSize+1));
function toggleBookmark(){if(!chapter)return;const ratio=currentRatio();const i=bookmarks.findIndex(m=>m.book===book.id&&m.chapter===chapterIndex&&Math.abs(m.ratio-ratio)<.025);if(i>=0){bookmarks.splice(i,1);toast('책갈피를 지웠습니다.')}else{bookmarks.push({id:Date.now(),book:book.id,chapter:chapterIndex,ratio,title:chapter.title,created:new Date().toISOString()});toast('이 페이지에 책갈피를 꽂았습니다.')}writeStore('sai.bookmarks',bookmarks);updateFooter()}
$('#bookmark-toggle').onclick=toggleBookmark;
$('#toc-open').onclick=()=>{tocTab='contents';$('#toc-search').value='';renderToc();showDialog('#toc-dialog')};
$$('[data-tab]').forEach(b=>b.onclick=()=>{tocTab=b.dataset.tab;$('#toc-search').value='';renderToc()});
$('#toc-search').addEventListener('input',()=>{clearTimeout(searchTimer);searchTimer=setTimeout(renderToc,tocTab==='search'?250:0)});
async function renderToc(){
  if(!book)return;const token=++searchToken;const targetBook=book;
  $$('[data-tab]').forEach(b=>{b.classList.toggle('active',b.dataset.tab===tocTab);b.setAttribute('aria-pressed',String(b.dataset.tab===tocTab))});
  const query=$('#toc-search').value.trim().toLowerCase();
  $('.dialog-search').hidden=tocTab==='bookmarks';$('#toc-search-label').textContent=tocTab==='search'?'책 속 문장 찾기':'목차에서 찾기';$('#toc-search').placeholder=tocTab==='search'?'영어 단어 또는 문장 (2자 이상)':'장 제목을 입력하세요';
  if(tocTab==='bookmarks'){
    const marked=bookmarks.filter(m=>m.book===book.id).sort((a,b)=>a.chapter-b.chapter||a.ratio-b.ratio);
    $('#toc-results').innerHTML=marked.length?marked.map(m=>`<div class="bookmark-row"><button class="toc-item" data-bookmark-id="${m.id}">${escapeHTML(m.title)}<small>이 장의 ${Math.round(m.ratio*100)}% 지점</small></button><button class="icon-button" data-delete-bookmark="${m.id}" aria-label="책갈피 삭제">×</button></div>`).join(''):'<p class="result-count">저장한 책갈피가 없습니다. 독서 화면 위의 책갈피 버튼을 눌러보세요.</p>';return;
  }
  if(tocTab==='search'){
    if(query.length<2){$('#toc-results').innerHTML='<p class="result-count">두 글자 이상 입력하면 이 책 전체에서 찾아드립니다.</p>';return}
    $('#toc-results').innerHTML='<p class="result-count">책 속을 찾고 있습니다…</p>';
    try{
      if(!searchCache.has(book.id)){const response=await fetch(`./books/${book.id}/search.json?v=${dataVersion}`);if(!response.ok)throw Error();searchCache.set(book.id,await response.json())}
      if(token!==searchToken||book!==targetBook)return;
      const matches=[];for(const c of searchCache.get(book.id)){for(let i=0;i<c.paragraphs.length;i++){const p=c.paragraphs[i],at=p.toLowerCase().indexOf(query);if(at>=0){matches.push({chapter:c.id,paragraph:i,excerpt:(at>65?'…':'')+p.slice(Math.max(0,at-65),at+query.length+110)+'…'});if(matches.length>=60)break}}if(matches.length>=60)break}
      $('#toc-results').innerHTML=`<p class="result-count">${matches.length===60?'처음 60개 결과':`${matches.length}개 결과`}</p>`+matches.map(m=>`<button class="toc-item" data-search-chapter="${m.chapter}" data-paragraph="${m.paragraph}">${escapeHTML(book.chapters[m.chapter].title)}<span class="search-excerpt" style="display:block">${escapeHTML(m.excerpt)}</span></button>`).join('');
    }catch{if(token===searchToken)$('#toc-results').innerHTML='<p class="result-count">검색 데이터를 불러오지 못했습니다. 인터넷 연결을 확인하고 다시 검색하세요.</p>'}return;
  }
  let group='';$('#toc-results').innerHTML=book.chapters.map((c,i)=>({c,i})).filter(({c})=>`${c.title} ${c.group}`.toLowerCase().includes(query)).map(({c,i})=>{let heading='';if(group!==c.group){group=c.group;heading=`<p class="toc-group">${escapeHTML(group)}</p>`}return `${heading}<button class="toc-item ${i===chapterIndex?'current':''}" data-go-chapter="${i}" ${i===chapterIndex?'aria-current="true"':''}>${escapeHTML(c.title)}<small>${i+1} / ${book.chapters.length}</small></button>`}).join('')||'<p class="result-count">해당하는 장이 없습니다. 다른 제목으로 찾아보세요.</p>';
}
$('#toc-results').addEventListener('click',async e=>{
  const del=e.target.closest('[data-delete-bookmark]');if(del){bookmarks=bookmarks.filter(m=>m.id!==Number(del.dataset.deleteBookmark));writeStore('sai.bookmarks',bookmarks);updateFooter();renderToc();return}
  const mark=e.target.closest('[data-bookmark-id]');if(mark){const m=bookmarks.find(m=>m.id===Number(mark.dataset.bookmarkId));if(m){$('#toc-dialog').close();await openReader(m.book,m.chapter,{ratio:m.ratio});history.replaceState(null,'',`#/read/${m.book}/${m.chapter}`)}return}
  const go=e.target.closest('[data-go-chapter]');if(go){$('#toc-dialog').close();goChapter(Number(go.dataset.goChapter));return}
  const found=e.target.closest('[data-search-chapter]');if(found){const index=Number(found.dataset.searchChapter),para=Number(found.dataset.paragraph);$('#toc-dialog').close();await openReader(book.id,index,{ratio:0});history.replaceState(null,'',`#/read/${book.id}/${index}`);requestAnimationFrame(()=>{const element=$(`#paragraph-${para}`)||$(`[data-paragraph-ids~="${para}"]`);if(!element)return;if(settings.mode==='pages'){const offset=element.getBoundingClientRect().left-$('#page-viewport').getBoundingClientRect().left;page=Math.max(0,Math.min(pageCount-1,Math.floor((offset+2)/columnStep)));$('#prose').style.transform=`translateX(${-page*columnStep}px)`}else{element.scrollIntoView({block:'center'})}updateFooter();storePosition()})}
});
document.addEventListener('keydown',e=>{if(!book||!chapter||$('dialog[open]')||e.target.closest('.figure-table-scroll')||/INPUT|TEXTAREA|SELECT/.test(e.target.tagName)||e.ctrlKey||e.metaKey||e.altKey)return;switch(e.key.toLowerCase()){case'arrowright':case'pagedown':e.preventDefault();turnPage(1);break;case'arrowleft':case'pageup':e.preventDefault();turnPage(-1);break;case'b':toggleBookmark();break;case't':$('#toc-open').click();break;case'a':$('#settings-open').click();break}});
async function init(){try{const response=await fetch(`./books/catalog.json?v=${dataVersion}`);if(!response.ok)throw Error();catalog=await response.json();await route()}catch{$('#books-grid').innerHTML='<div class="empty-state"><p>책장을 불러오지 못했습니다. 인터넷 연결을 확인하고 새로고침하세요.</p><button id="reload-library">다시 불러오기</button></div>';$('#reload-library').onclick=init}}
init();
