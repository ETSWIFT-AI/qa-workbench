"""Versioned model input schema. Labels never enter model features."""
import hashlib
import json
from pathlib import Path

SCHEMA=1
FEATURE_NAMES=['width','height','text_length','controls','fields','images','missing_alt','small_targets','unlabelled','overflow','contrast_candidates','heading_count','links','js_errors','failed_requests','load_ms']

def byte_tokens(text):
    # Empty documents still have one nonpadding token; vocabulary is fixed bytes, not pretrained.
    values=[b+1 for b in text.encode('utf-8')[:256]] or [1]
    return values+[0]*(256-len(values))

def safe_image(root,relative):
    if not relative: raise ValueError('Missing screenshot')
    p=(Path(root)/relative).resolve()
    if not p.is_relative_to(Path(root).resolve()) or not p.is_file(): raise ValueError('Image outside dataset folder or missing')
    return p

def load_records(path,labels=True):
    path=Path(path);rows=[]
    for index,line in enumerate(path.read_text(encoding='utf-8').splitlines()):
        if not line.strip():continue
        row=json.loads(line)
        if row.get('schema')!=SCHEMA or len(row.get('features',[]))!=16:raise ValueError(f'Invalid schema/features on line {index+1}')
        if not isinstance(row.get('group'),str) or not row['group']:raise ValueError('Each record needs an independent site/project group')
        if not isinstance(row.get('text'),str):raise ValueError('Text must be a string')
        import math
        if any(not isinstance(x,(int,float)) or not math.isfinite(x) for x in row['features']):raise ValueError('Non-finite feature')
        events=row.get('events',[])
        if not isinstance(events,list) or any(len(e)!=6 or any(not isinstance(v,(int,float)) or not math.isfinite(v) for v in e) for e in events):raise ValueError('Events need six finite numbers each')
        safe_image(path.parent,row.get('image'))
        if labels:
            label=row.get('labels',{})
            if not isinstance(label.get('ui_score'),(int,float)) or not 0<=label['ui_score']<=100 or type(label.get('defect')) is not bool:raise ValueError('Every record needs human ui_score 0–100 and defect boolean')
            if not row.get('reviewer'):raise ValueError('Reviewer is required; do not train on unreviewed machine scores')
        rows.append(row)
    if not rows:raise ValueError('Dataset is empty')
    return rows

def fingerprint(rows):
    return hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest()

def make_batch(rows,root,mean=None,std=None):
    import numpy as np
    from PIL import Image
    import torch
    images=[];seq=[];lengths=[]
    for row in rows:
        with Image.open(safe_image(root,row['image'])) as im:
            images.append(np.asarray(im.convert('RGB').resize((128,128)),dtype=np.float32).transpose(2,0,1)/255)
        events=row.get('events',[])[:32] or [[0.]*6]
        lengths.append(len(events));seq.append(events+[[0.]*6]*(32-len(events)))
    features=torch.tensor([r['features'] for r in rows],dtype=torch.float32)
    if mean is not None:features=(features-torch.tensor(mean))/torch.tensor(std)
    return (torch.tensor(np.stack(images)),torch.tensor([byte_tokens(r['text']) for r in rows]),torch.tensor(seq,dtype=torch.float32),torch.tensor(lengths),features)
