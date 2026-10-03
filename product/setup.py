import sys
from pathlib import Path
from thorough import setup
if __name__=='__main__':
    problems=setup(Path(sys.argv[1]))
    for problem in problems:print(problem)
    raise SystemExit(1 if problems else 0)
