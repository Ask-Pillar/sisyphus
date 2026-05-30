"""code-index: AST-based code indexer for Python projects.
Zero dependencies, Python 3.9+.

Usage:
    python3 code_index.py /path/to/project/src > code_index.json
    python3 code_index.py /path/to/project/src --query "retrieve"
"""

import ast
import json
import sys
import os
from pathlib import Path
from collections import defaultdict


def parse_file(filepath: str) -> dict:
    """Extract functions, classes, imports from a Python file."""
    with open(filepath) as f:
        try:
            tree = ast.parse(f.read())
        except SyntaxError:
            return {}

    result = {"file": filepath, "functions": [], "classes": [], "imports": []}

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            result["functions"].append({
                "name": node.name,
                "args": [a.arg for a in node.args.args],
                "line": node.lineno,
                "decorators": [
                    d.id if isinstance(d, ast.Name) else str(d)
                    for d in node.decorator_list
                ] if node.decorator_list else [],
            })
        elif isinstance(node, ast.ClassDef):
            methods = [
                n.name for n in node.body
                if isinstance(n, ast.FunctionDef)
            ]
            result["classes"].append({
                "name": node.name,
                "line": node.lineno,
                "methods": methods,
            })
        elif isinstance(node, ast.Import):
            for alias in node.names:
                result["imports"].append({
                    "module": alias.name,
                    "alias": alias.asname,
                    "type": "import",
                    "line": node.lineno,
                })
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                result["imports"].append({
                    "module": node.module or "",
                    "name": alias.name,
                    "alias": alias.asname,
                    "type": "from",
                    "line": node.lineno,
                })

    return result


def build_index(src_dir: str) -> dict:
    """Index all Python files in a directory."""
    index = {
        "functions": defaultdict(list),   # func_name -> [file:line]
        "classes": defaultdict(list),
        "imports": defaultdict(list),
        "callers": defaultdict(list),      # func_name -> [caller_func]
        "files": [],
    }

    py_files = list(Path(src_dir).rglob("*.py"))

    # Phase 1: parse all files
    for fp in py_files:
        data = parse_file(str(fp))
        if not data:
            continue
        index["files"].append(data)

        for func in data["functions"]:
            index["functions"][func["name"]].append(f"{data['file']}:{func['line']}")

        for cls in data["classes"]:
            index["classes"][cls["name"]].append(f"{data['file']}:{cls['line']}")

        for imp in data["imports"]:
            key = f"{imp['module']}.{imp['name']}" if imp['type'] == 'from' else imp['module']
            index["imports"][key].append(data["file"])

    # Phase 2: build call graph
    for fp in py_files:
        with open(fp) as f:
            try:
                tree = ast.parse(f.read())
            except SyntaxError:
                continue

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                func_name = node.name
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Call):
                        if isinstance(sub.func, ast.Name):
                            callee = sub.func.id
                            index["callers"][callee].append({
                                "caller": func_name,
                                "file": str(fp),
                                "line": sub.lineno,
                            })
                        elif isinstance(sub.func, ast.Attribute):
                            callee = sub.func.attr
                            index["callers"][callee].append({
                                "caller": func_name,
                                "file": str(fp),
                                "line": sub.lineno,
                            })

    return index


def query_index(index: dict, query: str):
    """Search index for a function/class/module name."""
    results = []

    for func, locs in index["functions"].items():
        if query.lower() in func.lower():
            results.append(f"📌 function {func}:")
            for loc in locs:
                results.append(f"     {loc}")
            callers = index["callers"].get(func, [])
            if callers:
                results.append(f"     called by:")
                seen = set()
                for c in callers[:5]:
                    key = f"{c['caller']}"
                    if key not in seen:
                        results.append(f"       - {c['caller']} ({c['file']}:{c['line']})")
                        seen.add(key)
            results.append("")

    for cls, locs in index["classes"].items():
        if query.lower() in cls.lower():
            results.append(f"📌 class {cls}:")
            for loc in locs:
                results.append(f"     {loc}")
            results.append("")

    for imp, files in index["imports"].items():
        if query.lower() in imp.lower():
            results.append(f"📌 import {imp}:")
            for f in files[:5]:
                results.append(f"     {f}")
            results.append("")

    return "\n".join(results) if results else f"No results for '{query}'"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 code_index.py <src_dir> [--query <name>] [--full]")
        sys.exit(1)

    src = sys.argv[1]
    index = build_index(src)

    if "--query" in sys.argv:
        qi = sys.argv.index("--query")
        if qi + 1 < len(sys.argv):
            print(query_index(index, sys.argv[qi + 1]))
    elif "--full" in sys.argv:
        print(json.dumps({
            "files": index["files"],
            "callers": {k: v for k, v in index["callers"].items()},
        }, indent=2, default=str))
    else:
        print(json.dumps({
            "functions": {k: len(v) for k, v in index["functions"].items()},
            "classes": {k: len(v) for k, v in index["classes"].items()},
            "total_functions": sum(len(v) for v in index["functions"].values()),
            "total_classes": sum(len(v) for v in index["classes"].values()),
            "total_files": len(index["files"]),
            "total_call_edges": sum(len(v) for v in index["callers"].values()),
        }, indent=2))
