#!/usr/bin/env python3
"""Sisyphus A/B Test: Agent with memory vs Agent without memory.
 
Same questions, same LLM, same knowledge base — the only variable:
  Group A: AgentMemory.before_turn() injects relevant context
  Group B: Empty context, relies on model's training data only
"""

import json, os, time, tempfile, urllib.request
from pathlib import Path
from typing import List, Tuple

# ── Test Knowledge Base (facts taught BEFORE the test) ──
FACTS = [
    ("Sisyphus存储层级", "decision",
     "Sisyphus采用四层存储架构：RAW层(Markdown文件，append-only永不删除)、REFINED层(LLM加工产物，可重建)、MOC层(Obsidian兼容wikilink索引)、AGENT层(子agent独立沙箱)。数据以文件为唯一真相源(SSOT)，SQLite仅为可重建的加速缓存。"),
    ("decay_score衰减算法", "pattern",
     "记忆权重衰减使用指数模型：decay_score = importance × 0.5^(days/30)，半衰期30天。优先使用last_recalled_at计算时间差，若为空则回退到created_at。每次检索后自动更新recall_count和last_recalled_at。"),
    ("SubagentLauncher子进程调度", "architecture",
     "所有LLM加工在独立子进程中执行，主进程仅做书签同步。流程：主进程写task.json→spawn子进程(python -m sisyphus.memory.subagent)→子进程做LLM+文件IO→写result.json→主进程读结果。支持5个handler：dream/compress/recall_search/recall_relevant/classify_types。"),
    ("ContextRetriever三层检索", "architecture",
     "L1通过MOC INDEX.md查找与query相关的记忆类型(关键词重叠打分)。L2从refined层召回reflection和summary。L3在L2结果不足top_k时从RAW层按需补缺。decay_score排序后截断。MOC支持两种格式：MocGenerator的##type标题格式和MemoryStore的flat格式。"),
    ("MCP Server集成方案", "decision",
     "通过stdio JSON-RPC协议实现零依赖MCP server。4个工具：write_memory(写记忆)、search_memory(搜索返回上下文块+列表)、get_context(返回<sisyphus_context>块)、memory_stats(统计概览)。一次配置，支持opencode/ClaudeDesktop/VS Code/Cursor等所有MCP兼容客户端。"),
    ("AgentMemory自动注入", "architecture",
     "AgentMemory是自动注入入口类。before_turn(query)每次agent响应前调用，自动处理全量/增量刷新。三种触发全量检索的条件：turn==0、MemoryStore被标记为dirty(写入后)、距离上次全量超过refresh_interval。dirty标记在create/update/delete时自动设True，检索后clear。"),
    ("回路检测LoopDetector", "pattern",
     "检测同标题≥3次的重复记忆模式。按精确标题分组，阈值默认3(可在CLI中指定阈值)。检测到回路后：标记最早出现的那条记忆的repeat_count字段、创建RefinedStore中的loop_record记录。与recall_count语义独立。"),
    ("断链清理LinkCleaner", "pattern",
     "三种清理操作：删除指向不存在记忆的死链(dead links)、移除重复链接(deduplicate)、去除自引用(self-reference removes)。执行完毕后保留有效链接。与LinkAnalyzer废弃的自动关联不同，LinkCleaner只做按需清理不做自动关联。"),
    ("LLM max_tokens坑", "lesson",
     "使用DeepSeek reasoning模型(deepseek-v4-flash)时，max_tokens=500会导致内容为空。原因：reasoning_content占用token预算后content没分到。修复：max_tokens提高到2048，可通过SISYPHUS_LLM_MAX_TOKENS环境变量控制。"),
    ("记忆系统的测试策略", "lesson",
     "采用三层测试：单元测试(mock LLM，188条全绿)、集成测试(子进程协议验证，task.json→subprocess→result.json)、全链路验证(真实LLM写入→dream→recall→context)。大规模测试使用200条记忆+165次recall+compress，总消耗103万token。"),
    ("Pipeline自动流水线", "architecture",
     "5个顺序步骤：1.回路检测(扫描RAW层同标题≥3次标记) 2.压缩(RAW超阈值退火合并) 3.反射(未加工记忆≥3条触发DreamEngine) 4.MOC索引(增量更新) 5.断链清理(无效/重复/自引用)。无LLM API key时LLM步骤自动跳过。"),
    ("DreamEngine反射机制", "architecture",
     "DreamEngine收集所有未加工记忆→委托SubagentLauncher→子进程调LLM分析→生成reflection记忆存入refined/reflection/目录。每条reflection含title/content/importance/evidence(原始记忆ID列表)。原记忆的refined_by字段更新为reflection的ID。"),
    ("Compressor退火压缩", "architecture",
     "threshold参数控制触发阈值(默认20条)。keep_recent保留最新N条不压缩。压缩过程：子进程列出store→调LLM生成摘要→创建新compressed记忆→删除旧记忆。主进程只拿到deleted_count。运行方法：compressor.run() 返回删除数量。"),
    ("Recall召回机制", "architecture",
     "Recall.search(query,top_k)将全部记忆列表+query发给子进程LLM，子进程返回相关memory_ids。主进程用这些ID从store中取出完整Memory对象。Recall.is_relevant(memory,query)评分单条记忆相关性(0.0-1.0)。支持Recaller别名。"),
    ("188测试覆盖全景", "lesson",
     "19个测试文件覆盖19个模块：store/store_v2(CRUD+frontmatter)、refined(三层加工)、dream/compression/recall(子agent委托)、retrieval(三层检索+MOC匹配)、context(MemoryContext+dirty+AgentMemory)、pipeline(自动触发)、loop(回路检测)、link(断链清理)、moc(索引生成)、agent(沙箱隔离)、cache(SQLite)、log(结构化日志)、snapshot(冻结快照)、extraction(记忆提取)、search(嵌入搜索)、cli(命令解析)。"),
]

