import json
import re
from pathlib import Path

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)


def import_memories(store, source):
    path = Path(source).expanduser()
    if not path.exists():
        return {"error": f"Path not found: {source}"}

    imported = 0
    skipped = 0
    errors = []

    files = []
    if path.is_dir():
        for ext in ["*.md", "*.jsonl"]:
            files.extend(path.rglob(ext))
    elif path.suffix in (".md", ".jsonl"):
        files = [path]
    else:
        return {"error": f"Unsupported format: {path.suffix}"}

    for filepath in files:
        try:
            if filepath.suffix == ".jsonl":
                with open(filepath) as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            item = json.loads(line)
                            if _import_one(store, item):
                                imported += 1
                        except json.JSONDecodeError as e:
                            errors.append(f"{filepath.name}:{line[:20]} JSON parse error: {e}")
            elif filepath.suffix == ".md":
                text = filepath.read_text()
                fm = _parse_frontmatter(text)
                body = _strip_frontmatter(text)
                if fm:
                    item = {
                        "title": fm.get("title", filepath.stem),
                        "type": fm.get("type", fm.get("tags", "note").split(",")[0] if "tags" in fm else "note"),
                        "content": fm.get("content", body[:500]) if "content" in fm else body[:500],
                        "tags": fm.get("tags", "").split(",") if isinstance(fm.get("tags", ""), str) else fm.get("tags", []),
                        "importance": int(fm.get("importance", 5)),
                    }
                    if _import_one(store, item):
                        imported += 1
                else:
                    item = {
                        "title": filepath.stem,
                        "type": "note",
                        "content": body[:500],
                        "tags": [],
                        "importance": 5,
                    }
                    if _import_one(store, item):
                        imported += 1
        except Exception as e:
            errors.append(f"{filepath.name}: {e}")

    return {"imported": imported, "skipped": skipped, "errors": errors}


def _import_one(store, item):
    title = item.get("title", "").strip()
    if not title:
        return False
    mem_type = item.get("type", "note").strip() or "note"
    content = item.get("content", "").strip()
    tags = item.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    importance = item.get("importance", 5)
    if isinstance(importance, str):
        try:
            importance = int(importance)
        except ValueError:
            importance = 5
    existing = store.list()
    for m in existing:
        if m.title == title:
            return False
    store.create(title=title, type=mem_type, content=content, tags=tags, importance=importance)
    return True


def _parse_frontmatter(text):
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}
    lines = match.group(1).strip().split("\n")
    result = {}
    for line in lines:
        if ":" in line:
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip().strip("'\"")
            result[key] = val
    return result


def _strip_frontmatter(text):
    match = FRONTMATTER_RE.match(text)
    if match:
        return text[match.end():].strip()
    return text.strip()
