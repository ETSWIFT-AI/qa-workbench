"""Opt-in local source structure inventory. No code execution or hidden-server access."""
import ast
import re
from pathlib import Path

IGNORE={'node_modules','.git','.venv','venv','dist','build','__pycache__','vendor','.next','secrets'}

def inspect_source(folder,max_files=100):
    root=Path(folder).resolve()
    if not root.is_dir():raise ValueError('Source folder does not exist')
    rows=[];budget=0
    for path in root.rglob('*'):
        rel=path.relative_to(root)
        if path.is_symlink() or any(p in IGNORE or p.startswith('.') for p in rel.parts):continue
        if path.suffix.lower() not in ('.py','.js','.jsx','.ts','.tsx','.html','.css'):continue
        if not path.is_file() or path.stat().st_size>200000:continue
        if not path.resolve().is_relative_to(root):continue
        budget+=path.stat().st_size
        if len(rows)>=max_files or budget>4_000_000:break
        text=path.read_text(encoding='utf-8',errors='replace');item={'file':str(rel),'lines':len(text.splitlines()),'review':[]}
        if path.suffix=='.py':
            try:
                tree=ast.parse(text);item['functions']=[n.name for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))][:100];item['branch_nodes']=sum(isinstance(n,(ast.If,ast.For,ast.While,ast.Try,ast.Match)) for n in ast.walk(tree))
                for node in ast.walk(tree):
                    if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id in ('eval','exec'):item['review'].append({'line':node.lineno,'reason':'Dynamic code execution call; inspect data trust boundary. Not proof of vulnerability.'})
            except SyntaxError:item['parse']='Could not parse with current Python version'
        else:
            for i,line in enumerate(text.splitlines(),1):
                if re.search(r'innerHTML\s*=|dangerouslySetInnerHTML|\beval\s*\(',line):item['review'].append({'line':i,'reason':'Dynamic HTML/code sink; inspect sanitization and data provenance. Not proof of vulnerability.'})
        rows.append(item)
    return {'files':rows,'scope':'Bounded local source structure and sink-pattern review, not a call-graph proof, decompiler, full SAST, backend reconstruction, or root-cause attribution.'}
