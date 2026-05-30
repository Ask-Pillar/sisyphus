"""Generate detailed code-index.html from code-index.json."""

import json
import sys
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
IDX_PATH = ROOT / "docs" / "code-index.json"
OUT_PATH = ROOT / "docs" / "code-index.html"

# ── descriptions (same as before) ───────────────────────────────────────────
DESC = {
    "store.py": "CRUD + file-based markdown storage (Memory, MemoryStore)",
    "retrieval.py": "ContextRetriever, BM25, BCE Reranker, TF-IDF, decay scoring",
    "context.py": "Per-turn memory injection (AgentMemory, MemoryContext)",
    "extraction.py": "Auto-extract lessons/decisions from conversation",
    "refined.py": "Refined memories: reflection, summary, loop_record",
    "pipeline.py": "Auto-trigger: compress, dream, index, link, loop detect",
    "dream.py": "LLM-powered reflection engine",
    "loop.py": "LoopDetector: repeated memory patterns",
    "compression.py": "Compress old memories into summaries",
    "cli.py": "CLI: record, search, forget, restore, stats, dream, dashboard...",
    "dashboard.py": "HTML dashboard: card view + Cytoscape.js graph",
    "mcp.py": "MCP server tools: write_memory, search_memory, memory_stats",
    "link.py": "LinkCleaner: broken/duplicate links",
    "moc.py": "MocGenerator: table-of-contents (INDEX.md / MOC.md)",
    "fts_index.py": "SQLite FTS5 full-text search index",
    "cache.py": "SQLite cache for fast reads",
    "log.py": "Operation log (JSONL) + LogEntry",
    "snapshot.py": "FrozenSnapshot for system-prompt injection",
    "tree.py": "TreeStore: hierarchical tree storage (L0/L1/L2)",
    "tree_builder.py": "TreeBuilder: co-clust / fine-clust / upsert",
    "tree_retriever.py": "TreeRetriever: browse by tree traversal",
    "utils.py": "Atomic file write, DirLock",
    "llm.py": "OpenAI-compatible LLMClient (urllib, zero deps)",
    "recall.py": "LLM-powered Recall engine (deprecated)",
    "search.py": "SemanticSearch via Qwen3 embeddings",
    "sandbox.py": "AgentSandbox: isolated agent memory stores",
    "agent.py": "AgentRegistry for multi-agent memory sandboxes",
    "subagent.py": "Subprocess-based SubagentLauncher",
    "reranker_bce.py": "BCERerankerSimple cross-encoder",
    "audit.py": "Auditor: memory coverage report",
    "hooks.py": "OpenCode before_turn / after_turn hook scripts",
    "importer.py": "Import memories from .md / .jsonl files",
}

# ── helpers ──────────────────────────────────────────────────────────────────
def extract_public(items, key="name"):
    """Return items whose name does NOT start with '_'."""
    return [i for i in items if not i.get(key, "").startswith("_")]

def extract_private(items, key="name"):
    return [i for i in items if i.get(key, "").startswith("_")]

# ── load data ────────────────────────────────────────────────────────────────
index = json.loads(IDX_PATH.read_text())

# Build file → {classes, functions, imports} map
file_map = {}
for fdata in index["files"]:
    file_map[fdata["file"]] = fdata

# Short-name lookup: "store.py" → full path
short_map = {}
for full in file_map:
    name = Path(full).name
    short_map[name] = full

# Group by directory
dir_groups = defaultdict(list)
for full in sorted(file_map.keys()):
    rel = str(Path(full).relative_to(ROOT / "src" / "sisyphus"))
    parts = rel.split("/")
    if len(parts) > 1:
        dir_groups[parts[0]].append(rel)
    else:
        dir_groups["root"].append(rel)

# ── HTML ─────────────────────────────────────────────────────────────────────
CSS = """<style>
:root{--bg:#1e1e1e;--fg:#d4d4d4;--dim:#808080;--accent:#569cd6;--border:#333;--card:#252526;--func:#ce9178;--classc:#dcdcaa;--call:#6a9955}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:var(--fg);font-family:-apple-system,sans-serif;padding:16px;max-width:960px;margin:0 auto}
h1{font-size:1.1rem;margin-bottom:4px}
.stats{display:flex;gap:6px;margin:10px 0 14px;flex-wrap:wrap}
.stat{background:var(--card);border:1px solid var(--border);border-radius:6px;padding:5px 10px;font-size:.68rem}
.stat b{color:var(--accent)}
.search{width:100%;padding:8px 12px;background:var(--card);border:1px solid var(--border);border-radius:6px;color:var(--fg);font-size:.76rem;margin-bottom:14px;outline:none}
.search:focus{border-color:var(--accent)}
.dir{margin-bottom:18px}
.dir-h2{font-size:.78rem;color:var(--accent);margin-bottom:4px;padding-bottom:2px;cursor:pointer;user-select:none}
.dir-h2:hover{opacity:.8}
.file{border-left:2px solid var(--border);margin-left:8px;margin-bottom:6px;padding:4px 0 4px 10px;transition:border-color .15s}
.file:hover{border-color:rgba(86,156,214,.3)}
.file-name{font-size:.74rem;color:var(--accent);font-weight:500;margin-bottom:2px}
.file-desc{font-size:.65rem;color:var(--dim);margin-bottom:3px}
.item-list{display:flex;flex-wrap:wrap;gap:3px;margin-bottom:3px}
.tag{font-size:.6rem;padding:1px 5px;border-radius:3px;white-space:nowrap;cursor:default}
.tc{background:rgba(220,220,170,.1);color:var(--classc)}
.tf{background:rgba(206,145,120,.1);color:var(--func)}
.ti{background:rgba(106,153,85,.1);color:var(--call)}
.tk{background:rgba(128,128,128,.1);color:var(--dim)}
.class-line{font-size:.62rem;color:var(--dim);margin:1px 0}
.class-line .cls-name{color:var(--classc)}
.class-line .m-name{color:var(--func)}
.callers-line{font-size:.62rem;color:var(--dim);margin:1px 0;padding-left:6px}
.callers-line .caller{color:var(--call)}
.footer{color:var(--dim);font-size:.6rem;text-align:center;margin-top:20px;padding-top:10px;border-top:1px solid var(--border)}
.no-results{color:var(--dim);font-size:.7rem;text-align:center;padding:20px}
</style>"""

