"""OCR photographed book pages, ordered by EXIF capture time; resume from cache.

Requires Pillow, numpy, opencv-python, rapidocr-onnxruntime and Tesseract English.
Original photos are read only. Intermediate OCR files stay in ignored artifacts/.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image, ImageOps
import argparse, csv, io, json, os, re, subprocess, threading, time
import cv2
import numpy as np
import onnxruntime as ort
from rapidocr_onnxruntime import RapidOCR

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / 'artifacts' / 'shark' / 'ocr'
BOOK = ROOT / 'dist' / 'books' / 'advanced-holdem'
LOCAL = threading.local()

def capture_info(p):
    with Image.open(p) as im:
        exif = im.getexif()
        original = exif.get_ifd(34665).get(36867)
        date = original or exif.get(306)
        return {'filename': p.name, 'capturedAt': date or p.stem, 'timeSource': 'EXIF DateTimeOriginal' if original else 'EXIF DateTime' if date else 'filename', 'bytes': p.stat().st_size}

def detector():
    if not hasattr(LOCAL, 'detector'):
        engine = RapidOCR(det_limit_side_len=1500, det_model_path=None, det_thresh=.15, det_box_thresh=.25, use_angle_cls=False)
        old = engine.text_detector.infer.session
        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        options.log_severity_level = 4
        model = Path(__import__('rapidocr_onnxruntime').__file__).parent / 'models' / 'ch_PP-OCRv3_det_infer.onnx'
        engine.text_detector.infer.session = ort.InferenceSession(str(model),sess_options=options,providers=['CPUExecutionProvider'])
        LOCAL.detector = engine.text_detector
    return LOCAL.detector

def rectify(image):
    h,w = image.shape[:2]
    boxes,_ = detector()(image)
    lines=[]
    for box in boxes if boxes is not None else []:
        p=np.asarray(box);dx=p[1,0]-p[0,0]
        if dx > w*.32 and p[:,0].mean() < w*.92:
            slope=(p[1,1]-p[0,1])/dx
            if abs(slope)<.4:
                lines.append((p[:,1].mean(),slope))
    a=b=0.
    if len(lines)>=4:
        points=np.asarray(lines)
        a,b=np.polyfit(points[:,0],points[:,1],1)
        residual=abs(points[:,1]-(a*points[:,0]+b))
        selected=points[residual<max(.015,float(np.median(residual))*3)]
        if len(selected)>=4:
            a,b=np.polyfit(selected[:,0],selected[:,1],1)
        if abs(a*h)>.65 or abs(b)>.5:
            a,b=0.,float(np.median(points[:,1]))
    elif lines:
        b=float(np.median(np.asarray(lines)[:,1]))
    y,x=np.mgrid[0:h,0:w].astype(np.float32)
    source_y=((y+b*(x-w/2))/(1-a*(x-w/2))).astype(np.float32)
    warped=cv2.remap(image,x,source_y,cv2.INTER_CUBIC,borderMode=cv2.BORDER_CONSTANT,borderValue=(255,255,255))
    return warped, {'slopeChange':float(a),'skew':float(b),'baselineSamples':len(lines)}

def process(item,source,tesseract):
    p=source/item['filename'];stem=p.stem
    metadata=CACHE/(stem+'.json')
    if metadata.exists() and (CACHE/(stem+'.tsv')).exists() and (BOOK/'pages'/f'{item["sequence"]:03}.webp').exists():
        return json.loads(metadata.read_text(encoding='utf8'))
    with Image.open(p) as original:
        image=ImageOps.exif_transpose(original).convert('RGB')
        image.thumbnail((1800,2400),Image.Resampling.LANCZOS)
    image.save(BOOK/'pages'/f'{item["sequence"]:03}.webp','WEBP',quality=85,method=4)
    arr=np.asarray(image)
    warped,geometry=rectify(arr)
    png=CACHE/(stem+'.png')
    Image.fromarray(warped).save(png)
    Image.fromarray(warped).save(CACHE/(stem+'.jpg'),quality=88)
    env=dict(os.environ,OMP_THREAD_LIMIT='1')
    result=subprocess.run([str(tesseract),str(png),str(CACHE/stem),'-l','eng','--psm','3','--dpi','300','txt','tsv'],env=env,capture_output=True,timeout=120)
    if result.returncode:
        raise RuntimeError(f'{p.name}: {result.stderr.decode(errors="replace")}')
    words=list(csv.DictReader(io.StringIO((CACHE/(stem+'.tsv')).read_text(encoding='utf8')),delimiter='\t'))
    confidence=[float(w['conf']) for w in words if w['text'].strip() and float(w['conf'])>=0]
    bottom=[w for w in words if re.fullmatch(r'\d{1,3}',w['text'].strip()) and int(w['top'])>image.height*.80]
    candidates=[{'text':w['text'],'confidence':round(float(w['conf']),1),'x':int(w['left']),'y':int(w['top'])} for w in bottom]
    meta={**item,'size':list(image.size),'geometry':geometry,'meanWordConfidence':round(float(np.mean(confidence)),1) if confidence else 0,'pageNumberCandidates':candidates}
    metadata.write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf8')
    png.unlink()
    return meta

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,default=Path.home()/'Downloads'/'상어책')
    parser.add_argument('--tesseract',type=Path,default=Path('C:/Program Files/Tesseract-OCR/tesseract.exe'))
    parser.add_argument('--workers',type=int,default=3)
    parser.add_argument('--limit',type=int)
    args=parser.parse_args()
    CACHE.mkdir(parents=True,exist_ok=True);(BOOK/'pages').mkdir(parents=True,exist_ok=True)
    files=sorted(args.source.glob('*.jpg'))
    ordered=sorted([capture_info(p) for p in files],key=lambda i:(i['capturedAt'],i['filename']))
    for i,item in enumerate(ordered):item['sequence']=i+1;item['expectedPage']=i+18
    (CACHE/'capture-order.json').write_text(json.dumps(ordered,ensure_ascii=False,indent=2),encoding='utf8')
    selected=ordered[:args.limit] if args.limit else ordered
    start=time.time();done=0;results=[]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures={pool.submit(process,item,args.source,args.tesseract):item for item in selected}
        for future in as_completed(futures):
            result=future.result();results.append(result);done+=1
            if done%5==0 or done==len(selected):
                print(json.dumps({'done':done,'total':len(selected),'elapsedSeconds':round(time.time()-start),'last':result['filename'],'confidence':result['meanWordConfidence']}),flush=True)
    results.sort(key=lambda r:r['sequence'])
    (CACHE/'report.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
    print('OCR complete.',flush=True)

if __name__=='__main__':main()
