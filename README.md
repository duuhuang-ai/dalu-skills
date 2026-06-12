# dalu-skills

大路的 Claude Code Skills 合集。

## 安装

在 Claude Code 中运行：

```
/install-skill https://github.com/duuhuang-ai/dalu-skills/tree/main/{skill名}
```

例如：

```
/install-skill https://github.com/duuhuang-ai/dalu-skills/tree/main/xhs-blogger-report
```

```
/install-skill https://github.com/duuhuang-ai/dalu-skills/tree/main/feishu-base-pair-incremental-sync
```

## Skills 一览

### 飞书多维表格同步

**feishu-base-pair-incremental-sync** — 飞书多维表格原数据/新数据增量同步

用户提交一组或多组飞书多维表格「原数据 → 新数据」配对，并指定每组的核对字段后，先 dry-run 预检，再把原数据表中新增的记录追加到新数据表。

- 支持多组表批量增量同步
- 每组可独立指定核对字段，如更新时间、发布时间、录入时间
- 写入前强制 dry-run，用户确认后才执行追加
- 只追加，不删除、不覆盖、不修改字段结构
- 内置日期解析、链接去重、共有字段写入、写入后复查
- 依赖：lark-cli

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
| feishu-base-pair-incremental-sync | lark-cli |
| xhs-blogger-report | lark-cli、lark-base skill |