QUESTIONS = [
    "Sisyphus有几层存储架构？每层的作用是什么？",
    "decay_score的衰减公式是什么？半衰期是多少天？如何计算时间差？",
    "SubagentLauncher的工作流程是怎样的？支持哪些handler？",
    "ContextRetriever的三层检索分别是什么？L1是如何确定相关类型的？",
    "MCP Server提供哪四个工具？使用什么协议？",
    "AgentMemory的before_turn()在什么条件下触发全量检索？",
    "LoopDetector如何检测回路？阈值默认是多少？检测到回路后做什么？",
    "LinkCleaner做哪三种清理操作？它与LinkAnalyzer有什么区别？",
    "使用DeepSeek reasoning模型时max_tokens应设为多少？为什么？",
    "大规模测试消耗了多少token？包含哪些步骤？",
    "Pipeline的5个步骤分别是什么？无LLM key时如何处理？",
    "DreamEngine的反射结果包含哪些字段？源记忆如何关联到reflection？",
    "Compressor的threshold和keep_recent参数是什么？run()返回什么？",
    "Recall.search()和Recall.is_relevant()的功能有什么区别？",
    "188个测试分布在多少个测试文件中？列出至少5个测试文件及其覆盖模块。",
]

# ── LLM call for answering ──
def llm_answer(messages, max_tokens=1024):
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
    resp = urllib.request.urlopen(req, timeout=60)
    data = json.loads(resp.read().decode())
    return data["choices"][0]["message"]["content"]

# ── Grading ──
GRADE_PROMPT = """You are a grading assistant. Compare the student's answer against the ground truth.

Ground truth:
{ground_truth}

Student answer:
{student_answer}

Score the answer from 0 to 10 based on:
- Factual accuracy (6 points): Are the facts correct?
- Completeness (3 points): Are all key points covered?
- No hallucination (1 point): No made-up information?

Return ONLY a JSON: {{"score": X, "reason": "brief explanation"}}"""


