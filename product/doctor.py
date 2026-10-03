import importlib.util
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]

def diagnose():
    rows=[{'name':'Python','ok':sys.version_info>=(3,10),'detail':sys.version.split()[0],'fix':'Install Python 3.12 and create a virtual environment.'}]
    for module,fix in [('playwright','Run dependency setup.'),('keyring','Install requirements-product.txt to use the OS credential store.')]:
        rows.append({'name':module,'ok':importlib.util.find_spec(module) is not None,'detail':'Python package availability','fix':fix})
    for program in ('node','npm'):
        rows.append({'name':program,'ok':bool(shutil.which(program)),'detail':'Executable on PATH','fix':'Install Node.js/npm and reopen the terminal.'})
    rows.append({'name':'axe','ok':(ROOT/'node_modules/axe-core/axe.min.js').is_file(),'detail':'Local accessibility engine','fix':'Run dependency setup after installing Node.js.'})
    if importlib.util.find_spec('playwright'):
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as pw:
                for engine in ('chromium','firefox','webkit'):
                    present=Path(getattr(pw,engine).executable_path).is_file()
                    rows.append({'name':engine,'ok':present,'detail':'Browser file presence; startup is checked by thorough mode','fix':'Run dependency setup. Linux may need OS browser packages.'})
        except Exception as exc:rows.append({'name':'Browser inspection','ok':False,'detail':type(exc).__name__,'fix':'Repair Playwright installation.'})
    try:
        from .security import keyring_api
        keyring_api();ok=True;detail='Supported OS-backed credential store'
    except Exception:ok=False;detail='Unavailable; credentials will not be saved as plaintext'
    rows.append({'name':'Credential store','ok':ok,'detail':detail,'fix':'Enable the Windows/macOS/Linux OS keyring; optional for public read-only scans.'})
    return rows
