"""Grouped train/validation/test split, held-out metrics, and advisory-only inference."""
import json
import math
import random
from pathlib import Path
from .data import load_records,make_batch,fingerprint,FEATURE_NAMES

def split_groups(rows,seed):
    groups=sorted({r['group'] for r in rows});random.Random(seed).shuffle(groups)
    if len(groups)<5:raise ValueError('Need at least 5 independent site/project groups; never split screenshots from one site across train/test')
    n=max(1,len(groups)//5);test=set(groups[:n]);val=set(groups[n:2*n])
    return [[r for r in rows if (r['group'] in test if part=='test' else r['group'] in val if part=='val' else r['group'] not in test|val)] for part in ('train','val','test')]

def metrics(logits,rows,temperature=1):
    import torch
    truth=torch.tensor([float(r['labels']['defect']) for r in rows]); ui=torch.tensor([r['labels']['ui_score'] for r in rows]);prob=torch.sigmoid(logits[:,1]/temperature);pred=prob>=.5
    recalls=[float((pred[truth==c]==bool(c)).float().mean()) for c in (0,1) if (truth==c).any()]
    return {'samples':len(rows),'groups':len({r['group'] for r in rows}),'ui_mae':float((logits[:,0].sigmoid()*100-ui).abs().mean()),'balanced_accuracy':sum(recalls)/2 if len(recalls)==2 else None,'brier':float(((prob-truth)**2).mean()),'both_classes':len(recalls)==2}

def train(dataset,output,epochs=30,seed=42,batch_size=16):
    import torch
    from .models import WebsiteNet
    if not 1<=epochs<=1000 or not 1<=batch_size<=256:raise ValueError('Invalid training budget')
    torch.set_num_threads(min(4,torch.get_num_threads()));torch.manual_seed(seed);random.seed(seed)
    path=Path(dataset);rows=load_records(path)
    from .data import safe_image
    import hashlib
    image_groups={}
    for row in rows:
        digest=hashlib.sha256(safe_image(path.parent,row['image']).read_bytes()).hexdigest()
        if digest in image_groups and image_groups[digest]!=row['group']:raise ValueError('Identical screenshots appear in different groups; prevent train/test leakage')
        image_groups[digest]=row['group']
        row['image_sha256']=digest
    parts=split_groups(rows,seed);training,validation,testing=parts
    f=torch.tensor([r['features'] for r in training],dtype=torch.float32);mean=f.mean(0);std=f.std(0,unbiased=False).clamp(min=1)
    model=WebsiteNet();optimizer=torch.optim.AdamW(model.parameters(),lr=.001,weight_decay=.01)
    def evaluate(records):
        model.eval()
        with torch.no_grad(): return torch.cat([model(*make_batch(records[i:i+batch_size],path.parent,mean.tolist(),std.tolist())) for i in range(0,len(records),batch_size)])
    def loss(pred,records):
        target=torch.tensor([[r['labels']['ui_score']/100,float(r['labels']['defect'])] for r in records])
        return ((pred[:,0].sigmoid()-target[:,0])**2).mean()+torch.nn.functional.binary_cross_entropy_with_logits(pred[:,1],target[:,1])
    best=float('inf');best_state=None;history=[]
    for epoch in range(epochs):
        model.train();random.shuffle(training)
        for i in range(0,len(training),batch_size):
            batch=training[i:i+batch_size];optimizer.zero_grad();value=loss(model(*make_batch(batch,path.parent,mean.tolist(),std.tolist())),batch);value.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),1);optimizer.step()
        pred=evaluate(validation);score=float(loss(pred,validation));history.append({'epoch':epoch+1,'validation_loss':score})
        if score<best:best=score;best_state={k:v.detach().clone() for k,v in model.state_dict().items()}
        print(f'Epoch {epoch+1}/{epochs}: validation loss {score:.4f}',flush=True)
    model.load_state_dict(best_state);pred=evaluate(validation)
    target=torch.tensor([float(r['labels']['defect']) for r in validation])
    temps=[.5,.75,1.,1.5,2.,3.,5.];temperature=min(temps,key=lambda t:float(torch.nn.functional.binary_cross_entropy_with_logits(pred[:,1]/t,target)))
    residuals=sorted(abs(float(p)-r['labels']['ui_score']) for p,r in zip(pred[:,0].sigmoid()*100,validation))
    radius=residuals[min(len(residuals)-1,math.ceil((len(residuals)+1)*.9)-1)]
    stats={name:metrics(evaluate(part),part,temperature) for name,part in zip(('train','validation','test'),parts)}
    support=all(x['samples']>=20 and x['groups']>=5 and x['both_classes'] for x in stats.values())
    synthetic=any(r.get('synthetic') for r in rows)
    qualified=support and not synthetic and stats['test']['ui_mae']<=15 and stats['test']['balanced_accuracy']>=.7
    metadata={'schema':1,'architecture':'CNN+GRU+byteTransformer+MLP','pretrained':False,'seed':seed,'epochs':epochs,'dataset_fingerprint':fingerprint(rows),'feature_names':FEATURE_NAMES,'mean':mean.tolist(),'std':std.tolist(),'temperature':temperature,'ui_error_radius':radius,'metrics':stats,'eligible_for_advisory':qualified,'synthetic':synthetic,'history':history,'groups':{name:sorted({r['group'] for r in part}) for name,part in zip(('train','validation','test'),parts)},'limitation':'Experimental held-out results, not proof of transfer to arbitrary sites. Calibration and error radius rely on representative independent data.'}
    out=Path(output);out.mkdir(parents=True,exist_ok=True);torch.save(model.state_dict(),out/'weights.pt');(out/'model.json').write_text(json.dumps(metadata,indent=2));return metadata

def predict(records,root,model_dir):
    if not model_dir:return {'status':'NOT_TRAINED','note':'No trained scratch model supplied. Measured checks still run; no neural rating invented.'}
    import torch
    from .models import WebsiteNet
    directory=Path(model_dir);meta=json.loads((directory/'model.json').read_text())
    if meta.get('pretrained') is not False or meta.get('schema')!=1:raise ValueError('Unsupported model schema')
    if not meta.get('eligible_for_advisory'):return {'status':'ABSTAIN','reason':'Training/evaluation support or held-out performance is insufficient; synthetic models never qualify','metrics':meta.get('metrics')}
    if (directory/'weights.pt').stat().st_size>100_000_000:raise ValueError('Model file exceeds size limit')
    model=WebsiteNet();model.load_state_dict(torch.load(directory/'weights.pt',map_location='cpu',weights_only=True));model.eval();results=[]
    with torch.no_grad():
        for row in records:
            batch=make_batch([row],root,meta['mean'],meta['std']);distance=float(batch[-1].abs().max())
            if distance>8:results.append({'id':row['id'],'status':'ABSTAIN','reason':'Structural features outside training range'});continue
            logits=model(*batch)[0];quality=float(logits[0].sigmoid()*100);risk=float((logits[1]/meta['temperature']).sigmoid());radius=meta['ui_error_radius']
            results.append({'id':row['id'],'status':'REVIEW','ui_estimate':round(quality,1),'empirical_ui_range':[round(max(0,quality-radius),1),round(min(100,quality+radius),1)],'defect_probability':round(risk,3),'uncertain':.2<risk<.8,'note':'Advisory prediction only; empirical range is not a guaranteed confidence interval. Does not alter test outcomes.'})
    return {'status':'ADVISORY','model_metrics':meta['metrics'],'predictions':results}