def main():
    from sisyphus.memory.store import MemoryStore
    from sisyphus.memory.refined import RefinedStore
    from sisyphus.memory.context import AgentMemory

    print("=" * 70)
    print("Sisyphus A/B Test: With Memory vs Without Memory")
    print("=" * 70)

    tmp = Path(tempfile.mkdtemp()) / "mem"
    store = MemoryStore(base_path=tmp)
    refined = RefinedStore(base_path=tmp)

    # Write facts as memories (Group A's knowledge base)
    for title, mem_type, content in FACTS:
        store.create(title=title, type=mem_type, content=content, tags=[mem_type])

    a_scores = []
    b_scores = []
    a_answers = []
    b_answers = []

    for i, (question, (title, _, fact)) in enumerate(zip(QUESTIONS, FACTS)):
        print(f"\nQ{i+1}: {question[:60]}...")

        # ── Group A: with memory context ──
        agent = AgentMemory(store, refined)
        ctx = agent.before_turn(query=question)

        system_a = f"You are a knowledge QA agent. Use the context below to answer.\n\n{ctx}"
        answer_a = llm_answer([
            {"role": "system", "content": system_a},
            {"role": "user", "content": question},
        ])
        a_answers.append(answer_a)

        # ── Group B: without memory ──
        answer_b = llm_answer([
            {"role": "system", "content": "You are a knowledge QA agent. Answer based on your training data only."},
            {"role": "user", "content": question},
        ])
        b_answers.append(answer_b)

        # ── Grade ──
        grade_a = llm_answer([{"role": "user", "content": GRADE_PROMPT.format(
            ground_truth=fact, student_answer=answer_a
        )}], max_tokens=256)
        grade_b = llm_answer([{"role": "user", "content": GRADE_PROMPT.format(
            ground_truth=fact, student_answer=answer_b
        )}], max_tokens=256)

        def _parse_grade(raw):
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            try:
                return json.loads(raw).get("score", 0)
            except:
                return 0
        sa = _parse_grade(grade_a)
        sb = _parse_grade(grade_b)

        a_scores.append(sa)
        b_scores.append(sb)
        print(f"  A (with memory):    {sa}/10")
        print(f"  B (without memory): {sb}/10")

    avg_a = sum(a_scores) / len(a_scores)
    avg_b = sum(b_scores) / len(b_scores)

    print("\n" + "=" * 70)
    print("A/B TEST RESULTS")
    print("=" * 70)
    print(f"Questions:                {len(QUESTIONS)}")
    print(f"Group A (with memory):    {avg_a:.1f}/10 average")
    print(f"Group B (without memory): {avg_b:.1f}/10 average")
    print(f"Improvement:              +{avg_a - avg_b:.1f} points ({(avg_a/avg_b - 1)*100:.0f}%)")
    print("=" * 70)

    # Detailed breakdown
    print("\nDetailed Scores:")
    print(f"{'#':<4} {'A':>5} {'B':>5} {'Δ':>5} Question")
    for i, (sa, sb) in enumerate(zip(a_scores, b_scores)):
        delta = sa - sb
        print(f"{i+1:<4} {sa:>5.1f} {sb:>5.1f} {delta:>+5.1f} {QUESTIONS[i][:50]}")

    # Save report
    report = {
        "test_type": "ab_test",
        "avg_score_with_memory": avg_a,
        "avg_score_without_memory": avg_b,
        "improvement_percent": (avg_a/avg_b - 1) * 100,
        "per_question": [
            {"question": q, "score_a": sa, "score_b": sb, "answer_a": aa, "answer_b": ab}
            for q, sa, sb, aa, ab in zip(QUESTIONS, a_scores, b_scores, a_answers, b_answers)
        ],
    }
    json.dump(report, open(Path.home() / "sisyphus-ab-report.json", "w"), indent=2, ensure_ascii=False)
    print(f"\nReport saved: ~/sisyphus-ab-report.json")

    # Conclusion
    if avg_a > avg_b + 2:
        print("\n✅ CONCLUSION: Memory system significantly improves recall accuracy.")
    elif avg_a > avg_b:
        print("\n✅ CONCLUSION: Memory system provides measurable improvement.")
    else:
        print("\n⚠️ CONCLUSION: Marginal difference — check test design.")

if __name__ == "__main__":
    main()
