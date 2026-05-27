"""CLI for Sisyphus memory management."""

import argparse
import sys
from pathlib import Path

from sisyphus.memory.store import MemoryStore
from sisyphus.memory.refined import RefinedStore
from sisyphus.memory.moc import MocGenerator
from sisyphus.memory.log import LogStore
from sisyphus.memory.subagent import SubagentLauncher


def _base() -> Path:
    return Path.home() / ".omo"


def _store() -> MemoryStore:
    return MemoryStore(base_path=_base() / "memory")


def _refined_store() -> RefinedStore:
    return RefinedStore(base_path=_base() / "memory")


def _log_store() -> LogStore:
    return LogStore(base_path=_base())


def _subagent() -> SubagentLauncher:
    return SubagentLauncher(store_path=_base() / "memory")


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
    from sisyphus.memory.recall import Recall
    from sisyphus.memory.snapshot import FrozenSnapshot

    store = _store()
    subagent = _subagent()
    recall = Recall(store=store, subagent=subagent)
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

    store = _store()
    rstore = _refined_store()
    subagent = _subagent()
    engine = DreamEngine(store=store, refined_store=rstore, subagent=subagent)
    reflections = engine.dream()
    print(f"Dream complete: {len(reflections)} reflection(s) generated.")
    for r in reflections:
        print(f"  [{r.id}] {r.title} (importance={r.importance})")


def cmd_link(args):
    from sisyphus.memory.link import LinkCleaner

    store = _store()
    cleaner = LinkCleaner(store)
    result = cleaner.clean()
    print(f"Link clean: {result['total_cleaned']} memory(ies) cleaned, "
          f"{result['removed_dead']} dead link(s), "
          f"{result['removed_duplicates']} duplicate(s), "
          f"{result['removed_self_refs']} self-ref(s) removed.")


def cmd_detect_loop(args):
    from sisyphus.memory.loop import LoopDetector

    store = _store()
    rstore = _refined_store()
    detector = LoopDetector(store, rstore)
    loops = detector.detect()
    if not loops:
        print("No loops detected.")
        return
    print(f"Detected {len(loops)} loop(s):")
    for lp in loops:
        print(f"  [{lp['record_id']}] {lp['pattern']} (x{lp['count']})")


def cmd_clean(args):
    store = _store()
    rstore = _refined_store()
    matches = []
    for m in store.list():
        hit = False
        if args.tag and args.tag in m.tags:
            hit = True
        if args.title and args.title.lower() in m.title.lower():
            hit = True
        if hit:
            matches.append((m, "RAW"))
    for m in rstore.list_refined():
        hit = False
        if args.tag and args.tag in m.tags:
            hit = True
        if args.title and args.title.lower() in m.title.lower():
            hit = True
        if hit:
            matches.append((m, "REFINED"))

    if not matches:
        print("No matching memories found.")
        return

    for mem, layer in matches:
        print(f"[{layer}] [{mem.type}] {mem.title}")
        preview = (mem.content or "")[:100].replace("\n", " ")
        if preview:
            print(f"  {preview}")

    if args.force:
        deleted = 0
        for mem, layer in matches:
            if layer == "RAW":
                store.delete(mem.id)
            else:
                rstore.delete_refined(mem.id)
            deleted += 1
        print(f"\nDeleted {deleted} memories.")
    else:
        print(f"\nTotal: {len(matches)} match(es). Use --force to actually delete.")


def cmd_rebuild(args):
    from sisyphus.memory.fts_index import FtsIndex

    store = _store()
    fts = FtsIndex(store)
    count = fts.rebuild()
    print(f"FTS5 index rebuilt: {count} memories indexed")


def cmd_audit(args):
    from sisyphus.memory.audit import Auditor

    store = _store()
    auditor = Auditor(store)
    print(auditor.report(days=args.days))


def cmd_dashboard(args):
    from sisyphus.server.dashboard import generate

    store = _store()
    output = Path(args.output) if args.output else store.base_path / "dashboard.html"
    count = generate(store, output)
    print(f"Dashboard generated: {count} memories → {output}")


