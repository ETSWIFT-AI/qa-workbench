import subprocess
import sys
from pathlib import Path
root=Path(__file__).resolve().parent
if __name__=='__main__':
    if not (root/'models/calista_ui/ui-model.json').exists():raise SystemExit('Run train_ui.bat first.')
    url=input('Website URL (for example https://badssl.com/): ').strip()
    raise SystemExit(subprocess.call([sys.executable,str(root/'advanced.py'),'scan',url,'--ui-model',str(root/'models/calista_ui')],cwd=root))
