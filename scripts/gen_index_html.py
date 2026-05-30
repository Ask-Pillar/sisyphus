#!/usr/bin/env python3
"""生成带中文注释的详细代码索引 HTML"""

import json, subprocess, sys
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "code-index.html"

result = subprocess.run(
    [sys.executable, str(ROOT / "scripts" / "code_index.py"), str(ROOT / "src" / "sisyphus"), "--full"],
    capture_output=True, text=True, cwd=str(ROOT)
)
data = json.loads(result.stdout)
files, callers = data["files"], data["callers"]

# ── 中文模块描述 ──
DESC = {
    "store.py": "核心存储层：Memory 数据类 + MemoryStore CRUD，Markdown 文件存储",
    "retrieval.py": "检索引擎：ContextRetriever 入口，BM25/BCE/TF-IDF 排序，衰减打分",
    "context.py": "对话前注入记忆到系统提示词 (AgentMemory + MemoryContext)",
    "extraction.py": "后台从对话中自动提取 lesson/decision/pattern 记忆",
    "refined.py": "精炼记忆：reflection(反思) / summary(摘要) / loop_record(循环)",
    "pipeline.py": "自动流水线：压缩→反思→索引→链接清洗→循环检测",
    "dream.py": "LLM 反思引擎：从记忆中归纳模式和规律",
    "loop.py": "循环检测器：发现重复出现的记忆模式",
    "compression.py": "旧记忆压缩为摘要",
    "cli.py": "命令行：record/search/forget/restore/stats/dream/dashboard 等 20+ 命令",
    "dashboard.py": "可视化面板：卡片视图 + Cytoscape.js 知识图谱",
    "mcp.py": "MCP 服务端工具：write/search/context/stats/import",
    "link.py": "链接清洗：修复断裂、去重、删自引用",
    "moc.py": "目录生成器：按类型分组生成 INDEX.md / MOC.md",
    "fts_index.py": "SQLite FTS5 全文索引",
    "cache.py": "SQLite 缓存层，加速读取",
    "log.py": "操作日志 JSONL：记录增删改操作",
    "snapshot.py": "冻结快照：生成记忆摘要注入系统提示词",
    "tree.py": "树形存储：L0/L1/L2 层级节点，支持子树浏览",
    "tree_builder.py": "树构建：粗聚类(按类型)→细聚类(标题相似度)→插入",
    "tree_retriever.py": "树检索器：按层级浏览记忆树",
    "utils.py": "工具函数：原子写入 + 目录锁",
    "llm.py": "LLM 客户端：兼容 OpenAI API (urllib，零依赖)",
    "recall.py": "LLM 召回引擎（已弃用）",
    "search.py": "语义搜索：Qwen3 向量嵌入",
    "sandbox.py": "Agent 沙箱：子 Agent 隔离记忆空间",
    "agent.py": "Agent 注册表：多 Agent 记忆沙箱管理",
    "subagent.py": "子进程启动器：dream/compress/recall 等 LLM 工作放入子进程",
    "reranker_bce.py": "BCE 交叉编码器精排",
    "audit.py": "审计器：根据操作日志统计覆盖率",
    "hooks.py": "OpenCode 钩子：before_turn 注入 / after_turn 提取",
    "importer.py": "批量导入 md/jsonl 文件中的记忆",
    "__init__.py": "包初始化",
}

def get_callers(name):
    cs = callers.get(name, [])
    seen, uniq = set(), []
    for c in cs:
        cn = c.get("caller", "") if isinstance(c, dict) else str(c)
        if cn and cn not in seen:
            seen.add(cn); uniq.append(cn)
    return uniq[:3]

CSS = """
:root{--bg:#1e1e1e;--fg:#d4d4d4;--dim:#808080;--accent:#569cd6;--border:#333;--card:#252526}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:var(--fg);font-family:-apple-system,PingFang SC,Hiragino Sans GB,Microsoft YaHei,sans-serif;padding:20px;max-width:1100px;margin:0 auto;font-size:13px;line-height:1.6}
h1{font-size:1.15rem;font-weight:600;margin-bottom:4px}
.stats{display:flex;gap:8px;margin:10px 0 18px;flex-wrap:wrap}
.stat{background:var(--card);border:1px solid var(--border);border-radius:4px;padding:4px 10px;font-size:.75rem}
.stat b{color:var(--accent);font-weight:600}
.search{width:100%;padding:8px 12px;background:var(--card);border:1px solid var(--border);border-radius:4px;color:var(--fg);font-size:.82rem;margin-bottom:18px;outline:none}
.search:focus{border-color:var(--accent)}
.dir{margin-bottom:20px}
.dir-h2{font-size:.9rem;color:var(--accent);font-weight:600;cursor:pointer;user-select:none;margin-bottom:6px;padding:4px 0;border-bottom:1px solid rgba(86,156,214,.12)}
.file{margin-bottom:10px;margin-left:6px;border-left:2px solid var(--border);padding:4px 0 4px 12px;transition:border-color .15s}
.file:hover{border-color:rgba(86,156,214,.25)}
.file-header{display:flex;align-items:baseline;gap:10px;margin-bottom:4px;flex-wrap:wrap}
.file-name{color:#9cdcfe;font-weight:500;font-size:.85rem}
.file-desc{color:#608b4e;font-size:.72rem}
.line{margin:2px 0;font-size:.73rem}
.cls{color:#dcdcaa;font-weight:500}
.fn{color:#ce9178}
.caller{color:#6a9955}
.dim{color:var(--dim)}
.kw{color:#9cdcfe}
.no-results{color:var(--dim);text-align:center;padding:30px;font-size:.8rem}
.footer{color:var(--dim);font-size:.65rem;text-align:center;margin-top:24px;padding-top:12px;border-top:1px solid var(--border)}
count{color:var(--dim);font-size:.65rem;margin:0 2px}
"""

