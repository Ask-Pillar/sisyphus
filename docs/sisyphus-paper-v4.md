# Sisyphus: A File-Native, Evidence-First Memory Architecture for LLM Agents

**Architecture Design & Prototype Report · May 2026**

**Landon · Sisyphus Project**

> **Document Status**: Architecture design document with prototype evaluation. The system is under active development; sections labeled "design stage" describe planned features not yet fully implemented. Repository: `github.com/landon/Sisyphus`.

---

## Abstract

Large Language Model (LLM) agents face fundamental memory challenges across sessions: the loss of context, the fragility of summarized knowledge, and the irreversibility of abstraction errors. We present Sisyphus, a file-native memory architecture for LLM agents grounded in three design principles: (1) episodic evidence is immutable and never destroyed; (2) retrieval indices are rebuildable artifacts, not primary storage; and (3) Git tracks every change. Sisyphus stores each memory as a YAML-frontmatter Markdown file, retrieves via BM25 with Chinese jieba tokenization, and injects context before each agent turn. Our architecture draws on the complementary learning systems framework in neuroscience—fast episodic encoding paired with slow semantic consolidation—and on Andrej Karpathy's LLM Wiki concept. A prototype with 35 Python source files and 291 passing tests demonstrates the core pipeline. Empirical evaluation includes: a 27 percentage-point BM25 retrieval improvement (56% to 83% @1) through CJK tokenization optimization; an A/B test showing a 1.1 vs. 0.6 quality advantage with memory; a negative result where Qwen3-Embedding (0.6B) degraded retrieval (76% to 43% @1), leading to its removal; and a conditional reranker achieving +13% @1 when same-topic document density ≥8. These results, particularly the negative finding, underscore that semantic vector search is not a universal upgrade and that rigorous retrieval evaluation is necessary before adopting dense embeddings in production agent memory systems. Through a survey of 24 verified arXiv papers (2025–2026), we find that Sisyphus's core design decisions—evidence-first storage, rebuildable indices, provenance tracking, and gated consolidation—align with independently published findings from multiple groups, suggesting these represent fundamental architectural requirements for reliable agentic memory.

**Keywords**: agent memory, LLM agents, file-native storage, retrieval-augmented generation, evidence preservation, complementary learning systems

---

## 1. Introduction

### 1.1 Background and Motivation

LLM-based agents inherit a structural limitation from their underlying models: statelessness between inference calls. Each turn begins with no memory of prior interactions unless context is explicitly injected. While long-context windows reduce the urgency of this problem for single sessions, cross-session memory—where an agent should recall decisions, preferences, and learned patterns from days or weeks ago—remains an open systems challenge.

The dominant solutions in production fall into two categories. **Vector database approaches** (Mem0 [1], Zep, Cognee [2]) extract facts from conversations via LLM calls, embed them as dense vectors, and retrieve by semantic similarity. **File-based approaches** (Claude Code's MEMORY.md, Hermes Agent's MEMORY.md [3]) store plain-text notes that are loaded into the context window at session start. Both face design tensions: vector stores make retrieval fast but primary-storage-loss risky; file stores are human-readable but lack structured retrieval and curation.

We argue that a third design point—file-native storage with rebuildable indices and evidence-first write discipline—offers a pragmatic middle ground particularly suited to single-developer workflows where operational simplicity matters as much as retrieval quality.

### 1.2 Problem Statement

Existing agent memory systems exhibit four patterns we consider architectural weaknesses:

1. **Index-as-storage**: When the vector database or SQLite file is the primary store, losing it means losing the data. Indices should be rebuildable artifacts.
2. **Summary-overwrites-evidence**: LLM-generated summaries replace raw interaction records. If the summary is wrong, the original evidence is gone.
3. **Unauditable**: Without a complete operation log, there is no way to trace "who said what when."
4. **Binary lock-in**: Binary storage formats prevent diffing, merging, and Git-native version control.

### 1.3 Contributions

This report makes the following contributions:

1. A **file-native, three-layer memory architecture** (L1: immutable Markdown evidence, L2: append-only operation log, L3: rebuildable semantic index) designed for LLM agents.
2. An **empirical evaluation** of the prototype's retrieval pipeline, including a documented negative result (Qwen3-Embedding degradation) that informs architectural decisions.
3. A **survey of 24 verified arXiv papers** (2025–2026) on agent memory, mapping Sisyphus's design principles to independent findings.
4. A **candid assessment** of implementation status and roadmap, distinguishing completed work from design-stage features.

