"""CLI for Sisyphus memory management."""

import argparse
import sys
from pathlib import Path

from sisyphus.memory.store import MemoryStore
from sisyphus.memory.refined import RefinedStore
from sisyphus.memory.moc import MocGenerator
from sisyphus.memory.log import LogStore


def _base() -> Path:
    return Path.home() / ".omo"


def _store() -> MemoryStore:
    return MemoryStore(base_path=_base() / "memory")


def _refined_store() -> RefinedStore:
    return RefinedStore(base_path=_base() / "memory")


def _log_store() -> LogStore:
    return LogStore(base_path=_base())


def cmd_record(args):
    store = _store()
    mem = store.create(
        title=args.title,
        type=args.type,
        content=args.content or "",
        tags=args.tags.split(",") if args.tags else [],
    )
    print(f"Recorded {mem.id}: {mem.title}")


def cmd_search(args):
    store = _store()
    query = args.query.lower()
    results = []
    for m in store.list():
        if query in m.title.lower() or query in m.content.lower() or query in " ".join(m.tags).lower():
            results.append(m)
    if not results:
        print(f"No memories match: {args.query}")
        return
    print(f"Found {len(results)} memory(ies) for '{args.query}':\n")
    for m in results:
        created = m.created_at[:19].replace("T", " ") if m.created_at else ""
        tags = f" [{', '.join(m.tags)}]" if m.tags else ""
        print(f"  [{m.id}] {m.type:20s} | {created} | {m.title}{tags}")
        if m.content:
            print(f"         {m.content[:80]}")
        print()


def cmd_recent(args):
    store = _store()
    limit = args.limit or 10
    memories = store.list()
    memories.sort(key=lambda m: m.created_at, reverse=True)
    memories = memories[:limit]
    if not memories:
        print("No memories found.")
        return
    for m in memories:
        created = m.created_at[:19].replace("T", " ") if m.created_at else ""
        tags = f" [{', '.join(m.tags)}]" if m.tags else ""
        print(f"  [{m.id}] {m.type:20s} | {created} | {m.title}{tags}")


def cmd_show(args):
    store = _store()
    mem = store.get(args.id)
    if not mem:
        rstore = _refined_store()
        mem = rstore.get_refined(args.id)
    if not mem:
        print(f"Memory not found: {args.id}")
        return
    print(f"ID:        {mem.id}")
    print(f"Type:      {mem.type}")
    print(f"Title:     {mem.title}")
    print(f"Created:   {mem.created_at[:19].replace('T', ' ') if mem.created_at else ''}")
    print(f"Updated:   {mem.updated_at[:19].replace('T', ' ') if mem.updated_at else ''}")
    print(f"Tags:      {', '.join(mem.tags) if mem.tags else '(none)'}")
    print(f"Importance: {mem.importance}")
    print(f"Status:    {mem.status}")
    if mem.links:
        print(f"Links:     {', '.join(mem.links)}")
    if mem.evidence:
        print(f"Evidence:  {', '.join(mem.evidence)}")
    if mem.compressed_from:
        print(f"From:      {', '.join(mem.compressed_from)}")
    if mem.refined_by:
        print(f"RefinedBy: {', '.join(mem.refined_by)}")
    if mem.trigger:
        print(f"Trigger:   {mem.trigger}")
    if mem.repeat_count:
        print(f"Loop:      {mem.repeat_count}x {mem.repeat_pattern}")
    if mem.content:
        print(f"\n{mem.content}")


def cmd_forget(args):
    store = _store()
    store.delete(args.id)
    print(f"Forgotten: {args.id}")


def cmd_stats(args):
    store = _store()
    rstore = _refined_store()
    memories = store.list()
    refined = rstore.list_refined()
    if not memories and not refined:
        print("Memory store is empty.")
        return
    by_type = {}
    for m in memories:
        by_type[m.type] = by_type.get(m.type, 0) + 1
    for m in refined:
        by_type[m.type] = by_type.get(m.type, 0) + 1
    total = len(memories) + len(refined)
    print(f"Total memories: {total} (RAW: {len(memories)}, Refined: {len(refined)})")
    print(f"Store:         {store.base_path}")
    print()
    for t, count in sorted(by_type.items()):
        print(f"  {t:20s}  {count}")


def cmd_snapshot(args):
    from sisyphus.memory.llm import LLMClient
    from sisyphus.memory.recall import Recall
    from sisyphus.memory.snapshot import FrozenSnapshot
    store = _store()
    llm = LLMClient()
    recall = Recall(store=store, llm_client=llm)
    snap = FrozenSnapshot(recall=recall, max_memories=args.max, max_chars=args.max_chars)
    print(snap.build(query=args.query))


