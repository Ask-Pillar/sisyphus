# Nexus 知识层方案 — 接入 Obsidian + 大数据导入

## 原则

- **Sisyphus 只管记忆** — 决策、教训、偏好、对话历史
- **Obsidian 管知识** — 文档、笔记、代码片段、wiki
- **Nexus 做桥梁** — 统一检索入口，Agent 不用知道底层是哪个

## 架构

```
Agent: "nginx proxy_pass 怎么配"
  → Nexus Core
    ├── sisyphus: "上次配置过 proxy_pass，踩了 trailing slash 的坑"
    └── Obsidian: ~/notes/nginx/proxy_pass.md → 返回文档
  → 合并结果 → 给 Agent
```

## Obsidian 接入方案

Obsidian 就是 Markdown 文件目录，不需要任何转换：

```yaml
# config/nexus.yaml
knowledge:
  provider: obsidian
  vault_path: ~/notes
  include_tags: [permanent, reference]  # 只索引固定笔记
  exclude_tags: [draft, daily]          # 跳过日记和草稿
  fts5_index: ~/.omo/knowledge/obsidian.db
```

**实现**（20 行 Python）：

```python
def index_obsidian_vault(vault_path, db_path):
    """Index all .md files in Obsidian vault into SQLite FTS5."""
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS docs USING fts5(path, title, content, tags)")

    for md_file in Path(vault_path).rglob("*.md"):
        content = md_file.read_text()
        # 提取 frontmatter tags
        tags = extract_frontmatter_tags(content)
        # 跳过草稿和日记
        if "draft" in tags or "daily" in tags:
            continue
        conn.execute(
            "INSERT INTO docs VALUES (?, ?, ?, ?)",
            (str(md_file), md_file.stem, content, ",".join(tags)),
        )
    conn.commit()
```

**好处**：
- 不改 Obsidian — 你继续在 Obsidian 里写笔记
- 不复制文件 — 只建 FTS5 索引，文档原样保留
- 支持 frontmatter — `tags: [permanent, nginx]` 控制索引范围
- 搜索秒级 — FTS5 全文检索，50GB vault ~100ms

## 大数据量知识导入方案（50GB+）

### 第一步：分析扫描

```bash
python nexus knowledge scan ~/knowledge/
# 输出:
#   pdf: 4200 个, 12GB
#   markdown: 8900 个, 800MB
#   txt: 1500 个, 200MB
#   jsonl: 300 个, 3GB
#   csv: 200 个, 5GB
#   png: 5000 个, 18GB
#   docx: 800 个, 4GB
#   其他: 1200 个, 7GB
#   总计: 50GB, 22100 个文件
```

### 第二步：分批导入

```bash
python nexus knowledge import ~/knowledge/ \
  --batch-size 500MB \
  --workers 4 \
  --format pdf,markdown,txt,jsonl,csv \
  --output ~/.omo/knowledge/docs.db
```

| 批次 | 文件数 | 大小 | 时间 | 操作 |
|------|--------|------|------|------|
| 1 | 500 | 500MB | 30s | 提取文本 → FTS5 写入 |
| 2 | 500 | 500MB | 30s | 同上 |
| ... | ... | ... | ... | ... |
| 100 | 500 | 500MB | 30s | 同上 |
| **总计** | **22,100** | **50GB** | **~50 分钟** | SQLite 事务 + 批量提交 |

### 第三步：中断续传

```bash
# 导入 30% 时停止了
python nexus knowledge resume \
  --checkpoint ~/.omo/knowledge/import_checkpoint.json
# 自动跳过已导入的文件，从断点继续
```

检查点文件：

```json
{
  "last_imported": "/path/to/file_1500.pdf",
  "progress": "30%",
  "files_done": 6600,
  "files_total": 22100
}
```

### 第四步：增量更新

```bash
# 每周运行，只导入新增/修改的文件
python nexus knowledge sync ~/knowledge/ \
  --since "7 days ago"
```

通过文件修改时间判断是否需要重新索引。

### 格式处理

| 格式 | 提取方式 | 库 |
|------|----------|-----|
| .md | 直接读取 | 内置 |
| .txt | 直接读取 | 内置 |
| .pdf（文本层） | 提取文本 | pymupdf |
| .pdf（扫描件） | OCR | tesseract |
| .docx | 解压 XML | python-docx |
| .jsonl | 逐行解析 | 内置 |
| .csv | 逐行读取 | 内置 |
| .png/.jpg | OCR 或 llama-vision | tesseract / llama-vision |

## 配置

```yaml
# config/nexus.yaml
knowledge:
  providers:
    obsidian:
      enabled: true
      vault_path: ~/notes
    imported:
      enabled: true
      db_path: ~/.omo/knowledge/docs.db
      sources:
        - path: ~/knowledge/
          formats: [pdf, markdown, txt, jsonl, csv]
        - path: ~/documents/research/
          formats: [pdf]
```

## 命令

```bash
# 扫描
nexus knowledge scan ~/knowledge/

# 导入
nexus knowledge import ~/knowledge/ --batch-size 500MB

# 恢复
nexus knowledge resume

# 增量同步
nexus knowledge sync ~/knowledge/ --since "7 days ago"

# 搜索
nexus knowledge search "nginx proxy_pass"

# 统计
nexus knowledge stats
```

## 搜索性能

| 知识库大小 | FTS5 索引大小 | 搜索延迟 |
|-----------|-------------|---------|
| 1GB | ~200MB | < 10ms |
| 10GB | ~2GB | < 50ms |
| 50GB | ~10GB | < 100ms |

索引大小约为原文的 20%。10GB 索引对 3TB 硬盘完全无压力。
