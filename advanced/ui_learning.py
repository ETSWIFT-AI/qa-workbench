"""Small randomly initialized screenshot-only CNN for published aesthetic labels."""
import hashlib
import json
import random
from pathlib import Path
import torch
from torch import nn

class UICNN(nn.Module):
    def __init__(self):
        super().__init__()
        self.net=nn.Sequential(nn.Conv2d(3,16,5,2,2),nn.ReLU(),nn.Conv2d(16,24,3,2,1),nn.ReLU(),nn.Conv2d(24,32,3,2,1),nn.ReLU(),nn.AdaptiveAvgPool2d((4,4)),nn.Flatten(),nn.Linear(512,32),nn.ReLU(),nn.Dropout(.1),nn.Linear(32,1))
    def forward(self,x):return self.net(x).squeeze(-1).sigmoid()

def image_tensor(path):
    import numpy as np
    from PIL import Image,ImageOps
    with Image.open(path) as im:
        im=ImageOps.pad(im.convert('RGB'),(128,128),method=Image.Resampling.LANCZOS,color='white')
        return torch.from_numpy(np.asarray(im,dtype=np.float32).copy().transpose(2,0,1)/255)

def load_dataset(path):
    path=Path(path).resolve();rows=json.loads(path.read_text());groups=set();ids=set();images={}
    for row in rows:
        image=(path.parent/row['image']).resolve()
        if not image.is_relative_to(path.parent):raise ValueError('Image escapes dataset folder')
        digest=hashlib.sha256(image.read_bytes()).hexdigest()
        if digest!=row['bundled_image_sha256']:raise ValueError('Dataset image checksum mismatch')
        if row['id'] in ids:raise ValueError('Duplicate record ID')
        if digest in images and images[digest]!=row['group']:raise ValueError('Duplicate image crosses groups')
        if not 0<=row['ui_score']<=100:raise ValueError('Invalid UI score')
        groups.add(row['group']);ids.add(row['id']);images[digest]=row['group']
    if len(groups)<10:raise ValueError('Need at least ten independent website groups')
    return rows

def train(dataset,output,epochs=40,batch_size=8,threads=2,seed=42):
    if not 1<=epochs<=500 or not 1<=batch_size<=32 or not 1<=threads<=8:raise ValueError('Training limits invalid')
    torch.set_num_threads(threads);torch.manual_seed(seed);rng=random.Random(seed)
    path=Path(dataset);rows=load_dataset(path);groups=sorted({r['group'] for r in rows});rng.shuffle(groups);n=max(1,int(len(groups)*.15))
    test=set(groups[:n]);val=set(groups[n:2*n]);parts={k:[i for i,r in enumerate(rows) if (r['group'] in test if k=='test' else r['group'] in val if k=='validation' else r['group'] not in test|val)] for k in ('train','validation','test')}
    x=torch.stack([image_tensor(path.parent/r['image']) for r in rows]);y=torch.tensor([r['ui_score']/100 for r in rows]);model=UICNN();opt=torch.optim.AdamW(model.parameters(),lr=.001,weight_decay=.01)
    def evaluate(indices):
        model.eval()
        with torch.no_grad():return torch.cat([model(x[indices[i:i+batch_size]]) for i in range(0,len(indices),batch_size)])
    best=float('inf');best_state=None;history=[];stale=0
    for epoch in range(epochs):
        model.train();order=parts['train'].copy();rng.shuffle(order);losses=[]
        for i in range(0,len(order),batch_size):
            batch=order[i:i+batch_size];opt.zero_grad();loss=nn.functional.mse_loss(model(x[batch]),y[batch]);loss.backward();opt.step();losses.append(float(loss.detach()))
        prediction=evaluate(parts['validation']);mae=float((prediction-y[parts['validation']]).abs().mean()*100);history.append({'epoch':epoch+1,'train_loss':sum(losses)/len(losses),'validation_mae':mae})
        print(f'Epoch {epoch+1}/{epochs} | validation MAE {mae:.2f}/100',flush=True)
        if mae<best:best=mae;best_state={k:v.clone() for k,v in model.state_dict().items()};stale=0
        else:stale+=1
        if stale>=10:print('Early stopping: validation has not improved for 10 epochs.');break
    model.load_state_dict(best_state);baseline=float(y[parts['train']].mean());stats={}
    for name,indices in parts.items():
        prediction=evaluate(indices);stats[name]={'samples':len(indices),'groups':len({rows[i]['group'] for i in indices}),'mae':float((prediction-y[indices]).abs().mean()*100),'constant_baseline_mae':float((y[indices]-baseline).abs().mean()*100)}
    residuals=sorted(float(z) for z in (evaluate(parts['validation'])-y[parts['validation']]).abs()*100);radius=residuals[min(len(residuals)-1,int(.9*(len(residuals)+1)))]
    metadata={'architecture':'UICNN-v1','pretrained':False,'task':'Historical screenshot aesthetic preference regression only','dataset_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'seed':seed,'threads':threads,'batch_size':batch_size,'epochs_completed':len(history),'metrics':stats,'history':history,'ui_error_radius':radius,'beats_constant_baseline_on_test':stats['test']['mae']<stats['test']['constant_baseline_mae'],'groups':{k:sorted({rows[i]['group'] for i in indices}) for k,indices in parts.items()},'status':'EXPERIMENTAL_SMALL_DATASET','limitation':'100 historical webpages, preference-derived labels and small holdout. No proof of generalization or functional correctness. Published labels are already globally ranked before this split.'}
    out=Path(output);out.mkdir(parents=True,exist_ok=True);torch.save(model.state_dict(),out/'ui-weights.pt');(out/'ui-model.json').write_text(json.dumps(metadata,indent=2));print(json.dumps(stats,indent=2));print('Saved model:',out.resolve());return metadata

def predict(rows,root,model_dir):
    directory=Path(model_dir);meta=json.loads((directory/'ui-model.json').read_text())
    if meta.get('architecture')!='UICNN-v1' or meta.get('pretrained') is not False:raise ValueError('Unexpected UI model format')
    if not meta.get('beats_constant_baseline_on_test'):return {'status':'ABSTAIN','reason':'Trained model did not beat a constant training-mean predictor on held-out data; no UI estimate reported','metrics':meta['metrics']}
    weights=directory/'ui-weights.pt'
    if weights.stat().st_size>10_000_000:raise ValueError('UI weights too large')
    model=UICNN();model.load_state_dict(torch.load(weights,map_location='cpu',weights_only=True));model.eval();predictions=[]
    with torch.no_grad():
        for row in rows:
            p=(Path(root)/row['image']).resolve()
            if not p.is_relative_to(Path(root).resolve()):raise ValueError('Image outside observations folder')
            value=float(model(image_tensor(p).unsqueeze(0))[0])*100;radius=meta['ui_error_radius']
            predictions.append({'id':row['id'],'aesthetic_estimate':round(value,1),'validation_error_range':[round(max(0,value-radius),1),round(min(100,value+radius),1)],'status':'REVIEW','note':'Experimental visual preference estimate, not usability/security/functional quality. Range is empirical, not guaranteed.'})
    return {'status':'EXPERIMENTAL','metrics':meta['metrics'],'predictions':predictions,'scope':meta['limitation']}
