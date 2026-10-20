"""Rebuild the reading library from the two unchanged source PDFs."""
from pathlib import Path
import json, re, unicodedata
import pymupdf

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'dist' / 'books'
OUT.mkdir(parents=True, exist_ok=True)

def clean(text):
    text = unicodedata.normalize('NFKC', text)
    text = re.sub(r'(?<=[a-z])-\s*\n\s*(?=[a-z])', '', text)
    return re.sub(r'\s+', ' ', text).strip()

def holmes_paragraphs(doc, start, end):
    paragraphs = []
    for pi in range(start, end):
        lines = []
        for block in doc[pi].get_text('dict')['blocks']:
            for line in block.get('lines', []):
                spans = line['spans']
                x, y, right, bottom = line['bbox']
                if y < 48 or bottom > 725 or not spans or max(s['size'] for s in spans) > 11:
                    continue
                t = ''.join(s['text'] for s in spans).strip()
                if t:
                    lines.append((0 if x < 298 else 1, y, x, t))
        for col in (0, 1):
            rows = []
            for _, y, x, t in sorted((l for l in lines if l[0] == col), key=lambda a:(round(a[1]/3),a[2])):
                if rows and abs(rows[-1][0]-y) < 4:
                    rows[-1][2].append((x,t))
                    rows[-1][1] = min(rows[-1][1], x)
                else:
                    rows.append([y,x,[(x,t)]])
            prev_y = None
            base = 63.8 if col == 0 else 308.3
            for y,x,pieces in rows:
                pieces.sort()
                t = ' '.join(t for _,t in pieces)
                if len(pieces)>1 and len(pieces[0][1]) == 1:
                    t = pieces[0][1] + ' '.join(t for _,t in pieces[1:])
                indented = base + 8 < x < base + 28
                new = indented or (prev_y is not None and y-prev_y > 17)
                if not paragraphs or new:
                    paragraphs.append(t)
                else:
                    paragraphs[-1] += '\n' + t
                prev_y = y
    return [clean(p) for p in paragraphs if clean(p)]

def write_book(meta, chapters):
    folder = OUT / meta['id']
    folder.mkdir(exist_ok=True)
    for i,c in enumerate(chapters):
        c['id'] = i
        c['words'] = sum(len(p.split()) for p in c['paragraphs'])
        (folder / f'{i}.json').write_text(json.dumps(c,ensure_ascii=False), encoding='utf-8')
    meta['chapters'] = [{k:v for k,v in c.items() if k != 'paragraphs'} for c in chapters]
    meta['words'] = sum(c['words'] for c in chapters)
    (folder / 'search.json').write_text(json.dumps([{'id':c['id'],'paragraphs':c['paragraphs']} for c in chapters],ensure_ascii=False),encoding='utf-8')
    return meta

doc = pymupdf.open(ROOT.parent / 'the-complete-sherlock-holmes.pdf')
toc = doc.get_toc()
chapters = []
book = part = ''
for i,(level,title,page) in enumerate(toc):
    if level == 1:
        book, part = title, ''
    elif level == 2 and title.lower().startswith('part'):
        part = title
    if i+1 < len(toc) and toc[i+1][0] > level:
        continue
    end = toc[i+1][2]-1 if i+1 < len(toc) else len(doc)
    paras = holmes_paragraphs(doc,page-1,end)
    if paras:
        chapters.append({'title':title,'group':book + (' / '+part if part else ''),'sourcePage':page,'paragraphs':paras})
holmes = write_book({'id':'sherlock-holmes','title':'The Complete Sherlock Holmes','shortTitle':'Sherlock Holmes','koreanTitle':'셜록 홈즈 전집','author':'Arthur Conan Doyle','genre':'미스터리','description':'베이커가 221B에서 시작되는 추리. 셜록 홈즈와 왓슨의 사건들을 한 권의 서재에서 만나보세요.','detail':'장편 4편과 단편집 5권','pages':len(doc)},chapters)

doc = pymupdf.open(next(ROOT.parent.glob('pdfcoffee*.pdf')))
chapters = []
current = None
for pi in range(6,len(doc)):
    for block in sorted(doc[pi].get_text('blocks'), key=lambda b:(b[1],b[0])):
        x,y,r,b,text,*_ = block
        if y > 780:
            continue
        t = clean(text)
        if not t:
            continue
        match = re.match(r'^Chapter\s+(\d{3})\b', t)
        if match and 201 <= int(match[1]) <= 270:
            current = {'title':t,'group':'본편' if int(match[1]) <= 243 else '외전','sourcePage':pi+1,'paragraphs':[]}
            chapters.append(current)
        elif current and not any(ad in t for ad in ('Download all your fav Novels', 'RnD Novels', 'Stay up to date on Novel Updates', 'by Joining our DISCORD')):
            current['paragraphs'].append(clean(text))
assert len(chapters) == 70, f'Expected 70 chapters, got {len(chapters)}'
solo = write_book({'id':'solo-leveling','title':'Solo Leveling','shortTitle':'Solo Leveling','koreanTitle':'나 혼자만 레벨업','author':'Chugong','genre':'판타지','description':'성진우의 이야기가 이어지는 곳. 본편의 마지막 여정부터 외전까지, 영어 원문으로 읽어보세요.','detail':'Chapter 201–270 · 외전 포함','pages':len(doc)},chapters)
(OUT / 'catalog.json').write_text(json.dumps([holmes,solo],ensure_ascii=False),encoding='utf-8')
print(json.dumps([{'book':m['id'],'chapters':len(m['chapters']),'words':m['words']} for m in [holmes,solo]]))
