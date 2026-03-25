#!/usr/bin/env python3
"""Build a navigable markdown catalog of all reusable engine objects.

Scans: workers, executors, templates, contracts, fixups, plugins, archetypes, schemas.
Outputs: library/catalog/ with interlinked markdown files.

Usage:
    python3 scripts/build_catalog.py
    python3 scripts/build_catalog.py --search "financeiro"
    python3 scripts/build_catalog.py --search "web_search"
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG_DIR = ROOT / "library" / "catalog"


def scan_workers() -> list[dict]:
    """Scan INDEX.json for all workers."""
    index_path = ROOT / "contracts" / "steps" / "INDEX.json"
    if not index_path.exists():
        return []
    idx = json.loads(index_path.read_text(encoding="utf-8"))
    return list(idx.get("steps", {}).values())


def scan_executors() -> list[dict]:
    """Scan lib/executors/ for all executor plugins."""
    executors = []
    exec_dir = ROOT / "lib" / "executors"
    for f in sorted(exec_dir.glob("*.py")):
        if f.name.startswith("_"):
            continue
        name = f.stem
        docstring = ""
        is_available = False
        # Extract docstring from file
        content = f.read_text(encoding="utf-8")
        for line in content.splitlines():
            if line.strip().startswith('"""') and not docstring:
                docstring = line.strip().strip('"').strip()
                break
        executors.append({
            "name": name,
            "file": f"lib/executors/{f.name}",
            "docstring": docstring,
        })
    return executors


def scan_templates() -> dict[str, list[dict]]:
    """Scan templates/ for components, pages, contracts, agent docs."""
    result = {"components": [], "pages": [], "contracts": [], "agent": []}
    tmpl_dir = ROOT / "templates"

    for subdir, key in [("components", "components"), ("pages", "pages"),
                         ("contracts", "contracts"), ("agent", "agent")]:
        d = tmpl_dir / subdir
        if not d.exists():
            continue
        for f in sorted(d.glob("*")):
            if f.name.startswith("_") or f.name.startswith("."):
                continue
            first_line = ""
            try:
                first_line = f.read_text(encoding="utf-8").splitlines()[0][:100]
            except Exception:
                pass
            result[key].append({
                "name": f.stem,
                "file": f"templates/{subdir}/{f.name}",
                "first_line": first_line,
            })
    return result


def scan_fixups() -> list[dict]:
    """Scan fixup registry."""
    reg_path = ROOT / "lib" / "fixups" / "registry.json"
    if not reg_path.exists():
        return []
    reg = json.loads(reg_path.read_text(encoding="utf-8"))
    return reg.get("fixups", [])


def scan_r10_plugins() -> list[dict]:
    """Scan R10a validation plugins."""
    plugins = []
    plugin_dir = ROOT / "lib" / "r10_plugins"
    for f in sorted(plugin_dir.glob("*.py")):
        if f.name.startswith("_"):
            continue
        plugins.append({"name": f.stem, "file": f"lib/r10_plugins/{f.name}"})
    return plugins


def scan_archetypes() -> list[dict]:
    """Scan pipeline archetypes."""
    arch_path = ROOT / "config" / "pipeline_archetypes.json"
    if not arch_path.exists():
        return []
    data = json.loads(arch_path.read_text(encoding="utf-8"))
    result = []
    for name, spec in data.get("archetypes", {}).items():
        result.append({
            "name": name,
            "description": spec.get("description", ""),
            "steps": len(spec.get("steps", [])),
            "default_executor": spec.get("default_executor", ""),
        })
    return result


def scan_schemas() -> list[dict]:
    """Scan contract schemas."""
    schemas = []
    for f in sorted((ROOT / "contracts").glob("*.schema.json")):
        schemas.append({"name": f.stem, "file": f"contracts/{f.name}"})
    for f in sorted((ROOT / "contracts" / "schemas").glob("*.json")):
        schemas.append({"name": f.stem, "file": f"contracts/schemas/{f.name}"})
    return schemas


def scan_generic_workers() -> list[dict]:
    """Scan lib/workers/ for generic reusable workers."""
    workers = []
    workers_dir = ROOT / "lib" / "workers"
    if not workers_dir.exists():
        return []
    for f in sorted(workers_dir.glob("*.py")):
        if f.name.startswith("_"):
            continue
        docstring = ""
        content = f.read_text(encoding="utf-8")
        for line in content.splitlines():
            if line.strip().startswith('"""') and not docstring:
                docstring = line.strip().strip('"').strip()
                break
        workers.append({"name": f.stem, "file": f"lib/workers/{f.name}", "docstring": docstring})
    return workers


