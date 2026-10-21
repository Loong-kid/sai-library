"""Recognize locally rectified text regions and discard clipped neighboring lines."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image,ImageOps
from collections import defaultdict
import argparse,csv,io,json,math,os,subprocess,time
import cv2
import numpy as np
from ocr_photos import ROOT,CACHE,BOOK,detector

def recognize(meta):
    stem=Path(meta['filename']).stem
    out=CACHE/(stem+'-refined-v2.json')
    if out.exists():return json.loads(out.read_text(encoding='utf8'))
    image=Image.open(BOOK/'pages'/f'{meta["sequence"]:03}.webp').convert('RGB')
    arr=np.asarray(image);h,w=arr.shape[:2]
    boxes,_=detector()(arr)
    # The other page sometimes appears along the photo edge. Its clipped text
    # boxes identify that column, preventing two pages from becoming one line.
    neighboring=[];left_page=meta['expectedPage']%2==0
    for box in boxes if boxes is not None else []:
        p=np.asarray(box);left=p[:,0].min();right=p[:,0].max();cy=p[:,1].mean()
        if not h*.1<cy<h*.92:continue
        if left_page and left>w*.65 and right>w*.97 and right-left>w*.055:neighboring.append(left)
        elif not left_page and left<w*.03 and right<w*.35 and right-left>w*.055:neighboring.append(right)
    crop_left=0;crop_right=w
    if len(neighboring)>=3:
        if left_page:crop_right=int(max(w*.72,np.percentile(neighboring,15)-w*.012))
        else:crop_left=int(min(w*.28,np.percentile(neighboring,85)+w*.012))
    if crop_left==0 and crop_right==w:
        previous=CACHE/(stem+'-refined.json')
        if previous.exists():
            data=json.loads(previous.read_text(encoding='utf8'));data['mainPageCrop']=[0,w];out.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8');return data
    else:
        arr=arr[:,crop_left:crop_right];boxes,_=detector()(arr)
    regions=[]
    for box in boxes if boxes is not None else []:
        p=np.asarray(box,np.float32)
        bw=max(np.linalg.norm(p[1]-p[0]),np.linalg.norm(p[2]-p[3]));bh=max(np.linalg.norm(p[3]-p[0]),np.linalg.norm(p[2]-p[1]))
        if bw<w*.055 or bw/bh<2.0 or p[:,0].mean()+crop_left>w*.94 or p[:,0].mean()+crop_left<w*.055 or bh<12:
            continue
        target=np.float32([[0,0],[int(bw)-1,0],[int(bw)-1,int(bh)-1],[0,int(bh)-1]])
        crop=cv2.warpPerspective(arr,cv2.getPerspectiveTransform(p,target),(int(bw),int(bh)),borderMode=cv2.BORDER_REPLICATE)
        crop=ImageOps.autocontrast(Image.fromarray(crop).convert('L'),cutoff=1)
        global_box=p.copy();global_box[:,0]+=crop_left
        regions.append({'box':global_box.tolist(),'x':float(global_box[:,0].min()),'y':float(p[:,1].mean()),'width':float(bw),'height':float(bh),'crop':crop})
    regions.sort(key=lambda r:(round(r['y']/18),r['x']))
    if not regions:raise RuntimeError(f'No text regions: {stem}')
    sheet_width=max(r['crop'].width for r in regions)+48
    sheet_height=sum(r['crop'].height+64 for r in regions)+24
    sheet=Image.new('L',(sheet_width,sheet_height),255)
    top=24
    for region in regions:
        sheet.paste(region['crop'],(24,top));region['stripTop']=top;top+=region['crop'].height+64
    png=CACHE/(stem+'-strips.png');sheet.save(png)
    base=CACHE/(stem+'-strips')
    env=os.environ|{'OMP_THREAD_LIMIT':'1'}
    result=subprocess.run(['C:/Program Files/Tesseract-OCR/tesseract.exe',str(png),str(base),'-l','eng','--psm','6','--dpi','300','tsv'],capture_output=True,env=env,timeout=120)
    if result.returncode:raise RuntimeError(result.stderr.decode(errors='replace'))
    words=list(csv.DictReader(io.StringIO(base.with_suffix('.tsv').read_text(encoding='utf8')),delimiter='\t'))
    for region in regions:
        candidates=defaultdict(list)
        for word in words:
            if not word['text'].strip() or float(word['conf'])<0:continue
            center=int(word['top'])+int(word['height'])/2
            if region['stripTop']-2<=center<=region['stripTop']+region['height']+2:
                candidates[(word['block_num'],word['par_num'],word['line_num'])].append(word)
        ranked=[]
        for line in candidates.values():
            line.sort(key=lambda t:int(t['left']))
            text=' '.join(v['text'] for v in line)
            conf=sum(float(v['conf'])*max(1,len(v['text'])) for v in line)/sum(max(1,len(v['text'])) for v in line)
            cy=sum(int(v['top'])+int(v['height'])/2 for v in line)/len(line)
            distance=abs(cy-(region['stripTop']+region['height']/2))/region['height']
            score=conf+min(len(text),80)*.12-distance*10
            ranked.append((score,text,conf))
        best=max(ranked,default=(0,'',0))
        region.update(text=best[1],confidence=round(best[2],1))
        del region['crop'];del region['stripTop']
    data={'sequence':meta['sequence'],'filename':meta['filename'],'mainPageCrop':[crop_left,crop_right],'lines':regions}
    out.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
    png.unlink()
    return data

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--limit',type=int);parser.add_argument('--workers',type=int,default=3);args=parser.parse_args()
    metas=json.loads((CACHE/'report.json').read_text(encoding='utf8'))
    if args.limit:metas=metas[:args.limit]
    start=time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures=[pool.submit(recognize,m) for m in metas]
        for n,f in enumerate(as_completed(futures),1):
            data=f.result()
            if n%10==0 or n==len(metas):print(json.dumps({'refined':n,'total':len(metas),'seconds':round(time.time()-start),'last':data['sequence']}),flush=True)

if __name__=='__main__':main()
