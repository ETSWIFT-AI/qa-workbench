"""Train a screenshot CNN from random weights on the bundled real Calista subset."""
import argparse
from pathlib import Path

def main():
    root=Path(__file__).resolve().parent
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--epochs',type=int,default=40);p.add_argument('--batch-size',type=int,default=8);p.add_argument('--threads',type=int,default=2);p.add_argument('--seed',type=int,default=42);p.add_argument('--dataset',default=str(root/'data/calista_ui/dataset.json'));p.add_argument('--output',default=str(root/'models/calista_ui'));a=p.parse_args()
    from advanced.ui_learning import train
    train(a.dataset,a.output,a.epochs,a.batch_size,a.threads,a.seed)
if __name__=='__main__':main()
