"""Dashboard generator - Option A: Obsidian-style card layout.

Single HTML file. Cytoscape.js from CDN. Real data from MemoryStore.
"""

import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

from sisyphus.memory.store import MemoryStore

TYPE_LABELS = {
    "decision": "\u51b3\u7b56", "lesson": "\u6559\u8bad", "pattern": "\u6a21\u5f0f",
    "note": "\u7b14\u8bb0", "conversation": "\u5bf9\u8bdd", "reflection": "\u53cd\u601d",
    "project_context": "\u9879\u76ee", "user_preference": "\u504f\u597d",
    "idea": "\u60f3\u6cd5", "compressed": "\u538b\u7f29",
}
TYPE_COLORS = {
    "decision": "#3fb950", "lesson": "#d2991d", "pattern": "#58a6ff",
    "note": "#8b949e", "conversation": "#a371f7", "reflection": "#f85149",
    "project_context": "#79c0ff", "user_preference": "#d2a8ff",
    "idea": "#ffa657", "compressed": "#7d8590",
}

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Sisyphus</title>
<script src="https://cdn.jsdelivr.net/npm/cytoscape@3.28.1/dist/cytoscape.min.js"></script>
<style>
:root{{--bg:#1e1e1e;--fg:#d4d4d4;--dim:#808080;--accent:#569cd6;--border:#333;--card:#252526;--input:#3c3c3c}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:var(--bg);color:var(--fg);font-family:-apple-system,sans-serif;padding:16px;max-width:680px;margin:0 auto}}
.stats{{display:flex;gap:8px;margin-bottom:14px;flex-wrap:wrap}}
.stat{{flex:1;min-width:0;background:var(--card);border:1px solid var(--border);border-radius:8px;padding:10px 8px;text-align:center;cursor:pointer;transition:border-color .15s;user-select:none}}
.stat:hover{{border-color:var(--accent)}}
.stat.active{{border-color:var(--accent);background:rgba(86,156,214,.1)}}
.stat-num{{font-size:1.3rem;font-weight:700}}
.stat-label{{font-size:.65rem;color:var(--dim);margin-top:2px}}
.search{{width:100%;padding:9px 14px;background:var(--input);border:1px solid var(--border);border-radius:8px;color:var(--fg);font-size:.85rem;margin-bottom:10px;outline:none}}
.search:focus{{border-color:var(--accent)}}
.tabs{{display:flex;gap:6px;margin-bottom:12px;overflow-x:auto;-webkit-overflow-scrolling:touch}}
.tab{{padding:4px 14px;border-radius:14px;font-size:.75rem;border:1px solid var(--border);background:var(--card);color:var(--dim);cursor:pointer;white-space:nowrap;flex-shrink:0}}
.tab.active{{background:var(--accent);color:#fff;border-color:var(--accent)}}
.tab .count{{font-size:.65rem;margin-left:3px;opacity:.7}}
.cards{{display:flex;flex-direction:column;gap:8px}}
.card{{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:10px 12px;cursor:pointer;transition:border-color .1s}}
.card:hover{{border-color:var(--accent)}}
.card-header{{display:flex;align-items:center;gap:6px;margin-bottom:3px}}
.card-type{{font-size:.6rem;padding:1px 7px;border-radius:8px;font-weight:600;flex-shrink:0}}
.card-title{{font-size:.85rem;font-weight:500;flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.card-importance{{font-size:.65rem;color:var(--dim);flex-shrink:0}}
.card-preview{{font-size:.73rem;color:var(--dim);line-height:1.4;margin-bottom:5px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}}
.card-footer{{display:flex;gap:4px;flex-wrap:wrap;align-items:center}}
.tag{{font-size:.6rem;padding:1px 6px;border-radius:6px;background:rgba(86,156,214,.1);color:var(--accent)}}
.card-time{{font-size:.6rem;color:var(--dim);margin-left:auto}}
.graph-section{{margin-top:16px}}
.graph-toggle{{display:flex;align-items:center;gap:6px;padding:8px 14px;background:var(--card);border:1px solid var(--border);border-radius:8px;color:var(--dim);font-size:.78rem;cursor:pointer;width:100%;text-align:left}}
.graph-toggle:hover{{color:var(--fg)}}
#cy{{width:100%;height:350px;background:var(--card);border:1px solid var(--border);border-radius:8px;margin-top:8px;display:none}}
#cy.show{{display:block}}
@media(min-width:600px){{body{{padding:24px}}.cards{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}.stats{{gap:10px}}}}
</style>
</head>
<body>

<div class="stats">
<div class="stat" onclick="filterPinned(this)" id="stat-total"><div class="stat-num" style="color:var(--fg)">{total}</div><div class="stat-label">总记忆</div></div>
<div class="stat" onclick="filterPinned(this)" id="stat-week"><div class="stat-num" style="color:#569cd6">{this_week}</div><div class="stat-label">本周新增</div></div>
<div class="stat" onclick="filterPinned(this)" id="stat-pinned"><div class="stat-num" style="color:#dcdcaa">{pinned}</div><div class="stat-label">固定记忆</div></div>
<div class="stat"><div class="stat-num" style="color:#c586c0">{avg_importance}</div><div class="stat-label">平均重要性</div></div>
</div>

<input class="search" placeholder="搜索记忆..." oninput="doSearch(this.value)" id="search">

<div class="tabs" id="tabs">
<div class="tab active" onclick="filterType('all',this)" data-type="all">全部<span class="count">{total}</span></div>
{tabs_html}
</div>

<div class="cards" id="cards">
{cards_html}
</div>

<div class="graph-section">
<button class="graph-toggle" onclick="toggleGraph()" id="graphBtn">话题图谱</button>
<div id="cy"></div>
</div>

<script>
var allCards = document.querySelectorAll('.card');
var activeType = 'all';
var activePinned = false;

function filterType(type, el) {{
  activeType = type;
  activePinned = false;
  document.querySelectorAll('.stat').forEach(function(s){{s.classList.remove('active')}});
  document.querySelectorAll('.tab').forEach(function(t){{t.classList.remove('active')}});
  el.classList.add('active');
  applyFilters(document.getElementById('search').value.toLowerCase());
}}

function filterPinned(el) {{
  if (el.id === 'stat-pinned') {{
    activePinned = !activePinned;
    if (activePinned) {{
      document.querySelectorAll('.tab').forEach(function(t){{t.classList.remove('active')}});
      activeType = 'all';
    }}
  }} else {{
    activePinned = false;
  }}
  document.querySelectorAll('.stat').forEach(function(s){{s.classList.remove('active')}});
  if (activePinned) el.classList.add('active');
  applyFilters(document.getElementById('search').value.toLowerCase());
}}

function doSearch(val) {{ applyFilters(val.toLowerCase()); }}

function applyFilters(searchVal) {{
  var visible = 0;
  allCards.forEach(function(c) {{
    var typeMatch = activeType === 'all' || c.dataset.type === activeType;
    var pinnedMatch = !activePinned || c.dataset.pinned === 'true';
    var text = (c.dataset.title + ' ' + c.dataset.preview + ' ' + c.dataset.tags).toLowerCase();
    var searchMatch = searchVal === '' || text.indexOf(searchVal) >= 0;
    c.style.display = (typeMatch && pinnedMatch && searchMatch) ? '' : 'none';
    if (typeMatch && pinnedMatch && searchMatch) visible++;
  }});
  document.getElementById('graphBtn').textContent = '话题图谱(' + visible + '条)';
}}

var cyInit = false;
function toggleGraph() {{
  var cyEl = document.getElementById('cy');
  cyEl.classList.toggle('show');
  if (cyEl.classList.contains('show') && !cyInit) {{
    cyInit = true;
    var visibleIds = new Set();
    allCards.forEach(function(c){{ if(c.style.display !== 'none') visibleIds.add(c.dataset.id); }});
    var cy = cytoscape({{
      container: document.getElementById('cy'),
      elements: {nodes_json}.filter(function(n){{return visibleIds.has(n.data.id)}}).concat(
        {edges_json}.filter(function(e){{return visibleIds.has(e.data.source) && visibleIds.has(e.data.target)}})
      ),
      style: [
        {{selector:'node',style:{{'background-color':'#569cd6','label':'data(label)','color':'#d4d4d4','font-size':'9px','text-valign':'bottom','text-halign':'center','text-max-width':'80px'}}}},
        {{selector:'node[type="decision"]',style:{{'background-color':'#3fb950','shape':'diamond'}}}},
        {{selector:'node[type="lesson"]',style:{{'background-color':'#d2991d','shape':'triangle'}}}},
        {{selector:'edge',style:{{'width':1,'line-color':'rgba(255,255,255,.06)','curve-style':'bezier'}}}}
      ],
      layout:{{name:'cose',padding:30}}
    }});
  }}
}}
</script>
</body>
</html>"""


def generate(store: MemoryStore, output_path: Path):
    memories = store.list()
    stats = _compute_stats(memories)
    nodes, edges = _build_graph(memories)
    cards = _build_cards(memories)

    tab_lines = _build_tab_lines(stats)
    card_lines = _build_card_lines(cards)

    html = HTML_TEMPLATE.format(
        total=stats["total"],
        this_week=stats["this_week"],
        pinned=stats["pinned"],
        avg_importance=stats["avg_importance"],
        tabs_html="\n".join(tab_lines),
        cards_html="\n".join(card_lines),
        nodes_json=json.dumps(nodes, ensure_ascii=False),
        edges_json=json.dumps(edges, ensure_ascii=False),
    )

    output_path.write_text(html, encoding="utf-8")
    return len(memories)


def _build_tab_lines(stats):
    tc = stats.get("type_counts", {})
    order = ["decision", "lesson", "pattern", "note", "conversation"]
    lines = []
    for t in order:
        count = tc.get(t, 0)
        if count > 0:
            label = TYPE_LABELS.get(t, t)
            lines.append(
                f'<div class="tab" onclick="filterType(\'{t}\',this)" data-type="{t}">{label}<span class="count">{count}</span></div>'
            )
    return lines


def _build_card_lines(cards):
    lines = []
    for c in cards:
        label = TYPE_LABELS.get(c["type"], c["type"])
        color = TYPE_COLORS.get(c["type"], "#8b949e")
        tags_html = "".join(f'<span class="tag">{t}</span>' for t in c["tags"][:4])
        pinned = 'data-pinned="true"' if c["pinned"] else ""
        lines.append(
            f'<div class="card" data-type="{c["type"]}" data-id="{c["id"]}" data-title="{c["title"]}" data-preview="{c["preview"]}" data-tags="{c["tags_str"]}" {pinned}>'
            f'<div class="card-header"><span class="card-type" style="background:{color}22;color:{color}">{label}</span>'
            f'<span class="card-title">{c["title"]}</span><span class="card-importance">&#11088;{c["importance"]}</span></div>'
            f'<div class="card-preview">{c["preview"]}</div>'
            f'<div class="card-footer">{tags_html}<span class="card-time">{c["time"]}</span></div>'
            f"</div>"
        )
    return lines


def _compute_stats(memories):
    now = datetime.now(timezone.utc)
    week_ago = (now - timedelta(days=7)).isoformat()
    type_counts = {}
    total_imp = 0
    pinned = 0
    this_week = 0
    for m in memories:
        type_counts[m.type] = type_counts.get(m.type, 0) + 1
        total_imp += m.importance or 5
        if getattr(m, "pinned", False):
            pinned += 1
        if m.created_at and m.created_at >= week_ago:
            this_week += 1
    return {
        "total": len(memories),
        "this_week": this_week,
        "pinned": pinned,
        "avg_importance": round(total_imp / max(len(memories), 1), 1),
        "type_counts": type_counts,
    }


def _build_cards(memories):
    cards = []
    for m in memories:
        preview = (m.content or "")[:120].replace("\n", " ").replace('"', "'")
        title = (m.title or "")[:60].replace('"', "'")
        tags_str = " ".join(m.tags or [])
        cards.append({
            "id": m.id,
            "type": m.type,
            "title": title,
            "preview": preview,
            "tags": (m.tags or [])[:4],
            "tags_str": tags_str,
            "importance": m.importance or 5,
            "time": _format_time(m.created_at),
            "pinned": getattr(m, "pinned", False),
        })
    return cards


def _build_graph(memories):
    nodes = []
    edges = []
    added = set()
    for m in memories:
        if m.id in added:
            continue
        added.add(m.id)
        label = (m.title or "")[:20]
        nodes.append({"data": {"id": m.id, "label": label.replace('"', "'"), "type": m.type}})
        for link in (m.links or []):
            edges.append({"data": {"source": m.id, "target": link}})
    return nodes, edges


def _format_time(ts):
    if not ts:
        return ""
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        diff = datetime.now(timezone.utc) - dt
        if diff.days == 0:
            return "今天"
        elif diff.days == 1:
            return "昨天"
        elif diff.days < 7:
            return f"{diff.days}天前"
        else:
            return dt.strftime("%m-%d")
    except Exception:
        return ""
