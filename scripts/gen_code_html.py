"""Generate detailed HTML code index from --full JSON."""
import json, sys
from pathlib import Path

STYLE = '''
:root{--bg:#1e1e1e;--fg:#d4d4d4;--dim:#808080;--accent:#569cd6;--border:#333;--card:#252526;--func:#ce9178;--classc:#dcdcaa;--importc:#6a9955}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:var(--fg);font-family:-apple-system,sans-serif;padding:16px;max-width:1000px;margin:0 auto}
h1{font-size:1.1rem;color:var(--accent);margin-bottom:6px}
.summary{display:flex;gap:6px;margin:8px 0 14px;flex-wrap:wrap}
.summary span{background:var(--card);border:1px solid var(--border);border-radius:5px;padding:4px 10px;font-size:.68rem}
.summary b{color:var(--accent)}
.search{width:100%;padding:8px 12px;background:var(--card);border:1px solid var(--border);border-radius:6px;color:var(--fg);font-size:.76rem;margin-bottom:14px;outline:none;position:sticky;top:8px;z-index:10}
.search:focus{border-color:var(--accent)}
.dir{margin:0 0 20px}
.dir h2{font-size:.82rem;color:var(--accent);margin:14px 0 6px;border-bottom:1px solid rgba(86,156,214,.12);padding-bottom:2px;cursor:pointer}
.file{background:var(--card);border:1px solid var(--border);border-radius:6px;margin-bottom:6px;overflow:hidden}
.file-head{padding:7px 10px;cursor:pointer;display:flex;align-items:baseline;gap:8px;border-bottom:1px solid transparent;transition:background .1s}
.file-head:hover{background:rgba(86,156,214,.04)}
.file-head.open{border-bottom-color:var(--border)}
.file-name{color:var(--accent);font-size:.75rem;font-weight:600;flex-shrink:0}
.file-desc{color:var(--dim);font-size:.66rem}
.file-body{display:none;padding:6px 10px 10px}
.file-head.open + .file-body{display:block}
.section-label{font-size:.65rem;color:var(--dim);margin:6px 0 2px;text-transform:uppercase;letter-spacing:.5px}
.tags{display:flex;flex-wrap:wrap;gap:3px;margin:0 0 6px}
.tag{font-size:.64rem;padding:1px 6px;border-radius:3px;white-space:nowrap;cursor:pointer}
.tag-cls{background:rgba(220,220,170,.1);color:var(--classc)}
.tag-fn{background:rgba(206,145,120,.1);color:var(--func)}
.tag-imp{background:rgba(106,153,85,.1);color:var(--importc)}
.fn-detail{font-size:.64rem;color:var(--dim);margin:1px 0 1px 12px}
.caller-ref{font-size:.62rem;color:var(--dim);margin-left:4px}
.caller-ref a{color:var(--dim);text-decoration:none}
.caller-ref a:hover{color:var(--accent)}
'''

TEMPLATE = '''<!DOCTYPE html>
<html lang="zh"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sisyphus Code Index</title><style>{style}</style></head><body>
<h1>Sisyphus Code Index</h1>
<div class="summary">
<span>Files <b>{nfiles}</b></span><span>Functions <b>{nfuncs}</b></span>
<span>Classes <b>{nclasses}</b></span><span>Call edges <b>{nedges}</b></span>
</div>
<input class="search" placeholder="Search functions, classes, modules..." oninput="filter(this.value)" id="search">
{body}
<script>
document.querySelectorAll('.file-head').forEach(h=>h.onclick=()=>h.classList.toggle('open'));
function filter(q){{
q=q.toLowerCase();
document.querySelectorAll('.file').forEach(f=>{{
var m=f.dataset.search.toLowerCase().includes(q);
f.style.display=m?'':'none';
}});
var vis=document.querySelectorAll('.file:not([style*="none"])').length;
var dirs=document.querySelectorAll('.dir');
dirs.forEach(d=>{{
var count=d.querySelectorAll('.file:not([style*="none"])').length;
d.style.display=count?'':'none';
}});
}}</script></body></html>'''

