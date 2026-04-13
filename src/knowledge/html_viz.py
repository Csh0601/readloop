"""知识图谱 HTML 交互式可视化 -- 基于 vis-network (CDN)

Upgraded with Graphify patterns: sidebar, community legend,
info panel, degree-based sizing, confidence edge styling.
Dual encoding: color=community, shape=node_type.
"""
from __future__ import annotations

import html as _html
import json
from pathlib import Path

from .models import KnowledgeGraph


def _esc(s: str) -> str:
    """HTML-escape a string to prevent XSS in tooltips."""
    return _html.escape(str(s))

# Color scheme per node type (fallback when no communities)
NODE_COLORS = {
    "paper": "#4A90D9",
    "concept": "#E8A838",
    "method": "#50C878",
    "dataset": "#DA70D6",
    "metric": "#FF6B6B",
}

NODE_SHAPES = {
    "paper": "box",
    "concept": "ellipse",
    "method": "diamond",
    "dataset": "database",
    "metric": "triangle",
}

EDGE_COLORS = {
    "proposes": "#4A90D9",
    "uses": "#888888",
    "improves": "#50C878",
    "compares": "#E8A838",
    "contradicts": "#FF4444",
    "complements": "#9B59B6",
    "shared_concept": "#FF69B4",
    "evaluated_on": "#888888",
}

# From Graphify: 10-color community palette
COMMUNITY_COLORS = [
    "#4E79A7", "#F28E2B", "#E15759", "#76B7B2", "#59A14F",
    "#EDC948", "#B07AA1", "#FF9DA7", "#9C755F", "#BAB0AC",
]


