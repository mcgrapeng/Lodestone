---
description: 刷一遍最新 AI 项目雷达（GitHub + HuggingFace + MCP Registry + arXiv 多源聚合，20 个用途分类、中文友好仪表盘）
---

使用 yz-ai skill，按其 SKILL.md 的流程执行：先调用宿主模型（OpenCode 自身）做用户意图解析与回显，再按需执行 `radar.py crawl`（约 5-8 分钟爬取+入库）→ `radar.py today`（终端看 Top 15）→ `radar.py web`（一键仪表盘）；卡片由宿主模型实时生成 5 桶中文介绍（是什么 / 能干什么 / 解决什么问题 / 同类竞品 / 何时选它），无需外部 LLM API key。主题/筛选参数：$ARGUMENTS。
