"""Build searchable photographed-book chapters without replacing existing books."""
from pathlib import Path
import json,re,statistics,unicodedata
import cv2,numpy as np
from PIL import Image
from ocr_photos import ROOT,CACHE,BOOK
CORRECTIONS=json.loads((ROOT/'scripts/shark_corrections.json').read_text(encoding='utf8'))
NATIVE=json.loads((ROOT/'scripts/native_figures.json').read_text(encoding='utf8'))
FIGURES={}

def normalize(text):
    text=unicodedata.normalize('NFKC',text)
    text=re.sub(r'\s+',' ',text).strip(' |¦_')
    text=re.sub(r'\bAs \|(?=\s)','As I',text)
    return text

def join_lines(lines):
    value=''
    for line in lines:
        if value.endswith('-') and re.match(r'^[a-z]',line):value=value[:-1]+line
        else:value+=(' ' if value else '')+line
    return value

def is_heading(line,image):
    if not 5<len(line['text'])<110 or line['confidence']<60:return False
    points=np.asarray(line['box'],np.int32)
    x,y,w,h=cv2.boundingRect(points)
    area=image[max(y,0):min(y+h,image.shape[0]),max(x,0):min(x+w,image.shape[1])]
    if area.size==0:return False
    hsv=cv2.cvtColor(area,cv2.COLOR_RGB2HSV)
    red=((hsv[:,:,0]<15)|(hsv[:,:,0]>165))&(hsv[:,:,1]>60)&(hsv[:,:,2]>60)
    return float(red.mean())>.018

