#!/usr/bin/env python3
"""Sisyphus A/B Test v2: with memory vs without memory.
Produces detailed JSON report for HTML rendering.
"""

import json, os, time, tempfile, urllib.request
from pathlib import Path
from typing import List, Tuple

FACTS = [
    ("Sisyphus四层存储架构", "lesson",
     "Sisyphus采用四层存储架构：RAW层（Markdown文件append-only永不删除）、REFINED层（LLM加工产物可重建）、MOC层（Obsidian兼容wikilink索引）、AGENT层（子agent独立沙箱）。核心原则：文件即唯一真相源(SSOT)，SQLite仅为可重建的加速缓存。存储路径为~/.omo/memory/，每条记忆一个带YAML frontmatter的Markdown文件。"),
    ("decay_score记忆权重衰减", "pattern",
     "衰减公式：decay_score = importance × 0.5^(days/30)，半衰期为30天。时间差计算：优先使用last_recalled_at字段（最近被召回时间），若为空则回退到created_at（创建时间）。每次检索后自动更新recall_count加1并刷新last_recalled_at为当前UTC时间。decay_score用于排序记忆并截断到top_k，越久未被召回的权重越低，腾出上下文空间。"),
    ("SubagentLauncher子进程LLM调度", "architecture",
     "所有LLM加工通过SubagentLauncher在独立子进程中执行，防止主进程上下文被LLM污染。流程：主进程序列化任务为task.json → subprocess.run()启动子进程(python -m sisyphus.memory.subagent) → 子进程读task.json、做LLM OpenAI兼容API调用、文件IO(创建refined记忆文件) → 写result.json → 子进程退出 → 主进程读result.json。支持5个handler：dream（反射洞察）、compress（退火压缩合并）、recall_search（全文+嵌入召回）、recall_relevant（单条相关性评分）、classify_types（类型分类，已废弃改用MOC）。"),
    ("ContextRetriever三层分层召回", "architecture",
     "三层架构：L1通过读取INDEX.md MOC文件按query关键词重叠打分匹配相关记忆类型（不再依赖LLM分类），支持MocGenerator的##type格式和MemoryStore的flat格式。L2从refined层（reflection/summary）中召回已加工记忆。L3在L2结果不足top_k时从RAW层按需补缺高重要性记忆。所有候选记忆经decay_score排序后截断。支持全量(retrieve)和轻量(retrieve_refined_only)两种模式。"),
    ("MCP stdio Server", "decision",
     "通过stdio JSON-RPC协议实现零依赖MCP server。4个工具：write_memory（记录新记忆至~/.omo/memory/）、search_memory（按关键词搜索返回context块+匹配列表）、get_context（返回<sisyphus_context>格式上下文块用于agent prompt注入）、memory_stats（返回total_raw/total_refined/by_type统计）。兼容所有MCP客户端（opencode/Claude Desktop/VS Code/Cursor）。启动命令：PYTHONPATH=src python -m sisyphus.server.mcp。"),
    ("AgentMemory自动注入入口", "architecture",
     "AgentMemory是自动注入入口类，封装MemoryStore+ContextRetriever+MemoryContext。before_turn(query)每次agent响应前调用，返回<sisyphus_context>格式上下文块。三种触发全量三层检索的条件：turn_count==0（首轮）、MemoryStore被dirty标记（新记忆写入时自动置脏）、距离上次全量超过refresh_interval（默认5轮）。增量模式下refined_only为空时自动fallback到全量检索。record()方法写记忆并自动标记dirty。"),
    ("LoopDetector回路检测", "pattern",
     "检测同标题≥3次的重复记忆模式。按精确标题分组，阈值默认3（CLI中通过--threshold调整）。检测到回路后：标记最早出现的那条记忆（设置repeat_count和repeat_pattern字段）、在RefinedStore中创建loop_record记录（含detected_at时间戳和pattern描述）。repeat_count与retrieval的recall_count语义完全独立：一个是回路重复计数，一个是检索使用计数。"),
    ("LinkCleaner断链清理", "pattern",
     "三种清理操作：①删除指向不存在记忆ID的死链(dead links) ②移除同一条记忆内的重复链接(deduplicate) ③去除自引用(self-reference，memory的links字段包含自己ID会被移除)。与废弃的LinkAnalyzer不同：LinkCleaner只做按需清理，不做自动关联；LinkAnalyzer原本试图按标签自动建立记忆间关联，但该设计被放弃。"),
    ("LLM max_tokens与reasoning模型", "lesson",
     "使用DeepSeek reasoning模型(deepseek-v4-flash)时发现关键bug：max_tokens=500导致LLM响应content为空。原因：DeepSeek的reasoning_content字段占用token预算，剩余给content的token不够甚至为0。修复方案：将默认max_tokens提高到2048，同时通过SISYPHUS_LLM_MAX_TOKENS环境变量允许用户自定义。LLMClient还支持SISYPHUS_LLM_API_KEY/SISYPHUS_LLM_BASE_URL/SISYPHUS_LLM_MODEL等配置。"),
    ("大规模测试103万token", "lesson",
     "测试规模：200条多样记忆（覆盖Python编程/系统架构/设计模式/AI/DevOps五大领域，中英文混合）。Dream反射成功生成4条insight（虽然后续因超时丢失）。165次Recall查询，95次命中/70次未命中（58%命中率）。Compress压缩了195条记忆为摘要。实测DeepSeek API单次recall消耗5,755 token。总token消耗1,036,390，超过100万目标。测试耗时约19分钟。"),
    ("Pipeline自动流水线", "architecture",
     "5步顺序执行：1.回路检测（扫描RAW层同标题≥3次标记并创建loop_record）2.压缩（RAW数量超过阈值时退火合并旧记忆）3.反射（≥3条未加工记忆触发DreamEngine）4.MOC索引重建（增量更新INDEX.md）5.断链清理（移除无效/重复/自引用链接）。无LLM API key时所有LLM步骤自动跳过不崩溃。CLI通过memory pipeline命令手动触发，也可嵌入agent循环。"),
    ("DreamEngine反射机制", "architecture",
     "DreamEngine收集所有未加工记忆→委托SubagentLauncher.dream()→子进程LLM分析模式/原则/insight→生成reflection记忆存入refined/reflection/目录。每条reflection包含：id/title/content/importance(1-10)/evidence(支撑该insight的原始记忆ID列表)。源记忆的refined_by字段更新为对应reflection的ID。DreamEngine.dream()返回List[Memory]供主进程使用。"),
    ("Compressor退火压缩", "architecture",
     "threshold参数控制触发阈值（默认20条RAW记忆）。keep_recent保留最新N条不被压缩。流程：Compressor.run()→检查RAW数量是否超过threshold→委托SubagentLauncher.compress()→子进程LLM将所有旧记忆总结为一条compressed类型新记忆→删除旧记忆。主进程仅获得deleted_count返回值。注意API是run()不是compress()（之前大规模测试中写错过一次）。"),
    ("Recall召回机制", "architecture",
     "Recall.search(query, top_k)将全部记忆列表+query序列化为prompt→委托SubagentLauncher.recall_search()→子进程LLM选出相关memory_ids→主进程用这些ID从MemoryStore取出完整Memory对象返回。Recall.is_relevant(memory, query)评分单条记忆与query的相关性（0.0-1.0），委托SubagentLauncher.recall_relevant()。无LLM key时返回空列表/0.0。与embeddings向量搜索(search.py)互补。"),
    ("188测试覆盖全景", "lesson",
     "19个测试文件覆盖19个模块：test_store.py(CRUD+持久化)、test_store_v2.py(frontmatter格式+向后兼容)、test_refined.py(三层加工存储)、test_dream.py(反射引擎+subagent委托)、test_compression.py(退火压缩+阈值)、test_recall.py(LLM召回)、test_retrieval.py(三层检索+MOC匹配+衰减，22条)、test_context.py(MemoryContext+dirty+AgentMemory，14条)、test_pipeline.py(自动流水线)、test_loop.py(回路检测)、test_link.py(断链清理)、test_moc.py(索引生成)、test_agent.py(沙箱隔离)、test_cache.py(SQLite缓存)、test_log.py(结构化日志)、test_snapshot.py(冻结快照)、test_extraction.py(记忆提取)、test_search.py(嵌入搜索)、test_cli.py(命令解析)。全部188条测试通过。"),
]