JS = """
<script>
function filter(v){
 var q=v.toLowerCase();
 document.querySelectorAll('.file').forEach(function(c){
  c.style.display=c.dataset.search.toLowerCase().includes(q)?'':'none';
 });
 var vis=document.querySelectorAll('.file:not([style*="none"])').length;
 var nr=document.querySelector('.no-results');
 if(vis===0){
  if(!nr){nr=document.createElement('div');nr.className='no-results';nr.textContent='没有匹配结果';document.querySelector('.search').after(nr)}
 }else if(nr){nr.remove()}
}
function toggle(el){
 var div=el.nextElementSibling;
 while(div&&div.classList.contains('file')){
  div.style.display=div.style.display==='none'?'':'none';
  div=div.nextElementSibling;
 }
 el.textContent=(el.nextElementSibling&&el.nextElementSibling.style.display==='none'?'▶ ':'▼ ')+el.textContent.replace(/^[▶▼] /,'');
}
</script>
"""

# 按目录分组
dir_groups = defaultdict(list)
for fd in files:
    try: rel = str(Path(fd["file"]).relative_to(ROOT / "src" / "sisyphus"))
    except: rel = Path(fd["file"]).name
    d = rel.split("/")[0] if "/" in rel else "root"
    dir_groups[d].append((rel, fd))

TF = len(files); TFC = sum(len(f.get("functions",[])) for f in files)
TCL = sum(len(f.get("classes",[])) for f in files); TE = sum(len(v) for v in callers.values())

lines = [f"""<!DOCTYPE html><html lang="zh"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sisyphus 代码索引</title><style>{CSS}</style></head><body>
<h1>Sisyphus 代码索引</h1>
<div class="stats">
<div class="stat">文件 <b>{TF}</b></div><div class="stat">函数 <b>{TFC}</b></div>
<div class="stat">类 <b>{TCL}</b></div><div class="stat">调用边 <b>{TE}</b></div>
<div class="stat">测试 <b>279 通过</b></div><div class="stat">记忆 <b>73 条</b></div>
</div>
<input class="search" placeholder="搜索函数名、类名、文件名..." oninput="filter(this.value)">
{JS}
"""]

for dn in ["memory", "server", "agent", "pipeline", "cli"]:
    items = sorted(dir_groups.get(dn, []), key=lambda x: x[0])
    if not items: continue
    lines.append(f'<div class="dir"><div class="dir-h2" onclick="toggle(this)">▼ {dn}/</div>')
    for rel, fd in items:
        fn = rel.split("/")[-1]
        desc = DESC.get(fn, "")
        classes = fd.get("classes", [])
        functions = fd.get("functions", [])
        pub_f = [f for f in functions if not f["name"].startswith("_")]
        prv_f = [f for f in functions if f["name"].startswith("_")]

        st = fn + " " + desc + " "
        for c in classes: st += c["name"] + " " + " ".join(c.get("methods",[])) + " "
        for f in functions: st += f["name"] + " "

        lines.append(f'<div class="file" data-search="{st.strip()}">')
        lines.append(f'<div class="file-header"><span class="file-name">{fn}</span><span class="file-desc">{desc}</span></div>')

        # 类
        for c in classes:
            ms = c.get("methods", [])
            pub_m = [m for m in ms if not m.startswith("_")]
            m_tags = " ".join(f'<span class="fn">{m}</span>' for m in pub_m) if pub_m else ""
            lines.append(f'<div class="line"><span class="kw">class</span> <span class="cls">{c["name"]}</span> <count>({len(pub_m)} 个公开方法)</count>')
            if m_tags: lines.append(f'<div class="line" style="padding-left:16px">{m_tags}</div>')

        # 公开函数
        if pub_f:
            items2 = []
            for f in pub_f:
                cs = get_callers(f["name"])
                cs_str = ""
                if cs:
                    cs_html = " · ".join(f'<span class="caller">{c}</span>' for c in cs)
                    cs_str = f' <count>← {cs_html}</count>'
                items2.append(f'<span class="fn">{f["name"]}</span>{cs_str}')
            lines.append(f'<div class="line">{"  ".join(items2)}</div>')

        # 私有函数
        if prv_f:
            ns = " ".join(f'<span class="dim">{f["name"]}</span>' for f in prv_f[:10])
            more = f' <count>+{len(prv_f)-10}</count>' if len(prv_f) > 10 else ""
            lines.append(f'<div class="line"><span class="dim">内部: {ns}{more}</span></div>')

        lines.append('</div>')
    lines.append('</div>')

lines.append('<div class="footer">scripts/gen_index_html.py 生成</div></body></html>')
OUT.write_text("\n".join(lines), encoding="utf-8")
print(f"OK {len(lines)} lines → {OUT}")
