# ReadLoop v2.1 — Agent Harness for Paper Research

> 把"读完就忘"变成"知识资产"

## 一句话描述

一个基于 Harness Engineering 理念设计的论文研究 Agent 系统：自动分析学术论文 → 构建知识图谱 + 长期记忆 → Leiden 社区检测发现研究主题 → 跨论文关联与空白发现 → 语义问答 + 综述生成 + 研究提案。交互式 CLI 界面，24 个 slash 命令。

---

## 当前状态

| 指标 | 数值 |
|------|------|
| 已分析论文 | 14 篇（reference paper 目录） |
| 待分析论文 | 286 篇（agentmemory/papers A/B/C 类） |
| 知识图谱 | 390 nodes, 467 edges, 120 communities |
| 长期记忆 | 250 entries, 14 papers covered |
| 代码量 | ~3,600 行 Python, 27 个源文件 |
| CLI 命令 | 24 个交互式 slash 命令 |
| 导出格式 | HTML / Obsidian Wiki (174 篇) / GraphML / Mermaid |

---

## 版本历史

### v2.1.0 (当前)
- Graphify 集成: Leiden 社区检测、图谱分析、Obsidian Wiki 导出、GraphML 导出
- 交互式 CLI (类似 Claude Code): 24 个 slash 命令、Tab 补全、输入历史
- HTML 可视化升级: sidebar + 社区着色 + 信息面板 + 度数缩放
- 记忆搜索升级: 混合评分 (embedding 70% + keyword 15% + tag 10% + conf 5%)
- Q&A 反馈循环: 问答自动存为新记忆
- 安全加固: XSS 转义、路径穿越防护、from_dict 字段过滤

### v2.0.0
- 知识图谱构建 + 跨论文边检测
- 长期记忆系统 + 语义搜索 + 上下文召回
- 自动综述、概念演进、研究提案
- 交互式 HTML 可视化 (vis-network)
- 双轨 LLM (DeepSeek + Claude)

### v1.0.0
- 基础论文分析管道
- PDF/图片文本提取
- 单篇 + 批量分析

---

## 技术栈

| 层 | 技术 |
|----|------|
| LLM | DeepSeek V3 (主) + Claude Sonnet 4.6 (备) |
| PDF | PyMuPDF |
| Embedding | all-MiniLM-L6-v2 (22MB, 384 维, CPU) |
| 图算法 | NetworkX + graspologic (Leiden) |
| 可视化 | vis-network 9.1.6 |
| CLI | prompt_toolkit + Rich |
| 存储 | JSON + NumPy (全本地, 无数据库) |

---

## 快速开始

```bash
# 安装
cd D:/wu/readloop
pip install -r requirements.txt

# 启动交互式 CLI
python run.py

# 或脚本模式
python run.py --single "A-MEM"
python run.py --build-graph
python run.py --ask "哪些论文讨论了记忆压缩？"
```

详细架构设计见 [ARCHITECTURE.md](./ARCHITECTURE.md)。