def generate_index(workers, executors, templates, fixups, plugins, archetypes, schemas, generic_workers):
    """Generate _index.md — the entry point."""
    lines = [
        "# Engine Catalog",
        "",
        "All reusable objects in the pipeline engine. Auto-generated by `build_catalog.py`.",
        "**Do not edit manually** — run `python3 scripts/build_catalog.py` to regenerate.",
        "",
        "## Quick Navigation",
        "",
        f"- [[_by_domain]] — {len([w for w in workers if not w.get('abstract')])} workers by domain",
        f"- [[_by_type]] — {len([w for w in workers if w.get('abstract')])} super-classes with children",
        f"- [[_executors]] — {len(executors)} executor plugins",
        f"- [[_templates]] — {sum(len(v) for v in templates.values())} templates (components, pages, contracts, agent)",
        f"- [[_archetypes]] — {len(archetypes)} pipeline archetypes",
        f"- [[_schemas]] — {len(schemas)} schemas",
        f"- [[_generic_workers]] — {len(generic_workers)} utility workers (lib/workers/)",
        f"- [[_fixups]] — {len(fixups)} fixups registered",
        f"- [[_plugins]] — {len(plugins)} R10a validation plugins",
        "",
        "## Most Used Workers",
        "",
    ]
    # Top workers by proven_in_production
    proven = [w for w in workers if w.get("library", {}).get("proven_in_production")]
    for w in proven[:10]:
        name = w["id"]
        desc = w.get("description", "")[:80]
        lines.append(f"- [[{name}]] — {desc}")

    return "\n".join(lines) + "\n"


def generate_by_domain(workers):
    """Generate _by_domain.md with hierarchical domain.subdomain."""
    # Load domain registry for descriptions
    registry = {}
    reg_path = ROOT / "config" / "domains.json"
    if reg_path.exists():
        registry = json.loads(reg_path.read_text(encoding="utf-8")).get("domains", {})

    # Group: domain -> subdomain -> [workers]
    hierarchy: dict[str, dict[str, list]] = {}
    for w in workers:
        if w.get("abstract"):
            continue
        lib = w.get("library", {})
        domain = lib.get("domain", "uncategorized")
        subdomain = lib.get("subdomain", "geral")
        hierarchy.setdefault(domain, {}).setdefault(subdomain, []).append(w)
        # Also list in also_relevant domains (as cross-ref)
        for ref in lib.get("also_relevant", []):
            if "." in ref:
                rd, rs = ref.split(".", 1)
                hierarchy.setdefault(rd, {}).setdefault(rs, [])

    lines = ["# Workers by Domain", "", "Auto-generated. [[_index|← Back to catalog]]", ""]
    for domain in sorted(hierarchy.keys()):
        domain_desc = registry.get(domain, {}).get("description", "")
        lines.append(f"## {domain}")
        if domain_desc:
            lines.append(f"*{domain_desc}*")
        lines.append("")

        for subdomain in sorted(hierarchy[domain].keys()):
            sub_desc = registry.get(domain, {}).get("subdomains", {}).get(subdomain, "")
            workers_in_sub = hierarchy[domain][subdomain]
            lines.append(f"### {domain}.{subdomain}")
            if sub_desc:
                lines.append(f"*{sub_desc}*")
            lines.append("")

            if not workers_in_sub:
                lines.append("*(no workers yet)*")
                lines.append("")
                continue

            lines.append("| Worker | Type | Origin | Cost | Description |")
            lines.append("|---|---|---|---|---|")
            for w in sorted(workers_in_sub, key=lambda x: x["id"]):
                name = w["id"]
                wtype = w.get("type", "?")
                origin = w.get("library", {}).get("origin", "?")
                cost = w.get("library", {}).get("typical_cost_usd", 0)
                desc = w.get("description", "")[:60]
                # Mark cross-domain workers
                primary_domain = w.get("library", {}).get("domain", "")
                xref = " ↗" if primary_domain != domain else ""
                lines.append(f"| [[{name}]]{xref} | {wtype} | {origin} | ${cost} | {desc} |")
            lines.append("")

    return "\n".join(lines) + "\n"


