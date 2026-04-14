"""知识图谱提取 Prompt"""

EXTRACT_ENTITIES = """你是一位结构化信息提取专家。从以下论文分析报告中提取实体和关系。

<analysis>
{analysis_text}
</analysis>

请返回 **严格的 JSON**（不要 markdown 代码块，不要额外文字），格式如下：

{{
  "paper": {{
    "title": "论文英文标题",
    "authors": ["作者1", "作者2"],
    "year": 2025,
    "venue": "发表渠道",
    "domain_tags": ["tag1", "tag2", "tag3"]
  }},
  "concepts": [
    {{"name": "概念名（英文优先）", "definition": "一句话定义", "role": "core|used|compared"}}
  ],
  "methods": [
    {{"name": "方法名", "description": "一句话描述", "type": "proposed|baseline|component"}}
  ],
  "datasets": [
    {{"name": "数据集名", "domain": "领域"}}
  ],
  "metrics": [
    {{"name": "指标名", "description": "含义"}}
  ],
  "relationships": [
    {{
      "source_type": "paper|concept|method|dataset",
      "source": "源名称",
      "relation": "proposes|uses|improves|compares|contradicts|evaluated_on",
      "target_type": "paper|concept|method|dataset",
      "target": "目标名称",
      "evidence": "简短证据"
    }}
  ],
  "key_claims": [
    {{"claim": "论文的关键论断", "evidence_strength": "strong|moderate|weak"}}
  ]
}}

提取要求：
1. concepts 提取 5-15 个关键概念（优先用英文名称）
2. methods 提取论文提出的方法 + 对比的 baseline 方法
3. relationships 至少 8 条，覆盖论文的核心创新关系
4. key_claims 提取 3-5 个关键论断
5. 所有名称统一用英文（或英文缩写），保持跨论文可匹配性
"""

FIND_GAPS = """你是一位研究方法论专家。分析以下知识图谱数据，识别研究空白和潜在创新点。

图谱统计：
{graph_stats}

所有概念节点：
{concepts}

所有方法节点：
{methods}

所有关系：
{edges}

请分析并输出 Markdown 报告：

# 研究空白与潜在创新点分析

## 1. 孤立概念（被提及但缺乏深入研究）
（列出只在 1-2 篇论文出现、没有被充分展开的概念）

## 2. 缺失的方法-数据集组合
（哪些方法从未在某些重要数据集上评测？）

## 3. 未被探索的方法组合
（哪些方法可以互补但从未被组合？基于改进链 A→B→C 分析）

## 4. 矛盾论断
（不同论文对同一问题给出了矛盾的结论？列出矛盾点及证据）

## 5. 高价值研究方向建议
（基于以上分析，给出 3-5 个具体的、可操作的研究方向，按价值排序）

每个方向需包含：
- **方向名称**
- **为什么重要**（基于图谱中的证据）
- **切入点**（具体可以做什么）
- **相关论文**（图谱中与此方向最相关的 2-3 篇论文）
"""
