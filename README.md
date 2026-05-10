# dalu-skills

大路的 Claude Code Skills 合集。

## 安装

在 Claude Code 中运行：

```
/install-skill https://github.com/alchaincyf/dalu-skills/tree/main/{skill名}
```

例如：

```
/install-skill https://github.com/alchaincyf/dalu-skills/tree/main/xhs-blogger-report
```

## Skills 一览

### 博主分析

**xhs-blogger-report** — 小红书博主账号分析报告

从飞书多维表格读取笔记数据，自动生成结构化 Markdown 分析报告。

- 6大分析维度：数据概览 / 爆款剖析 / 情绪词频 / 人设推断 / 策略建议 / 整合评分
- 动态字段映射，适配不同飞书表格结构
- 自动识别评论>点赞（咨询需求旺盛）、收藏>点赞（工具属性强）等关键信号
- 依赖：lark-cli + lark-base skill

## 依赖

| Skill | 依赖 |
|-------|------|
| xhs-blogger-report | lark-cli、lark-base skill |