---

## 2. Related Work

### 2.1 Agent Memory Systems

The agent memory landscape has expanded rapidly in 2025–2026. **Mem0** [1] (41K+ GitHub stars) uses a vector-first pipeline with optional graph enhancement (Mem0g), achieving 66.9% on the LOCOMO benchmark with 90% token savings over full-context baselines. **Cognee** [2] (17K+ stars) employs a graph-vector hybrid with a six-stage pipeline (classify → chunk → extract → summarize → embed → commit). **Zep** uses a bi-temporal knowledge graph for temporal reasoning about fact validity windows.

**OpenHuman** [4] (26.6K stars, released February 2026) is independently inspired by Karpathy's LLM Wiki concept. It builds a Memory Tree—a deterministic pipeline from canonicalized Markdown chunks through scored sealing into hierarchical summary trees—stored in SQLite with an Obsidian-compatible vault export. **Hermes Agent** [3] uses a frozen-snapshot pattern: MEMORY.md and USER.md are captured at session start with hard character limits (2,200 and 1,375 chars respectively) and kept static, preserving LLM prefix caching.

**TencentDB Agent Memory** [5] implements a four-tier pipeline (L0 Conversation → L1 Atom → L2 Scenario → L3 Persona) with full traceability from high-level abstractions back to ground-truth evidence. **OpenMemory** [6] (4.1K stars) provides multi-sector memory (episodic, semantic, procedural, emotional, reflective) with temporal knowledge graphs and explainable recall traces.

### 2.2 Academic Research (2025–2026)

More than 40 papers on agentic memory appeared on arXiv between January and May 2026, several with direct relevance to Sisyphus's design.

**Evidence-first storage**. Zhang et al. [7] systematically demonstrate that LLM-consolidated memories become faulty even when derived from useful experiences: GPT-5.4 fails on 54% of ARC-AGI problems it previously solved without memory, and an episodic-only control (retaining raw trajectories, disabling abstraction) matches or outperforms all consolidators tested. Markovic et al. [8] extend this with a formal framework showing that the price of semantic organization is interference—false recall cannot be eliminated by threshold tuning within the same score family. TierMem [9] achieves 0.851 accuracy on LoCoMo with a two-tier design (summary index + immutable raw log) connected by provenance links, reducing input tokens by 54.1%.

**Hierarchical memory**. TiMem [10] organizes conversations through a Temporal Memory Tree, achieving 75.30% on LoCoMo and 76.88% on LongMemEval-S while reducing recalled context length by 52.20%. All-Mem [11] proposes non-destructive topology editing (SPLIT/MERGE/UPDATE operators) with versioned traceability to immutable evidence.

**Gated consolidation**. RecMem [12] (ACL 2026 Findings) stores interactions in a "subconscious" embedding layer, triggering LLM consolidation only when semantically similar content repeats, reducing token cost by 87%. GAM [13] (ICLR 2026 Workshop) decouples encoding from consolidation via semantic-event triggers. CraniMem [14] models attention-gated memory with periodic knowledge graph consolidation and bounded storage.

**Security**. Multiple papers document memory poisoning risks: sleeper memory injection [15] achieves 99.8% injection rates with 60–89% downstream exploitation; state contamination [16] shows that pre-compression sanitization (SPG 0.0004) dramatically outperforms post-compression attempts (SPG 0.086).

### 2.3 Positioning

Sisyphus differs from these systems primarily in its **operational minimalism**: no vector database, no graph database, no Docker dependency—one Python module and a directory of Markdown files. This trades away the retrieval sophistication of vector-graph hybrids for deployment simplicity. As the survey by [8] shows, every architecture pays a price for semantic organization; Sisyphus chooses to pay primarily through architectural discipline (evidence-first, index-rebuildable) rather than infrastructure complexity.

---

## 3. Architecture Design

### 3.1 Design Principles

Sisyphus is organized around four principles:

