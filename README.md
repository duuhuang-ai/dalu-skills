# dalu-skills

大路的 Claude Code Skills 合集。

## 安装

在 Claude Code 中运行：

```
/install-skill https://github.com/duuhuang-ai/dalu-skills/tree/master/{skill名}
```

例如：

```
/install-skill https://github.com/duuhuang-ai/dalu-skills/tree/master/xhs-blogger-report
```

```
/install-skill https://github.com/duuhuang-ai/dalu-skills/tree/master/feishu-base-pair-incremental-sync
```

```
/install-skill https://github.com/duuhuang-ai/dalu-skills/tree/master/brok-prompt-generator
```

```
/install-skill https://github.com/duuhuang-ai/dalu-skills/tree/master/xhs-virtual-selection-assistant
```

## Skills 一览

### 提示词生成

**brok-prompt-generator** — BROK 框架提示词生成器

基于 BROK 框架（Background/背景、Role/角色、Objective/目标、Key Results & Constraints/关键结果与约束）生成、改写、优化、审查提示词。

- 三种模式：全新生成、改写优化、提示词审查
- 将模糊需求转化为具体可观测的标准
- 支持中文/英文提示词
- 输出包含 BROK 拆解、可复用提示词、使用说明

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

### 小红书虚拟选品

**xhs-virtual-selection-assistant** — 小红书虚拟产品选品分析助手

根据小红书虚拟商品链接或手动商品信息，判断商品是否值得跟进、如何改造成自己的产品，以及上架前需要规避的风险。

- 支持商品链接和手动商品信息两种输入方式
- 输出 推荐做 / 改造后再做 / 不建议做 的商家决策
- 拆解需求、价格、销量、差异化空间、交付难度和违规风险
- 给出 3 个可落地的改造方向和上架包装建议
- 默认生成可直接打开的独立 HTML 选品分析报告

## 依赖

| Skill | 依赖 |
|-------|------|
| brok-prompt-generator | 无 |
| feishu-base-pair-incremental-sync | lark-cli |
| xhs-blogger-report | lark-cli、lark-base skill |
| xhs-virtual-selection-assistant | 无 |