def compile_page(meta):
    stem=Path(meta['filename']).stem
    refined=json.loads((CACHE/(stem+'-refined-v2.json')).read_text(encoding='utf8'))
    with Image.open(BOOK/'pages'/f'{meta["sequence"]:03}.webp') as im:image=np.asarray(im.convert('RGB'))
    h,w=image.shape[:2]
    diagrams=FIGURES.get(meta['expectedPage'],[])
    lines=[];headings=[]
    for item in refined['lines']:
        t=normalize(item['text'])
        if not t or item['confidence']<25:continue
        if re.search(r'ADVANCED\s+CONCEPTS|NO.LIMIT\s+HOLD',t,re.I) and item['y']>h*.8:continue
        if re.fullmatch(r'(?:\d{1,3}|\d{1,3}[.,]\d+%|[AKQJT23456789 ]+|[% ]*of Raise|Not in range|Raise|Fold|Call|XX)',t,re.I):continue
        if len(re.findall('[A-Za-z]',t))<3 and '=' not in t:continue
        if len(t)<4:continue
        # Labels already drawn in a figure should not reappear as broken prose.
        inside_figure=False
        for f in diagrams:
            if not f.get('box'):continue
            if not(f['box'][0]<=item['x']+item['width']/2<=f['box'][2] and f['box'][1]<=item['y']<=f['box'][3]):continue
            # Perspective can place prose beside a figure's lower corner.
            # Keep those complete sentences after masking them out of the SVG.
            core=f.get('inkBox',f['box'])
            if item['width']>w*.35 and f['kind'] in ['diagram','chart','range'] and (item['y']<core[1]+30 or item['y']>core[3]-30):continue
            inside_figure=True;break
        if inside_figure:continue
        line={**item,'text':t};line['heading']=is_heading(line,image)
        if line['heading']:headings.append(line)
        lines.append(line)
    # Deep detection preserves each source line's position. Rebuild paragraphs
    # from indentation and vertical gaps rather than the OCR engine's reading order.
    body=[x for x in lines if len(x['text'])>35 and not x['heading']]
    gaps=[b['y']-a['y'] for a,b in zip(body,body[1:]) if 10<b['y']-a['y']<100]
    typical=statistics.median(gaps) if gaps else 45
    left=statistics.median(x['x'] for x in body) if body else w*.1
    paras=[];para_ys=[];current=[];current_y=None;previous=None
    for line in lines:
        new=previous is None or line['heading'] or previous['heading'] or line['y']-previous['y']>typical*1.45
        if line['x']>left+22 and line['width']>w*.4 and previous is not None and not previous['text'].endswith('-'):
            new=True
        if line['text'].startswith(('• ','- ','* ')):new=True
        if new and current:paras.append(join_lines(current));para_ys.append(current_y);current=[];current_y=None
        if current_y is None:current_y=line['y']
        current.append(line['text']);previous=line
    if current:paras.append(join_lines(current));para_ys.append(current_y)
    paras=[p for p in paras if p]
    # These opening tables were checked against the original photograph.
    if meta['sequence']==1:
        paras=[
            'Type of Draw — Number of Outs — Example',
            'Gutshot: 4 outs. 9♥-8♦ on A♥-6♦-5♣.',
            'Open-ended straight draw: 8 outs. 9♥-8♦ on A♥-7♦-6♣.',
            'Flush draw: 9 outs. K♥-Q♥ on A♥-7♥-6♣.',
            'Set to full house: 7–10 outs. 7♣-7♥ on 7♦-4♦-2♦.',
            'Gutshots are far more important than most people realize. Due to their disguised nature they can, in the right situations, generate tremendous value from implied odds. Open-ended straight draws have twice as many outs but they aren’t as well disguised and can also be duplicated. Flush draws are very powerful, especially nut flush draws, since they can’t be duplicated.',
            'Finally, board pair outs can come in handy if you hold a set and run into a straight or flush. If this happens on the the flop, you will have seven outs to pair the board on the turn. If you miss your draw on the turn, you will have ten outs to improve on the river regardless of which turn card is dealt.',
            'The dynamic nature of each draw will become more apparent later in the book. Below is a chart of outs and the odds of improving when you hold this number of outs. Don’t worry about memorizing all of these numbers. There will be a simple formula for this in the next section.',
            'Outs — Flop to turn — Turn to river — Flop to river',
            '1 — 2.13% — 2.17% — 4.26%',
            '2 — 4.26% — 4.35% — 8.42%',
            '3 — 6.38% — 6.52% — 12.49%',
            '4 — 8.51% — 8.70% — 16.47%',
            '5 — 10.64% — 10.87% — 20.35%',
            '6 — 12.77% — 13.04% — 24.14%',
            '7 — 14.89% — 15.22% — 27.84%',
        ]
    if meta['expectedPage']==19:
        table=NATIVE['tables']['19'][0]
        paras=[' — '.join(table['headers'])]+[' — '.join(row) for row in table['rows']]+[
            'Rule of Two and Four',
            'If memorizing these charts seems like a daunting task, have no worries. There’s a much easier way to quickly estimate how likely you are to improve. If you’re on the flop, count up all your outs and multiply by four. If you’re on the turn, count up all your outs and multiply by two.',
            'Rule of Two (for turn play)',
            '(number of outs)(2) = odds of improving',
            'Example for straight draw (8 outs)',
            '(number of outs)(2) = odds of improving',
            '(8)(2) = odds of improving',
            '16% = odds of improving',
        ]
    if not paras:paras=['This page contains a chart or diagram.']
    page=meta['expectedPage'];index=meta['sequence']-1
    if str(page) in CORRECTIONS:paras=CORRECTIONS[str(page)]
    start=18+(index//20)*20;end=min(272,start+19)
    top_headings=[l['text'] for l in headings if l['y']<h*.5 and len(l['text'])<85]
    title=f'{page}쪽'+(' · '+top_headings[0] if top_headings else '')
    if page==48:title='48쪽 · Opening Ranges'
    confirmed=any(int(c['text'])==page for c in meta['pageNumberCandidates']) or index==0
    prose_lines=[l for l in lines if len(l['text'])>45]
    confidence=sum(l['confidence']*len(l['text']) for l in prose_lines)/sum(len(l['text']) for l in prose_lines) if prose_lines else 100
    needs_review=confidence<80 and page!=18 and str(page) not in CORRECTIONS
    rendered=[]
    for diagram in diagrams:
        allowed=['id','kind','method','src','width','height','caption','beforeParagraph','replaces','headers','rows','sourcePage']
        figure={k:v for k,v in diagram.items() if k in allowed}
        if 'beforeParagraph' not in figure:
            y=diagram['box'][1]
            figure['beforeParagraph']=next((i for i,py in enumerate(para_ys) if py>y),len(paras))
        figure.setdefault('caption',{'range':'Hand range','table':'Table','chart':'Chart','diagram':'Poker situation','pie':'Odds chart'}.get(figure['kind'],'Diagram'))
        if figure.get('headers') and diagram.get('box'):
            figure['replaces']=[len(paras)]
            paras.append(' — '.join(figure['headers'])+'; '+'; '.join(' — '.join(row) for row in figure['rows']))
        rendered.append(figure)
    return {'id':index,'title':title,'group':f'촬영본 · {start}–{end}쪽','sourcePage':page,'sourcePageBasis':'visible folio' if confirmed else 'capture sequence, checked against surrounding folios','sourceImage':f'./books/advanced-holdem/pages/{meta["sequence"]:03}.webp','sourceFilename':meta['filename'],'capturedAt':meta['capturedAt'],'ocr':True,'ocrNeedsReview':needs_review,'figures':rendered,'paragraphs':paras,'words':sum(len(p.split()) for p in paras),'recognizedLines':[{'text':l['text'],'confidence':l['confidence']} for l in lines]}

def main():
    global FIGURES
    manifest=BOOK/'figures/manifest.json'
    if manifest.exists():
        diagrams=json.loads(manifest.read_text(encoding='utf8'))
        assert len(diagrams)==255,'Finish figure extraction for all 255 pages before compiling.'
        FIGURES={row['sourcePage']:row['figures'] for row in diagrams}
    report=json.loads((CACHE/'report.json').read_text(encoding='utf8'))
    assert len(report)==255
    pages=[compile_page(m) for m in report]
    for page in pages:(BOOK/f'{page["id"]}.json').write_text(json.dumps(page,ensure_ascii=False),encoding='utf8')
    metadata={'id':'advanced-holdem','title':"Advanced Concepts in No-Limit Hold’em",'shortTitle':'Advanced Hold’em','koreanTitle':'상어책','author':'Hunter Cichy','genre':'포커 전략','description':'촬영한 책 255쪽을 순서대로 모았습니다. 본문과 함께 표와 도표를 읽고, 필요하면 원본을 펼쳐 비교하세요.','detail':'촬영본 18–272쪽 · 본문과 도표','pages':255,'unit':'page','sourceNotice':'촬영본은 18쪽부터 시작합니다. 사진에 없는 1–17쪽은 포함되어 있지 않습니다.','bibliographicSource':'https://www.simonandschuster.ca/books/Advanced-Concepts-in-No-Limit-Holdem/Hunter-Cichy/9781909457683','words':sum(p['words'] for p in pages),'chapters':[{k:v for k,v in p.items() if k not in ['paragraphs','recognizedLines','sourcePageBasis','sourceFilename','capturedAt','ocr','figures'] } for p in pages]}
    catalog_path=ROOT/'dist/books/catalog.json';catalog=json.loads(catalog_path.read_text(encoding='utf8'));catalog=[b for b in catalog if b['id']!='advanced-holdem'];catalog.append(metadata)
    catalog_path.write_text(json.dumps(catalog,ensure_ascii=False),encoding='utf8')
    (BOOK/'search.json').write_text(json.dumps([{'id':p['id'],'paragraphs':p['paragraphs']} for p in pages],ensure_ascii=False),encoding='utf8')
    (BOOK/'sources.json').write_text(json.dumps([{k:p[k] for k in ['id','sourcePage','sourcePageBasis','sourceFilename','capturedAt','sourceImage']} for p in pages],ensure_ascii=False,indent=2),encoding='utf8')
    (BOOK/'extracted.txt').write_text('\n\n'.join(f'[{p["sourcePage"]}] {p["sourceFilename"]}\n\n'+'\n\n'.join(p['paragraphs']) for p in pages),encoding='utf8')
    print(json.dumps({'book':metadata['id'],'pages':len(pages),'words':metadata['words'],'firstPage':pages[0]['sourcePage'],'lastPage':pages[-1]['sourcePage']}))

if __name__=='__main__':main()
