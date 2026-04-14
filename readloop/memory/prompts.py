"""记忆提取与问答 Prompt"""

EXTRACT_MEMORIES = """从以下论文分析中提取关键知识条目。

<analysis>
{analysis_text}
</analysis>

论文名称: {paper_name}

请返回严格 JSON（不要 markdown 代码块）:

{{
  "facts": [
    {{"content": "不可变的事实陈述（方法定义、架构描述、实验设置等）", "tags": ["tag1", "tag2"]}}
  ],
  "claims": [
    {{"content": "论文的关键论断（性能声明、比较结论等，可能与其他论文矛盾）", "confidence": 0.8, "tags": ["tag1"]}}
  ]
}}

要求:
1. facts 提取 8-15 条核心事实
2. claims 提取 3-8 条关键论断，标注 confidence (0-1)
3. 每条 content 需自包含（不依赖上下文即可理解）
4. tags 使用英文，保持跨论文可匹配性
"""

ANSWER_QUERY = """你是一位论文知识库助手。基于以下检索到的知识条目回答用户问题。

用户问题: {query}

相关知识条目:
{memories}

请基于以上知识条目回答问题。要求:
1. 回答要具体，引用来源论文
2. 如果不同论文有矛盾观点，需指出
3. 如果知识条目不足以回答，坦诚说明
4. 使用中文回答
"""

CONTEXTUAL_RECALL_INTRO = """## 已有相关研究知识（来自已分析论文）

以下是与当前论文相关的已有知识。请在分析时参考这些信息，进行更深入的对比和关联分析：

{recalled_memories}

---

"""
