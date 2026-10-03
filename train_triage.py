"""Train an advisory logistic-regression + neural MLP severity ensemble on YOUR data."""
import argparse
import json
from pathlib import Path


def train(dataset,output):
    import joblib
    import numpy as np
    from sklearn.ensemble import VotingClassifier
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import classification_report, f1_score
    from sklearn.model_selection import GroupShuffleSplit
    from sklearn.neural_network import MLPClassifier
    from sklearn.pipeline import Pipeline
    rows=[json.loads(line) for line in Path(dataset).read_text(encoding='utf-8').splitlines() if line.strip()]
    if len(rows)<50: raise ValueError('Provide at least 50 genuine labeled examples; hundreds/thousands across independent projects are preferable.')
    for row in rows:
        if not all(isinstance(row.get(k),str) and row[k].strip() for k in ('text','severity','project')): raise ValueError('Every row needs text, severity and project strings')
        if row['severity'] not in ('critical','high','medium','low','info'): raise ValueError('Invalid severity label')
    # Exact duplicate text cannot leak across projects or carry conflicting labels.
    seen={}
    for r in rows:
        key=' '.join(r['text'].lower().split())
        if key in seen and seen[key]['severity']!=r['severity']: raise ValueError('Conflicting labels for duplicate text')
        seen.setdefault(key,r)
    rows=list(seen.values())
    if len(rows)<50 or len({r['project'] for r in rows})<5: raise ValueError('Need 50 unique examples from at least 5 independent projects')
    x=np.array([r['text'] for r in rows]); y=np.array([r['severity'] for r in rows]); groups=np.array([r['project'] for r in rows])
    tr,te=next(GroupShuffleSplit(n_splits=1,test_size=.25,random_state=42).split(x,y,groups))
    if set(y[tr])!=set(y) or set(y[te])!=set(y): raise ValueError('Fixed project holdout is missing a class. Collect more class-diverse projects; do not tune the test set.')
    if min(sum(y[tr]==c) for c in set(y))<5: raise ValueError('Need at least 5 training examples per class; collect more data')
    model=Pipeline([
      ('text',TfidfVectorizer(ngram_range=(1,2),max_features=10000,sublinear_tf=True)),
      ('ensemble',VotingClassifier(estimators=[
         ('linear',LogisticRegression(max_iter=1000,class_weight='balanced',random_state=42)),
         ('neural',MLPClassifier(hidden_layer_sizes=(64,32),max_iter=300,random_state=42))
      ],voting='soft'))])
    model.fit(x[tr],y[tr])
    prediction=model.predict(x[te])
    metrics=classification_report(y[te],prediction,output_dict=True,zero_division=0)
    card={'purpose':'Advisory severity triage, NOT vulnerability detection or software certification','models':['TF-IDF','logistic regression','MLP neural classifier','soft-voting ensemble'],
      'training_examples':len(tr),'holdout_examples':len(te),'train_projects':sorted(set(groups[tr])),'holdout_projects':sorted(set(groups[te])),
      'macro_f1':f1_score(y[te],prediction,average='macro'),'metrics':metrics,'limitations':['Small or synthetic data does not establish real-world accuracy.','Near-duplicate issues and biased labels may remain.','Probabilities are not calibrated.','No hyperparameter tuning on the holdout.','Validate on later unseen projects before use.']}
    path=Path(output); path.parent.mkdir(parents=True,exist_ok=True)
    joblib.dump(model,path)
    path.with_suffix('.model-card.json').write_text(json.dumps(card,indent=2),encoding='utf-8')
    print(json.dumps(card,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dataset'); parser.add_argument('--output',default='models/triage.joblib')
    a=parser.parse_args(); train(a.dataset,a.output)
