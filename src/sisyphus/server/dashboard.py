"""Dashboard generator — single HTML with knowledge graph + stats.

Zero dependencies beyond Python stdlib.
Cytoscape.js and Chart.js loaded from CDN.
"""

import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

from sisyphus.memory.store import MemoryStore


def generate(store: MemoryStore, output_path: Path):
    memories = store.list()
    nodes, edges = _build_graph(memories)
    stats = _compute_stats(memories)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Sisyphus Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/cytoscape@3.28.1/dist/cytoscape.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#0d1117;color:#c9d1d9;font-family:-apple-system,sans-serif;padding:1rem}}
h1{{color:#58a6ff;margin-bottom:1rem}}
.grid{{display:grid;grid-template-columns:2fr 1fr;gap:1rem}}
#cy{{width:100%;height:500px;background:#161b22;border:1px solid #30363d;border-radius:8px}}
.panel{{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:1rem}}
.chart-wrap{{height:180px;margin:.5rem 0}}
.stat{{display:flex;justify-content:space-between;padding:.3rem 0;border-bottom:1px solid #21262d}}
.stat:last-child{{border:none}}
.stat-val{{color:#58a6ff;font-weight:600}}
</style>
</head>
<body>
<h1>Sisyphus Knowledge Dashboard</h1>
<div class="grid">
<div id="cy"></div>
<div class="panel">
<h3>Stats</h3>
<div class="stat"><span>Total</span><span class="stat-val">{stats['total']}</span></div>
<div class="stat"><span>This Week</span><span class="stat-val">{stats['this_week']}</span></div>
<div class="stat"><span>Pinned</span><span class="stat-val">{stats['pinned']}</span></div>
<div class="stat"><span>Avg Importance</span><span class="stat-val">{stats['avg_importance']}</span></div>
<div class="chart-wrap"><canvas id="typeChart"></canvas></div>
</div>
</div>
<script>
// Knowledge Graph
var cy = cytoscape({{
  container: document.getElementById('cy'),
  elements: {json.dumps(nodes + edges)},
  style: [
    {{selector:'node',style:{{'background-color':'#58a6ff','label':'data(label)','color':'#c9d1d9','font-size':'10px','text-valign':'bottom','text-halign':'center'}}}},
    {{selector:'node[type="decision"]',style:{{'background-color':'#3fb950','shape':'diamond'}}}},
    {{selector:'node[type="lesson"]',style:{{'background-color':'#d2991d','shape':'triangle'}}}},
    {{selector:'edge',style:{{'width':1,'line-color':'#30363d','curve-style':'bezier'}}}}
  ],
  layout:{{name:'cose',padding:20}}
}});

// Type Distribution
new Chart(document.getElementById('typeChart'),{{
  type:'doughnut',
  data:{{
    labels:{json.dumps(list(stats['type_counts'].keys()))},
    datasets:[{{data:{json.dumps(list(stats['type_counts'].values()))},backgroundColor:['#58a6ff','#3fb950','#d2991d','#f85149','#a371f7','#8b949e']}}]
  }},
  options:{{plugins:{{legend:{{labels:{{color:'#8b949e',font:{{size:10}}}}}}}}}}
}});
</script>
</body>
</html>"""
    output_path.write_text(html)
    return len(memories)


def _build_graph(memories):
    nodes = []
    edges = []
    added = set()
    for m in memories:
        if m.id in added:
            continue
        added.add(m.id)
        nodes.append({
            "data": {"id": m.id, "label": m.title[:30], "type": m.type},
            "classes": m.type,
        })
        for link in (m.links or []):
            edges.append({"data": {"source": m.id, "target": link}})
    return nodes, edges


def _compute_stats(memories):
    now = datetime.now(timezone.utc)
    week_ago = (now - timedelta(days=7)).isoformat()
    type_counts = {}
    total_importance = 0
    pinned = 0
    this_week = 0
    for m in memories:
        type_counts[m.type] = type_counts.get(m.type, 0) + 1
        total_importance += m.importance or 5
        if getattr(m, 'pinned', False):
            pinned += 1
        if m.created_at and m.created_at >= week_ago:
            this_week += 1
    return {
        "total": len(memories),
        "this_week": this_week,
        "pinned": pinned,
        "avg_importance": round(total_importance / max(len(memories), 1), 1),
        "type_counts": type_counts,
    }