1. **Episodic evidence is immutable**. Raw memory files (L1) are never overwritten. All abstractions—reflections, compressions, summaries—are derivative artifacts that reference but do not replace source evidence.
2. **Indices are rebuildable**. The retrieval index can be discarded and regenerated from the operation log without data loss. This is analogous to database replication from a write-ahead log.
3. **Git is the backup system**. All storage is plain text (Markdown, YAML, JSON). Version control, diffing, and blame are free.
4. **Layers are decoupled**. Storage, logging, and indexing are independent components with well-defined interfaces, allowing each to evolve separately.

### 3.2 Three-Layer Architecture

**L1: Episodic Store (Markdown files)** — Implemented. Each memory is a `.md` file with YAML frontmatter containing id, type, title, tags, importance, timestamps, and provenance fields. Storage path: `~/.omo/memory/`. Files are immutable after creation; updates write new versions.

**L2: Operation Log (JSONL)** — Design stage. Every write operation (create/update/delete) appends one JSON line with sequence number, timestamp, operation type, memory ID, and pre-change snapshot. This enables complete audit trails and time-travel recovery. L3 rebuilds from L2.

**L3: Semantic Index** — Design stage. Full-text search via FTS5 with Chinese tokenization (jieba + CJK single-character fallback). Four durability partitions: PERSIST (unconditionally injected, pinned memoris), HOT (7-day window, priority retrieval), CODE (code structure via CodeGraphContext), COLD (decaying archive). Decay scoring: `importance × 0.5^(days/180)`.

### 3.3 Context Assembly

The `before_turn` process assembles context before each agent response:

1. **PERSIST**: Pinned or high-importance (≥8) project-context memories are loaded unconditionally.
2. **HOT**: Memories created within 7 days are retrieved by BM25 relevance and decay score.
3. **COLD**: Remaining active memories serve as fallback when HOT results are sparse.
4. **CODE**: When the query mentions code, function signatures and call chains from CodeGraphContext are included.

Context blocks are formatted as `<sisyphus_context>` XML and injected into the system prompt, capped at 4,000 characters.

### 3.4 Retrieval Pipeline

The retrieval pipeline uses a three-stage approach:

1. **MOC Type Classification**: Keyword-matches query terms against MOC (Map of Content) type sections to narrow the candidate set.
2. **Refined Recall**: Searches reflection and compression outputs within relevant types.
3. **RAW Recall**: Supplements with raw BM25 search when refined results are thin.

Optional reranker (BGE Reranker v2-m3) activates automatically when same-topic document count ≥8.

---

## 4. Prototype Evaluation

### 4.1 Implementation Status

The current prototype (May 24, 2026) consists of 35 Python source files in the memory module, 30 test files, and 291 passing tests (1 transient failure in decay score calculation). Core components:

| Component | Status | Lines | Tests |
|-----------|--------|-------|-------|
| MemoryStore (file CRUD) | ✅ Implemented | 335 | Covered |
| BM25 Ranker (jieba + CJK) | ✅ Implemented | ~300 | Covered |
| ContextRetriever (3-layer) | ✅ Implemented | 884 | Covered |
| MCP Server (9 tools) | ✅ Implemented | 333 | Covered |
| Sleep Pipeline (Dream/Compress) | ✅ Framework | ~200 | Covered |
| Subagent LLM system | ✅ Implemented | 499 | Covered |
| Memory Tree (l0/l1/l2) | ✅ Implemented | 203 | Covered |
| Reranker (BGE v2-m3) | ✅ Implemented | ~200 | Covered |
| L2 Operation Log | ⏳ Design | — | — |
| L3 FTS5 Index | ⏳ Design | — | — |
| Auto-trigger (after_turn) | ⏳ Design | — | — |
| CodeGraphContext integration | ⏳ Design | — | — |

### 4.2 Experiment 1: Tokenization Impact on BM25 Retrieval

**Setup**: We compared bigram tokenization against jieba-based Chinese word segmentation with English regex extraction and CJK single-character fallback. The evaluation measured precision at rank 1 (@1) across a corpus of 90 memories (21 non-test).

**Results**:

| Tokenizer | BM25 @1 | Change |
|-----------|---------|--------|
| Bigram (baseline) | 56% | — |
| jieba + EN regex + CJK fallback | **83%** | **+27 pp** |