def build_html(index_path):
    with open(index_path) as f:
        data = json.load(f)
    
    files_by_dir = {}
    for f in data['files']:
        rel = f['file'].split('src/sisyphus/')[-1] if 'src/sisyphus/' in f['file'] else Path(f['file']).name
        parts = rel.split('/')
        dirname = parts[0] if len(parts) > 1 else 'root'
        files_by_dir.setdefault(dirname, []).append((rel, f))
    
    callers = data.get('callers', {})
    
    body_parts = []
    total_funcs = 0
    total_classes = 0
    
    for dirname in ['memory', 'server', 'agent', 'pipeline', 'cli']:
        entries = sorted(files_by_dir.get(dirname, []), key=lambda x: x[0])
        if not entries:
            continue
        body_parts.append(f'<div class="dir"><h2>{dirname}/</h2>')
        
        for rel, fdata in entries:
            fname = rel.split('/')[-1]
            funcs = fdata.get('functions', [])
            classes = fdata.get('classes', [])
            imports = fdata.get('imports', [])
            total_funcs += len(funcs)
            total_classes += len(classes)
            
            # Build search index
            search_terms = fname
            cls_names = [c['name'] for c in classes]
            fn_names = [fn['name'] for fn in funcs]
            search_terms += ' ' + ' '.join(cls_names + fn_names)
            
            file_html = f'<div class="file" data-search="{search_terms}">'
            file_html += f'<div class="file-head"><span class="file-name">{fname}</span><span class="file-desc">{len(classes)} classes, {len(funcs)} funcs</span></div>'
            file_html += '<div class="file-body">'
            
            # Classes
            for cls in classes:
                methods = ', '.join(cls.get('methods', [])[:8])
                file_html += f'<div class="section-label">class</div>'
                file_html += f'<span class="tag tag-cls">{cls["name"]}</span>'
                if methods:
                    file_html += f'<span class="fn-detail">methods: {methods}</span>'
                # Show callers for this class
                cls_callers = callers.get(cls['name'], [])
                if cls_callers:
                    caller_names = ', '.join(set(c['caller'] for c in cls_callers[:3]))
                    file_html += f'<span class="caller-ref">called by: {caller_names}</span>'
            
            # Functions
            public_funcs = [fn for fn in funcs if not fn['name'].startswith('_')]
            private_funcs = [fn for fn in funcs if fn['name'].startswith('_')]
            
            if public_funcs:
                file_html += f'<div class="section-label">public functions ({len(public_funcs)})</div>'
                file_html += '<div class="tags">'
                for fn in public_funcs:
                    fn_callers = callers.get(fn['name'], [])
                    title = f'args: {", ".join(fn.get("args",[]))}' if fn.get('args') else ''
                    title += f' | line {fn["line"]}'
                    if fn_callers:
                        title += f' | called by {len(fn_callers)}'
                    file_html += f'<span class="tag tag-fn" title="{title}">{fn["name"]}</span>'
                file_html += '</div>'
            
            if private_funcs:
                file_html += f'<div class="section-label">private ({len(private_funcs)})</div>'
                file_html += '<div class="tags">'
                for fn in private_funcs[:10]:
                    file_html += f'<span class="tag tag-fn" style="opacity:.6">{fn["name"]}</span>'
                if len(private_funcs) > 10:
                    file_html += f'<span style="color:var(--dim);font-size:.62rem">+{len(private_funcs)-10} more</span>'
                file_html += '</div>'
            
            # Imports
            internal_imports = [i for i in imports if 'sisyphus' in (i.get('module','') or '')]
            if internal_imports:
                file_html += f'<div class="section-label">internal imports ({len(internal_imports)})</div>'
                file_html += '<div class="tags">'
                for imp in internal_imports[:8]:
                    mod = imp.get('module','')
                    name = imp.get('name','')
                    label = f'{mod}.{name}' if name else mod
                    file_html += f'<span class="tag tag-imp">{label}</span>'
                if len(internal_imports) > 8:
                    file_html += f'<span style="color:var(--dim);font-size:.62rem">+{len(internal_imports)-8} more</span>'
                file_html += '</div>'
            
            file_html += '</div></div>'
            body_parts.append(file_html)
        
        body_parts.append('</div>')
    
    return TEMPLATE.format(
        style=STYLE,
        nfiles=len(data['files']),
        nfuncs=total_funcs,
        nclasses=total_classes,
        nedges=sum(len(v) for v in callers.values()),
        body='\n'.join(body_parts)
    )

if __name__ == '__main__':
    html = build_html(sys.argv[1])
    out = sys.argv[2] if len(sys.argv) > 2 else '/Users/landon/PycharmProjects/workspace/sisyphus/docs/code-index.html'
    with open(out, 'w') as f:
        f.write(html)
    print(f'OK {len(html)} bytes -> {out}')