def generate_by_type(workers):
    """Generate _by_type.md — super-classes with children."""
    abstracts = [w for w in workers if w.get("abstract")]
    by_parent: dict[str, list] = {}
    for w in workers:
        parent = w.get("_extends", w.get("extends", ""))
        if parent:
            by_parent.setdefault(parent, []).append(w)

    lines = ["# Workers by Type (Inheritance)", "", "Auto-generated. [[_index|← Back to catalog]]", ""]
    for a in sorted(abstracts, key=lambda x: x["id"]):
        name = a["id"]
        desc = a.get("description", "")[:80]
        children = by_parent.get(name, [])
        lines.append(f"## [[{name}]] — {desc}")
        lines.append("")
        if children:
            for c in sorted(children, key=lambda x: x["id"]):
                cdesc = c.get("description", "")[:60]
                lines.append(f"- [[{c['id']}]] — {cdesc}")
        else:
            lines.append("- *(no concrete implementations yet)*")
        lines.append("")

    return "\n".join(lines) + "\n"


def generate_executors(executors):
    """Generate _executors.md."""
    lines = [
        "# Executors", "",
        "Auto-generated. [[_index|← Back to catalog]]",
        "Full documentation: see `docs/EXECUTORS.md`.", "",
        "| Executor | File | Description |",
        "|---|---|---|",
    ]
    for e in executors:
        lines.append(f"| `{e['name']}` | `{e['file']}` | {e['docstring'][:80]} |")
    return "\n".join(lines) + "\n"


def generate_templates(templates):
    """Generate _templates.md."""
    lines = ["# Templates", "", "Auto-generated. [[_index|← Back to catalog]]", ""]
    for category, items in templates.items():
        if not items:
            continue
        lines.append(f"## {category.title()}")
        lines.append("")
        for t in items:
            lines.append(f"- **{t['name']}** (`{t['file']}`)")
        lines.append("")
    return "\n".join(lines) + "\n"


def generate_archetypes(archetypes):
    """Generate _archetypes.md."""
    lines = [
        "# Pipeline Archetypes", "",
        "Auto-generated. [[_index|← Back to catalog]]", "",
        "| Archetype | Steps | Executor | Description |",
        "|---|---|---|---|",
    ]
    for a in archetypes:
        lines.append(f"| `{a['name']}` | {a['steps']} | {a['default_executor']} | {a['description'][:60]} |")
    return "\n".join(lines) + "\n"


def generate_schemas(schemas):
    lines = ["# Schemas", "", "Auto-generated. [[_index|← Back to catalog]]", ""]
    for s in schemas:
        lines.append(f"- **{s['name']}** (`{s['file']}`)")
    return "\n".join(lines) + "\n"


def generate_generic_workers(generic_workers):
    lines = [
        "# Generic Workers (lib/workers/)", "",
        "Auto-generated. [[_index|← Back to catalog]]", "",
        "| Worker | File | Description |",
        "|---|---|---|",
    ]
    for w in generic_workers:
        lines.append(f"| `{w['name']}` | `{w['file']}` | {w['docstring'][:80]} |")
    return "\n".join(lines) + "\n"


def generate_fixups(fixups):
    lines = ["# Fixups", "", "Auto-generated. [[_index|← Back to catalog]]", ""]
    if not fixups:
        lines.append("*No fixups registered in this engine. Consumer repos add domain-specific fixups.*")
    for f in fixups:
        lines.append(f"- **{f.get('id', '?')}** — {f.get('description', '')[:60]}")
    return "\n".join(lines) + "\n"


def generate_plugins(plugins):
    lines = ["# R10a Validation Plugins", "", "Auto-generated. [[_index|← Back to catalog]]", ""]
    for p in plugins:
        lines.append(f"- **{p['name']}** (`{p['file']}`)")
    return "\n".join(lines) + "\n"