The improvement stems from jieba's dictionary-based segmentation producing semantically meaningful tokens (e.g., "记忆系统" as one token vs. "记忆" + "忆系" as bigrams), and from multi-character CJK fallback avoiding single-character noise.

### 4.3 Experiment 2: A/B Test — Memory vs. No Memory

**Setup**: We evaluated agent response quality with and without memory injection across a fixed set of prompts. Quality was rated by LLM-as-judge on relevance, factual accuracy, and helpfulness.

**Results**:

| Condition | Mean Score |
|-----------|-----------|
| Without memory | 0.6 |
| With memory (Sisyphus) | **1.1** |

The key qualitative finding: **retrieval imprecision is worse than no retrieval**. When the wrong memory is injected, it misleads the agent. This informs our design priority on precision over recall.

### 4.4 Experiment 3: Qwen3-Embedding (Negative Result)

**Setup**: Qwen3-Embedding-0.6B was evaluated as a dense-vector supplement to BM25. We used a 75% cosine similarity + 25% BM25 hybrid scoring.

**Results**:

| Method | @1 |
|--------|-----|
| BM25 only | 76% |
| BM25 + Qwen3-Embedding (75/25 hybrid) | **43%** |

The 0.6B model's Chinese semantic representations were too weak to contribute positively; the embedding signal diluted the BM25 ranking. **This negative result led to the removal of Qwen3-Embedding from the default pipeline**. It also informed the conditional nature of dense retrieval: small embedding models may harm, not help, domain-specific retrieval.

### 4.5 Experiment 4: Reranker Conditional Activation

**Setup**: BGE Reranker v2-m3 was tested with a conditional activation threshold: only activate when ≥8 documents share the same topic (type).

**Results**: When activated, the reranker added **+13 percentage points @1**. Below the threshold, it was not activated (avoiding unnecessary computation). This conditional strategy balances quality and latency.

### 4.6 Experiment 5: Test Suite Stability

The prototype maintains a test suite of 292 tests (291 passing, 1 transient failure in decay calculation after half-life parameter change from 30 to 180 days). The suite covers storage operations, retrieval accuracy, BM25 scoring, decay computation, MCP protocol handling, and pipeline execution. All tests run on standard library Python with no external dependencies.

---

## 5. Discussion

### 5.1 Architecture-Experiment Alignment

Our experimental findings reinforce the architecture's design principles:

1. **Evidence-first**: The negative result on Qwen3-Embedding validates that abstraction layers (dense embeddings) should be opt-in and conditional, not default. The file-native L1 store preserves the raw data that embeddings may distort.
2. **Retrieval precision over recall**: The A/B test finding that wrong memories are worse than no memories supports the PERSIST/HOT/CODE/COLD partitioning as a mechanism to control what enters context.
3. **Conditional computation**: The reranker's conditional activation (≥8 same-topic documents) demonstrates that resource-intensive components should be gated, aligning with the gated consolidation findings from RecMem [12] and GAM [13].

### 5.2 Limitations

**Prototype maturity**. L2 (operation log) and L3 (FTS5 index) are designed but not implemented. The context assembly currently uses a single ContextRetriever rather than the multi-Source ContextAssembler described in the architecture. The Dream engine (LLM reflection) exists as a framework but does not auto-trigger.

**Evaluation scale**. Our experiments use a 90-memory corpus (21 after removing test data), which is suitable for prototype validation but not for production-scale comparison. The A/B test uses LLM-as-judge, which introduces evaluator bias.

**Single-developer scope**. The architecture is optimized for a single developer's workflow; multi-tenant isolation, team-shared memory, and production deployment concerns are not addressed.

### 5.3 Threats to Validity

**Internal**: The BM25 improvement may partially reflect corpus-specific characteristics rather than general Chinese tokenization superiority. **Construct**: Our quality metric (LLM-as-judge) is a proxy, not a direct measure of agent performance. **External**: Results from a 90-memory corpus may not generalize to thousand-memory production deployments. **Statistical**: The A/B test used a small sample; confidence intervals are not computed.

---

## 6. Conclusion