def generate_html(
    graph: KnowledgeGraph,
    output_path: Path,
    communities: dict[int, list[str]] | None = None,
) -> Path:
    """Generate interactive HTML visualization with sidebar and community support."""
    has_communities = communities is not None and len(communities) > 0

    # Compute degree for sizing
    degree: dict[str, int] = {}
    for node in graph.nodes.values():
        degree[node.id] = len(graph.get_edges_for_node(node.id))
    max_deg = max(degree.values(), default=1) or 1

    # Build vis-network nodes
    vis_nodes = []
    for node in graph.nodes.values():
        deg = degree[node.id]
        cid = node.community

        # Color: community or type fallback
        if has_communities and cid is not None:
            bg_color = COMMUNITY_COLORS[cid % len(COMMUNITY_COLORS)]
        else:
            bg_color = NODE_COLORS.get(node.type, "#999")

        # Degree-based sizing (from Graphify)
        size = 10 + 30 * (deg / max_deg)

        # Tooltip (all values HTML-escaped to prevent XSS)
        title_parts = [f"<b>{_esc(node.label)}</b>", f"Type: {_esc(node.type)}"]
        if has_communities and cid is not None:
            comm_name = graph.community_labels.get(cid, f"Community {cid}")
            title_parts.append(f"Community: {_esc(comm_name)}")
        title_parts.append(f"Connections: {deg}")
        if node.type == "paper":
            year = node.metadata.get("year", "")
            tags = ", ".join(node.metadata.get("domain_tags", [])[:3])
            if year:
                title_parts.append(f"Year: {_esc(str(year))}")
            if tags:
                title_parts.append(f"Tags: {_esc(tags)}")
        elif node.type == "concept":
            defn = node.metadata.get("definition", "")[:120]
            if defn:
                title_parts.append(f"Def: {_esc(defn)}")
        elif node.type == "method":
            desc = node.metadata.get("description", "")[:120]
            if desc:
                title_parts.append(f"Desc: {_esc(desc)}")

        vis_nodes.append({
            "id": node.id,
            "label": node.label[:35],
            "title": "<br>".join(title_parts),
            "color": {"background": bg_color, "border": bg_color,
                      "highlight": {"background": "#ffffff", "border": bg_color}},
            "shape": NODE_SHAPES.get(node.type, "dot"),
            "size": round(size, 1),
            "font": {"size": 12 if deg >= max_deg * 0.15 else 0, "color": "#eee"},
            "community": cid if cid is not None else -1,
            "community_name": graph.community_labels.get(cid, "") if cid is not None else "",
            "node_type": node.type,
            "degree": deg,
        })

    # Build vis-network edges
    vis_edges = []
    for edge in graph.edges:
        dashes = edge.weight < 0.7
        width = 2 if edge.weight >= 0.7 else 1
        opacity = 0.7 if edge.weight >= 0.7 else 0.35

        vis_edges.append({
            "from": edge.source,
            "to": edge.target,
            "title": f"{_esc(edge.relation)}: {_esc(edge.evidence[:80])}" if edge.evidence else _esc(edge.relation),
            "dashes": dashes,
            "width": width,
            "color": {"color": EDGE_COLORS.get(edge.relation, "#cccccc"), "opacity": opacity},
            "arrows": {"to": {"enabled": True, "scaleFactor": 0.5}},
        })

    nodes_json = json.dumps(vis_nodes, ensure_ascii=False)
    edges_json = json.dumps(vis_edges, ensure_ascii=False)

    # Community legend data
    legend_items = []
    if has_communities:
        for cid in sorted(communities.keys()):
            label = graph.community_labels.get(cid, f"Community {cid}")
            color = COMMUNITY_COLORS[cid % len(COMMUNITY_COLORS)]
            count = len(communities[cid])
            legend_items.append({"cid": cid, "label": label, "color": color, "count": count})
    legend_json = json.dumps(legend_items, ensure_ascii=False)

    # Type legend data
    type_counts: dict[str, int] = {}
    for node in graph.nodes.values():
        type_counts[node.type] = type_counts.get(node.type, 0) + 1
    type_legend = []
    for t in ["paper", "concept", "method", "dataset", "metric"]:
        if t in type_counts:
            type_legend.append({"type": t, "color": NODE_COLORS[t], "count": type_counts[t],
                                "shape": NODE_SHAPES[t]})
    type_legend_json = json.dumps(type_legend, ensure_ascii=False)

    stats = graph.stats()

    html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <title>ReadLoop Knowledge Graph</title>
    <script src="https://unpkg.com/vis-network@9.1.6/standalone/umd/vis-network.min.js"></script>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ background: #0f0f1a; color: #e0e0e0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; display: flex; height: 100vh; overflow: hidden; }}
        #graph {{ flex: 1; }}
        #sidebar {{ width: 280px; background: #1a1a2e; border-left: 1px solid #2a2a4e; display: flex; flex-direction: column; overflow: hidden; }}
        #search-wrap {{ padding: 12px; border-bottom: 1px solid #2a2a4e; }}
        #search {{ width: 100%; background: #0f0f1a; border: 1px solid #3a3a5e; color: #e0e0e0; padding: 7px 10px; border-radius: 6px; font-size: 13px; outline: none; }}
        #search:focus {{ border-color: #4E79A7; }}
        #search-results {{ max-height: 140px; overflow-y: auto; padding: 4px 12px; border-bottom: 1px solid #2a2a4e; display: none; }}
        .search-item {{ padding: 4px 6px; cursor: pointer; border-radius: 4px; font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
        .search-item:hover {{ background: #2a2a4e; }}
        #info-panel {{ padding: 14px; border-bottom: 1px solid #2a2a4e; min-height: 120px; }}
        #info-panel h3 {{ font-size: 13px; color: #aaa; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.05em; }}
        #info-content {{ font-size: 13px; color: #ccc; line-height: 1.6; }}
        #info-content .field {{ margin-bottom: 5px; }}
        #info-content .field b {{ color: #e0e0e0; }}
        #info-content .empty {{ color: #555; font-style: italic; }}
        .neighbor-link {{ display: block; padding: 2px 6px; margin: 2px 0; border-radius: 3px; cursor: pointer; font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; border-left: 3px solid #333; }}
        .neighbor-link:hover {{ background: #2a2a4e; }}
        #neighbors-list {{ max-height: 130px; overflow-y: auto; margin-top: 4px; }}
        .legend-section {{ padding: 10px 12px; border-bottom: 1px solid #2a2a4e; }}
        .legend-section h3 {{ font-size: 12px; color: #aaa; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.05em; }}
        #legend-communities {{ flex: 1; overflow-y: auto; }}
        .legend-item {{ display: flex; align-items: center; gap: 8px; padding: 4px 0; cursor: pointer; border-radius: 4px; font-size: 12px; }}
        .legend-item:hover {{ background: #2a2a4e; padding-left: 4px; }}
        .legend-item.dimmed {{ opacity: 0.35; }}
        .legend-dot {{ width: 12px; height: 12px; border-radius: 50%; flex-shrink: 0; }}
        .legend-label {{ flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
        .legend-count {{ color: #666; font-size: 11px; }}
        .type-shape {{ width: 14px; height: 14px; flex-shrink: 0; display: inline-flex; align-items: center; justify-content: center; font-size: 10px; }}
        #stats {{ padding: 10px 14px; border-top: 1px solid #2a2a4e; font-size: 11px; color: #555; }}
    </style>
</head>
<body>
    <div id="graph"></div>
    <div id="sidebar">
        <div id="search-wrap">
            <input id="search" type="text" placeholder="Search nodes...">
        </div>
        <div id="search-results"></div>
        <div id="info-panel">
            <h3>Node Info</h3>
            <div id="info-content"><span class="empty">Click a node to inspect it</span></div>
        </div>
        <div class="legend-section">
            <h3>Communities</h3>
            <div id="legend-communities"></div>
        </div>
        <div class="legend-section">
            <h3>Node Types</h3>
            <div id="legend-types"></div>
        </div>
        <div id="stats">{stats['total_nodes']} nodes | {stats['total_edges']} edges | {len(communities) if has_communities else 0} communities</div>
    </div>

    <script>
const RAW_NODES = {nodes_json};
const RAW_EDGES = {edges_json};
const COMMUNITY_LEGEND = {legend_json};
const TYPE_LEGEND = {type_legend_json};

function esc(s) {{
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}}

const nodesDS = new vis.DataSet(RAW_NODES.map(n => ({{
  id: n.id, label: n.label, color: n.color, size: n.size,
  shape: n.shape, font: n.font, title: n.title,
  _community: n.community, _community_name: n.community_name,
  _node_type: n.node_type, _degree: n.degree,
}})));

const edgesDS = new vis.DataSet(RAW_EDGES.map((e, i) => ({{
  id: i, from: e.from, to: e.to, title: e.title,
  dashes: e.dashes, width: e.width, color: e.color, arrows: e.arrows,
}})));

const container = document.getElementById('graph');
const network = new vis.Network(container, {{ nodes: nodesDS, edges: edgesDS }}, {{
  physics: {{
    enabled: true,
    solver: 'forceAtlas2Based',
    forceAtlas2Based: {{
      gravitationalConstant: -60,
      centralGravity: 0.005,
      springLength: 150,
      springConstant: 0.08,
      damping: 0.4,
      avoidOverlap: 0.8,
    }},
    stabilization: {{ iterations: 200, fit: true }},
  }},
  interaction: {{
    hover: true, tooltipDelay: 100, hideEdgesOnDrag: true,
    navigationButtons: false, keyboard: false,
  }},
  nodes: {{ borderWidth: 1.5 }},
  edges: {{ smooth: {{ type: 'continuous', roundness: 0.2 }}, selectionWidth: 3 }},
}});

network.once('stabilizationIterationsDone', () => {{
  network.setOptions({{ physics: {{ enabled: false }} }});
}});

// --- Info Panel ---
function showInfo(nodeId) {{
  const n = nodesDS.get(nodeId);
  if (!n) return;
  const neighborIds = network.getConnectedNodes(nodeId);
  const neighborItems = neighborIds.map(nid => {{
    const nb = nodesDS.get(nid);
    const color = nb ? nb.color.background : '#555';
    return `<span class="neighbor-link" style="border-left-color:${{esc(color)}}" onclick="focusNode(${{JSON.stringify(nid)}})">${{esc(nb ? nb.label : nid)}}</span>`;
  }}).join('');
  document.getElementById('info-content').innerHTML = `
    <div class="field"><b>${{esc(n.label)}}</b></div>
    <div class="field">Type: ${{esc(n._node_type || 'unknown')}}</div>
    ${{n._community >= 0 ? `<div class="field">Community: ${{esc(n._community_name)}}</div>` : ''}}
    <div class="field">Degree: ${{n._degree}}</div>
    ${{neighborIds.length ? `<div class="field" style="margin-top:6px;color:#aaa;font-size:11px">Neighbors (${{neighborIds.length}})</div><div id="neighbors-list">${{neighborItems}}</div>` : ''}}
  `;
}}

function focusNode(nodeId) {{
  network.focus(nodeId, {{ scale: 1.4, animation: true }});
  network.selectNodes([nodeId]);
  showInfo(nodeId);
}}

// Click handling
let hoveredNodeId = null;
network.on('hoverNode', p => {{ hoveredNodeId = p.node; container.style.cursor = 'pointer'; }});
network.on('blurNode', () => {{ hoveredNodeId = null; container.style.cursor = 'default'; }});
container.addEventListener('click', () => {{
  if (hoveredNodeId !== null) {{ showInfo(hoveredNodeId); network.selectNodes([hoveredNodeId]); }}
}});
network.on('click', p => {{
  if (p.nodes.length > 0) showInfo(p.nodes[0]);
  else if (hoveredNodeId === null) document.getElementById('info-content').innerHTML = '<span class="empty">Click a node to inspect it</span>';
}});

// --- Search ---
const searchInput = document.getElementById('search');
const searchResults = document.getElementById('search-results');
searchInput.addEventListener('input', () => {{
  const q = searchInput.value.toLowerCase().trim();
  searchResults.innerHTML = '';
  if (!q) {{ searchResults.style.display = 'none'; return; }}
  const matches = RAW_NODES.filter(n => n.label.toLowerCase().includes(q) || n.id.toLowerCase().includes(q)).slice(0, 20);
  if (!matches.length) {{ searchResults.style.display = 'none'; return; }}
  searchResults.style.display = 'block';
  matches.forEach(n => {{
    const el = document.createElement('div');
    el.className = 'search-item';
    el.textContent = n.label;
    el.style.borderLeft = `3px solid ${{n.color.background}}`;
    el.style.paddingLeft = '8px';
    el.onclick = () => {{
      focusNode(n.id);
      searchResults.style.display = 'none';
      searchInput.value = '';
    }};
    searchResults.appendChild(el);
  }});
}});
document.addEventListener('click', e => {{
  if (!searchResults.contains(e.target) && e.target !== searchInput)
    searchResults.style.display = 'none';
}});

// --- Community Legend ---
const hiddenCommunities = new Set();
const legendEl = document.getElementById('legend-communities');
COMMUNITY_LEGEND.forEach(c => {{
  const item = document.createElement('div');
  item.className = 'legend-item';
  item.innerHTML = `<div class="legend-dot" style="background:${{c.color}}"></div>
    <span class="legend-label">${{esc(c.label)}}</span>
    <span class="legend-count">${{c.count}}</span>`;
  item.onclick = () => {{
    if (hiddenCommunities.has(c.cid)) {{
      hiddenCommunities.delete(c.cid);
      item.classList.remove('dimmed');
    }} else {{
      hiddenCommunities.add(c.cid);
      item.classList.add('dimmed');
    }}
    applyVisibility();
  }};
  legendEl.appendChild(item);
}});

// --- Type Legend ---
const hiddenTypes = new Set();
const typesEl = document.getElementById('legend-types');
TYPE_LEGEND.forEach(t => {{
  const item = document.createElement('div');
  item.className = 'legend-item';
  item.innerHTML = `<div class="legend-dot" style="background:${{t.color}}"></div>
    <span class="legend-label">${{t.type}}</span>
    <span class="legend-count">${{t.count}}</span>`;
  item.onclick = () => {{
    if (hiddenTypes.has(t.type)) {{
      hiddenTypes.delete(t.type);
      item.classList.remove('dimmed');
    }} else {{
      hiddenTypes.add(t.type);
      item.classList.add('dimmed');
    }}
    applyVisibility();
  }};
  typesEl.appendChild(item);
}});

// --- Visibility (combines community + type + search filters) ---
function applyVisibility() {{
  const updates = RAW_NODES.map(n => {{
    const communityHidden = hiddenCommunities.has(n.community);
    const typeHidden = hiddenTypes.has(n.node_type);
    return {{ id: n.id, hidden: communityHidden || typeHidden }};
  }});
  nodesDS.update(updates);
}}
    </script>
</body>
</html>"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path
