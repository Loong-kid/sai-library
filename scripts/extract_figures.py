"""Extract printed figures and redraw their ink as self-contained SVG paths.

This preserves card suits and numeric glyphs instead of guessing them with OCR.
Photos remain unchanged; generated SVGs contain no embedded raster images.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import argparse,json,math
import cv2,numpy as np
from PIL import Image,ImageDraw
from ocr_photos import ROOT,CACHE,BOOK

OUT=BOOK/'figures'
NATIVE=json.loads((ROOT/'scripts/native_figures.json').read_text(encoding='utf8'))

def intersects(a,b):
    x=max(a[0],b[0]);y=max(a[1],b[1]);r=min(a[2],b[2]);s=min(a[3],b[3])
    return max(0,r-x)*max(0,s-y)

def candidates(image,meta):
    h,w=image.shape[:2]
    cropmeta=json.loads((CACHE/(Path(meta['filename']).stem+'-refined-v2.json')).read_text(encoding='utf8'))
    left,right=cropmeta.get('mainPageCrop',[0,w])
    main=image[:,left:right];mh,mw=main.shape[:2]
    gray=cv2.cvtColor(main,cv2.COLOR_RGB2GRAY)
    binary=cv2.adaptiveThreshold(gray,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY_INV,35,12)
    contours,_=cv2.findContours(binary,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    boxes=[]
    for contour in contours:
        x,y,bw,bh=cv2.boundingRect(contour)
        if bw<mw*.3 or bh<mh*.055 or bw*bh<mw*mh*.018 or bh>mh*.80:continue
        if y<mh*.025 or y+bh>mh*.96 or x<mw*.02 or x+bw>mw*.985:continue
        if cv2.contourArea(contour)/(bw*bh)<.25:continue
        ratio=bw/bh
        if .7<ratio<1.45 and bh>mh*.15:kind='range'
        elif ratio>2.4 and bh<mh*.24:kind='table'
        else:kind='diagram'
        quad=cv2.approxPolyDP(contour,.025*cv2.arcLength(contour,True),True)
        boxes.append({'box':[x+left,y,x+bw+left,y+bh],'kind':kind,'basis':'connected printed outline','quad':(quad.reshape(-1,2)+[left,0]).tolist() if len(quad)==4 else None})
    hsv=cv2.cvtColor(main,cv2.COLOR_RGB2HSV)
    red=(((hsv[:,:,0]<10)|(hsv[:,:,0]>173))&(hsv[:,:,1]>40)&(hsv[:,:,2]>55)).astype(np.uint8)*255
    red=cv2.morphologyEx(red,cv2.MORPH_CLOSE,np.ones((9,9),np.uint8))
    contours,_=cv2.findContours(red,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    for contour in contours:
        x,y,bw,bh=cv2.boundingRect(contour);area=cv2.contourArea(contour)
        if area<mw*mh*.005 or bw<mw*.10 or bh<mh*.045:continue
        if y+bh>mh*.93 or x<mw*.015 or x+bw>mw*.985:continue
        if area/(bw*bh)<.28:continue
        ratio=bw/bh
        if ratio<.25 or ratio>7:continue
        box=[x+left,y,x+bw+left,y+bh]
        if any(intersects(box,b['box'])>area*.5 for b in boxes):continue
        boxes.append({'box':box,'kind':'diagram' if ratio>1.4 else 'chart','basis':'printed red figure','quad':None})
    # Outline and fill candidates describing the same printed figure become one.
    merged=[]
    for box in sorted(boxes,key=lambda b:(b['box'][2]-b['box'][0])*(b['box'][3]-b['box'][1]),reverse=True):
        if any(intersects(box['box'],b['box'])>.55*(box['box'][2]-box['box'][0])*(box['box'][3]-box['box'][1]) for b in merged):continue
        merged.append(box)
    results=[]
    for item in merged:
        x,y,r,s=item['box'];bw,bh=r-x,s-y
        if item['kind']=='range':px=int(mw*.025);py1=int(mh*.015);py2=int(mh*.09)
        elif item['kind']=='table':px=int(mw*.025);py1=py2=int(mh*.012)
        else:px=int(mw*.09);py1=int(mh*.045);py2=int(mh*.07)
        expanded=[max(left,x-px),max(0,y-py1),min(right,r+px),min(h,s+py2)]
        item['inkBox']=item['box'];item['box']=expanded
        results.append(item)
    # Combine overlapping expansions to avoid slicing a player's cards in two.
    results.sort(key=lambda b:b['box'][1])
    final=[]
    for item in results:
        joined=False
        for previous in final:
            a=item['box'];b=previous['box'];intersection=intersects(a,b)
            if intersection>.18*min((a[2]-a[0])*(a[3]-a[1]),(b[2]-b[0])*(b[3]-b[1])):
                previous['box']=[min(a[0],b[0]),min(a[1],b[1]),max(a[2],b[2]),max(a[3],b[3])]
                previous['kind']='diagram';previous['quad']=None;joined=True;break
        if not joined:final.append(item)
    return sorted(final,key=lambda b:b['box'][1])

def straighten(image,item):
    x,y,r,s=item['box'];crop=image[y:s,x:r]
    quad=item['quad']
    if quad is not None and item['kind'] in ['range','table']:
        points=np.asarray(quad,np.float32)
        ordered=np.zeros((4,2),np.float32);total=points.sum(axis=1);diff=np.diff(points,axis=1).ravel()
        ordered[0]=points[np.argmin(total)];ordered[2]=points[np.argmax(total)]
        ordered[1]=points[np.argmin(diff)];ordered[3]=points[np.argmax(diff)]
        width=int(max(np.linalg.norm(ordered[1]-ordered[0]),np.linalg.norm(ordered[2]-ordered[3])))
        height=int(max(np.linalg.norm(ordered[3]-ordered[0]),np.linalg.norm(ordered[2]-ordered[1])))
        if width>100 and height>60:
            pad_x=30;pad_top=20;pad_bottom=180 if item['kind']=='range' else 20
            target=np.float32([[pad_x,pad_top],[pad_x+width,pad_top],[pad_x+width,pad_top+height],[pad_x,pad_top+height]])
            matrix=cv2.getPerspectiveTransform(ordered,target)
            crop=cv2.warpPerspective(image,matrix,(width+pad_x*2,height+pad_top+pad_bottom),borderMode=cv2.BORDER_CONSTANT,borderValue=(255,255,255))
    if crop.shape[1]>1500:crop=cv2.resize(crop,(1500,round(crop.shape[0]*1500/crop.shape[1])),interpolation=cv2.INTER_AREA)
    return crop

def isolate_poker_table(image,item,lines):
    """Follow the connected table, player boxes and cards, without prose."""
    x,y,r,s=item['box'];roi=image[y:s,x:r]
    gray=cv2.cvtColor(roi,cv2.COLOR_RGB2GRAY)
    gray=cv2.GaussianBlur(gray,(3,3),.65)
    ink=cv2.adaptiveThreshold(gray,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY_INV,51,16)
    hsv=cv2.cvtColor(roi,cv2.COLOR_RGB2HSV)
    red=(((hsv[:,:,0]<12)|(hsv[:,:,0]>171))&(hsv[:,:,1]>40)).astype(np.uint8)
    mask=cv2.morphologyEx(ink|(red*255),cv2.MORPH_CLOSE,np.ones((7,7),np.uint8))
    count,labels,stats,_=cv2.connectedComponentsWithStats(mask)
    if count<2:return image
    weights=np.bincount(labels.ravel(),weights=red.ravel(),minlength=count);weights[0]=0
    chosen=int(weights.argmax());bx,by,bw,bh,area=stats[chosen]
    if weights[chosen]<roi.shape[0]*roi.shape[1]*.04 or bw<roi.shape[1]*.5 or bh<roi.shape[0]*.35:
        if item['basis']=='connected printed outline' and item['kind']=='diagram':
            a,b,c,d=item['inkBox'];item['box']=[max(x,a-20),max(y,b-20),min(r,c+20),min(s,d+20)];item['kind']='table'
        return image
    bounds=[max(x,x+int(bx)-20),max(y,y+int(by)-20),min(r,x+int(bx+bw)+20),min(s,y+int(by+bh)+20)]
    subject=(labels==chosen).astype(np.uint8)*255
    outlines,_=cv2.findContours(subject,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(subject,outlines,-1,255,cv2.FILLED)
    subject=cv2.dilate(subject,np.ones((5,5),np.uint8))
    for line in lines:
        if len(line['text'])<24 and any(t in line['text'].lower() for t in ['bluff','value-bet','protection']):
            if bounds[1]-140<line['y']<bounds[1]+40:
                bounds[0]=min(bounds[0],max(x,int(line['x'])-10));bounds[1]=min(bounds[1],max(y,int(min(p[1] for p in line['box']))-10))
                cv2.fillPoly(subject,[np.asarray(line['box'],np.int32)-[x,y]],255)
    item['box']=bounds
    clean=image.copy();clean[y:s,x:r][subject==0]=255
    return clean

def contour_path(mask):
    contours,hierarchy=cv2.findContours(mask.astype(np.uint8),cv2.RETR_TREE,cv2.CHAIN_APPROX_SIMPLE)
    paths=[]
    for contour in contours:
        if len(contour)<3 or abs(cv2.contourArea(contour))<.7:continue
        pts=cv2.approxPolyDP(contour,.35,True).reshape(-1,2)
        if len(pts)<3:continue
        paths.append('M'+' '.join(f'{x},{y}' for x,y in pts)+'Z')
    return ''.join(paths)

def smooth_regions(mask,fill_holes=30):
    mask=mask.astype(np.uint8)*255
    contours,hierarchy=cv2.findContours(mask,cv2.RETR_CCOMP,cv2.CHAIN_APPROX_SIMPLE)
    if hierarchy is None:return mask
    for i,c in enumerate(contours):
        parent=hierarchy[0][i][3]
        if parent>=0 and cv2.contourArea(contours[parent])>1000 and cv2.contourArea(c)<fill_holes:
            cv2.drawContours(mask,[c],-1,255,-1)
    return mask

def pie_svg(spec):
    values=spec['values'];total=sum(values);colors=['#bd4148','#252827','#7b7d7c']
    parts=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 500" width="900" height="500" role="img"><title>'+spec['caption']+'</title><rect width="900" height="500" fill="#fafbf9"/>']
    angle=-math.pi/2;cx=245;cy=250;radius=188
    for i,(value,label) in enumerate(zip(values,spec['labels'])):
        end=angle+value/total*2*math.pi
        x1=cx+radius*math.cos(angle);y1=cy+radius*math.sin(angle);x2=cx+radius*math.cos(end);y2=cy+radius*math.sin(end)
        parts.append(f'<path d="M{cx} {cy}L{x1:.2f} {y1:.2f}A{radius} {radius} 0 {int(end-angle>math.pi)} 1 {x2:.2f} {y2:.2f}Z" fill="{colors[i]}" stroke="#fafbf9" stroke-width="3"/>')
        middle=(angle+end)/2;tx=cx+radius*.64*math.cos(middle);ty=cy+radius*.64*math.sin(middle)
        parts.append(f'<text x="{tx:.2f}" y="{ty+11:.2f}" text-anchor="middle" fill="#fafbf9" font-family="Arial,sans-serif" font-size="32" font-weight="600">{value}%</text>')
        sy=160+i*88;parts.append(f'<rect x="490" y="{sy-24}" width="25" height="25" rx="2" fill="{colors[i]}"/><text x="534" y="{sy-2}" font-family="Arial,sans-serif" font-size="23" fill="#252827">{label}</text><text x="534" y="{sy+30}" font-family="Arial,sans-serif" font-size="23" font-weight="600" fill="#252827">{value}%</text>')
        angle=end
    parts.append('</svg>');return ''.join(parts),900,500

def replace_pies(image,figures,page):
    specs=NATIVE['pies'].get(str(page),[])
    if not specs:return figures
    h,w=image.shape[:2];hsv=cv2.cvtColor(image,cv2.COLOR_RGB2HSV)
    mask=(((hsv[:,:,0]<10)|(hsv[:,:,0]>173))&(hsv[:,:,1]>45)&(hsv[:,:,2]>55)).astype(np.uint8)*255
    contours,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    blobs=[]
    for c in contours:
        x,y,bw,bh=cv2.boundingRect(c);area=cv2.contourArea(c)
        if area>w*h*.007 and .2<bw/max(bh,1)<4 and x>w*.10 and x+bw<w*.95 and y>h*.07 and y+bh<h*.94:
            blobs.append((area,[x,y,x+bw,y+bh]))
    blobs=sorted(sorted(blobs,reverse=True)[:len(specs)],key=lambda v:v[1][1])
    if len(blobs)!=len(specs):raise RuntimeError(f'Cannot locate all verified pie charts on page {page}')
    native=[]
    for i,((_,b),spec) in enumerate(zip(blobs,specs)):
        overlapping=[f for f in figures if intersects(b,f.get('inkBox',f['box']))>0]
        if overlapping:
            parent=max(overlapping,key=lambda f:intersects(b,f.get('inkBox',f['box'])))
            box=parent['box'];figures=[f for f in figures if f is not parent]
        else:
            x,y,r,s=b;size=max(r-x,s-y)
            box=[max(0,int(x-size*.5)),max(0,y-30),min(w,int(r+size*.8)),min(h,int(y+size*1.3))]
        svg,width,height=pie_svg(spec);filename=f'p{page:03}-pie-{i+1}.svg';(OUT/filename).write_text(svg,encoding='utf8')
        native.append({'id':f'p{page}-pie-{i+1}','kind':'pie','method':'verified-data','src':f'./books/advanced-holdem/figures/{filename}','width':width,'height':height,'caption':spec['caption'],'values':spec['values'],'labels':spec['labels'],'box':box,'inkBox':b,'sourcePage':page})
    return sorted(figures+native,key=lambda f:f['box'][1])

def vectorize(image,title,preserve_shades=False):
    h,w=image.shape[:2];rgb=image.astype(np.float32)
    paper=np.percentile(rgb.reshape(-1,3),96,axis=0)
    adjusted=np.clip(rgb*(245/np.maximum(paper,1)),0,255).astype(np.uint8)
    adjusted=cv2.GaussianBlur(adjusted,(3,3),.65)
    hsv=cv2.cvtColor(adjusted,cv2.COLOR_RGB2HSV);gray=cv2.cvtColor(adjusted,cv2.COLOR_RGB2GRAY)
    delta=adjusted[:,:,0].astype(np.int16)-adjusted[:,:,1].astype(np.int16)
    red=((hsv[:,:,0]<12)|(hsv[:,:,0]>171))&(hsv[:,:,1]>42)&(delta>28)
    strong=red.copy();pink=np.zeros_like(red)
    # A poker table is printed with a single pale fill. Lighting should not
    # turn parts of that same table into unrelated dark-red patches.
    groups,components,statistics,_=cv2.connectedComponentsWithStats(red.astype(np.uint8))
    for i in range(1,groups):
        if statistics[i,cv2.CC_STAT_AREA]>w*h*.025:
            pink[components==i]=True;strong[components==i]=False
    mid0=((gray>=100)&(gray<185)&~red).astype(np.uint8)
    count,labels,stats,_=cv2.connectedComponentsWithStats(mid0)
    mid=np.zeros_like(mid0)
    for i in range(1,count):
        x,y,bw,bh,area=stats[i]
        if area>1200 and area/(bw*bh)>.22:mid[labels==i]=1
    # Local contrast retains printed lines on shaded pages without tracing
    # the page shadow itself as a filled shape.
    ink=cv2.adaptiveThreshold(gray,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY_INV,51,16)>0
    if preserve_shades:ink|=(gray<90)&~red
    if preserve_shades:
        # Range-chart red/pink has strategic meaning. Preserve measured shades
        # rather than reclassifying a shaded photo cell as a different action.
        quantized=(adjusted//24)*24+12
        colors,counts=np.unique(quantized[red],axis=0,return_counts=True)
        base=np.median(adjusted[red],axis=0).astype(np.uint8) if red.any() else np.array([190,70,80])
        layers=[('#'+''.join(f'{int(c):02x}' for c in base),smooth_regions(red,120))]
        for color,count in zip(colors,counts):
            if count<25:continue
            mask=red&np.all(quantized==color,axis=2)
            layers.append(('#'+''.join(f'{min(255,int(c)):02x}' for c in color),mask.astype(np.uint8)*255))
        layers.extend([('#7b7d7c',smooth_regions(mid,180)),('#252827',smooth_regions(ink,20))])
    else:layers=[('#e8a5aa',smooth_regions(pink,80)),('#bd4148',smooth_regions(strong,80)),('#252827',smooth_regions(ink,20))]
    parts=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img"><title>{title}</title><rect width="100%" height="100%" fill="#fafbf9"/>']
    for color,mask in layers:
        path=contour_path(mask)
        if path:parts.append(f'<path fill="{color}" fill-rule="evenodd" d="{path}"/>')
    parts.append('</svg>')
    return ''.join(parts),w,h

def process(meta,force=False):
    seq=meta['sequence'];page=meta['expectedPage'];cachefile=CACHE/f'figures-{seq:03}.json'
    if cachefile.exists() and not force:return json.loads(cachefile.read_text(encoding='utf8'))
    if page in [18,19,43,133]:figures=[]
    else:
        with Image.open(BOOK/'pages'/f'{seq:03}.webp') as im:im=np.asarray(im.convert('RGB'))
        figures=candidates(im,meta)
        refined=json.loads((CACHE/(Path(meta['filename']).stem+'-refined-v2.json')).read_text(encoding='utf8'))
        for i,item in enumerate(figures):
            title=f'Page {page}, figure {i+1}'
            clean=im
            if item['kind'] in ['diagram','chart']:
                clean=isolate_poker_table(im,item,refined['lines'])
            crop=straighten(clean,item);svg,width,height=vectorize(crop,title,item['kind']=='range');item['method']='vector-trace'
            filename=f'p{page:03}-{i+1}.svg';(OUT/filename).write_text(svg,encoding='utf8')
            item.update(id=f'p{page}-{i+1}',src=f'./books/advanced-holdem/figures/{filename}',width=width,height=height,sourcePage=page)
    if page not in [18,19,43,133]:figures=replace_pies(im,figures,page)
    else:figures=[{**f,'sourcePage':page} for f in NATIVE['tables'].get(str(page),[])]
    if page not in [18,19]:figures.extend({**f,'sourcePage':page} for f in NATIVE['tables'].get(str(page),[]))
    data={'sequence':seq,'sourcePage':page,'figures':figures}
    cachefile.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
    return data

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--limit',type=int);parser.add_argument('--force',action='store_true');args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    report=json.loads((CACHE/'report.json').read_text(encoding='utf8'))
    if args.limit:report=report[:args.limit]
    results=[]
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures=[pool.submit(process,m,args.force) for m in report]
        for n,f in enumerate(as_completed(futures),1):
            results.append(f.result())
            if n%25==0 or n==len(report):print(json.dumps({'pages':n,'total':len(report),'figures':sum(len(r['figures']) for r in results)}),flush=True)
    results.sort(key=lambda r:r['sequence'])
    (OUT/'manifest.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
    if len(results)==255:
        used={Path(f['src']).name for row in results for f in row['figures'] if f.get('src')}
        for obsolete in OUT.glob('p*.svg'):
            if obsolete.name not in used:obsolete.unlink()
    # Contact sheets make coverage and false positives reviewable.
    for start in range(0,len(results),40):
        subset=results[start:start+40];sheet=Image.new('RGB',(1200,8*420),'#eeeeec');draw=ImageDraw.Draw(sheet)
        for k,result in enumerate(subset):
            im=Image.open(BOOK/'pages'/f'{result["sequence"]:03}.webp').convert('RGB');paint=ImageDraw.Draw(im)
            for item in result['figures']:
                if 'box' in item:paint.rectangle(item['box'],outline='#16a03a',width=9)
            im.thumbnail((232,380));x=(k%5)*240;y=(k//5)*420;sheet.paste(im,(x,y+26));draw.text((x+4,y+4),f'P{result["sourcePage"]}  {len(result["figures"])} figures',fill='#202020')
        sheet.save(ROOT/'artifacts/shark'/f'figures-contact-{start//40+1}.jpg',quality=88)

if __name__=='__main__':main()