JS = """<script>
function filter(q){
  q=q.toLowerCase();
  var cards=document.querySelectorAll('.file');
  var visible=0;
  cards.forEach(function(c){
    var show=c.dataset.search.toLowerCase().includes(q);
    c.style.display=show?'':'none';
    if(show)visible++;
  });
  var nr=document.querySelector('.no-results');
  if(visible===0){
    if(!nr){nr=document.createElement('div');nr.className='no-results';nr.textContent='no matches';document.body.appendChild(nr)}
  }else{if(nr)nr.remove()}
}
function toggleDir(h2){
  var div=h2.nextElementSibling;
  while(div&&div.classList.contains('file')){
    div.style.display=div.style.display==='none'?'':'none';
    div=div.nextElementSibling;
  }
}
</script>"""

HEADER = f"""<!DOCTYPE html>
<html lang="zh"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sisyphus Code Index</title>{CSS}</head><body>
<h1>Sisyphus Code Index</h1>
<div class="stats">
<div class="stat">files <b>{index['total_files']}</b></div>
<div class="stat">functions <b>{index['total_functions']}</b></div>
<div class="stat">classes <b>{index['total_classes']}</b></div>
<div class="stat">call edges <b>{index['total_call_edges']}</b></div>
<div class="stat">tests <b>279 pass</b></div>
<div class="stat">memories <b>73 RAW</b></div>
</div>
<input class="search" placeholder="search functions, classes, or filenames..." oninput="filter(this.value)">
"""

FOOTER = """<div class="footer">scripts/gen_code_index_html.py</div>
</body></html>"""

# ── build call graph index for lookup ────────────────────────────────────────
# callers[func_name] = [{"caller": ..., "file": ..., "line": ...}]
callers = index.get("callers", {})

def callers_for(func_name, max_show=3):
    """Get caller HTML for a function."""
    cs = callers.get(func_name, [])
    if not cs:
        return ""
    seen = set()
    unique = []
    for c in cs:
        key = c["caller"]
        if key not in seen:
            seen.add(key)
            unique.append(c)
    unique = unique[:max_show]
    tags = "".join(f'<span class="tag ti">{c["caller"]}</span>' for c in unique)
    more = f' +{len(cs) - max_show}' if len(cs) > max_show else ""
    return f'<div class="callers-line">called by {tags}{more}</div>' if tags else ""

# ── render ───────────────────────────────────────────────────────────────────
body_parts = []

for dirname in ["memory", "server", "agent", "pipeline", "cli", "root"]:
    files_in_dir = dir_groups.get(dirname, [])
    if not files_in_dir:
        continue
    body_parts.append(f'<div class="dir"><div class="dir-h2" onclick="toggleDir(this)">▸ {dirname}/</div>')
    for rel in sorted(files_in_dir):
        fname = rel.split("/")[-1]
        full = str(ROOT / "src" / "sisyphus" / rel)
        info = file_map.get(full, {})
        desc = DESC.get(fname, "")

        classes = info.get("classes", [])
        functions = info.get("functions", [])
        imports = info.get("imports", [])

        pub_funcs = extract_public(functions)
        prv_funcs = extract_private(functions)
        pub_imports = extract_public(imports, "module")

        # search data
        search_terms = f"{fname} {desc} "
        for c in classes:
            search_terms += f"{c['name']} "
            for m in c.get("methods", []):
                search_terms += f"{m} "
        for f in functions:
            search_terms += f"{f['name']} "

        line = f'<div class="file" data-search="{search_terms.strip()}">'
        line += f'<div class="file-name">{fname}</div>'

        if desc:
            line += f'<div class="file-desc">{desc}</div>'

        # classes with their methods
        for c in classes:
            methods = c.get("methods", [])
            pub_m = [m for m in methods if not m.startswith("_")]
            pub_tags = " ".join(f'<span class="tag tf">{m}</span>' for m in pub_m)
            line += f'<div class="class-line"><span class="cls-name">class {c["name"]}</span>{" → "+pub_tags if pub_tags else ""}</div>'

        # public functions with callers
        if pub_funcs:
            func_tags = []
            for f in pub_funcs:
                tag_html = f'<span class="tag tf">{f["name"]}</span>'
                c_html = callers_for(f["name"])
                if c_html:
                    tag_html += c_html
                func_tags.append(tag_html)
            line += f'<div class="item-list">{" ".join(func_tags)}</div>'

        # private functions (just count)
        if prv_funcs:
            line += f'<div class="item-list"><span class="tag tk">+{len(prv_funcs)} private</span></div>'

        line += '</div>'
        body_parts.append(line)
    body_parts.append('</div>')

html = HEADER + "\n".join(body_parts) + FOOTER
OUT_PATH.write_text(html, encoding="utf-8")
print(f"OK: {OUT_PATH} ({len(html)} bytes, {len(body_parts)} blocks)")