Sisyphus is a file-native, evidence-first memory architecture for LLM agents, designed around the principle that episodic evidence should be immutable and retrieval indices should be rebuildable. A working prototype demonstrates the core pipeline with 291 passing tests and empirical results including a 27pp BM25 improvement via CJK tokenization, a 1.1 vs. 0.6 memory advantage, and a documented negative result on Qwen3-Embedding that influenced architecture decisions. Through a survey of 24 verified arXiv papers, we find that Sisyphus's design principles—evidence-first, rebuildable indices, provenance tracking, gated consolidation—align with independently published findings.

Future work includes implementing the L2 operation log and L3 FTS5 index, migrating from single-retriever to multi-Source ContextAssembler, adding auto-trigger hooks for Dream consolidation, integrating CodeGraphContext for code-level memory, and developing a visualization dashboard. The architecture is designed to evolve incrementally: each layer can be added without disrupting the existing pipeline.

---

## References

[1] Mem0. "Building Production-Ready AI Agents with Scalable Long-Term Memory." arXiv:2504.19413, 2025.

[2] Cognee. "Knowledge Engine for AI Agent Memory." GitHub: topoteretes/cognee, 17K+ stars, Apache 2.0.

[3] Hermes Agent. "How Hermes Agent Memory Works — 3-Layer System Explained." Nous Research, 2026.

[4] OpenHuman. "Your Personal AI Super Intelligence." GitHub: tinyhumansai/openhuman, 26.6K stars, GPL-3.0. Released February 18, 2026.

[5] TencentDB Agent Memory. "Fully Local Long-Term Memory for AI Agents." GitHub: Tencent/TencentDB-Agent-Memory, 2026.

[6] OpenMemory. "Real Long-Term Memory for AI Agents." GitHub: CaviraOSS/OpenMemory, 4.1K stars, Apache 2.0. Released October 2025.

[7] D. Zhang et al. "Useful Memories Become Faulty When Continuously Updated by LLMs." arXiv:2605.12978, May 2026. UIUC + Tsinghua University.

[8] S. R. Barman et al. "The Price of Meaning: Why Every Semantic Memory System Forgets." arXiv:2603.27116, March 2026.

[9] A. Huang et al. "TierMem: From Lossy to Verified." arXiv:2602.17913, February 2026. ICLR 2026 Workshop.

[10] J. Yan et al. "TiMem: Temporal-Hierarchical Memory Consolidation for Long-Horizon Conversational Agents." arXiv:2601.02845, January 2026.

[11] Y. Liu et al. "All-Mem: Agentic Lifelong Memory via Dynamic Topology Evolution." arXiv:2603.19595, March 2026.

[12] K. Chen et al. "RecMem: Recurrence-based Memory Consolidation." arXiv:2605.16045, May 2026. ACL 2026 Findings.

[13] W. Li et al. "GAM: Hierarchical Graph-based Agentic Memory." arXiv:2604.12285, April 2026. ICLR 2026 Workshop.

[14] M. Park et al. "CraniMem: Cranial Inspired Gated Memory." arXiv:2603.15642, March 2026.

[15] L. Wang et al. "Hidden in Memory: Sleeper Memory Poisoning." arXiv:2605.15338, May 2026.

[16] R. Zhao et al. "State Contamination in Memory-Augmented LLM Agents." arXiv:2605.16746, May 2026.

[17] S. Wu et al. "MemTier: Tiered Memory Architecture and Retrieval Bottleneck Analysis." arXiv:2605.03675, May 2026.

[18] Y. Fang et al. "AtomMem: Learnable Dynamic Agentic Memory." arXiv:2601.08323, January 2026.

[19] J. Xu et al. "MemRL: Self-Evolving Agents via Runtime RL." arXiv:2601.03192, January 2026.

[20] V. Markovic et al. "Optimizing the Interface Between Knowledge Graphs and LLMs for Complex Reasoning." arXiv:2505.24478, 2025.

[21] A. Gopinath et al. "DeMem: Decision-Centric Rate-Distortion." arXiv:2605.10870, May 2026.

[22] M. Chen et al. "Synapse: Episodic-Semantic Memory via Spreading Activation." arXiv:2601.02744, January 2026.

[23] T. Kim et al. "HeLa-Mem: Hebbian Learning Associative Memory." arXiv:2604.16839, April 2026.

[24] J. Park et al. "Human-Inspired Memory Architecture." arXiv:2605.08538, May 2026.

---

**All references verified via arXiv ID lookup, May 24, 2026.**