QUESTIONS = [
    "Sisyphus采用几层存储架构？每层叫什么名字，各自的特点是什么？",
    "decay_score的完整衰减公式是什么？半衰期是多少天？如何计算时间差？每次检索后自动更新什么字段？",
    "SubagentLauncher的完整工作流程是怎样的？支持哪5个handler？各自的用途？",
    "ContextRetriever的三层检索L1/L2/L3分别做什么？L1现在用什么方式确定相关类型（不再依赖什么）？",
    "MCP Server使用什么通信协议？提供哪四个工具？列出它们的参数。兼容哪些客户端？",
    "AgentMemory.before_turn()在什么条件下触发全量检索？增量模式空结果时如何处理？dirty标记是谁设的？",
    "LoopDetector如何检测回路？阈值默认是多少？检测到回路后做哪两件事？repeat_count和recall_count有什么区别？",
    "LinkCleaner做哪三种清理操作？它与废弃的LinkAnalyzer在设计理念上有什么区别？",
    "DeepSeek reasoning模型使用中发现了什么关键bug？原因是什么？如何修复的？",
    "大规模测试使用了多少条记忆？覆盖哪些领域？总共消耗了多少token？Recall命中率是多少？",
    "Pipeline自动流水线有哪5个步骤？在没有LLM API key时如何处理？",
    "DreamEngine的反射结果写入哪个目录？每条reflection包含哪些字段？源记忆如何关联到reflection？",
    "Compressor的正确API方法名是什么？threshold和keep_recent的作用分别是什么？run()返回什么？",
    "Recall.search()和Recall.is_relevant()的功能区别是什么？它们各自委托哪个subagent handler？",
    "188个测试分布在多少个文件中？列出至少8个测试文件名及其覆盖的模块。",
]