def cmd_index(args):
    store = _store()
    rstore = _refined_store()
    gen = MocGenerator(store, refined_store=rstore)
    gen.generate()
    print(f"INDEX.md updated at {store.base_path / 'INDEX.md'}")


def cmd_log(args):
    lstore = _log_store()
    limit = args.limit or 10
    logs = lstore.list_logs()[:limit]
    if not logs:
        print("No logs found.")
        return
    for log in logs:
        started = log.started[:19].replace("T", " ") if log.started else ""
        print(f"  [{log.id}] {log.command:15s} | {started} | {log.status}")


def cmd_refined(args):
    rstore = _refined_store()
    type_filter = args.type
    mems = rstore.list_refined(type_filter=type_filter)
    if not mems:
        print("No refined memories found.")
        return
    for m in mems:
        created = m.created_at[:19].replace("T", " ") if m.created_at else ""
        tags = f" [{', '.join(m.tags)}]" if m.tags else ""
        print(f"  [{m.id}] {m.type:20s} | {created} | {m.title}{tags}")


def cmd_dream(args):
    from sisyphus.memory.dream import DreamEngine
    from sisyphus.memory.llm import LLMClient
    store = _store()
    rstore = _refined_store()
    llm = LLMClient()
    engine = DreamEngine(store=store, refined_store=rstore, llm_client=llm)
    reflections = engine.dream()
    print(f"Dream complete: {len(reflections)} reflection(s) generated.")
    for r in reflections:
        print(f"  [{r.id}] {r.title} (importance={r.importance})")


def cmd_link(args):
    from sisyphus.memory.link import LinkAnalyzer
    store = _store()
    analyzer = LinkAnalyzer(store)
    pairs = analyzer.analyze()
    print(f"Link analysis: {len(pairs)} pair(s) linked.")


def cmd_link(args):
    from sisyphus.memory.link import LinkAnalyzer
    store = _store()
    analyzer = LinkAnalyzer(store)
    pairs = analyzer.analyze()
    print(f"Link analysis complete: {len(pairs)} pair(s) linked.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sisyphus memory management")
    sub = parser.add_subparsers(dest="command")

    p_record = sub.add_parser("record", help="Record a new memory")
    p_record.add_argument("type", help="Memory type")
    p_record.add_argument("title", help="Memory title")
    p_record.add_argument("--content", "-c", help="Memory content")
    p_record.add_argument("--tags", "-t", help="Comma-separated tags")

    p_search = sub.add_parser("search", help="Search memories")
    p_search.add_argument("query", help="Search query")

    p_recent = sub.add_parser("recent", help="Show recent memories")
    p_recent.add_argument("--limit", "-l", type=int, default=10)

    p_show = sub.add_parser("show", help="Show a memory")
    p_show.add_argument("id", help="Memory ID")

    p_forget = sub.add_parser("forget", help="Delete a memory")
    p_forget.add_argument("id", help="Memory ID")

    p_stats = sub.add_parser("stats", help="Memory statistics")

    p_snapshot = sub.add_parser("snapshot", help="Generate frozen memory snapshot")
    p_snapshot.add_argument("--query", "-q", default="", help="Query to focus recall")
    p_snapshot.add_argument("--max", type=int, default=5, help="Max memories")
    p_snapshot.add_argument("--max-chars", type=int, default=2000, help="Max snapshot chars")

    p_index = sub.add_parser("index", help="Update INDEX.md with MOC format")
    p_log = sub.add_parser("log", help="Show operation logs")
    p_log.add_argument("--limit", "-l", type=int, default=10)

    p_refined = sub.add_parser("refined", help="List refined memories")
    p_refined.add_argument("--type", "-t", help="Filter by refined type")

    p_dream = sub.add_parser("dream", help="Run reflection engine (dream)")

    p_link = sub.add_parser("link", help="Auto-discover and create links")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "record":
        cmd_record(args)
    elif args.command == "search":
        cmd_search(args)
    elif args.command == "recent":
        cmd_recent(args)
    elif args.command == "show":
        cmd_show(args)
    elif args.command == "forget":
        cmd_forget(args)
    elif args.command == "stats":
        cmd_stats(args)
    elif args.command == "snapshot":
        cmd_snapshot(args)
    elif args.command == "index":
        cmd_index(args)
    elif args.command == "log":
        cmd_log(args)
    elif args.command == "refined":
        cmd_refined(args)
    elif args.command == "dream":
        cmd_dream(args)
    elif args.command == "link":
        cmd_link(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