def generate_worker_note(worker):
    """Generate individual worker note."""
    w = worker
    name = w["id"]
    extends = w.get("_extends", w.get("extends", ""))
    lib = w.get("library", {})

    lines = [
        f"# {w.get('name', name)}",
        "",
        f"**ID:** `{name}`",
    ]
    if extends:
        lines.append(f"**Extends:** [[{extends}]]")
    lines.append(f"**Type:** `{w.get('type', '?')}`")
    if w.get("abstract"):
        lines.append("**Abstract:** yes (cannot be used directly in DAG)")
    lines.append("")
    lines.append(w.get("description", ""))
    lines.append("")

    # Library metadata
    if lib:
        lines.append("## Library Info")
        lines.append("")
        if lib.get("origin"):
            lines.append(f"- **Origin:** {lib['origin']} ({lib.get('origin_version', '')})")
        if lib.get("proven_in_production"):
            lines.append("- **Proven in production:** yes")
        if lib.get("typical_cost_usd") is not None:
            lines.append(f"- **Typical cost:** ${lib['typical_cost_usd']}")
        if lib.get("typical_duration_s"):
            lines.append(f"- **Typical duration:** {lib['typical_duration_s']}s")
        if lib.get("quality_notes"):
            lines.append(f"- **Quality notes:** {lib['quality_notes']}")
        lines.append("")

    # Domain / Subdomain
    domain = lib.get("domain")
    subdomain = lib.get("subdomain")
    if domain and subdomain:
        lines.append(f"**Domain:** `{domain}.{subdomain}`")
        also = lib.get("also_relevant", [])
        if also:
            lines.append(f"**Also relevant:** {', '.join(f'`{a}`' for a in also)}")
        lines.append("")
    elif lib.get("domains"):
        # Legacy flat list — flag for migration
        lines.append(f"**Domains (legacy):** {', '.join(lib['domains'])}")
        lines.append("")

    # Complementary
    comp = lib.get("complementary_workers", [])
    if comp:
        lines.append("## Complementary Workers")
        lines.append("")
        for c in comp:
            lines.append(f"- [[{c}]]")
        lines.append("")

    # Suggested fixups
    fixups = lib.get("suggested_fixups", w.get("suggested_fixups", []))
    if fixups:
        lines.append("## Suggested Fixups")
        lines.append("")
        for f in fixups:
            lines.append(f"- `{f}`")
        lines.append("")

    # Use cases
    cases = lib.get("use_cases", [])
    if cases:
        lines.append("## Use Cases")
        lines.append("")
        for c in cases:
            lines.append(f"- {c}")
        lines.append("")

    # Known limitations
    lims = w.get("known_limitations", [])
    if lims:
        lines.append("## Known Limitations")
        lines.append("")
        for l in lims:
            lines.append(f"- {l}")
        lines.append("")

    lines.append("---")
    lines.append("[[_index|← Back to catalog]] | [[_by_domain|By domain]] | [[_by_type|By type]]")

    return "\n".join(lines) + "\n"


## ---------------------------------------------------------------------------
## Graph builder + ranked search (inspired by cognitive-plugin v0.4.0)
## ---------------------------------------------------------------------------

import re
import sqlite3

GRAPH_DB = CATALOG_DIR / "catalog.db"
WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")


