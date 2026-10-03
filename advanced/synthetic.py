"""Tiny artificial fixtures for exercising gradients/serialization, not website expertise."""
import json
import random
from pathlib import Path

def generate(output):
    from PIL import Image,ImageDraw
    out=Path(output);out.mkdir(parents=True,exist_ok=True);rows=[];rng=random.Random(31)
    for i in range(30):
        bad=i%2==0;image=Image.new('RGB',(128,128),(rng.randrange(180,255),rng.randrange(180,255),rng.randrange(180,255)));draw=ImageDraw.Draw(image)
        draw.rectangle([10,10,90 if bad else 110,55],fill='red' if bad else 'navy');draw.text((12,70),str(i),fill='black');name=f'synthetic-{i}.png';image.save(out/name)
        rows.append({'schema':1,'id':str(i),'group':f'synthetic-group-{i//2}','image':name,'text':'button overlaps title' if bad else 'clear heading and link','events':[[1,.33,float(bad),0,.2,0]],'features':[128,128,30,2,0,0,0,float(bad),0,float(bad),0,1,1,0,0,200],'labels':{'ui_score':30 if bad else 85,'defect':bad},'reviewer':'synthetic generator — NOT HUMAN','synthetic':True})
    (out/'dataset.jsonl').write_text('\n'.join(json.dumps(r) for r in rows)+'\n')