def cmd_agent(args):
    from sisyphus.memory.agent import AgentRegistry

    reg = AgentRegistry(_base())
    if args.agent_command == "list":
        agents = reg.all()
        if not agents:
            print("No agents found.")
            return
        for name in agents:
            sb = reg.get(name)
            s = sb.stats()
            print(f"  {name:20s}  {s['raw']} raw, {s['refined']} refined")
    elif args.agent_command == "create":
        reg.create(args.name)
        print(f"Agent '{args.name}' created.")
    elif args.agent_command == "show":
        sb = reg.get(args.name)
        s = sb.stats()
        print(f"Agent: {s['agent']}")
        print(f"Path:  {s['path']}")
        print(f"Raw:   {s['raw']}")
        print(f"Refined: {s['refined']}")


def cmd_cache(args):
    from sisyphus.memory.cache import CacheStore

    cache = CacheStore(_base())
    if args.cache_command == "rebuild":
        store = _store()
        result = cache.rebuild(store)
        print(f"Cache rebuilt: {result['cached']} memories cached.")
    elif args.cache_command == "status":
        s = cache.status()
        print(f"Total:   {s['total']}")
        print(f"Rebuilt: {s['last_rebuild']}")
        if s["by_type"]:
            print("By type:")
            for t, c in sorted(s["by_type"].items()):
                print(f"  {t}: {c}")
    elif args.cache_command == "search":
        results = cache.search(args.query)
        if not results:
            print("No results.")
            return
        for r in results:
            print(f"  [{r['id']}] {r['type']:20s} | {r['title']}")
            if r["content"]:
                print(f"         {r['content'][:100]}")


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

    p_link = sub.add_parser("link", help="Clean up broken/duplicate links in memories")

    p_loop = sub.add_parser("detect-loop", help="Detect repeated memory patterns")
    p_loop.add_argument("--threshold", "-t", type=int, default=3,
                        help="Min repeats to flag as loop (default: 3)")

    p_clean = sub.add_parser("clean", help="Delete memories by tag or title")
    p_clean.add_argument("--tag", "-t", help="Tag to filter for deletion")
    p_clean.add_argument("--title", help="Title to match for deletion")
    p_clean.add_argument("--force", "-f", action="store_true", help="Actually delete (dry-run by default)")

    p_rebuild = sub.add_parser("rebuild", help="Rebuild FTS5 index from RAW files")

    p_audit = sub.add_parser("audit", help="Audit memory coverage from L2 operation log")
    p_audit.add_argument("--days", "-d", type=int, default=1, help="Days to audit (default: 1)")

    p_dashboard = sub.add_parser("dashboard", help="Generate visualization dashboard HTML")
    p_dashboard.add_argument("--output", "-o", default=None, help="Output path (default: ~/.omo/memory/dashboard.html)")

    p_agent = sub.add_parser("agent", help="Manage sub-agent memory sandboxes")
    p_agent_sub = p_agent.add_subparsers(dest="agent_command")
    p_agent_list = p_agent_sub.add_parser("list", help="List all agent sandboxes")
    p_agent_create = p_agent_sub.add_parser("create", help="Create a new agent sandbox")
    p_agent_create.add_argument("name", help="Agent name")
    p_agent_show = p_agent_sub.add_parser("show", help="Show agent sandbox details")
    p_agent_show.add_argument("name", help="Agent name")

    p_cache = sub.add_parser("cache", help="SQLite cache operations")
    p_cache_sub = p_cache.add_subparsers(dest="cache_command")
    p_cache_rebuild = p_cache_sub.add_parser("rebuild", help="Rebuild cache from files")
    p_cache_status = p_cache_sub.add_parser("status", help="Show cache status")
    p_cache_search = p_cache_sub.add_parser("search", help="Search cached memories")
    p_cache_search.add_argument("query", help="Search query")

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
    elif args.command == "detect-loop":
        cmd_detect_loop(args)
    elif args.command == "clean":
        cmd_clean(args)
    elif args.command == "rebuild":
        cmd_rebuild(args)
    elif args.command == "audit":
        cmd_audit(args)
    elif args.command == "dashboard":
        cmd_dashboard(args)
    elif args.command == "agent":
        cmd_agent(args)
    elif args.command == "cache":
        cmd_cache(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