def build_graph(catalog_files: dict[Path, str]) -> None:
    """Extract [[wikilinks]] from catalog markdown, build SQLite graph with PageRank."""
    db = sqlite3.connect(str(GRAPH_DB))
    db.execute("DROP TABLE IF EXISTS graph_nodes")
    db.execute("DROP TABLE IF EXISTS graph_edges")
    db.execute("DROP TABLE IF EXISTS fts_content")
    db.execute("""CREATE TABLE graph_nodes (
        id TEXT PRIMARY KEY,
        label TEXT,
        type TEXT,
        in_degree INTEGER DEFAULT 0,
        out_degree INTEGER DEFAULT 0,
        pagerank REAL DEFAULT 0.0
    )""")
    db.execute("""CREATE TABLE graph_edges (
        source TEXT, target TEXT,
        relation TEXT DEFAULT 'references'
            CHECK(relation IN ('extends', 'complementary', 'suggested_fixup', 'references', 'structural')),
        weight REAL DEFAULT 0.5
            CHECK(weight >= 0.0 AND weight <= 1.0),
        UNIQUE(source, target)
    )""")
    # FTS5 for text search
    db.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS fts_content USING fts5(
        id, type, content, tokenize='porter'
    )""")

    # Typed edge weights (inspired by cognitive-plugin v0.4.1)
    EDGE_WEIGHTS = {
        "extends": 1.0,       # inheritance — strongest relation
        "complementary": 0.7, # works well together
        "suggested_fixup": 0.6,
        "references": 0.5,    # default
        "structural": 0.3,    # index page mentions
    }

    def _classify_edge(line: str, source_type: str) -> tuple[str, float]:
        """Infer edge type from the markdown line context."""
        ll = line.lower().strip()
        if "**extends:**" in ll or "extends" in ll and "[[" in ll:
            return "extends", EDGE_WEIGHTS["extends"]
        if "complementary" in ll:
            return "complementary", EDGE_WEIGHTS["complementary"]
        if "fixup" in ll:
            return "suggested_fixup", EDGE_WEIGHTS["suggested_fixup"]
        if source_type == "index":
            return "structural", EDGE_WEIGHTS["structural"]
        return "references", EDGE_WEIGHTS["references"]

    # Extract nodes and edges
    nodes: dict[str, dict] = {}
    edges: list[tuple[str, str, str, float]] = []  # (source, target, relation, weight)

    for path, content in catalog_files.items():
        node_id = path.stem
        node_type = "index" if node_id.startswith("_") else "worker"
        if path.parent.name == "catalog":
            node_type = "index"

        nodes[node_id] = {"label": node_id, "type": node_type, "content": content}

        # Extract wikilinks with line context for type inference
        for line in content.splitlines():
            for match in WIKILINK_RE.finditer(line):
                target = match.group(1)
                if target != node_id:
                    relation, weight = _classify_edge(line, node_type)
                    edges.append((node_id, target, relation, weight))
                    if target not in nodes:
                        nodes[target] = {"label": target, "type": "reference", "content": ""}

    # Insert nodes
    for nid, info in nodes.items():
        db.execute("INSERT OR REPLACE INTO graph_nodes (id, label, type) VALUES (?, ?, ?)",
                    (nid, info["label"], info["type"]))
        if info["content"]:
            db.execute("INSERT INTO fts_content (id, type, content) VALUES (?, ?, ?)",
                        (nid, info["type"], info["content"]))

    # Insert edges and compute degrees
    for source, target, relation, weight in edges:
        try:
            db.execute("INSERT INTO graph_edges (source, target, relation, weight) VALUES (?, ?, ?, ?)",
                       (source, target, relation, weight))
        except sqlite3.IntegrityError:
            pass  # duplicate edge

    # Compute degrees
    for row in db.execute("SELECT target, COUNT(*) FROM graph_edges GROUP BY target"):
        db.execute("UPDATE graph_nodes SET in_degree = ? WHERE id = ?", (row[1], row[0]))
    for row in db.execute("SELECT source, COUNT(*) FROM graph_edges GROUP BY source"):
        db.execute("UPDATE graph_nodes SET out_degree = ? WHERE id = ?", (row[1], row[0]))

    # PageRank (3 iterations, damping 0.85)
    all_ids = [r[0] for r in db.execute("SELECT id FROM graph_nodes")]
    n = len(all_ids)
    if n == 0:
        db.commit()
        db.close()
        return

    scores = {nid: 1.0 / n for nid in all_ids}
    damping = 0.85

    # Build adjacency with weights
    outlinks: dict[str, list[tuple[str, float]]] = {nid: [] for nid in all_ids}
    for source, target, relation, weight in edges:
        if source in outlinks:
            outlinks[source].append((target, weight))

    for _ in range(3):
        new_scores = {}
        for nid in all_ids:
            incoming = db.execute("SELECT source, weight FROM graph_edges WHERE target = ?", (nid,)).fetchall()
            rank = (1 - damping) / n
            for src, edge_weight in incoming:
                out_count = len(outlinks.get(src, []))
                if out_count > 0:
                    rank += damping * scores.get(src, 0) / out_count * edge_weight
            new_scores[nid] = rank
        scores = new_scores

    # Normalize to 0-1
    max_score = max(scores.values()) if scores else 1
    for nid, score in scores.items():
        normalized = score / max_score if max_score > 0 else 0
        db.execute("UPDATE graph_nodes SET pagerank = ? WHERE id = ?", (round(normalized, 4), nid))

    db.commit()
    db.close()


def search_catalog(query: str, workers, executors, templates, generic_workers, archetypes):
    """Search catalog with FTS5 + PageRank blending if graph DB exists.

    Supports domain.subdomain syntax: "financeiro.investimentos" filters
    workers to that domain+subdomain before text search.
    """
    q = query.lower()

    # Domain.subdomain filter: "financeiro.investimentos" or "financeiro"
    domain_filter = None
    subdomain_filter = None
    text_query = q
    if "." in q and " " not in q:
        # Looks like domain.subdomain syntax
        parts = q.split(".", 1)
        domain_filter = parts[0]
        subdomain_filter = parts[1] if len(parts) > 1 else None
        text_query = None  # pure domain filter, no text search
    elif q in _load_domain_names():
        # Bare domain name — filter by domain
        domain_filter = q
        text_query = None

    if domain_filter:
        return _domain_search(domain_filter, subdomain_filter, workers)

    # Try ranked search via SQLite FTS5 + PageRank
    if GRAPH_DB.exists():
        try:
            return _ranked_search(q)
        except Exception:
            pass  # fallback to simple search

    # Fallback: simple substring match
    return _simple_search(q, workers, executors, templates, generic_workers, archetypes)


def _load_domain_names() -> set[str]:
    """Load registered domain names for filter detection."""
    reg_path = ROOT / "config" / "domains.json"
    if not reg_path.exists():
        return set()
    data = json.loads(reg_path.read_text(encoding="utf-8"))
    return set(data.get("domains", {}).keys())


def _domain_search(domain: str, subdomain: str | None, workers: list[dict]) -> list[str]:
    """Filter workers by domain and optional subdomain."""
    results = []
    for w in workers:
        if w.get("abstract"):
            continue
        lib = w.get("library", {})
        w_domain = lib.get("domain", "")
        w_subdomain = lib.get("subdomain", "")
        also = lib.get("also_relevant", [])

        # Match primary domain
        match = w_domain == domain
        if not match:
            # Check also_relevant
            for ref in also:
                if "." in ref:
                    rd, rs = ref.split(".", 1)
                    if rd == domain and (subdomain is None or rs == subdomain):
                        match = True
                        break

        if not match:
            continue

        # If subdomain specified, filter further
        if subdomain and w_subdomain != subdomain:
            # Check if it matches via also_relevant
            ar_match = any(
                ref == f"{domain}.{subdomain}" for ref in also
            )
            if not ar_match:
                continue

        cost = lib.get("typical_cost_usd", 0)
        xref = " (cross-ref)" if w_domain != domain else ""
        desc = w.get("description", "")[:60]
        results.append(
            f"worker: {w['id']} [{w_domain}.{w_subdomain}]{xref} — {desc} (${cost})"
        )

    if not results:
        target = f"{domain}.{subdomain}" if subdomain else domain
        results.append(f"No workers found for domain '{target}'.")
        # Show available subdomains
        reg_path = ROOT / "config" / "domains.json"
        if reg_path.exists():
            data = json.loads(reg_path.read_text(encoding="utf-8"))
            dom_info = data.get("domains", {}).get(domain, {})
            subs = dom_info.get("subdomains", {})
            if subs:
                results.append(f"Available subdomains for '{domain}': {', '.join(sorted(subs.keys()))}")

    return results


def _ranked_search(query: str) -> list[str]:
    """Search using FTS5 BM25 + PageRank blending."""
    db = sqlite3.connect(str(GRAPH_DB))

    # FTS5 search
    rows = db.execute("""
        SELECT fts_content.id, fts_content.type, rank,
               COALESCE(graph_nodes.pagerank, 0) as pr
        FROM fts_content
        LEFT JOIN graph_nodes ON fts_content.id = graph_nodes.id
        WHERE fts_content MATCH ?
        ORDER BY rank
        LIMIT 30
    """, (query,)).fetchall()

    if not rows:
        # Fallback: LIKE search on content
        rows = db.execute("""
            SELECT fts_content.id, fts_content.type, 0 as rank,
                   COALESCE(graph_nodes.pagerank, 0) as pr
            FROM fts_content
            LEFT JOIN graph_nodes ON fts_content.id = graph_nodes.id
            WHERE fts_content.content LIKE ?
            LIMIT 30
        """, (f"%{query}%",)).fetchall()

    db.close()

    if not rows:
        return []

    # Blend: 80% text relevance + 20% graph importance
    scored = []
    max_bm25 = max(abs(r[2]) for r in rows) if rows else 1
    for nid, ntype, bm25_rank, pagerank in rows:
        text_score = 1.0 - (abs(bm25_rank) / max_bm25) if max_bm25 > 0 else 0.5
        final = 0.80 * text_score + 0.20 * pagerank
        scored.append((final, nid, ntype, pagerank))

    scored.sort(key=lambda x: -x[0])

    results = []
    for score, nid, ntype, pr in scored[:20]:
        pr_str = f" [PR:{pr:.2f}]" if pr > 0.01 else ""
        results.append(f"{ntype}: {nid}{pr_str}")

    return results


def _simple_search(query, workers, executors, templates, generic_workers, archetypes):
    """Fallback: simple substring match (no graph)."""
    q = query.lower()
    results = []

    for w in workers:
        searchable = json.dumps(w, ensure_ascii=False).lower()
        if q in searchable:
            results.append(f"worker: {w['id']} — {w.get('description', '')[:60]}")

    for e in executors:
        if q in e["name"].lower() or q in e["docstring"].lower():
            results.append(f"executor: {e['name']} — {e['docstring'][:60]}")

    for category, items in templates.items():
        for t in items:
            if q in t["name"].lower() or q in t.get("first_line", "").lower():
                results.append(f"template/{category}: {t['name']}")

    for w in generic_workers:
        if q in w["name"].lower() or q in w["docstring"].lower():
            results.append(f"generic_worker: {w['name']} — {w['docstring'][:60]}")

    for a in archetypes:
        if q in a["name"].lower() or q in a["description"].lower():
            results.append(f"archetype: {a['name']} — {a['description'][:60]}")

    return results


def main():
    parser = argparse.ArgumentParser(description="Build or search the engine catalog")
    parser.add_argument("--search", default=None, help="Search catalog for a term")
    args = parser.parse_args()

    workers = scan_workers()
    executors = scan_executors()
    templates = scan_templates()
    fixups = scan_fixups()
    plugins = scan_r10_plugins()
    archetypes = scan_archetypes()
    schemas = scan_schemas()
    generic_workers = scan_generic_workers()

    if args.search:
        results = search_catalog(args.search, workers, executors, templates, generic_workers, archetypes)
        if results:
            print(f"Found {len(results)} results for '{args.search}':")
            for r in results:
                print(f"  {r}")
        else:
            print(f"No results for '{args.search}'")
        return

    # Generate catalog
    CATALOG_DIR.mkdir(parents=True, exist_ok=True)
    workers_dir = CATALOG_DIR / "workers"
    workers_dir.mkdir(exist_ok=True)

    files = {
        CATALOG_DIR / "_index.md": generate_index(workers, executors, templates, fixups, plugins, archetypes, schemas, generic_workers),
        CATALOG_DIR / "_by_domain.md": generate_by_domain(workers),
        CATALOG_DIR / "_by_type.md": generate_by_type(workers),
        CATALOG_DIR / "_executors.md": generate_executors(executors),
        CATALOG_DIR / "_templates.md": generate_templates(templates),
        CATALOG_DIR / "_archetypes.md": generate_archetypes(archetypes),
        CATALOG_DIR / "_schemas.md": generate_schemas(schemas),
        CATALOG_DIR / "_generic_workers.md": generate_generic_workers(generic_workers),
        CATALOG_DIR / "_fixups.md": generate_fixups(fixups),
        CATALOG_DIR / "_plugins.md": generate_plugins(plugins),
    }

    # Individual worker notes
    for w in workers:
        files[workers_dir / f"{w['id']}.md"] = generate_worker_note(w)

    for path, content in files.items():
        path.write_text(content, encoding="utf-8")

    # Build graph from generated catalog
    build_graph(files)

    # Stats
    node_count = 0
    edge_count = 0
    if GRAPH_DB.exists():
        db = sqlite3.connect(str(GRAPH_DB))
        node_count = db.execute("SELECT COUNT(*) FROM graph_nodes").fetchone()[0]
        edge_count = db.execute("SELECT COUNT(*) FROM graph_edges").fetchone()[0]
        top = db.execute("SELECT id, pagerank FROM graph_nodes ORDER BY pagerank DESC LIMIT 5").fetchall()
        db.close()

    print(f"Catalog generated: {CATALOG_DIR}")
    print(f"  Index pages: {len([f for f in files if f.parent == CATALOG_DIR])}")
    print(f"  Worker notes: {len([f for f in files if f.parent == workers_dir])}")
    print(f"  Total files: {len(files)}")
    print(f"  Graph: {node_count} nodes, {edge_count} edges")
    if GRAPH_DB.exists() and top:
        print(f"  Top PageRank: {', '.join(f'{r[0]}({r[1]:.2f})' for r in top)}")


if __name__ == "__main__":
    main()