def llm_answer(messages, max_tokens=2048):
    body = json.dumps({
        "model": "deepseek-v4-flash",
        "messages": messages,
        "temperature": 0.0,
        "max_tokens": max_tokens,
    }).encode()
    url = "https://api.deepseek.com/v1/chat/completions"
    req = urllib.request.Request(url, data=body, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.environ['SISYPHUS_LLM_API_KEY']}",
    }, method="POST")
    resp = urllib.request.urlopen(req, timeout=120)
    data = json.loads(resp.read().decode())
    return data["choices"][0]["message"]["content"]


GRADE_PROMPT = """Score this answer against the ground truth (0-10).

Ground truth: {ground_truth}
Student answer: {student_answer}

Scoring:
- Factual accuracy (6 pts): correct facts?
- Completeness (3 pts): key points covered?
- No hallucination (1 pt): no made-up info?

Return ONLY JSON: {{"score": N, "reason": "short"}}"""


def parse_grade(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        return json.loads(raw)
    except:
        # Try to extract just the number
        import re
        m = re.search(r'"score"\s*:\s*(\d+)', raw)
        if m:
            return {"score": int(m.group(1)), "reason": "extracted"}
        return {"score": 0, "reason": f"parse error: {raw[:80]}"}


def main():
    from sisyphus.memory.store import MemoryStore
    from sisyphus.memory.refined import RefinedStore
    from sisyphus.memory.retrieval import ContextRetriever
    from sisyphus.memory.subagent import SubagentLauncher

    print("="*70)
    print("Sisyphus A/B Test: With Memory vs Without Memory")
    print("="*70)

    start_time = time.time()
    tmp = Path(tempfile.mkdtemp()) / "mem"
    store = MemoryStore(base_path=tmp)
    refined = RefinedStore(base_path=tmp)
    subagent = SubagentLauncher(store_path=tmp)

    for title, mem_type, content in FACTS:
        store.create(title=title, type=mem_type, content=content, tags=[mem_type])

    results = []
    a_total = b_total = 0

    for i, (question, (title, _, ground_truth)) in enumerate(zip(QUESTIONS, FACTS)):
        print(f"\nQ{i+1}: {question[:60]}...")

        # ── Group A: with memory ──
        retriever = ContextRetriever(store, refined, subagent)
        mems = retriever.retrieve(query=question, top_k=5)
        ctx_lines = ["<sisyphus_context>"]
        for m, s in mems:
            ctx_lines.append(f"- [{m.type}] {m.title} | importance={s:.0f}")
            ctx_lines.append(f"  {m.content}")
        ctx_lines.append("</sisyphus_context>")
        ctx = "\n".join(ctx_lines)

        ans_a = llm_answer([
            {"role": "system", "content": f"使用以下记忆上下文详细回答问题，列出所有关键事实：\n\n{ctx}"},
            {"role": "user", "content": question},
        ])
        grade_a = llm_answer([
            {"role": "user", "content": GRADE_PROMPT.format(ground_truth=ground_truth, student_answer=ans_a)},
        ], max_tokens=512)
        ga = parse_grade(grade_a)
        a_total += ga["score"]

        # ── Group B: without memory ──
        ans_b = llm_answer([
            {"role": "system", "content": "根据你的训练数据回答。如果不知道就诚实说不知道。"},
            {"role": "user", "content": question},
        ])
        grade_b = llm_answer([
            {"role": "user", "content": GRADE_PROMPT.format(ground_truth=ground_truth, student_answer=ans_b)},
        ], max_tokens=512)
        gb = parse_grade(grade_b)
        b_total += gb["score"]

        delta = ga["score"] - gb["score"]
        symbol = "✅" if delta > 2 else ("➡️" if delta >= 0 else "❌")

        print(f"  A (memory): {ga['score']}/10 | B (no memory): {gb['score']}/10 | Δ={delta:+d} {symbol}")

        results.append({
            "question": question,
            "ground_truth": ground_truth[:500],
            "score_a": ga["score"],
            "score_b": gb["score"],
            "delta": delta,
            "answer_a": ans_a[:600],
            "answer_b": ans_b[:600],
            "grade_a_reason": ga.get("reason", ""),
            "grade_b_reason": gb.get("reason", ""),
            "context_a": ctx[:500],
        })

    elapsed = time.time() - start_time
    avg_a = round(a_total / len(QUESTIONS), 1)
    avg_b = round(b_total / len(QUESTIONS), 1)

    print("\n" + "="*70)
    print("A/B TEST RESULTS")
    print("="*70)
    print(f"Questions:                {len(QUESTIONS)}")
    print(f"Group A (with memory):    {avg_a}/10 average")
    print(f"Group B (without memory): {avg_b}/10 average")
    print(f"Improvement:              +{avg_a - avg_b} points ({(avg_b and (avg_a/avg_b-1)*100) or 0:.0f}%)")
    print(f"Time:                     {elapsed:.0f}s")
    print("="*70)

    for i, (r, (title, _, _)) in enumerate(zip(results, FACTS)):
        d = r["delta"]
        sym = "✅" if d > 2 else ("➡️" if d >= 0 else "❌")
        print(f"  Q{i+1:2d}  A={r['score_a']} B={r['score_b']} Δ={d:+d} {sym}  {title}")

    report = {
        "test": "Sisyphus A/B Test — With vs Without Memory",
        "timestamp": time.strftime("%Y-%m-%d %H:%M UTC"),
        "model": "deepseek-v4-flash",
        "questions": len(QUESTIONS),
        "avg_a": avg_a,
        "avg_b": avg_b,
        "improvement_pct": round((avg_b and (avg_a/avg_b-1)*100) or 0, 1),
        "elapsed_s": int(elapsed),
        "details": results,
    }

    out = Path.home() / "sisyphus-ab-report.json"
    json.dump(report, open(out, "w"), indent=2, ensure_ascii=False)
    print(f"\nReport saved: {out}")

if __name__ == "__main__":
    main()
